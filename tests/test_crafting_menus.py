"""Testes unitários para mapeamento e detecção das interfaces de crafting:
- Transmutador (Duran the Transmuter - CCombineMenu em +0x02E0)
- Sockets (Gron e Furl - CEnchantMenu em +0x02DC modo 0x19/0x1A/0x1B)
- Encantador (Goren the Enchanter - CEnchantMenu em +0x02DC modo 0x15/0x16)
"""
import unittest
from unittest.mock import MagicMock, patch

from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    GAMEPLAY_MENUS,
    OFFSET_GAMECLIENT,
    OFFSET_GAMEUI,
    TorchlightMemoryReader,
)
from torchbridge.models import (
    PANEL_SIDE,
    Rect,
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


if __name__ == "__main__":
    unittest.main()
