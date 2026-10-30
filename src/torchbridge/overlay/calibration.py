from __future__ import annotations

from ..models import (
    BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION,
    CHAR_MENU_NODES_HAS_POINTS,
    CHAR_MENU_NODES_NO_POINTS,
    CRAFTING_BUTTONS,
    CRAFTING_SLOTS,
    CREATE_CHAR_BUTTONS,
    DEATH_SCREEN_BUTTONS,
    DIFFICULTY_BUTTONS,
    INVENTORY_GRID_COLS,
    INVENTORY_GRID_ROWS,
    INVENTORY_UPPER_COORDS,
    MERCHANT_GRID_COLS,
    MERCHANT_GRID_ROWS,
    OverlaySnapshot,
    PAUSE_BUTTONS,
    PET_GRID_COLS,
    PET_GRID_ROWS,
    PET_UPPER_COORDS,
    QUEST_ROW_COUNT,
    SETTINGS_BUTTONS,
    SETTINGS_DROPDOWNS,
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    STASH_GRID_COLS,
    STASH_GRID_ROWS,
    TITLE_BUTTONS,
    bottom_hud_target_rect,
    char_create_button_point,
    close_tab_vertices,
    crafting_button_point,
    crafting_slot_point,
    death_screen_button_point,
    dialog_button_point,
    difficulty_menu_button_point,
    fishing_hook_point,
    hud_asset_path,
    hud_purple_button_point,
    hud_target_rect,
    inventory_slot_point,
    inventory_tab_point,
    inventory_upper_point,
    load_char_button_point,
    merchant_slot_point,
    merchant_tab_point,
    modal_ok_point,
    panel_regions,
    pause_menu_button_point,
    pet_actions_target_rect,
    pet_click_point,
    pet_inventory_slot_point,
    pet_inventory_tab_point,
    pet_inventory_upper_point,
    quest_abandon_point,
    quest_reward_point,
    quest_slot_point,
    settings_button_point,
    settings_dropdown_option_point,
    settings_slider_bounds,
    skill_bridge_col,
    skill_slot_pink_point,
    skill_slot_point,
    skill_spell_slot_point,
    skill_tab_point,
    stash_upper_slot_point,
    title_menu_button_point,
)
from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtSvg import QSvgRenderer

log = logging.getLogger(__name__) if "logging" in globals() else None


class CalibrationOverlayMixin:
    """Mixin com métodos de desenho e animação para calibration."""

    def _load_hud_pixmap(self) -> QPixmap | None:
        path = hud_asset_path()
        if path is None or not path.exists():
            return None
        try:
            renderer = QSvgRenderer()
            if not renderer.load(str(path)):
                return None
            size = renderer.defaultSize()
            pixmap = QPixmap(int(size.width()), int(size.height()))
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap
        except Exception:  # noqa: BLE001 - sem Qt Svg o modo calibração segue sem a HUD.
            return None

    def _draw_calibration(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        cfg = self.config.get()
        # Só visível com a flag ligada e o retângulo do jogo válido.
        if not cfg["overlay"].get("show_calibration", False):
            return
        rect = snapshot.game_rect
        if not rect.valid:
            return
        # Janela do overlay = área do jogo: converte coordenadas absolutas para locais.
        def local(box: tuple[int, int, int, int]) -> QRectF:
            x, y, w, h = box
            return QRectF(x - rect.left, y - rect.top, w, h)

        # Vértices da aba em coordenadas locais do overlay (QPolygonF, pra drawPolygon).
        def local_polygon(side: str) -> QPolygonF:
            return QPolygonF([
                QPointF(x - rect.left, y - rect.top)
                for x, y in close_tab_vertices(rect, side)
            ])

        state_desc = snapshot.memory_state_desc

        # Telas que NÃO devem exibir HUD inferior nem Pet Actions:
        # - Configurações (Settings)
        # - Telas de Carregamento (Loading)
        # - Diálogos e Missões (NPCs, Quests, História)
        is_settings = (
            "Configurações" in (snapshot.memory_open_menus or [])
            or any("configura" in m.lower() or "setting" in m.lower() for m in (snapshot.memory_open_menus or []))
            or (bool(state_desc) and ("configura" in state_desc.lower() or "setting" in state_desc.lower()))
        )
        is_loading = (
            snapshot.memory_is_loading
            or (bool(state_desc) and "carregando" in state_desc.lower())
        )
        is_dialog = (
            bool(snapshot.dialog_type)
            or any(
                "missão" in m.lower()
                or "missao" in m.lower()
                or "diálogo" in m.lower()
                or "dialogo" in m.lower()
                or "história" in m.lower()
                or "historia" in m.lower()
                for m in (snapshot.memory_open_menus or [])
            )
        )
        is_death_screen = (
            snapshot.death_screen_focus is not None
            or any(
                "morte" in m.lower()
                or "respawn" in m.lower()
                for m in (snapshot.memory_open_menus or [])
            )
        )

        is_in_game = (snapshot.memory_is_in_game or not state_desc) and not is_settings and not is_loading

        if is_in_game:
            regions = panel_regions(rect)
            left_open = bool(snapshot.active_panels and len(snapshot.active_panels) > 0 and snapshot.active_panels[0])
            right_open = bool(snapshot.active_panels and len(snapshot.active_panels) > 1 and snapshot.active_panels[1])
            both_open = left_open and right_open

            # 1. Painel Esquerdo e Aba de Fechar Esquerda (só visível com menu esquerdo aberto e fora de diálogos)
            if not is_dialog and left_open:
                painter.setPen(QPen(QColor(111, 210, 235, 170), 1.5 * scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(local(regions["panel_left"]))

                # As telas de Crafting (Transmutador, Sockets, Encantador) são placas suspensas sem aba lateral
                left_panel = snapshot.active_panels[0] if (snapshot.active_panels and len(snapshot.active_panels) > 0) else ""
                if left_panel not in ("T", "K", "E"):
                    painter.setPen(QPen(QColor(255, 159, 67, 235), 2.5 * scale))
                    painter.setBrush(QColor(255, 159, 67, 55))
                    close_left_poly = local_polygon("left")
                    painter.drawPolygon(close_left_poly)

                    painter.setFont(self._font(max(7, round(9 * scale)), True))
                    painter.setPen(QColor(255, 159, 67, 245))
                    painter.drawText(close_left_poly.boundingRect().adjusted(0, -26 * scale, 0, -6 * scale), Qt.AlignmentFlag.AlignCenter, "FECHA ESQ")

                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(111, 210, 235, 200))
                painter.drawText(local(regions["panel_left"]).adjusted(0, 6 * scale, 0, 24 * scale), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "PAINEL")

            # 2. Painel Direito e Aba de Fechar Direita (só visível com menu direito aberto e fora de diálogos)
            if not is_dialog and right_open:
                painter.setPen(QPen(QColor(111, 210, 235, 170), 1.5 * scale))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(local(regions["panel_right"]))

                painter.setPen(QPen(QColor(255, 159, 67, 235), 2.5 * scale))
                painter.setBrush(QColor(255, 159, 67, 55))
                close_right_poly = local_polygon("right")
                painter.drawPolygon(close_right_poly)

                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(255, 159, 67, 245))
                painter.drawText(close_right_poly.boundingRect().adjusted(0, -26 * scale, 0, -6 * scale), Qt.AlignmentFlag.AlignCenter, "FECHA DIR")
                painter.setPen(QColor(111, 210, 235, 200))
                painter.drawText(local(regions["panel_right"]).adjusted(0, 6 * scale, 0, 24 * scale), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "PAINEL")

            # 3. Zona Central: tracejado (clique nela fecha ambos somente quando os dois estiverem abertos e fora de diálogos)
            if not is_dialog and both_open:
                painter.setPen(
                    QPen(QColor(120, 220, 150, 170), 1.2 * scale, Qt.PenStyle.DashLine)
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(local(regions["center"]))

                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(120, 220, 150, 200))
                painter.drawText(local(regions["center"]).adjusted(0, 6 * scale, 0, 24 * scale), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "CENTRO (ZERA TUDO)")

            # 4. HUD inferior (elemento fixo da interface in-game, oculto em diálogos/missões e tela de morte)
            if not is_dialog and not is_death_screen and self._hud_pixmap is not None:
                hl, ht, hw, hh = hud_target_rect(rect)
                target = QRectF(hl - rect.left, ht - rect.top, hw, hh)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setPen(QPen(QColor(60, 235, 90, 120), 1.0 * scale))
                painter.setBrush(QColor(60, 235, 90, 38))
                painter.drawPixmap(
                    int(target.x()), int(target.y()), int(target.width()), int(target.height()),
                    self._hud_pixmap,
                )
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

                hud_local = QRectF(hl - rect.left, ht - rect.top, hw, hh)
                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(120, 235, 90, 235))
                label_box = QRectF(
                    hud_local.left(), hud_local.top() - 24 * scale,
                    hud_local.width(), 20 * scale,
                )
                painter.drawText(
                    label_box,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    "HUD (NÃO FECHA)",
                )

                # Marcador do ponto roxo (#8A38F5 / D-pad esquerdo)
                px, py = hud_purple_button_point(rect)
                p_local = QPointF(px - rect.left, py - rect.top)
                painter.setPen(QPen(QColor(138, 56, 245, 230), 1.5 * scale))
                painter.setBrush(QColor(138, 56, 245, 80))
                painter.drawEllipse(p_local, 7.0 * scale, 7.0 * scale)
                painter.setFont(self._font(max(6, round(7.5 * scale)), True))
                painter.setPen(QColor(210, 160, 255, 240))
                painter.drawText(
                    QRectF(p_local.x() - 40 * scale, p_local.y() - 18 * scale, 80 * scale, 14 * scale),
                    Qt.AlignmentFlag.AlignCenter,
                    "D-PAD ESQ",
                )

            # 4b. HUD inferior dos controles (calibração visual da área)
            if not is_dialog and not is_death_screen:
                overlay_cfg = cfg.get("overlay", {})
                offset_y = float(overlay_cfg.get("bottom_hud_offset_y_percent", BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION))
                scale_hud = float(overlay_cfg.get("bottom_hud_scale", 1.0))
                bhl, bht, bhw, bhh = bottom_hud_target_rect(rect, offset_y, scale_hud)
                bh_target = QRectF(bhl - rect.left, bht - rect.top, bhw, bhh)
                painter.setPen(QPen(QColor(69, 211, 239, 160), 1.5 * scale, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(69, 211, 239, 25))
                painter.drawRect(bh_target)
                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(69, 211, 239, 240))
                pct = int(round(offset_y * 100))
                painter.drawText(
                    QRectF(bh_target.left(), bh_target.top() - 18 * scale, bh_target.width(), 16 * scale),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    f"HUD CONTROLE (INFERIOR -{pct}%)",
                )

            # 5. Pet actions: visível somente quando o painel esquerdo NÃO estiver cobrindo a HUD do pet e fora de diálogos/missões
            if not is_dialog and not left_open and self._pet_actions_pixmap is not None:
                pl, pt, pw, ph = pet_actions_target_rect(rect)
                pet_local = QRectF(pl - rect.left, pt - rect.top, pw, ph)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setPen(QPen(QColor(196, 120, 255, 130), 1.0 * scale))
                painter.setBrush(QColor(196, 120, 255, 34))
                painter.drawPixmap(
                    int(pet_local.x()), int(pet_local.y()), int(pet_local.width()), int(pet_local.height()),
                    self._pet_actions_pixmap,
                )
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

                radius = 7.0 * scale
                pens = (
                    QPen(QColor(255, 255, 255, 255), 4.5 * scale),
                    QPen(QColor(255, 80, 80, 255), 2.0 * scale),
                )
                for index in range(1, 5):
                    px, py = pet_click_point(rect, index)
                    lx = px - rect.left
                    ly = py - rect.top
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    for pen in pens:
                        painter.setPen(pen)
                        painter.drawEllipse(QPointF(lx, ly), radius, radius)
                        painter.drawLine(QPointF(lx - radius - 3 * scale, ly), QPointF(lx + radius + 3 * scale, ly))
                        painter.drawLine(QPointF(lx, ly - radius - 3 * scale), QPointF(lx, ly + radius + 3 * scale))

                painter.setFont(self._font(max(7, round(9 * scale)), True))
                painter.setPen(QColor(216, 156, 255, 235))
                label_box = QRectF(
                    pet_local.right() + 6 * scale,
                    pet_local.top(),
                    120 * scale, pet_local.height(),
                )
                painter.drawText(
                    label_box,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    "PET ACTIONS",
                )

            # 6. Alvos de Diálogo (Missões, Diálogo Simples, História) em modo calibração
            if snapshot.dialog_type and snapshot.dialog_buttons:
                btn_w = 124 * scale * (rect.height / 768.0)
                btn_h = 24 * scale * (rect.height / 768.0)
                for btn_name in snapshot.dialog_buttons:
                    bx, by = dialog_button_point(rect, btn_name)
                    lx = bx - rect.left - btn_w / 2
                    ly = by - rect.top - btn_h / 2
                    is_focus = (snapshot.dialog_focus == btn_name.lower())
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 110))
                    else:
                        painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                        painter.setBrush(QColor(46, 204, 113, 75))
                    painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)
                    painter.setFont(self._font(max(7, round(8 * scale)), True))
                    painter.setPen(QColor(255, 255, 255, 240))
                    label = btn_name.upper()
                    if label == "ACCEPT":
                        label = "ACEITAR"
                    elif label == "DECLINE":
                        label = "RECUSAR"
                    elif label in ("SKIP", "CONTINUE"):
                        label = "CONTINUAR"
                    painter.drawText(QRectF(lx, ly, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, label)

                # Slot de Recompensa de Item da Missão (se houver)
                if snapshot.dialog_has_reward:
                    rx, ry = dialog_button_point(rect, "reward_slot")
                    slot_size = 40 * scale * (rect.height / 768.0)
                    rlx = rx - rect.left - slot_size / 2
                    rly = ry - rect.top - slot_size / 2
                    is_reward_focus = (snapshot.dialog_focus == "reward_slot")
                    if is_reward_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 110))
                    else:
                        painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                        painter.setBrush(QColor(46, 204, 113, 75))
                    painter.drawRoundedRect(QRectF(rlx, rly, slot_size, slot_size), 4 * scale, 4 * scale)
                    painter.setFont(self._font(max(6, round(7 * scale)), True))
                    painter.setPen(QColor(255, 255, 255, 240))
                    painter.drawText(QRectF(rlx, rly, slot_size, slot_size), Qt.AlignmentFlag.AlignCenter, "ITEM")

            # 7. Alvos de Crafting (Transmutador, Sockets, Encantador) com foco ativo
            crafting_menu = next((m for m in ("Transmutador", "Sockets", "Encantador") if m in (snapshot.memory_open_menus or [])), None)
            if crafting_menu or snapshot.crafting_open:
                active_menu = snapshot.crafting_menu or crafting_menu or "Transmutador"
                # Desenha slots de itens
                slots = CRAFTING_SLOTS.get(active_menu, [])
                if active_menu == "Transmutador":
                    slot_w = 48 * scale * (rect.height / 768.0)
                    slot_h = 68 * scale * (rect.height / 768.0)
                else:
                    slot_w = 96 * scale * (rect.height / 768.0)
                    slot_h = 96 * scale * (rect.height / 768.0)

                for s_idx in range(len(slots)):
                    sx, sy = crafting_slot_point(rect, active_menu, s_idx)
                    lx = sx - rect.left - slot_w / 2
                    ly = sy - rect.top - slot_h / 2
                    is_focus = (snapshot.crafting_focus == f"slot_{s_idx}")
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 160))
                    else:
                        painter.setPen(QPen(QColor(111, 210, 235, 230), 1.5 * scale))
                        painter.setBrush(QColor(111, 210, 235, 50))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_w, slot_h), 4 * scale, 4 * scale)
                    painter.setFont(self._font(max(7, round(8 * scale)), True))
                    painter.setPen(QColor(255, 255, 255, 240))
                    slot_label = f"SLOT {s_idx + 1}" if len(slots) > 1 else "ITEM"
                    painter.drawText(QRectF(lx, ly, slot_w, slot_h), Qt.AlignmentFlag.AlignCenter, slot_label)

                # Desenha botões de ação (Decline, Transmute / Recover / Enchant)
                buttons = CRAFTING_BUTTONS.get(active_menu, {})
                btn_w = 128 * scale * (rect.height / 768.0)
                btn_h = 24 * scale * (rect.height / 768.0)
                for b_name in buttons:
                    if b_name in ("accept", "action"):
                        continue  # accept / action é a mesma posição do botão principal
                    bx, by = crafting_button_point(rect, active_menu, b_name)
                    lx = bx - rect.left - btn_w / 2
                    ly = by - rect.top - btn_h / 2
                    is_focus = (
                        snapshot.crafting_focus == b_name
                        or (snapshot.crafting_focus == "action" and b_name in ("transmute", "recover", "enchant"))
                    )
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 160))
                    else:
                        painter.setPen(QPen(QColor(255, 159, 67, 230), 1.5 * scale))
                        painter.setBrush(QColor(255, 159, 67, 75))
                    painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)
                    painter.setFont(self._font(max(7, round(8 * scale)), True))
                    painter.setPen(QColor(255, 255, 255, 240))
                    label_map = {
                        "decline": "FECHAR",
                        "transmute": "TRANSMUTAR",
                        "recover": "RECUPERAR",
                        "enchant": "ENCANTAR",
                    }
                    painter.drawText(QRectF(lx, ly, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, label_map.get(b_name, b_name.upper()))

            # 8. Alvos do Menu de Pause (COptionsMenu / Options) em modo calibração
            # Segue o padrão de assets/images/menus/in-game paused.png:
            # Amarelo para o foco ativo (default: return_to_game) e verde para as possibilidades.
            is_paused = (
                "Pause" in (snapshot.memory_open_menus or [])
                or any(m.lower() in ("pause", "paused") for m in (snapshot.memory_open_menus or []))
            )
            if is_paused:
                box_size = 17.0 * scale * (rect.height / 768.0)
                for btn_name in PAUSE_BUTTONS:
                    bx, by = pause_menu_button_point(rect, btn_name)
                    lx = bx - rect.left - box_size / 2.0
                    ly = by - rect.top - box_size / 2.0
                    is_focus = (snapshot.pause_menu_focus == btn_name)
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 160))
                    else:
                        painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                        painter.setBrush(QColor(46, 204, 113, 90))
                    painter.drawRoundedRect(QRectF(lx, ly, box_size, box_size), 3.0 * scale, 3.0 * scale)

            # 8b. Alvos da Tela de Morte / Respawn em modo calibração
            # Segue o padrão de assets/images/sreensXcursor/death-screen.png:
            # Amarelo para o foco ativo (default: resurrect_entrance) e verde para as possibilidades.
            is_death_screen = (
                "Morte / Respawn" in (snapshot.memory_open_menus or [])
                or any("morte" in m.lower() or "respawn" in m.lower() for m in (snapshot.memory_open_menus or []))
            )
            if is_death_screen:
                box_size = 20.0 * scale * (rect.height / 768.0)
                for btn_name in DEATH_SCREEN_BUTTONS:
                    bx, by = death_screen_button_point(rect, btn_name)
                    lx = bx - rect.left - box_size / 2.0
                    ly = by - rect.top - box_size / 2.0
                    is_focus = (snapshot.death_screen_focus == btn_name)
                    if is_focus:
                        painter.setPen(QPen(QColor(230, 193, 42, 240), 2.0 * scale))
                        painter.setBrush(QColor(230, 193, 42, 160))
                    else:
                        painter.setPen(QPen(QColor(9, 178, 0, 230), 1.5 * scale))
                        painter.setBrush(QColor(9, 178, 0, 90))
                    painter.drawRoundedRect(QRectF(lx, ly, box_size, box_size), 3.0 * scale, 3.0 * scale)

            # 9. Alvos do Inventário do Jogador (Abas + Grid 3x7 + Equipamentos superiores)
            is_inv_open = snapshot.inventory_open or ("Inventário" in (snapshot.memory_open_menus or []))
            if is_inv_open:
                c_ciano = QColor(0x0B, 0xE0, 0xEF, 220)
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)

                # Abas do inventário (1, 2, 3) em ciano (#0BE0EF)
                tab_w = 95.0 * scale * (rect.height / 768.0)
                tab_h = 18.0 * scale * (rect.height / 768.0)
                for tab_idx in (1, 2, 3):
                    tx, ty = inventory_tab_point(rect, tab_idx)
                    lx = tx - rect.left - tab_w / 2.0
                    ly = ty - rect.top - tab_h / 2.0
                    is_active_tab = (snapshot.inventory_tab == f"tab-{tab_idx}")
                    if is_active_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.0 * scale))
                        painter.setBrush(c_ciano)
                    else:
                        painter.setPen(QPen(c_ciano, 1.5 * scale))
                        painter.setBrush(QColor(0x0B, 0xE0, 0xEF, 100))
                    painter.drawRoundedRect(QRectF(lx, ly, tab_w, tab_h), 3.0 * scale, 3.0 * scale)

                # Slots do Grid 3x7 (Linha 1..3, Coluna 1..7)
                slot_box = 18.0 * scale * (rect.height / 768.0)
                is_pet_also_open = snapshot.pet_inventory_open or ("Pet" in (snapshot.memory_open_menus or []))
                is_stash_also_open = snapshot.stash_open or ("Baú" in (snapshot.memory_open_menus or []))
                is_merchant_also_open = snapshot.merchant_open or ("Vendedor (Loja)" in (snapshot.memory_open_menus or []))
                is_crafting_also_open = snapshot.crafting_open or any(m in (snapshot.memory_open_menus or []) for m in ("Transmutador", "Sockets", "Encantador"))
                is_char_also_open = snapshot.char_menu_open or ("Atributos" in (snapshot.memory_open_menus or []))
                is_left_also_open = is_pet_also_open or is_stash_also_open or is_merchant_also_open or is_crafting_also_open or is_char_also_open
                for r in range(1, INVENTORY_GRID_ROWS + 1):
                    for c in range(1, INVENTORY_GRID_COLS + 1):
                        sx, sy = inventory_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_slot1 = (r == 1 and c == 1)
                        is_focus = (snapshot.inventory_focus in (f"({r}, {c})", f"({r},{c})"))
                        is_bridge = is_left_also_open and (c == 1)
                        color = c_laranja if is_bridge else (c_amarelo if is_slot1 else c_verde)
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # 16 Slots Superiores de Equipamento e Spells
                for slot_name in INVENTORY_UPPER_COORDS:
                    ux, uy = inventory_upper_point(rect, slot_name)
                    lx = ux - rect.left - slot_box / 2.0
                    ly = uy - rect.top - slot_box / 2.0
                    is_focus = (snapshot.inventory_focus == slot_name)
                    is_bridge = is_left_also_open and (slot_name in ("spell_1", "main_hand", "belt", "gloves", "helmet"))
                    color = c_laranja if is_bridge else c_verde
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

            # 10. Alvos do Menu do Pet (Abas + Grid 3x7 + Equipamentos/Spells superiores)
            is_pet_open = snapshot.pet_inventory_open or ("Pet" in (snapshot.memory_open_menus or []))
            if is_pet_open:
                c_ciano = QColor(0x0B, 0xE0, 0xEF, 220)
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)

                # Abas do menu de pet (1, 2, 3) em ciano (#0BE0EF)
                tab_w = 95.0 * scale * (rect.height / 768.0)
                tab_h = 18.0 * scale * (rect.height / 768.0)
                for tab_idx in (1, 2, 3):
                    tx, ty = pet_inventory_tab_point(rect, tab_idx)
                    lx = tx - rect.left - tab_w / 2.0
                    ly = ty - rect.top - tab_h / 2.0
                    is_active_tab = (snapshot.pet_inventory_tab == f"tab-{tab_idx}")
                    if is_active_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.0 * scale))
                        painter.setBrush(c_ciano)
                    else:
                        painter.setPen(QPen(c_ciano, 1.5 * scale))
                        painter.setBrush(QColor(0x0B, 0xE0, 0xEF, 100))
                    painter.drawRoundedRect(QRectF(lx, ly, tab_w, tab_h), 3.0 * scale, 3.0 * scale)

                # Slots do Grid 3x7 (Linha 1..3, Coluna 1..7)
                slot_box = 18.0 * scale * (rect.height / 768.0)
                is_inv_also_open = snapshot.inventory_open or ("Inventário" in (snapshot.memory_open_menus or []))
                is_skills_also_open = snapshot.skill_menu_open or ("Habilidades" in (snapshot.memory_open_menus or []))
                is_quest_also_open = "Missões (Quests)" in (snapshot.memory_open_menus or [])
                is_right_also_open = is_inv_also_open or is_skills_also_open or is_quest_also_open
                for r in range(1, PET_GRID_ROWS + 1):
                    for c in range(1, PET_GRID_COLS + 1):
                        sx, sy = pet_inventory_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_slot1 = (r == 1 and c == 1)
                        is_focus = (snapshot.pet_inventory_focus in (f"({r}, {c})", f"({r},{c})"))
                        is_bridge = is_right_also_open and (c == 7)
                        color = c_amarelo if is_slot1 else (c_laranja if is_bridge else c_verde)
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # 5 Slots Superiores de Equipamento e Spells do Pet
                for slot_name in PET_UPPER_COORDS:
                    ux, uy = pet_inventory_upper_point(rect, slot_name)
                    lx = ux - rect.left - slot_box / 2.0
                    ly = uy - rect.top - slot_box / 2.0
                    is_focus = (snapshot.pet_inventory_focus == slot_name)
                    is_bridge = is_right_also_open and (slot_name == "pet_spell_2")
                    color = c_laranja if is_bridge else c_verde
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

            # 11. Alvos do Menu do Baú (Stash 6x7 + Pet 3x7 + Abas)
            is_stash_open = snapshot.stash_open or ("Baú" in (snapshot.memory_open_menus or []))
            if is_stash_open:
                c_ciano = QColor(0x0B, 0xE0, 0xEF, 220)
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)

                # Abas do menu de pet/baú (1, 2, 3) em ciano (#0BE0EF)
                tab_w = 95.0 * scale * (rect.height / 768.0)
                tab_h = 18.0 * scale * (rect.height / 768.0)
                for tab_idx in (1, 2, 3):
                    tx, ty = pet_inventory_tab_point(rect, tab_idx)
                    lx = tx - rect.left - tab_w / 2.0
                    ly = ty - rect.top - tab_h / 2.0
                    is_active_tab = (snapshot.stash_tab == f"tab-{tab_idx}")
                    if is_active_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.0 * scale))
                        painter.setBrush(c_ciano)
                    else:
                        painter.setPen(QPen(c_ciano, 1.5 * scale))
                        painter.setBrush(QColor(0x0B, 0xE0, 0xEF, 100))
                    painter.drawRoundedRect(QRectF(lx, ly, tab_w, tab_h), 3.0 * scale, 3.0 * scale)

                # Slots do Grid Inferior do Pet (Linha 1..3, Coluna 1..7)
                slot_box = 18.0 * scale * (rect.height / 768.0)
                is_inv_also_open = snapshot.inventory_open or ("Inventário" in (snapshot.memory_open_menus or []))
                for r in range(1, PET_GRID_ROWS + 1):
                    for c in range(1, PET_GRID_COLS + 1):
                        sx, sy = pet_inventory_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_slot1 = (r == 1 and c == 1)
                        is_focus = (snapshot.stash_focus in (f"('pet', {r}, {c})", f"('pet',{r},{c})"))
                        is_bridge = is_inv_also_open and (c == 7)
                        color = c_amarelo if is_slot1 else (c_laranja if is_bridge else c_verde)
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # Slots do Grid Superior do Baú (Linha 1..6, Coluna 1..7)
                for r in range(1, STASH_GRID_ROWS + 1):
                    for c in range(1, STASH_GRID_COLS + 1):
                        sx, sy = stash_upper_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_focus = (snapshot.stash_focus in (f"('stash', {r}, {c})", f"('stash',{r},{c})"))
                        is_bridge = is_inv_also_open and (c == 7)
                        color = c_laranja if is_bridge else c_verde
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

            # 12. Alvos do Menu do Mercador (Loja 6x7 + Pet 3x7 + Abas Rosa + Abas Ciano)
            is_merchant_open = snapshot.merchant_open or ("Vendedor (Loja)" in (snapshot.memory_open_menus or []))
            if is_merchant_open:
                c_rosa = QColor(0xFD, 0x62, 0xCE, 220)
                c_ciano = QColor(0x0B, 0xE0, 0xEF, 220)
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)

                # 3 Abas Rosa da Loja (1=Misc, 2=Weapon, 3=Armor) (#FD62CE)
                tab_w = 88.0 * scale * (rect.height / 768.0)
                tab_h = 22.0 * scale * (rect.height / 768.0)
                for tab_idx in (1, 2, 3):
                    tx, ty = merchant_tab_point(rect, tab_idx)
                    lx = tx - rect.left - tab_w / 2.0
                    ly = ty - rect.top - tab_h / 2.0
                    is_active_tab = (snapshot.merchant_tab == f"tab-{tab_idx}")
                    is_focus = (snapshot.merchant_focus in (f"('merchant_tab', {tab_idx})", f"('merchant_tab',{tab_idx})"))
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(c_rosa)
                    elif is_active_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 1.8 * scale))
                        painter.setBrush(QColor(0xFD, 0x62, 0xCE, 180))
                    else:
                        painter.setPen(QPen(c_rosa, 1.5 * scale))
                        painter.setBrush(QColor(0xFD, 0x62, 0xCE, 100))
                    painter.drawRoundedRect(QRectF(lx, ly, tab_w, tab_h), 3.0 * scale, 3.0 * scale)

                # Abas do menu de pet (1, 2, 3) em ciano (#0BE0EF)
                pet_tab_w = 95.0 * scale * (rect.height / 768.0)
                pet_tab_h = 18.0 * scale * (rect.height / 768.0)
                for tab_idx in (1, 2, 3):
                    tx, ty = pet_inventory_tab_point(rect, tab_idx)
                    lx = tx - rect.left - pet_tab_w / 2.0
                    ly = ty - rect.top - pet_tab_h / 2.0
                    is_active_tab = (snapshot.pet_inventory_tab == f"tab-{tab_idx}" or snapshot.stash_tab == f"tab-{tab_idx}")
                    if is_active_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.0 * scale))
                        painter.setBrush(c_ciano)
                    else:
                        painter.setPen(QPen(c_ciano, 1.5 * scale))
                        painter.setBrush(QColor(0x0B, 0xE0, 0xEF, 100))
                    painter.drawRoundedRect(QRectF(lx, ly, pet_tab_w, pet_tab_h), 3.0 * scale, 3.0 * scale)

                # Slots do Grid Inferior do Pet (Linha 1..3, Coluna 1..7)
                slot_box = 18.0 * scale * (rect.height / 768.0)
                is_inv_also_open = snapshot.inventory_open or ("Inventário" in (snapshot.memory_open_menus or []))
                for r in range(1, PET_GRID_ROWS + 1):
                    for c in range(1, PET_GRID_COLS + 1):
                        sx, sy = pet_inventory_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_slot1 = (r == 1 and c == 1)
                        is_focus = (snapshot.merchant_focus in (f"('pet', {r}, {c})", f"('pet',{r},{c})"))
                        is_bridge = is_inv_also_open and (c == 7)
                        color = c_amarelo if is_slot1 else (c_laranja if is_bridge else c_verde)
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # Slots do Grid Superior do Mercador (Linha 1..6, Coluna 1..7)
                for r in range(1, MERCHANT_GRID_ROWS + 1):
                    for c in range(1, MERCHANT_GRID_COLS + 1):
                        sx, sy = merchant_slot_point(rect, r, c)
                        lx = sx - rect.left - slot_box / 2.0
                        ly = sy - rect.top - slot_box / 2.0
                        is_slot1 = (r == 1 and c == 1)
                        is_focus = (snapshot.merchant_focus in (f"('merchant', {r}, {c})", f"('merchant',{r},{c})"))
                        is_bridge = is_inv_also_open and (c == 7)
                        color = c_amarelo if is_slot1 else (c_laranja if is_bridge else c_verde)
                        if is_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(color)
                        else:
                            painter.setPen(QPen(color, 1.5 * scale))
                            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                        painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

            # 13. Alvos do Menu de Personagem (C) - Atributos, Topo (XP/Fame/HP/MP) e Resistências
            is_char_open = snapshot.char_menu_open or ("Atributos" in (snapshot.memory_open_menus or []))
            if is_char_open:
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)
                c_rosa = QColor(0xB2, 0x00, 0x7C, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)

                slot_box = 18.0 * scale * (rect.height / 768.0)
                has_points = (snapshot.attr_points_remaining > 0)
                nodes_dict = CHAR_MENU_NODES_HAS_POINTS if has_points else CHAR_MENU_NODES_NO_POINTS

                is_inv_also_open = snapshot.inventory_open or ("Inventário" in (snapshot.memory_open_menus or []))
                is_skills_also_open = snapshot.skill_menu_open or ("Habilidades" in (snapshot.memory_open_menus or []))
                is_quest_also_open = "Missões (Quests)" in (snapshot.memory_open_menus or [])
                is_right_also_open = is_inv_also_open or is_skills_also_open or is_quest_also_open

                for node_name, (base_x, base_y) in nodes_dict.items():
                    nx = rect.left + base_x * (rect.height / 768.0)
                    ny = rect.top + base_y * (rect.height / 768.0)
                    lx = nx - rect.left - slot_box / 2.0
                    ly = ny - rect.top - slot_box / 2.0

                    is_focus = (snapshot.char_menu_focus == node_name)

                    if node_name.endswith("_pink"):
                        color = c_rosa
                    elif node_name in ("xp", "fame", "mp", "res_fire", "res_ice") or node_name.endswith("_bridge"):
                        color = c_laranja if is_right_also_open else c_verde
                    else:
                        color = c_verde

                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(c_amarelo)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 150))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

            # 14. Alvos do Menu de Habilidades (S) - Abas e Grid Dinâmica da Skill Tree
            is_skills_open = snapshot.skill_menu_open or ("Habilidades" in (snapshot.memory_open_menus or []))
            if is_skills_open:
                c_ciano = QColor(0x0B, 0xE0, 0xEF, 220)
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)
                c_rosa = QColor(0xB2, 0x00, 0x7C, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)

                tab_w = 90.0 * scale * (rect.height / 768.0)
                tab_h = 22.0 * scale * (rect.height / 768.0)
                slot_box = 40.0 * scale * (rect.height / 768.0)
                pink_box = 15.0 * scale * (rect.height / 768.0)

                active_tab = snapshot.skill_tab or 1
                char_cls = (snapshot.char_class or "alchemist").lower()
                if char_cls not in SKILL_TREE_LAYOUTS:
                    char_cls = "alchemist"

                # 1. Três Abas de Habilidades (1, 2, 3)
                for tab_idx in (1, 2, 3):
                    tx, ty = skill_tab_point(rect, tab_idx)
                    tlx = tx - rect.left - tab_w / 2.0
                    tly = ty - rect.top - tab_h / 2.0
                    is_current_tab = (active_tab == tab_idx)
                    is_tab_focus = (snapshot.skill_focus == f"tab_{tab_idx}")

                    if is_tab_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(c_amarelo)
                    elif is_current_tab:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.0 * scale))
                        painter.setBrush(c_amarelo)
                    else:
                        painter.setPen(QPen(c_ciano, 1.5 * scale))
                        painter.setBrush(QColor(0x0B, 0xE0, 0xEF, 100))
                    painter.drawRoundedRect(QRectF(tlx, tly, tab_w, tab_h), 3.0 * scale, 3.0 * scale)

                # 2. Grid de Habilidades da Aba Ativa
                tab_name = SKILL_TAB_NAMES.get(char_cls, {}).get(active_tab, "arcane")
                layout = SKILL_TREE_LAYOUTS.get(char_cls, {}).get(tab_name, [])

                skill_pts = snapshot.skill_points_remaining
                up_map = snapshot.skill_upgradeable or {}

                for r, row_layout in enumerate(layout):
                    bridge_col = skill_bridge_col(row_layout)
                    for c, val in enumerate(row_layout):
                        if val is None:
                            continue  # Célula sem skill

                        sx, sy = skill_slot_point(rect, r, c)
                        slx = sx - rect.left - slot_box / 2.0
                        sly = sy - rect.top - slot_box / 2.0

                        is_bridge = (c == bridge_col)
                        is_slot_focus = (snapshot.skill_focus == f"({r}, {c})")

                        base_color = c_laranja if is_bridge else c_verde

                        if is_slot_focus:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(c_amarelo)
                        else:
                            painter.setPen(QPen(base_color, 1.5 * scale))
                            painter.setBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), 140))
                        painter.drawRoundedRect(QRectF(slx, sly, slot_box, slot_box), 4.0 * scale, 4.0 * scale)

                        # 3. Nó Rosa de Level-up (+): visível se skill_points > 0 e slot elegível
                        is_upgradeable = up_map.get((r, c), False) if up_map else (skill_pts > 0)
                        if skill_pts > 0 and is_upgradeable:
                            px, py = skill_slot_pink_point(rect, r, c)
                            plx = px - rect.left - pink_box / 2.0
                            ply = py - rect.top - pink_box / 2.0
                            is_pink_focus = (snapshot.skill_focus == f"({r}, {c}, pink)")

                            if is_pink_focus:
                                painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                                painter.setBrush(c_amarelo)
                            else:
                                painter.setPen(QPen(c_rosa, 1.5 * scale))
                                painter.setBrush(QColor(c_rosa.red(), c_rosa.green(), c_rosa.blue(), 170))
                            painter.drawRoundedRect(QRectF(plx, ply, pink_box, pink_box), 3.0 * scale, 3.0 * scale)

                # 4. Slots de Spells no rodapé do Menu S
                for s_i in range(4):
                    sx, sy = skill_spell_slot_point(rect, s_i)
                    slx = sx - rect.left - slot_box / 2.0
                    sly = sy - rect.top - slot_box / 2.0
                    s_color = c_laranja if s_i == 0 else c_verde
                    is_spell_focus = (snapshot.skill_focus == f"spell_{s_i}")
                    if is_spell_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(c_amarelo)
                    else:
                        painter.setPen(QPen(s_color, 1.5 * scale))
                        painter.setBrush(QColor(s_color.red(), s_color.green(), s_color.blue(), 140))
                    painter.drawRoundedRect(QRectF(slx, sly, slot_box, slot_box), 4.0 * scale, 4.0 * scale)

            # 15. Alvos do Menu de Missões / Quests (Q)
            is_quest_open = "Missões (Quests)" in (snapshot.memory_open_menus or [])
            if is_quest_open:
                c_verde = QColor(0x09, 0xB2, 0x00, 220)
                c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
                c_laranja = QColor(0xFD, 0x61, 0x00, 220)

                slot_box = 18.0 * scale * (rect.height / 768.0)
                is_pet_also_open = snapshot.pet_inventory_open or ("Pet" in (snapshot.memory_open_menus or []))
                is_char_also_open = snapshot.char_menu_open or ("Atributos" in (snapshot.memory_open_menus or []))
                has_left_menu = is_pet_also_open or is_char_also_open

                # Cor padrão dos slots: laranja se houver menu à esquerda (ponte), verde se não
                normal_color = c_laranja if has_left_menu else c_verde

                # 6 slots da lista de missões (ou quantidade visível de linhas ativas)
                rows_to_draw = snapshot.quest_visible_rows or max(1, min(snapshot.quest_count or QUEST_ROW_COUNT, QUEST_ROW_COUNT))
                for i in range(rows_to_draw):
                    sx, sy = quest_slot_point(rect, i)
                    lx = sx - rect.left - slot_box / 2.0
                    ly = sy - rect.top - slot_box / 2.0
                    is_focus = (snapshot.quest_focus == f"quest_{i}")

                    color = c_amarelo if is_focus else normal_color
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # Slot de recompensa de item (se a missão selecionada tiver recompensa)
                if snapshot.quest_has_item_reward:
                    rx, ry = quest_reward_point(rect)
                    lx = rx - rect.left - slot_box / 2.0
                    ly = ry - rect.top - slot_box / 2.0
                    is_focus = (snapshot.quest_focus == "reward")

                    color = c_amarelo if is_focus else normal_color
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

                # Botão Abandon (se a missão selecionada puder ser abandonada)
                if snapshot.quest_can_abandon:
                    ax, ay = quest_abandon_point(rect)
                    lx = ax - rect.left - slot_box / 2.0
                    ly = ay - rect.top - slot_box / 2.0
                    is_focus = (snapshot.quest_focus == "abandon")

                    color = c_amarelo if is_focus else normal_color
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 140))
                    painter.drawRoundedRect(QRectF(lx, ly, slot_box, slot_box), 3.0 * scale, 3.0 * scale)

        elif state_desc == "Tela Inicial":
            # Alvos da Tela Inicial (Title Screen) em modo calibração
            btn_w = 43 * scale
            btn_h = 36 * scale
            for btn_name in TITLE_BUTTONS:
                if btn_name == "continue" and snapshot.title_menu_focus != "continue":
                    continue
                bx, by = title_menu_button_point(rect, btn_name)
                lx = bx - rect.left - btn_w / 2
                ly = by - rect.top - btn_h / 2
                is_focus = (snapshot.title_menu_focus == btn_name)
                if is_focus:
                    painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                    painter.setBrush(QColor(255, 215, 0, 110))
                else:
                    painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                    painter.setBrush(QColor(46, 204, 113, 75))
                painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)

        elif state_desc == "Criar Personagem":
            # Alvos da Tela de Criação de Personagem (state_id == 1) em modo calibração
            for btn_name in CREATE_CHAR_BUTTONS:
                if btn_name in ("destroyer", "vanquisher", "alchemist"):
                    btn_w, btn_h = 44 * scale, 38 * scale
                elif btn_name in ("dog", "cat", "ferret", "pet_name"):
                    btn_w, btn_h = 34 * scale, 18 * scale
                else:  # back, character_name, ok
                    btn_w, btn_h = 47 * scale, 37 * scale

                bx, by = char_create_button_point(rect, btn_name)
                lx = bx - rect.left - btn_w / 2
                ly = by - rect.top - btn_h / 2
                is_focus = (snapshot.char_create_focus == btn_name)
                if btn_name == "ok" and snapshot.char_name_len == 0:
                    painter.setPen(QPen(QColor(231, 76, 60, 160), 1.5 * scale, Qt.PenStyle.DashLine))
                    painter.setBrush(QColor(231, 76, 60, 40))
                elif is_focus:
                    painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                    painter.setBrush(QColor(255, 215, 0, 110))
                else:
                    painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                    painter.setBrush(QColor(46, 204, 113, 75))
                painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)

        elif state_desc == "Selecionar Dificuldade":
            # Alvos da Tela de Seleção de Dificuldade (state_id == 2) em modo calibração
            btn_w = 24 * scale
            btn_h = 23 * scale
            for btn_name in DIFFICULTY_BUTTONS:
                bx, by = difficulty_menu_button_point(rect, btn_name)
                lx = bx - rect.left - btn_w / 2
                ly = by - rect.top - btn_h / 2
                is_focus = (snapshot.difficulty_focus == btn_name)
                if is_focus:
                    painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                    painter.setBrush(QColor(255, 215, 0, 110))
                else:
                    painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                    painter.setBrush(QColor(46, 204, 113, 75))
                painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)

        elif state_desc == "Carregar Personagem":
            # Alvos da Tela de Carregar Personagem (state_id == 3) em modo calibração
            box_w = 34 * scale * (rect.height / 768.0)
            box_h = 18 * scale * (rect.height / 768.0)

            if snapshot.load_char_delete_open:
                # Modal de Confirmação de Exclusão (Delete Character)
                del_buttons = ("delete_confirm", "delete_cancel")
                for btn_name in del_buttons:
                    bx, by = load_char_button_point(rect, btn_name)
                    lx = bx - rect.left - box_w / 2
                    ly = by - rect.top - box_h / 2
                    is_focus = (snapshot.load_char_focus == btn_name)
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 160))
                    else:
                        painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                        painter.setBrush(QColor(46, 204, 113, 90))
                    painter.drawRoundedRect(QRectF(lx, ly, box_w, box_h), 3 * scale, 3 * scale)
            else:
                # Tela principal de carregamento de personagens
                # Slots 1 a 5, setas de scroll e botões inferiores (Delete, Back, Play)
                active_buttons = ["slot_1", "slot_2", "slot_3", "slot_4", "slot_5", "scroll_up", "scroll_down", "delete", "back", "play"]
                for btn_name in active_buttons:
                    bx, by = load_char_button_point(rect, btn_name)
                    lx = bx - rect.left - box_w / 2
                    ly = by - rect.top - box_h / 2
                    is_focus = (snapshot.load_char_focus == btn_name)
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
                        painter.setBrush(QColor(255, 215, 0, 160))
                    else:
                        painter.setPen(QPen(QColor(46, 204, 113, 230), 1.5 * scale))
                        painter.setBrush(QColor(46, 204, 113, 90))
                    painter.drawRoundedRect(QRectF(lx, ly, box_w, box_h), 3 * scale, 3 * scale)

        elif is_settings:
            # Calibração da Tela de Configurações (Settings)
            # Conforme assets/images/sreensXcursor/settings/info.md:
            # - verde: #09B200 (pontos navegáveis)
            # - amarelo: #E6C12A (ponto de deslocamento padrão do cursor)
            # - rosa: #B2007C (pontos de dropdown)
            # - roxo: #5600B2 (sliders de som baseado no volume salvo)
            # - ciano: #00C7D5 (limites de deslocamento X dos sliders)
            c_verde = QColor(0x09, 0xB2, 0x00, 220)
            c_amarelo = QColor(0xE6, 0xC1, 0x2A, 220)
            c_rosa = QColor(0xB2, 0x00, 0x7C, 220)
            c_roxo = QColor(0x56, 0x00, 0xB2, 220)
            c_ciano = QColor(0x00, 0xC7, 0xD5, 220)

            box_size = 18.0 * scale * (rect.height / 768.0)

            if snapshot.settings_dropdown:
                # Dropdown aberto: desenha apenas o opener rosa, a opção default amarela e opções verdes
                drop_name = snapshot.settings_dropdown
                drop_info = SETTINGS_DROPDOWNS.get(drop_name)
                if drop_info:
                    # 1. Opener rosa
                    ox, oy = settings_button_point(rect, drop_name)
                    olx = ox - rect.left - box_size / 2.0
                    oly = oy - rect.top - box_size / 2.0
                    painter.setPen(QPen(c_rosa, 2.0 * scale))
                    painter.setBrush(QColor(0xB2, 0x00, 0x7C, 140))
                    painter.drawRoundedRect(QRectF(olx, oly, box_size, box_size), 3 * scale, 3 * scale)

                    # 2. Opções da lista (no resolution: 18px altura e 4px gap na ref 1280x1024 -> h=13.5 na base 768p)
                    opt_box_w = box_size
                    opt_box_h = 13.5 * scale * (rect.height / 768.0) if drop_name == "resolution" else box_size
                    for idx in range(len(drop_info["options"])):
                        opt_x, opt_y = settings_dropdown_option_point(rect, drop_name, idx)
                        opt_lx = opt_x - rect.left - opt_box_w / 2.0
                        opt_ly = opt_y - rect.top - opt_box_h / 2.0
                        is_sel = (snapshot.settings_dropdown_idx == idx)
                        base_color = c_amarelo if idx == 0 else c_verde
                        if is_sel:
                            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                            painter.setBrush(base_color)
                        else:
                            painter.setPen(QPen(base_color, 1.5 * scale))
                            painter.setBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), 100))
                        painter.drawRoundedRect(QRectF(opt_lx, opt_ly, opt_box_w, opt_box_h), 3 * scale, 3 * scale)
            else:
                # Tela principal de configurações
                # 1. Linhas ciano dos sliders
                (sx1, sy1), (sx2, sy2) = settings_slider_bounds(rect, is_music=False)
                (mx1, my1), (mx2, my2) = settings_slider_bounds(rect, is_music=True)
                pen_ciano = QPen(c_ciano, 3.0 * scale)
                painter.setPen(pen_ciano)
                painter.drawLine(QPointF(sx1 - rect.left, sy1 - rect.top), QPointF(sx2 - rect.left, sy2 - rect.top))
                painter.drawLine(QPointF(mx1 - rect.left, my1 - rect.top), QPointF(mx2 - rect.left, my2 - rect.top))

                # 2. Botões da tela principal
                sound_vol = snapshot.settings_sound_vol
                music_vol = snapshot.settings_music_vol

                for btn_name in SETTINGS_BUTTONS:
                    if btn_name == "sound_slider":
                        bx, by = settings_button_point(rect, btn_name, sound_vol)
                        color = c_roxo
                    elif btn_name == "music_slider":
                        bx, by = settings_button_point(rect, btn_name, music_vol)
                        color = c_roxo
                    elif btn_name in ("resolution", "shadows", "particle_detail"):
                        bx, by = settings_button_point(rect, btn_name)
                        color = c_rosa
                    elif btn_name == "row1_col1":
                        bx, by = settings_button_point(rect, btn_name)
                        color = c_amarelo
                    else:
                        bx, by = settings_button_point(rect, btn_name)
                        color = c_verde

                    lx = bx - rect.left - box_size / 2.0
                    ly = by - rect.top - box_size / 2.0
                    is_focus = (snapshot.settings_focus == btn_name)

                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(color)
                    else:
                        painter.setPen(QPen(color, 1.5 * scale))
                        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 120))

                    painter.drawRoundedRect(QRectF(lx, ly, box_size, box_size), 3 * scale, 3 * scale)

                    if is_focus and snapshot.settings_slider_dragging and btn_name in ("sound_slider", "music_slider"):
                        painter.setPen(QPen(QColor(255, 255, 0, 255), 1.5 * scale, Qt.PenStyle.DashLine))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawEllipse(QPointF(bx - rect.left, by - rect.top), box_size * 0.8, box_size * 0.8)

        # 11. Modal de Confirmação (Resultado de Pesca / Popups com Ok)
        if snapshot.modal_confirm_focus:
            btn_w = 125 * scale * (rect.height / 768.0)
            btn_h = 24 * scale * (rect.height / 768.0)
            bx, by = modal_ok_point(rect)
            lx = bx - rect.left - btn_w / 2.0
            ly = by - rect.top - btn_h / 2.0
            painter.setPen(QPen(QColor(255, 215, 0, 240), 2.0 * scale))
            painter.setBrush(QColor(255, 215, 0, 110))
            painter.drawRoundedRect(QRectF(lx, ly, btn_w, btn_h), 4 * scale, 4 * scale)
            painter.setFont(self._font(max(7, round(8 * scale)), True))
            painter.setPen(QColor(255, 255, 255, 240))
            painter.drawText(QRectF(lx, ly, btn_w, btn_h), Qt.AlignmentFlag.AlignCenter, "OK")

        # 12. Interface de Pesca (Anzol de Pescaria)
        if snapshot.fishing_focus:
            hook_size = 40.0 * scale * (rect.height / 768.0)
            hx, hy = fishing_hook_point(rect)
            lx = hx - rect.left - hook_size / 2.0
            ly = hy - rect.top - hook_size / 2.0
            painter.setPen(QPen(QColor(255, 30, 30, 240), 2.5 * scale))
            painter.setBrush(QColor(255, 30, 30, 60))
            painter.drawRect(QRectF(lx, ly, hook_size, hook_size))
            painter.setFont(self._font(max(7, round(8 * scale)), True))
            painter.setPen(QColor(255, 255, 255, 240))
            painter.drawText(QRectF(lx, ly - 14 * scale, hook_size, 14 * scale), Qt.AlignmentFlag.AlignCenter, "PESCA")

        # Badge de diagnóstico da Memória Interna (visível em todas as telas no modo calibração)
        mem_desc = snapshot.memory_state_desc or "Aguardando jogo..."
        menus_str = ", ".join(snapshot.memory_open_menus) if snapshot.memory_open_menus else "Nenhum"
        diag_lines = [
            f"ESTADO: {mem_desc.upper()}",
            f"MENUS : {menus_str}",
            f"MODO  : {snapshot.mode.upper()}",
        ]

        painter.setFont(self._font(max(7, round(8.5 * scale)), True))
        fm = painter.fontMetrics()
        max_line_w = max(fm.horizontalAdvance(line) for line in diag_lines)
        header_w = fm.horizontalAdvance("LEITURA DE MEMÓRIA (DEBUG)")
        box_w = max(340 * scale, max(max_line_w, header_w) + 28 * scale)
        box_h = (len(diag_lines) * 16 + 24) * scale
        # Centralizado no topo: fica livre da caixa do Pet (esquerda) e dos menus/mapa (direita)
        box_x = (rect.width - box_w) / 2
        box_y = 12 * scale

        # Fundo glassmorphism translúcido escuro com borda ciano
        painter.setPen(QPen(QColor(75, 222, 247, 190), 1.2 * scale))
        painter.setBrush(QColor(8, 20, 28, 225))
        painter.drawRoundedRect(QRectF(box_x, box_y, box_w, box_h), 6 * scale, 6 * scale)

        # Cabeçalho do badge
        painter.setPen(QColor(75, 222, 247, 240))
        painter.drawText(
            QRectF(box_x + 10 * scale, box_y + 4 * scale, box_w - 20 * scale, 16 * scale),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "LEITURA DE MEMÓRIA (DEBUG)",
        )

        # Linhas de informação
        for idx, line in enumerate(diag_lines):
            line_y = box_y + (23 + idx * 15) * scale
            color = (
                QColor(255, 175, 75)
                if ("ABERTO" in line or "LOADING" in line or "CARREGANDO" in line or (idx == 1 and menus_str != "Nenhum"))
                else QColor(220, 240, 248)
            )
            painter.setPen(color)
            painter.drawText(
                QRectF(box_x + 12 * scale, line_y, box_w - 24 * scale, 15 * scale),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
