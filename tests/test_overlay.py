"""Testes unitários para o módulo de overlay e modo de calibração contextual."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
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


if __name__ == "__main__":
    unittest.main()
