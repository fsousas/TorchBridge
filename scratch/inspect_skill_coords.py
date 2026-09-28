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
    p_skill_mgr = reader.read_u32(p_player + 0x184)
    
    vec_skills = reader.read_u32(p_skill_mgr + 0x3C)
    num_skills = reader.read_u32(p_skill_mgr + 0x40)
    
    print(f"Total skills in CSkillManager: {num_skills}")
    for i in range(num_skills):
        p_sk = reader.read_u32(vec_skills + i * 4)
        if not p_sk:
            continue
        rank = reader.read_u32(p_sk + 0xA4)
        base_lvl = reader.read_u32(p_sk + 0xA0)
        # Check ints in p_sk that look like row (0..5 or 1..6) and col (0..2 or 1..3) and pane (0..2 or 1..3)
        candidates = []
        for off in range(0x80, 0x140, 4):
            val = reader.read_u32(p_sk + off)
            if val is not None and 0 <= val <= 10:
                candidates.append((f"+0x{off:02X}", val))
        print(f"Skill [{i:2d}] at 0x{p_sk:08X}: rank={rank}, base_lvl={base_lvl}, small_ints: {candidates[:8]}")

reader.close()
