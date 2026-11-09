from __future__ import annotations

import logging
import math
import sys
import time

from ..config import ConfigManager
from ..models import (
    BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION,
    CHAR_ATTR_ORDER,
    CHAR_MENU_NODES_HAS_POINTS,
    CHAR_MENU_NODES_NO_POINTS,
    CRAFTING_BUTTONS,
    CRAFTING_SLOTS,
    CREATE_CHAR_BUTTONS,
    DEATH_SCREEN_BUTTONS,
    DIFFICULTY_BUTTONS,
    INVENTORY_GRID_COLS,
    INVENTORY_GRID_ROWS,
    INVENTORY_TAB_COORDS,
    INVENTORY_UPPER_COORDS,
    KEYBOARD_GRID_COLS,
    KEYBOARD_GRID_ROWS,
    KEYBOARD_LAYOUT,
    LOAD_CHAR_BUTTONS,
    MERCHANT_GRID_COLS,
    MERCHANT_GRID_ROWS,
    MERCHANT_TABS_COORDS,
    OverlaySnapshot,
    PAUSE_BUTTONS,
    PET_GRID_COLS,
    PET_GRID_ROWS,
    PET_TAB_COORDS,
    PET_UPPER_COORDS,
    QUEST_ROW_COUNT,
    Rect,
    SETTINGS_BUTTONS,
    SETTINGS_DROPDOWNS,
    SHORTCUT_HUD_NODES,
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    STASH_GRID_COLS,
    STASH_GRID_ROWS,
    SharedOverlayState,
    TITLE_BUTTONS,
    bottom_hud_asset_path,
    bottom_hud_target_rect,
    char_attr_bridge_point,
    char_attr_pink_point,
    char_attr_point,
    char_create_button_point,
    char_menu_point,
    close_tab_vertices,
    controller_type_from_name,
    crafting_button_point,
    crafting_slot_point,
    death_screen_button_point,
    dialog_button_point,
    difficulty_menu_button_point,
    fishing_hook_point,
    hud_asset_path,
    hud_purple_button_point,
    hud_target_rect,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    load_char_button_point,
    merchant_slot_point,
    merchant_tab_point,
    modal_ok_point,
    panel_regions,
    panels_x_shift,
    pause_menu_button_point,
    pet_actions_asset_path,
    pet_actions_target_rect,
    pet_click_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    pet_inventory_upper_point,
    quest_abandon_point,
    quest_reward_point,
    quest_slot_point,
    settings_button_point,
    settings_dropdown_option_point,
    settings_slider_bounds,
    shortcut_config_info_asset_path,
    shortcut_config_info_tooltip_asset_path,
    shortcut_grid_cell_point,
    shortcut_info_node_point,
    shortcut_instruction_asset_path,
    shortcut_mask_asset_path,
    skill_bridge_col,
    skill_slot_pink_point,
    skill_slot_point,
    skill_spell_slot_point,
    skill_tab_point,
    stash_upper_slot_point,
    title_menu_button_point,
    virtual_keyboard_asset_path,
    virtual_keyboard_bg_asset_path,
    virtual_keyboard_grid_to_key,
    virtual_keyboard_highlight_filename,
    virtual_keyboard_info_label_filename,
    virtual_keyboard_key_cursor_point,
    virtual_keyboard_key_filename,
    virtual_keyboard_key_rect,
    virtual_keyboard_target_rect,
)
from ..native_overlay import (
    FrameChannel,
    frame_size,
)
from ..platform import (
    IS_WINDOWS,
    IS_LINUX,
    WindowLocator,
    make_overlay_clickthrough,
    position_overlay,
)
from PySide6.QtCore import (
    QEvent,
    QPointF,
    QRectF,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget
from pathlib import Path

from .radial import _radial_icons_dir, _radial_extra_hud_dir
from .keyboard import KeyboardInputSurface

log = logging.getLogger(__name__)



def _get_overlay_fn(name: str, fallback):
    mod = sys.modules.get("torchbridge.overlay")
    return getattr(mod, name, fallback)


class GameOverlayBase(QWidget):
    """Base do overlay: janela Qt transparente, timers e ciclo de vida."""

    def __init__(self, shared: SharedOverlayState, config: ConfigManager) -> None:
        super().__init__()
        self.shared = shared
        self.config = config
        # Controle do showEvent: aplica os estilos Win32 só na primeira exibição.
        self._native_styled = False
        self._last_rect = None
        self._last_raise = 0.0
        # Handles de plataformas Qt offscreen/minimal não são HWNDs, mesmo no Windows.
        self._native_windows = IS_WINDOWS and QGuiApplication.platformName() == "windows"
        self._wayland = None
        if IS_LINUX and QGuiApplication.platformName().startswith("wayland"):
            from ..wayland import Connection
            self._wayland = Connection()
        self._wayland_monitor = None
        self._wayland_monitor_check = 0.0
        self._wayland_rect = None
        self._channel: FrameChannel | None = None
        self._channel_pid: int | None = None
        self._channel_retry_at = 0.0
        self.backend_status = "Overlay: janela"
        self.setWindowTitle("TorchBridge Overlay")
        # FramelessWindowHint: sem borda/título; StaysOnTop: acima do jogo; Tool: some da barra de tarefas.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            # Transparente a cliques e sem foco (nunca rouba o input do jogo).
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        # Fundo transparente, sem receber eventos de mouse e sem ativar ao aparecer.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # Cache dos pixmaps do radial: carrega cada PNG uma única vez (desenhar a 60 FPS).
        self._radial_cache: dict[tuple[str, str], QPixmap] = {}
        # Cache das informações extras do menu radial (TB-16):
        self._radial_info_cache: dict[str, QPixmap] = {}
        self._radial_instruction_cache: dict[str, QPixmap] = {}
        # Animação do card superior de informações (fade e scale para entrada/saída; fade puro em crossfade):
        self._radial_top_info_current: str | None = None
        self._radial_top_info_target: str | None = None
        self._radial_top_info_progress: float = 0.0
        self._radial_top_info_anim_seconds: float = 0.18
        self._radial_top_info_last_time: float = time.monotonic()
        # Crossfade entre opções selecionadas:
        self._radial_top_info_prev: str | None = None
        self._radial_top_info_prev_opacity: float = 0.0
        self._radial_top_info_crossfade: bool = False
        self._radial_top_info_crossfade_progress: float = 0.0
        self._radial_top_info_crossfade_seconds: float = 0.14
        # Cache dos pixmaps do HUD inferior dos controles (Xbox, PlayStation, Nintendo).
        self._bottom_hud_cache: dict[str, QPixmap] = {}
        # Cache do pixmap de fundo do teclado virtual (assets/keyboard/background.png).
        self._keyboard_bg_pixmap: QPixmap | None = None
        # Cache de pixmaps das teclas do teclado virtual.
        self._keyboard_keys_cache: dict[str, QPixmap] = {}
        # Cache do backdrop com efeito spotlight para o modo de configuração de atalhos.
        self._cached_spotlight_backdrop: QImage | None = None
        self._cached_spotlight_size: tuple[int, int] | None = None
        # Cache da imagem de instruções de atalhos e progresso da animação (fade e slide-in).
        self._shortcut_instruction_cache: dict[str, QPixmap] = {}
        self._config_info_pixmap: QPixmap | None = None
        self._config_info_tooltip_cache: dict[str, QPixmap] = {}
        self._shortcut_tooltip_opacity = 0.0
        self._shortcut_anim_progress = 0.0
        self._shortcut_anim_last_time = time.monotonic()
        self._shortcut_anim_seconds = 0.35
        # Silhueta verde da HUD (modo de calibração): renderizada uma vez do SVG, se existir.
        # None = asset ausente (nada a desenhar).
        self._hud_pixmap = self._load_hud_pixmap()
        # Caixinha de pet actions (modo de calibração): referência visual no canto
        # superior esquerdo, renderizada uma vez do SVG, se existir. None = ausente.
        self._pet_actions_pixmap = self._load_pet_actions_pixmap()
        # Progresso da animação de entrada/saída do menu radial (0 = fechado, 1 = aberto).
        self._radial_progress = 0.0
        self._radial_last_time = time.monotonic()
        # Duração da animação do radial em cada direção (aparecer e sumir).
        self._radial_anim_seconds = 0.2
        # Progresso da animação da sublinha de pet (0 = tudo dentro do nó P, 1 = no lugar).
        # As bolinhas saem de DENTRO do nó P (todas no centro dele) e abrem em leque
        # até a fileira final, cada uma chegando 75ms depois da anterior (pá, pá, pá, pá).
        self._pet_submenu_progress = 0.0
        self._pet_submenu_last_time = time.monotonic()
        self._pet_submenu_anim_seconds = 0.3
        # Último nó P e marcador com a sublinha ABERTA — guardados para a animação de
        # SAÍDA: no tick em que a sublinha fecha, o snapshot já zera pet_submenu_open e
        # a seleção, então sem esses backups a saída não teria onde partir.
        self._last_pet_point: QPointF | None = None
        self._last_pet_selection: int | None = None
        # Progresso da animação do teclado virtual (0 = fechado, 1 = aberto).
        self._virtual_keyboard_progress = 0.0
        self._virtual_keyboard_last_time = time.monotonic()
        self._virtual_keyboard_anim_seconds = 0.25
        self._last_virtual_keyboard_target = "character_name"
        # Animação suave da tecla pressionada no teclado virtual (estilo CSS)
        self._kb_press_anim_key: str | None = None
        self._kb_press_anim_start: float = 0.0
        self._kb_press_anim_id: int = 0
        self._keyboard_input = KeyboardInputSurface(self.shared, self)
        if self._wayland is not None:
            pointer_path = virtual_keyboard_asset_path("pointer.cur")
            if pointer_path is not None and pointer_path.is_file():
                self._wayland.set_cursor(QImage(str(pointer_path)))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        # Redesenho a cada 16 ms (~60 FPS); o motor publica o estado a 120 Hz.
        self._timer.start(16)

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        if self._native_windows and not self._native_styled:
            _get_overlay_fn("make_overlay_clickthrough", make_overlay_clickthrough)(int(self.winId()))
            self._native_styled = True

    def event(self, event) -> bool:  # type: ignore[no-untyped-def]
        if event.type() == QEvent.Type.WinIdChange:
            self._native_styled = False
            self._last_rect = None
            self._last_raise = 0.0
        return super().event(event)

    def shutdown(self) -> None:
        self._timer.stop()
        if self._wayland is not None:
            self._wayland.close()
            self._wayland = None
        self._keyboard_input.hide()
        self.hide()
        if self._channel is not None:
            self._channel.close()
            self._channel = None

    def _sync_channel(self, snapshot: OverlaySnapshot) -> None:
        pid = snapshot.game_pid if snapshot.game_found else None
        if pid != self._channel_pid:
            if self._channel is not None:
                self._channel.close()
            self._channel = None
            self._channel_pid = pid
            self._channel_retry_at = 0.0
        if self._native_windows and pid and self._channel is None:
            if time.monotonic() < self._channel_retry_at:
                return
            try:
                self._channel = FrameChannel(pid)
            except OSError:
                log.exception("Não foi possível abrir o canal do overlay D3D9")
                self._channel_retry_at = time.monotonic() + 5.0

    def _render_native(self, snapshot: OverlaySnapshot, max_width: int, max_height: int) -> QImage:
        rect = snapshot.game_rect
        width, height = frame_size(rect.width, rect.height, max_width, max_height)
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            raise MemoryError("Sem memória para a imagem do overlay fullscreen")
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            painter.scale(width / rect.width, height / rect.height)
            self._paint_overlay(painter, snapshot)
        finally:
            painter.end()
        return image

    def _refresh(self) -> None:
        snapshot = self.shared.get()
        # As animações avançam pelo tempo real do tick, independente de visibilidade.
        # A da sublinha é CHAMADA DIRETO AQUI (não dentro da da roda): o atalho de
        # "chegou ao alvo" do radial faz return cedo e congelaria a da sublinha.
        self._tick_radial_anim(snapshot)
        self._tick_radial_top_info_anim(snapshot)
        self._tick_pet_submenu_anim(snapshot)
        self._tick_virtual_keyboard_anim(snapshot)
        self._tick_shortcut_mode_anim(snapshot)
        rect = snapshot.game_rect
        # Só desenha com overlay habilitado, jogo presente e janela válida.
        should_show = snapshot.enabled and snapshot.game_found and snapshot.game_active and rect.valid
        # Revalida o foco na UI: um snapshot atrasado não pode cobrir outro aplicativo.
        if should_show and (self._native_windows or self._wayland is not None) and snapshot.game_hwnd:
            should_show = WindowLocator.is_foreground(snapshot.game_hwnd)
        kb_active = snapshot.virtual_keyboard_open and self._virtual_keyboard_progress >= 1.0
        if self._wayland is not None:
            try:
                self._refresh_wayland(snapshot, should_show, kb_active)
            except (OSError, ValueError, MemoryError):
                log.exception("Falha no overlay Wayland")
                self._wayland.hide()
                self._wayland_monitor = None
                self.backend_status = "Overlay: erro Wayland; consulte o log"
            return
        if should_show and kb_active:
            target = snapshot.virtual_keyboard_target or self._last_virtual_keyboard_target or "character_name"
            geometry = virtual_keyboard_target_rect(rect, target)
            self._keyboard_input.physical_rect = Rect(*geometry)
            if not self._native_windows:
                self._keyboard_input.setGeometry(*geometry)
            self._keyboard_input.show()
            if self._native_windows:
                _get_overlay_fn("position_overlay", position_overlay)(int(self._keyboard_input.winId()), Rect(*geometry))
                _get_overlay_fn("make_overlay_clickthrough", make_overlay_clickthrough)(int(self._keyboard_input.winId()), interactive=True)
            self._keyboard_input.raise_()
        else:
            self._keyboard_input.hide()
        self._sync_channel(snapshot)
        if self._channel is not None:
            try:
                status = self._channel.status()
                if should_show and status.connected and status.fullscreen:
                    self.hide()
                    self._last_rect = None
                    image = self._render_native(snapshot, status.max_width, status.max_height)
                    self._channel.publish(image.constBits(), image.width(), image.height(), image.bytesPerLine())
                    self.backend_status = "Overlay: Direct3D 9 (fullscreen)"
                    return
                self._channel.clear()
            except (OSError, ValueError, MemoryError):
                log.exception("Falha ao publicar o overlay D3D9; nova tentativa em 5 s")
                self._channel.close()
                self._channel = None
                self._channel_retry_at = time.monotonic() + 5.0
        self.backend_status = "Overlay: janela"
        if should_show:
            geometry = (rect.left, rect.top, rect.width, rect.height)
            if not self._native_windows and geometry != self._last_rect:
                self.setGeometry(*geometry)
                self._last_rect = geometry
            newly_visible = not self.isVisible()
            if not self.isVisible():
                self.show()
            now = time.monotonic()
            if self._native_windows:
                if not self._native_styled:
                    _get_overlay_fn("make_overlay_clickthrough", make_overlay_clickthrough)(int(self.winId()))
                    self._native_styled = True
                if newly_visible or geometry != self._last_rect or now - self._last_raise >= 0.25:
                    if _get_overlay_fn("position_overlay", position_overlay)(int(self.winId()), rect):
                        self._last_rect = geometry
                    self._last_raise = now
            self.update()
        # Sem razão de aparecer: esconde para não sobrar janela órfã na tela.
        elif self.isVisible():
            self.hide()

    def _refresh_wayland(self, snapshot: OverlaySnapshot, should_show: bool, kb_active: bool) -> None:
        """Render the shared Qt painter into a focusless layer above fullscreen.

        Geometry stays in compositor pixels. Rasterizing at ceil(output scale)
        keeps fractional-scale monitors sharp without changing engine coordinates.
        """
        import math
        rect = snapshot.game_rect
        self._keyboard_input.hide()
        self.hide()  # QWidget is only the painter/controller on this backend.
        for kind, x, y in self._wayland.events():
            if should_show and kb_active:
                self.shared.keyboard_event(kind, rect.left + x, rect.top + y)
        if not should_show:
            self._wayland.hide()
            self._wayland_monitor = None
            return
        now = time.monotonic()
        if (self._wayland_monitor is None or rect != self._wayland_rect
                or now - self._wayland_monitor_check >= 0.25):
            self._wayland_monitor = WindowLocator.monitor(snapshot.game_hwnd)
            self._wayland_monitor_check = now
        monitor = self._wayland_monitor
        if monitor is None:
            self._wayland.hide()
            return
        scale = max(1, math.ceil(monitor["scale"]))
        image = QImage(rect.width * scale, rect.height * scale, QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():
            raise MemoryError("Sem memória para o overlay Wayland")
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            painter.scale(scale, scale)
            self._paint_overlay(painter, snapshot)
        finally:
            painter.end()
        keyboard = None
        if kb_active:
            target = snapshot.virtual_keyboard_target or self._last_virtual_keyboard_target or "character_name"
            keyboard = Rect(*virtual_keyboard_target_rect(rect, target))
        self._wayland.present(image, monitor, rect, keyboard)
        self._wayland_rect = rect
        self.backend_status = "Overlay: Wayland (janela e fullscreen)"

    @staticmethod
    # Fonte padrão do overlay, com tamanho e peso.
    def _font(size: int, bold: bool = False) -> QFont:
        font = QFont("Segoe UI", size)
        font.setBold(bold)
        return font

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        del event
        painter = QPainter(self)
        try:
            # Os modelos e SendInput usam pixels físicos, Qt usa pixels lógicos.
            ratio = self.devicePixelRatioF()
            painter.scale(1.0 / ratio, 1.0 / ratio)
            self._paint_overlay(painter, self.shared.get())
        finally:
            painter.end()

    def _paint_overlay(self, painter: QPainter, snapshot: OverlaySnapshot) -> None:
        scale = float(self.config.get()["overlay"]["scale"])
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._draw_shortcut_spotlight(painter, snapshot)
        self._draw_shortcut_nodes(painter, snapshot)
        self._draw_shortcut_instruction(painter, snapshot)
        self._draw_bottom_hud(painter, snapshot)
        self._draw_aim(painter, snapshot, scale)
        self._draw_calibration(painter, snapshot, scale)
        self._draw_virtual_keyboard(painter, snapshot, scale)
        self._draw_radial(painter, snapshot, scale)
        self._draw_mode_badge(painter, snapshot, scale)
        # Desenhado antes do toast para o aviso temporário cobrir o indicador quando sobreposto.
        self._draw_active_panels(painter, snapshot, scale)
        self._draw_toast(painter, snapshot, scale)
