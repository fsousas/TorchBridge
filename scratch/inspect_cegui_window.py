import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
import struct
from src.torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
reader._ensure_handle()

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

def read_std_string(addr: int) -> str:
    # No MSVC STL (x86 32-bit):
    # struct std::string {
    #   union { char _Buf[16]; char* _Ptr; } _Bx;
    #   size_t _Mysize;
    #   size_t _Myres;
    # }; (tamanho total 24 ou 28 ou 32 bytes)
    # Se _Myres < 16, string inline em _Bx. Se >= 16, ponteiro em _Bx._Ptr.
    raw = read_bytes(addr, 24)
    if len(raw) < 24:
        return ""
    mysize = struct.unpack("<I", raw[16:20])[0]
    myres = struct.unpack("<I", raw[20:24])[0]
    if 0 < mysize < 256:
        if myres < 16:
            return raw[:mysize].decode("latin1", errors="ignore")
        else:
            ptr = struct.unpack("<I", raw[:4])[0]
            s_bytes = read_bytes(ptr, mysize)
            return s_bytes.decode("latin1", errors="ignore")
    return ""

# Teste com uma das janelas de 0x02B8
window_candidates = [
    0x18CF6BA0, 0x18CF4C38, 0x18CF5280, 0x18CF5F10,
    0x18CF45F0, 0x18CF71E8, 0x18CF3960, 0x18CFB0B8
]

for w in window_candidates:
    print(f"\n--- Inspecionando CEGUI::Window em 0x{w:08X} ---")
    data = read_bytes(w, 256)
    # Procura strings std::string nos primeiros 128 bytes
    found_strings = []
    for off in range(0, 160, 4):
        s = read_std_string(w + off)
        if s and len(s) >= 3 and s.isprintable():
            found_strings.append((f"+0x{off:02X}", s))
    for off, s in found_strings:
        print(f"  {off}: '{s}'")

