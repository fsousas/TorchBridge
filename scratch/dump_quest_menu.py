import sys, ctypes
from ctypes import wintypes
sys.path.insert(0, r"c:\Users\kleve\Documents\Projetos\TorchBridge\src")
from torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
reader.update()
h_proc = reader._handle

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02

target_needle = "Ember of Another Color".encode("utf-16le")
matches = []

addr = 0x00400000
mbi = MEMORY_BASIC_INFORMATION()
while addr < 0x30000000:
    if not kernel32.VirtualQueryEx(h_proc, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    base = mbi.BaseAddress or addr
    size = mbi.RegionSize
    if mbi.State == MEM_COMMIT and (mbi.Protect & 0xF0 == 0) and mbi.Protect != 0x01: # not PAGE_NOACCESS
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(h_proc, ctypes.c_void_p(base), buf, size, ctypes.byref(read)):
            raw = buf.raw[:read.value]
            idx = 0
            while True:
                found = raw.find(target_needle, idx)
                if found == -1:
                    break
                match_va = base + found
                matches.append(match_va)
                print(f"Found needle at VA: 0x{match_va:08X}")
                idx = found + len(target_needle)
                if len(matches) >= 5:
                    break
    addr = base + size
    if len(matches) >= 5:
        break

print(f"Total string matches: {len(matches)}")
# Para cada match, procura ponteiros para match_va na memória
for m_va in matches:
    m_bytes = m_va.to_bytes(4, "little")
    # Procura referências no heap
    addr = 0x00400000
    while addr < 0x30000000:
        if not kernel32.VirtualQueryEx(h_proc, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.BaseAddress or addr
        size = mbi.RegionSize
        if mbi.State == MEM_COMMIT and (mbi.Protect & 0xF0 == 0) and mbi.Protect != 0x01:
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t()
            if kernel32.ReadProcessMemory(h_proc, ctypes.c_void_p(base), buf, size, ctypes.byref(read)):
                raw = buf.raw[:read.value]
                idx = 0
                while True:
                    found = raw.find(m_bytes, idx)
                    if found == -1:
                        break
                    ref_va = base + found
                    print(f"  Reference to 0x{m_va:08X} at 0x{ref_va:08X}")
                    # Inspeciona o objeto ao redor de ref_va
                    # Se for struct CQuest*, ref_va = obj + 0xB4 ou similar
                    cand_obj = ref_va - 0xB4
                    vt = reader.read_u32(cand_obj)
                    cand_obj2 = ref_va - 0x98
                    vt2 = reader.read_u32(cand_obj2)
                    print(f"    cand_obj (ref-0xB4): 0x{cand_obj:08X} (vt=0x{vt:08X if vt else 0:08X})")
                    print(f"    cand_obj (ref-0x98): 0x{cand_obj2:08X} (vt=0x{vt2:08X if vt2 else 0:08X})")
                    idx = found + 4
        addr = base + size
