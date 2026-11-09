"""Same proximity drawing in desktop, scaled Wayland and native fullscreen frames."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.models import OverlaySnapshot, Rect, SharedOverlayState
from torchbridge.overlay import GameOverlay
from test_world import world_fixture


class WorldOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = ConfigManager(Path(self.directory.name) / "perfil.json")
        self.overlay = GameOverlay(SharedOverlayState(), self.config)
        self.addCleanup(self.overlay.shutdown)
        self.snapshot = OverlaySnapshot(game_active=True, game_found=True, controller_connected=True,
                                         memory_is_in_game=True, game_rect=Rect(100, 80, 1920, 1080),
                                         world=world_fixture(), interaction_target=world_fixture().entities[0])

    def render(self, snapshot, scale=1., calibration=False):
        image = QImage(snapshot.game_rect.width, snapshot.game_rect.height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            with patch("torchbridge.overlay.interaction.time.monotonic", return_value=10.05):
                if calibration:
                    self.overlay._draw_world_calibration(painter, snapshot, scale)
                else:
                    self.overlay._draw_world_interaction(painter, snapshot, scale)
        finally:
            painter.end()
        return bytes(image.constBits())

    def test_prompt_renders_at_different_resolutions_and_scales(self):
        for width, height, scale in ((1920, 1080, 1.), (1280, 720, 1.5), (800, 600, 2.), (2560, 1440, .6)):
            with self.subTest(width=width, scale=scale):
                snap = replace(self.snapshot, game_rect=Rect(-1280, 80, width, height))
                self.assertTrue(any(self.render(snap, scale)))

    def test_prompt_disappears_in_menus_radial_focus_loss_disconnect_and_stale_world(self):
        for changes in ({"enabled": False}, {"game_active": False}, {"controller_connected": False},
                        {"memory_is_menu_open": True}, {"memory_open_menus": ["Pause"]},
                        {"memory_is_loading": True}, {"radial_active": True}, {"active_panels": ["P", ""]},
                        {"mode": "cursor"}, {"interaction_target": None},
                        {"world": replace(self.snapshot.world, sampled_at=9.)}):
            with self.subTest(changes=changes):
                self.assertFalse(any(self.render(replace(self.snapshot, **changes))))

    def test_positions_can_be_displayed_without_a_nearby_target_or_prompt(self):
        self.config._data["interaction"].update(show_prompt=False, show_positions=True)
        self.assertTrue(any(self.render(replace(self.snapshot, interaction_target=None))))

    def test_shared_native_fullscreen_renderer_calls_interaction_painter(self):
        with patch.object(self.overlay, "_draw_world_interaction", wraps=self.overlay._draw_world_interaction) as draw:
            frame = self.overlay._render_native(self.snapshot, 1280, 720)
        self.assertEqual((frame.width(), frame.height()), (1280, 720))
        draw.assert_called_once()

    def test_calibration_toggle_automatically_shows_player_and_entity_coordinates(self):
        self.assertFalse(self.config.get()["interaction"]["show_positions"])
        self.assertFalse(any(self.render(self.snapshot, calibration=True)))
        self.config.set_show_calibration(True)
        with patch.object(self.overlay, "_draw_world_marker", wraps=self.overlay._draw_world_marker) as draw:
            pixels = self.render(self.snapshot, calibration=True)
        self.assertTrue(any(pixels))
        self.assertEqual({call.args[3] for call in draw.call_args_list}, {"NPC: Vasman", "Jogador"})
        self.assertIn("X 0.50  Y -4.00", draw.call_args_list[0].args[4])
        # Ground markers appear at their projected positions, away from the info panel.
        for x, y in ((960, 540), (1080, 540)):
            self.assertGreater(pixels[(y * 1920 + x) * 4 + 3], 0)
        self.config.set_show_calibration(False)
        self.assertFalse(any(self.render(self.snapshot, calibration=True)))

    def test_calibration_does_not_require_interaction_enabled_controller_or_direct_mode(self):
        self.config.set_show_calibration(True)
        self.config._data["interaction"].update(enabled=False, show_prompt=False, show_positions=False)
        snap = replace(self.snapshot, controller_connected=False, mode="cursor", interaction_target=None,
                       memory_is_menu_open=True, memory_open_menus=["Inventário"], active_panels=["", "I"])
        with patch.object(self.overlay, "_draw_world_marker", wraps=self.overlay._draw_world_marker) as draw:
            self.assertTrue(any(self.render(snap, calibration=True)))
        self.assertEqual(draw.call_count, 2)

    def test_calibration_marks_distant_objects_too_and_clips_offscreen_objects(self):
        self.config.set_show_calibration(True)
        world = self.snapshot.world
        distant = replace(world.entities[0], address=0x400000, kind="portal", name="Portal",
                          position=replace(world.player_position, x=2., y=-10.))
        offscreen = replace(distant, address=0x400004, position=replace(distant.position, x=100.))
        snap = replace(self.snapshot, world=replace(world, entities=(*world.entities, distant, offscreen)))
        for width, height, scale in ((1920, 1080, 1.), (1280, 720, 1.5), (800, 600, 2.)):
            with self.subTest(width=width, scale=scale):
                snap = replace(snap, game_rect=Rect(-1280, 80, width, height))
                with patch.object(self.overlay, "_draw_world_marker", wraps=self.overlay._draw_world_marker) as draw:
                    self.assertTrue(any(self.render(snap, scale, calibration=True)))
                self.assertEqual(draw.call_count, 3)  # player + near NPC + distant portal
                portal = next(call for call in draw.call_args_list if call.args[3] == "Portal: Portal")
                self.assertEqual(portal.args[2], world.camera.project(distant.position, width, height))
                self.assertGreater(portal.args[5].blue(), portal.args[5].red())

    def test_calibration_reports_unavailable_data_without_drawing_stale_markers(self):
        self.config.set_show_calibration(True)
        for snap in (replace(self.snapshot, world=replace(self.snapshot.world, sampled_at=9.)),
                     replace(self.snapshot, memory_is_loading=True),
                     replace(self.snapshot, world=replace(self.snapshot.world, camera=None))):
            with self.subTest(snap=snap):
                with patch.object(self.overlay, "_draw_world_marker") as draw:
                    self.assertTrue(any(self.render(snap, calibration=True)))
                draw.assert_not_called()
        for changes in ({"game_active": False}, {"enabled": False}, {"game_found": False}):
            self.assertFalse(any(self.render(replace(self.snapshot, **changes), calibration=True)))

    def test_calibration_uses_native_renderer_and_preserves_painter_state(self):
        self.config.set_show_calibration(True)
        with patch.object(self.overlay, "_draw_world_calibration", wraps=self.overlay._draw_world_calibration) as draw:
            with patch("torchbridge.overlay.interaction.time.monotonic", return_value=10.05):
                frame = self.overlay._render_native(self.snapshot, 1280, 720)
        self.assertEqual((frame.width(), frame.height()), (1280, 720))
        draw.assert_called_once()
        image = QImage(1920, 1080, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        try:
            before = (painter.pen(), painter.brush(), painter.font())
            with patch("torchbridge.overlay.interaction.time.monotonic", return_value=10.05):
                self.overlay._draw_world_calibration(painter, self.snapshot, 1.)
            self.assertEqual((painter.pen(), painter.brush(), painter.font()), before)
        finally:
            painter.end()

    def test_calibration_replaces_optional_position_panel_instead_of_duplicating_it(self):
        self.config.set_show_calibration(True)
        self.config._data["interaction"].update(show_prompt=False, show_positions=True)
        self.assertFalse(any(self.render(self.snapshot)))
        self.assertTrue(any(self.render(self.snapshot, calibration=True)))

    def test_calibration_identifies_merchants_and_quest_givers(self):
        self.config.set_show_calibration(True)
        world = self.snapshot.world
        merchant = replace(world.entities[0], npc_role="merchant")
        quest_giver = replace(world.entities[0], address=0x400000, quest_status="ready_to_turn_in")
        snap = replace(self.snapshot, world=replace(world, entities=(merchant, quest_giver)))
        with patch.object(self.overlay, "_draw_world_marker", wraps=self.overlay._draw_world_marker) as draw:
            with patch.object(self.overlay, "_draw_world_calibration_panel",
                              wraps=self.overlay._draw_world_calibration_panel) as panel:
                self.assertTrue(any(self.render(snap, calibration=True)))
        labels = {call.args[3] for call in draw.call_args_list}
        self.assertIn("Mercador: Vasman", labels)
        self.assertIn("NPC · Missão para entregar (?): Vasman", labels)
        self.assertIn("Mercadores: 1 · NPCs com missão: 1", panel.call_args.args[2])
