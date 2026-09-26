import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from torchbridge.fullscreen import IDENTITY, MANIFEST, install, remove, validate_x86


def pe_file(*, dll=False, machine=0x14C):
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, machine)
    struct.pack_into("<H", data, 86, 0x2000 if dll else 2)
    struct.pack_into("<H", data, 88, 0x10B)
    if dll:
        data.extend(IDENTITY)
    return bytes(data)


class FullscreenInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "Torchlight.exe"
        self.game.write_bytes(pe_file())
        self.source = self.root / "native.dll"
        self.source.write_bytes(pe_file(dll=True))

    def test_install_remove_preserves_game_and_settings(self):
        settings = self.root / "settings.txt"
        settings.write_text("FULLSCREEN:1")
        before = self.game.read_bytes()
        target = install(self.game, self.source)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())
        record = json.loads((self.root / MANIFEST).read_text())
        self.assertEqual(record["sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
        remove(self.game)
        self.assertFalse(target.exists())
        self.assertFalse((self.root / MANIFEST).exists())
        self.assertEqual(self.game.read_bytes(), before)
        self.assertEqual(settings.read_text(), "FULLSCREEN:1")

    def test_existing_mod_is_never_replaced_even_with_different_case(self):
        mod = self.root / "D3D9.DLL"
        mod.write_bytes(b"another mod")
        with self.assertRaises(FileExistsError):
            install(self.game, self.source)
        self.assertEqual(mod.read_bytes(), b"another mod")
        self.assertFalse((self.root / MANIFEST).exists())

    def test_modified_proxy_is_never_removed(self):
        target = install(self.game, self.source)
        target.write_bytes(target.read_bytes() + b"changed")
        with self.assertRaises(ValueError):
            remove(self.game)
        self.assertTrue(target.exists())
        self.assertTrue((self.root / MANIFEST).exists())

    def test_missing_or_wrong_architecture_binary_leaves_no_installation(self):
        for binary in (b"not PE", pe_file(dll=True, machine=0x8664), pe_file()):
            self.source.write_bytes(binary)
            with self.assertRaises(ValueError):
                install(self.game, self.source)
            self.assertIsNone(next(self.root.glob("d3d9.dll"), None))
            self.assertFalse((self.root / MANIFEST).exists())
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            install(self.game, self.source)

    def test_game_must_be_torchlight_x86(self):
        self.game.write_bytes(pe_file(machine=0x8664))
        with self.assertRaises(ValueError):
            install(self.game, self.source)
        other = self.root / "other.exe"
        other.write_bytes(pe_file())
        with self.assertRaises(ValueError):
            install(other, self.source)

    def test_truncated_or_out_of_bounds_pe_is_rejected(self):
        data = bytearray(pe_file())
        struct.pack_into("<I", data, 0x3C, 0xFFFFFFFE)
        for candidate in (bytes(data), pe_file()[:70], b"MZ"):
            with self.assertRaises(ValueError):
                validate_x86(candidate)

    def test_failed_metadata_write_rolls_back_dll(self):
        original_open = Path.open

        def fail_manifest(path, *args, **kwargs):
            if path.name == MANIFEST:
                raise PermissionError("read-only")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", fail_manifest):
            with self.assertRaises(PermissionError):
                install(self.game, self.source)
        self.assertFalse((self.root / "d3d9.dll").exists())

    def test_loaded_dll_keeps_manifest_when_windows_refuses_removal(self):
        target = install(self.game, self.source)
        original_unlink = Path.unlink

        def refuse_loaded(path, *args, **kwargs):
            if path == target:
                raise PermissionError("DLL in use")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", refuse_loaded):
            with self.assertRaises(PermissionError):
                remove(self.game)
        self.assertTrue(target.exists())
        self.assertTrue((self.root / MANIFEST).exists())
