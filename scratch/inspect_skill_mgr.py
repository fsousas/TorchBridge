import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    
    p_skills = reader.read_u32(p_player + 0x184)
    print(f"p_player: 0x{p_player:08X}")
    print(f"p_player + 0x184: 0x{p_skills:08X}" if p_skills else "p_skills: None")

    if p_skills:
        for off in range(0, 0x80, 4):
            val = reader.read_u32(p_skills + off)
            print(f"  +0x{off:02X}: 0x{val:08X} ({val})")

reader.close()
