import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

def read_cegui_name(p_win):
    if not p_win:
        return ""
    # In CEGUI::Window, d_name is a String at +0x6C or +0x70
    # Let's search inside p_win for ASCII name
    import ctypes
    buf = ctypes.create_string_buffer(64)
    read = ctypes.c_size_t()
    for off in (0x6C, 0x70, 0x68, 0x64):
        # try direct
        if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(p_win + off), buf, 32, ctypes.byref(read)):
            raw = buf.raw[:read.value].split(b"\x00")[0]
            try:
                s = raw.decode("latin1")
                if len(s) >= 2 and all(32 <= ord(c) < 127 for c in s):
                    return s
            except Exception:
                pass
        # try pointer
        ptr = reader.read_u32(p_win + off)
        if ptr and ptr > 0x10000:
            if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(ptr), buf, 32, ctypes.byref(read)):
                raw = buf.raw[:read.value].split(b"\x00")[0]
                try:
                    s = raw.decode("latin1")
                    if len(s) >= 2 and all(32 <= ord(c) < 127 for c in s):
                        return s
                except Exception:
                    pass
    return ""

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_skill_menu = reader.read_u32(p_ui + 0x030C)
    
    # Check tabs (+0x0C, +0x10, +0x14)
    for i, tab_off in enumerate([0x0C, 0x10, 0x14]):
        p_tab = reader.read_u32(p_skill_menu + tab_off)
        name = read_cegui_name(p_tab)
        # Check child windows of p_tab:
        # In CEGUI::Window, children vector is at +0x58 (d_children: vector<Window*>)
        vec_children = reader.read_u32(p_tab + 0x58)
        num_children = reader.read_u32(p_tab + 0x5C)
        # Or let's check size
        print(f"Tab {i} (0x{p_tab:08X}): name='{name}'")
        for ch_off in (0x54, 0x58, 0x60, 0x80):
            val = reader.read_u32(p_tab + ch_off)
            print(f"   off 0x{ch_off:02X}: 0x{val:08X} ({val})")

reader.close()
