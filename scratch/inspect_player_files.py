import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    names = z.namelist()
    player_files = [n for n in names if "player" in n.lower() or "classes" in n.lower()]
    for f in player_files[:40]:
        print(f"  {f}")
