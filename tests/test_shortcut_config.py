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
    shortcut_config_info_asset_path,
    shortcut_config_info_tooltip_asset_path,
    shortcut_info_node_point,
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

    def test_spotlight_backdrop_removed_keeps_transparency(self):
        """Valida que o backdrop escuro foi removido e não escurece a tela."""
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

            # Como o backdrop escuro foi desativado/removido, a tela permanece totalmente transparente (alpha == 0)
            self.assertEqual(img.pixelColor(640, 200).alpha(), 0)
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

    def test_instruction_banner_animates_exit_slide_out(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            # Modo inativo (shortcut_config_active = False), mas animando saída (progresso > 0)
            snapshot_inactive = OverlaySnapshot(
                game_rect=Rect(0, 0, 1280, 960),
                shortcut_config_active=False,
                controller_type="xbox",
            )

            overlay._shortcut_anim_progress = 0.5
            img = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            try:
                overlay._draw_shortcut_instruction(painter, snapshot_inactive)
            finally:
                painter.end()

            # Pixmap deve ter sido carregado e processado no desenho
            if overlay._config_info_pixmap is not None:
                # Confirma que foi desenhado algo na tela durante a saída
                has_pixels = any(
                    img.pixelColor(x, y).alpha() > 0
                    for x in (640,)
                    for y in range(0, 70)
                )
                self.assertTrue(has_pixels)

            # Quando a animação atinge 0.0, não deve desenhar nada
            overlay._shortcut_anim_progress = 0.0
            img_done = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_done.fill(Qt.GlobalColor.transparent)
            painter_done = QPainter(img_done)
            try:
                overlay._draw_shortcut_instruction(painter_done, snapshot_inactive)
            finally:
                painter_done.end()
            self.assertEqual(img_done.pixelColor(640, 20).alpha(), 0)

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

    def test_press_start_or_esc_disarms_shortcut_config_completely(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # 1. Abre o grid e pressiona Start: deve desarmar por completo e voltar para o jogo
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_grid_active)
            self.assertTrue(shared.get().shortcut_config_active)

            # Pressiona Start: desarma completamente
            self._tick(engine, self._state(("start",)), now=0.25)
            self._tick(engine, self._state(), now=0.30)
            snap = shared.get()
            self.assertFalse(snap.shortcut_grid_active)
            self.assertFalse(snap.shortcut_config_active)

            # 2. Entra no modo de atalhos (apenas nós da HUD) e pressiona Start: desarma para o jogo
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.35)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.40)
            self._tick(engine, self._state(), now=0.45)
            self.assertTrue(shared.get().shortcut_config_active)
            self.assertFalse(shared.get().shortcut_grid_active)

            self._tick(engine, self._state(("start",)), now=0.50)
            self._tick(engine, self._state(), now=0.55)
            snap2 = shared.get()
            self.assertFalse(snap2.shortcut_config_active)
            self.assertFalse(snap2.shortcut_grid_active)

    def test_backdrop_completely_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)
            overlay._shortcut_anim_progress = 1.0

            rect = Rect(0, 0, 1280, 960)
            # O backdrop escuro foi desativado: nenhum pixel deve ser escurecido
            snap_hud = OverlaySnapshot(game_rect=rect, shortcut_config_active=True, shortcut_grid_active=False)
            img_hud = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_hud.fill(Qt.GlobalColor.transparent)
            painter1 = QPainter(img_hud)
            try:
                overlay._draw_shortcut_spotlight(painter1, snap_hud)
            finally:
                painter1.end()
            self.assertEqual(img_hud.pixelColor(640, 200).alpha(), 0)


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

            # 2. Modo calibração ligado, mas shortcut_config_active=False: NÃO deve desenhar
            config.set_show_calibration(True)
            snap_inactive = OverlaySnapshot(
                game_rect=rect,
                shortcut_config_active=False,
                shortcut_node_focus=0,
            )
            img_inact = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_inact.fill(Qt.GlobalColor.transparent)
            painter_inact = QPainter(img_inact)
            try:
                overlay._draw_shortcut_nodes(painter_inact, snap_inactive)
            finally:
                painter_inact.end()
            self.assertEqual(img_inact.pixelColor(p0_x, p0_y).alpha(), 0)

            # 3. Na Tela Inicial (mesmo com calibração ligada): NÃO deve desenhar
            snap_title = OverlaySnapshot(
                game_rect=rect,
                memory_state_desc="Tela Inicial",
                memory_is_in_game=False,
                shortcut_config_active=True,
                shortcut_node_focus=0,
            )
            img_title = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img_title.fill(Qt.GlobalColor.transparent)
            painter_title = QPainter(img_title)
            try:
                overlay._draw_shortcut_nodes(painter_title, snap_title)
            finally:
                painter_title.end()
            self.assertEqual(img_title.pixelColor(p0_x, p0_y).alpha(), 0)

            # 4. Modo calibração ligado + shortcut_config_active=True + em jogo: DEVEM ser desenhados
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

    def test_engine_adapts_grid_counts_from_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Simula leitura real da memória: 8 colunas, 3 linhas, contagens (7, 2, 8)
            engine.memory.read_shortcut_grid_info = lambda: (8, 3, (7, 2, 8))

            # Entra no modo de atalhos e abre o grid
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)

            snap = shared.get()
            self.assertTrue(snap.shortcut_grid_active)
            self.assertEqual(snap.shortcut_grid_cols, 8)
            self.assertEqual(snap.shortcut_grid_rows, 3)
            self.assertEqual(snap.shortcut_grid_counts, (7, 2, 8))

            # Desce para a linha 1 (que só possui 2 nós acessíveis: índice 0 e 1)
            self._tick(engine, self._state(("dpad_down",)), now=0.25)
            self._tick(engine, self._state(), now=0.30)
            self.assertEqual(shared.get().shortcut_grid_pos, (1, 0))

            # D-pad Direita: move para col=1
            self._tick(engine, self._state(("dpad_right",)), now=0.35)
            self._tick(engine, self._state(), now=0.40)
            self.assertEqual(shared.get().shortcut_grid_pos, (1, 1))

            # D-pad Direita novamente: trava no nó 1 (pois a linha 1 só tem 2 nós, índices 0 e 1)
            self._tick(engine, self._state(("dpad_right",)), now=0.45)
            self._tick(engine, self._state(), now=0.50)
            self.assertEqual(shared.get().shortcut_grid_pos, (1, 1))

    def test_bottom_hud_switches_to_shortcut_active_variant_in_shortcut_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            rect = Rect(0, 0, 1280, 960)

            # 1. Quando o modo de configuração está ativo: deve carregar a variante shortcut-config-active
            snap_active = OverlaySnapshot(
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                shortcut_config_active=True,
                shortcut_grid_active=False,
                shortcut_node_focus=0,
                controller_type="xbox",
            )
            img1 = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img1.fill(Qt.GlobalColor.transparent)
            painter1 = QPainter(img1)
            try:
                overlay._draw_bottom_hud(painter1, snap_active)
            finally:
                painter1.end()
            self.assertIn("xbox_shortcut", overlay._bottom_hud_cache)

            # 2. Quando o modo de configuração NÃO está ativo: usa o HUD padrão
            snap_game = OverlaySnapshot(
                game_rect=rect,
                controller_connected=True,
                memory_is_in_game=True,
                shortcut_config_active=False,
                shortcut_grid_active=False,
                shortcut_node_focus=0,
                controller_type="playstation",
            )
            img2 = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img2.fill(Qt.GlobalColor.transparent)
            painter2 = QPainter(img2)
            try:
                overlay._draw_bottom_hud(painter2, snap_game)
            finally:
                painter2.end()
            self.assertIn("playstation", overlay._bottom_hud_cache)
            self.assertNotIn("playstation_shortcut", overlay._bottom_hud_cache)

    def test_config_info_and_tooltip_assets_exist(self):
        info_path = shortcut_config_info_asset_path()
        self.assertIsNotNone(info_path)
        self.assertTrue(info_path.is_file(), f"Arquivo {info_path} não existe")

        for ctrl in ("playstation", "xbox", "nintendo"):
            tt_path = shortcut_config_info_tooltip_asset_path(ctrl)
            self.assertIsNotNone(tt_path, f"Tooltip para {ctrl} não encontrado")
            self.assertTrue(tt_path.is_file(), f"Arquivo {tt_path} não existe")

    def test_shortcut_info_node_point_calculation(self):
        rect = Rect(100, 50, 1280, 960)
        cx, cy = shortcut_info_node_point(rect)
        self.assertEqual(cx, 100 + 640)
        self.assertEqual(cy, 50 + 34)

    def test_dpad_up_navigates_to_shortcut_info_focus_and_down_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Ativa modo de atalhos e solta botões
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            engine.injector.events.clear()

            self.assertTrue(shared.get().shortcut_config_active)
            self.assertFalse(shared.get().shortcut_info_focus)

            # D-pad Cima: move o foco para a aba superior de informações
            self._tick(engine, self._state(("dpad_up",)), now=0.15)
            self.assertTrue(engine._shortcut_info_focus)
            self.assertTrue(shared.get().shortcut_info_focus)
            info_x, info_y = shortcut_info_node_point(rect)
            self.assertIn(("move", info_x, info_y), engine.injector.events)

            # Solta D-pad
            self._tick(engine, self._state(), now=0.20)
            engine.injector.events.clear()

            # D-pad Baixo: retorna foco para os nós da HUD inferior
            self._tick(engine, self._state(("dpad_down",)), now=0.25)
            self.assertFalse(engine._shortcut_info_focus)
            self.assertFalse(shared.get().shortcut_info_focus)
            node_x, node_y = shortcut_node_point(rect, engine._shortcut_node_focus)
            self.assertIn(("move", node_x, node_y), engine.injector.events)

    def test_button_b_returns_from_shortcut_info_focus_to_hud(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)
            rect = Rect(0, 0, 1920, 1080)

            # Ativa modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)

            # D-pad Cima entra na aba de informações
            self._tick(engine, self._state(("dpad_up",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_info_focus)
            engine.injector.events.clear()

            # Botão B retorna foco para a HUD inferior sem fechar o modo de atalhos
            self._tick(engine, self._state(("b",)), now=0.25)
            self.assertTrue(engine._shortcut_config_active)
            self.assertFalse(engine._shortcut_info_focus)
            self.assertFalse(shared.get().shortcut_info_focus)
            node_x, node_y = shortcut_node_point(rect, engine._shortcut_node_focus)
            self.assertIn(("move", node_x, node_y), engine.injector.events)

    def test_start_or_esc_from_shortcut_info_focus_disarms_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Ativa modo de atalhos e sobe para aba de informações
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)
            self._tick(engine, self._state(("dpad_up",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(shared.get().shortcut_info_focus)

            # Botão Start desarma completamente o modo
            self._tick(engine, self._state(("start",)), now=0.25)
            self.assertFalse(engine._shortcut_config_active)
            self.assertFalse(engine._shortcut_info_focus)
            self.assertFalse(shared.get().shortcut_config_active)
            self.assertFalse(shared.get().shortcut_info_focus)

    def test_grid_active_suppresses_shortcut_info_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, shared, _ = self._engine(directory)

            # Ativa modo de atalhos
            self._tick(engine, self._state(("lb",), rx=0.0, ry=0.8), now=0.0)
            self._tick(engine, self._state(("lb", "a"), rx=0.0, ry=0.8), now=0.05)
            self._tick(engine, self._state(), now=0.10)

            # Pressiona A no nó 0 para abrir o grid de opções
            self._tick(engine, self._state(("a",)), now=0.15)
            self._tick(engine, self._state(), now=0.20)
            self.assertTrue(engine._shortcut_grid_active)
            self.assertTrue(shared.get().shortcut_grid_active)

            # Enquanto o grid estiver aberto, D-pad Cima não navega para a aba de informações
            self._tick(engine, self._state(("dpad_up",)), now=0.25)
            self.assertFalse(engine._shortcut_info_focus)
            self.assertFalse(shared.get().shortcut_info_focus)
            self.assertTrue(engine._shortcut_grid_active)

    def test_overlay_animates_config_info_and_tooltip_fade(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._engine(directory)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            snapshot = OverlaySnapshot(
                game_rect=Rect(0, 0, 1280, 960),
                shortcut_config_active=True,
                shortcut_info_focus=True,
                controller_type="xbox",
            )

            overlay._shortcut_anim_last_time = 0.0
            overlay._shortcut_anim_progress = 1.0
            overlay._tick_shortcut_mode_anim(snapshot)
            self.assertGreater(overlay._shortcut_tooltip_opacity, 0.0)

            img = QImage(1280, 960, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            try:
                overlay._draw_shortcut_instruction(painter, snapshot)
            finally:
                painter.end()

            self.assertIsNotNone(overlay._config_info_pixmap)
            self.assertIn("xbox", overlay._config_info_tooltip_cache)


if __name__ == "__main__":
    unittest.main()

