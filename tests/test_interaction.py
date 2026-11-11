"""Controller intent, nearest selection and cancellation without world clicks."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from torchbridge.config import ConfigManager, DEFAULT_CONFIG
from torchbridge.engine import BridgeEngine
from torchbridge.input_session import InputCancelled, InputSession
from torchbridge.memory import GameMemoryState
from torchbridge.models import ControllerState, Rect, SharedOverlayState
from torchbridge.native_input import NativeInputStatus, ACTIVE, DIRECT, WALKING, ALLOW_INTERACTION
from torchbridge.world import WorldCamera
from test_engine import FakeHub, FakeInjector
from test_world import world_fixture


class FakeNativeInput:
    def __init__(self):
        self.ready = True
        self.message = "Pronto"
        self.status = NativeInputStatus(flags=17, selected=world_fixture().entities[0].address)
        self.actions = 0
        self.pickups = []
        self.attacks = []
        self.commands = []
        self.closed = False

    def connect(self, memory, now):
        pass

    def interact(self, *, pickup=False, attack=False):
        self.actions += 1
        self.pickups.append(pickup)
        self.attacks.append(attack)

    def send(self, **command):
        self.commands.append(command)

    def close(self):
        self.closed = True


class WorldInteractionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(ConfigManager(Path(self.directory.name) / "perfil.json"), self.shared)
        self.injector = FakeInjector()
        self.engine.injector = self.injector
        self.native = FakeNativeInput()
        self.engine.native_input = self.native
        self.cfg = deepcopy(DEFAULT_CONFIG)
        self.rect = Rect(100, 80, 1920, 1080)
        self.state = ControllerState(connected=True, buttons=frozenset({"dpad_up"}))
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True,
                                                   world=world_fixture())

    def tick(self, now=10., state=None):
        self.engine._memory_state = replace(self.engine._memory_state,
                                            world=replace(self.engine._memory_state.world, sampled_at=now))
        state = self.state if state is None else state
        with patch("torchbridge.engine.core.time.monotonic", return_value=now):
            self.engine._process_active(FakeHub(), state, self.rect, self.cfg, now, 1/120)
        self.engine._previous = state

    def test_dpad_sends_one_native_action_without_moving_or_clicking_mouse(self):
        for now in (10., 10.02, 10.08, 10.3):
            self.tick(now)
        self.assertEqual(self.native.actions, 1)
        self.assertEqual(self.injector.events, [])
        self.assertEqual(self.native.commands[-1]["flags"], ACTIVE | DIRECT | ALLOW_INTERACTION)
        self.assertEqual(self.shared.get().interaction_target, self.engine._memory_state.world.entities[0])

    def test_release_then_repress_is_required_for_another_action(self):
        self.tick()
        self.tick(10.1, replace(self.state, buttons=frozenset()))
        self.tick(10.2)
        self.assertEqual(self.native.actions, 2)

    def pickup_target(self, kind="loot"):
        world = self.engine._memory_state.world
        target = replace(world.entities[0], kind=kind, name="Item no chão")
        self.engine._memory_state = replace(self.engine._memory_state,
                                            world=replace(world, entities=(target,)))
        self.native.status = replace(self.native.status, selected=target.address)
        return target

    def prepared_tick(self, state, now=10.):
        self.engine._needs_rearm = False
        self.tick(now, self.engine._prepare_active_state(state))

    def test_loot_and_gold_use_the_labelled_face_button_for_each_controller(self):
        for family, button in (("xbox", "a"), ("playstation", "a"), ("nintendo", "b")):
            for kind in ("loot", "gold"):
                with self.subTest(family=family, kind=kind):
                    self.pickup_target(kind)
                    self.engine._previous = ControllerState()
                    self.injector.events.clear()
                    before = self.native.actions
                    self.tick(state=replace(self.state, controller_type=family, buttons=frozenset({button})))
                    self.assertEqual(self.native.actions, before + 1)
                    self.assertTrue(self.native.pickups[-1])
                    self.assertEqual(self.shared.get().interaction_button, button)
                    self.assertEqual(self.injector.events, [])

    def test_dpad_does_not_collect_ground_items(self):
        for kind in ("loot", "gold"):
            self.pickup_target(kind)
            self.engine._previous = ControllerState()
            self.tick()
        self.assertEqual(self.native.actions, 0)
        self.assertEqual(self.injector.events, [])

    def test_props_and_npcs_keep_the_world_button_and_non_pickup_intent(self):
        for kind in ("npc", "chest", "door", "stairs", "portal", "lever", "fishing"):
            self.pickup_target(kind)
            self.engine._previous = ControllerState()
            self.tick()
            self.assertEqual(self.shared.get().interaction_button, "dpad_up")
            self.assertFalse(self.native.pickups[-1])
            self.assertFalse(self.native.attacks[-1])
        self.assertEqual(self.native.actions, 7)
        self.assertEqual(self.injector.events, [])

    def test_destructibles_use_the_labelled_a_button_and_send_only_native_attacks(self):
        self.pickup_target("breakable")
        for family, button in (("xbox", "a"), ("playstation", "a"), ("nintendo", "b")):
            with self.subTest(family=family):
                self.engine._previous = ControllerState()
                before = self.native.actions
                self.tick(state=replace(self.state, controller_type=family, buttons=frozenset({button})))
                self.assertEqual(self.native.actions, before + 1)
                self.assertEqual(self.shared.get().interaction_button, button)
                self.assertTrue(self.native.attacks[-1])
                self.assertFalse(self.native.pickups[-1])
                self.assertEqual(self.injector.events, [])

    def test_dpad_and_custom_world_buttons_do_not_attack_destructibles(self):
        self.pickup_target("breakable")
        for button in ("dpad_up", "dpad_down", "l3"):
            self.cfg["interaction"]["button"] = button
            self.engine._previous = ControllerState()
            self.tick(state=replace(self.state, buttons=frozenset({button})))
        self.assertEqual(self.native.actions, 0)
        self.assertEqual(self.injector.events, [])

    def test_holding_attack_after_destruction_cannot_collect_the_new_loot(self):
        self.pickup_target("breakable")
        pressed = replace(self.state, buttons=frozenset({"a"}))
        self.prepared_tick(pressed)
        self.pickup_target("loot")
        for now in (10.02, 10.08, 10.2):
            self.prepared_tick(pressed, now)
        self.assertEqual(self.native.attacks, [True])
        self.assertEqual(self.native.pickups, [False])
        self.assertEqual(self.injector.events, [])
        self.prepared_tick(replace(pressed, buttons=frozenset()), 10.3)
        self.prepared_tick(pressed, 10.4)
        self.assertEqual(self.native.attacks, [True, False])
        self.assertEqual(self.native.pickups, [False, True])

    def test_holding_pickup_does_not_attack_when_the_item_disappears(self):
        self.pickup_target()
        pressed = replace(self.state, buttons=frozenset({"a"}))
        self.prepared_tick(pressed)
        world = self.engine._memory_state.world
        self.engine._memory_state = replace(self.engine._memory_state, world=replace(world, entities=()))
        self.native.status = replace(self.native.status, selected=0)
        for now in (10.02, 10.08, 10.2):
            self.prepared_tick(pressed, now)
        self.assertEqual(self.native.actions, 1)
        self.assertEqual(self.injector.events, [])
        self.prepared_tick(replace(pressed, buttons=frozenset()), 10.3)
        self.prepared_tick(pressed, 10.4)
        self.assertEqual(self.native.actions, 1)
        self.assertIn(("key", "SHIFT", True), self.injector.events)
        self.assertIn(("mouse", "left", True), self.injector.events)

    def test_pickup_requires_release_before_collecting_another_item(self):
        self.pickup_target()
        pressed = replace(self.state, buttons=frozenset({"a"}))
        self.prepared_tick(pressed)
        self.prepared_tick(pressed, 10.1)
        self.assertEqual(self.native.actions, 1)
        self.prepared_tick(replace(pressed, buttons=frozenset()), 10.2)
        self.prepared_tick(pressed, 10.3)
        self.assertEqual(self.native.actions, 2)
        self.assertEqual(self.injector.events, [])

    def test_pickup_releases_a_prior_attack_without_sending_a_new_click(self):
        self.pickup_target()
        self.engine._set_mouse("left", True)
        self.engine._set_mouse("right", True)
        self.engine._set_key("SHIFT", True)
        self.engine._a_shift_held = True
        self.injector.events.clear()
        self.tick(state=replace(self.state, buttons=frozenset({"a"})))
        self.assertEqual(self.native.pickups, [True])
        self.assertNotIn(("mouse", "left", True), self.injector.events)
        self.assertNotIn(("key", "SHIFT", True), self.injector.events)
        self.assertFalse(self.injector.buttons["left"])
        self.assertFalse(self.injector.buttons["right"])
        self.assertFalse(self.injector.buttons["SHIFT"])

    def test_combos_and_other_face_buttons_still_block_pickup(self):
        self.pickup_target()
        for changes in ({"buttons": frozenset({"a", "lb"})},
                        {"buttons": frozenset({"a", "x"})},
                        {"buttons": frozenset({"a"}), "lt": 1.},
                        {"buttons": frozenset({"a"}), "rt": 1.}):
            self.assertFalse(self.engine._handle_world_interaction(
                replace(self.state, **changes), self.rect, self.cfg, 10.))
        self.assertEqual(self.native.actions, 0)

    def test_interaction_button_is_rearmed_before_menu_navigation(self):
        self.tick()
        self.engine._needs_rearm = False
        self.assertFalse(self.engine._prepare_active_state(self.state).pressed("dpad_up"))
        self.engine._prepare_active_state(ControllerState(connected=True))
        self.assertTrue(self.engine._prepare_active_state(self.state).pressed("dpad_up"))

    def test_nearest_is_independent_of_camera_and_screen_projection(self):
        world = self.engine._memory_state.world
        farther = world.entities[0]
        nearer = replace(farther, address=farther.address + 4, name="Mais próximo",
                         position=replace(world.player_position, x=.1))
        for camera in (world.camera, None):
            self.engine._memory_state = replace(self.engine._memory_state,
                world=replace(world, camera=camera, entities=(farther, nearer)))
            self.assertEqual(self.engine._world_target(self.rect, self.cfg), nearer)
            self.assertEqual(self.engine._world_target(Rect(), self.cfg), nearer)

    def test_equal_distances_use_stable_address_tiebreak(self):
        world = self.engine._memory_state.world
        a = world.entities[0]
        b = replace(a, address=a.address+4)
        self.engine._memory_state = replace(self.engine._memory_state, world=replace(world, entities=(b,a)))
        self.assertEqual(self.engine._world_target(self.rect, self.cfg), a)

    def test_prompt_uses_the_same_target_as_native_highlight(self):
        world = self.engine._memory_state.world
        second = replace(world.entities[0], address=0x400000, name="Outro")
        self.engine._memory_state = replace(self.engine._memory_state,
                                            world=replace(world, entities=(*world.entities,second)))
        self.native.status = replace(self.native.status, selected=second.address, flags=21)
        self.tick()
        self.assertEqual(self.shared.get().interaction_target, second)
        self.assertTrue(self.shared.get().native_highlight)
        self.assertEqual(self.native.actions, 1)

    def test_no_mouse_fallback_when_module_or_roster_is_unavailable(self):
        for ready, flags in ((False,17), (True,1)):
            self.native.ready = ready
            self.native.status = replace(self.native.status, flags=flags)
            self.engine._previous = ControllerState()
            self.tick()
        self.assertEqual(self.native.actions, 0)
        self.assertEqual(self.injector.events, [])

    def test_menus_loading_cursor_radial_combos_and_sequences_block_interaction(self):
        memory = self.engine._memory_state
        cases = [("_memory_state",replace(memory,is_loading=True)),
                 ("_memory_state",replace(memory,is_menu_open=True)),
                 ("_memory_state",replace(memory,open_menus=["Inventário"])),
                 ("_memory_state",replace(memory,dialog_type="simples")),
                 ("_mode","cursor"),("_active_panels",["I",""]),
                 ("_shortcut_config_active",True),("_virtual_keyboard_open",True),
                 ("_pet_click_seq",(1,)),("_hud_click_seq",(1,)),("_modifier_seq",(1,))]
        for attr, value in cases:
            before = getattr(self.engine,attr)
            setattr(self.engine,attr,value)
            self.assertFalse(self.engine._handle_world_interaction(self.state,self.rect,self.cfg,10.))
            setattr(self.engine,attr,before)
        for state in (replace(self.state,buttons=frozenset({"dpad_up","lb"})),
                      replace(self.state,lt=1.),replace(self.state,rt=1.),
                      replace(self.state,buttons=frozenset({"dpad_up","a"}))):
            self.assertFalse(self.engine._handle_world_interaction(state,self.rect,self.cfg,10.))
        self.assertEqual(self.native.actions,0)

    def test_stale_or_missing_player_snapshots_never_authorize_interaction(self):
        world = self.engine._memory_state.world
        for changed in (replace(world,sampled_at=9.),
                        replace(world,player_position=None)):
            self.engine._memory_state = replace(self.engine._memory_state,world=changed)
            self.assertFalse(self.engine._handle_world_interaction(self.state,self.rect,self.cfg,10.))
        self.assertEqual(self.native.actions,0)

    def test_partial_external_metadata_does_not_override_the_complete_game_roster(self):
        memory=self.engine._memory_state
        self.engine._memory_state=replace(memory,world=replace(memory.world,roster_complete=False))
        self.tick()
        self.assertEqual(self.native.actions,1)
        self.assertEqual(self.injector.events,[])

    def test_left_stick_moves_cursor_with_marker_and_navigates_natively(self):
        world = self.engine._memory_state.world
        camera = WorldCamera((1,0,0,0,0,.707,.707,0,0,-.707,.707,-5,0,0,0,1),
                             world.camera.projection)
        self.engine._memory_state = replace(self.engine._memory_state,world=replace(world,camera=camera))
        self.tick(state=replace(self.state,lx=1.,buttons=frozenset()))
        command = self.native.commands[-1]
        self.assertTrue(command["flags"] & WALKING)
        self.assertAlmostEqual(command["dx"],1.)
        self.assertAlmostEqual(command["dz"],0.)
        snapshot = self.shared.get()
        self.assertEqual(self.injector.events, [("move", self.rect.left + snapshot.aim_x,
                                               self.rect.top + snapshot.aim_y)])
        events = self.injector.events.copy()
        self.tick(10.1,replace(self.state,buttons=frozenset()))
        self.assertFalse(self.native.commands[-1]["flags"] & WALKING)
        self.assertEqual(self.injector.events,events)
        self.assertEqual(self.native.actions,0)

    def test_action_takes_priority_over_held_walking_stick(self):
        self.tick(state=replace(self.state,lx=1.))
        self.assertEqual(self.native.actions,1)
        self.assertFalse(self.native.commands[-1]["flags"] & WALKING)
        self.assertEqual(self.injector.events,[])

    def test_explicit_attack_uses_walking_heading_without_a_walking_mouse_hold(self):
        world=self.engine._memory_state.world
        camera=WorldCamera((1,0,0,0,0,.707,.707,0,0,-.707,.707,-5,0,0,0,1),
                           world.camera.projection)
        self.engine._memory_state=replace(self.engine._memory_state,world=replace(world,camera=camera))
        self.tick(state=replace(self.state,lx=1.,buttons=frozenset()))
        self.assertEqual(len(self.injector.moved), 1)
        self.assertTrue(all(event[0] == "move" for event in self.injector.events))
        self.tick(10.1,replace(self.state,buttons=frozenset({"a"})))
        self.assertTrue(self.injector.moved)
        self.assertIn(("key","SHIFT",True),self.injector.events)
        self.assertIn(("mouse","left",True),self.injector.events)

    def test_attack_with_stick_held_keeps_cursor_on_the_visible_aim(self):
        world = self.engine._memory_state.world
        camera = replace(world.camera, view=(1,0,0,0,0,.707,.707,0,0,-.707,.707,-5,0,0,0,1))
        self.engine._memory_state = replace(self.engine._memory_state, world=replace(world, camera=camera))
        self.tick(state=replace(self.state, lx=1., buttons=frozenset({"a"})))
        snapshot = self.shared.get()
        self.assertEqual(self.injector.moved, [(self.rect.left + snapshot.aim_x,
                                               self.rect.top + snapshot.aim_y)])
        self.assertIn(("key", "SHIFT", True), self.injector.events)
        self.assertIn(("mouse", "left", True), self.injector.events)

    def test_right_stick_aim_takes_priority_over_walking_aim(self):
        self.tick(state=replace(self.state, lx=1., rx=1., buttons=frozenset()))
        snapshot = self.shared.get()
        self.assertEqual(self.injector.moved, [(self.rect.left + snapshot.aim_x,
                                               self.rect.top + snapshot.aim_y)])
        self.assertFalse(self.native.commands[-1]["flags"] & WALKING)
        self.assertTrue(all(event[0] == "move" for event in self.injector.events))

    def test_focus_guard_cancels_before_native_command_and_release_closes_channel(self):
        self.engine.injector = InputSession(self.injector,lambda:False)
        with self.assertRaises(InputCancelled):
            self.tick()
        self.assertEqual(self.native.commands,[])
        self.engine._release_all()
        self.assertTrue(self.native.closed)

    def test_calibration_receives_native_status_and_destination(self):
        self.native.status = replace(self.native.status,destination_x=4.,destination_z=8.,
                                     blocked_interactions=3,blocked_warps=2)
        self.tick()
        snapshot = self.shared.get()
        self.assertEqual(snapshot.movement_destination,(4.,8.))
        self.assertEqual((snapshot.blocked_interactions,snapshot.blocked_warps),(3,2))
