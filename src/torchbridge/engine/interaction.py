"""Explicit proximity interaction through the normal, focus-guarded mouse.

Move -> wait for the game's hover to acknowledge this entity -> click -> release.
No memory writes, remote function calls, sleeps, or automatic interactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import ControllerState, Rect
from ..world import WorldEntity


@dataclass(slots=True)
class InteractionClick:
    level: int
    player: int
    entity: int
    rect: Rect
    return_point: tuple[int, int]
    started: float
    probe_started: float
    point: tuple[int, int]
    probe: int = 0
    phase: str = "hover"


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
            and memory.world.fresh(now) and memory.world.roster_complete
            and memory.world.camera is not None
        )

    def _world_target(self, rect: Rect, cfg: dict[str, Any]) -> WorldEntity | None:
        world = self._memory_state.world
        if world.camera is None:
            return None
        for target in world.nearby(cfg["interaction"]["radius"]):
            lift = 0.8 if target.kind == "npc" else 0.3
            if world.camera.project(target.position, rect.width, rect.height, lift) is not None:
                return target
        return None

    def _cancel_world_interaction(self, restore: bool = False) -> None:
        click = self._world_click
        if click is not None:
            self._set_mouse("left", False)
            self._world_click = None
            if restore and click.rect.contains(*click.return_point):
                self.injector.move(*click.return_point)
        self.shared.update(interaction_target=None)

    def _handle_world_interaction(self, state: ControllerState, rect: Rect,
                                  cfg: dict[str, Any], now: float) -> bool:
        allowed = self._world_interaction_allowed(state, cfg, now)
        target = self._world_target(rect, cfg) if allowed else None
        self.shared.update(interaction_target=target, interaction_button=cfg["interaction"]["button"])
        click = self._world_click
        if click is not None:
            world = self._memory_state.world
            # Never switch to a nearer entity in the middle of a pending click.
            target = next((e for e in world.nearby(cfg["interaction"]["radius"])
                           if e.address == click.entity), None)
            if (not allowed or target is None or rect != click.rect or now < click.started
                    or now - click.started > 0.6
                    or (world.level_address, world.player_address) != (click.level, click.player)):
                self._cancel_world_interaction()
                return True
            self.shared.update(interaction_target=target)
            if click.phase == "click":
                if now - click.probe_started >= 0.07:
                    self._cancel_world_interaction(restore=True)
                return True
            lift = (0.8, 0.3, 1.5)[click.probe] if target.kind == "npc" else (0.3, 0.8, 1.5)[click.probe]
            point = world.camera.project(target.position, rect.width, rect.height, lift)
            if point is None:
                self._cancel_world_interaction()
                return True
            absolute = (rect.left + point[0], rect.top + point[1])
            if max(abs(absolute[i] - click.point[i]) for i in (0, 1)) > 3:
                # Camera/target moved: wait for a new hover sample at the new pixel.
                click.point = absolute
                click.probe_started = now
                if not self.injector.move(*absolute):
                    self._cancel_world_interaction()
                return True
            # A stale hover from before we placed the cursor must never authorize a click.
            if (now - click.probe_started >= 0.05
                    and world.sampled_at >= click.probe_started + 0.025
                    and self._memory_state.hover_entity == click.entity):
                self._set_mouse("left", True)
                if "left" in self._held_mouse:
                    click.phase = "click"
                    click.probe_started = now
                return True
            if now - click.probe_started >= 0.1:
                if click.probe >= 2:
                    self._cancel_world_interaction(restore=True)
                    self.shared.toast("Alvo encoberto ou indisponível", 1.8)
                else:
                    click.probe += 1
                    click.probe_started = now
                    lift = (0.8, 0.3, 1.5)[click.probe] if target.kind == "npc" else (0.3, 0.8, 1.5)[click.probe]
                    point = world.camera.project(target.position, rect.width, rect.height, lift)
                    if point is None:
                        self._cancel_world_interaction()
                    else:
                        click.point = (rect.left + point[0], rect.top + point[1])
                        if not self.injector.move(*click.point):
                            self._cancel_world_interaction()
            return True

        button = cfg["interaction"]["button"]
        if target is None or not state.pressed(button) or self._previous.pressed(button):
            return False
        world = self._memory_state.world
        lift = 0.8 if target.kind == "npc" else 0.3
        point = world.camera.project(target.position, rect.width, rect.height, lift)
        if point is None:
            return False
        # Stop click-to-move and attack holds before moving toward the selected object.
        self._set_mouse("left", False)
        self._set_mouse("right", False)
        if self._a_shift_held:
            self._set_key("SHIFT", False)
            self._ensure_modifier_released("SHIFT")
            self._a_shift_held = False
        if self._held_mouse or any(self.injector.key_pressed(key) for key in ("SHIFT", "CTRL", "ALT")):
            # A failed release or a physical modifier must not turn the target
            # placement into an unintended held/modified click.
            return True
        self._direct_move_active = False
        self._previous_left_pressed = False
        self._auto_move_resume_times.clear()
        absolute = (rect.left + point[0], rect.top + point[1])
        self._world_click = InteractionClick(world.level_address, world.player_address, target.address,
                                              rect, self.injector.cursor_position(), now, now, absolute)
        # A menu can open before the physical button is released. Keep that
        # press out of menu navigation until the next release/rearm.
        self._blocked_buttons.add(button)
        if not self.injector.move(*absolute):
            self._cancel_world_interaction()
        return True
