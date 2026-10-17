"""Monitor sonoro e de terminal em tempo real para testar hover em Portais, Portas, Baús, NPCs e Monstros.
Roda continuamente até você apertar Ctrl+C no terminal.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time
import winsound

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    OFFSET_GAMECLIENT,
    OFFSET_GAMEUI,
    TorchlightMemoryReader,
)

reader = TorchlightMemoryReader()
mem = reader.update()
if not reader.pid:
    print("[ERRO] Torchlight.exe não encontrado em execução!")
    print("Certifique-se de que o jogo está aberto com o personagem carregado.")
    sys.exit(1)

p_game = reader.read_u32(ADDR_CGAME_GLOBAL)
p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)

print("=" * 70)
print(f"🔍 MONITOR DE HOVER AO VIVO (Conectado ao Torchlight PID {reader.pid})")
print("=" * 70)
print("Instruções:")
print(" - Aponte o mouse para qualquer coisa: Kolos, Baú, Portal, Inimigo, Chão...")
print(" - O terminal vai imprimir em tempo real quando detectar o alvo!")
print(" - Pressione [Ctrl + C] para encerrar quando quiser.")
print("=" * 70 + "\n")

last_is_hover = None

try:
    while True:
        ptr = reader.read_u32(p_client + 0x1BC)
        flag = reader.read_u32(p_client + 0x1C0)
        ui_type = reader.read_u32(p_ui + 0x28)

        is_hover = bool(ptr and ptr > 0x00400000)

        if is_hover != last_is_hover:
            if is_hover:
                desc = "NPC" if flag == 2 else ("Baú/Item" if flag == 1 else f"Objeto (flag={flag})")
                print(f"🟢 [HOVER ATIVO!]   Tipo: {desc:10s} | Objeto: 0x{ptr:08X} | Flag: {flag} | UIType: {ui_type}")
                try:
                    winsound.Beep(1400, 60)
                except Exception:
                    pass
            else:
                print(f"⚪ [CHÃO LIMPO]     (Nenhum objeto sob o mouse)")
                try:
                    winsound.Beep(800, 50)
                except Exception:
                    pass
            last_is_hover = is_hover

        time.sleep(0.04)
except KeyboardInterrupt:
    print("\n[Encerrado pelo usuário]")
