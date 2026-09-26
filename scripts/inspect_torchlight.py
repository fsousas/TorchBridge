"""Script de inspeção para o executável do Torchlight 1.
Analisa seções de memória, endereços base e procura assinaturas de GameState e UI.
"""
from __future__ import annotations

import os
import re
import struct
from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")

def inspect_pe() -> None:
    if not EXE_PATH.exists():
        print(f"Executável não encontrado em: {EXE_PATH}")
        return

    data = EXE_PATH.read_bytes()
    print(f"Tamanho do executável: {len(data):,} bytes")

    # Checa cabeçalho DOS (MZ)
    if data[:2] != b"MZ":
        print("Não é um executável PE válido (sem assinatura MZ).")
        return

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    pe_sig = data[pe_offset:pe_offset+4]
    if pe_sig != b"PE\x00\x00":
        print("Assinatura PE inválida.")
        return

    machine, num_sections = struct.unpack_from("<HH", data, pe_offset + 4)
    print(f"Arquitetura: {'x86 (32-bit)' if machine == 0x14C else f'0x{machine:X}'}")
    print(f"Número de seções: {num_sections}")

    opt_header_offset = pe_offset + 24
    magic = struct.unpack_from("<H", data, opt_header_offset)[0]
    is_32bit = magic == 0x10B
    print(f"Cabeçalho opcional: {'PE32' if is_32bit else 'PE32+'}")

    image_base = struct.unpack_from("<I", data, opt_header_offset + 28)[0]
    print(f"ImageBase preferencial: 0x{image_base:08X}")

    dll_char = struct.unpack_from("<H", data, opt_header_offset + 70)[0]
    has_aslr = bool(dll_char & 0x0040)
    print(f"ASLR (Dynamic Base): {'Sim' if has_aslr else 'Não (Endereços fixos na memória!)'}")

    # Lista de seções
    section_table_offset = opt_header_offset + (96 + 16 * 8 if is_32bit else 112 + 16 * 8)
    # A standard optional header size can be obtained from SizeOfOptionalHeader
    size_of_opt = struct.unpack_from("<H", data, pe_offset + 20)[0]
    section_table_offset = opt_header_offset + size_of_opt

    sections = []
    print("\nSeções do PE:")
    for i in range(num_sections):
        sec_offset = section_table_offset + i * 40
        sec_name = data[sec_offset:sec_offset+8].rstrip(b"\x00").decode("latin1", errors="ignore")
        vsize, vaddr, raw_size, raw_offset = struct.unpack_from("<IIII", data, sec_offset + 8)
        sections.append((sec_name, vaddr, vsize, raw_offset, raw_size))
        print(f"  {sec_name:<8}: RVA 0x{vaddr:08X} - 0x{vaddr+vsize:08X} (Tamanho: {vsize:,} bytes)")

    # Busca por strings relevantes relacionadas a telas/estados
    keywords = [
        b"CGame",
        b"GameState",
        b"MainMenu",
        b"TitleState",
        b"CharSelect",
        b"CPlayer",
        b"CInventory",
        b"CGUIManager",
        b"QuitGame",
        b"Continue",
        b"NewGame",
    ]
    
    print("\nBuscando padrões de strings de interface e estados:")
    for kw in keywords:
        matches = [m.start() for m in re.finditer(re.escape(kw), data)]
        print(f"  String '{kw.decode()}': encontrada {len(matches)} vezes no arquivo")

if __name__ == "__main__":
    inspect_pe()
