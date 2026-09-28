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
    
    attr_pts = reader.read_u32(p_player + 0x3DC)
    print(f"p_player: 0x{p_player:08X}")
    print(f"CPlayer + 0x3DC (attr_points_remaining): {attr_pts}")
    for off in range(0x3B0, 0x410, 4):
        val = reader.read_u32(p_player + off)
        print(f"  +0x{off:03X}: {val} (0x{val:08X})")

reader.close()
