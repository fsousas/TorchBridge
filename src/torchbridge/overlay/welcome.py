from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap

from ..models import (
    OverlaySnapshot,
    controller_type_from_name,
    resource_root,
    welcome_button_rect,
    welcome_screen_target_rect,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


def _welcome_base_dir() -> Path:
    return resource_root() / "assets" / "hud" / "boas-vindas"


class WelcomeOverlayMixin:
    """Mixin com métodos de desenho e gerenciamento visual da tela de boas-vindas (TB-17)."""

    def _welcome_page_pixmap(self, page: int) -> QPixmap | None:
        if not hasattr(self, "_welcome_pixmap_cache"):
            self._welcome_pixmap_cache: dict[str, QPixmap] = {}
        key = f"page_{page}"
        if key in self._welcome_pixmap_cache:
            return self._welcome_pixmap_cache[key]
        path = _welcome_base_dir() / "Telas" / f"{page}.png"
        if not path.is_file():
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        self._welcome_pixmap_cache[key] = pix
        return pix

    def _welcome_button_pixmap(self, company: str, btn_type: str, active: bool) -> QPixmap | None:
        if not hasattr(self, "_welcome_pixmap_cache"):
            self._welcome_pixmap_cache: dict[str, QPixmap] = {}
        state_str = "ativo" if active else "normal"
        key = f"btn_{company}_{btn_type}_{state_str}"
        if key in self._welcome_pixmap_cache:
            return self._welcome_pixmap_cache[key]

        buttons_dir = _welcome_base_dir() / "bototes"
        if btn_type == "x":
            filename = "btn-x-ativo.png" if active else "btn-x.png"
            path = buttons_dir / filename
        else:
            folder_map = {
                "nintendo": "Nintendo",
                "playstation": "Playstation",
                "xbox": "XBox",
            }
            folder_name = folder_map.get(company.lower(), "XBox")
            filename = f"btn-{btn_type}-ativo.png" if active else f"btn-{btn_type}.png"
            path = buttons_dir / folder_name / filename

        if not path.is_file():
            return None
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        self._welcome_pixmap_cache[key] = pix
        return pix

    def _draw_welcome_screen(
        self,
        painter: QPainter,
        snapshot: OverlaySnapshot,
        scale: float,
    ) -> None:
        if not snapshot.welcome_screen_open or not snapshot.game_rect.valid:
            return

        # Não exibe a tela de boas-vindas se o jogo estiver em tela de carregamento (loading),
        # em modo bloqueado, ou enquanto o estado for 'Inicializando CGame...' / 'Aguardando jogo...'
        if snapshot.memory_is_loading or snapshot.mode == "blocked":
            return

        desc = (snapshot.memory_state_desc or "").lower().strip()
        if not desc:
            return
        if any(k in desc for k in ("inicializando", "aguardando", "carregando", "loading")):
            return

        painter.save()

        # Fundo escurecido semi-transparente cobrindo toda a janela do jogo (em coordenadas locais)
        bg_rect = QRectF(0.0, 0.0, float(snapshot.game_rect.width), float(snapshot.game_rect.height))
        painter.fillRect(bg_rect, QColor(0, 0, 0, 160))

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Diálogo centralizado (convertendo para coordenadas locais do overlay)
        abs_l, abs_t, dlg_w, dlg_h = welcome_screen_target_rect(snapshot.game_rect)
        dlg_left = abs_l - snapshot.game_rect.left
        dlg_top = abs_t - snapshot.game_rect.top

        if dlg_w > 0 and dlg_h > 0:
            pix_page = self._welcome_page_pixmap(snapshot.welcome_screen_page)
            if pix_page and not pix_page.isNull():
                painter.drawPixmap(QRect(dlg_left, dlg_top, dlg_w, dlg_h), pix_page)

        # Determina a empresa do controle para renderizar os glifos corretos
        cfg = self.config.get()
        overlay_cfg = cfg.get("overlay", {})
        layout_cfg = str(overlay_cfg.get("controller_layout", "auto")).lower()
        if layout_cfg in ("xbox", "playstation", "nintendo"):
            controller_type = layout_cfg
        else:
            controller_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)
        if controller_type not in ("playstation", "nintendo", "xbox"):
            controller_type = "xbox"

        page = snapshot.welcome_screen_page
        total = snapshot.welcome_screen_total_pages
        focus = snapshot.welcome_screen_focus

        # Regras de renderização dos botões conforme a página (TB-17)
        if page == 1:
            # Página 1: apenas botão Próximo
            bx, by, bw, bh = welcome_button_rect(snapshot.game_rect, "next")
            local_bx = bx - snapshot.game_rect.left
            local_by = by - snapshot.game_rect.top
            pix_next = self._welcome_button_pixmap(controller_type, "proximo", focus == "next")
            if pix_next and not pix_next.isNull() and bw > 0 and bh > 0:
                painter.drawPixmap(QRect(local_bx, local_by, bw, bh), pix_next)
        elif page >= total:
            # Última página: Anterior e Fechar
            ax, ay, aw, ah = welcome_button_rect(snapshot.game_rect, "prev")
            local_ax = ax - snapshot.game_rect.left
            local_ay = ay - snapshot.game_rect.top
            pix_prev = self._welcome_button_pixmap(controller_type, "anterior", focus == "prev")
            if pix_prev and not pix_prev.isNull() and aw > 0 and ah > 0:
                painter.drawPixmap(QRect(local_ax, local_ay, aw, ah), pix_prev)

            cx, cy, cw, ch = welcome_button_rect(snapshot.game_rect, "close")
            local_cx = cx - snapshot.game_rect.left
            local_cy = cy - snapshot.game_rect.top
            pix_close = self._welcome_button_pixmap(controller_type, "fechar", focus == "close")
            if pix_close and not pix_close.isNull() and cw > 0 and ch > 0:
                painter.drawPixmap(QRect(local_cx, local_cy, cw, ch), pix_close)
        else:
            # Páginas intermediárias: Anterior e Próximo
            ax, ay, aw, ah = welcome_button_rect(snapshot.game_rect, "prev")
            local_ax = ax - snapshot.game_rect.left
            local_ay = ay - snapshot.game_rect.top
            pix_prev = self._welcome_button_pixmap(controller_type, "anterior", focus == "prev")
            if pix_prev and not pix_prev.isNull() and aw > 0 and ah > 0:
                painter.drawPixmap(QRect(local_ax, local_ay, aw, ah), pix_prev)

            bx, by, bw, bh = welcome_button_rect(snapshot.game_rect, "next")
            local_bx = bx - snapshot.game_rect.left
            local_by = by - snapshot.game_rect.top
            pix_next = self._welcome_button_pixmap(controller_type, "proximo", focus == "next")
            if pix_next and not pix_next.isNull() and bw > 0 and bh > 0:
                painter.drawPixmap(QRect(local_bx, local_by, bw, bh), pix_next)

        # Botão X no canto superior direito (apenas quando can_close == True)
        if snapshot.welcome_screen_can_close:
            xx, xy, xw, xh = welcome_button_rect(snapshot.game_rect, "x")
            local_xx = xx - snapshot.game_rect.left
            local_xy = xy - snapshot.game_rect.top
            pix_x = self._welcome_button_pixmap(controller_type, "x", focus == "x")
            if pix_x and not pix_x.isNull() and xw > 0 and xh > 0:
                painter.drawPixmap(QRect(local_xx, local_xy, xw, xh), pix_x)

        painter.restore()

