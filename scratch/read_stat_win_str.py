from pathlib import Path

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

off = 0x00A90070 - 0x00400000
print(data[off:off+100])
