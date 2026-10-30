from __future__ import annotations

import sys
from pathlib import Path

from ..mathutils import clamp
from .base import Rect, get_project_root
from .screens import char_create_pet_panel_rect, char_create_text_field_rect


# Coordenadas e layout do Teclado Virtual (Tela de Criação de Personagem - state_id == 1)
KEYBOARD_REF_WIDTH = 568.0
KEYBOARD_REF_HEIGHT = 290.0
KEYBOARD_REF_BASE_HEIGHT = 1007.0  # Altura das capturas de referência do teclado.
KEYBOARD_GRID_ROWS = 5
KEYBOARD_GRID_COLS = 13
KEYBOARD_ANCHOR_GAP_768 = 4.0  # Espaço entre o teclado e o painel/campo em 768p.
KEYBOARD_NAME_ANCHOR_GAP_768 = 8.0  # Respiro visual acima do rótulo do personagem.
KEYBOARD_NAME_LABEL_HEIGHT_768 = 12.0  # Reserva o rótulo acima do campo do personagem.


# Layout de teclas do Teclado Virtual (5 linhas x 13 colunas)
# Cada entrada é (key_id, row, col, span_cols, key_type)
KEYBOARD_LAYOUT: list[tuple[str, int, int, int, str]] = []
for _r in (1, 2, 3):
    for _c in range(1, 14):
        KEYBOARD_LAYOUT.append((f"{_r}x{_c}", _r, _c, 1, "simple"))

KEYBOARD_LAYOUT.append(("caps", 4, 1, 2, "caps"))
for _c in range(3, 12):
    KEYBOARD_LAYOUT.append((f"4x{_c}", 4, _c, 1, "simple"))
KEYBOARD_LAYOUT.append(("backspace", 4, 12, 2, "backspace"))

KEYBOARD_LAYOUT.append(("space", 5, 1, 10, "space"))
KEYBOARD_LAYOUT.append(("ok", 5, 11, 3, "ok"))


def virtual_keyboard_asset_path(filename: str = "background.png") -> Path | None:
    """Retorna o caminho de um asset PNG da pasta do teclado virtual."""
    base = get_project_root()
    path = base / "assets" / "keyboard" / filename
    return path if path.is_file() else None


def virtual_keyboard_bg_asset_path() -> Path | None:
    """Retorna o caminho do asset PNG do background do teclado virtual."""
    return virtual_keyboard_asset_path("background.png")


# Characters printed on the supplied min-/mai- assets (US QWERTY).
KEYBOARD_CHARACTERS = (
    ("`1234567890-=", "~!@#$%^&*()_+"),
    ("qwertyuiop[]\\", "QWERTYUIOP{}|"),
    ("asdfghjkl;'/?", 'ASDFGHJKL:"/?'),
    ("zxcvbnm,.", "ZXCVBNM<>"),
)


def virtual_keyboard_character(key_id: str, caps_state: str = "default") -> str:
    row, col = map(int, key_id.split("x"))
    index = col - (3 if row == 4 else 1)
    return KEYBOARD_CHARACTERS[row - 1][caps_state != "default"][index]


def virtual_keyboard_grid_to_key(row: int, col: int) -> tuple[str, str]:
    """Mapeia (row, col) do grid 5x13 para (key_id, key_type)."""
    if row in (1, 2, 3):
        return (f"{row}x{col}", "simple")
    elif row == 4:
        if col in (1, 2):
            return ("caps", "caps")
        elif col in (12, 13):
            return ("backspace", "backspace")
        else:
            return (f"4x{col}", "simple")
    elif row == 5:
        if col <= 10:
            return ("space", "space")
        else:
            return ("ok", "ok")
    return ("1x1", "simple")


def virtual_keyboard_key_filename(key_id: str, caps_state: str = "default") -> str:
    """Retorna o nome do arquivo PNG para a tecla especificada considerando o estado do Caps Lock."""
    if key_id == "caps":
        if caps_state == "next_letter":
            return "Caps-lock-on-only-next-letter-4x1-e-4x2.png"
        elif caps_state == "all_letters":
            return "Caps-lock-on-4x1-e-4x2.png"
        else:
            return "Caps-lock-default-4x1-e-4x2.png"
    elif key_id == "backspace":
        return "Backspace-4x12-e-4x13.png"
    elif key_id == "space":
        return "tecla-espaço-5x1-a-5x10.png"
    elif key_id == "ok":
        return "OK-5x11-a-5x13.png"
    else:
        prefix = "mai-" if caps_state in ("next_letter", "all_letters") else "min-"
        return f"{prefix}{key_id}.png"


def virtual_keyboard_highlight_filename(key_type: str) -> str:
    """Retorna o nome do asset PNG de highlight correspondente ao tipo de tecla."""
    if key_type in ("caps", "backspace"):
        return "highlight-tecla-dupla.png"
    elif key_type == "ok":
        return "highlight-tecla-tripla.png"
    elif key_type == "space":
        return "highlight-tecla-grande.png"
    else:
        return "highlight-tecla-simples.png"


def virtual_keyboard_info_label_filename(controller_type: str) -> str:
    """Retorna o asset da barra informativa superior conforme o controle detectado."""
    ctrl = controller_type.lower()
    if "nintendo" in ctrl or "switch" in ctrl:
        return "info-label-nintendo.png"
    elif "playstation" in ctrl or "ps" in ctrl or "sony" in ctrl:
        return "info-label-ps.png"
    else:
        return "info-label-xbox.png"


def virtual_keyboard_key_rect(
    kb_x: float,
    kb_y: float,
    kb_w: float,
    kb_h: float,
    key_id: str,
) -> tuple[float, float, float, float]:
    """Calcula as coordenadas absolutas (x, y, w, h) de uma tecla no teclado."""
    scale_k = kb_h / KEYBOARD_REF_HEIGHT
    margin_x = 18.5 * scale_k
    margin_y = 6.0 * scale_k
    step_x = 41.0 * scale_k
    step_y = 56.0 * scale_k

    if key_id == "caps":
        return (
            kb_x + margin_x,
            kb_y + margin_y + 3 * step_y,
            80.0 * scale_k,
            54.0 * scale_k,
        )
    elif key_id == "backspace":
        return (
            kb_x + margin_x + 11 * step_x,
            kb_y + margin_y + 3 * step_y,
            80.0 * scale_k,
            54.0 * scale_k,
        )
    elif key_id == "space":
        return (
            kb_x + margin_x,
            kb_y + margin_y + 4 * step_y,
            399.0 * scale_k,
            55.0 * scale_k,
        )
    elif key_id == "ok":
        return (
            kb_x + margin_x + 399.0 * scale_k + 5.0 * scale_k,
            kb_y + margin_y + 4 * step_y,
            120.0 * scale_k,
            56.0 * scale_k,
        )
    else:
        parts = key_id.split("x")
        r = int(parts[0])
        c = int(parts[1])
        return (
            kb_x + margin_x + (c - 1) * step_x,
            kb_y + margin_y + (r - 1) * step_y,
            39.0 * scale_k,
            54.0 * scale_k,
        )


def virtual_keyboard_key_cursor_point(
    key_x: float,
    key_y: float,
    key_w: float,
    key_h: float,
) -> tuple[int, int]:
    """Calcula a posição do cursor/nó na tecla: posX = largura - 15px, posY = altura - 15px."""
    return (int(round(key_x + key_w - 15.0)), int(round(key_y + key_h - 15.0)))


def virtual_keyboard_target_rect(
    rect: Rect,
    target_field: str = "character_name",
) -> tuple[int, int, int, int]:
    """Posiciona o teclado acima do nome ou à esquerda do painel do pet.

    A UI do jogo escala pela altura, inclusive a largura do painel lateral.
    As âncoras usam os campos existentes e as capturas de referência de 1007p.
    Reserva também espaço para a barra de instruções acima do background.
    """
    if not rect.valid:
        return (0, 0, 0, 0)

    ui_scale = rect.height / KEYBOARD_REF_BASE_HEIGHT
    gap = KEYBOARD_ANCHOR_GAP_768 * rect.height / 768.0
    padding = min(gap, max(0.0, (rect.width - 1) / 2.0))
    field = char_create_text_field_rect(rect, target_field)
    if target_field == "pet_name":
        panel = char_create_pet_panel_rect(rect)
        right = max(rect.left + padding + 1, panel.left - gap)
        bottom = panel.bottom
        available_width = right - rect.left - padding
    else:
        label_height = KEYBOARD_NAME_LABEL_HEIGHT_768 * rect.height / 768.0
        name_gap = KEYBOARD_NAME_ANCHOR_GAP_768 * rect.height / 768.0
        bottom = field.top - label_height - name_gap
        available_width = rect.width - 2 * padding

    # Fit the complete keyboard and its 25px instruction overhang inside the client.
    scale_k = min(ui_scale, available_width / KEYBOARD_REF_WIDTH,
                  (bottom - rect.top) / (KEYBOARD_REF_HEIGHT + 25.0))
    w = max(1, round(KEYBOARD_REF_WIDTH * scale_k))
    h = max(1, round(KEYBOARD_REF_HEIGHT * scale_k))
    if target_field == "pet_name":
        x = round(right) - w
    else:
        x = round(field.left + field.width / 2 - w / 2)
    y = round(bottom) - h
    return (x, y, w, h)

