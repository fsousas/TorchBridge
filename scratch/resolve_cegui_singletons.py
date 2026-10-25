import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from src.torchbridge.memory import TorchlightMemoryReader, kernel32, MODULEENTRY32, TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32
import ctypes

reader = TorchlightMemoryReader()
reader._ensure_handle()

# 1. Pega base de CEGUIBase.dll no Torchlight
snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, reader.pid)
cegui_base = 0
try:
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(MODULEENTRY32)
    if kernel32.Module32First(snap, ctypes.byref(me)):
        while True:
            if me.szModule.decode("latin1", errors="ignore").lower() == "ceguibase.dll":
                cegui_base = int(me.modBaseAddr)
                break
            if not kernel32.Module32Next(snap, ctypes.byref(me)):
                break
finally:
    kernel32.CloseHandle(snap)

print(f"CEGUIBase.dll base no processo: 0x{cegui_base:08X}")

# 2. Parse da EAT de CEGUIBase.dll
dll_bytes = (Path(reader._exe_path).parent / "CEGUIBase.dll").read_bytes()
pe_offset = struct.unpack("<I", dll_bytes[0x3C:0x40])[0]
optional_hdr_offset = pe_offset + 4 + 20
export_rva = struct.unpack("<I", dll_bytes[optional_hdr_offset + 96 : optional_hdr_offset + 100])[0]

# Procura a seção que contém o export_rva
num_sections = struct.unpack("<H", dll_bytes[pe_offset + 6 : pe_offset + 8])[0]
sections_offset = pe_offset + 4 + 20 + struct.unpack("<H", dll_bytes[pe_offset + 20 : pe_offset + 22])[0]

def rva_to_offset(rva):
    for i in range(num_sections):
        s_off = sections_offset + i * 40
        v_addr = struct.unpack("<I", dll_bytes[s_off + 12 : s_off + 16])[0]
        v_size = struct.unpack("<I", dll_bytes[s_off + 8 : s_off + 12])[0]
        r_ptr = struct.unpack("<I", dll_bytes[s_off + 20 : s_off + 24])[0]
        if v_addr <= rva < v_addr + v_size:
            return r_ptr + (rva - v_addr)
    return None

exp_off = rva_to_offset(export_rva)
num_functions = struct.unpack("<I", dll_bytes[exp_off + 20 : exp_off + 24])[0]
num_names = struct.unpack("<I", dll_bytes[exp_off + 24 : exp_off + 28])[0]
funcs_rva = struct.unpack("<I", dll_bytes[exp_off + 28 : exp_off + 32])[0]
names_rva = struct.unpack("<I", dll_bytes[exp_off + 32 : exp_off + 36])[0]
ordinals_rva = struct.unpack("<I", dll_bytes[exp_off + 36 : exp_off + 40])[0]

funcs_off = rva_to_offset(funcs_rva)
names_off = rva_to_offset(names_rva)
ord_off = rva_to_offset(ordinals_rva)

target_mangled = b"?getSingletonPtr@?$Singleton@VWindowManager@CEGUI@@@CEGUI@@SAPAVWindowManager@2@XZ"
target_system_mangled = b"?getSingletonPtr@?$Singleton@VSystem@CEGUI@@@CEGUI@@SAPAVSystem@2@XZ"

for i in range(num_names):
    n_rva = struct.unpack("<I", dll_bytes[names_off + i * 4 : names_off + (i + 1) * 4])[0]
    n_off = rva_to_offset(n_rva)
    null_idx = dll_bytes.find(b"\x00", n_off)
    name = dll_bytes[n_off:null_idx]
    if name in (target_mangled, target_system_mangled):
        ordinal = struct.unpack("<H", dll_bytes[ord_off + i * 2 : ord_off + (i + 1) * 2])[0]
        fn_rva = struct.unpack("<I", dll_bytes[funcs_off + ordinal * 4 : funcs_off + (ordinal + 1) * 4])[0]
        print(f"Função {name.decode('latin1')}: RVA = 0x{fn_rva:08X}")
        
        # Lê os primeiros 16 bytes do código da função na DLL / na memória
        fn_off = rva_to_offset(fn_rva)
        fn_code = dll_bytes[fn_off:fn_off + 16]
        print(f"  Opcode: {fn_code.hex()}")
        # Típico: A1 xx xx xx xx (mov eax, [ptr]) C3 (ret)
        if fn_code[0] == 0xA1:
            var_addr_rva = struct.unpack("<I", fn_code[1:5])[0]
            # No PE 32-bit, var_addr é endereço virtual (base 0x10000000 + RVA)
            image_base = struct.unpack("<I", dll_bytes[optional_hdr_offset + 28 : optional_hdr_offset + 32])[0]
            var_rva = var_addr_rva - image_base
            actual_addr = cegui_base + var_rva
            print(f"  --> Endereço da variável global ms_Singleton no processo: 0x{actual_addr:08X}")
            # Lê o valor do singleton
            val = reader.read_u32(actual_addr)
            print(f"  --> VALOR DO SINGLETON: 0x{val:08X}" if val else "  --> Singleton é None")

