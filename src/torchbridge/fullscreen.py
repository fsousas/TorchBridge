"""Instalação reversível do módulo D3D9, sem substituir DLLs de outros mods."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


IDENTITY = b"TorchBridge.D3D9.Overlay.v1.x86"
MANIFEST = ".torchbridge-overlay.json"


def bundled_dll() -> Path:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(__file__).resolve().parents[2]
    return root / "assets" / "native" / "x86" / "d3d9.dll"


def validate_x86(data: bytes, *, dll: bool = False) -> None:
    """Confere PE32 antes de colocar um binário junto ao jogo de 32 bits."""
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("O arquivo não é um executável Windows válido")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset + 26 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("Cabeçalho PE inválido")
    if struct.unpack_from("<H", data, offset + 4)[0] != 0x14C:
        raise ValueError("O overlay requer Torchlight 1 e DLL de 32 bits (x86)")
    if struct.unpack_from("<H", data, offset + 24)[0] != 0x10B:
        raise ValueError("O overlay requer PE32")
    if dll and (not struct.unpack_from("<H", data, offset + 22)[0] & 0x2000 or IDENTITY not in data):
        raise ValueError("A DLL não é o módulo de fullscreen do TorchBridge")


def _game_directory(exe: Path) -> Path:
    exe = exe.resolve(strict=True)
    if exe.name.casefold() != "torchlight.exe" or not exe.is_file():
        raise ValueError("Selecione o Torchlight.exe do Torchlight 1")
    return exe.parent


def _proxy(directory: Path) -> Path | None:
    # Também evita colisões ao testar a instalação num filesystem case-sensitive.
    return next((p for p in directory.iterdir() if p.name.casefold() == "d3d9.dll"), None)


def install(exe: Path, source: Path | None = None) -> Path:
    directory = _game_directory(exe)
    validate_x86(exe.read_bytes())
    existing = _proxy(directory)
    if existing is not None:
        raise FileExistsError(
            f"Já existe {existing.name} nessa pasta. Nenhum arquivo foi substituído. "
            "ReShade, DXVK e outros proxies D3D9 precisam ser removidos separadamente."
        )
    manifest = directory / MANIFEST
    if manifest.exists() or manifest.is_symlink():
        raise FileExistsError(f"Já existe um registro de instalação: {manifest}")
    source = source or bundled_dll()
    if not source.is_file():
        raise FileNotFoundError("Módulo fullscreen ausente. Execute GERAR_OVERLAY_FULLSCREEN.bat "
                                "ou utilize uma distribuição que inclua assets/native/x86/d3d9.dll.")
    data = source.read_bytes()
    validate_x86(data, dll=True)
    record = {"owner": "TorchBridge", "version": 1, "sha256": hashlib.sha256(data).hexdigest()}
    target = directory / "d3d9.dll"
    wrote_dll = wrote_manifest = False
    try:
        with target.open("xb") as out:
            wrote_dll = True
            out.write(data)
        with manifest.open("x", encoding="utf-8") as out:
            wrote_manifest = True
            json.dump(record, out, indent=2)
    except Exception:
        if wrote_manifest:
            manifest.unlink(missing_ok=True)
        if wrote_dll:
            target.unlink(missing_ok=True)
        raise
    return target


def remove(exe: Path) -> None:
    directory = _game_directory(exe)
    target = _proxy(directory)
    manifest = directory / MANIFEST
    if target is None or not manifest.is_file():
        raise FileNotFoundError("Nenhuma instalação gerenciada do overlay foi encontrada")
    if target.is_symlink() or manifest.is_symlink():
        raise ValueError("A instalação contém links; nenhum arquivo foi removido")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    data = target.read_bytes()
    validate_x86(data, dll=True)
    if (not isinstance(record, dict) or record.get("owner") != "TorchBridge" or
            record.get("version") != 1 or record.get("sha256") != hashlib.sha256(data).hexdigest()):
        raise ValueError("A DLL foi alterada desde a instalação; nenhum arquivo foi removido")
    # Uma DLL em uso é protegida pelo Windows. Nesse caso o manifesto permanece.
    target.unlink()
    manifest.unlink()


def configure_dialog(*, uninstall: bool = False) -> int:
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv[:1])
    filename, _ = QFileDialog.getOpenFileName(
        None, "Feche o jogo e selecione Torchlight.exe", "", "Torchlight (Torchlight.exe)"
    )
    if not filename:
        return 0
    try:
        if uninstall:
            remove(Path(filename))
            message = "Suporte a fullscreen removido. O overlay em janela continua disponível."
        else:
            install(Path(filename))
            message = "Suporte a fullscreen instalado. Abra o TorchBridge e reinicie o Torchlight."
        QMessageBox.information(None, "TorchBridge", message)
        return 0
    except (OSError, ValueError) as error:
        QMessageBox.warning(None, "TorchBridge", str(error))
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Overlay fullscreen do Torchlight 1; feche o jogo antes.")
    parser.add_argument("action", choices=("install", "remove"))
    parser.add_argument("game", nargs="?", type=Path, help="Caminho completo do Torchlight.exe")
    args = parser.parse_args(argv)
    if args.game is None:
        return configure_dialog(uninstall=args.action == "remove")
    try:
        if args.action == "install":
            print(f"Instalado: {install(args.game)}. Reinicie o Torchlight.")
        else:
            remove(args.game)
            print("Suporte a fullscreen removido.")
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
