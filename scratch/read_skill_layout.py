import zipfile
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for name in z.namelist():
        if "skillmenu.layout" in name.lower():
            print(f"Found: {name}")
            content = z.read(name)
            try:
                text = content.decode("utf-16")
            except Exception:
                text = content.decode("utf-8", errors="ignore")
            # Write to scratch/skillmenu.layout.xml
            with open(r"c:\Users\kleve\Documents\Projetos\TorchBridge\scratch\skillmenu.layout.xml", "w", encoding="utf-8") as out:
                out.write(text)
            print("Written to scratch/skillmenu.layout.xml, length:", len(text))
