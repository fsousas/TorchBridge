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
            mock_windll = MagicMock()
            mock_windll.kernel32 = MagicMock()
            mock_windll.user32 = MagicMock()
            mock_windll.psapi = MagicMock()
            mock_windll.winmm = MagicMock()

            # Evita loops infinitos de enumeração quando funções retornam Mock (sempre truthy)
            mock_windll.kernel32.Process32First.return_value = False
            mock_windll.kernel32.Process32Next.return_value = False
            mock_windll.kernel32.Module32First.return_value = False
            mock_windll.kernel32.Module32Next.return_value = False
            mock_windll.kernel32.CreateToolhelp32Snapshot.return_value = 0
            mock_windll.kernel32.OpenProcess.return_value = 0
            mock_windll.kernel32.CloseHandle.return_value = 1
            mock_windll.user32.GetForegroundWindow.return_value = 0
            mock_windll.user32.EnumWindows.return_value = False

            stack.enter_context(patch.object(ctypes, "windll", mock_windll, create=True))
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
