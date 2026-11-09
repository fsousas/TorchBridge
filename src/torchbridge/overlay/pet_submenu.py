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

    PET_SUBMENU_ICONS = ["pet-seller.png", "pet-passive.png", "pet-defensive.png", "pet-agressive.png"]
    PET_SUBMENU_STAGGER = 0.08
    def _tick_pet_submenu_anim(self, snapshot: OverlaySnapshot) -> None:
        target = 1.0 if snapshot.pet_submenu_open else 0.0
        now = time.monotonic()
        dt = now - self._pet_submenu_last_time
        self._pet_submenu_last_time = now
        if abs(self._pet_submenu_progress - target) < 1e-3:
            self._pet_submenu_progress = target
            return
        step = dt / self._pet_submenu_anim_seconds
        if target > self._pet_submenu_progress:
            self._pet_submenu_progress = min(target, self._pet_submenu_progress + step)
        else:
            self._pet_submenu_progress = max(target, self._pet_submenu_progress - step)

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
        # Centro do 4º círculo no eixo do nó; os demais recuam de 64 em 64 (lado+vão).
        center4_x = point.x()
        center_y = top + side / 2.0
        # O ícone (31x31) entra no círculo com leve respiro: 78% do diâmetro.
        icon_size = side * 0.78
        # Clip: a sublinha é visível num retângulo de ALTURA DOBRADA em relação ao
        # antigo (~118px em 1080p: do ponto.y() - 24 até o fim da fileira). O topo
        # fica 2px ACIMA do topo da bolinha parada no centro do nó (raio 22) — assim
        # a bolinha já nasce INTEIRA, sem a fatia/achatamento que o clip antigo
        # (point.y() + 44) causava quando as bolinhas entravam (bug visto no jogo,
        # ago/2026: "as bolinhas entram cortadas"). Como o desenho da sublinha
        # acontece DEPOIS dos nós/ícones, a bolinha voa POR CIMA do ícone da opção P
        # saindo dele redonda — é isso que vende o "sair de dentro do menu".
        clip_top = point.y() - 24 * scale
        clip_bottom = top + side + 8 * scale
        painter.save()
        painter.setClipRect(QRectF(point.x() - 220 * scale, clip_top, 440 * scale, clip_bottom - clip_top))
        base_opacity = painter.opacity()
        # Cada bolinha tem uma JANELA de progresso [start, start + stagger] dentro
        # do 0→1 global: parte do nó e chega ao destino no fim da janela. As 4
        # janelas encadeiam sem sobrepor nem folga (25% cada, 75ms a 0.3s): a 4ª
        # (a mais perto do nó) viaja em [0, 0.25], a 3ª em [0.25, 0.5], a 2ª em
        # [0.5, 0.75], a 1ª em [0.75, 1.0] — chegada a cada 75ms, a mais distante
        # por último. Na saída, o progresso desce e a ordem inverte de graça.
        stagger = self.PET_SUBMENU_STAGGER
        for i in range(4):
            # i=3 é a 4ª bolinha (debaixo do nó): janela [0, stagger]; i=0 (a 1ª):
            # janela [3*stagger, 4*stagger]. O `start` cresce conforme se afasta do nó.
            start = stagger * (3 - i)
            raw = (progress - start) / stagger
            p_i = max(0.0, min(1.0, raw))
            eased = p_i * p_i * (3.0 - 2.0 * p_i)
            # Lugar final da bolinha (mesma fileira desenhada sem animação).
            final_x = center4_x - (3 - i) * (side + gap)
            final_y = center_y
            # Partida: o CENTRO do nó P (point). Lerp radial nó → lugar final.
            cx = point.x() + (final_x - point.x()) * eased
            cy = point.y() + (final_y - point.y()) * eased
            # Fade individual por cima da opacidade herdada da roda.
            painter.setOpacity(base_opacity * (0.2 + 0.8 * eased))
            if selection is not None and i + 1 == selection:
                # Marcador do círculo ativo: dourado, igual à cor do nó selecionado da roda.
                painter.setPen(QPen(QColor(255, 202, 82, 255), 3.0 * scale))
                painter.setBrush(QColor(24, 28, 34, 235))
            else:
                painter.setPen(QPen(QColor(232, 234, 238, 235), 2.0 * scale))
                painter.setBrush(QColor(216, 219, 224, 242))
            painter.drawEllipse(QPointF(cx, cy), side / 2.0, side / 2.0)
            # Ícone da ação centralizado no círculo (fallback: sem PNG, só o círculo).
            pixmap = self._pet_icon(self.PET_SUBMENU_ICONS[i])
            if pixmap is not None:
                painter.drawPixmap(
                    QRectF(cx - icon_size / 2.0, cy - icon_size / 2.0, icon_size, icon_size),
                    pixmap,
                    QRectF(pixmap.rect()),
                )
        # Devolve opacidade/clip antes de fechar o painter.
        painter.setOpacity(base_opacity)
        painter.restore()
