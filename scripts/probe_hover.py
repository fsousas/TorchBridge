"""Sonda interativa de memória acionada pela tecla [ESPAÇO] globalmente.
Você coloca o mouse onde quiser com toda a calma e só aperta a barra de ESPAÇO para capturar!
"""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import time
import winsound
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
VK_SPACE = 0x20

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from torchbridge.memory import (
    ADDR_CGAME_GLOBAL,
    OFFSET_GAMECLIENT,
    OFFSET_GAMEUI,
    OFFSET_PLAYER,
    TorchlightMemoryReader,
)


def sample_offsets(reader: TorchlightMemoryReader, base: int, size: int) -> dict[int, int]:
    res: dict[int, int] = {}
    for off in range(0, size, 4):
        val = reader.read_u32(base + off)
        if val is not None:
            res[off] = val
    return res


def is_space_pressed() -> bool:
    return bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)


class SpaceBanner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("Container")
        box_layout = QVBoxLayout(self.container)
        box_layout.setContentsMargins(24, 12, 24, 12)

        self.step_label = QLabel("PASSO 1 DE 3", self)
        self.step_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.step_label.setStyleSheet("color: #00F0FF;")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.step_label)

        self.instruction_label = QLabel("Deixe o mouse no CHÃO LIMPO e aperte [ESPAÇO]", self)
        self.instruction_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.instruction_label.setStyleSheet("color: #FFFFFF;")
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.instruction_label)

        self.action_label = QLabel("Aperte [ESPAÇO] no teclado quando estiver pronto", self)
        self.action_label.setFont(QFont("Segoe UI", 13))
        self.action_label.setStyleSheet("color: #FFE600;")
        self.action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.action_label)

        layout.addWidget(self.container)
        self.resize(780, 130)

        self.set_style("#00F0FF")

        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.left() + (geom.width() - self.width()) // 2
            y = geom.top() + 45
            self.move(x, y)

    def set_style(self, border_color: str):
        self.container.setStyleSheet(f"""
            QWidget#Container {{
                background-color: rgba(10, 16, 26, 245);
                border: 3px solid {border_color};
                border-radius: 14px;
            }}
        """)

    def set_content(self, step: str, instruction: str, hint: str, border="#00F0FF", hint_color="#FFE600"):
        self.step_label.setText(step)
        self.instruction_label.setText(instruction)
        self.action_label.setText(hint)
        self.action_label.setStyleSheet(f"color: {hint_color};")
        self.set_style(border)
        self.update()


def run_probe_gui():
    app = QApplication.instance() or QApplication(sys.argv[:1])

    reader = TorchlightMemoryReader()
    mem_state = reader.update()
    if not mem_state.is_connected or not reader.pid:
        print("[ERRO] Torchlight.exe não encontrado em execução!")
        return 1

    cgame_addr = reader._resolve_cgame_address() or ADDR_CGAME_GLOBAL
    p_game = reader.read_u32(cgame_addr)
    if not p_game:
        print("[ERRO] CGame não inicializado.")
        return 1
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    if not p_client:
        print("[ERRO] CGameClient não inicializado.")
        return 1

    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)

    print(f"[OK] Conectado ao Torchlight (PID {reader.pid})")
    print(f"  CGame:       0x{p_game:08X}")
    print(f"  CGameClient: 0x{p_client:08X}")
    print(f"  CPlayer:     0x{p_player:08X}" if p_player else "  CPlayer:     (null)")
    print(f"  CGameUI:     0x{p_ui:08X}" if p_ui else "  CGameUI:     (null)")

    banner = SpaceBanner()
    banner.show()

    g_client: dict[int, int] = {}
    g_player: dict[int, int] = {}
    g_ui: dict[int, int] = {}

    h_client: dict[int, int] = {}
    h_player: dict[int, int] = {}
    h_ui: dict[int, int] = {}

    c_client: dict[int, int] = {}
    c_player: dict[int, int] = {}
    c_ui: dict[int, int] = {}

    state = {"phase": 1, "last_space": True}

    timer = QTimer()

    def check_input():
        space_down = is_space_pressed()
        rising_edge = space_down and not state["last_space"]
        state["last_space"] = space_down

        phase = state["phase"]

        if phase == 1:
            banner.set_content(
                "PASSO 1 DE 3: CHÃO LIMPO",
                "Mantenha o mouse no CHÃO LIMPO",
                "Pressione a tecla [ESPAÇO] para gravar",
                border="#00F0FF",
                hint_color="#FFE600"
            )
            if rising_edge:
                try:
                    winsound.Beep(1400, 120)
                except Exception:
                    pass
                banner.set_content("PASSO 1: GRAVADO!", "Chão capturado com sucesso!", "Carregando...", border="#00FF66", hint_color="#00FF66")
                app.processEvents()
                nonlocal g_client, g_player, g_ui
                g_client = sample_offsets(reader, p_client, 0x1000)
                if p_player:
                    g_player = sample_offsets(reader, p_player, 0x1000)
                if p_ui:
                    g_ui = sample_offsets(reader, p_ui, 0x1800)

                state["phase"] = 2
                time.sleep(0.3)
                state["last_space"] = True
                return

        elif phase == 2:
            banner.set_content(
                "PASSO 2 DE 3: OBJETO INTERATIVO",
                "Mire em um NPC, BAÚ, PORTA ou PORTAL",
                "Pressione [ESPAÇO] com o mouse sobre o objeto",
                border="#FF9900",
                hint_color="#FF9900"
            )
            if rising_edge:
                try:
                    winsound.Beep(1600, 150)
                except Exception:
                    pass
                banner.set_content("PASSO 2: GRAVADO!", "Objeto capturado com sucesso!", "Carregando...", border="#00FF66", hint_color="#00FF66")
                app.processEvents()
                nonlocal h_client, h_player, h_ui
                h_client = sample_offsets(reader, p_client, 0x1000)
                if p_player:
                    h_player = sample_offsets(reader, p_player, 0x1000)
                if p_ui:
                    h_ui = sample_offsets(reader, p_ui, 0x1800)

                state["phase"] = 3
                time.sleep(0.3)
                state["last_space"] = True
                return

        elif phase == 3:
            banner.set_content(
                "PASSO 3 DE 3: VOLTE AO CHÃO",
                "Volte o mouse para o CHÃO LIMPO",
                "Pressione [ESPAÇO] para concluir o teste",
                border="#00F0FF",
                hint_color="#FFE600"
            )
            if rising_edge:
                try:
                    winsound.Beep(1800, 200)
                except Exception:
                    pass
                banner.set_content("CONCLUÍDO!", "Analisando dados da memória...", "Aguarde...", border="#00FF66", hint_color="#00FF66")
                app.processEvents()
                nonlocal c_client, c_player, c_ui
                c_client = sample_offsets(reader, p_client, 0x1000)
                if p_player:
                    c_player = sample_offsets(reader, p_player, 0x1000)
                if p_ui:
                    c_ui = sample_offsets(reader, p_ui, 0x1800)

                timer.stop()
                time.sleep(0.6)
                banner.close()
                app.quit()
                return

    timer.timeout.connect(check_input)
    timer.start(50)  # Checa a cada 50ms para resposta instantânea ao ESPAÇO

    app.exec()

    print("\n" + "=" * 70)
    print("RESULTADOS DA ANÁLISE DE HOVER / ALVO")
    print("=" * 70)

    output_lines = []

    def check_diffs(struct_name, base_addr, g_map, h_map, c_map):
        matches = []
        for off, g_val in g_map.items():
            h_val = h_map.get(off)
            c_val = c_map.get(off)
            if h_val is not None and c_val is not None and g_val != h_val:
                is_perfect = (g_val == 0 and h_val > 0x00400000 and c_val == 0)
                is_ptr = (h_val > 0x00400000)
                returned = (c_val == g_val)
                score = (3 if is_perfect else (2 if (is_ptr and returned) else (1 if is_ptr else 0)))
                matches.append((score, off, g_val, h_val, c_val))

        matches.sort(key=lambda x: (-x[0], x[1]))
        if matches:
            header = f"\n🎯 {struct_name} (Base 0x{base_addr:08X}) - {len(matches)} diferenças detectadas:"
            print(header)
            output_lines.append(header)
            for score, off, g_val, h_val, c_val in matches[:25]:
                if score == 3:
                    star = "⭐⭐⭐ [ALVO PERFEITO 0->PTR->0]"
                elif score == 2:
                    star = "⭐⭐  [Ponteiro que retornou]   "
                elif score == 1:
                    star = "⭐   [Ponteiro novo]           "
                else:
                    star = "     [Valor alterado]          "
                line = f" {star} +0x{off:03X} ({off:4d}): Chão=0x{g_val:08X} -> Hover=0x{h_val:08X} -> Volta=0x{c_val:08X}"
                print(line)
                output_lines.append(line)
        else:
            header = f"\n  {struct_name}: Nenhuma diferença encontrada."
            print(header)
            output_lines.append(header)

    check_diffs("CGameClient", p_client, g_client, h_client, c_client)
    if p_player:
        check_diffs("CPlayer", p_player, g_player, h_player, c_player)
    if p_ui:
        check_diffs("CGameUI", p_ui, g_ui, h_ui, c_ui)

    print("\n" + "=" * 70)

    report_file = ROOT / "build" / "hover_probe_results.txt"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"Relatório salvo em: {report_file}")
    reader.close()
    return 0


if __name__ == "__main__":
    sys.exit(run_probe_gui() or 0)
