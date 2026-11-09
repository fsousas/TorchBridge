"""Immutable world data and geometry shared by Windows and Proton.

Torchlight uses Ogre's X/Z ground plane. Public map coordinates are (x, y),
where map y is Ogre z; height is Ogre y. Distances are game units, not pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class WorldPosition:
    x: float
    y: float
    height: float = 0.0

    @property
    def valid(self) -> bool:
        return all(math.isfinite(v) and abs(v) <= 1_000_000 for v in (self.x, self.y, self.height))

    def distance_to(self, other: WorldPosition) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


KIND_LABELS = {
    "npc": "NPC", "portal": "Portal", "stairs": "Escadas",
    "health_shrine": "Fonte de vida", "mana_shrine": "Fonte de mana",
    "enchant_shrine": "Fonte de melhoria", "shrine": "Fonte",
    "door": "Porta", "lever": "Alavanca", "fishing": "Local de pesca",
    "chest": "Baú", "interactive": "Objeto interativo",
}

NPC_ROLE_LABELS = {
    "merchant": "Mercador", "gambler": "Mercador (Apostador)",
    "enchanter": "Encantador", "transmuter": "Transmutador",
    "gem_recover": "Recuperador de gemas", "gem_destroy": "Removedor de gemas",
}
QUEST_STATUS_LABELS = {
    "available": "Missão disponível (!)", "in_progress": "Missão em andamento (?)",
    "ready_to_turn_in": "Missão para entregar (?)", "unavailable": "Missão indisponível",
    "unknown": "Missão não verificada",
}


def classify_prop(identifier: str, name: str) -> str:
    # The internal NAME is independent of translations; DISPLAYNAME is a fallback.
    text = unicodedata.normalize("NFKD", f"{identifier} {name}").encode("ascii", "ignore").decode().upper()
    rules = (
        ("fishing", ("FISH", "PESCA")),
        ("stairs", ("STAIR", "ESCADA")),
        ("health_shrine", ("HEALING", "HEALTH", "VIDA", "CURA")),
        ("mana_shrine", ("MANA",)),
        ("enchant_shrine", ("ENCHANTSHRINE", "ENCHANTING SHRINE", "MELHORIA", "ENCANTAMENTO")),
        ("portal", ("PORTAL", "WARP", "WAYGATE", "WAYPOINT")),
        ("lever", ("LEVER", "ALAVANCA", "HORN")),
        ("door", ("DOOR", "GATE", "BOOKCASE", "PORTA")),
        ("shrine", ("SHRINE", "FOUNTAIN", "FONTE")),
        ("chest", ("CHEST", "STASH", "BAU")),
    )
    return next((kind for kind, words in rules if any(word in text for word in words)), "interactive")


def clean_name(text: str) -> str:
    text = re.sub(r"\|c[0-9a-fA-F]{8}", "", text).replace("|u", "").replace("|U", "")
    return " ".join("".join(c for c in text if c.isprintable()).split())[:160]


@dataclass(frozen=True, slots=True)
class WorldEntity:
    address: int
    kind: str
    name: str
    position: WorldPosition
    identifier: str = ""
    npc_role: str = ""
    quest_status: str = ""

    @property
    def label(self) -> str:
        label = KIND_LABELS.get(self.kind, KIND_LABELS["interactive"])
        if self.kind == "npc":
            label = NPC_ROLE_LABELS.get(self.npc_role, label)
            if self.quest_status in QUEST_STATUS_LABELS:
                label += " · " + QUEST_STATUS_LABELS[self.quest_status]
        return label

    @property
    def is_merchant(self) -> bool:
        return self.kind == "npc" and self.npc_role in ("merchant", "gambler")


@dataclass(frozen=True, slots=True)
class WorldCamera:
    view: tuple[float, ...]
    projection: tuple[float, ...]

    @property
    def valid(self) -> bool:
        return (len(self.view) == len(self.projection) == 16
                and all(math.isfinite(v) for v in self.view + self.projection)
                and all(abs(self.view[i]) < 1e-4 for i in (12, 13, 14))
                and abs(self.view[15] - 1) < 1e-4
                and abs(self.projection[0]) > 1e-6 and abs(self.projection[5]) > 1e-6)

    def project(self, position: WorldPosition, width: int, height: int,
                lift: float = 0.0) -> tuple[int, int] | None:
        """Local client pixels/logical coordinates, never desktop/DPI coordinates."""
        if not self.valid or not position.valid or width <= 0 or height <= 0:
            return None
        point = (position.x, position.height + lift, position.y, 1.0)
        eye = tuple(sum(self.view[r * 4 + c] * point[c] for c in range(4)) for r in range(4))
        clip = tuple(sum(self.projection[r * 4 + c] * eye[c] for c in range(4)) for r in range(4))
        if not all(math.isfinite(v) for v in clip) or clip[3] <= 1e-4:
            return None
        x, y, z = (clip[i] / clip[3] for i in range(3))
        if not (-1 <= x <= 1 and -1 <= y <= 1 and -1 <= z <= 1):
            return None
        px, py = round((x + 1) * width / 2), round((1 - y) * height / 2)
        return (px, py) if 2 <= px < width - 2 and 2 <= py < height - 2 else None


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    level_address: int = 0
    level_name: str = ""
    player_address: int = 0
    player_position: WorldPosition | None = None
    entities: tuple[WorldEntity, ...] = ()
    camera: WorldCamera | None = None
    sampled_at: float = 0.0
    roster_complete: bool = False
    status: str = "Aguardando cenário"

    def fresh(self, now: float) -> bool:
        return (self.player_position is not None and self.player_position.valid
                and self.level_address != 0 and 0 <= now - self.sampled_at <= 0.2)

    def nearby(self, radius: float, max_height: float = 2.5) -> tuple[WorldEntity, ...]:
        player = self.player_position
        if player is None or not player.valid or not math.isfinite(radius) or radius <= 0:
            return ()
        return tuple(sorted((entity for entity in self.entities
                             if entity.position.valid
                             and abs(entity.position.height - player.height) <= max_height
                             and player.distance_to(entity.position) <= radius),
                            key=lambda entity: (player.distance_to(entity.position), entity.address)))


INTERACTION_BUTTONS = ("dpad_up", "dpad_down", "l3")
INTERACTION_LABELS = {"dpad_up": "D-pad ↑", "dpad_down": "D-pad ↓", "l3": "L3"}
