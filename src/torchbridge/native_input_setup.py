"""Managed, reversible installation of the independent x86 input module."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from .fullscreen import validate_x86
from .resources import resource_root

IDENTITY = b"TorchBridge.NativeInput.v2.x86"
MANIFEST = ".torchbridge-input.json"


def bundled_dll():
    return resource_root() / "assets/native/x86/winmm.dll"


def validate_module(data):
    validate_x86(data)
    pe = struct.unpack_from("<I", data, 60)[0]
    if not struct.unpack_from("<H", data, pe + 22)[0] & 0x2000 or IDENTITY not in data:
        raise ValueError("O arquivo não é o módulo de movimento do TorchBridge")


def directory(exe):
    exe = Path(exe).resolve(strict=True)
    if exe.name.casefold() != "torchlight.exe" or not exe.is_file():
        raise ValueError("Selecione Torchlight.exe")
    data = exe.read_bytes()
    validate_x86(data)
    pe = struct.unpack_from("<I", data, 60)[0]
    if struct.unpack_from("<I", data, pe + 8)[0] not in (0x4B5F7519, 0x4FFC6815):
        raise ValueError("Esta versão do Torchlight ainda não tem um layout de movimento validado")
    return exe.parent


def proxy(folder):
    return next((p for p in folder.iterdir() if p.name.casefold() == "winmm.dll"), None)


def installed_record(folder, target):
    manifest = folder / MANIFEST
    if target.is_symlink() or manifest.is_symlink():
        raise ValueError("A integração contém links; nenhum arquivo foi substituído")
    data = target.read_bytes()
    validate_module(data)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(record, dict) or record.get("owner") != "TorchBridge"
            or record.get("version") != 2
            or record.get("sha256") != hashlib.sha256(data).hexdigest()):
        raise ValueError("O módulo foi alterado desde a instalação; nenhum arquivo foi substituído")
    return record, data


def write_record(folder, record):
    import tempfile
    fd, filename = tempfile.mkstemp(prefix=".torchbridge-input-", suffix=".tmp", dir=folder)
    temporary = Path(filename)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(record, out, indent=2)
        temporary.replace(folder / MANIFEST)
    finally:
        temporary.unlink(missing_ok=True)


def install(exe, source=None):
    folder = directory(exe)
    target = proxy(folder)
    manifest = folder / MANIFEST
    if target is None and (manifest.exists() or manifest.is_symlink()):
        raise FileExistsError("Já existe um registro de instalação do movimento")
    source = Path(source) if source else bundled_dll()
    if not source.is_file():
        raise FileNotFoundError("Módulo de movimento ausente. Gere-o com scripts/build_native_input.py "
                                "ou use uma distribuição que inclua winmm.dll")
    data = source.read_bytes()
    validate_module(data)
    if target is not None:
        if not manifest.is_file():
            raise FileExistsError(f"Outro módulo usa {target.name}. Nenhum arquivo foi substituído")
        record, previous = installed_record(folder, target)
        if previous == data:
            return target
        # Update only an intact managed installation. A loaded DLL on Windows
        # cannot be replaced; report the need to close the game in that case.
        import tempfile
        fd, filename = tempfile.mkstemp(prefix=".torchbridge-input-", suffix=".dll", dir=folder)
        temporary = Path(filename)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
            try:
                temporary.replace(target)
            except PermissionError as error:
                raise PermissionError("Feche o Torchlight para atualizar os controles") from error
            record["sha256"] = hashlib.sha256(data).hexdigest()
            try:
                write_record(folder, record)
            except Exception:
                target.write_bytes(previous)
                raise
        finally:
            temporary.unlink(missing_ok=True)
        return target
    target = folder / "winmm.dll"
    wrote_binary = wrote_manifest = False
    try:
        with target.open("xb") as out:
            wrote_binary = True
            out.write(data)
        with manifest.open("x", encoding="utf-8") as out:
            wrote_manifest = True
            json.dump({"owner": "TorchBridge", "version": 2,
                       "sha256": hashlib.sha256(data).hexdigest()}, out, indent=2)
    except Exception:
        if wrote_manifest:
            manifest.unlink(missing_ok=True)
        if wrote_binary:
            target.unlink(missing_ok=True)
        raise
    return target


def remove(exe):
    folder = directory(exe)
    target, manifest = proxy(folder), folder / MANIFEST
    if target is None or not manifest.is_file():
        raise FileNotFoundError("Movimento seguro não está instalado nesta pasta")
    record, _ = installed_record(folder, target)
    from .game_setup import restore_wine_activation
    restore_wine_activation(exe, record)
    target.unlink()
    manifest.unlink()
    from .memory_handoff import HOST_FILE, MAGIC
    host = folder / HOST_FILE
    if host.is_file() and not host.is_symlink() and host.read_bytes().startswith(MAGIC):
        host.unlink()


def launch_environment(environment):
    """Keep existing Wine overrides, including DXVK/ReShade selections."""
    result = dict(environment)
    entries = []
    for entry in result.get("WINEDLLOVERRIDES", "").split(";"):
        names, separator, setting = entry.partition("=")
        remaining = [name.strip() for name in names.split(",") if name.strip().casefold() != "winmm"]
        if separator and any(remaining):
            entries.append(",".join(remaining) + "=" + setting)
    entries.append("winmm=n,b")
    result["WINEDLLOVERRIDES"] = ";".join(entries)
    return result


def configure_dialog(*, uninstall=False):
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv[:1])
    filename, _ = QFileDialog.getOpenFileName(
        None, "Selecione Torchlight.exe", "", "Torchlight (Torchlight.exe)")
    if not filename:
        return 0
    try:
        if uninstall:
            remove(filename)
            message = "Movimento seguro removido. Reinicie o jogo."
        else:
            from .game_setup import prepare
            prepare(exe=Path(filename))
            message = "Integração pronta. Se o Torchlight estiver aberto, reinicie o jogo."
        QMessageBox.information(None, "TorchBridge", message)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        QMessageBox.warning(None, "TorchBridge", str(error))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "remove"))
    parser.add_argument("game", nargs="?", type=Path)
    args = parser.parse_args(argv)
    if args.game is None:
        return configure_dialog(uninstall=args.action == "remove")
    try:
        if args.action == "install":
            from .game_setup import prepare
            prepare(exe=args.game)
            print("Integração pronta. Se o Torchlight estiver aberto, reinicie o jogo.")
        else:
            remove(args.game)
            print("Movimento seguro removido.")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
