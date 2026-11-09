"""Executa testes unitários sem enviar entrada ao desktop, também no Linux.

As fronteiras de entrada são simuladas em ambos os sistemas. O Qt é sempre
offscreen, mesmo numa sessão Wayland. Isso não envia entrada ao desktop.
"""
import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        # O módulo real do motor permanece em uso; somente as fronteiras de
        # entrada/busca de janela são simuladas (inclusive ao testar no Windows).
        stack.enter_context(patch("torchbridge.engine.WindowLocator"))
        mock_injector = stack.enter_context(patch("torchbridge.engine.InputInjector"))
        mock_injector.return_value.key_pressed.return_value = False
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=args.pattern)
        result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
