import sys
import io
import struct
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
reader.update()

def read_str(addr, max_len=64):
    if not addr or not reader._handle:
        return ""
    import ctypes
    buf = ctypes.create_string_buffer(max_len)
    read = ctypes.c_size_t()
    if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, max_len, ctypes.byref(read)):
        raw = buf.raw[:read.value]
        # find null
        idx = raw.find(b"\x00")
        if idx != -1:
            raw = raw[:idx]
        return raw.decode("latin1", errors="ignore")
    return ""

def read_std_string(addr):
    # MSVC std::string:
    # +0x00: union { char buf[16]; char* ptr; }
    # +0x10: size (u32)
    # +0x14: capacity (u32)
    size = reader.read_u32(addr + 16)
    cap = reader.read_u32(addr + 20)
    if size is None or cap is None or size > 1000 or cap > 1000:
        return ""
    if cap < 16:
        return read_str(addr, size)
    else:
        ptr = reader.read_u32(addr)
        return read_str(ptr, size)

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    print(f"p_player: 0x{p_player:08X}")
    
    # Let's search strings inside p_player up to 0x1000
    for off in range(0, 0x1000, 4):
        s = read_std_string(p_player + off)
        if s and len(s) >= 3 and any(c.isalpha() for c in s):
            print(f"p_player +0x{off:03X}: std::string = '{s}'")
        
        # Also check if it's a pointer to an ascii string
        ptr = reader.read_u32(p_player + off)
        if ptr and ptr > 0x400000:
            s_ptr = read_str(ptr, 32)
            if s_ptr and len(s_ptr) >= 3 and s_ptr.isprintable() and any(c.isalpha() for c in s_ptr):
                # filter out obvious garbage
                if all(32 <= ord(c) < 127 for c in s_ptr[:8]):
                    print(f"p_player +0x{off:03X} (ptr 0x{ptr:08X}): c_str = '{s_ptr}'")

reader.close()
