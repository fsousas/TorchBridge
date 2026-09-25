"""Leitor de memória nativo e direto para o Torchlight 1 (x86 32-bit).
Mapeia a cadeia estática: CGame -> CGameClient -> CGameUI -> Menus
Permite que o motor e o overlay saibam com 100% de precisão o estado do jogo.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import struct
import time

log = logging.getLogger(__name__)

PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002

kernel32 = ctypes.windll.kernel32

# Endereços estáticos e offsets mapeados por engenharia reversa (.data sem ASLR)
ADDR_CGAME_GLOBAL = 0x00C1AD64
OFFSET_GAMECLIENT = 0x64
OFFSET_PLAYER     = 0x2C
OFFSET_LEVEL      = 0x38
OFFSET_GAMEUI     = 0x3C
OFFSET_MENU_MGR   = 0x0324
OFFSET_MAIN_STATE = 0x0D84
OFFSET_NEW_GAME_MENU = 0x0D78
OFFSET_CHAR_EDITBOX  = 0x70
OFFSET_CHAR_NAME_LEN = 0x88

MAIN_MENU_STATES: dict[int, str] = {
    0: "Tela Inicial",
    1: "Criar Personagem",
    2: "Selecionar Dificuldade",
    3: "Carregar Personagem",
    4: "Detalhes do Personagem",
    6: "Em Jogo",
}

# (offset_em_CGameUI, offset_do_byte_isOpen)
GAMEPLAY_MENUS: dict[str, tuple[int, int]] = {
    "Inventário":        (0x02CC, 0x30),
    "Atributos":         (0x02D0, 0x44),
    "Pet":               (0x02D4, 0x34),
    "Vendedor (Loja)":   (0x02D8, 0x30),
    "Encantador":        (0x02DC, 0x38),
    "Baú":               (0x02E4, 0x30),
    "Portal (Waypoint)": (0x02F4, 0x18),
    "Diálogo NPC":       (0x02F8, 0x18),
    "Diálogo Missão":    (0x02FC, 0x18),
    "Habilidades":       (0x030C, 0x1C),
    "Diário (Journal)":  (0x0310, 0x1C),
    "Missões (Quests)":  (0x0314, 0xC8),
    "Pesca":             (0x031C, 0x18),
    "Morte / Respawn":   (0x02F0, 0x18),
}


def get_save_character_count() -> int:
    """Retorna o número de personagens existentes na pasta de saves do Torchlight."""
    save_dir = Path(os.environ.get("APPDATA", "")) / "runic games" / "torchlight" / "save"
    if not save_dir.is_dir():
        return 0
    try:
        files = {f.name.lower() for f in save_dir.iterdir() if f.is_file() and f.suffix.lower() == ".svt"}
        return len(files)
    except Exception:
        return 0


def get_audio_settings() -> dict[str, float | bool]:
    """Lê os volumes normalizados (0.0 a 1.0) e flags de mudo em local_settings.txt."""
    settings_file = Path(os.environ.get("APPDATA", "")) / "runic games" / "torchlight" / "local_settings.txt"
    out: dict[str, float | bool] = {
        "sound_volume": 1.0,
        "music_volume": 1.0,
        "sound_mute": False,
        "music_mute": False,
    }
    if not settings_file.is_file():
        return out
    try:
        raw = settings_file.read_bytes()
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().upper()
            val = val.strip()
            if key == "SOUND VOLUME":
                out["sound_volume"] = float(val)
            elif key == "MUSIC VOLUME":
                out["music_volume"] = float(val)
            elif key == "SOUND MUTE":
                out["sound_mute"] = (val == "1")
            elif key == "MUSIC MUTE":
                out["music_mute"] = (val == "1")
    except Exception:
        pass
    return out


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


@dataclass(frozen=True)
class GameMemoryState:
    """Estado do jogo obtido diretamente da memória RAM e configurações locais."""
    is_connected: bool = False
    pid: int | None = None
    state_id: int = -1
    state_desc: str = "Aguardando jogo..."
    is_loading: bool = False
    is_in_game: bool = False
    is_menu_open: bool = False
    open_menus: list[str] = field(default_factory=list)
    recommended_mode: str = "direct"  # "direct", "cursor", "blocked"
    save_count: int = 0
    sound_volume: float = 1.0
    music_volume: float = 1.0
    char_name_len: int = 0


class TorchlightMemoryReader:
    """Gerencia a leitura segura da memória do processo Torchlight.exe."""

    def __init__(self) -> None:
        self.pid: int | None = None
        self._handle: int | None = None
        self._cached_save_count: int = 0
        self._cached_audio: dict[str, float | bool] = {
            "sound_volume": 1.0,
            "music_volume": 1.0,
            "sound_mute": False,
            "music_mute": False,
        }
        self._last_disk_check: float = 0.0

    def close(self) -> None:
        if self._handle:
            try:
                kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None
            self.pid = None

    def _find_pid(self) -> int | None:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return None
        try:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if kernel32.Process32First(snap, ctypes.byref(pe)):
                while True:
                    name = pe.szExeFile.decode("latin1", errors="ignore").lower()
                    if name == "torchlight.exe":
                        return pe.th32ProcessID
                    if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                        break
        finally:
            kernel32.CloseHandle(snap)
        return None

    def _ensure_handle(self) -> bool:
        current_pid = self._find_pid()
        if not current_pid:
            self.close()
            return False

        if current_pid != self.pid or not self._handle:
            self.close()
            h = kernel32.OpenProcess(PROCESS_VM_READ, False, current_pid)
            if h:
                self.pid = current_pid
                self._handle = h
                log.info(f"[MemoryReader] Conectado ao Torchlight (PID {current_pid})")
                return True
            return False
        return True

    def read_u32(self, address: int) -> int | None:
        if not self._handle or not address:
            return None
        buf = ctypes.create_string_buffer(4)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self._handle, ctypes.c_void_p(address), buf, 4, ctypes.byref(read)):
            if read.value == 4:
                return struct.unpack("<I", buf.raw)[0]
        return None

    def read_u8(self, address: int) -> int | None:
        if not self._handle or not address:
            return None
        buf = ctypes.create_string_buffer(1)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self._handle, ctypes.c_void_p(address), buf, 1, ctypes.byref(read)):
            if read.value == 1:
                return buf.raw[0]
        return None

    def update(self) -> GameMemoryState:
        """Executa um ciclo de leitura rápida (microssegundos) e retorna o estado atual."""
        # Atualiza contagem de saves e áudio em disco periodicamente (a cada 1.0s)
        now = time.monotonic()
        if now - self._last_disk_check >= 1.0:
            self._cached_save_count = get_save_character_count()
            self._cached_audio = get_audio_settings()
            self._last_disk_check = now

        sound_vol = float(self._cached_audio.get("sound_volume", 1.0))
        music_vol = float(self._cached_audio.get("music_volume", 1.0))

        if not self._ensure_handle():
            return GameMemoryState(
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        p_game = self.read_u32(ADDR_CGAME_GLOBAL)
        if not p_game:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_desc="Inicializando CGame...",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        p_client = self.read_u32(p_game + OFFSET_GAMECLIENT)
        if not p_client:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_desc="Inicializando CGameClient...",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        p_ui = self.read_u32(p_client + OFFSET_GAMEUI)
        if not p_ui:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_desc="Inicializando CGameUI...",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        # Overlays: Settings e Modal
        p_settings = self.read_u32(p_ui + 0x02EC)
        is_settings_open = (self.read_u8(p_settings + 0x18) == 1) if p_settings else False

        p_modal = self.read_u32(p_ui + 0x0304)
        is_modal_open = (self.read_u8(p_modal + 0x18) == 1) if p_modal else False

        # Loading screen
        p_loading = self.read_u32(p_ui + 0x0298)
        loading_parent = self.read_u32(p_loading + 0x80) if p_loading else None
        p_player = self.read_u32(p_client + OFFSET_PLAYER)

        p_menu_mgr = self.read_u32(p_ui + OFFSET_MENU_MGR)
        main_state_id = self.read_u32(p_menu_mgr + OFFSET_MAIN_STATE) if p_menu_mgr else 6
        state_desc = MAIN_MENU_STATES.get(main_state_id, f"Estado {main_state_id}")

        is_loading = bool((loading_parent is not None and loading_parent != 0) or (main_state_id == 6 and not p_player))

        # Overlays ativos
        if is_settings_open:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_id=main_state_id,
                state_desc="Configurações (Settings)",
                is_in_game=(main_state_id == 6),
                is_menu_open=True,
                open_menus=["Configurações"],
                recommended_mode="cursor",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        if is_modal_open:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_id=main_state_id,
                state_desc="Confirmação / Sair",
                is_in_game=(main_state_id == 6),
                is_menu_open=True,
                open_menus=["Confirmação Sair"],
                recommended_mode="cursor",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        # Tela de carregamento
        if is_loading:
            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_id=main_state_id,
                state_desc="Carregando...",
                is_loading=True,
                is_in_game=(main_state_id == 6),
                is_menu_open=False,
                recommended_mode="blocked",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
            )

        # Tela inicial (menus principais)
        if main_state_id != 6:
            char_name_len = 0
            if main_state_id == 1 and p_menu_mgr:
                p_new_game = self.read_u32(p_menu_mgr + OFFSET_NEW_GAME_MENU)
                if p_new_game:
                    p_editbox = self.read_u32(p_new_game + OFFSET_CHAR_EDITBOX)
                    if p_editbox:
                        val = self.read_u32(p_editbox + OFFSET_CHAR_NAME_LEN)
                        char_name_len = val if val is not None else 0

            return GameMemoryState(
                is_connected=True,
                pid=self.pid,
                state_id=main_state_id,
                state_desc=state_desc,
                is_in_game=False,
                is_menu_open=True,
                open_menus=[state_desc],
                recommended_mode="cursor",
                save_count=self._cached_save_count,
                sound_volume=sound_vol,
                music_volume=music_vol,
                char_name_len=char_name_len,
            )

        # Em gameplay: verificar todos os menus
        open_menus: list[str] = []
        for name, (ui_offset, open_offset) in GAMEPLAY_MENUS.items():
            p_menu = self.read_u32(p_ui + ui_offset)
            if p_menu and self.read_u8(p_menu + open_offset) == 1:
                open_menus.append(name)

        # Pause em jogo
        p_options = self.read_u32(p_ui + 0x02E8)
        if p_options and self.read_u8(p_options + 0x18) == 1:
            open_menus.append("Pause")

        is_menu_open = len(open_menus) > 0
        return GameMemoryState(
            is_connected=True,
            pid=self.pid,
            state_id=6,
            state_desc="Em Jogo",
            is_in_game=True,
            is_menu_open=is_menu_open,
            open_menus=open_menus,
            recommended_mode="cursor" if is_menu_open else "direct",
            save_count=self._cached_save_count,
            sound_volume=sound_vol,
            music_volume=music_vol,
        )
