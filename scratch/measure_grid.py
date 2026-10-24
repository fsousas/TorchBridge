import sys
from pathlib import Path
import struct

# Decodificador PNG simples em python puro sem PIL
# Vamos ler a imagem usando biblioteca padrão ou zlib
import zlib

def load_png(path):
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    
    pos = 8
    width = height = bit_depth = color_type = 0
    idat = []
    
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        pos += 12 + length
        
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
        elif chunk_type == b"IDAT":
            idat.append(chunk_data)
        elif chunk_type == b"IEND":
            break
            
    raw_data = zlib.decompress(b"".join(idat))
    # Para RGB (color_type 2, 3 bytes por pixel) ou RGBA (color_type 6, 4 bytes por pixel)
    bpp = 4 if color_type == 6 else 3
    stride = width * bpp
    
    # Reconstrói scanlines com filtros PNG
    pixels = bytearray(width * height * 4)
    out_pos = 0
    in_pos = 0
    
    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    
    for y in range(height):
        filter_type = raw_data[in_pos]
        in_pos += 1
        row_raw = raw_data[in_pos:in_pos+stride]
        in_pos += stride
        
        for i in range(stride):
            val = row_raw[i]
            a = curr_row[i - bpp] if i >= bpp else 0
            b = prev_row[i]
            c = prev_row[i - bpp] if i >= bpp else 0
            
            if filter_type == 0:
                filt = val
            elif filter_type == 1:
                filt = (val + a) & 0xFF
            elif filter_type == 2:
                filt = (val + b) & 0xFF
            elif filter_type == 3:
                filt = (val + ((a + b) >> 1)) & 0xFF
            elif filter_type == 4:
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - 2*c)
                p = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                filt = (val + p) & 0xFF
            else:
                filt = val
            curr_row[i] = filt
            
        for x in range(width):
            if bpp == 4:
                pixels[out_pos:out_pos+4] = curr_row[x*4:x*4+4]
            else:
                pixels[out_pos:out_pos+3] = curr_row[x*3:x*3+3]
                pixels[out_pos+3] = 255
            out_pos += 4
            
        prev_row[:] = curr_row[:]
        
    return width, height, pixels

img_path = r"C:\Users\kleve\.gemini\antigravity-ide\brain\d8d0b587-9b7c-4baf-b543-53b9cbec8636\.tempmediaStorage\media_1792721111547.png"
w, h, pix = load_png(img_path)
print(f"Loaded image: {w}x{h}")

# Procura a borda do popup grid na metade inferior da tela
# A borda tem cor cinza/marrom (aprox rgb 140, 110, 80 ou similar) e fundo quase preto (rgb < 30)
# Vamos varrer linhas de y = 600 até 900
# procurando uma linha horizontal longa com caixa preta
for y in range(650, 950, 5):
    black_run = 0
    max_run = 0
    start_x = 0
    best_start = 0
    for x in range(100, w - 100):
        idx = (y * w + x) * 4
        r, g, b = pix[idx], pix[idx+1], pix[idx+2]
        # Se for muito escuro (interior da janela de popup)
        if r < 30 and g < 30 and b < 30:
            if black_run == 0:
                start_x = x
            black_run += 1
            if black_run > max_run:
                max_run = black_run
                best_start = start_x
        else:
            black_run = 0
    if max_run > 300:
        print(f"y={y}: interior escuro de x={best_start} até {best_start + max_run} (largura={max_run})")

