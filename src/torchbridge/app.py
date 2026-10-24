# Ponto de entrada da aplicação GUI: cria a bandeja do Windows, o overlay Qt,
# o motor de entrada (thread) e liga o menu/sinais de encerramento.
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import sys


# Linha de comando: permite um perfil alternativo (útil em testes).
def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controle para Torchlight PC")
    parser.add_argument("--perfil", type=Path, help="Caminho de um perfil JSON alternativo")
    parser.add_argument("--fullscreen-setup", choices=("install", "remove"),
                        help="Instala ou remove o suporte a fullscreen")
    return parser.parse_args()


# Log técnico em %APPDATA%\TorchBridge\torchbridge.log.
def _configure_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=directory / "torchbridge.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def _add_fullscreen_actions(menu) -> None:
    from .fullscreen import configure_dialog

    install_action = menu.addAction("Instalar suporte a fullscreen...")
    install_action.triggered.connect(lambda _checked=False: configure_dialog())
    remove_action = menu.addAction("Remover suporte a fullscreen...")
    remove_action.triggered.connect(lambda _checked=False: configure_dialog(uninstall=True))


def _populate_controller_menu(menu, config, devices) -> None:
    from PySide6.QtGui import QActionGroup

    menu.clear()
    previous_group = getattr(menu, "_selection_group", None)
    if previous_group is not None:
        previous_group.deleteLater()
    group = QActionGroup(menu)
    menu._selection_group = group
    selected = config.get()["input"]["device_guid"]
    choices = [("", "Selecionar automaticamente"), *dict.fromkeys(devices)]
    if selected and selected not in {guid for guid, _ in devices}:
        choices.append((selected, "Controle selecionado (desconectado)"))
    for guid, name in choices:
        action = menu.addAction(name)
        action.setCheckable(True)
        action.setChecked(guid == selected)
        group.addAction(action)
        action.triggered.connect(lambda _checked=False, value=guid: config.select_controller(value))


# Orquestra tudo: valida SO, monta Qt, inicia o motor e roda o event loop até Sair.
def main() -> int:
    # O TorchBridge depende do SendInput; fora do Windows não faz sentido rodar.
    if os.name != "nt":
        print("TorchBridge requer Windows 10 ou Windows 11.", file=sys.stderr)
        return 2

    args = _arguments()
    # SDL lê o controle mesmo com o Torchlight em primeiro plano.
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from .config import ConfigManager, user_config_dir
    from .engine import BridgeEngine
    from .models import SharedOverlayState, app_icon_path
    from .overlay import GameOverlay
    from .win32 import SingleInstance, enable_dpi_awareness, show_information

    # Antes de criar janelas: DPI awareness para as coordenadas casarem com o jogo.
    enable_dpi_awareness()
    if args.fullscreen_setup:
        from .fullscreen import configure_dialog
        return configure_dialog(uninstall=args.fullscreen_setup == "remove")
    # Mutex: uma única instância ativa por sessão.
    single_instance = SingleInstance()
    # Outra instância viva: avisa e encerra esta (evita abrir duas vezes).
    if single_instance.already_running:
        show_information("TorchBridge", "O TorchBridge já está em execução perto do relógio do Windows.")
        single_instance.close()
        return 0
    # Carrega/valida o perfil; o log fica na pasta padrão do usuário.
    config = ConfigManager(args.perfil)
    _configure_logging(user_config_dir())

    # Aplicação Qt; sys.argv[:1] evita que o Qt interprete argumentos nossos.
    app = QApplication(sys.argv[:1])
    app.setApplicationName("TorchBridge")
    # Não fecha ao esconder o overlay — vive na bandeja até 'Sair'.
    app.setQuitOnLastWindowClosed(False)

    # Ícone fallback desenhado em código caso os assets PNG estejam ausentes.
    fallback_pixmap = QPixmap(64, 64)
    fallback_pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(fallback_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(7, 24, 34))
    painter.setPen(QColor(75, 222, 247))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    painter.setPen(QColor(238, 250, 252))
    painter.drawText(fallback_pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "TB")
    painter.end()
    fallback_icon = QIcon(fallback_pixmap)

    # Cache dos ícones da bandeja por estado: (ativo, calibração) -> QIcon.
    icon_cache: dict[tuple[bool, bool], QIcon] = {}

    def get_app_icon(ativo: bool, calibration: bool) -> QIcon:
        key = (bool(ativo), bool(calibration))
        if key in icon_cache:
            return icon_cache[key]
        path = app_icon_path(ativo, calibration)
        if path is not None and path.is_file():
            ico = QIcon(str(path))
            if not ico.isNull():
                icon_cache[key] = ico
                return ico
        return fallback_icon

    initial_calib = bool(config.get()["overlay"].get("show_calibration", False))
    current_icon = get_app_icon(True, initial_calib)
    app.setWindowIcon(current_icon)

    # Estado compartilhado motor ↔ overlay (ponte thread-safe).
    shared = SharedOverlayState()
    # Motor de entrada (thread de 120 Hz).
    engine = BridgeEngine(config, shared)

    # Filtro nativo do Windows: detecta conexão e desconexão de controles em tempo real (USB / Bluetooth).
    device_filter = None
    device_receiver = None
    if sys.platform == "win32":
        from ctypes import wintypes
        from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
        from PySide6.QtWidgets import QWidget

        WM_DEVICECHANGE = 0x0219

        class DeviceChangeFilter(QAbstractNativeEventFilter):
            def __init__(self, on_change) -> None:
                super().__init__()
                self._on_change = on_change
                self._debounce_timer = QTimer()
                self._debounce_timer.setSingleShot(True)
                self._debounce_timer.timeout.connect(self._fire)
                self._handshake_timer = QTimer()
                self._handshake_timer.setSingleShot(True)
                self._handshake_timer.timeout.connect(self._fire)

            def _fire(self) -> None:
                self._on_change()

            def nativeEventFilter(self, event_type, message):
                try:
                    if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
                        msg = wintypes.MSG.from_address(int(message))
                        if msg.message == WM_DEVICECHANGE:
                            # Debounce de 250ms para evitar tempestade de mensagens ao espetar USB
                            self._debounce_timer.start(250)
                            # Segundo disparo a 900ms para aguardar o handshake do Bluetooth
                            self._handshake_timer.start(900)
                except Exception:
                    pass
                return False, 0

        # Garante que a aplicação possua um HWND Win32 ativo para receber broadcasts do sistema
        device_receiver = QWidget()
        _ = device_receiver.winId()

        device_filter = DeviceChangeFilter(engine.trigger_rescan)
        app.installNativeEventFilter(device_filter)

    # Overlay Qt; a exibição é controlada pelo próprio _refresh conforme o jogo.
    overlay = GameOverlay(shared, config)
    # Ícone da bandeja: pausa, perfil, recarga e saída.
    tray = QSystemTrayIcon(current_icon, app)
    tray.setToolTip("TorchBridge — aguardando o Torchlight")

    _last_icon_state: tuple[bool, bool] = (True, initial_calib)

    def update_tray_icon() -> None:
        nonlocal _last_icon_state
        ativo = engine.is_enabled()
        calib = bool(config.get()["overlay"].get("show_calibration", False))
        state_key = (ativo, calib)
        if state_key == _last_icon_state:
            return
        _last_icon_state = state_key
        new_icon = get_app_icon(ativo, calib)
        tray.setIcon(new_icon)
        app.setWindowIcon(new_icon)

    menu = QMenu()
    # Checkbox 'Ativado': liga/desliga o envio de comandos.
    enabled_action = menu.addAction("Ativado")
    enabled_action.setCheckable(True)
    enabled_action.setChecked(True)

    def toggle_enabled(checked: bool) -> None:
        engine.set_enabled(checked)
        update_tray_icon()

    enabled_action.triggered.connect(toggle_enabled)

    # Checkbox 'Modo de calibração': liga/desliga o desenho das marcações de calibração no overlay.
    calib_action = menu.addAction("Modo de calibração")
    calib_action.setCheckable(True)
    calib_action.setChecked(initial_calib)

    def toggle_calibration(checked: bool) -> None:
        config.set_show_calibration(checked)
        update_tray_icon()
        overlay.update()
        shared.toast("Calibração ativada" if checked else "Calibração desativada")

    calib_action.triggered.connect(toggle_calibration)

    # Mantém os checkboxes sincronizados caso o perfil seja alterado externamente.
    def sync_menu_state() -> None:
        enabled_action.setChecked(engine.is_enabled())
        calib_action.setChecked(config.get()["overlay"].get("show_calibration", False))
        update_tray_icon()

    menu.aboutToShow.connect(sync_menu_state)

    open_profile_action = menu.addAction("Abrir perfil de controles")

    # Abre o perfil.json no editor padrão do Windows.
    def open_profile() -> None:
        os.startfile(config.path)  # type: ignore[attr-defined]

    open_profile_action.triggered.connect(open_profile)
    reload_action = menu.addAction("Recarregar perfil")

    def reload_profile() -> None:
        config.reload(force=True)
        sync_menu_state()
        update_tray_icon()
        overlay.update()
        shared.toast(config.last_error or "Perfil recarregado")

    reload_action.triggered.connect(reload_profile)
    menu.addSeparator()
    controller_menu = menu.addMenu("Controle")
    controller_menu.aboutToShow.connect(
        lambda: _populate_controller_menu(controller_menu, config, shared.get().controller_devices)
    )
    _add_fullscreen_actions(menu)
    menu.addSeparator()
    exit_action = menu.addAction("Sair")
    # 'Sair' encerra o event loop → passa pelo cleanup.
    exit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.show()
    # Aviso inicial da bandeja ao iniciar.
    tray.showMessage(
        "TorchBridge iniciado",
        "Conecte o controle e abra o Torchlight.",
        QSystemTrayIcon.MessageIcon.Information,
        2600,
    )

    tooltip_timer = QTimer()
    last_engine_error = ""

    # Dica do ícone e estado atualizados a cada 500 ms.
    def update_tooltip() -> None:
        nonlocal last_engine_error
        update_tray_icon()
        state = shared.get()
        if state.engine_error:
            tray.setToolTip(f"TorchBridge — {state.engine_error}")
            if state.engine_error != last_engine_error:
                tray.showMessage("TorchBridge", state.engine_error, QSystemTrayIcon.MessageIcon.Critical)
                last_engine_error = state.engine_error
            return
        if config.last_error:
            tray.setToolTip(f"TorchBridge — {config.last_error}")
            return
        # Caso completo: controle + jogo (mostra se está ativo ou em segundo plano).
        if state.controller_connected and state.game_found:
            suffix = "ativo" if state.game_active else "jogo em segundo plano"
            tray.setToolTip(f"TorchBridge — {state.controller_name} — {suffix}\n{overlay.backend_status}")
        elif state.controller_connected:
            tray.setToolTip(f"TorchBridge — {state.controller_name} — aguardando Torchlight")
        else:
            tray.setToolTip("TorchBridge — aguardando controle")

    tooltip_timer.timeout.connect(update_tooltip)
    tooltip_timer.start(500)

    # cleanup idempotente: roda uma única vez (app.quit e aboutToQuit podem chamar).
    cleaned = False

    # Desligamento ordenado: para o motor, espera a thread, esconde a bandeja, solta o mutex.
    def cleanup() -> None:
        nonlocal cleaned
        if cleaned:
            return
        cleaned = True
        overlay.shutdown()
        engine.stop()
        # Espera o loop encerrar (limitado a 3 s para não travar a saída).
        engine.join(timeout=3.0)
        tray.hide()
        single_instance.close()

    # Garante a limpeza em qualquer caminho de saída.
    app.aboutToQuit.connect(cleanup)
    # Ctrl+C no terminal encerra a UI de forma limpa.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # No Windows o Python só roda handlers de sinal quando o loop acorda; este timer de 250 ms garante isso.
    keep_signals_alive = QTimer()
    keep_signals_alive.timeout.connect(lambda: None)
    keep_signals_alive.start(250)

    # A thread do motor começa aqui; app.exec() roda até 'Sair'.
    engine.start()
    # Event loop Qt (bandeja + overlay) até o usuário sair.
    result = app.exec()
    cleanup()
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
