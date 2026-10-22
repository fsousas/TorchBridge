"""Cancelable input lease; releases remain possible after focus is lost."""
from __future__ import annotations

from typing import Any, Callable


class InputCancelled(Exception):
    """The target, controller, or enabled state changed during an action."""


class InputSession:
    def __init__(self, injector: Any, allowed: Callable[[], bool]) -> None:
        self.injector = injector
        self.allowed = allowed
        self.keys: set[str] = set()
        self.mouse: set[str] = set()

    def check(self) -> None:
        if not self.allowed():
            raise InputCancelled()

    def key(self, name: str, down: bool) -> bool:
        if down:
            self.check()
        sent = self.injector.key(name, down)
        if sent:
            if down:
                self.keys.add(name)
            else:
                self.keys.discard(name)
        return sent

    def mouse_button(self, button: str, down: bool) -> bool:
        if down:
            self.check()
        sent = self.injector.mouse_button(button, down)
        if sent:
            if down:
                self.mouse.add(button)
            else:
                self.mouse.discard(button)
        return sent

    def tap(self, name: str) -> bool:
        down = self.key(name, True)
        up = self.key(name, False)
        return down and up

    def text(self, text: str) -> bool:
        self.check()
        return self.injector.text(text)

    def move(self, x: int, y: int) -> bool:
        self.check()
        return self.injector.move(x, y)

    def cursor_position(self) -> tuple[int, int]:
        return self.injector.cursor_position()

    def key_pressed(self, name: str) -> bool:
        return self.injector.key_pressed(name)

    def release_all(self) -> None:
        # Retain unsuccessful releases so the next inactive tick retries them.
        for name in tuple(self.keys):
            self.key(name, False)
        for button in tuple(self.mouse):
            self.mouse_button(button, False)
