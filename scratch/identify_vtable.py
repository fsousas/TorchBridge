import struct
from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

def get_class_name_for_vtable(vtable_va):
    # In MSVC 32-bit:
    # vtable[-1] (i.e. at vtable_va - 4) is pointer to RTTICompleteObjectLocator (COL)
    # COL:
    #   +0x00: signature (0)
    #   +0x04: offset
    #   +0x08: cdOffset
    #   +0x0C: pTypeDescriptor (VA)
    #   +0x10: pClassDescriptor (VA)
    # TypeDescriptor:
    #   +0x00: pVFTable
    #   +0x04: spare
    #   +0x08: name (.?AVClassName@@)
    
    # Image base is 0x00400000 for GOG
    image_base = 0x00400000
    vtable_file_offset = vtable_va - image_base # only if in .rdata/.data
    
    # We can search directly in data for the vtable address or search COL
    # Let's search data for pointer to COL
    col_ptr_pos = -1
    for i in range(0, len(data) - 4, 4):
        # find where vtable points to
        pass
    
    # Simpler: convert VA to file offset using PE sections
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

    raw_vt = va_to_off(vtable_va)
    if not raw_vt:
        return f"Cannot map vtable VA 0x{vtable_va:08X}"
    
    col_va = struct.unpack_from("<I", data, raw_vt - 4)[0]
    raw_col = va_to_off(col_va)
    if not raw_col:
        return f"Cannot map COL VA 0x{col_va:08X}"
    
    type_desc_va = struct.unpack_from("<I", data, raw_col + 12)[0]
    raw_td = va_to_off(type_desc_va)
    if not raw_td:
        return f"Cannot map TypeDesc VA 0x{type_desc_va:08X}"
    
    name_bytes = data[raw_td + 8: raw_td + 100].split(b"\x00")[0]
    return name_bytes.decode("latin1")

# Test with vtables we saw:
# CPlayer: 0x00AA8F24
# CStatsMenu: 0x00AB87C4
# CSkillMenu: 0x00AB8508
for vt in [0x00AA8F24, 0x00AB87C4, 0x00AB8508]:
    print(f"vtable 0x{vt:08X} -> {get_class_name_for_vtable(vt)}")
