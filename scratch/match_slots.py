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
    
    # 1. Build GUID -> (rank, name) map from CSkillManager
    vec_skills = reader.read_u32(p_skill_mgr + 0x3C)
    num_skills = reader.read_u32(p_skill_mgr + 0x40)
    guid_to_skill = {}
    for i in range(num_skills):
        p_sk = reader.read_u32(vec_skills + i * 4)
        if p_sk:
            glo = reader.read_u32(p_sk + 0x180)
            ghi = reader.read_u32(p_sk + 0x184)
            rank = reader.read_u32(p_sk + 0xA4)
            base_lvl = reader.read_u32(p_sk + 0xA0)
            guid_to_skill[(glo, ghi)] = (rank, base_lvl, p_sk)
    
    print(f"CSkillManager has {len(guid_to_skill)} skills with GUIDs:")
    for guid, (rank, base_lvl, p_sk) in list(guid_to_skill.items())[:5]:
        print(f"  GUID (0x{guid[0]:08X}, 0x{guid[1]:08X}): rank={rank}, base_lvl={base_lvl}")

    # 2. Check GUIDs in CSkillMenu +0x80 onwards
    print("\nMatching with CSkillMenu slots:")
    # Slots start at +0x80, each GUID is 8 bytes
    slot_idx = 0
    for off in range(0x80, 0x150, 8):
        glo = reader.read_u32(p_skill_menu + off)
        ghi = reader.read_u32(p_skill_menu + off + 4)
        if glo and ghi and (glo, ghi) in guid_to_skill:
            rank, base_lvl, p_sk = guid_to_skill[(glo, ghi)]
            print(f"Slot {slot_idx:2d} (off +0x{off:03X}): GUID=(0x{glo:08X}, 0x{ghi:08X}) -> rank={rank}, base_lvl={base_lvl}")
            slot_idx += 1

reader.close()
