"""Analisa RTTI, vtables e referências no executável do Torchlight 1 (x86 32-bit).
Funciona de forma puramente estática no arquivo .exe (não toca na memória do sistema).
"""
from __future__ import annotations

import struct
from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")

def main():
    if not EXE_PATH.exists():
        print(f"Executável não encontrado em: {EXE_PATH}")
        return

    data = EXE_PATH.read_bytes()
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
    opt_header_offset = pe_offset + 24
    image_base = struct.unpack_from("<I", data, opt_header_offset + 28)[0]
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

    def va_to_offset(va: int) -> int | None:
        for s in sections:
            if s["va_start"] <= va < s["va_end"]:
                rel = va - s["va_start"]
                if rel < (s["raw_end"] - s["raw_start"]):
                    return s["raw_start"] + rel
        return None

    def offset_to_va(off: int) -> int | None:
        for s in sections:
            if s["raw_start"] <= off < s["raw_end"]:
                return s["va_start"] + (off - s["raw_start"])
        return None

    print(f"Executável: {EXE_PATH.name} | ImageBase: 0x{image_base:08X}")
    for s in sections:
        print(f"  {s['name']:<8}: VA 0x{s['va_start']:08X}-0x{s['va_end']:08X} (raw 0x{s['raw_start']:08X}-0x{s['raw_end']:08X})")

    # Classes essenciais para menus e UI
    target_classes = [
        "CGame",
        "CGameStateController",
        "CMenuManager",
        "CGameUI",
        "CMainMenu",
        "CContinueGameMenu",
        "CNewGameMenu",
        "CInventoryMenu",
        "CMerchantMenu",
        "CPetMenu",
        "CStashMenu",
        "CSkillMenu",
        "CStatsMenu",
        "CJournalMenu",
        "CQuestDialogMenu",
        "CDialogMenu",
        "CDieMenu",
        "CFishingMenu",
        "CEnchantMenu",
        "CWaypointMenu",
        "COptionsMenu",
        "CModalMenu"
    ]

    vtables: dict[str, int] = {}

    for cls_name in target_classes:
        needle = f".?AV{cls_name}@@".encode("latin1")
        p = 0
        while True:
            idx = data.find(needle, p)
            if idx == -1:
                break
            type_desc_offset = idx - 8
            type_desc_va = offset_to_va(type_desc_offset)
            if type_desc_va is None:
                p = idx + 1
                continue

            td_bytes = struct.pack("<I", type_desc_va)
            
            # Localizar CompleteObjectLocator (COL) que aponta para este TypeDescriptor
            # Em 32-bit MSVC: COL possui pTypeDescriptor no offset +12
            col_search_pos = 0
            while True:
                col_ref = data.find(td_bytes, col_search_pos)
                if col_ref == -1:
                    break
                col_offset = col_ref - 12
                col_va = offset_to_va(col_offset)
                if col_va is not None:
                    col_bytes = struct.pack("<I", col_va)
                    # Procurar vtable que aponta para o COL (col_va fica em vtable[-4])
                    vt_ref = data.find(col_bytes)
                    if vt_ref != -1:
                        vtable_offset = vt_ref + 4
                        vtable_va = offset_to_va(vtable_offset)
                        if vtable_va is not None:
                            vtables[cls_name] = vtable_va
                            break
                col_search_pos = col_ref + 1
            p = idx + 1

    print(f"\n{len(vtables)} VTABLES ENCONTRADAS (Endereços virtuais fixos em memória):")
    print(f"{'Classe':<24} | {'Vtable VA':<12}")
    print("-" * 40)
    for name, va in sorted(vtables.items()):
        print(f"{name:<24} | 0x{va:08X}")

    # Agora vamos analisar CMenuManager e CGameUI
    print("\nAnalisando referências e métodos de CMenuManager e CGameUI:")
    for cls_name in ["CMenuManager", "CGameUI"]:
        vt_va = vtables.get(cls_name)
        if not vt_va:
            continue
        vt_bytes = struct.pack("<I", vt_va)
        pos = 0
        while True:
            idx = data.find(vt_bytes, pos)
            if idx == -1:
                break
            code_va = offset_to_va(idx)
            print(f"  [{cls_name}] Vtable atribuída no offset raw 0x{idx:08X} (VA 0x{code_va:08X})")
            pos = idx + 1
            
    # Mapear todos os ponteiros de menus em CGameUI (offsets a partir de CGameUI)
    # A função CGameUI::InitMenus (em VA 0x00562D80) cria e armazena os menus
    print("\n" + "="*50)
    print("MAPEAMENTO DOS PONTEIROS DE MENUS EM CGameUI:")
    print("="*50)
    
    # Inverter mapa de vtables para lookup por endereço
    vt_to_name = {va: name for name, va in vtables.items()}
    
    # Escaneia CGameUI::InitMenus (raw 0x00162100 até 0x00162C00)
    for r in range(0x00162100, 0x00162C00 - 6):
        if data[r:r+2] == b"\x89\x86": # mov [esi + disp32], eax
            disp = struct.unpack_from("<I", data, r + 2)[0]
            code_va = offset_to_va(r)
            
            # Procurar chamada anterior para ver qual classe foi instanciada
            menu_class = "Desconhecido"
            for back in range(r - 30, r):
                if data[back] == 0xE8:
                    rel = struct.unpack_from("<i", data, back + 1)[0]
                    call_va = offset_to_va(back)
                    dest_va = (call_va + 5 + rel) & 0xFFFFFFFF
                    dest_raw = va_to_offset(dest_va)
                    if dest_raw:
                        # Busca vtables escritas nos primeiros 300 bytes do construtor
                        for cr in range(dest_raw, dest_raw + 300):
                            if data[cr] == 0xC7:
                                cand_vt = struct.unpack_from("<I", data, cr + 2)[0]
                                if cand_vt in vt_to_name:
                                    menu_class = vt_to_name[cand_vt]
                                    break
            print(f"  CGameUI + 0x{disp:04X} -> {menu_class:<22} (registrado em VA 0x{code_va:08X})")

if __name__ == "__main__":
    main()
