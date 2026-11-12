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


class RecordingPainter(QPainter):
    def __init__(self, image):
        super().__init__(image)
        self.texts = []
        self.images = []
        self.image_rects = []

    def drawText(self, *args):
        self.texts.append(args[-1])
        return super().drawText(*args)

    def drawPixmap(self, *args):
        self.images.append(args[1])
        self.image_rects.append(args[0])
        return super().drawPixmap(*args)


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

    def render(self, snapshot, scale=1., calibration=False, dpi=None):
        image = QImage(snapshot.game_rect.width, snapshot.game_rect.height, QImage.Format.Format_ARGB32)
        if dpi is not None:
            image.setDotsPerMeterX(round(dpi / .0254))
            image.setDotsPerMeterY(round(dpi / .0254))
        image.fill(Qt.GlobalColor.transparent)
        painter = RecordingPainter(image)
        try:
            with patch("torchbridge.overlay.interaction.time.monotonic", return_value=10.05):
                if calibration:
                    self.overlay._draw_world_calibration(painter, snapshot, scale)
                else:
                    self.overlay._draw_world_interaction(painter, snapshot, scale)
        finally:
            painter.end()
        self.drawn_text = painter.texts
        self.drawn_images = painter.images
        self.drawn_image_rects = painter.image_rects
        return bytes(image.constBits())

    def test_all_six_assets_render_for_the_correct_controller_and_action(self):
        frames = []
        for family in ("xbox", "playstation", "nintendo"):
            for kind, face_button in (("npc", False), ("loot", True), ("gold", True), ("breakable", True)):
                with self.subTest(family=family, kind=kind):
                    target = replace(self.snapshot.interaction_target, kind=kind)
                    snap = replace(self.snapshot, controller_type=family, interaction_target=target,
                                   interaction_button=("b" if family == "nintendo" else "a") if face_button else "dpad_up")
                    with patch.object(self.overlay, "_interaction_icon", wraps=self.overlay._interaction_icon) as icon:
                        pixels = self.render(snap)
                    icon.assert_called_once_with(family, face_button)
                    self.assertEqual(self.drawn_text, ["Vasman · 0.5"])
                    self.assertEqual(len(self.drawn_images), 1)
                    self.assertFalse(self.drawn_images[0].isNull())
                    if kind in ("npc", "loot"):
                        frames.append(pixels)
        self.assertEqual(len(set(frames)), 6)

    def test_controller_layout_override_selects_the_same_family_as_the_hud(self):
        self.config._data["overlay"]["controller_layout"] = "playstation"
        with patch.object(self.overlay, "_interaction_icon", wraps=self.overlay._interaction_icon) as icon:
            self.render(replace(self.snapshot, controller_type="xbox"))
        icon.assert_called_once_with("playstation", False)

    def test_realistic_neutral_shops_from_memory_render_their_role_and_dpad(self):
        from test_world_memory import memory_fixture
        for unit_type, name, label in ((41, "Tarn", "Mercador"),
                                       (127, "Duros", "Mercador (Apostador)"),
                                       (128, "Stash", "Baú pessoal")):
            with self.subTest(unit_type=unit_type):
                space, reader, client, _, player, _, npc, *_ = memory_fixture()
                space.u32(npc + 0x174, unit_type)
                space.f32(npc + 0x394, 30.)
                space.string(npc + 0x420, name)
                for address, x in ((player, 0.), (npc, .5)):
                    space.f32(address + 0x70, x)
                    space.f32(address + 0x74, 0.)
                    space.f32(address + 0x78, -4.)
                world = reader._world_reader.read(client, player, 10.)
                target = next(e for e in world.entities if e.address == npc)
                with patch.object(self.overlay, "_interaction_icon", wraps=self.overlay._interaction_icon) as icon:
                    self.render(replace(self.snapshot, world=world, interaction_target=target,
                                        interaction_button="dpad_up", controller_type="xbox"))
                icon.assert_called_once_with("xbox", False)
                self.assertIn(label, self.drawn_text[0])
                self.assertIn(name, self.drawn_text[0])
                self.assertEqual(len(self.drawn_images), 1)

    def test_visible_native_prop_label_gets_only_an_icon_on_its_left(self):
        for kind in ("door", "portal", "stairs", "lever", "chest", "interactive", "fishing"):
            for width, height, scale in ((1920, 1080, 1.), (1280, 720, 1.5)):
                with self.subTest(kind=kind, width=width):
                    target = replace(self.snapshot.interaction_target, kind=kind,
                                     native_label_rect=(.4, .3, .6, .35))
                    snap = replace(self.snapshot, game_rect=Rect(-1280, 80, width, height),
                                   interaction_target=target)
                    self.render(snap, scale)
                    self.assertEqual(self.drawn_text, [])
                    self.assertEqual(len(self.drawn_images), 1)
                    rect = self.drawn_image_rects[0]
                    self.assertAlmostEqual(rect.right(), width * .4 - 2 * scale)
                    self.assertAlmostEqual(rect.height(), 48 * scale)
                    self.assertAlmostEqual(rect.center().y(), height * .325)
                    # No duplicate box/text is painted over the game's own name.
                    self.assertLess(rect.right(), width * .4)

    def test_hidden_native_label_restores_the_overlay_name_and_icon(self):
        target = replace(self.snapshot.interaction_target, kind="door", native_label_rect=(.4, .3, .6, .35))
        self.render(replace(self.snapshot, interaction_target=target))
        self.assertEqual(self.drawn_text, [])
        self.render(replace(self.snapshot, interaction_target=replace(target, native_label_rect=None)))
        self.assertEqual(self.drawn_text, ["Vasman · 0.5"])
        self.assertEqual(len(self.drawn_images), 1)

    def test_native_label_does_not_replace_npc_pickup_or_destructible_prompts(self):
        for kind in ("npc", "loot", "gold", "breakable"):
            with self.subTest(kind=kind):
                target = replace(self.snapshot.interaction_target, kind=kind,
                                 native_label_rect=(.4, .3, .6, .35))
                self.render(replace(self.snapshot, interaction_target=target))
                self.assertEqual(self.drawn_text, ["Vasman · 0.5"])

    def test_icon_replaces_only_the_button_and_preserves_npc_details(self):
        target = replace(self.snapshot.interaction_target, name="Miner", quest_status="unavailable")
        self.render(replace(self.snapshot, interaction_target=target))
        self.assertEqual(self.drawn_text, ["NPC · Missão indisponível: Miner · 0.5"])
        self.assertEqual(len(self.drawn_images), 1)

    def test_long_names_keep_the_distance_visible(self):
        target = replace(self.snapshot.interaction_target, name="Nome muito longo " * 50)
        self.render(replace(self.snapshot, interaction_target=target))
        self.assertIn("…", self.drawn_text[0])
        self.assertTrue(self.drawn_text[0].endswith(" · 0.5"))

    def test_prompt_keeps_npc_details_and_geometry_at_different_device_dpi(self):
        target = replace(self.snapshot.interaction_target, name="Miner", quest_status="unavailable")
        snapshot = replace(self.snapshot, interaction_target=target)
        for scale in (1., 1.5):
            reference = self.render(snapshot, scale, dpi=96)
            for dpi in (96, 144, 192):
                with self.subTest(scale=scale, dpi=dpi):
                    frame = self.render(snapshot, scale, dpi=dpi)
                    self.assertEqual(self.drawn_text, ["NPC · Missão indisponível: Miner · 0.5"])
                    self.assertEqual(frame, reference)

    def test_missing_image_falls_back_to_the_correct_button_label(self):
        for kind in ("loot", "breakable"):
            target = replace(self.snapshot.interaction_target, kind=kind)
            with patch.object(self.overlay, "_interaction_icon", return_value=None):
                self.render(replace(self.snapshot, controller_type="playstation", interaction_target=target,
                                    interaction_button="a"))
            self.assertEqual(self.drawn_text, ["[×] Vasman · 0.5"])
            self.assertEqual(self.drawn_images, [])

    def test_custom_world_button_does_not_show_an_incorrect_dpad_up_image(self):
        self.render(replace(self.snapshot, interaction_button="dpad_down"))
        self.assertEqual(self.drawn_text, ["[D-pad ↓] Vasman · 0.5"])
        self.assertEqual(self.drawn_images, [])

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

    def test_calibration_shows_native_movement_highlight_and_blocked_events(self):
        self.config.set_show_calibration(True)
        snap=replace(self.snapshot,movement_status="Caminhando",native_input_ready=True,
                     native_highlight=True,movement_direction=(.5,-.5),
                     movement_destination=(12.,34.),blocked_interactions=3,blocked_warps=2)
        with patch.object(self.overlay,"_draw_world_calibration_panel",
                          wraps=self.overlay._draw_world_calibration_panel) as panel:
            self.assertTrue(any(self.render(snap,calibration=True)))
        lines=panel.call_args.args[2]
        self.assertIn("Movimento seguro: Caminhando",lines)
        self.assertTrue(any("12.00, 34.00" in line for line in lines))
        self.assertTrue(any("Highlight: ativo" in line and "3 usos / 2 transições" in line for line in lines))
