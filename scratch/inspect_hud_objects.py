import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
import struct
from src.torchbridge.memory import TorchlightMemoryReader, OFFSET_GAMECLIENT, OFFSET_GAMEUI, kernel32

reader = TorchlightMemoryReader()
if not reader._ensure_handle():
    print("ERRO")
    sys.exit(1)

def safe_u32(addr: int) -> int:
    v = reader.read_u32(addr)
    return v if v is not None else 0

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

cgame_addr = reader._resolve_cgame_address()
p_game = safe_u32(cgame_addr)
p_client = safe_u32(p_game + OFFSET_GAMECLIENT)
p_ui = safe_u32(p_client + OFFSET_GAMEUI)

slots = [
    ("0x02AC", safe_u32(p_ui + 0x02AC)),
    ("0x02B0", safe_u32(p_ui + 0x02B0)),
    ("0x02B4", safe_u32(p_ui + 0x02B4)),
    ("0x02B8", safe_u32(p_ui + 0x02B8)),
    ("0x02BC", safe_u32(p_ui + 0x02BC)),
]

for name, ptr in slots:
    print(f"\n================ Objeto {name} em 0x{ptr:08X} ================")
    raw = read_bytes(ptr, 128)
    for off in range(0, len(raw), 16):
        chunk = raw[off:off+16]
        hex_vals = " ".join(f"{b:02x}" for b in chunk)
        # Tenta interpretar como u32s
        u32s = [struct.unpack("<I", chunk[i:i+4])[0] for i in range(0, len(chunk), 4) if i+4 <= len(chunk)]
        u32_str = " ".join(f"0x{u:08X}" for u in u32s)
        print(f"  +0x{off:02X}: {hex_vals} | {u32_str}")

