from __future__ import annotations

from ..controller import ControllerHub
from ..models import (
    ControllerState,
    Rect,
    crafting_button_point,
    crafting_slot_point,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    merchant_slot_point,
    merchant_tab_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class MerchantCraftingNavigationMixin:
    """Mixin com métodos de navegação para merchant_crafting."""

    def _handle_merchant_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos slots do Mercador (grid 6x7), 3 abas rosa e Pet inferior via D-pad, L2/R2 e X/A."""
        if not rect.valid:
            return

        # 1. Inicialização ao abrir o Mercador
        if not self._merchant_initialized:
            self._merchant_initialized = True
            npc_name = self._memory_state.merchant_npc_name or ""
            self._merchant_npc_name = npc_name
            # Determina a aba default pelo nome do NPC lido da memória:
            # Kolos e Duros -> WEAPONS (tab-2)
            # Tarn e Triya -> MISC (tab-1)
            name_lower = npc_name.lower()
            if any(k in name_lower for k in ("kolos", "duros", "blacksmith", "blade", "smith")):
                self._merchant_tab = "tab-2"
            else:
                self._merchant_tab = "tab-1"

            self._merchant_focus = ("merchant", 1, 1)
            target_x, target_y = merchant_slot_point(rect, 1, 1)
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                merchant_open=True,
                merchant_tab=self._merchant_tab,
                merchant_focus="('merchant', 1, 1)",
                merchant_npc_name=self._merchant_npc_name,
            )
            return

        cur_x, cur_y = self.injector.cursor_position()
        is_left_half = (cur_x < rect.left + rect.width * 0.5)

        # 2. Troca de abas Ciano do Pet via L2 ou R2 (somente se o cursor estiver na metade esquerda da tela)
        # L2 e R2 continuam trocando as abas em ciano
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
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)

            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)

            self._stash_tab = f"tab-{new_tab_num}"
            self._merchant_focus = ("pet", 1, 1)

            slot_x, slot_y = pet_inventory_slot_point(rect, 1, 1)
            self.injector.move(slot_x, slot_y)
            hub.rumble(0.05, 0.12, 40)

            self.shared.update(
                merchant_open=True,
                merchant_tab=self._merchant_tab or "tab-1",
                merchant_focus="('pet', 1, 1)",
            )
            return

        # 3. Interação com Botão X / A quando o cursor estiver em uma das abas rosa ("merchant_tab", tab_idx)
        # Opção A: Ao pressionar X/A, clica na aba rosa e retorna imediatamente para o ponto amarelo (1, 1) do grid do mercador
        current = self._merchant_focus or ("merchant", 1, 1)
        sec = current[0]

        btn_a_pressed = state.pressed("a") and not self._previous.pressed("a")
        btn_x_pressed = state.pressed("x") and not self._previous.pressed("x")

        if sec == "merchant_tab" and (btn_a_pressed or btn_x_pressed):
            tab_idx = int(current[1])
            tab_x, tab_y = merchant_tab_point(rect, tab_idx)
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)

            self._merchant_tab = f"tab-{tab_idx}"
            self._merchant_focus = ("merchant", 1, 1)
            yellow_x, yellow_y = merchant_slot_point(rect, 1, 1)
            self.injector.move(yellow_x, yellow_y)
            hub.rumble(0.05, 0.12, 40)
            self.shared.update(
                merchant_open=True,
                merchant_tab=self._merchant_tab,
                merchant_focus="('merchant', 1, 1)",
            )
            return

        # 4. Navegação via D-pad
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        is_inv_open = "Inventário" in (self._memory_state.open_menus or [])
        new_focus = current

        if sec == "pet":
            _, row, col = current
            if dpad_right:
                if col < 7:
                    new_focus = ("pet", row, col + 1)
                elif is_inv_open:
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
                    # Transição vertical para a Linha 6 do Mercador
                    new_focus = ("merchant", 6, col)

        elif sec == "merchant":
            _, row, col = current
            if dpad_right:
                if col < 7:
                    new_focus = ("merchant", row, col + 1)
                elif is_inv_open:
                    # Ponte para o Inventário Direito
                    MERCHANT_TO_INV_MAP = {
                        1: "helmet",
                        2: "gloves",
                        3: "belt",
                        4: "belt",
                        5: "main_hand",
                        6: "spell_1",
                    }
                    target_slot = MERCHANT_TO_INV_MAP.get(row, "spell_1")
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
                    new_focus = ("merchant", 2, 1)
                elif row == 2:
                    new_focus = ("merchant", 3, 1)
                elif row == 3:
                    new_focus = ("merchant", 4, 1)
                elif row == 4:
                    new_focus = ("merchant", 5, 1)
                elif row == 5:
                    new_focus = ("merchant", 6, 1)
                elif row == 6:
                    new_focus = ("merchant", 1, 1)
            elif dpad_left:
                if col > 1:
                    new_focus = ("merchant", row, col - 1)
                elif row == 1:
                    new_focus = ("merchant", 6, 7)
                elif row == 2:
                    new_focus = ("merchant", 1, 7)
                elif row == 3:
                    new_focus = ("merchant", 2, 7)
                elif row == 4:
                    new_focus = ("merchant", 3, 7)
                elif row == 5:
                    new_focus = ("merchant", 4, 7)
                elif row == 6:
                    new_focus = ("merchant", 5, 7)
            elif dpad_up:
                if row > 1:
                    new_focus = ("merchant", row - 1, col)
                else:
                    # Sobe para a aba ativa rosa do mercador!
                    active_tab_num = 1
                    if self._merchant_tab:
                        try:
                            active_tab_num = int(self._merchant_tab.replace("tab-", ""))
                        except Exception:
                            active_tab_num = 1
                    new_focus = ("merchant_tab", active_tab_num)
            elif dpad_down:
                if row < 6:
                    new_focus = ("merchant", row + 1, col)
                else:
                    # Transição vertical para o Pet Linha 1
                    new_focus = ("pet", 1, col)

        elif sec == "merchant_tab":
            tab_idx = int(current[1])
            if dpad_right:
                # Wrap cíclico 1 -> 2 -> 3 -> 1
                new_tab_idx = (tab_idx % 3) + 1
                new_focus = ("merchant_tab", new_tab_idx)
            elif dpad_left:
                # Wrap cíclico 1 -> 3 -> 2 -> 1
                new_tab_idx = 3 if tab_idx == 1 else tab_idx - 1
                new_focus = ("merchant_tab", new_tab_idx)
            elif dpad_down:
                # Desce para a Linha 1 do grid do mercador na coluna correspondente à aba
                TAB_TO_COL = {1: 1, 2: 4, 3: 7}
                target_col = TAB_TO_COL.get(tab_idx, 1)
                new_focus = ("merchant", 1, target_col)
            elif dpad_up:
                # Bloqueio no topo
                new_focus = current

        if new_focus != current:
            self._merchant_focus = new_focus
            if new_focus[0] == "pet":
                target_x, target_y = pet_inventory_slot_point(rect, new_focus[1], new_focus[2])
            elif new_focus[0] == "merchant":
                target_x, target_y = merchant_slot_point(rect, new_focus[1], new_focus[2])
            elif new_focus[0] == "merchant_tab":
                target_x, target_y = merchant_tab_point(rect, new_focus[1])

            self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                merchant_open=True,
                merchant_tab=self._merchant_tab or "tab-1",
                merchant_focus=str(new_focus),
            )

    def _handle_crafting_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos slots de itens e botões de ação nas telas de Transmutador, Sockets e Encantador."""
        if not rect.valid:
            return

        active_menu = next((m for m in ("Transmutador", "Sockets", "Encantador") if m in (self._memory_state.open_menus or [])), "Transmutador")

        # 1. Inicialização ao abrir o menu de Crafting
        if not self._crafting_initialized:
            self._crafting_initialized = True
            self._crafting_menu = active_menu
            self._crafting_focus = "slot_0"
            target_x, target_y = crafting_slot_point(rect, active_menu, 0)
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.08, 30)
            self.shared.update(
                crafting_open=True,
                crafting_menu=self._crafting_menu,
                crafting_focus="slot_0",
            )
            return

        cur_x, cur_y = self.injector.cursor_position()

        # 2. Troca de abas do Inventário do Jogador via L2 ou R2
        # Como o menu de crafting não possui abas próprias, L2 e R2 ciclam as abas do Inventário à direita
        if self._rt_edge_up or self._lt_edge_up:
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
            self.injector.move(tab_x, tab_y)
            self._wait_for_input(0.060)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.040)
            self.injector.mouse_button("left", False)
            self._wait_for_input(0.030)

            self._inventory_tab = f"tab-{new_tab_num}"

            # Retorna o cursor para o elemento ativo do crafting
            cur_focus = self._crafting_focus or "slot_0"
            if cur_focus.startswith("slot_"):
                idx = int(cur_focus.replace("slot_", ""))
                slot_x, slot_y = crafting_slot_point(rect, active_menu, idx)
            elif cur_focus == "decline":
                slot_x, slot_y = crafting_button_point(rect, active_menu, "decline")
            else:
                slot_x, slot_y = crafting_button_point(rect, active_menu, "action")

            self.injector.move(slot_x, slot_y)
            hub.rumble(0.05, 0.12, 40)
            self.shared.update(
                inventory_open=True,
                inventory_tab=self._inventory_tab,
                crafting_open=True,
                crafting_menu=self._crafting_menu,
                crafting_focus=self._crafting_focus,
            )
            return

        # 3. Navegação via D-pad
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if not (dpad_up or dpad_down or dpad_left or dpad_right):
            return

        current = self._crafting_focus or "slot_0"
        new_focus = current
        is_inv_open = "Inventário" in (self._memory_state.open_menus or [])

        if active_menu == "Transmutador":
            # Grid 2x2: slot_0 (1, 1), slot_1 (1, 2), slot_2 (2, 1), slot_3 (2, 2)
            # Botões: decline (FECHAR), action (TRANSMUTAR)
            if current == "slot_0":
                if dpad_right:
                    new_focus = "slot_1"
                elif dpad_down:
                    new_focus = "slot_2"
            elif current == "slot_1":
                if dpad_left:
                    new_focus = "slot_0"
                elif dpad_down:
                    new_focus = "slot_3"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 1, 1)
                    self._inventory_focus = (1, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(1, 1)",
                    )
                    return
            elif current == "slot_2":
                if dpad_up:
                    new_focus = "slot_0"
                elif dpad_right:
                    new_focus = "slot_3"
                elif dpad_down:
                    new_focus = "decline"
            elif current == "slot_3":
                if dpad_up:
                    new_focus = "slot_1"
                elif dpad_left:
                    new_focus = "slot_2"
                elif dpad_down:
                    new_focus = "decline"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 2, 1)
                    self._inventory_focus = (2, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(2, 1)",
                    )
                    return
            elif current == "decline":
                if dpad_up:
                    new_focus = "slot_2"
                elif dpad_down:
                    new_focus = "action"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 2, 1)
                    self._inventory_focus = (2, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(2, 1)",
                    )
                    return
            elif current == "action":
                if dpad_up:
                    new_focus = "decline"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 3, 1)
                    self._inventory_focus = (3, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(3, 1)",
                    )
                    return
        else:
            # Sockets e Encantador (Goren / Gorn / Furl)
            # 1 Slot Central: slot_0
            # Botões: decline (FECHAR), action (ENCANTAR / RECUPERAR)
            if current == "slot_0":
                if dpad_down:
                    new_focus = "decline"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 1, 1)
                    self._inventory_focus = (1, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(1, 1)",
                    )
                    return
            elif current == "decline":
                if dpad_up:
                    new_focus = "slot_0"
                elif dpad_down:
                    new_focus = "action"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 2, 1)
                    self._inventory_focus = (2, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(2, 1)",
                    )
                    return
            elif current == "action":
                if dpad_up:
                    new_focus = "decline"
                elif dpad_right and is_inv_open:
                    target_x, target_y = inventory_slot_point(rect, 3, 1)
                    self._inventory_focus = (3, 1)
                    self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
                    hub.rumble(0.03, 0.08, 30)
                    self.shared.update(
                        inventory_open=True,
                        inventory_tab=self._inventory_tab or "tab-1",
                        inventory_focus="(3, 1)",
                    )
                    return

        if new_focus != current:
            self._crafting_focus = new_focus
            if new_focus.startswith("slot_"):
                idx = int(new_focus.replace("slot_", ""))
                target_x, target_y = crafting_slot_point(rect, active_menu, idx)
            elif new_focus == "decline":
                target_x, target_y = crafting_button_point(rect, active_menu, "decline")
            else:
                target_x, target_y = crafting_button_point(rect, active_menu, "action")

            self._move_cursor_with_leave_step(current, cur_x, cur_y, target_x, target_y, rect)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(
                crafting_open=True,
                crafting_menu=self._crafting_menu,
                crafting_focus=self._crafting_focus,
            )
