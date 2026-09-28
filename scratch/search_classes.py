from pathlib import Path
import re

EXE_PATH = Path(r"C:\GOG Games\Torchlight\Torchlight.exe")
data = EXE_PATH.read_bytes()

# Search for case-insensitive ascii and utf-16 of "destroyer", "vanquisher", "alchemist"
for word in ["destroyer", "vanquisher", "alchemist"]:
    print(f"=== Matches for {word} ===")
    for pattern, enc in [(word.encode("ascii"), "ascii"), (word.encode("utf-16le"), "utf-16")]:
        p = 0
        while True:
            idx = data.lower().find(pattern.lower(), p)
            if idx == -1:
                break
            # get surrounding text
            start = max(0, idx - 10)
            end = min(len(data), idx + len(pattern) + 20)
            print(f"  [{enc}] offset 0x{idx:08X} (VA 0x{0x00400000 + idx:08X}): {data[start:end]}")
            p = idx + 1
            if p > idx + 50:
                break
