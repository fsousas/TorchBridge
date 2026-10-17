"""Testes unitários para o teclado virtual na tela de criação de personagem."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    KEYBOARD_GRID_COLS,
    KEYBOARD_GRID_ROWS,
    KEYBOARD_LAYOUT,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    virtual_keyboard_asset_path,
    virtual_keyboard_bg_asset_path,
    virtual_keyboard_grid_to_key,
    virtual_keyboard_highlight_filename,
    virtual_keyboard_info_label_filename,
    virtual_keyboard_key_filename,
    virtual_keyboard_key_rect,
    virtual_keyboard_target_rect,
)
from torchbridge.overlay import GameOverlay


class VirtualKeyboardModelTests(unittest.TestCase):
    def test_virtual_keyboard_bg_asset_exists(self):
        path = virtual_keyboard_bg_asset_path()
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "background.png")

    def test_target_rect_character_name_centered_and_discount(self):
        rect = Rect(0, 0, 1920, 1080)
        x, y, w, h = virtual_keyboard_target_rect(rect, "character_name")
        self.assertEqual(w, 568)
        self.assertEqual(h, 290)
        self.assertEqual(x, (1920 - 568) // 2)
        self.assertEqual(y + h, int(round(1080 * 0.90)))

    def test_target_rect_pet_name_fixed_margin_and_discount(self):
        rect = Rect(0, 0, 1920, 1080)
        x, y, w, h = virtual_keyboard_target_rect(rect, "pet_name")
        self.assertEqual(w, 568)
        self.assertEqual(h, 290)
        self.assertEqual(x, 1920 - 259 - 568)
        self.assertEqual(y + h, int(round(1080 * 0.80)))

    def test_target_rect_invalid_rect(self):
        invalid_rect = Rect(0, 0, 0, 0)
        self.assertEqual(virtual_keyboard_target_rect(invalid_rect), (0, 0, 0, 0))

    def test_keyboard_layout_and_assets_exist(self):
        self.assertEqual(len(KEYBOARD_LAYOUT), 52)
        for key_id, r, c, span, k_type in KEYBOARD_LAYOUT:
            min_file = virtual_keyboard_key_filename(key_id, "default")
            path_min = virtual_keyboard_asset_path(min_file)
            self.assertIsNotNone(path_min, f"Arquivo não encontrado: {min_file}")
            assert path_min is not None
            self.assertTrue(path_min.is_file())

            mai_file = virtual_keyboard_key_filename(key_id, "all_letters")
            path_mai = virtual_keyboard_asset_path(mai_file)
            self.assertIsNotNone(path_mai, f"Arquivo não encontrado: {mai_file}")
            assert path_mai is not None
            self.assertTrue(path_mai.is_file())

    def test_highlight_filenames(self):
        self.assertEqual(virtual_keyboard_highlight_filename("simple"), "highlight-tecla-simples.png")
        self.assertEqual(virtual_keyboard_highlight_filename("caps"), "highlight-tecla-dupla.png")
        self.assertEqual(virtual_keyboard_highlight_filename("backspace"), "highlight-tecla-dupla.png")
        self.assertEqual(virtual_keyboard_highlight_filename("space"), "highlight-tecla-grande.png")
        self.assertEqual(virtual_keyboard_highlight_filename("ok"), "highlight-tecla-tripla.png")

    def test_info_labels_exist(self):
        for ctrl in ("xbox", "playstation", "nintendo"):
            fn = virtual_keyboard_info_label_filename(ctrl)
            path = virtual_keyboard_asset_path(fn)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.is_file())

    def test_grid_to_key_mapping(self):
        self.assertEqual(virtual_keyboard_grid_to_key(3, 1), ("3x1", "simple"))
        self.assertEqual(virtual_keyboard_grid_to_key(4, 1), ("caps", "caps"))
        self.assertEqual(virtual_keyboard_grid_to_key(4, 2), ("caps", "caps"))
        self.assertEqual(virtual_keyboard_grid_to_key(4, 5), ("4x5", "simple"))
        self.assertEqual(virtual_keyboard_grid_to_key(4, 12), ("backspace", "backspace"))
        self.assertEqual(virtual_keyboard_grid_to_key(4, 13), ("backspace", "backspace"))
        self.assertEqual(virtual_keyboard_grid_to_key(5, 5), ("space", "space"))
        self.assertEqual(virtual_keyboard_grid_to_key(5, 11), ("ok", "ok"))
        self.assertEqual(virtual_keyboard_grid_to_key(5, 13), ("ok", "ok"))


class VirtualKeyboardEngineTests(unittest.TestCase):
    def _make_engine(self, directory: str) -> tuple[BridgeEngine, SharedOverlayState, MagicMock]:
        config_path = Path(directory) / "perfil.json"
        config_path.write_text(json.dumps({"overlay": {"enabled": True}}), encoding="utf-8")
        config = ConfigManager(config_path)
        shared = SharedOverlayState()
        engine = BridgeEngine(config, shared)
        injector = MagicMock()
        injector.cursor_position.return_value = (960, 540)
        engine.injector = injector
        return engine, shared, injector

    def test_open_and_close_virtual_keyboard_with_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect = Rect(0, 0, 1920, 1080)
            hub = MagicMock()
            engine._memory_state = GameMemoryState(is_connected=True, state_id=1, char_name_len=0)

            # Inicializa char_create
            engine._handle_char_create_navigation(ControllerState(), rect, hub)
            self.assertFalse(engine._virtual_keyboard_open)

            # Foca em character_name
            engine._char_create_focus = "character_name"

            # Pressiona A sobre character_name -> Abre teclado virtual!
            engine._previous = ControllerState()
            engine._handle_char_create_navigation(ControllerState(buttons={"a"}), rect, hub)
            self.assertTrue(engine._virtual_keyboard_open)
            self.assertEqual(engine._virtual_keyboard_target, "character_name")
            self.assertEqual(engine._virtual_keyboard_focus, (3, 1))

            snapshot = shared.get()
            self.assertTrue(snapshot.virtual_keyboard_open)
            self.assertEqual(snapshot.virtual_keyboard_target, "character_name")
            self.assertEqual(snapshot.virtual_keyboard_focus, (3, 1))

            # Pressiona B -> Atua como Backspace quando o teclado está aberto
            engine._previous = ControllerState()
            engine._handle_char_create_navigation(ControllerState(buttons={"b"}), rect, hub)
            injector.key.assert_any_call("BACKSPACE", True)

            # Pressiona Start -> Fecha teclado virtual e retorna ao campo
            engine._previous = ControllerState()
            engine._handle_char_create_navigation(ControllerState(buttons={"start"}), rect, hub)
            self.assertFalse(engine._virtual_keyboard_open)
            self.assertEqual(engine._virtual_keyboard_target, "")
            self.assertFalse(shared.get().virtual_keyboard_open)

    def test_dpad_navigation_inside_keyboard(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect = Rect(0, 0, 1920, 1080)
            hub = MagicMock()
            engine._memory_state = GameMemoryState(is_connected=True, state_id=1, char_name_len=0)

            # Abre o teclado
            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_target = "character_name"
            engine._virtual_keyboard_focus = (3, 1)

            # Move D-pad direita -> (3, 2)
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"dpad_right"}), rect, hub)
            self.assertEqual(engine._virtual_keyboard_focus, (3, 2))
            self.assertEqual(shared.get().virtual_keyboard_focus, (3, 2))

            # Move D-pad baixo -> (4, 2) que é a tecla Caps
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"dpad_down"}), rect, hub)
            self.assertEqual(engine._virtual_keyboard_focus, (4, 2))

            # Move D-pad direita saindo do Caps -> deve pular para col 3
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"dpad_right"}), rect, hub)
            self.assertEqual(engine._virtual_keyboard_focus, (4, 3))

            # Move D-pad baixo para a linha 5 -> espaço (col 3)
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"dpad_down"}), rect, hub)
            self.assertEqual(engine._virtual_keyboard_focus, (5, 3))

            # Move D-pad direita na linha do espaço -> pula para OK (col 11)
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"dpad_right"}), rect, hub)
            self.assertEqual(engine._virtual_keyboard_focus, (5, 11))

    def test_caps_lock_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect = Rect(0, 0, 1920, 1080)
            hub = MagicMock()

            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_caps_state = "default"

            # 1. Gatilho LT alterna de default para next_letter
            engine._previous = ControllerState()
            engine._handle_virtual_keyboard_navigation(ControllerState(lt=1.0), rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "next_letter")
            self.assertEqual(shared.get().virtual_keyboard_caps_state, "next_letter")

            # 2. Gatilho LT alterna de next_letter para all_letters
            engine._previous = ControllerState(lt=0.0)
            engine._handle_virtual_keyboard_navigation(ControllerState(lt=1.0), rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "all_letters")
            self.assertEqual(shared.get().virtual_keyboard_caps_state, "all_letters")

            # 3. Gatilho LT alterna de all_letters para default
            engine._previous = ControllerState(lt=0.0)
            engine._handle_virtual_keyboard_navigation(ControllerState(lt=1.0), rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "default")
            self.assertEqual(shared.get().virtual_keyboard_caps_state, "default")


class VirtualKeyboardOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_overlay(self, directory: str) -> tuple[GameOverlay, SharedOverlayState]:
        config_path = Path(directory) / "perfil.json"
        config_path.write_text(json.dumps({"overlay": {"scale": 1.0}}), encoding="utf-8")
        config = ConfigManager(config_path)
        shared = SharedOverlayState()
        overlay = GameOverlay(shared, config)
        return overlay, shared

    def test_draw_virtual_keyboard_overlay_with_keys_and_highlights(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            rect = Rect(0, 0, 1920, 1080)
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Criar Personagem",
                char_create_focus="character_name",
                virtual_keyboard_open=True,
                virtual_keyboard_target="character_name",
                virtual_keyboard_focus=(3, 1),
                virtual_keyboard_caps_state="default",
                controller_type="xbox",
            )
            pix = QPixmap(1920, 1080)
            painter = QPainter(pix)
            try:
                overlay._draw_virtual_keyboard(painter, snap, 1.0)
            finally:
                painter.end()


if __name__ == "__main__":
    unittest.main()
