"""showcase.py OUTDIR: the overlay used for the showcase pictures (E-M5 III 1.7, 2026-11-21). Own palette ramps
(layer 1 entries 100-124, layer 2 entries 60-63), rounded see-through panels, a histogram of rainbow bars, a tone curve
and a dial built from small boxes, and camera-font text, all between drawOsdStart and drawOsdEnd. Writes OUTDIR/hud.png.
Run with OM_BACKDROP=FILE.rgb (patch 0003; ../c3d/backdrop.py) to see it over a stand-in live view."""
import math, os, struct, sys, colorsys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osdlab import Script
def setpal(s, first, words, layer=1):
    data = b''.join(struct.pack('<I', w) for w in words)
    s.call(0x60c94f90, {'d0': first, 'd1': len(words), 'a0': 'scratch', 'a1': 'scratch+96'}, None, scratch=96 + len(data), frame=[0, 0],
           mem=[['scratch+72', '=scratch+80'], ['scratch+80', struct.pack('<H', layer).hex()], ['scratch+96', data.hex()]])
def rgb(r, g, b, a=255): return (a << 24) | (r << 16) | (g << 8) | b
out = sys.argv[1]
s = Script(out).tok('wait:3000')
N = 20
pal = []
for i in range(N):
    r, g, b = colorsys.hsv_to_rgb(0.62 - i / N * 0.62, 0.85, 1.0)   # blue -> red rainbow
    pal.append(rgb(int(r * 255), int(g * 255), int(b * 255), 235))
pal += [rgb(10, 12, 30, 150), rgb(255, 255, 255, 255), rgb(255, 200, 80, 255), rgb(120, 220, 255, 255), rgb(255, 255, 255, 110)]
setpal(s, 100, pal)
setpal(s, 60, [rgb(255,255,255), rgb(0,0,0,200), rgb(255,200,80), rgb(120,220,255)], layer=2)          # 100-119 rainbow, 120 smoked glass, 121 white, 122 amber, 123 cyan, 124 white 43%
s.update(0).tok('wait:100')
s.start()
def panel(x, y, w, h, c, r=6):
    for k in range(r):          # rounded corners: stepped insets
        inset = r - int(math.sqrt(r * r - (r - k - 0.5) ** 2))
        s.rect(x + inset, y + k, w - 2 * inset, 1, c, 1); s.rect(x + inset, y + h - 1 - k, w - 2 * inset, 1, c, 1)
    s.rect(x, y + r, w, h - 2 * r, c, 1)
# left panel: histogram from rainbow bars
panel(90, 250, 250, 160, 120)
bins = 48
for i in range(bins):
    t = i / (bins - 1)
    v = 0.15 + 0.75 * math.exp(-((t - 0.35) / 0.16) ** 2) + 0.45 * math.exp(-((t - 0.78) / 0.09) ** 2)
    h = int(130 * min(v, 1.0))
    s.rect(102 + i * 4 + 0, 396 - int(h*0.8), 3, int(h*0.8), 100 + int(t * (N - 1)), 1)
s.rect(102, 397, 192, 2, 121, 1)
# curve: a tone curve of thick dots over a grid
panel(400, 44, 240, 196, 120)
GX, GY, GW, GH = 416, 88, 208, 136
for k in range(1, 4):
    s.rect(GX + k * GW // 4, GY, 1, GH, 124, 1); s.rect(GX, GY + k * GH // 4, GW, 1, 124, 1)
s.rect(GX, GY, GW, 1, 124, 1); s.rect(GX, GY + GH, GW + 1, 1, 124, 1); s.rect(GX, GY, 1, GH, 124, 1); s.rect(GX + GW, GY, 1, GH, 124, 1)
def curve(t):
    y = 1 / (1 + math.exp(-9 * (t - 0.5))); return (y - 0.0110) / (0.9890 - 0.0110)
for i in range(0, GW + 1, 2):
    py = int(GY + GH - curve(i / GW) * GH); s.rect(GX + i - 1, py - 1, 3, 3, 122, 1)
for tx in (0.25, 0.75):
    cx, cy = int(GX + tx * GW), int(GY + GH - curve(tx) * GH)
    s.rect(cx - 5, cy - 5, 11, 11, 121, 1); s.rect(cx - 3, cy - 3, 7, 7, 123, 1)
# level gauge: a dotted arc and a needle of dots
cx0, cy0, R = 520, 405, 95
for a in range(200, 341, 4):
    th = math.radians(a); s.rect(int(cx0 + R * math.cos(th)) - 1, int(cy0 + R * math.sin(th)) - 1, 3, 3, 121, 1)
for a in range(200, 341, 20):
    th = math.radians(a)
    for rr in range(R - 14, R - 3, 2): s.rect(int(cx0 + rr * math.cos(th)) - 1, int(cy0 + rr * math.sin(th)) - 1, 3, 3, 123, 1)
th = math.radians(255)
for rr in range(0, R - 18, 3): s.rect(int(cx0 + rr * math.cos(th)) - 2, int(cy0 + rr * math.sin(th)) - 2, 4, 4, 122, 1)
s.rect(cx0 - 6, cy0 - 6, 13, 13, 121, 1)
# own text with the camera font (layer 2)
s.text(90, 52, 390, 88, 'Own colours, own', colour=2)
s.text(90, 88, 390, 124, 'shapes, own text', colour=2)
s.text(102, 256, 340, 290, 'Histogram', colour=2)
s.text(412, 50, 640, 84, 'Tone curve', colour=2)
s.end().update(0).tok('wait:300', 'shot:hud.png')
recs, bad, err = s.run()
print('ok' if not bad else bad[:3]); print(err[-600:])
