from __future__ import annotations

import time

from ..controller import ControllerHub
from ..input_session import wait_for_text_field_cursor
from ..mathutils import clamp
from ..models import (
    ControllerState,
    KEYBOARD_LAYOUT,
    Rect,
    SETTINGS_DROPDOWNS,
    SETTINGS_NAV_MAP,
    char_create_button_point,
    char_create_text_field_rect,
    load_char_button_point,
    settings_button_point,
    settings_dropdown_option_point,
    virtual_keyboard_character,
    virtual_keyboard_grid_to_key,
    virtual_keyboard_key_cursor_point,
    virtual_keyboard_key_rect,
    virtual_keyboard_target_rect,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class CharacterNavigationMixin:
    """Mixin com métodos de navegação para character."""

    def _handle_char_create_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação na Tela de Criação de Personagem (state_id == 1) via D-pad."""
        if not self._char_create_initialized or self._last_state_id != 1:
            self._char_create_initialized = True
            self._last_state_id = 1
            self._char_create_focus = "destroyer"
            target_x, target_y = char_create_button_point(rect, self._char_create_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(char_create_focus=self._char_create_focus)
            return

        current = self._char_create_focus
        has_name = (self._memory_state.char_name_len > 0)

        # Se o teclado virtual estiver aberto, delega para o controlador de navegação do teclado:
        if self._virtual_keyboard_open:
            self._handle_virtual_keyboard_navigation(state, rect, hub)
            return

        confirm, cancel = self._keyboard_buttons(state)

        # Abrir teclado virtual ao pressionar 'a' quando focado em character_name ou pet_name
        if current in ("character_name", "pet_name"):
            if state.pressed(confirm) and not self._previous.pressed(confirm):
                self._open_virtual_keyboard(current, rect, hub)
                return

        # Se o foco estava no 'ok' mas o nome foi apagado, recua para 'character_name'
        if current == "ok" and not has_name:
            current = "character_name"
            self._char_create_focus = "character_name"
            target_x, target_y = char_create_button_point(rect, "character_name")
            self.injector.move(target_x, target_y)
            self.shared.update(char_create_focus="character_name")

        new_focus = current

        # Botão B (Bolinha no PlayStation / B no Xbox): atalho direto para Cancelar / Voltar
        if state.pressed(cancel) and not self._previous.pressed(cancel):
            self._char_create_focus = "back"
            target_x, target_y = char_create_button_point(rect, "back")
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.10, 35)
            self.shared.update(char_create_focus="back")
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.04)
            self.injector.mouse_button("left", False)
            return

        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_right:
            if current == "destroyer":
                new_focus = "dog"
            elif current == "vanquisher":
                new_focus = "cat"
            elif current == "alchemist":
                new_focus = "ferret"
            elif current == "back":
                new_focus = "character_name"
            elif current == "character_name":
                if has_name:
                    new_focus = "ok"
        elif dpad_left:
            if current == "dog":
                new_focus = "destroyer"
            elif current == "cat":
                new_focus = "vanquisher"
            elif current == "ferret":
                new_focus = "alchemist"
            elif current == "pet_name":
                new_focus = "alchemist"
            elif current == "character_name":
                new_focus = "back"
            elif current == "ok":
                new_focus = "character_name"
        elif dpad_down:
            if current == "destroyer":
                new_focus = "vanquisher"
            elif current == "vanquisher":
                new_focus = "alchemist"
            elif current == "alchemist":
                new_focus = "back"
            elif current == "dog":
                new_focus = "cat"
            elif current == "cat":
                new_focus = "ferret"
            elif current == "ferret":
                new_focus = "pet_name"
            elif current == "pet_name":
                new_focus = "ok" if has_name else "character_name"
        elif dpad_up:
            if current == "back":
                new_focus = "alchemist"
            elif current in ("character_name", "ok"):
                new_focus = "pet_name"
            elif current == "alchemist":
                new_focus = "vanquisher"
            elif current == "vanquisher":
                new_focus = "destroyer"
            elif current == "pet_name":
                new_focus = "ferret"
            elif current == "ferret":
                new_focus = "cat"
            elif current == "cat":
                new_focus = "dog"

        if new_focus != current:
            self._char_create_focus = new_focus
            target_x, target_y = char_create_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(char_create_focus=new_focus)

    @staticmethod
    def _keyboard_buttons(state: ControllerState) -> tuple[str, str]:
        nintendo = any(name in state.controller_type.lower() for name in ("nintendo", "switch"))
        return ("b", "a") if nintendo else ("a", "b")

    def _handle_keyboard_mouse(self, rect: Rect, hub: ControllerHub) -> None:
        # Qt consumes clicks on keys so the game edit control retains its caret/focus.
        down = self.injector.key_pressed("MOUSE_LEFT") is True
        events = self.shared.take_keyboard_events()
        intercepted = any(kind == "click" for kind, _, _ in events)
        for kind, x, y in events:
            if not self._virtual_keyboard_open:
                continue
            kx, ky, kw, kh = virtual_keyboard_target_rect(rect, self._virtual_keyboard_target)
            for key_id, row, col, _span, _key_type in KEYBOARD_LAYOUT:
                bx, by, bw, bh = virtual_keyboard_key_rect(kx, ky, kw, kh, key_id)
                if bx <= x < bx + bw and by <= y < by + bh:
                    self._virtual_keyboard_focus = (row, col)
                    self.shared.update(virtual_keyboard_focus=(row, col))
                    if kind == "click":
                        self._activate_virtual_key(key_id, rect, hub)
                    break
        # The main overlay remains click-through outside the keyboard.
        if down and not self._keyboard_mouse_down and not intercepted:
            x, y = self.injector.cursor_position()
            kx, ky, kw, kh = virtual_keyboard_target_rect(rect, self._virtual_keyboard_target)
            if not self._virtual_keyboard_open or not Rect(kx, ky, kw, kh).contains(x, y):
                for field in ("character_name", "pet_name"):
                    if char_create_text_field_rect(rect, field).contains(x, y):
                        self._open_virtual_keyboard(field, rect, hub)
                        break
                else:
                    if self._virtual_keyboard_open:
                        self._close_virtual_keyboard(rect, hub)
        self._keyboard_mouse_down = down

    def _open_virtual_keyboard(self, target: str, rect: Rect, hub: ControllerHub) -> None:
        # Focus the actual game edit control before moving onto the virtual keys.
        self._set_mouse("left", False)
        self.injector.move(*char_create_button_point(rect, target))
        wait_for_text_field_cursor(self.injector)
        self.injector.mouse_button("left", True)
        self.injector.mouse_button("left", False)
        self._virtual_keyboard_open = True
        self._virtual_keyboard_target = target
        self._virtual_keyboard_focus = (3, 1)
        self._virtual_keyboard_caps_state = "default"
        self._char_create_focus = target
        self.shared.update(virtual_keyboard_open=True, virtual_keyboard_target=target,
                           virtual_keyboard_focus=(3, 1), virtual_keyboard_caps_state="default",
                           virtual_keyboard_pressed_key=None, virtual_keyboard_press_id=0,
                           char_create_focus=target)
        kx, ky, kw, kh = virtual_keyboard_target_rect(rect, target)
        x, y, w, h = virtual_keyboard_key_rect(kx, ky, kw, kh, "3x1")
        cx, cy = virtual_keyboard_key_cursor_point(x, y, w, h)
        self.injector.move(cx, cy)
        hub.rumble(0.04, 0.10, 40)

    def _activate_virtual_key(self, key_id: str, rect: Rect, hub: ControllerHub) -> None:
        self._keyboard_press_counter = getattr(self, "_keyboard_press_counter", 0) + 1
        self._keyboard_pressed_until = time.monotonic() + 0.18
        self.shared.update(
            virtual_keyboard_pressed_key=key_id,
            virtual_keyboard_press_id=self._keyboard_press_counter,
        )
        hub.rumble(0.03, 0.08, 35)
        if key_id == "ok":
            self._close_virtual_keyboard(rect, hub)
        elif key_id == "caps":
            self._cycle_caps_lock(hub)
        elif key_id == "backspace":
            self.injector.tap("BACKSPACE")
        else:
            char = " " if key_id == "space" else virtual_keyboard_character(
                key_id, self._virtual_keyboard_caps_state)
            sent = self.injector.text(char)
            if sent and char.isalpha() and self._virtual_keyboard_caps_state == "next_letter":
                self._virtual_keyboard_caps_state = "default"
                self.shared.update(virtual_keyboard_caps_state="default")

    def _cycle_caps_lock(self, hub: ControllerHub) -> None:
        """Alterna ciclicamente os 3 estados do Caps Lock: default -> next_letter -> all_letters -> default."""
        cur = getattr(self, "_virtual_keyboard_caps_state", "default")
        if cur == "default":
            next_state = "next_letter"
        elif cur == "next_letter":
            next_state = "all_letters"
        else:
            next_state = "default"
        self._virtual_keyboard_caps_state = next_state
        self.shared.update(virtual_keyboard_caps_state=next_state)
        hub.rumble(0.03, 0.08, 30)

    def _close_virtual_keyboard(self, rect: Rect, hub: ControllerHub) -> None:
        """Fecha o teclado virtual e retorna o cursor ao nó rosa do campo de texto ativo."""
        self._virtual_keyboard_open = False
        self._keyboard_cancel_repeat_at = 0.0
        self._keyboard_confirm_repeat_at = 0.0
        self._keyboard_confirm_latched = True
        target = self._virtual_keyboard_target
        self._virtual_keyboard_target = ""
        self._virtual_keyboard_pressed_key = None
        self.shared.update(
            virtual_keyboard_open=False,
            virtual_keyboard_target="",
            virtual_keyboard_pressed_key=None,
            virtual_keyboard_press_id=0,
        )
        hub.rumble(0.04, 0.10, 35)
        if target:
            tx, ty = char_create_button_point(rect, target)
            self.injector.move(tx, ty)

    def _handle_virtual_keyboard_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação no grid 5x13 e as ações do teclado virtual."""
        confirm, cancel = self._keyboard_buttons(state)
        # 1. Fechar pelo botão START (mesma ação do botão OK do teclado virtual)
        if state.pressed("start") and not self._previous.pressed("start"):
            self._close_virtual_keyboard(rect, hub)
            return

        # 2. Alternar Caps Lock pelo gatilho (LT / L2 / ZL)
        lt_now = state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
        lt_prev = self._previous.lt >= self.TRIGGER_ACTIVE_THRESHOLD
        if lt_now and not lt_prev:
            self._cycle_caps_lock(hub)

        # 3. Navegação via D-pad pelo grid 5x13
        cur_row, cur_col = self._virtual_keyboard_focus or (3, 1)
        new_row, new_col = cur_row, cur_col

        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_right:
            if cur_row == 4 and cur_col in (1, 2):
                new_col = 3
            elif cur_row == 4 and cur_col == 11:
                new_col = 12
            elif cur_row == 5 and cur_col <= 10:
                new_col = 11
            elif (cur_row == 4 and cur_col >= 12) or (cur_row == 5 and cur_col >= 11):
                pass
            else:
                new_col = min(13, cur_col + 1)
        elif dpad_left:
            if cur_row == 4 and cur_col == 3:
                new_col = 1
            elif cur_row == 4 and cur_col in (12, 13):
                new_col = 11
            elif cur_row == 5 and cur_col >= 11:
                new_col = 10
            elif (cur_row == 4 and cur_col <= 2) or cur_row == 5:
                pass
            else:
                new_col = max(1, cur_col - 1)
        elif dpad_down:
            new_row = min(5, cur_row + 1)
        elif dpad_up:
            new_row = max(1, cur_row - 1)

        if (new_row, new_col) != (cur_row, cur_col):
            self._virtual_keyboard_focus = (new_row, new_col)
            hub.rumble(0.02, 0.06, 25)
            self.shared.update(virtual_keyboard_focus=(new_row, new_col))
            kx, ky, kw, kh = virtual_keyboard_target_rect(rect, self._virtual_keyboard_target)
            key_id, _ = virtual_keyboard_grid_to_key(new_row, new_col)
            key_rx, key_ry, key_rw, key_rh = virtual_keyboard_key_rect(kx, ky, kw, kh, key_id)
            cx, cy = virtual_keyboard_key_cursor_point(key_rx, key_ry, key_rw, key_rh)
            self.injector.move(cx, cy)
            self._keyboard_confirm_repeat_at = 0.0

        now = time.monotonic()
        key_id, _ = virtual_keyboard_grid_to_key(new_row, new_col)

        # 4. Ativação de tecla com botão de confirmação (A no Xbox/PS, B no Nintendo)
        if state.pressed(confirm):
            if not self._previous.pressed(confirm):
                self._activate_virtual_key(key_id, rect, hub)
                if not self._virtual_keyboard_open:
                    return
                if key_id == "backspace":
                    self._keyboard_confirm_repeat_at = now + self.KEYBOARD_REPEAT_DELAY
            elif key_id == "backspace" and self._keyboard_confirm_repeat_at > 0.0 and now >= self._keyboard_confirm_repeat_at:
                self.injector.tap("BACKSPACE")
                self._keyboard_press_counter = getattr(self, "_keyboard_press_counter", 0) + 1
                self._keyboard_pressed_until = now + 0.10
                self.shared.update(
                    virtual_keyboard_pressed_key="backspace",
                    virtual_keyboard_press_id=self._keyboard_press_counter,
                )
                self._keyboard_confirm_repeat_at = now + self.KEYBOARD_REPEAT_INTERVAL
        else:
            self._keyboard_confirm_repeat_at = 0.0

        if now >= self._keyboard_pressed_until:
            self.shared.update(virtual_keyboard_pressed_key=None)

        # 5. Botão B (Leste no Xbox/PS, Sul no Nintendo) funciona como Backspace com repetição contínua
        if state.pressed(cancel):
            if not self._previous.pressed(cancel):
                hub.rumble(0.03, 0.08, 30)
                self.injector.key("BACKSPACE", True)
                self.injector.key("BACKSPACE", False)
                self._keyboard_cancel_repeat_at = now + self.KEYBOARD_REPEAT_DELAY
            elif self._keyboard_cancel_repeat_at > 0.0 and now >= self._keyboard_cancel_repeat_at:
                self.injector.key("BACKSPACE", True)
                self.injector.key("BACKSPACE", False)
                self._keyboard_cancel_repeat_at = now + self.KEYBOARD_REPEAT_INTERVAL
        else:
            self._keyboard_cancel_repeat_at = 0.0

        # 6. Botões de ombro (LB/RB, L1/R1, L/R): movem o cursor do texto (setas esquerda e direita)
        if state.pressed("lb") and not self._previous.pressed("lb"):
            self.injector.key("LEFT", True)
            self.injector.key("LEFT", False)
            hub.rumble(0.02, 0.05, 20)
        elif state.pressed("rb") and not self._previous.pressed("rb"):
            self.injector.key("RIGHT", True)
            self.injector.key("RIGHT", False)
            hub.rumble(0.02, 0.05, 20)

    def _handle_load_char_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        now: float = 0.0,
    ) -> None:
        """Gerencia a navegação na Tela de Carregar Personagem (state_id == 3) via D-pad e atalhos."""
        cur_time = now if now > 0 else time.monotonic()
        if not self._load_char_initialized or self._last_state_id != 3:
            self._load_char_initialized = True
            self._last_state_id = 3
            self._load_char_delete_dialog_open = False
            self._load_char_focus = "slot_1"
            self._load_char_last_slot = "slot_1"
            self._load_char_dialog_debounce = 0.0
            target_x, target_y = load_char_button_point(rect, self._load_char_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(load_char_focus=self._load_char_focus, load_char_delete_open=False)
            return

        current = self._load_char_focus or "slot_1"

        # -------------------------------------------------------------
        # CASO 1: Modal de Confirmação de Exclusão de Personagem aberto
        # -------------------------------------------------------------
        if self._load_char_delete_dialog_open:
            if cur_time < self._load_char_dialog_debounce:
                return

            cancel_pressed = (state.pressed("b") and not self._previous.pressed("b"))
            action_pressed = (
                (state.pressed("a") and not self._previous.pressed("a"))
                or (state.pressed("x") and not self._previous.pressed("x"))
            )

            dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
            dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

            new_focus = current
            if dpad_up:
                new_focus = "delete_confirm"
            elif dpad_down:
                new_focus = "delete_cancel"

            if new_focus != current:
                self._load_char_focus = new_focus
                target_x, target_y = load_char_button_point(rect, new_focus)
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(load_char_focus=new_focus, load_char_delete_open=True)
                return

            if cancel_pressed or (action_pressed and current == "delete_cancel"):
                # Clica em Cancelar no modal
                target_x, target_y = load_char_button_point(rect, "delete_cancel")
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.05)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.10, 35)

                # Debounce: aguarda o modal fechar no jogo antes de devolver o cursor
                self._wait_for_input(0.20)

                # Cursor volta para o botão de delete pequeno na parte inferior da tela
                self._load_char_delete_dialog_open = False
                self._load_char_focus = "delete"
                del_x, del_y = load_char_button_point(rect, "delete")
                self.injector.move(del_x, del_y)
                self._load_char_dialog_debounce = cur_time + 0.25
                self.shared.update(load_char_focus="delete", load_char_delete_open=False)
                return

            if action_pressed and current == "delete_confirm":
                # Clica em Deletar para confirmar exclusão
                target_x, target_y = load_char_button_point(rect, "delete_confirm")
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.05)
                self.injector.mouse_button("left", False)
                hub.rumble(0.06, 0.15, 50)

                # Debounce: aguarda a exclusão assentar antes de devolver o cursor
                self._wait_for_input(0.20)

                # Cursor volta para o botão de delete pequeno na parte inferior da tela
                self._load_char_delete_dialog_open = False
                self._load_char_focus = "delete"
                if self._load_char_scroll_offset > 0:
                    self._load_char_scroll_offset -= 1
                del_x, del_y = load_char_button_point(rect, "delete")
                self.injector.move(del_x, del_y)
                self._load_char_dialog_debounce = cur_time + 0.25
                self.shared.update(load_char_focus="delete", load_char_delete_open=False)
                return

            return

        # -------------------------------------------------------------
        # CASO 2: Navegação Normal na Tela de Carregar Personagem
        # -------------------------------------------------------------
        # Botão B: atalho direto para Voltar ao Menu Principal
        if state.pressed("b") and not self._previous.pressed("b"):
            self._load_char_focus = "back"
            target_x, target_y = load_char_button_point(rect, "back")
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.10, 35)
            self.shared.update(load_char_focus="back", load_char_delete_open=False)
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.04)
            self.injector.mouse_button("left", False)
            return

        # Ações de Seleção / Clique (Botão A ou X):
        action_pressed = (
            (state.pressed("a") and not self._previous.pressed("a"))
            or (state.pressed("x") and not self._previous.pressed("x"))
        )

        if action_pressed:
            # 1. Selecionou um personagem no lado direito da tela:
            # Clica no slot para selecionar o personagem e move imediatamente o cursor para o botão Play
            if current.startswith("slot_"):
                slot_x, slot_y = load_char_button_point(rect, current)
                self.injector.move(slot_x, slot_y)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.04)
                self.injector.mouse_button("left", False)

                # Move para o Play na barra inferior
                self._load_char_last_slot = current
                self._load_char_focus = "play"
                play_x, play_y = load_char_button_point(rect, "play")
                self.injector.move(play_x, play_y)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(load_char_focus="play", load_char_delete_open=False)
                return

            # 2. Clicou no botão pequeno de delete:
            # Abre o modal de confirmação com foco padrão em Cancelar (amarelo)
            elif current == "delete":
                if cur_time < self._load_char_dialog_debounce:
                    return

                del_x, del_y = load_char_button_point(rect, "delete")
                self.injector.move(del_x, del_y)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.05)
                self.injector.mouse_button("left", False)

                # Debounce crucial: aguarda 200ms com o cursor ainda no botão Delete inferior
                # para o clique físico assentar e o popup abrir no jogo antes de mover para Cancelar.
                self._wait_for_input(0.20)

                self._load_char_delete_dialog_open = True
                self._load_char_focus = "delete_cancel"
                target_x, target_y = load_char_button_point(rect, "delete_cancel")
                self.injector.move(target_x, target_y)
                hub.rumble(0.04, 0.10, 35)
                self._load_char_dialog_debounce = cur_time + 0.25
                self.shared.update(load_char_focus="delete_cancel", load_char_delete_open=True)
                return

            # 3. Clicou em Play, Back ou Scroll
            elif current in ("play", "back", "scroll_up", "scroll_down"):
                target_x, target_y = load_char_button_point(rect, current)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.04)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.10, 35)
                if current == "scroll_down":
                    self._load_char_scroll_offset += 1
                elif current == "scroll_up" and self._load_char_scroll_offset > 0:
                    self._load_char_scroll_offset -= 1
                return

        # Navegação com D-pad
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        save_count = self._memory_state.save_count
        max_visible_slots = min(5, max(1, save_count)) if save_count > 0 else 5

        new_focus = current

        # D-pad Cima / Baixo
        if dpad_down:
            if current == "scroll_up":
                new_focus = "slot_1"
            elif current == "slot_1":
                new_focus = "slot_2" if max_visible_slots >= 2 else "slot_1"
            elif current == "slot_2":
                new_focus = "slot_3" if max_visible_slots >= 3 else "slot_2"
            elif current == "slot_3":
                new_focus = "slot_4" if max_visible_slots >= 4 else "slot_3"
            elif current == "slot_4":
                new_focus = "slot_5" if max_visible_slots >= 5 else "slot_4"
            elif current == "slot_5":
                # Rolagem contínua via D-pad: se houver mais personagens abaixo da página visível,
                # clica na seta inferior para rolar 1 personagem e mantém o cursor no slot_5.
                max_offset = max(0, save_count - 5) if save_count > 0 else 0
                if save_count > 5 and self._load_char_scroll_offset < max_offset:
                    scroll_x, scroll_y = load_char_button_point(rect, "scroll_down")
                    self.injector.move(scroll_x, scroll_y)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.04)
                    self.injector.mouse_button("left", False)
                    self._load_char_scroll_offset += 1

                    slot_x, slot_y = load_char_button_point(rect, "slot_5")
                    self.injector.move(slot_x, slot_y)
                    hub.rumble(0.04, 0.10, 35)
                    self._load_char_focus = "slot_5"
                    self._load_char_last_slot = "slot_5"
                    self.shared.update(load_char_focus="slot_5", load_char_delete_open=False)
                    return
        elif dpad_up:
            if current == "scroll_down":
                new_focus = "slot_5"
            elif current == "slot_5":
                new_focus = "slot_4"
            elif current == "slot_4":
                new_focus = "slot_3"
            elif current == "slot_3":
                new_focus = "slot_2"
            elif current == "slot_2":
                new_focus = "slot_1"
            elif current == "slot_1":
                # Rolagem contínua via D-pad: se a lista foi rolada para baixo,
                # clica na seta superior para rolar 1 personagem para cima e mantém o cursor no slot_1.
                if self._load_char_scroll_offset > 0:
                    scroll_x, scroll_y = load_char_button_point(rect, "scroll_up")
                    self.injector.move(scroll_x, scroll_y)
                    self.injector.mouse_button("left", True)
                    self._wait_for_input(0.04)
                    self.injector.mouse_button("left", False)
                    self._load_char_scroll_offset -= 1

                    slot_x, slot_y = load_char_button_point(rect, "slot_1")
                    self.injector.move(slot_x, slot_y)
                    hub.rumble(0.04, 0.10, 35)
                    self._load_char_focus = "slot_1"
                    self._load_char_last_slot = "slot_1"
                    self.shared.update(load_char_focus="slot_1", load_char_delete_open=False)
                    return
            elif current in ("back", "delete", "play"):
                new_focus = self._load_char_last_slot or "slot_1"

        # D-pad Esquerda / Direita
        elif dpad_left:
            if current.startswith("slot_") or current in ("scroll_up", "scroll_down"):
                self._load_char_last_slot = current if current.startswith("slot_") else "slot_1"
                new_focus = "play"
            elif current == "play":
                new_focus = "delete"
            elif current == "delete":
                new_focus = "back"
        elif dpad_right:
            if current == "back":
                new_focus = "delete"
            elif current == "delete":
                new_focus = "play"
            elif current == "play":
                new_focus = self._load_char_last_slot or "slot_1"

        if new_focus != current:
            self._load_char_focus = new_focus
            if new_focus.startswith("slot_"):
                self._load_char_last_slot = new_focus
            target_x, target_y = load_char_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(load_char_focus=new_focus, load_char_delete_open=False)

    def _handle_settings_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        now: float = 0.0,
    ) -> None:
        """Gerencia a navegação na Tela de Configurações (Settings) via D-pad e atalhos."""
        if not self._settings_initialized:
            self._settings_initialized = True
            self._settings_focus = "row1_col1"
            self._settings_dropdown = None
            self._settings_dropdown_idx = 0
            self._settings_slider_dragging = False
            self._settings_sound_vol = self._memory_state.sound_volume
            self._settings_music_vol = self._memory_state.music_volume
            target_x, target_y = settings_button_point(rect, self._settings_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(
                settings_focus=self._settings_focus,
                settings_dropdown=None,
                settings_dropdown_idx=0,
                settings_slider_dragging=False,
                settings_sound_vol=self._settings_sound_vol,
                settings_music_vol=self._settings_music_vol,
            )
            return

        current = self._settings_focus or "row1_col1"

        btn_a_pressed = (state.pressed("a") and not self._previous.pressed("a"))
        btn_b_pressed = (state.pressed("b") and not self._previous.pressed("b"))
        btn_x_pressed = (state.pressed("x") and not self._previous.pressed("x"))
        action_pressed = (btn_a_pressed or btn_x_pressed)

        dpad_up = (state.pressed("dpad_up") and not self._previous.pressed("dpad_up"))
        dpad_down = (state.pressed("dpad_down") and not self._previous.pressed("dpad_down"))
        dpad_left = (state.pressed("dpad_left") and not self._previous.pressed("dpad_left"))
        dpad_right = (state.pressed("dpad_right") and not self._previous.pressed("dpad_right"))

        # -------------------------------------------------------------
        # CASO 1: Slider Dragging (ajuste horizontal com clique segurado)
        # -------------------------------------------------------------
        if self._settings_slider_dragging:
            if btn_b_pressed or action_pressed:
                # OBS 1: Apertar B (ou A/X) solta o clique esquerdo e libera navegação
                self._settings_slider_dragging = False
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(settings_slider_dragging=False)
                return

            stick_left = (state.lx < -0.4 and (now - self._settings_slider_last_stick >= 0.08))
            stick_right = (state.lx > 0.4 and (now - self._settings_slider_last_stick >= 0.08))

            if dpad_left or stick_left:
                if stick_left:
                    self._settings_slider_last_stick = now
                step = 0.05
                if current == "music_slider":
                    self._settings_music_vol = clamp(self._settings_music_vol - step, 0.0, 1.0)
                    target_x, target_y = settings_button_point(rect, "music_slider", self._settings_music_vol)
                else:
                    self._settings_sound_vol = clamp(self._settings_sound_vol - step, 0.0, 1.0)
                    target_x, target_y = settings_button_point(rect, "sound_slider", self._settings_sound_vol)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                hub.rumble(0.02, 0.05, 20)
                self.shared.update(
                    settings_sound_vol=self._settings_sound_vol,
                    settings_music_vol=self._settings_music_vol,
                )
            elif dpad_right or stick_right:
                if stick_right:
                    self._settings_slider_last_stick = now
                step = 0.05
                if current == "music_slider":
                    self._settings_music_vol = clamp(self._settings_music_vol + step, 0.0, 1.0)
                    target_x, target_y = settings_button_point(rect, "music_slider", self._settings_music_vol)
                else:
                    self._settings_sound_vol = clamp(self._settings_sound_vol + step, 0.0, 1.0)
                    target_x, target_y = settings_button_point(rect, "sound_slider", self._settings_sound_vol)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                hub.rumble(0.02, 0.05, 20)
                self.shared.update(
                    settings_sound_vol=self._settings_sound_vol,
                    settings_music_vol=self._settings_music_vol,
                )
            return

        # -------------------------------------------------------------
        # CASO 2: Dropdown Aberto (Resolution, Shadows, Particle Detail)
        # -------------------------------------------------------------
        if self._settings_dropdown is not None:
            dropdown_name = self._settings_dropdown
            drop_info = SETTINGS_DROPDOWNS.get(dropdown_name, {})
            options = drop_info.get("options", [])
            total_options = len(options)

            if btn_b_pressed:
                # OBS 2: Apertar B volta ao ponto rosa e clica nele para fechar o dropdown
                pink_btn = dropdown_name
                self._settings_dropdown = None
                self._settings_dropdown_idx = 0
                self._settings_focus = pink_btn
                target_x, target_y = settings_button_point(rect, pink_btn)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(
                    settings_dropdown=None,
                    settings_dropdown_idx=0,
                    settings_focus=pink_btn,
                )
                return

            if action_pressed:
                # OBS 2: Pressionar A/X em uma opção clica nela e volta para a opção rosa
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                pink_btn = dropdown_name
                self._settings_dropdown = None
                self._settings_dropdown_idx = 0
                self._settings_focus = pink_btn
                target_x, target_y = settings_button_point(rect, pink_btn)
                self.injector.move(target_x, target_y)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(
                    settings_dropdown=None,
                    settings_dropdown_idx=0,
                    settings_focus=pink_btn,
                )
                return

            if dpad_up and self._settings_dropdown_idx > 0:
                self._settings_dropdown_idx -= 1
                target_x, target_y = settings_dropdown_option_point(rect, dropdown_name, self._settings_dropdown_idx)
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(settings_dropdown_idx=self._settings_dropdown_idx)
            elif dpad_down and self._settings_dropdown_idx < total_options - 1:
                self._settings_dropdown_idx += 1
                target_x, target_y = settings_dropdown_option_point(rect, dropdown_name, self._settings_dropdown_idx)
                self.injector.move(target_x, target_y)
                hub.rumble(0.03, 0.08, 30)
                self.shared.update(settings_dropdown_idx=self._settings_dropdown_idx)
            return

        # -------------------------------------------------------------
        # CASO 3: Tela Principal de Configurações
        # -------------------------------------------------------------
        if btn_b_pressed:
            # Botão B fecha as configurações clicando no botão Cancelar
            target_x, target_y = settings_button_point(rect, "cancel")
            self.injector.move(target_x, target_y)
            self.injector.mouse_button("left", True)
            self.injector.mouse_button("left", False)
            self._settings_focus = "cancel"
            hub.rumble(0.05, 0.12, 40)
            self.shared.update(settings_focus="cancel")
            return

        if action_pressed:
            if current in ("sound_slider", "music_slider"):
                # OBS 1: Apertar A/X sobre o roxo inicia o hold do clique esquerdo
                vol = self._settings_music_vol if current == "music_slider" else self._settings_sound_vol
                target_x, target_y = settings_button_point(rect, current, vol)
                self.injector.move(target_x, target_y)
                self.injector.mouse_button("left", True)
                self._settings_slider_dragging = True
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(settings_slider_dragging=True)
                return
            elif current in ("resolution", "shadows", "particle_detail"):
                # OBS 2: Apertar A/X no botão rosa abre o dropdown e move cursor pro amarelo
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                self._settings_dropdown = current
                self._settings_dropdown_idx = 0
                target_x, target_y = settings_dropdown_option_point(rect, current, 0)
                self.injector.move(target_x, target_y)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(
                    settings_dropdown=current,
                    settings_dropdown_idx=0,
                )
                return
            else:
                # Botões normais (checkboxes, mute, cancel, apply)
                self.injector.mouse_button("left", True)
                self.injector.mouse_button("left", False)
                hub.rumble(0.04, 0.10, 35)
                return

        # Navegação no grafo de posições
        new_focus = current
        nav_options = SETTINGS_NAV_MAP.get(current, {})
        if dpad_up and "up" in nav_options:
            new_focus = nav_options["up"]
        elif dpad_down and "down" in nav_options:
            new_focus = nav_options["down"]
        elif dpad_left and "left" in nav_options:
            new_focus = nav_options["left"]
        elif dpad_right and "right" in nav_options:
            new_focus = nav_options["right"]

        if new_focus != current:
            self._settings_focus = new_focus
            if new_focus == "sound_slider":
                target_x, target_y = settings_button_point(rect, new_focus, self._settings_sound_vol)
            elif new_focus == "music_slider":
                target_x, target_y = settings_button_point(rect, new_focus, self._settings_music_vol)
            else:
                target_x, target_y = settings_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(settings_focus=new_focus)
