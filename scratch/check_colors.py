from PIL import Image

def find_colored_regions(img_path):
    im = Image.open(img_path).convert('RGB')
    w, h = im.size
    print(f'=== {img_path} (size: {w}x{h}) ===')
    nodes = []
    for y in range(0, h, 2):
        for x in range(0, min(550, w), 2):
            r, g, b = im.getpixel((x, y))
            col = None
            if g > 170 and r < 90 and b < 90:
                col = 'green'
            elif r > 210 and 100 < g < 185 and b < 65:
                col = 'orange'
            elif r > 210 and g < 110 and b > 140:
                col = 'pink'
            elif r > 220 and g > 210 and b < 100:
                col = 'yellow'
            if col:
                nodes.append((x, y, col, (r, g, b)))
    
    clusters = []
    for x, y, col, rgb in nodes:
        found = False
        for c in clusters:
            cx, cy = c['center']
            if abs(cx - x) < 22 and abs(cy - y) < 22 and c['col'] == col:
                c['pts'].append((x, y))
                c['center'] = (sum(p[0] for p in c['pts'])/len(c['pts']), sum(p[1] for p in c['pts'])/len(c['pts']))
                found = True
                break
        if not found:
            clusters.append({'col': col, 'center': (x, y), 'pts': [(x, y)]})
    clusters.sort(key=lambda c: (c['center'][1], c['center'][0]))
    for c in clusters:
        if len(c['pts']) > 3:
            pts_cnt = len(c['pts'])
            print(f"  {c['col']:8s} at x={c['center'][0]:.1f}, y={c['center'][1]:.1f} ({pts_cnt} pts)")

find_colored_regions('assets/images/menus/skilltrees/character+skill 4x3 - player has no points.png')
find_colored_regions('assets/images/menus/skilltrees/character+skill 4x3 - player has points.png')
