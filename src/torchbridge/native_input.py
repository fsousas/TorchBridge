"""Bounded nonblocking local transport to the game-thread input module."""
from __future__ import annotations

from dataclasses import dataclass
import errno
import math
import socket
import struct
import time

MAGIC = b"TBINP002"
VERSION = 2
ENDPOINT = struct.Struct("<8sII16sIIII")
COMMAND = struct.Struct("<8sII16sIIIfffII")
REPLY = struct.Struct("<8sIIIIIIIIffIIII")
ACTIVE, DIRECT, WALKING, ALLOW_INTERACTION = 1, 2, 4, 8
READY, PROTECTED, HIGHLIGHTED, MOVING, COMPLETE = 1, 2, 4, 8, 16
REASONS = ("Parado", "Caminhando", "Aguardando controle", "Jogo sem foco",
           "Cenário mudou", "Menu aberto", "Habilidade em execução", "Nenhum alvo próximo",
           "Interagindo", "Versão não reconhecida", "Lista incompleta", "Canal indisponível")


@dataclass(frozen=True, slots=True)
class NativeInputStatus:
    flags: int = 0
    reason: int = 2
    selected: int = 0
    executed: int = 0
    action_result: int = 0
    count: int = 0
    destination_x: float = 0.
    destination_z: float = 0.
    lease_age: int = 0
    blocked_interactions: int = 0
    blocked_warps: int = 0
    frames: int = 0

    @property
    def description(self):
        return REASONS[self.reason] if 0 <= self.reason < len(REASONS) else "Aguardando jogo"


class NativeInputClient:
    def __init__(self):
        self.socket = None
        self.status = NativeInputStatus()
        self.message = "Aguardando conexão com Torchlight"
        self._preparation = None
        self._context = None
        self._endpoint_address = None
        self._token = bytes(16)
        self._sequence = 0
        self._action = 0
        self._action_at = 0.
        self._frame_at = 0.
        self._retry_at = 0.
        self._out = b""
        self._in = bytearray()
        self._connected_at = self._reply_at = 0.
        self._connecting = False
        self._last_send = 0.

    @property
    def ready(self):
        return bool(self.socket is not None and self.status.flags & READY
                    and 0 <= time.monotonic() - self._reply_at <= .2
                    and self.status.frames and 0 <= time.monotonic() - self._frame_at <= .2)

    def close(self):
        if self.socket is not None:
            self.socket.close()
        self.socket = None
        self.status = NativeInputStatus()
        self._out = b""
        self._in.clear()
        self._connecting = False
        self._reply_at = 0.
        self._frame_at = 0.

    def interact(self):
        self._action = (self._action + 1) & 0xFFFFFFFF or 1
        self._action_at = time.monotonic()

    def connect(self, memory, now):
        context = (memory.pid, getattr(memory, "_module_base", 0),
                   getattr(getattr(memory, "_linux", None), "start", None))
        if context != self._context:
            self.close()
            self._context = context
            self._endpoint_address = None
            self._retry_at = 0.
            self._action = 0
            self._preparation = None
        if self.socket is not None or now < self._retry_at or not memory.pid:
            return
        self._retry_at = now + .5
        try:
            address = self._endpoint_address or memory.find_export("winmm.dll", "TorchBridgeInputEndpoint")
            if address is None:
                exe = getattr(memory, "_exe_path", "")
                if exe:
                    from .game_setup import prepare_async
                    if self._preparation is None:
                        self._preparation = prepare_async(exe=exe)
                    if not self._preparation.done():
                        self.message = "Preparando os controles do Torchlight"
                    else:
                        try:
                            self._preparation.result()
                        except Exception as error:
                            self.message = str(error)
                        else:
                            self.message = "Reinicie o Torchlight para ativar os controles"
                else:
                    self.message = "Aguardando conexão com Torchlight"
                return
            raw = memory.read_bytes(address, ENDPOINT.size)
            if len(raw) != ENDPOINT.size:
                return
            magic, version, port, token, pid, image_base, capabilities, error = ENDPOINT.unpack(raw)
            if magic != MAGIC:
                self.message = "Aguardando inicialização do Torchlight"
                return
            if version != VERSION or image_base != context[1]:
                self.message = "Módulo de controles incompatível; repare a integração e reinicie o jogo"
                return
            self._endpoint_address = address
            if error:
                self.message = REASONS[error] if error < len(REASONS) else "Módulo indisponível"
                return
            if not 0 < port <= 65535 or not capabilities & READY:
                return
            # Windows PID is intentionally not compared with a Unix PID. The
            # endpoint/token above were read from the selected process itself.
            channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            channel.setblocking(False)
            channel.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            result = channel.connect_ex(("127.0.0.1", port))
            if result not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY,
                              10035, 10036, 10037):
                channel.close()
                return
            self.socket = channel
            self._token = token
            self._connecting = result != 0
            self._connected_at = now
            self.message = "Conectando ao movimento seguro"
        except (OSError, ValueError, struct.error):
            self.close()

    def send(self, *, flags, player, level, dx=0., dz=0., radius=4.5, now=None):
        now = time.monotonic() if now is None else now
        if self.socket is None:
            return
        try:
            if self._connecting:
                import select
                _, writable, errors = select.select([], [self.socket], [self.socket], 0)
                if errors or now - self._connected_at > .2:
                    raise OSError("Connection timed out")
                if not writable:
                    return
                error = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if error:
                    raise OSError(error, "Connection failed")
                self._connecting = False
            while True:
                try:
                    data = self.socket.recv(4096)
                except BlockingIOError:
                    break
                if not data:
                    raise OSError("Input module closed")
                self._in.extend(data)
                if len(self._in) > REPLY.size * 64:
                    raise ValueError("Reply buffer limit")
                while len(self._in) >= REPLY.size:
                    values = REPLY.unpack(self._in[:REPLY.size])
                    del self._in[:REPLY.size]
                    if values[:2] != (MAGIC, VERSION):
                        raise ValueError("Input protocol mismatch")
                    previous_frame = self.status.frames
                    self.status = NativeInputStatus(*values[3:])
                    if self.status.frames != previous_frame:
                        self._frame_at = now
                    self._reply_at = now
                    self.message = self.status.description
            if now - (self._reply_at or self._connected_at) > .2:
                raise OSError("Input module stalled")
            if not self._out and now - self._last_send >= 1 / 120:
                if (not all(math.isfinite(v) for v in (dx, dz, radius))
                        or math.hypot(dx, dz) > 1.001 or not .5 <= radius <= 8):
                    raise ValueError("Invalid movement")
                self._sequence = (self._sequence + 1) & 0xFFFFFFFF
                self._out = COMMAND.pack(MAGIC, VERSION, self._sequence, self._token, flags,
                                         player, level, dx, dz, radius, self._action,
                                         min(0xFFFFFFFF, int(max(0., now-self._action_at)*1000)))
                self._last_send = now
            if self._out:
                try:
                    sent = self.socket.send(self._out)
                except BlockingIOError:
                    sent = 0
                self._out = self._out[sent:]
        except (OSError, ValueError, struct.error):
            self.close()
            self._retry_at = now + .5
            self.message = "Movimento seguro desconectado"
