"""Proximity prompt drawn by the shared Qt/Wayland/D3D9 painter."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from ..models import OverlaySnapshot, Rect, controller_type_from_name
from ..resources import resource_root
from ..world import INTERACTION_LABELS, WorldCamera, WorldEntity, WorldPosition


class WorldInteractionOverlayMixin:
    def _interaction_icon(self, family: str, face_button: bool) -> QPixmap | None:
        filename = f"{'interact' if face_button else 'dpad-up'}-{family}.png"
        if filename not in self._interaction_icon_cache:
            image = QPixmap(str(resource_root() / "assets/hud/general" / filename))
            self._interaction_icon_cache[filename] = image
        image = self._interaction_icon_cache[filename]
        return None if image.isNull() else image

    def _interaction_family(self, config: dict, snapshot: OverlaySnapshot) -> str:
        layout = str(config["overlay"].get("controller_layout", "auto")).lower()
        family = (layout if layout in ("xbox", "playstation", "nintendo") else
                  snapshot.controller_type or controller_type_from_name(snapshot.controller_name))
        return family if family in ("xbox", "playstation", "nintendo") else controller_type_from_name(family)

    def _draw_native_interaction_icon(self, painter: QPainter, snapshot: OverlaySnapshot,
                                      target: WorldEntity, scale: float, config: dict) -> bool:
        rect = target.native_label_rect
        if (target.kind == "npc" or target.uses_face_button or snapshot.interaction_button != "dpad_up"
                or rect is None or len(rect) != 4 or not all(math.isfinite(v) for v in rect)):
            return False
        left, top, right, bottom = rect
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            return False
        left *= snapshot.game_rect.width
        middle = (top + bottom) * snapshot.game_rect.height / 2
        icon = self._interaction_icon(self._interaction_family(config, snapshot), False)
        height, gap = 24 * scale, 6 * scale
        painter.save()
        if icon is not None:
            width = height * icon.width() / icon.height()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(QRectF(left - width - gap, middle - height / 2, width, height),
                               icon, QRectF(icon.rect()))
        else:
            painter.setFont(self._font(max(8, round(10 * scale)), True))
            painter.setPen(QColor(255, 240, 210))
            width = painter.fontMetrics().horizontalAdvance("[D-pad ↑]")
            painter.drawText(QRectF(left - width - gap, middle - height / 2, width, height),
                             Qt.AlignmentFlag.AlignVCenter, "[D-pad ↑]")
        painter.restore()
        return True

    def _draw_world_interaction(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        config = self.config.get()
        cfg = config["interaction"]
        if (not snapshot.enabled or not snapshot.game_active or not snapshot.controller_connected
                or not snapshot.memory_is_in_game or snapshot.memory_is_loading
                or snapshot.memory_is_menu_open or snapshot.memory_open_menus
                or snapshot.radial_active or any(snapshot.active_panels)
                or snapshot.shortcut_config_active or snapshot.virtual_keyboard_open
                or snapshot.mode != "direct" or not cfg["enabled"]):
            return
        world = snapshot.world
        if not world.fresh(time.monotonic()):
            return
        target = snapshot.interaction_target
        if cfg["show_prompt"] and target is not None:
            native_prompt = self._draw_native_interaction_icon(painter, snapshot, target, scale, config)
            point = (world.camera.project(target.position, snapshot.game_rect.width,
                                          snapshot.game_rect.height, 1.6)
                     if not native_prompt and world.camera is not None else None)
            if point is not None:
                distance = world.player_position.distance_to(target.position)
                family = self._interaction_family(config, snapshot)
                icon = (self._interaction_icon(family, target.uses_face_button)
                        if target.uses_face_button or snapshot.interaction_button == "dpad_up" else None)
                button = (("×" if family == "playstation" else "A") if target.uses_face_button else
                          INTERACTION_LABELS.get(snapshot.interaction_button, "D-pad ↑"))
                name = target.name or target.label
                if target.npc_role or target.quest_status:
                    name = f"{target.label}: {name}"
                text = name
                if icon is None:
                    text = f"[{button}] {text}"
                painter.save()
                painter.setFont(self._font(max(8, round(10 * scale)), True))
                padding, gap = 12 * scale, 8 * scale if icon is not None else 0
                icon_height = 24 * scale if icon is not None else 0
                icon_width = icon_height * icon.width() / icon.height() if icon is not None else 0
                leading = icon_width + gap
                max_width = max(1, min(360 * scale, snapshot.game_rect.width - 16))
                suffix = f" · {distance:.1f}"
                text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight,
                    max(1, int(max_width - padding * 2 - leading
                               - painter.fontMetrics().horizontalAdvance(suffix)))) + suffix
                width = min(max_width, painter.fontMetrics().horizontalAdvance(text) + padding * 2 + leading)
                height = 32 * scale
                left = max(8, min(point[0] - width / 2, snapshot.game_rect.width - width - 8))
                top = max(8, min(point[1] - height - 12 * scale, snapshot.game_rect.height - height - 8))
                box = QRectF(left, top, width, height)
                painter.setPen(QPen(QColor(225, 184, 104, 230), 1.2))
                painter.setBrush(QColor(20, 17, 14, 225))
                painter.drawRoundedRect(box, 8 * scale, 8 * scale)
                painter.setClipRect(box, Qt.ClipOperation.IntersectClip)
                if icon is not None:
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                    painter.drawPixmap(QRectF(left + padding, top + (height - icon_height) / 2,
                                              icon_width, icon_height), icon, QRectF(icon.rect()))
                painter.setPen(QColor(255, 240, 210))
                painter.drawText(QRectF(left + padding + leading, top,
                                        max(1, width - padding * 2 - leading), height),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
                painter.restore()
        if cfg["show_positions"] and not config["overlay"]["show_calibration"]:
            player = world.player_position
            lines = [f"{world.level_name or 'Cenário'} · X {player.x:.2f}  Y {player.y:.2f}",
                     f"{len(world.entities)} elementos · {world.status}"]
            for entity in world.nearby(cfg["radius"])[:5]:
                lines.append(f"{entity.label}: {entity.name or entity.identifier}  "
                             f"({entity.position.x:.1f}, {entity.position.y:.1f})")
            painter.save()
            painter.setFont(self._font(max(8, round(9 * scale))))
            width = min(460 * scale, max(1, snapshot.game_rect.width - 32))
            height = (len(lines) * 22 + 16) * scale
            box = QRectF(16 * scale, 70 * scale, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(12, 14, 18, 220))
            painter.drawRoundedRect(box, 6, 6)
            painter.setPen(QColor(235, 235, 235))
            for i, line in enumerate(lines):
                text = painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, max(1, int(width - 16)))
                painter.drawText(QRectF(box.left() + 8, box.top() + (8 + i * 22) * scale,
                                        width - 16, 22 * scale), Qt.AlignmentFlag.AlignLeft, text)
            painter.restore()

    def _draw_world_calibration(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        config = self.config.get()
        rect = snapshot.game_rect
        if (not config["overlay"]["show_calibration"] or not snapshot.enabled
                or not snapshot.game_found or not snapshot.game_active or not rect.valid
                or not (snapshot.memory_is_in_game or snapshot.memory_is_loading)):
            return
        world = snapshot.world
        fresh = not snapshot.memory_is_loading and world.fresh(time.monotonic())
        player = world.player_position if fresh else None
        cfg = config["interaction"]
        lines = [f"POSICIONAMENTO · {world.level_name or 'Cenário'}"]
        if snapshot.movement_status:
            dx, dz = snapshot.movement_direction
            tx, tz = snapshot.movement_destination
            lines.extend([
                f"Movimento seguro: {snapshot.movement_status}",
                f"Direção: {dx:.2f}, {dz:.2f} · Destino: {tx:.2f}, {tz:.2f}",
                f"Highlight: {'ativo' if snapshot.native_highlight else 'inativo'} · "
                f"Bloqueios: {snapshot.blocked_interactions} usos / {snapshot.blocked_warps} transições",
            ])
        painter.save()
        try:
            painter.setFont(self._font(max(8, round(9 * scale))))
            if player is not None:
                nearby = {entity.address for entity in world.nearby(cfg["radius"])}
                camera = world.camera
                target = snapshot.interaction_target
                visible = 0
                if camera is not None:
                    # Project the range on the same ground plane as the player.
                    painter.setPen(QPen(QColor(95, 230, 140, 160), 1.5 * scale, Qt.PenStyle.DashLine))
                    self._draw_world_radius(painter, camera, rect, player, cfg["radius"])
                    painter.setPen(QPen(QColor(255, 170, 90, 160), 1.5 * scale, Qt.PenStyle.DashLine))
                    self._draw_world_radius(painter, camera, rect, player, cfg["radius"] * 2)
                    for entity in world.entities:
                        if entity.kind == "fishing":
                            painter.setPen(QPen(QColor(120, 215, 255, 160), 1.5 * scale, Qt.PenStyle.DashLine))
                            self._draw_world_radius(painter, camera, rect, entity.position, entity.action_radius(0))
                        point = camera.project(entity.position, rect.width, rect.height)
                        if point is None:
                            continue
                        visible += 1
                        selected = target is not None and entity.address == target.address
                        color = QColor(255, 215, 105) if selected else (
                            QColor(95, 230, 140) if entity.address in nearby else QColor(90, 195, 250))
                        label = f"{entity.label}: {entity.name or entity.identifier or entity.label}"
                        details = (f"X {entity.position.x:.2f}  Y {entity.position.y:.2f}  "
                                   f"dist. {player.distance_to(entity.position):.2f}")
                        self._draw_world_marker(painter, rect, point, label, details, color, scale)
                    point = camera.project(player, rect.width, rect.height)
                    if point is not None:
                        self._draw_world_marker(painter, rect, point, "Jogador",
                                                f"X {player.x:.2f}  Y {player.y:.2f}",
                                                QColor(255, 135, 235), scale, below=True)
                lines.extend([
                    f"Jogador: X {player.x:.2f}  Y {player.y:.2f}  altura {player.height:.2f}",
                    f"{len(world.entities)} elementos · {len(nearby)} próximos · {visible} visíveis",
                    f"Raio: {cfg['radius']:.1f} · {world.status}",
                    f"Destrutíveis: raio {cfg['radius'] * 2:.1f} (laranja) · Pesca: círculo azul",
                    "Verde: próximo · Azul: distante · Amarelo: alvo",
                ])
                merchants = sum(entity.is_merchant for entity in world.entities)
                quests = sum(entity.kind == "npc" and entity.quest_status not in ("", "unknown")
                             for entity in world.entities)
                if merchants or quests:
                    lines.append(f"Mercadores: {merchants} · NPCs com missão: {quests}")
                if camera is None:
                    lines.append("Câmera indisponível: marcadores não projetados")
                # Include distant/offscreen elements too; the panel is for inspection,
                # independent of cursor mode, input enablement and proximity prompts.
                entities = sorted((e for e in world.entities if e.position.valid),
                                  key=lambda e: (player.distance_to(e.position), e.address))
                for entity in entities[:5]:
                    lines.append(f"{entity.label}: {entity.name or entity.identifier} · "
                                 f"X {entity.position.x:.1f}  Y {entity.position.y:.1f} · "
                                 f"dist. {player.distance_to(entity.position):.1f}")
                if len(entities) > 5:
                    lines.append(f"Mais {len(entities) - 5} elementos no cenário")
            else:
                lines.append("Carregando cenário..." if snapshot.memory_is_loading
                             else "Posições indisponíveis ou desatualizadas")
                lines.append(world.status)
            self._draw_world_calibration_panel(painter, rect, lines, scale)
        finally:
            painter.restore()

    def _draw_world_radius(self, painter: QPainter, camera: WorldCamera, rect: Rect,
                           center: WorldPosition, radius: float) -> None:
        previous = None
        for i in range(65):
            angle = i * math.tau / 64
            position = WorldPosition(center.x + math.cos(angle) * radius,
                                     center.y + math.sin(angle) * radius, center.height)
            point = camera.project(position, rect.width, rect.height)
            if previous is not None and point is not None:
                painter.drawLine(QPointF(*previous), QPointF(*point))
            previous = point

    def _draw_world_marker(self, painter: QPainter, rect: Rect, point: tuple[int, int],
                           label: str, details: str, color: QColor, scale: float, *, below: bool = False) -> None:
        x, y = point
        radius = 6 * scale
        painter.setPen(QPen(color, 2 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.drawLine(QPointF(x - radius - 3, y), QPointF(x + radius + 3, y))
        painter.drawLine(QPointF(x, y - radius - 3), QPointF(x, y + radius + 3))
        metrics = painter.fontMetrics()
        width = min(max(metrics.horizontalAdvance(label), metrics.horizontalAdvance(details)) + 16 * scale,
                    360 * scale, max(1, rect.width - 16))
        height = metrics.height() * 2 + 12 * scale
        left = max(8, min(x + 12 * scale, rect.width - width - 8))
        top = y + 12 * scale if below else y - height - 12 * scale
        top = max(8, min(top, rect.height - height - 8))
        box = QRectF(left, top, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(12, 14, 18, 220))
        painter.drawRoundedRect(box, 4 * scale, 4 * scale)
        painter.setPen(color)
        for i, text in enumerate((label, details)):
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(1, int(width - 12 * scale)))
            painter.drawText(QRectF(left + 6 * scale, top + 6 * scale + i * metrics.height(),
                                    width - 12 * scale, metrics.height()), Qt.AlignmentFlag.AlignLeft, text)

    def _draw_world_calibration_panel(self, painter: QPainter, rect: Rect, lines: list[str], scale: float) -> None:
        metrics = painter.fontMetrics()
        line_height = metrics.height() + 4 * scale
        margin = 12 * scale
        left = min(16 * scale, rect.width / 4)
        top = min(70 * scale, rect.height / 4)
        width = min(520 * scale, rect.width - left * 2)
        max_rows = max(1, int((rect.height - top - margin * 2) / line_height))
        lines = lines[:max_rows]
        box = QRectF(left, top, width, len(lines) * line_height + margin * 2)
        painter.setPen(QPen(QColor(90, 195, 250, 220), scale))
        painter.setBrush(QColor(12, 14, 18, 235))
        painter.drawRoundedRect(box, 6 * scale, 6 * scale)
        painter.setPen(QColor(235, 240, 250))
        for i, line in enumerate(lines):
            text = metrics.elidedText(line, Qt.TextElideMode.ElideRight, max(1, int(width - margin * 2)))
            painter.drawText(QRectF(left + margin, top + margin + i * line_height,
                                    width - margin * 2, line_height), Qt.AlignmentFlag.AlignLeft, text)
