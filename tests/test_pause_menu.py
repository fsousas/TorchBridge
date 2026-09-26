"""Testes unitários para mapeamento, coordenadas e navegação do Menu de Pause (COptionsMenu / Options) em jogo."""
import unittest
from unittest.mock import MagicMock

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GAMEPLAY_MENUS, GameMemoryState
from torchbridge.models import (
    PAUSE_BUTTONS,
    PAUSE_BUTTON_COORDS,
    ControllerState,
    Rect,
    SharedOverlayState,
    pause_menu_button_point,
)


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


class PauseMenuTests(unittest.TestCase):
    def test_gameplay_menus_has_pause(self):
        """Verifica se o Menu de Pause está registrado na memória em +0x02E8."""
        self.assertIn("Pause", GAMEPLAY_MENUS)
        self.assertEqual(GAMEPLAY_MENUS["Pause"], (0x02E8, 0x18))

    def test_pause_menu_button_coordinates(self):
        """Verifica se os pontos calculados batem exatamente no centro dos quadradinhos calibrados."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Settings (verde - superior): (599, 233)
        sx, sy = pause_menu_button_point(rect, "settings")
        self.assertEqual((sx, sy), (599, 233))

        # Exit to Title (verde - intermediário): (599, 323)
        ex, ey = pause_menu_button_point(rect, "exit_to_title")
        self.assertEqual((ex, ey), (599, 323))

        # Return to Game (amarelo - padrão/inferior): (599, 413)
        rx, ry = pause_menu_button_point(rect, "return_to_game")
        self.assertEqual((rx, ry), (599, 413))

    def test_pause_menu_navigation(self):
        """Testa o ciclo de vida completo e navegação via D-pad no Menu de Pause."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)

        # 1. Simula entrada no menu de pause em jogo
        mem_state_paused = GameMemoryState(
            is_connected=True,
            state_id=6,
            is_in_game=True,
            state_desc="Em Jogo",
            open_menus=["Pause"],
        )
        engine._memory_state = mem_state_paused

        cfg = config.get()
        empty_controller = ControllerState()

        # Primeiro tick com pause aberto: deve focar automaticamente no botão amarelo 'return_to_game'
        engine._process_active(hub, empty_controller, rect, cfg, 0.0, 0.05)
        self.assertEqual(engine._pause_focus, "return_to_game")
        self.assertEqual(shared.get().pause_menu_focus, "return_to_game")
        self.assertIn(("move", 599, 413), injector.events)

        # 2. D-pad Cima: move de 'return_to_game' para 'exit_to_title' (599, 323)
        up_controller = ControllerState(buttons={"dpad_up"})
        engine._previous = empty_controller
        engine._process_active(hub, up_controller, rect, cfg, 0.1, 0.05)
        self.assertEqual(engine._pause_focus, "exit_to_title")
        self.assertEqual(shared.get().pause_menu_focus, "exit_to_title")
        self.assertIn(("move", 599, 323), injector.events)

        # 3. D-pad Cima novamente: move de 'exit_to_title' para 'settings' (599, 233)
        engine._previous = empty_controller  # soltou e apertou de novo
        engine._process_active(hub, up_controller, rect, cfg, 0.2, 0.05)
        self.assertEqual(engine._pause_focus, "settings")
        self.assertEqual(shared.get().pause_menu_focus, "settings")
        self.assertIn(("move", 599, 233), injector.events)

        # 4. D-pad Baixo: move de 'settings' para 'exit_to_title' (599, 323)
        down_controller = ControllerState(buttons={"dpad_down"})
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.3, 0.05)
        self.assertEqual(engine._pause_focus, "exit_to_title")
        self.assertEqual(shared.get().pause_menu_focus, "exit_to_title")

        # 5. D-pad Baixo novamente: move de 'exit_to_title' para 'return_to_game' (599, 413)
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._pause_focus, "return_to_game")
        self.assertEqual(shared.get().pause_menu_focus, "return_to_game")

        # 6. Botão B: atalho direto para fechar/retornar ao jogo com clique esquerdo
        b_controller = ControllerState(buttons={"b"})
        engine._previous = empty_controller
        engine._process_active(hub, b_controller, rect, cfg, 0.5, 0.05)
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

        # 7. Menu de Pause fechado pelo jogo
        mem_state_gameplay = GameMemoryState(
            is_connected=True,
            state_id=6,
            is_in_game=True,
            state_desc="Em Jogo",
            open_menus=[],
        )
        engine._memory_state = mem_state_gameplay
        engine._previous = empty_controller
        engine._process_active(hub, empty_controller, rect, cfg, 0.6, 0.05)
        self.assertFalse(engine._pause_menu_initialized)
        self.assertIsNone(engine._pause_focus)
        self.assertIsNone(shared.get().pause_menu_focus)


if __name__ == "__main__":
    unittest.main()
