import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader

p_win_mgr = 0x10C59530
print(f"CEGUI::WindowManager = 0x{p_win_mgr:08X}")

# Inspeciona os membros de CEGUI::WindowManager
# Em geral, offset 0x4 ou 0x8 é o root do std::map d_windowRegistry
raw = read_bytes(p_win_mgr, 64)
for off in range(0, len(raw), 4):
    val = struct.unpack("<I", raw[off:off+4])[0]
    print(f"  +0x{off:02X}: 0x{val:08X}")

# Vamos testar o std::map em +0x04 ou +0x08 ou +0x0C
# No MSVC STL std::map:
# _Myhead (ponteiro para nó sentinela)
# _Mysize (número de nós)

