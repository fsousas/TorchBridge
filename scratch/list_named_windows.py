import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
import re
from src.torchbridge.memory import TorchlightMemoryReader, kernel32
import ctypes

reader = TorchlightMemoryReader()
reader._ensure_handle()

def safe_u32(addr: int) -> int:
    v = reader.read_u32(addr)
    return v if v is not None else 0

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

head_ptr = 0x10C4D028
root_ptr = safe_u32(head_ptr + 0x04)

visited = set()
nodes = [root_ptr]
windows = []

while nodes:
    curr = nodes.pop()
    if not curr or curr in visited or curr == head_ptr:
        continue
    visited.add(curr)
    
    left = safe_u32(curr + 0x00)
    right = safe_u32(curr + 0x08)
    
    w_name = decode_utf32_str(curr + 0x20, 32)
    w_ptr = safe_u32(curr + 0xA4)
    if w_ptr and safe_u32(w_ptr) == 0x01BB0D1C:
        windows.append((w_name, w_ptr))
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

non_slot = []
prefixes = set()

for name, ptr in windows:
    m = re.match(r"^(\d+)_(.*)$", name)
    if m:
        prefixes.add(m.group(1))
        item = m.group(2)
        if not re.match(r"^Slot\d+$", item):
            non_slot.append((name, ptr))
    else:
        non_slot.append((name, ptr))

print(f"Prefixos encontrados: {sorted(list(prefixes), key=lambda x: int(x))}")
print(f"Janelas descritivas ({len(non_slot)}):")
for name, ptr in sorted(non_slot, key=lambda x: x[0]):
    print(f"  '{name}' -> 0x{ptr:08X}")

