"""Testes unitários para interface de pesca e modal de confirmação (resultado da pesca / mensagens)."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    ControllerState,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    fishing_hook_point,
    fishing_close_point,
    modal_ok_point,
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
        self.events.append(("key", name, down))
        return True

    def key_pressed(self, name: str) -> bool:
        return self.buttons.get(name, False)

    def tap(self, name: str) -> bool:
        self.events.append(("tap", name))
        return True


class FishingAndModalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_coordinates_base_1024x768(self):
        """Valida que o anzol de pesca e o botão Ok do modal batem pixel a pixel com a calibração."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Anzol de pesca (centro do quadrado vermelho no print 3)
        self.assertEqual(fishing_hook_point(rect), (512, 498))
        self.assertEqual(fishing_close_point(rect), (512, 448))

        # Botão Ok da confirmação (prints 1 e 2)
        self.assertEqual(modal_ok_point(rect), (509, 467))

    def test_fishing_navigation_locks_cursor_and_clicks(self):
        """O botão sul executa um clique simples no anzol."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        # 1. Entra na pesca
        engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            state_desc="Em Jogo",
            open_menus=["Pesca"],
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        self.assertTrue(engine._fishing_initialized)
        self.assertEqual(injector.cursor, (512, 498))
        self.assertEqual(shared.get().fishing_focus, "hook")

        # 2. Roda de habilidades deve estar bloqueada
        self.assertFalse(engine._is_radial_allowed())

        # 3. Pressiona A -> Clica no anzol para puxar
        btn_a = ControllerState(buttons={"a"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_a, rect, cfg, 0.1, 0.05)

        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)
        # NUNCA deve vazar clique direito!
        self.assertNotIn(("mouse", "right", True), injector.events)

    def _fishing_engine(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = ConfigManager(Path(directory.name) / "perfil.json")
        engine = BridgeEngine(config, SharedOverlayState())
        engine.injector = FakeInjector()
        engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True,
                                               state_desc="Em Jogo", open_menus=["Pesca"])
        return engine, config.get(), Rect(100, 80, 1024, 768)

    def test_fishing_physical_south_east_mapping_and_nintendo_inversion(self):
        for family, confirm, cancel in (("xbox", "a", "b"), ("playstation", "a", "b"),
                                        ("nintendo", "b", "a")):
            for button, focus in ((confirm, "hook"), (cancel, "close")):
                with self.subTest(family=family, button=button):
                    engine, cfg, rect = self._fishing_engine()
                    empty = ControllerState(controller_type=family)
                    engine._process_active(MagicMock(), empty, rect, cfg, 1., .05)
                    engine._previous = empty
                    engine.injector.events.clear()
                    state = ControllerState(controller_type=family, buttons=frozenset({button}))
                    engine._process_active(MagicMock(), state, rect, cfg, 1.1, .05)
                    point = fishing_close_point(rect) if focus == "close" else fishing_hook_point(rect)
                    self.assertEqual(engine.injector.events[-3:],
                                     [("move", *point), ("mouse", "left", True), ("mouse", "left", False)])
                    self.assertEqual(engine.shared.get().fishing_focus, focus)
                    self.assertFalse(any(e[0] == "key" and e[2] for e in engine.injector.events))
                    # Holding cannot repeat, reposition to the hook or cast a spell.
                    engine._previous = state
                    engine.injector.events.clear()
                    engine._process_active(MagicMock(), state, rect, cfg, 1.3, .05)
                    self.assertEqual(engine.injector.events, [])
                    self.assertEqual(engine.injector.cursor, point)

    def test_fishing_ignores_every_other_controller_input_before_general_handlers(self):
        ignored = ("x", "y", "r3", "l3", "lb", "rb", "back", "start",
                   "dpad_up", "dpad_down", "dpad_left", "dpad_right")
        for button in ignored:
            with self.subTest(button=button):
                engine, cfg, rect = self._fishing_engine()
                engine._process_active(MagicMock(), ControllerState(), rect, cfg, 1., .05)
                engine.injector.events.clear()
                state = ControllerState(buttons=frozenset({button}), lt=1., rt=1., lx=1., ly=1., rx=1., ry=1.)
                engine._process_active(MagicMock(), state, rect, cfg, 1.2, .05)
                self.assertEqual(engine.injector.events, [])
                self.assertEqual(engine.injector.cursor, fishing_hook_point(rect))
                self.assertEqual(engine._native_direction, (0., 0.))
                self.assertFalse(engine.shared.get().radial_active)

    def test_fishing_entry_releases_attack_and_modified_click_before_plain_hook_click(self):
        engine, cfg, rect = self._fishing_engine()
        engine._held_keys = {"SHIFT", "CTRL"}
        engine._held_mouse = {"left", "right"}
        engine._a_shift_held = True
        engine._modifier_seq = ("SHIFT", .9)
        engine._modifier_left_down = True
        engine.injector.buttons = {"SHIFT": True, "CTRL": True, "left": True, "right": True}
        engine._process_active(MagicMock(), ControllerState(buttons=frozenset({"a"})), rect, cfg, 1., .05)
        events = engine.injector.events
        click = events.index(("mouse", "left", True))
        for modifier in ("SHIFT", "CTRL"):
            self.assertIn(("key", modifier, False), events[:click])
            self.assertFalse(engine.injector.buttons[modifier])
        self.assertEqual(events[click:], [("mouse", "left", True), ("mouse", "left", False)])
        self.assertIsNone(engine._modifier_seq)
        self.assertFalse(engine._a_shift_held)

    def test_fishing_close_offset_is_fifty_pixels_at_any_resolution(self):
        for rect in (Rect(0, 0, 1024, 768), Rect(-1280, 80, 1280, 720), Rect(100, 80, 1920, 1080)):
            hook, close = fishing_hook_point(rect), fishing_close_point(rect)
            self.assertEqual(hook[0], close[0])
            self.assertEqual(hook[1] - close[1], 50)

    def test_modal_confirmation_navigation_and_ok_click(self):
        """Valida que no popup modal (peixe pego / nenhum peixe) o cursor vai pro Ok e A/X/B clicam."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        # 1. Entra no modal de confirmação
        engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            state_desc="Confirmação / Sair",
            open_menus=["Confirmação Sair"],
        )
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        self.assertTrue(engine._modal_confirm_initialized)
        self.assertEqual(injector.cursor, (509, 467))
        self.assertEqual(shared.get().modal_confirm_focus, "ok")

        # 2. Roda de habilidades deve estar bloqueada
        self.assertFalse(engine._is_radial_allowed())

        # 3. Pressiona X -> Clica no botão Ok
        btn_x = ControllerState(buttons={"x"})
        engine._previous = empty
        injector.events.clear()
        engine._process_active(hub, btn_x, rect, cfg, 0.1, 0.05)

        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)
        self.assertNotIn(("mouse", "right", True), injector.events)

    def test_overlay_renders_fishing_and_modal(self):
        """Valida que o overlay desenha sem erros quando pesca ou modal estão focados."""
        config = ConfigManager()
        shared = SharedOverlayState()
        overlay = GameOverlay(shared, config)
        rect = Rect(left=0, top=0, width=1024, height=768)

        shared.update(
            game_found=True,
            game_rect=rect,
            mode="cursor",
            fishing_focus="hook",
            modal_confirm_focus="ok",
        )

        pixmap = QPixmap(1024, 768)
        painter = QPainter(pixmap)
        scale = 1.0
        overlay._draw_calibration(painter, shared.get(), scale)
        painter.end()


if __name__ == "__main__":
    unittest.main()
