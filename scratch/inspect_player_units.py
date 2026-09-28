import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    names = z.namelist()
    player_units = [n for n in names if n.startswith("media/units/players")]
    for f in player_units:
        print(f"  {f}")
