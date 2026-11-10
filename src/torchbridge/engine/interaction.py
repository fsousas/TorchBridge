"""Explicit proximity interaction and native selection; no mouse click/warp."""
from __future__ import annotations

from typing import Any
from ..models import ControllerState, Rect
from ..world import WorldEntity


class WorldInteractionMixin:
    def _world_interaction_allowed(self, state: ControllerState, cfg: dict[str, Any], now: float) -> bool:
        memory = self._memory_state
        return bool(
            cfg["interaction"]["enabled"] and self._mode == "direct"
            and memory.is_connected and memory.is_in_game and not memory.is_loading
            and not memory.is_menu_open and not memory.open_menus and not memory.dialog_type
            and not any(self._active_panels) and not self._shortcut_config_active
            and not self._virtual_keyboard_open
            and self._pet_click_seq is None and self._hud_click_seq is None and self._modifier_seq is None
            and not any(state.pressed(b) for b in ("lb", "back", "start"))
            and state.lt < self.TRIGGER_ACTIVE_THRESHOLD
            and state.rt < self.TRIGGER_ACTIVE_THRESHOLD
            and not any(state.pressed(b) for b in ("a", "b", "x", "y", "rb", "r3"))
            and memory.world.fresh(now)
        )

    def _world_target(self, rect: Rect, cfg: dict[str, Any]) -> WorldEntity | None:
        # Pure proximity, including offscreen/occluded objects. Screen projection
        # must never cause the second-nearest object to receive the action.
        nearby = self._memory_state.world.nearby(cfg["interaction"]["radius"])
        return nearby[0] if nearby else None

    def _cancel_world_interaction(self, restore: bool = False) -> None:
        self._world_click = None
        self.shared.update(interaction_target=None)

    def _handle_world_interaction(self, state: ControllerState, rect: Rect,
                                  cfg: dict[str, Any], now: float) -> bool:
        allowed = self._world_interaction_allowed(state, cfg, now)
        self._native_interaction_allowed = allowed
        target = self._world_target(rect, cfg) if allowed else None
        native = self.native_input
        if native.ready and allowed:
            # The game selects from current positions on its own update thread.
            # Its acknowledgement drives the prompt and the native highlight.
            address = native.status.selected
            target = next((e for e in self._memory_state.world.nearby(cfg["interaction"]["radius"])
                           if e.address == address), None)
        self.shared.update(interaction_target=target, interaction_button=cfg["interaction"]["button"])
        button = cfg["interaction"]["button"]
        if not allowed or not state.pressed(button) or self._previous.pressed(button):
            return False
        self._blocked_buttons.add(button)
        if native.ready and native.status.flags & 16:
            # No pointer is trusted as an execution address. The module chooses
            # and validates the nearest live entity again when consuming this ID.
            native.interact()
        else:
            self.shared.toast(native.message, 2.5)
        return True
