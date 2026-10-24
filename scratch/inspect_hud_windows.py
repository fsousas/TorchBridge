import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader

# Vamos ler os ponteiros dentro de 0x02B8
p_02b8 = 0x159F4498
raw_02b8 = read_bytes(p_02b8, 256)

ptrs = []
for off in range(0x2C, 0x100, 4):
    p = safe_u32(p_02b8 + off)
    if p and p > 0x10000:
        vt = safe_u32(p)
        ptrs.append((off, p, vt))

print(f"Total de ponteiros em 0x02B8: {len(ptrs)}")

for off, p, vt in ptrs:
    raw = read_bytes(p, 256)
    # Procura floats válidos de coordenadas de tela (ex: 0 a 1920)
    floats = []
    for f_off in range(0, len(raw) - 4, 4):
        val = struct.unpack("<f", raw[f_off:f_off+4])[0]
        # Se for um float razoável de coordenada de tela (ex: 10.0 a 1600.0) ou dimensão (ex: 20.0 a 600.0)
        if 1.0 <= val <= 2000.0 and abs(val - round(val)) < 0.1:
            floats.append((f"+0x{f_off:02X}", round(val, 1)))
        elif 0.001 <= val <= 1.0:
            floats.append((f"+0x{f_off:02X}", round(val, 3)))
    
    # Procura ponteiros para strings de texto
    strs = []
    for s_off in range(0, len(raw) - 4, 4):
        s_ptr = struct.unpack("<I", raw[s_off:s_off+4])[0]
        if 0x00400000 <= s_ptr <= 0x7FFFFFFF:
            b_cand = read_bytes(s_ptr, 32)
            null_idx = b_cand.find(b"\x00")
            if null_idx > 2:
                cand = b_cand[:null_idx].decode("latin1", errors="ignore")
                if cand.isprintable() and len(cand) >= 3:
                    strs.append(f"[+0x{s_off:02X}:{cand}]")
    
    print(f"0x02B8 + 0x{off:02X} -> 0x{p:08X} (vt: 0x{vt:08X}) | strs={strs[:3]} | floats={floats[:6]}")

