import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_skill = reader.read_u32(p_ui + 0x030C)
    
    print(f"CSkillMenu: 0x{p_skill:08X}")
    # Search for pointers to CSkill or CEGUI windows
    # Let's inspect fields
    for off in range(0x100, 0x400, 4):
        val = reader.read_u32(p_skill + off)
        if val and val > 0x10000:
            # check if val has vtable
            vt = reader.read_u32(val)
            if vt and 0x400000 <= vt <= 0x3000000:
                print(f"  +0x{off:03X}: 0x{val:08X} (vt 0x{vt:08X})")

reader.close()
