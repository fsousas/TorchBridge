"""Install/remove a user launcher for a checkout or a portable Linux bundle."""
import argparse
import os
from pathlib import Path
import shutil


def desktop_quote(value):
    # Desktop Entry Exec escaping: percent is a field code even inside quotes.
    value = str(value).replace("%", "%%")
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--bundle", type=Path, help="Pasta dist/TorchBridge")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    desktop = data / "applications/io.github.torchbridge.TorchBridge.desktop"
    icon = data / "icons/hicolor/256x256/apps/torchbridge.png"
    if args.remove:
        desktop.unlink(missing_ok=True)
        icon.unlink(missing_ok=True)
        return
    executable = (args.bundle.resolve() / "TorchBridge" if args.bundle else root / "INICIAR_TORCHBRIDGE.sh")
    if not executable.is_file():
        raise SystemExit(f"Executável ausente: {executable}")
    source = (args.bundle.resolve() / "_internal" if args.bundle else root) / "assets/images/app/torchbridge-ativo-true-calibration-false.png"
    desktop.parent.mkdir(parents=True, exist_ok=True)
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, icon)
    desktop.write_text("[Desktop Entry]\nType=Application\nName=TorchBridge\n"
                       "Comment=Controle para Torchlight 1\n"
                       f"Exec={desktop_quote(executable)}\nIcon=torchbridge\n"
                       "Terminal=false\nCategories=Game;\nStartupNotify=false\n",
                       encoding="utf-8")
    print(f"Launcher: {desktop}")


if __name__ == "__main__":
    main()
