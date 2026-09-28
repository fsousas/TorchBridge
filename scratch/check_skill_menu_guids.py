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
    p_skill_menu = reader.read_u32(p_ui + 0x030C)
    
    print("Reading GUIDs at CSkillMenu +0x80..0x160:")
    for off in range(0x80, 0x160, 8):
        glo = reader.read_u32(p_skill_menu + off)
        ghi = reader.read_u32(p_skill_menu + off + 4)
        if glo or ghi:
            print(f"  +0x{off:03X}: (0x{glo:08X}, 0x{ghi:08X})")

reader.close()
