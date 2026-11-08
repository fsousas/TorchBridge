"""Small cross-platform helpers for the reverse-engineering tools in scripts/."""
import os
from pathlib import Path
import sys


def beep(frequency, duration):
    if os.name == "nt":
        import winsound
        winsound.Beep(frequency, duration)
    else:
        # Use the terminal's configured bell; no audio daemon or privileged device.
        sys.stdout.write("\a")
        sys.stdout.flush()


def default_exe_path():
    if os.name == "nt":
        return Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
    return Path.home() / ".local/share/Steam/steamapps/common/Torchlight/Torchlight.exe"


def exe_argument():
    import argparse
    parser = argparse.ArgumentParser(description="Inspeção offline do executável PE32 do Torchlight 1")
    parser.add_argument("exe", nargs="?", type=Path, default=default_exe_path())
    return parser.parse_args().exe
