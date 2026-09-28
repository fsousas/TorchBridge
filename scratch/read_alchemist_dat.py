import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    raw = z.read("media/units/players/Alchemist/ALCHEMIST.DAT.adm")
    print("Length:", len(raw))
    print("Raw bytes:", raw[:80])
