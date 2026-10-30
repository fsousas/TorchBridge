from __future__ import annotations

import math
import sys
from pathlib import Path

from ..mathutils import clamp
from .base import Rect, get_project_root


# ==============================================================================
# Menu de Personagem / Character (C) (Base de referência 1024×768 — painel esquerdo)
# ==============================================================================
# Calibrado a partir de assets/images/menus/skilltrees/character+skill 4x3 *.png
# Painel esquerdo ancorado a rect.left:
#   x = rect.left + base_x * scale
#   y = rect.top  + base_y * scale

# Mapa completo de nós do Menu de Personagem (C) sem pontos para distribuir (16 nós)
CHAR_MENU_NODES_NO_POINTS: dict[str, tuple[float, float]] = {
    # Topo
    "xp":               (260.5, 129.5),
    "fame":             (260.5, 161.5),
    "hp":               (161.5, 204.5),
    "mp":               (288.5, 204.5),
    # Atributos (Strength, Dexterity, Magic, Defense)
    "strength":         (134.5, 271.5),
    "strength_bridge":  (260.5, 271.5),
    "dexterity":        (134.5, 338.5),
    "dexterity_bridge": (260.5, 338.5),
    "magic":            (134.5, 405.5),
    "magic_bridge":     (260.5, 405.5),
    "defense":          (134.5, 472.5),
    "defense_bridge":   (260.5, 472.5),
    # Resistências
    "res_poison":       (143.5, 581.5),
    "res_fire":         (260.5, 581.5),
    "res_electric":     (143.5, 615.5),
    "res_ice":          (260.5, 615.5),
}

# Mapa completo de nós do Menu de Personagem (C) com pontos para distribuir (24 nós)
CHAR_MENU_NODES_HAS_POINTS: dict[str, tuple[float, float]] = {
    # Topo
    "xp":               (260.5, 129.5),
    "fame":             (260.5, 161.5),
    "hp":               (161.5, 204.5),
    "mp":               (288.5, 204.5),
    # Atributos (com botões de + e estatísticas)
    "strength":         (134.5, 271.5),
    "strength_stat":    (260.5, 271.5),
    "strength_pink":    (288.5, 271.5),
    "strength_bridge":  (316.5, 271.5),
    "dexterity":        (134.5, 338.5),
    "dexterity_stat":   (260.5, 338.5),
    "dexterity_pink":   (288.5, 338.5),
    "dexterity_bridge": (316.5, 338.5),
    "magic":            (134.5, 405.5),
    "magic_stat":       (260.5, 405.5),
    "magic_pink":       (288.5, 405.5),
    "magic_bridge":     (316.5, 405.5),
    "defense":          (134.5, 472.5),
    "defense_stat":     (260.5, 472.5),
    "defense_pink":     (288.5, 472.5),
    "defense_bridge":   (316.5, 472.5),
    # Resistências
    "res_poison":       (143.5, 581.5),
    "res_fire":         (260.5, 581.5),
    "res_electric":     (143.5, 615.5),
    "res_ice":          (260.5, 615.5),
}

CHAR_ATTR_ORDER: list[str] = ["strength", "dexterity", "magic", "defense"]

# Linhas de navegação D-pad no Menu de Personagem (C)
CHAR_MENU_ROWS_NO_POINTS: list[list[str]] = [
    ["xp"],
    ["fame"],
    ["hp", "mp"],
    ["strength", "strength_bridge"],
    ["dexterity", "dexterity_bridge"],
    ["magic", "magic_bridge"],
    ["defense", "defense_bridge"],
    ["res_poison", "res_fire"],
    ["res_electric", "res_ice"],
]

CHAR_MENU_ROWS_HAS_POINTS: list[list[str]] = [
    ["xp"],
    ["fame"],
    ["hp", "mp"],
    ["strength", "strength_stat", "strength_pink", "strength_bridge"],
    ["dexterity", "dexterity_stat", "dexterity_pink", "dexterity_bridge"],
    ["magic", "magic_stat", "magic_pink", "magic_bridge"],
    ["defense", "defense_stat", "defense_pink", "defense_bridge"],
    ["res_poison", "res_fire"],
    ["res_electric", "res_ice"],
]


def char_menu_point(rect: Rect, node_name: str, has_points: bool = False) -> tuple[int, int]:
    """Coordenada (x, y) de qualquer nó do menu de Personagem (C)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    nodes = CHAR_MENU_NODES_HAS_POINTS if has_points else CHAR_MENU_NODES_NO_POINTS
    base_x, base_y = nodes.get(node_name, (134.5, 271.5))
    x = rect.left + base_x * scale
    y = rect.top + base_y * scale
    return (int(clamp(round(x), rect.left + 2, rect.right - 2)),
            int(clamp(round(y), rect.top + 2, rect.bottom - 2)))


def char_attr_point(rect: Rect, attr: str) -> tuple[int, int]:
    """Coordenada (x, y) do nó verde de um atributo do menu de Personagem."""
    return char_menu_point(rect, attr.lower(), has_points=False)


def char_attr_bridge_point(rect: Rect, attr: str) -> tuple[int, int]:
    """Coordenada (x, y) do nó laranja (ponte → menu S) de um atributo."""
    return char_menu_point(rect, f"{attr.lower()}_bridge", has_points=False)


def char_attr_pink_point(rect: Rect, attr: str) -> tuple[int, int]:
    """Coordenada (x, y) do nó rosa (+atributo) quando há pontos para distribuir."""
    return char_menu_point(rect, f"{attr.lower()}_pink", has_points=True)


# ==============================================================================
# Árvore de Habilidades / Skill Tree (S) (Base de referência 1024×768 — painel direito)
# ==============================================================================
# Calibrado a partir de assets/images/menus/skilltrees/character+skill 4x3 *.png
# Painel direito ancorado a rect.right:
#   x = rect.right - (1024.0 - base_x) * scale
#   y = rect.top   + base_y * scale

# Aba de skills — barra de tabs no topo do painel direito (base 1024x768).
SKILL_TAB_COORDS: dict[int, tuple[float, float]] = {
    1: (748.5, 78.5),
    2: (848.5, 78.5),
    3: (948.5, 78.5),
}

# Grid de skills: 6 linhas × 3 colunas (cols 0, 1, 2 internamente; visualmente 1, 2, 3).
SKILL_GRID_COL_X: dict[int, float] = {
    0: 762.5,
    1: 848.5,
    2: 934.5,
}
SKILL_GRID_ROW_Y: dict[int, float] = {
    0: 129.5,
    1: 204.5,
    2: 278.5,
    3: 354.5,
    4: 429.5,
    5: 505.5,
}

# Nó rosa de level-up aparece ABAIXO do nó da skill (quando skill_points_remaining > 0).
SKILL_PINK_OFFSET_Y: float = 33.5


def skill_tab_point(rect: Rect, tab_index: int) -> tuple[int, int]:
    """Coordenada (x, y) de uma aba de habilidades (1, 2 ou 3) no painel S."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(tab_index, 1, 3))
    base_x, base_y = SKILL_TAB_COORDS.get(idx, (848.5, 119.0))
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    return (int(clamp(round(x), rect.left + 2, rect.right - 2)),
            int(clamp(round(y), rect.top + 2, rect.bottom - 2)))


def skill_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Coordenada (x, y) de um slot da skill tree (row 0..5, col 0..2).

    Usa índices base-0 internamente para compatibilidade com SKILL_TREE_LAYOUTS.
    """
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 0, 5))
    c = int(clamp(col, 0, 2))
    base_x = SKILL_GRID_COL_X.get(c, 848.5)
    base_y = SKILL_GRID_ROW_Y.get(r, 163.0 + r * 60.0)
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    return (int(clamp(round(x), rect.left + 2, rect.right - 2)),
            int(clamp(round(y), rect.top + 2, rect.bottom - 2)))


def skill_slot_pink_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Coordenada (x, y) do nó rosa (level-up) abaixo de um slot de skill."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 0, 5))
    c = int(clamp(col, 0, 2))
    base_x = SKILL_GRID_COL_X.get(c, 848.5)
    base_y = SKILL_GRID_ROW_Y.get(r, 163.0 + r * 60.0) + SKILL_PINK_OFFSET_Y
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    return (int(clamp(round(x), rect.left + 2, rect.right - 2)),
            int(clamp(round(y), rect.top + 2, rect.bottom - 2)))


SKILL_SPELL_COLS_X: list[float] = [751.5, 815.5, 879.5, 943.5]
SKILL_SPELL_ROW_Y: float = 612.5


def skill_spell_slot_point(rect: Rect, slot_idx: int) -> tuple[int, int]:
    """Coordenada (x, y) de um dos 4 slots de Spells (feitiços) no rodapé do menu de skills (0..3)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(slot_idx, 0, 3))
    base_x = SKILL_SPELL_COLS_X[idx]
    base_y = SKILL_SPELL_ROW_Y
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    return (int(clamp(round(x), rect.left + 2, rect.right - 2)),
            int(clamp(round(y), rect.top + 2, rect.bottom - 2)))


# ==============================================================================
# Layouts das Skill Trees por personagem e aba
# ==============================================================================
# Cada linha é uma lista de 3 elementos (col-0, col-1, col-2).
#   None  → célula vazia (sem skill, sem nó de navegação).
#   int   → coluna real (0, 1 ou 2) presente na imagem de referência — usamos o
#           próprio índice para confirmar a presença: valor == índice da coluna.
# O nó LARANJA de cada linha é calculado em runtime por skill_bridge_col():
#   é sempre a primeira coluna não-None da linha (leftmost).

SKILL_TREE_LAYOUTS: dict[str, dict[str, list[list[int | None]]]] = {
    "destroyer": {
        "berserker": [
            [None, 1, 2],    # L1: col-2, col-3
            [None, 1, None], # L2: col-2
            [0, None, 2],    # L3: col-1, col-3
            [None, 1, None], # L4: col-2
            [None, 1, 2],    # L5: col-2, col-3
            [0, 1, None],    # L6: col-1, col-2
        ],
        "titan": [
            [None, 1, None], # L1: col-2
            [None, 1, 2],    # L2: col-2, col-3
            [0, 1, 2],       # L3: col-1, col-2, col-3
            [None, 1, None], # L4: col-2
            [0, None, 2],    # L5: col-1, col-3
            [None, 1, None], # L6: col-2
        ],
        "spectral": [
            [None, 1, None], # L1: col-2
            [None, 1, 2],    # L2: col-2, col-3
            [0, 1, 2],       # L3: col-1, col-2, col-3
            [0, None, None], # L4: col-1
            [None, 1, None], # L5: col-2
            [None, 1, 2],    # L6: col-2, col-3
        ],
    },
    "vanquisher": {
        "marksman": [
            [0, 1, None],    # L1: col-1, col-2
            [None, 1, 2],    # L2: col-2, col-3
            [0, 1, 2],       # L3: col-1, col-2, col-3
            [None, 1, None], # L4: col-2
            [None, None, 2], # L5: col-3 (único → será laranja)
            [None, 1, None], # L6: col-2
        ],
        "rogue": [
            [None, 1, None], # L1: col-2
            [None, 1, 2],    # L2: col-2, col-3
            [None, 1, 2],    # L3: col-2, col-3
            [None, None, 2], # L4: col-3 (único → será laranja)
            [0, 1, None],    # L5: col-1, col-2
            [0, 1, None],    # L6: col-1, col-2
        ],
        "arbiter": [
            [None, 1, None], # L1: col-2
            [0, 1, None],    # L2: col-1, col-2
            [None, None, 2], # L3: col-3 (único → será laranja)
            [None, 1, 2],    # L4: col-2, col-3
            [0, 1, None],    # L5: col-1, col-2
            [None, 1, 2],    # L6: col-2, col-3
        ],
    },
    "alchemist": {
        "arcane": [
            [None, 1, 2],    # L1: col-2, col-3
            [0, None, 2],    # L2: col-1, col-3
            [0, 1, 2],       # L3: col-1, col-2, col-3
            [None, 1, None], # L4: col-2
            [0, None, 2],    # L5: col-1, col-3
            [None, 1, None], # L6: col-2
        ],
        "lore": [
            [None, 1, None], # L1: col-2
            [0, None, 2],    # L2: col-1, col-3
            [None, 1, 2],    # L3: col-2, col-3
            [0, None, 2],    # L4: col-1, col-3
            [0, None, 2],    # L5: col-1, col-3
            [None, 1, 2],    # L6: col-2, col-3
        ],
        "battle": [
            [None, 1, 2],    # L1: col-2, col-3
            [0, None, 2],    # L2: col-1, col-3
            [None, 1, 2],    # L3: col-2, col-3
            [0, None, 2],    # L4: col-1, col-3
            [0, None, 2],    # L5: col-1, col-3
            [None, 1, None], # L6: col-2
        ],
    },
}

# Mapa de abas por personagem: índice 1, 2, 3 → nome interno.
SKILL_TAB_NAMES: dict[str, dict[int, str]] = {
    "destroyer":  {1: "berserker", 2: "titan",    3: "spectral"},
    "vanquisher": {1: "marksman",  2: "rogue",    3: "arbiter"},
    "alchemist":  {1: "arcane",    2: "lore",     3: "battle"},
}


def skill_bridge_col(row_layout: list[int | None]) -> int | None:
    """Retorna o índice da coluna laranja (leftmost com skill) de uma linha.

    O nó laranja é sempre o mais próximo da borda esquerda em cada linha —
    mesmo que seja a Col-3, se for o único nó presente.
    Retorna None se a linha estiver completamente vazia.
    """
    for col_idx, val in enumerate(row_layout):
        if val is not None:
            return col_idx
    return None


def skill_snap_col(row_layout: list[int | None], current_col: int) -> int | None:
    """Snap dinâmico ↑↓: retorna a coluna mais próxima disponível na linha destino.

    Regra de desempate: entre colunas igualmente próximas, prefere a esquerda (menor índice).
    Retorna None se a linha estiver completamente vazia.
    """
    filled = [i for i, v in enumerate(row_layout) if v is not None]
    if not filled:
        return None
    if current_col in filled:
        return current_col
    return min(filled, key=lambda c: (abs(c - current_col), c))


def skill_layout_for(char_class: str, tab_index: int) -> list[list[int | None]] | None:
    """Retorna o layout de linhas da aba `tab_index` (1-3) do personagem `char_class`.

    Retorna None se a combinação não for reconhecida.
    """
    cls = char_class.lower()
    tab_names = SKILL_TAB_NAMES.get(cls)
    if tab_names is None:
        return None
    tab_name = tab_names.get(tab_index)
    if tab_name is None:
        return None
    return SKILL_TREE_LAYOUTS.get(cls, {}).get(tab_name)


# ==============================================================================
# Menu de Missões / Quests (Q) (Base de referência 1024×768 — painel direito)
# ==============================================================================
# Calibrado a partir de assets/images/menus/quest/Quest-menu-open.png
# e assets/images/menus/quest/Quest-menu-plus-other-menus-open.png
# Painel direito ancorado a rect.right:
# x = rect.right - (1024.0 - base_x) * scale
# y = rect.top + base_y * scale

QUEST_ROW_ORIGIN = (976.5, 106.5)
QUEST_ROW_STEP_Y = 25.0
QUEST_ROW_COUNT = 6

QUEST_REWARD_POINT = (964.5, 573.5)
QUEST_ABANDON_POINT = (894.5, 646.5)


def quest_slot_point(rect: Rect, index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de uma linha de missão na lista (index 0..5)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(index, 0, QUEST_ROW_COUNT - 1))
    base_x = QUEST_ROW_ORIGIN[0]
    base_y = QUEST_ROW_ORIGIN[1] + idx * QUEST_ROW_STEP_Y
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def quest_reward_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do slot de recompensa de item do menu de missões."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    x = rect.right - (1024.0 - QUEST_REWARD_POINT[0]) * scale
    y = rect.top + QUEST_REWARD_POINT[1] * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def quest_abandon_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão Abandon (Abandonar Missão)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    x = rect.right - (1024.0 - QUEST_ABANDON_POINT[0]) * scale
    y = rect.top + QUEST_ABANDON_POINT[1] * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


