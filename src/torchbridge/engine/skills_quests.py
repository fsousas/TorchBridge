from __future__ import annotations

import time

from ..controller import ControllerHub
from ..mathutils import clamp
from ..models import (
    CHAR_MENU_NODES_HAS_POINTS,
    CHAR_MENU_NODES_NO_POINTS,
    CHAR_MENU_ROWS_HAS_POINTS,
    CHAR_MENU_ROWS_NO_POINTS,
    ControllerState,
    Rect,
    SKILL_GRID_COL_X,
    SKILL_SPELL_COLS_X,
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    char_menu_point,
    inventory_slot_point,
    inventory_upper_point,
    pet_inventory_slot_point,
    pet_inventory_upper_point,
    quest_abandon_point,
    quest_reward_point,
    quest_slot_point,
    skill_bridge_col,
    skill_layout_for,
    skill_slot_pink_point,
    skill_slot_point,
    skill_snap_col,
    skill_spell_slot_point,
    skill_tab_point,
)
from typing import Any

log = logging.getLogger(__name__) if "logging" in globals() else None


class SkillQuestNavigationMixin:
    """Mixin com métodos de navegação para skills_quests."""

    def _move_cursor_with_leave_step(
        self,
        current_focus: Any,
        cur_x: int,
        cur_y: int,
        target_x: int,
        target_y: int,
        rect: Rect,
    ) -> None:
        """Move o cursor para o alvo garantindo o encerramento limpo de tooltips de spells e travessias entre telas.

        No Torchlight (CEGUI), slots de spell são botões que só fecham o tooltip quando
        recebem um evento OnMouseLeave. Saltos instantâneos via SendInput para outro widget
        ou outra tela ignoram a borda neutra, deixando o tooltip preso na tela.
        """
        scale = rect.height / 768.0 if (rect and rect.valid) else 1.0
        is_leaving_spell = False
        origin_x, origin_y = cur_x, cur_y

        if current_focus is not None:
            f_str = str(current_focus)
            if f_str.startswith("spell_"):
                is_leaving_spell = True
                if rect and rect.valid:
                    origin_x, origin_y = inventory_upper_point(rect, f_str)
            elif f_str.startswith("pet_spell_"):
                is_leaving_spell = True
                if rect and rect.valid:
                    origin_x, origin_y = pet_inventory_upper_point(rect, f_str)

        is_cross_screen = abs(target_x - origin_x) > 250 * scale

        if is_leaving_spell:
            # 1. Passo neutro no pergaminho logo abaixo do spell para forçar OnMouseLeave
            leave_x = origin_x
            leave_y = origin_y + int(35 * scale)
            self.injector.move(leave_x, leave_y)
            self._wait_for_input(0.025)

            # 2. Se for travessia de painéis (Pet <-> Inventário), passa pelo centro neutro da tela
            if is_cross_screen:
                mid_x = (leave_x + target_x) // 2
                mid_y = (leave_y + target_y) // 2
                self.injector.move(mid_x, mid_y)
                self._wait_for_input(0.025)

        elif is_cross_screen:
            # Travessia entre painéis: passa pelo centro neutro da tela (mundo 3D)
            mid_x = (cur_x + target_x) // 2
            mid_y = (cur_y + target_y) // 2
            self.injector.move(mid_x, mid_y)
            self._wait_for_input(0.025)

        # Movimento final até o slot de destino
        self.injector.move(target_x, target_y)

    def _handle_char_menu_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        skill_also_open: bool = False,
        inv_also_open: bool = False,
        quest_also_open: bool = False,
        attr_points: int = 0,
    ) -> None:
        """Gerencia a navegação pelo menu de Personagem (C) via D-pad.

        Navega por todos os nós do menu:
        - Topo: XP, Fame, HP, MP
        - Atributos: Strength, Dexterity, Magic, Defense (nós verdes, laranjas e rosas)
        - Resistências: Poison, Fire, Lightning, Ice

        Nós laranjas são sempre acessíveis pelo D-pad. Quando o menu de Habilidades (S)
        ou o Inventário (I) está aberto, o D-pad direita no nó laranja atravessa a ponte.
        """
        if not rect.valid:
            return
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return

        has_points = (attr_points > 0)
        rows = CHAR_MENU_ROWS_HAS_POINTS if has_points else CHAR_MENU_ROWS_NO_POINTS
        nodes_dict = CHAR_MENU_NODES_HAS_POINTS if has_points else CHAR_MENU_NODES_NO_POINTS

        # 1. Inicialização: posiciona no primeiro atributo (Strength).
        if not self._char_menu_initialized or not self._char_menu_focus:
            self._char_menu_initialized = True
            self._char_menu_focus = "strength"
            tx, ty = char_menu_point(rect, "strength", has_points=has_points)
            self.injector.move(tx, ty)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(char_menu_open=True, char_menu_focus="strength")
            return

        dpad_up    = state.pressed("dpad_up")    and not self._previous.pressed("dpad_up")
        dpad_down  = state.pressed("dpad_down")  and not self._previous.pressed("dpad_down")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left  = state.pressed("dpad_left")  and not self._previous.pressed("dpad_left")

        focus = self._char_menu_focus

        # Localiza linha e coluna atuais na matriz de navegação
        cur_r = None
        cur_c = None
        for r_idx, r_nodes in enumerate(rows):
            if focus in r_nodes:
                cur_r = r_idx
                cur_c = r_nodes.index(focus)
                break

        if cur_r is None:
            # Fallback se o foco não existir na matriz atual
            cur_r = 3
            cur_c = 0
            focus = "strength"

        # Clique A no nó rosa de incremento de atributo
        if state.pressed("a") and not self._previous.pressed("a"):
            if focus.endswith("_pink"):
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.04)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.12, 50)
                return

        new_focus = focus

        if dpad_left:
            if cur_c > 0:
                new_focus = rows[cur_r][cur_c - 1]

        elif dpad_right:
            if cur_c < len(rows[cur_r]) - 1:
                # Navega para o nó da direita na mesma linha (ex: verde -> laranja ou verde -> rosa)
                new_focus = rows[cur_r][cur_c + 1]
            elif skill_also_open:
                # Estamos no nó mais à direita (laranja / ponte) e Menu S está aberto: atravessa a ponte!
                if cur_r >= 7:
                    # Linhas de resistência (fogo e gelo) atravessam para a seção de Spells (slot 0)
                    self._skill_in_spells = True
                    self._skill_spell_idx = 0
                    self._skill_in_tabbar = False
                    self._skill_in_pink = False
                    self._skill_menu_initialized = True

                    tx, ty = skill_spell_slot_point(rect, 0)
                    self._move_cursor_with_leave_step(focus, *self.injector.cursor_position(), tx, ty, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        char_menu_open=True,
                        char_menu_focus=focus,
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus="spell_0",
                    )
                    return
                elif cur_r <= 3:
                    s_row = 0
                elif cur_r == 4:
                    s_row = 1
                elif cur_r == 5:
                    s_row = 2
                else:
                    s_row = 3

                char_cls = self._char_class or "alchemist"
                tab_name = SKILL_TAB_NAMES.get(char_cls, {}).get(self._skill_tab, "arcane")
                layout = SKILL_TREE_LAYOUTS.get(char_cls, {}).get(tab_name, [])
                row_layout = layout[s_row] if s_row < len(layout) else layout[0]
                s_col = skill_bridge_col(row_layout)
                if s_col is None:
                    s_col = 0

                self._skill_focus_row = s_row
                self._skill_focus_col = s_col
                self._skill_in_tabbar = False
                self._skill_in_pink = False
                self._skill_menu_initialized = True

                tx, ty = skill_slot_point(rect, s_row, s_col)
                self._move_cursor_with_leave_step(focus, *self.injector.cursor_position(), tx, ty, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    char_menu_open=True,
                    char_menu_focus=focus,
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({s_row}, {s_col})",
                )
                return
            elif inv_also_open:
                # Estamos no nó mais à direita (laranja / ponte) e Inventário está aberto: atravessa a ponte!
                # Mapeamento 1-a-1 por alinhamento vertical:
                # Linhas 0, 1 (xp, fame) -> helmet
                # Linha 2 (mp) -> gloves
                # Linha 3 (strength_bridge) -> belt
                # Linha 4 (dexterity_bridge) -> main_hand
                # Linha 5 (magic_bridge) -> spell_1
                # Linha 6 (defense_bridge) -> Grid (1, 1)
                # Linha 7 (res_fire) -> Grid (2, 1)
                # Linha 8 (res_ice) -> Grid (3, 1)
                self._inventory_initialized = True
                if cur_r <= 1:
                    inv_target = "helmet"
                    target_x, target_y = inventory_upper_point(rect, inv_target)
                    self._inventory_focus = inv_target
                elif cur_r == 2:
                    inv_target = "gloves"
                    target_x, target_y = inventory_upper_point(rect, inv_target)
                    self._inventory_focus = inv_target
                elif cur_r == 3:
                    inv_target = "belt"
                    target_x, target_y = inventory_upper_point(rect, inv_target)
                    self._inventory_focus = inv_target
                elif cur_r == 4:
                    inv_target = "main_hand"
                    target_x, target_y = inventory_upper_point(rect, inv_target)
                    self._inventory_focus = inv_target
                elif cur_r == 5:
                    inv_target = "spell_1"
                    target_x, target_y = inventory_upper_point(rect, inv_target)
                    self._inventory_focus = inv_target
                elif cur_r == 6:
                    grid_r = 1
                    target_x, target_y = inventory_slot_point(rect, grid_r, 1)
                    self._inventory_focus = (grid_r, 1)
                    inv_target = f"({grid_r}, 1)"
                elif cur_r == 7:
                    grid_r = 2
                    target_x, target_y = inventory_slot_point(rect, grid_r, 1)
                    self._inventory_focus = (grid_r, 1)
                    inv_target = f"({grid_r}, 1)"
                else:
                    grid_r = 3
                    target_x, target_y = inventory_slot_point(rect, grid_r, 1)
                    self._inventory_focus = (grid_r, 1)
                    inv_target = f"({grid_r}, 1)"

                self._move_cursor_with_leave_step(focus, *self.injector.cursor_position(), target_x, target_y, rect)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    char_menu_open=True,
                    char_menu_focus=focus,
                    inventory_open=True,
                    inventory_tab=self._inventory_tab or "tab-1",
                    inventory_focus=inv_target,
                )
                return
            elif quest_also_open:
                # Estamos no nó mais à direita (laranja / ponte) e Missões está aberto: atravessa a ponte!
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
                    char_menu_open=True,
                    char_menu_focus=focus,
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                )
                return
            # Se nem Menu S, nem Inventário, nem Quests estiverem abertos: borda direita, sem ação

        elif dpad_up:
            if cur_r > 0:
                target_row = rows[cur_r - 1]
                cur_x = nodes_dict.get(focus, (134.5, 0))[0]
                new_focus = min(target_row, key=lambda n: abs(nodes_dict.get(n, (134.5, 0))[0] - cur_x))

        elif dpad_down:
            if cur_r < len(rows) - 1:
                target_row = rows[cur_r + 1]
                cur_x = nodes_dict.get(focus, (134.5, 0))[0]
                new_focus = min(target_row, key=lambda n: abs(nodes_dict.get(n, (134.5, 0))[0] - cur_x))

        if new_focus == focus:
            return

        self._char_menu_focus = new_focus
        tx, ty = char_menu_point(rect, new_focus, has_points=has_points)
        self._move_cursor_with_leave_step(focus, *self.injector.cursor_position(), tx, ty, rect)
        hub.rumble(0.03, 0.08, 30)
        self.shared.update(char_menu_open=True, char_menu_focus=new_focus)

    def _handle_skill_menu_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        char_also_open: bool,
        skill_points: int,
        char_class: str,
        now: float = 0.0,
        pet_also_open: bool = False,
    ) -> None:
        """Gerencia a navegação pela skill tree do personagem via D-pad e L2/R2.

        char_also_open: True quando o menu C também está aberto (permite ponte ←).
        pet_also_open:  True quando o menu Pet também está aberto (permite ponte ←).
        skill_points:   número de pontos de habilidade disponíveis (>0 → nós rosas abaixo).
        char_class:     "destroyer", "vanquisher" ou "alchemist".
        """
        if not rect.valid:
            return
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return

        # 1. Inicialização: preserva a aba ativa atual (self._skill_tab) pois o jogo não reseta para a aba 1 ao fechar/abrir.
        if not self._skill_menu_initialized:
            self._skill_menu_initialized = True
            if self._skill_tab not in (1, 2, 3):
                self._skill_tab = 1
            self._skill_focus_row = 0
            layout = skill_layout_for(char_class, self._skill_tab)
            if layout and layout[0]:
                self._skill_focus_col = skill_snap_col(layout[0], 1) or 1
            else:
                self._skill_focus_col = 1
            self._skill_in_tabbar = False
            self._skill_in_pink = False
            self._skill_in_spells = False
            tx, ty = skill_slot_point(rect, self._skill_focus_row, self._skill_focus_col)
            self.injector.move(tx, ty)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                skill_menu_open=True,
                skill_tab=self._skill_tab,
                skill_focus=f"({self._skill_focus_row}, {self._skill_focus_col})",
                char_class=char_class,
            )
            return

        dpad_up    = state.pressed("dpad_up")    and not self._previous.pressed("dpad_up")
        dpad_down  = state.pressed("dpad_down")  and not self._previous.pressed("dpad_down")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left  = state.pressed("dpad_left")  and not self._previous.pressed("dpad_left")

        layout = skill_layout_for(char_class, self._skill_tab)
        if layout is None:
            # Classe desconhecida: tenta "destroyer" como fallback seguro.
            layout = skill_layout_for("destroyer", self._skill_tab)
        if layout is None:
            return


        # 2. Troca de aba com L2/R2 (se um menu da esquerda estiver aberto, restringe à metade direita).
        now_ts = now if now > 0 else time.monotonic()
        cur_x, _ = self.injector.cursor_position()
        mid_x = rect.left + rect.width * 0.5
        is_left_menu_open = char_also_open or pet_also_open
        if (not is_left_menu_open or cur_x >= mid_x) and (self._rt_edge_up or self._lt_edge_up) and now_ts >= self._skill_tab_debounce:
            self._skill_tab_debounce = now_ts + 0.25
            curr = self._skill_tab
            if self._rt_edge_up:
                new_tab = (curr % 3) + 1
            else:
                new_tab = (curr - 2) % 3 + 1

            # Clica na aba para sincronizar o jogo (timing calibrado como no inventário)
            tab_x, tab_y = skill_tab_point(rect, new_tab)
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)

            self._skill_tab = new_tab
            layout = skill_layout_for(char_class, new_tab) or skill_layout_for("destroyer", new_tab)
            row0 = layout[0] if layout else [None, 1, None]
            target_col = skill_bridge_col(row0) if skill_bridge_col(row0) is not None else 1

            self._skill_focus_row = 0
            self._skill_focus_col = target_col
            self._skill_in_tabbar = False
            self._skill_in_pink = False
            self._skill_in_spells = False

            tx, ty = skill_slot_point(rect, 0, target_col)
            self.injector.move(tx, ty)
            hub.rumble(0.04, 0.10, 40)
            self.shared.update(
                skill_menu_open=True,
                skill_tab=new_tab,
                skill_focus=f"(0, {target_col})",
            )
            return

        row = self._skill_focus_row
        col = self._skill_focus_col
        new_row, new_col = row, col
        move_to_tabbar = False
        move_to_pink = False
        leave_pink = False

        # 3. Foco na tab bar (↑ a partir da L1)
        if self._skill_in_tabbar:
            if state.pressed("a") and not self._previous.pressed("a"):
                # Pressionar A ativa a aba focada na tabbar
                tab_idx = self._skill_focus_col + 1
                if tab_idx != self._skill_tab:
                    tab_x, tab_y = skill_tab_point(rect, tab_idx)
                    self.injector.move(tab_x, tab_y)
                    self._wait_for_input(0.060)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.040)
                    self.injector.mouse_button("left", False)
                    self._wait_for_input(0.030)
                    self._skill_tab = tab_idx
                    hub.rumble(0.04, 0.10, 40)
                    self.shared.update(skill_menu_open=True, skill_tab=tab_idx)
                return
            if dpad_down:
                self._skill_in_tabbar = False
                new_row, new_col = 0, 1  # volta para L1-Col2
            elif dpad_left:
                new_col = max(0, col - 1)
            elif dpad_right:
                new_col = min(2, col + 1)
            # ↑ na tabbar: sem ação (borda superior)
            if not self._skill_in_tabbar:
                tx, ty = skill_slot_point(rect, new_row, new_col)
            else:
                self._skill_focus_col = new_col
                tx, ty = skill_tab_point(rect, new_col + 1)
                self.injector.move(tx, ty)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"tab_{new_col + 1}",
                    char_class=char_class,
                )
                return
            self._skill_focus_row = new_row
            self._skill_focus_col = new_col
            self.injector.move(tx, ty)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                skill_menu_open=True,
                skill_tab=self._skill_tab,
                skill_focus=f"({new_row}, {new_col})",
                char_class=char_class,
            )
            return

        # 4. Foco na seção de Spells (feitiços no rodapé)
        if self._skill_in_spells:
            s_idx = self._skill_spell_idx
            if dpad_left:
                if s_idx > 0:
                    self._skill_spell_idx = s_idx - 1
                    tx, ty = skill_spell_slot_point(rect, self._skill_spell_idx)
                    self.injector.move(tx, ty)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=f"spell_{self._skill_spell_idx}",
                    )
                    return
                elif char_also_open:
                    # Ponte para o Menu C (res_ice, nó laranja da última linha)
                    target_attr = "res_ice"
                    self._char_menu_focus = target_attr
                    self._char_menu_initialized = True
                    has_points = (skill_points > 0 or getattr(self._memory_state, "attr_points_remaining", 0) > 0)
                    tx, ty = char_menu_point(rect, target_attr, has_points=has_points)
                    self._move_cursor_with_leave_step(
                        f"spell_{s_idx}", *self.injector.cursor_position(), tx, ty, rect
                    )
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=f"spell_{s_idx}",
                        char_menu_open=True,
                        char_menu_focus=target_attr,
                    )
                    return
                elif pet_also_open:
                    # Ponte para o Menu do Pet: spell_0 -> linha 3, coluna 7 do Pet
                    target_x, target_y = pet_inventory_slot_point(rect, 3, 7)
                    self._pet_inventory_focus = (3, 7)
                    self._pet_inventory_initialized = True
                    self._move_cursor_with_leave_step(
                        f"spell_{s_idx}", *self.injector.cursor_position(), target_x, target_y, rect
                    )
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=f"spell_{s_idx}",
                        pet_inventory_open=True,
                        pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                        pet_inventory_focus="(3, 7)",
                    )
                    return
            elif dpad_right:
                if s_idx < 3:
                    self._skill_spell_idx = s_idx + 1
                    tx, ty = skill_spell_slot_point(rect, self._skill_spell_idx)
                    self.injector.move(tx, ty)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=f"spell_{self._skill_spell_idx}",
                    )
                    return
            elif dpad_up:
                # Sobe para a última linha da grade (Row 5)
                self._skill_in_spells = False
                last_row = len(layout) - 1
                row_layout = layout[last_row]
                spell_x = SKILL_SPELL_COLS_X[s_idx]
                filled = [c for c, v in enumerate(row_layout) if v is not None]
                if not filled:
                    filled = [0, 1, 2]
                snapped_col = min(filled, key=lambda c: abs(SKILL_GRID_COL_X[c] - spell_x))
                self._skill_focus_row = last_row
                self._skill_focus_col = snapped_col
                tx, ty = skill_slot_point(rect, last_row, snapped_col)
                self.injector.move(tx, ty)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({last_row}, {snapped_col})",
                )
                return
            return

        # 5. Foco no nó rosa de level-up (abaixo do slot atual)
        if self._skill_in_pink:
            if state.pressed("a") and not self._previous.pressed("a"):
                # Clica no botão de melhoria da habilidade
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.04)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.12, 50)
                return
            if dpad_up:
                # Volta para o nó da skill acima
                self._skill_in_pink = False
                tx, ty = skill_slot_point(rect, row, col)
                self.injector.move(tx, ty)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({row}, {col})",
                )
                return
            if dpad_down:
                self._skill_in_pink = False
                if row < len(layout) - 1:
                    # Desce do nó rosa para a próxima linha da árvore
                    target_layout = layout[row + 1]
                    snapped = skill_snap_col(target_layout, col)
                    if snapped is not None:
                        self._skill_focus_row = row + 1
                        self._skill_focus_col = snapped
                        tx, ty = skill_slot_point(rect, row + 1, snapped)
                        self.injector.move(tx, ty)
                        hub.rumble(0.03, 0.08, 30)
                        self.shared.update(
                            skill_menu_open=True,
                            skill_tab=self._skill_tab,
                            skill_focus=f"({row + 1}, {snapped})",
                        )
                    return
                else:
                    # Desce da última linha (row 5) para Spells
                    self._skill_in_spells = True
                    cur_col_x = SKILL_GRID_COL_X[col]
                    self._skill_spell_idx = min(range(4), key=lambda i: abs(SKILL_SPELL_COLS_X[i] - cur_col_x))
                    tx, ty = skill_spell_slot_point(rect, self._skill_spell_idx)
                    self.injector.move(tx, ty)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        skill_menu_open=True,
                        skill_tab=self._skill_tab,
                        skill_focus=f"spell_{self._skill_spell_idx}",
                    )
                    return
            # ←/→ no pink: sem ação (mantém foco)
            return

        # 6. Foco em um slot da grid
        row_layout = layout[row]

        if dpad_up:
            if row == 0:
                # Sobe para a tab bar
                move_to_tabbar = True
            else:
                target_layout = layout[row - 1]
                snapped = skill_snap_col(target_layout, col)
                if snapped is not None:
                    new_row, new_col = row - 1, snapped

        elif dpad_down:
            # Verifica se o slot atual está liberado para melhoria com base em pontos, nível e rank
            up_map = getattr(self._memory_state, "skill_upgradeable", {})
            tier_reqs = [1, 5, 10, 15, 20, 25]
            tier_lvl = tier_reqs[row] if row < len(tier_reqs) else 1
            pl_lvl = getattr(self._memory_state, "player_level", 1)
            is_slot_upgradeable = up_map.get((row, col), False) if up_map else (skill_points > 0 and pl_lvl >= tier_lvl)

            if skill_points > 0 and is_slot_upgradeable and not self._skill_in_pink:
                # Desce para o nó rosa de level-up abaixo do slot atual
                move_to_pink = True
            elif row < len(layout) - 1:
                target_layout = layout[row + 1]
                snapped = skill_snap_col(target_layout, col)
                if snapped is not None:
                    new_row, new_col = row + 1, snapped
            else:
                # Row 5 (última linha) e sem nó rosa: desce para a seção de Spells
                self._skill_in_spells = True
                cur_col_x = SKILL_GRID_COL_X[col]
                self._skill_spell_idx = min(range(4), key=lambda i: abs(SKILL_SPELL_COLS_X[i] - cur_col_x))
                tx, ty = skill_spell_slot_point(rect, self._skill_spell_idx)
                self.injector.move(tx, ty)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"spell_{self._skill_spell_idx}",
                )
                return

        elif dpad_left:
            bridge_col = skill_bridge_col(row_layout)
            if col == bridge_col and char_also_open:
                # Ponte: sai do menu S para o menu C no nó laranja alinhado com essa linha.
                attr_map = {
                    0: "strength_bridge",
                    1: "dexterity_bridge",
                    2: "magic_bridge",
                    3: "defense_bridge",
                    4: "res_fire",
                    5: "res_ice",
                }
                target_attr = attr_map.get(row, "defense_bridge")
                self._char_menu_focus = target_attr
                self._char_menu_initialized = True
                has_points = (skill_points > 0 or getattr(self._memory_state, "attr_points_remaining", 0) > 0)
                tx, ty = char_menu_point(rect, target_attr, has_points=has_points)
                self._move_cursor_with_leave_step(
                    f"({row},{col})", *self.injector.cursor_position(), tx, ty, rect
                )
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({row}, {col})",
                    char_menu_open=True,
                    char_menu_focus=target_attr,
                )
                return
            elif col == bridge_col and pet_also_open:
                # Ponte: sai do menu S para o menu do Pet na borda direita correspondente.
                if row <= 3:
                    target_slot: str | tuple[int, int] = "pet_spell_2"
                    target_x, target_y = pet_inventory_upper_point(rect, "pet_spell_2")
                elif row == 4:
                    target_slot = (1, 7)
                    target_x, target_y = pet_inventory_slot_point(rect, 1, 7)
                else:  # row == 5
                    target_slot = (2, 7)
                    target_x, target_y = pet_inventory_slot_point(rect, 2, 7)

                self._pet_inventory_focus = target_slot
                self._pet_inventory_initialized = True
                self._move_cursor_with_leave_step(
                    f"({row},{col})", *self.injector.cursor_position(), target_x, target_y, rect
                )
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    skill_menu_open=True,
                    skill_tab=self._skill_tab,
                    skill_focus=f"({row}, {col})",
                    pet_inventory_open=True,
                    pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                    pet_inventory_focus=str(target_slot),
                )
                return
            else:
                # Move para a coluna imediatamente à esquerda com skill
                filled = [i for i, v in enumerate(row_layout) if v is not None]
                lefts = [c for c in filled if c < col]
                if lefts:
                    new_col = max(lefts)

        elif dpad_right:
            filled = [i for i, v in enumerate(row_layout) if v is not None]
            rights = [c for c in filled if c > col]
            if rights:
                new_col = min(rights)
            # Se não há coluna à direita: borda, sem ação

        if move_to_tabbar:
            self._skill_in_tabbar = True
            self._skill_focus_col = self._skill_tab - 1  # aba ativa
            tx, ty = skill_tab_point(rect, self._skill_tab)
            self.injector.move(tx, ty)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                skill_menu_open=True,
                skill_tab=self._skill_tab,
                skill_focus=f"tab_{self._skill_tab}",
                char_class=char_class,
            )
            return

        if move_to_pink:
            self._skill_in_pink = True
            tx, ty = skill_slot_pink_point(rect, row, col)
            self.injector.move(tx, ty)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                skill_menu_open=True,
                skill_tab=self._skill_tab,
                skill_focus=f"({row}, {col}, pink)",
                char_class=char_class,
            )
            return

        if new_row == row and new_col == col:
            return

        self._skill_focus_row = new_row
        self._skill_focus_col = new_col
        tx, ty = skill_slot_point(rect, new_row, new_col)
        self._move_cursor_with_leave_step(
            f"({row},{col})", *self.injector.cursor_position(), tx, ty, rect
        )
        hub.rumble(0.03, 0.08, 30)
        self.shared.update(
            skill_menu_open=True,
            skill_tab=self._skill_tab,
            skill_focus=f"({new_row}, {new_col})",
            char_class=char_class,
        )

    def _handle_quest_menu_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        pet_also_open: bool = False,
        char_also_open: bool = False,
    ) -> None:
        """Gerencia a navegação por D-pad no Menu de Missões / Quests (Q).

        - 6 slots superiores na lista de missões (quest_0..quest_5).
        - D-pad Up / Down navega e realiza clique simples com o botão esquerdo para o jogo
          atualizar Description e Rewards.
        - Memória interna: recupera e armazena o último slot selecionado ao fechar e reabrir.
        - Slots inferiores dinâmicos conforme propriedades da missão selecionada:
          recompensa de item (reward) e botão Abandon (abandon).
        - Ações de ponte bidirecionais quando Pet ou Character estiver aberto na lateral esquerda.
        """
        if not rect.valid:
            return

        # LB abre o menu radial quando permitido
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return

        visible_rows = getattr(self._memory_state, "quest_visible_rows", 1) or 1
        can_abandon = getattr(self._memory_state, "quest_can_abandon", False)
        has_reward = getattr(self._memory_state, "quest_has_item_reward", False)

        # 1. Inicialização ao abrir o menu de missões
        if not self._quest_menu_initialized:
            self._quest_menu_initialized = True
            mem_selected = getattr(self._memory_state, "quest_selected_idx", 0)
            initial_idx = mem_selected if mem_selected is not None else self._last_quest_slot
            initial_idx = int(clamp(initial_idx, 0, max(0, visible_rows - 1)))
            self._quest_focus = f"quest_{initial_idx}"
            self._last_quest_slot = initial_idx

            target_x, target_y = quest_slot_point(rect, initial_idx)
            self.injector.move(target_x, target_y)
            self.shared.update(
                quest_menu_open=True,
                quest_focus=self._quest_focus,
                quest_count=getattr(self._memory_state, "quest_count", 0),
                quest_selected_idx=initial_idx,
                quest_visible_rows=visible_rows,
                quest_can_abandon=can_abandon,
                quest_has_item_reward=has_reward,
            )
            return

        # 2. Leitura de borda dos botões D-pad e botões A / B
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        a_pressed = state.pressed("a") and not self._previous.pressed("a")
        b_pressed = state.pressed("b") and not self._previous.pressed("b")

        current = self._quest_focus or "quest_0"

        # Botão B (Bolinha no PS / B no Xbox) nas opções inferiores (reward / abandon):
        # retorna o cursor para a navegação da parte de cima (última missão selecionada)
        if b_pressed and current in ("reward", "abandon"):
            last_idx = int(clamp(self._last_quest_slot, 0, max(0, visible_rows - 1)))
            self._quest_focus = f"quest_{last_idx}"
            self._last_quest_slot = last_idx
            target_x, target_y = quest_slot_point(rect, last_idx)
            self.injector.move(target_x, target_y)
            self._wait_for_input(0.075)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            hub.rumble(0.02, 0.06, 25)
            self.shared.update(
                quest_menu_open=True,
                quest_focus=self._quest_focus,
                quest_count=getattr(self._memory_state, "quest_count", 0),
                quest_selected_idx=self._last_quest_slot,
                quest_visible_rows=visible_rows,
                quest_can_abandon=can_abandon,
                quest_has_item_reward=has_reward,
            )
            self._quest_b_consumed = True
            return

        # Clique no botão Abandon se focado e botão A (Sul / X no PS) pressionado
        if a_pressed and current == "abandon" and can_abandon:
            target_x, target_y = quest_abandon_point(rect)
            self.injector.move(target_x, target_y)
            self._wait_for_input(0.075)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            hub.rumble(0.04, 0.10, 35)
            return

        # Atalho do botão A (Sul / X no PS) na lista de missões superior:
        # Move para recompensa (se houver) ou abandonar (se puder abandonar).
        # Se não tiver nenhum dos dois, não faz nada.
        if a_pressed and current.startswith("quest_"):
            if has_reward:
                self._quest_focus = "reward"
                target_x, target_y = quest_reward_point(rect)
                self.injector.move(target_x, target_y)
                hub.rumble(0.02, 0.06, 25)
                self.shared.update(
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                    quest_count=getattr(self._memory_state, "quest_count", 0),
                    quest_selected_idx=self._last_quest_slot,
                    quest_visible_rows=visible_rows,
                    quest_can_abandon=can_abandon,
                    quest_has_item_reward=has_reward,
                )
                return
            elif can_abandon:
                self._quest_focus = "abandon"
                target_x, target_y = quest_abandon_point(rect)
                self.injector.move(target_x, target_y)
                hub.rumble(0.02, 0.06, 25)
                self.shared.update(
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                    quest_count=getattr(self._memory_state, "quest_count", 0),
                    quest_selected_idx=self._last_quest_slot,
                    quest_visible_rows=visible_rows,
                    quest_can_abandon=can_abandon,
                    quest_has_item_reward=has_reward,
                )
                return
            # Se não tiver recompensa nem abandonar, não faz nada
            return

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        # 3. D-pad Left: Ponte para o menu do lado esquerdo (Pet ou Character)
        if dpad_left:
            if pet_also_open:
                # Ponte para o Pet: extremidade direita do grid do pet (coluna 7)
                if current == "quest_0":
                    pet_target = (1, 7)
                elif current == "quest_1":
                    pet_target = (1, 7)
                elif current == "quest_2":
                    pet_target = (2, 7)
                else:
                    pet_target = (3, 7)
                self._pet_inventory_initialized = True
                self._pet_inventory_focus = pet_target
                target_x, target_y = pet_inventory_slot_point(rect, pet_target[0], pet_target[1])
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    pet_inventory_open=True,
                    pet_inventory_tab=self._pet_inventory_tab or "tab-1",
                    pet_inventory_focus=f"({pet_target[0]}, {pet_target[1]})",
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                )
                return
            elif char_also_open:
                # Ponte para o Character: extremidade direita dos atributos
                if current == "quest_0":
                    char_target = "xp"
                elif current == "quest_1":
                    char_target = "fame"
                elif current == "quest_2":
                    char_target = "strength_bridge"
                elif current == "quest_3":
                    char_target = "dexterity_bridge"
                elif current == "quest_4":
                    char_target = "magic_bridge"
                elif current == "quest_5":
                    char_target = "defense_bridge"
                elif current == "reward":
                    char_target = "res_fire"
                else:  # abandon
                    char_target = "res_ice"

                self._char_menu_initialized = True
                self._char_menu_focus = char_target
                has_points = (getattr(self._memory_state, "attr_points_remaining", 0) > 0)
                nodes_dict = CHAR_MENU_NODES_HAS_POINTS if has_points else CHAR_MENU_NODES_NO_POINTS
                base_x, base_y = nodes_dict.get(char_target, (282.5, 309.5))
                scale = rect.height / 768.0
                target_x = int(clamp(round(rect.left + base_x * scale), rect.left + 2, rect.right - 2))
                target_y = int(clamp(round(rect.top + base_y * scale), rect.top + 2, rect.bottom - 2))
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(
                    char_menu_open=True,
                    char_menu_focus=char_target,
                    quest_menu_open=True,
                    quest_focus=self._quest_focus,
                )
                return

        # 4. D-pad Down: Desce na lista de missões ou para os slots inferiores
        if dpad_down:
            if current.startswith("quest_"):
                idx = int(current.split("_")[1])
                if idx + 1 < visible_rows:
                    new_idx = idx + 1
                    self._quest_focus = f"quest_{new_idx}"
                    self._last_quest_slot = new_idx
                    target_x, target_y = quest_slot_point(rect, new_idx)
                    self.injector.move(target_x, target_y)
                    self._wait_for_input(0.075)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.040)
                    self.injector.mouse_button("left", False)
                    hub.rumble(0.02, 0.06, 25)
                elif has_reward:
                    self._quest_focus = "reward"
                    target_x, target_y = quest_reward_point(rect)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.02, 0.06, 25)
                elif can_abandon:
                    self._quest_focus = "abandon"
                    target_x, target_y = quest_abandon_point(rect)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.02, 0.06, 25)
            elif current == "reward":
                if can_abandon:
                    self._quest_focus = "abandon"
                    target_x, target_y = quest_abandon_point(rect)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.02, 0.06, 25)

        # 5. D-pad Up: Sobe na lista ou a partir de abandon/reward
        elif dpad_up:
            if current == "abandon":
                if has_reward:
                    self._quest_focus = "reward"
                    target_x, target_y = quest_reward_point(rect)
                    self.injector.move(target_x, target_y)
                    hub.rumble(0.02, 0.06, 25)
                else:
                    last_idx = max(0, visible_rows - 1)
                    self._quest_focus = f"quest_{last_idx}"
                    self._last_quest_slot = last_idx
                    target_x, target_y = quest_slot_point(rect, last_idx)
                    self.injector.move(target_x, target_y)
                    self._wait_for_input(0.075)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.040)
                    self.injector.mouse_button("left", False)
                    hub.rumble(0.02, 0.06, 25)
            elif current == "reward":
                last_idx = max(0, visible_rows - 1)
                self._quest_focus = f"quest_{last_idx}"
                self._last_quest_slot = last_idx
                target_x, target_y = quest_slot_point(rect, last_idx)
                self.injector.move(target_x, target_y)
                self._wait_for_input(0.075)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.040)
                self.injector.mouse_button("left", False)
                hub.rumble(0.02, 0.06, 25)
            elif current.startswith("quest_"):
                idx = int(current.split("_")[1])
                if idx > 0:
                    new_idx = idx - 1
                    self._quest_focus = f"quest_{new_idx}"
                    self._last_quest_slot = new_idx
                    target_x, target_y = quest_slot_point(rect, new_idx)
                    self.injector.move(target_x, target_y)
                    self._wait_for_input(0.075)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.040)
                    self.injector.mouse_button("left", False)
                    hub.rumble(0.02, 0.06, 25)

        self.shared.update(
            quest_menu_open=True,
            quest_focus=self._quest_focus,
            quest_selected_idx=self._last_quest_slot,
            quest_visible_rows=visible_rows,
            quest_can_abandon=can_abandon,
            quest_has_item_reward=has_reward,
        )
