from __future__ import annotations

import time

from ..models import (
    OverlaySnapshot,
    pet_actions_asset_path,
)
from PySide6.QtCore import (
    QPointF,
    QRectF,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

log = logging.getLogger(__name__) if "logging" in globals() else None


class PetSubmenuOverlayMixin:
    """Mixin com métodos de desenho e animação para pet_submenu."""

    PET_SUBMENU_ICONS = ["pet-1", "pet-2", "pet-3", "pet-4"]
    PET_SUBMENU_STAGGER = 0.08
    def _tick_pet_submenu_anim(self, snapshot: OverlaySnapshot) -> None:
        target = 1.0 if snapshot.pet_submenu_open else 0.0
        now = time.monotonic()
        dt = now - getattr(self, "_pet_submenu_last_time", now)
        self._pet_submenu_last_time = now
        if abs(self._pet_submenu_progress - target) < 1e-3:
            self._pet_submenu_progress = target
        else:
            step = dt / self._pet_submenu_anim_seconds
            if target > self._pet_submenu_progress:
                self._pet_submenu_progress = min(target, self._pet_submenu_progress + step)
            else:
                self._pet_submenu_progress = max(target, self._pet_submenu_progress - step)

        # Transição de escala suave na opção selecionada (1.0 -> 1.13)
        if not hasattr(self, "_pet_item_scales") or len(self._pet_item_scales) != 4:
            self._pet_item_scales = [1.0, 1.0, 1.0, 1.0]

        sel = snapshot.pet_submenu_selection if snapshot.pet_submenu_open else getattr(self, "_last_pet_selection", None)
        transition_speed = 1.0 / 0.12  # ~120ms para transição completa
        for idx in range(4):
            target_scale = 1.13 if (sel is not None and sel == idx + 1) else 1.0
            cur = self._pet_item_scales[idx]
            if cur < target_scale:
                self._pet_item_scales[idx] = min(target_scale, cur + dt * (1.13 - 1.0) * transition_speed)
            elif cur > target_scale:
                self._pet_item_scales[idx] = max(target_scale, cur - dt * (1.13 - 1.0) * transition_speed)

    def _load_pet_actions_pixmap(self) -> QPixmap | None:
        path = pet_actions_asset_path()
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
        except Exception:  # noqa: BLE001 - sem Qt Svg o modo calibração segue sem ela.
            return None

    def _pet_icon(self, name: str) -> QPixmap | None:
        return self._radial_icon(name, False)

    def _draw_pet_submenu(
        self,
        painter: QPainter,
        point: QPointF,
        scale: float,
        selection: int | None,
        progress: float,
    ) -> None:
        if progress <= 0.0:
            return
        side = 44 * scale
        gap = 20 * scale
        top = point.y() + 50 * scale
        # Centro do 4º medalhão no eixo do nó; os demais recuam de 64 em 64 (lado+vão).
        center4_x = point.x()
        center_y = top + side / 2.0

        if not hasattr(self, "_pet_item_scales") or len(self._pet_item_scales) != 4:
            self._pet_item_scales = [
                1.13 if (selection is not None and selection == idx + 1) else 1.0
                for idx in range(4)
            ]

        # Clip com respiro generoso para acomodar a escala 1.13 da opção selecionada sem corte
        clip_top = point.y() - 30 * scale
        clip_bottom = top + side * 1.35 + 14 * scale
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setClipRect(QRectF(point.x() - 250 * scale, clip_top, 500 * scale, clip_bottom - clip_top))
        base_opacity = painter.opacity()

        stagger = self.PET_SUBMENU_STAGGER
        for i in range(4):
            # i=3 é a 4ª bolinha (debaixo do nó): janela [0, stagger]; i=0 (a 1ª):
            # janela [3*stagger, 4*stagger]. O `start` cresce conforme se afasta do nó.
            start = stagger * (3 - i)
            raw = (progress - start) / stagger
            p_i = max(0.0, min(1.0, raw))
            eased = p_i * p_i * (3.0 - 2.0 * p_i)
            # Lugar final do medalhão
            final_x = center4_x - (3 - i) * (side + gap)
            final_y = center_y
            # Partida: o CENTRO do nó P (point). Lerp radial nó → lugar final.
            cx = point.x() + (final_x - point.x()) * eased
            cy = point.y() + (final_y - point.y()) * eased
            # Fade individual por cima da opacidade herdada da roda.
            painter.setOpacity(base_opacity * (0.2 + 0.8 * eased))

            # Escala animada com transição suave (1.0 -> 1.13 na opção selecionada)
            item_scale = self._pet_item_scales[i]
            current_size = side * item_scale

            # Ícone PNG da ação desenhado diretamente (sem bordas adicionais grotescas)
            pixmap = self._pet_icon(self.PET_SUBMENU_ICONS[i])
            if pixmap is not None and not pixmap.isNull():
                painter.drawPixmap(
                    QRectF(
                        cx - current_size / 2.0,
                        cy - current_size / 2.0,
                        current_size,
                        current_size,
                    ),
                    pixmap,
                    QRectF(pixmap.rect()),
                )
        # Devolve opacidade/clip antes de fechar o painter.
        painter.setOpacity(base_opacity)
        painter.restore()
