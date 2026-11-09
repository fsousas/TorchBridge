from __future__ import annotations

import math
import sys
import time

from ..models import (
    OverlaySnapshot,
    controller_type_from_name,
    panels_x_shift,
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
)
from pathlib import Path

from ..resources import resource_root

log = logging.getLogger(__name__) if "logging" in globals() else None

def _radial_icons_dir() -> Path:
    base = resource_root()
    return base / "assets" / "images" / "radial-menu-icons"


# Diretório dos assets extras do menu radial (TB-16): informações e instruções.
def _radial_extra_hud_dir() -> Path:
    base = resource_root()
    return base / "assets" / "hud" / "menu radial"



class RadialOverlayMixin:
    """Mixin com métodos de desenho e animação para radial."""

    def _tick_radial_anim(self, snapshot: OverlaySnapshot) -> None:
        target = 1.0 if snapshot.radial_active else 0.0
        now = time.monotonic()
        dt = now - self._radial_last_time
        self._radial_last_time = now
        # Sem nada a animar: mantém o progresso e para de gastar ciclos.
        if abs(self._radial_progress - target) < 1e-3:
            self._radial_progress = target
            return
        step = dt / self._radial_anim_seconds
        if target > self._radial_progress:
            self._radial_progress = min(target, self._radial_progress + step)
        else:
            self._radial_progress = max(target, self._radial_progress - step)

    def _radial_icon(self, name: str, active: bool) -> QPixmap | None:
        key = (name, "ativo" if active else "normal")
        cached = self._radial_cache.get(key)
        if cached is not None:
            return cached
        filename = f"{name}-ativo.png" if active else f"{name}.png"
        path = _radial_icons_dir() / filename
        if not path.is_file():
            filename = f"{name.lower()}-ativo.png" if active else f"{name.lower()}.png"
            path = _radial_icons_dir() / filename
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._radial_cache[key] = pixmap
        return pixmap

    def _draw_radial(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        # A animação só termina quando o progresso chega ao alvo: a saída some aos poucos,
        # então desenha enquanto houver progresso (LB solto e progresso ainda > 0).
        progress = self._radial_progress
        if progress <= 0.0:
            return
        # Painel lateral aberto sozinho desloca a roda para o lado oposto (12,5% da largura).
        shift = panels_x_shift(snapshot.active_panels)
        center = QPointF(snapshot.game_rect.width * (0.5 + shift), snapshot.game_rect.height / 2)
        # Easing suave (smoothstep) do progresso: entra e sai mais lento nas pontas,
        # duração total continua sendo a do _tick_radial_anim (0.4 s nos dois sentidos).
        eased = progress * progress * (3.0 - 2.0 * progress)
        painter.save()
        # Aparência da animação: opacidade 0→1 e escala 0.7→1 em torno do centro da roda.
        painter.setOpacity(eased)
        scale_factor = 0.7 + 0.3 * eased
        painter.translate(center.x(), center.y())
        painter.scale(scale_factor, scale_factor)
        painter.translate(-center.x(), -center.y())
        ring_radius = 126 * scale
        node_radius = 27 * scale

        cfg = self.config.get()
        radial_slots = cfg["bindings"].get("radial_slots", [])

        # Centro: emblema dos assets; sem a arte, disco escuro com "MENUS".
        center_icon = self._radial_icon("Center", False)
        if center_icon is not None:
            size = int(124 * scale)
            painter.drawPixmap(int(center.x() - size / 2), int(center.y() - size / 2), size, size, center_icon)
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(4, 9, 15, 174))
            painter.drawEllipse(center, 62 * scale, 62 * scale)
            painter.setFont(self._font(max(8, round(9 * scale)), True))
            painter.setPen(QColor(221, 236, 244, 225))
            painter.drawText(
                QRectF(center.x() - 52 * scale, center.y() - 18 * scale, 104 * scale, 36 * scale),
                Qt.AlignmentFlag.AlignCenter,
                "MENUS",
            )

        # Ícones a partir do topo, no sentido horário — mesmo layout da função radial_slot.
        selected_point: QPointF | None = None
        for index in range(len(radial_slots)):
            angle = math.radians(-90 + index * (360 / len(radial_slots)))
            point = QPointF(
                center.x() + math.cos(angle) * ring_radius,
                center.y() + math.sin(angle) * ring_radius,
            )
            # Slot marcado pelo análogo troca para a arte "-ativo".
            selected = snapshot.radial_selection == index + 1
            if selected:
                selected_point = point
            icon = self._radial_icon(str(radial_slots[index]).upper(), selected)
            if icon is not None:
                width = int(80 * scale)
                height = int(width * icon.height() / icon.width())
                painter.drawPixmap(int(point.x() - width / 2), int(point.y() - height / 2), width, height, icon)
            else:
                # Fallback sem arte para essa letra: círculo vetorial com a letra.
                radius = node_radius * (1.14 if selected else 1.0)
                painter.setPen(
                    QPen(
                        QColor(255, 202, 82, 245) if selected else QColor(111, 210, 235, 205),
                        3.0 * scale if selected else 1.5 * scale,
                    )
                )
                painter.setBrush(QColor(35, 30, 18, 238) if selected else QColor(6, 17, 25, 224))
                painter.drawEllipse(point, radius, radius)
                painter.setFont(self._font(max(11, round(15 * scale)), True))
                painter.setPen(QColor(255, 220, 137) if selected else QColor(231, 247, 251))
                painter.drawText(
                    QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    str(radial_slots[index]),
                )
        # Sublinha de pet actions: 4 círculos cinza sob o nó do slot 'P', o 4º alinhado
        # no eixo do nó. Visível quando snapshot.pet_submenu_open (roda aberta + pet
        # selecionado + d-pad baixo). O círculo marcado fica dourado. Animação
        # entrada/saída: as bolinhas nascem no CENTRO do nó P e abrem em leque até a
        # fileira (e voltam ao fechar), com fade e chegadas em cascata — a 4ª pá,
        # a 3ª pá, a 2ª pá, a 1ª (mais distante) por último.
        pet_progress = self._pet_submenu_progress
        if snapshot.pet_submenu_open and selected_point is not None:
            # Sublinha aberta: atualiza os backups (nó P atual + marcador) — eles
            # sustentam a animação de saída no tick em que o snapshot zerar tudo.
            self._last_pet_point = selected_point
            self._last_pet_selection = snapshot.pet_submenu_selection
        elif not (self._last_pet_point is not None and progress > 0.0):
            # Nem aberta, nem com roda de pé para a saída: zera (e apaga o backup,
            # para uma roda NOVA não herdar a sublinha de uma sessão anterior).
            pet_progress = 0.0
            self._last_pet_point = None
            self._last_pet_selection = None
        # `progress` é o da roda: a sublinha só desenha com a roda de pé. A saída
        # segue no último nó guardado até o progresso zerar.
        if pet_progress > 0.0 and self._last_pet_point is not None:
            self._draw_pet_submenu(
                painter, self._last_pet_point, scale, self._last_pet_selection, pet_progress
            )
        # Devolve transformações de estado (opacidade/translate/scale) ao desenhista.
        painter.restore()

        # TB-16: Informações extras no menu radial (card superior e instruções inferiores)
        self._draw_radial_top_info(painter, center, scale)
        self._draw_radial_bottom_instructions(painter, center, scale, snapshot)

    def _get_radial_top_info_key(self, snapshot: OverlaySnapshot) -> str | None:
        if not snapshot.radial_active or snapshot.radial_selection is None:
            return None
        cfg = self.config.get()
        slots = cfg.get("bindings", {}).get("radial_slots", [])
        idx = snapshot.radial_selection - 1
        if not (0 <= idx < len(slots)):
            return None
        slot = str(slots[idx]).strip()
        slot_upper = slot.upper()
        if slot_upper in ("SHORT-CUT", "SHORTCUT", "SHORTCUTS", "SHORT-CUTS"):
            return "Shortcuts"
        if slot_upper == "P":
            if snapshot.pet_submenu_open and snapshot.pet_submenu_selection:
                sub_map = {
                    1: "P-agressive",
                    2: "P-defensive",
                    3: "P-passive",
                    4: "P-sell",
                }
                return sub_map.get(snapshot.pet_submenu_selection, "P")
            return "P"
        return slot_upper

    def _tick_radial_top_info_anim(self, snapshot: OverlaySnapshot) -> None:
        target_key = self._get_radial_top_info_key(snapshot)
        now = time.monotonic()
        dt = now - self._radial_top_info_last_time
        self._radial_top_info_last_time = now

        if target_key != self._radial_top_info_target:
            prev_target = self._radial_top_info_target
            self._radial_top_info_target = target_key

            if target_key is not None:
                if prev_target is None or self._radial_top_info_progress <= 0.0 or not self._radial_top_info_current:
                    # Entrada inicial (do estado nada selecionado): fade + scale
                    self._radial_top_info_current = target_key
                    self._radial_top_info_prev = None
                    self._radial_top_info_progress = 0.0
                    self._radial_top_info_crossfade = False
                else:
                    # Troca entre opções com card já visível: fade somente (sem scale)
                    self._radial_top_info_prev = self._radial_top_info_current
                    self._radial_top_info_prev_opacity = 1.0
                    self._radial_top_info_current = target_key
                    self._radial_top_info_crossfade = True
                    self._radial_top_info_crossfade_progress = 0.0
            else:
                # Saída: fade + scale
                self._radial_top_info_crossfade = False

        if self._radial_top_info_crossfade:
            cf_step = dt / self._radial_top_info_crossfade_seconds if self._radial_top_info_crossfade_seconds > 0 else 1.0
            self._radial_top_info_crossfade_progress = min(1.0, self._radial_top_info_crossfade_progress + cf_step)
            t = self._radial_top_info_crossfade_progress
            eased_t = t * t * (3.0 - 2.0 * t)
            self._radial_top_info_prev_opacity = max(0.0, 1.0 - eased_t)
            self._radial_top_info_progress = 1.0
            if self._radial_top_info_crossfade_progress >= 1.0:
                self._radial_top_info_crossfade = False
                self._radial_top_info_prev = None
        else:
            step = dt / self._radial_top_info_anim_seconds if self._radial_top_info_anim_seconds > 0 else 1.0
            target_prog = 1.0 if self._radial_top_info_target is not None else 0.0
            if abs(self._radial_top_info_progress - target_prog) < 1e-3:
                self._radial_top_info_progress = target_prog
                if target_prog == 0.0:
                    self._radial_top_info_current = None
            elif target_prog > self._radial_top_info_progress:
                self._radial_top_info_progress = min(target_prog, self._radial_top_info_progress + step)
            else:
                self._radial_top_info_progress = max(target_prog, self._radial_top_info_progress - step)
                if self._radial_top_info_progress <= 0.0:
                    self._radial_top_info_current = None

    def _radial_info_pixmap(self, key: str) -> QPixmap | None:
        if key in self._radial_info_cache:
            return self._radial_info_cache[key]
        filename = f"raidal-menu-info-{key}.png"
        path = _radial_extra_hud_dir() / filename
        if not path.is_file():
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        self._radial_info_cache[key] = pix
        return pix

    def _radial_instruction_pixmap(self, filename: str) -> QPixmap | None:
        if filename in self._radial_instruction_cache:
            return self._radial_instruction_cache[filename]
        path = _radial_extra_hud_dir() / filename
        if not path.is_file():
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        self._radial_instruction_cache[filename] = pix
        return pix

    def _draw_radial_top_info(
        self,
        painter: QPainter,
        center: QPointF,
        scale: float,
    ) -> None:
        if self._radial_top_info_progress <= 0.0 and not self._radial_top_info_crossfade:
            return

        # Topo da roda radial: center.y - 166 * scale.
        # Offset de 30px acima: a base do card fica em center.y - (166 + 30) * scale = center.y - 196 * scale.
        card_bottom_y = center.y() - 196.0 * scale

        if self._radial_top_info_crossfade:
            # Troca entre opções: crossfade suave sem escala.
            if self._radial_top_info_prev:
                pix_prev = self._radial_info_pixmap(self._radial_top_info_prev)
                if pix_prev and not pix_prev.isNull():
                    w = int(pix_prev.width() * scale)
                    h = int(pix_prev.height() * scale)
                    rect = QRectF(center.x() - w / 2, card_bottom_y - h, w, h)
                    painter.save()
                    painter.setOpacity(self._radial_top_info_prev_opacity)
                    painter.drawPixmap(rect.toRect(), pix_prev)
                    painter.restore()

            if self._radial_top_info_current:
                pix_curr = self._radial_info_pixmap(self._radial_top_info_current)
                if pix_curr and not pix_curr.isNull():
                    w = int(pix_curr.width() * scale)
                    h = int(pix_curr.height() * scale)
                    rect = QRectF(center.x() - w / 2, card_bottom_y - h, w, h)
                    painter.save()
                    curr_opacity = min(1.0, 1.0 - self._radial_top_info_prev_opacity)
                    painter.setOpacity(curr_opacity)
                    painter.drawPixmap(rect.toRect(), pix_curr)
                    painter.restore()
        else:
            # Entrada ou Saída: Fade + Scale em torno do centro do card.
            prog = self._radial_top_info_progress
            if prog <= 0.0 or not self._radial_top_info_current:
                return
            pix = self._radial_info_pixmap(self._radial_top_info_current)
            if not pix or pix.isNull():
                return
            w = int(pix.width() * scale)
            h = int(pix.height() * scale)
            card_rect = QRectF(center.x() - w / 2, card_bottom_y - h, w, h)
            card_center = card_rect.center()

            eased = prog * prog * (3.0 - 2.0 * prog)
            scale_factor = 0.8 + 0.2 * eased

            painter.save()
            painter.setOpacity(eased)
            painter.translate(card_center.x(), card_center.y())
            painter.scale(scale_factor, scale_factor)
            painter.translate(-card_center.x(), -card_center.y())
            painter.drawPixmap(card_rect.toRect(), pix)
            painter.restore()

    def _draw_radial_bottom_instructions(
        self,
        painter: QPainter,
        center: QPointF,
        scale: float,
        snapshot: OverlaySnapshot,
    ) -> None:
        progress = self._radial_progress
        if progress <= 0.0:
            return

        cfg = self.config.get()
        overlay_cfg = cfg.get("overlay", {})
        layout_cfg = str(overlay_cfg.get("controller_layout", "auto")).lower()
        if layout_cfg in ("xbox", "playstation", "nintendo"):
            controller_type = layout_cfg
        else:
            controller_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)

        if controller_type == "playstation":
            asset_name = "menu-radial-instructions-ps.png"
        elif controller_type == "nintendo":
            asset_name = "menu-radial-instructions-nintendo.png"
        else:
            asset_name = "menu-radial-instructions-xbox.png"

        pix = self._radial_instruction_pixmap(asset_name)
        if not pix or pix.isNull():
            return

        # Base da roda radial: center.y + 166 * scale.
        # Offset de 80px abaixo: topo do banner em center.y + (166 + 80) * scale = center.y + 246 * scale.
        banner_top_y = center.y() + 246.0 * scale
        w = int(pix.width() * scale)
        h = int(pix.height() * scale)
        banner_rect = QRectF(center.x() - w / 2, banner_top_y, w, h)
        banner_center = banner_rect.center()

        eased = progress * progress * (3.0 - 2.0 * progress)
        scale_factor = 0.8 + 0.2 * eased

        painter.save()
        painter.setOpacity(eased)
        painter.translate(banner_center.x(), banner_center.y())
        painter.scale(scale_factor, scale_factor)
        painter.translate(-banner_center.x(), -banner_center.y())
        painter.drawPixmap(banner_rect.toRect(), pix)
        painter.restore()
