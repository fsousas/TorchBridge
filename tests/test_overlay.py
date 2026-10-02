"""Testes unitários para o módulo de overlay e modo de calibração contextual."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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


if __name__ == "__main__":
    unittest.main()


