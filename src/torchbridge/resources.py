"""Find runtime assets in a checkout, an installed wheel or a portable bundle."""
from pathlib import Path
import sys
import site


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "assets/images/app").is_dir():
        return checkout
    prefix = Path(sys.prefix) / "share/torchbridge"
    if prefix.is_dir():
        return prefix
    user = Path(site.getuserbase()) / "share/torchbridge"
    return user if user.is_dir() else prefix
