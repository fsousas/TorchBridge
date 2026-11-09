from __future__ import annotations

import math
import sys
import time

from ..models import (
    KEYBOARD_LAYOUT,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    char_create_button_point,
    controller_type_from_name,
    virtual_keyboard_asset_path,
    virtual_keyboard_bg_asset_path,
    virtual_keyboard_grid_to_key,
    virtual_keyboard_highlight_filename,
    virtual_keyboard_info_label_filename,
    virtual_keyboard_key_cursor_point,
    virtual_keyboard_key_filename,
    virtual_keyboard_key_rect,
    virtual_keyboard_target_rect,
)
from ..win32 import (
    IS_WINDOWS,
    make_overlay_clickthrough,
)
from PySide6.QtCore import (
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget
from pathlib import Path

log = logging.getLogger(__name__) if "logging" in globals() else None

class KeyboardInputSurface(QWidget):
    """Intercept virtual-key clicks without activating a window or clicking the game."""

    def __init__(self, shared: SharedOverlayState, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.shared = shared
        self.physical_rect = Rect()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._native_cursor = None
        self._setup_game_cursor()

    def _setup_game_cursor(self) -> None:
        p = virtual_keyboard_asset_path("pointer.cur")
        if not p or not p.exists():
            for candidate in (
                Path(r"C:\GOG Games\Torchlight\icons\pointer.cur"),
                Path(r"C:\Program Files (x86)\Steam\steamapps\common\Torchlight\icons\pointer.cur"),
            ):
                if candidate.exists():
                    p = candidate
                    break
        if p and p.exists():
            pix = QPixmap(str(p))
            if not pix.isNull():
                self.setCursor(QCursor(pix, 0, 0))
            if IS_WINDOWS:
                import ctypes
                user32 = ctypes.windll.user32
                self._native_cursor = user32.LoadCursorFromFileW(str(p))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if IS_WINDOWS and QGuiApplication.platformName() == "windows":
            make_overlay_clickthrough(int(self.winId()), interactive=True)

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" or event_type == b"windows_generic_MSG":
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0021:  # WM_MOUSEACTIVATE: retain the game's keyboard focus.
                return True, 3  # MA_NOACTIVATE
            if msg.message == 0x0020:  # WM_SETCURSOR: exibe a mãozinha do jogo
                if self._native_cursor:
                    user32 = ctypes.windll.user32
                    user32.SetCursor(self._native_cursor)
                    return True, 1
        return super().nativeEvent(event_type, message)

    def paintEvent(self, event) -> None:
        # Nonzero alpha makes the entire surface hit-testable on Windows layered windows.
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        painter.end()

    def _physical_point(self, event) -> tuple[int, int]:
        rect = self.physical_rect
        point = event.position()
        return (round(rect.left + point.x() * rect.width / max(1, self.width())),
                round(rect.top + point.y() * rect.height / max(1, self.height())))

    def mouseMoveEvent(self, event) -> None:
        x, y = self._physical_point(event)
        self.shared.keyboard_event("hover", x, y)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._physical_point(event)
            self.shared.keyboard_event("click", x, y)
        event.accept()



class VirtualKeyboardOverlayMixin:
    """Mixin com métodos de desenho e animação para keyboard."""

    def _tick_virtual_keyboard_anim(self, snapshot: OverlaySnapshot) -> None:
        if snapshot.virtual_keyboard_target:
            self._last_virtual_keyboard_target = snapshot.virtual_keyboard_target
        target = 1.0 if snapshot.virtual_keyboard_open else 0.0
        now = time.monotonic()
        dt = now - self._virtual_keyboard_last_time
        self._virtual_keyboard_last_time = now
        if abs(self._virtual_keyboard_progress - target) < 1e-3:
            self._virtual_keyboard_progress = target
        else:
            step = dt / self._virtual_keyboard_anim_seconds
            if target > self._virtual_keyboard_progress:
                self._virtual_keyboard_progress = min(target, self._virtual_keyboard_progress + step)
            else:
                self._virtual_keyboard_progress = max(target, self._virtual_keyboard_progress - step)

        # Rastreia novo acionamento de tecla para animar encolhimento suave (CSS-like)
        press_id = getattr(snapshot, "virtual_keyboard_press_id", 0)
        pressed_key = snapshot.virtual_keyboard_pressed_key
        if press_id > 0 and press_id != self._kb_press_anim_id and pressed_key:
            self._kb_press_anim_id = press_id
            self._kb_press_anim_key = pressed_key
            self._kb_press_anim_start = now
        elif pressed_key and pressed_key != self._kb_press_anim_key:
            self._kb_press_anim_key = pressed_key
            self._kb_press_anim_start = now

    def _get_keyboard_bg_pixmap(self) -> QPixmap | None:
        if self._keyboard_bg_pixmap is not None:
            return self._keyboard_bg_pixmap
        path = virtual_keyboard_bg_asset_path()
        if path is None or not path.exists():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._keyboard_bg_pixmap = pixmap
        return pixmap

    def _get_keyboard_key_pixmap(self, filename: str) -> QPixmap | None:
        if filename in self._keyboard_keys_cache:
            return self._keyboard_keys_cache[filename]
        path = virtual_keyboard_asset_path(filename)
        if path is None or not path.exists():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        self._keyboard_keys_cache[filename] = pixmap
        return pixmap

    def _draw_virtual_keyboard(self, painter: QPainter, snapshot: OverlaySnapshot, scale: float) -> None:
        """Desenha o teclado virtual completo (background, teclas, highlights, label e cursor)."""
        if not snapshot.virtual_keyboard_open and self._virtual_keyboard_progress <= 0.0:
            return

        progress = self._virtual_keyboard_progress if self._virtual_keyboard_progress > 0.0 else (1.0 if snapshot.virtual_keyboard_open else 0.0)

        rect = snapshot.game_rect
        if not rect.valid:
            return

        target = snapshot.virtual_keyboard_target or self._last_virtual_keyboard_target or "character_name"
        kx, ky, kw, kh = virtual_keyboard_target_rect(rect, target)
        local_x = float(kx - rect.left)
        local_y = float(ky - rect.top)
        scale_k = kh / 290.0

        if snapshot.virtual_keyboard_open:
            # Entrada: slide com leve bounce (overshoot suave de ~2.5% a 3%)
            t1 = progress - 1.0
            eased = 1.0 + 1.8 * (t1 ** 3) + 0.8 * (t1 ** 2)
        else:
            # Saída: slide suave de retorno
            eased = progress * progress * (3.0 - 2.0 * progress)

        if target == "pet_name":
            # SlideLeft com bounce: vem de fora da tela (direita) até a posição final
            slide_dist = max(rect.width - local_x + 20.0, 100.0)
            offset_x = slide_dist * (1.0 - eased)
            offset_y = 0.0
        else:
            # SlideUP com bounce: vem de fora da tela (baixo) até a posição final
            slide_dist = max(rect.height - local_y + 20.0, 100.0)
            offset_x = 0.0
            offset_y = slide_dist * (1.0 - eased)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.translate(offset_x, offset_y)

        # 1. Background do teclado [Camada Fundo]
        bg_pix = self._get_keyboard_bg_pixmap()
        if bg_pix and not bg_pix.isNull():
            painter.drawPixmap(
                int(round(local_x)),
                int(round(local_y)),
                int(round(kw)),
                int(round(kh)),
                bg_pix,
            )
        else:
            painter.setPen(QPen(QColor(180, 160, 120, 240), 2.0 * scale))
            painter.setBrush(QColor(22, 19, 18, 245))
            painter.drawRoundedRect(QRectF(local_x, local_y, kw, kh), 8.0 * scale, 8.0 * scale)

        # 2. Barra informativa superior (info-label-*.png conforme o controle)
        ctrl_type = snapshot.controller_type or controller_type_from_name(snapshot.controller_name)
        label_file = virtual_keyboard_info_label_filename(ctrl_type)
        label_pix = self._get_keyboard_key_pixmap(label_file)
        if label_pix and not label_pix.isNull():
            lbl_w = 513.0 * scale_k
            lbl_h = 29.0 * scale_k
            lbl_x = local_x + (kw - lbl_w) / 2.0
            lbl_y = local_y - 25.0 * scale_k
            painter.drawPixmap(
                int(round(lbl_x)),
                int(round(lbl_y)),
                int(round(lbl_w)),
                int(round(lbl_h)),
                label_pix,
            )

        # 3. Teclas [Camada Tecla]
        caps_state = snapshot.virtual_keyboard_caps_state or "default"
        pressed_key = snapshot.virtual_keyboard_pressed_key

        focus = snapshot.virtual_keyboard_focus or (3, 1)
        focused_key_id, focused_key_type = virtual_keyboard_grid_to_key(focus[0], focus[1])

        # Animação suave estilo CSS ao pressionar tecla: encolhe e retorna suavemente
        anim_scale = 1.0
        anim_key_id = self._kb_press_anim_key or pressed_key
        if anim_key_id:
            now = time.monotonic()
            if self._kb_press_anim_start > 0.0:
                elapsed = now - self._kb_press_anim_start
                t_down = 0.06
                t_up = 0.12
                t_total = t_down + t_up
                min_scale = 0.94
                if elapsed < t_down:
                    p = elapsed / t_down
                    # Curva seno suave para o impacto
                    eased = math.sin(p * math.pi / 2.0)
                    anim_scale = 1.0 - (1.0 - min_scale) * eased
                elif elapsed < t_total:
                    p = (elapsed - t_down) / t_up
                    # Cubic ease-out para o retorno suave (como transition/translate no CSS)
                    eased = 1.0 - ((1.0 - p) ** 3)
                    anim_scale = min_scale + (1.0 - min_scale) * eased
                else:
                    anim_scale = 1.0
                    if not pressed_key:
                        self._kb_press_anim_key = None
            else:
                # Fallback estático para testes unitários com snapshot
                anim_scale = 0.94

        for key_id, r, c, span, k_type in KEYBOARD_LAYOUT:
            key_x, key_y, key_w, key_h = virtual_keyboard_key_rect(local_x, local_y, kw, kh, key_id)
            key_file = virtual_keyboard_key_filename(key_id, caps_state)
            key_pix = self._get_keyboard_key_pixmap(key_file)
            if key_pix and not key_pix.isNull():
                is_pressed = (key_id == anim_key_id and anim_scale != 1.0)
                if is_pressed:
                    # Efeito de clique afundar suave com centro na tecla
                    painter.save()
                    cx = key_x + key_w / 2.0
                    cy = key_y + key_h / 2.0
                    painter.translate(cx, cy)
                    painter.scale(anim_scale, anim_scale)
                    painter.translate(-cx, -cy)
                    painter.drawPixmap(
                        int(round(key_x)),
                        int(round(key_y)),
                        int(round(key_w)),
                        int(round(key_h)),
                        key_pix,
                    )
                    painter.restore()
                else:
                    painter.drawPixmap(
                        int(round(key_x)),
                        int(round(key_y)),
                        int(round(key_w)),
                        int(round(key_h)),
                        key_pix,
                    )

        # 4. Highlight da tecla sob foco [Camada Highlight]
        # O highlight também acompanha o encolhimento da tecla no clique
        f_kx, f_ky, f_kw, f_kh = virtual_keyboard_key_rect(local_x, local_y, kw, kh, focused_key_id)
        hl_file = virtual_keyboard_highlight_filename(focused_key_type)
        hl_pix = self._get_keyboard_key_pixmap(hl_file)
        if hl_pix and not hl_pix.isNull():
            hl_w = hl_pix.width() * scale_k
            hl_h = hl_pix.height() * scale_k
            hl_x = f_kx + (f_kw - hl_w) / 2.0
            hl_y = f_ky + (f_kh - hl_h) / 2.0
            is_hl_pressed = (focused_key_id == anim_key_id and anim_scale != 1.0)
            if is_hl_pressed:
                painter.save()
                f_cx = f_kx + f_kw / 2.0
                f_cy = f_ky + f_kh / 2.0
                painter.translate(f_cx, f_cy)
                painter.scale(anim_scale, anim_scale)
                painter.translate(-f_cx, -f_cy)
                painter.drawPixmap(
                    int(round(hl_x)),
                    int(round(hl_y)),
                    int(round(hl_w)),
                    int(round(hl_h)),
                    hl_pix,
                )
                painter.restore()
            else:
                painter.drawPixmap(
                    int(round(hl_x)),
                    int(round(hl_y)),
                    int(round(hl_w)),
                    int(round(hl_h)),
                    hl_pix,
                )

        # 5. Cursor / Nós de calibração [Camada Topo]
        show_cal = bool(self.config.get().get("overlay", {}).get("show_calibration", False))
        if show_cal:
            # Em modo calibração, exibe os nós verdes em todas as teclas
            for key_id, r, c, span, k_type in KEYBOARD_LAYOUT:
                kx_i, ky_i, kw_i, kh_i = virtual_keyboard_key_rect(local_x, local_y, kw, kh, key_id)
                cx, cy = virtual_keyboard_key_cursor_point(kx_i, ky_i, kw_i, kh_i)
                sz = 14.0 * scale_k
                if key_id == "3x1":
                    # Nó inicial amarelo #F4DC2A
                    painter.setPen(QPen(QColor(244, 220, 42, 240), 1.5))
                    painter.setBrush(QColor(244, 220, 42, 220))
                else:
                    # Nó de navegação verde #09B200
                    painter.setPen(QPen(QColor(9, 178, 0, 240), 1.5))
                    painter.setBrush(QColor(9, 178, 0, 220))
                painter.drawRect(QRectF(cx - sz / 2.0, cy - sz / 2.0, sz, sz))

        # 6. Nó de Retorno Rosa (#B2007C) sobre o campo de texto ativo
        if show_cal and target in ("character_name", "pet_name"):
            painter.save()
            painter.translate(-offset_x, -offset_y)
            tx, ty = char_create_button_point(rect, target)
            pink_lx = tx - rect.left
            pink_ly = ty - rect.top
            pink_w = 46.0 * scale_k
            pink_h = 24.0 * scale_k
            painter.setPen(QPen(QColor(178, 0, 124, 240), 2.0))
            painter.setBrush(QColor(178, 0, 124, 180))  # Rosa #B2007C
            painter.drawRect(
                QRectF(
                    pink_lx - pink_w * 0.5,
                    pink_ly - pink_h * 0.5,
                    pink_w,
                    pink_h,
                )
            )
            painter.restore()

        painter.restore()
