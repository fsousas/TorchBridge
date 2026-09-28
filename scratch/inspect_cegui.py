import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

def read_cegui_text(p_win):
    if not p_win:
        return ""
    for off in (0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40, 0x44):
        p_str = reader.read_u32(p_win + off)
        if p_str and p_str > 0x10000:
            s = reader.read_wstring(p_str, 64)
            if s and len(s) > 0 and s[0].isprintable():
                return f"[off 0x{off:02X} -> 0x{p_str:08X}]: '{s}'"
        s = reader.read_wstring(p_win + off, 32)
        if s and len(s) > 1 and s[0].isprintable() and not s.startswith("?"):
            return f"[direct 0x{off:02X}]: '{s}'"
    return ""

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    
    p_stats = reader.read_u32(p_ui + 0x02D0)
    p_skill = reader.read_u32(p_ui + 0x030C)
    
    print("=== INSPECTING CStatsMenu ===")
    for off in range(0, 0x140, 4):
        val = reader.read_u32(p_stats + off)
        if val and val > 0x10000:
            txt = read_cegui_text(val)
            if txt:
                print(f"CStatsMenu +0x{off:03X} (0x{val:08X}): {txt}")

    print("\n=== INSPECTING CSkillMenu ===")
    for off in range(0, 0x200, 4):
        val = reader.read_u32(p_skill + off)
        if val and val > 0x10000:
            txt = read_cegui_text(val)
            if txt:
                print(f"CSkillMenu +0x{off:03X} (0x{val:08X}): {txt}")

reader.close()
