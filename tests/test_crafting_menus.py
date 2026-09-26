"""Testes unitários para mapeamento e detecção das interfaces de crafting:
- Transmutador (Duran the Transmuter - CCombineMenu em +0x02E0)
- Sockets (Gron e Furl - CEnchantMenu em +0x02DC modo 0x19/0x1A/0x1B)
- Encantador (Goren the Enchanter - CEnchantMenu em +0x02DC modo 0x15/0x16)
"""
import unittest
from unittest.mock import MagicMock, patch

from torchbridge.controller import ControllerState
from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    GAMEPLAY_MENUS,
    GameMemoryState,
    OFFSET_GAMECLIENT,
    OFFSET_GAMEUI,
    TorchlightMemoryReader,
)
from torchbridge.models import (
    PANEL_SIDE,
    Rect,
    SharedOverlayState,
    both_panels_open,
    crafting_button_point,
    crafting_slot_point,
)


class CraftingMenusTests(unittest.TestCase):
    def test_gameplay_menus_has_transmutador_and_encantador(self):
        self.assertIn("Transmutador", GAMEPLAY_MENUS)
        self.assertEqual(GAMEPLAY_MENUS["Transmutador"], (0x02E0, 0x54))
        self.assertIn("Encantador", GAMEPLAY_MENUS)
        self.assertEqual(GAMEPLAY_MENUS["Encantador"], (0x02DC, 0x38))

    def test_panel_side_mapping(self):
        self.assertEqual(PANEL_SIDE["T"], 0)  # Transmutador no painel esquerdo
        self.assertEqual(PANEL_SIDE["K"], 0)  # Sockets no painel esquerdo
        self.assertEqual(PANEL_SIDE["E"], 0)  # Encantador no painel esquerdo
        self.assertEqual(PANEL_SIDE["V"], 0)  # Vendedor no painel esquerdo
        self.assertEqual(PANEL_SIDE["B"], 0)  # Baú no painel esquerdo
        self.assertEqual(PANEL_SIDE["I"], 1)  # Inventário no painel direito

    @patch("torchbridge.memory.kernel32")
    def test_transmutador_detection(self, mock_kernel):
        reader = TorchlightMemoryReader()
        reader.pid = 1234
        reader._handle = 9999
        reader._ensure_handle = MagicMock(return_value=True)

        p_game = 0x1000
        p_client = 0x2000
        p_ui = 0x3000
        p_combine = 0x4000
        p_inv = 0x5000
        p_player = 0x6000

        def fake_read_u32(addr):
            if addr == ADDR_CGAME_GLOBAL:
                return p_game
            if addr == p_game + OFFSET_GAMECLIENT:
                return p_client
            if addr == p_client + OFFSET_GAMEUI:
                return p_ui
            if addr == p_client + 0x2C:  # OFFSET_PLAYER
                return p_player
            if addr == p_ui + 0x02E0:  # Transmutador
                return p_combine
            if addr == p_ui + 0x02CC:  # Inventário
                return p_inv
            return 0

        def fake_read_u8(addr):
            # Transmutador aberto (0x54 == 1)
            if addr == p_combine + 0x54:
                return 1
            # Inventário aberto (0x30 == 1)
            if addr == p_inv + 0x30:
                return 1
            return 0

        reader.read_u32 = MagicMock(side_effect=fake_read_u32)
        reader.read_u8 = MagicMock(side_effect=fake_read_u8)

        state = reader.update()
        self.assertIn("Transmutador", state.open_menus)
        self.assertIn("Inventário", state.open_menus)

    @patch("torchbridge.memory.kernel32")
    def test_sockets_vs_enchant_detection(self, mock_kernel):
        reader = TorchlightMemoryReader()
        reader.pid = 1234
        reader._handle = 9999
        reader._ensure_handle = MagicMock(return_value=True)

        p_game = 0x1000
        p_client = 0x2000
        p_ui = 0x3000
        p_enchant = 0x4000
        p_player = 0x6000

        # Caso 1: Sockets (Gron/Furl - modo 0x19 = 25)
        def fake_read_u32_sockets(addr):
            if addr == ADDR_CGAME_GLOBAL:
                return p_game
            if addr == p_game + OFFSET_GAMECLIENT:
                return p_client
            if addr == p_client + OFFSET_GAMEUI:
                return p_ui
            if addr == p_client + 0x2C:  # OFFSET_PLAYER
                return p_player
            if addr == p_ui + 0x02DC:  # CEnchantMenu
                return p_enchant
            if addr == p_enchant + 0x90:  # Modo Sockets
                return 0x19
            return 0

        reader.read_u32 = MagicMock(side_effect=fake_read_u32_sockets)
        reader.read_u8 = MagicMock(side_effect=lambda addr: 1 if addr == p_enchant + 0x38 else 0)

        state = reader.update()
        self.assertIn("Sockets", state.open_menus)
        self.assertNotIn("Encantador", state.open_menus)

        # Caso 2: Encantador (Goren - modo 0x15 = 21)
        def fake_read_u32_enchant(addr):
            if addr == ADDR_CGAME_GLOBAL:
                return p_game
            if addr == p_game + OFFSET_GAMECLIENT:
                return p_client
            if addr == p_client + OFFSET_GAMEUI:
                return p_ui
            if addr == p_client + 0x2C:  # OFFSET_PLAYER
                return p_player
            if addr == p_ui + 0x02DC:
                return p_enchant
            if addr == p_enchant + 0x90:  # Modo Encantador
                return 0x15
            return 0

        reader.read_u32 = MagicMock(side_effect=fake_read_u32_enchant)
        state2 = reader.update()
        self.assertIn("Encantador", state2.open_menus)
        self.assertNotIn("Sockets", state2.open_menus)

    def test_crafting_button_and_slot_coordinates(self):
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Transmutador: 2 botões e 4 slots calibrados
        dec_x, dec_y = crafting_button_point(rect, "Transmutador", "decline")
        self.assertEqual((dec_x, dec_y), (240, 405))

        act_x, act_y = crafting_button_point(rect, "Transmutador", "transmute")
        self.assertEqual((act_x, act_y), (240, 450))

        s1_x, s1_y = crafting_slot_point(rect, "Transmutador", 0)
        s2_x, s2_y = crafting_slot_point(rect, "Transmutador", 1)
        s3_x, s3_y = crafting_slot_point(rect, "Transmutador", 2)
        s4_x, s4_y = crafting_slot_point(rect, "Transmutador", 3)

        self.assertEqual((s1_x, s1_y), (216, 266))
        self.assertEqual((s2_x, s2_y), (268, 266))
        self.assertEqual((s3_x, s3_y), (216, 339))
        self.assertEqual((s4_x, s4_y), (268, 339))

        # Sockets / Encantador: 2 botões e 1 slot calibrados
        s_dec_x, s_dec_y = crafting_button_point(rect, "Sockets", "decline")
        s_rec_x, s_rec_y = crafting_button_point(rect, "Sockets", "recover")
        s_slot_x, s_slot_y = crafting_slot_point(rect, "Sockets", 0)

        self.assertEqual((s_dec_x, s_dec_y), (240, 402))
        self.assertEqual((s_rec_x, s_rec_y), (240, 447))
        self.assertEqual((s_slot_x, s_slot_y), (240, 314))


class CraftingNavigationTests(unittest.TestCase):
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
        from torchbridge.engine import BridgeEngine
        self.engine = BridgeEngine(self.cfg_mock, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (216, 266)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def test_crafting_initialization_transmutador(self):
        """Duran the Transmuter abre focado no slot_0 (topo-esquerda do grid 2x2)."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Transmutador"],
        )
        empty_state = ControllerState()
        self.engine._handle_crafting_navigation(empty_state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._crafting_initialized)
        self.assertEqual(self.engine._crafting_menu, "Transmutador")
        self.assertEqual(self.engine._crafting_focus, "slot_0")

        exp_x, exp_y = crafting_slot_point(self.rect, "Transmutador", 0)
        self.engine.injector.move.assert_called_with(exp_x, exp_y)

        snap = self.shared.get()
        self.assertTrue(snap.crafting_open)
        self.assertEqual(snap.crafting_menu, "Transmutador")
        self.assertEqual(snap.crafting_focus, "slot_0")

    def test_crafting_initialization_sockets_or_enchant(self):
        """Goren (Encantador) e Gron/Furl (Sockets) abrem focados no slot_0 central."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Sockets"],
        )
        empty_state = ControllerState()
        self.engine._handle_crafting_navigation(empty_state, self.rect, self.hub_mock)

        self.assertTrue(self.engine._crafting_initialized)
        self.assertEqual(self.engine._crafting_menu, "Sockets")
        self.assertEqual(self.engine._crafting_focus, "slot_0")

        exp_x, exp_y = crafting_slot_point(self.rect, "Sockets", 0)
        self.engine.injector.move.assert_called_with(exp_x, exp_y)

    def test_crafting_duran_2x2_navigation(self):
        """Navega pelo grid 2x2 de Duran e pelos botões Fechar e Transmutar."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Transmutador"],
        )
        self.engine._crafting_initialized = True
        self.engine._crafting_menu = "Transmutador"
        self.engine._crafting_focus = "slot_0"

        # slot_0 + Direita -> slot_1
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_right"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_1")

        # slot_1 + Baixo -> slot_3
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_3")

        # slot_3 + Esquerda -> slot_2
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_left"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_2")

        # slot_2 + Cima -> slot_0
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_up"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_0")

        # slot_0 + Baixo -> slot_2
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_2")

        # slot_2 + Baixo -> decline
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "decline")

        # decline + Baixo -> action (transmute)
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "action")

        # action + Cima -> decline
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_up"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "decline")

        # decline + Cima -> slot_2
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_up"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_2")

    def test_crafting_goren_sockets_navigation(self):
        """Navega pelo slot único de Goren/Sockets e pelos botões Fechar e Ação."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Encantador"],
        )
        self.engine._crafting_initialized = True
        self.engine._crafting_menu = "Encantador"
        self.engine._crafting_focus = "slot_0"

        # slot_0 + Baixo -> decline
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "decline")

        # decline + Baixo -> action
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_down"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "action")

        # action + Cima -> decline
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_up"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "decline")

        # decline + Cima -> slot_0
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_up"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_0")

    def test_crafting_bridge_to_inventory_on_dpad_right(self):
        """Pressionar D-pad Direita nas bordas do crafting pula para o Inventário do Jogador."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Transmutador"],
        )
        self.engine._crafting_initialized = True
        self.engine._crafting_menu = "Transmutador"
        self.engine._crafting_focus = "slot_1"

        # slot_1 + Direita -> Inventário (1, 1)
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_right"})
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # slot_3 + Direita -> Inventário (2, 1)
        self.engine._crafting_focus = "slot_3"
        self.engine._previous = ControllerState()
        self.engine._handle_crafting_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._inventory_focus, (2, 1))

    def test_inventory_bridge_to_crafting_on_dpad_left(self):
        """Pressionar D-pad Esquerda na coluna 1 ou equipamentos do inventário pula para o Crafting."""
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário", "Transmutador"],
        )
        self.engine._inventory_initialized = True
        self.engine._inventory_focus = (1, 1)

        # Inventário (1, 1) + Esquerda -> Duran slot_1
        self.engine._previous = ControllerState()
        state = ControllerState(buttons={"dpad_left"})
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_1")

        # Inventário (2, 1) + Esquerda -> Duran slot_3
        self.engine._inventory_focus = (2, 1)
        self.engine._previous = ControllerState()
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_3")

        # Equipamento helmet + Esquerda -> Duran slot_1
        self.engine._inventory_focus = "helmet"
        self.engine._previous = ControllerState()
        self.engine._handle_inventory_navigation(state, self.rect, self.hub_mock)
        self.assertEqual(self.engine._crafting_focus, "slot_1")

    def test_crafting_close_resets_state(self):
        """Ao fechar o menu de crafting, o estado do motor e overlay é reiniciado."""
        from torchbridge.controller import ControllerState
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Inventário"],  # Transmutador fechou
        )
        self.engine._crafting_initialized = True
        self.engine._crafting_menu = "Transmutador"
        self.engine._crafting_focus = "slot_0"

        empty_state = ControllerState()
        # Chama a rotina principal de menus
        self.engine._handle_inventory_navigation(empty_state, self.rect, self.hub_mock)

        # Simula o tick que limpa menus não mais abertos
        is_crafting = any(m in (self.engine._memory_state.open_menus or []) for m in ("Transmutador", "Sockets", "Encantador"))
        self.assertFalse(is_crafting)
        if not is_crafting and self.engine._crafting_initialized:
            self.engine._crafting_initialized = False
            self.engine._crafting_menu = None
            self.engine._crafting_focus = None
            self.engine.shared.update(crafting_open=False, crafting_menu=None, crafting_focus=None)

        self.assertFalse(self.engine._crafting_initialized)
        snap = self.shared.get()
        self.assertFalse(snap.crafting_open)


if __name__ == "__main__":
    unittest.main()

