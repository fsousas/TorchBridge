import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.models import Rect, SharedOverlayState
from torchbridge.native_overlay import NativeStatus
from torchbridge.overlay import GameOverlay
from torchbridge import win32


class OverlayLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.shared = SharedOverlayState()
        self.config = ConfigManager(Path(directory.name) / "perfil.json")
        self.overlay = GameOverlay(self.shared, self.config)
        self.overlay._timer.stop()
        self.addCleanup(self.overlay.shutdown)
        self.addCleanup(self.overlay.close)
        self.shared.update(game_found=True, game_active=True, game_rect=Rect(-400, 50, 400, 300))

    def attach_channel(self, *, fullscreen=True):
        self.shared.update(game_pid=123)
        self.overlay._channel_pid = 123
        channel = MagicMock()
        channel.status.return_value = NativeStatus(True, fullscreen, 400, 300)
        self.overlay._channel = channel
        self.frames = []
        channel.publish.side_effect = lambda pixels, w, h, stride: self.frames.append(
            (bytes(pixels), w, h, stride))
        return channel

    def test_overlay_disappears_on_focus_loss_and_returns(self):
        self.overlay._refresh()
        self.assertTrue(self.overlay.isVisible())
        self.shared.update(game_active=False)
        self.overlay._refresh()
        self.assertFalse(self.overlay.isVisible())
        self.shared.update(game_active=True)
        self.overlay._refresh()
        self.assertTrue(self.overlay.isVisible())

    def test_disabled_minimized_or_missing_game_never_shows(self):
        for changes in ({"enabled": False}, {"game_found": False}, {"game_rect": Rect()}):
            self.shared.update(enabled=True, game_found=True, game_rect=Rect(0, 0, 400, 300))
            self.shared.update(**changes)
            self.overlay._refresh()
            self.assertFalse(self.overlay.isVisible())

    def test_exclusive_publishes_bgra_without_showing_external_window(self):
        channel = self.attach_channel()
        self.overlay._refresh()
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(len(self.frames), 1)
        pixels, width, height, stride = self.frames[0]
        self.assertEqual((width, height, stride, len(pixels)), (400, 300, 1600, 480000))
        self.assertEqual(pixels[:4], bytes(4))
        self.assertIn("Direct3D 9", self.overlay.backend_status)
        self.shared.update(game_active=False)
        self.overlay._refresh()
        self.assertEqual(channel.publish.call_count, 1)
        channel.clear.assert_called_once()

    def test_fullscreen_to_windowed_returns_to_qt_and_clears_native_frame(self):
        channel = self.attach_channel()
        self.overlay._refresh()
        channel.status.return_value = NativeStatus(True, False, 400, 300)
        self.overlay._refresh()
        self.assertTrue(self.overlay.isVisible())
        channel.clear.assert_called_once()
        self.assertEqual(channel.publish.call_count, 1)

    def test_closing_game_releases_old_pid_channel(self):
        channel = self.attach_channel()
        self.shared.update(game_found=False, game_pid=None)
        self.overlay._refresh()
        channel.close.assert_called_once()
        self.assertIsNone(self.overlay._channel)

    def test_transport_failure_closes_channel_without_stopping_ui(self):
        channel = self.attach_channel()
        channel.publish.side_effect = OSError("channel unavailable")
        with self.assertLogs("torchbridge.overlay", level="ERROR"):
            self.overlay._refresh()
        channel.close.assert_called_once()
        self.assertIsNone(self.overlay._channel)
        self.assertTrue(self.overlay.isVisible())

    def test_native_drawing_uses_game_coordinates_when_qt_window_has_different_size(self):
        self.overlay.resize(100, 100)
        self.shared.update(aim_x=200, aim_y=150)
        image = self.overlay._render_native(self.shared.get(), 4096, 4096)
        self.assertGreater(image.pixelColor(211, 150).alpha(), 0)
        self.assertEqual(image.pixelColor(20, 250).alpha(), 0)
        small = self.overlay._render_native(self.shared.get(), 200, 200)
        self.assertEqual((small.width(), small.height()), (200, 150))
        self.assertGreater(small.pixelColor(105, 75).alpha(), 0)

    def test_qt_paint_keeps_physical_aim_position_at_current_dpi(self):
        self.shared.update(aim_x=200, aim_y=150)
        ratio = self.overlay.devicePixelRatioF()
        self.overlay.resize(round(400 / ratio), round(300 / ratio))
        image = self.overlay.grab().toImage()
        self.assertGreater(image.pixelColor(211, 150).alpha(), 0)
        self.assertEqual(image.pixelColor(20, 250).alpha(), 0)

    def test_native_geometry_uses_pixels_and_never_activates_overlay(self):
        self.overlay._native_windows = True
        self.shared.update(game_hwnd=456)
        with patch("torchbridge.overlay.WindowLocator.is_foreground", return_value=True), \
                patch("torchbridge.overlay.make_overlay_clickthrough") as style, \
                patch("torchbridge.overlay.position_overlay", return_value=True) as position:
            self.overlay._refresh()
            self.assertEqual(position.call_args.args[1], Rect(-400, 50, 400, 300))
            style.assert_called_once()
            self.overlay.event(QEvent(QEvent.Type.WinIdChange))
            self.overlay._refresh()
            self.assertEqual(style.call_count, 2)
        with patch.object(win32, "IS_WINDOWS", True), \
                patch.object(win32, "user32", create=True) as api:
            api.SetWindowPos.return_value = 1
            self.assertTrue(win32.position_overlay(123, Rect(-1920, 0, 1920, 1080)))
            api.SetWindowPos.assert_called_once_with(123, -1, -1920, 0, 1920, 1080, 0x210)

    def test_native_focus_recheck_rejects_stale_engine_snapshot(self):
        self.overlay._native_windows = True
        self.shared.update(game_hwnd=456)
        with patch("torchbridge.overlay.WindowLocator.is_foreground", return_value=False), \
                patch("torchbridge.overlay.position_overlay") as position:
            self.overlay._refresh()
            self.assertFalse(self.overlay.isVisible())
            position.assert_not_called()
