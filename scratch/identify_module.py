import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
from ctypes import wintypes
from src.torchbridge.memory import TorchlightMemoryReader, kernel32, psapi, MODULEENTRY32, TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32

reader = TorchlightMemoryReader()
reader._ensure_handle()

target_addr = 0x01BB0D1C

snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, reader.pid)
if snap not in (None, 0, -1, ctypes.c_void_p(-1).value):
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        if kernel32.Module32First(snap, ctypes.byref(me)):
            while True:
                base = int(me.modBaseAddr)
                size = int(me.modBaseSize)
                name = me.szModule.decode("latin1", errors="ignore")
                if base <= target_addr < base + size:
                    print(f"Endereço 0x{target_addr:08X} PERTENCE A: {name} (Base 0x{base:08X}, Size 0x{size:08X})")
                if not kernel32.Module32Next(snap, ctypes.byref(me)):
                    break
    finally:
        kernel32.CloseHandle(snap)

