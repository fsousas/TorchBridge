import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    p_skill_menu = reader.read_u32(p_ui + 0x030C)
    p_skill_mgr = reader.read_u32(p_player + 0x184)
    
    # Check skills in CSkillManager
    vec_skills = reader.read_u32(p_skill_mgr + 0x3C)
    num_skills = reader.read_u32(p_skill_mgr + 0x40)
    
    skill_map = {}
    for i in range(num_skills):
        p_sk = reader.read_u32(vec_skills + i * 4)
        if p_sk:
            # Check GUID in CSkill (where is 64-bit GUID in CSkill? e.g. +0x10, +0x18, +0x20, etc.)
            guid_lo = reader.read_u32(p_sk + 0x1C)
            guid_hi = reader.read_u32(p_sk + 0x20)
            rank = reader.read_u32(p_sk + 0xA4)
            # Find GUID offsets in CSkill
            for g_off in range(0x04, 0x40, 4):
                glo = reader.read_u32(p_sk + g_off)
                ghi = reader.read_u32(p_sk + g_off + 4)
                if glo == 0x9E3311DE or ghi == 0x9E3311DE:
                    print(f"CSkill [{i:2d}] has GUID at +0x{g_off:02X}: 0x{glo:08X} 0x{ghi:08X}, rank={rank}")
                    break

reader.close()
