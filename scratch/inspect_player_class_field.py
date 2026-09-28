import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    
    print(f"p_player: 0x{p_player:08X}")
    for off in range(0x20, 0x60, 4):
        val = reader.read_u32(p_player + off)
        ws = reader.read_wstring(val) if val and val > 0x10000 else ""
        print(f"  +0x{off:02X}: 0x{val:08X} ({val}) ws='{ws}'")

reader.close()
