from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..controller import ControllerHub
from ..models import (
    ControllerState,
    Rect,
    resource_root,
    welcome_button_point,
    welcome_button_rect,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class WelcomeNavigationMixin:
    """Mixin com métodos de navegação e ciclo de vida da tela de Boas-Vindas (TB-17)."""

    def _init_welcome_state(self) -> None:
        self._welcome_open: bool = False
        self._welcome_page: int = 1
        self._welcome_focus: str = "next"
        self._welcome_can_close: bool = False
        self._welcome_first_checked: bool = False
        self._welcome_close_latched: bool = False
        self._welcome_close_until: float = 0.0
        self._welcome_total_pages: int = self._get_welcome_total_pages()

    def _get_welcome_total_pages(self) -> int:
        """Determina o total de páginas lendo os arquivos numerados em assets/hud/boas-vindas/Telas."""
        telas_dir = resource_root() / "assets" / "hud" / "boas-vindas" / "Telas"
        if not telas_dir.is_dir():
            return 9
        count = 0
        for p in telas_dir.glob("*.png"):
            try:
                val = int(p.stem)
                if val > count:
                    count = val
            except ValueError:
                continue
        return max(1, count)

    def _is_welcome_suppressed(self) -> bool:
        """Verifica se a tela de boas-vindas deve ficar temporariamente oculta/inativa.
        
        Suprime durante inicialização do CGame (launcher, splash screens, logos),
        telas de carregamento (loading), desconexão de memória ou telas de transição.
        """
        mem = getattr(self, "_memory_state", None)
        if not mem or not getattr(mem, "is_connected", False):
            return True
        if getattr(mem, "is_loading", False):
            return True
        desc = (getattr(mem, "state_desc", "") or "").lower().strip()
        if not desc:
            return True
        if any(k in desc for k in ("inicializando", "aguardando", "carregando", "loading")):
            return True
        return False

    def _is_welcome_allowed_to_show(self) -> bool:
        """Verifica se o jogo está em tela válida para exibir as boas-vindas pela primeira vez.

        Não deve aparecer no launcher, nem em telas de loading, nem antes do menu principal.
        Só é permitido quando a memória estiver conectada, não estiver carregando,
        não estiver inicializando CGame, e o jogo estiver na Tela Inicial (menu principal, state_id == 0) ou já em jogo.
        """
        if self._is_welcome_suppressed():
            return False
        mem = getattr(self, "_memory_state", None)
        if not mem:
            return False
        state_id = getattr(mem, "state_id", -1)
        # Estado 0: Tela Inicial (menu principal do Torchlight)
        if state_id == 0:
            return True
        # Em jogo (state_id == 6 ou is_in_game)
        if getattr(mem, "is_in_game", False) or state_id == 6:
            return True
        return False

    def _safe_move_to_button(self, rect: Rect, button_name: str) -> None:
        if self._is_welcome_suppressed():
            return
        if rect.valid:
            try:
                target_x, target_y = welcome_button_point(rect, button_name)
                self._welcome_last_cursor_pos = (target_x, target_y)
                self.injector.move(target_x, target_y)
            except Exception:
                pass

    def _open_welcome(self, can_close: bool, rect: Rect) -> None:
        """Abre a tela de boas-vindas com foco inicial no botão Próximo."""
        if hasattr(self, "_release_all"):
            self._release_all()
        self._welcome_total_pages = self._get_welcome_total_pages()
        self._welcome_open = True
        self._welcome_page = 1
        self._welcome_focus = "next"
        self._welcome_can_close = can_close
        self.shared.update(
            welcome_screen_open=True,
            welcome_screen_page=1,
            welcome_screen_total_pages=self._welcome_total_pages,
            welcome_screen_focus="next",
            welcome_screen_can_close=can_close,
        )
        self._safe_move_to_button(rect, "next")

    def _close_welcome(self, from_last_page: bool = False, rect: Rect | None = None, now: float | None = None) -> None:
        """Fecha a tela de boas-vindas e atualiza perfil.json se fechado no botão final."""
        import time

        self._welcome_open = False
        self._welcome_close_latched = True
        base_now = now if now is not None else time.monotonic()
        self._welcome_close_until = base_now + 0.25
        if hasattr(self, "_release_all"):
            self._release_all()

        if from_last_page:
            try:
                self.config.set_show_welcome(0)
            except Exception as exc:
                if log:
                    log.warning("Falha ao atualizar show-welcome no perfil: %s", exc)
        self.shared.update(
            welcome_screen_open=False,
            welcome_screen_focus="next",
        )

    def _handle_welcome_navigation(
        self,
        hub: ControllerHub,
        state: ControllerState,
        rect: Rect,
        cfg: dict[str, Any],
        now: float,
    ) -> bool:
        """Processa navegação por D-pad e botões exclusivamente na tela de boas-vindas.
        
        Retorna True se a tela consumiu o tick.
        """
        if not self._welcome_open:
            return False

        total = self._welcome_total_pages
        page = self._welcome_page
        is_first = (page == 1)
        is_last = (page >= total)

        # Transições via D-pad (na borda de subida)
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")
        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_up = state.pressed("dpad_up") and not self._previous.pressed("dpad_up")
        dpad_down = state.pressed("dpad_down") and not self._previous.pressed("dpad_down")

        # Botão Sul (Confirmar / Interagir) e Botão Leste / Start (Cancelar / Fechar)
        nintendo = any(name in state.controller_type.lower() for name in ("nintendo", "switch"))
        confirm_btn = "b" if nintendo else "a"
        cancel_btn = "a" if nintendo else "b"

        confirm_pressed = (
            (state.pressed(confirm_btn) and not self._previous.pressed(confirm_btn))
            or (state.pressed("a") and not self._previous.pressed("a"))
        )
        cancel_pressed = (
            (state.pressed(cancel_btn) and not self._previous.pressed(cancel_btn))
            or (state.pressed("b") and not self._previous.pressed("b"))
        )
        start_pressed = state.pressed("start") and not self._previous.pressed("start")

        # Suporte a clique do mouse físico e atalhos de teclado (Enter / Espaço)
        mouse_clicked = False
        try:
            if hasattr(self, "injector") and callable(getattr(self.injector, "key_pressed", None)):
                res_lbutton = self.injector.key_pressed("MOUSE_LEFT")
                if isinstance(res_lbutton, bool):
                    is_lbutton_down = res_lbutton
                    was_lbutton_down = getattr(self, "_welcome_mouse_lbutton_prev", False)
                    self._welcome_mouse_lbutton_prev = is_lbutton_down
                    if is_lbutton_down and not was_lbutton_down:
                        mouse_clicked = True

                res_enter = self.injector.key_pressed("RETURN")
                res_space = self.injector.key_pressed("SPACE")
                if isinstance(res_enter, bool) and isinstance(res_space, bool):
                    enter_down = res_enter or res_space
                    enter_prev = getattr(self, "_welcome_enter_prev", False)
                    self._welcome_enter_prev = enter_down
                    if enter_down and not enter_prev:
                        confirm_pressed = True
        except Exception:
            pass

        # Detecção de hover e clique do mouse sobre os botões da tela
        if rect.valid:
            try:
                get_pos = getattr(self.injector, "cursor_position", None)
                if callable(get_pos):
                    pos = get_pos()
                    if isinstance(pos, tuple) and len(pos) == 2 and isinstance(pos[0], (int, float)):
                        cur_x, cur_y = int(pos[0]), int(pos[1])
                        last_pos = getattr(self, "_welcome_last_cursor_pos", None)
                        mouse_moved = (last_pos is not None and (cur_x, cur_y) != last_pos)
                        self._welcome_last_cursor_pos = (cur_x, cur_y)

                        # Botão Próximo / Fechar (canto inferior direito)
                        nx, ny, nw, nh = welcome_button_rect(rect, "next")
                        if nx <= cur_x <= nx + nw and ny <= cur_y <= ny + nh:
                            if mouse_moved:
                                self._welcome_focus = "close" if is_last else "next"
                            if mouse_clicked:
                                if is_last:
                                    self._close_welcome(from_last_page=True, rect=rect, now=now)
                                    hub.rumble(0.05, 0.12, 40)
                                    return True
                                else:
                                    if self._welcome_page < total:
                                        self._welcome_page += 1
                                        if self._welcome_page >= total:
                                            self._welcome_focus = "close"
                                        else:
                                            self._welcome_focus = "next"
                                        self._safe_move_to_button(rect, self._welcome_focus)
                                        hub.rumble(0.03, 0.08, 30)
                                        mouse_clicked = False
                                        confirm_pressed = False

                        # Botão Anterior (canto inferior esquerdo, da pág 2 em diante)
                        elif not is_first:
                            px, py, pw, ph = welcome_button_rect(rect, "prev")
                            if px <= cur_x <= px + pw and py <= cur_y <= py + ph:
                                if mouse_moved:
                                    self._welcome_focus = "prev"
                                if mouse_clicked:
                                    if self._welcome_page > 1:
                                        self._welcome_page -= 1
                                        if self._welcome_page <= 1:
                                            self._welcome_focus = "next"
                                        else:
                                            self._welcome_focus = "prev"
                                        self._safe_move_to_button(rect, self._welcome_focus)
                                        hub.rumble(0.03, 0.08, 30)
                                        mouse_clicked = False
                                        confirm_pressed = False

                        # Botão X (canto superior direito, se permitido fechar)
                        if self._welcome_can_close:
                            xx, xy, xw, xh = welcome_button_rect(rect, "x")
                            if xx <= cur_x <= xx + xw and xy <= cur_y <= xy + xh:
                                if mouse_moved:
                                    self._welcome_focus = "x"
                                if mouse_clicked:
                                    self._close_welcome(from_last_page=False, rect=rect, now=now)
                                    hub.rumble(0.04, 0.08, 30)
                                    return True
            except Exception:
                pass

        # D-pad Direita: sai de Anterior -> Próximo / Fechar
        if dpad_right:
            if self._welcome_focus == "prev":
                new_focus = "close" if is_last else "next"
                self._welcome_focus = new_focus
                self._safe_move_to_button(rect, new_focus)
                hub.rumble(0.02, 0.05, 20)

        # D-pad Esquerda: sai de Próximo / Fechar -> Anterior (se não for página 1)
        elif dpad_left:
            if self._welcome_focus in ("next", "close") and not is_first:
                self._welcome_focus = "prev"
                self._safe_move_to_button(rect, "prev")
                hub.rumble(0.02, 0.05, 20)

        # D-pad Cima: sobe para o botão "X" (se reaberto e can_close == True)
        elif dpad_up:
            if self._welcome_can_close and self._welcome_focus != "x":
                self._welcome_focus = "x"
                self._safe_move_to_button(rect, "x")
                hub.rumble(0.02, 0.05, 20)

        # D-pad Baixo: desce do botão "X" de volta para os botões do rodapé
        elif dpad_down:
            if self._welcome_focus == "x":
                new_focus = "next" if is_first else ("close" if is_last else "next")
                self._welcome_focus = new_focus
                self._safe_move_to_button(rect, new_focus)
                hub.rumble(0.02, 0.05, 20)

        # Confirmar ação no botão focado
        if confirm_pressed:
            if self._welcome_focus == "next":
                if self._welcome_page < total:
                    self._welcome_page += 1
                    if self._welcome_page >= total:
                        self._welcome_focus = "close"
                    self._safe_move_to_button(rect, self._welcome_focus)
                    hub.rumble(0.03, 0.08, 30)
            elif self._welcome_focus == "prev":
                if self._welcome_page > 1:
                    self._welcome_page -= 1
                    if self._welcome_page <= 1:
                        self._welcome_focus = "next"
                    self._safe_move_to_button(rect, self._welcome_focus)
                    hub.rumble(0.03, 0.08, 30)
            elif self._welcome_focus == "close":
                self._close_welcome(from_last_page=True, rect=rect, now=now)
                hub.rumble(0.05, 0.12, 40)
                return True
            elif self._welcome_focus == "x":
                if self._welcome_can_close:
                    self._close_welcome(from_last_page=False, rect=rect, now=now)
                    hub.rumble(0.04, 0.08, 30)
                    return True

        # Cancelar / Sair via Botão Leste ou Start (apenas se can_close)
        elif (cancel_pressed or start_pressed) and self._welcome_can_close:
            self._close_welcome(from_last_page=False, rect=rect, now=now)
            hub.rumble(0.04, 0.08, 30)
            return True

        self.shared.update(
            welcome_screen_open=self._welcome_open,
            welcome_screen_page=self._welcome_page,
            welcome_screen_total_pages=self._welcome_total_pages,
            welcome_screen_focus=self._welcome_focus,
            welcome_screen_can_close=self._welcome_can_close,
        )
        return True
