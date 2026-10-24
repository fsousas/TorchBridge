import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader, p_player, p_ui

print(f"p_player = 0x{p_player:08X}")
p_skill_mgr = safe_u32(p_player + 0x184)
print(f"p_skill_mgr (player + 0x184) = 0x{p_skill_mgr:08X}")

if p_skill_mgr:
    vec_skills = safe_u32(p_skill_mgr + 0x3C)
    num_skills = safe_u32(p_skill_mgr + 0x40) or 0
    print(f"vec_skills = 0x{vec_skills:08X}, num_skills = {num_skills}")
    
    for i in range(num_skills):
        p_sk = safe_u32(vec_skills + i * 4)
        if p_sk:
            rank = safe_u32(p_sk + 0xA4)
            # Lê nome do skill (wstring ou string nos membros)
            name = ""
            for name_off in (0x8, 0xC, 0x10, 0x14, 0x18, 0x24, 0x28, 0x2C, 0x30, 0x48, 0x98, 0xB4):
                ptr_name = safe_u32(p_sk + name_off)
                if ptr_name:
                    ws = reader.read_wstring(ptr_name)
                    if ws and len(ws) > 2:
                        name = f"[+0x{name_off:02X}:{ws}]"
                        break
            # Vamos ler mais offsets de p_sk para descobrir passive/active e level requirement
            raw_sk = read_bytes(p_sk, 160)
            u32s = [struct.unpack("<I", raw_sk[j:j+4])[0] for j in range(0, min(len(raw_sk), 64), 4)]
            print(f"Skill #{i:02d} (0x{p_sk:08X}): rank={rank} {name} u32s={u32s[:8]}")

