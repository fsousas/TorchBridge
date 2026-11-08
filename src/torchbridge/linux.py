"""Omarchy/Hyprland integration. All engine coordinates are compositor logical pixels.

Hyprland IPC is used directly, with timeouts and fail-closed focus checks. Input
uses the compositor's virtual devices, not X11 warps or a privileged uinput daemon.
Xwayland is consulted only for the physical key/button state used by the engine.
"""
from __future__ import annotations

import ctypes as C
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import time

from .models import Rect
from .wayland import Connection
from .win32 import key_code


class Hyprland:
    @staticmethod
    def request(command: str):
        signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        runtime = os.environ.get("XDG_RUNTIME_DIR", "")
        if not signature or not runtime:
            raise OSError("Inicie o TorchBridge dentro da sessão Omarchy/Hyprland")
        path = Path(runtime) / "hypr" / signature / ".socket.sock"
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.2)
            client.connect(str(path))
            client.sendall(("j/" + command).encode())
            parts = []
            size = 0
            while chunk := client.recv(65536):
                parts.append(chunk)
                size += len(chunk)
                if size > 4 * 1024 * 1024:
                    raise OSError("Resposta Hyprland excedeu o limite")
        return json.loads(b"".join(parts))

    @classmethod
    def monitors(cls):
        return [m for m in cls.request("monitors") if not m.get("disabled")]


def process_name(pid: int) -> str:
    """Wine sets comm to the PE executable; never accept a title as process identity."""
    try:
        return (Path("/proc") / str(pid) / "comm").read_text(errors="replace").strip().casefold()
    except OSError:
        return ""


class WindowLocator:
    def __init__(self, process_names, title_fragments):
        self.process_names = {n.casefold() for n in process_names}
        self.title_fragments = {t.casefold() for t in title_fragments}
        self._clients = []
        self._last_scan = 0.0

    def _matches(self, window):
        if (not window.get("mapped") or window.get("hidden") or not window.get("xwayland")
                or not window.get("pid") or not window.get("address")):
            return False
        if self.process_names:
            return process_name(int(window["pid"])) in self.process_names
        return window.get("title", "").casefold() in self.title_fragments

    def find(self):
        try:
            active = Hyprland.request("activewindow")
            if self._matches(active):
                return int(active["address"], 16)
            now = time.monotonic()
            if now - self._last_scan >= 0.1:
                self._clients = Hyprland.request("clients")
                self._last_scan = now
            return next((int(w["address"], 16) for w in self._clients if self._matches(w)), None)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def details(hwnd):
        if not hwnd:
            return None
        # Query live state: a cached focus check must never authorize input.
        for window in Hyprland.request("clients"):
            if int(window["address"], 16) == hwnd:
                return window
        return None

    @staticmethod
    def window_pid(hwnd):
        try:
            window = WindowLocator.details(hwnd)
            return int(window["pid"]) if window else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def client_rect(hwnd):
        try:
            window = WindowLocator.details(hwnd)
            if not window or window.get("hidden") or not window.get("mapped"):
                return Rect()
            return Rect(*window["at"], *window["size"])
        except (OSError, ValueError, KeyError, TypeError):
            return Rect()

    @staticmethod
    def is_foreground(hwnd):
        try:
            window = Hyprland.request("activewindow")
            return bool(window.get("mapped") and not window.get("hidden")
                        and window.get("visible", True) and window.get("xwayland")
                        and int(window.get("address", "0"), 16) == hwnd)
        except (OSError, ValueError, TypeError):
            return False

    @staticmethod
    def monitor(hwnd):
        window = WindowLocator.details(hwnd)
        if window:
            return next((m for m in Hyprland.monitors() if m["id"] == window["monitor"]), None)
        return None


# Evdev codes, matching the physical US scan codes used by the Windows backend.
KEYS = dict(zip("1234567890", range(2, 12)))
KEYS.update(dict(zip("QWERTYUIOP", range(16, 26))))
KEYS.update(dict(zip("ASDFGHJKL", range(30, 39))))
KEYS.update(dict(zip("ZXCVBNM", range(44, 51))))
KEYS.update(ESC=1, ESCAPE=1, TAB=15, SHIFT=42, CTRL=29, CONTROL=29,
            ALT=56, SPACE=57, ENTER=28, RETURN=28, BACKSPACE=14, LEFT=105, RIGHT=106)


TEXT_KEYS = {c.lower(): (code, False) for c, code in KEYS.items() if len(c) == 1}
TEXT_KEYS.update({c: (code, True) for c, code in KEYS.items() if len(c) == 1 and c.isalpha()})
for low, high, code in (("`", "~", 41), ("-", "_", 12), ("=", "+", 13),
                        ("[", "{", 26), ("]", "}", 27), ("\\", "|", 43),
                        (";", ":", 39), ("'", '"', 40), (",", "<", 51),
                        (".", ">", 52), ("/", "?", 53)):
    TEXT_KEYS[low], TEXT_KEYS[high] = (code, False), (code, True)
for digit, symbol in zip("1234567890", "!@#$%^&*()"):
    TEXT_KEYS[symbol] = (KEYS[digit], True)
TEXT_KEYS[" "] = (57, False)


class PhysicalState:
    """Read the Xwayland seat, including hardware presses, without sending input."""
    def __init__(self):
        self.api = C.CDLL("libX11.so.6")
        self.api.XOpenDisplay.argtypes = [C.c_char_p]
        self.api.XOpenDisplay.restype = C.c_void_p
        self.api.XCloseDisplay.argtypes = [C.c_void_p]
        self.api.XQueryKeymap.argtypes = [C.c_void_p, C.c_void_p]
        self.api.XDefaultRootWindow.argtypes = [C.c_void_p]
        self.api.XDefaultRootWindow.restype = C.c_ulong
        self.api.XQueryPointer.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
                                          C.POINTER(C.c_ulong)] + [C.POINTER(C.c_int)]*4 + [C.POINTER(C.c_uint)]
        self.display = self.api.XOpenDisplay(None)
        if not self.display:
            raise OSError("Xwayland indisponível (DISPLAY ausente); use Proton com wineX11")
        self.root = self.api.XDefaultRootWindow(self.display)

    def pressed(self, name):
        if name == "MOUSE_LEFT":
            root, child, mask = C.c_ulong(), C.c_ulong(), C.c_uint()
            coords = [C.c_int() for _ in range(4)]
            ok = self.api.XQueryPointer(self.display, self.root, C.byref(root), C.byref(child),
                                       *(C.byref(c) for c in coords), C.byref(mask))
            return bool(ok and mask.value & 256)
        code = KEYS[name] + 8
        bits = C.create_string_buffer(32)
        self.api.XQueryKeymap(self.display, bits)
        return bool(bits.raw[code//8] & (1 << (code % 8)))

    def text_character(self, char, allowed=lambda: True):
        """Unicode fallback for Xwayland clients, beyond the supplied ASCII keyboard.

        Borrow an unpressed, unused X keycode; preserve and restore its mapping.
        XTEST is used only here: Wayland virtual keymap changes are not propagated
        reliably by Xwayland for otherwise unmapped F13/F24 keys.
        """
        self.api.XGetKeyboardMapping.argtypes = [C.c_void_p, C.c_ubyte, C.c_int, C.POINTER(C.c_int)]
        self.api.XGetKeyboardMapping.restype = C.POINTER(C.c_ulong)
        self.api.XChangeKeyboardMapping.argtypes = [C.c_void_p, C.c_int, C.c_int, C.POINTER(C.c_ulong), C.c_int]
        self.api.XSync.argtypes = [C.c_void_p, C.c_int]
        self.api.XFree.argtypes = [C.c_void_p]
        xtst = C.CDLL("libXtst.so.6")
        xtst.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
        count = C.c_int()
        code = None
        old = None
        bits = C.create_string_buffer(32)
        self.api.XQueryKeymap(self.display, bits)
        for candidate in range(255, 199, -1):
            mapping = self.api.XGetKeyboardMapping(self.display, candidate, 1, C.byref(count))
            if not mapping:
                continue
            values = tuple(mapping[i] for i in range(count.value))
            self.api.XFree(mapping)
            if not any(values) and not bits.raw[candidate//8] & (1 << (candidate%8)):
                code, old = candidate, values
                break
        if code is None:
            return False
        symbol = ord(char) if ord(char) <= 255 else 0x01000000 | ord(char)
        new = (C.c_ulong * 1)(symbol)
        previous = (C.c_ulong * len(old))(*old)
        try:
            self.api.XChangeKeyboardMapping(self.display, code, 1, new, 1)
            self.api.XSync(self.display, False)
            time.sleep(0.01)  # Let Xwayland clients consume MappingNotify before KeyPress.
            if not allowed():
                return False
            down = xtst.XTestFakeKeyEvent(self.display, code, True, 0)
            up = xtst.XTestFakeKeyEvent(self.display, code, False, 0)
            self.api.XSync(self.display, False)
            time.sleep(0.01)
            return bool(down and up)
        finally:
            self.api.XChangeKeyboardMapping(self.display, code, len(old), previous, 1)
            self.api.XSync(self.display, False)

    def close(self):
        if self.display:
            self.api.XCloseDisplay(self.display)
            self.display = None


class InputInjector:
    def __init__(self):
        self._connection = None
        self._physical = None
        self._monitors = []
        self._last_monitors = 0.0
        self._focus_guard = lambda: True

    def set_focus_guard(self, allowed):
        self._focus_guard = allowed

    def wait_for_text_field_cursor(self):
        # Wine/OIS can process a click before the preceding Wayland pointer
        # motion reaches its game-side cursor. This wait is only for activating
        # the character/pet edit box, never for normal analog cursor movement.
        deadline = time.monotonic() + 0.080
        while True:
            if not self._focus_guard():
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(0.005, remaining))

    def _connect(self):
        if self._connection is None:
            self._connection = Connection(input=True)
        return self._connection

    def key(self, name, down):
        name = name.strip().upper()
        key_code(name)  # Identical validation on both systems.
        if name not in KEYS:
            raise ValueError(f"Tecla não suportada no perfil: {name!r}")
        c = self._connect()
        return bool(c.api.tb_key(c.handle, KEYS[name], down))

    def tap(self, name):
        down = self.key(name, True)
        up = self.key(name, False)
        return down and up

    def text(self, text):
        c = self._connect()
        for char in text:
            if not self._focus_guard():
                return False
            if char in TEXT_KEYS:
                code, shift = TEXT_KEYS[char]
                try:
                    if shift and not c.api.tb_key(c.handle, 42, True):
                        return False
                    if not c.api.tb_key(c.handle, code, True):
                        return False
                    if not c.api.tb_key(c.handle, code, False):
                        return False
                finally:
                    if shift:
                        c.api.tb_key(c.handle, 42, False)
            else:
                if self._physical is None:
                    self._physical = PhysicalState()
                if not self._physical.text_character(char, self._focus_guard):
                    return False
        return True

    def mouse_button(self, button, down):
        c = self._connect()
        return bool(c.api.tb_button(c.handle, {"left": 0x110, "right": 0x111}[button], down))

    def move(self, x, y):
        now = time.monotonic()
        if now - self._last_monitors > 0.5 or not self._monitors:
            self._monitors = Hyprland.monitors()
            self._last_monitors = now
        left, top, width, height = desktop_bounds(self._monitors)
        c = self._connect()
        return bool(c.api.tb_move(c.handle, max(0, min(width, x-left)), max(0, min(height, y-top)), width, height))

    @staticmethod
    def cursor_position():
        cursor = Hyprland.request("cursorpos")
        return round(cursor["x"]), round(cursor["y"])

    def key_pressed(self, name):
        name = name.strip().upper()
        key_code(name)
        if self._physical is None:
            self._physical = PhysicalState()
        return self._physical.pressed(name)

    def close(self):
        if self._physical:
            self._physical.close()
            self._physical = None
        if self._connection:
            self._connection.close()
            self._connection = None


def desktop_bounds(monitors):
    if not monitors:
        raise OSError("Nenhum monitor ativo no Hyprland")
    left = min(m["x"] for m in monitors)
    top = min(m["y"] for m in monitors)
    def size(m):
        w, h = m["width"], m["height"]
        if m.get("transform", 0) % 2:
            w, h = h, w
        return w / m["scale"], h / m["scale"]
    right = max(m["x"] + size(m)[0] for m in monitors)
    bottom = max(m["y"] + size(m)[1] for m in monitors)
    return left, top, round(right-left), round(bottom-top)


class SingleInstance:
    def __init__(self, name="TorchBridge.ControllerBridge"):
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        # Persistent inode: unlinking a live flock could allow a third instance.
        token = hashlib.sha256(name.encode()).hexdigest()[:16]
        fd = os.open(runtime / f"torchbridge-{token}.lock", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        self._file = os.fdopen(fd, "w")
        try:
            fcntl.flock(self._file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.already_running = False
        except BlockingIOError:
            self.already_running = True

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


def enable_dpi_awareness():
    pass  # Wayland supplies logical geometry and output scale explicitly.


def begin_high_resolution_timer():
    pass  # Linux monotonic timers do not require changing a global timer period.


def end_high_resolution_timer():
    pass


def show_information(title, message):
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    QMessageBox.information(None, title, message)


def make_overlay_clickthrough(hwnd, *, interactive=False):
    pass  # The Wayland layer sets an empty input region (except the keyboard).


def position_overlay(hwnd, rect):
    return False  # Positioning is handled by the layer-shell transport.
