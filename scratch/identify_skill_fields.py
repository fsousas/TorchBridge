import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_GAMEUI
import identify_vtable as iv

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_skill = reader.read_u32(p_ui + 0x030C)
    
    for off in [0x0C, 0x10, 0x14, 0x34, 0x38, 0x7C, 0x6D4]:
        ptr = reader.read_u32(p_skill + off)
        if ptr:
            vt = reader.read_u32(ptr)
            cls = iv.get_class_name_for_vtable(vt) if vt else "None"
            print(f"CSkillMenu +0x{off:02X} (0x{ptr:08X}): {cls}")

reader.close()
