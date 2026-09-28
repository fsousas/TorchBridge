import zipfile
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for name in z.namelist():
        if "skillfoldout.layout" in name.lower():
            print(f"Found: {name}")
            raw = z.read(name)
            text = raw.decode("utf-16-le", errors="ignore")
            # print window names
            import re
            for m in re.finditer(r'Name="([^"]+)"', text):
                print("  Window:", m.group(1))
