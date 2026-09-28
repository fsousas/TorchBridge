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
    
    # Player level & skill points
    player_level = reader.read_u32(p_player + 0xF0) or 1
    skill_points = reader.read_u32(p_player + 0x3E0) or 0
    attr_points = reader.read_u32(p_player + 0x3DC) or 0
    p_cls = reader.read_u32(p_player + 0x34)
    char_class = reader.read_wstring(p_cls).strip().lower() if p_cls else ""
    
    print(f"Player Level: {player_level}")
    print(f"Char Class:   {char_class}")
    print(f"Attr Points:  {attr_points}")
    print(f"Skill Points: {skill_points}")
    
    # Read guid_to_rank from CSkillManager
    vec_skills = reader.read_u32(p_skill_mgr + 0x3C)
    num_skills = reader.read_u32(p_skill_mgr + 0x40) or 0
    guid_to_rank = {}
    for i in range(num_skills):
        p_sk = reader.read_u32(vec_skills + i * 4)
        if p_sk:
            glo = reader.read_u32(p_sk + 0x180)
            ghi = reader.read_u32(p_sk + 0x184)
            rank = reader.read_u32(p_sk + 0xA4) or 0
            if glo and ghi:
                guid_to_rank[(glo, ghi)] = rank
                
    # Read slots from CSkillMenu +0x80
    TIER_BASE_LEVEL = [1, 5, 10, 15, 20, 25]
    print("\nSkill slots in CSkillMenu:")
    for slot_idx in range(20):
        glo = reader.read_u32(p_skill_menu + 0x80 + slot_idx * 8)
        ghi = reader.read_u32(p_skill_menu + 0x84 + slot_idx * 8)
        if (glo, ghi) in guid_to_rank:
            rank = guid_to_rank[(glo, ghi)]
            # Check upgradeable
            # For test: assume tier based on slot index or base level
            # If skill_points > 0:
            print(f"  Slot {slot_idx:2d}: GUID=(0x{glo:08X}, 0x{ghi:08X}) | Current Rank = {rank}")

reader.close()
