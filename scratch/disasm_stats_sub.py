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

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

def disasm_range(start_va, count=80):
    off = va_to_off(start_va)
    code = data[off : off + count * 5]
    for i in md.disasm(code, start_va):
        print(f"0x{i.address:08X}: {i.mnemonic:8s} {i.op_str}")
        count -= 1
        if count <= 0:
            break

print("=== Disassembly of 0x005B0BF0 ===")
disasm_range(0x005B0BF0, 80)
