import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

def inspect_cegui_win(addr, name):
    print(f"\n--- {name} (0x{addr:08X}) ---")
    # In CEGUI::Window:
    # d_name is often at +0x6C or +0x70 or similar (CEGUI::String)
    for off in range(0, 0xA0, 4):
        val = reader.read_u32(addr + off)
        # try wstring
        ws = reader.read_wstring(val, 32) if val and val > 0x10000 else ""
        # try reading string directly
        direct_s = ""
        import ctypes
        buf = ctypes.create_string_buffer(32)
        read = ctypes.c_size_t()
        if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr + off), buf, 32, ctypes.byref(read)):
            raw = buf.raw[:read.value].split(b"\x00")[0]
            try:
                s = raw.decode("latin1")
                if len(s) >= 3 and all(32 <= ord(c) < 127 for c in s):
                    direct_s = s
            except Exception:
                pass
        if ws or direct_s:
            print(f"  +0x{off:02X}: 0x{val:08X} ws='{ws}' direct='{direct_s}'")

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_skill = reader.read_u32(p_ui + 0x030C)
    
    inspect_cegui_win(reader.read_u32(p_skill + 0x0C), "Tab 0 (+0x0C)")
    inspect_cegui_win(reader.read_u32(p_skill + 0x10), "Tab 1 (+0x10)")
    inspect_cegui_win(reader.read_u32(p_skill + 0x14), "Tab 2 (+0x14)")

reader.close()
