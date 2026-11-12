from __future__ import annotations

from ..controller import ControllerHub
from ..models import (
    ControllerState,
    Rect,
    death_screen_button_point,
    dialog_button_point,
    difficulty_menu_button_point,
    fishing_hook_point,
    fishing_close_point,
    modal_ok_point,
    modal_tips_checkbox_point,
    pause_menu_button_point,
    title_menu_button_point,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class CommonMenuNavigationMixin:
    """Mixin com métodos de navegação para common_menus."""

    def _handle_title_menu_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação pelos botões da Tela Inicial (Title Screen) via D-pad."""
        has_save = (self._memory_state.save_count >= 1)

        # Inicialização ao entrar na Tela Inicial
        if not self._title_screen_initialized or self._last_state_id != 0:
            self._title_screen_initialized = True
            self._last_state_id = 0
            self._title_focus = "continue" if has_save else "new_character"
            target_x, target_y = title_menu_button_point(rect, self._title_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(title_menu_focus=self._title_focus)
            return

        current = self._title_focus
        new_focus = current

        # Transições via D-pad (na borda de subida)
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_right:
            if current == "new_character":
                new_focus = "load_character"
            elif current == "load_character":
                new_focus = "settings"
            elif current == "settings":
                new_focus = "quit_game"
            elif current == "continue":
                new_focus = "quit_game"
        elif dpad_left:
            if current == "quit_game":
                new_focus = "settings"
            elif current == "settings":
                new_focus = "load_character"
            elif current == "load_character":
                new_focus = "new_character"
            elif current == "continue":
                new_focus = "settings"
        elif dpad_down:
            if current == "continue":
                new_focus = "quit_game"
        elif dpad_up:
            if has_save and current in ("quit_game", "settings"):
                new_focus = "continue"

        if new_focus != current:
            self._title_focus = new_focus
            target_x, target_y = title_menu_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(title_menu_focus=new_focus)

    def _handle_difficulty_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação na Tela de Seleção de Dificuldade (state_id == 2) via D-pad."""
        if not self._difficulty_initialized or self._last_state_id not in (2, 4):
            self._difficulty_initialized = True
            self._last_state_id = self._memory_state.state_id
            self._difficulty_focus = "hardcore"
            target_x, target_y = difficulty_menu_button_point(rect, self._difficulty_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(difficulty_focus=self._difficulty_focus)
            return

        current = self._difficulty_focus
        new_focus = current

        # Botão B (Bolinha no PlayStation / B no Xbox): atalho direto para Voltar
        if state.pressed("b") and not self._previous.pressed("b"):
            self._difficulty_focus = "back"
            target_x, target_y = difficulty_menu_button_point(rect, "back")
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.10, 35)
            self.shared.update(difficulty_focus="back")
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.04)
            self.injector.mouse_button("left", False)
            return

        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_down:
            if current == "easy":
                new_focus = "normal"
            elif current == "normal":
                new_focus = "hard"
            elif current == "hard":
                new_focus = "very_hard"
            elif current == "very_hard":
                new_focus = "hardcore"
            elif current == "hardcore":
                new_focus = "back"
        elif dpad_up:
            if current == "back":
                new_focus = "hardcore"
            elif current == "hardcore":
                new_focus = "very_hard"
            elif current == "very_hard":
                new_focus = "hard"
            elif current == "hard":
                new_focus = "normal"
            elif current == "normal":
                new_focus = "easy"
        elif dpad_right:
            if current == "hardcore":
                new_focus = "very_hard"
        elif dpad_left:
            if current in ("easy", "normal", "hard", "very_hard"):
                new_focus = "hardcore"

        if new_focus != current:
            self._difficulty_focus = new_focus
            target_x, target_y = difficulty_menu_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(difficulty_focus=new_focus)

    def _handle_dialog_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação nos botões de diálogos (Ok, Accept, Decline, Continue) e slot de recompensa via D-pad."""
        dtype = self._memory_state.dialog_type
        buttons = self._memory_state.dialog_buttons
        has_reward = self._memory_state.dialog_has_item_reward
        if not dtype or not buttons:
            return

        # Inicialização ao entrar no diálogo ou mudar de tipo
        if not self._dialog_initialized or self._last_dialog_type != dtype:
            self._dialog_initialized = True
            self._last_dialog_type = dtype
            # Default focus: primeiro botão da lista (Accept em missao_aceitar, Ok em andamento/concluida)
            self._dialog_focus = buttons[0]
            target_x, target_y = dialog_button_point(rect, self._dialog_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(
                dialog_focus=self._dialog_focus,
                dialog_type=dtype,
                dialog_buttons=list(buttons),
                dialog_has_reward=has_reward,
            )
            return

        current = self._dialog_focus or buttons[0]
        new_focus = current

        # Botão B (Bolinha no PlayStation / B no Xbox): atalho direto para Recusar / Decline se disponível
        if "decline" in buttons:
            if state.pressed("b") and not self._previous.pressed("b"):
                self._dialog_focus = "decline"
                target_x, target_y = dialog_button_point(rect, "decline")
                self.injector.move(target_x, target_y)
                hub.rumble(0.04, 0.10, 35)
                self.shared.update(dialog_focus="decline")
                self.injector.mouse_button("left", True)
                self._wait_for_input(0.04)
                self.injector.mouse_button("left", False)
                return

        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")

        if dpad_right:
            if current == "reward_slot":
                # Da recompensa para a direita: volta para o botão de ação (accept ou ok)
                new_focus = "accept" if "accept" in buttons else "ok"
            elif "decline" in buttons and current == "accept":
                new_focus = "decline"
        elif dpad_left:
            if current == "decline" and "accept" in buttons:
                new_focus = "accept"
            elif current in ("accept", "ok") and has_reward:
                new_focus = "reward_slot"

        if new_focus != current:
            self._dialog_focus = new_focus
            target_x, target_y = dialog_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(dialog_focus=new_focus)

    def _handle_pause_menu_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação no Menu de Pause (COptionsMenu / Options) em jogo via D-pad."""
        if not self._pause_menu_initialized:
            self._pause_menu_initialized = True
            # Foco padrão: 'return_to_game' (marcador amarelo do usuário)
            self._pause_focus = "return_to_game"
            target_x, target_y = pause_menu_button_point(rect, self._pause_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(pause_menu_focus=self._pause_focus)
            return

        current = self._pause_focus or "return_to_game"
        new_focus = current

        # Botão B: atalho direto para Retornar ao Jogo
        if state.pressed("b") and not self._previous.pressed("b"):
            self._pause_focus = "return_to_game"
            target_x, target_y = pause_menu_button_point(rect, "return_to_game")
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.10, 35)
            self.shared.update(pause_menu_focus="return_to_game")
            self.injector.mouse_button("left", True)
            self._wait_for_input(0.04)
            self.injector.mouse_button("left", False)
            return

        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_up:
            if current == "return_to_game":
                new_focus = "exit_to_title"
            elif current == "exit_to_title":
                new_focus = "settings"
        elif dpad_down:
            if current == "settings":
                new_focus = "exit_to_title"
            elif current == "exit_to_title":
                new_focus = "return_to_game"

        if new_focus != current:
            self._pause_focus = new_focus
            target_x, target_y = pause_menu_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(pause_menu_focus=new_focus)

    def _handle_death_screen_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia a navegação na Tela de Morte / Respawn em jogo via D-pad."""
        if not self._death_screen_initialized:
            self._death_screen_initialized = True
            # Foco padrão: 'resurrect_entrance' (marcador amarelo do usuário)
            self._death_screen_focus = "resurrect_entrance"
            target_x, target_y = death_screen_button_point(rect, self._death_screen_focus)
            self.injector.move(target_x, target_y)
            self.shared.update(death_screen_focus=self._death_screen_focus)
            return

        current = self._death_screen_focus or "resurrect_entrance"
        new_focus = current

        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        if dpad_up:
            if current == "exit_to_title":
                new_focus = "resurrect_town"
            elif current == "resurrect_town":
                new_focus = "resurrect_entrance"
            elif current == "resurrect_entrance":
                new_focus = "resurrect_here"
        elif dpad_down:
            if current == "resurrect_here":
                new_focus = "resurrect_entrance"
            elif current == "resurrect_entrance":
                new_focus = "resurrect_town"
            elif current == "resurrect_town":
                new_focus = "exit_to_title"

        if new_focus != current:
            self._death_screen_focus = new_focus
            target_x, target_y = death_screen_button_point(rect, new_focus)
            self.injector.move(target_x, target_y)
            hub.rumble(0.03, 0.08, 30)
            self.shared.update(death_screen_focus=new_focus)

    def _cancel_fishing_click(self, *, clear_pending: bool = True) -> None:
        if self._fishing_click_down:
            self.injector.mouse_button("left", False)
        self._fishing_click_seq = None
        self._fishing_click_down = False
        if clear_pending:
            self._fishing_next_click = None

    def _handle_fishing_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        now: float,
        *, visible: bool = True,
    ) -> None:
        """Fishing owns controller input: confirm hooks, cancel clicks 50 px up."""
        if not self._fishing_initialized:
            self._fishing_initialized = True
            self._fishing_closing = False
            # Entry can follow an A attack or a modified inventory click. Release
            # those inputs before the game's fishing click is allowed to happen.
            for button in ("left", "right"):
                self.injector.mouse_button(button, False)
                self._held_mouse.discard(button)
            self._modifier_seq = self._pet_click_seq = self._hud_click_seq = None
            self._modifier_left_down = self._modifier_left_up = False
            self._previous_left_pressed = self._a_shift_held = False
            for modifier in ("SHIFT", "CTRL"):
                self._held_keys.discard(modifier)
                self._ensure_modifier_released(modifier)
            self._skill_repeat_at.clear()
            self._skill_repeat_sources.clear()
            for key in tuple(self._held_keys):
                self._set_key(key, False)
            self._cancel_world_interaction()
            self._native_heading = None
            self.shared.update(fishing_focus="hook", radial_active=False, pet_submenu_open=False)

        # Casting/reeling states precede/follow the visible menu. Consume input
        # through that whole transition, but click only while the hook exists.
        self._blocked_buttons.update(state.buttons)
        self._blocked_lt = self._blocked_lt or state.lt >= self.TRIGGER_ACTIVE_THRESHOLD
        self._blocked_rt = self._blocked_rt or state.rt >= self.TRIGGER_ACTIVE_THRESHOLD
        if state.pressed("back") or state.pressed("start"):
            self._center_combo_seen = self._center_combo_triggered = True
        if not visible:
            self._cancel_fishing_click()
            self.shared.update(fishing_focus=None)
            return

        confirm, cancel = self._keyboard_buttons(state)
        hook_pressed = state.pressed(confirm) and not self._previous.pressed(confirm)
        close_pressed = state.pressed(cancel) and not self._previous.pressed(cancel)
        if close_pressed or hook_pressed:
            self._fishing_next_click = close_pressed
        start_click = self._fishing_click_seq is None and self._fishing_next_click is not None
        if start_click:
            self._fishing_closing = self._fishing_next_click
            self._fishing_next_click = None
        target_x, target_y = fishing_close_point(rect) if self._fishing_closing else fishing_hook_point(rect)
        self.shared.update(fishing_focus="close" if self._fishing_closing else "hook")
        cur_x, cur_y = self.injector.cursor_position()
        if abs(cur_x - target_x) > 4 or abs(cur_y - target_y) > 4:
            self.injector.move(target_x, target_y)

        # Ignore and consume every other input, including deferred Back/Start
        # releases. A held fishing button must not turn into combat after close.
        if start_click:
            # The game polls its input per frame. Same-tick down/up can vanish
            # under OIS/Wine, and Wayland cursor moves arrive asynchronously.
            # Give the pointer/modifier releases a frame, then hold one plain
            # click across frames without blocking native heartbeats/focus checks.
            self.injector.move(target_x, target_y)
            self._fishing_click_seq = (target_x, target_y, now + .030)
        if self._fishing_click_seq is not None:
            x, y, deadline = self._fishing_click_seq
            if now >= deadline:
                if self._fishing_click_down:
                    self._cancel_fishing_click(clear_pending=False)
                elif any(self.injector.key_pressed(key) for key in ("SHIFT", "CTRL")):
                    self._cancel_fishing_click()
                else:
                    self.injector.move(x, y)
                    if self.injector.mouse_button("left", True):
                        self._fishing_click_down = True
                        self._fishing_click_seq = (x, y, now + .060)
                        hub.rumble(0.04, 0.10, 35)
                    else:
                        self._cancel_fishing_click()

    def _handle_modal_confirm_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia o posicionamento e confirmação no popup modal (Ok do peixe/mensagem/tutorial)."""
        tutorial = "Dica (Tutorial)" in (self._memory_state.open_menus or [])
        if not self._modal_confirm_initialized:
            self._modal_confirm_initialized = True
            self._modal_confirm_focus = "ok"
            target_x, target_y = modal_ok_point(rect, tutorial=tutorial)
            self.injector.move(target_x, target_y)
            self.shared.update(modal_confirm_focus=self._modal_confirm_focus)

        if tutorial:
            dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
            dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
            dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
            dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")
            stick_right = state.lx > 0.5 and self._previous.lx <= 0.5
            stick_left = state.lx < -0.5 and self._previous.lx >= -0.5

            current = getattr(self, "_modal_confirm_focus", "ok")
            new_focus = current
            if (dpad_right or stick_right or dpad_up) and current == "ok":
                new_focus = "show_tips"
            elif (dpad_left or stick_left or dpad_down) and current == "show_tips":
                new_focus = "ok"

            if new_focus != current:
                self._modal_confirm_focus = new_focus
                self.shared.update(modal_confirm_focus=new_focus)
                hub.rumble(0.03, 0.08, 30)

        focus = getattr(self, "_modal_confirm_focus", "ok")
        if tutorial and focus == "show_tips":
            target_x, target_y = modal_tips_checkbox_point(rect)
        else:
            target_x, target_y = modal_ok_point(rect, tutorial=tutorial)

        # Garante o cursor sobre o elemento focado
        cur_x, cur_y = self.injector.cursor_position()
        if abs(cur_x - target_x) > 4 or abs(cur_y - target_y) > 4:
            self.injector.move(target_x, target_y)

        btn_a_pressed = state.pressed("a") and not self._previous.pressed("a")
        btn_x_pressed = state.pressed("x") and not self._previous.pressed("x")
        btn_b_pressed = state.pressed("b") and not self._previous.pressed("b")

        if btn_b_pressed:
            ok_x, ok_y = modal_ok_point(rect, tutorial=tutorial)
            self.injector.move(ok_x, ok_y)
            if tutorial:
                self._wait_for_input(0.03)  # Let Wine/OIS receive the cursor first.
            try:
                self.injector.mouse_button("left", True)
                if tutorial:
                    self._wait_for_input(0.06)  # A same-frame down/up can be lost.
            finally:
                self.injector.mouse_button("left", False)
            hub.rumble(0.04, 0.10, 35)
        elif btn_a_pressed or btn_x_pressed:
            self.injector.move(target_x, target_y)
            if tutorial:
                self._wait_for_input(0.03)  # Let Wine/OIS receive the cursor first.
            try:
                self.injector.mouse_button("left", True)
                if tutorial:
                    self._wait_for_input(0.06)  # A same-frame down/up can be lost.
            finally:
                self.injector.mouse_button("left", False)
            hub.rumble(0.04, 0.10, 35)
