from __future__ import annotations

import time

from ..models import (
    BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION,
    OverlaySnapshot,
    bottom_hud_asset_path,
    bottom_hud_target_rect,
    controller_type_from_name,
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

log = logging.getLogger(__name__) if "logging" in globals() else None


class BottomHudOverlayMixin:
    """Mixin com métodos de desenho e animação para bottom_hud."""

    def _get_bottom_hud_pixmap(self, controller_type: str, shortcut_active: bool = False) -> QPixmap | None:
        cache_key = f"{controller_type}_shortcut" if shortcut_active else controller_type
        if cache_key in self._bottom_hud_cache:
            return self._bottom_hud_cache[cache_key]
        path = bottom_hud_asset_path(controller_type, shortcut_active=shortcut_active)
        if path is None or not path.exists():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._bottom_hud_cache[cache_key] = pixmap
        return pixmap

    def _should_show_bottom_hud(self, snapshot: OverlaySnapshot) -> bool:
        """Determina se o HUD inferior do controle deve ser renderizado.

        Regras (assets/hud/inferior/descrição.md):
        - A HUD deve ser aplicada de forma absoluta enquanto o ESTADO for igual a EM JOGO.
        - A HUD NÃO deve ser aplicada em: DIALOG, TITLE MENU, CHARACTER SELECT,
          CUTSCENES, CHARACTER CREATE, LOADING SCREEN, OPTIONS SCREEN.
        - Menus em jogo (Inventário, Habilidades, Journal/Missões, etc.) mantêm a HUD visível.
        """
        if not snapshot.controller_connected:
            return False

        if snapshot.mode == "blocked":
            return False

        if snapshot.memory_is_loading:
            return False
        state_desc = (snapshot.memory_state_desc or "").lower()
        if any(k in state_desc for k in ("carregando", "loading")):
            return False

        if not snapshot.memory_is_in_game:
            return False

        open_menus = [m.lower() for m in (snapshot.memory_open_menus or [])]

        # 1. OPTIONS SCREEN / Configurações (ex: tela de opções de áudio/vídeo)
        # Nota: O menu de Pause (ESC em jogo) NÃO deve ocultar o HUD inferior.
        if (
            snapshot.settings_focus is not None
            or any("configura" in m or "setting" in m for m in open_menus)
            or any(k in state_desc for k in ("configura", "setting"))
        ):
            return False

        # 2. DIALOG (NPCs, conversas)
        if (
            bool(snapshot.dialog_type)
            or bool(snapshot.dialog_focus)
            or any("diálogo" in m or "dialogo" in m or "história" in m or "historia" in m for m in open_menus)
        ):
            return False

        # 3. TITLE MENU, CHARACTER SELECT, CHARACTER CREATE, CUTSCENES
        if any(
            k in state_desc
            for k in ("inicial", "criar", "dificuldade", "carregar", "cutscene", "cinematica")
        ):
            return False

        # 4. TELA DE MORTE / RESPAWN (não deve exibir o HUD inferior de controle)
        if (
            snapshot.death_screen_focus is not None
            or any("morte" in m or "respawn" in m for m in open_menus)
        ):
            return False

        return True

    def _draw_bottom_hud(self, painter: QPainter, snapshot: OverlaySnapshot) -> None:
        """Desenha o HUD inferior do controle sobre a janela do jogo."""
        cfg = self.config.get()
        overlay_cfg = cfg.get("overlay", {})
        if not overlay_cfg.get("show_bottom_hud", True):
            return

        if not self._should_show_bottom_hud(snapshot):
            return

        rect = snapshot.game_rect
        if not rect.valid:
            return

        layout_cfg = str(overlay_cfg.get("controller_layout", "auto")).lower()
        if layout_cfg in ("xbox", "playstation", "nintendo"):
            controller_type = layout_cfg
        else:
            controller_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)

        shortcut_active = bool(snapshot.shortcut_config_active)
        pixmap = self._get_bottom_hud_pixmap(controller_type, shortcut_active=shortcut_active)
        if pixmap is None or pixmap.isNull():
            return

        offset_y = float(overlay_cfg.get("bottom_hud_offset_y_percent", BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION))
        scale_hud = float(overlay_cfg.get("bottom_hud_scale", 1.0))
        hl, ht, hw, hh = bottom_hud_target_rect(rect, offset_y, scale_hud)

        local_x = hl - rect.left
        local_y = ht - rect.top

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(
            int(round(local_x)),
            int(round(local_y)),
            int(round(hw)),
            int(round(hh)),
            pixmap,
        )
        painter.restore()

    def _draw_aim(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        # Sem alvo ou com a roda aberta: não desenha a mira.
        if snapshot.aim_x is None or snapshot.aim_y is None or snapshot.radial_active:
            return
        center = QPointF(snapshot.aim_x, snapshot.aim_y)
        radius = 11 * scale
        painter.setPen(QPen(QColor(73, 224, 255, 205), max(1.5, 2.0 * scale)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)
        painter.drawLine(QPointF(center.x() - radius - 5, center.y()), QPointF(center.x() - radius + 1, center.y()))
        painter.drawLine(QPointF(center.x() + radius - 1, center.y()), QPointF(center.x() + radius + 5, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - radius - 5), QPointF(center.x(), center.y() - radius + 1))
        painter.drawLine(QPointF(center.x(), center.y() + radius - 1), QPointF(center.x(), center.y() + radius + 5))

    def _draw_mode_badge(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        cfg = self.config.get()
        # Pode ser desligado pelo perfil.
        if not cfg["overlay"].get("show_mode_badge", True):
            return
        label = "DIRETO" if snapshot.mode == "direct" else "CURSOR"
        color = QColor(69, 211, 239, 210) if snapshot.mode == "direct" else QColor(255, 191, 69, 220)
        width = 104 * scale
        height = 28 * scale
        box = QRectF(snapshot.game_rect.width - width - 16 * scale, 16 * scale, width, height)
        painter.setPen(QPen(color, 1.2 * scale))
        painter.setBrush(QColor(3, 10, 16, 185))
        painter.drawRoundedRect(box, 8 * scale, 8 * scale)
        painter.setFont(self._font(max(8, round(9 * scale)), True))
        painter.setPen(QColor(230, 245, 248, 235))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, f"MODO {label}")

    def _draw_active_panels(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        # Índice 0 = lado esquerdo (C/P), 1 = direito (I/S/Q/J); tolera listas curtas.
        left, right = (list(snapshot.active_panels) + ["", ""])[:2]
        # Ambos os lados vazios: nada a indicar — mantém a tela limpa (só aparece com painel aberto).
        if not left and not right:
            return
        text = f"{left or '·'} | {right or '·'}"
        painter.setFont(self._font(max(7, round(8 * scale)), True))
        metrics = painter.fontMetrics()
        padding = 8 * scale
        height = 16 * scale
        width = metrics.horizontalAdvance(text) + padding * 2
        box = QRectF((snapshot.game_rect.width - width) / 2, 4 * scale, width, height)
        painter.setPen(QPen(QColor(87, 218, 244, 130), 1.0 * scale))
        painter.setBrush(QColor(3, 10, 16, 165))
        painter.drawRoundedRect(box, 8 * scale, 8 * scale)
        painter.setPen(QColor(220, 242, 248, 210))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_toast(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        import time

        # Texto vazio ou expirado: nada a desenhar.
        if not snapshot.toast_text or snapshot.toast_until <= time.monotonic():
            return
        width = min(snapshot.game_rect.width - 40 * scale, max(260 * scale, len(snapshot.toast_text) * 8.4 * scale))
        height = 44 * scale
        box = QRectF((snapshot.game_rect.width - width) / 2, 22 * scale, width, height)
        painter.setPen(QPen(QColor(87, 218, 244, 210), 1.3 * scale))
        painter.setBrush(QColor(2, 9, 14, 222))
        painter.drawRoundedRect(box, 12 * scale, 12 * scale)
        painter.setFont(self._font(max(9, round(11 * scale)), True))
        painter.setPen(QColor(235, 248, 251))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, snapshot.toast_text)
