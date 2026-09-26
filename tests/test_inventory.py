"""Testes unitários para o Mapeamento e Navegação do Inventário do Jogador:
- Coordenadas de Abas (1, 2, 3) e Slots (Grid 3x7 + 16 Equipamentos superiores)
- Âncoragem à borda direita da tela (proporção e escalonamento)
- Navegação entre abas com L2/R2 (1 -> 2 -> 3 -> 1 e 1 -> 3 -> 2 -> 1)
- Navegação pelo grid 3x7 via D-pad com wrap-around horizontal e bloqueio inferior
- Transição suave entre grid inferior e slots de equipamento superiores
- Preservação do movimento direto do personagem (Left Stick) e menu radial (LB) quando apenas o inventário está aberto
- Reset ao fechar o inventário
"""
import unittest
from unittest.mock import MagicMock

from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    INVENTORY_GRID_COLS,
    INVENTORY_GRID_ROWS,
    INVENTORY_TAB_COORDS,
    INVENTORY_UPPER_COORDS,
    INVENTORY_UPPER_NAV_MAP,
    PET_GRID_COLS,
    PET_GRID_ROWS,
    PET_TAB_COORDS,
    PET_UPPER_COORDS,
    PET_UPPER_NAV_MAP,
    Rect,
    SharedOverlayState,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    pet_inventory_upper_point,
)


class InventoryCoordinatesTests(unittest.TestCase):
    def test_inventory_tab_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Tab 1: base (752.5, 492.5) -> (752, 492) ou (753, 492)
        t1_x, t1_y = inventory_tab_point(rect, 1)
        self.assertEqual((t1_x, t1_y), (752, 492) if t1_x == 752 else (753, 492))

        # Tab 2: base (852.5, 492.5) -> (852, 492) ou (853, 492)
        t2_x, t2_y = inventory_tab_point(rect, 2)
        self.assertEqual((t2_x, t2_y), (852, 492) if t2_x == 852 else (853, 492))

        # Tab 3: base (952.5, 492.5) -> (952, 492) ou (953, 492)
        t3_x, t3_y = inventory_tab_point(rect, 3)
        self.assertEqual((t3_x, t3_y), (952, 492) if t3_x == 952 else (953, 492))

    def test_inventory_grid_slot_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Slot (1, 1): base (739.5, 520.5)
        s11_x, s11_y = inventory_slot_point(rect, 1, 1)
        self.assertEqual((s11_x, s11_y), (740, 520) if s11_x == 740 else (739, 520))

        # Slot (1, 7): base 739.5 + 6 * 40 = 979.5, y = 520.5
        s17_x, s17_y = inventory_slot_point(rect, 1, 7)
        self.assertEqual((s17_x, s17_y), (980, 520) if s17_x == 980 else (979, 520))

        # Slot (3, 7): y = 520.5 + 2 * 55 = 630.5
        s37_x, s37_y = inventory_slot_point(rect, 3, 7)
        self.assertEqual((s37_x, s37_y), (980, 630) if s37_x == 980 else (979, 631))

    def test_inventory_upper_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Spell 1: base (779.5, 409.5)
        sp1_x, sp1_y = inventory_upper_point(rect, "spell_1")
        self.assertEqual((sp1_x, sp1_y), (780, 410))

        # Helmet: base (729.5, 107.5)
        helm_x, helm_y = inventory_upper_point(rect, "helmet")
        self.assertEqual((helm_x, helm_y), (730, 108))

        # Shoulders: base (962.5, 107.5)
        shld_x, shld_y = inventory_upper_point(rect, "shoulders")
        self.assertEqual((shld_x, shld_y), (962, 108) if shld_x == 962 else (963, 108))

    def test_right_edge_anchoring_on_ultrawide_and_16x9(self):
        # Em 1920x1080 (16:9), scale = 1080 / 768 = 1.40625
        # dist_from_right = (1024 - 952.5) * 1.40625 = 71.5 * 1.40625 = 100.54
        # x = 1920 - 100.54 = ~1819
        rect_169 = Rect(left=0, top=0, width=1920, height=1080)
        t3_x, _ = inventory_tab_point(rect_169, 3)
        self.assertTrue(1815 <= t3_x <= 1825)


class PetCoordinatesTests(unittest.TestCase):
    def test_pet_tab_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Tab 1: base (69.5, 495.5)
        t1_x, t1_y = pet_inventory_tab_point(rect, 1)
        self.assertEqual((t1_x, t1_y), (70, 496) if t1_x == 70 else (69, 496))

        # Tab 2: base (169.5, 495.5)
        t2_x, t2_y = pet_inventory_tab_point(rect, 2)
        self.assertEqual((t2_x, t2_y), (170, 496) if t2_x == 170 else (169, 496))

        # Tab 3: base (269.5, 495.5)
        t3_x, t3_y = pet_inventory_tab_point(rect, 3)
        self.assertEqual((t3_x, t3_y), (270, 496) if t3_x == 270 else (269, 496))

    def test_pet_grid_slot_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Slot (1, 1): base (56.5, 523.5)
        s11_x, s11_y = pet_inventory_slot_point(rect, 1, 1)
        self.assertEqual((s11_x, s11_y), (56, 524) if s11_x == 56 else (57, 524))

        # Slot (1, 7): base 56.5 + 6 * 40 = 296.5, y = 523.5
        s17_x, s17_y = pet_inventory_slot_point(rect, 1, 7)
        self.assertEqual((s17_x, s17_y), (296, 524) if s17_x == 296 else (297, 524))

        # Slot (3, 7): y = 523.5 + 2 * 55 = 633.5
        s37_x, s37_y = pet_inventory_slot_point(rect, 3, 7)
        self.assertEqual((s37_x, s37_y), (296, 634) if s37_x == 296 else (297, 634))

    def test_pet_upper_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Spell 1: base (96.5, 327.5)
        sp1_x, sp1_y = pet_inventory_upper_point(rect, "pet_spell_1")
        self.assertEqual((sp1_x, sp1_y), (96, 328) if sp1_x == 96 else (97, 328))

        # Collar: base (178.5, 338.5)
        col_x, col_y = pet_inventory_upper_point(rect, "pet_collar")
        self.assertEqual((col_x, col_y), (178, 338) if col_x == 178 else (179, 339))

        # Spell 2: base (282.5, 327.5)
        sp2_x, sp2_y = pet_inventory_upper_point(rect, "pet_spell_2")
        self.assertEqual((sp2_x, sp2_y), (282, 328) if sp2_x == 282 else (283, 328))

    def test_left_edge_anchoring_on_ultrawide_and_16x9(self):
        # Em 1920x1080 (16:9), scale = 1080 / 768 = 1.40625
        # Ancorado à borda esquerda (rect.left = 0):
        # x = 0 + 69.5 * 1.40625 = ~98
        rect_169 = Rect(left=0, top=0, width=1920, height=1080)
        t1_x, _ = pet_inventory_tab_point(rect_169, 1)
        self.assertTrue(95 <= t1_x <= 100)



import tempfile
from pathlib import Path

from torchbridge.config import ConfigManager


class InventoryNavigationEngineTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_initial_state_on_opening_inventory(self):
        # Abre o inventário pela primeira vez
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._inventory_initialized)
        self.assertEqual(self.engine._inventory_tab, "tab-1")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # Deve ter movido o mouse para o Slot (1, 1)
        expected_x, expected_y = inventory_slot_point(self.rect, 1, 1)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

    def test_tab_switching_r2_forward_cycle(self):
        # 1. Inicializa na Tab 1
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-1")

        # 2. Pressiona R2 na metade direita da tela: 1 -> 2
        self.engine.injector.cursor_position.return_value = (750, 500)  # metade direita
        self.engine._rt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-2")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 3. Pressiona R2 novamente: 2 -> 3
        self.engine._rt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-3")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 4. Pressiona R2 novamente na Tab 3: volta para Tab 1 (fluxo natural)
        self.engine._rt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-1")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

    def test_tab_switching_l2_backward_cycle(self):
        # 1. Inicializa na Tab 1
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-1")

        # 2. Pressiona L2 na Tab 1: 1 -> 3
        self.engine.injector.cursor_position.return_value = (750, 500)
        self.engine._lt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-3")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 3. Pressiona L2 na Tab 3: 3 -> 2
        self.engine._lt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-2")

        # 4. Pressiona L2 na Tab 2: 2 -> 1
        self.engine._lt_edge_up = True
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_tab, "tab-1")

    def test_tab_switching_ignored_on_left_half(self):
        # Cursor na metade esquerda (ex: x=300 < 512)
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.engine.injector.cursor_position.return_value = (300, 400)
        self.engine._rt_edge_up = True

        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        # Tab não deve mudar
        self.assertEqual(self.engine._inventory_tab, "tab-1")

    def test_dpad_grid_navigation_and_wraparound(self):
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)

        # 1. Direita a partir de (1, 1) -> (1, 2)
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 2))

        # 2. Estando em (1, 7) e mover para a direita -> (2, 1)
        self.engine._inventory_focus = (1, 7)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (2, 1))

        # 3. Estando em (2, 7) e mover para a direita -> (3, 1)
        self.engine._inventory_focus = (2, 7)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (3, 1))

        # 4. Estando em (3, 7) e mover para a direita -> volta para (1, 1)
        self.engine._inventory_focus = (3, 7)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 5. Estando em (1, 1) e mover para a esquerda -> (3, 7)
        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (3, 7))

        # 6. Estando em (3, 1) e mover para a esquerda -> (2, 7)
        self.engine._inventory_focus = (3, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (2, 7))

        # 7. Estando em (2, 1) e mover para a esquerda -> (1, 7)
        self.engine._inventory_focus = (2, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 7))

    def test_dpad_bottom_row_down_blocked(self):
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)

        # Na linha 3, mover para baixo não faz nada
        self.engine._inventory_focus = (3, 4)
        state_d = ControllerState(connected=True, buttons={"dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (3, 4))

    def test_dpad_transition_between_grid_and_upper_equipment(self):
        state = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)

        # Cima em (1, 1) -> spell_1
        self.engine._inventory_focus = (1, 1)
        state_u = ControllerState(connected=True, buttons={"dpad_up"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "spell_1")

        # Cima em spell_1 -> main_hand
        self.engine._handle_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "main_hand")

        # Cima em main_hand -> belt
        self.engine._handle_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "belt")

        # Cima em belt -> gloves
        self.engine._handle_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "gloves")

        # Cima em gloves -> helmet
        self.engine._handle_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "helmet")

        # Direita em helmet -> ring_1
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "ring_1")

        # Direita em ring_1 -> necklace
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "necklace")

        # Direita em necklace -> ring_2
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "ring_2")

        # Direita em ring_2 -> shoulders
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "shoulders")

        # Baixo em shoulders -> chest
        state_d = ControllerState(connected=True, buttons={"dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "chest")

        # Baixo em chest -> boots
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "boots")

        # Baixo em boots -> off_hand
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "off_hand")

        # Baixo em off_hand -> spell_4
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "spell_4")

        # Baixo em spell_4 -> volta para o grid (1, 7)!
        self.engine._handle_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 7))

    def test_direct_mode_preserved_when_only_inventory_open(self):
        # 1. Quando somente o inventário está aberto: effective_mode = direct
        self.engine._mode = "direct"
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            is_menu_open=True,
            open_menus=["Inventário"],
        )
        state = ControllerState(connected=True, lx=0.8, ly=0.0)
        self.engine._move_pointer(state, self.rect, self.config.get(), 0.016)

        # Moveu o ponteiro com click-to-move direto
        self.assertTrue(self.engine._direct_move_active)

    def test_cursor_mode_activated_when_multiple_menus_open(self):
        # 2. Quando mercador / baú / pet também está aberto: effective_mode = cursor
        self.engine._mode = "direct"
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            is_menu_open=True,
            open_menus=["Vendedor (Loja)", "Inventário"],
        )
        state = ControllerState(connected=True, lx=0.8, ly=0.0)
        self.engine._move_pointer(state, self.rect, self.config.get(), 0.016)

        # Não ativa o click-to-move de direct move
        self.assertFalse(self.engine._direct_move_active)

    def test_direct_mode_preserved_when_only_pet_open(self):
        # Quando somente o menu de Pet está aberto: effective_mode = direct
        self.engine._mode = "direct"
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            is_menu_open=True,
            open_menus=["Pet"],
        )
        state = ControllerState(connected=True, lx=0.8, ly=0.0)
        self.engine._move_pointer(state, self.rect, self.config.get(), 0.016)

        # Moveu o ponteiro com click-to-move direto
        self.assertTrue(self.engine._direct_move_active)

    def test_radial_menu_allowed_when_only_inventory_or_pet_open(self):
        # Permitido durante gameplay normal (sem menus)
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True, open_menus=[])
        self.assertTrue(self.engine._is_radial_allowed())

        # Permitido quando SOMENTE o inventário está aberto
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True, open_menus=["Inventário"])
        self.assertTrue(self.engine._is_radial_allowed())

        # Permitido quando SOMENTE o pet está aberto
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True, open_menus=["Pet"])
        self.assertTrue(self.engine._is_radial_allowed())

        # Permitido quando AMBOS Pet e Inventário estão abertos
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True, open_menus=["Pet", "Inventário"])
        self.assertTrue(self.engine._is_radial_allowed())

        # BLOQUEADO quando outro menu está aberto (ex: Vendedor, Baú)
        self.engine._memory_state = GameMemoryState(
            is_connected=True, is_in_game=True, open_menus=["Vendedor (Loja)", "Inventário"]
        )
        self.assertFalse(self.engine._is_radial_allowed())
        self.engine._memory_state = GameMemoryState(
            is_connected=True, is_in_game=True, open_menus=["Vendedor (Loja)", "Pet"]
        )
        self.assertFalse(self.engine._is_radial_allowed())


class PetNavigationEngineTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_initial_state_on_opening_pet_inventory(self):
        # Abre o menu de pet pela primeira vez
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._pet_inventory_initialized)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

        # Deve ter movido o mouse para o Slot 1 do Pet (1, 1)
        expected_x, expected_y = pet_inventory_slot_point(self.rect, 1, 1)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

    def test_pet_tab_switching_r2_forward_cycle(self):
        # 1. Inicializa na Tab 1
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")

        # 2. Pressiona R2 na metade esquerda da tela: 1 -> 2
        self.engine.injector.cursor_position.return_value = (200, 500)  # metade esquerda
        self.engine._rt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-2")
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

        # 3. Pressiona R2 novamente: 2 -> 3
        self.engine._rt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-3")
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

        # 4. Pressiona R2 novamente na Tab 3: volta para Tab 1 (fluxo natural)
        self.engine._rt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

    def test_pet_tab_switching_l2_backward_cycle(self):
        # 1. Inicializa na Tab 1
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")

        # 2. Pressiona L2 na Tab 1: 1 -> 3
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.engine._lt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-3")
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

        # 3. Pressiona L2 na Tab 3: 3 -> 2
        self.engine._lt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-2")

        # 4. Pressiona L2 na Tab 2: 2 -> 1
        self.engine._lt_edge_up = True
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")

    def test_pet_tab_switching_ignored_on_right_half(self):
        # Cursor na metade direita (ex: x=700 >= 512)
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        self.engine.injector.cursor_position.return_value = (700, 400)
        self.engine._rt_edge_up = True

        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)
        # Tab não deve mudar
        self.assertEqual(self.engine._pet_inventory_tab, "tab-1")

    def test_pet_dpad_grid_navigation_and_wraparound(self):
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)

        # 1. Direita a partir de (1, 1) -> (1, 2)
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 2))

        # 2. Estando em (1, 7) e mover para a direita -> (2, 1)
        self.engine._pet_inventory_focus = (1, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (2, 1))

        # 3. Estando em (2, 7) e mover para a direita -> (3, 1)
        self.engine._pet_inventory_focus = (2, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (3, 1))

        # 4. Estando em (3, 7) e mover para a direita -> volta para (1, 1)
        self.engine._pet_inventory_focus = (3, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 1))

        # 5. Estando em (1, 1) e mover para a esquerda -> (3, 7)
        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (3, 7))

        # 6. Estando em (3, 1) e mover para a esquerda -> (2, 7)
        self.engine._pet_inventory_focus = (3, 1)
        self.engine._handle_pet_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (2, 7))

        # 7. Estando em (2, 1) e mover para a esquerda -> (1, 7)
        self.engine._pet_inventory_focus = (2, 1)
        self.engine._handle_pet_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 7))

    def test_pet_dpad_bottom_row_down_blocked(self):
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)

        # Na linha 3, mover para baixo não faz nada
        self.engine._pet_inventory_focus = (3, 4)
        state_d = ControllerState(connected=True, buttons={"dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (3, 4))

    def test_pet_dpad_transition_between_grid_and_upper_equipment(self):
        state = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state, self.rect, self.hub_mock)

        # Cima em (1, 1) -> pet_spell_1
        self.engine._pet_inventory_focus = (1, 1)
        state_u = ControllerState(connected=True, buttons={"dpad_up"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_spell_1")

        # Direita em pet_spell_1 -> pet_ring_1
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_ring_1")

        # Direita em pet_ring_1 -> pet_collar
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_collar")

        # Direita em pet_collar -> pet_ring_2
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_ring_2")

        # Direita em pet_ring_2 -> pet_spell_2
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_spell_2")

        # Baixo em pet_spell_2 -> volta para o grid (1, 7)
        state_d = ControllerState(connected=True, buttons={"dpad_down"})
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_pet_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 7))

        # Cima em (1, 4) -> pet_collar
        self.engine._pet_inventory_focus = (1, 4)
        self.engine._handle_pet_inventory_navigation(state_u, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, "pet_collar")

        # Baixo em pet_collar -> volta para (1, 4)
        self.engine._handle_pet_inventory_navigation(state_d, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 4))


class DualInventoryTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_dual_inventory_dispatch_by_cursor_position(self):
        # Ambos os menus abertos e inicializados
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Inventário"],
        )
        self.engine._pet_inventory_initialized = True
        self.engine._pet_inventory_focus = (1, 1)
        self.engine._pet_inventory_tab = "tab-1"

        self.engine._inventory_initialized = True
        self.engine._inventory_focus = (1, 1)
        self.engine._inventory_tab = "tab-1"

        cfg = self.config.get()
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)

        # 1. Cursor na metade esquerda (x=200 < 512): D-pad navega no menu do Pet
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.0, 0.016)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 2))
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 2. Cursor na metade direita (x=800 >= 512): D-pad navega no Inventário do Jogador
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.engine._previous = ControllerState(connected=True)
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.05, 0.016)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 2))
        self.assertEqual(self.engine._inventory_focus, (1, 2))

    def test_trigger_combos_suppression_for_active_panel(self):
        # Configura trigger edges
        self.engine._rt_edge_up = True
        self.engine._lt_current = False
        bindings = {"rt": "4"}

        # Caso 1: Menu Pet aberto e cursor na metade esquerda -> combo suprimido (retorna sem tocar tecla)
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet"],
        )
        self.engine.injector.cursor_position.return_value = (200, 500)
        state = ControllerState(connected=True, rt=1.0)
        self.engine._previous_rt_active = False
        self.engine._update_trigger_edges(state)
        self.engine._tap_binding = MagicMock()
        self.engine._handle_trigger_combos(state, self.rect, bindings, 1.0)
        self.engine._tap_binding.assert_not_called()

        # Caso 2: Menu Inventário aberto e cursor na metade direita -> combo suprimido
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário"],
        )
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.engine._tap_binding = MagicMock()
        self.engine._handle_trigger_combos(state, self.rect, bindings, 1.0)
        self.engine._tap_binding.assert_not_called()

        # Caso 3: Menu Pet aberto mas cursor na metade direita -> não suprime (ou sem pet/inv aberto)
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=[],
        )
        self.engine._tap_binding = MagicMock()
        self.engine._handle_trigger_combos(state, self.rect, bindings, 1.0)
        self.engine._tap_binding.assert_called_with("4")

    def test_seam_jump_from_pet_to_inventory_grid_and_spells(self):
        # Ambos os menus abertos
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Inventário"],
        )
        self.engine._pet_inventory_initialized = True
        self.engine._inventory_initialized = True
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (200, 500)

        # 1. Pet (1, 7) + Direita -> Pula para Inventário (1, 1)
        self.engine._pet_inventory_focus = (1, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 2. Pet (2, 7) + Direita -> Pula para Inventário (2, 1)
        self.engine._pet_inventory_focus = (2, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (2, 1))

        # 3. Pet (3, 7) + Direita -> Pula para Inventário (3, 1)
        self.engine._pet_inventory_focus = (3, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (3, 1))

        # 4. Pet pet_spell_2 + Direita -> Pula para Inventário spell_1
        self.engine._pet_inventory_focus = "pet_spell_2"
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, "spell_1")

    def test_seam_jump_from_inventory_to_pet_grid_and_equipment(self):
        # Ambos os menus abertos
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Inventário"],
        )
        self.engine._pet_inventory_initialized = True
        self.engine._inventory_initialized = True
        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)

        # 1. Inventário (1, 1) + Esquerda -> Pula para Pet (1, 7)
        self.engine._inventory_focus = (1, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 7))

        # 2. Inventário (2, 1) + Esquerda -> Pula para Pet (2, 7)
        self.engine._inventory_focus = (2, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (2, 7))

        # 3. Inventário (3, 1) + Esquerda -> Pula para Pet (3, 7)
        self.engine._inventory_focus = (3, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (3, 7))

        # 4. Equipamentos/spells da borda esquerda do Inventário -> Pula para Pet pet_spell_2
        for eq in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
            self.engine._inventory_focus = eq
            self.engine._pet_inventory_focus = None
            self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
            self.assertEqual(self.engine._pet_inventory_focus, "pet_spell_2", f"Falhou para {eq}")

    def test_option_3_isolated_outer_edges(self):
        # Ambos os menus abertos: as bordas externas NÃO pulam de menu, fazem wrap interno
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Inventário"],
        )
        self.engine._pet_inventory_initialized = True
        self.engine._inventory_initialized = True

        # 1. Pet Coluna 1 (borda externa esquerda) + Esquerda -> continua dando wrap dentro do Pet
        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.engine._pet_inventory_focus = (1, 1)
        self.engine._handle_pet_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._pet_inventory_focus, (3, 7))

        # 2. Inventário Coluna 7 (borda externa direita) + Direita -> continua dando wrap dentro do Inventário
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.engine._inventory_focus = (1, 7)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (2, 1))

        self.engine._inventory_focus = (3, 7)
        self.engine._handle_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 1))


class MoveCursorWithLeaveStepTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_grid_to_grid_normal_snappy_zero_delay(self):
        self.engine._move_cursor_with_leave_step((1, 1), 740, 520, 780, 520, self.rect)
        self.assertEqual(self.engine.injector.move.call_count, 1)
        self.engine.injector.move.assert_called_with(780, 520)

    def test_leaving_spell_within_same_panel(self):
        sp2_x, sp2_y = inventory_upper_point(self.rect, "spell_2")
        target_x, target_y = inventory_slot_point(self.rect, 1, 3)
        self.engine._move_cursor_with_leave_step("spell_2", sp2_x, sp2_y, target_x, target_y, self.rect)
        self.assertEqual(self.engine.injector.move.call_count, 2)
        self.assertEqual(self.engine.injector.move.call_args_list[0][0], (sp2_x, sp2_y + 35))
        self.assertEqual(self.engine.injector.move.call_args_list[1][0], (target_x, target_y))

    def test_leaving_spell_cross_screen(self):
        sp1_x, sp1_y = inventory_upper_point(self.rect, "spell_1")
        target_x, target_y = pet_inventory_upper_point(self.rect, "pet_spell_2")
        self.engine._move_cursor_with_leave_step("spell_1", sp1_x, sp1_y, target_x, target_y, self.rect)
        self.assertEqual(self.engine.injector.move.call_count, 3)
        self.assertEqual(self.engine.injector.move.call_args_list[0][0], (sp1_x, sp1_y + 35))
        mid_x = (sp1_x + target_x) // 2
        mid_y = (sp1_y + 35 + target_y) // 2
        self.assertEqual(self.engine.injector.move.call_args_list[1][0], (mid_x, mid_y))
        self.assertEqual(self.engine.injector.move.call_args_list[2][0], (target_x, target_y))

    def test_grid_cross_screen_bridge(self):
        cur_x, cur_y = pet_inventory_slot_point(self.rect, 1, 7)
        target_x, target_y = inventory_slot_point(self.rect, 1, 1)
        self.engine._move_cursor_with_leave_step((1, 7), cur_x, cur_y, target_x, target_y, self.rect)
        self.assertEqual(self.engine.injector.move.call_count, 2)
        mid_x = (cur_x + target_x) // 2
        mid_y = (cur_y + target_y) // 2
        self.assertEqual(self.engine.injector.move.call_args_list[0][0], (mid_x, mid_y))
        self.assertEqual(self.engine.injector.move.call_args_list[1][0], (target_x, target_y))


if __name__ == "__main__":
    unittest.main()


