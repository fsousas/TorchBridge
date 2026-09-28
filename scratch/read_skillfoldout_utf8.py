import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    for name in z.namelist():
        if "skillfoldout.layout" in name.lower():
            text = z.read(name).decode("utf-8")
            with open(r"c:\Users\kleve\Documents\Projetos\TorchBridge\scratch\skillfoldout.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("Wrote skillfoldout.txt, size:", len(text))
