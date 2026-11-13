"""Prepare the controller integration without a separate user installation."""
from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

from .native_input_setup import MANIFEST, install, installed_record, proxy, write_record

log = logging.getLogger(__name__)
_lock = threading.RLock()
_key = r"HKCU\Software\Wine\AppDefaults\Torchlight.exe\DllOverrides"
_section = r"Software\\Wine\\AppDefaults\\Torchlight.exe\\DllOverrides"


@dataclass(frozen=True)
class Installation:
    exe: Path
    prefix: Path | None = None
    proton: Path | None = None
    steam: Path | None = None


def _values(text, key):
    tokens = re.findall(r'//[^\n]*|"(?:\\.|[^"\\])*"|[{}]', text)
    tokens = [token for token in tokens if not token.startswith("//")]
    for i, token in enumerate(tokens[:-1]):
        if token.casefold() == f'"{key}"'.casefold() and tokens[i+1].startswith('"'):
            yield re.sub(r'\\(["\\])', r'\1', tokens[i+1][1:-1])


def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _windows_locations():
    if os.name != "nt":
        return [], []
    import winreg
    steam, games = [], []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for key, value in ((r"Software\Valve\Steam", "SteamPath"),
                               (r"Software\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as opened:
                        steam.append(Path(winreg.QueryValueEx(opened, value)[0]))
                except OSError:
                    pass
            try:
                with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                                    0, winreg.KEY_READ | view) as parent:
                    for i in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, i)) as entry:
                                if winreg.QueryValueEx(entry, "DisplayName")[0].casefold() == "torchlight":
                                    games.append(Path(winreg.QueryValueEx(entry, "InstallLocation")[0]))
                        except OSError:
                            pass
            except OSError:
                pass
    return steam, games


def _proton(prefix):
    for line in _read(prefix.parent / "config_info").splitlines():
        if "/files/" in line:
            candidate = Path(line.split("/files/", 1)[0]) / "proton"
            if candidate.is_file():
                return candidate
    return None


def discover(launch=(), *, environment=None, home=None):
    env = os.environ if environment is None else environment
    home = Path.home() if home is None else Path(home)
    roots, standalone = _windows_locations()
    if os.name != "nt":
        roots.extend((home / ".local/share/Steam", home / ".steam/steam", home / ".steam/root"))
    if env.get("STEAM_COMPAT_CLIENT_INSTALL_PATH"):
        roots.insert(0, Path(env["STEAM_COMPAT_CLIENT_INSTALL_PATH"]))
    prefix = (Path(env["WINEPREFIX"]) if env.get("WINEPREFIX") else
              Path(env["STEAM_COMPAT_DATA_PATH"]) / "pfx"
              if env.get("STEAM_COMPAT_DATA_PATH") else None)
    explicit = [Path(arg) for arg in (launch or ()) if Path(arg).name.casefold() == "torchlight.exe"]
    if env.get("STEAM_COMPAT_INSTALL_PATH"):
        explicit.insert(0, Path(env["STEAM_COMPAT_INSTALL_PATH"]) / "Torchlight.exe")
    found = []
    for root in dict.fromkeys(p.resolve() for p in roots if p.is_dir()):
        libraries = [root]
        libraries.extend(Path(path) for path in _values(_read(root / "steamapps/libraryfolders.vdf"), "path"))
        for library in dict.fromkeys(libraries):
            manifest = _read(library / "steamapps/appmanifest_41500.acf")
            directory = next(_values(manifest, "installdir"), None)
            if not directory:
                continue
            exe = library / "steamapps/common" / directory / "Torchlight.exe"
            compat = next((p for p in (library / "steamapps/compatdata/41500/pfx",
                                      root / "steamapps/compatdata/41500/pfx") if p.is_dir()), None)
            found.append(Installation(exe, compat, _proton(compat) if compat else None, root))
    found.extend(Installation(path / "Torchlight.exe") for path in standalone)
    # The launch command/environment identifies a specific installation. Do not
    # change a second copy of the game while launching the selected one.
    if explicit:
        selected = []
        for exe in explicit:
            match = next((game for game in found if game.exe.resolve() == exe.resolve()), None)
            selected.append(match or Installation(exe, prefix, _proton(prefix) if prefix else None))
        found = selected
    result = {}
    for game in found:
        if game.exe.is_file():
            result.setdefault(game.exe.resolve(), game)
    return list(result.values())


def for_exe(exe, *, environment=None):
    exe = Path(exe).resolve()
    env = os.environ if environment is None else environment
    games = discover(environment=env)
    match = next((game for game in games if game.exe.resolve() == exe), None)
    if match:
        return match
    prefix = (Path(env["WINEPREFIX"]) if env.get("WINEPREFIX") else
              Path(env["STEAM_COMPAT_DATA_PATH"]) / "pfx"
              if env.get("STEAM_COMPAT_DATA_PATH") else None)
    return Installation(exe, prefix, _proton(prefix) if prefix else None)


def _registry_value(prefix):
    text = _read(prefix / "user.reg")
    for block in re.split(r"(?m)(?=^\[)", text):
        header = block.splitlines()[0] if block else ""
        if header.casefold().startswith(f"[{_section}]".casefold()):
            match = re.search(r'(?mi)^"winmm"="([^"]*)"\s*$', block)
            return match.group(1) if match else None
    return None


def _reg(game, arguments, *, missing_ok=False):
    env = dict(os.environ, WINEPREFIX=str(game.prefix), WINEDEBUG="-all")
    if game.proton:
        env.update(STEAM_COMPAT_DATA_PATH=str(game.prefix.parent),
                   STEAM_COMPAT_CLIENT_INSTALL_PATH=str(game.steam or game.proton.parent.parent),
                   SteamAppId="41500", SteamGameId="41500")
        command = [str(game.proton), "run", "reg.exe"]
    elif wine := shutil.which("wine"):
        command = [wine, "reg.exe"]
    else:
        raise RuntimeError("Não foi possível localizar o Wine/Proton usado pelo Torchlight")
    try:
        result = subprocess.run(command + arguments, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors="replace", timeout=30)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("O Proton demorou para preparar o Torchlight. Tente novamente.") from error
    if result.returncode == 1 and missing_ok:
        return None
    if result.returncode:
        log.error("Falha na configuração Wine do Torchlight: %s", result.stdout[-2000:])
        raise RuntimeError("Não foi possível ativar os controles no Proton; consulte torchbridge.log")
    return result.stdout


def _query(game):
    # Wine's console output is not reliably forwarded through Proton's pipes.
    # Export this one application key instead of parsing localized CLI output.
    with tempfile.TemporaryDirectory(prefix="torchbridge-wine-reg-") as directory:
        exported = Path(directory) / "activation.reg"
        windows_path = "Z:" + str(exported).replace("/", "\\")
        output = _reg(game, ["export", _key, windows_path, "/y"], missing_ok=True)
        if output is None:
            return None
        if not exported.is_file():
            raise RuntimeError("O Proton não confirmou a configuração dos controles")
        raw = exported.read_bytes()
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        match = re.search(r'(?mi)^"winmm"="([^"\r\n]*)"\s*$', text)
        return match.group(1) if match else None


def activate_wine(game):
    if os.name == "nt" or not game.prefix or not (game.prefix / "user.reg").is_file():
        return
    previous = _registry_value(game.prefix)
    if previous and previous.replace(" ", "").casefold() == "native,builtin":
        return
    # Query the running registry server as well: user.reg may not yet have
    # flushed another program's most recent setting to disk.
    previous = _query(game)
    if previous and previous.replace(" ", "").casefold() == "native,builtin":
        return
    folder = game.exe.parent
    record, _ = installed_record(folder, proxy(folder))
    # Keep the previous setting so removal can restore it. Record intent before
    # changing Wine, so an interrupted preparation remains repairable.
    if record.get("wine", {}).get("prefix") != str(game.prefix.resolve()):
        record["wine"] = {"prefix": str(game.prefix.resolve()), "previous": previous}
        write_record(folder, record)
    _reg(game, ["add", _key, "/v", "winmm", "/t", "REG_SZ", "/d", "native,builtin", "/f"])


def restore_wine_activation(exe, record):
    owned = record.get("wine")
    if os.name == "nt" or not isinstance(owned, dict):
        return
    prefix = Path(owned["prefix"])
    if not prefix.is_dir():
        return
    game = for_exe(exe)
    game = Installation(game.exe, prefix, _proton(prefix), game.steam)
    if _query(game) != "native,builtin":
        return
    if owned.get("previous") is None:
        _reg(game, ["delete", _key, "/v", "winmm", "/f"])
    else:
        _reg(game, ["add", _key, "/v", "winmm", "/t", "REG_SZ", "/d", owned["previous"], "/f"])


def prepare(launch=(), *, exe=None, environment=None):
    games = [for_exe(exe, environment=environment)] if exe is not None else discover(launch, environment=environment)
    prepared = []
    with _lock:
        for game in games:
            install(game.exe)
            activate_wine(game)
            from .memory_handoff import publish
            publish(game.exe)
            log.info("Integração pronta: %s", game.exe)
            prepared.append(game.exe)
    return prepared


def prepare_async(launch=(), *, exe=None, environment=None):
    future = Future()

    def work():
        try:
            future.set_result(prepare(launch, exe=exe, environment=environment))
        except Exception as error:
            log.exception("Não foi possível preparar a integração com Torchlight")
            future.set_exception(error)

    threading.Thread(target=work, name="Torchlight preparation", daemon=True).start()
    return future
