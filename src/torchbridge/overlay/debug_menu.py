from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from ..models import (
    DEBUG_MENU_ITEMS,
    OverlaySnapshot,
    controller_type_from_name,
)
from ..resources import resource_root

log = logging.getLogger(__name__)


class DebugMenuOverlayMixin:
    """Mixin para renderização visual do Painel de Debug interativo baseado em assets."""

    def _debug_menu_pixmap(self, filename: str) -> QPixmap | None:
        """Carrega e armazena em cache os pixmaps do menu de debug."""
        if not hasattr(self, "_debug_menu_cache"):
            self._debug_menu_cache: dict[str, QPixmap | None] = {}
        if filename not in self._debug_menu_cache:
            path = resource_root() / "assets" / "hud" / "debug menu" / filename
            if path.is_file():
                pix = QPixmap(str(path))
                self._debug_menu_cache[filename] = pix if not pix.isNull() else None
            else:
                self._debug_menu_cache[filename] = None
        return self._debug_menu_cache[filename]

    def _draw_debug_menu(
        self,
        painter: QPainter,
        snapshot: OverlaySnapshot,
        scale: float,
    ) -> None:
        """Desenha o Painel de Debug com background temático, checkboxes, scrollbar e prompts de controle."""
        if not getattr(snapshot, "debug_menu_open", False):
            return

        rect = snapshot.game_rect
        if not rect.valid or rect.width <= 0 or rect.height <= 0:
            return

        # Dimensões base do quadro.png: 603x817
        modal_scale = min(scale, (rect.height * 0.92) / 817.0, (rect.width * 0.90) / 603.0)
        card_w = 603.0 * modal_scale
        card_h = 817.0 * modal_scale
        card_x = (rect.width - card_w) / 2.0
        card_y = (rect.height - card_h) / 2.0

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        def draw_asset(target_rect: QRectF, name: str) -> None:
            pix = self._debug_menu_pixmap(name)
            if pix is not None and not pix.isNull():
                painter.drawPixmap(target_rect, pix, QRectF(pix.rect()))

        # 1. Quadro de fundo (quadro.png)
        draw_asset(QRectF(card_x, card_y, card_w, card_h), "quadro.png")

        # 2. Barra de Rolagem (scroll-bar.png)
        draw_asset(
            QRectF(
                card_x + 561.0 * modal_scale,
                card_y + 202.0 * modal_scale,
                30.0 * modal_scale,
                505.0 * modal_scale,
            ),
            "scroll-bar.png",
        )

        # 3. Indicador de Rolagem / Gema vermelha (scroll-indicator.png)
        total_checkboxes = len(DEBUG_MENU_ITEMS)
        visible_rows = 10
        max_scroll = max(0, total_checkboxes - visible_rows)
        raw_scroll = getattr(snapshot, "debug_menu_scroll", 0)
        scroll = max(0, min(raw_scroll, max_scroll))
        scroll_pct = (float(scroll) / float(max_scroll)) if max_scroll > 0 else 0.0
        # O trilho útil percorre de y=228 a y=649 (curso de 421px)
        indicator_y = 228.0 + scroll_pct * 421.0
        draw_asset(
            QRectF(
                card_x + 563.5 * modal_scale,
                card_y + indicator_y * modal_scale,
                25.0 * modal_scale,
                32.0 * modal_scale,
            ),
            "scroll-indicator.png",
        )

        # 4. Linhas de Checkboxes com suporte a Scroll
        raw_focus = getattr(snapshot, "debug_menu_focus", 0)
        current_focus = max(0, min(raw_focus, total_checkboxes))
        font_size = max(8, round(11.5 * modal_scale))
        font = getattr(
            self,
            "_font",
            lambda sz, b=False: QFont("Segoe UI", sz, QFont.Weight.Bold if b else QFont.Weight.Normal),
        )(font_size, True)
        painter.setFont(font)

        for i in range(min(visible_rows, total_checkboxes)):
            item_idx = scroll + i
            if item_idx >= total_checkboxes:
                break
            attr_key, label_text = DEBUG_MENU_ITEMS[item_idx]
            is_focused = (current_focus == item_idx)
            is_checked = bool(getattr(snapshot, attr_key, False))
            slot_y = card_y + (208.0 + i * 49.0) * modal_scale

            # Destaque de linha em foco (hover.png)
            if is_focused:
                draw_asset(
                    QRectF(
                        card_x + 99.0 * modal_scale,
                        card_y + (208.0 + i * 49.0 + 5.0) * modal_scale,
                        437.0 * modal_scale,
                        30.0 * modal_scale,
                    ),
                    "hover.png",
                )

            # Ícone de checkbox (check-on.png / check-off.png)
            chk_name = "check-on.png" if is_checked else "check-off.png"
            draw_asset(
                QRectF(
                    card_x + 46.0 * modal_scale,
                    slot_y,
                    53.0 * modal_scale,
                    40.0 * modal_scale,
                ),
                chk_name,
            )

            # Rótulo de texto da opção com sombra suave
            text_rect = QRectF(
                card_x + 112.0 * modal_scale,
                slot_y,
                420.0 * modal_scale,
                40.0 * modal_scale,
            )
            painter.setPen(QColor(0, 0, 0, 220))
            painter.drawText(
                text_rect.translated(1.5 * modal_scale, 1.5 * modal_scale),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label_text,
            )
            text_color = QColor(255, 255, 255) if is_focused else QColor(220, 220, 220)
            painter.setPen(text_color)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label_text,
            )

        # 5. Botão Selecionável "Fechar" (btn-on.png se focado, senão btn-off.png)
        close_is_focused = (current_focus == total_checkboxes)
        close_btn_asset = "btn-on.png" if close_is_focused else "btn-off.png"
        draw_asset(
            QRectF(
                card_x + 193.0 * modal_scale,
                card_y + 721.0 * modal_scale,
                220.0 * modal_scale,
                40.0 * modal_scale,
            ),
            close_btn_asset,
        )

        # 6. Ícones de controle no rodapé (D-Pad e Confirmar / Interagir)
        controller_family = "xbox"
        if hasattr(self, "_interaction_family") and hasattr(self, "config"):
            try:
                controller_family = self._interaction_family(self.config.get(), snapshot)
            except Exception:
                pass
        if controller_family not in ("xbox", "playstation", "nintendo"):
            ctrl_type = (
                getattr(snapshot, "controller_type", "")
                or controller_type_from_name(getattr(snapshot, "controller_name", ""))
            )
            controller_family = ctrl_type if ctrl_type in ("xbox", "playstation", "nintendo") else "xbox"

        draw_asset(
            QRectF(
                card_x + 118.0 * modal_scale,
                card_y + 783.0 * modal_scale,
                24.0 * modal_scale,
                24.0 * modal_scale,
            ),
            f"dpad-up-{controller_family}.png",
        )

        draw_asset(
            QRectF(
                card_x + 364.0 * modal_scale,
                card_y + 784.0 * modal_scale,
                22.0 * modal_scale,
                22.0 * modal_scale,
            ),
            f"interact-{controller_family}.png",
        )

        painter.restore()
