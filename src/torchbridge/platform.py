"""Platform boundary; never import Linux native libraries on Windows."""
import os
import sys

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    from .win32 import (InputInjector, WindowLocator, SingleInstance, enable_dpi_awareness,
                        show_information, make_overlay_clickthrough, position_overlay,
                        begin_high_resolution_timer, end_high_resolution_timer)
elif IS_LINUX:
    from .linux import (InputInjector, WindowLocator, SingleInstance, enable_dpi_awareness,
                        show_information, make_overlay_clickthrough, position_overlay,
                        begin_high_resolution_timer, end_high_resolution_timer)
else:
    raise RuntimeError("TorchBridge suporta Windows e Omarchy Linux")
