from pathlib import Path
import re

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

for m in re.finditer(rb"[a-zA-Z0-9_/\\-]+\.layout", data, re.IGNORECASE):
    print(f"Offset 0x{m.start():08X}: {m.group().decode('latin1', errors='ignore')}")
