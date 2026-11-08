"""Regression for Wine name fields: settle pointer before clicking, not every move."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.input_session import InputCancelled, InputSession
from torchbridge.models import Rect, SharedOverlayState, char_create_button_point
from torchbridge import win32


class TextFieldFocusTests(unittest.TestCase):
    def engine(self, directory, injector):
        shared = SharedOverlayState()
        engine = BridgeEngine(ConfigManager(Path(directory) / "perfil.json"), shared)
        engine.injector = injector
        return engine, shared

    def test_win32_keeps_original_click_order_without_any_wait(self):
        # Exercise the actual Windows backend methods against a fake user32, even
        # on Linux. The new hook must not add sleeps or change native calls.
        rect = Rect(0, 0, 1920, 1080)
        for wrapped in (False, True):
            for target in ("character_name", "pet_name"):
                with self.subTest(wrapped=wrapped, target=target), tempfile.TemporaryDirectory() as directory:
                    with patch.object(win32, "IS_WINDOWS", True):
                        native = win32.InputInjector()
                    calls = []
                    with patch.object(native, "move", side_effect=lambda x, y: calls.append(("move", x, y)) or True), \
                            patch.object(native, "mouse_button", side_effect=lambda b, d: calls.append((b, d)) or True), \
                            patch("time.sleep") as sleep:
                        injector = InputSession(native, lambda: True) if wrapped else native
                        engine, shared = self.engine(directory, injector)
                        engine._open_virtual_keyboard(target, rect, MagicMock())
                    self.assertEqual(calls[:3], [("move", *char_create_button_point(rect, target)),
                                                ("left", True), ("left", False)])
                    self.assertEqual(len(calls), 4)
                    self.assertEqual(calls[-1][0], "move")
                    self.assertTrue(shared.get().virtual_keyboard_open)
                    sleep.assert_not_called()

    def test_focus_cancellation_during_settle_never_clicks_or_opens_keyboard(self):
        class Backend:
            def __init__(self):
                self.calls = []
            def move(self, x, y):
                self.calls.append("move")
                return True
            def wait_for_text_field_cursor(self):
                self.calls.append("wait-cancelled")
                return False
            def mouse_button(self, button, down):
                self.calls.append("click")
                return True
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            engine, shared = self.engine(directory, InputSession(backend, lambda: True))
            with self.assertRaises(InputCancelled):
                engine._open_virtual_keyboard("pet_name", Rect(0, 0, 1920, 1080), MagicMock())
            self.assertEqual(backend.calls, ["move", "wait-cancelled"])
            self.assertFalse(shared.get().virtual_keyboard_open)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux focus synchronization")
    def test_linux_wait_precedes_field_click_for_both_targets_and_wrappers(self):
        from torchbridge.linux import InputInjector
        rect = Rect(0, 0, 1920, 1080)
        for wrapped in (False, True):
            for target in ("character_name", "pet_name"):
                with self.subTest(wrapped=wrapped, target=target), tempfile.TemporaryDirectory() as directory:
                    backend = InputInjector()
                    calls = []
                    with patch.object(backend, "move", side_effect=lambda x, y: calls.append(("move", x, y)) or True), \
                            patch.object(backend, "mouse_button", side_effect=lambda b, d: calls.append((b, d)) or True):
                        # Class lookup deliberately bypasses MagicMock capabilities;
                        # mock the clock/sleep rather than replacing the hook.
                        elapsed = [0.0]
                        def sleep(dt):
                            calls.append(("wait", dt))
                            elapsed[0] += dt
                        injector = InputSession(backend, lambda: True) if wrapped else backend
                        engine, shared = self.engine(directory, injector)
                        with patch("torchbridge.linux.time.monotonic", side_effect=lambda: elapsed[0]), \
                                patch("torchbridge.linux.time.sleep", side_effect=sleep):
                            engine._open_virtual_keyboard(target, rect, MagicMock())
                    self.assertEqual(calls[0], ("move", *char_create_button_point(rect, target)))
                    click_index = calls.index(("left", True))
                    self.assertAlmostEqual(sum(c[1] for c in calls[1:click_index]), .080)
                    self.assertEqual(calls[click_index + 1], ("left", False))
                    self.assertEqual(calls[click_index + 2][0], "move")
                    self.assertEqual(len(calls), click_index + 3)
                    self.assertTrue(shared.get().virtual_keyboard_open)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux focus synchronization")
    def test_linux_wait_rechecks_lease_while_waiting(self):
        from torchbridge.linux import InputInjector
        backend = InputInjector()
        backend.set_focus_guard(MagicMock(side_effect=[True, False]))
        with patch("torchbridge.linux.time.monotonic", return_value=0), \
                patch("torchbridge.linux.time.sleep") as sleep:
            self.assertFalse(backend.wait_for_text_field_cursor())
        sleep.assert_called_once_with(.005)
