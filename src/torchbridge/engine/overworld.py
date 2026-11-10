from __future__ import annotations

from ..controller import ControllerHub
from ..mathutils import radial_slot
from ..models import (
    ControllerState,
    PET_SUBMENU_COUNT,
    PET_SUBMENU_DEFAULT,
    Rect,
    click_zone,
    hud_purple_button_point,
    pet_click_point,
    pet_submenu_open,
    shortcut_node_point,
    toggle_panel,
)
from typing import Any

log = logging.getLogger(__name__) if "logging" in globals() else None


class OverworldNavigationMixin:
    """Mixin com métodos de navegação para overworld."""

    def _handle_center_buttons(
        self,
        state: ControllerState,
        rect: Rect,
        bindings: dict[str, Any],
        now: float,
    ) -> None:
        # Lê os dois botões centrais uma vez por chamada.
        back = state.pressed("back")
        start = state.pressed("start")
        both = back and start

        # Combo (Back+Start) pressionado: inicia a contagem para a calibração.
        if both:
            if not self._center_combo_seen:
                # Primeiro tick do combo: guarda quando começou.
                self._center_combo_started = now
            self._center_combo_seen = True
            # Combo mantido por 0,8 s: dispara a calibração do centro uma única vez por combo.
            if (
                not self._center_combo_triggered
                and self._center_combo_started is not None
                and now - self._center_combo_started >= 0.8
            ):
                # A âncora nova é a posição atual do cursor — aponte o herói antes.
                x, y = self.injector.cursor_position()
                # Só calibra com o cursor dentro da janela do jogo; senão, orienta o usuário.
                if rect.contains(x, y):
                    self.config.update_anchor(
                        (x - rect.left) / rect.width,
                        (y - rect.top) / rect.height,
                    )
                    self.shared.toast("Centro do personagem calibrado", 2.8)
                else:
                    self.shared.toast("Coloque o cursor sobre o personagem", 2.8)
                # Marca para não repetir enquanto o combo continuar pressionado.
                self._center_combo_triggered = True
            return

        if not self._center_combo_seen:
            # Combo inativo: borda de descida do Back → alterna o modo.
            if self._previous.pressed("back") and not back:
                # Alterna entre movimento direto e modo cursor/menus.
                self._mode = "cursor" if self._mode == "direct" else "direct"
                label = "CURSOR / MENUS" if self._mode == "cursor" else "MOVIMENTO DIRETO"
                # Informa o modo atual no overlay.
                self.shared.toast(f"Modo: {label}")
            # Borda de descida do Start (sem combo) → dispara o binding de Start (ESC por padrão).
            if self._previous.pressed("start") and not start:
                self._tap_binding(bindings.get("start", "ESC"))
                # O ESC fechou os menus do jogo: esquece os painéis que a roda acompanhava.
                self._reset_active_panels()

        # Nenhum botão central pressionado: zera o estado do combo para a próxima tentativa.
        if not back and not start:
            self._center_combo_seen = False
            self._center_combo_started = None
            self._center_combo_triggered = False

    def _handle_discrete_bindings(
        self,
        state: ControllerState,
        bindings: dict[str, Any],
    ) -> None:
        # Só opera estritamente no modo EM JOGO
        if self._memory_state.is_connected and not self._memory_state.is_in_game:
            return
        if self._shortcut_config_active:
            return
        # Roda aberta: a roda é o mundo — nenhum toque de tecla dispara enquanto ela
        # estiver de pé (o d-pad controla a sublinha de pet actions lá dentro).
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return
        # R3: borda de subida, um toque por pressionamento, sem auto-repeat.
        if state.pressed("r3") and not self._previous.pressed("r3"):
            r3_action = bindings.get("r3")
            if not r3_action or r3_action == "TAB":
                r3_action = "MOUSE_LEFT"
            self._tap_binding(r3_action)

    def _handle_trigger_combos(
        self,
        state: ControllerState,
        rect: Rect,
        bindings: dict[str, Any],
        now: float,
    ) -> None:
        # Roda aberta: o A pertence à confirmação de slot; nada de combo pode vazar.
        if state.pressed("lb") and not self._radial_dismissed:
            return
        # Sequência do pet em curso: o cursor/click é exclusivo dela — nenhum combo
        # pode vazar no meio do clique (o A do jogador pertence à confirmação).
        if self._pet_click_seq is not None:
            return
        # Clique modificado em curso: o left está com a sequência — nenhum outro
        # combo pode vazar (LT+A viraria um segundo Ctrl+clique no meio do clique).
        if self._modifier_seq is not None:
            return
        # Se o inventário ou menu de pet estiver aberto e o cursor na respectiva metade da tela,
        # L2 e R2 pertencem à troca de abas e não acionam combos.
        open_menus = self._memory_state.open_menus or []
        cur_x, _ = self.injector.cursor_position()
        mid_x = rect.left + rect.width * 0.5
        if ("Inventário" in open_menus or "Habilidades" in open_menus) and cur_x >= mid_x:
            return
        if ("Pet" in open_menus or "Baú" in open_menus or "Vendedor (Loja)" in open_menus or "Atributos" in open_menus or any(m in open_menus for m in ("Transmutador", "Sockets", "Encantador"))) and cur_x < mid_x:
            return
        lt_now = self._lt_current
        # RB: borda de subida → 9 com LT ativo (prioridade), senão 3 (sempre toque —
        # o antigo hold SHIFT morreu no remap).
        if state.pressed("rb") and not self._previous.pressed("rb"):
            self._tap_binding(bindings.get("lt_rb", "9") if lt_now else bindings.get("rb", "3"))
        # RT: borda de subida (histerese no limiar) → 0 com LT ativo, senão 4.
        if self._rt_edge_up:
            self._tap_binding(bindings.get("lt_rt", "0") if lt_now else bindings.get("rt", "4"))
        # A com LT: borda de subida → Ctrl+clique (painel aberto) ou toque 5 (fechado).
        # O A com LT segurado NUNCA segura o clique esquerdo comum: o _process_active
        # desliga o left_pressed enquanto LT está ativo (o combo tem prioridade).
        if state.pressed("a") and not self._previous.pressed("a") and lt_now:
            stable = self._previous_panels
            if bool(stable[0]) or bool(stable[1]):
                # Ctrl+clique: arma a sequência — o left up (120 ms) e o Ctrl up
                # (180 ms) saem nos ticks seguintes via _handle_modifier_release;
                # os ticks em curso ficam sob o gate do _process_active.
                self._start_modifier_click("CTRL", now)
            else:
                self._tap_binding(bindings.get("lt_a", "5"))
        # X com LT: borda de subida → 6 (o X com LT nunca segura o clique direito comum).
        if state.pressed("x") and not self._previous.pressed("x") and lt_now:
            self._tap_binding(bindings.get("lt_x", "6"))
        # Y com LT: borda de subida → 7 SEMPRE (o remap contextual de Y=Shift+clique
        # confere o LT antes — o LT+ tem prioridade sobre o remap, igual ao LT+B=8).
        if state.pressed("y") and not self._previous.pressed("y") and lt_now:
            self._tap_binding(bindings.get("lt_y", "7"))
        # B com LT: borda de subida → 8 SEMPRE (o LT+ tem prioridade sobre o remap
        # contextual de B=ESC — o _handle_overworld_remap confere o LT antes).
        if state.pressed("b") and not self._previous.pressed("b") and lt_now:
            self._tap_binding(bindings.get("lt_b", "8"))

    def _handle_overworld_remap(
        self,
        state: ControllerState,
        rect: Rect,
        bindings: dict[str, Any],
        now: float,
    ) -> None:
        # Roda aberta: a roda é o mundo — B/Y suprimidos (regra clássica).
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return
        # Sequência do pet em curso: o cursor/click é exclusivo dela — o Shift+clique
        # do Y não pode mexer no cursor no meio do clique do pet, nem a ESC do B
        # pode fechar os menus no meio da sequência.
        if self._pet_click_seq is not None or self._hud_click_seq is not None:
            return
        # Clique modificado em curso: o left está com a sequência — o Y não arma um
        # segundo Shift+clique no meio do clique em andamento.
        if self._modifier_seq is not None:
            return
        lt_now = self._lt_current
        stable = self._previous_panels
        panels_open = bool(stable[0]) or bool(stable[1])
        # B: LT+B (8) já foi consumido pelos combos — não reprocessar aqui (senão
        # sairia ESC E 8 no mesmo tick). Sem LT: com painel aberto no tick anterior,
        # B = ESC + reset; senão B toca o 2.
        if state.pressed("b") and not self._previous.pressed("b") and not lt_now:
            if getattr(self, "_quest_b_consumed", False):
                self._quest_b_consumed = False
            elif panels_open:
                # ESC direto no injetor (não _tap_binding): o jogo fechou os menus,
                # o rastreador acompanha. O clique esquerdo retido do click-to-move
                # segue intacto — a parte de cursor roda depois no mesmo tick.
                self.injector.tap("ESC")
                self._reset_active_panels()
            else:
                self._tap_binding(bindings.get("b"))
        # Y: LT+Y (7) já foi consumido pelos combos. Sem LT: com painel aberto no tick
        # anterior, Y = Shift + clique esquerdo; senão Y toca o 1.
        if state.pressed("y") and not self._previous.pressed("y") and not lt_now:
            if panels_open:
                # Shift+clique: arma a sequência — o left up (120 ms) e o Shift up
                # (180 ms, garantido pelo estado físico) saem nos ticks seguintes via
                # _handle_modifier_release; os ticks em curso ficam sob o gate do
                # _process_active. O Shift fica FÍSICAMENTE pressionado nos frames do
                # clique: o jogo amostra a tecla por frame (a forma antiga, down/up no
                # mesmo tick, saía como clique simples — bug real, ago/2026).
                self._start_modifier_click("SHIFT", now)
                # O jogo abre o OUTRO painel quando o Y é pressionado no lado da
                # tela com o painel ABERTO (comportamento do doc, OBS): o rastreador
                # acompanha de forma otimista. Clique no lado do ABERTO com o outro
                # fechado → abre o outro; clique na aba de fechar → fecha só aquele.
                x, y = self.injector.cursor_position()
                zone = click_zone(rect, x, y, self._hud_mask)
                left, right = self._active_panels
                if zone == "left" and left and not right:
                    self._active_panels[1] = "I"
                elif zone == "right" and right and not left:
                    self._active_panels[0] = "P"
                elif zone == "close_left" and left:
                    self._active_panels[0] = ""
                elif zone == "close_right" and right:
                    self._active_panels[1] = ""
                if [left, right] != self._active_panels:
                    self.shared.update(active_panels=list(self._active_panels))
            else:
                self._tap_binding(bindings.get("y"))

    def _handle_overworld_dpad(
        self,
        state: ControllerState,
        rect: Rect,
        hub: ControllerHub,
        bindings: dict[str, Any],
        now: float,
    ) -> None:
        """Navegação e ações por D-pad no overworld quando ESTADO = EM JOGO e MENUS = NENHUM.

        - D-pad para a esquerda:
          -> mover o cursor para o ponto ROXO (#8A38F5) da imagem da HUD
          -> clicar no ponto ROXO (#8A38F5)
          -> voltar ao local que estava antes de sair
        - D-pad para a direita:
          -> realizar a ação do TAB quando clicado
        """
        # Só opera estritamente quando em jogo e nenhum menu estiver aberto
        if not self._memory_state.is_connected or not self._memory_state.is_in_game:
            return
        if self._memory_state.open_menus or self._memory_state.dialog_type:
            return

        # Roda de habilidades aberta (LB segurado): o D-pad é da sublinha do pet
        if state.pressed("lb") and self._is_radial_allowed() and not self._radial_dismissed:
            return

        # Sequências em andamento: não aceita nova ação enquanto já houver clique em curso
        if self._pet_click_seq is not None or self._hud_click_seq is not None or self._modifier_seq is not None:
            return

        dpad_left = state.pressed("dpad_left") and not self._previous.pressed("dpad_left")
        dpad_right = state.pressed("dpad_right") and not self._previous.pressed("dpad_right")

        if dpad_left:
            # Libera cliques retidos anteriores e cancela direct move ativo
            if "left" in self._held_mouse:
                self.injector.mouse_button("left", False)
                self._held_mouse.discard("left")
            if "right" in self._held_mouse:
                self.injector.mouse_button("right", False)
                self._held_mouse.discard("right")
            self._direct_move_active = False
            self._previous_left_pressed = False

            cur_x, cur_y = self.injector.cursor_position()
            if not rect.contains(cur_x, cur_y):
                if self._last_anchor:
                    cur_x, cur_y = self._last_anchor
                else:
                    movement = self.config.get()["movement"]
                    cur_x = int(round(rect.left + rect.width * float(movement["anchor_x"])))
                    cur_y = int(round(rect.top + rect.height * float(movement["anchor_y"])))

            target_x, target_y = hud_purple_button_point(rect)
            self._hud_click_seq = (
                target_x,
                target_y,
                cur_x,
                cur_y,
                now,
            )
            self._hud_click_down = False
            self._hud_click_up = False
            self._hud_click_returned = False
            self.injector.move(target_x, target_y)
            hub.rumble(0.04, 0.10, 35)

        elif dpad_right:
            tab_action = bindings.get("dpad_right") or "TAB"
            self._tap_binding(tab_action)
            hub.rumble(0.03, 0.08, 30)

    def _handle_pet_click(self, now: float) -> None:
        seq = self._pet_click_seq
        if seq is None:
            return
        target_x, target_y, return_x, return_y, pending_panel, t0 = seq
        t = now - t0
        if t < 0:
            return
        # Com painel aberto: a letra sai na hora (animação de fechamento começa) e
        # o cursor só vai até o botão depois dos 500 ms de espera.
        panel_wait = self.PET_PANEL_CLOSE_DELAY if pending_panel else 0.0
        if not self._pet_click_panel_done:
            # Letra do painel esquerdo pendente: fecha o painel no jogo (a tecla
            # repetida é o toggle) — ANTES do clique quando o painel está aberto.
            if pending_panel:
                self._tap_binding(pending_panel)
            self._pet_click_panel_done = True
            return
        if t < panel_wait:
            # Esperando a animação de fechamento do painel — o botão do pet só é
            # clicável com o painel já fora da tela.
            return
        if t < panel_wait + 0.12:
            # Fase de ida: mantém o cursor no botão (defensivo — o move já aconteceu
            # na fase anterior; reenviar o mesmo ponto absoluto é idempotente).
            self.injector.move(target_x, target_y)
            return
        if t < panel_wait + 0.21:
            # Descida: aperta o botão esquerdo exatamente uma vez na borda.
            if self._pet_click_down:
                return
            if self.injector.mouse_button("left", True):
                self._pet_click_down = True
            return
        if t < panel_wait + 0.24:
            # Solta na hora que chega (e logo em seguida, se o tick atrasou):
            # nunca segura o clique além do tempo de um clique físico.
            if self._pet_click_down:
                self.injector.mouse_button("left", False)
                self._pet_click_down = False
            return
        # Fim (ou tick que puxou fases por atraso): garante solta, garante a letra
        # do painel (nunca perde) e devolve o cursor ao centro — fim da sequência.
        if not self._pet_click_panel_done and pending_panel:
            self._tap_binding(pending_panel)
            self._pet_click_panel_done = True
        if self._pet_click_down:
            self.injector.mouse_button("left", False)
            self._pet_click_down = False
        self._pet_click_seq = None
        self.injector.move(return_x, return_y)

    def _handle_hud_purple_click(self, now: float) -> None:
        seq = self._hud_click_seq
        if seq is None:
            return
        target_x, target_y, return_x, return_y, t0 = seq
        t = now - t0
        if t < 0:
            return
        # Fase 1: Hover no alvo
        if t < 0.05:
            self.injector.move(target_x, target_y)
            return
        # Fase 2: Pressiona o botão esquerdo exatamente uma vez
        if t < 0.11:
            if not self._hud_click_down:
                if self.injector.mouse_button("left", True):
                    self._hud_click_down = True
            return
        # Fase 3: Solta o botão esquerdo e MANTÉM o cursor sobre o alvo (delay de ~50 ms)
        # O jogo/Windows processa o UP no botão antes de o cursor se mover
        if t < 0.16:
            if self._hud_click_down and not self._hud_click_up:
                self.injector.mouse_button("left", False)
                self._hud_click_up = True
            return
        # Fase 4: Retorno do cursor à posição original (mouse permanece estritamente solto)
        if t < 0.20:
            if not self._hud_click_returned:
                self.injector.move(return_x, return_y)
                self._hud_click_returned = True
            return
        # Fase 5: Conclusão da sequência
        if self._hud_click_down and not self._hud_click_up:
            self.injector.mouse_button("left", False)
            self._hud_click_up = True
        if not self._hud_click_returned:
            self.injector.move(return_x, return_y)
            self._hud_click_returned = True
        self._hud_click_seq = None
        self._hud_click_down = False
        self._hud_click_up = False
        self._hud_click_returned = False
        self._direct_move_active = False

    def _is_radial_allowed(self) -> bool:
        """Determina se a roda de habilidades pode ser aberta.
        Regra: somente permitida quando em gameplay (is_in_game) e sem menus modais/diálogos/configurações abertos.
        Permitida quando nenhum menu está aberto, ou quando os menus de painel (Inventário, Pet, Atributos, Habilidades)
        estão abertos."""
        if not self._memory_state.is_connected:
            return True
        if not self._memory_state.is_in_game:
            return False
        menus = self._memory_state.open_menus or []
        # Permitido sem menus abertos, ou quando painéis comuns de gameplay (Inventário, Pet, Atributos, Habilidades, Missões (Quests)) estão abertos
        allowed_panels = {"Inventário", "Pet", "Atributos", "Habilidades", "Missões (Quests)", "Diário (Journal)"}
        other_menus = [m for m in menus if m not in allowed_panels]
        if other_menus:
            return False
        desc = (self._memory_state.state_desc or "").lower()
        if "confirma" in desc or "setting" in desc or "configura" in desc:
            return False
        return True

    def _handle_radial(
        self,
        hub: ControllerHub,
        state: ControllerState,
        bindings: dict[str, Any],
        rect: Rect,
        now: float,
    ) -> None:
        active = state.pressed("lb") and self._is_radial_allowed()
        slots = bindings.get("radial_slots", [])
        # Borda de subida do LB: rearma a roda — novo aperto começa do zero (nada selecionado).
        if not self._previous.pressed("lb") and active:
            self._radial_dismissed = False
            self._radial_selection = None
            self._radial_cancel_lock = None
            self._pet_submenu = False
            self._pet_submenu_selection = PET_SUBMENU_DEFAULT

        # LB liberado (borda de descida): CONFIRMA a seleção feita enquanto a roda esteve aberta
        if self._previous.pressed("lb") and not active:
            if (
                self._radial_selection is not None
                and self._radial_selection <= len(slots)
            ):
                if not self._pet_submenu:
                    slot = slots[self._radial_selection - 1]
                    if str(slot).lower() in ("short-cut", "shortcut"):
                        has_open_menu = bool(
                            self._memory_state.is_menu_open
                            or any(self._active_panels)
                            or getattr(self, "_skill_menu_open", False)
                            or getattr(self, "_quest_menu_initialized", False)
                            or getattr(self, "_dialog_initialized", False)
                        )
                        if has_open_menu:
                            self.injector.tap("ESC")
                            self._reset_active_panels()
                            if getattr(self, "_skill_menu_open", False):
                                self._skill_menu_open = False
                                self._skill_in_spells = False
                                self._skill_spell_idx = 0
                            if getattr(self, "_quest_menu_initialized", False):
                                self._quest_menu_initialized = False
                                self._quest_b_consumed = False
                            if getattr(self, "_dialog_initialized", False):
                                self._dialog_initialized = False
                                self._dialog_focus = None

                        self._shortcut_config_active = True
                        self._shortcut_node_focus = 0
                        self._shortcut_info_focus = False
                        self.shared.update(
                            shortcut_config_active=True,
                            shortcut_node_focus=0,
                            shortcut_info_focus=False,
                            active_panels=list(self._active_panels),
                        )
                        self._release_all()
                        target_x, target_y = shortcut_node_point(rect, 0)
                        self.injector.move(target_x, target_y)
                    else:
                        self._tap_binding(slot)
                        next_panels = toggle_panel(self._active_panels, slot)
                        if next_panels != self._active_panels:
                            self._active_panels = next_panels
                            self.shared.update(active_panels=list(next_panels))
                else:
                    target = pet_click_point(rect, self._pet_submenu_selection)
                    if self._last_anchor:
                        return_x, return_y = self._last_anchor
                    else:
                        movement = self.config.get()["movement"]
                        return_x = rect.left + rect.width * float(movement["anchor_x"])
                        return_y = rect.top + rect.height * float(movement["anchor_y"])
                    pending_panel = self._active_panels[0] or None
                    self._pet_click_seq = (
                        int(round(target[0])),
                        int(round(target[1])),
                        int(round(return_x)),
                        int(round(return_y)),
                        pending_panel,
                        now,
                    )
                    self._pet_click_down = False
                    self._pet_click_panel_done = pending_panel is None
                    if pending_panel:
                        self._active_panels[0] = ""
                        self.shared.update(active_panels=list(self._active_panels))
                hub.rumble(0.06, 0.12, 50)

            self._pet_submenu = False
            self._pet_submenu_selection = PET_SUBMENU_DEFAULT
            self._radial_selection = None
            self._radial_cancel_lock = None
            self._radial_dismissed = False

        # Roda de pé: LB segurado E sem latch de confirmação/dismissal.
        open = active and not self._radial_dismissed

        # Leitura do analógico direito para o setor (1..N) com inclinação mínima.
        raw_selection = radial_slot(state.rx, state.ry, len(slots)) if open else None

        # Se o analógico retornou ao centro (deadzone), libera a trava de cancelamento
        if raw_selection is None:
            self._radial_cancel_lock = None

        # Setor mudou (roda de pé): atualiza a seleção persistida e vibra para retorno tátil
        if (
            open
            and raw_selection is not None
            and raw_selection != self._radial_cancel_lock
            and raw_selection != self._radial_selection
        ):
            self._radial_selection = raw_selection
            self._radial_cancel_lock = None
            hub.rumble(0.04, 0.10, 35)

        # A sublinha acompanha a seleção PERSISTIDA (self._radial_selection), não a
        # seleção instantânea do analógico.
        current = self._radial_selection if open else None

        # Sublinha de pet actions (4 quadradinhos sob o slot 'P'): d-pad PARA BAIXO abre,
        # para CIMA fecha — enquanto a roda está aberta e o setor do pet é o selecionado.
        if current is not None:
            current_slot = slots[current - 1] if 1 <= current <= len(slots) else ""
            if pet_submenu_open(open, current, current_slot, True):
                if state.pressed("dpad_down") and not self._previous.pressed("dpad_down"):
                    if not self._pet_submenu:
                        self._pet_submenu = True
                        self._pet_submenu_selection = PET_SUBMENU_DEFAULT
                        hub.rumble(0.04, 0.10, 35)
                elif state.pressed("dpad_up") and not self._previous.pressed("dpad_up"):
                    if self._pet_submenu:
                        self._pet_submenu = False
                        hub.rumble(0.04, 0.10, 35)
                elif self._pet_submenu:
                    if state.pressed("dpad_right") and not self._previous.pressed("dpad_right"):
                        self._pet_submenu_selection = (self._pet_submenu_selection % PET_SUBMENU_COUNT) + 1
                        hub.rumble(0.03, 0.08, 30)
                    elif state.pressed("dpad_left") and not self._previous.pressed("dpad_left"):
                        self._pet_submenu_selection = ((self._pet_submenu_selection - 2) % PET_SUBMENU_COUNT) + 1
                        hub.rumble(0.03, 0.08, 30)
            elif self._pet_submenu:
                self._pet_submenu = False
        else:
            self._pet_submenu = False

        # Botão Leste (B / Bolinha no PS): cancela a seleção do analógico e fecha o submenu do pet
        # caso estejam ativos, retornando o menu radial para o estado inicial (aberto, mas nada selecionado).
        if open and state.pressed("b") and not self._previous.pressed("b"):
            if self._radial_selection is not None or self._pet_submenu:
                self._radial_selection = None
                self._pet_submenu = False
                self._pet_submenu_selection = PET_SUBMENU_DEFAULT
                self._radial_cancel_lock = raw_selection
                hub.rumble(0.04, 0.08, 30)

        # TB-17: Botão Norte (Y no Xbox, Triângulo no PS, X no Nintendo) enquanto segura o menu radial
        # dispara a mensagem de boas-vindas novamente com opção de fechar (can_close=True).
        north_pressed = state.pressed("y") and not self._previous.pressed("y")
        if open and north_pressed:
            self._radial_dismissed = True
            self._radial_selection = None
            self._radial_cancel_lock = None
            self._pet_submenu = False
            self.shared.update(radial_active=False, radial_selection=None, pet_submenu_open=False)
            if hasattr(self, "_open_welcome"):
                self._open_welcome(can_close=True, rect=rect)
            hub.rumble(0.04, 0.10, 35)
            return

        self.shared.update(
            radial_active=open,
            radial_selection=self._radial_selection if open else None,
            pet_submenu_open=pet_submenu_open(
                open,
                self._radial_selection if open else None,
                slots[self._radial_selection - 1]
                if self._radial_selection is not None and 1 <= self._radial_selection <= len(slots)
                else "",
                self._pet_submenu,
            ),
            pet_submenu_selection=(
                self._pet_submenu_selection
                if pet_submenu_open(
                    open,
                    self._radial_selection if open else None,
                    slots[self._radial_selection - 1]
                    if self._radial_selection is not None and 1 <= self._radial_selection <= len(slots)
                    else "",
                    self._pet_submenu,
                )
                else None
            ),
        )
