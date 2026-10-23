import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader, p_player

p_skill_mgr = safe_u32(p_player + 0x184)
vec_skills = safe_u32(p_skill_mgr + 0x3C)
num_skills = safe_u32(p_skill_mgr + 0x40) or 0

print(f"=== HABILIDADES ATIVAS ADQUIRIDAS DO JOGADOR ===")
for i in range(num_skills):
    p_sk = safe_u32(vec_skills + i * 4)
    rank = safe_u32(p_sk + 0xA4)
    if rank and rank > 0:
        # Lê membros de p_sk procurando o nome da habilidade
        # Vamos olhar p_sk + 0x14 (u32s[5]), etc.
        p_desc = safe_u32(p_sk + 0x14)
        name_str = ""
        if p_desc:
            # Tenta ler wstring ou string
            ws = reader.read_wstring(p_desc)
            if ws:
                name_str = f"ws:{ws}"
            else:
                raw = read_bytes(p_desc, 32)
                null_i = raw.find(b"\x00")
                if null_i > 1:
                    name_str = f"str:{raw[:null_i].decode('latin1', errors='ignore')}"
        
        # Também procura em outros ponteiros de p_sk
        other_names = []
        for off in range(0, 0x100, 4):
            val = safe_u32(p_sk + off)
            if val and 0x00400000 <= val <= 0x7FFFFFFF:
                ws = reader.read_wstring(val)
                if ws and len(ws) >= 3 and ws.isprintable() and not ws.startswith("<"):
                    other_names.append(f"+0x{off:02X}:{ws}")
        
        u32_7 = safe_u32(p_sk + 0x1C)
        is_passive = (safe_u32(p_sk + 0x18) == 0)
        print(f"Skill #{i:02d} (0x{p_sk:08X}): rank={rank} passive={is_passive} u32_7={u32_7} names={other_names[:3]}")

