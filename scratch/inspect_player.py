import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
state = reader.update()
print(f"Connected: {state.is_connected}, PID: {state.pid}, Version: {state.game_version}")
print(f"State: {state.state_desc} (id={state.state_id}), In Game: {state.is_in_game}")
print(f"Open menus: {state.open_menus}")

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT) if p_game else None
    p_player = reader.read_u32(p_client + OFFSET_PLAYER) if p_client else None
    print(f"p_game: 0x{p_game:08X}" if p_game else "p_game: None")
    print(f"p_client: 0x{p_client:08X}" if p_client else "p_client: None")
    print(f"p_player: 0x{p_player:08X}" if p_player else "p_player: None")

    if p_player:
        words = []
        for offset in range(0, 0x600, 4):
            val = reader.read_u32(p_player + offset)
            words.append((offset, val))
        
        print("\nNon-zero words in CPlayer (first 0x600 bytes):")
        for offset, val in words:
            if val is not None and val != 0:
                print(f"  +0x{offset:03X} ({offset:3d}): 0x{val:08X} ({val})")
reader.close()
