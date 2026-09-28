import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
reader.update()

def read_str_ptr(addr):
    if not addr or addr < 0x10000:
        return ""
    ws = reader.read_wstring(addr, 32)
    if ws and len(ws) >= 3 and ws[0].isprintable() and not ws.startswith("?"):
        return f"ws:'{ws}'"
    import ctypes
    buf = ctypes.create_string_buffer(32)
    read = ctypes.c_size_t()
    if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, 32, ctypes.byref(read)):
        raw = buf.raw[:read.value].split(b"\x00")[0]
        try:
            s = raw.decode("latin1")
            if len(s) >= 3 and all(32 <= ord(c) < 127 for c in s):
                return f"s:'{s}'"
        except Exception:
            pass
    return ""

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    
    # Check all pointers inside p_player up to 0x400
    for off in range(0, 0x400, 4):
        ptr = reader.read_u32(p_player + off)
        if ptr and ptr > 0x10000:
            # Check if ptr directly points to string
            s = read_str_ptr(ptr)
            if s and any(c.lower() in s.lower() for c in ["destroy", "vanq", "alch", "player", "warrior"]):
                print(f"CPlayer +0x{off:03X} -> 0x{ptr:08X}: {s}")
            # Also check if ptr is an object that has strings at +0x00..+0x40
            for inner_off in range(0, 0x40, 4):
                inner_ptr = reader.read_u32(ptr + inner_off)
                if inner_ptr and inner_ptr > 0x10000:
                    inner_s = read_str_ptr(inner_ptr)
                    if inner_s and any(c.lower() in inner_s.lower() for c in ["destroy", "vanq", "alch", "player", "warrior"]):
                        print(f"CPlayer +0x{off:03X} -> ptr+0x{inner_off:02X} (0x{inner_ptr:08X}): {inner_s}")

reader.close()
