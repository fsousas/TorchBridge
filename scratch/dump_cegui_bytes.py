import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
import struct
from src.torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
reader._ensure_handle()

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

w = 0x18CF6BA0
raw = read_bytes(w, 256)
for off in range(0, len(raw), 16):
    chunk = raw[off:off+16]
    hex_str = " ".join(f"{b:02X}" for b in chunk)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
    print(f"+0x{off:02X}: {hex_str} | {ascii_str}")

