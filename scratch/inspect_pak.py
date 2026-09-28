import zipfile

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    names = z.namelist()
    skill_files = [n for n in names if "skill" in n.lower() or "class" in n.lower()]
    print(f"Total files in Pak.zip: {len(names)}")
    print(f"Skill/Class files: {len(skill_files)}")
    for f in skill_files[:40]:
        print(f"  {f}")
