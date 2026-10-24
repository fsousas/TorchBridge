import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader

head_ptr = 0x10C4D028
root_ptr = safe_u32(head_ptr + 0x04)

def decode_utf32_str(addr: int, max_len: int = 48) -> str:
    chars = []
    for i in range(max_len):
        val = safe_u32(addr + i * 4)
        if 32 <= val < 127:
            chars.append(chr(val))
        elif val == 0:
            break
        else:
            break
    return "".join(chars)

visited = set()
nodes = [root_ptr]
windows = []

while nodes:
    curr = nodes.pop()
    if not curr or curr in visited or curr == head_ptr:
        continue
    visited.add(curr)
    
    left = safe_u32(curr + 0x00)
    parent = safe_u32(curr + 0x04)
    right = safe_u32(curr + 0x08)
    
    # Nome da janela
    w_name = decode_utf32_str(curr + 0x20, 32)
    w_ptr = safe_u32(curr + 0xA4)
    if w_ptr and safe_u32(w_ptr) == 0x01BB0D1C:
        windows.append((w_name, w_ptr))
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

print(f"Total de nós visitados: {len(visited)}")
print(f"Total de janelas CEGUI no jogo: {len(windows)}")

# Filtra janelas relevantes
keywords = ["flyout", "grid", "slot", "popup", "action", "quick", "select", "shortcut", "menu", "hud"]
matching = []
for name, ptr in windows:
    nl = name.lower()
    if any(k in nl for k in keywords):
        matching.append((name, ptr))

print(f"Janelas filtradas: {len(matching)}")
for name, ptr in matching:
    # Checa visibilidade: em CEGUI::Window, d_visible geralmente é um byte.
    # Vamos ler o byte de visibilidade (testando offsets comuns como 0x80, 0x84, 0x90, 0xA0, 0x1A0)
    b = read_bytes(ptr, 512)
    print(f"  '{name}' -> 0x{ptr:08X}")

