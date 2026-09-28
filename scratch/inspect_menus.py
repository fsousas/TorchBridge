import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
state = reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT) if p_game else None
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI) if p_client else None
    
    p_stats = reader.read_u32(p_ui + 0x02D0) if p_ui else None
    p_skill = reader.read_u32(p_ui + 0x030C) if p_ui else None
    
    print(f"p_stats (CStatsMenu): 0x{p_stats:08X}" if p_stats else "p_stats: None")
    print(f"p_skill (CSkillMenu): 0x{p_skill:08X}" if p_skill else "p_skill: None")

    if p_stats:
        print("\nCStatsMenu words:")
        for off in range(0, 0x100, 4):
            val = reader.read_u32(p_stats + off)
            if val is not None and val != 0:
                print(f"  +0x{off:03X}: 0x{val:08X} ({val})")

    if p_skill:
        print("\nCSkillMenu words:")
        for off in range(0, 0x100, 4):
            val = reader.read_u32(p_skill + off)
            if val is not None and val != 0:
                print(f"  +0x{off:03X}: 0x{val:08X} ({val})")

reader.close()
