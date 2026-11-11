from __future__ import annotations

import logging
import threading
import sys
import time

from ..config import ConfigManager
from ..controller import ControllerHub
from ..input_session import (
    InputCancelled,
    InputSession,
)
from ..mathutils import (
    clamp,
    cursor_delta,
    radial_deadzone,
    radial_slot,
)
from ..memory import (
    GameMemoryState,
    TorchlightMemoryReader,
)
from ..native_input import NativeInputClient, ACTIVE, DIRECT, WALKING, ALLOW_INTERACTION
from ..models import (
    CHAR_ATTR_ORDER,
    CHAR_MENU_NODES_HAS_POINTS,
    CHAR_MENU_NODES_NO_POINTS,
    CHAR_MENU_ROWS_HAS_POINTS,
    CHAR_MENU_ROWS_NO_POINTS,
    ControllerState,
    INVENTORY_UPPER_NAV_MAP,
    KEYBOARD_LAYOUT,
    MERCHANT_GRID_COLS,
    MERCHANT_GRID_ROWS,
    PET_SUBMENU_COUNT,
    PET_SUBMENU_DEFAULT,
    PET_UPPER_NAV_MAP,
    QUEST_ROW_COUNT,
    Rect,
    SETTINGS_BUTTONS,
    SETTINGS_DROPDOWNS,
    SETTINGS_NAV_MAP,
    SHORTCUT_HUD_NODES,
    SKILL_GRID_COL_X,
    SKILL_SPELL_COLS_X,
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    STASH_GRID_COLS,
    STASH_GRID_ROWS,
    SharedOverlayState,
    both_panels_open,
    char_attr_bridge_point,
    char_attr_pink_point,
    char_attr_point,
    char_create_button_point,
    char_create_text_field_rect,
    char_menu_point,
    click_zone,
    crafting_button_point,
    crafting_slot_point,
    death_screen_button_point,
    dialog_button_point,
    difficulty_menu_button_point,
    fishing_hook_point,
    hud_purple_button_point,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    load_char_button_point,
    load_hud_mask,
    merchant_slot_point,
    merchant_tab_point,
    modal_ok_point,
    panels_x_shift,
    pause_menu_button_point,
    pet_click_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    pet_inventory_upper_point,
    pet_submenu_open,
    quest_abandon_point,
    quest_reward_point,
    quest_slot_point,
    settings_button_point,
    settings_dropdown_option_point,
    shortcut_grid_cell_point,
    shortcut_info_node_point,
    shortcut_node_point,
    skill_bridge_col,
    skill_layout_for,
    skill_slot_pink_point,
    skill_slot_point,
    skill_snap_col,
    skill_spell_slot_point,
    skill_tab_point,
    stash_upper_slot_point,
    title_menu_button_point,
    toggle_panel,
    virtual_keyboard_character,
    virtual_keyboard_grid_to_key,
    virtual_keyboard_key_cursor_point,
    virtual_keyboard_key_rect,
    virtual_keyboard_target_rect,
)
from ..platform import (
    InputInjector,
    WindowLocator,
    begin_high_resolution_timer,
    end_high_resolution_timer,
)
from dataclasses import replace
from typing import Any

log = logging.getLogger(__name__)


class BridgeEngineCore(threading.Thread):
    """Núcleo do motor: thread daemon, ciclo de vida e despacho de ticks."""

    TRIGGER_ACTIVE_THRESHOLD = 0.50
    KEYBOARD_REPEAT_DELAY = 0.38
    KEYBOARD_REPEAT_INTERVAL = 0.065
    _MODIFIER_CLICK_HOLD = 0.12
    _MODIFIER_RELEASE_HOLD = 0.18
    _MODIFIER_RELEASE_TIMEOUT = 0.05
    _SKILL_REPEAT_INTERVAL = 0.12
    _MODIFIER_RELEASE_RETRY_INTERVAL = 0.005
    PET_PANEL_CLOSE_DELAY = 0.5

    def __init__(self, config: ConfigManager, shared: SharedOverlayState) -> None:
        super().__init__(name="TorchBridgeInput", daemon=True)
        self.config = config
        self.shared = shared
        # Leitor de memória direto do processo do jogo
        self.memory = TorchlightMemoryReader()
        self.native_input = NativeInputClient()
        self._native_direction = (0., 0.)
        self._native_heading = None
        self._native_heading_scene = None
        self._memory_state = GameMemoryState()
        self._memory_last_read = 0.0
        self._world_click = None
        initial = config.get()
        target = initial["target"]
        # Localizador da janela do Torchlight + injetor de entrada do Windows.
        engine_mod = sys.modules.get("torchbridge.engine")
        locator_cls = getattr(engine_mod, "WindowLocator", WindowLocator)
        injector_cls = getattr(engine_mod, "InputInjector", InputInjector)
        self.locator = locator_cls(target["process_names"], target["window_titles"])
        self.injector = injector_cls()
        # Parada pedida pela UI; locks protegem estado lido por outra thread.
        self._stop_event = threading.Event()
        self._input_context: tuple | None = None
        self._enabled_lock = threading.Lock()
        self._enabled = True
        # Modo atual: 'direct' (movimento direto) ou 'cursor' (menus/inventário).
        self._mode = initial["movement"]["initial_mode"]
        # Estado do tick anterior: detecta bordas (transições), nunca auto-repeat.
        self._previous = ControllerState()
        # Clique esquerdo retido no tick anterior (borda de subida do clique).
        self._previous_left_pressed = False
        # Movimento direto ativo no tick anterior (borda de descida -> devolver o cursor ao centro).
        self._direct_move_active = False
        # Âncora (x, y em px) do último movimento direto: pra onde o cursor volta ao soltar o stick.
        self._last_anchor: tuple[int, int] | None = None
        # Teclas e botões de mouse retidos agora (liberados todos na perda de foco/saída).
        self._held_keys: set[str] = set()
        self._skill_repeat_at: dict[str, float] = {}
        self._skill_repeat_sources: dict[str, str] = {}
        self._held_mouse: set[str] = set()
        # Nome do último controle visto — detecta troca/conexão/desconexão.
        # Última recarga do perfil (no mínimo 1 s entre tentativas).
        self._last_reload = 0.0
        self._last_controller_name = ""
        self._last_controller_instance: int | None = None
        self._needs_rearm = True
        self._blocked_buttons: set[str] = set()
        self._blocked_lt = False
        self._blocked_rt = False
        # Borda da detecção do jogo (aviso único de 'Torchlight detectado').
        self._game_was_found = False
        self._last_game_pid: int | None = None
        # Estado do combo Back+Start (calibração): visto?, desde quando?, já disparou?
        # Setor da roda selecionado enquanto LB estiver segurado.
        self._radial_selection: int | None = None
        self._radial_dismissed: bool = False
        self._radial_cancel_lock: int | None = None
        self._rescan_requested: bool = False
        # Modo de configuração de atalhos inferior (spotlight ativo).
        self._shortcut_config_active: bool = False
        self._shortcut_node_focus: int = 0
        self._shortcut_info_focus: bool = False
        self._shortcut_grid_active: bool = False
        self._shortcut_grid_row: int = 0
        self._shortcut_grid_col: int = 0
        self._shortcut_grid_cols: int = 8
        self._shortcut_grid_rows: int = 3
        self._shortcut_grid_counts: tuple[int, ...] = (8, 8, 8)
        self._previous_physical_esc: bool = False
        # Toggle interno da sublinha de pet actions (4 quadradinhos sob o slot 'P'): d-pad
        # para BAIXO abre, para CIMA fecha. Desmarca o setor 'P' ou fecha a roda: a sublinha
        # some automaticamente (estado interno volta a False).
        self._pet_submenu: bool = False
        # Quadrado (1..4) com o marcador na sublinha; ao abrir, nasce em PET_SUBMENU_DEFAULT
        # (o 4º, embaixo do ícone P). D-pad ESQUERDO/DIRITO navega com wrap enquanto aberta.
        self._pet_submenu_selection: int = PET_SUBMENU_DEFAULT
        # Painéis laterais abertos pela roda: índice 0 = esquerdo (C/P), 1 = direito (I/S/Q/J); "" = fechado.
        self._active_panels: list[str] = ["", ""]
        # Painéis no tick ativo anterior: o remap contextual de B/Y só vale com o
        # estado ESTÁVEL — abrir/fechar o painel no mesmo tick (roda/ESC) não conta
        # como "aberto" para a borda do B (senão o B abriria a ESC em vez do 2).
        self._previous_panels: tuple[str, str] = ("", "")
        # Gatilhos no tick anterior (histerese em TRIGGER_ACTIVE_THRESHOLD): bordas de
        # RT (toque 4) e do combo LT+RT (toque 0). ATUALIZADAS A CADA TICK EM run() —
        # também com o jogo sem foco — para um gatilho segurado através de uma perda
        # de foco não vazar um toque falso ao retomar.
        self._previous_lt_active = False
        self._previous_rt_active = False
        # Estado corrente/bordas calculado em _update_trigger_edges (todo tick).
        self._lt_current = False
        self._lt_edge_up = False
        self._rt_edge_up = False
        # Clique modificado em curso (Shift/Ctrl + left, remap contextual de Y / LT+A):
        # (modificador, t de início). Os ticks intermediários seguram o modificador
        # FÍSICAMENTE (e o left, se a sequência baixou) — o jogo amostra a tecla por
        # frame, então o clique precisa nascer com o modificador ainda pressionado;
        # soltar no mesmo tick fazia o jogo lê-lo como clique simples (bug, ago/2026).
        self._modifier_seq: tuple[str, float] | None = None
        # Flags de fase da sequência: a sequência baixou o left? já soltou?
        self._modifier_left_down = False
        self._modifier_left_up = False
        # Sequência de clique do pet em andamento: (x, y do alvo, retorno_x, retorno_y,
        # letra do painel esquerdo pendente, t de início). Enquanto existe, o cursor é
        # exclusivo da sequência — o stick não move o mouse — e o clique esquerdo
        # retido pelo click-to-move não é tocado. None = nada em curso.
        self._pet_click_seq: tuple[int, int, int, int, str | None, float] | None = None
        # Flags de fase da sequência (rearmadas ao armar uma nova): botão esquerdo
        # já foi baixado? a letra do painel pendente já disparou?
        self._pet_click_down = False
        self._pet_click_panel_done = False
        # Sequência de clique do ponto roxo (#8A38F5) da HUD inferior (D-pad esquerdo no overworld):
        # (target_x, target_y, return_x, return_y, t0).
        self._hud_click_seq: tuple[int, int, int, int, float] | None = None
        self._hud_click_down = False
        self._hud_click_up = False
        self._hud_click_returned = False
        self._center_combo_seen = False
        self._center_combo_started: float | None = None
        self._center_combo_triggered = False
        # Silhueta verde da HUD inferior (área que não fecha painéis): rasterizada uma
        # vez aqui e passada ao click_zone em cada borda de clique. None = sem asset
        # (comportamento antigo: clique central com ambos abertos fecha tudo).
        self._hud_mask = load_hud_mask()
        # Navegação no Menu Inicial (Title Screen) via D-pad
        self._title_screen_initialized = False
        self._title_focus = "continue"
        # Navegação na Criação de Personagem (state_id == 1) via D-pad
        self._char_create_initialized = False
        self._char_create_focus = "destroyer"
        self._keyboard_confirm_latched = False
        self._keyboard_mouse_down = False
        self._keyboard_pressed_until = 0.0
        self._virtual_keyboard_open = False
        self._virtual_keyboard_target = ""
        self._virtual_keyboard_focus = (3, 1)
        self._virtual_keyboard_caps_state = "default"
        self._virtual_keyboard_pressed_key: str | None = None
        self._keyboard_cancel_repeat_at = 0.0
        self._keyboard_confirm_repeat_at = 0.0
        # Navegação na Seleção de Dificuldade (state_id == 2) via D-pad
        self._difficulty_initialized = False
        self._difficulty_focus = "hardcore"
        # Navegação em Diálogos e Telas de História via D-pad
        self._dialog_initialized = False
        self._dialog_focus: str | None = None
        self._last_dialog_type = ""
        # Navegação no Menu de Pause (COptionsMenu / Options) via D-pad
        self._pause_menu_initialized = False
        self._pause_focus = "return_to_game"
        # Navegação na Tela de Morte / Respawn em jogo via D-pad
        self._death_screen_initialized = False
        self._death_screen_focus: str | None = None
        # Navegação na Tela de Carregar Personagem (state_id == 3) via D-pad
        self._load_char_initialized = False
        self._load_char_focus: str | None = None
        self._load_char_delete_dialog_open = False
        self._load_char_last_slot = "slot_1"
        self._load_char_scroll_offset = 0
        self._load_char_dialog_debounce: float = 0.0
        self._last_state_id = -1
        # Navegação na Tela de Configurações (Settings) via D-pad
        self._settings_initialized = False
        self._settings_focus: str | None = None
        self._settings_dropdown: str | None = None
        self._settings_dropdown_idx = 0
        self._settings_slider_dragging = False
        self._settings_slider_last_stick: float = 0.0
        self._settings_sound_vol: float = 1.0
        self._settings_music_vol: float = 1.0
        # Navegação na Interface de Pesca e Modal de Confirmação (Peixe/Mensagens)
        self._fishing_initialized: bool = False
        self._fishing_closing: bool = False
        self._modal_confirm_initialized: bool = False
        # Navegação no Inventário do Jogador (Abas + Grid 3x7 + Equipamentos superiores)
        self._inventory_initialized: bool = False
        self._inventory_tab: str | None = None  # "tab-1", "tab-2", "tab-3"
        self._inventory_focus: tuple[int, int] | str | None = None
        # Navegação no Menu do Pet (Abas + Grid 3x7 + Equipamentos/Spells superiores)
        self._pet_inventory_initialized: bool = False
        self._pet_inventory_tab: str | None = None  # "tab-1", "tab-2", "tab-3"
        self._pet_inventory_focus: tuple[int, int] | str | None = None
        # Navegação no Menu do Baú (Stash 6x7 superior + Pet 3x7 inferior + Abas)
        self._stash_initialized: bool = False
        self._stash_tab: str | None = None  # "tab-1", "tab-2", "tab-3"
        self._stash_focus: tuple[str, int, int] | None = None
        # Navegação no Menu do Mercador (Lojas 6x7 superior com 3 abas rosa + Pet 3x7 inferior)
        self._merchant_initialized: bool = False
        self._merchant_tab: str | None = None  # "tab-1", "tab-2", "tab-3"
        self._merchant_focus: tuple[Any, ...] | None = None
        self._merchant_npc_name: str = ""
        # Navegação nos Menus de Crafting (Transmutador, Sockets, Encantador)
        self._crafting_initialized: bool = False
        self._crafting_menu: str | None = None
        self._crafting_focus: str | None = None
        # Navegação no Menu de Personagem (C) — atributos Strength/Dex/Magic/Defense
        # e pontos de atributo (nó rosa à direita quando points_remaining > 0).
        self._char_menu_initialized: bool = False
        self._char_menu_focus: str = "strength"  # atributo com foco atual
        # Navegação na Árvore de Habilidades (S) — 6 linhas × 3 colunas por aba.
        # _skill_focus_row/col: posição na grade (base-0). "tab" indica foco na tab bar.
        # _skill_in_tabbar: cursor na barra de abas (não em um slot).
        # _skill_in_pink: cursor no nó rosa de level-up (abaixo do slot atual).
        self._skill_menu_initialized: bool = False
        self._skill_tab: int = 1           # aba ativa: 1, 2 ou 3
        self._skill_focus_row: int = 0     # linha atual base-0 (0 = L1)
        self._skill_focus_col: int = 1     # coluna atual base-0 (1 = Col-2, posição inicial)
        self._skill_in_tabbar: bool = False
        self._skill_in_pink: bool = False  # cursor no nó rosa de level-up
        self._skill_in_spells: bool = False # cursor nos feitiços (rodapé)
        self._skill_spell_idx: int = 0      # índice do slot de spell (0..3)
        self._skill_tab_debounce: float = 0.0 # debounce de troca de aba
        # Classe do personagem atual — lida da memória; necessária para skill_layout_for().
        # Valores esperados: "destroyer", "vanquisher", "alchemist" (ou "" se desconhecida).
        self._char_class: str = ""
        # Navegação no Menu de Missões / Quests (Q)
        self._quest_menu_initialized: bool = False
        self._quest_focus: str = "quest_0"
        self._last_quest_slot: int = 0
        self._quest_b_consumed: bool = False
        self._a_shift_held: bool = False

    def _reset_active_panels(self) -> None:
        self._active_panels = ["", ""]
        self.shared.update(active_panels=list(self._active_panels))

    def _reset_radial_session(self) -> None:
        self._reset_transient_navigation()
        self._reset_active_panels()
        self._radial_selection = None
        self._radial_dismissed = False
        self._radial_cancel_lock = None
        self._dialog_initialized = False
        self._dialog_focus = None
        self._last_dialog_type = ""
        self._pause_menu_initialized = False
        self._pause_focus = None
        self._load_char_initialized = False
        self._load_char_focus = None
        self._load_char_delete_dialog_open = False
        self._load_char_scroll_offset = 0
        self._load_char_dialog_debounce = 0.0
        self._settings_initialized = False
        self._settings_focus = None
        self._settings_dropdown = None
        self._settings_dropdown_idx = 0
        self._settings_slider_dragging = False
        self._settings_slider_last_stick = 0.0
        self._inventory_initialized = False
        self._inventory_tab = None
        self._inventory_focus = None
        self._pet_inventory_initialized = False
        self._pet_inventory_tab = None
        self._pet_inventory_focus = None
        self._stash_initialized = False
        self._stash_tab = None
        self._stash_focus = None
        self._merchant_initialized = False
        self._merchant_tab = None
        self._merchant_focus = None
        self._merchant_npc_name = ""
        self._crafting_initialized = False
        self._crafting_menu = None
        self._crafting_focus = None
        self._char_class = ""
        self._char_menu_initialized = False
        self._char_menu_focus = "strength"
        self._skill_menu_initialized = False
        self._skill_tab = 1
        self._skill_focus_row = 0
        self._skill_focus_col = 1
        self._skill_in_tabbar = False
        self._skill_in_pink = False
        self._skill_in_spells = False
        self._skill_spell_idx = 0
        self.shared.update(
            char_class="",
            radial_selection=None,
            pause_menu_focus=None,
            death_screen_focus=None,
            load_char_focus=None,
            load_char_delete_open=False,
            settings_focus=None,
            settings_dropdown=None,
            settings_dropdown_idx=0,
            settings_slider_dragging=False,
            fishing_focus=None,
            modal_confirm_focus=None,
            inventory_open=False,
            inventory_tab=None,
            inventory_focus=None,
            pet_inventory_open=False,
            pet_inventory_tab=None,
            pet_inventory_focus=None,
            stash_open=False,
            stash_tab=None,
            stash_focus=None,
            merchant_open=False,
            merchant_tab=None,
            merchant_focus=None,
            merchant_npc_name="",
            crafting_open=False,
            crafting_menu=None,
            crafting_focus=None,
            char_menu_open=False,
            char_menu_focus=None,
            skill_menu_open=False,
            skill_tab=1,
            skill_focus=None,
            quest_menu_open=False,
            quest_focus=None,
            quest_count=0,
            quest_selected_idx=0,
            quest_visible_rows=0,
            quest_can_abandon=False,
            quest_has_item_reward=False,
        )
        self._quest_menu_initialized = False
        self._quest_focus = "quest_0"
        self._last_quest_slot = 0
        self._quest_b_consumed = False
        self._fishing_initialized = False
        self._modal_confirm_initialized = False
        self._a_shift_held = False

    def stop(self) -> None:
        self._stop_event.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._enabled_lock:
            # Escrita protegida: a UI e a thread leem este valor.
            self._enabled = enabled
        if not enabled:
            self.shared.toast("TorchBridge pausado")
        else:
            self.shared.toast("TorchBridge ativado")

    def is_enabled(self) -> bool:
        with self._enabled_lock:
            return self._enabled

    def _set_key(self, name: str, desired: bool) -> None:
        # Binding vazio/ausente no perfil: ignora silenciosamente.
        if not isinstance(name, str) or not name.strip():
            return
        normalized = name.strip().upper()
        try:
            # Borda de subida: tecla ainda não retida → pressiona e registra.
            if desired and normalized not in self._held_keys:
                if self.injector.key(normalized, True):
                    self._held_keys.add(normalized)
            # Borda de descida: tecla retida → libera e esquece.
            elif not desired and normalized in self._held_keys:
                if self.injector.key(normalized, False):
                    self._held_keys.discard(normalized)
        # Tecla não suportada no perfil: avisa no log e segue o jogo.
        except ValueError as exc:
            log.warning("Binding de retenção ignorado: %s", exc)

    def _set_mouse(self, button: str, desired: bool) -> None:
        if desired and button not in self._held_mouse:
            if self.injector.mouse_button(button, True):
                self._held_mouse.add(button)
        elif not desired and button in self._held_mouse:
            if self.injector.mouse_button(button, False):
                self._held_mouse.discard(button)

    def _release_all(self) -> None:
        self._skill_repeat_at.clear()
        self._skill_repeat_sources.clear()
        self.native_input.close()
        self.shared.update(native_input_ready=False, native_highlight=False,
                           movement_direction=(0., 0.), movement_status="Movimento suspenso")
        self._needs_rearm = True
        self._cancel_world_interaction()
        self._reset_transient_navigation()
        if isinstance(self.injector, InputSession):
            self.injector.release_all()
        if getattr(self, "_a_shift_held", False):
            self._set_key("SHIFT", False)
            self._ensure_modifier_released("SHIFT")
            self._a_shift_held = False
        for key in tuple(self._held_keys):
            self._set_key(key, False)
        for button in tuple(self._held_mouse):
            self._set_mouse(button, False)
        # Interrupção no meio da sequência do pet: solta o botão esquerdo se o clique
        # estava no ar e descarta o restante (o cursor não volta ao centro — quem
        # deteve o foco detém o cursor; a sequência não sobrevive à pausa).
        if self._pet_click_seq is not None:
            if self._pet_click_down:
                self.injector.mouse_button("left", False)
                self._pet_click_down = False
            self._pet_click_seq = None
            self._pet_click_panel_done = False
        if self._hud_click_seq is not None:
            if self._hud_click_down and not self._hud_click_up:
                self.injector.mouse_button("left", False)
            self._hud_click_down = False
            self._hud_click_up = False
            self._hud_click_returned = False
            self._hud_click_seq = None
        # Interrompe o "movimento direto ativo" para o retorno ao centro não disparar no tick de volta.
        self._direct_move_active = False
        if self._settings_slider_dragging:
            self.injector.mouse_button("left", False)
            self._settings_slider_dragging = False
        # A roda fechou (interrupção): a sublinha de pet actions não pode sobreviver aberta.
        self._pet_submenu = False
        self._pet_submenu_selection = PET_SUBMENU_DEFAULT
        self._radial_dismissed = False
        self._radial_cancel_lock = None
        # Clique modificado em curso: solta o left da sequência (ele NÃO está em
        # _held_mouse) — o modificador já foi solto pelo laço de _held_keys acima.
        # A sequência não sobrevive à pausa (o que deteve o foco detém as entradas).
        if self._modifier_seq is not None:
            if self._modifier_left_down and not self._modifier_left_up:
                self.injector.mouse_button("left", False)
                self._modifier_left_up = True
            self._modifier_seq = None
        self.shared.update(
            radial_active=False,
            radial_selection=None,
            pet_submenu_open=False,
            pet_submenu_selection=None,
            aim_x=None,
            aim_y=None,
            title_menu_focus=None,
            char_create_focus=None,
            difficulty_focus=None,
            pause_menu_focus=None,
            death_screen_focus=None,
            load_char_focus=None,
            load_char_delete_open=False,
            inventory_open=False,
            inventory_tab=None,
            inventory_focus=None,
            pet_inventory_open=False,
            pet_inventory_tab=None,
            pet_inventory_focus=None,
            stash_open=False,
            stash_tab=None,
            stash_focus=None,
            merchant_open=False,
            merchant_tab=None,
            merchant_focus=None,
            merchant_npc_name="",
            crafting_open=False,
            crafting_menu=None,
            crafting_focus=None,
            char_menu_open=False,
            char_menu_focus=None,
            skill_menu_open=False,
            skill_tab=self._skill_tab,
            skill_focus=None,
        )
        self._inventory_initialized = False
        self._inventory_tab = None
        self._inventory_focus = None
        self._pet_inventory_initialized = False
        self._pet_inventory_tab = None
        self._pet_inventory_focus = None
        self._stash_initialized = False
        self._stash_tab = None
        self._stash_focus = None
        self._merchant_initialized = False
        self._merchant_tab = None
        self._merchant_focus = None
        self._merchant_npc_name = ""
        self._crafting_initialized = False
        self._crafting_menu = None
        self._crafting_focus = None
        self._char_menu_initialized = False
        self._char_menu_focus = "strength"
        self._skill_menu_initialized = False
        self._skill_focus_row = 0
        self._skill_focus_col = 1
        self._skill_in_tabbar = False
        self._skill_in_pink = False
        self._skill_in_spells = False
        self._skill_spell_idx = 0
        self._quest_menu_initialized = False
        self._quest_focus = "quest_0"
        self._last_quest_slot = 0
        self._quest_b_consumed = False

    def _reset_transient_navigation(self) -> None:
        self._virtual_keyboard_open = False
        self._virtual_keyboard_target = ""
        self._virtual_keyboard_pressed_key = None
        self._virtual_keyboard_focus = (3, 1)
        self._virtual_keyboard_caps_state = "default"
        self._keyboard_pressed_until = 0.0
        self._keyboard_cancel_repeat_at = 0.0
        self._keyboard_confirm_repeat_at = 0.0
        self._keyboard_confirm_latched = False
        self._keyboard_mouse_down = False
        self._title_screen_initialized = False
        self._char_create_initialized = False
        self._difficulty_initialized = False
        self._last_state_id = -1
        self._center_combo_seen = False
        self._center_combo_started = None
        self._center_combo_triggered = False
        self._dialog_initialized = False
        self._dialog_focus = None
        self._pause_menu_initialized = False
        self._load_char_initialized = False
        self._settings_initialized = False
        self._settings_focus = None
        self._settings_dropdown = None
        self._fishing_initialized = False
        self._modal_confirm_initialized = False
        self._previous_left_pressed = False
        self.shared.take_keyboard_events()
        self.shared.update(virtual_keyboard_open=False, virtual_keyboard_target="",
                           virtual_keyboard_pressed_key=None, char_create_focus=None,
                           title_menu_focus=None, difficulty_focus=None,
                           dialog_focus=None, dialog_type="", dialog_buttons=[],
                           settings_focus=None, settings_dropdown=None,
                           fishing_focus=None, modal_confirm_focus=None)

    def _input_allowed(self) -> bool:
        context = self._input_context
        if context is None:
            return False
        hub, hwnd, pid, instance, cfg = context
        if (self._stop_event.is_set() or not self.is_enabled() or
                not self.locator.is_foreground(hwnd) or
                self.locator.window_pid(hwnd) != pid):
            return False
        state = hub.poll(cfg["raw_controller"], cfg["input"]["device_guid"])
        return state.connected and state.instance_id == instance

    def _prepare_active_state(self, state: ControllerState) -> ControllerState:
        rearm = self._needs_rearm
        if rearm:
            self._blocked_buttons = set(state.buttons)
            self._blocked_lt = state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
            self._blocked_rt = state.rt >= self.TRIGGER_ACTIVE_THRESHOLD
        self._blocked_buttons.intersection_update(state.buttons)
        self._blocked_lt = self._blocked_lt and state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
        self._blocked_rt = self._blocked_rt and state.rt >= self.TRIGGER_ACTIVE_THRESHOLD
        state = replace(state, buttons=frozenset(state.buttons - self._blocked_buttons),
                        lt=0.0 if self._blocked_lt else state.lt,
                        rt=0.0 if self._blocked_rt else state.rt)
        if rearm:
            self._previous = state
            self._previous_lt_active = state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
            self._previous_rt_active = state.rt >= self.TRIGGER_ACTIVE_THRESHOLD
            self._needs_rearm = False
        return state

    def _wait_for_input(self, duration: float) -> None:
        """Keep calibrated timings while making every wait interruptible."""
        if self._input_context is None:
            time.sleep(duration)
            return
        deadline = time.monotonic() + duration
        while True:
            if not self._input_allowed():
                raise InputCancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._stop_event.wait(min(remaining, 1 / 120))

    def _tap_skill_binding(self, source: str, value: Any, now: float, edge: bool) -> None:
        if not isinstance(value, str):
            return
        key = value.strip().upper()
        if key not in "1234567890" or len(key) != 1:
            self._skill_repeat_sources.pop(source, None)
            if edge:
                self._tap_binding(value)
            return
        if edge:
            self._skill_repeat_sources[source] = key
        if self._skill_repeat_sources.get(source) != key:
            return  # A press consumed by a panel/item cannot become a held spell.
        if edge or now >= self._skill_repeat_at.get(key, float("-inf")):
            self._tap_binding(value)
            self._skill_repeat_at[key] = now + self._SKILL_REPEAT_INTERVAL

    def _tap_binding(self, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        normalized = value.strip().upper()
        if normalized in {"MOUSE_LEFT", "LEFT_CLICK", "LMB", "CLICK", "MOUSE1"}:
            if "left" in self._held_mouse:
                self.injector.mouse_button("left", False)
                self._held_mouse.discard("left")
            self.injector.mouse_button("left", True)
            self.injector.mouse_button("left", False)
            return
        if normalized in {"MOUSE_RIGHT", "RIGHT_CLICK", "RMB", "MOUSE2"}:
            if "right" in self._held_mouse:
                self.injector.mouse_button("right", False)
                self._held_mouse.discard("right")
            self.injector.mouse_button("right", True)
            self.injector.mouse_button("right", False)
            return
        temporarily_released: list[str] = []
        modifiers = ["ALT"]
        # Para TAB/ESC, libera também o SHIFT retido: senão o toque viraria Shift+Tab ou Shift+Esc.
        if normalized in {"TAB", "ESC", "ESCAPE"}:
            modifiers.append("SHIFT")
        try:
            # Solta temporariamente os modificadores retidos (ALT; + SHIFT para TAB/ESC)...
            for modifier in modifiers:
                if modifier in self._held_keys:
                    self.injector.key(modifier, False)
                    self._held_keys.discard(modifier)
                    temporarily_released.append(modifier)
            # ...envia o toque e, no finally, religa os modificadores que foram soltos.
            self.injector.tap(normalized)
        except ValueError as exc:
            log.warning("Binding ignorado: %s", exc)
        finally:
            for modifier in temporarily_released:
                if self.injector.key(modifier, True):
                    self._held_keys.add(modifier)

    def _update_trigger_edges(self, state: ControllerState) -> None:
        self._lt_was_active = self._previous_lt_active
        self._rt_edge_down = self._previous_rt_active and state.rt < self.TRIGGER_ACTIVE_THRESHOLD
        self._lt_current = state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
        self._lt_edge_up = self._lt_current and not self._previous_lt_active
        self._rt_edge_up = state.rt >= self.TRIGGER_ACTIVE_THRESHOLD and not self._previous_rt_active
        self._previous_lt_active = self._lt_current
        self._previous_rt_active = state.rt >= self.TRIGGER_ACTIVE_THRESHOLD

    def _start_modifier_click(self, modifier: str, now: float) -> None:
        # Borda de subida: se o modificador já está retido por outro caminho, não o
        # tocamos (não soltamos o hold alheio) — a sequência só solta o que baixou.
        self._modifier_seq = (modifier, now)
        self._modifier_left_down = False
        self._modifier_left_up = False
        if modifier not in self._held_keys:
            # Defensivo: limpa entrada fantasma (registrado sem o down ter saído).
            self._held_keys.discard(modifier)
            if self.injector.key(modifier, True):
                self._held_keys.add(modifier)
        # Botão esquerdo JÁ retido (click-to-move em curso): injetar o clique soltaria
        # o clique retido antes da hora (o left up mataria o movimento) — o clique já
        # "aconteceu" na descida do A; a sequência só acompanha a liberação do
        # modificador, sem tocar no botão.
        if "left" not in self._held_mouse:
            if self.injector.mouse_button("left", True):
                self._modifier_left_down = True

    def _handle_modifier_release(self, now: float) -> None:
        seq = self._modifier_seq
        if seq is None:
            return
        modifier, t0 = seq
        t = now - t0
        if t < 0:
            return
        if not self._modifier_left_up and t >= self._MODIFIER_CLICK_HOLD:
            if self._modifier_left_down:
                self.injector.mouse_button("left", False)
            self._modifier_left_up = True
        if t >= self._MODIFIER_RELEASE_HOLD:
            self._modifier_seq = None
            self._modifier_left_down = False
            # O modificador só foi baixado por esta sequência se segue retido — caso
            # contrário (retido por outro caminho) não o tocamos.
            if modifier in self._held_keys:
                self._held_keys.discard(modifier)
                self._ensure_modifier_released(modifier)

    def _ensure_modifier_released(self, modifier: str) -> None:
        deadline = time.monotonic() + self._MODIFIER_RELEASE_TIMEOUT
        self.injector.key(modifier, False)
        while self.injector.key_pressed(modifier):
            if time.monotonic() >= deadline:
                log.warning(
                    "Liberação física de %s não confirmada; o modificador pode continuar preso",
                    modifier,
                )
                break
            time.sleep(self._MODIFIER_RELEASE_RETRY_INTERVAL)
            self.injector.key(modifier, False)

    def _move_pointer(
        self,
        state: ControllerState,
        rect: Rect,
        cfg: dict[str, Any],
        dt: float,
    ) -> bool:
        input_cfg = cfg["input"]
        movement = cfg["movement"]
        deadzone = float(input_cfg["deadzone"])
        curve = float(input_cfg["response_curve"])
        lx, ly, lmag = radial_deadzone(state.lx, state.ly, deadzone, curve)
        rx, ry, rmag = radial_deadzone(state.rx, state.ry, deadzone, curve)
        radial_active = state.pressed("lb") and self._is_radial_allowed()
        auto_move = False
        aim_local: tuple[int, int] | None = None

        # O modo efetivo respeita o estado do jogo na memória RAM:
        # Se qualquer menu estiver aberto (exceto quando apenas o inventário estiver aberto)
        # ou estiver fora do jogo, o modo vira cursor e a caminhada fica suspensa.
        effective_mode = (
            "cursor"
            if (
                self._memory_state.is_connected
                and (self._memory_state.is_menu_open or not self._memory_state.is_in_game)
            )
            else self._mode
        )

        # Movimento direto: exige analógico esquerdo inclinado, direito parado, roda fechada
        # e ao menos uma lateral livre — com os dois painéis abertos, o esquerdo vira cursor livre.
        # Com a sequência de clique do pet em curso o cursor é EXCLUSIVO dela: os sticks
        # ficam bloqueados até o retorno ao centro (evita disputar o cursor no meio do
        # hover/clique do pet).
        if (
            effective_mode == "direct"
            and lmag > 0
            and rmag == 0
            and not radial_active
            and self._pet_click_seq is None
            and self._hud_click_seq is None
            and not any(self._active_panels)
            and self._memory_state.is_connected
            and self._memory_state.is_in_game
            and not self._memory_state.is_menu_open
        ):
            # Âncora do herói em pixels, a partir das frações do perfil.
            # Painel lateral aberto sozinho desloca a âncora para o lado oposto (área visível).
            anchor_shift = panels_x_shift(self._active_panels)
            anchor_x = rect.left + rect.width * clamp(
                float(movement["anchor_x"]) + anchor_shift, 0.05, 0.95
            )
            anchor_y = rect.top + rect.height * float(movement["anchor_y"])
            # Shared anchor for the aim marker and the system cursor.
            self._last_anchor = (round(anchor_x), round(anchor_y))
            # Raio circular: fração da ALTURA da janela nos dois eixos (área de movimento = círculo
            # ideal, sem ovalizar nas laterais como quando o eixo x usava a largura).
            radius = rect.height * float(movement["movement_radius_percent"])
            # Keep the cursor on the same aim point as the direction marker.
            # Movement itself remains a separate native navigation command.
            center_frac = float(movement["click_center_fraction"])
            reach = center_frac + (1.0 - center_frac) * lmag
            target_x = round(anchor_x + (lx / max(lmag, 1e-6)) * radius * reach)
            target_y = round(anchor_y + (ly / max(lmag, 1e-6)) * radius * reach)
            target_x = int(clamp(target_x, rect.left + 2, rect.right - 2))
            target_y = int(clamp(target_y, rect.top + 2, rect.bottom - 2))
            self.injector.move(target_x, target_y)
            aim_local = (target_x - rect.left, target_y - rect.top)
            world = self._memory_state.world
            if world.fresh(time.monotonic()) and world.camera is not None:
                self._native_direction = world.camera.ground_direction(lx, ly)
                if any(self._native_direction):
                    self._native_heading = self._native_direction
                    self._native_heading_scene = (world.player_address, world.level_address)
        else:
            # Modo cursor: analógico direito move o cursor; no modo 'cursor', o esquerdo também.
            cursor_x = cursor_y = cursor_mag = 0.0
            if not radial_active and rmag > 0:
                cursor_x, cursor_y, cursor_mag = rx, ry, rmag
            # No modo cursor/menus, o analógico esquerdo assume o papel de cursor.
            elif not radial_active and effective_mode == "cursor" and lmag > 0:
                cursor_x, cursor_y, cursor_mag = lx, ly, lmag
            # Ambos os painéis abertos: o esquerdo vira cursor livre (sem o click-to-move).
            elif not radial_active and lmag > 0 and both_panels_open(self._active_panels):
                cursor_x, cursor_y, cursor_mag = lx, ly, lmag

            # Há movimento de cursor: desloca da posição atual em vez de saltar para um ponto fixo.
            if cursor_mag > 0:
                self._native_heading = None
                current_x, current_y = self.injector.cursor_position()
                speed = float(cfg["cursor"]["speed_pixels_per_second"])
                # Delta em pixels; dt limitado a 50 ms para o cursor não 'saltar' após engasgos.
                dx, dy = cursor_delta(cursor_x, cursor_y, speed, min(dt, 0.05))
                # Move o cursor do sistema para a nova posição do modo cursor.
                target_x = int(clamp(round(current_x + dx), rect.left + 2, rect.right - 2))
                target_y = int(clamp(round(current_y + dy), rect.top + 2, rect.bottom - 2))
                self.injector.move(target_x, target_y)
                aim_local = (target_x - rect.left, target_y - rect.top)

        # A neutral stick leaves the cursor at its last aim point.
        self._direct_move_active = bool(any(self._native_direction) and self.native_input.ready)

        # Publica o marcador de mira no overlay (posição relativa à janela).
        if cfg["overlay"].get("show_aim_marker", True) and aim_local:
            self.shared.update(aim_x=aim_local[0], aim_y=aim_local[1])
        else:
            # Sem alvo (ou marcador desligado): limpa o marcador.
            self.shared.update(aim_x=None, aim_y=None)
        return auto_move

    def _process_active(self, hub, state, rect, cfg, now, dt) -> None:
        self._native_direction = (0., 0.)
        self._native_interaction_allowed = False
        for source in tuple(self._skill_repeat_sources):
            pressed = state.rt >= self.TRIGGER_ACTIVE_THRESHOLD if source == "rt" else state.pressed(source)
            if not pressed:
                del self._skill_repeat_sources[source]
        self.native_input.connect(self.memory, now)
        try:
            self._process_active_inputs(hub, state, rect, cfg, now, dt)
            self._publish_native_input(state, cfg, now)
        except BaseException:
            self._native_direction = (0., 0.)
            self.native_input.close()
            raise

    def _publish_native_input(self, state, cfg, now) -> None:
        memory = self._memory_state
        world = memory.world
        live = (state.connected and memory.is_connected and memory.is_in_game
                and world.fresh(now) and not memory.is_loading)
        direct = (live and self._mode == "direct" and not memory.is_menu_open
                  and not memory.dialog_type and not any(self._active_panels)
                  and not self._virtual_keyboard_open and not self._shortcut_config_active)
        if isinstance(self.injector, InputSession):
            self.injector.check()
        flags = ACTIVE if state.connected else 0
        if direct:
            flags |= DIRECT
            if any(self._native_direction):
                flags |= WALKING
            if self._native_interaction_allowed:
                flags |= ALLOW_INTERACTION
        self.native_input.send(flags=flags, player=world.player_address, level=world.level_address,
                               dx=self._native_direction[0] if direct else 0.,
                               dz=self._native_direction[1] if direct else 0.,
                               radius=cfg["interaction"]["radius"], now=now)
        native = self.native_input.status
        self.shared.update(movement_status=self.native_input.message,
                           native_input_ready=self.native_input.ready,
                           movement_direction=self._native_direction,
                           movement_destination=(native.destination_x, native.destination_z),
                           native_highlight=bool(native.flags & 4),
                           blocked_interactions=native.blocked_interactions,
                           blocked_warps=native.blocked_warps)

    def _process_active_inputs(
        self,
        hub: ControllerHub,
        state: ControllerState,
        rect: Rect,
        cfg: dict[str, Any],
        now: float,
        dt: float,
    ) -> None:
        self._update_trigger_edges(state)
        # Handle fishing before center buttons, discrete bindings and combat.
        # Its only controller inputs are the physical confirm/cancel pair.
        menus = self._memory_state.open_menus or []
        modal = "Confirmação Sair" in menus or "confirma" in (self._memory_state.state_desc or "").lower()
        if self._memory_state.is_connected and "Pesca" in menus and not modal:
            self._handle_fishing_navigation(state, rect, hub)
            self._previous_panels = tuple(self._active_panels)
            return
        if self._memory_state.is_connected and self._memory_state.state_id == 1:
            was_open = self._virtual_keyboard_open
            self._handle_char_create_navigation(state, rect, hub)
            self._handle_keyboard_mouse(rect, hub)
            if was_open or self._virtual_keyboard_open:
                return
            confirm, _ = self._keyboard_buttons(state)
            if self._keyboard_confirm_latched:
                if state.pressed(confirm) or state.pressed("start"):
                    return
                self._keyboard_confirm_latched = False
                return
        bindings = cfg["bindings"]
        self._handle_center_buttons(state, rect, bindings, now)
        if self._handle_world_interaction(state, rect, cfg, now):
            return
        self._handle_discrete_bindings(state, bindings)
        # Navegação nos Menus via D-pad conforme o estado da memória
        if self._memory_state.is_connected:
            # Sincronização contínua de classe do personagem e reset da skill tree ao trocar de personagem
            if self._memory_state.is_in_game:
                raw_class = getattr(self._memory_state, "char_class", "").strip().lower()
                if raw_class in ("destroyer", "vanquisher", "alchemist"):
                    if self._char_class != raw_class:
                        self._char_class = raw_class
                        self._skill_tab = 1
                        self._skill_menu_initialized = False
                        self._skill_focus_row = 0
                        self._skill_focus_col = 1
                        self._skill_in_tabbar = False
                        self._skill_in_pink = False
                        self._skill_in_spells = False
                        self.shared.update(char_class=raw_class, skill_tab=1)
            else:
                if self._char_class:
                    self._char_class = ""
                    self._skill_tab = 1
                    self._skill_menu_initialized = False
                    self.shared.update(char_class="", skill_tab=1)

            state_id = self._memory_state.state_id
            if state_id == 0:
                self._handle_title_menu_navigation(state, rect, hub)
            elif self._title_screen_initialized:
                self._title_screen_initialized = False
                self.shared.update(title_menu_focus=None)

            if state_id != 1 and self._char_create_initialized:
                self._char_create_initialized = False
                self._virtual_keyboard_open = False
                self._virtual_keyboard_target = ""
                self.shared.update(char_create_focus=None, virtual_keyboard_open=False, virtual_keyboard_target="")

            if state_id in (2, 4):
                self._handle_difficulty_navigation(state, rect, hub)
            elif self._difficulty_initialized:
                self._difficulty_initialized = False
                self.shared.update(difficulty_focus=None)

            if state_id == 3:
                self._handle_load_char_navigation(state, rect, hub, now)
            elif self._load_char_initialized:
                self._load_char_initialized = False
                self._load_char_focus = None
                self._load_char_delete_dialog_open = False
                self._load_char_scroll_offset = 0
                self.shared.update(load_char_focus=None, load_char_delete_open=False)

            # Diálogos de NPCs, Missões e Telas de História
            if self._memory_state.dialog_type:
                self._handle_dialog_navigation(state, rect, hub)
            elif self._dialog_initialized:
                self._dialog_initialized = False
                self._last_dialog_type = ""
                self._dialog_focus = None
                self.shared.update(dialog_focus=None, dialog_type="", dialog_buttons=[], dialog_has_reward=False)

            # Menu de Pause (COptionsMenu / Options) em jogo
            is_paused = self._memory_state.is_in_game and (
                "Pause" in self._memory_state.open_menus
                or "paused" in [m.lower() for m in self._memory_state.open_menus]
            )
            if is_paused:
                self._handle_pause_menu_navigation(state, rect, hub)
            elif self._pause_menu_initialized:
                self._pause_menu_initialized = False
                self._pause_focus = None
                self.shared.update(pause_menu_focus=None)

            # Tela de Morte / Respawn em jogo
            is_death_screen = self._memory_state.is_in_game and (
                "Morte / Respawn" in self._memory_state.open_menus
                or any("morte" in m.lower() or "respawn" in m.lower() for m in self._memory_state.open_menus)
            )
            if is_death_screen:
                self._handle_death_screen_navigation(state, rect, hub)
            elif self._death_screen_initialized:
                self._death_screen_initialized = False
                self._death_screen_focus = None
                self.shared.update(death_screen_focus=None)

            # Tela de Configurações (Settings) em qualquer estado (in-game ou menu principal)
            is_settings = (
                "Configurações" in (self._memory_state.open_menus or [])
                or any("configura" in m.lower() or "setting" in m.lower() for m in (self._memory_state.open_menus or []))
                or (bool(self._memory_state.state_desc) and ("configura" in self._memory_state.state_desc.lower() or "setting" in self._memory_state.state_desc.lower()))
            )
            if is_settings:
                self._handle_settings_navigation(state, rect, hub, now)
                self._previous_panels = (self._active_panels[0], self._active_panels[1])
                return
            elif self._settings_initialized:
                if self._settings_slider_dragging:
                    self.injector.mouse_button("left", False)
                    self._settings_slider_dragging = False
                self._settings_initialized = False
                self._settings_focus = None
                self._settings_dropdown = None
                self._settings_dropdown_idx = 0
                self.shared.update(
                    settings_focus=None,
                    settings_dropdown=None,
                    settings_dropdown_idx=0,
                    settings_slider_dragging=False,
                )

            # Modal de Confirmação (Resultado de Pesca, Avisos e Sair)
            is_modal = (
                "Confirmação Sair" in (self._memory_state.open_menus or [])
                or "confirma" in (self._memory_state.state_desc or "").lower()
            )
            if is_modal:
                self._handle_modal_confirm_navigation(state, rect, hub)
                self._previous_panels = (self._active_panels[0], self._active_panels[1])
                return
            elif self._modal_confirm_initialized:
                self._modal_confirm_initialized = False
                self.shared.update(modal_confirm_focus=None)

            if self._fishing_initialized:
                self._fishing_initialized = False
                self.shared.update(fishing_focus=None)

            # Inventário do Jogador, Menu do Pet, Baú (Stash), Mercador (Loja) e Crafting (Transmutador, Sockets, Encantador)
            is_inventory = "Inventário" in (self._memory_state.open_menus or [])
            is_pet = "Pet" in (self._memory_state.open_menus or [])
            is_stash = "Baú" in (self._memory_state.open_menus or [])
            is_merchant = "Vendedor (Loja)" in (self._memory_state.open_menus or [])
            is_crafting = any(m in (self._memory_state.open_menus or []) for m in ("Transmutador", "Sockets", "Encantador"))
            is_char   = "Atributos"    in (self._memory_state.open_menus or [])
            is_skills = "Habilidades"  in (self._memory_state.open_menus or [])
            is_quest  = "Missões (Quests)" in (self._memory_state.open_menus or [])

            if is_char or is_skills:
                # Lê classe do personagem da memória (ex: "destroyer", "vanquisher", "alchemist").
                # _char_class é mantido entre ticks; atualiza e reseta a aba para 1 quando muda.
                raw_class = getattr(self._memory_state, "char_class", "").strip().lower()
                if raw_class in ("destroyer", "vanquisher", "alchemist"):
                    if self._char_class != raw_class:
                        self._char_class = raw_class
                        self._skill_tab = 1
                        self._skill_menu_initialized = False
                        self._skill_focus_row = 0
                        self._skill_focus_col = 1
                        self._skill_in_tabbar = False
                        self._skill_in_pink = False
                        self._skill_in_spells = False
                        self.shared.update(char_class=raw_class, skill_tab=1)
                    self._char_class = raw_class

            if is_crafting and not self._crafting_initialized:
                self._handle_crafting_navigation(state, rect, hub)
            elif is_merchant and not self._merchant_initialized:
                self._handle_merchant_navigation(state, rect, hub)
            elif is_stash and not self._stash_initialized:
                self._handle_stash_navigation(state, rect, hub)
            elif is_pet and not self._pet_inventory_initialized:
                self._handle_pet_inventory_navigation(state, rect, hub)
            elif is_char and not self._char_menu_initialized and not is_skills and not is_inventory and not is_quest:
                attr_points = getattr(self._memory_state, "attr_points_remaining", 0)
                self._handle_char_menu_navigation(state, rect, hub, skill_also_open=False, inv_also_open=False, quest_also_open=False, attr_points=attr_points)
            elif is_inventory and not self._inventory_initialized and not is_char:
                self._handle_inventory_navigation(state, rect, hub)
            elif (is_pet or is_stash or is_merchant or is_crafting) and is_inventory:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                if cur_x < mid_x:
                    if is_crafting:
                        self._handle_crafting_navigation(state, rect, hub)
                    elif is_merchant:
                        self._handle_merchant_navigation(state, rect, hub)
                    elif is_stash:
                        self._handle_stash_navigation(state, rect, hub)
                    else:
                        self._handle_pet_inventory_navigation(state, rect, hub)
                else:
                    self._handle_inventory_navigation(state, rect, hub)
            elif is_pet and is_skills:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                if cur_x < mid_x:
                    self._handle_pet_inventory_navigation(state, rect, hub)
                else:
                    skill_points = getattr(self._memory_state, "skill_points_remaining", 0)
                    self._handle_skill_menu_navigation(
                        state, rect, hub,
                        char_also_open=False,
                        pet_also_open=True,
                        skill_points=skill_points,
                        char_class=self._char_class,
                        now=now,
                    )
            elif is_char and is_inventory:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                if cur_x < mid_x:
                    attr_points = getattr(self._memory_state, "attr_points_remaining", 0)
                    self._handle_char_menu_navigation(
                        state, rect, hub,
                        skill_also_open=False,
                        inv_also_open=True,
                        quest_also_open=False,
                        attr_points=attr_points,
                    )
                else:
                    self._handle_inventory_navigation(state, rect, hub)
            elif is_pet and is_quest:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                if cur_x < mid_x:
                    self._handle_pet_inventory_navigation(state, rect, hub)
                else:
                    self._handle_quest_menu_navigation(state, rect, hub, pet_also_open=True, char_also_open=False)
            elif is_char and is_quest:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                if cur_x < mid_x:
                    attr_points = getattr(self._memory_state, "attr_points_remaining", 0)
                    self._handle_char_menu_navigation(
                        state, rect, hub,
                        skill_also_open=False,
                        inv_also_open=False,
                        quest_also_open=True,
                        attr_points=attr_points,
                    )
                else:
                    self._handle_quest_menu_navigation(state, rect, hub, pet_also_open=False, char_also_open=True)
            elif is_quest:
                self._handle_quest_menu_navigation(state, rect, hub, pet_also_open=False, char_also_open=False)
            elif is_crafting:
                self._handle_crafting_navigation(state, rect, hub)
            elif is_merchant:
                self._handle_merchant_navigation(state, rect, hub)
            elif is_stash:
                self._handle_stash_navigation(state, rect, hub)
            elif is_pet:
                self._handle_pet_inventory_navigation(state, rect, hub)
            elif is_inventory:
                self._handle_inventory_navigation(state, rect, hub)

            if not is_inventory and self._inventory_initialized:
                self._inventory_initialized = False
                self._inventory_tab = None
                self._inventory_focus = None
                self.shared.update(inventory_open=False, inventory_tab=None, inventory_focus=None)

            if not is_pet and self._pet_inventory_initialized:
                self._pet_inventory_initialized = False
                self._pet_inventory_tab = None
                self._pet_inventory_focus = None
                self.shared.update(pet_inventory_open=False, pet_inventory_tab=None, pet_inventory_focus=None)

            if not is_stash and self._stash_initialized:
                self._stash_initialized = False
                self._stash_tab = None
                self._stash_focus = None
                self.shared.update(stash_open=False, stash_tab=None, stash_focus=None)

            if not is_merchant and self._merchant_initialized:
                self._merchant_initialized = False
                self._merchant_tab = None
                self._merchant_focus = None
                self._merchant_npc_name = ""
                self.shared.update(
                    merchant_open=False,
                    merchant_tab=None,
                    merchant_focus=None,
                    merchant_npc_name="",
                )

            if not is_crafting and self._crafting_initialized:
                self._crafting_initialized = False
                self._crafting_menu = None
                self._crafting_focus = None
                self.shared.update(
                    crafting_open=False,
                    crafting_menu=None,
                    crafting_focus=None,
                )

            # Menu de Personagem (C) e Árvore de Habilidades (S)
            if (is_char or is_skills) and not (is_pet and is_skills) and not (is_char and is_inventory) and not (is_char and is_quest):
                # Contexto para os handlers
                char_also_open  = is_char
                skill_also_open = is_skills
                attr_points  = getattr(self._memory_state, "attr_points_remaining",  0)
                skill_points = getattr(self._memory_state, "skill_points_remaining", 0)

                # Decide qual handler recebe o dpad com base na posição do cursor.
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5

                if is_char and is_skills:
                    # Ambos abertos: cursor à esquerda → menu C; à direita → menu S.
                    if cur_x < mid_x:
                        self._handle_char_menu_navigation(
                            state, rect, hub, skill_also_open=True, inv_also_open=False, quest_also_open=False, attr_points=attr_points
                        )
                    else:
                        self._handle_skill_menu_navigation(
                            state, rect, hub,
                            char_also_open=True,
                            pet_also_open=False,
                            skill_points=skill_points,
                            char_class=self._char_class,
                            now=now,
                        )
                elif is_char:
                    self._handle_char_menu_navigation(
                        state, rect, hub, skill_also_open=False, inv_also_open=False, quest_also_open=False, attr_points=attr_points
                    )
                else:
                    self._handle_skill_menu_navigation(
                        state, rect, hub,
                        char_also_open=False,
                        pet_also_open=False,
                        skill_points=skill_points,
                        char_class=self._char_class,
                        now=now,
                    )

            if not is_char and self._char_menu_initialized:
                self._char_menu_initialized = False
                self._char_menu_focus = "strength"
                self.shared.update(char_menu_open=False, char_menu_focus=None)

            if not is_skills and self._skill_menu_initialized:
                self._skill_menu_initialized = False
                self._skill_focus_row = 0
                self._skill_focus_col = 1
                self._skill_in_tabbar = False
                self._skill_in_pink = False
                self._skill_in_spells = False
                self._skill_spell_idx = 0
                self.shared.update(skill_menu_open=False, skill_focus=None)

            if not is_quest and self._quest_menu_initialized:
                self._quest_menu_initialized = False
                self._quest_b_consumed = False
                self.shared.update(quest_menu_open=False, quest_focus=None)
        else:
            if self._title_screen_initialized:
                self._title_screen_initialized = False
                self.shared.update(title_menu_focus=None)
            if self._char_create_initialized:
                self._char_create_initialized = False
                self.shared.update(char_create_focus=None)
            if self._difficulty_initialized:
                self._difficulty_initialized = False
                self.shared.update(difficulty_focus=None)
            if self._load_char_initialized:
                self._load_char_initialized = False
                self._load_char_focus = None
                self._load_char_delete_dialog_open = False
                self._load_char_scroll_offset = 0
                self.shared.update(load_char_focus=None, load_char_delete_open=False)
            if self._dialog_initialized:
                self._dialog_initialized = False
                self._last_dialog_type = ""
                self._dialog_focus = None
                self.shared.update(dialog_focus=None, dialog_type="", dialog_buttons=[])
            if self._pause_menu_initialized:
                self._pause_menu_initialized = False
                self._pause_focus = None
                self.shared.update(pause_menu_focus=None)
            if self._death_screen_initialized:
                self._death_screen_initialized = False
                self._death_screen_focus = None
                self.shared.update(death_screen_focus=None)
            if self._settings_initialized:
                if self._settings_slider_dragging:
                    self.injector.mouse_button("left", False)
                    self._settings_slider_dragging = False
                self._settings_initialized = False
                self._settings_focus = None
                self._settings_dropdown = None
                self._settings_dropdown_idx = 0
                self.shared.update(
                    settings_focus=None,
                    settings_dropdown=None,
                    settings_dropdown_idx=0,
                    settings_slider_dragging=False,
                )
            if self._modal_confirm_initialized:
                self._modal_confirm_initialized = False
                self.shared.update(modal_confirm_focus=None)
            if self._fishing_initialized:
                self._fishing_initialized = False
                self.shared.update(fishing_focus=None)
            if self._inventory_initialized:
                self._inventory_initialized = False
                self._inventory_tab = None
                self._inventory_focus = None
                self.shared.update(inventory_open=False, inventory_tab=None, inventory_focus=None)
            if self._pet_inventory_initialized:
                self._pet_inventory_initialized = False
                self._pet_inventory_tab = None
                self._pet_inventory_focus = None
                self.shared.update(pet_inventory_open=False, pet_inventory_tab=None, pet_inventory_focus=None)
            if self._stash_initialized:
                self._stash_initialized = False
                self._stash_tab = None
                self._stash_focus = None
                self.shared.update(stash_open=False, stash_tab=None, stash_focus=None)
            if self._merchant_initialized:
                self._merchant_initialized = False
                self._merchant_tab = None
                self._merchant_focus = None
                self._merchant_npc_name = ""
                self.shared.update(merchant_open=False, merchant_tab=None, merchant_focus=None, merchant_npc_name="")
            if self._crafting_initialized:
                self._crafting_initialized = False
                self._crafting_menu = None
                self._crafting_focus = None
                self.shared.update(crafting_open=False, crafting_menu=None, crafting_focus=None)
            if self._char_menu_initialized:
                self._char_menu_initialized = False
                self._char_menu_focus = "strength"
                self.shared.update(char_menu_open=False, char_menu_focus=None)
            if self._skill_menu_initialized:
                self._skill_menu_initialized = False
                self._skill_focus_row = 0
                self._skill_focus_col = 1
                self._skill_in_tabbar = False
                self._skill_in_pink = False
                self._skill_in_spells = False
                self._skill_spell_idx = 0
                self.shared.update(skill_menu_open=False, skill_focus=None)
            if self._quest_menu_initialized:
                self._quest_menu_initialized = False
                self._quest_b_consumed = False
                self.shared.update(quest_menu_open=False, quest_focus=None)

        hud_active_before = self._hud_click_seq is not None
        # A roda antes das sequências: o A arma a do pet neste mesmo tick e o
        # _handle_pet_click abaixo já faz o movimento até o botão na hora.
        self._handle_radial(hub, state, bindings, rect, now)
        if self._shortcut_config_active:
            # Se LB ainda estiver segurado após a confirmação na roda, aguarda soltura
            if state.pressed("lb"):
                return

            is_key_pressed_fn = getattr(self.injector, "is_key_pressed", None)
            physical_esc = is_key_pressed_fn("ESC") if is_key_pressed_fn else False
            esc_edge = physical_esc and not getattr(self, "_previous_physical_esc", False)
            self._previous_physical_esc = physical_esc

            # Sub-modo: Grid de Opções aberto e ativo para navegação
            if self._shortcut_grid_active:
                # Atualização dinâmica de dimensões caso CEGUI tenha atualizado o layout após o clique
                grid_info = getattr(self.memory, "read_shortcut_grid_info", lambda: None)()
                if grid_info:
                    new_cols, new_rows, new_counts = grid_info
                    if (new_cols, new_rows, new_counts) != (
                        self._shortcut_grid_cols,
                        self._shortcut_grid_rows,
                        self._shortcut_grid_counts,
                    ):
                        self._shortcut_grid_cols = new_cols
                        self._shortcut_grid_rows = new_rows
                        self._shortcut_grid_counts = new_counts
                        self._shortcut_grid_row = min(self._shortcut_grid_row, max(0, self._shortcut_grid_rows - 1))
                        row_items = (
                            self._shortcut_grid_counts[self._shortcut_grid_row]
                            if self._shortcut_grid_row < len(self._shortcut_grid_counts)
                            else self._shortcut_grid_cols
                        )
                        self._shortcut_grid_col = min(self._shortcut_grid_col, max(0, row_items - 1))
                        self.shared.update(
                            shortcut_grid_cols=self._shortcut_grid_cols,
                            shortcut_grid_rows=self._shortcut_grid_rows,
                            shortcut_grid_counts=self._shortcut_grid_counts,
                            shortcut_grid_pos=(self._shortcut_grid_row, self._shortcut_grid_col),
                        )
                else:
                    dims = self.memory.read_shortcut_grid_dims()
                    if dims and dims != (self._shortcut_grid_cols, self._shortcut_grid_rows):
                        self._shortcut_grid_cols, self._shortcut_grid_rows = dims
                        self._shortcut_grid_counts = (self._shortcut_grid_cols,) * self._shortcut_grid_rows
                        self._shortcut_grid_row = min(self._shortcut_grid_row, max(0, self._shortcut_grid_rows - 1))
                        self._shortcut_grid_col = min(self._shortcut_grid_col, max(0, self._shortcut_grid_cols - 1))
                        self.shared.update(
                            shortcut_grid_cols=self._shortcut_grid_cols,
                            shortcut_grid_rows=self._shortcut_grid_rows,
                            shortcut_grid_counts=self._shortcut_grid_counts,
                            shortcut_grid_pos=(self._shortcut_grid_row, self._shortcut_grid_col),
                        )

                # Tecla ESC ou Botão Start: desarma completamente a configuração e volta para o jogo
                if (state.pressed("start") and not self._previous.pressed("start")) or esc_edge:
                    self._shortcut_config_active = False
                    self._shortcut_grid_active = False
                    self._shortcut_node_focus = 0
                    self._shortcut_info_focus = False
                    self.shared.update(shortcut_config_active=False, shortcut_node_focus=0, shortcut_grid_active=False, shortcut_info_focus=False)
                    # Envia clique para fechar o pop-up nativo do jogo
                    target_x, target_y = shortcut_node_point(rect, self._shortcut_node_focus)
                    self.injector.move(target_x, target_y)
                    self.injector.mouse_button("left", True)
                    self.injector.mouse_button("left", False)
                    center_x = rect.left + rect.width // 2
                    center_y = rect.top + rect.height // 2
                    self.injector.move(center_x, center_y)
                    hub.rumble(0.04, 0.08, 30)
                    return

                # Botão Leste (B / Bolinha no PS): cancela e fecha apenas o grid, voltando para os nós da HUD
                if state.pressed("b") and not self._previous.pressed("b"):
                    self._shortcut_grid_active = False
                    self._shortcut_info_focus = False
                    self.shared.update(shortcut_grid_active=False, shortcut_info_focus=False)
                    # Retorna o cursor para o nó da HUD que estava focado
                    target_x, target_y = shortcut_node_point(rect, self._shortcut_node_focus)
                    self.injector.move(target_x, target_y)
                    # Envia clique para fechar o pop-up nativo do jogo
                    self.injector.mouse_button("left", True)
                    self.injector.mouse_button("left", False)
                    hub.rumble(0.04, 0.08, 30)
                    return

                # Navegação no Grid com D-pad (Cima / Baixo / Esquerda / Direita)
                dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
                dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
                dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
                dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

                if dpad_up or dpad_down or dpad_left or dpad_right:
                    new_r = self._shortcut_grid_row
                    new_c = self._shortcut_grid_col
                    if dpad_up:
                        new_r = max(0, new_r - 1)
                    elif dpad_down:
                        new_r = min(self._shortcut_grid_rows - 1, new_r + 1)

                    # Número de colunas válidas nesta linha específica
                    row_items = self._shortcut_grid_counts[new_r] if new_r < len(self._shortcut_grid_counts) else self._shortcut_grid_cols
                    max_col_for_row = max(0, row_items - 1)

                    if dpad_left:
                        new_c = max(0, min(new_c, max_col_for_row) - 1)
                    elif dpad_right:
                        new_c = min(max_col_for_row, new_c + 1)
                    else:
                        new_c = min(new_c, max_col_for_row)

                    if new_r != self._shortcut_grid_row or new_c != self._shortcut_grid_col:
                        self._shortcut_grid_row = new_r
                        self._shortcut_grid_col = new_c
                        self.shared.update(shortcut_grid_pos=(new_r, new_c))
                        target_x, target_y = shortcut_grid_cell_point(
                            rect, self._shortcut_node_focus, new_r, new_c, self._shortcut_grid_cols, self._shortcut_grid_rows
                        )
                        self.injector.move(target_x, target_y)
                        hub.rumble(0.03, 0.06, 25)

                # Botão Sul (A / X): Confirma a seleção do item/habilidade no grid
                if state.pressed("a") and not self._previous.pressed("a"):
                    target_x, target_y = shortcut_grid_cell_point(
                        rect, self._shortcut_node_focus, self._shortcut_grid_row, self._shortcut_grid_col, self._shortcut_grid_cols, self._shortcut_grid_rows
                    )
                    self.injector.move(target_x, target_y)
                    self.injector.mouse_button("left", True)
                    self.injector.mouse_button("left", False)
                    # O grid nativo fecha ao clicar numa opção; voltamos para a navegação de nós
                    self._shortcut_grid_active = False
                    self._shortcut_info_focus = False
                    self.shared.update(shortcut_grid_active=False, shortcut_info_focus=False)
                    node_x, node_y = shortcut_node_point(rect, self._shortcut_node_focus)
                    self.injector.move(node_x, node_y)
                    hub.rumble(0.05, 0.12, 40)

                return

            # Sub-modo: Foco na aba superior de informações (config-info.png)
            if self._shortcut_info_focus:
                # Tecla ESC ou Botão Start: desarma completamente a configuração e volta para o jogo
                if (state.pressed("start") and not self._previous.pressed("start")) or esc_edge:
                    self._shortcut_config_active = False
                    self._shortcut_node_focus = 0
                    self._shortcut_grid_active = False
                    self._shortcut_info_focus = False
                    self.shared.update(shortcut_config_active=False, shortcut_node_focus=0, shortcut_grid_active=False, shortcut_info_focus=False)
                    center_x = rect.left + rect.width // 2
                    center_y = rect.top + rect.height // 2
                    self.injector.move(center_x, center_y)
                    hub.rumble(0.04, 0.08, 30)
                    return

                # D-pad Baixo ou Botão Leste (B / Bolinha no PS): retorna para os nós da HUD inferior
                dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
                b_pressed = state.pressed("b") and not self._previous.pressed("b")
                if dpad_down or b_pressed:
                    self._shortcut_info_focus = False
                    self.shared.update(shortcut_info_focus=False)
                    target_x, target_y = shortcut_node_point(rect, self._shortcut_node_focus)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.03, 0.08, 30)
                    return

                # Suprime os outros comandos enquanto na aba superior
                return

            # Modo principal de seleção de slots da HUD inferior:
            # Botão Leste (B / Bolinha no PS) ou Start/ESC desativa o modo e volta ao jogo
            if (state.pressed("b") and not self._previous.pressed("b")) or (
                state.pressed("start") and not self._previous.pressed("start")
            ) or esc_edge:
                self._shortcut_config_active = False
                self._shortcut_node_focus = 0
                self._shortcut_grid_active = False
                self._shortcut_info_focus = False
                self.shared.update(shortcut_config_active=False, shortcut_node_focus=0, shortcut_grid_active=False, shortcut_info_focus=False)
                center_x = rect.left + rect.width // 2
                center_y = rect.top + rect.height // 2
                self.injector.move(center_x, center_y)
                hub.rumble(0.04, 0.08, 30)
                return

            # D-pad Cima: navega para a aba superior de informações (config-info.png)
            dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
            if dpad_up:
                self._shortcut_info_focus = True
                self.shared.update(shortcut_info_focus=True)
                target_x, target_y = shortcut_info_node_point(rect)
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                return

            # Navegação pelos 13 nós da HUD inferior via D-pad
            dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
            dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
            if dpad_right:
                new_focus = min(len(SHORTCUT_HUD_NODES) - 1, self._shortcut_node_focus + 1)
                if new_focus != self._shortcut_node_focus:
                    self._shortcut_node_focus = new_focus
                    self.shared.update(shortcut_node_focus=new_focus)
                    target_x, target_y = shortcut_node_point(rect, new_focus)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.03, 0.08, 30)
            elif dpad_left:
                new_focus = max(0, self._shortcut_node_focus - 1)
                if new_focus != self._shortcut_node_focus:
                    self._shortcut_node_focus = new_focus
                    self.shared.update(shortcut_node_focus=new_focus)
                    target_x, target_y = shortcut_node_point(rect, new_focus)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.03, 0.08, 30)

            # Botão Norte (Y / Triângulo): Dispara Ctrl + Clique Esquerdo (remove item/skill do slot)
            if state.pressed("y") and not self._previous.pressed("y"):
                target_x, target_y = shortcut_node_point(rect, self._shortcut_node_focus)
                self.injector.move(target_x, target_y)
                self.injector.key("ctrl", True)
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                self.injector.key("ctrl", False)
                hub.rumble(0.04, 0.08, 30)

            # Botão Sul (A / X): Dispara Clique Esquerdo (abre o grid de opções e ativa navegação no grid)
            if state.pressed("a") and not self._previous.pressed("a"):
                target_x, target_y = shortcut_node_point(rect, self._shortcut_node_focus)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                # Define dimensões padrão inteligentes para cada tipo de nó da HUD
                if self._shortcut_node_focus == 5:
                    # Clique Esquerdo: apenas ataque físico + skills ativas Lv 1 (1 linha x 3 colunas)
                    default_cols, default_rows = 3, 1
                    default_counts = (3,)
                elif self._shortcut_node_focus in (6, 7):
                    # Clique Direito e Tab: apenas skills + spells (sem consumíveis)
                    default_cols, default_rows = 7, 2
                    default_counts = (7, 2)
                elif self._shortcut_node_focus <= 4:
                    # Números 1 a 5: skills + spells + consumíveis
                    default_cols, default_rows = 7, 3
                    default_counts = (7, 2, 7)
                else:
                    # Números 6 a 0: skills + spells + consumíveis (clamped à direita)
                    default_cols, default_rows = 8, 4
                    default_counts = (8, 2, 8, 6)

                # Consulta dinâmica das dimensões reais e contagem de itens por linha (CEGUI gui__3501Base)
                grid_info = getattr(self.memory, "read_shortcut_grid_info", lambda: None)()
                if grid_info:
                    self._shortcut_grid_cols, self._shortcut_grid_rows, self._shortcut_grid_counts = grid_info
                else:
                    dims = self.memory.read_shortcut_grid_dims()
                    if dims:
                        self._shortcut_grid_cols, self._shortcut_grid_rows = dims
                        self._shortcut_grid_counts = (self._shortcut_grid_cols,) * self._shortcut_grid_rows
                    else:
                        self._shortcut_grid_cols = default_cols
                        self._shortcut_grid_rows = default_rows
                        self._shortcut_grid_counts = default_counts

                # Ativa o grid de opções e posiciona na célula (0, 0)
                self._shortcut_grid_active = True
                self._shortcut_grid_row = 0
                self._shortcut_grid_col = 0
                self.shared.update(
                    shortcut_grid_active=True,
                    shortcut_grid_pos=(0, 0),
                    shortcut_grid_cols=self._shortcut_grid_cols,
                    shortcut_grid_rows=self._shortcut_grid_rows,
                    shortcut_grid_counts=self._shortcut_grid_counts,
                )
                gx, gy = shortcut_grid_cell_point(
                    rect, self._shortcut_node_focus, 0, 0, self._shortcut_grid_cols, self._shortcut_grid_rows
                )
                self.injector.move(gx, gy)
                hub.rumble(0.04, 0.08, 30)

            return
        else:
            self._previous_physical_esc = False
        self._handle_pet_click(now)
        self._handle_hud_purple_click(now)
        # Remap do overworld e combos de gatilho (mapa docs/REMAP-BOTOES): B/Y
        # contextuais (ESC / Shift+clique) e RB/RT/LT+ (3/4/5..0). Rodam depois da
        # roda: com LB de pé eles se auto-suprimem lá dentro. O cronômetro do clique
        # modificado roda DEPOIS: um Y/LT+A do próprio tick arma a sequência e o
        # _handle_modifier_release já executa as fases já vencidas (determinístico).
        # Pertencem exclusivamente ao gameplay in-game: fora do jogo (telas iniciais e menus)
        # esses atalhos não devem vazar teclas de combate/habilidade (1, 2, 3..0).
        if not self._memory_state.is_connected or self._memory_state.is_in_game:
            self._handle_trigger_combos(state, rect, bindings, now)
            self._handle_overworld_remap(state, rect, bindings, now)
            self._handle_overworld_dpad(state, rect, hub, bindings, now)
            self._handle_modifier_release(now)

        # Posiciona o cursor; retorna True quando o movimento direto deve segurar o clique esquerdo.
        # Com a sequência do pet ou hud em curso os sticks estão bloqueados: nenhum move, nenhum
        # clique retido e nenhuma borda de subida dispara a lógica de fechamento de painéis.
        seq_active = (
            self._pet_click_seq is not None
            or self._hud_click_seq is not None
            or hud_active_before
        )
        if seq_active:
            # O clique do pet é injetado direto pelo _handle_pet_click (fora de
            # _held_mouse): não mexe no botão esquerdo nem na borda de subida — o
            # estado 'left' fica exatamente como estava antes da sequência, então
            # nem a borda de descida (soltar por engano) nem a borda de subida
            # (click_zone fechando painéis) disparam no meio do hover/clique.
            self._previous_panels = (self._active_panels[0], self._active_panels[1])
            self._previous_left_pressed = False
            return
        # Clique modificado em curso (Shift+clique do Y / Ctrl+clique do LT+A): os
        # ticks intermediários pulam cursor/botões — o left da sequência vive fora de
        # _held_mouse (a borda de subida dispararia a click_zone de fechamento de
        # painéis no meio do clique) e o cursor não salta nos frames do clique.
        if self._modifier_seq is not None:
            self._previous_panels = (self._active_panels[0], self._active_panels[1])
            return
        self._move_pointer(state, rect, cfg, dt)
        # Cliques de mouse vêm dos botões face: A = esquerdo, X = direito.
        # Cruz (PS) / A (Xbox) / A (Nintendo) chegam normalizados como "a" e
        # quadrado (PS) / X (Xbox) / X (Nintendo) como "x" (mapeamento do SDL —
        # ver BUTTONS em controller.py): uma regra cobre as três famílias.
        # Enquanto LB está segurado (roda de atalhos) os dois ficam inertes: o A
        # confirma slot/sublinha lá dentro e nenhum toque pode vazar clique de
        # mouse no jogo — inclusive depois da confirmação, quando o usuário
        # ainda segura A/LB no fim da sequência do pet (sem isso o clique
        # esquerdo grudaria e o herói seguiria o cursor).
        # Com LT ativo os dois ficam inertes TAMBÉM: A/X pertencem aos combos
        # LT+A (5 / Ctrl+clique) e LT+X (6) — segurar o LT com o A não pode
        # segurar o clique comum.
        radial_held = state.pressed("lb") and self._is_radial_allowed()
        lt_held = self._lt_current
        # Na tela de Carregar Personagem (state_id == 3) e na tela de Configurações, as ações
        # dos botões A e X são tratadas inteiramente pelos respectivos handlers (que realizam o
        # clique e movem o cursor para o próximo destino). Suprimimos o mouse aqui para que o botão
        # ainda segurado no controle não dispare um clique falso/residual no destino do cursor.
        in_quest_side = False
        if self._quest_menu_initialized and getattr(self, "_memory_state", None):
            is_quest_open = (
                "Missões (Quests)" in (self._memory_state.open_menus or [])
                or getattr(self._memory_state, "quest_menu_open", False)
            )
            if is_quest_open:
                cur_x, _ = self.injector.cursor_position()
                mid_x = rect.left + rect.width * 0.5
                is_pet_open = "Pet" in (self._memory_state.open_menus or [])
                is_char_open = "Atributos" in (self._memory_state.open_menus or [])
                if is_pet_open or is_char_open:
                    in_quest_side = (cur_x >= mid_x)
                else:
                    in_quest_side = True

        suppress_mouse = (
            self._load_char_initialized
            or self._settings_initialized
            or self._fishing_initialized
            or self._modal_confirm_initialized
            or in_quest_side
            or self._virtual_keyboard_open
        )
        a_pressed = (
            state.pressed("a") and not radial_held and not lt_held and not suppress_mouse
        )
        is_overworld = bool(
            getattr(self, "_memory_state", None)
            and self._memory_state.is_connected
            and self._memory_state.is_in_game
            and not self._memory_state.is_menu_open
            and not getattr(self._memory_state, "dialog_type", "")
            and not self._active_panels[0]
            and not self._active_panels[1]
        )
        want_shift = (
            a_pressed
            and is_overworld
        )

        # Walking has already aligned the cursor with the visible aim marker.
        # After stopping, an explicit attack may use the remembered heading.
        # Right-stick aiming overrides it; a scene change invalidates it.
        world = self._memory_state.world
        if (want_shift and not any(self._native_direction)
                and self._native_heading is not None and world.camera is not None
                and world.fresh(time.monotonic())
                and self._native_heading_scene == (world.player_address, world.level_address)):
            hx, hz = self._native_heading
            magnitude = max((hx * hx + hz * hz) ** .5, 1e-6)
            point = world.camera.project(replace(world.player_position,
                x=world.player_position.x + hx / magnitude * 2,
                y=world.player_position.y + hz / magnitude * 2), rect.width, rect.height)
            if point is not None:
                self.injector.move(rect.left + point[0], rect.top + point[1])

        if want_shift:
            if not self._a_shift_held:
                self._set_key("SHIFT", True)
                self._a_shift_held = True
        else:
            if self._a_shift_held:
                self._set_key("SHIFT", False)
                self._ensure_modifier_released("SHIFT")
                self._a_shift_held = False

        # Walking is an independent game-thread command. Skill release must
        # never pulse a world click; only an explicit A press owns left mouse.
        left_pressed = a_pressed
        right_pressed = (
            state.pressed("x") and not radial_held and not lt_held and not suppress_mouse
        )
        self._set_mouse("left", left_pressed)
        self._set_mouse("right", right_pressed)
        # Borda de subida do clique esquerdo: sincroniza com o fechamento de menus do jogo
        # (mesma regra do ESC/Alt+F4). Botão do painel = fecha só aquele lado; zona central
        # com os dois abertos = fechou tudo.
        if left_pressed and not self._previous_left_pressed:
            cursor_x, cursor_y = self.injector.cursor_position()
            zone = click_zone(rect, cursor_x, cursor_y, self._hud_mask)
            # Botão fechar do painel ESQUERDO: o jogo fechou só o lado esquerdo (não se aplica a T/K/E que não têm aba).
            if zone == "close_left" and self._active_panels[0] and self._active_panels[0] not in ("T", "K", "E"):
                self._active_panels[0] = ""
                self.shared.update(active_panels=list(self._active_panels))
            # Botão fechar do painel DIREITO: espelho do caso acima.
            elif zone == "close_right" and self._active_panels[1]:
                self._active_panels[1] = ""
                self.shared.update(active_panels=list(self._active_panels))
            # Ambos abertos e clique no meio (fora dos painéis E fora da HUD): o jogo
            # fechou os dois. A área verde da HUD (zone "hud") é interativa no jogo —
            # o jogador apertou um botão ali — então NUNCA zera os painéis.
            # Restringido a ambos-abertos para não interferir no click-to-move (um painel só),
            # cuja âncora ainda cai na zona central.
            elif zone == "center" and both_panels_open(self._active_panels):
                self._reset_active_panels()

        self._previous_left_pressed = left_pressed
        # Snapshot do estado de painéis para o tick seguinte: o remap contextual de
        # B/Y decide com o estado ESTÁVEL do tick anterior (ver docstring do handler).
        self._previous_panels = (self._active_panels[0], self._active_panels[1])

    def trigger_rescan(self) -> None:
        """Solicita re-enumeração e reconexão imediata do controle (ex: evento do Windows)."""
        self._rescan_requested = True

    def run(self) -> None:
        # Sobe a resolução do relógio do Windows para 1 ms (estabilidade do 120 Hz).
        engine_mod = sys.modules.get("torchbridge.engine")
        begin_timer = getattr(engine_mod, "begin_high_resolution_timer", begin_high_resolution_timer)
        end_timer = getattr(engine_mod, "end_high_resolution_timer", end_high_resolution_timer)
        hub_cls = getattr(engine_mod, "ControllerHub", ControllerHub)
        begin_timer()
        hub: ControllerHub | None = None
        last_tick = time.perf_counter()
        try:
            hub = hub_cls()
            self.injector = InputSession(self.injector, self._input_allowed)
            while not self._stop_event.is_set():
                tick_start = time.perf_counter()
                # Intervalo real desde o último tick (cursor em px/s); 'now' alimenta timeouts.
                dt = tick_start - last_tick
                last_tick = tick_start
                now = time.monotonic()

                # Evento nativo do SO (WM_DEVICECHANGE) ou solicitação externa de reconexão
                if self._rescan_requested:
                    self._rescan_requested = False
                    if hub is not None:
                        hub.trigger_rescan()

                # A cada 1 s tenta recarregar o perfil — edição externa vale na hora.
                if now - self._last_reload >= 1.0:
                    # Só avisa o usuário quando houve mudança real.
                    if self.config.reload():
                        self.shared.toast("Perfil recarregado")
                    self._last_reload = now
                # Cópia da configuração para este tick (imune a edições no meio do ciclo).
                cfg = self.config.get()
                # Estado atual do controle (SDL ou RAW, com reconexão automática).
                state = hub.poll(cfg["raw_controller"], cfg["input"]["device_guid"])
                # Janela do Torchlight (usa cache; varre com EnumWindows quando preciso).
                hwnd = self.locator.find()
                # Área útil da janela em coordenadas de tela; vazia sem janela.
                rect = self.locator.client_rect(hwnd) if hwnd else Rect()
                # Jogo presente e com área utilizável?
                game_found = bool(hwnd and rect.valid)
                # E está em primeiro plano — condição que autoriza enviar entrada.
                game_active = bool(game_found and self.locator.is_foreground(hwnd))
                target_pid = self.locator.window_pid(hwnd) if hwnd else None
                enabled = self.is_enabled()

                # Controle conectado (novo ou religado): avisa e vibra para confirmar.
                if state.connected and (state.name != self._last_controller_name or
                                        state.instance_id != self._last_controller_instance):
                    self._release_all()
                    self._last_controller_name = state.name
                    self._last_controller_instance = state.instance_id
                    self.shared.toast(f"Controle conectado: {state.name}", 3.0)
                    hub.rumble()
                    self._previous = state
                # Controle desconectado: avisa — o release_all abaixo solta o que estava retido.
                elif not state.connected and self._last_controller_name:
                    self.shared.toast("Controle desconectado", 2.5)
                    self._last_controller_name = ""
                    self._last_controller_instance = None

                # Jogo acabou de aparecer: aviso único (sem spam a cada tick).
                if game_found and (not self._game_was_found or target_pid != self._last_game_pid):
                    self._release_all()
                    self.memory.close()
                    self._memory_state = GameMemoryState()
                    self._memory_last_read = 0.0
                    self.shared.toast("Torchlight detectado", 2.5)
                    # Sessão nova: reseta painéis/seleção da roda (Alt+F4 não limpou o estado).
                    self._reset_radial_session()
                elif not game_found and self._game_was_found:
                    # Jogo acabou de fechar: libera handle da memória e limpa estados residuais
                    self.memory.close()
                    self._reset_radial_session()

                # Guarda o estado de detecção para as bordas (subida/descida).
                self._game_was_found = game_found
                self._last_game_pid = target_pid

                # Leitura periódica da memória RAM do Torchlight (a cada 20 ms / 50 Hz)
                if now - self._memory_last_read >= 0.020:
                    self._memory_state = self.memory.update(target_pid=target_pid or -1)
                    self._memory_last_read = now

                    # Sincroniza classe e reseta aba de skills ao trocar de personagem
                    if self._memory_state.is_in_game:
                        mem_cls = (getattr(self._memory_state, "char_class", "") or "").strip().lower()
                        if mem_cls in ("destroyer", "vanquisher", "alchemist"):
                            if self._char_class != mem_cls:
                                self._char_class = mem_cls
                                self._skill_tab = 1
                                self._skill_menu_initialized = False
                                self.shared.update(char_class=mem_cls, skill_tab=1)
                    else:
                        if self._char_class:
                            self._char_class = ""
                            self._skill_tab = 1
                            self._skill_menu_initialized = False
                            self.shared.update(char_class="", skill_tab=1)

                    # Sincroniza painéis ativos se estiver em jogo
                    if self._memory_state.is_in_game:
                        left = ""
                        if "Pet" in self._memory_state.open_menus:
                            left = "P"
                        elif "Atributos" in self._memory_state.open_menus:
                            left = "C"
                        elif "Transmutador" in self._memory_state.open_menus:
                            left = "T"
                        elif "Sockets" in self._memory_state.open_menus:
                            left = "K"
                        elif "Encantador" in self._memory_state.open_menus:
                            left = "E"
                        elif "Vendedor (Loja)" in self._memory_state.open_menus:
                            left = "V"
                        elif "Baú" in self._memory_state.open_menus:
                            left = "B"

                        right = ""
                        if "Inventário" in self._memory_state.open_menus:
                            right = "I"
                        elif "Habilidades" in self._memory_state.open_menus:
                            right = "S"
                        elif "Missões (Quests)" in self._memory_state.open_menus:
                            right = "Q"
                        elif "Diário (Journal)" in self._memory_state.open_menus:
                            right = "J"
                        elif "Portal (Waypoint)" in self._memory_state.open_menus:
                            right = "W"

                        self._active_panels = [left, right]

                # Memory sampling happens after the tick started. Use a current
                # clock so a fresh world sample is never treated as future data.
                now = time.monotonic()
                effective_mode = (
                    "blocked"
                    if self._memory_state.is_loading
                    else (
                        "cursor"
                        if (
                            self._memory_state.is_connected
                            and (self._memory_state.is_menu_open or not self._memory_state.is_in_game)
                        )
                        else self._mode
                    )
                )

                # Publica o estado completo para o overlay Qt (thread-safe).
                self.shared.update(
                    enabled=enabled and bool(cfg["overlay"].get("enabled", True)),
                    game_found=game_found,
                    game_active=game_active,
                    game_rect=rect,
                    game_hwnd=hwnd,
                    game_pid=target_pid,
                    controller_connected=state.connected,
                    controller_devices=hub.devices,
                    controller_name=state.name,
                    controller_mapping=state.mapping,
                    controller_type=state.controller_type,
                    mode=effective_mode,
                    active_panels=list(self._active_panels),
                    memory_state_desc=self._memory_state.state_desc,
                    memory_is_in_game=self._memory_state.is_in_game,
                    memory_is_loading=self._memory_state.is_loading,
                    memory_is_menu_open=self._memory_state.is_menu_open,
                    memory_open_menus=list(self._memory_state.open_menus),
                    world=self._memory_state.world,
                    char_name_len=self._memory_state.char_name_len,
                    title_menu_focus=self._title_focus if (self._memory_state.is_connected and self._memory_state.state_id == 0) else None,
                    dialog_focus=self._dialog_focus if (self._memory_state.is_connected and self._memory_state.dialog_type) else None,
                    dialog_type=self._memory_state.dialog_type if self._memory_state.is_connected else "",
                    dialog_buttons=list(self._memory_state.dialog_buttons) if self._memory_state.is_connected else [],
                    inventory_open=self._inventory_initialized,
                    inventory_tab=self._inventory_tab,
                    inventory_focus=str(self._inventory_focus) if self._inventory_focus else None,
                    pet_inventory_open=self._pet_inventory_initialized,
                    pet_inventory_tab=self._pet_inventory_tab,
                    pet_inventory_focus=str(self._pet_inventory_focus) if self._pet_inventory_focus else None,
                    stash_open=self._stash_initialized,
                    stash_tab=self._stash_tab,
                    stash_focus=str(self._stash_focus) if self._stash_focus else None,
                    char_menu_open=self._char_menu_initialized,
                    char_menu_focus=self._char_menu_focus if self._char_menu_initialized else None,
                    skill_menu_open=self._skill_menu_initialized,
                    skill_tab=self._skill_tab,
                    skill_focus=(
                        f"tab_{self._skill_focus_col + 1}" if self._skill_in_tabbar else (
                            f"({self._skill_focus_row}, {self._skill_focus_col}, pink)" if self._skill_in_pink else f"({self._skill_focus_row}, {self._skill_focus_col})"
                        )
                    ) if self._skill_menu_initialized else None,
                    quest_menu_open=self._quest_menu_initialized and ("Missões (Quests)" in (self._memory_state.open_menus or [])),
                    quest_focus=self._quest_focus if self._quest_menu_initialized else None,
                    quest_count=getattr(self._memory_state, "quest_count", 0) if self._quest_menu_initialized else 0,
                    quest_selected_idx=self._last_quest_slot if self._quest_menu_initialized else 0,
                    quest_visible_rows=getattr(self._memory_state, "quest_visible_rows", 0) if self._quest_menu_initialized else 0,
                    quest_can_abandon=getattr(self._memory_state, "quest_can_abandon", False) if self._quest_menu_initialized else False,
                    quest_has_item_reward=getattr(self._memory_state, "quest_has_item_reward", False) if self._quest_menu_initialized else False,
                    char_class=self._char_class or getattr(self._memory_state, "char_class", "").lower(),
                    attr_points_remaining=getattr(self._memory_state, "attr_points_remaining", 0),
                    skill_points_remaining=getattr(self._memory_state, "skill_points_remaining", 0),
                    skill_upgradeable=dict(getattr(self._memory_state, "skill_upgradeable", {})),
                )

                # PORTÃO DE SEGURANÇA: comandos só saem com jogo em foco, habilitado e controle conectado.
                if enabled and not self.memory.last_error and game_active and state.connected:
                    if self._memory_state.is_loading:
                        self._release_all()
                    else:
                        state = self._prepare_active_state(state)
                        self._input_context = (hub, hwnd, target_pid, state.instance_id, cfg)
                        try:
                            self._process_active(hub, state, rect, cfg, now, dt)
                        except InputCancelled:
                            self._release_all()
                        finally:
                            self._input_context = None
                # Qualquer interrupção (pausa, jogo em segundo plano, sem controle): libera tudo.
                # As bordas dos gatilhos continuam acompanhando o hardware NOS TICKS
                # INATIVOS (dentro de _process_active no tick ativo): um gatilho
                # segurado através de uma perda de foco não vaza toque falso ao retomar.
                else:
                    self._update_trigger_edges(state)
                    self._release_all()

                self.shared.update(engine_error=self.memory.last_error)
                self._previous = state
                # Duração do tick alvo (1/120 s por padrão).
                period = 1.0 / float(cfg["input"]["poll_hz"])
                remaining = period - (time.perf_counter() - tick_start)
                # Dorme o restante do período para manter a taxa configurada.
                if remaining > 0:
                    self._stop_event.wait(remaining)
        # Erro inesperado não derruba em silêncio: loga e mostra toast com o caminho do log.
        except Exception:
            log.exception("Falha fatal no loop de entrada")
            self.shared.update(engine_error="Erro no motor; consulte torchbridge.log")
            self.shared.toast("Erro no motor; consulte torchbridge.log", 8.0)
        # Garantias finais: solta entradas, desconecta o controle e restaura o relógio do Windows.
        finally:
            self.shared.update(game_active=False, game_found=False, game_hwnd=None, game_pid=None)
            try:
                for attempt in range(3):
                    self._release_all()
                    pending = self._held_keys or self._held_mouse
                    if isinstance(self.injector, InputSession):
                        pending = pending or self.injector.keys or self.injector.mouse
                    if not pending:
                        break
                    if attempt < 2:
                        time.sleep(0.005)
                if pending:
                    log.warning("Entradas pendentes de liberação ao encerrar o motor")
            finally:
                try:
                    if hub is not None:
                        hub.close()
                finally:
                    self.memory.close()
                    injector = self.injector.injector if isinstance(self.injector, InputSession) else self.injector
                    close = getattr(injector, "close", None)
                    if close is not None:
                        close()
                    end_timer()
