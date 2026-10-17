"""Detector de hover específico para Portais, Escadas e Entradas de Dungeons.
Monitora CLevel e CGameClient para ver qual offset é ativado ao mirar no portal.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    OFFSET_GAMECLIENT,
    TorchlightMemoryReader,
)

reader = TorchlightMemoryReader()
reader.update()
if not reader.pid:
    print("[ERRO] Torchlight não encontrado!")
    sys.exit(1)

p_game = reader.read_u32(ADDR_CGAME_GLOBAL)
p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
p_level = reader.read_u32(p_client + 0x38)

print("=" * 70)
print(f"🌀 MONITOR DE PORTAL / ENTRADAS (PID {reader.pid})")
print("=" * 70)
print(f"CGameClient: 0x{p_client:08X} | CLevel: 0x{p_level:08X}")
print("Mova o mouse entre o CHÃO e o PORTAL / ENTRADA DA MINA nos próximos 15 segundos...")
print("=" * 70 + "\n")

prev_client = [reader.read_u32(p_client + i) for i in range(0, 0x600, 4)]
prev_level = [reader.read_u32(p_level + i) for i in range(0, 0x600, 4)]

t0 = time.monotonic()
while time.monotonic() - t0 < 15.0:
    time.sleep(0.08)
    curr_client = [reader.read_u32(p_client + i) for i in range(0, 0x600, 4)]
    curr_level = [reader.read_u32(p_level + i) for i in range(0, 0x600, 4)]

    # Ignora ruídos comuns de animação/timer
    ignored_client = {0x224}
    ignored_level = {0x54, 0x478, 0x480, 0x49C, 0x4A4, 0x4A8, 0x4B0, 0x4B4, 0x4BC, 0x4D4, 0x4DC}

    for idx in range(len(curr_client)):
        off = idx * 4
        if off not in ignored_client and curr_client[idx] != prev_client[idx]:
            v_old = prev_client[idx]
            v_new = curr_client[idx]
            print(f"[CGameClient +0x{off:03X}]: 0x{v_old:08X} -> 0x{v_new:08X}")
            prev_client[idx] = v_new

    for idx in range(len(curr_level)):
        off = idx * 4
        if off not in ignored_level and curr_level[idx] != prev_level[idx]:
            v_old = prev_level[idx]
            v_new = curr_level[idx]
            print(f"[CLevel      +0x{off:03X}]: 0x{v_old:08X} -> 0x{v_new:08X}")
            prev_level[idx] = v_new

print("\nFim do teste!")
