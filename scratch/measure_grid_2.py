import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
import zlib
from scratch.measure_grid import load_png

img_path = r"C:\Users\kleve\.gemini\antigravity-ide\brain\d8d0b587-9b7c-4baf-b543-53b9cbec8636\.tempmediaStorage\media_1792721111547.png"
w, h, pix = load_png(img_path)

# Vamos procurar a moldura do grid:
# A moldura é um retângulo com borda dourada/marrom clara que envolve o grid
# Nos prints, o grid do slot 1 está entre X=200 e X=800, Y=650 e Y=900
# Vamos escanear pixels em x=200..800
for y in range(650, 930, 2):
    row_str = ""
    # conta quantos pixels têm fundo muito escuro
    dark_pixels = sum(1 for x in range(200, 850) if pix[(y*w + x)*4] < 20 and pix[(y*w + x)*4 + 1] < 20 and pix[(y*w + x)*4 + 2] < 20)
    if dark_pixels > 100:
        # Acha start_x e end_x dos dark_pixels
        xs = [x for x in range(200, 850) if pix[(y*w + x)*4] < 20 and pix[(y*w + x)*4 + 1] < 20 and pix[(y*w + x)*4 + 2] < 20]
        print(f"y={y}: dark_pixels={dark_pixels}, min_x={min(xs)}, max_x={max(xs)}, largura={max(xs) - min(xs)}")

