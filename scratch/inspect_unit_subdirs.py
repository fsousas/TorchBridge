import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    names = z.namelist()
    subdirs = set()
    for n in names:
        if n.startswith("media/units/"):
            parts = n.split("/")
            if len(parts) > 2:
                subdirs.add(parts[2])
    print(f"Subdirs of media/units/: {subdirs}")
    
    # Also find any file named *.DAT with "destroyer" or "alchemist" or "vanquisher"
    matches = [n for n in names if any(c in n.lower() for c in ["destroyer", "alchemist", "vanquisher"])]
    print(f"\nTotal files matching class names: {len(matches)}")
    for m in matches[:30]:
        print(f"  {m}")
