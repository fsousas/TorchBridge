from __future__ import annotations

import time

from ..models import (
    OverlaySnapshot,
    SHORTCUT_HUD_NODES,
    controller_type_from_name,
    shortcut_config_info_asset_path,
    shortcut_config_info_tooltip_asset_path,
    shortcut_grid_cell_point,
    shortcut_info_node_point,
    shortcut_instruction_asset_path,
)
from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
)

log = logging.getLogger(__name__) if "logging" in globals() else None


class ShortcutConfigOverlayMixin:
    """Mixin com métodos de desenho e animação para shortcut_config."""

    def _tick_shortcut_mode_anim(self, snapshot: OverlaySnapshot) -> None:
        now = time.monotonic()
        dt = now - self._shortcut_anim_last_time
        self._shortcut_anim_last_time = now

        # Animação de descida/subida da aba config-info
        target = 1.0 if snapshot.shortcut_config_active else 0.0
        if abs(self._shortcut_anim_progress - target) < 1e-3:
            self._shortcut_anim_progress = target
        else:
            step = dt / self._shortcut_anim_seconds
            if target > self._shortcut_anim_progress:
                self._shortcut_anim_progress = min(target, self._shortcut_anim_progress + step)
            else:
                self._shortcut_anim_progress = max(target, self._shortcut_anim_progress - step)

        # Animação de fade-in/fade-out do tooltip (quando focado na aba e grid fechado)
        tooltip_target = (
            1.0
            if snapshot.shortcut_config_active
            and snapshot.shortcut_info_focus
            and not snapshot.shortcut_grid_active
            else 0.0
        )
        if abs(self._shortcut_tooltip_opacity - tooltip_target) < 1e-3:
            self._shortcut_tooltip_opacity = tooltip_target
        else:
            tooltip_step = dt / 0.18
            if tooltip_target > self._shortcut_tooltip_opacity:
                self._shortcut_tooltip_opacity = min(tooltip_target, self._shortcut_tooltip_opacity + tooltip_step)
            else:
                self._shortcut_tooltip_opacity = max(tooltip_target, self._shortcut_tooltip_opacity - tooltip_step)

    def _draw_shortcut_spotlight(self, painter: QPainter, snapshot: OverlaySnapshot) -> None:
        """Backdrop escuro desativado conforme solicitado."""
        return

    def _get_shortcut_instruction_pixmap(self, controller_type: str) -> QPixmap | None:
        cached = self._shortcut_instruction_cache.get(controller_type)
        if cached is not None:
            return cached
        path = shortcut_instruction_asset_path(controller_type)
        if path is None or not path.is_file():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._shortcut_instruction_cache[controller_type] = pixmap
        return pixmap

    def _get_config_info_pixmap(self) -> QPixmap | None:
        if self._config_info_pixmap is not None:
            return self._config_info_pixmap
        path = shortcut_config_info_asset_path()
        if path is None or not path.is_file():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._config_info_pixmap = pixmap
        return pixmap

    def _get_config_info_tooltip_pixmap(self, controller_type: str) -> QPixmap | None:
        cached = self._config_info_tooltip_cache.get(controller_type)
        if cached is not None:
            return cached
        path = shortcut_config_info_tooltip_asset_path(controller_type)
        if path is None or not path.is_file():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._config_info_tooltip_cache[controller_type] = pixmap
        return pixmap

    def _draw_shortcut_instruction(self, painter: QPainter, snapshot: OverlaySnapshot) -> None:
        if snapshot.memory_state_desc and not snapshot.memory_is_in_game:
            return
        progress = self._shortcut_anim_progress
        if progress <= 0.0:
            return

        rect = snapshot.game_rect
        w = int(rect.width) if rect.valid and rect.width > 0 else self.width()
        h = int(rect.height) if rect.valid and rect.height > 0 else self.height()
        if w <= 0 or h <= 0:
            return

        # Escala proporcional com base na resolução de referência (1280x960)
        scale = h / 960.0

        info_pixmap = self._get_config_info_pixmap()
        if info_pixmap is not None and not info_pixmap.isNull():
            bw = int(round(217.0 * scale))
            bh = int(round(68.0 * scale))
            bx = int(round((w - bw) / 2.0))
            target_y = 0
            start_y = -bh - 10

            # Animação suave com desaceleração (cubic ease-out na descida, suave na subida)
            ease = 1.0 - (1.0 - progress) ** 3
            by = int(round(start_y + (target_y - start_y) * ease))

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(bx, by, bw, bh, info_pixmap)
            painter.restore()

            # Tooltip de layout do controle (506 x 308) - renderizado logo abaixo da aba com fade
            if self._shortcut_tooltip_opacity > 0.0:
                cfg = self.config.get()
                overlay_cfg = cfg.get("overlay", {})
                layout_cfg = str(overlay_cfg.get("controller_layout", "auto")).lower()
                if layout_cfg in ("xbox", "playstation", "nintendo"):
                    controller_type = layout_cfg
                else:
                    controller_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)

                tooltip_pixmap = self._get_config_info_tooltip_pixmap(controller_type)
                if tooltip_pixmap is not None and not tooltip_pixmap.isNull():
                    tw = int(round(506.0 * scale))
                    th = int(round(308.0 * scale))
                    tx = int(round((w - tw) / 2.0))
                    ty = by + bh  # Posicionado logo abaixo da aba

                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    painter.setOpacity(self._shortcut_tooltip_opacity)
                    painter.drawPixmap(tx, ty, tw, th, tooltip_pixmap)
                    painter.restore()
        else:
            # Fallback para o banner de instruções antigo caso config-info.png não exista
            cfg = self.config.get()
            overlay_cfg = cfg.get("overlay", {})
            layout_cfg = str(overlay_cfg.get("controller_layout", "auto")).lower()
            if layout_cfg in ("xbox", "playstation", "nintendo"):
                controller_type = layout_cfg
            else:
                controller_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)

            pixmap = self._get_shortcut_instruction_pixmap(controller_type)
            if pixmap is not None and not pixmap.isNull():
                bw = int(round(571.0 * scale))
                bh = int(round(806.0 * scale))
                bx = int(round((w - bw) / 2.0))
                target_y = (h - bh) / 2.0 - bh * 0.40
                start_y = -bh - 40
                ease = 1.0 - (1.0 - progress) ** 3
                by = int(round(start_y + (target_y - start_y) * ease))

                painter.save()
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawPixmap(bx, by, bw, bh, pixmap)
                painter.restore()

    def _draw_shortcut_nodes(self, painter: QPainter, snapshot: OverlaySnapshot) -> None:
        cfg = self.config.get()
        if not cfg.get("overlay", {}).get("show_calibration", False):
            return
        # Os nós de calibração da HUD de atalhos só devem aparecer no modo EM JOGO
        # e estritamente quando o modo de configuração de teclas de atalho estiver ativo.
        if (snapshot.memory_state_desc and not snapshot.memory_is_in_game) or not snapshot.shortcut_config_active:
            return
        rect = snapshot.game_rect
        w = int(rect.width) if rect.valid and rect.width > 0 else self.width()
        h = int(rect.height) if rect.valid and rect.height > 0 else self.height()
        if w <= 0 or h <= 0:
            return

        scale = h / 960.0
        c_amarelo = QColor(0xE6, 0xC1, 0x2A)
        c_verde = QColor(0x09, 0xB2, 0x00)

        # Se o grid de opções estiver ativo, desenha as células do grid (modo calibração)
        if snapshot.shortcut_grid_active:
            painter.save()
            sel_r, sel_c = snapshot.shortcut_grid_pos
            cell_box = 18.0 * scale
            for r in range(snapshot.shortcut_grid_rows):
                items_in_row = (
                    snapshot.shortcut_grid_counts[r]
                    if r < len(snapshot.shortcut_grid_counts)
                    else snapshot.shortcut_grid_cols
                )
                for c in range(items_in_row):
                    cx, cy = shortcut_grid_cell_point(
                        rect,
                        snapshot.shortcut_node_focus,
                        r,
                        c,
                        snapshot.shortcut_grid_cols,
                        snapshot.shortcut_grid_rows,
                    )
                    lx = cx - rect.left - cell_box / 2.0
                    ly = cy - rect.top - cell_box / 2.0
                    is_focus = (r == sel_r and c == sel_c)
                    if is_focus:
                        painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                        painter.setBrush(QColor(230, 193, 42, 230))
                    else:
                        painter.setPen(QPen(c_verde, 1.5 * scale))
                        painter.setBrush(QColor(9, 178, 0, 140))
                    painter.drawRoundedRect(QRectF(lx, ly, cell_box, cell_box), 2.0 * scale, 2.0 * scale)
            painter.restore()
            return

        mw = 948.0 * scale
        mh = 171.0 * scale
        mx = (w - mw) / 2.0
        my = h - mh

        progress = self._shortcut_anim_progress if snapshot.shortcut_config_active else 1.0
        painter.save()
        painter.setOpacity(progress)
        box_sz = 15.0 * scale

        # Nó da aba superior de informações (config-info.png)
        top_cx, top_cy = shortcut_info_node_point(rect)
        top_lx = top_cx - rect.left
        top_ly = top_cy - rect.top
        top_rect = QRectF(top_lx - box_sz / 2.0, top_ly - box_sz / 2.0, box_sz, box_sz)
        if snapshot.shortcut_info_focus:
            painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
            painter.setBrush(QColor(230, 193, 42, 230))
        else:
            painter.setPen(QPen(c_verde, 1.5 * scale))
            painter.setBrush(QColor(c_verde.red(), c_verde.green(), c_verde.blue(), 170))
        painter.drawRoundedRect(top_rect, 2.0 * scale, 2.0 * scale)

        for idx, col_name, base_x, base_y in SHORTCUT_HUD_NODES:
            lx = mx + base_x * scale
            ly = my + base_y * scale
            node_rect = QRectF(lx - box_sz / 2.0, ly - box_sz / 2.0, box_sz, box_sz)

            is_focus = (snapshot.shortcut_node_focus == idx and not snapshot.shortcut_info_focus)
            base_col = c_amarelo if col_name == "yellow" else c_verde

            if is_focus:
                # Destaque no nó selecionado: borda branca brilhante e fundo amarelo vivo
                painter.setPen(QPen(QColor(255, 255, 255, 255), 2.5 * scale))
                painter.setBrush(QColor(230, 193, 42, 230))
            else:
                painter.setPen(QPen(base_col, 1.5 * scale))
                painter.setBrush(QColor(base_col.red(), base_col.green(), base_col.blue(), 170))

            painter.drawRoundedRect(node_rect, 2.0 * scale, 2.0 * scale)

        painter.restore()
