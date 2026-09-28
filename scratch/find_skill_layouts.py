from pathlib import Path
import re

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

# Search for strings containing "skills" or "skilltree" or ".layout"
for m in re.finditer(rb"[a-zA-Z0-9_/\\-]*skill[a-zA-Z0-9_/\\-]*\.layout", data, re.IGNORECASE):
    print(f"Found layout at offset 0x{m.start():08X} (VA 0x{0x00400000 + m.start():08X}): {m.group()}")
