import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
from src.torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
if not reader._ensure_handle():
    print("ERRO")
    sys.exit(1)

def read_bytes(addr: int, size: int) -> bytes:
    if not reader._handle or not addr:
        return b""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)):
        return buf.raw[:read.value]
    return b""

p_menu_mgr = 0x1373AC40
raw = read_bytes(p_menu_mgr + 0x28, 2048)
text = raw.decode("utf-16le", errors="ignore")
print("=== Texto em p_menu_mgr + 0x28 ===")
print(text[:1500])

