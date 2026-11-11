"""Bounded, read-only world traversal for Torchlight 1 PE32 (Steam/GOG).

Only uses the reader's read_bytes/u32/u8/f32 interface, so no platform APIs or
game calls/writes live here. See docs/POSICIONAMENTO.md for layout evidence.
"""
from __future__ import annotations

import math
import struct
from typing import Protocol

from .world import WorldCamera, WorldEntity, WorldPosition, WorldSnapshot, classify_prop, clean_name

LEVEL_CHARACTERS = 0x5C
LEVEL_ITEMS = 0x68
POSITION = 0x70
OBJECT_NAME = 0x30
ITEM_NAME = 0x1B0
CHARACTER_NAME = 0x420
LEVEL_NAME = 0x1F0
MAX_NODES = 4096
MAX_CLASSES = 256
MAX_NPC_TAGS = 128
MAX_TAG_NAMES = 512
# Vanilla Steam/GOG UNITTYPE ids (UNITTYPES.HIE): classify the role, not the NPC's name.
NPC_ROLES = {41: "merchant", 127: "gambler", 130: "enchanter", 134: "transmuter",
             132: "gem_recover", 133: "gem_destroy", 128: "stash", 170: "shared_stash",
             175: "retirement"}
QUEST_TAGS = {"QUEST COMPLETE": "ready_to_turn_in", "QUEST GIVING": "available",
              "QUEST INCOMPLETE": "in_progress", "QUEST PASSIVE": "unavailable"}


class MemorySource(Protocol):
    def read_bytes(self, address: int, size: int) -> bytes: ...
    def read_u32(self, address: int) -> int | None: ...
    def read_u8(self, address: int) -> int | None: ...
    def read_f32(self, address: int) -> float | None: ...


def pointer(value: int | None) -> bool:
    return isinstance(value, int) and 0x10000 <= value < 0xFFFF0000 and value % 4 == 0


class WorldMemoryReader:
    def __init__(self, memory: MemorySource):
        self.memory = memory
        self.reset()

    def reset(self) -> None:
        self._classes: dict[int, str] = {}
        self._class_bases: dict[int, frozenset[str]] = {}
        self._tag_names: dict[int, str] = {}
        self._context = None
        self._entities_complete = True

    def _string(self, address: int, header: bytes | None = None) -> str:
        """MSVC 2008 std::wstring: allocator, union[16], size, capacity (28 bytes)."""
        raw = header if header is not None else self.memory.read_bytes(address, 28)
        if len(raw) != 28:
            return ""
        size, capacity = struct.unpack_from("<II", raw, 20)
        if not 0 < size <= 256 or size > capacity or capacity > 65536:
            return ""
        if capacity < 8:
            data = raw[4:4 + size * 2]
        else:
            buffer = struct.unpack_from("<I", raw, 4)[0]
            if not pointer(buffer):
                return ""
            data = self.memory.read_bytes(buffer, size * 2)
        if len(data) != size * 2:
            return ""
        try:
            return clean_name(data.decode("utf-16-le"))
        except UnicodeDecodeError:
            return ""

    def _class(self, address: int) -> str:
        vt = self.memory.read_u32(address)
        if not pointer(vt):
            return ""
        if vt in self._classes:
            return self._classes[vt]
        # MSVC x86 RTTI: vtable[-1] -> COL -> TypeDescriptor -> decorated name.
        col = self.memory.read_u32(vt - 4)
        td = self.memory.read_u32(col + 12) if pointer(col) else None
        raw = self.memory.read_bytes(td + 8, 96) if pointer(td) else b""
        name = raw.split(b"\0", 1)[0]
        if not name.startswith(b".?AVC") or not name.endswith(b"@@"):
            return ""
        result = name[4:-2].decode("ascii", errors="replace")
        if len(self._classes) >= MAX_CLASSES:
            self._classes.clear()
            self._class_bases.clear()
        self._classes[vt] = result
        bases = {result}
        hierarchy = self.memory.read_u32(col + 16)
        count = self.memory.read_u32(hierarchy + 8) if pointer(hierarchy) else 0
        array = self.memory.read_u32(hierarchy + 12) if pointer(hierarchy) else 0
        if isinstance(count, int) and 0 < count <= 64 and pointer(array):
            for i in range(count):
                descriptor = self.memory.read_u32(array + i * 4)
                base_td = self.memory.read_u32(descriptor) if pointer(descriptor) else 0
                base_name = self.memory.read_bytes(base_td + 8, 96) if pointer(base_td) else b""
                base_name = base_name.split(b"\0", 1)[0]
                if base_name.startswith(b".?AVC") and base_name.endswith(b"@@"):
                    bases.add(base_name[4:-2].decode("ascii", errors="replace"))
        self._class_bases[vt] = frozenset(bases)
        return result

    def _position(self, address: int, header: bytes | None = None) -> WorldPosition | None:
        # CPositionableObject::getPosition(true) uses the derived scene position
        # for parented objects; +0x70 alone would mix local and map coordinates.
        parent = (struct.unpack_from("<I", header, 0x50)[0] if header is not None
                  else self.memory.read_u32(address + 0x50))
        node = (struct.unpack_from("<I", header, 0x58)[0] if header is not None
                else self.memory.read_u32(address + 0x58))
        if parent:
            if not pointer(node) or self.memory.read_u8(node + 0xA0) != 0:
                return None
            raw = self.memory.read_bytes(node + 0x10C, 12)
        else:
            raw = header[POSITION:POSITION + 12] if header is not None else self.memory.read_bytes(address + POSITION, 12)
        if len(raw) != 12:
            return None
        x, height, y = struct.unpack("<3f", raw)
        position = WorldPosition(x, y, height)
        return position if position.valid else None

    def _list(self, level: int, offset: int, budget: list[int]) -> tuple[list[int], bool]:
        container = self.memory.read_u32(level + offset)
        if not pointer(container):
            return [], False
        node = self.memory.read_u32(container)
        seen = set()
        units = []
        while node:
            if not pointer(node) or node in seen or budget[0] <= 0:
                return units, False
            budget[0] -= 1
            seen.add(node)
            raw = self.memory.read_bytes(node, 8)
            if len(raw) != 8:
                return units, False
            unit, node = struct.unpack("<II", raw)
            if pointer(unit):
                units.append(unit)
        return units, node == 0  # None (unreadable) is not an empty list.

    def _native_label_rect(self, raw: bytes, viewport: tuple[float, float]) -> tuple[float, float, float, float] | None:
        # CItem::Show/HideLabel tracks attachment at +1A4, with the actual
        # GuiLook/ItemText window at +198. Its cached unclipped screen rectangle
        # (+360) follows the game's overlap avoidance, zoom and camera movement.
        # Reading it also observes physical Alt and the HUD toggle/D-pad left.
        window = struct.unpack_from("<I", raw, 0x198)[0]
        width, height = viewport
        if raw[0x1A4] != 1 or not pointer(window) or not width or not height:
            return None
        rect = self.memory.read_bytes(window + 0x360, 16)
        if len(rect) != 16:
            return None
        left, top, right, bottom = struct.unpack("<4f", rect)
        if not (all(math.isfinite(v) for v in (left, top, right, bottom))
                and 0 <= left < right <= width and 0 <= top < bottom <= height):
            return None
        # CEGUI::Window::isVisible(false) includes every parent's visible bit.
        seen = set()
        while window:
            if not pointer(window) or window in seen or len(seen) >= 16:
                return None
            seen.add(window)
            if self.memory.read_u8(window + 0x1A1) != 1:
                return None
            parent = self.memory.read_u32(window + 0x80)
            if parent is None:
                return None
            window = parent
        return left / width, top / height, right / width, bottom / height

    def _entity(self, address: int, characters: bool, player: int, pet: int,
                viewport: tuple[float, float] = (0., 0.)) -> WorldEntity | None:
        if address in (player, pet):
            return None
        cls = self._class(address)
        bases = self._class_bases.get(self.memory.read_u32(address), frozenset({cls}))
        if not bases.intersection(("CMonster", "CCharacter") if characters else
                                  ("CItem", "CTriggerUnit", "CEquipment", "CItemGold", "CBreakable")):
            return None
        # Batch the fixed fields: one process read instead of a syscall per flag,
        # coordinate and string header on the 50 Hz path.
        size = 0x5B8 if characters else 0x1CC
        raw = self.memory.read_bytes(address, size)
        if len(raw) != size or raw[0x6E] != 1 or raw[0x161] != 1:
            return None
        npc_role = quest_status = ""
        if characters:
            # NPCs share CMonster with enemies. Exclude pets, summons, dead and hostile units.
            if struct.unpack_from("<I", raw, 0x28C)[0] not in (1, 3):
                return None
            health = struct.unpack_from("<f", raw, 0x394)[0]
            if not 0 < health < 1e12 or struct.unpack_from("<I", raw, 0x284)[0] in (5, 6):
                return None
            if struct.unpack_from("<I", raw, 0x5B4)[0] != 0:
                return None
            kind = "npc"
            npc_role = NPC_ROLES.get(struct.unpack_from("<I", raw, 0x174)[0], "")
            quest_status = self._npc_quest_status(raw)
            name = self._string(address + CHARACTER_NAME, raw[CHARACTER_NAME:CHARACTER_NAME + 28])
        else:
            if raw[0x19C] != 1 or raw[0x19D] != 0:
                return None
            name = self._string(address + ITEM_NAME, raw[ITEM_NAME:ITEM_NAME + 28])
            kind = "interactive"
        pos = self._position(address, raw)
        if pos is None:
            self._entities_complete = False
            return None
        identifier = self._string(address + OBJECT_NAME, raw[OBJECT_NAME:OBJECT_NAME + 28])
        unit_type = struct.unpack_from("<I", raw, 0x174)[0]
        if not characters:
            if "CBreakable" in bases:
                kind = "breakable"
            elif not bases.intersection(("CTriggerUnit",)):
                kind = "gold" if cls == "CItemGold" or unit_type == 34 else "loot"
            else:
                kind = classify_prop(identifier, name, unit_type)
        radius = struct.unpack_from("<f", raw, 0x15C)[0] if kind == "fishing" else 0.0
        label_rect = (self._native_label_rect(raw, viewport)
                      if kind not in ("npc", "loot", "gold", "breakable") else None)
        return WorldEntity(address, kind, name or identifier, pos, identifier, npc_role, quest_status,
                           unit_type, "talk" if characters else "item", radius, label_rect)

    def _npc_quest_status(self, raw: bytes) -> str:
        """Read the same active/pending tag templates CBaseUnit::HasTag checks.

        These are the quest manager's live QUEST GIVING/INCOMPLETE/COMPLETE/PASSIVE
        markers, not the GUID of a quest enemy or a hardcoded list of NPC names.
        Tag templates are immutable; their per-NPC membership is read every frame.
        """
        names = set()
        seen = set()
        for offset in (0x114, 0x124):
            data, count, capacity = struct.unpack_from("<III", raw, offset)
            if count > MAX_NPC_TAGS or count > capacity or capacity > 4096:
                return "unknown"
            if count == 0:
                continue
            if not pointer(data):
                return "unknown"
            entries = self.memory.read_bytes(data, count * 4)
            if len(entries) != count * 4:
                return "unknown"
            for (tag,) in struct.iter_unpack("<I", entries):
                if tag in seen:
                    continue
                seen.add(tag)
                if not pointer(tag):
                    return "unknown"
                name = self._tag_names.get(tag)
                if name is None:
                    name = self._string(tag + 0x18)
                    if not name:
                        return "unknown"
                    if len(self._tag_names) >= MAX_TAG_NAMES:
                        self._tag_names.clear()
                    self._tag_names[tag] = name
                names.add(name)
        # The manager removes the previous marker before applying the new one.
        # Prefer an actionable state if two markers coexist during that update.
        return next((status for name, status in QUEST_TAGS.items() if name in names), "")

    def _camera(self, client: int) -> WorldCamera | None:
        control = self.memory.read_u32(client + 0x10)
        camera = self.memory.read_u32(control + 8) if pointer(control) else None
        if not pointer(camera):
            return None
        # Ogre::Camera can delegate its view to a culling frustum; projection stays on camera.
        alternate = self.memory.read_u32(camera + 0x4F0)
        view_source = alternate if pointer(alternate) else camera
        view = self.memory.read_bytes(view_source + 0x25C, 64)
        projection = self.memory.read_bytes(camera + 0x21C, 64)
        if len(view) != 64 or len(projection) != 64:
            return None
        result = WorldCamera(struct.unpack("<16f", view), struct.unpack("<16f", projection))
        return result if result.valid else None

    def read(self, client: int, player: int, now: float) -> WorldSnapshot:
        mem = self.memory
        level = mem.read_u32(client + 0x38)
        if not pointer(level) or not pointer(player):
            self.reset()
            return WorldSnapshot(status="Cenário indisponível")
        context = (client, level, player)
        if context != self._context:
            self.reset()
            self._context = context
        # Validate the root before interpreting the shared Steam/GOG layout.
        if self._class(player) != "CPlayer":
            return WorldSnapshot(status="Layout do jogador não reconhecido")
        position = self._position(player)
        if position is None:
            return WorldSnapshot(status="Posição do jogador indisponível")
        pet = mem.read_u32(client + 0x30) or 0
        budget = [MAX_NODES]
        characters, chars_ok = self._list(level, LEVEL_CHARACTERS, budget)
        props, props_ok = self._list(level, LEVEL_ITEMS, budget)
        entities = {}
        self._entities_complete = True
        ui = mem.read_u32(client + 0x3C)
        viewport = mem.read_bytes(ui + 0x13E4, 8) if pointer(ui) else b""
        viewport = struct.unpack("<2f", viewport) if len(viewport) == 8 else (0., 0.)
        if not all(math.isfinite(v) and 64 <= v <= 32768 for v in viewport):
            viewport = (0., 0.)
        for addresses, is_character in ((characters, True), (props, False)):
            for address in addresses:
                entity = self._entity(address, is_character, player, pet, viewport)
                if entity:
                    entities[address] = entity
        # Discard a torn snapshot if a level/player switch happened during traversal.
        if mem.read_u32(client + 0x38) != level or mem.read_u32(client + 0x2C) != player:
            self.reset()
            return WorldSnapshot(status="Transição de cenário")
        complete = chars_ok and props_ok and self._entities_complete
        return WorldSnapshot(level, self._string(level + LEVEL_NAME), player, position,
                             tuple(entities.values()), self._camera(client), now, complete,
                             "Disponível" if complete else "Lista do cenário incompleta")
