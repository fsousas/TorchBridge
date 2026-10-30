from __future__ import annotations

from ..controller import ControllerHub
from ..models import (
    ControllerState,
    Rect,
    death_screen_button_point,
    dialog_button_point,
    difficulty_menu_button_point,
    fishing_hook_point,
    modal_ok_point,
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

    def _handle_fishing_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia o posicionamento e interação na interface de pesca."""
        target_x, target_y = fishing_hook_point(rect)
        if not self._fishing_initialized:
            self._fishing_initialized = True
            self.injector.move(target_x, target_y)
            self.shared.update(fishing_focus="hook")

        # Mantém o cursor fixo no anzol como única opção
        cur_x, cur_y = self.injector.cursor_position()
        if abs(cur_x - target_x) > 4 or abs(cur_y - target_y) > 4:
            self.injector.move(target_x, target_y)

        btn_a_pressed = state.pressed("a") and not self._previous.pressed("a")
        btn_x_pressed = state.pressed("x") and not self._previous.pressed("x")
        if btn_a_pressed or btn_x_pressed:
            self.injector.move(target_x, target_y)
            self.injector.mouse_button("left", True)
            self.injector.mouse_button("left", False)
            hub.rumble(0.04, 0.10, 35)

    def _handle_modal_confirm_navigation(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
    ) -> None:
        """Gerencia o posicionamento e confirmação no popup modal (Ok do peixe/mensagem)."""
        target_x, target_y = modal_ok_point(rect)
        if not self._modal_confirm_initialized:
            self._modal_confirm_initialized = True
            self.injector.move(target_x, target_y)
            self.shared.update(modal_confirm_focus="ok")

        # Garante o cursor sobre o botão Ok
        cur_x, cur_y = self.injector.cursor_position()
        if abs(cur_x - target_x) > 4 or abs(cur_y - target_y) > 4:
            self.injector.move(target_x, target_y)

        btn_a_pressed = state.pressed("a") and not self._previous.pressed("a")
        btn_x_pressed = state.pressed("x") and not self._previous.pressed("x")
        btn_b_pressed = state.pressed("b") and not self._previous.pressed("b")

        if btn_a_pressed or btn_x_pressed or btn_b_pressed:
            self.injector.move(target_x, target_y)
            self.injector.mouse_button("left", True)
            self.injector.mouse_button("left", False)
            hub.rumble(0.04, 0.10, 35)
