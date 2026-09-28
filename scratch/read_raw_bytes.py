import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for name in z.namelist():
        if "skillfoldout.layout" in name.lower():
            raw = z.read(name)
            print("Bytes:", raw[:40])
