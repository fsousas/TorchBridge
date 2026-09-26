"""Executa testes unitários sem enviar entrada ao desktop, também no Linux.

DLLs Win32 são simuladas no Linux só para importar o leitor de memória. Os
testes usam seus próprios estados/fakes; isso não testa o driver nem o D3D9.
"""
import argparse
from contextlib import ExitStack
import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        if os.name != "nt":
            stack.enter_context(patch.object(ctypes, "windll", MagicMock(), create=True))
        # O módulo real do motor permanece em uso; somente as fronteiras de
        # entrada/busca de janela são simuladas (inclusive ao testar no Windows).
        stack.enter_context(patch("torchbridge.engine.WindowLocator"))
        stack.enter_context(patch("torchbridge.engine.InputInjector"))
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=args.pattern)
        result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
