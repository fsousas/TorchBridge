import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
import ctypes
from src.torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
if not reader._ensure_handle():
    print("ERRO")
    sys.exit(1)

def safe_u32(addr: int) -> int:
    v = reader.read_u32(addr)
    return v if v is not None else 0

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

def decode_utf32_str(addr: int, max_len: int = 32) -> str:
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
icons = {}

while nodes:
    curr = nodes.pop()
    if not curr or curr in visited or curr == head_ptr:
        continue
    visited.add(curr)
    
    left = safe_u32(curr + 0x00)
    right = safe_u32(curr + 0x08)
    
    w_name = decode_utf32_str(curr + 0x20, 24)
    if "SkillIcon" in w_name and "gui__3501" in w_name:
        w_ptr = safe_u32(curr + 0xA4)
        icons[w_name] = w_ptr
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

print(f"Total SkillIcons encontrados: {len(icons)}")

# Vamos checar as 5 linhas e suas colunas
for r in range(1, 7):
    row_icons = []
    for c in range(1, 9):
        name = f"gui__3501SkillIcon{r}{c}"
        ptr = icons.get(name)
        if ptr:
            raw = read_bytes(ptr, 384)
            top = struct.unpack("<f", raw[0x12C:0x130])[0]
            left = struct.unpack("<f", raw[0x134:0x138])[0]
            w = struct.unpack("<f", raw[0x14C:0x150])[0]
            h = struct.unpack("<f", raw[0x148:0x14C])[0]
            if w > 10 and h > 10 and 0 <= left < 330 and 0 <= top < 330:
                row_icons.append(f"C{c}(x={left:.0f},y={top:.0f})")
    print(f"Linha {r}: {len(row_icons)} itens -> {row_icons}")

