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

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

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
skill_icons = {}

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
        if "SkillIcon" in w_name or "SkillHotkey" in w_name or "gui__350" in w_name:
            skill_icons[w_name] = w_ptr
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

print(f"Total de componentes do Grid encontrados: {len(skill_icons)}")

# Vamos inspecionar as janelas SkillIcon
# Em CEGUI::Window, vamos procurar:
# 1. d_visible (onde fica o bool isVisible?)
# 2. d_pixelRect ou área absoluta / relativa
# Vamos pegar a janela SkillIcon11 e inspecionar seus bytes
w11 = skill_icons.get("gui__3501SkillIcon11")
w12 = skill_icons.get("gui__3501SkillIcon12")
w21 = skill_icons.get("gui__3501SkillIcon21")

print(f"SkillIcon11 ptr: {hex(w11) if w11 else 'None'}")
print(f"SkillIcon12 ptr: {hex(w12) if w12 else 'None'}")
print(f"SkillIcon21 ptr: {hex(w21) if w21 else 'None'}")

if w11:
    raw11 = read_bytes(w11, 256)
    raw12 = read_bytes(w12, 256)
    # Diferenças entre 11 e 12 nos indicam os offsets de X/Y/Col/Row!
    diffs = []
    for off in range(0, 256, 4):
        u11 = struct.unpack("<I", raw11[off:off+4])[0]
        u12 = struct.unpack("<I", raw12[off:off+4])[0]
        f11 = struct.unpack("<f", raw11[off:off+4])[0]
        f12 = struct.unpack("<f", raw12[off:off+4])[0]
        if u11 != u12:
            diffs.append((f"+0x{off:02X}", u11, u12, f11, f12))
    print(f"Diferenças entre SkillIcon11 e SkillIcon12 ({len(diffs)}):")
    for d in diffs:
        print(f"  {d[0]}: u11=0x{d[1]:08X} u12=0x{d[2]:08X} | f11={d[3]:.2f} f12={d[4]:.2f}")

