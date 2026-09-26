import ctypes
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from torchbridge import native_overlay as native


def status_header(tick=1000, fullscreen=1):
    return native.HEADER.pack(native.MAGIC, 1, 64, 0, 0, 0, 0, 0, 0,
                              tick, 1920, 1080, fullscreen, 1, 4096, 4096)


class NativeProtocolTests(unittest.TestCase):
    def test_status_timeout_and_tick_wrap(self):
        self.assertTrue(native.decode_status(status_header(), 1001).fullscreen)
        self.assertFalse(native.decode_status(status_header(), 2501).connected)
        self.assertTrue(native.decode_status(status_header(0xFFFFFF00), 0x100).connected)
        self.assertFalse(native.decode_status(status_header(fullscreen=0), 1001).fullscreen)
        self.assertFalse(native.decode_status(bytes(64), 1001).connected)

    def test_texture_limits_preserve_aspect_ratio(self):
        self.assertEqual(native.frame_size(1920, 1080, 4096, 4096), (1920, 1080))
        self.assertEqual(native.frame_size(7680, 4320, 4096, 4096), (4096, 2304))
        self.assertEqual(native.frame_size(3840, 2160, 2048, 2048), (2048, 1152))
        with self.assertRaises(ValueError):
            native.frame_size(0, 1080, 4096, 4096)

    def test_channel_is_scoped_to_pid(self):
        self.assertNotEqual(native.mapping_name(123), native.mapping_name(456))
        with self.assertRaises(ValueError):
            native.mapping_name(0)


class FakeMapping(bytearray):
    closed = False
    def close(self):
        self.closed = True


class FrameChannelTests(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.api.CreateMutexW.return_value = 123
        self.api.WaitForSingleObject.return_value = 0
        self.api.GetTickCount.return_value = 1000
        self.memory = FakeMapping(4096)
        for p in (patch.object(native, "os", SimpleNamespace(name="nt")),
                  patch.object(ctypes, "WinDLL", return_value=self.api, create=True),
                  patch.object(native.mmap, "mmap", return_value=self.memory)):
            p.start()
            self.addCleanup(p.stop)
        self.channel = native.FrameChannel(1234)
        self.addCleanup(self.channel.close)

    def test_bgra_publish_preserves_consumer_status_and_clear_stops_visibility(self):
        self.memory[:64] = status_header()
        pixels = memoryview(bytes([10, 20, 30, 40]) * 6)
        self.assertTrue(self.channel.publish(pixels, 3, 2, 12))
        header = native.HEADER.unpack(self.memory[:64])
        self.assertEqual(header[3:9], (3, 2, 12, 1, 1, 1000))
        self.assertEqual(header[9:], native.HEADER.unpack(status_header())[9:])
        self.assertEqual(self.memory[64:88], bytes(pixels))
        self.channel.clear()
        self.assertEqual(struct.unpack_from("<I", self.memory, 24)[0], 0)

    def test_mutex_contention_never_waits_or_switches_a_fresh_backend(self):
        self.memory[:64] = status_header()
        self.assertTrue(self.channel.status().connected)
        before = bytes(self.memory)
        self.api.WaitForSingleObject.return_value = 258
        self.assertFalse(self.channel.publish(memoryview(bytes(16)), 2, 2, 8))
        self.assertEqual(bytes(self.memory), before)
        self.assertTrue(self.channel.status().connected)
        self.api.WaitForSingleObject.assert_called_with(123, 0)
        self.api.GetTickCount.return_value = 3000
        self.assertFalse(self.channel.status().connected)

    def test_abandoned_writer_cannot_leave_a_torn_frame_visible(self):
        self.channel.publish(memoryview(bytes(16)), 2, 2, 8)
        self.api.WaitForSingleObject.return_value = 0x80
        self.channel.status()
        self.assertEqual(struct.unpack_from("<I", self.memory, 24)[0], 0)
        self.api.ReleaseMutex.assert_called_with(123)

    def test_malformed_pixels_rejected_before_touching_channel(self):
        before = bytes(self.memory)
        for width, height, stride, size in ((0, 1, 0, 0), (4097, 1, 16388, 16388),
                                           (2, 2, 12, 24), (2, 2, 8, 12)):
            with self.assertRaises(ValueError):
                self.channel.publish(memoryview(bytes(size)), width, height, stride)
        self.assertEqual(bytes(self.memory), before)

    def test_close_clears_pixels_and_releases_handles_once(self):
        self.channel.publish(memoryview(bytes(16)), 2, 2, 8)
        self.channel.close()
        self.channel.close()
        self.assertTrue(self.memory.closed)
        self.assertEqual(struct.unpack_from("<I", self.memory, 24)[0], 0)
        self.api.CloseHandle.assert_called_once_with(123)
