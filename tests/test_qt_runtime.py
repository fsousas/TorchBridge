"""Exercise Qt's C/Python boundary and interpreter shutdown in a child process."""
import os
import subprocess
import sys
import textwrap
import unittest


class QtRuntimeTests(unittest.TestCase):
    def test_offscreen_uses_real_proportional_font_metrics(self):
        code = textwrap.dedent("""
            from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
            from PySide6.QtWidgets import QApplication
            app = QApplication([])
            assert QFontDatabase.families(), "Offscreen font database is empty"
            font = QFont("Segoe UI")
            font.setPixelSize(13)
            metrics = QFontMetrics(font)
            assert metrics.horizontalAdvance("WWW") > metrics.horizontalAdvance("iii"), (
                "Offscreen is measuring placeholder glyphs", font.toString())
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_signal_emissions_and_normal_shutdown(self):
        # PYSIDE-3474: PySide6 6.12.0 over-releases singleton references on
        # Python <= 3.11. Assertions inside the suite can pass even though
        # finalizing the interpreter later aborts (the original CI failure).
        code = textwrap.dedent("""
            from PySide6.QtCore import QObject, Signal, Slot
            from PySide6.QtWidgets import QApplication, QWidget

            class Receiver(QObject):
                object_signal = Signal(object)
                bool_signal = Signal(bool)

                def __init__(self):
                    super().__init__()
                    self.calls = 0

                @Slot(object)
                def receive_object(self, value):
                    assert value is None
                    self.calls += 1

                @Slot(bool)
                def receive_bool(self, value):
                    assert value is True
                    self.calls += 1

            app = QApplication([])
            widget = QWidget()
            receiver = Receiver()
            receiver.object_signal.connect(receiver.receive_object)
            receiver.bool_signal.connect(receiver.receive_bool)
            for _ in range(2000):
                receiver.object_signal.emit(None)
                receiver.bool_signal.emit(True)
            assert receiver.calls == 4000
            widget.close()
            app.processEvents()
        """)
        result = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-c", code],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
