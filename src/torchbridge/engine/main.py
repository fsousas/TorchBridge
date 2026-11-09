from __future__ import annotations

import logging
from .core import BridgeEngineCore
from .common_menus import CommonMenuNavigationMixin
from .character import CharacterNavigationMixin
from .skills_quests import SkillQuestNavigationMixin
from .inventory import InventoryNavigationMixin
from .merchant_crafting import MerchantCraftingNavigationMixin
from .overworld import OverworldNavigationMixin
from .interaction import WorldInteractionMixin

log = logging.getLogger(__name__)


class BridgeEngine(
    WorldInteractionMixin,
    CommonMenuNavigationMixin,
    CharacterNavigationMixin,
    SkillQuestNavigationMixin,
    InventoryNavigationMixin,
    MerchantCraftingNavigationMixin,
    OverworldNavigationMixin,
    BridgeEngineCore,
):
    """120 Hz controller-to-keyboard/mouse translation loop.
    
    Composição modular de classes de navegação especializadas sobre o núcleo BridgeEngineCore.
    """
    pass
