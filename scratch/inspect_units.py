import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    names = z.namelist()
    unit_files = [n for n in names if "media/units/" in n.lower()]
    for f in unit_files[:40]:
        print(f"  {f}")
