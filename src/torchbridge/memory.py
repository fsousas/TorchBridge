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
import re
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
    4: "Selecionar Dificuldade",
    6: "Em Jogo",
}

# (offset_em_CGameUI, offset_do_byte_isOpen)
GAMEPLAY_MENUS: dict[str, tuple[int, int]] = {
    "Inventário":        (0x02CC, 0x30),
    "Atributos":         (0x02D0, 0x44),
    "Pet":               (0x02D4, 0x34),
    "Vendedor (Loja)":   (0x02D8, 0x30),
    "Encantador":        (0x02DC, 0x38),
    "Transmutador":      (0x02E0, 0x54),
    "Baú":               (0x02E4, 0x30),
    "Pause":             (0x02E8, 0x18),
    "Portal (Waypoint)": (0x02F4, 0x18),
    "Habilidades":       (0x030C, 0x1C),
    "Diário (Journal)":  (0x0310, 0x1C),
    "Missões (Quests)":  (0x0314, 0xC8),
    "Pesca":             (0x031C, 0x18),
    "Morte / Respawn":   (0x02F0, 0x18),
}


def strip_torchlight_formatting(text: str) -> str:
    """Remove tags de formatação de cores e sublinhado nativas do Torchlight (ex: |cFFFFBA00 e |u)."""
    if not text:
        return ""
    clean = re.sub(r"\|c[0-9A-Fa-f]{8}", "", text)
    clean = clean.replace("|u", "").replace("|U", "")
    return clean.strip()


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
    dialog_type: str = ""  # "historia", "simples", "missao_aceitar", "missao_andamento", "missao_concluida", "missao_principal"
    dialog_buttons: list[str] = field(default_factory=list)  # ["ok"], ["accept", "decline"], ["accept"], ["continue"]
    dialog_quest_name: str = ""
    dialog_quest_title: str = ""


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

    def read_wstring(self, address: int, max_chars: int = 64) -> str:
        """Lê uma string UTF-16LE da memória do jogo até o caractere nulo."""
        if not self._handle or not address:
            return ""
        buf = ctypes.create_string_buffer(max_chars * 2)
        read = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self._handle, ctypes.c_void_p(address), buf, max_chars * 2, ctypes.byref(read)):
            try:
                raw = buf.raw[:read.value]
                return raw.decode("utf-16le", errors="ignore").split("\x00")[0]
            except Exception:
                pass
        return ""

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
            if not p_menu:
                continue
            if self.read_u8(p_menu + open_offset) == 1:
                if name == "Encantador":
                    # Distingue Sockets (Gron / Furl) de Encantador (Goren) pelo modo em +0x90
                    # Modos 0x19 (25), 0x1A (26), 0x1B (27) correspondem a Sockets
                    mode = self.read_u32(p_menu + 0x90)
                    if mode in (0x19, 0x1A, 0x1B):
                        open_menus.append("Sockets")
                    else:
                        open_menus.append("Encantador")
                else:
                    open_menus.append(name)

        # Diálogos de NPCs, Missões e Telas de História
        dialog_type = ""
        dialog_buttons: list[str] = []
        dialog_quest_name = ""
        dialog_quest_title = ""

        # 1. Tela de História / Cinemática (CCinematicMenu em +0x0300)
        p_cine = self.read_u32(p_ui + 0x0300)
        if p_cine and self.read_u8(p_cine + 0x18) == 1:
            dialog_type = "historia"
            dialog_buttons = ["continue"]
            open_menus.append("Tela de História")

        # 2. Diálogos de Missões e NPCs (CQuestDialogMenu em +0x02FC ou CDialogMenu em +0x02F8)
        p_qdialog = self.read_u32(p_ui + 0x02FC)
        p_dialog = self.read_u32(p_ui + 0x02F8)
        p_active_dlg = None
        if p_qdialog and self.read_u8(p_qdialog + 0x18) == 1:
            p_active_dlg = p_qdialog
        elif p_dialog and self.read_u8(p_dialog + 0x18) == 1:
            p_active_dlg = p_dialog

        if p_active_dlg:
            btn_ok = self.read_u32(p_active_dlg + 0x6C)
            btn_accept = self.read_u32(p_active_dlg + 0x70)
            btn_decline = self.read_u32(p_active_dlg + 0x74)

            ok_vis = (self.read_u8(btn_ok + 0x1A0) == 1) if btn_ok else False
            acc_vis = (self.read_u8(btn_accept + 0x1A0) == 1) if btn_accept else False
            dec_vis = (self.read_u8(btn_decline + 0x1A0) == 1) if btn_decline else False

            p_qdlg = self.read_u32(p_active_dlg + 0x98)
            enum_type = self.read_u32(p_qdlg + 0x5C) if p_qdlg else None
            p_quest = self.read_u32(p_qdlg + 0x8) if p_qdlg else None
            if p_quest:
                dialog_quest_name = self.read_wstring(self.read_u32(p_quest + 0x98))
                raw_title = self.read_wstring(self.read_u32(p_quest + 0xB4))
                dialog_quest_title = strip_torchlight_formatting(raw_title)

            # Classificação dos tipos de diálogo conforme Enum nativo e botões
            if acc_vis and dec_vis:
                dialog_type = "missao_aceitar"
                dialog_buttons = ["accept", "decline"]
                open_menus.append("Missão (Aceitar)")
            elif acc_vis and not dec_vis:
                dialog_type = "missao_principal"
                dialog_buttons = ["accept"]
                open_menus.append("Missão Principal")
            elif ok_vis:
                if enum_type == 3:
                    dialog_type = "missao_concluida"
                    dialog_buttons = ["ok"]
                    open_menus.append("Missão (Concluída)")
                elif enum_type == 2:
                    dialog_type = "missao_andamento"
                    dialog_buttons = ["ok"]
                    open_menus.append("Missão (Em Andamento)")
                else:
                    dialog_type = "simples"
                    dialog_buttons = ["ok"]
                    open_menus.append("Diálogo Simples")
            else:
                dialog_type = "simples"
                dialog_buttons = ["ok"]
                open_menus.append("Diálogo")

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
            dialog_type=dialog_type,
            dialog_buttons=dialog_buttons,
            dialog_quest_name=dialog_quest_name,
            dialog_quest_title=dialog_quest_title,
        )
