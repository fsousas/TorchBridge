import struct
import capstone
from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()
image_base = 0x00400000

pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
opt_header_offset = pe_offset + 24
size_of_opt = struct.unpack_from("<H", data, pe_offset + 20)[0]
sec_table_offset = opt_header_offset + size_of_opt

sections = []
for i in range(num_sections):
    o = sec_table_offset + i * 40
    name = data[o:o+8].rstrip(b"\x00").decode("latin1")
    vsize, vaddr, raw_size, raw_offset = struct.unpack_from("<IIII", data, o + 8)
    sections.append({
        "name": name,
        "va_start": image_base + vaddr,
        "va_end": image_base + vaddr + vsize,
        "raw_start": raw_offset,
        "raw_end": raw_offset + raw_size
    })

def va_to_off(va):
    for s in sections:
        if s["va_start"] <= va < s["va_end"]:
            return s["raw_start"] + (va - s["va_start"])
    return None

def off_to_va(off):
    for s in sections:
        if s["raw_start"] <= off < s["raw_end"]:
            return s["va_start"] + (off - s["raw_start"])
    return None

# Find references to CStatsMenu vtable (0x00AB87C4)
vt_bytes = struct.pack("<I", 0x00AB87C4)
p = 0
print("=== References to CStatsMenu vtable ===")
while True:
    idx = data.find(vt_bytes, p)
    if idx == -1:
        break
    va = off_to_va(idx)
    print(f"Found vtable ref at VA 0x{va:08X} (offset 0x{idx:08X})")
    p = idx + 1

# Find references to CSkillMenu vtable (0x00AB8508)
vt_bytes = struct.pack("<I", 0x00AB8508)
p = 0
print("\n=== References to CSkillMenu vtable ===")
while True:
    idx = data.find(vt_bytes, p)
    if idx == -1:
        break
    va = off_to_va(idx)
    print(f"Found vtable ref at VA 0x{va:08X} (offset 0x{idx:08X})")
    p = idx + 1
