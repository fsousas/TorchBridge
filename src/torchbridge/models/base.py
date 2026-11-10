from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Lock
from typing import Any


from ..resources import resource_root


def get_project_root() -> Path:
    """Retorna o diretório raiz do projeto (suporta PyInstaller frozen, wheel e checkout)."""
    return resource_root()


@dataclass(frozen=True)
# Área retangular útil (cliente) da janela do jogo, em coordenadas absolutas de tela.
class Rect:
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0

    @property
    # Borda direita (exclusiva), derivada de left + width.
    def right(self) -> int:
        return self.left + self.width

    @property
    # Borda inferior (exclusiva), derivada de top + height.
    def bottom(self) -> int:
        return self.top + self.height

    @property
    # A janela só é utilizável com área positiva; retângulo vazio = 'sem jogo'.
    def valid(self) -> bool:
        return self.width > 0 and self.height > 0

    # Teste de ponto dentro da área [left, right) × [top, bottom).
    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


def controller_type_from_name(name: str) -> str:
    """Classifica o controle como 'playstation', 'nintendo' ou 'xbox' (padrão) a partir do nome."""
    if not name:
        return "xbox"
    lower = name.lower()
    if any(k in lower for k in ("xbox", "xinput", "microsoft")):
        return "xbox"
    if any(k in lower for k in ("dualsense", "dualshock", "playstation", "ps5", "ps4", "ps3", "sony")) or lower.strip() == "wireless controller":
        return "playstation"
    if any(k in lower for k in ("switch", "joy-con", "pro controller", "nintendo")):
        return "nintendo"
    return "xbox"


@dataclass(frozen=True)
# Fotografia imutável do controle em um tick: eixos (-1..1), gatilhos (0..1) e botões.
class ControllerState:
    connected: bool = False
    name: str = ""
    mapping: str = ""
    controller_type: str = "xbox"
    device_guid: str = ""
    instance_id: int | None = None
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0
    # Botões pressionados como frozenset de nomes lógicos ('a', 'lb', 'dpad_up'...) — imutável e barato de comparar.
    buttons: frozenset[str] = field(default_factory=frozenset)

    # Atalho: o botão lógico está pressionado neste tick?
    def pressed(self, button: str) -> bool:
        return button in self.buttons



@dataclass(frozen=True)
# Estado visual imutável que o motor publica para o overlay Qt desenhar.
class OverlaySnapshot:
    engine_error: str = ""
    controller_devices: tuple[tuple[str, str], ...] = ()
    enabled: bool = True
    game_found: bool = False
    game_active: bool = False
    game_rect: Rect = field(default_factory=Rect)
    game_hwnd: int | None = None
    game_pid: int | None = None
    controller_connected: bool = False
    controller_name: str = ""
    controller_mapping: str = ""
    controller_type: str = "xbox"
    mode: str = "direct"
    radial_active: bool = False
    radial_selection: int | None = None
    # Sublinha de pet actions (4 quadradinhos) visível sob o slot 'P' da roda.
    pet_submenu_open: bool = False
    # Quadrado (1..4) com o marcador na sublinha de pet actions; None quando fechada.
    pet_submenu_selection: int | None = None
    # Painéis laterais abertos pela roda: índice 0 = esquerdo (C/P), 1 = direito (I/S/Q/J); "" = fechado.
    active_panels: list[str] = field(default_factory=lambda: ["", ""])
    aim_x: int | None = None
    aim_y: int | None = None
    toast_text: str = ""
    toast_until: float = 0.0
    # Estado do jogo lido diretamente da memória RAM
    memory_state_desc: str = ""
    memory_is_in_game: bool = False
    memory_is_loading: bool = False
    memory_is_menu_open: bool = False
    memory_open_menus: list[str] = field(default_factory=list)
    char_name_len: int = 0
    title_menu_focus: str | None = None
    char_create_focus: str | None = None
    virtual_keyboard_open: bool = False
    virtual_keyboard_target: str = ""
    virtual_keyboard_focus: tuple[int, int] = (3, 1)
    virtual_keyboard_caps_state: str = "default"
    virtual_keyboard_pressed_key: str | None = None
    virtual_keyboard_press_id: int = 0
    difficulty_focus: str | None = None
    dialog_focus: str | None = None
    dialog_type: str = ""
    dialog_buttons: list[str] = field(default_factory=list)
    dialog_has_reward: bool = False
    pause_menu_focus: str | None = None
    death_screen_focus: str | None = None
    load_char_focus: str | None = None
    load_char_delete_open: bool = False
    settings_focus: str | None = None
    settings_dropdown: str | None = None
    settings_dropdown_idx: int = 0
    settings_slider_dragging: bool = False
    settings_sound_vol: float = 1.0
    settings_music_vol: float = 1.0
    fishing_focus: str | None = None
    modal_confirm_focus: str | None = None
    inventory_open: bool = False
    inventory_tab: str | None = None
    inventory_focus: str | None = None
    pet_inventory_open: bool = False
    pet_inventory_tab: str | None = None
    pet_inventory_focus: str | None = None
    stash_open: bool = False
    stash_tab: str | None = None
    stash_focus: str | None = None
    merchant_open: bool = False
    merchant_tab: str | None = None
    merchant_focus: str | None = None
    merchant_npc_name: str = ""
    crafting_open: bool = False
    crafting_menu: str | None = None
    crafting_focus: str | None = None
    # Menu de Personagem (C): aberto, foco atual e nó de ponte ativo.
    # char_menu_focus: atributo com foco ("strength", "dexterity", "magic", "defense",
    #   "<attr>_bridge" para o nó laranja, ou "<attr>_pink" para o nó rosa).
    char_menu_open: bool = False
    char_menu_focus: str | None = None
    # Árvore de Habilidades (S): aberto, aba ativa (1..3), foco atual.
    # skill_focus: "tab" para a barra de abas, (row, col) para um slot, ou
    #   (row, col, "pink") para o nó rosa de level-up.
    skill_menu_open: bool = False
    skill_tab: int = 1   # aba ativa: 1, 2 ou 3
    skill_focus: str | None = None
    char_class: str = ""
    attr_points_remaining: int = 0
    skill_points_remaining: int = 0
    skill_upgradeable: dict[tuple[int, int], bool] = field(default_factory=dict)
    # Menu de Missões / Quests (Q)
    quest_menu_open: bool = False
    quest_focus: str | None = None  # "quest_0".."quest_5", "reward", "abandon"
    quest_count: int = 0
    quest_selected_idx: int = 0
    quest_visible_rows: int = 0
    quest_can_abandon: bool = False
    quest_has_item_reward: bool = False
    shortcut_config_active: bool = False
    shortcut_node_focus: int = 0
    shortcut_info_focus: bool = False
    shortcut_grid_active: bool = False
    shortcut_grid_pos: tuple[int, int] = (0, 0)
    shortcut_grid_cols: int = 8
    shortcut_grid_rows: int = 3
    shortcut_grid_counts: tuple[int, ...] = (8, 8, 8)
    # Tela de Boas-Vindas / Onboarding (TB-17)
    welcome_screen_open: bool = False
    welcome_screen_page: int = 1
    welcome_screen_total_pages: int = 9
    welcome_screen_focus: str = "next"
    welcome_screen_can_close: bool = False



# Ponte thread-safe entre o motor (thread 'TorchBridgeInput') e a thread da UI (Qt).
class SharedOverlayState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot = OverlaySnapshot()
        self._keyboard_events: list[tuple[str, int, int]] = []

    def keyboard_event(self, kind: str, x: int, y: int) -> None:
        with self._lock:
            self._keyboard_events.append((kind, x, y))

    def take_keyboard_events(self) -> list[tuple[str, int, int]]:
        with self._lock:
            events, self._keyboard_events = self._keyboard_events, []
            return events

    # Leitura atômica do último snapshot publicado.
    def get(self) -> OverlaySnapshot:
        with self._lock:
            return self._snapshot

    # Publica um novo snapshot com apenas os campos alterados (dataclasses.replace).
    def update(self, **changes: object) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)

    # Publica uma mensagem temporária com validade em segundos; o overlay apaga sozinho.
    def toast(self, text: str, seconds: float = 2.2) -> None:
        self.update(toast_text=text, toast_until=time.monotonic() + seconds)

