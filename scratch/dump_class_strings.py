import zipfile
import re
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for cls in ["Alchemist", "Destroyer", "Vanquisher"]:
        filename = f"media/units/players/{cls}/{cls.upper()}.DAT.adm"
        raw = z.read(filename)
        # Extract utf-16 strings
        matches = re.findall(rb'(?:[\x20-\x7e]\x00){3,}', raw)
        strings = [m.decode("utf-16le") for m in matches]
        print(f"\n=== {cls} (total strings: {len(strings)}) ===")
        # Look for skills or tree references
        skill_refs = [s for s in strings if "SKILL" in s or "TREE" in s or "TAB" in s]
        print(f"Skill/Tree strings: {len(skill_refs)}")
        for s in strings:
            if any(k in s for k in ["SKILL", "TREE", "TAB", "LEVEL"]):
                print("  ", s)
