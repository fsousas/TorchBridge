import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader, p_player

print(f"p_player = 0x{p_player:08X}")

# No Torchlight, itens/equipamentos/inventário estão em CPlayer:
# Vamos escanear offsets em p_player procurando ponteiros para containers (std::vector com tamanho > 0 e < 100)
for off in range(0, 0x600, 4):
    p1 = safe_u32(p_player + off)
    p2 = safe_u32(p_player + off + 4)
    p3 = safe_u32(p_player + off + 8)
    # Padrão std::vector: _Myfirst, _Mylast, _Myend
    # Se p1 < p2 <= p3 e (p2 - p1) % 4 == 0:
    if p1 and p2 and p3 and 0x10000000 <= p1 <= 0x7FFFFFFF:
        if p1 < p2 <= p3 and (p2 - p1) % 4 == 0:
            count = (p2 - p1) // 4
            if 1 <= count <= 120:
                # Checa o primeiro elemento
                first_elem = safe_u32(p1)
                vt_first = safe_u32(first_elem) if first_elem > 0x10000 else 0
                print(f"p_player + 0x{off:04X} -> std::vector count={count} first=0x{first_elem:08X} (vt=0x{vt_first:08X})")

