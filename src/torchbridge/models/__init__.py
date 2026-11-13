from __future__ import annotations

from typing import Any

from . import base, character, hud, inventory, keyboard, screens
from .base import (
    Rect,
    ControllerState,
    controller_type_from_name,
    OverlaySnapshot,
    SharedOverlayState,
    DEBUG_MENU_ITEMS,
    DEFAULT_DEBUG_OPTIONS,
    get_project_root,
    resource_root,
)
from .hud import *
from .hud import _rasterize_hud_mask, _CLOSE_TAB_SVG
from .keyboard import *
from .screens import *
from .inventory import *
from .character import *

__annotations__: dict[str, Any] = {}
for _mod in (base, hud, keyboard, screens, inventory, character):
    if hasattr(_mod, "__annotations__"):
        __annotations__.update(_mod.__annotations__)
