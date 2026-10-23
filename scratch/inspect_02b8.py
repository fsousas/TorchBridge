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

p_02b8 = 0x159F4498
raw = read_bytes(p_02b8, 512)
print(f"Tamanho lido: {len(raw)} bytes")

# Vamos ver os ponteiros contidos em 0x02B8
ptrs = []
for i in range(0, len(raw) - 4, 4):
    val = struct.unpack("<I", raw[i:i+4])[0]
    if 0x10000000 <= val <= 0x7FFFFFFF:
        # Lê vtable do objeto
        vt_bytes = read_bytes(val, 4)
        vt = struct.unpack("<I", vt_bytes)[0] if len(vt_bytes) == 4 else 0
        ptrs.append((i, val, vt))

print(f"Ponteiros encontrados em 0x02B8: {len(ptrs)}")
for off, val, vt in ptrs[:30]:
    # Lê primeiros bytes do objeto apontado
    ob_b = read_bytes(val, 32)
    # Tenta achar string
    cand_str = ""
    for b in ob_b:
        if 32 <= b < 127:
            cand_str += chr(b)
        elif cand_str:
            break
    print(f"  +0x{off:03X} -> ptr=0x{val:08X} vt=0x{vt:08X} str='{cand_str}'")

