"""Read-only diagnostic report. Never sends keys, clicks or cursor motion."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import sys


def collect():
    from .config import user_config_dir
    from .resources import resource_root
    report = {"system": platform.system(), "python": platform.python_version(),
              "config": str(user_config_dir()), "assets": str(resource_root() / "assets")}
    if not sys.platform.startswith("linux"):
        report["ready"] = os.name == "nt"
        return report
    from .linux import Hyprland, WindowLocator
    from .config import DEFAULT_CONFIG
    from .memory import TorchlightMemoryReader
    from .wayland import Connection
    report["ready"] = True
    report["wayland"] = bool(os.environ.get("WAYLAND_DISPLAY"))
    report["hyprland"] = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    report["xwayland"] = bool(os.environ.get("DISPLAY"))
    try:
        report["monitors"] = [{k: m[k] for k in ("name", "x", "y", "width", "height", "scale", "transform")}
                               for m in Hyprland.monitors()]
        for mode, name in ((False, "layer_shell"), (True, "virtual_input")):
            connection = Connection(input=mode)
            connection.close()
            report[name] = True
        target = DEFAULT_CONFIG["target"]
        locator = WindowLocator(target["process_names"], target["window_titles"])
        window = locator.find()
        reader = TorchlightMemoryReader()
        try:
            state = reader.update(target_pid=locator.window_pid(window) if window else -1)
            report["game"] = {"found": bool(window), "pid": state.pid,
                              "memory_connected": state.is_connected, "version": state.game_version,
                              "state": state.state_desc, "error": reader.last_error}
            if reader.last_error:
                report["ready"] = False
        finally:
            reader.close()
        scope = Path("/proc/sys/kernel/yama/ptrace_scope")
        report["ptrace_scope"] = scope.read_text().strip() if scope.exists() else "unavailable"
    except (OSError, ValueError, RuntimeError) as error:
        report["error"] = str(error)
        report["ready"] = False
    if not all(report[k] for k in ("wayland", "hyprland", "xwayland")):
        report["ready"] = False
    return report


def main():
    report = collect()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready"] else 1
