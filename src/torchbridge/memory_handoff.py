"""Receive the game's own read-only memory fd over a private Unix socket."""
from __future__ import annotations

import array
import atexit
import os
from pathlib import Path
import shutil
import socket
import struct
import tempfile
import threading

MAGIC = b"TBMEMFD1"
HOST = struct.Struct("<8sII108s")
HOST_FILE = ".torchbridge-input-host"
_broker = None
_lock = threading.Lock()


class MemoryHandoff:
    def __init__(self):
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        self.directory = Path(tempfile.mkdtemp(prefix="tb-memory-", dir=runtime or None))
        self.address = str(self.directory / "reader.sock")
        if len(os.fsencode(self.address)) >= 108:
            shutil.rmtree(self.directory)
            raise OSError("Caminho do socket de integração excede o limite do Linux")
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(self.address)
        self.listener.listen(4)
        self.listener.settimeout(.25)
        self.lock = threading.Lock()
        self.descriptors = {}
        self.files = {}
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._serve, name="Torchlight memory", daemon=True)
        self.thread.start()

    def publish(self, exe):
        payload = HOST.pack(MAGIC, 1, os.getpid(), os.fsencode(self.address))
        target = Path(exe).parent / HOST_FILE
        if target.is_symlink():
            raise ValueError("O registro da integração contém um link")
        if target.exists() and not target.read_bytes().startswith(MAGIC):
            raise FileExistsError("Outro arquivo ocupa o registro da integração com Torchlight")
        fd, name = tempfile.mkstemp(prefix=".torchbridge-host-", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        self.files[target] = payload

    def _receive(self, peer):
        import fcntl
        from .linux_process import process_start
        descriptors = []
        try:
            pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            peer.settimeout(.2)
            data, ancillary, flags, _ = peer.recvmsg(8, socket.CMSG_SPACE(4), socket.MSG_CMSG_CLOEXEC)
            for level, kind, value in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    integers = array.array("i")
                    integers.frombytes(value[:len(value) - len(value) % integers.itemsize])
                    descriptors.extend(integers)
            while len(data) < 8:
                chunk = peer.recv(8-len(data))
                if not chunk:
                    return
                data += chunk
            if (uid != os.getuid() or data != MAGIC or flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC)
                    or len(descriptors) != 1):
                return
            fd = descriptors[0]
            if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
                return
            proc = Path("/proc") / str(pid)
            if (proc / "comm").read_text().strip().casefold() != "torchlight.exe":
                return
            source, expected = os.fstat(fd), (proc / "mem").stat()
            if (source.st_dev, source.st_ino) != (expected.st_dev, expected.st_ino):
                return
            start = process_start(pid)
            with self.lock:
                old = self.descriptors.pop(pid, None)
                if old:
                    os.close(old[1])
                self.descriptors[pid] = (start, fd)
                descriptors.clear()
        finally:
            for fd in descriptors:
                os.close(fd)

    def _expire(self):
        from .linux_process import process_start
        with self.lock:
            for pid, (start, fd) in list(self.descriptors.items()):
                try:
                    live = process_start(pid) == start
                except OSError:
                    live = False
                if not live:
                    os.close(fd)
                    del self.descriptors[pid]

    def _serve(self):
        while not self.stopped.is_set():
            try:
                peer, _ = self.listener.accept()
                with peer:
                    self._receive(peer)
            except (OSError, ValueError):
                pass
            self._expire()

    def descriptor(self, pid, start):
        with self.lock:
            value = self.descriptors.get(pid)
            return os.dup(value[1]) if value and value[0] == start else None

    def close(self):
        if self.stopped.is_set():
            return
        self.stopped.set()
        self.listener.close()
        self.thread.join(timeout=1)
        with self.lock:
            for _, fd in self.descriptors.values():
                os.close(fd)
            self.descriptors.clear()
        for target, payload in list(self.files.items()):
            try:
                if not target.is_symlink() and target.read_bytes() == payload:
                    target.unlink()
            except OSError:
                pass
        shutil.rmtree(self.directory, ignore_errors=True)


def publish(exe):
    global _broker
    if os.name == "nt":
        return
    with _lock:
        if _broker is None:
            _broker = MemoryHandoff()
            atexit.register(_broker.close)
        _broker.publish(exe)


def descriptor(pid, start):
    return _broker.descriptor(pid, start) if _broker else None
