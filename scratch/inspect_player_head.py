import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
state = reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT) if p_game else None
    p_player = reader.read_u32(p_client + OFFSET_PLAYER) if p_client else None
    print(f"p_player: 0x{p_player:08X}")
    
    # Read vtable of CPlayer
    vtable = reader.read_u32(p_player)
    print(f"CPlayer vtable: 0x{vtable:08X}")

    for off in range(0, 0x200, 4):
        val = reader.read_u32(p_player + off)
        if val is not None:
            # Try float
            import struct
            flt_val = struct.unpack("<f", struct.pack("<I", val))[0]
            flt_str = f"{flt_val:.2f}" if -100000 < flt_val < 100000 and abs(flt_val) > 0.001 else ""
            print(f"+0x{off:03X} ({off:3d}): 0x{val:08X} ({val:10d})  flt={flt_str}")

reader.close()
