from __future__ import annotations

import logging
from .window import GameOverlayBase
from .radial import RadialOverlayMixin, _radial_icons_dir, _radial_extra_hud_dir
from .bottom_hud import BottomHudOverlayMixin
from .pet_submenu import PetSubmenuOverlayMixin
from .keyboard import VirtualKeyboardOverlayMixin, KeyboardInputSurface
from .shortcut_config import ShortcutConfigOverlayMixin
from .calibration import CalibrationOverlayMixin
from .welcome import WelcomeOverlayMixin
from .interaction import WorldInteractionOverlayMixin
from .debug_menu import DebugMenuOverlayMixin

log = logging.getLogger(__name__)


class GameOverlay(
    DebugMenuOverlayMixin,
    WelcomeOverlayMixin,
    WorldInteractionOverlayMixin,
    RadialOverlayMixin,
    BottomHudOverlayMixin,
    PetSubmenuOverlayMixin,
    VirtualKeyboardOverlayMixin,
    ShortcutConfigOverlayMixin,
    CalibrationOverlayMixin,
    GameOverlayBase,
):
    """Janela de overlay do TorchBridge com suporte a HUD, radial menu, atalhos e teclado virtual."""
    pass
