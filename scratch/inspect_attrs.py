import sys
import io
import struct
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_stats = reader.read_u32(p_ui + 0x02D0)
    
    attr_names = ["Strength", "Dexterity", "Magic", "Defense"]
    offsets = [0x60, 0xF8, 0x190, 0x228]
    
    for name, base_off in zip(attr_names, offsets):
        print(f"\n--- {name} (base 0x{base_off:03X}) ---")
        for off in range(0, 0x98, 4):
            val = reader.read_u32(p_stats + base_off + off)
            if val is not None and val != 0:
                print(f"  +0x{off:02X} (abs 0x{base_off+off:03X}): 0x{val:08X} ({val})")

reader.close()
