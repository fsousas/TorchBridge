"""Testes unitários para o módulo de leitura direta de memória RAM."""
import unittest
from unittest.mock import MagicMock, patch

from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    GAMEPLAY_MENUS,
    MAIN_MENU_STATES,
    GameMemoryState,
    TorchlightMemoryReader,
)
from torchbridge.models import OverlaySnapshot, SharedOverlayState


class MemoryModuleTests(unittest.TestCase):
    def test_default_memory_state(self):
        state = GameMemoryState()
        self.assertFalse(state.is_connected)
        self.assertIsNone(state.pid)
        self.assertFalse(state.is_in_game)
        self.assertFalse(state.is_loading)
        self.assertFalse(state.is_menu_open)
        self.assertEqual(state.open_menus, [])
        self.assertEqual(state.recommended_mode, "direct")

    def test_main_menu_states_mapping(self):
        self.assertEqual(MAIN_MENU_STATES[0], "Tela Inicial")
        self.assertEqual(MAIN_MENU_STATES[1], "Criar Personagem")
        self.assertEqual(MAIN_MENU_STATES[3], "Carregar Personagem")
        self.assertEqual(MAIN_MENU_STATES[6], "Em Jogo")

    def test_gameplay_menus_offsets_defined(self):
        self.assertIn("Inventário", GAMEPLAY_MENUS)
        self.assertIn("Atributos", GAMEPLAY_MENUS)
        self.assertIn("Pet", GAMEPLAY_MENUS)
        self.assertIn("Habilidades", GAMEPLAY_MENUS)
        self.assertIn("Missões (Quests)", GAMEPLAY_MENUS)
        self.assertIn("Diário (Journal)", GAMEPLAY_MENUS)
        self.assertIn("Portal (Waypoint)", GAMEPLAY_MENUS)

    def test_snapshot_includes_memory_fields(self):
        snapshot = OverlaySnapshot(
            memory_state_desc="Em Jogo",
            memory_is_in_game=True,
            memory_is_loading=False,
            memory_is_menu_open=True,
            memory_open_menus=["Inventário", "Pet"],
        )
        self.assertEqual(snapshot.memory_state_desc, "Em Jogo")
        self.assertTrue(snapshot.memory_is_in_game)
        self.assertFalse(snapshot.memory_is_loading)
        self.assertTrue(snapshot.memory_is_menu_open)
        self.assertEqual(snapshot.memory_open_menus, ["Inventário", "Pet"])

    def test_shared_state_publishes_memory_fields(self):
        shared = SharedOverlayState()
        shared.update(
            memory_state_desc="Carregando...",
            memory_is_loading=True,
            memory_is_in_game=True,
            memory_is_menu_open=False,
            memory_open_menus=[],
        )
        snap = shared.get()
        self.assertEqual(snap.memory_state_desc, "Carregando...")
        self.assertTrue(snap.memory_is_loading)
        self.assertTrue(snap.memory_is_in_game)
        self.assertFalse(snap.memory_is_menu_open)
        self.assertEqual(snap.memory_open_menus, [])

    @patch("torchbridge.memory.kernel32")
    def test_memory_reader_lifecycle(self, mock_kernel):
        reader = TorchlightMemoryReader()
        self.assertIsNone(reader.pid)
        self.assertIsNone(reader._handle)
        reader.close()
        self.assertIsNone(reader._handle)


if __name__ == "__main__":
    unittest.main()
