from __future__ import annotations

import math
import sys
from pathlib import Path

from ..mathutils import clamp
from .base import Rect, get_project_root


# Coordenadas relativas dos botões da Tela Inicial (Title Screen)
# Base de referência: 768p (1024x768). Proporção ancorada na ALTURA da janela (rect.height).
TITLE_BUTTON_BOTTOM_Y_FRACTION = 0.9466  # Y = rect.top + rect.height * 0.9466 (~727px em 768p)
TITLE_BUTTON_CONTINUE_Y_FRACTION = 0.8464  # Y = rect.top + rect.height * 0.8464 (~650px em 768p)

# Deslocamentos horizontais a partir do CENTRO da janela (rect.left + rect.width * 0.5)
# Escala multiplicada por (rect.height / 768.0)
TITLE_X_OFFSET_NEW_CHARACTER = -299.5
TITLE_X_OFFSET_LOAD_CHARACTER = -44.5
TITLE_X_OFFSET_SETTINGS = 206.5
TITLE_X_OFFSET_QUIT = 457.5
TITLE_X_OFFSET_CONTINUE = 457.5

TITLE_BUTTONS = ("new_character", "load_character", "settings", "quit_game", "continue")


def title_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) absoluta de um botão na Tela Inicial,
    respeitando a proporção da altura da janela (rect.height).
    """
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    if button_name == "continue":
        x = center_x + TITLE_X_OFFSET_CONTINUE * scale
        y = rect.top + rect.height * TITLE_BUTTON_CONTINUE_Y_FRACTION
    elif button_name == "new_character":
        x = center_x + TITLE_X_OFFSET_NEW_CHARACTER * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "load_character":
        x = center_x + TITLE_X_OFFSET_LOAD_CHARACTER * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "settings":
        x = center_x + TITLE_X_OFFSET_SETTINGS * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "quit_game":
        x = center_x + TITLE_X_OFFSET_QUIT * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    else:
        x = center_x
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões da Tela de Criação de Personagem (state_id == 1)
# Todas as posições são ancoradas e escaladas proporcionalmente à ALTURA da janela (rect.height),
# garantindo alinhamento sub-pixel idêntico em 4:3, 16:9 ou qualquer outra proporção.
CHAR_CREATE_CLASSES_X_FRACTION = 0.1855  # Âncora na borda esquerda: rect.left + height * 0.1855
CHAR_CREATE_DESTROYER_Y_FRACTION = 0.382
CHAR_CREATE_VANQUISHER_Y_FRACTION = 0.558
CHAR_CREATE_ALCHEMIST_Y_FRACTION = 0.733

CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION = 0.072  # Âncora na borda direita: rect.right - height * 0.072
CHAR_CREATE_PET_DOG_Y_FRACTION = 0.552
CHAR_CREATE_PET_CAT_Y_FRACTION = 0.591
CHAR_CREATE_PET_FERRET_Y_FRACTION = 0.631
CHAR_CREATE_PET_NAME_Y_FRACTION = 0.719

CHAR_CREATE_BOTTOM_Y_FRACTION = 0.948  # Âncora no rodapé / centro
CHAR_CREATE_BACK_X_OFFSET_FRACTION = -0.266
CHAR_CREATE_NAME_X_OFFSET_FRACTION = 0.052
CHAR_CREATE_OK_X_OFFSET_FRACTION = 0.454

CREATE_CHAR_BUTTONS = (
    "destroyer",
    "vanquisher",
    "alchemist",
    "dog",
    "cat",
    "ferret",
    "pet_name",
    "back",
    "character_name",
    "ok",
)


def char_create_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão na Tela de Criação de Personagem."""
    if not rect.valid:
        return (0, 0)

    center_x = rect.left + rect.width * 0.5

    if button_name == "destroyer":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_DESTROYER_Y_FRACTION
    elif button_name == "vanquisher":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_VANQUISHER_Y_FRACTION
    elif button_name == "alchemist":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_ALCHEMIST_Y_FRACTION
    elif button_name == "dog":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_DOG_Y_FRACTION
    elif button_name == "cat":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_CAT_Y_FRACTION
    elif button_name == "ferret":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_FERRET_Y_FRACTION
    elif button_name == "pet_name":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_NAME_Y_FRACTION
    elif button_name == "back":
        x = center_x + rect.height * CHAR_CREATE_BACK_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    elif button_name == "character_name":
        x = center_x + rect.height * CHAR_CREATE_NAME_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    elif button_name == "ok":
        x = center_x + rect.height * CHAR_CREATE_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    else:
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_DESTROYER_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def char_create_pet_panel_rect(rect: Rect) -> Rect:
    """Pet panel in physical client pixels; its size follows height, not width."""
    if not rect.valid:
        return Rect()
    left = round(rect.right - rect.height * 0.250)
    right = round(rect.right - rect.height * 0.014)
    top = round(rect.top + rect.height * 0.460)
    bottom = round(rect.top + rect.height * 0.770)
    return Rect(left, top, right - left, bottom - top)


def char_create_text_field_rect(rect: Rect, target_field: str) -> Rect:
    """Bounds of the name edit boxes, excluding their labels/calibration nodes."""
    if not rect.valid:
        return Rect()
    if target_field == "pet_name":
        panel = char_create_pet_panel_rect(rect)
        left = round(panel.left + rect.height * 0.004)
        right = round(panel.right - rect.height * 0.004)
        center_y = rect.top + rect.height * CHAR_CREATE_PET_NAME_Y_FRACTION
    else:
        center_x = rect.left + rect.width / 2
        left = round(center_x - rect.height * 0.1185)
        right = round(center_x + rect.height * 0.1185)
        center_y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    top = round(center_y - rect.height * 0.033)
    bottom = round(center_y + rect.height * 0.033)
    return Rect(left, top, right - left, bottom - top)





# Coordenadas dos botões da Tela de Seleção de Dificuldade (state_id == 2)
DIFFICULTY_OPTIONS_X_FRACTION = 0.239  # Âncora na borda esquerda: rect.left + height * 0.239
DIFFICULTY_EASY_Y_FRACTION = 0.378
DIFFICULTY_NORMAL_Y_FRACTION = 0.428
DIFFICULTY_HARD_Y_FRACTION = 0.481
DIFFICULTY_VERY_HARD_Y_FRACTION = 0.532

DIFFICULTY_HARDCORE_X_FRACTION = 0.1068  # Caixa de seleção Hardcore
DIFFICULTY_HARDCORE_Y_FRACTION = 0.631

DIFFICULTY_BOTTOM_Y_FRACTION = 0.948  # Botão Voltar (rodapé/centro)
DIFFICULTY_BACK_X_OFFSET_FRACTION = -0.266

DIFFICULTY_BUTTONS = (
    "easy",
    "normal",
    "hard",
    "very_hard",
    "hardcore",
    "back",
)


def difficulty_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão na Tela de Seleção de Dificuldade."""
    if not rect.valid:
        return (0, 0)

    center_x = rect.left + rect.width * 0.5

    if button_name == "easy":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_EASY_Y_FRACTION
    elif button_name == "normal":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_NORMAL_Y_FRACTION
    elif button_name == "hard":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARD_Y_FRACTION
    elif button_name == "very_hard":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_VERY_HARD_Y_FRACTION
    elif button_name == "hardcore":
        x = rect.left + rect.height * DIFFICULTY_HARDCORE_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARDCORE_Y_FRACTION
    elif button_name == "back":
        x = center_x + rect.height * DIFFICULTY_BACK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIFFICULTY_BOTTOM_Y_FRACTION
    else:
        x = rect.left + rect.height * DIFFICULTY_HARDCORE_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARDCORE_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas calibradas para Botões de Diálogos e Telas de História (base 1024x768)
DIALOG_BUTTON_Y_FRACTION = 573.0 / 768.0          # Linha vertical dos botões Ok, Accept, Decline (573/768 = ~0.7461)
DIALOG_ACCEPT_X_OFFSET_FRACTION = -51.0 / 768.0  # -0.0664 (461px - 512px = 51px à esquerda do centro em 768p)
DIALOG_DECLINE_X_OFFSET_FRACTION = 146.0 / 768.0  # +0.1901 (658px - 512px = 146px à direita do centro em 768p)
DIALOG_OK_X_OFFSET_FRACTION = 42.0 / 768.0       # +0.0547 (554px - 512px = 42px à direita do centro em 768p)

DIALOG_REWARD_SLOT_X_OFFSET_FRACTION = -338.0 / 768.0  # -0.4401 (174px - 512px = 338px à esquerda do centro em 768p)
DIALOG_REWARD_SLOT_Y_FRACTION = 506.0 / 768.0         # 0.6589 (506px em 768p)

CINEMATIC_SKIP_X_OFFSET_FRACTION = 0.487          # Botão Skip/Continue na tela de história
CINEMATIC_SKIP_Y_FRACTION = 0.948


def dialog_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão ou slot de recompensa em diálogos de NPCs, missões e tela de história."""
    if not rect.valid:
        return (0, 0)
    center_x = rect.left + rect.width * 0.5
    btn = button_name.lower()
    if btn == "ok":
        x = center_x + rect.height * DIALOG_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn == "accept":
        x = center_x + rect.height * DIALOG_ACCEPT_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn == "decline":
        x = center_x + rect.height * DIALOG_DECLINE_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn in ("reward", "reward_slot", "slot"):
        x = center_x + rect.height * DIALOG_REWARD_SLOT_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_REWARD_SLOT_Y_FRACTION
    elif btn in ("skip", "continue"):
        x = center_x + rect.height * CINEMATIC_SKIP_X_OFFSET_FRACTION
        y = rect.top + rect.height * CINEMATIC_SKIP_Y_FRACTION
    else:
        x = center_x + rect.height * DIALOG_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas calibradas para Pesca e Diálogo Modal de Confirmação (base 1024x768)
FISHING_HOOK_COORD: tuple[float, float] = (512.0, 498.0)
MODAL_OK_COORD: tuple[float, float] = (509.0, 467.0)


def fishing_hook_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão de anzol na interface de pesca."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_x, base_y = FISHING_HOOK_COORD
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def modal_ok_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão Ok no modal de confirmação / mensagem de pesca."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_x, base_y = MODAL_OK_COORD
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)



# Coordenadas base dos botões e slots de interfaces de crafting (painel esquerdo, base 1024x768)
# Calibradas e validadas pixel a pixel a partir dos elementos visuais reais in-game
CRAFTING_BUTTONS: dict[str, dict[str, tuple[float, float]]] = {
    "Transmutador": {
        "decline": (240.0, 405.0),
        "transmute": (240.0, 450.0),
        "accept": (240.0, 450.0),
        "action": (240.0, 450.0),
    },
    "Sockets": {
        "decline": (240.0, 402.0),
        "recover": (240.0, 447.0),
        "accept": (240.0, 447.0),
        "action": (240.0, 447.0),
    },
    "Encantador": {
        "decline": (240.0, 402.0),
        "enchant": (240.0, 447.0),
        "accept": (240.0, 447.0),
        "action": (240.0, 447.0),
    },
}

# Posições dos slots de itens (base 1024x768)
CRAFTING_SLOTS: dict[str, list[tuple[float, float]]] = {
    # 4 slots: 2x2 grid (topo-esq, topo-dir, baixo-esq, baixo-dir)
    "Transmutador": [
        (216.0, 266.0),
        (268.0, 266.0),
        (216.0, 339.0),
        (268.0, 339.0),
    ],
    # 1 slot central quadrado (inner 96x96)
    "Sockets": [
        (240.0, 314.0),
    ],
    # 1 slot central quadrado (inner 96x96)
    "Encantador": [
        (240.0, 314.0),
    ],
}


def crafting_button_point(rect: Rect, menu_name: str, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão nas telas de Transmutador, Sockets e Encantador."""
    if not rect.valid:
        return (0, 0)
    buttons = CRAFTING_BUTTONS.get(menu_name, CRAFTING_BUTTONS.get("Encantador", {}))
    bx, by = buttons.get(button_name.lower(), (200.0, 274.0))
    scale = rect.height / 768.0
    x = rect.left + bx * scale
    y = rect.top + by * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def crafting_slot_point(rect: Rect, menu_name: str, slot_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot de item nas telas de Transmutador (0..3) ou Sockets/Encantador (0)."""
    if not rect.valid:
        return (0, 0)
    slots = CRAFTING_SLOTS.get(menu_name, CRAFTING_SLOTS.get("Encantador", []))
    if not slots:
        return (0, 0)
    idx = max(0, min(slot_index, len(slots) - 1))
    sx, sy = slots[idx]
    scale = rect.height / 768.0
    x = rect.left + sx * scale
    y = rect.top + sy * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões do Menu de Pause (COptionsMenu / Options) em jogo (base 1024x768)
# Calibradas e validadas a partir dos quadradinhos em assets/images/menus/in-game paused.png
PAUSE_BUTTONS: tuple[str, ...] = ("settings", "exit_to_title", "return_to_game")

PAUSE_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "settings": (599.0, 233.0),
    "exit_to_title": (599.0, 323.0),
    "return_to_game": (599.0, 413.0),
}


def pause_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) central do quadradinho mapeado no Menu de Pause."""
    if not rect.valid:
        return (0, 0)
    bx, by = PAUSE_BUTTON_COORDS.get(button_name.lower(), (599.0, 413.0))
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    # Offset horizontal em relacao ao centro da tela (512 em 1024x768)
    x = center_x + (bx - 512.0) * scale
    y = rect.top + by * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões da tela de Morte / Respawn em jogo (base 1024x768)
# Calibradas e validadas a partir de assets/images/sreensXcursor/death-screen.png
# Ordem vertical:
# 1. "resurrect_here" (verde - superior): Resurrect here, but lose Experience/Fame
# 2. "resurrect_entrance" (amarelo - padrão inicial): Resurrect at entrance, but lose Gold
# 3. "resurrect_town" (verde - intermediário): Resurrect in town and lose nothing
# 4. "exit_to_title" (verde - inferior): Exit to Title
DEATH_SCREEN_BUTTONS: tuple[str, ...] = (
    "resurrect_here",
    "resurrect_entrance",
    "resurrect_town",
    "exit_to_title",
)

DEATH_SCREEN_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "resurrect_here": (334.0, 248.0),
    "resurrect_entrance": (334.0, 348.0),
    "resurrect_town": (334.0, 448.0),
    "exit_to_title": (563.0, 552.0),
}


def death_screen_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão na tela de Morte / Respawn."""
    if not rect.valid:
        return (0, 0)
    bx, by = DEATH_SCREEN_BUTTON_COORDS.get(button_name.lower(), (334.0, 348.0))
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    x = center_x + (bx - 512.0) * scale
    y = rect.top + by * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões e slots da tela de Carregar Personagem (state_id == 3) (base 1024x768)
# Calibradas e validadas a partir de assets/images/sreensXcursor/load-char
LOAD_CHAR_BUTTONS: tuple[str, ...] = (
    "slot_1", "slot_2", "slot_3", "slot_4", "slot_5",
    "scroll_up", "scroll_down",
    "delete", "back", "play",
    "delete_confirm", "delete_cancel",
)

LOAD_CHAR_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "slot_1": (971.0, 227.0),
    "slot_2": (971.0, 299.5),
    "slot_3": (971.0, 372.0),
    "slot_4": (971.0, 445.0),
    "slot_5": (971.0, 517.0),
    "scroll_up": (979.0, 155.0),
    "scroll_down": (971.0, 618.0),
    "delete": (558.0, 663.0),
    "back": (300.0, 728.0),
    "play": (859.0, 728.0),
    "delete_confirm": (576.0, 362.0),
    "delete_cancel": (576.0, 411.0),
}


def load_char_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão/slot na tela de Carregar Personagem."""
    if not rect.valid:
        return (0, 0)
    btn = button_name.lower()
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    # Slots e setas de rolagem da lista de personagens (ancorados a borda direita)
    if btn.startswith("slot_") or btn in ("scroll_up", "scroll_down"):
        base_x, base_y = LOAD_CHAR_BUTTON_COORDS.get(btn, (971.0, 227.0))
        right_dist = (1024.0 - base_x) * scale
        x = rect.right - right_dist
        y = rect.top + base_y * scale
    else:
        # Botoes centralizados/inferiores e modal de delete (ancorados ao centro horizontal)
        base_x, base_y = LOAD_CHAR_BUTTON_COORDS.get(btn, (859.0, 728.0))
        x = center_x + (base_x - 512.0) * scale
        y = rect.top + base_y * scale

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões e controles da tela de Configurações (Settings) (base 1024x768)
# Calibradas e validadas a partir de assets/images/sreensXcursor/settings
SETTINGS_BUTTONS: tuple[str, ...] = (
    "row1_col1", "row1_col2", "row1_col3",
    "row2_col1", "row2_col2", "row2_col3",
    "resolution", "shadows",
    "music_slider", "music_mute", "particle_detail",
    "row5_col3",
    "sound_slider", "sound_mute", "row6_col3",
    "row7_col1", "row7_col3",
    "cancel", "apply",
)

SETTINGS_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "row1_col1": (238.0, 132.0),
    "row1_col2": (437.0, 132.0),
    "row1_col3": (636.0, 132.0),
    "row2_col1": (238.0, 184.0),
    "row2_col2": (437.0, 184.0),
    "row2_col3": (636.0, 184.0),
    "resolution": (398.0, 247.0),
    "shadows": (800.0, 247.0),
    "music_slider": (272.0, 344.0),
    "music_mute": (486.0, 346.0),
    "particle_detail": (800.0, 346.0),
    "row5_col3": (636.0, 401.0),
    "sound_slider": (304.0, 445.0),
    "sound_mute": (486.0, 448.0),
    "row6_col3": (636.0, 444.0),
    "row7_col1": (238.0, 488.0),
    "row7_col3": (636.0, 488.0),
    "cancel": (465.0, 552.0),
    "apply": (657.0, 552.0),
}

SETTINGS_SLIDER_X_MIN = 228.0
SETTINGS_SLIDER_X_MAX = 447.0
SETTINGS_MUSIC_SLIDER_Y = 344.0
SETTINGS_SOUND_SLIDER_Y = 445.0

SETTINGS_DROPDOWNS: dict[str, dict[str, Any]] = {
    "resolution": {
        "opener": (398.0, 247.0),
        "options": [
            (385.0, 293.0),
            (385.0, 309.5),
            (385.0, 326.0),
            (385.0, 342.5),
            (385.0, 359.0),
            (385.0, 375.5),
            (385.0, 392.0),
            (385.0, 408.5),
            (385.0, 425.0),
            (385.0, 441.5),
            (385.0, 458.0),
            (385.0, 474.5),
            (385.0, 491.0),
            (385.0, 507.5),
            (385.0, 524.0),
            (385.0, 540.5),
            (385.0, 557.0),
            (385.0, 573.5),
        ],
    },
    "shadows": {
        "opener": (800.0, 247.0),
        "options": [
            (780.0, 293.0),
            (780.0, 310.0),
            (780.0, 329.0),
            (780.0, 346.0),
            (780.0, 363.0),
            (780.0, 380.0),
        ],
    },
    "particle_detail": {
        "opener": (800.0, 346.0),
        "options": [
            (785.0, 396.0),
            (785.0, 413.0),
            (785.0, 431.0),
        ],
    },
}

SETTINGS_NAV_MAP: dict[str, dict[str, str]] = {
    # Row 1 (y=132)
    "row1_col1": {"right": "row1_col2", "down": "row2_col1"},
    "row1_col2": {"left": "row1_col1", "right": "row1_col3", "down": "row2_col2"},
    "row1_col3": {"left": "row1_col2", "down": "row2_col3"},

    # Row 2 (y=184)
    "row2_col1": {"up": "row1_col1", "right": "row2_col2", "down": "resolution"},
    "row2_col2": {"up": "row1_col2", "left": "row2_col1", "right": "row2_col3", "down": "resolution"},
    "row2_col3": {"up": "row1_col3", "left": "row2_col2", "down": "shadows"},

    # Row 3 (y=247)
    "resolution": {"up": "row2_col2", "right": "shadows", "down": "music_slider"},
    "shadows": {"up": "row2_col3", "left": "resolution", "down": "particle_detail"},

    # Row 4 (y=344..346)
    "music_slider": {"up": "resolution", "right": "music_mute", "down": "sound_slider"},
    "music_mute": {"up": "resolution", "left": "music_slider", "right": "particle_detail", "down": "sound_mute"},
    "particle_detail": {"up": "shadows", "left": "music_mute", "down": "row5_col3"},

    # Row 5 (y=401)
    "row5_col3": {"up": "particle_detail", "left": "music_mute", "down": "row6_col3"},

    # Row 6 (y=444..448)
    "sound_slider": {"up": "music_slider", "right": "sound_mute", "down": "row7_col1"},
    "sound_mute": {"up": "music_mute", "left": "sound_slider", "right": "row6_col3", "down": "cancel"},
    "row6_col3": {"up": "row5_col3", "left": "sound_mute", "down": "row7_col3"},

    # Row 7 (y=488)
    "row7_col1": {"up": "sound_slider", "right": "row7_col3", "down": "cancel"},
    "row7_col3": {"up": "row6_col3", "left": "row7_col1", "down": "apply"},

    # Row 8 (y=552)
    "cancel": {"up": "row7_col1", "right": "apply"},
    "apply": {"up": "row7_col3", "left": "cancel"},
}


def settings_button_point(rect: Rect, button_name: str, volume: float | None = None) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão/controle na tela de Configurações."""
    if not rect.valid:
        return (0, 0)
    btn = button_name.lower()
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    if btn == "music_slider":
        vol = 0.5 if volume is None else clamp(volume, 0.0, 1.0)
        base_x = SETTINGS_SLIDER_X_MIN + vol * (SETTINGS_SLIDER_X_MAX - SETTINGS_SLIDER_X_MIN)
        base_y = SETTINGS_MUSIC_SLIDER_Y
    elif btn == "sound_slider":
        vol = 0.5 if volume is None else clamp(volume, 0.0, 1.0)
        base_x = SETTINGS_SLIDER_X_MIN + vol * (SETTINGS_SLIDER_X_MAX - SETTINGS_SLIDER_X_MIN)
        base_y = SETTINGS_SOUND_SLIDER_Y
    else:
        base_x, base_y = SETTINGS_BUTTON_COORDS.get(btn, (238.0, 132.0))

    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def settings_dropdown_option_point(rect: Rect, dropdown_name: str, option_idx: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de uma opção dentro de um dropdown aberto na tela de Configurações."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    data = SETTINGS_DROPDOWNS.get(dropdown_name.lower())
    if not data:
        return (0, 0)
    options = data["options"]
    idx = int(clamp(option_idx, 0, len(options) - 1))
    base_x, base_y = options[idx]
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def settings_slider_bounds(rect: Rect, is_music: bool = True) -> tuple[tuple[int, int], tuple[int, int]]:
    """Retorna os pontos (x1, y1) e (x2, y2) da linha ciano do slider na tela de Configurações."""
    if not rect.valid:
        return ((0, 0), (0, 0))
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_y = SETTINGS_MUSIC_SLIDER_Y if is_music else SETTINGS_SOUND_SLIDER_Y
    y = rect.top + base_y * scale

    x1 = center_x + (SETTINGS_SLIDER_X_MIN - 512.0) * scale
    x2 = center_x + (SETTINGS_SLIDER_X_MAX - 512.0) * scale
    p1 = (int(clamp(round(x1), rect.left + 2, rect.right - 2)), int(clamp(round(y), rect.top + 2, rect.bottom - 2)))
    p2 = (int(clamp(round(x2), rect.left + 2, rect.right - 2)), int(clamp(round(y), rect.top + 2, rect.bottom - 2)))
    return (p1, p2)

