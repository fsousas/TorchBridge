"""Transporte local de imagens BGRA premultiplicadas para o renderer D3D9 x86.

O processo do jogo abre os objetos pelo próprio PID. Só há dados de imagem e
estado; não há endereços, comandos ou entrada de teclado/mouse neste protocolo.
Layout compartilhado com native/fullscreen/protocol.h (inteiros LE de 32 bits).
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import mmap
import os
import struct


MAGIC = 0x54424F31
VERSION = 1
HEADER = struct.Struct("<16I")
MAX_DIMENSION = 4096
MAP_SIZE = HEADER.size + MAX_DIMENSION * MAX_DIMENSION * 4
TIMEOUT_MS = 1500


def mapping_name(pid: int) -> str:
    if pid <= 0:
        raise ValueError("PID inválido")
    return f"Local\\TorchBridge.Overlay.v1.{pid}"


def frame_size(width: int, height: int, max_width: int, max_height: int) -> tuple[int, int]:
    """Limita a textura sem mudar a proporção das coordenadas do jogo."""
    if min(width, height, max_width, max_height) <= 0:
        raise ValueError("Dimensões inválidas")
    ratio = min(1.0, min(MAX_DIMENSION, max_width) / width,
                min(MAX_DIMENSION, max_height) / height)
    return max(1, int(width * ratio)), max(1, int(height * ratio))


@dataclass(frozen=True)
class NativeStatus:
    connected: bool = False
    fullscreen: bool = False
    width: int = 0
    height: int = 0
    max_width: int = MAX_DIMENSION
    max_height: int = MAX_DIMENSION


def decode_status(header: bytes, now_ms: int) -> NativeStatus:
    fields = HEADER.unpack(header)
    if fields[:3] != (MAGIC, VERSION, HEADER.size):
        return NativeStatus()
    age = (now_ms - fields[9]) & 0xFFFFFFFF  # GetTickCount dá a volta a cada ~49 dias.
    if fields[13] != 1 or age > TIMEOUT_MS:
        return NativeStatus()
    if not fields[10] or not fields[11] or not fields[14] or not fields[15]:
        return NativeStatus()
    return NativeStatus(True, bool(fields[12]), fields[10], fields[11],
                        fields[14], fields[15])


class FrameChannel:
    """Um produtor Qt e um consumidor D3D9; nenhum deles espera pelo outro."""

    def __init__(self, pid: int) -> None:
        if os.name != "nt":
            raise OSError("O transporte do overlay nativo requer Windows")
        self._api = ctypes.WinDLL("kernel32", use_last_error=True)
        self._api.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        self._api.CreateMutexW.restype = wintypes.HANDLE
        self._api.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self._api.WaitForSingleObject.restype = wintypes.DWORD
        self._api.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        self._api.ReleaseMutex.restype = wintypes.BOOL
        self._api.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._api.CloseHandle.restype = wintypes.BOOL
        self._api.GetTickCount.argtypes = ()
        self._api.GetTickCount.restype = wintypes.DWORD
        self._mutex = self._api.CreateMutexW(None, False, mapping_name(pid) + ".Mutex")
        self._map: mmap.mmap | None = None
        self._last_header = HEADER.pack(*([0] * 16))
        if not self._mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self._map = mmap.mmap(-1, MAP_SIZE, tagname=mapping_name(pid), access=mmap.ACCESS_WRITE)
            with self._locked(50) as acquired:
                if not acquired:
                    raise OSError("O canal do overlay está ocupado")
                self._map[:HEADER.size] = HEADER.pack(MAGIC, VERSION, HEADER.size, *([0] * 13))
        except Exception:
            self.close()
            raise

    @contextmanager
    def _locked(self, timeout_ms: int = 0):
        result = self._api.WaitForSingleObject(self._mutex, timeout_ms)
        acquired = result in (0, 0x80)  # WAIT_OBJECT_0 / WAIT_ABANDONED
        try:
            # Um escritor morto pode ter deixado um frame incompleto.
            if result == 0x80 and self._map is not None:
                struct.pack_into("<I", self._map, 24, 0)
            yield acquired
        finally:
            if acquired:
                self._api.ReleaseMutex(self._mutex)

    def status(self) -> NativeStatus:
        with self._locked() as acquired:
            if acquired and self._map is not None:
                self._last_header = self._map[:HEADER.size]
            # Contenção por um frame não deve alternar entre Qt e D3D9.
            return decode_status(self._last_header, self._api.GetTickCount())

    def publish(self, pixels: memoryview, width: int, height: int, stride: int) -> bool:
        if not (0 < width <= MAX_DIMENSION and 0 < height <= MAX_DIMENSION):
            raise ValueError("Frame maior que o canal do overlay")
        size = stride * height
        if stride != width * 4 or len(pixels) != size or size > MAP_SIZE - HEADER.size:
            raise ValueError("Frame BGRA inválido")
        with self._locked() as acquired:
            if not acquired or self._map is None:
                return False
            self._map[HEADER.size:HEADER.size + size] = pixels
            fields = list(HEADER.unpack(self._map[:HEADER.size]))
            fields[3:9] = (width, height, stride, 1, (fields[7] + 1) & 0xFFFFFFFF,
                           self._api.GetTickCount())
            self._map[:HEADER.size] = HEADER.pack(*fields)
        return True

    def clear(self) -> None:
        if self._map is None:
            return
        with self._locked() as acquired:
            if acquired:
                struct.pack_into("<I", self._map, 24, 0)  # visible

    def close(self) -> None:
        if self._map is not None:
            self.clear()
            self._map.close()
            self._map = None
        if self._mutex:
            self._api.CloseHandle(self._mutex)
            self._mutex = None
