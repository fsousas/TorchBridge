import zipfile
import struct

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    raw = z.read("media/units/players/Alchemist/ALCHEMIST.DAT.adm")

# Let's inspect the header and string table or blocks
print("Total size:", len(raw))
# The first 4 bytes are version (1)
version, num_strings = struct.unpack_from("<II", raw, 0)
print(f"Version: {version}, num_strings: {num_strings}")

# Let's parse the string table
offset = 8
strings = []
for i in range(num_strings):
    str_id, str_len = struct.unpack_from("<II", raw, offset)
    offset += 8
    # UTF-16LE string of length str_len (str_len characters = str_len * 2 bytes)
    s = raw[offset:offset + str_len * 2].decode("utf-16le")
    strings.append(s)
    offset += str_len * 2

print(f"Read {len(strings)} strings. Remainder offset: 0x{offset:04X} ({offset}/{len(raw)})")
print("First 20 strings:", strings[:20])
print("Tail offset:", offset)
