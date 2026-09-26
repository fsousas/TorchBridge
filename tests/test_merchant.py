"""Testes unitários para o Mapeamento e Navegação do Menu do Mercador (Lojas / Vendedores):
- Coordenadas de Abas Rosa (Misc, Weapon, Armor) e Slots (Grid 6x7 de 42 slots)
- Detecção automática de NPC e aba default (Kolos/Duros -> WEAPONS, Tarn/Triya -> MISC)
- Posicionamento inicial no Ponto Amarelo (1, 1)
- Subida da Linha 1 para a Aba Rosa ativa via D-pad Cima
- Navegação horizontal entre as Abas Rosa com Wrap cíclico via D-pad Esquerda/Direita
- Confirmação de troca de aba com Botão X/A (clique rosa -> teleporta para o Ponto Amarelo 1, 1)
- Navegação vertical contínua entre Mercador Linha 6 e Pet Linha 1
- Pontes bidirecionais entre Coluna 7 e Inventário Direito
- L2 e R2 dedicados à troca de abas Ciano do Pet na metade esquerda
- Reset ao fechar a loja
"""
import unittest
from unittest.mock import MagicMock

from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    MERCHANT_GRID_COLS,
    MERCHANT_GRID_ROWS,
    MERCHANT_TABS_COORDS,
    Rect,
    SharedOverlayState,
    merchant_slot_point,
    merchant_tab_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    inventory_slot_point,
    inventory_upper_point,
)


class MerchantCoordinatesTests(unittest.TestCase):
    def test_merchant_tab_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Tab 1 (Misc): base (88.0, 78.0)
        t1_x, t1_y = merchant_tab_point(rect, 1)
        self.assertEqual((t1_x, t1_y), (88, 78))

        # Tab 2 (Weapon): base (183.0, 78.0)
        t2_x, t2_y = merchant_tab_point(rect, 2)
        self.assertEqual((t2_x, t2_y), (183, 78))

        # Tab 3 (Armor): base (278.0, 78.0)
        t3_x, t3_y = merchant_tab_point(rect, 3)
        self.assertEqual((t3_x, t3_y), (278, 78))

    def test_merchant_grid_slot_coordinates_base(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        # Slot (1, 1) - Ponto Amarelo: base (63.5, 109.5)
        s11_x, s11_y = merchant_slot_point(rect, 1, 1)
        self.assertEqual((s11_x, s11_y), (64, 110))

        # Slot (1, 7): base 63.5 + 6 * 40.0 = 303.5, y = 109.5
        s17_x, s17_y = merchant_slot_point(rect, 1, 7)
        self.assertEqual((s17_x, s17_y), (304, 110))

        # Slot (6, 7): x = 303.5, y = 387.5
        s67_x, s67_y = merchant_slot_point(rect, 6, 7)
        self.assertEqual((s67_x, s67_y), (304, 388))


class MerchantNavigationTests(unittest.TestCase):
    def setUp(self):
        self.cfg_mock = MagicMock()
        self.cfg_mock.get.return_value = {
            "target": {"process_names": ["Torchlight.exe"], "window_titles": ["Torchlight"]},
            "movement": {"initial_mode": "cursor"},
            "bindings": {},
            "cursor": {"speed_pixels_per_second": 800},
            "overlay": {},
        }
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.cfg_mock, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (64, 110)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def test_merchant_initialization_kolos_opens_tab2_weapons(self):
        """Kolos the Smith abre automaticamente na aba WEAPONS (tab-2) e no ponto amarelo (1, 1)."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Vendedor (Loja)"],
            merchant_npc_name="Kolos the Smith",
        )
        empty_state = ControllerState()
        self.engine._handle_merchant_navigation(empty_state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._merchant_initialized)
        self.assertEqual(self.engine._merchant_tab, "tab-2")
        self.assertEqual(self.engine._merchant_focus, ("merchant", 1, 1))

        # Move cursor para o ponto amarelo (1, 1)
        expected_x, expected_y = merchant_slot_point(self.rect, 1, 1)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

        # Snapshot do overlay atualizado
        snap = self.shared.get()
        self.assertTrue(snap.merchant_open)
        self.assertEqual(snap.merchant_tab, "tab-2")
        self.assertEqual(snap.merchant_focus, "('merchant', 1, 1)")
        self.assertEqual(snap.merchant_npc_name, "Kolos the Smith")

    def test_merchant_initialization_tarn_opens_tab1_misc(self):
        """Tarn the Merchant abre automaticamente na aba MISC (tab-1) e no ponto amarelo (1, 1)."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Vendedor (Loja)"],
            merchant_npc_name="Tarn the Merchant",
        )
        empty_state = ControllerState()
        self.engine._handle_merchant_navigation(empty_state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._merchant_initialized)
        self.assertEqual(self.engine._merchant_tab, "tab-1")
        self.assertEqual(self.engine._merchant_focus, ("merchant", 1, 1))

    def test_dpad_up_from_row1_goes_to_active_pink_tab(self):
        """Estando na Linha 1, pressionar D-pad Cima sobe diretamente para a aba ativa (rosa)."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-2"
        self.engine._merchant_focus = ("merchant", 1, 3)
        self.engine._previous = ControllerState()

        state_up = ControllerState(buttons={"dpad_up"})
        self.engine._handle_merchant_navigation(state_up, self.rect, self.hub_mock)

        self.assertEqual(self.engine._merchant_focus, ("merchant_tab", 2))
        expected_x, expected_y = merchant_tab_point(self.rect, 2)
        self.engine.injector.move.assert_called_with(expected_x, expected_y)

    def test_pink_tab_horizontal_wrap(self):
        """Nas abas rosa, D-pad Direita e Esquerda ciclam com wrap (1 <-> 2 <-> 3 <-> 1)."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-3"
        self.engine._merchant_focus = ("merchant_tab", 3)
        self.engine._previous = ControllerState()

        # Tab 3 + Direita -> Tab 1 (wrap)
        state_right = ControllerState(buttons={"dpad_right"})
        self.engine._handle_merchant_navigation(state_right, self.rect, self.hub_mock)
        self.assertEqual(self.engine._merchant_focus, ("merchant_tab", 1))

        # Tab 1 + Esquerda -> Tab 3 (wrap)
        self.engine._previous = ControllerState()
        state_left = ControllerState(buttons={"dpad_left"})
        self.engine._handle_merchant_navigation(state_left, self.rect, self.hub_mock)
        self.assertEqual(self.engine._merchant_focus, ("merchant_tab", 3))

    def test_pink_tab_dpad_down_returns_to_row1(self):
        """Estando na aba rosa, pressionar D-pad Baixo desce de volta para a Linha 1 do grid."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-2"
        self.engine._merchant_focus = ("merchant_tab", 2)
        self.engine._previous = ControllerState()

        state_down = ControllerState(buttons={"dpad_down"})
        self.engine._handle_merchant_navigation(state_down, self.rect, self.hub_mock)
        self.assertEqual(self.engine._merchant_focus, ("merchant", 1, 4))

    def test_pink_tab_confirm_click_returns_to_yellow_slot(self):
        """Ao pressionar X/A sobre uma aba rosa, clica na aba e retorna imediatamente ao ponto amarelo (1, 1)."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-1"
        self.engine._merchant_focus = ("merchant_tab", 3)
        self.engine._previous = ControllerState()

        state_a = ControllerState(buttons={"a"})
        self.engine._handle_merchant_navigation(state_a, self.rect, self.hub_mock)

        # Atualiza a aba ativa para tab-3
        self.assertEqual(self.engine._merchant_tab, "tab-3")
        # Retorna o foco para o ponto amarelo (1, 1)
        self.assertEqual(self.engine._merchant_focus, ("merchant", 1, 1))

        # Garante que clicou com mouse esquerdo
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)

        # Garante que moveu para o ponto amarelo
        yellow_x, yellow_y = merchant_slot_point(self.rect, 1, 1)
        self.engine.injector.move.assert_called_with(yellow_x, yellow_y)

    def test_vertical_continuous_navigation_merchant_and_pet(self):
        """Linha 6 do Mercador + Baixo -> Linha 1 do Pet; Linha 1 do Pet + Cima -> Linha 6 do Mercador."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-2"
        self.engine._merchant_focus = ("merchant", 6, 4)
        self.engine._previous = ControllerState()

        # Desce de Mercador L6 para Pet L1 (mantém coluna 4)
        state_down = ControllerState(buttons={"dpad_down"})
        self.engine._handle_merchant_navigation(state_down, self.rect, self.hub_mock)
        self.assertEqual(self.engine._merchant_focus, ("pet", 1, 4))

        # Sobe de Pet L1 para Mercador L6 (mantém coluna 4)
        self.engine._previous = ControllerState()
        state_up = ControllerState(buttons={"dpad_up"})
        self.engine._handle_merchant_navigation(state_up, self.rect, self.hub_mock)
        self.assertEqual(self.engine._merchant_focus, ("merchant", 6, 4))

    def test_bridge_from_merchant_col7_to_inventory_right(self):
        """Coluna 7 do Mercador + Direita transita para os equipamentos da direita."""
        self.engine._merchant_initialized = True
        self.engine._merchant_tab = "tab-2"
        self.engine._merchant_focus = ("merchant", 1, 7)
        self.engine._memory_state = GameMemoryState(open_menus=["Inventário", "Vendedor (Loja)"])
        self.engine._previous = ControllerState()

        state_right = ControllerState(buttons={"dpad_right"})
        self.engine._handle_merchant_navigation(state_right, self.rect, self.hub_mock)

        # Linha 1 Col 7 -> helmet
        self.assertEqual(self.engine._inventory_focus, "helmet")

    def test_bridge_from_inventory_right_to_merchant_col7(self):
        """Borda esquerda do Inventário + Esquerda transita para a Coluna 7 do Mercador."""
        self.engine._inventory_initialized = True
        self.engine._inventory_focus = "helmet"
        self.engine._memory_state = GameMemoryState(open_menus=["Inventário", "Vendedor (Loja)"])
        self.engine._previous = ControllerState()

        state_left = ControllerState(buttons={"dpad_left"})
        self.engine._handle_inventory_navigation(state_left, self.rect, self.hub_mock)

        # helmet -> Mercador Linha 1 Coluna 7
        self.assertEqual(self.engine._merchant_focus, ("merchant", 1, 7))


if __name__ == "__main__":
    unittest.main()
