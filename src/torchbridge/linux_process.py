"""Read-only access to the PE32 process running under Wine/Proton.

No ptrace attach, writes, signals, capabilities or global sysctl changes. Keeping
an O_RDONLY /proc/PID/mem fd pins the address space; starttime rejects PID reuse.
The game module can hand over its own O_RDONLY fd without changing Yama. The
launcher ancestry remains an alternative for older/nonstandard installations.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct


def process_start(pid, proc=Path("/proc")):
    # comm may contain spaces and ')' characters; fields after the final ')' start at 3.
    fields = (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    return fields[19]  # field 22: starttime


def mapped_files(text):
    """Yield mapping starts, offsets, paths (including spaces) without assuming ASLR."""
    for line in text.splitlines():
        fields = line.split(None, 5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        start, end = (int(s, 16) for s in fields[0].split("-"))
        yield start, end, int(fields[2], 16), fields[5].removesuffix(" (deleted)")


def process_environment(pid, proc=Path("/proc")):
    raw = (proc / str(pid) / "environ").read_bytes()
    # Only keep the two paths we need; do not expose the process environment.
    wanted = {b"WINEPREFIX", b"STEAM_COMPAT_DATA_PATH"}
    return {key.decode(): os.fsdecode(value) for entry in raw.split(b"\0")
            for key, sep, value in [entry.partition(b"=")] if sep and key in wanted}


def game_data_directory(pid=None, proc=Path("/proc")):
    if override := os.environ.get("TORCHBRIDGE_GAME_DATA"):
        return Path(override).expanduser()
    environment = process_environment(pid, proc) if pid else os.environ
    prefix = environment.get("WINEPREFIX")
    if not prefix and environment.get("STEAM_COMPAT_DATA_PATH"):
        prefix = str(Path(environment["STEAM_COMPAT_DATA_PATH"]) / "pfx")
    if not prefix:
        # Offline convenience for the default Steam library; live reads always use
        # the selected process, never a second installation's saves or settings.
        if pid:
            return None
        prefix = str(Path.home() / ".local/share/Steam/steamapps/compatdata/41500/pfx")
    users = Path(prefix) / "drive_c/users"
    if not users.is_dir():
        return None
    candidates = sorted(users.iterdir(), key=lambda p: p.name != "steamuser")
    for user in candidates:
        for appdata in (user / "AppData/Roaming", user / "Application Data"):
            # Wine prefixes can preserve Windows capitalization on Linux.
            current = appdata
            for name in ("runic games", "torchlight"):
                if not current.is_dir():
                    break
                current = next((p for p in current.iterdir() if p.name.casefold() == name), current / name)
            if current.is_dir() and current != appdata:
                return current
    return None


class LinuxProcess:
    def __init__(self, proc=Path("/proc")):
        self.proc = proc
        self.pid = None
        self.fd = None
        self.start = None
        self.error = ""
        self.data_directory = None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
        self.pid = self.fd = self.start = None
        self.data_directory = None

    def find_pid(self):
        # Used by standalone diagnostics; the engine always passes the window PID.
        for path in self.proc.iterdir():
            if path.name.isdecimal():
                try:
                    if (path / "comm").read_text(errors="replace").strip().casefold() == "torchlight.exe":
                        return int(path.name)
                except OSError:
                    continue
        return None

    def attach(self, pid=None):
        pid = pid if pid is not None else self.pid or self.find_pid()
        if not pid or pid <= 0:
            self.close()
            self.error = ""
            return False
        try:
            start = process_start(pid, self.proc)
            if pid == self.pid and self.fd is not None and start == self.start:
                return True
            self.close()
            if (self.proc / str(pid) / "comm").read_text(errors="replace").strip().casefold() != "torchlight.exe":
                return False
            try:
                self.fd = os.open(self.proc / str(pid) / "mem", os.O_RDONLY | os.O_CLOEXEC)
            except PermissionError:
                from .memory_handoff import descriptor
                self.fd = descriptor(pid, start)
                if self.fd is None:
                    raise
            self.pid, self.start = pid, start
            self.data_directory = game_data_directory(pid, self.proc)
            self.error = ""
            return True
        except PermissionError:
            self.close()
            self.error = "Aguardando integração com Torchlight; reinicie o jogo se já estava aberto"
        except OSError:
            self.close()
            self.error = ""
        return False

    def read(self, address, size):
        if self.fd is None or not address or not 0 < size <= 1024 * 1024:
            return b""
        try:
            return os.pread(self.fd, size, address)
        except (OSError, OverflowError):
            return b""

    def module_info(self, name="Torchlight.exe"):
        if self.pid is None:
            return 0, 0, ""
        try:
            entries = list(mapped_files((self.proc / str(self.pid) / "maps").read_text()))
        except OSError:
            return 0, 0, ""
        candidates = [(start, path) for start, _, offset, path in entries
                      if Path(path).name.casefold() == name.casefold() and offset == 0]
        for start, path in sorted(candidates):
            header = self.read(start, 64)
            if len(header) != 64 or header[:2] != b"MZ":
                continue
            pe = self.read(start + struct.unpack_from("<I", header, 60)[0], 84)
            if (len(pe) == 84 and pe[:4] == b"PE\0\0" and
                    struct.unpack_from("<H", pe, 4)[0] == 0x14c and
                    struct.unpack_from("<H", pe, 24)[0] == 0x10b):
                return start, struct.unpack_from("<I", pe, 80)[0], path
        return 0, 0, ""
