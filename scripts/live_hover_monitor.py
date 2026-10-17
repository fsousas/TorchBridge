"""Monitor em tempo real de 15 segundos para inspecionar CGameUI, CGameClient e CPlayer.
Basta mover o mouse sobre o chão, depois sobre a Syl / baú / monstro!
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
    OFFSET_GAMEUI,
    OFFSET_PLAYER,
    TorchlightMemoryReader,
)

reader = TorchlightMemoryReader()
mem = reader.update()
if not reader.pid:
    print("[ERRO] Torchlight não encontrado!")
    sys.exit(1)

p_game = reader.read_u32(ADDR_CGAME_GLOBAL)
p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
p_player = reader.read_u32(p_client + OFFSET_PLAYER)

print(f"Monitor iniciado! (PID {reader.pid})")
print(f"CGame: 0x{p_game:08X} | CClient: 0x{p_client:08X} | CUI: 0x{p_ui:08X} | CPlayer: 0x{p_player:08X}")
print("Mova o mouse entre o chão e a Syl / Baú pelos próximos 10 segundos...")

prev_ui = [reader.read_u32(p_ui + i) for i in range(0, 0x1000, 4)]
prev_client = [reader.read_u32(p_client + i) for i in range(0, 0x500, 4)]
prev_player = [reader.read_u32(p_player + i) for i in range(0, 0x500, 4)] if p_player else []

start_t = time.monotonic()
changes_found = 0

while time.monotonic() - start_t < 10.0:
    time.sleep(0.1)
    curr_ui = [reader.read_u32(p_ui + i) for i in range(0, 0x1000, 4)]
    curr_client = [reader.read_u32(p_client + i) for i in range(0, 0x500, 4)]
    curr_player = [reader.read_u32(p_player + i) for i in range(0, 0x500, 4)] if p_player else []

    # Checa CGameUI
    for idx in range(len(curr_ui)):
        if curr_ui[idx] != prev_ui[idx]:
            off = idx * 4
            v_old = prev_ui[idx]
            v_new = curr_ui[idx]
            # ignora contadores triviais se houver
            print(f"[CGameUI +0x{off:03X}]: 0x{v_old:08X} -> 0x{v_new:08X}")
            changes_found += 1
            prev_ui[idx] = v_new

    # Checa CGameClient
    for idx in range(len(curr_client)):
        if curr_client[idx] != prev_client[idx]:
            off = idx * 4
            v_old = prev_client[idx]
            v_new = curr_client[idx]
            if off != 0x224:  # ignora o tick counter 0x224
                print(f"[CGameClient +0x{off:03X}]: 0x{v_old:08X} -> 0x{v_new:08X}")
                changes_found += 1
            prev_client[idx] = v_new

    # Checa CPlayer
    for idx in range(len(curr_player)):
        if curr_player[idx] != prev_player[idx]:
            off = idx * 4
            v_old = prev_player[idx]
            v_new = curr_player[idx]
            # ignora coords do herói idle (0x1a0, 0x214-0x220) se o herói respirar
            if off not in (0x1A0, 0x214, 0x218, 0x21C, 0x220, 0x2C8):
                print(f"[CPlayer +0x{off:03X}]: 0x{v_old:08X} -> 0x{v_new:08X}")
                changes_found += 1
            prev_player[idx] = v_new

print(f"\nFinalizado! Total de eventos detectados: {changes_found}")
