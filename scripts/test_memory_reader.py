"""Leitor de memória direto e seguro para o Torchlight 1 (x86 32-bit).
Mapeia a cadeia exata: CGame -> CGameClient -> CGameUI -> Menus
Monitora em tempo real a tela do jogo, overlays de configurações e menus abertos.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
import struct
import sys
import time

PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002

kernel32 = ctypes.windll.kernel32

ADDR_CGAME_GLOBAL = 0x00C1AD64   # Ponteiro global estático em .data para CGame
OFFSET_GAMECLIENT = 0x64         # CGame -> CGameClient*
OFFSET_GAMEUI     = 0x3C         # CGameClient -> CGameUI*
OFFSET_MENU_MGR   = 0x0324       # CGameUI -> CMenuManager*
OFFSET_MAIN_STATE = 0x0D84       # CMenuManager -> Estado dos menus da tela inicial (0..5: título, 6: em jogo)

# Mapeamento dos estados principais da tela inicial (0x005643AC)
MAIN_MENU_STATES = {
    0: "Tela Inicial (Menu Principal)",
    1: "Criar Personagem (New Character)",
    2: "Criar Personagem (Modo Hardcore)",
    3: "Carregar Personagem (Load Character / Continue)",
    4: "Carregar Personagem (Detalhes)",
    6: "Em Jogo (Gameplay - Cidade / Dungeon)",
}

# Offsets dos menus dentro de CGameUI e seus bytes de isOpen
GAMEPLAY_MENUS = {
    "Inventário":       (0x02CC, 0x30),
    "Atributos":        (0x02D0, 0x44),
    "Pet":              (0x02D4, 0x34),
    "Vendedor (Loja)":  (0x02D8, 0x30),
    "Encantador":       (0x02DC, 0x30),
    "Baú":              (0x02E4, 0x30),
    "Habilidades":      (0x030C, 0x1C),
}

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]

def find_torchlight_pid() -> int | None:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return None
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if kernel32.Process32First(snap, ctypes.byref(pe)):
            while True:
                name = pe.szExeFile.decode("latin1", errors="ignore").lower()
                if name == "torchlight.exe":
                    return pe.th32ProcessID
                if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return None

class ProcessMemory:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
        if not self.handle:
            err = kernel32.GetLastError()
            raise RuntimeError(f"Falha ao abrir processo {pid}: Erro Win32 {err}")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def read_u32(self, address: int) -> int | None:
        buf = ctypes.create_string_buffer(4)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, 4, ctypes.byref(read)):
            if read.value == 4:
                return struct.unpack("<I", buf.raw)[0]
        return None

    def read_u8(self, address: int) -> int | None:
        buf = ctypes.create_string_buffer(1)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, 1, ctypes.byref(read)):
            if read.value == 1:
                return buf.raw[0]
        return None

def inspect_game(mem: ProcessMemory) -> None:
    p_game = mem.read_u32(ADDR_CGAME_GLOBAL)
    if not p_game:
        print("[0x00C1AD64] CGame ainda não instanciado.")
        return

    p_client = mem.read_u32(p_game + OFFSET_GAMECLIENT)
    if not p_client:
        print(f"CGame: 0x{p_game:08X} | CGameClient não inicializado.")
        return

    p_game_ui = mem.read_u32(p_client + OFFSET_GAMEUI)
    if not p_game_ui:
        print(f"CGameClient: 0x{p_client:08X} | CGameUI não inicializado.")
        return

    # Checa overlays (Settings e Modal de confirmação)
    p_settings = mem.read_u32(p_game_ui + 0x02EC)
    is_settings_open = (mem.read_u8(p_settings + 0x18) == 1) if p_settings else False

    p_modal = mem.read_u32(p_game_ui + 0x0304)
    is_modal_open = (mem.read_u8(p_modal + 0x18) == 1) if p_modal else False

    p_menu_mgr = mem.read_u32(p_game_ui + OFFSET_MENU_MGR)
    main_state_id = mem.read_u32(p_menu_mgr + OFFSET_MAIN_STATE) if p_menu_mgr else 6
    state_desc = MAIN_MENU_STATES.get(main_state_id, f"Estado {main_state_id}")

    # Exibição do estado
    if is_settings_open:
        print("ESTADO DO JOGO : Configurações (Settings) [Overlay Ativo]")
        print("-" * 60)
        print("-> Tela Atual: MENU DE CONFIGURAÇÕES (SETTINGS)")
        print("   Overlay de opções aberto sobre a tela.")
        print("   MODO RECOMENDADO: [MOUSE / CURSOR]")
        return

    if is_modal_open:
        print("ESTADO DO JOGO : Janela de Confirmação (Sair do Jogo) [Modal Ativo]")
        print("-" * 60)
        print("-> Tela Atual: CONFIRMAÇÃO / SAIR (QUIT GAME)")
        print("   MODO RECOMENDADO: [MOUSE / CURSOR]")
        return

    print(f"ESTADO DO JOGO : {state_desc} [código {main_state_id}]")
    print("-" * 60)

    if main_state_id != 6:
        # Está em alguma das telas iniciais/título
        print(f"-> Tela Atual: {state_desc.upper()}")
        print("   Menus de gameplay inativos.")
        print("   MODO RECOMENDADO: [MOUSE / CURSOR]")
        return

    # Está dentro do jogo (gameplay ativo)!
    print("STATUS DOS MENUS DE GAMEPLAY:")
    any_open = False
    for menu_name, (ui_offset, open_offset) in GAMEPLAY_MENUS.items():
        p_menu = mem.read_u32(p_game_ui + ui_offset)
        if not p_menu:
            print(f"  {menu_name:<18}: Não instanciado")
            continue

        is_open = mem.read_u8(p_menu + open_offset)
        status = "ABERTO" if (is_open == 1) else "fechado"
        if is_open == 1:
            any_open = True
        print(f"  {menu_name:<18}: {status:<8} (ptr: 0x{p_menu:08X})")

    # Opções / Pause em jogo
    p_options = mem.read_u32(p_game_ui + 0x02E8)
    if p_options:
        is_paused = (mem.read_u8(p_options + 0x18) == 1)
        if is_paused:
            any_open = True
            print(f"  {'Pause / Opções':<18}: ABERTO")

    print("-" * 60)
    print(f"MODO DE CONTROLE RECOMENDADO: {'[MOUSE / MENU]' if any_open else '[DIRETO / JOGO]'}")

def main():
    parser = argparse.ArgumentParser(description="Leitor de memória do Torchlight")
    parser.add_argument("--once", action="store_true", help="Executa apenas uma vez e sai")
    args = parser.parse_args()

    mem = None
    current_pid = None
    try:
        while True:
            pid = find_torchlight_pid()
            if not pid:
                if mem:
                    mem.close()
                    mem = None
                    current_pid = None
                os.system("cls" if os.name == "nt" else "clear")
                print("Aguardando o executável do Torchlight abrir...")
                if args.once:
                    return
                time.sleep(1.0)
                continue

            if pid != current_pid or mem is None:
                if mem:
                    mem.close()
                try:
                    mem = ProcessMemory(pid)
                    current_pid = pid
                except RuntimeError:
                    time.sleep(0.5)
                    continue

            os.system("cls" if os.name == "nt" else "clear")
            print(f"Torchlight (PID {pid}) — MONITOR EM TEMPO REAL  [Ctrl+C para parar]\n")
            inspect_game(mem)

            if args.once:
                break
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado pelo usuário.")
    finally:
        if mem:
            mem.close()

if __name__ == "__main__":
    main()
