import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
import struct
from src.torchbridge.memory import TorchlightMemoryReader, OFFSET_GAMECLIENT, OFFSET_GAMEUI, OFFSET_PLAYER, kernel32

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
p_player = safe_u32(p_client + OFFSET_PLAYER)

print("=== Objetos em CGameUI com vtable em Torchlight.exe ===")
for off in range(0x0, 0x1000, 4):
    val = safe_u32(p_ui + off)
    if val > 0x10000:
        vt = safe_u32(val)
        # Se vtable estiver no range do executável (0x00400000 a 0x00B00000)
        if 0x00400000 <= vt <= 0x00B00000:
            # Lê primeiros 64 bytes
            b = read_bytes(val, 64)
            # Checa se algum byte parece flag isOpen / isVisible (geralmente byte em 0x18, 0x1C, 0x30, 0x34, 0x44 etc)
            flags = [f"+0x{i:02X}={b[i]}" for i in (0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40, 0x44) if i < len(b) and b[i] == 1]
            print(f"p_ui + 0x{off:04X} -> 0x{val:08X} (vt: 0x{vt:08X}) flags==1: {flags}")

