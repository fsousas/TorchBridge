import zipfile
import struct
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def parse_adm_skills(cls_name):
    with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
        filename = f"media/units/players/{cls_name}/{cls_name.upper()}.DAT.adm"
        raw = z.read(filename)

    version, num_strings = struct.unpack_from("<II", raw, 0)
    offset = 8
    strings = []
    for _ in range(num_strings):
        str_id, str_len = struct.unpack_from("<II", raw, offset)
        offset += 8
        s = raw[offset:offset + str_len * 2].decode("utf-16le")
        strings.append(s)
        offset += str_len * 2

    # Map string -> index
    str_to_idx = {s: i for i, s in enumerate(strings)}
    
    # We want to find SKILL blocks
    # In Torchlight ADM, tokens reference string indices
    # Let's search raw for occurrences of string index for "SKILL"
    # and find surrounding PANE, COLUMN, ROW, LEVEL_REQUIRED
    print(f"\n==================== {cls_name} ====================")
    # Print tab names
    for tab_key in ["SKILL_TAB1", "SKILL_TAB2", "SKILL_TAB3"]:
        if tab_key in str_to_idx:
            t_idx = str_to_idx[tab_key]
            # search where t_idx is in the tail
            p = 0
            while True:
                idx = raw.find(struct.pack("<H", t_idx), offset + p)
                if idx == -1:
                    break
                # The value string index is shortly after
                val_u16 = struct.unpack_from("<H", raw, idx + 4)[0]
                if val_u16 < len(strings):
                    print(f"{tab_key}: {strings[val_u16]}")
                    break
                p = (idx - offset) + 1

    # Let's scan for all skill blocks in the tail
    # Each block has SKILL (name), PANE, COLUMN, ROW, LEVEL_REQUIRED
    # Let's search for "PANE", "COLUMN", "ROW"
    idx_skill = str_to_idx.get("SKILL")
    idx_pane = str_to_idx.get("PANE")
    idx_col = str_to_idx.get("COLUMN")
    idx_row = str_to_idx.get("ROW")
    idx_lvl = str_to_idx.get("LEVEL_REQUIRED")
    
    print(f"Indices: SKILL={idx_skill}, PANE={idx_pane}, COL={idx_col}, ROW={idx_row}, LVL={idx_lvl}")
    
    # Let's scan 4-byte / 2-byte aligned words in tail
    skills = []
    tail = raw[offset:]
    for i in range(0, len(tail) - 30, 2):
        u16 = struct.unpack_from("<H", tail, i)[0]
        if u16 == idx_skill:
            # We found a SKILL key!
            # Let's see what is nearby
            # Let's inspect next 40 bytes
            chunk = tail[i:i+60]
            words = [struct.unpack_from("<H", chunk, j)[0] for j in range(0, len(chunk), 2)]
            # Check if any word is idx_pane
            if idx_pane in words:
                # Skill name index is words[2]
                name_idx = words[2]
                skill_name = strings[name_idx] if name_idx < len(strings) else f"idx_{name_idx}"
                pane = -1
                col = -1
                row = -1
                lvl = -1
                for w_i, w in enumerate(words):
                    if w == idx_pane and w_i + 2 < len(words):
                        pane = words[w_i + 2]
                    elif w == idx_col and w_i + 2 < len(words):
                        col = words[w_i + 2]
                    elif w == idx_row and w_i + 2 < len(words):
                        row = words[w_i + 2]
                    elif w == idx_lvl and w_i + 2 < len(words):
                        lvl = words[w_i + 2]
                skills.append((pane, col, row, skill_name, lvl))

    print(f"Extracted {len(skills)} skills:")
    for s in sorted(skills, key=lambda x: (x[0], x[2], x[1])):
        print(f"  Pane {s[0]}, Row {s[2]}, Col {s[1]}: '{s[3]}' (Req Lv: {s[4]})")

for cls in ["Destroyer", "Vanquisher", "Alchemist"]:
    parse_adm_skills(cls)
