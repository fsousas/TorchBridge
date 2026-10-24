"""Testes unitários para mapeamento, coordenadas e navegação da Tela de Morte / Respawn."""
import unittest
from unittest.mock import MagicMock

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GAMEPLAY_MENUS, GameMemoryState
from torchbridge.models import (
    DEATH_SCREEN_BUTTONS,
    DEATH_SCREEN_BUTTON_COORDS,
    ControllerState,
    Rect,
    SharedOverlayState,
    death_screen_button_point,
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


class DeathScreenTests(unittest.TestCase):
    def test_gameplay_menus_has_death_screen(self):
        """Verifica se a Tela de Morte / Respawn está registrada na memória em +0x02F0."""
        self.assertIn("Morte / Respawn", GAMEPLAY_MENUS)
        self.assertEqual(GAMEPLAY_MENUS["Morte / Respawn"], (0x02F0, 0x18))

    def test_death_screen_button_coordinates(self):
        """Verifica se os pontos calculados batem exatamente nos quadradinhos calibrados da imagem death-screen.png."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # 1. Resurrect here (verde - superior): (334, 248)
        hx, hy = death_screen_button_point(rect, "resurrect_here")
        self.assertEqual((hx, hy), (334, 248))

        # 2. Resurrect at entrance (amarelo - padrão inicial): (334, 348)
        ex, ey = death_screen_button_point(rect, "resurrect_entrance")
        self.assertEqual((ex, ey), (334, 348))

        # 3. Resurrect in town (verde - intermediário): (334, 448)
        tx, ty = death_screen_button_point(rect, "resurrect_town")
        self.assertEqual((tx, ty), (334, 448))

        # 4. Exit to Title (verde - inferior): (563, 552)
        xt, yt = death_screen_button_point(rect, "exit_to_title")
        self.assertEqual((xt, yt), (563, 552))

    def test_death_screen_navigation_lifecycle(self):
        """Testa o ciclo de vida e a navegação por D-pad na Tela de Morte."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)

        # 1. Simula entrada na tela de morte em jogo
        mem_state_death = GameMemoryState(
            is_connected=True,
            state_id=6,
            is_in_game=True,
            state_desc="Em Jogo",
            open_menus=["Morte / Respawn"],
        )
        engine._memory_state = mem_state_death

        cfg = config.get()
        empty_controller = ControllerState()

        # Primeiro tick com tela de morte aberta: foco automático no nó amarelo 'resurrect_entrance'
        engine._process_active(hub, empty_controller, rect, cfg, 0.0, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_entrance")
        self.assertEqual(shared.get().death_screen_focus, "resurrect_entrance")
        self.assertIn(("move", 334, 348), injector.events)

        # 2. D-pad Cima: move de 'resurrect_entrance' para 'resurrect_here'
        up_controller = ControllerState(buttons={"dpad_up"})
        engine._previous = empty_controller
        engine._process_active(hub, up_controller, rect, cfg, 0.1, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_here")
        self.assertEqual(shared.get().death_screen_focus, "resurrect_here")
        self.assertIn(("move", 334, 248), injector.events)

        # 3. D-pad Cima no topo: deve permanecer em 'resurrect_here'
        engine._previous = empty_controller
        engine._process_active(hub, up_controller, rect, cfg, 0.2, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_here")

        # 4. D-pad Baixo: volta para 'resurrect_entrance' (amarelo)
        down_controller = ControllerState(buttons={"dpad_down"})
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.3, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_entrance")
        self.assertEqual(shared.get().death_screen_focus, "resurrect_entrance")
        self.assertIn(("move", 334, 348), injector.events)

        # 5. D-pad Baixo: move para 'resurrect_town'
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_town")
        self.assertEqual(shared.get().death_screen_focus, "resurrect_town")
        self.assertIn(("move", 334, 448), injector.events)

        # 6. D-pad Baixo: move para 'exit_to_title'
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.5, 0.05)
        self.assertEqual(engine._death_screen_focus, "exit_to_title")
        self.assertEqual(shared.get().death_screen_focus, "exit_to_title")
        self.assertIn(("move", 563, 552), injector.events)

        # 7. D-pad Baixo na base: deve permanecer em 'exit_to_title'
        engine._previous = empty_controller
        engine._process_active(hub, down_controller, rect, cfg, 0.6, 0.05)
        self.assertEqual(engine._death_screen_focus, "exit_to_title")

        # 8. D-pad Cima: sobe de volta para 'resurrect_town'
        engine._previous = empty_controller
        engine._process_active(hub, up_controller, rect, cfg, 0.7, 0.05)
        self.assertEqual(engine._death_screen_focus, "resurrect_town")
        self.assertEqual(shared.get().death_screen_focus, "resurrect_town")

        # 9. Tela de Morte fechada pelo jogo (jogador reviveu ou mudou de tela)
        mem_state_revived = GameMemoryState(
            is_connected=True,
            state_id=6,
            is_in_game=True,
            state_desc="Em Jogo",
            open_menus=[],
        )
        engine._memory_state = mem_state_revived
        engine._previous = empty_controller
        engine._process_active(hub, empty_controller, rect, cfg, 0.8, 0.05)
        self.assertFalse(engine._death_screen_initialized)
        self.assertIsNone(engine._death_screen_focus)
        self.assertIsNone(shared.get().death_screen_focus)


if __name__ == "__main__":
    unittest.main()
