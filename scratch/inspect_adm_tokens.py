import zipfile
import struct

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    raw = z.read("media/units/players/Alchemist/ALCHEMIST.DAT.adm")

version, num_strings = struct.unpack_from("<II", raw, 0)
offset = 8
strings = []
for _ in range(num_strings):
    str_id, str_len = struct.unpack_from("<II", raw, offset)
    offset += 8
    s = raw[offset:offset + str_len * 2].decode("utf-16le")
    strings.append(s)
    offset += str_len * 2

tail = raw[offset:]
# Search for bytes containing 62 (SKILL) or 138 (PANE)
idx_skill = strings.index("SKILL")
print("SKILL string index:", idx_skill)

# Search in tail for 32-bit or 16-bit uint matching idx_skill
for i in range(0, len(tail) - 8, 2):
    val16 = struct.unpack_from("<H", tail, i)[0]
    val32 = struct.unpack_from("<I", tail, i)[0]
    if val16 == idx_skill or val32 == idx_skill:
        # print 40 bytes around i
        snippet = tail[max(0, i-10):min(len(tail), i+50)]
        ints = [struct.unpack_from("<I", snippet, j)[0] for j in range(0, len(snippet)-4, 4)]
        shorts = [struct.unpack_from("<H", snippet, j)[0] for j in range(0, len(snippet)-2, 2)]
        print(f"Match at tail +{i}:")
        print("  as shorts:", shorts)
        print("  as ints:  ", ints)
        break
