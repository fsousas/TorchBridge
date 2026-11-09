from __future__ import annotations

from ..controller import ControllerHub
from ..mathutils import clamp
from ..models import (
    ControllerState,
    INVENTORY_UPPER_NAV_MAP,
    PET_UPPER_NAV_MAP,
    Rect,
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    char_menu_point,
    crafting_button_point,
    crafting_slot_point,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    merchant_slot_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    pet_inventory_upper_point,
    quest_slot_point,
    skill_bridge_col,
    skill_slot_point,
    skill_spell_slot_point,
    stash_upper_slot_point,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class InventoryNavigationMixin:
    """Mixin com métodos de navegação para inventory."""

    def _handle_inventory_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos slots e abas do Inventário do jogador via D-pad e L2/R2."""
        if not rect.valid:
            return

        # 1. Inicialização ao abrir o inventário: abre sempre na Tab 1 e no Slot 1 do grid (739.5, 520.5)
        if not self._inventory_initialized:
            self._inventory_initialized = True
            self._inventory_tab = "tab-1"
            self._inventory_focus = (1, 1)
            target_x, target_y = inventory_slot_point(rect, 1, 1)
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                inventory_open=True,
                inventory_tab=self._inventory_tab,
                inventory_focus="(1, 1)",
            )
            return

        cur_x, cur_y = self.injector.cursor_position()
        is_right_half = (cur_x >= rect.left + rect.width * 0.5)

        # 2. Troca de abas via L2 ou R2 (somente se o cursor estiver na metade direita da tela)
        # R2 avança: 1 -> 2 -> 3 -> 1
        # L2 volta:  1 -> 3 -> 2 -> 1
        if is_right_half and (self._rt_edge_up or self._lt_edge_up):
            curr_tab_num = 1
            if self._inventory_tab:
                try:
                    curr_tab_num = int(self._inventory_tab.replace("tab-", ""))
                except Exception:
                    curr_tab_num = 1

            if self._rt_edge_up:
                new_tab_num = (curr_tab_num % 3) + 1
            else:
                new_tab_num = 3 if curr_tab_num == 1 else curr_tab_num - 1

            tab_x, tab_y = inventory_tab_point(rect, new_tab_num)
            # Sequência calibrada para o jogo registrar o hover e o clique da aba:
            # 1. Move o cursor para a aba correspondente
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)  # Espera 60ms para o jogo registrar o hover sobre a aba

            # 2. Clica na aba com hold suficiente
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)  # Hold do clique de 40ms
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)  # Espera pós-clique de 30ms

            self._inventory_tab = f"tab-{new_tab_num}"
            self._inventory_focus = (1, 1)

            # 3. Retorna o cursor para o quadrado amarelo (Slot 1: linha 1, col 1)
            slot_x, slot_y = inventory_slot_point(rect, 1, 1)
            self.injector.move(slot_x, slot_y)
            hub.rumble(0.05, 0.12, 40)

            self.shared.update(
                inventory_open=True,
                inventory_tab=self._inventory_tab,
                inventory_focus="(1, 1)",
            )
            return

        # 3. Navegação via D-pad
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        current = self._inventory_focus or (1, 1)
        new_focus: tuple[int, int] | str = current

        is_pet_open = "Pet" in (self._memory_state.open_menus or [])
        is_stash_open = "Baú" in (self._memory_state.open_menus or [])
        is_merchant_open = "Vendedor (Loja)" in (self._memory_state.open_menus or [])
        is_crafting_open = any(m in (self._memory_state.open_menus or []) for m in ("Transmutador", "Sockets", "Encantador"))
        is_char_open = "Atributos" in (self._memory_state.open_menus or [])

        if isinstance(current, tuple):
            row, col = current
            if dpad_right:
                if col < 7:
                    new_focus = (row, col + 1)
                elif row == 1:
                    new_focus = (2, 1)
                elif row == 2:
                    new_focus = (3, 1)
                elif row == 3:
                    new_focus = (1, 1)
            elif dpad_left:
                if col > 1:
                    new_focus = (row, col - 1)
                elif is_char_open:
                    # Ponte para o Menu de Personagem/Atributos (C):
                    # Linha 1 (1, 1) -> defense_bridge
                    # Linha 2 (2, 1) -> res_fire
                    # Linha 3 (3, 1) -> res_ice
                    has_points = getattr(self._memory_state, "attr_points_remaining", 0) > 0
                    if row == 1:
                        char_target = "defense_bridge"
                    elif row == 2:
                        char_target = "res_fire"
                    else:
                        char_target = "res_ice"

                    target_x, target_y = char_menu_point(rect, char_target, has_points=has_points)
                    self._char_menu_focus = char_target
                    self._char_menu_initialized = True
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        char_menu_open=True,
                        char_menu_focus=char_target,
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus=f"({row}, 1)",
                    )
                    return
                elif is_crafting_open:
                    # Ponte para Crafting (Transmutador / Sockets / Encantador)
                    active_craft = next((m for m in ("Transmutador", "Sockets", "Encantador") if m in (self._memory_state.open_menus or [])), "Transmutador")
                    if active_craft == "Transmutador":
                        if row == 1:
                            craft_focus = "slot_1"
                            target_x, target_y = crafting_slot_point(rect, active_craft, 1)
                        elif row == 2:
                            craft_focus = "slot_3"
                            target_x, target_y = crafting_slot_point(rect, active_craft, 3)
                        else:
                            craft_focus = "decline"
                            target_x, target_y = crafting_button_point(rect, active_craft, "decline")
                    else:
                        if row == 1:
                            craft_focus = "slot_0"
                            target_x, target_y = crafting_slot_point(rect, active_craft, 0)
                        elif row == 2:
                            craft_focus = "decline"
                            target_x, target_y = crafting_button_point(rect, active_craft, "decline")
                        else:
                            craft_focus = "action"
                            target_x, target_y = crafting_button_point(rect, active_craft, "action")
                    self._crafting_focus = craft_focus
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        crafting_open=True,
                        crafting_menu=active_craft,
                        crafting_focus=self._crafting_focus,
                    )
                    return
                elif is_merchant_open:
                    # Ponte para o Mercador (Pet inferior): Coluna 1 do Inventário -> Coluna 7 do Pet
                    target_x, target_y = pet_inventory_slot_point(rect, row, 7)
                    self._merchant_focus = ("pet", row, 7)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        merchant_open=True,
                        merchant_tab=self._merchant_tab or "tab-1",
                        merchant_focus=f"('pet', {row}, 7)",
                    )
                    return
                elif is_stash_open:
                    # Ponte para o Baú (Pet inferior): Coluna 1 do Inventário -> Coluna 7 do Pet
                    target_x, target_y = pet_inventory_slot_point(rect, row, 7)
                    self._stash_focus = ("pet", row, 7)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        stash_open=True,
                        stash_tab=self._stash_tab or "tab-1",
                        stash_focus=f"('pet', {row}, 7)",
                    )
                    return
                elif is_pet_open:
                    # Ponte para o Pet: Coluna 1 do Inventário -> Coluna 7 do Pet
                    target_x, target_y = pet_inventory_slot_point(rect, row, 7)
                    self._pet_inventory_focus = (row, 7)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        pet_inventory_open=True,
                        pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                        pet_inventory_focus=f"({row}, 7)",
                    )
                    return
                elif row == 1:
                    new_focus = (3, 7)
                elif row == 2:
                    new_focus = (1, 7)
                elif row == 3:
                    new_focus = (2, 7)
            elif dpad_down:
                if row < 3:
                    new_focus = (row + 1, col)
                else:
                    new_focus = current
            elif dpad_up:
                if row > 1:
                    new_focus = (row - 1, col)
                else:
                    if col in (1, 2):
                        new_focus = "spell_1"
                    elif col in (3, 4):
                        new_focus = "spell_2"
                    elif col == 5:
                        new_focus = "spell_3"
                    else:
                        new_focus = "spell_4"
        else:
            if is_char_open and dpad_left and str(current) in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
                # Ponte para o Menu de Personagem/Atributos (C):
                has_points = getattr(self._memory_state, "attr_points_remaining", 0) > 0
                INV_TO_CHAR_MAP = {
                    "helmet": "xp",
                    "gloves": "mp",
                    "belt": "strength_bridge",
                    "main_hand": "dexterity_bridge",
                    "spell_1": "magic_bridge",
                }
                char_target = INV_TO_CHAR_MAP.get(str(current), "defense_bridge")
                target_x, target_y = char_menu_point(rect, char_target, has_points=has_points)
                self._char_menu_focus = char_target
                self._char_menu_initialized = True
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    char_menu_open=True,
                    char_menu_focus=char_target,
                    inventory_open=True,
                    inventory_tab=self._inventory_tab or "tab-1",
                    inventory_focus=str(current),
                )
                return
            elif is_crafting_open and dpad_left and str(current) in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
                active_craft = next((m for m in ("Transmutador", "Sockets", "Encantador") if m in (self._memory_state.open_menus or [])), "Transmutador")
                if active_craft == "Transmutador":
                    if str(current) in ("helmet", "gloves"):
                        craft_focus = "slot_1"
                        target_x, target_y = crafting_slot_point(rect, active_craft, 1)
                    elif str(current) == "belt":
                        craft_focus = "slot_3"
                        target_x, target_y = crafting_slot_point(rect, active_craft, 3)
                    elif str(current) == "main_hand":
                        craft_focus = "decline"
                        target_x, target_y = crafting_button_point(rect, active_craft, "decline")
                    else:  # spell_1
                        craft_focus = "action"
                        target_x, target_y = crafting_button_point(rect, active_craft, "action")
                else:
                    if str(current) in ("helmet", "gloves"):
                        craft_focus = "slot_0"
                        target_x, target_y = crafting_slot_point(rect, active_craft, 0)
                    elif str(current) == "belt":
                        craft_focus = "decline"
                        target_x, target_y = crafting_button_point(rect, active_craft, "decline")
                    else:
                        craft_focus = "action"
                        target_x, target_y = crafting_button_point(rect, active_craft, "action")
                self._crafting_focus = craft_focus
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    crafting_open=True,
                    crafting_menu=active_craft,
                    crafting_focus=self._crafting_focus,
                )
                return
            elif is_merchant_open and dpad_left and str(current) in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
                # Ponte para o Mercador: Borda esquerda superior do Inventário -> Coluna 7 do Mercador Superior
                INV_TO_MERCHANT_MAP = {
                    "helmet": 1,
                    "gloves": 2,
                    "belt": 3,
                    "main_hand": 5,
                    "spell_1": 6,
                }
                merchant_row = INV_TO_MERCHANT_MAP.get(str(current), 6)
                target_x, target_y = merchant_slot_point(rect, merchant_row, 7)
                self._merchant_focus = ("merchant", merchant_row, 7)
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    merchant_open=True,
                    merchant_tab=self._merchant_tab or "tab-1",
                    merchant_focus=f"('merchant', {merchant_row}, 7)",
                )
                return
            elif is_stash_open and dpad_left and str(current) in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
                # Ponte para o Baú: Borda esquerda superior do Inventário -> Coluna 7 do Baú Superior
                INV_TO_STASH_MAP = {
                    "helmet": 1,
                    "gloves": 2,
                    "belt": 3,
                    "main_hand": 5,
                    "spell_1": 6,
                }
                stash_row = INV_TO_STASH_MAP.get(str(current), 6)
                target_x, target_y = stash_upper_slot_point(rect, stash_row, 7)
                self._stash_focus = ("stash", stash_row, 7)
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    stash_open=True,
                    stash_tab=self._stash_tab or "tab-1",
                    stash_focus=f"('stash', {stash_row}, 7)",
                )
                return
            elif is_pet_open and dpad_left and str(current) in ("spell_1", "main_hand", "belt", "gloves", "helmet"):
                # Ponte para o Pet: Borda esquerda superior do Inventário -> pet_spell_2 do Pet
                target_x, target_y = pet_inventory_upper_point(rect, "pet_spell_2")
                self._pet_inventory_focus = "pet_spell_2"
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    pet_inventory_open=True,
                    pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                    pet_inventory_focus="pet_spell_2",
                )
                return

            direction = "up" if dpad_up else ("down" if dpad_down else ("left" if dpad_left else "right"))
            nav = INVENTORY_UPPER_NAV_MAP.get(str(current), {})
            if direction in nav:
                new_focus = nav[direction]

        if new_focus != current:
            self._inventory_focus = new_focus
            if isinstance(new_focus, tuple):
                target_x, target_y = inventory_slot_point(rect, new_focus[0], new_focus[1])
            else:
                target_x, target_y = inventory_upper_point(rect, str(new_focus))

            self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                inventory_open=True,
                inventory_tab=self._inventory_tab or "tab-1",
                inventory_focus=str(new_focus),
            )

    def _handle_pet_inventory_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos slots e abas do menu de Pet via D-pad e L2/R2."""
        if not rect.valid:
            return

        # 1. Inicialização ao abrir o menu de pet: abre sempre na Tab 1 e no Slot 1 do grid (56.5, 523.5)
        if not self._pet_inventory_initialized:
            self._pet_inventory_initialized = True
            self._pet_inventory_tab = "tab-1"
            self._pet_inventory_focus = (1, 1)
            target_x, target_y = pet_inventory_slot_point(rect, 1, 1)
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                pet_inventory_open=True,
                pet_inventory_tab=self._pet_inventory_tab,
                pet_inventory_focus="(1, 1)",
            )
            return

        cur_x, cur_y = self.injector.cursor_position()
        is_left_half = (cur_x < rect.left + rect.width * 0.5)

        # 2. Troca de abas via L2 ou R2 (somente se o cursor estiver na metade esquerda da tela)
        # R2 avança: 1 -> 2 -> 3 -> 1
        # L2 volta:  1 -> 3 -> 2 -> 1
        if is_left_half and (self._rt_edge_up or self._lt_edge_up):
            curr_tab_num = 1
            if self._pet_inventory_tab:
                try:
                    curr_tab_num = int(self._pet_inventory_tab.replace("tab-", ""))
                except Exception:
                    curr_tab_num = 1

            if self._rt_edge_up:
                new_tab_num = (curr_tab_num % 3) + 1
            else:
                new_tab_num = 3 if curr_tab_num == 1 else curr_tab_num - 1

            tab_x, tab_y = pet_inventory_tab_point(rect, new_tab_num)
            # Sequência calibrada para o jogo registrar o hover e o clique da aba:
            # 1. Move o cursor para a aba correspondente
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)  # Espera 60ms para o jogo registrar o hover sobre a aba

            # 2. Clica na aba com hold suficiente
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)  # Hold do clique de 40ms
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)  # Espera pós-clique de 30ms

            self._pet_inventory_tab = f"tab-{new_tab_num}"
            self._pet_inventory_focus = (1, 1)

            # 3. Retorna o cursor para o quadrado amarelo (Slot 1: linha 1, col 1)
            slot_x, slot_y = pet_inventory_slot_point(rect, 1, 1)
            self.injector.move(slot_x, slot_y)
            hub.rumble(0.05, 0.12, 40)

            self.shared.update(
                pet_inventory_open=True,
                pet_inventory_tab=self._pet_inventory_tab,
                pet_inventory_focus="(1, 1)",
            )
            return

        # 3. Navegação via D-pad
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        current = self._pet_inventory_focus or (1, 1)
        new_focus: tuple[int, int] | str = current

        is_inv_open = "Inventário" in (self._memory_state.open_menus or [])
        is_skills_open = "Habilidades" in (self._memory_state.open_menus or [])
        is_quest_open = "Missões (Quests)" in (self._memory_state.open_menus or [])

        if isinstance(current, tuple):
            row, col = current
            if dpad_right:
                if col < 7:
                    new_focus = (row, col + 1)
                elif is_inv_open:
                    # Ponte para o Inventário: Coluna 7 do Pet -> Coluna 1 do Inventário
                    target_x, target_y = inventory_slot_point(rect, row, 1)
                    self._inventory_focus = (row, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus=f"({row}, 1)",
                    )
                    return
                elif is_skills_open:
                    # Ponte para o Menu de Habilidades (Skill Tree)
                    char_cls = self._char_class or "alchemist"
                    tab_name = SKILL_TAB_NAMES.get(char_cls, {}).get(self._skill_tab, "arcane")
                    layout = SKILL_TREE_LAYOUTS.get(char_cls, {}).get(tab_name, [])

                    if row == 1:
                        s_row = 4
                        row_layout = layout[s_row] if s_row < len(layout) else layout[0]
                        s_col = skill_bridge_col(row_layout) if skill_bridge_col(row_layout) is not None else 0
                        self._skill_focus_row = s_row
                        self._skill_focus_col = s_col
                        self._skill_in_tabbar = False
                        self._skill_in_pink = False
                        self._skill_in_spells = False
                        self._skill_menu_initialized = True
                        target_x, target_y = skill_slot_point(rect, s_row, s_col)
                        focus_str = f"({s_row}, {s_col})"
                    elif row == 2:
                        s_row = 5
                        row_layout = layout[s_row] if s_row < len(layout) else layout[0]
                        s_col = skill_bridge_col(row_layout) if skill_bridge_col(row_layout) is not None else 0
                        self._skill_focus_row = s_row
                        self._skill_focus_col = s_col
                        self._skill_in_tabbar = False
                        self._skill_in_pink = False
                        self._skill_in_spells = False
                        self._skill_menu_initialized = True
                        target_x, target_y = skill_slot_point(rect, s_row, s_col)
                        focus_str = f"({s_row}, {s_col})"
                    else:  # row == 3
                        self._skill_in_spells = True
                        self._skill_spell_idx = 0
                        self._skill_in_tabbar = False
                        self._skill_in_pink = False
                        self._skill_menu_initialized = True
                        target_x, target_y = skill_spell_slot_point(rect, 0)
                        focus_str = "spell_0"

                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        pet_inventory_open=True,
                        pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                        pet_inventory_focus=f"({row}, 7)",
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=focus_str,
                    )
                    return
                elif is_quest_open:
                    # Ponte para o Menu de Quests: pula para a quest ativa selecionada
                    q_idx = getattr(self._memory_state, "quest_selected_idx", 0) or 0
                    q_rows = getattr(self._memory_state, "quest_visible_rows", 1) or 1
                    target_idx = int(clamp(q_idx, 0, max(0, q_rows - 1)))
                    self._quest_menu_initialized = True
                    self._quest_focus = f"quest_{target_idx}"
                    self._last_quest_slot = target_idx
                    target_x, target_y = quest_slot_point(rect, target_idx)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        pet_inventory_open=True,
                        pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                        pet_inventory_focus=f"({row}, 7)",
                        quest_menu_open=True,
                        quest_focus=self._quest_focus,
                    )
                    return
                elif row == 1:
                    new_focus = (2, 1)
                elif row == 2:
                    new_focus = (3, 1)
                elif row == 3:
                    new_focus = (1, 1)
            elif dpad_left:
                if col > 1:
                    new_focus = (row, col - 1)
                elif row == 1:
                    new_focus = (3, 7)
                elif row == 2:
                    new_focus = (1, 7)
                elif row == 3:
                    new_focus = (2, 7)
            elif dpad_down:
                if row < 3:
                    new_focus = (row + 1, col)
                else:
                    new_focus = current
            elif dpad_up:
                if row > 1:
                    new_focus = (row - 1, col)
                else:
                    if col in (1, 2):
                        new_focus = "pet_spell_1"
                    elif col == 3:
                        new_focus = "pet_ring_1"
                    elif col == 4:
                        new_focus = "pet_collar"
                    elif col == 5:
                        new_focus = "pet_ring_2"
                    else:
                        new_focus = "pet_spell_2"
        else:
            if is_inv_open and dpad_right and str(current) == "pet_spell_2":
                # Ponte para o Inventário: pet_spell_2 do Pet -> spell_1 do Inventário
                target_x, target_y = inventory_upper_point(rect, "spell_1")
                self._inventory_focus = "spell_1"
                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    inventory_open=True,
                    inventory_tab=self._inventory_tab or "tab-1",
                    inventory_focus="spell_1",
                )
                return
            elif is_skills_open and dpad_right and str(current) == "pet_spell_2":
                # Ponte para o Menu de Habilidades: pet_spell_2 -> Linha 0 (nó laranja) da Skill Tree
                char_cls = self._char_class or "alchemist"
                tab_name = SKILL_TAB_NAMES.get(char_cls, {}).get(self._skill_tab, "arcane")
                layout = SKILL_TREE_LAYOUTS.get(char_cls, {}).get(tab_name, [])
                s_row = 0
                row_layout = layout[s_row] if s_row < len(layout) else layout[0]
                s_col = skill_bridge_col(row_layout) if skill_bridge_col(row_layout) is not None else 0

                self._skill_focus_row = s_row
                self._skill_focus_col = s_col
                self._skill_in_tabbar = False
                self._skill_in_pink = False
                self._skill_in_spells = False
                self._skill_menu_initialized = True
                target_x, target_y = skill_slot_point(rect, s_row, s_col)

                self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    pet_inventory_open=True,
                    pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                    pet_inventory_focus="pet_spell_2",
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({s_row}, {s_col})",
                )
                return
            elif is_quest_open and dpad_right and str(current) == "pet_spell_2":
                # Ponte para o Menu de Quests: pet_spell_2 -> quest ativa selecionada
                q_idx = getattr(self._memory_state, "quest_selected_idx", 0) or 0
                q_rows = getattr(self._memory_state, "quest_visible_rows", 1) or 1
                target_idx = int(clamp(q_idx, 0, max(0, q_rows - 1)))
                self._quest_menu_initialized = True
                self._quest_focus = f"quest_{target_idx}"
                self._last_quest_slot = target_idx
                target_x, target_y = quest_slot_point(rect, target_idx)
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    pet_inventory_open=True,
                    pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                    pet_inventory_focus="pet_spell_2",
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                )
                return

            direction = "up" if dpad_up else ("down" if dpad_down else ("left" if dpad_left else "right"))
            nav = PET_UPPER_NAV_MAP.get(str(current), {})
            if direction in nav:
                new_focus = nav[direction]

        if new_focus != current:
            self._pet_inventory_focus = new_focus
            if isinstance(new_focus, tuple):
                target_x, target_y = pet_inventory_slot_point(rect, new_focus[0], new_focus[1])
            else:
                target_x, target_y = pet_inventory_upper_point(rect, str(new_focus))

            self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                pet_inventory_open=True,
                pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                pet_inventory_focus=str(new_focus),
            )

    def _handle_stash_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos slots do Baú (grid 6x7) e Pet inferior (grid 3x7 + abas) via D-pad e L2/R2."""
        if not rect.valid:
            return

        # 1. Inicialização ao abrir o Baú: abre sempre na Tab 1 do Pet e no Slot 1 do grid inferior (56.5, 523.5)
        if not self._stash_initialized:
            self._stash_initialized = True
            self._stash_tab = "tab-1"
            self._stash_focus = ("pet", 1, 1)
            target_x, target_y = pet_inventory_slot_point(rect, 1, 1)
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                stash_open=True,
                stash_tab=self._stash_tab,
                stash_focus="('pet', 1, 1)",
            )
            return

        cur_x, cur_y = self.injector.cursor_position()
        is_left_half = (cur_x < rect.left + rect.width * 0.5)

        # 2. Troca de abas via L2 ou R2 (somente se o cursor estiver na metade esquerda da tela)
        # R2 avança: 1 -> 2 -> 3 -> 1
        # L2 volta:  1 -> 3 -> 2 -> 1
        if is_left_half and (self._rt_edge_up or self._lt_edge_up):
            curr_tab_num = 1
            if self._stash_tab:
                try:
                    curr_tab_num = int(self._stash_tab.replace("tab-", ""))
                except Exception:
                    curr_tab_num = 1

            if self._rt_edge_up:
                new_tab_num = (curr_tab_num % 3) + 1
            else:
                new_tab_num = 3 if curr_tab_num == 1 else curr_tab_num - 1

            tab_x, tab_y = pet_inventory_tab_point(rect, new_tab_num)
            # Sequência calibrada para o jogo registrar o hover e o clique da aba:
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)

            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)

            self._stash_tab = f"tab-{new_tab_num}"
            self._stash_focus = ("pet", 1, 1)

            slot_x, slot_y = pet_inventory_slot_point(rect, 1, 1)
            self.injector.move(slot_x, slot_y)
            hub.rumble(0.05, 0.12, 40)

            self.shared.update(
                stash_open=True,
                stash_tab=self._stash_tab,
                stash_focus="('pet', 1, 1)",
            )
            return

        # 3. Navegação via D-pad
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        current = self._stash_focus or ("pet", 1, 1)
        sec, row, col = current
        new_focus = current

        is_inv_open = "Inventário" in (self._memory_state.open_menus or [])

        if sec == "pet":
            if dpad_right:
                if col < 7:
                    new_focus = ("pet", row, col + 1)
                elif is_inv_open:
                    # Ponte para o Inventário: Coluna 7 do Pet -> Coluna 1 do Inventário
                    target_x, target_y = inventory_slot_point(rect, row, 1)
                    self._inventory_focus = (row, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus=f"({row}, 1)",
                    )
                    return
                elif row == 1:
                    new_focus = ("pet", 2, 1)
                elif row == 2:
                    new_focus = ("pet", 3, 1)
                elif row == 3:
                    new_focus = ("pet", 1, 1)
            elif dpad_left:
                if col > 1:
                    new_focus = ("pet", row, col - 1)
                elif row == 1:
                    new_focus = ("pet", 3, 7)
                elif row == 2:
                    new_focus = ("pet", 1, 7)
                elif row == 3:
                    new_focus = ("pet", 2, 7)
            elif dpad_down:
                if row < 3:
                    new_focus = ("pet", row + 1, col)
                else:
                    new_focus = current
            elif dpad_up:
                if row > 1:
                    new_focus = ("pet", row - 1, col)
                else:
                    # Transição vertical para a Linha 6 do Baú superior
                    new_focus = ("stash", 6, col)

        elif sec == "stash":
            if dpad_right:
                if col < 7:
                    new_focus = ("stash", row, col + 1)
                elif is_inv_open:
                    # Ponte para o Inventário: Coluna 7 do Baú -> Equipamentos/Spells do Inventário
                    STASH_TO_INV_MAP = {
                        1: "helmet",
                        2: "gloves",
                        3: "belt",
                        4: "belt",
                        5: "main_hand",
                        6: "spell_1",
                    }
                    target_slot = STASH_TO_INV_MAP.get(row, "spell_1")
                    target_x, target_y = inventory_upper_point(rect, target_slot)
                    self._inventory_focus = target_slot
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus=target_slot,
                    )
                    return
                elif row == 1:
                    new_focus = ("stash", 2, 1)
                elif row == 2:
                    new_focus = ("stash", 3, 1)
                elif row == 3:
                    new_focus = ("stash", 4, 1)
                elif row == 4:
                    new_focus = ("stash", 5, 1)
                elif row == 5:
                    new_focus = ("stash", 6, 1)
                elif row == 6:
                    new_focus = ("stash", 1, 1)
            elif dpad_left:
                if col > 1:
                    new_focus = ("stash", row, col - 1)
                elif row == 1:
                    new_focus = ("stash", 6, 7)
                elif row == 2:
                    new_focus = ("stash", 1, 7)
                elif row == 3:
                    new_focus = ("stash", 2, 7)
                elif row == 4:
                    new_focus = ("stash", 3, 7)
                elif row == 5:
                    new_focus = ("stash", 4, 7)
                elif row == 6:
                    new_focus = ("stash", 5, 7)
            elif dpad_up:
                if row > 1:
                    new_focus = ("stash", row - 1, col)
                else:
                    new_focus = current
            elif dpad_down:
                if row < 6:
                    new_focus = ("stash", row + 1, col)
                else:
                    # Transição vertical para a Linha 1 do Pet inferior
                    new_focus = ("pet", 1, col)

        if new_focus != current:
            self._stash_focus = new_focus
            if new_focus[0] == "pet":
                target_x, target_y = pet_inventory_slot_point(rect, new_focus[1], new_focus[2])
            else:
                target_x, target_y = stash_upper_slot_point(rect, new_focus[1], new_focus[2])

            self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                stash_open=True,
                stash_tab=self._stash_tab or "tab-1",
                stash_focus=str(new_focus),
            )
