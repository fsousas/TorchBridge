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
    print("ERRO: Torchlight não encontrado.")
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

# Acessa CEGUI WindowManager
head_ptr = 0x10C4D028
root_ptr = safe_u32(head_ptr + 0x04)

visited = set()
nodes = [root_ptr]
target_ptr = None

while nodes:
    curr = nodes.pop()
    if not curr or curr in visited or curr == head_ptr:
        continue
    visited.add(curr)
    
    left = safe_u32(curr + 0x00)
    right = safe_u32(curr + 0x08)
    
    w_name = decode_utf32_str(curr + 0x20, 24)
    if w_name == "gui__3501Base":
        target_ptr = safe_u32(curr + 0xA4)
        break
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

print(f"Janela gui__3501Base: {hex(target_ptr) if target_ptr else 'Não encontrada'}")
if target_ptr:
    raw = read_bytes(target_ptr, 384)
    top = struct.unpack("<f", raw[0x12C:0x130])[0]
    left = struct.unpack("<f", raw[0x134:0x138])[0]
    bottom = struct.unpack("<f", raw[0x13C:0x140])[0]
    right = struct.unpack("<f", raw[0x144:0x148])[0]
    h = struct.unpack("<f", raw[0x148:0x14C])[0]
    w = struct.unpack("<f", raw[0x14C:0x150])[0]
    print(f"=== Dimensões Reais da Janela do Grid Agora ===")
    print(f"  left={left:.2f}, top={top:.2f}, right={right:.2f}, bottom={bottom:.2f}")
    print(f"  largura={w:.2f}, altura={h:.2f}")
    cols = round((w - 10.4) / 65.1)
    rows = round((h - 10.4) / 65.1)
    print(f"  -> COLUNAS: {cols}")
    print(f"  -> LINHAS:  {rows}")

