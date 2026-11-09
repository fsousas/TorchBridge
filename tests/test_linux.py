"""Linux boundaries: identity/focus, scaling, memory permissions and installed assets.

No Wayland connections or synthetic input are opened by these tests. The one
/proc integration test reads only a fixture child process owned by this test.
"""
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

LINUX = sys.platform.startswith("linux")
if LINUX:
    from torchbridge import linux
    from torchbridge.linux_process import LinuxProcess, mapped_files, game_data_directory, process_start
from torchbridge.memory import TorchlightMemoryReader, get_audio_settings, get_save_character_count
from torchbridge.models import Rect, SharedOverlayState
from torchbridge.config import ConfigManager


@unittest.skipUnless(LINUX, "Linux platform boundary")
class LinuxWindowTests(unittest.TestCase):
    def setUp(self):
        self.game = dict(address="0x123", pid=123, mapped=True, hidden=False, visible=True,
                         xwayland=True, at=[-400, -50], size=[800, 600], monitor=1, title="Torchlight")
        self.active = self.game.copy()
        self.windows = [self.game]
        self.locator = linux.WindowLocator(["Torchlight.exe"], ["Torchlight"])
        def request(command):
            return {"activewindow": self.active, "clients": self.windows}[command]
        self.request = patch.object(linux.Hyprland, "request", side_effect=request)
        self.request.start()
        self.addCleanup(self.request.stop)
        self.name = patch.object(linux, "process_name", return_value="torchlight.exe")
        self.name.start()
        self.addCleanup(self.name.stop)

    def test_foreground_identity_geometry_and_pid(self):
        self.assertEqual(self.locator.find(), 0x123)
        self.assertEqual(self.locator.client_rect(0x123), Rect(-400, -50, 800, 600))
        self.assertEqual(self.locator.window_pid(0x123), 123)
        self.assertTrue(self.locator.is_foreground(0x123))

    def test_folder_title_cannot_impersonate_game(self):
        with patch.object(linux, "process_name", return_value="nautilus"):
            self.assertIsNone(self.locator.find())

    def test_hidden_or_wayland_native_elf_is_not_accepted_as_pe_game(self):
        for changes in ({"hidden": True}, {"mapped": False}, {"xwayland": False}):
            with self.subTest(changes=changes):
                self.windows = [dict(self.game, **changes)]
                self.active = self.windows[0]
                self.locator._last_scan = 0
                self.assertIsNone(self.locator.find())

    def test_focus_is_live_and_ipc_failure_fails_closed(self):
        self.assertTrue(self.locator.is_foreground(0x123))
        self.active = dict(self.game, address="0x456")
        self.assertFalse(self.locator.is_foreground(0x123))
        with patch.object(linux.Hyprland, "request", side_effect=TimeoutError):
            self.assertFalse(self.locator.is_foreground(0x123))
            self.assertIsNone(self.locator.find())
            self.assertEqual(self.locator.client_rect(0x123), Rect())
            self.assertIsNone(self.locator.window_pid(0x123))

    def test_negative_origins_fractional_scale_and_rotation(self):
        monitors = [dict(x=0, y=0, width=1920, height=1080, scale=1.25, transform=0),
                    dict(x=-900, y=-200, width=1920, height=1080, scale=1.2, transform=1)]
        self.assertEqual(linux.desktop_bounds(monitors), (-900, -200, 2436, 1600))

    def test_movement_normalizes_logical_coordinates_and_clamps(self):
        injector = linux.InputInjector()
        connection = MagicMock()
        injector._connection = connection
        monitor = dict(x=-100, y=-200, width=1000, height=800, scale=2)
        with patch.object(linux.Hyprland, "monitors", return_value=[monitor]):
            self.assertTrue(injector.move(150, 0))
            connection.api.tb_move.assert_called_with(connection.handle, 250, 200, 500, 400)
            injector.move(-1000, 1000)
            connection.api.tb_move.assert_called_with(connection.handle, 0, 400, 500, 400)

    def test_text_releases_shift_even_if_character_send_fails(self):
        injector = linux.InputInjector()
        connection = MagicMock()
        injector._connection = connection
        connection.api.tb_key.side_effect = [True, False, True]
        self.assertFalse(injector.text("A"))
        self.assertEqual(connection.api.tb_key.call_args.args[-2:], (42, False))

    def test_all_keyboard_asset_characters_have_native_input_codes(self):
        from torchbridge.models import KEYBOARD_CHARACTERS
        for variants in KEYBOARD_CHARACTERS:
            for row in variants:
                for char in row:
                    self.assertIn(char, linux.TEXT_KEYS)

    def test_single_instance_releases_without_unlink_race(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
            first = linux.SingleInstance()
            second = linux.SingleInstance()
            self.assertFalse(first.already_running)
            self.assertTrue(second.already_running)
            second.close()
            first.close()
            third = linux.SingleInstance()
            self.assertFalse(third.already_running)
            third.close()
            third.close()
            self.assertEqual(len(list(Path(directory).glob("*.lock"))), 1)


@unittest.skipUnless(LINUX, "Linux process boundary")
class LinuxMemoryTests(unittest.TestCase):
    def test_maps_preserve_spaces_offsets_and_deleted_mapping_names(self):
        text = ("7b240000-7b241000 r--p 00000000 08:01 12 /games/My Torchlight/Torchlight.exe\n"
                "7b241000-7b250000 r-xp 00001000 08:01 12 /games/My Torchlight/Torchlight.exe (deleted)\n"
                "ab000000-ab100000 rw-p 00000000 00:00 0 [heap]\n")
        entries = list(mapped_files(text))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], (0x7b240000, 0x7b241000, 0, "/games/My Torchlight/Torchlight.exe"))
        self.assertEqual(entries[1][2], 0x1000)
        self.assertEqual(entries[1][3], entries[0][3])

    def test_starttime_ignores_parentheses_and_spaces_in_comm(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / "123").mkdir()
            (proc / "123/stat").write_text("123 (My (game)) " + " ".join(["S"] + ["0"]*18 + ["98765"]))
            self.assertEqual(process_start(123, proc), "98765")

    def test_permissions_are_reported_without_global_workaround(self):
        process = LinuxProcess()
        with patch("torchbridge.linux_process.process_start", return_value="123"), \
                patch.object(Path, "read_text", return_value="Torchlight.exe"), \
                patch("torchbridge.linux_process.os.open", side_effect=PermissionError):
            self.assertFalse(process.attach(5))
        self.assertIn("--launch", process.error)
        self.assertIsNone(process.fd)
        self.assertFalse(process.attach(-1))
        self.assertEqual(process.error, "")

    def test_module_base_is_read_from_pe_header_instead_of_fixed_address(self):
        process = LinuxProcess()
        process.pid = 5
        header = bytearray(64)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 60, 0x100)
        pe = bytearray(84)
        pe[:4] = b"PE\0\0"
        struct.pack_into("<H", pe, 4, 0x14c)
        struct.pack_into("<H", pe, 24, 0x10b)
        struct.pack_into("<I", pe, 80, 0x900000)
        process.read = lambda addr, size: bytes(header if addr == 0x71000000 else pe)
        with patch.object(Path, "read_text", return_value="71000000-71001000 r--p 00000000 00:00 1 /games/Torchlight.exe"):
            self.assertEqual(process.module_info(), (0x71000000, 0x900000, "/games/Torchlight.exe"))
        pe[4:6] = b"\x64\x86"  # x64 is not a mapped Torchlight 1 layout.
        with patch.object(Path, "read_text", return_value="71000000-71001000 r--p 00000000 00:00 1 /games/Torchlight.exe"):
            self.assertEqual(process.module_info(), (0, 0, ""))

    def test_prefix_case_sensitive_paths_save_and_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "drive_c/users/steamuser/AppData/Roaming/Runic Games/Torchlight"
            (data / "save").mkdir(parents=True)
            (data / "save/Hero.SVT").write_bytes(b"save")
            (data / "local_settings.txt").write_bytes("SOUND VOLUME:0.4\nMUSIC VOLUME:0.8\nSOUND MUTE:1\n".encode("utf-16"))
            with patch.dict(os.environ, {"WINEPREFIX": directory, "TORCHBRIDGE_GAME_DATA": ""}):
                found = game_data_directory()
            self.assertEqual(found, data)
            self.assertEqual(get_save_character_count(found), 1)
            settings = get_audio_settings(found)
            self.assertEqual(settings["sound_volume"], .4)
            self.assertTrue(settings["sound_mute"])

    def test_partial_and_invalid_reads_do_not_publish_fabricated_values(self):
        reader = TorchlightMemoryReader()
        reader._handle = 123
        reader._linux = MagicMock()
        reader._linux.read.return_value = b"\x01"
        self.assertIsNone(reader.read_u32(10))
        self.assertIsNone(reader.read_f32(10))
        self.assertEqual(reader.read_u8(10), 1)
        reader._linux.read.return_value = b"A\x00\x00\x00"
        self.assertEqual(reader.read_wstring(10), "A")

    def test_real_child_memory_is_read_only_and_stale_process_is_detached(self):
        # Yama scope=1 permits descendants; no games or foreign memory are read.
        code = ('import ctypes, sys; c=ctypes.CDLL(None); '
                'c.prctl(15,b"Torchlight.exe",0,0,0); '
                'b=ctypes.create_string_buffer(b"TB-memory-fixture"); '
                'print(ctypes.addressof(b),flush=True); sys.stdin.read()')
        child = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        process = LinuxProcess()
        try:
            address = int(child.stdout.readline())
            if not process.attach(child.pid):
                self.skipTest("Kernel policy does not allow reading child memory")
            self.assertEqual(process.read(address, 17), b"TB-memory-fixture")
            self.assertEqual(process.read(1, 4), b"")
            child.stdin.close()
            child.wait(timeout=5)
            self.assertFalse(process.attach(child.pid))
            self.assertIsNone(process.fd)
        finally:
            process.close()
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            child.stdout.close()


@unittest.skipUnless(LINUX, "Linux overlay boundary")
class LinuxOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_layer_paints_at_output_scale_and_keyboard_events_use_logical_origin(self):
        from torchbridge.overlay import GameOverlay
        with tempfile.TemporaryDirectory() as directory:
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, ConfigManager(Path(directory)/"perfil.json"))
            overlay._timer.stop()
            connection = MagicMock()
            overlay._wayland = connection
            overlay._virtual_keyboard_progress = 1.0
            connection.events.return_value = [("click", 20, 30)]
            monitor = dict(name="test", x=-800, y=-600, scale=1.25)
            shared.update(enabled=True, game_found=True, game_active=True, game_hwnd=123,
                          game_rect=Rect(-400, -300, 800, 600), virtual_keyboard_open=True)
            try:
                with patch("torchbridge.overlay.WindowLocator.is_foreground", return_value=True), \
                        patch("torchbridge.overlay.WindowLocator.monitor", return_value=monitor):
                    overlay._refresh()
                image, actual_monitor, rect, keyboard = connection.present.call_args.args
                self.assertEqual((image.width(), image.height()), (1600, 1200))
                self.assertEqual(rect, Rect(-400, -300, 800, 600))
                self.assertTrue(keyboard.valid)
                self.assertEqual(shared.take_keyboard_events(), [("click", -380, -270)])
                self.assertFalse(overlay.isVisible())
                shared.update(game_active=False)
                overlay._refresh()
                connection.hide.assert_called()
            finally:
                overlay.shutdown()
                overlay.close()

    def test_stale_focus_snapshot_never_presents_layer(self):
        from torchbridge.overlay import GameOverlay
        with tempfile.TemporaryDirectory() as directory:
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, ConfigManager(Path(directory)/"perfil.json"))
            overlay._timer.stop()
            connection = MagicMock()
            overlay._wayland = connection
            shared.update(enabled=True, game_found=True, game_active=True, game_hwnd=123, game_rect=Rect(0,0,800,600))
            try:
                with patch("torchbridge.overlay.WindowLocator.is_foreground", return_value=False):
                    overlay._refresh()
                connection.present.assert_not_called()
                connection.hide.assert_called()
            finally:
                overlay.shutdown()
                overlay.close()


class InstalledResourcesTests(unittest.TestCase):
    def test_frozen_resources_keep_existing_windows_bundle_layout(self):
        from torchbridge.resources import resource_root
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", "/bundle", create=True):
            self.assertEqual(resource_root(), Path("/bundle"))

    def test_wheel_resolves_assets_relative_to_python_prefix(self):
        from torchbridge.resources import resource_root
        with patch.object(Path, "is_dir", return_value=False), patch.object(sys, "prefix", "/test/prefix"):
            self.assertEqual(resource_root(), Path("/test/prefix/share/torchbridge"))


class LaunchArgumentTests(unittest.TestCase):
    def test_proton_command_keeps_its_own_double_dash_and_paths_with_spaces(self):
        from torchbridge.app import _arguments
        command = ["/games/My Runtime/run", "--", "/games/GE Proton/proton", "run", "/games/Torchlight.exe"]
        args = _arguments(["--perfil", "/tmp/My Profile.json", "--launch", *command])
        self.assertEqual(args.launch, command)
        self.assertEqual(args.perfil, Path("/tmp/My Profile.json"))

    def test_windows_fullscreen_arguments_keep_existing_behavior(self):
        from torchbridge.app import _arguments
        args = _arguments(["--fullscreen-setup", "install"])
        self.assertEqual(args.fullscreen_setup, "install")
        self.assertIsNone(args.launch)
