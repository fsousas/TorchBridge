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
        self.assertEqual(state.char_name_len, 0)
        self.assertFalse(state.is_hover_interactive)
        self.assertEqual(state.hover_flag, 0)

    def test_main_menu_states_mapping(self):
        self.assertEqual(MAIN_MENU_STATES[0], "Tela Inicial")
        self.assertEqual(MAIN_MENU_STATES[1], "Criar Personagem")
        self.assertEqual(MAIN_MENU_STATES[2], "Selecionar Dificuldade")
        self.assertEqual(MAIN_MENU_STATES[3], "Carregar Personagem")
        self.assertEqual(MAIN_MENU_STATES[4], "Selecionar Dificuldade")
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
            char_name_len=7,
        )
        self.assertEqual(snapshot.memory_state_desc, "Em Jogo")
        self.assertTrue(snapshot.memory_is_in_game)
        self.assertFalse(snapshot.memory_is_loading)
        self.assertTrue(snapshot.memory_is_menu_open)
        self.assertEqual(snapshot.memory_open_menus, ["Inventário", "Pet"])
        self.assertEqual(snapshot.char_name_len, 7)

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

    def test_save_character_count_type(self):
        from torchbridge.memory import get_save_character_count
        count = get_save_character_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_audio_settings_keys(self):
        from torchbridge.memory import get_audio_settings
        audio = get_audio_settings()
        self.assertIn("sound_volume", audio)
        self.assertIn("music_volume", audio)
        self.assertIn("sound_mute", audio)
        self.assertIn("music_mute", audio)
        self.assertIsInstance(audio["sound_volume"], float)
        self.assertIsInstance(audio["music_volume"], float)

    def test_rva_constants_defined(self):
        from torchbridge.memory import RVA_CGAME_GOG, RVA_CGAME_STEAM, OFFSET_GAMECLIENT
        self.assertEqual(RVA_CGAME_GOG, 0x0081AD64)
        self.assertEqual(RVA_CGAME_STEAM, 0x007F0E0C)
        self.assertEqual(OFFSET_GAMECLIENT, 0x64)

    def test_resolve_cgame_address_steam(self):
        reader = TorchlightMemoryReader()
        reader._module_base = 0x008F0000
        reader._exe_path = r"E:\SteamLibrary\steamapps\common\Torchlight\Torchlight.exe"
        
        # Simula read_u32 retornando ponteiros válidos para o RVA Steam
        def fake_read_u32(addr):
            if addr == reader._module_base + 0x007F0E0C:
                return 0x054E24B8  # p_game
            if addr == 0x054E24B8 + 0x64:
                return 0x14CE7D58  # p_client
            return None

        reader.read_u32 = fake_read_u32
        resolved = reader._resolve_cgame_address()
        self.assertEqual(resolved, 0x008F0000 + 0x007F0E0C)
        self.assertEqual(reader.game_version, "Steam")

    def test_resolve_cgame_address_gog(self):
        reader = TorchlightMemoryReader()
        reader._module_base = 0x00400000
        reader._exe_path = r"C:\GOG Games\Torchlight\Torchlight.exe"
        
        # Simula read_u32 retornando ponteiros válidos para o RVA GOG
        def fake_read_u32(addr):
            if addr in (0x00C1AD64, reader._module_base + 0x0081AD64):
                return 0x044E24B8  # p_game
            if addr == 0x044E24B8 + 0x64:
                return 0x13CE7D58  # p_client
            return None

        reader.read_u32 = fake_read_u32
        resolved = reader._resolve_cgame_address()
        self.assertEqual(resolved, 0x00C1AD64)
        self.assertEqual(reader.game_version, "GOG")

    def test_update_with_target_pid(self):
        reader = TorchlightMemoryReader()
        # When target_pid is explicitly <= 0, ensure_handle returns False and reader is closed
        state = reader.update(target_pid=-1)
        self.assertFalse(state.is_connected)
        self.assertIsNone(reader.pid)

    def test_ui_state_loading_detection(self):
        """Valida que ui_state_id != 6 em CGameUI ativa imediatamente o estado Carregando..."""
        from torchbridge.memory import (
            OFFSET_GAMECLIENT,
            OFFSET_GAMEUI,
            OFFSET_MENU_MGR,
            OFFSET_MAIN_STATE,
            OFFSET_UI_STATE,
            OFFSET_PLAYER,
        )
        reader = TorchlightMemoryReader()
        reader.pid = 9999
        reader._handle = 1234
        reader._ensure_handle = MagicMock(return_value=True)

        p_game = 0x1000
        p_client = 0x2000
        p_ui = 0x3000
        p_menu_mgr = 0x4000
        p_player = 0x5000

        # Caso 1: ui_state_id = 1 (transição de masmorra disparada)
        def fake_read_transition(addr):
            if addr == ADDR_CGAME_GLOBAL:
                return p_game
            if addr == p_game + OFFSET_GAMECLIENT:
                return p_client
            if addr == p_client + OFFSET_GAMEUI:
                return p_ui
            if addr == p_client + OFFSET_PLAYER:
                return p_player
            if addr == p_ui + OFFSET_MENU_MGR:
                return p_menu_mgr
            if addr == p_menu_mgr + OFFSET_MAIN_STATE:
                return 6  # Em jogo no switch principal
            if addr == p_ui + OFFSET_UI_STATE:
                return 1  # Transição ativa no CGameUI
            return 0

        reader.read_u32 = MagicMock(side_effect=fake_read_transition)
        reader.read_u8 = MagicMock(return_value=0)

        state = reader.update()
        self.assertTrue(state.is_loading)
        self.assertFalse(state.is_in_game)
        self.assertEqual(state.state_desc, "Carregando...")

        # Caso 2: ui_state_id = 6 (jogabilidade normal)
        def fake_read_ingame(addr):
            if addr == p_ui + OFFSET_UI_STATE:
                return 6  # Gameplay ativo
            return fake_read_transition(addr)

        reader.read_u32 = MagicMock(side_effect=fake_read_ingame)
        state_ingame = reader.update()
        self.assertFalse(state_ingame.is_loading)
        self.assertTrue(state_ingame.is_in_game)
        self.assertEqual(state_ingame.state_desc, "Em Jogo")
        # Casting/reeling briefly hide the menu; they still own controller input.
        for mode in (0, 3, 32, 33, 34):
            reader.read_u32 = MagicMock(side_effect=lambda addr, mode=mode:
                mode if addr == p_player + 0x284 else fake_read_ingame(addr))
            self.assertEqual(reader.update().is_fishing, mode in (32, 33, 34))

    def test_hover_interactive_detection(self):
        """Valida detecção de entidades interativas (NPC=2, Baú=1) vs chão vazio (0)."""
        from torchbridge.memory import (
            OFFSET_GAMECLIENT,
            OFFSET_GAMEUI,
            OFFSET_MENU_MGR,
            OFFSET_MAIN_STATE,
            OFFSET_UI_STATE,
            OFFSET_PLAYER,
            OFFSET_HOVER_ENTITY,
            OFFSET_HOVER_FLAG,
        )
        reader = TorchlightMemoryReader()
        reader.pid = 9999
        reader._handle = 1234
        reader._ensure_handle = MagicMock(return_value=True)

        p_game = 0x1000
        p_client = 0x2000
        p_ui = 0x3000
        p_menu_mgr = 0x4000
        p_player = 0x5000

        hover_entity = 0x054E24B8
        current_hover_flag = 2  # NPC
        current_hover_ptr = hover_entity

        def fake_read(addr):
            if addr == ADDR_CGAME_GLOBAL:
                return p_game
            if addr == p_game + OFFSET_GAMECLIENT:
                return p_client
            if addr == p_client + OFFSET_GAMEUI:
                return p_ui
            if addr == p_client + OFFSET_PLAYER:
                return p_player
            if addr == p_ui + OFFSET_MENU_MGR:
                return p_menu_mgr
            if addr == p_menu_mgr + OFFSET_MAIN_STATE:
                return 6
            if addr == p_ui + OFFSET_UI_STATE:
                return 6
            if addr == p_client + OFFSET_HOVER_ENTITY:
                return current_hover_ptr
            if addr == p_client + OFFSET_HOVER_FLAG:
                return current_hover_flag
            return 0

        reader.read_u32 = MagicMock(side_effect=fake_read)
        reader.read_u8 = MagicMock(return_value=0)

        # 1. Hover em NPC (flag 2, ptr válido)
        current_hover_ptr = hover_entity
        current_hover_flag = 2
        st = reader.update()
        self.assertTrue(st.is_hover_interactive)
        self.assertEqual(st.hover_flag, 2)

        # 2. Hover em Baú (flag 1, ptr válido)
        current_hover_ptr = hover_entity
        current_hover_flag = 1
        st = reader.update()
        self.assertTrue(st.is_hover_interactive)
        self.assertEqual(st.hover_flag, 1)

        # 3. Chão vazio (flag 0, ptr 0)
        current_hover_ptr = 0
        current_hover_flag = 0
        st = reader.update()
        self.assertFalse(st.is_hover_interactive)
        self.assertEqual(st.hover_flag, 0)

    def test_read_shortcut_grid_info_with_visible_cells(self):
        reader = TorchlightMemoryReader()
        reader._handle = 12345
        reader._ensure_handle = MagicMock(return_value=True)

        # Base window
        base_ptr = 0x1000
        reader._cached_gui_3501_base_ptr = base_ptr

        # Mock memory values: base visible, h=150.0, w=350.0
        def fake_read_u8(addr):
            if addr == base_ptr + 0x1A0:
                return 1  # base is visible
            # Células visíveis:
            # Row 1: cols 1..7 (ptr 0x2101..0x2107)
            # Row 2: cols 1..2 (ptr 0x2201..0x2202)
            # Row 3: cols 1..4 (ptr 0x2301..0x2304)
            if addr in (
                0x2101 + 0x1A0, 0x2102 + 0x1A0, 0x2103 + 0x1A0, 0x2104 + 0x1A0,
                0x2105 + 0x1A0, 0x2106 + 0x1A0, 0x2107 + 0x1A0,
                0x2201 + 0x1A0, 0x2202 + 0x1A0,
                0x2301 + 0x1A0, 0x2302 + 0x1A0, 0x2303 + 0x1A0, 0x2304 + 0x1A0,
            ):
                return 1
            return 0

        def fake_read_f32(addr):
            if addr == base_ptr + 0x148:
                return 350.0  # width
            if addr == base_ptr + 0x14C:
                return 150.0  # height
            return 0.0

        reader.read_u8 = MagicMock(side_effect=fake_read_u8)
        reader.read_f32 = MagicMock(side_effect=fake_read_f32)

        # Células mapeadas como (col, row)
        reader._cached_gui_3501_icons = {
            (1, 1): 0x2101, (2, 1): 0x2102, (3, 1): 0x2103, (4, 1): 0x2104,
            (5, 1): 0x2105, (6, 1): 0x2106, (7, 1): 0x2107,
            (1, 2): 0x2201, (2, 2): 0x2202,
            (1, 3): 0x2301, (2, 3): 0x2302, (3, 3): 0x2303, (4, 3): 0x2304,
            (5, 3): 0x2305,  # invisível
        }

        info = reader.read_shortcut_grid_info()
        self.assertIsNotNone(info)
        cols, rows, counts = info
        self.assertEqual(cols, 7)
        self.assertEqual(rows, 3)
        self.assertEqual(counts, (7, 2, 4))
        self.assertEqual(reader.read_shortcut_grid_dims(), (7, 3))

    def test_cutscene_memory_detection(self):
        """Valida a detecção de Cutscenes in-game e Telas de História em ambas as versões (Steam e GOG)."""
        from torchbridge.memory import (
            OFFSET_GAMECLIENT,
            OFFSET_PLAYER,
            OFFSET_GAMEUI,
            OFFSET_MENU_MGR,
            OFFSET_MAIN_STATE,
            OFFSET_UI_STATE,
            RVA_CGAME_STEAM,
            RVA_CGAME_GOG,
        )

        for version, rva_cgame in (("Steam", RVA_CGAME_STEAM), ("GOG", RVA_CGAME_GOG)):
            with self.subTest(version=version):
                reader = TorchlightMemoryReader()
                reader.pid = 9999
                reader._handle = 12345
                reader._exe_path = "Torchlight.exe"
                reader._module_base = 0x400000
                reader._ensure_handle = MagicMock(return_value=True)

                p_cgame_addr = reader._module_base + rva_cgame
                p_game = 0x2000
                p_client = 0x3000
                p_ui = 0x4000
                p_player = 0x5000
                p_menu_mgr = 0x6000
                p_cine = 0x7000
                p_skip = 0x8000

                def fake_read_u32(addr):
                    if addr == p_cgame_addr:
                        return p_game
                    if addr == p_game + OFFSET_GAMECLIENT:
                        return p_client
                    if addr == p_client + OFFSET_GAMEUI:
                        return p_ui
                    if addr == p_client + OFFSET_PLAYER:
                        return p_player
                    if addr == p_ui + OFFSET_MENU_MGR:
                        return p_menu_mgr
                    if addr == p_menu_mgr + OFFSET_MAIN_STATE:
                        return 6
                    if addr == p_ui + OFFSET_UI_STATE:
                        return 6
                    if addr == p_ui + 0x0300:
                        return p_cine
                    if addr == p_cine + 0x70:
                        return p_skip
                    return 0

                reader.read_u32 = MagicMock(side_effect=fake_read_u32)

                # 1. Gameplay normal: cine_open=0, cine_flag=1 (padrão quando nenhuma cena está ativa)
                reader.read_u8 = MagicMock(side_effect=lambda a: 1 if a == p_cine + 0x19 else 0)
                st = reader.update()
                self.assertEqual(reader.game_version, version)
                self.assertFalse(st.is_cutscene)
                self.assertEqual(st.state_desc, "Em Jogo")
                self.assertEqual(st.recommended_mode, "direct")
                self.assertNotIn("Cutscene", st.open_menus)

                # 2. Cutscene automática com barras pretas (letterbox): cine_open=0, cine_flag=0, skip invisível
                reader.read_u8 = MagicMock(return_value=0)
                st = reader.update()
                self.assertTrue(st.is_cutscene)
                self.assertEqual(st.state_desc, "Cutscene")
                self.assertIn("Cutscene", st.open_menus)
                self.assertEqual(st.recommended_mode, "blocked")

                # 3. Tela de História (vignette): cine_open=1, cine_flag=1, botão Continue/Skip visível (+0x1A0 = 1)
                def read_story(addr):
                    if addr in (p_cine + 0x18, p_cine + 0x19, p_skip + 0x1A0):
                        return 1
                    return 0

                reader.read_u8 = MagicMock(side_effect=read_story)
                st = reader.update()
                self.assertTrue(st.is_cutscene)
                self.assertEqual(st.state_desc, "Tela de História")
                self.assertIn("Tela de História", st.open_menus)
                self.assertEqual(st.dialog_type, "historia")
                self.assertEqual(st.dialog_buttons, ["continue"])
                self.assertEqual(st.recommended_mode, "cursor")


if __name__ == "__main__":
    unittest.main()


