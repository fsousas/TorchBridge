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
    SHORTCUT_HUD_NODES,
    shortcut_node_point,
    shortcut_grid_cell_point,
    shortcut_nodes_asset_path,
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
        self.keys = {}
        self.moves = []

    def tap(self, key):
        self.tapped.append(key)
        self.events.append(("tap", key))

    def key(self, name, down):
        self.keys[name] = down
        self.events.append(("key", name, down))
        return True

    def mouse_button(self, button, pressed):
        self.buttons[button] = pressed
        self.events.append(("mouse", button, pressed))
        return True

    def move(self, x, y):
        self.moves.append((x, y))
        self.events.append(("move", x, y))
        return True

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

    def test_spotlight_backdrop_adapts_to_window_resize_and_widescreen(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)
            overlay._shortcut_anim_progress = 1.0

            # 1. Primeira renderização em 1280x960
            snapshot_1 = OverlaySnapshot(
                game_rect=Rect(0, 0, 1280, 960),
                shortcut_config_active=True,
            )
            img_1 = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_1.fill(Qt.GlobalColor.transparent)
            painter_1 = QPainter(img_1)
            try:
                overlay._draw_shortcut_spotlight(painter_1, snapshot_1)
            finally:
                painter_1.end()
            self.assertEqual(overlay._cached_spotlight_size, (1280, 960))

            # 2. Usuário redimensiona a janela para widescreen (ex: 1920x1080)
            snapshot_2 = OverlaySnapshot(
                game_rect=Rect(0, 0, 1920, 1080),
                shortcut_config_active=True,
            )
            img_2 = QImage(1920, 1080, QImage.Format.Format_ARGB32_Premultiplied)
            img_2.fill(Qt.GlobalColor.transparent)
            painter_2 = QPainter(img_2)
            try:
                overlay._draw_shortcut_spotlight(painter_2, snapshot_2)
            finally:
                painter_2.end()

            # Cache do spotlight deve ter sido reconstruído nas novas dimensões
            self.assertEqual(overlay._cached_spotlight_size, (1920, 1080))
            # Centro recortado onde fica o HUD inferior (h = 1080, recortado na base)
            self.assertEqual(img_2.pixelColor(960, 1070).alpha(), 0)
            # Lateral fora do HUD inferior deve continuar com backdrop escuro 70%
            self.assertAlmostEqual(img_2.pixelColor(100, 1070).alpha(), 178, delta=2)
            # Área acima do HUD (y = 800) não deve estar recortada
            self.assertAlmostEqual(img_2.pixelColor(960, 800).alpha(), 178, delta=2)

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

    def test_shortcut_nodes_definitions(self):
        path = shortcut_nodes_asset_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertEqual(len(SHORTCUT_HUD_NODES), 13)
        self.assertEqual(SHORTCUT_HUD_NODES[0][1], "yellow")
        for i in range(1, 13):
            self.assertEqual(SHORTCUT_HUD_NODES[i][1], "green")

    def test_shortcut_mode_entry_positions_cursor_at_node_0(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Ativa o modo de atalhos a partir da confirmação do radial (South / Slot 5)
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self.assertTrue(shared.get().shortcut_config_active)
            self.assertEqual(shared.get().shortcut_node_focus, 0)
            self.assertEqual(engine._shortcut_node_focus, 0)

            # Cursor deve ter sido movido para o nó 0
            n0_x, n0_y = shortcut_node_point(rect, 0)
            self.assertIn(("move", n0_x, n0_y), engine.injector.events)

    def test_shortcut_mode_dpad_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Entra no modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            engine.injector.events.clear()

            # D-pad Direita: move do nó 0 para o nó 1
            self._tick(engine, self._state(("dpad_right",)), now=0.15)
            self.assertEqual(engine._shortcut_node_focus, 1)
            self.assertEqual(shared.get().shortcut_node_focus, 1)
            n1_x, n1_y = shortcut_node_point(rect, 1)
            self.assertIn(("move", n1_x, n1_y), engine.injector.events)

            # Solta D-pad
            self._tick(engine, self._state(), now=0.20)
            engine.injector.events.clear()

            # D-pad Direita de novo: nó 1 -> nó 2
            self._tick(engine, self._state(("dpad_right",)), now=0.25)
            self.assertEqual(engine._shortcut_node_focus, 2)
            n2_x, n2_y = shortcut_node_point(rect, 2)
            self.assertIn(("move", n2_x, n2_y), engine.injector.events)

            # Solta D-pad
            self._tick(engine, self._state(), now=0.30)
            engine.injector.events.clear()

            # D-pad Esquerda: nó 2 -> nó 1
            self._tick(engine, self._state(("dpad_left",)), now=0.35)
            self.assertEqual(engine._shortcut_node_focus, 1)
            self.assertIn(("move", n1_x, n1_y), engine.injector.events)

    def test_shortcut_mode_north_button_ctrl_clicks(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Entra no modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            engine.injector.events.clear()

            # Pressiona Y (Botão Norte): dispara Ctrl + Clique Esquerdo
            self._tick(engine, self._state(("y",)), now=0.15)
            expected_seq = [
                ("key", "ctrl", True),
                ("mouse", "left", True),
                ("mouse", "left", False),
                ("key", "ctrl", False),
            ]
            events = [e for e in engine.injector.events if e[0] in ("key", "mouse")]
            self.assertEqual(events, expected_seq)

    def test_shortcut_mode_south_button_opens_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Entra no modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            engine.injector.events.clear()

            # Pressiona A (Botão Sul): abre o grid de opções e ativa o modo grid
            self._tick(engine, self._state(("a",)), now=0.15)
            snap = shared.get()
            self.assertTrue(snap.shortcut_grid_active)
            self.assertEqual(snap.shortcut_grid_pos, (0, 0))

            # Verifica que enviou clique esquerdo e moveu para a primeira célula do grid
            expected_mouse_clicks = [e for e in engine.injector.events if e[0] == "mouse"]
            self.assertEqual(expected_mouse_clicks, [("mouse", "left", True), ("mouse", "left", False)])

    def test_shortcut_grid_cell_point_calculation(self):
        rect = Rect(0, 0, 1280, 960)
        # Testa cálculo de pontos da célula (0, 0) e (1, 1)
        p00 = shortcut_grid_cell_point(rect, slot_index=1, row=0, col=0, num_cols=8, num_rows=3)
        p01 = shortcut_grid_cell_point(rect, slot_index=1, row=0, col=1, num_cols=8, num_rows=3)
        p10 = shortcut_grid_cell_point(rect, slot_index=1, row=1, col=0, num_cols=8, num_rows=3)

        self.assertGreater(p00[0], 0)
        self.assertGreater(p00[1], 0)
        # Na horizontal, a coluna 1 fica à direita da coluna 0 por ~60px (48px na base 768p)
        self.assertAlmostEqual(p01[0] - p00[0], 60, delta=2)
        # Na vertical, a linha 1 fica abaixo da linha 0 por ~60px
        self.assertAlmostEqual(p10[1] - p00[1], 60, delta=2)

    def test_dpad_navigates_grid_2d(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Entra no modo de atalhos e abre o grid
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_grid_active)

            # 1. D-pad Direita: move para col=1
            self._tick(engine, self._state(("dpad_right",)), now=0.25)
            self._tick(engine, self._state(), now=0.30)
            self.assertEqual(shared.get().shortcut_grid_pos, (0, 1))

            # 2. D-pad Baixo: move para row=1, col=1
            self._tick(engine, self._state(("dpad_down",)), now=0.35)
            self._tick(engine, self._state(), now=0.40)
            self.assertEqual(shared.get().shortcut_grid_pos, (1, 1))

            # 3. D-pad Esquerda: volta para row=1, col=0
            self._tick(engine, self._state(("dpad_left",)), now=0.45)
            self._tick(engine, self._state(), now=0.50)
            self.assertEqual(shared.get().shortcut_grid_pos, (1, 0))

            # 4. D-pad Cima: volta para row=0, col=0
            self._tick(engine, self._state(("dpad_up",)), now=0.55)
            self._tick(engine, self._state(), now=0.60)
            self.assertEqual(shared.get().shortcut_grid_pos, (0, 0))

    def test_press_a_in_grid_confirms_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Entra no modo de atalhos e abre o grid
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_grid_active)

            # Move para col=2
            self._tick(engine, self._state(("dpad_right",)), now=0.25)
            self._tick(engine, self._state(), now=0.30)
            self._tick(engine, self._state(("dpad_right",)), now=0.35)
            self._tick(engine, self._state(), now=0.40)
            self.assertEqual(shared.get().shortcut_grid_pos, (0, 2))

            # Pressiona A: confirma a seleção, envia clique na célula e sai do modo grid
            engine.injector.events.clear()
            self._tick(engine, self._state(("a",)), now=0.45)
            self._tick(engine, self._state(), now=0.50)

            snap = shared.get()
            self.assertFalse(snap.shortcut_grid_active)
            self.assertTrue(snap.shortcut_config_active)  # Ainda no modo de configuração de slots
            clicks = [e for e in engine.injector.events if e[0] == "mouse"]
            self.assertEqual(clicks, [("mouse", "left", True), ("mouse", "left", False)])

    def test_press_b_in_grid_cancels_and_returns_to_hud(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Entra no modo de atalhos e abre o grid
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_grid_active)

            # Pressiona B: cancela a seleção do grid
            engine.injector.events.clear()
            self._tick(engine, self._state(("b",)), now=0.25)
            self._tick(engine, self._state(), now=0.30)

            snap = shared.get()
            self.assertFalse(snap.shortcut_grid_active)
            self.assertTrue(snap.shortcut_config_active)

    def test_backdrop_hidden_when_grid_active(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)
            overlay._shortcut_anim_progress = 1.0

            rect = Rect(0, 0, 1280, 960)
            # 1. Quando o grid NÃO está ativo: backdrop é desenhado
            snap_hud = OverlaySnapshot(game_rect=rect, shortcut_config_active=True, shortcut_grid_active=False)
            img_hud = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_hud.fill(Qt.GlobalColor.transparent)
            painter1 = QPainter(img_hud)
            try:
                overlay._draw_shortcut_spotlight(painter1, snap_hud)
            finally:
                painter1.end()
            # Ponto superior escurecido pelo backdrop
            self.assertGreater(img_hud.pixelColor(640, 200).alpha(), 100)

            # 2. Quando o grid ESTÁ ativo: backdrop tem opacidade 0 (invisível)
            snap_grid = OverlaySnapshot(game_rect=rect, shortcut_config_active=True, shortcut_grid_active=True)
            img_grid = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_grid.fill(Qt.GlobalColor.transparent)
            painter2 = QPainter(img_grid)
            try:
                overlay._draw_shortcut_spotlight(painter2, snap_grid)
            finally:
                painter2.end()
            # Nenhum pixel escurecido pelo backdrop!
            self.assertEqual(img_grid.pixelColor(640, 200).alpha(), 0)


    def test_shortcut_nodes_only_render_in_calibration_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)
            overlay._shortcut_anim_progress = 1.0

            rect = Rect(0, 0, 1280, 960)
            snapshot = OverlaySnapshot(
                game_rect=rect,
                shortcut_config_active=True,
                shortcut_node_focus=0,
            )

            # 1. Modo normal (sem calibração): os nós NÃO devem ser desenhados
            img = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            try:
                overlay._draw_shortcut_nodes(painter, snapshot)
            finally:
                painter.end()

            p0_x, p0_y = shortcut_node_point(rect, 0)
            self.assertEqual(img.pixelColor(p0_x, p0_y).alpha(), 0)

            # 2. Modo calibração ligado: os nós DEVEM ser desenhados
            config.set_show_calibration(True)
            img_cal = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_cal.fill(Qt.GlobalColor.transparent)
            painter_cal = QPainter(img_cal)
            try:
                overlay._draw_shortcut_nodes(painter_cal, snapshot)
            finally:
                painter_cal.end()

            self.assertGreater(img_cal.pixelColor(p0_x, p0_y).alpha(), 100)
            p1_x, p1_y = shortcut_node_point(rect, 1)
            self.assertGreater(img_cal.pixelColor(p1_x, p1_y).alpha(), 100)

    def test_engine_adapts_grid_dimensions_from_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Simula que a memória reporta grid 5x5 (sem spells)
            engine.memory.read_shortcut_grid_dims = lambda: (5, 5)

            # Entra no modo de atalhos e abre o grid
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)

            snap = shared.get()
            self.assertTrue(snap.shortcut_grid_active)
            self.assertEqual(snap.shortcut_grid_cols, 5)
            self.assertEqual(snap.shortcut_grid_rows, 5)
            self.assertEqual(engine._shortcut_grid_cols, 5)
            self.assertEqual(engine._shortcut_grid_rows, 5)


if __name__ == "__main__":
    unittest.main()

