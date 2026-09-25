"""Testes unitários para o sistema de detecção e navegação de diálogos e telas de história."""
import unittest
from unittest.mock import MagicMock, patch

from torchbridge.memory import strip_torchlight_formatting, GameMemoryState, TorchlightMemoryReader
from torchbridge.models import (
    Rect,
    OverlaySnapshot,
    dialog_button_point,
    DIALOG_BUTTON_Y_FRACTION,
)
from torchbridge.controller import ControllerState


class DialogFormattingAndPointsTests(unittest.TestCase):
    def test_strip_torchlight_formatting(self):
        self.assertEqual(
            strip_torchlight_formatting("The |cFFFFBA00Gleaming Ember|u"),
            "The Gleaming Ember",
        )
        self.assertEqual(
            strip_torchlight_formatting("|cFFFFBA00Battle Varkaseer|u"),
            "Battle Varkaseer",
        )
        self.assertEqual(strip_torchlight_formatting(""), "")
        self.assertEqual(strip_torchlight_formatting("Plain text"), "Plain text")

    def test_dialog_button_point_calculations(self):
        rect = Rect(left=0, top=0, width=1024, height=768)
        self.assertTrue(rect.valid)

        # Ok button: exactly centered horizontally
        ok_x, ok_y = dialog_button_point(rect, "ok")
        self.assertEqual(ok_x, 512)
        self.assertEqual(ok_y, round(768 * DIALOG_BUTTON_Y_FRACTION))

        # Accept button: center - 99 px
        acc_x, acc_y = dialog_button_point(rect, "accept")
        self.assertEqual(acc_x, 512 - 99)
        self.assertEqual(acc_y, ok_y)

        # Decline button: center + 99 px
        dec_x, dec_y = dialog_button_point(rect, "decline")
        self.assertEqual(dec_x, 512 + 99)
        self.assertEqual(dec_y, ok_y)

        # Continue / Skip button: bottom right
        cont_x, cont_y = dialog_button_point(rect, "continue")
        self.assertEqual(cont_x, round(512 + 768 * 0.487))
        self.assertEqual(cont_y, round(768 * 0.948))

    def test_dialog_button_point_invalid_rect(self):
        invalid_rect = Rect(0, 0, 0, 0)
        self.assertEqual(dialog_button_point(invalid_rect, "ok"), (0, 0))


class DialogMemoryClassificationTests(unittest.TestCase):
    def test_dialog_fields_default_in_memory_state(self):
        state = GameMemoryState()
        self.assertEqual(state.dialog_type, "")
        self.assertEqual(state.dialog_buttons, [])
        self.assertEqual(state.dialog_quest_name, "")
        self.assertEqual(state.dialog_quest_title, "")

    def test_overlay_snapshot_includes_dialog_fields(self):
        snap = OverlaySnapshot(
            dialog_type="missao_aceitar",
            dialog_buttons=["accept", "decline"],
            dialog_focus="accept",
        )
        self.assertEqual(snap.dialog_type, "missao_aceitar")
        self.assertEqual(snap.dialog_buttons, ["accept", "decline"])
        self.assertEqual(snap.dialog_focus, "accept")


class DialogEngineNavigationTests(unittest.TestCase):
    def setUp(self):
        from torchbridge.config import ConfigManager
        from torchbridge.models import SharedOverlayState
        from torchbridge.engine import BridgeEngine

        self.cfg_mock = MagicMock(spec=ConfigManager)
        self.cfg_mock.get.return_value = {
            "target": {"process_names": ["Torchlight.exe"], "window_titles": ["Torchlight"]},
            "movement": {"anchor_x": 0.5, "anchor_y": 0.5, "initial_mode": "direct"},
            "radial": {"slots": ["I", "P", "S", "C"]},
            "raw_controller": False,
            "overlay": {"enabled": True},
        }
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.cfg_mock, self.shared)
        self.engine.injector = MagicMock()
        self.hub = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def test_accept_decline_dpad_navigation(self):
        # Configure memory state with quest offer
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            state_id=6,
            dialog_type="missao_aceitar",
            dialog_buttons=["accept", "decline"],
        )

        # 1st tick: initialization focuses 'accept'
        state = ControllerState(connected=True)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_dialog_navigation(state, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "accept")

        # 2nd tick: press dpad_right -> moves to 'decline'
        state_right = ControllerState(connected=True, buttons=frozenset(["dpad_right"]))
        self.engine._previous = ControllerState(connected=True, buttons=frozenset())
        self.engine._handle_dialog_navigation(state_right, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "decline")

        # 3rd tick: press dpad_left -> moves back to 'accept'
        state_left = ControllerState(connected=True, buttons=frozenset(["dpad_left"]))
        self.engine._previous = ControllerState(connected=True, buttons=frozenset())
        self.engine._handle_dialog_navigation(state_left, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "accept")

    def test_b_button_decline(self):
        # Configure memory state with quest offer
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            state_id=6,
            dialog_type="missao_aceitar",
            dialog_buttons=["accept", "decline"],
        )

        state = ControllerState(connected=True)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_dialog_navigation(state, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "accept")

        # Press B -> directly focuses decline and clicks left mouse button
        state_b = ControllerState(connected=True, buttons=frozenset(["b"]))
        self.engine._previous = ControllerState(connected=True, buttons=frozenset())
        self.engine._handle_dialog_navigation(state_b, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "decline")
        self.engine.injector.mouse_button.assert_any_call("left", True)
        self.engine.injector.mouse_button.assert_any_call("left", False)

    def test_single_ok_dialog_navigation(self):
        # Configure memory state with in-progress or completed quest
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            state_id=6,
            dialog_type="missao_concluida",
            dialog_buttons=["ok"],
        )

        state = ControllerState(connected=True)
        self.engine._previous = ControllerState(connected=True)
        self.engine._handle_dialog_navigation(state, self.rect, self.hub)
        self.assertEqual(self.engine._dialog_focus, "ok")


if __name__ == "__main__":
    unittest.main()
