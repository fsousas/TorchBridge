from PIL import Image

im = Image.open('assets/images/menus/skilltrees/character+skill 4x3 - player has no points.png').convert('RGB')
pts = []
for y in range(550, 700):
    for x in range(680, 1000):
        r, g, b = im.getpixel((x, y))
        col = None
        if g > 170 and r < 90 and b < 90:
            col = 'green'
        elif r > 210 and 80 < g < 185 and b < 65:
            col = 'orange'
        if col:
            pts.append((x, y, col))

clusters = []
for x, y, col in pts:
    found = False
    for c in clusters:
        cx, cy = c['center']
        if abs(cx - x) < 30 and abs(cy - y) < 30:
            c['pts'].append((x, y))
            c['center'] = (sum(p[0] for p in c['pts'])/len(c['pts']), sum(p[1] for p in c['pts'])/len(c['pts']))
            found = True
            break
    if not found:
        clusters.append({'col': col, 'center': (x, y), 'pts': [(x, y)]})

clusters.sort(key=lambda c: c['center'][0])
for i, c in enumerate(clusters):
    cx, cy = c['center']
    client_y = cy - 32
    col_str = c['col']
    cnt = len(c['pts'])
    print(f"Spell slot {i}: {col_str} at x={cx:.1f}, y={cy:.1f} -> client_y={client_y:.1f}, pts={cnt}")
