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
        self.commands = []
        self.closed = False

    def connect(self, memory, now):
        pass

    def interact(self):
        self.actions += 1

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

    def test_left_stick_only_sends_camera_relative_native_movement(self):
        world = self.engine._memory_state.world
        camera = WorldCamera((1,0,0,0,0,.707,.707,0,0,-.707,.707,-5,0,0,0,1),
                             world.camera.projection)
        self.engine._memory_state = replace(self.engine._memory_state,world=replace(world,camera=camera))
        self.tick(state=replace(self.state,lx=1.,buttons=frozenset()))
        command = self.native.commands[-1]
        self.assertTrue(command["flags"] & WALKING)
        self.assertAlmostEqual(command["dx"],1.)
        self.assertAlmostEqual(command["dz"],0.)
        self.assertEqual(self.injector.events,[])
        self.tick(10.1,replace(self.state,buttons=frozenset()))
        self.assertFalse(self.native.commands[-1]["flags"] & WALKING)
        self.assertEqual(self.injector.events,[])

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
        self.assertEqual(self.injector.events,[])
        self.tick(10.1,replace(self.state,buttons=frozenset({"a"})))
        self.assertTrue(self.injector.moved)
        self.assertIn(("key","SHIFT",True),self.injector.events)
        self.assertIn(("mouse","left",True),self.injector.events)

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
