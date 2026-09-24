"""Leitor e scanner de vtables e instâncias de menus na memória do Torchlight.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import struct
import sys

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

class ProcessMemory:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.handle:
            err = kernel32.GetLastError()
            raise RuntimeError(f"Falha ao abrir processo {pid}: Erro Win32 {err}")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def read_bytes(self, address: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read)):
            return b""
        return buf.raw[:bytes_read.value]

    def read_u32(self, address: int) -> int | None:
        raw = self.read_bytes(address, 4)
        if len(raw) == 4:
            return struct.unpack("<I", raw)[0]
        return None

def find_torchlight_pid() -> int | None:
    hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
    if hdesk:
        user32.SetThreadDesktop(hdesk)

    target_pid = None
    def cb(hwnd, _):
        nonlocal target_pid
        if user32.IsWindowVisible(hwnd):
            len_t = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(len_t + 1)
            user32.GetWindowTextW(hwnd, buf, len_t + 1)
            if buf.value == "Torchlight":
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                target_pid = pid.value
                return False
        return True

    cb_func = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb)
    user32.EnumWindows(cb_func, 0)
    return target_pid

# Query virtual memory regions
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
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40

def get_memory_regions(mem: ProcessMemory):
    regions = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while addr < 0x7FFF0000:
        if not kernel32.VirtualQueryEx(mem.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        state = mbi.State
        protect = mbi.Protect
        if state == MEM_COMMIT and (protect & (PAGE_READONLY | PAGE_READWRITE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE)):
            regions.append((base, size, protect))
        addr = base + size
    return regions

def main():
    pid = find_torchlight_pid()
    if not pid:
        print("Torchlight não encontrado.")
        return

    print(f"Torchlight conectado (PID {pid})!")
    mem = ProcessMemory(pid)
    try:
        # Lê a imagem inteira do executável: 0x00400000 até 0x01000000 (12 MB)
        base_addr = 0x00400000
        image_size = 0x00C00000 # 12MB
        exe_mem = mem.read_bytes(base_addr, image_size)
        print(f"Lidos {len(exe_mem):,} bytes da imagem do executável em RAM.")

        classes_to_find = [
            "CMainMenu",
            "CContinueGameMenu",
            "CNewGameMenu",
            "CInventoryMenu",
            "CMerchantMenu",
            "CGameUI",
            "CGameStateController",
            "CMenuManager"
        ]

        vtables = {}
        for cls_name in classes_to_find:
            needle = f".?AV{cls_name}@@".encode("latin1")
            idx = exe_mem.find(needle)
            if idx == -1:
                continue
            type_desc_va = base_addr + (idx - 8)
            td_bytes = struct.pack("<I", type_desc_va)
            
            # Procura referências ao TypeDescriptor no executável
            pos = 0
            while True:
                ref = exe_mem.find(td_bytes, pos)
                if ref == -1:
                    break
                col_va = base_addr + (ref - 12)
                col_bytes = struct.pack("<I", col_va)
                
                # Procura a vtable que aponta para o CompleteObjectLocator
                ref2 = exe_mem.find(col_bytes)
                if ref2 != -1:
                    vtable_va = base_addr + ref2 + 4
                    vtables[cls_name] = vtable_va
                    break
                pos = ref + 1

        print("\nVtables encontradas:")
        for k, v in vtables.items():
            print(f"  {k:<22}: 0x{v:08X}")

        # Agora vamos escanear a memória dinâmica (HEAP / DATA) procurando instâncias vivas!
        regions = get_memory_regions(mem)
        print(f"\nEscaneando {len(regions)} regiões de memória ativa do jogo por instâncias ativas...")

        alive_instances = {}
        for base, size, protect in regions:
            # Pula a própria imagem do executável ao buscar instâncias
            if 0x00400000 <= base < 0x01000000:
                continue
            chunk = mem.read_bytes(base, size)
            if not chunk:
                continue
            for cls_name, vt_addr in vtables.items():
                vt_bytes = struct.pack("<I", vt_addr)
                pos = 0
                while True:
                    p = chunk.find(vt_bytes, pos)
                    if p == -1:
                        break
                    obj_addr = base + p
                    alive_instances.setdefault(cls_name, []).append(obj_addr)
                    pos = p + 4

        print("\nINSTANCIAS ATIVAS NO MOMENTO:")
        for cls_name, addrs in alive_instances.items():
            print(f"  * {cls_name}: {len(addrs)} instancia(s) encontrada(s) -> {[f'0x{a:08X}' for a in addrs]}")

        if not alive_instances:
            print("  Nenhuma instancia de menu encontrada na heap no momento.")

    finally:
        mem.close()

if __name__ == "__main__":
    main()
