"""Opt-in real Omarchy integration test using an isolated Xwayland input window.

Creates virtual devices, moves the pointer and types ONLY while our own fixture
is in focus. Restores the previous focus/cursor and closes all resources.
Does not open Torchlight, alter desktop settings, or touch real saves.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def fixture(result):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QLineEdit
    app = QApplication([])
    field = QLineEdit()
    field.setWindowTitle("TorchBridge Linux input smoke")
    field.resize(640, 240)
    field.show()
    field.setFocus()
    timer = QTimer()
    def finish():
        if Path(result + ".done").exists():
            Path(result).write_text(json.dumps({"text": field.text()}))
            app.quit()
    timer.timeout.connect(finish)
    timer.start(20)
    QTimer.singleShot(20000, app.quit)
    return app.exec()


def focus(address):
    result = subprocess.run(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{address}" }})'], capture_output=True)
    if result.returncode:
        subprocess.run(["hyprctl", "dispatch", "focuswindow", "address:" + address], check=True, capture_output=True)


def main():
    from torchbridge.linux import Hyprland, InputInjector, WindowLocator
    from torchbridge.models import Rect
    from torchbridge.wayland import Connection
    from PySide6.QtGui import QImage, QColor
    old_focus = Hyprland.request("activewindow").get("address")
    old_cursor = InputInjector.cursor_position()
    injector = InputInjector()
    overlay = None
    with tempfile.TemporaryDirectory(prefix="torchbridge-smoke-") as directory:
        result = Path(directory) / "result.json"
        child = subprocess.Popen([sys.executable, __file__, "--fixture", str(result)],
                                 env=dict(os.environ, QT_QPA_PLATFORM="xcb"))
        try:
            deadline = time.monotonic() + 10
            window = None
            while time.monotonic() < deadline and child.poll() is None:
                window = next((w for w in Hyprland.request("clients") if w["pid"] == child.pid), None)
                if window:
                    break
                time.sleep(.05)
            assert window, "Xwayland fixture failed to open"
            focus(window["address"])
            time.sleep(.1)
            hwnd = int(window["address"], 16)
            def guarded(action):
                assert WindowLocator.is_foreground(hwnd), "Fixture lost focus; input cancelled"
                assert WindowLocator.window_pid(hwnd) == child.pid, "Fixture PID changed"
                assert action(), "Native input rejected"
            rect = WindowLocator.client_rect(hwnd)
            guarded(lambda: injector.move(rect.left+rect.width//2, rect.top+rect.height//2))
            time.sleep(.05)
            cursor = injector.cursor_position()
            assert abs(cursor[0]-(rect.left+rect.width//2)) <= 1, (cursor, rect)
            assert abs(cursor[1]-(rect.top+rect.height//2)) <= 1, (cursor, rect)
            guarded(lambda: injector.key("SHIFT", True))
            assert injector.key_pressed("SHIFT"), "Modifier down not observable in Xwayland"
            injector.key("SHIFT", False)
            assert not injector.key_pressed("SHIFT"), "Modifier release not observable"
            guarded(lambda: injector.tap("B"))
            time.sleep(.1)
            guarded(lambda: injector.text("aA!zé"))
            time.sleep(.1)
            # A layer may receive pointer clicks but must never steal keyboard focus.
            overlay = Connection()
            from torchbridge.models import virtual_keyboard_asset_path
            overlay.set_cursor(QImage(str(virtual_keyboard_asset_path("pointer.cur"))))
            monitor = WindowLocator.monitor(hwnd)
            import math
            scale = math.ceil(monitor["scale"])
            image = QImage(rect.width*scale, rect.height*scale, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor(0, 0, 0, 0))
            overlay.present(image, monitor, rect, Rect(cursor[0]-20, cursor[1]-20, 40, 40))
            time.sleep(.1)
            guarded(lambda: injector.move(cursor[0]+1, cursor[1]+1))
            time.sleep(.05)
            guarded(lambda: injector.mouse_button("left", True))
            injector.mouse_button("left", False)
            time.sleep(.05)
            events = list(overlay.events())
            assert any(kind == "click" for kind, _, _ in events), events
            assert WindowLocator.is_foreground(hwnd), "Layer stole game focus"
            overlay.hide()
            time.sleep(.05)
            overlay.present(image, monitor, rect)
            print("Wayland: geometry, fractional scale, pointer, modifier release, keyboard click and hide/show OK")
            guarded(lambda: injector.key("ALT", True))
            injector.close()  # The native destructor must release a held modifier.
            time.sleep(.05)
            assert not injector.key_pressed("ALT"), "Native close left Alt held"
            result.with_suffix(".json.done").touch()
            child.wait(timeout=5)
            actual = json.loads(result.read_text())["text"]
            assert actual == "baA!zé", repr(actual)
            print("Exact text (case, punctuation, Unicode) OK")
        finally:
            if overlay:
                overlay.close()
            injector.key("SHIFT", False)
            injector.mouse_button("left", False)
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            injector.move(*old_cursor)
            injector.close()
            if old_focus:
                focus(old_focus)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        raise SystemExit(fixture(sys.argv[2]))
    raise SystemExit(main())
