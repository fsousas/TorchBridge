import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for name in z.namelist():
        if ("skill" in name.lower() or "tree" in name.lower()) and name.endswith(".DAT.adm") or name.endswith(".DAT"):
            if "affixes" not in name.lower():
                print(name)
