import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

def read_str_ptr(addr):
    if not addr or addr < 0x10000:
        return ""
    # Try wstring
    ws = reader.read_wstring(addr, 32)
    if ws and len(ws) >= 3 and ws[0].isprintable() and not ws.startswith("?"):
        return ws
    # Try ascii
    import ctypes
    buf = ctypes.create_string_buffer(32)
    read = ctypes.c_size_t()
    if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, 32, ctypes.byref(read)):
        raw = buf.raw[:read.value].split(b"\x00")[0]
        try:
            s = raw.decode("latin1")
            if len(s) >= 3 and all(32 <= ord(c) < 127 for c in s):
                return s
        except Exception:
            pass
    return ""

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_skill = reader.read_u32(p_ui + 0x030C)
    
    print(f"p_skill: 0x{p_skill:08X}")
    for off in range(0, 0x700, 4):
        val = reader.read_u32(p_skill + off)
        if val and val > 0x10000:
            s = read_str_ptr(val)
            if s:
                print(f"CSkillMenu +0x{off:03X} -> 0x{val:08X}: '{s}'")

reader.close()
