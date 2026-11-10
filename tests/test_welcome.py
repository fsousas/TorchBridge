import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager, DEFAULT_CONFIG
from torchbridge.controller import ControllerHub
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    ControllerState,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    welcome_button_point,
    welcome_button_rect,
    welcome_screen_target_rect,
)
from torchbridge.engine.welcome import WelcomeNavigationMixin
from torchbridge.overlay import GameOverlay


class MockEngine(WelcomeNavigationMixin):
    def __init__(self, config: ConfigManager, shared: SharedOverlayState):
        self.config = config
        self.shared = shared
        self.injector = MagicMock()
        self._previous = ControllerState()
        self._init_welcome_state()


class TestWelcomeConfig(unittest.TestCase):
    def test_default_config_has_show_welcome(self):
        self.assertIn("show-welcome", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["show-welcome"], 1)

    def test_config_manager_set_show_welcome(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "perfil.json"
            cfg = ConfigManager(cfg_path)
            self.assertEqual(cfg.get()["show-welcome"], 1)

            cfg.set_show_welcome(0)
            self.assertEqual(cfg.get()["show-welcome"], 0)

            # Recarrega do disco
            cfg2 = ConfigManager(cfg_path)
            self.assertEqual(cfg2.get()["show-welcome"], 0)


class TestWelcomeGeometry(unittest.TestCase):
    def test_welcome_target_rect_centering_768p(self):
        # Resolução 1366x768 (escala 1.0 pela altura de 768p)
        rect = Rect(100, 50, 1366, 768)
        left, top, w, h = welcome_screen_target_rect(rect)
        self.assertEqual(w, 762)
        self.assertEqual(h, 657)
        self.assertEqual(left, 100 + int(round((1366 - 762) / 2.0)))
        self.assertEqual(top, 50 + int(round((768 - 657) / 2.0)))

    def test_welcome_target_rect_centering_1080p(self):
        # Resolução 1920x1080 (escala 1080 / 768.0 = 1.40625)
        rect = Rect(0, 0, 1920, 1080)
        left, top, w, h = welcome_screen_target_rect(rect)
        scale = 1080.0 / 768.0
        expected_w = int(round(762.0 * scale))
        expected_h = int(round(657.0 * scale))
        self.assertEqual(w, expected_w)
        self.assertEqual(h, expected_h)
        self.assertEqual(left, int(round((1920 - expected_w) / 2.0)))
        self.assertEqual(top, int(round((1080 - expected_h) / 2.0)))

    def test_welcome_button_rects(self):
        rect = Rect(100, 100, 1280, 720)
        prev_rect = welcome_button_rect(rect, "prev")
        next_rect = welcome_button_rect(rect, "next")
        close_rect = welcome_button_rect(rect, "close")
        x_rect = welcome_button_rect(rect, "x")

        # Anterior deve estar à esquerda de Próximo
        self.assertLess(prev_rect[0], next_rect[0])
        # Fechar tem as mesmas coordenadas de Próximo
        self.assertEqual(next_rect, close_rect)
        # Botão X deve estar acima dos botões inferiores
        self.assertLess(x_rect[1], prev_rect[1])

        # Centros dos botões
        pt_next = welcome_button_point(rect, "next")
        self.assertEqual(pt_next[0], next_rect[0] + next_rect[2] // 2)
        self.assertEqual(pt_next[1], next_rect[1] + next_rect[3] // 2)


class TestWelcomeNavigation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmpdir.name) / "perfil.json"
        self.config = ConfigManager(self.cfg_path)
        self.shared = SharedOverlayState()
        self.engine = MockEngine(self.config, self.shared)
        self.hub = MagicMock()
        self.rect = Rect(0, 0, 1920, 1080)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_first_time_navigation_flow(self):
        # Abre no modo obrigatório (can_close=False)
        self.engine._open_welcome(can_close=False, rect=self.rect)
        self.assertTrue(self.engine._welcome_open)
        self.assertEqual(self.engine._welcome_page, 1)
        self.assertEqual(self.engine._welcome_focus, "next")
        self.assertFalse(self.engine._welcome_can_close)

        # Cancelar / Start não fecha no modo obrigatório
        state_cancel = ControllerState(connected=True, buttons=frozenset(["b"]))
        self.engine._handle_welcome_navigation(self.hub, state_cancel, self.rect, self.config.get(), 1.0)
        self.assertTrue(self.engine._welcome_open)

        state_start = ControllerState(connected=True, buttons=frozenset(["start"]))
        self.engine._handle_welcome_navigation(self.hub, state_start, self.rect, self.config.get(), 1.1)
        self.assertTrue(self.engine._welcome_open)

        # Na página 1, dpad_left não muda o foco de "next"
        state_dpad_left = ControllerState(connected=True, buttons=frozenset(["dpad_left"]))
        self.engine._handle_welcome_navigation(self.hub, state_dpad_left, self.rect, self.config.get(), 1.2)
        self.assertEqual(self.engine._welcome_focus, "next")

        # Confirmar avança para página 2
        state_confirm = ControllerState(connected=True, buttons=frozenset(["a"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_confirm, self.rect, self.config.get(), 1.3)
        self.assertEqual(self.engine._welcome_page, 2)

        # Na página 2, dpad_left vai para "prev"
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_dpad_left, self.rect, self.config.get(), 1.4)
        self.assertEqual(self.engine._welcome_focus, "prev")

        # Dpad_right volta para "next"
        state_dpad_right = ControllerState(connected=True, buttons=frozenset(["dpad_right"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_dpad_right, self.rect, self.config.get(), 1.5)
        self.assertEqual(self.engine._welcome_focus, "next")

        # Avança até a última página
        total = self.engine._welcome_total_pages
        self.engine._welcome_page = total - 1
        self.engine._welcome_focus = "next"
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_confirm, self.rect, self.config.get(), 1.6)
        self.assertEqual(self.engine._welcome_page, total)
        self.assertEqual(self.engine._welcome_focus, "close")

        # Confirmar em "close" fecha e salva show-welcome=0
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_confirm, self.rect, self.config.get(), 1.7)
        self.assertFalse(self.engine._welcome_open)
        self.assertEqual(self.config.get()["show-welcome"], 0)

    def test_reopened_navigation_can_close_with_cancel_and_start(self):
        # Abre no modo opcional (can_close=True)
        self.engine._open_welcome(can_close=True, rect=self.rect)
        self.assertTrue(self.engine._welcome_open)
        self.assertTrue(self.engine._welcome_can_close)

        # Fecha com botão Leste ("b")
        state_cancel = ControllerState(connected=True, buttons=frozenset(["b"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_cancel, self.rect, self.config.get(), 2.0)
        self.assertFalse(self.engine._welcome_open)

        # Abre novamente e fecha com Start
        self.engine._open_welcome(can_close=True, rect=self.rect)
        self.assertTrue(self.engine._welcome_open)
        state_start = ControllerState(connected=True, buttons=frozenset(["start"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_start, self.rect, self.config.get(), 2.1)
        self.assertFalse(self.engine._welcome_open)

    def test_reopened_navigation_can_close_with_x_button(self):
        self.engine._open_welcome(can_close=True, rect=self.rect)
        # D-pad Cima sobe para "x"
        state_up = ControllerState(connected=True, buttons=frozenset(["dpad_up"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_up, self.rect, self.config.get(), 3.0)
        self.assertEqual(self.engine._welcome_focus, "x")

        # D-pad Baixo desce de volta para "next"
        state_down = ControllerState(connected=True, buttons=frozenset(["dpad_down"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_down, self.rect, self.config.get(), 3.1)
        self.assertEqual(self.engine._welcome_focus, "next")

        # Sobe novamente e confirma no "x"
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_up, self.rect, self.config.get(), 3.2)
        state_confirm = ControllerState(connected=True, buttons=frozenset(["a"]))
        self.engine._previous = ControllerState()
        self.engine._handle_welcome_navigation(self.hub, state_confirm, self.rect, self.config.get(), 3.3)
        self.assertFalse(self.engine._welcome_open)

    def test_mouse_click_advances_page(self):
        self.engine._open_welcome(can_close=False, rect=self.rect)
        self.assertEqual(self.engine._welcome_page, 1)

        # Mock de cursor sobre o botão Próximo
        btn_x, btn_y, bw, bh = welcome_button_rect(self.rect, "next")
        self.engine.injector.cursor_position = lambda: (btn_x + bw // 2, btn_y + bh // 2)

        # Simula clique do mouse (DOWN)
        self.engine.injector.key_pressed = lambda k: True if k == "MOUSE_LEFT" else False
        state = ControllerState(connected=True)
        self.engine._handle_welcome_navigation(self.hub, state, self.rect, self.config.get(), 1.0)
        self.assertEqual(self.engine._welcome_page, 2)

    def test_keyboard_enter_advances_page(self):
        self.engine._open_welcome(can_close=False, rect=self.rect)
        self.assertEqual(self.engine._welcome_page, 1)

        # Simula tecla RETURN / ENTER pressionada
        self.engine.injector.key_pressed = lambda k: True if k == "RETURN" else False
        self.engine.injector.cursor_position = lambda: (0, 0)
        state = ControllerState(connected=True)
        self.engine._handle_welcome_navigation(self.hub, state, self.rect, self.config.get(), 1.0)
        self.assertEqual(self.engine._welcome_page, 2)


class TestWelcomeOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_draw_welcome_screen_and_radial_banner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "perfil.json"
            config = ConfigManager(cfg_path)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            rect = Rect(0, 0, 1280, 720)
            pix = QPixmap(1280, 720)
            painter = QPainter(pix)
            try:
                # 1. Página 1 com controle Xbox
                snap1 = OverlaySnapshot(
                    game_rect=rect,
                    controller_connected=True,
                    controller_type="xbox",
                    welcome_screen_open=True,
                    welcome_screen_page=1,
                    welcome_screen_total_pages=9,
                    welcome_screen_focus="next",
                    welcome_screen_can_close=False,
                    memory_state_desc="Tela Inicial",
                )
                overlay._draw_welcome_screen(painter, snap1, 1.0)

                # 2. Página intermediária com controle PlayStation
                snap2 = OverlaySnapshot(
                    game_rect=rect,
                    controller_connected=True,
                    controller_type="playstation",
                    welcome_screen_open=True,
                    welcome_screen_page=2,
                    welcome_screen_total_pages=9,
                    welcome_screen_focus="prev",
                    welcome_screen_can_close=True,
                    memory_state_desc="Tela Inicial",
                )
                overlay._draw_welcome_screen(painter, snap2, 1.0)

                # 3. Última página com controle Nintendo
                snap3 = OverlaySnapshot(
                    game_rect=rect,
                    controller_connected=True,
                    controller_type="nintendo",
                    welcome_screen_open=True,
                    welcome_screen_page=9,
                    welcome_screen_total_pages=9,
                    welcome_screen_focus="close",
                    welcome_screen_can_close=True,
                    memory_state_desc="Em Jogo",
                )
                overlay._draw_welcome_screen(painter, snap3, 1.0)

                # 4. Banner superior do radial (slide-in / slide-out)
                overlay._radial_progress = 0.8
                snap_radial = OverlaySnapshot(
                    game_rect=rect,
                    radial_active=True,
                    controller_type="xbox",
                )
                overlay._draw_radial_welcome_top_banner(painter, snap_radial, 1.0)

                # 5. Não renderiza durante carregamento (loading)
                snap_loading = OverlaySnapshot(
                    game_rect=rect,
                    welcome_screen_open=True,
                    memory_is_loading=True,
                    memory_state_desc="Carregando...",
                )
                overlay._draw_welcome_screen(painter, snap_loading, 1.0)

                # 6. Não renderiza durante "Inicializando CGame..."
                snap_init = OverlaySnapshot(
                    game_rect=rect,
                    welcome_screen_open=True,
                    memory_is_loading=False,
                    memory_state_desc="Inicializando CGame...",
                )
                overlay._draw_welcome_screen(painter, snap_init, 1.0)

                # 7. Não renderiza com estado vazio
                snap_empty = OverlaySnapshot(
                    game_rect=rect,
                    welcome_screen_open=True,
                    memory_state_desc="",
                )
                overlay._draw_welcome_screen(painter, snap_empty, 1.0)
            finally:
                painter.end()


class TestWelcomeAllowedToTrigger(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmpdir.name) / "perfil.json"
        self.config = ConfigManager(self.cfg_path)
        self.shared = SharedOverlayState()
        self.engine = MockEngine(self.config, self.shared)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_not_allowed_when_disconnected(self):
        self.engine._memory_state = GameMemoryState(is_connected=False)
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_not_allowed_when_loading(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=True, state_id=0, state_desc="Carregando...")
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_not_allowed_when_inicializando_cgame(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, state_id=-1, state_desc="Inicializando CGame...")
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_not_allowed_when_inicializando_cgameclient(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, state_id=-1, state_desc="Inicializando CGameClient...")
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_not_allowed_when_aguardando(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, state_id=-1, state_desc="Aguardando jogo...")
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_not_allowed_when_empty_state_desc(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, state_id=-1, state_desc="")
        self.assertFalse(self.engine._is_welcome_allowed_to_show())
        self.assertTrue(self.engine._is_welcome_suppressed())

    def test_allowed_on_main_menu(self):
        # Estado 0: Tela Inicial (menu principal)
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, state_id=0, state_desc="Tela Inicial")
        self.assertFalse(self.engine._is_welcome_suppressed())
        self.assertTrue(self.engine._is_welcome_allowed_to_show())

    def test_allowed_in_game(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_loading=False, is_in_game=True, state_id=6, state_desc="Em Jogo")
        self.assertFalse(self.engine._is_welcome_suppressed())
        self.assertTrue(self.engine._is_welcome_allowed_to_show())


class TestWelcomeCloseLatch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmpdir.name) / "perfil.json"
        self.config = ConfigManager(self.cfg_path)
        self.shared = SharedOverlayState()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_close_welcome_sets_latched(self):
        engine = MockEngine(self.config, self.shared)
        rect = Rect(0, 0, 1280, 720)
        engine._open_welcome(can_close=True, rect=rect)
        self.assertTrue(engine._welcome_open)

        engine._close_welcome(from_last_page=False, rect=rect)
        self.assertFalse(engine._welcome_open)
        self.assertTrue(engine._welcome_close_latched)
        self.assertGreater(engine._welcome_close_until, 0.0)

    def test_bridge_engine_blocks_input_while_close_latched(self):
        from torchbridge.engine.main import BridgeEngine
        engine = BridgeEngine(self.config, self.shared)
        engine.injector = MagicMock()
        rect = Rect(0, 0, 1280, 720)
        hub = MagicMock()

        # Abre e fecha a tela de boas-vindas
        engine._open_welcome(can_close=True, rect=rect)
        engine._close_welcome(from_last_page=False, rect=rect, now=1.0)
        self.assertTrue(engine._welcome_close_latched)

        # Se o usuário ainda estiver segurando "A", o tick é consumido e nada é injetado
        state_holding_a = ControllerState(connected=True, buttons=frozenset(["a"]))
        engine._memory_state = GameMemoryState(is_connected=True, state_id=0, state_desc="Tela Inicial")
        engine._title_focus = "continue"

        engine._process_active(hub, state_holding_a, rect, self.config.get(), 1.0, 0.016)

        # Deve continuar travado e NÃO deve ter chamado clique de mouse
        self.assertTrue(engine._welcome_close_latched)
        engine.injector.mouse_button.assert_not_called()

        # Quando solta o botão "A" e passa o cooldown, destrava limpo
        state_released = ControllerState(connected=True, buttons=frozenset())
        engine._process_active(hub, state_released, rect, self.config.get(), 2.0, 0.016)
        self.assertFalse(engine._welcome_close_latched)


if __name__ == "__main__":
    unittest.main()
