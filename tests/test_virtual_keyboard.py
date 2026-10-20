"""Testes unitários para o teclado virtual na tela de criação de personagem."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
    virtual_keyboard_key_cursor_point,
    virtual_keyboard_character,
    virtual_keyboard_target_rect,
    char_create_pet_panel_rect,
    char_create_text_field_rect,
)
from torchbridge.overlay import GameOverlay


class VirtualKeyboardModelTests(unittest.TestCase):
    def test_virtual_keyboard_bg_asset_exists(self):
        path = virtual_keyboard_bg_asset_path()
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "background.png")

    def test_target_rect_character_name_matches_reference(self):
        rect = Rect(0, 0, 1919, 1007)
        x, y, w, h = virtual_keyboard_target_rect(rect, "character_name")
        self.assertEqual((w, h), (568, 290))
        self.assertAlmostEqual(x + w / 2, rect.width / 2, delta=0.5)
        self.assertEqual(y + h, 895)

    def test_target_rect_pet_name_matches_reference(self):
        rect = Rect(0, 0, 1919, 1007)
        x, y, w, h = virtual_keyboard_target_rect(rect, "pet_name")
        self.assertEqual((w, h), (568, 290))
        self.assertAlmostEqual(x + w, char_create_pet_panel_rect(rect).left - 4 * 1007 / 768, delta=0.5)
        self.assertEqual(y + h, char_create_pet_panel_rect(rect).bottom)

    def test_positions_scale_with_height_and_ignore_aspect_ratio_for_pet_margin(self):
        for width, height in ((1024, 768), (1280, 720), (1920, 1080),
                              (2560, 1440), (3440, 1440), (3840, 2160)):
            with self.subTest(size=(width, height)):
                rect = Rect(-300, 120, width, height)
                cx, cy, cw, ch = virtual_keyboard_target_rect(rect, "character_name")
                px, py, pw, ph = virtual_keyboard_target_rect(rect, "pet_name")
                self.assertLessEqual(abs(cx + cw / 2 - (rect.left + width / 2)), 0.5)
                panel = char_create_pet_panel_rect(rect)
                field = char_create_text_field_rect(rect, "character_name")
                self.assertAlmostEqual(panel.left - (px + pw), 4 * height / 768, delta=0.5)
                self.assertEqual((cw, ch), (pw, ph))
                self.assertAlmostEqual(field.top - (cy + ch), 20 * height / 768, delta=0.5)
                self.assertEqual(py + ph, panel.bottom)
                self.assertLess(px + pw, panel.left)
                for x, y, w, h in ((cx, cy, cw, ch), (px, py, pw, ph)):
                    self.assertGreaterEqual(x, rect.left)
                    self.assertLessEqual(x + w, rect.right)
                    self.assertGreaterEqual(y - 25 * h / 290, rect.top)
                    self.assertLess(y + h, rect.bottom)

    def test_user_window_captures_anchor_next_to_actual_boxes(self):
        # Measured client bounds and box edges in the two user screenshots.
        rect = Rect(2, 33, 830, 620)
        x, y, w, h = virtual_keyboard_target_rect(rect, "pet_name")
        self.assertAlmostEqual(x + w, 674, delta=2)
        self.assertAlmostEqual(y + h, 511, delta=2)
        panel = char_create_pet_panel_rect(rect)
        self.assertAlmostEqual(panel.left, 676, delta=2)
        self.assertLessEqual(panel.left - (x + w), 4)
        self.assertGreater(x, 300)  # Previous screenshot incorrectly started around 235px.
        rect = Rect(4, 30, 830, 620)
        x, y, w, h = virtual_keyboard_target_rect(rect, "character_name")
        self.assertAlmostEqual(x + w / 2, 419, delta=1)
        self.assertAlmostEqual(y + h, 581, delta=2)
        self.assertGreaterEqual(588 - (y + h), 6)  # Visible breathing room above the label.

    def test_resizing_only_width_keeps_pet_attached_and_centers_player(self):
        for height in (480, 620, 768, 1080, 1440):
            narrow = Rect(120, 80, round(height * 4 / 3), height)
            wide = Rect(120, 80, round(height * 21 / 9), height)
            dx = wide.width - narrow.width
            a = virtual_keyboard_target_rect(narrow, "pet_name")
            b = virtual_keyboard_target_rect(wide, "pet_name")
            self.assertEqual(b[0] - a[0], dx)
            self.assertEqual(a[1:], b[1:])
            a = virtual_keyboard_target_rect(narrow, "character_name")
            b = virtual_keyboard_target_rect(wide, "character_name")
            self.assertAlmostEqual(b[0] - a[0], dx / 2, delta=1)
            self.assertEqual(a[1:], b[1:])

    def test_keyboard_fits_narrow_windows_including_instruction_label(self):
        for target in ("character_name", "pet_name"):
            rect = Rect(150, 80, 400, 1080)
            x, y, w, h = virtual_keyboard_target_rect(rect, target)
            self.assertGreaterEqual(x, rect.left)
            self.assertLessEqual(x + w, rect.right)
            self.assertGreaterEqual(y - 25 * h / 290, rect.top)
            self.assertLessEqual(y + h, rect.bottom)

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

    def test_every_printed_character_can_be_inserted(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._virtual_keyboard_open = True
            for key_id, row, col, span, kind in KEYBOARD_LAYOUT:
                if kind != "simple":
                    continue
                for caps in ("default", "next_letter", "all_letters"):
                    engine._virtual_keyboard_caps_state = caps
                    engine._activate_virtual_key(key_id, rect, hub)
                    character = virtual_keyboard_character(key_id, caps)
                    injector.text.assert_called_with(character)
                    expected = "default" if caps == "next_letter" and character.isalpha() else caps
                    self.assertEqual(engine._virtual_keyboard_caps_state, expected)

    def test_printed_symbols_match_assets(self):
        self.assertEqual(virtual_keyboard_character("1x2", "default"), "1")
        self.assertEqual(virtual_keyboard_character("1x2", "all_letters"), "!")
        self.assertEqual(virtual_keyboard_character("2x13", "default"), "\\")
        self.assertEqual(virtual_keyboard_character("2x13", "all_letters"), "|")
        self.assertEqual(virtual_keyboard_character("3x11", "all_letters"), '"')
        self.assertEqual(virtual_keyboard_character("3x12", "all_letters"), "/")
        self.assertEqual(virtual_keyboard_character("4x11", "all_letters"), ">")

    def test_reopen_resets_caps_and_focuses_game_before_moving_to_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            engine._virtual_keyboard_caps_state = "all_letters"
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._open_virtual_keyboard("pet_name", rect, hub)
            self.assertEqual(shared.get().virtual_keyboard_caps_state, "default")
            self.assertEqual(shared.get().virtual_keyboard_focus, (3, 1))
            events = injector.mock_calls
            down = events.index(call.mouse_button("left", True))
            up = events.index(call.mouse_button("left", False))
            self.assertLess(down, up)
            self.assertEqual(events[-1][0], "move")

    def test_ok_consumes_controller_tick_without_gameplay_or_mouse(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._memory_state = GameMemoryState(is_connected=True, state_id=1)
            engine._char_create_initialized = True
            engine._last_state_id = 1
            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_target = "pet_name"
            engine._virtual_keyboard_focus = (5, 13)
            with patch.object(engine, "_handle_discrete_bindings") as bindings:
                engine._process_active(hub, ControllerState(buttons={"a"}), rect,
                                       engine.config.get(), 1.0, 0.01)
            self.assertFalse(shared.get().virtual_keyboard_open)
            injector.mouse_button.assert_not_called()
            bindings.assert_not_called()

    def test_mouse_key_click_and_ok_do_not_click_game_or_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_target = "character_name"
            for key_id, expected in (("3x1", "a"), ("ok", None)):
                kx, ky, kw, kh = virtual_keyboard_target_rect(rect, "character_name")
                x, y, w, h = virtual_keyboard_key_rect(kx, ky, kw, kh, key_id)
                shared.keyboard_event("click", round(x + w / 2), round(y + h / 2))
                injector.key_pressed.return_value = True
                engine._handle_keyboard_mouse(rect, hub)
                if expected:
                    injector.text.assert_called_with(expected)
            self.assertFalse(engine._virtual_keyboard_open)
            injector.mouse_button.assert_not_called()

    def test_nintendo_east_confirms_south_deletes_and_shoulders_move_caret(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_target = "character_name"
            engine._handle_virtual_keyboard_navigation(
                ControllerState(buttons={"b"}, controller_type="nintendo"), rect, hub)
            injector.text.assert_called_once_with("a")
            engine._handle_virtual_keyboard_navigation(
                ControllerState(buttons={"a", "lb"}, controller_type="nintendo"), rect, hub)
            injector.key.assert_any_call("BACKSPACE", True)
            injector.key.assert_any_call("LEFT", True)
            engine._handle_virtual_keyboard_navigation(ControllerState(buttons={"rb"}), rect, hub)
            injector.key.assert_any_call("RIGHT", True)

    def test_shift_once_survives_space_and_failed_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            engine._virtual_keyboard_caps_state = "next_letter"
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._activate_virtual_key("space", rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "next_letter")
            injector.text.return_value = False
            engine._activate_virtual_key("3x1", rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "next_letter")
            injector.text.return_value = True
            engine._activate_virtual_key("3x1", rect, hub)
            self.assertEqual(engine._virtual_keyboard_caps_state, "default")


    def test_physical_mouse_opens_switches_fields_and_closes_outside(self):
        from torchbridge.models import char_create_button_point
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(100, 50, 1920, 1080), MagicMock()
            for field in ("character_name", "pet_name"):
                injector.key_pressed.return_value = False
                engine._handle_keyboard_mouse(rect, hub)
                injector.cursor_position.return_value = char_create_button_point(rect, field)
                injector.key_pressed.return_value = True
                engine._handle_keyboard_mouse(rect, hub)
                self.assertEqual(shared.get().virtual_keyboard_target, field)
                self.assertTrue(engine._virtual_keyboard_open)
            injector.key_pressed.return_value = False
            engine._handle_keyboard_mouse(rect, hub)
            injector.cursor_position.return_value = (101, 51)
            injector.key_pressed.return_value = True
            engine._handle_keyboard_mouse(rect, hub)
            self.assertFalse(shared.get().virtual_keyboard_open)

    def test_holding_confirm_after_ok_never_clicks_creation_button(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, injector = self._make_engine(directory)
            rect, hub = Rect(0, 0, 1920, 1080), MagicMock()
            engine._memory_state = GameMemoryState(is_connected=True, state_id=1)
            engine._char_create_initialized = True
            engine._last_state_id = 1
            engine._virtual_keyboard_open = True
            engine._virtual_keyboard_target = "character_name"
            engine._virtual_keyboard_focus = (5, 11)
            held = ControllerState(buttons={"a"})
            for tick in range(3):
                engine._process_active(hub, held, rect, engine.config.get(), tick, 0.01)
                engine._previous = held
            self.assertFalse(engine._virtual_keyboard_open)
            injector.mouse_button.assert_not_called()


class VirtualKeyboardInjectionTests(unittest.TestCase):
    def test_arrows_are_supported_extended_scancodes(self):
        from types import SimpleNamespace
        from torchbridge import win32
        injector = object.__new__(win32.InputInjector)
        user32 = MagicMock()
        user32.MapVirtualKeyW.return_value = 75
        def keyboard(vk, scan, flags, timestamp, extra):
            return SimpleNamespace(vk=vk, scan=scan, flags=flags)
        with patch.object(win32, "user32", user32, create=True), \
             patch.object(win32, "KEYBDINPUT", keyboard, create=True), \
             patch.object(win32, "INPUT", lambda **kw: SimpleNamespace(**kw), create=True), \
             patch.object(injector, "_send", return_value=True) as send:
            for name, vk in (("LEFT", 0x25), ("RIGHT", 0x27)):
                injector.tap(name)
                user32.MapVirtualKeyW.assert_called_with(vk, 0)
                self.assertEqual(send.call_args_list[-2].args[0].ki.flags, 0x09)
                self.assertEqual(send.call_args_list[-1].args[0].ki.flags, 0x0B)

    def test_text_sends_exact_utf16_down_and_up_without_modifiers(self):
        from types import SimpleNamespace
        from torchbridge import win32
        injector = object.__new__(win32.InputInjector)
        def keyboard(vk, scan, flags, timestamp, extra):
            return SimpleNamespace(vk=vk, scan=scan, flags=flags)
        with patch.object(win32, "KEYBDINPUT", keyboard, create=True), \
             patch.object(win32, "INPUT", lambda **kw: SimpleNamespace(**kw), create=True), \
             patch.object(injector, "_send", return_value=True) as send:
            self.assertTrue(injector.text('aA!ç'))
            events = [c.args[0].ki for c in send.call_args_list]
            self.assertEqual([e.scan for e in events], [97, 97, 65, 65, 33, 33, 231, 231])
            self.assertEqual([e.flags for e in events], [4, 6] * 4)
            self.assertTrue(all(e.vk == 0 for e in events))
            send.return_value = False
            self.assertFalse(injector.text("a"))



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

    def test_calibration_nodes_only_render_when_mapping_is_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            for target in ("character_name", "pet_name"):
                for enabled in (False, True, False):
                    with self.subTest(target=target, calibration=enabled):
                        overlay.config.set_show_calibration(enabled)
                        snapshot = OverlaySnapshot(
                            game_rect=Rect(0, 0, 1920, 1080),
                            virtual_keyboard_open=True, virtual_keyboard_target=target,
                            virtual_keyboard_focus=(3, 2))
                        painter = MagicMock()
                        overlay._draw_virtual_keyboard(painter, snapshot, 1.0)
                        if enabled:
                            self.assertEqual(painter.drawRect.call_count, len(KEYBOARD_LAYOUT) + 1)
                        else:
                            painter.drawRect.assert_not_called()
                        # Background, key faces and focus highlight remain visible.
                        self.assertEqual(painter.drawPixmap.call_count, len(KEYBOARD_LAYOUT) + 3)
            overlay.shutdown()

    def test_mouse_surface_queues_click_in_physical_pixels(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            surface = overlay._keyboard_input
            surface.physical_rect = Rect(200, 300, 568, 290)
            # Simulate 200% display scaling: Qt logical size is half the physical size.
            surface.resize(284, 145)
            QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(100, 50))
            self.assertIn(("click", 400, 400), shared.take_keyboard_events())
            overlay.shutdown()

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

    def test_virtual_keyboard_key_cursor_point_matches_formula(self):
        # posX = largura - 10px e posY = altura - 10px
        cx, cy = virtual_keyboard_key_cursor_point(100.0, 200.0, 50.0, 40.0)
        self.assertEqual(cx, 140)
        self.assertEqual(cy, 230)

    def test_virtual_keyboard_animation_tick_and_direction(self):
        with tempfile.TemporaryDirectory() as directory:
            overlay, shared = self._make_overlay(directory)
            snap_open = OverlaySnapshot(virtual_keyboard_open=True, virtual_keyboard_target="character_name")
            snap_closed = OverlaySnapshot(virtual_keyboard_open=False, virtual_keyboard_target="")

            # Simula avanço de tempo para o tick
            overlay._virtual_keyboard_last_time = 0.0
            with patch("time.monotonic", return_value=0.15):
                overlay._tick_virtual_keyboard_anim(snap_open)
                self.assertGreater(overlay._virtual_keyboard_progress, 0.0)
                self.assertLessEqual(overlay._virtual_keyboard_progress, 1.0)
                self.assertEqual(overlay._last_virtual_keyboard_target, "character_name")

            # Quando fecha, diminui
            with patch("time.monotonic", return_value=0.30):
                overlay._tick_virtual_keyboard_anim(snap_closed)
                self.assertEqual(overlay._last_virtual_keyboard_target, "character_name")


if __name__ == "__main__":
    unittest.main()
