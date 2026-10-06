"""Testes unitários para o HUD inferior de controles (Xbox, PlayStation, Nintendo)."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.models import (
    BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION,
    BOTTOM_HUD_HEIGHT,
    BOTTOM_HUD_WIDTH,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    bottom_hud_asset_path,
    bottom_hud_target_rect,
    controller_type_from_name,
)
from torchbridge.overlay import GameOverlay


class BottomHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_overlay(self, directory: str, overlay_config: dict | None = None) -> tuple[GameOverlay, SharedOverlayState]:
        import json
        cfg = {"overlay": overlay_config or {"show_bottom_hud": True}}
        config_path = Path(directory) / "perfil.json"
        config_path.write_text(json.dumps(cfg), encoding="utf-8")
        config = ConfigManager(config_path)
        shared = SharedOverlayState()
        overlay = GameOverlay(shared, config)
        return overlay, shared

    def test_controller_type_detection(self):
        """Valida a detecção automática do tipo de controle pelo nome."""
        # PlayStation
        self.assertEqual(controller_type_from_name("DualSense Wireless Controller"), "playstation")
        self.assertEqual(controller_type_from_name("Wireless Controller"), "playstation") # Sony padrão
        self.assertEqual(controller_type_from_name("PS5 Controller"), "playstation")
        self.assertEqual(controller_type_from_name("PS4 DualShock"), "playstation")
        self.assertEqual(controller_type_from_name("Sony Interactive Entertainment"), "playstation")

        # Nintendo
        self.assertEqual(controller_type_from_name("Nintendo Switch Pro Controller"), "nintendo")
        self.assertEqual(controller_type_from_name("Joy-Con (L/R)"), "nintendo")
        self.assertEqual(controller_type_from_name("Switch Controller"), "nintendo")
        self.assertEqual(controller_type_from_name("Pro Controller"), "nintendo")

        # Xbox / Fallback
        self.assertEqual(controller_type_from_name("Xbox Series X Controller"), "xbox")
        self.assertEqual(controller_type_from_name("Xbox 360 Controller"), "xbox")
        self.assertEqual(controller_type_from_name("Xbox One Controller"), "xbox")
        self.assertEqual(controller_type_from_name("XInput Controller"), "xbox")
        self.assertEqual(controller_type_from_name("Controle Genérico"), "xbox")
        self.assertEqual(controller_type_from_name(""), "xbox")

    def test_bottom_hud_asset_paths_exist(self):
        """Verifica se os arquivos PNG de cada layout existem no disco."""
        xbox_path = bottom_hud_asset_path("xbox")
        self.assertIsNotNone(xbox_path)
        self.assertTrue(xbox_path.is_file(), f"Arquivo não encontrado: {xbox_path}")
        self.assertEqual(xbox_path.name, "hud-xbox.png")

        ps_path = bottom_hud_asset_path("playstation")
        self.assertIsNotNone(ps_path)
        self.assertTrue(ps_path.is_file(), f"Arquivo não encontrado: {ps_path}")
        self.assertEqual(ps_path.name, "hud-playstation.png")

        nintendo_path = bottom_hud_asset_path("nintendo")
        self.assertIsNotNone(nintendo_path)
        self.assertTrue(nintendo_path.is_file(), f"Arquivo não encontrado: {nintendo_path}")
        self.assertEqual(nintendo_path.name, "hud-nitendo.png")

    def test_bottom_hud_target_rect_1080p(self):
        """Valida coordenadas e proporção do HUD inferior em resolução 1080p (1920x1080) com redução de 27% e offset 2%."""
        rect = Rect(0, 0, 1920, 1080)
        left, top, width, height = bottom_hud_target_rect(rect)

        # Na referência 1080p, dimensões reduzidas em 27% (0.73)
        expected_width = BOTTOM_HUD_WIDTH * 0.73
        expected_height = BOTTOM_HUD_HEIGHT * 0.73
        self.assertAlmostEqual(width, expected_width, delta=0.01)
        self.assertAlmostEqual(height, expected_height, delta=0.01)

        # Centralizado horizontalmente: (1920 - expected_width) / 2
        self.assertAlmostEqual(left, (1920 - expected_width) / 2.0, delta=0.01)

        # Alinhado à base com offset de 1.5% da altura (16.2px):
        # top = 1080 - expected_height - 16.2
        self.assertAlmostEqual(top, 1080.0 - expected_height - 1080.0 * 0.015, delta=0.01)

        # Distância entre o rodapé do HUD e o rodapé da janela = exatamente 1.5% da altura
        hud_bottom = top + height
        distance_from_window_bottom = rect.bottom - hud_bottom
        self.assertAlmostEqual(distance_from_window_bottom, 1080 * 0.015, delta=0.01)

    def test_bottom_hud_target_rect_scaling(self):
        """Valida que o HUD escala estritamente pela altura da janela (ex: 1024x768) preservando aspect ratio."""
        rect = Rect(100, 200, 1024, 768)
        left, top, width, height = bottom_hud_target_rect(rect)

        # Proporção deve se manter idêntica à nativa (1347 / 242)
        native_aspect = BOTTOM_HUD_WIDTH / BOTTOM_HUD_HEIGHT
        calculated_aspect = width / height
        self.assertAlmostEqual(calculated_aspect, native_aspect, places=4)

        # Centralizado horizontalmente em relação à janela do jogo
        self.assertAlmostEqual(left, 100 + (1024 - width) / 2.0, delta=0.01)

        # Distância da base deve ser 1.5% da altura da janela (768 * 0.015 = 11.52px)
        distance_from_bottom = rect.bottom - (top + height)
        self.assertAlmostEqual(distance_from_bottom, 768 * 0.015, delta=0.01)

    def test_bottom_hud_visibility_rules(self):
        """Valida todas as regras de exibição e ocultação especificadas."""
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)

            # 1. Deve ser exibido no estado EM JOGO com controle conectado
            snap_in_game = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                controller_name="Xbox Series X Controller",
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
            )
            self.assertTrue(overlay._should_show_bottom_hud(snap_in_game))

            # 2. Oculto se não houver controle conectado
            snap_no_controller = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=False,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_no_controller))

            # 3. Oculto em TITLE MENU (Tela Inicial)
            snap_title = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=False,
                memory_state_desc="Tela Inicial",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_title))

            # 4. Oculto em CHARACTER SELECT (Carregar Personagem)
            snap_char_sel = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=False,
                memory_state_desc="Carregar Personagem",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_char_sel))

            # 5. Oculto em CHARACTER CREATE (Criar Personagem)
            snap_char_create = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=False,
                memory_state_desc="Criar Personagem",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_char_create))

            # 6. Oculto em LOADING SCREEN (testa várias combinações de flags/descrições)
            snap_loading = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=False,
                memory_is_loading=True,
                memory_state_desc="Carregando...",
                mode="blocked",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_loading))

            # Mesmo se memory_is_in_game estivesse True por qualquer motivo
            snap_loading_fallback = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_is_loading=True,
                memory_state_desc="Carregando...",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_loading_fallback))

            # Bloqueado pelo modo "blocked"
            snap_mode_blocked = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                mode="blocked",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_mode_blocked))

            # Bloqueado pela descrição "Carregando..."
            snap_desc_carregando = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_state_desc="Carregando...",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_desc_carregando))

            # 7. Oculto em DIALOG
            snap_dialog = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                dialog_type="missao_aceitar",
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_dialog))

            # 8. Oculto em QUEST
            snap_quest = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                quest_menu_open=True,
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_quest))

            # 9. Visível em PAUSE (ESC em jogo não fecha a barra nativa nem o HUD)
            snap_pause = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                pause_menu_focus="resume",
                memory_open_menus=["Pause"],
            )
            self.assertTrue(overlay._should_show_bottom_hud(snap_pause))

            # 10. Oculto em OPTIONS SCREEN / Configurações
            snap_settings = OverlaySnapshot(
                game_found=True,
                game_active=True,
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                memory_state_desc="Em Jogo",
                memory_open_menus=["Configurações"],
            )
            self.assertFalse(overlay._should_show_bottom_hud(snap_settings))

    def test_bottom_hud_render_all_layouts(self):
        """Valida que o desenho do HUD funciona para cada marca de controle sem exceções."""
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)
            pix = QPixmap(1920, 1080)

            for c_name, c_type in [
                ("Xbox Series X Controller", "xbox"),
                ("DualSense Wireless Controller", "playstation"),
                ("Nintendo Switch Pro Controller", "nintendo"),
            ]:
                snap = OverlaySnapshot(
                    game_found=True,
                    game_active=True,
                    game_rect=rect,
                    controller_connected=True,
                    controller_name=c_name,
                    controller_type=c_type,
                    memory_is_in_game=True,
                    memory_state_desc="Em Jogo",
                )
                painter = QPainter(pix)
                try:
                    overlay._draw_bottom_hud(painter, snap)
                finally:
                    painter.end()


if __name__ == "__main__":
    unittest.main()
