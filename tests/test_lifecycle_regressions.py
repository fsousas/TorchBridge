"""Regression coverage for launch order, reconnects and interrupted actions."""
import ctypes
from itertools import permutations
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QPointF, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMenu

from torchbridge import win32
from torchbridge.app import _add_fullscreen_actions, _populate_controller_menu
from torchbridge.config import ConfigManager, DEFAULT_CONFIG
from torchbridge.controller import ControllerHub, pygame
from torchbridge.engine import BridgeEngine
from torchbridge.input_session import InputCancelled, InputSession
from torchbridge.mathutils import radial_deadzone
from torchbridge.memory import TorchlightMemoryReader, GameMemoryState, RVA_CGAME_STEAM, OFFSET_GAMECLIENT
from torchbridge import memory
from torchbridge.models import ControllerState, Rect, SharedOverlayState
from torchbridge.overlay import GameOverlay


class WindowSelectionTests(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.windows = {}
        self.foreground = 0
        self.api.IsWindow.side_effect = lambda hwnd: hwnd in self.windows
        self.api.IsWindowVisible.side_effect = lambda hwnd: hwnd in self.windows
        self.api.GetForegroundWindow.side_effect = lambda: self.foreground
        self.api.GetWindowThreadProcessId.side_effect = lambda hwnd, out: setattr(out._obj, "value", hwnd)

        def enumerate_windows(callback, _):
            for hwnd in list(self.windows):
                if not callback(hwnd, 0):
                    break
        self.api.EnumWindows.side_effect = enumerate_windows
        for context in (
            patch.object(win32, "IS_WINDOWS", True),
            patch.object(win32, "user32", self.api, create=True),
            patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
            patch.object(win32.WindowLocator, "_process_name", side_effect=lambda pid: self.windows[pid][0]),
            patch.object(win32.WindowLocator, "title", side_effect=lambda hwnd: self.windows[hwnd][1]),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.locator = win32.WindowLocator(["Torchlight.exe"], ["Torchlight"])

    def test_all_launch_orders_ignore_explorer_and_find_game(self):
        for order in permutations(("game", "bridge", "controller")):
            with self.subTest(order=order):
                self.windows = {10: ("explorer.exe", "Torchlight")}
                self.locator._cached = None
                for step in order:
                    if step == "game":
                        self.windows[20] = ("Torchlight.exe", "Torchlight")
                    self.assertEqual(self.locator.find(), 20 if 20 in self.windows else None)

    def test_foreground_game_replaces_auxiliary_window_and_reused_handle_is_rejected(self):
        self.windows = {10: ("Torchlight.exe", "Launcher")}
        self.assertEqual(self.locator.find(), 10)
        self.windows[20] = ("Torchlight.exe", "Torchlight")
        self.foreground = 20
        self.assertEqual(self.locator.find(), 20)
        self.windows = {20: ("explorer.exe", "Torchlight")}
        self.assertIsNone(self.locator.find())


class ControllerSelectionTests(unittest.TestCase):
    def make_hub(self):
        with patch("torchbridge.controller.pygame.display.init"), \
                patch("torchbridge.controller.pygame.joystick.init"), \
                patch("torchbridge.controller.sdl_controller.init"):
            return ControllerHub()

    def test_linux_enumeration_preserves_the_running_sdl_subsystems(self):
        hub = self.make_hub()
        with patch("torchbridge.controller.IS_WINDOWS", False), \
                patch("torchbridge.controller.pygame.joystick.get_count", return_value=0), \
                patch("torchbridge.controller.pygame.joystick.quit") as joystick_quit, \
                patch("torchbridge.controller.sdl_controller.quit") as controller_quit:
            hub._refresh_devices()
        joystick_quit.assert_not_called()
        controller_quit.assert_not_called()

    def test_windows_empty_scan_reinitializes_discovery_before_enumerating(self):
        hub = self.make_hub()
        visible = False
        joystick = MagicMock()
        joystick.get_guid.return_value = "late-pad"
        joystick.get_name.return_value = "Connected after launch"
        joystick.get_instance_id.return_value = 42

        def initialize_joysticks():
            nonlocal visible
            visible = True

        with patch("torchbridge.controller.IS_WINDOWS", True), \
                patch("torchbridge.controller.pygame.joystick.quit") as joystick_quit, \
                patch("torchbridge.controller.sdl_controller.quit") as controller_quit, \
                patch("torchbridge.controller.pygame.joystick.init", side_effect=initialize_joysticks), \
                patch("torchbridge.controller.sdl_controller.init") as controller_init, \
                patch("torchbridge.controller.pygame.joystick.get_count", side_effect=lambda: int(visible)), \
                patch("torchbridge.controller.pygame.joystick.Joystick", return_value=joystick):
            hub._refresh_devices()
        self.assertEqual(hub.devices, (("late-pad", "Connected after launch"),))
        joystick_quit.assert_called_once()
        controller_quit.assert_called_once()
        controller_init.assert_called_once()

    def test_windows_reconnection_reinitializes_discovery_even_with_stale_device_list(self):
        hub = self.make_hub()
        # Simula que um controle estava conectado previamente no cache _devices,
        # mas foi desconectado e o dispositivo não está saudável.
        hub._devices = [(0, "stale-pad", "Disconnected pad", 10)]
        visible = False
        joystick = MagicMock()
        joystick.get_guid.return_value = "reconnected-pad"
        joystick.get_name.return_value = "Reconnected DualSense"
        joystick.get_instance_id.return_value = 20

        def initialize_joysticks():
            nonlocal visible
            visible = True

        with patch("torchbridge.controller.IS_WINDOWS", True), \
                patch("torchbridge.controller.pygame.joystick.quit") as joystick_quit, \
                patch("torchbridge.controller.sdl_controller.quit") as controller_quit, \
                patch("torchbridge.controller.pygame.joystick.init", side_effect=initialize_joysticks), \
                patch("torchbridge.controller.sdl_controller.init") as controller_init, \
                patch("torchbridge.controller.pygame.joystick.get_count", side_effect=lambda: int(visible)), \
                patch("torchbridge.controller.pygame.joystick.Joystick", return_value=joystick):
            hub._refresh_devices()
        self.assertEqual(hub.devices, (("reconnected-pad", "Reconnected DualSense"),))
        joystick_quit.assert_called_once()
        controller_quit.assert_called_once()
        controller_init.assert_called_once()

    def test_transient_enumeration_error_returns_disconnected_and_recovers(self):
        hub = self.make_hub()
        joystick = MagicMock()
        joystick.get_guid.return_value = "wanted"
        joystick.get_name.return_value = "Pad"
        joystick.get_instance_id.return_value = 123
        joystick.get_numaxes.return_value = 0
        joystick.get_numbuttons.return_value = 0
        joystick.get_numhats.return_value = 0
        raw = dict(DEFAULT_CONFIG["raw_controller"], force_raw=True)
        with patch("torchbridge.controller.pygame.event.get", return_value=[]), \
                patch("torchbridge.controller.pygame.joystick.get_count", side_effect=[pygame.error("removed"), 1]), \
                patch("torchbridge.controller.pygame.joystick.Joystick", return_value=joystick):
            self.assertFalse(hub.poll(raw).connected)
            self.assertTrue(hub.poll(raw).connected)

    def test_sdl_preference_survives_device_order_and_absence(self):
        hub = self.make_hub()
        controller = MagicMock()
        controller.get_axis.return_value = 0
        controller.get_button.return_value = False
        def open_selected(index):
            record = hub._devices[index]
            controller.as_joystick.return_value.get_guid.return_value = record[1]
            controller.as_joystick.return_value.get_instance_id.return_value = record[3]
            return controller
        with patch("torchbridge.controller.pygame.event.get", return_value=[]), \
                patch.object(hub, "_refresh_devices") as refresh, \
                patch("torchbridge.controller.sdl_controller.is_controller", return_value=True), \
                patch("torchbridge.controller.sdl_controller.Controller", side_effect=open_selected) as open_pad:
            hub._devices = [(0, "other", "Other", 10), (1, "wanted", "Wanted", 20)]
            state = hub.poll(DEFAULT_CONFIG["raw_controller"], "wanted")
            self.assertEqual((state.device_guid, state.instance_id), ("wanted", 20))
            open_pad.assert_called_once_with(1)
            hub._devices = [(0, "other", "Other", 10)]
            self.assertFalse(hub.poll(DEFAULT_CONFIG["raw_controller"], "wanted").connected)
            hub._devices = [(0, "wanted", "Wanted", 30), (1, "other", "Other", 10)]
            self.assertEqual(hub.poll(DEFAULT_CONFIG["raw_controller"], "wanted").instance_id, 30)

    def test_controller_device_removed_uses_which_attribute_safely(self):
        hub = self.make_hub()
        hub._instance_id = 42
        hub._controller = MagicMock()
        hub._controller.attached.return_value = True
        hub._devices = [(0, "guid", "Name", 42)]
        remove_event = pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, {"which": 42})
        with patch("torchbridge.controller.pygame.event.get", return_value=[remove_event]), \
                patch.object(hub, "_scan"):
            hub.poll(DEFAULT_CONFIG["raw_controller"])
        self.assertIsNone(hub._instance_id)
        self.assertIsNone(hub._controller)

    def test_trigger_rescan_preserves_healthy_controller(self):
        hub = self.make_hub()
        hub._instance_id = 99
        hub._controller = MagicMock()
        hub._controller.attached.return_value = True
        hub._devices = [(0, "guid", "Name", 99)]
        hub.trigger_rescan()
        self.assertEqual(hub._instance_id, 99)
        self.assertIsNotNone(hub._controller)
        self.assertFalse(hub._rescan_requested)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Uses the bundled Linux SDL shared library")
    def test_real_sdl_raw_disconnect_reconnect_uses_new_instance(self):
        library = next(Path(pygame.__file__).parent.parent.glob("pygame_ce.libs/libSDL2-2*.so*"), None)
        if library is None:
            self.skipTest("Bundled SDL not available")
        with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}):
            hub = ControllerHub()
        self.addCleanup(hub.close)
        sdl = ctypes.CDLL(str(library))
        sdl.SDL_JoystickAttachVirtual.argtypes = (ctypes.c_int,) * 4
        sdl.SDL_JoystickAttachVirtual.restype = ctypes.c_int
        sdl.SDL_JoystickDetachVirtual.argtypes = (ctypes.c_int,)
        raw = dict(DEFAULT_CONFIG["raw_controller"], force_raw=True)
        index = sdl.SDL_JoystickAttachVirtual(1, 6, 16, 1)
        self.assertGreaterEqual(index, 0)
        virtual = pygame.joystick.Joystick(index)
        raw["device_guid"] = virtual.get_guid()
        virtual.quit()
        first = hub.poll(raw)
        self.assertTrue(first.connected)
        self.assertEqual(first.device_guid, raw["device_guid"])
        self.assertEqual(sdl.SDL_JoystickDetachVirtual(index), 0)
        self.assertFalse(hub.poll(raw).connected)
        new_index = sdl.SDL_JoystickAttachVirtual(1, 6, 16, 1)
        self.addCleanup(sdl.SDL_JoystickDetachVirtual, new_index)
        second = hub.poll(raw)
        self.assertTrue(second.connected)
        self.assertNotEqual(first.instance_id, second.instance_id)
        for _ in range(2):
            hub._last_scan = 0.0
            self.assertEqual(hub.poll(raw).instance_id, second.instance_id)


class EngineRegressionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = ConfigManager(Path(directory.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.injector = MagicMock()
        self.injector.key_pressed.return_value = False
        self.injector.cursor_position.return_value = (1500, 400)
        self.engine.injector = self.injector
        self.engine.locator = MagicMock()
        self.rect = Rect(0, 0, 1920, 1080)
        self.hub = MagicMock()

    def test_keyboard_start_release_is_consumed(self):
        engine = self.engine
        engine._memory_state = GameMemoryState(is_connected=True, state_id=1, is_menu_open=True)
        engine._handle_char_create_navigation(ControllerState(), self.rect, self.hub)
        engine._open_virtual_keyboard("character_name", self.rect, self.hub)
        self.injector.reset_mock()
        for state in (ControllerState(buttons={"start"}), ControllerState(buttons={"start"}), ControllerState()):
            engine._process_active(self.hub, state, self.rect, self.config.get(), 1., .008)
            engine._previous = state
        self.assertFalse(engine._virtual_keyboard_open)
        self.injector.tap.assert_not_called()
        engine._process_active(self.hub, ControllerState(), self.rect, self.config.get(), 1.1, .008)
        self.injector.tap.assert_not_called()

    def test_interruption_and_session_reset_clear_keyboard_and_pending_clicks(self):
        for reset in (self.engine._release_all, self.engine._reset_radial_session):
            self.engine._open_virtual_keyboard("pet_name", self.rect, self.hub)
            self.shared.keyboard_event("click", 100, 100)
            reset()
            self.assertFalse(self.shared.get().virtual_keyboard_open)
            self.assertFalse(self.engine._virtual_keyboard_open)
            self.assertEqual(self.shared.take_keyboard_events(), [])

    def test_failed_release_is_retained_and_retried(self):
        self.engine._held_mouse.add("left")
        self.engine._held_keys.add("ALT")
        self.injector.mouse_button.return_value = False
        self.injector.key.return_value = False
        self.engine._release_all()
        self.assertIn("left", self.engine._held_mouse)
        self.assertIn("ALT", self.engine._held_keys)
        self.injector.mouse_button.return_value = True
        self.injector.key.return_value = True
        self.engine._release_all()
        self.assertFalse(self.engine._held_mouse)
        self.assertFalse(self.engine._held_keys)

    def test_resume_requires_release_before_reusing_held_buttons_and_triggers(self):
        held = ControllerState(buttons=frozenset({"a", "start"}), rt=1.)
        for _ in range(2):
            filtered = self.engine._prepare_active_state(held)
            self.assertFalse(filtered.buttons)
            self.assertEqual(filtered.rt, 0.)
        neutral = self.engine._prepare_active_state(ControllerState())
        self.engine._previous = filtered
        self.engine._handle_center_buttons(neutral, self.rect, self.config.get()["bindings"], 1.)
        self.injector.tap.assert_not_called()
        fresh = self.engine._prepare_active_state(held)
        self.assertEqual(fresh.buttons, held.buttons)
        self.assertEqual(fresh.rt, 1.)

    def test_rt_release_arms_walking_resume(self):
        self.engine._memory_state = GameMemoryState(is_connected=True, is_in_game=True, state_id=6)
        self.engine._previous = ControllerState(rt=1., lx=1.)
        self.engine._previous_rt_active = True
        with patch.object(self.engine, "_move_pointer", return_value=True):
            self.engine._process_active(self.hub, ControllerState(lx=1.), self.rect, self.config.get(), 5., .008)
        self.assertEqual(self.engine._auto_move_resume_times, [5.15, 5.3])

    def test_tab_action_cancels_before_click_after_focus_loss(self):
        engine = self.engine
        engine._inventory_initialized = True
        engine._inventory_tab = "tab-1"
        engine._rt_edge_up = True
        allowed = iter((True, False))
        engine.injector = InputSession(self.injector, lambda: next(allowed, False))
        engine._input_context = (self.hub, 10, 20, 30, self.config.get())
        with patch.object(engine, "_input_allowed", return_value=False):
            with self.assertRaises(InputCancelled):
                engine._handle_inventory_navigation(ControllerState(), self.rect, self.hub)
        self.injector.mouse_button.assert_not_called()

    def test_input_lease_expires_on_pause_focus_pid_or_controller_change(self):
        engine = self.engine
        engine._input_context = (self.hub, 10, 20, 30, self.config.get())
        engine.locator.is_foreground.return_value = True
        engine.locator.window_pid.return_value = 20
        self.hub.poll.return_value = ControllerState(connected=True, instance_id=30)
        self.assertTrue(engine._input_allowed())
        engine.locator.is_foreground.return_value = False
        self.assertFalse(engine._input_allowed())
        engine.locator.is_foreground.return_value = True
        engine.set_enabled(False)
        self.assertFalse(engine._input_allowed())
        engine.set_enabled(True)
        engine.locator.window_pid.return_value = 21
        self.assertFalse(engine._input_allowed())
        engine.locator.window_pid.return_value = 20
        self.hub.poll.return_value = ControllerState(connected=True, instance_id=31)
        self.assertFalse(engine._input_allowed())

    def test_run_loop_recovers_for_every_launch_order(self):
        for order in permutations(("game", "bridge", "controller")):
            with self.subTest(order=order):
                engine = BridgeEngine(self.config, SharedOverlayState())
                engine.injector = MagicMock()
                engine.memory = MagicMock()
                engine.memory.update.return_value = GameMemoryState(is_connected=True, is_in_game=True, state_id=6)
                engine.locator = MagicMock()
                engine.locator.client_rect.return_value = self.rect
                engine.locator.window_pid.return_value = 20
                engine.locator.is_foreground.return_value = True
                started = set(order[:order.index("bridge")])
                remaining = list(order[order.index("bridge") + 1:])
                hub = MagicMock()
                hub.devices = (("test-pad", "Pad"),)
                polls = 0

                def poll(*_):
                    nonlocal polls
                    polls += 1
                    if polls > 1 and remaining:
                        started.add(remaining.pop(0))
                    if polls >= 5:
                        engine.stop()
                    return ControllerState(connected="controller" in started, name="Pad", instance_id=30)

                hub.poll.side_effect = poll
                engine.locator.find.side_effect = lambda: 10 if "game" in started else None
                with patch("torchbridge.engine.ControllerHub", return_value=hub), \
                        patch("torchbridge.engine.begin_high_resolution_timer"), \
                        patch("torchbridge.engine.end_high_resolution_timer"), \
                        patch.object(engine, "_process_active") as process:
                    engine.run()
                self.assertGreater(process.call_count, 0)
                self.assertFalse(engine.shared.get().engine_error)
                hub.close.assert_called_once()

    def test_fatal_error_is_published_for_tray_even_without_overlay(self):
        with patch("torchbridge.engine.ControllerHub", side_effect=RuntimeError("init failed")), \
                patch("torchbridge.engine.begin_high_resolution_timer"), \
                patch("torchbridge.engine.end_high_resolution_timer"), \
                self.assertLogs("torchbridge.engine", level="ERROR"):
            self.engine.run()
        self.assertTrue(self.shared.get().engine_error)
        self.assertFalse(self.shared.get().game_found)


class InputSessionTests(unittest.TestCase):
    def test_cancel_blocks_new_input_but_releases_untracked_click(self):
        injector = MagicMock()
        permitted = True
        session = InputSession(injector, lambda: permitted)
        session.mouse_button("left", True)
        session.key("CTRL", True)
        permitted = False
        for action in (lambda: session.mouse_button("right", True), lambda: session.tap("I"),
                       lambda: session.text("a"), lambda: session.move(1, 2)):
            with self.assertRaises(InputCancelled):
                action()
        injector.mouse_button.return_value = False
        session.release_all()
        self.assertIn("left", session.mouse)
        injector.mouse_button.return_value = True
        session.release_all()
        self.assertFalse(session.mouse)
        self.assertFalse(session.keys)
        injector.mouse_button.assert_any_call("left", False)


class ProfileAndMemoryTests(unittest.TestCase):
    def test_nested_invalid_raw_profiles_retain_last_good_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigManager(Path(directory) / "perfil.json")
            before = config.get()
            for raw in ({"axes": []}, {"triggers": None}, {"buttons": {"a": []}},
                        {"axes": {"left_x": {"index": "bad"}}},
                        {"buttons": {"dpad_up": {"type": "hat", "value": [0]}}},
                        {"triggers": {"left": {"rest": float("nan")}}}):
                with self.subTest(raw=raw):
                    config.path.write_text(json.dumps({"raw_controller": raw}), encoding="utf-8")
                    self.assertFalse(config.reload(force=True))
                    self.assertEqual(config.get(), before)
                    self.assertTrue(config.last_error)

    def test_preferred_controller_persists_without_reusing_foreign_raw_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigManager(Path(directory) / "perfil.json")
            mapping = dict(DEFAULT_CONFIG["raw_controller"], device_guid="calibrated", force_raw=True)
            config.update_raw_mapping(mapping)
            config.select_controller("sdl")
            fresh = ConfigManager(config.path)
            self.assertEqual(fresh.get()["input"]["device_guid"], "sdl")
            self.assertFalse(fresh.get()["raw_controller"]["force_raw"])
            fresh.select_controller("calibrated")
            self.assertTrue(fresh.get()["raw_controller"]["force_raw"])

    def test_steam_fixed_base_outside_steam_directory(self):
        reader = TorchlightMemoryReader()
        reader._module_base = 0x00400000
        reader._exe_path = r"C:\Games\Torchlight\Torchlight.exe"
        address = reader._module_base + RVA_CGAME_STEAM
        reader.read_u32 = lambda addr: {address: 0x05000000, 0x05000000 + OFFSET_GAMECLIENT: 0x06000000}.get(addr)
        self.assertEqual(reader._resolve_cgame_address(), address)
        self.assertEqual(reader.game_version, "Steam")

    def test_remembering_detected_controller_preserves_user_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigManager(Path(directory) / "perfil.json")
            mapping = dict(DEFAULT_CONFIG["raw_controller"], device_guid="calibrated", force_raw=False)
            config.update_raw_mapping(mapping)
            config.select_controller("calibrated", apply_raw_mapping=False)
            self.assertFalse(config.get()["raw_controller"]["force_raw"])
            config.select_controller("calibrated")
            self.assertTrue(config.get()["raw_controller"]["force_raw"])
            config.select_controller("")
            self.assertFalse(config.get()["raw_controller"]["force_raw"])

    def test_full_diagonal_has_same_length_as_cardinal(self):
        for vector in ((1., 1.), (-1., 1.), (.9, -.9), (1., 0.)):
            x, y, magnitude = radial_deadzone(*vector)
            self.assertAlmostEqual(math.hypot(x, y), magnitude)
            self.assertLessEqual(math.hypot(x, y), 1.)

    def test_win32_signatures_preserve_pointer_sized_handles(self):
        with patch.object(memory, "kernel32") as kernel, patch.object(memory, "psapi") as psapi, \
                patch.object(memory, "user32"), \
                patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True):
            memory._configure_win32_api()
            self.assertIs(kernel.OpenProcess.restype, ctypes.wintypes.HANDLE)
            self.assertIs(kernel.CreateToolhelp32Snapshot.restype, ctypes.wintypes.HANDLE)
            self.assertIs(psapi.GetModuleFileNameExW.argtypes[1], ctypes.wintypes.HMODULE)
            self.assertIs(kernel.ReadProcessMemory.argtypes[3], ctypes.c_size_t)

    def test_invalid_snapshot_handle_is_not_enumerated_or_closed(self):
        reader = TorchlightMemoryReader()
        with patch.object(memory, "kernel32") as kernel:
            kernel.CreateToolhelp32Snapshot.return_value = ctypes.c_void_p(-1).value
            self.assertIsNone(reader._find_pid())
            kernel.Process32First.assert_not_called()
            kernel.CloseHandle.assert_not_called()


class TrayAndKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fullscreen_actions_call_installer_and_remover(self):
        menu = QMenu()
        with patch("torchbridge.fullscreen.configure_dialog") as configure:
            _add_fullscreen_actions(menu)
            menu.actions()[0].trigger()
            configure.assert_called_once_with()
            menu.actions()[1].trigger()
            self.assertEqual(configure.call_args.kwargs, {"uninstall": True})

    def test_controller_menu_persists_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigManager(Path(directory) / "perfil.json")
            menu = QMenu()
            _populate_controller_menu(menu, config, (("first", "First"), ("second", "Second")))
            menu.actions()[2].trigger()
            self.assertEqual(config.get()["input"]["device_guid"], "second")
            _populate_controller_menu(menu, config, ())
            self.assertTrue(menu.actions()[-1].isChecked())

    def test_keyboard_surface_consumes_clicks_without_making_overlay_interactive(self):
        with tempfile.TemporaryDirectory() as directory:
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, ConfigManager(Path(directory) / "perfil.json"))
            self.addCleanup(overlay.shutdown)
            surface = overlay._keyboard_input
            self.assertFalse(surface.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            self.assertFalse(surface.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            surface.physical_rect = Rect(100, 50, 200, 100)
            surface.resize(200, 100)
            event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 20), QPointF(10, 20),
                                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(surface, event)
            self.assertEqual(shared.take_keyboard_events(), [("click", 110, 70)])
