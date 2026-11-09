"""Explicit interaction, hover acknowledgement, cancellation and input ownership."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from torchbridge.config import ConfigManager, DEFAULT_CONFIG
from torchbridge.engine import BridgeEngine
from torchbridge.input_session import InputCancelled, InputSession
from torchbridge.memory import GameMemoryState
from torchbridge.models import ControllerState, Rect, SharedOverlayState
from test_engine import FakeHub, FakeInjector
from test_world import world_fixture


class WorldInteractionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(ConfigManager(Path(self.directory.name) / "perfil.json"), self.shared)
        self.injector = FakeInjector()
        self.engine.injector = self.injector
        self.cfg = deepcopy(DEFAULT_CONFIG)
        self.rect = Rect(100, 80, 1920, 1080)
        self.state = ControllerState(connected=True, buttons=frozenset({"dpad_up"}))
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True,
                                                    world=world_fixture())

    def tick(self, now, state=None, hover=0):
        self.engine._memory_state = replace(self.engine._memory_state,
                                            world=replace(self.engine._memory_state.world, sampled_at=now),
                                            hover_entity=hover)
        state = self.state if state is None else state
        self.engine._process_active(FakeHub(), state, self.rect, self.cfg, now, 1 / 120)
        self.engine._previous = state

    def test_move_wait_matching_hover_click_release_and_no_hold_repeat(self):
        self.tick(10.)
        self.assertIsNotNone(self.engine._world_click)
        self.assertEqual(self.injector.events, [("move", 1180, 512)])
        target = self.engine._memory_state.world.entities[0]
        self.tick(10.02, hover=target.address)
        self.assertNotIn(("mouse", "left", True), self.injector.events)
        self.tick(10.06, hover=target.address)
        self.assertEqual(self.injector.events[-1], ("mouse", "left", True))
        self.tick(10.14, hover=target.address)
        self.assertIsNone(self.engine._world_click)
        self.assertEqual(self.injector.events[-2:], [("mouse", "left", False), ("move", 100, 100)])
        self.tick(10.16, hover=target.address)
        self.assertEqual(self.injector.events.count(("mouse", "left", True)), 1)

    def test_wrong_hover_and_stale_hover_never_click(self):
        self.tick(10.)
        for now in (10.06, 10.11, 10.22, 10.33):
            self.tick(now, hover=0x123456)
        self.assertNotIn(("mouse", "left", True), self.injector.events)
        self.assertIsNone(self.engine._world_click)
        self.engine._previous = ControllerState()
        self.tick(11.)
        target = self.engine._memory_state.world.entities[0]
        self.engine._memory_state = replace(self.engine._memory_state, hover_entity=target.address)
        self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 11.06)
        self.assertNotIn(("mouse", "left", True), self.injector.events)

    def test_interaction_button_is_rearmed_before_it_can_navigate_the_opened_menu(self):
        self.tick(10.)
        self.engine._needs_rearm = False
        self.assertFalse(self.engine._prepare_active_state(self.state).pressed("dpad_up"))
        self.engine._prepare_active_state(ControllerState(connected=True))
        self.assertTrue(self.engine._prepare_active_state(self.state).pressed("dpad_up"))

    def test_normal_move_hold_released_before_cursor_targets_an_object(self):
        self.engine._held_mouse = {"left", "right"}
        self.engine._direct_move_active = True
        self.tick(10., replace(self.state, lx=1.))
        self.assertEqual(self.injector.events[:3], [("mouse", "left", False),
                                                   ("mouse", "right", False), ("move", 1180, 512)])
        self.assertFalse(self.engine._direct_move_active)

    def test_failed_mouse_release_and_physical_modifiers_prevent_cursor_placement(self):
        self.engine._held_mouse = {"left"}
        self.injector.mouse_button = lambda button, down: False
        self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 10.)
        self.assertIsNone(self.engine._world_click)
        self.assertEqual(self.injector.moved, [])
        self.engine._held_mouse.clear()
        self.injector.buttons["CTRL"] = True
        self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 10.)
        self.assertIsNone(self.engine._world_click)
        self.assertEqual(self.injector.moved, [])

    def test_menus_loading_cursor_radial_combos_and_sequences_block_interaction(self):
        memory = self.engine._memory_state
        cases = [("_memory_state", replace(memory, is_loading=True)),
                 ("_memory_state", replace(memory, is_menu_open=True)),
                 ("_memory_state", replace(memory, open_menus=["Inventário"])),
                 ("_memory_state", replace(memory, dialog_type="simples")),
                 ("_mode", "cursor"), ("_active_panels", ["I", ""]),
                 ("_shortcut_config_active", True), ("_virtual_keyboard_open", True),
                 ("_pet_click_seq", (1,)), ("_hud_click_seq", (1,)), ("_modifier_seq", (1,))]
        for attr, value in cases:
            with self.subTest(attr=attr, value=value):
                before = getattr(self.engine, attr)
                setattr(self.engine, attr, value)
                self.assertFalse(self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 10.))
                self.assertIsNone(self.shared.get().interaction_target)
                setattr(self.engine, attr, before)
        for state in (replace(self.state, buttons=frozenset({"dpad_up", "lb"})),
                      replace(self.state, lt=1.), replace(self.state, rt=1.),
                      replace(self.state, buttons=frozenset({"dpad_up", "a"}))):
            self.assertFalse(self.engine._handle_world_interaction(state, self.rect, self.cfg, 10.))
        self.assertEqual(self.injector.events, [])

    def test_out_of_range_missing_camera_and_old_or_incomplete_world_do_nothing(self):
        initial = self.engine._memory_state.world
        for world in (replace(initial, sampled_at=9.), replace(initial, camera=None),
                      replace(initial, roster_complete=False), replace(initial, entities=()),
                      replace(initial, player_position=replace(initial.player_position, x=50.))):
            self.engine._memory_state = replace(self.engine._memory_state, world=world)
            self.assertFalse(self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 10.))
        self.assertEqual(self.injector.events, [])

    def test_default_radius_reaches_large_stairs_collision_boundary(self):
        world = self.engine._memory_state.world
        stairs = replace(world.entities[0], kind="stairs", name="Stairs Down",
                         position=replace(world.player_position, y=-8.2))
        self.engine._memory_state = replace(self.engine._memory_state, world=replace(world, entities=(stairs,)))
        self.assertEqual(self.cfg["interaction"]["radius"], 4.5)
        self.assertEqual(self.engine._world_target(self.rect, self.cfg), stairs)
        self.cfg["interaction"]["radius"] = 3.5
        self.assertIsNone(self.engine._world_target(self.rect, self.cfg))

    def test_merchant_and_quest_metadata_keep_npc_aim_height_and_explicit_hover_gate(self):
        world = self.engine._memory_state.world
        npc = replace(world.entities[0], npc_role="merchant", quest_status="available")
        self.engine._memory_state = replace(self.engine._memory_state, world=replace(world, entities=(npc,)))
        self.tick(10.)
        self.assertEqual(self.injector.events[-1], ("move", 1180, 512))
        self.tick(10.06, hover=npc.address)
        self.assertEqual(self.injector.events[-1], ("mouse", "left", True))

    def test_pending_click_cancels_on_scene_player_target_menu_resize_and_stall(self):
        original = self.engine._memory_state
        cases = [replace(original, world=replace(original.world, level_address=0x654000)),
                 replace(original, world=replace(original.world, player_address=0x123000)),
                 replace(original, world=replace(original.world, entities=())),
                 replace(original, is_menu_open=True)]
        for memory in cases:
            self.engine._previous = ControllerState()
            self.engine._memory_state = original
            self.tick(10.)
            self.engine._memory_state = memory
            self.assertTrue(self.engine._handle_world_interaction(self.state, self.rect, self.cfg, 10.06))
            self.assertIsNone(self.engine._world_click)
        self.engine._memory_state = original
        for rect, now in ((replace(self.rect, width=1280), 10.06), (self.rect, 10.8)):
            self.engine._previous = ControllerState()
            self.tick(10.)
            self.engine._handle_world_interaction(self.state, rect, self.cfg, now)
            self.assertIsNone(self.engine._world_click)
        self.assertNotIn(("mouse", "left", True), self.injector.events)

    def test_focus_loss_or_disconnect_release_pending_down_without_moving_cursor(self):
        allowed = [True]
        self.engine.injector = InputSession(self.injector, lambda: allowed[0])
        self.tick(10.)
        target = self.engine._memory_state.world.entities[0]
        self.tick(10.06, hover=target.address)
        self.assertIn("left", self.engine._held_mouse)
        allowed[0] = False
        count = len(self.injector.events)
        self.engine._release_all()
        self.assertEqual(self.injector.events[count:], [("mouse", "left", False)])
        self.assertIsNone(self.engine._world_click)
        self.assertIsNone(self.shared.get().interaction_target)
        self.assertFalse(self.engine._held_mouse)

    def test_focus_loss_between_hover_and_press_is_guarded_by_input_session(self):
        allowed = [True]
        self.engine.injector = InputSession(self.injector, lambda: allowed[0])
        self.tick(10.)
        allowed[0] = False
        with self.assertRaises(InputCancelled):
            self.tick(10.06, hover=self.engine._memory_state.world.entities[0].address)
        self.engine._release_all()
        self.assertNotIn(("mouse", "left", True), self.injector.events)

    def test_cancel_after_click_opens_a_menu_releases_before_menu_navigation(self):
        self.tick(10.)
        self.tick(10.06, hover=self.engine._memory_state.world.entities[0].address)
        self.engine._memory_state = replace(self.engine._memory_state, is_menu_open=True,
                                            open_menus=["Pesca"])
        self.tick(10.08)
        self.assertEqual(self.injector.events[-1], ("mouse", "left", False))
        self.assertIsNone(self.engine._world_click)

    def test_nearer_entity_does_not_steal_pending_click(self):
        self.tick(10.)
        first = self.engine._memory_state.world.entities[0]
        nearer = replace(first, address=first.address + 4, position=replace(first.position, x=.1))
        self.engine._memory_state = replace(self.engine._memory_state,
                                            world=replace(self.engine._memory_state.world, entities=(nearer, first)))
        self.tick(10.06, hover=nearer.address)
        self.assertEqual(self.engine._world_click.entity, first.address)
        self.assertNotIn(("mouse", "left", True), self.injector.events)

    def test_profile_defaults_hot_reload_and_rejects_nonfinite_radius(self):
        config = self.engine.config
        self.assertEqual(config.get()["interaction"]["button"], "dpad_up")
        config.path.write_text('{"interaction":{"button":"l3","radius":2,"show_positions":true}}')
        self.assertTrue(config.reload(force=True))
        self.assertEqual(config.get()["interaction"]["button"], "l3")
        config.path.write_text('{"interaction":{"radius":"NaN"}}')
        self.assertFalse(config.reload(force=True))
        self.assertEqual(config.get()["interaction"]["radius"], 2.)
        config.path.write_text('{"interaction":{"button":"a","radius":100}}')
        self.assertTrue(config.reload(force=True))
        self.assertEqual(config.get()["interaction"]["button"], "dpad_up")
        self.assertEqual(config.get()["interaction"]["radius"], 8.)
