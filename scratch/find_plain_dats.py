import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    dats = [n for n in z.namelist() if n.lower().endswith(".dat")]
    print(f"Plain text .DAT files: {len(dats)}")
    for d in dats[:20]:
        print(" ", d)
