"""ctypes boundary for the Linux transport (no Python callbacks from C).

Only the owner thread touches each connection. Importing this module opens no
connections and emits no input; offscreen tests never load the native library.
"""
from __future__ import annotations

import ctypes as C
import importlib.util


def library():
    spec = importlib.util.find_spec("torchbridge._wayland")
    if spec is None or not spec.origin:
        raise OSError("Transporte Wayland ausente. Reinstale com: python -m pip install -e .")
    api = C.CDLL(spec.origin)
    signatures = {
        "tb_error": ([], C.c_char_p),
        "tb_open": ([C.c_int], C.c_void_p),
        "tb_close": ([C.c_void_p], None),
        "tb_dispatch": ([C.c_void_p], C.c_int),
        "tb_key": ([C.c_void_p, C.c_uint32, C.c_int], C.c_int),
        "tb_button": ([C.c_void_p, C.c_uint32, C.c_int], C.c_int),
        "tb_move": ([C.c_void_p] + [C.c_uint32] * 4, C.c_int),
        "tb_hide": ([C.c_void_p], None),
        "tb_geometry": ([C.c_void_p, C.c_char_p] + [C.c_int] * 8, C.c_int),
        "tb_cursor": ([C.c_void_p, C.c_void_p, C.c_int, C.c_int], C.c_int),
        "tb_present": ([C.c_void_p, C.c_void_p] + [C.c_int] * 3, C.c_int),
        "tb_next_event": ([C.c_void_p] + [C.POINTER(C.c_int)] * 3, C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    return api


class Connection:
    def __init__(self, *, input: bool = False):
        self.api = library()
        self.handle = self.api.tb_open(input)
        if not self.handle:
            raise OSError(self.api.tb_error().decode("utf-8", "replace"))

    def close(self):
        if self.handle:
            self.api.tb_close(self.handle)
            self.handle = None

    def hide(self):
        if self.handle:
            self.api.tb_hide(self.handle)

    def set_cursor(self, image):
        from PySide6.QtGui import QImage
        if image.isNull():
            return
        image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        pixels = C.c_char.from_buffer(image.bits())
        if not self.api.tb_cursor(self.handle, C.addressof(pixels), image.width(), image.height()):
            raise OSError("Falha ao configurar o cursor do teclado Wayland")

    def present(self, image, monitor: dict, rect, keyboard_rect=None):
        import math
        from .models import Rect
        scale = max(1, math.ceil(float(monitor["scale"])))
        keyboard = keyboard_rect or Rect()
        args = (keyboard.left - rect.left, keyboard.top - rect.top,
                keyboard.width, keyboard.height) if keyboard.valid else (0, 0, 0, 0)
        if not self.api.tb_geometry(self.handle, monitor["name"].encode(),
                                    rect.left - monitor["x"], rect.top - monitor["y"],
                                    rect.width, rect.height, *args):
            raise OSError("Não foi possível posicionar o overlay Wayland")
        # QImage owns the memory until this synchronous copy to wl_shm returns.
        pixels = C.c_char.from_buffer(image.bits())
        if not self.api.tb_present(self.handle, C.addressof(pixels), image.width(), image.height(), scale):
            raise OSError("Falha ao apresentar overlay Wayland")

    def events(self):
        if not self.api.tb_dispatch(self.handle):
            raise OSError("Conexão Wayland encerrada")
        kind, x, y = C.c_int(), C.c_int(), C.c_int()
        while self.api.tb_next_event(self.handle, C.byref(kind), C.byref(x), C.byref(y)):
            yield ("click" if kind.value == 2 else "hover", x.value, y.value)
