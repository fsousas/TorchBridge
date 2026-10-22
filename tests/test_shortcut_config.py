import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QImage, QColor
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.models import (
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    shortcut_mask_asset_path,
    shortcut_instruction_asset_path,
)
from torchbridge.overlay import GameOverlay


class FakeHub:
    def rumble(self, *args, **kwargs):
        pass


class FakeInjector:
    def __init__(self):
        self.tapped = []
        self.events = []
        self.buttons = {}

    def tap(self, key):
        self.tapped.append(key)

    def mouse_button(self, button, pressed):
        self.buttons[button] = pressed
        self.events.append(("mouse", button, pressed))

    def cursor_position(self):
        return (960, 540)


class ShortcutConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Garante app Qt para testes com QWidget/QPixmap/QImage
        cls._app = QApplication.instance() or QApplication([])

    def _state(self, buttons: tuple[str, ...] = (), **kw) -> ControllerState:
        return ControllerState(connected=True, buttons=frozenset(buttons), **kw)

    def _engine(self, directory: str):
        config = ConfigManager(Path(directory) / "perfil.json")
        shared = SharedOverlayState()
        engine = BridgeEngine(config, shared)
        engine._mode = "direct"
        engine.injector = FakeInjector()
        return engine, shared, config

    def _tick(self, engine, state, now=0.0):
        cfg = engine.config.get()
        rect = Rect(0, 0, 1920, 1080)
        engine._process_active(FakeHub(), state, rect, cfg, now, 0.05)
        engine._previous = state

    def test_shortcut_mask_asset_exists(self):
        path = shortcut_mask_asset_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())

    def test_shortcut_instruction_assets_exist(self):
        for controller in ("playstation", "xbox", "nintendo"):
            path = shortcut_instruction_asset_path(controller)
            self.assertIsNotNone(path, f"Asset para {controller} não encontrado")
            self.assertTrue(path.is_file(), f"Arquivo {path} não existe")

    def test_confirm_shortcut_in_radial_activates_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            # Slot 5 é short-cut (Sul / Baixo: rx=0.0, ry=0.8)
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            snap = shared.get()
            self.assertEqual(snap.radial_selection, 5)
            self.assertTrue(snap.radial_active)

            # Confirma com botão A
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)

            # Menu radial fecha e modo de atalhos ativa
            snap = shared.get()
            self.assertFalse(snap.radial_active)
            self.assertTrue(engine._shortcut_config_active)
            self.assertTrue(snap.shortcut_config_active)
            # Não deve ter acionado nenhuma tecla do teclado
            self.assertEqual(engine.injector.tapped, [])

    def test_east_button_b_exits_shortcut_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            # Ativa o modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self.assertTrue(shared.get().shortcut_config_active)

            # Solta botões
            self._tick(engine, self._state(), now=0.10)
            self.assertTrue(shared.get().shortcut_config_active)

            # Aperta B (Bolinha no PS / Leste) para sair
            self._tick(engine, self._state(("b",)), now=0.15)

            # Modo foi desativado
            self.assertFalse(engine._shortcut_config_active)
            self.assertFalse(shared.get().shortcut_config_active)

    def test_spotlight_backdrop_renders_correctly(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)
            overlay._shortcut_anim_progress = 1.0

            # Com shortcut_config_active = True
            snapshot = OverlaySnapshot(
                game_rect=Rect(0, 0, 1280, 960),
                shortcut_config_active=True,
            )

            img = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            try:
                overlay._draw_shortcut_spotlight(painter, snapshot)
            finally:
                painter.end()

            # O centro superior deve ter o fundo preto 70% (alpha ~ 178)
            self.assertAlmostEqual(img.pixelColor(640, 200).alpha(), 178, delta=2)
            # A parte inferior central (onde está a máscara) deve estar recortada (alpha ~ 0)
            self.assertEqual(img.pixelColor(640, 950).alpha(), 0)

    def test_instruction_banner_animates_and_renders(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            snapshot = OverlaySnapshot(
                game_rect=Rect(0, 0, 1280, 960),
                shortcut_config_active=True,
                controller_type="playstation",
            )

            # Simula tick de animação
            overlay._shortcut_anim_last_time = 0.0
            overlay._shortcut_anim_progress = 0.5

            img = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            try:
                overlay._draw_shortcut_instruction(painter, snapshot)
            finally:
                painter.end()


if __name__ == "__main__":
    unittest.main()
