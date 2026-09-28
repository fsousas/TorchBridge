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

# Search functions around 0x00488000 to 0x00489000 (CPlayer member functions)
start_va = 0x00488000
end_va = 0x00489000
raw_start = va_to_off(start_va)
raw_end = va_to_off(end_va)
code = data[raw_start:raw_end]

print("=== Instructions in CPlayer getters/setters ===")
for insn in md.disasm(code, start_va):
    if any(k in insn.op_str for k in ["+ 0x3", "+ 0x2", "+ 0x1"]):
        print(f"0x{insn.address:08X}: {insn.mnemonic:8s} {insn.op_str}")

