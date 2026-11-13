"""Testes unitários para o módulo de overlay e modo de calibração contextual."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.models import OverlaySnapshot, Rect, SharedOverlayState
from torchbridge.overlay import GameOverlay


class OverlayCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_overlay(self, directory: str) -> tuple[GameOverlay, SharedOverlayState]:
        import json
        config_path = Path(directory) / "perfil.json"
        config_path.write_text(json.dumps({"overlay": {"show_calibration": True}}), encoding="utf-8")
        config = ConfigManager(config_path)
        shared = SharedOverlayState()
        overlay = GameOverlay(shared, config)
        return overlay, shared

    def test_draw_calibration_in_game(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                # 1. Sem painéis abertos (tela limpa de menus)
                overlay._draw_calibration(painter, snap, 1.0)

                # 2. Painel esquerdo aberto (ex: Atributos 'C') -> esconde HUD pet, mostra painel esquerdo
                snap_left = OverlaySnapshot(
                    game_rect=rect,
                    memory_is_in_game=True,
                    memory_state_desc="Em Jogo",
                    active_panels=["C", ""],
                )
                overlay._draw_calibration(painter, snap_left, 1.0)

                # 3. Painel direito aberto (ex: Inventário 'I') -> mostra HUD pet e painel direito
                snap_right = OverlaySnapshot(
                    game_rect=rect,
                    memory_is_in_game=True,
                    memory_state_desc="Em Jogo",
                    active_panels=["", "I"],
                )
                overlay._draw_calibration(painter, snap_right, 1.0)

                # 4. Ambos painéis abertos -> mostra ambos + zona central
                snap_both = OverlaySnapshot(
                    game_rect=rect,
                    memory_is_in_game=True,
                    memory_state_desc="Em Jogo",
                    active_panels=["C", "I"],
                )
                overlay._draw_calibration(painter, snap_both, 1.0)
            finally:
                painter.end()

    def test_draw_calibration_title_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Tela Inicial",
                title_menu_focus="continue",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                overlay._draw_calibration(painter, snap, 1.0)
            finally:
                painter.end()

    def test_draw_calibration_char_create_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Criar Personagem",
                char_create_focus="destroyer",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                # Com nome vazio (char_name_len=0): botão OK desenhado tracejado
                overlay._draw_calibration(painter, snap, 1.0)

                # Com nome preenchido e foco em OK
                snap_with_name = OverlaySnapshot(
                    game_rect=rect,
                    memory_is_in_game=False,
                    memory_state_desc="Criar Personagem",
                    char_create_focus="ok",
                    char_name_len=8,
                )
                overlay._draw_calibration(painter, snap_with_name, 1.0)
            finally:
                painter.end()

    def test_draw_calibration_difficulty_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Selecionar Dificuldade",
                difficulty_focus="hardcore",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                overlay._draw_calibration(painter, snap, 1.0)
            finally:
                painter.end()

    def test_draw_calibration_crafting_menus(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            for menu_name in ("Transmutador", "Sockets", "Encantador"):
                snap = OverlaySnapshot(
                    game_rect=rect,
                    memory_is_in_game=True,
                    memory_state_desc="Em Jogo",
                    memory_open_menus=[menu_name, "Inventário"],
                    active_panels=["T", "I"],
                )
                pix = QPixmap(1024, 768)
                painter = QPainter(pix)
                try:
                    overlay._draw_calibration(painter, snap, 1.0)
                finally:
                    painter.end()

    def test_draw_calibration_pause_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                memory_open_menus=["Pause"],
                pause_menu_focus="return_to_game",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                overlay._draw_calibration(painter, snap, 1.0)
            finally:
                painter.end()

    def test_draw_calibration_settings_screen_hides_hud_and_pet(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Configurações (Settings)",
                memory_open_menus=["Configurações"],
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawPixmap = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # Não deve desenhar a HUD pixmap nem Pet Actions pixmap
                painter.drawPixmap.assert_not_called()
            finally:
                painter.end()

    def test_draw_calibration_loading_screen_hides_hud_and_pet(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_is_loading=True,
                memory_state_desc="Carregando...",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawPixmap = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                painter.drawPixmap.assert_not_called()
            finally:
                painter.end()

    def test_draw_calibration_dialog_screen_hides_hud_and_pet(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                memory_open_menus=["Missão (Em Andamento)"],
                dialog_type="missao_andamento",
                dialog_buttons=["ok"],
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawPixmap = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # Não deve desenhar a HUD pixmap nem Pet Actions pixmap
                painter.drawPixmap.assert_not_called()
            finally:
                painter.end()

    def test_draw_calibration_cutscene_hides_gameplay_and_shows_badge(self):
        """Valida que durante Cutscene a calibração de gameplay fica oculta e o status mostra Cutscene."""
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                enabled=True,
                game_found=True,
                game_active=True,
                game_rect=rect,
                memory_is_in_game=True,
                memory_is_cutscene=True,
                memory_state_desc="Cutscene",
                memory_open_menus=["Cutscene"],
                mode="blocked",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawPixmap = MagicMock()
            painter.drawText = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # Não deve desenhar a HUD pixmap nem Pet Actions pixmap
                painter.drawPixmap.assert_not_called()
                # O badge de status de memória deve ser desenhado exibindo Cutscene
                drawn_texts = [call.args[-1] for call in painter.drawText.call_args_list if call.args]
                self.assertIn("ESTADO: CUTSCENE", drawn_texts)
                self.assertIn("MENUS : Cutscene", drawn_texts)

                # World calibration também não deve desenhar linhas nem círculos
                painter.drawRect = MagicMock()
                painter.drawEllipse = MagicMock()
                overlay._draw_world_calibration(painter, snap, 1.0)
                painter.drawRect.assert_not_called()
                painter.drawEllipse.assert_not_called()
            finally:
                painter.end()


    def test_draw_calibration_character_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                char_menu_open=True,
                char_menu_focus="strength_pink",
                attr_points_remaining=5,
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawRoundedRect = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # 4 atributos * (1 nó verde + 1 nó laranja + 1 nó rosa com pontos) = 12 chamadas
                self.assertGreaterEqual(painter.drawRoundedRect.call_count, 12)
            finally:
                painter.end()

    def test_draw_calibration_skills_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                skill_menu_open=True,
                skill_tab=1,
                char_class="alchemist",
                skill_points_remaining=1,
                skill_upgradeable={(0, 1): True},
                skill_focus="(0, 1, pink)",
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            painter.drawRoundedRect = MagicMock()
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # 3 abas + slots preenchidos da grid + 1 nó rosa
                self.assertGreaterEqual(painter.drawRoundedRect.call_count, 10)
            finally:
                painter.end()


    def test_draw_calibration_pet_skill_bridge_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                pet_inventory_open=True,
                skill_menu_open=True,
                memory_open_menus=["Pet", "Habilidades"],
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            colors = []
            orig_setBrush = painter.setBrush

            def capture_brush(b):
                if isinstance(b, QColor):
                    colors.append((b.red(), b.green(), b.blue()))
                elif hasattr(b, "color") and callable(b.color):
                    c = b.color()
                    colors.append((c.red(), c.green(), c.blue()))
                orig_setBrush(b)

            painter.setBrush = capture_brush
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # O tom laranja de ponte é (0xFD=253, 0x61=97, 0x00=0)
                orange_count = sum(1 for r, g, b in colors if r == 253 and g == 97 and b == 0)
                # 3 slots do grid (coluna 7: 3 linhas) + 1 slot superior (pet_spell_2) = 4 slots no pet + slots na skill tree
                self.assertGreaterEqual(orange_count, 4)
            finally:
                painter.end()

    def test_draw_calibration_char_inventory_bridge_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(100, 100, 1024, 768)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                inventory_open=True,
                char_menu_open=True,
                memory_open_menus=["Atributos", "Inventário"],
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            colors = []
            orig_setBrush = painter.setBrush

            def capture_brush(b):
                if isinstance(b, QColor):
                    colors.append((b.red(), b.green(), b.blue()))
                elif hasattr(b, "color") and callable(b.color):
                    c = b.color()
                    colors.append((c.red(), c.green(), c.blue()))
                orig_setBrush(b)

            painter.setBrush = capture_brush
            try:
                overlay._draw_calibration(painter, snap, 1.0)
                # O tom laranja de ponte é (0xFD=253, 0x61=97, 0x00=0)
                orange_count = sum(1 for r, g, b in colors if r == 253 and g == 97 and b == 0)
                # No inventário: coluna 1 (3 linhas) + 5 slots superiores (spell_1, main_hand, belt, gloves, helmet) = 8
                # No menu de atributos: nós de ponte (xp, fame, mp, res_fire, res_ice, 4 attr_bridge) = 9
                # Total esperado >= 17 slots laranjas
                self.assertGreaterEqual(orange_count, 17)
            finally:
                painter.end()




class OverlayRadialExtraHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_overlay(self, directory: str, layout: str = "auto") -> tuple[GameOverlay, SharedOverlayState]:
        import json
        config_path = Path(directory) / "perfil.json"
        config_path.write_text(
            json.dumps({
                "overlay": {"show_calibration": False, "controller_layout": layout},
                "bindings": {"radial_slots": ["C", "I", "S", "Q", "J", "P", "Shortcuts", "A"]},
            }),
            encoding="utf-8",
        )
        config = ConfigManager(config_path)
        shared = SharedOverlayState()
        overlay = GameOverlay(shared, config)
        return overlay, shared

    def test_radial_extra_hud_assets_exist_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            instructions = [
                "menu-radial-instructions-xbox.png",
                "menu-radial-instructions-ps.png",
                "menu-radial-instructions-nintendo.png",
            ]
            for filename in instructions:
                pix = overlay._radial_instruction_pixmap(filename)
                self.assertIsNotNone(pix, f"Failed to load {filename}")
                self.assertFalse(pix.isNull(), f"Pixmap is null for {filename}")
                self.assertIn(filename, overlay._radial_instruction_cache)

            info_keys = [
                "A", "C", "I", "J", "P", "P-agressive",
                "P-defensive", "P-passive", "P-sell", "Q", "S", "Shortcuts",
            ]
            for key in info_keys:
                pix = overlay._radial_info_pixmap(key)
                self.assertIsNotNone(pix, f"Failed to load top info card for {key}")
                self.assertFalse(pix.isNull(), f"Pixmap is null for {key}")
                self.assertIn(key, overlay._radial_info_cache)

    def test_get_radial_top_info_key(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # 1. Radial fechado
            snap = OverlaySnapshot(game_rect=rect, radial_active=False, radial_selection=1)
            self.assertIsNone(overlay._get_radial_top_info_key(snap))

            # 2. Radial aberto sem seleção
            snap = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=None)
            self.assertIsNone(overlay._get_radial_top_info_key(snap))

            # 3. Seleção slot 1 ('C')
            snap = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=1)
            self.assertEqual(overlay._get_radial_top_info_key(snap), "C")

            # 4. Seleção slot 2 ('I')
            snap = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=2)
            self.assertEqual(overlay._get_radial_top_info_key(snap), "I")

            # 5. Seleção slot 7 ('Shortcuts')
            snap = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=7)
            self.assertEqual(overlay._get_radial_top_info_key(snap), "Shortcuts")

            # 6. Seleção slot 6 ('P') com submenu fechado
            snap = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=6, pet_submenu_open=False)
            self.assertEqual(overlay._get_radial_top_info_key(snap), "P")

            # 7. Seleção slot 6 ('P') com submenu aberto (1 a 4)
            sub_expected = {
                1: "P-agressive",
                2: "P-defensive",
                3: "P-passive",
                4: "P-sell",
            }
            for sel, expected in sub_expected.items():
                snap = OverlaySnapshot(
                    game_rect=rect,
                    radial_active=True,
                    radial_selection=6,
                    pet_submenu_open=True,
                    pet_submenu_selection=sel,
                )
                self.assertEqual(overlay._get_radial_top_info_key(snap), expected)

    def test_radial_top_info_animation_lifecycle(self):
        import time
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Estado inicial
            snap_none = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=None)
            overlay._tick_radial_top_info_anim(snap_none)
            self.assertIsNone(overlay._radial_top_info_current)
            self.assertEqual(overlay._radial_top_info_progress, 0.0)

            # 1. Entrada de 'C': fade + scale (crossfade=False)
            snap_c = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=1)
            overlay._tick_radial_top_info_anim(snap_c)
            self.assertEqual(overlay._radial_top_info_target, "C")
            self.assertEqual(overlay._radial_top_info_current, "C")
            self.assertFalse(overlay._radial_top_info_crossfade)

            # Avança o tempo para completar a entrada
            overlay._radial_top_info_last_time = time.monotonic() - 1.0
            overlay._tick_radial_top_info_anim(snap_c)
            self.assertEqual(overlay._radial_top_info_progress, 1.0)

            # 2. Troca de 'C' para 'I': crossfade puro (sem scale)
            snap_i = OverlaySnapshot(game_rect=rect, radial_active=True, radial_selection=2)
            overlay._tick_radial_top_info_anim(snap_i)
            self.assertEqual(overlay._radial_top_info_target, "I")
            self.assertEqual(overlay._radial_top_info_current, "I")
            self.assertEqual(overlay._radial_top_info_prev, "C")
            self.assertTrue(overlay._radial_top_info_crossfade)

            # Avança o tempo para completar o crossfade
            overlay._radial_top_info_last_time = time.monotonic() - 1.0
            overlay._tick_radial_top_info_anim(snap_i)
            self.assertFalse(overlay._radial_top_info_crossfade)
            self.assertIsNone(overlay._radial_top_info_prev)
            self.assertEqual(overlay._radial_top_info_progress, 1.0)

            # 3. Cancelamento pelo botão leste (radial_selection vira None): fade + scale de saída
            overlay._tick_radial_top_info_anim(snap_none)
            self.assertIsNone(overlay._radial_top_info_target)
            self.assertFalse(overlay._radial_top_info_crossfade)

            # Avança o tempo para completar a saída
            overlay._radial_top_info_last_time = time.monotonic() - 1.0
            overlay._tick_radial_top_info_anim(snap_none)
            self.assertEqual(overlay._radial_top_info_progress, 0.0)
            self.assertIsNone(overlay._radial_top_info_current)

    def test_draw_radial_renders_instructions_and_info(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory, layout="playstation")
            rect = Rect(0, 0, 1920, 1080)
            overlay._radial_progress = 1.0
            overlay._radial_top_info_progress = 1.0
            overlay._radial_top_info_current = "I"
            overlay._radial_top_info_target = "I"

            snap = OverlaySnapshot(
                game_rect=rect,
                radial_active=True,
                radial_selection=2,
                controller_type="playstation",
            )

            pix = QPixmap(1920, 1080)
            painter = QPainter(pix)
            try:
                overlay._draw_radial(painter, snap, 1.0)
            finally:
                painter.end()

            # Ambos devem ter sido consultados no cache
            self.assertIn("menu-radial-instructions-ps.png", overlay._radial_instruction_cache)
            self.assertIn("I", overlay._radial_info_cache)

    def test_pet_submenu_icons_exist_and_render(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Valida carregamento dos 4 ícones pet-1 a pet-4
            for icon_name in overlay.PET_SUBMENU_ICONS:
                pixmap = overlay._pet_icon(icon_name)
                self.assertIsNotNone(pixmap, f"Ícone {icon_name} não deve ser None")
                self.assertFalse(pixmap.isNull(), f"Ícone {icon_name} não deve ser nulo")

            # Renderiza o submenu do pet e valida que desenha sem erros
            pix = QPixmap(1920, 1080)
            painter = QPainter(pix)
            try:
                overlay._pet_submenu_progress = 1.0
                overlay._draw_pet_submenu(painter, QPointF(960, 540), 1.0, 1, 1.0)
            finally:
                painter.end()

            # Valida transição de escala da opção marcada (1.0 -> 1.13)
            snap_pet4 = OverlaySnapshot(
                game_rect=rect,
                radial_active=True,
                radial_selection=6,
                pet_submenu_open=True,
                pet_submenu_selection=4,
            )
            # Simula tick de tempo
            import time
            overlay._pet_submenu_last_time = time.monotonic() - 0.20
            overlay._tick_pet_submenu_anim(snap_pet4)
            # Item 4 (índice 3) atinge escala 1.13, enquanto 0, 1 e 2 permanecem 1.0
            self.assertAlmostEqual(overlay._pet_item_scales[3], 1.13, places=2)
            self.assertAlmostEqual(overlay._pet_item_scales[0], 1.0, places=2)
            self.assertAlmostEqual(overlay._pet_item_scales[1], 1.0, places=2)
            self.assertAlmostEqual(overlay._pet_item_scales[2], 1.0, places=2)

            # Muda seleção para item 2
            snap_pet2 = OverlaySnapshot(
                game_rect=rect,
                radial_active=True,
                radial_selection=6,
                pet_submenu_open=True,
                pet_submenu_selection=2,
            )
            overlay._pet_submenu_last_time = time.monotonic() - 0.20
            overlay._tick_pet_submenu_anim(snap_pet2)
            self.assertAlmostEqual(overlay._pet_item_scales[1], 1.13, places=2)
            self.assertAlmostEqual(overlay._pet_item_scales[3], 1.0, places=2)

    def test_draw_aim_renders_footstep(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # 1. Sem mira ativa: não desenha nada
            snap_no_aim = OverlaySnapshot(game_rect=rect, aim_x=None, aim_y=None)
            pix = QPixmap(1920, 1080)
            painter = QPainter(pix)
            try:
                overlay._draw_aim(painter, snap_no_aim, 1.0)
            finally:
                painter.end()

            # 2. Com mira ativa: desenha a pegada
            snap_aim = OverlaySnapshot(game_rect=rect, aim_x=500, aim_y=500)
            painter = QPainter(pix)
            try:
                overlay._draw_aim(painter, snap_aim, 1.0)
            finally:
                painter.end()

            # Valida carregamento do pixmap de pegada
            self.assertIsNotNone(overlay._footstep_pixmap())
            self.assertFalse(overlay._footstep_pixmap().isNull())
            self.assertEqual(overlay._footstep_pixmap().width(), 33)
            self.assertEqual(overlay._footstep_pixmap().height(), 29)

    def test_debug_menu_overlay_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # 1. Quando fechado, não desenha nada
            snap_closed = OverlaySnapshot(game_rect=rect, debug_menu_open=False)
            pix = QPixmap(1920, 1080)
            painter = QPainter(pix)
            try:
                overlay._draw_debug_menu(painter, snap_closed, 1.0)
            finally:
                painter.end()
            self.assertEqual(len(overlay._debug_menu_cache), 0)

            # 2. Quando aberto (layout Xbox, foco no item 0, scroll 0)
            snap_xbox = OverlaySnapshot(
                game_rect=rect,
                debug_menu_open=True,
                debug_menu_focus=0,
                debug_menu_scroll=0,
                controller_type="xbox",
                debug_bottom_hud=True,
                debug_aim_marker=True,
            )
            painter = QPainter(pix)
            try:
                overlay._draw_debug_menu(painter, snap_xbox, 1.0)
            finally:
                painter.end()

            # Valida que os assets principais foram carregados no cache
            self.assertIn("quadro.png", overlay._debug_menu_cache)
            self.assertIn("scroll-bar.png", overlay._debug_menu_cache)
            self.assertIn("scroll-indicator.png", overlay._debug_menu_cache)
            self.assertIn("hover.png", overlay._debug_menu_cache)
            self.assertIn("check-on.png", overlay._debug_menu_cache)
            self.assertIn("check-off.png", overlay._debug_menu_cache)
            self.assertIn("btn-off.png", overlay._debug_menu_cache)
            self.assertIn("dpad-up-xbox.png", overlay._debug_menu_cache)
            self.assertIn("interact-xbox.png", overlay._debug_menu_cache)

            # 3. Quando foco está no botão fechar (item 12) e scroll em 2 (layout PlayStation)
            snap_ps = OverlaySnapshot(
                game_rect=rect,
                debug_menu_open=True,
                debug_menu_focus=12,
                debug_menu_scroll=2,
                controller_type="playstation",
            )
            painter = QPainter(pix)
            try:
                overlay._draw_debug_menu(painter, snap_ps, 1.0)
            finally:
                painter.end()

            self.assertIn("btn-on.png", overlay._debug_menu_cache)
            self.assertIn("dpad-up-playstation.png", overlay._debug_menu_cache)
            self.assertIn("interact-playstation.png", overlay._debug_menu_cache)

            # 4. Layout Nintendo
            snap_nin = OverlaySnapshot(
                game_rect=rect,
                debug_menu_open=True,
                debug_menu_focus=5,
                debug_menu_scroll=1,
                controller_type="nintendo",
            )
            painter = QPainter(pix)
            try:
                overlay._draw_debug_menu(painter, snap_nin, 1.0)
            finally:
                painter.end()

            self.assertIn("dpad-up-nintendo.png", overlay._debug_menu_cache)
            self.assertIn("interact-nintendo.png", overlay._debug_menu_cache)



if __name__ == "__main__":
    unittest.main()


