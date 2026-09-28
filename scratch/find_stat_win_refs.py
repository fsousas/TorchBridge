import struct
from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

# Search for pointer to 0x00A90079 or nearby
for target_va in range(0x00A90060, 0x00A900A0, 4):
    target_bytes = struct.pack("<I", target_va)
    p = 0
    while True:
        idx = data.find(target_bytes, p)
        if idx == -1:
            break
        print(f"Ref to 0x{target_va:08X} at 0x{0x00400000 + idx:08X}")
        p = idx + 1
