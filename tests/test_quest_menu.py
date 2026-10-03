"""Testes unitários para o Menu de Missões / Quests (Q):
- Coordenadas de slots de missão (0..5), recompensa e botão abandonar
- Âncoragem à borda direita e escalonamento
- Leitura de estado de memória (quest_menu_open, quest_selected_idx, quest_count, etc.)
- Renderização visual no overlay (amarelo, verde e laranja de ponte)
- Navegação D-pad com clique automático ao trocar de missão
- Transição dinâmica para slots inferiores (recompensa de item e botão abandonar)
- Ponte bidirecional entre Pet/Character (esquerda) e Quests (direita)
"""
import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter

from torchbridge.config import ConfigManager
from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    QUEST_ROW_COUNT,
    QUEST_ROW_ORIGIN,
    QUEST_ROW_STEP_Y,
    QUEST_REWARD_POINT,
    QUEST_ABANDON_POINT,
    Rect,
    SharedOverlayState,
    quest_slot_point,
    quest_reward_point,
    quest_abandon_point,
    pet_inventory_slot_point,
)
from torchbridge.overlay import GameOverlay


class QuestCoordinatesTests(unittest.TestCase):
    def setUp(self):
        self.rect_1024 = Rect(left=0, top=0, width=1024, height=768)
        self.rect_1080 = Rect(left=0, top=0, width=1920, height=1080)

    def test_quest_slot_coordinates_base_1024(self):
        # Base 1024x768: x = 976.5 -> 976 ou 977
        for i in range(6):
            expected_y = round(106.5 + i * 25.0)
            sx, sy = quest_slot_point(self.rect_1024, i)
            self.assertIn(sx, (976, 977))
            self.assertAlmostEqual(sy, expected_y, delta=1)

    def test_quest_reward_coordinates_base_1024(self):
        # Base 1024x768: (964.5, 573.5)
        rx, ry = quest_reward_point(self.rect_1024)
        self.assertIn(rx, (964, 965))
        self.assertIn(ry, (573, 574))

    def test_quest_abandon_coordinates_base_1024(self):
        # Base 1024x768: (894.5, 646.5)
        ax, ay = quest_abandon_point(self.rect_1024)
        self.assertIn(ax, (894, 895))
        self.assertIn(ay, (646, 647))

    def test_quest_coordinates_scaling_1080p(self):
        # 1080p: scale = 1080 / 768 = 1.40625
        # x ancorado à borda direita: rect.right - (1024 - base_x) * scale
        scale = 1080.0 / 768.0
        expected_x = round(1920.0 - (1024.0 - 976.5) * scale)
        expected_y0 = round(106.5 * scale)
        sx, sy = quest_slot_point(self.rect_1080, 0)
        self.assertAlmostEqual(sx, expected_x, delta=2)
        self.assertAlmostEqual(sy, expected_y0, delta=2)

    def test_quest_invalid_rect(self):
        invalid = Rect(0, 0, 0, 0)
        self.assertEqual(quest_slot_point(invalid, 0), (0, 0))
        self.assertEqual(quest_reward_point(invalid), (0, 0))
        self.assertEqual(quest_abandon_point(invalid), (0, 0))


class QuestOverlayRenderingTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.config.set_show_calibration(True)
        self.shared = SharedOverlayState()
        self.overlay = GameOverlay(self.shared, self.config)
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_quest_menu_single_open_colors(self):
        # Menu de quests aberto sozinho: foco amarelo (#E6C12A), outros slots verdes (#09B200)
        self.shared.update(
            game_found=True,
            game_active=True,
            game_rect=self.rect,
            quest_menu_open=True,
            quest_focus="quest_0",
            quest_count=3,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
            memory_open_menus=["Missões (Quests)"],
        )
        img = self.overlay._render_native(self.shared.get(), 1024, 768)

        # Slot 0 (focado): pixel central deve ser amarelo
        s0_x, s0_y = quest_slot_point(self.rect, 0)
        c0 = img.pixelColor(s0_x, s0_y)
        self.assertGreater(c0.red(), 200)
        self.assertGreater(c0.green(), 170)
        self.assertLess(c0.blue(), 60)

        # Slot 1 (não focado, sem menu esquerdo): pixel central deve ser verde
        s1_x, s1_y = quest_slot_point(self.rect, 1)
        c1 = img.pixelColor(s1_x, s1_y)
        self.assertLess(c1.red(), 30)
        self.assertGreater(c1.green(), 150)
        self.assertLess(c1.blue(), 30)

    def test_quest_menu_dual_open_orange_bridge(self):
        # Menu de quests + Pet abertos juntos: foco amarelo, demais slots laranjas (#FD6100)
        self.shared.update(
            game_found=True,
            game_active=True,
            game_rect=self.rect,
            quest_menu_open=True,
            quest_focus="quest_0",
            quest_count=3,
            quest_visible_rows=3,
            pet_inventory_open=True,
            memory_open_menus=["Pet", "Missões (Quests)"],
        )
        img = self.overlay._render_native(self.shared.get(), 1024, 768)

        # Slot 1 no Quest Menu deve ser laranja (ponte ativa)
        s1_x, s1_y = quest_slot_point(self.rect, 1)
        c1 = img.pixelColor(s1_x, s1_y)
        self.assertGreater(c1.red(), 230)
        self.assertGreater(c1.green(), 80)
        self.assertLess(c1.blue(), 30)

        # Na extremidade direita do Pet (coluna 7), deve ser laranja
        pet_x, pet_y = pet_inventory_slot_point(self.rect, 1, 7)
        c_pet = img.pixelColor(pet_x, pet_y)
        self.assertGreater(c_pet.red(), 230)
        self.assertGreater(c_pet.green(), 80)
        self.assertLess(c_pet.blue(), 30)

    def test_quest_calibration_not_rendered_when_quest_menu_closed(self):
        # Menu de quests fechado (não presente em memory_open_menus):
        # mesmo com quest_menu_open=True no snapshot antigo, o overlay NÃO deve desenhar os alvos de calibração
        self.shared.update(
            game_found=True,
            game_active=True,
            game_rect=self.rect,
            quest_menu_open=True,
            quest_focus="quest_0",
            quest_count=3,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
            memory_open_menus=[],
        )
        img = self.overlay._render_native(self.shared.get(), 1024, 768)
        s0_x, s0_y = quest_slot_point(self.rect, 0)
        c0 = img.pixelColor(s0_x, s0_y)
        # Deve ser transparente (alpha == 0)
        self.assertEqual(c0.alpha(), 0)


class QuestEngineNavigationTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (500, 300)
        self.hub = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_quest_initialization_on_open(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_selected_idx=2,
            quest_count=4,
            quest_visible_rows=3,
        )
        state = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state, self.rect, self.hub)

        self.assertTrue(self.engine._quest_menu_initialized)
        self.assertEqual(self.engine._quest_focus, "quest_2")
        snap = self.shared.get()
        self.assertTrue(snap.quest_menu_open)
        self.assertEqual(snap.quest_focus, "quest_2")
        self.engine.injector.move.assert_called_once()

    def test_quest_dpad_down_and_up_navigation_with_clicks(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_selected_idx=0,
            quest_count=3,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_0"
        self.engine._last_quest_slot = 0

        # D-pad Down -> quest_1 e emite clique
        state_down = ControllerState(connected=True, buttons={"dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_down, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "quest_1")
        self.assertEqual(self.engine._last_quest_slot, 1)
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)

        # D-pad Down -> quest_2
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_down, self.rect, self.hub)
        self.assertEqual(self.engine._quest_focus, "quest_2")

        # D-pad Down no último slot (quest_2) -> reward (pois quest_has_item_reward=True)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_down, self.rect, self.hub)
        self.assertEqual(self.engine._quest_focus, "reward")

        # D-pad Down em reward -> abandon (pois quest_can_abandon=True)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_down, self.rect, self.hub)
        self.assertEqual(self.engine._quest_focus, "abandon")

        # D-pad Up em abandon -> volta para reward
        state_up = ControllerState(connected=True, buttons={"dpad_up"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_up, self.rect, self.hub)
        self.assertEqual(self.engine._quest_focus, "reward")

        # D-pad Up em reward -> volta para quest_2 (último slot da lista)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_up, self.rect, self.hub)
        self.assertEqual(self.engine._quest_focus, "quest_2")

    def test_quest_bridge_jump_to_pet(self):
        # Quests aberto + Pet aberto -> D-pad Left salta para o Pet
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_1"

        state_left = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_left, self.rect, self.hub, pet_also_open=True)

        self.assertTrue(self.engine._pet_inventory_initialized)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 7))

    def test_pet_bridge_jump_to_quest(self):
        # Pet na coluna 7 + Quests aberto -> D-pad Right salta para a quest ativa
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Missões (Quests)"],
            quest_menu_open=True,
            quest_selected_idx=2,
            quest_visible_rows=3,
        )
        self.engine._pet_inventory_initialized = True
        self.engine._pet_inventory_focus = (1, 7)
        self.engine._pet_inventory_tab = "tab-1"

        state_right = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_right, self.rect, self.hub)

        self.assertTrue(self.engine._quest_menu_initialized)
        self.assertEqual(self.engine._quest_focus, "quest_2")

    def test_char_bridge_jump_to_quest(self):
        # Character no nó de ponte (strength_bridge) + Quests aberto -> D-pad Right salta para a quest ativa
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos", "Missões (Quests)"],
            quest_menu_open=True,
            quest_selected_idx=1,
            quest_visible_rows=3,
        )
        self.engine._char_menu_initialized = True
        self.engine._char_menu_focus = "strength_bridge"

        state_right = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_char_menu_navigation(
            state_right, self.rect, self.hub,
            skill_also_open=False,
            inv_also_open=False,
            quest_also_open=True,
            attr_points=0,
        )

        self.assertTrue(self.engine._quest_menu_initialized)
        self.assertEqual(self.engine._quest_focus, "quest_1")

    def test_quest_button_a_jump_to_reward_when_has_item_reward(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_0"
        self.engine._last_quest_slot = 0

        state_a = ControllerState(connected=True, buttons={"a"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_a, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "reward")
        expected_x, expected_y = quest_reward_point(self.rect)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

    def test_quest_button_a_jump_to_abandon_when_no_reward_but_can_abandon(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=False,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_1"
        self.engine._last_quest_slot = 1

        state_a = ControllerState(connected=True, buttons={"a"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_a, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "abandon")
        expected_x, expected_y = quest_abandon_point(self.rect)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

    def test_quest_button_a_does_nothing_when_neither_reward_nor_abandon(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=False,
            quest_can_abandon=False,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_0"
        self.engine._last_quest_slot = 0

        state_a = ControllerState(connected=True, buttons={"a"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_a, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "quest_0")

    def test_radial_allowed_when_quest_menu_open(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
        )
        self.assertTrue(self.engine._is_radial_allowed())

    def test_quest_navigation_early_returns_when_lb_held(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_visible_rows=3,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_0"
        self.engine.injector.move.reset_mock()

        state_lb = ControllerState(connected=True, buttons={"lb", "dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_lb, self.rect, self.hub)

        # Não deve executar navegação quando LB estiver pressionado
        self.engine.injector.move.assert_not_called()
        self.assertEqual(self.engine._quest_focus, "quest_0")

    def test_quest_button_a_clicks_abandon(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "abandon"

        state_a = ControllerState(connected=True, buttons={"a"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_a, self.rect, self.hub)

        expected_x, expected_y = quest_abandon_point(self.rect)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)

    def test_quest_button_b_from_reward_returns_to_upper_quest_list(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "reward"
        self.engine._last_quest_slot = 1

        state_b = ControllerState(connected=True, buttons={"b"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_b, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "quest_1")
        expected_x, expected_y = quest_slot_point(self.rect, 1)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)
        self.assertTrue(self.engine._quest_b_consumed)

    def test_quest_button_b_from_abandon_returns_to_upper_quest_list(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=False,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "abandon"
        self.engine._last_quest_slot = 2

        state_b = ControllerState(connected=True, buttons={"b"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_b, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "quest_2")
        expected_x, expected_y = quest_slot_point(self.rect, 2)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)
        self.assertTrue(self.engine._quest_b_consumed)

    def test_quest_button_b_from_quest_row_does_not_consume_b(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Missões (Quests)"],
            quest_menu_open=True,
            quest_visible_rows=3,
            quest_has_item_reward=True,
            quest_can_abandon=True,
        )
        self.engine._quest_menu_initialized = True
        self.engine._quest_focus = "quest_0"
        self.engine._last_quest_slot = 0

        state_b = ControllerState(connected=True, buttons={"b"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_quest_menu_navigation(state_b, self.rect, self.hub)

        self.assertEqual(self.engine._quest_focus, "quest_0")
        self.assertFalse(self.engine._quest_b_consumed)

    def test_overworld_remap_does_not_tap_esc_when_quest_b_consumed(self):
        self.engine._quest_b_consumed = True
        self.engine._previous_panels = ("", "Q")
        state_b = ControllerState(connected=True, buttons={"b"})
        self.engine._previous = ControllerState(connected=True)

        self.engine._handle_overworld_remap(state_b, self.rect, {}, now=0.0)

        self.engine.injector.tap.assert_not_called()
        self.assertFalse(self.engine._quest_b_consumed)


if __name__ == "__main__":
    unittest.main()
