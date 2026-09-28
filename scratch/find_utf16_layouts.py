from pathlib import Path
import re

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

for m in re.finditer(rb"(?:[a-zA-Z0-9_/\\-]\x00)+\.[\x00]l[\x00]a[\x00]y[\x00]o[\x00]u[\x00]t", data, re.IGNORECASE):
    print(f"Offset 0x{m.start():08X}: {m.group().decode('utf-16le', errors='ignore')}")
