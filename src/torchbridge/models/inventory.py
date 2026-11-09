from __future__ import annotations

import math
import sys
from pathlib import Path

from ..mathutils import clamp
from .base import Rect, get_project_root


# ==============================================================================
# Inventário do Jogador (Base de referência 1024x768 - painel direito)
# ==============================================================================
# Calibrado a partir de assets/images/inventário/
# O painel direito do inventário é ancorado à borda direita da tela (rect.right):
# dist_from_right = (1024.0 - base_x) * scale
# x = rect.right - dist_from_right
# y = rect.top + base_y * scale

INVENTORY_TAB_COORDS: dict[int, tuple[float, float]] = {
    1: (752.5, 492.5),
    2: (852.5, 492.5),
    3: (952.5, 492.5),
}

INVENTORY_GRID_ORIGIN = (739.5, 520.5)
INVENTORY_GRID_STEP_X = 40.0
INVENTORY_GRID_STEP_Y = 55.0
INVENTORY_GRID_ROWS = 3
INVENTORY_GRID_COLS = 7

INVENTORY_UPPER_COORDS: dict[str, tuple[float, float]] = {
    # Fileira de Feitiços / Spells (y=409.5)
    "spell_1": (779.5, 409.5),
    "spell_2": (831.5, 409.5),
    "spell_3": (883.5, 409.5),
    "spell_4": (935.5, 409.5),
    # Armas e Bugiganga (y ~ 350)
    "main_hand": (729.5, 354.5),
    "trinket": (859.5, 347.5),
    "off_hand": (965.5, 354.5),
    # Cinto e Botas (y=257.5)
    "belt": (729.5, 257.5),
    "boots": (962.5, 257.5),
    # Luvas e Peito (y=182.5)
    "gloves": (729.5, 182.5),
    "chest": (962.5, 182.5),
    # Elmo e Ombros (y=107.5)
    "helmet": (729.5, 107.5),
    "shoulders": (962.5, 107.5),
    # Anéis e Colar (y=100.5)
    "ring_1": (801.5, 100.5),
    "necklace": (845.5, 100.5),
    "ring_2": (889.5, 100.5),
}

INVENTORY_UPPER_NAV_MAP: dict[str, dict[str, Any]] = {
    # Spells (y=409.5)
    "spell_1": {"left": "main_hand", "right": "spell_2", "up": "main_hand", "down": (1, 1)},
    "spell_2": {"left": "spell_1", "right": "spell_3", "up": "trinket", "down": (1, 3)},
    "spell_3": {"left": "spell_2", "right": "spell_4", "up": "trinket", "down": (1, 5)},
    "spell_4": {"left": "spell_3", "right": "off_hand", "up": "off_hand", "down": (1, 7)},
    # Armas / Trinket (y ~ 350)
    "main_hand": {"up": "belt", "down": "spell_1", "right": "trinket", "left": "main_hand"},
    "trinket": {"left": "main_hand", "right": "off_hand", "down": "spell_2", "up": "necklace"},
    "off_hand": {"up": "boots", "down": "spell_4", "left": "trinket", "right": "off_hand"},
    # Cinto e Botas (y=257.5)
    "belt": {"up": "gloves", "down": "main_hand", "right": "boots", "left": "belt"},
    "boots": {"up": "chest", "down": "off_hand", "left": "belt", "right": "boots"},
    # Luvas e Peito (y=182.5)
    "gloves": {"up": "helmet", "down": "belt", "right": "chest", "left": "gloves"},
    "chest": {"up": "shoulders", "down": "boots", "left": "gloves", "right": "chest"},
    # Elmo, Anéis, Colar, Ombros (y ~ 100-107)
    "helmet": {"down": "gloves", "right": "ring_1", "left": "helmet", "up": "helmet"},
    "ring_1": {"left": "helmet", "right": "necklace", "down": "main_hand", "up": "ring_1"},
    "necklace": {"left": "ring_1", "right": "ring_2", "down": "trinket", "up": "necklace"},
    "ring_2": {"left": "necklace", "right": "shoulders", "down": "off_hand", "up": "ring_2"},
    "shoulders": {"left": "ring_2", "down": "chest", "right": "shoulders", "up": "shoulders"},
}


def inventory_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot do grid do inventário (row 1..3, col 1..7)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 1, INVENTORY_GRID_ROWS))
    c = int(clamp(col, 1, INVENTORY_GRID_COLS))
    base_x = INVENTORY_GRID_ORIGIN[0] + (c - 1) * INVENTORY_GRID_STEP_X
    base_y = INVENTORY_GRID_ORIGIN[1] + (r - 1) * INVENTORY_GRID_STEP_Y
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def inventory_tab_point(rect: Rect, tab_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão da aba (1, 2 ou 3) do inventário."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(tab_index, 1, 3))
    base_x, base_y = INVENTORY_TAB_COORDS.get(idx, (752.5, 492.5))
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def inventory_upper_point(rect: Rect, slot_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot da parte superior de equipamentos do inventário."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    base_x, base_y = INVENTORY_UPPER_COORDS.get(slot_name.lower(), (779.5, 409.5))
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# ==============================================================================
# Menu / Inventário do Pet (Base de referência 1024x768 - painel esquerdo)
# ==============================================================================
# Calibrado a partir de assets/images/inventário/pet-4x3.png
# O painel esquerdo do Pet é ancorado à borda esquerda da tela (rect.left):
# x = rect.left + base_x * scale
# y = rect.top + base_y * scale

PET_TAB_COORDS: dict[int, tuple[float, float]] = {
    1: (69.5, 495.5),
    2: (169.5, 495.5),
    3: (269.5, 495.5),
}

PET_GRID_ORIGIN = (56.5, 523.5)
PET_GRID_STEP_X = 40.0
PET_GRID_STEP_Y = 55.0
PET_GRID_ROWS = 3
PET_GRID_COLS = 7

PET_UPPER_COORDS: dict[str, tuple[float, float]] = {
    "pet_spell_1": (96.5, 327.5),
    "pet_ring_1": (134.5, 338.5),
    "pet_collar": (178.5, 338.5),
    "pet_ring_2": (222.5, 338.5),
    "pet_spell_2": (282.5, 327.5),
}

PET_UPPER_NAV_MAP: dict[str, dict[str, Any]] = {
    "pet_spell_1": {"left": "pet_spell_1", "right": "pet_ring_1", "up": "pet_spell_1", "down": (1, 1)},
    "pet_ring_1": {"left": "pet_spell_1", "right": "pet_collar", "up": "pet_ring_1", "down": (1, 3)},
    "pet_collar": {"left": "pet_ring_1", "right": "pet_ring_2", "up": "pet_collar", "down": (1, 4)},
    "pet_ring_2": {"left": "pet_collar", "right": "pet_spell_2", "up": "pet_ring_2", "down": (1, 5)},
    "pet_spell_2": {"left": "pet_ring_2", "right": "pet_spell_2", "up": "pet_spell_2", "down": (1, 7)},
}


def pet_inventory_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot do grid do menu de Pet (row 1..3, col 1..7)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 1, PET_GRID_ROWS))
    c = int(clamp(col, 1, PET_GRID_COLS))
    base_x = PET_GRID_ORIGIN[0] + (c - 1) * PET_GRID_STEP_X
    base_y = PET_GRID_ORIGIN[1] + (r - 1) * PET_GRID_STEP_Y
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def pet_inventory_tab_point(rect: Rect, tab_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão da aba (1, 2 ou 3) do menu de Pet."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(tab_index, 1, 3))
    base_x, base_y = PET_TAB_COORDS.get(idx, (69.5, 495.5))
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def pet_inventory_upper_point(rect: Rect, slot_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot superior de equipamento/spell do Pet."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    base_x, base_y = PET_UPPER_COORDS.get(slot_name.lower(), (96.5, 327.5))
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# ==============================================================================
# Menu / Painel do Baú (Stash) (Base de referência 1024x768 - painel esquerdo)
# ==============================================================================
# Calibrado a partir de assets/images/inventário/bau-inventario-4x3.png
# O painel esquerdo do Baú é ancorado à borda esquerda da tela (rect.left):
# Parte Superior: Grid do Baú de 6 linhas x 7 colunas (42 slots)
# Parte Inferior: Grid do Pet de 3 linhas x 7 colunas (21 slots) + 3 Abas

STASH_GRID_ROWS = 6
STASH_GRID_COLS = 7
STASH_GRID_ORIGIN_X = 63.5
STASH_GRID_STEP_X = 40.0
STASH_GRID_ROW_Y: dict[int, float] = {
    1: 109.5,
    2: 164.5,
    3: 219.5,
    4: 277.5,
    5: 332.5,
    6: 387.5,
}


def stash_upper_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot do grid superior do Baú (row 1..6, col 1..7)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 1, STASH_GRID_ROWS))
    c = int(clamp(col, 1, STASH_GRID_COLS))
    base_x = STASH_GRID_ORIGIN_X + (c - 1) * STASH_GRID_STEP_X
    base_y = STASH_GRID_ROW_Y.get(r, 109.5 + (r - 1) * 55.0)
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# ==============================================================================
# Menu / Painel do Mercador (Lojas / Vendedores) (Base 1024x768 - painel esquerdo)
# ==============================================================================
# Calibrado a partir de assets/images/inventário/mercador-4x3.png
# Painel esquerdo ancorado a rect.left:
# 3 Abas Rosa no topo (Misc, Weapon, Armor)
# Grid da Loja de 6 linhas x 7 colunas (42 slots)
# Grid do Pet de 3 linhas x 7 colunas (21 slots) + 3 Abas Ciano

MERCHANT_TABS_COORDS: dict[int, tuple[float, float]] = {
    1: (88.0, 78.0),   # Misc
    2: (183.0, 78.0),  # Weapon
    3: (278.0, 78.0),  # Armor
}

MERCHANT_GRID_ROWS = 6
MERCHANT_GRID_COLS = 7
MERCHANT_GRID_ORIGIN_X = 63.5
MERCHANT_GRID_STEP_X = 40.0
MERCHANT_GRID_ROW_Y: dict[int, float] = {
    1: 109.5,
    2: 164.5,
    3: 219.5,
    4: 277.5,
    5: 332.5,
    6: 387.5,
}


def merchant_tab_point(rect: Rect, tab_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do ponto rosa de uma aba do Mercador (1=Misc, 2=Weapon, 3=Armor)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(tab_index, 1, 3))
    base_x, base_y = MERCHANT_TABS_COORDS.get(idx, (88.0, 78.0))
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def merchant_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do centro de um slot do grid do Mercador (row 1..6, col 1..7)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 1, MERCHANT_GRID_ROWS))
    c = int(clamp(col, 1, MERCHANT_GRID_COLS))
    base_x = MERCHANT_GRID_ORIGIN_X + (c - 1) * MERCHANT_GRID_STEP_X
    base_y = MERCHANT_GRID_ROW_Y.get(r, 109.5 + (r - 1) * 55.0)
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)

