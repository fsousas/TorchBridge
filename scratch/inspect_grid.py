import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
import struct
from src.torchbridge.memory import TorchlightMemoryReader, OFFSET_GAMECLIENT, OFFSET_GAMEUI, OFFSET_PLAYER, kernel32

reader = TorchlightMemoryReader()
if not reader._ensure_handle():
    print("ERRO: Torchlight não encontrado.")
    sys.exit(1)

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

def safe_u32(addr: int) -> int:
    v = reader.read_u32(addr)
    return v if v is not None else 0

cgame_addr = reader._resolve_cgame_address()
p_game = safe_u32(cgame_addr)
p_client = safe_u32(p_game + OFFSET_GAMECLIENT)
p_ui = safe_u32(p_client + OFFSET_GAMEUI)
p_player = safe_u32(p_client + OFFSET_PLAYER)

print(f"p_ui = 0x{p_ui:08X}")

print("\n--- Todos os campos em p_ui de 0x2A0 a 0x360 ---")
for off in range(0x2A0, 0x360, 4):
    val = safe_u32(p_ui + off)
    vt = safe_u32(val) if (val > 0x10000) else 0
    b = read_bytes(val, 32) if (val > 0x10000) else b""
    print(f"0x{off:04X}: val=0x{val:08X} vt=0x{vt:08X} bytes={b[:16].hex() if b else ''}")

p_menu_mgr = safe_u32(p_ui + 0x0324)
print(f"\np_menu_mgr (0x0324) = 0x{p_menu_mgr:08X}")
if p_menu_mgr:
    for off in range(0, 0x100, 4):
        val = safe_u32(p_menu_mgr + off)
        if val > 0x10000:
            vt = safe_u32(val)
            b = read_bytes(val, 16)
            print(f"  mgr + 0x{off:02X}: 0x{val:08X} (vt=0x{vt:08X}) {b.hex()}")

