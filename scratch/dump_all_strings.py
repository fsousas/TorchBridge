import zipfile
import re
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for cls in ["Alchemist"]:
        raw = z.read(f"media/units/players/{cls}/{cls.upper()}.DAT.adm")
        matches = re.findall(rb'(?:[\x20-\x7e]\x00){2,}', raw)
        strings = [m.decode("utf-16le") for m in matches]
        for i, s in enumerate(strings):
            print(f"[{i:3d}] {s}")
