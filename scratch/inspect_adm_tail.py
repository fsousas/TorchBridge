import zipfile
import struct

with zipfile.ZipFile(r"C:\GOG Games\Torchlight\Pak.zip", "r") as z:
    raw = z.read("media/units/players/Alchemist/ALCHEMIST.DAT.adm")

offset = 6000
tail = raw[offset:]
print("Tail length:", len(tail))
# Let's inspect first 100 bytes as shorts/ints
words = [struct.unpack_from("<H", tail, i)[0] for i in range(0, min(100, len(tail)), 2)]
print("Tail as u16:", words[:40])
