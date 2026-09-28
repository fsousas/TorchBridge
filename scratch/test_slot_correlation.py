import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER, OFFSET_GAMEUI
from torchbridge.models import SKILL_TREE_LAYOUTS, SKILL_TAB_NAMES

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    p_skill_menu = reader.read_u32(p_ui + 0x030C)
    p_skill_mgr = reader.read_u32(p_player + 0x184)
    
    player_level = reader.read_u32(p_player + 0xF0) or 1
    skill_points = reader.read_u32(p_player + 0x3E0) or 0
    attr_points = reader.read_u32(p_player + 0x3DC) or 0
    p_cls = reader.read_u32(p_player + 0x34)
    char_class = reader.read_wstring(p_cls).strip().lower() if p_cls else "destroyer"
    
    # Read GUID -> rank map from CSkillManager
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
                
    # Read slot GUIDs from CSkillMenu +0x80
    slot_guids = []
    for slot_idx in range(28):
        glo = reader.read_u32(p_skill_menu + 0x80 + slot_idx * 8)
        ghi = reader.read_u32(p_skill_menu + 0x84 + slot_idx * 8)
        if glo and ghi and (glo, ghi) in guid_to_rank:
            slot_guids.append((glo, ghi))
            
    print(f"Detected {len(slot_guids)} valid skill slots in CSkillMenu")
    
    # Correlate with layout
    # For Alchemist Arcane:
    layout = SKILL_TREE_LAYOUTS[char_class]["arcane"]
    tier_reqs = [1, 5, 10, 15, 20, 25]
    
    slot_idx = 0
    upgradeable = {}
    for r_idx, row in enumerate(layout):
        tier_req = tier_reqs[r_idx]
        for c_idx in row:
            if c_idx is not None:
                if slot_idx < len(slot_guids):
                    guid = slot_guids[slot_idx]
                    rank = guid_to_rank.get(guid, 0)
                else:
                    rank = 0
                req_lvl = tier_req if rank == 0 else (tier_req + rank * 2)
                can_up = (rank < 10 and player_level >= req_lvl)
                # When skill_points > 0:
                is_ready = can_up and (skill_points > 0)
                upgradeable[(r_idx, c_idx)] = is_ready
                print(f"Row {r_idx}, Col {c_idx}: rank={rank}, tier_req={tier_req}, req_lvl={req_lvl} -> can_upgrade_if_points={can_up}")
                slot_idx += 1

reader.close()
