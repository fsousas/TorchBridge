"""Testes unitários para mapeamento, coordenadas, overlay e navegação da tela de Configurações (Settings)."""
import unittest
from unittest.mock import MagicMock

from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    SETTINGS_BUTTONS,
    SETTINGS_BUTTON_COORDS,
    SETTINGS_DROPDOWNS,
    ControllerState,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    settings_button_point,
    settings_dropdown_option_point,
    settings_slider_bounds,
)
from torchbridge.overlay import GameOverlay


class FakeInjector:
    def __init__(self) -> None:
        self.moved: list[tuple[int, int]] = []
        self.cursor = (500, 500)
        self.buttons: dict[str, bool] = {}
        self.events: list[tuple] = []

    def move(self, x: int, y: int) -> bool:
        self.moved.append((x, y))
        self.cursor = (x, y)
        self.events.append(("move", x, y))
        return True

    def cursor_position(self) -> tuple[int, int]:
        return self.cursor

    def mouse_button(self, button: str, down: bool) -> bool:
        self.buttons[button] = down
        self.events.append(("mouse", button, down))
        return True

    def key(self, name: str, down: bool) -> bool:
        self.buttons[name] = down
        return True

    def key_pressed(self, name: str) -> bool:
        return self.buttons.get(name, False)

    def tap(self, name: str) -> bool:
        self.events.append(("tap", name))
        return True


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_button_coordinates_base_1024x768(self):
        """Valida que todos os botões e marcadores da tela principal batem pixel a pixel com a calibração."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Row 1 (y=132)
        self.assertEqual(settings_button_point(rect, "row1_col1"), (238, 132))  # Amarelo (default)
        self.assertEqual(settings_button_point(rect, "row1_col2"), (437, 132))  # Verde
        self.assertEqual(settings_button_point(rect, "row1_col3"), (636, 132))  # Verde

        # Row 2 (y=184)
        self.assertEqual(settings_button_point(rect, "row2_col1"), (238, 184))  # Verde
        self.assertEqual(settings_button_point(rect, "row2_col2"), (437, 184))  # Verde
        self.assertEqual(settings_button_point(rect, "row2_col3"), (636, 184))  # Verde

        # Row 3 (y=247) - Dropdowns Rosa
        self.assertEqual(settings_button_point(rect, "resolution"), (398, 247))
        self.assertEqual(settings_button_point(rect, "shadows"), (800, 247))

        # Row 4 (y=344..346) - Music Volume no topo
        # Sliders: extremidade esquerda (0%) = 228, direita (100%) = 447
        self.assertEqual(settings_button_point(rect, "music_slider", 0.0), (228, 344))
        self.assertEqual(settings_button_point(rect, "music_slider", 1.0), (447, 344))
        self.assertEqual(settings_button_point(rect, "music_mute"), (486, 346))
        self.assertEqual(settings_button_point(rect, "particle_detail"), (800, 346))

        # Row 5 (y=401)
        self.assertEqual(settings_button_point(rect, "row5_col3"), (636, 401))

        # Row 6 (y=444..448) - Sound Volume embaixo
        self.assertEqual(settings_button_point(rect, "sound_slider", 0.0), (228, 445))
        self.assertEqual(settings_button_point(rect, "sound_slider", 1.0), (447, 445))
        self.assertEqual(settings_button_point(rect, "sound_mute"), (486, 448))
        self.assertEqual(settings_button_point(rect, "row6_col3"), (636, 444))

        # Row 7 (y=488)
        self.assertEqual(settings_button_point(rect, "row7_col1"), (238, 488))
        self.assertEqual(settings_button_point(rect, "row7_col3"), (636, 488))

        # Barra inferior (y=552)
        self.assertEqual(settings_button_point(rect, "cancel"), (465, 552))
        self.assertEqual(settings_button_point(rect, "apply"), (657, 552))

        # Limites ciano dos sliders
        (m1, m2) = settings_slider_bounds(rect, is_music=True)
        self.assertEqual(m1, (228, 344))
        self.assertEqual(m2, (447, 344))

        (s1, s2) = settings_slider_bounds(rect, is_music=False)
        self.assertEqual(s1, (228, 445))
        self.assertEqual(s2, (447, 445))

    def test_dropdown_options_coordinates(self):
        """Valida as coordenadas das opções nos 3 menus dropdown."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Shadows: 6 opções (Opção 0 amarela em 780, 293)
        self.assertEqual(settings_dropdown_option_point(rect, "shadows", 0), (780, 293))
        self.assertEqual(settings_dropdown_option_point(rect, "shadows", 1), (780, 310))
        self.assertEqual(settings_dropdown_option_point(rect, "shadows", 5), (780, 380))

        # Resolution: 18 opções (Opção 0 amarela em 385, 293)
        self.assertEqual(settings_dropdown_option_point(rect, "resolution", 0), (385, 293))
        self.assertEqual(settings_dropdown_option_point(rect, "resolution", 1), (385, 310))
        self.assertEqual(settings_dropdown_option_point(rect, "resolution", 17), (385, 574))

        # Particle Detail: 3 opções (Opção 0 amarela em 785, 396)
        self.assertEqual(settings_dropdown_option_point(rect, "particle_detail", 0), (785, 396))
        self.assertEqual(settings_dropdown_option_point(rect, "particle_detail", 1), (785, 413))
        self.assertEqual(settings_dropdown_option_point(rect, "particle_detail", 2), (785, 431))

    def test_settings_initialization_moves_to_default_yellow(self):
        """Valida que ao abrir a tela de configurações, o cursor inicializa no ponto amarelo (row1_col1)."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        # Abre tela de configurações
        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_desc="Configurações (Settings)",
            open_menus=["Configurações"],
            sound_volume=0.5,
            music_volume=0.5,
        )

        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        self.assertEqual(engine._settings_focus, "row1_col1")
        self.assertEqual(injector.cursor, (238, 132))
        self.assertEqual(shared.get().settings_focus, "row1_col1")
        self.assertFalse(shared.get().settings_slider_dragging)
        self.assertIsNone(shared.get().settings_dropdown)

    def test_dpad_navigation_grid(self):
        """Valida a navegação D-pad através do grafo de posições na tela de configurações."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            open_menus=["Configurações"],
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        # 1. D-pad Right: row1_col1 -> row1_col2 -> row1_col3
        dpad_r = ControllerState(buttons={"dpad_right"})
        engine._previous = empty
        engine._process_active(hub, dpad_r, rect, cfg, 0.1, 0.05)
        self.assertEqual(engine._settings_focus, "row1_col2")
        self.assertEqual(injector.cursor, (437, 132))

        engine._previous = empty
        engine._process_active(hub, dpad_r, rect, cfg, 0.2, 0.05)
        self.assertEqual(engine._settings_focus, "row1_col3")
        self.assertEqual(injector.cursor, (636, 132))

        # 2. D-pad Down: row1_col3 -> row2_col3 -> shadows -> particle_detail -> row5_col3 -> row6_col3 -> row7_col3 -> apply
        dpad_d = ControllerState(buttons={"dpad_down"})
        engine._previous = empty
        engine._process_active(hub, dpad_d, rect, cfg, 0.3, 0.05)
        self.assertEqual(engine._settings_focus, "row2_col3")
        self.assertEqual(injector.cursor, (636, 184))

        engine._previous = empty
        engine._process_active(hub, dpad_d, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._settings_focus, "shadows")
        self.assertEqual(injector.cursor, (800, 247))

        engine._previous = empty
        engine._process_active(hub, dpad_d, rect, cfg, 0.5, 0.05)
        self.assertEqual(engine._settings_focus, "particle_detail")
        self.assertEqual(injector.cursor, (800, 346))

        # 3. D-pad Left: particle_detail -> music_mute -> music_slider
        dpad_l = ControllerState(buttons={"dpad_left"})
        engine._previous = empty
        engine._process_active(hub, dpad_l, rect, cfg, 0.6, 0.05)
        self.assertEqual(engine._settings_focus, "music_mute")
        self.assertEqual(injector.cursor, (486, 346))

        engine._previous = empty
        engine._process_active(hub, dpad_l, rect, cfg, 0.7, 0.05)
        self.assertEqual(engine._settings_focus, "music_slider")

    def test_slider_hold_and_adjust_volume(self):
        """Valida o comportamento OBS 1 do slider: segurar clique com A/X, ajustar com D-pad, soltar com B/O."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            open_menus=["Configurações"],
            sound_volume=0.5,
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        # Coloca foco no sound_slider
        engine._settings_focus = "sound_slider"
        engine._settings_sound_vol = 0.5
        engine._settings_slider_dragging = False

        # 1. Pressiona A sobre o sound_slider -> Inicia dragging com mouse down
        btn_a = ControllerState(buttons={"a"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_a, rect, cfg, 0.1, 0.05)

        self.assertTrue(engine._settings_slider_dragging)
        self.assertTrue(shared.get().settings_slider_dragging)
        self.assertIn(("mouse", "left", True), injector.events)

        # 2. D-pad Right incrementa volume
        dpad_r = ControllerState(buttons={"dpad_right"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, dpad_r, rect, cfg, 0.2, 0.05)

        self.assertAlmostEqual(engine._settings_sound_vol, 0.55, places=2)
        # Cursor moveu para a direita
        expected_x, expected_y = settings_button_point(rect, "sound_slider", 0.55)
        self.assertEqual(injector.cursor, (expected_x, expected_y))
        self.assertTrue(engine._settings_slider_dragging)

        # 3. Pressiona B -> Solta o clique e encerra o dragging
        btn_b = ControllerState(buttons={"b"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_b, rect, cfg, 0.3, 0.05)

        self.assertFalse(engine._settings_slider_dragging)
        self.assertFalse(shared.get().settings_slider_dragging)
        self.assertIn(("mouse", "left", False), injector.events)

    def test_slider_press_x_and_analog_stick(self):
        """Valida caso real reportado pelo usuário: apertar X uma vez, soltar X, mover analog/dpad e conferir que left-click é mantido e right-click não vaza."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_desc="Configurações (Settings)",
            open_menus=["Configurações"],
            music_volume=0.4,
            sound_volume=0.0,
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        # Foco no music_slider
        engine._settings_focus = "music_slider"
        engine._settings_music_vol = 0.4
        engine._settings_slider_dragging = False

        # 1. Aperta X uma vez sobre o music_slider
        btn_x = ControllerState(buttons={"x"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_x, rect, cfg, 0.1, 0.05)

        # Deve segurar clique esquerdo
        self.assertTrue(engine._settings_slider_dragging)
        self.assertTrue(shared.get().settings_slider_dragging)
        self.assertIn(("mouse", "left", True), injector.events)
        # NUNCA deve vazar clique direito!
        self.assertNotIn(("mouse", "right", True), injector.events)

        # 2. Solta X (usuário soltou o botão físico)
        engine._previous = btn_x
        injector.events.clear()
        engine._process_active(hub, empty, rect, cfg, 0.15, 0.05)

        # O estado de arrastar e o clique devem continuar ativos!
        self.assertTrue(engine._settings_slider_dragging)
        self.assertNotIn(("mouse", "left", False), injector.events)
        self.assertNotIn(("mouse", "right", True), injector.events)

        # 3. Move o analógico esquerdo para a direita (lx = 0.8)
        stick_r = ControllerState(lx=0.8)
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, stick_r, rect, cfg, 0.25, 0.05)

        self.assertAlmostEqual(engine._settings_music_vol, 0.45, places=2)
        expected_x, expected_y = settings_button_point(rect, "music_slider", 0.45)
        self.assertEqual(injector.cursor, (expected_x, expected_y))
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertNotIn(("mouse", "right", True), injector.events)
        self.assertTrue(engine._settings_slider_dragging)

        # 4. Aperta B para liberar
        btn_b = ControllerState(buttons={"b"})
        engine._previous = stick_r
        injector.events.clear()
        engine._process_active(hub, btn_b, rect, cfg, 0.35, 0.05)

        self.assertFalse(engine._settings_slider_dragging)
        self.assertFalse(shared.get().settings_slider_dragging)
        self.assertIn(("mouse", "left", False), injector.events)


    def test_dropdown_open_select_and_cancel(self):
        """Valida o comportamento OBS 2 dos dropdowns: abrir com A/X, navegar opções, confirmar com A e cancelar com B."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            open_menus=["Configurações"],
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        # 1. Posiciona no botão rosa de Shadows
        engine._settings_focus = "shadows"

        # 2. Pressiona A em Shadows -> Clica no botão rosa e move cursor pro amarelo (opção 0)
        btn_a = ControllerState(buttons={"a"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_a, rect, cfg, 0.1, 0.05)

        self.assertEqual(engine._settings_dropdown, "shadows")
        self.assertEqual(engine._settings_dropdown_idx, 0)
        self.assertEqual(shared.get().settings_dropdown, "shadows")
        self.assertEqual(injector.cursor, (780, 293))  # Opção 0 amarela
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

        # 3. D-pad Down -> Move para a opção 1
        dpad_d = ControllerState(buttons={"dpad_down"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, dpad_d, rect, cfg, 0.2, 0.05)

        self.assertEqual(engine._settings_dropdown_idx, 1)
        self.assertEqual(injector.cursor, (780, 310))  # Opção 1

        # 4. Pressiona A na opção 1 -> Clica na opção e volta o cursor pro botão rosa
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_a, rect, cfg, 0.3, 0.05)

        self.assertIsNone(engine._settings_dropdown)
        self.assertEqual(engine._settings_focus, "shadows")
        self.assertEqual(injector.cursor, (800, 247))  # Botão rosa
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

        # 5. Testa cancelar com B: abre dropdown de novo e aperta B
        engine._previous = empty
        engine._process_active(hub, btn_a, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._settings_dropdown, "shadows")

        btn_b = ControllerState(buttons={"b"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_b, rect, cfg, 0.5, 0.05)

        self.assertIsNone(engine._settings_dropdown)
        self.assertEqual(engine._settings_focus, "shadows")
        self.assertEqual(injector.cursor, (800, 247))
        # Clica no botão rosa para fechar o dropdown no jogo
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

    def test_main_screen_cancel_button(self):
        """Valida que na tela principal de configurações, pressionar B/O move para o botão Cancelar e clica."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            open_menus=["Configurações"],
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        btn_b = ControllerState(buttons={"b"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_b, rect, cfg, 0.1, 0.05)

        self.assertEqual(engine._settings_focus, "cancel")
        self.assertEqual(injector.cursor, (465, 552))
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

    def test_overlay_renders_settings_calibration(self):
        """Valida que o overlay renderiza sem exceções em modo calibração na tela principal e em dropdown."""
        shared = SharedOverlayState()
        config = ConfigManager()
        overlay = GameOverlay(shared, config)
        rect = Rect(left=0, top=0, width=1024, height=768)

        # 1. Tela principal com calibração ativa
        snapshot_main = OverlaySnapshot(
            game_rect=rect,
            mode="calibration",
            memory_state_desc="Configurações (Settings)",
            memory_open_menus=["Configurações"],
            settings_focus="sound_slider",
            settings_slider_dragging=True,
            settings_sound_vol=0.35,
            settings_music_vol=0.20,
        )
        pixmap = QPixmap(1024, 768)
        painter = QPainter(pixmap)
        try:
            overlay._draw_calibration(painter, snapshot_main, 1.0)
        finally:
            painter.end()

        # 2. Tela com dropdown aberto
        snapshot_dropdown = OverlaySnapshot(
            game_rect=rect,
            mode="calibration",
            memory_state_desc="Configurações (Settings)",
            memory_open_menus=["Configurações"],
            settings_dropdown="shadows",
            settings_dropdown_idx=2,
        )
        pixmap2 = QPixmap(1024, 768)
        painter2 = QPainter(pixmap2)
        try:
            overlay._draw_calibration(painter2, snapshot_dropdown, 1.0)
        finally:
            painter2.end()


if __name__ == "__main__":
    unittest.main()
