"""The om-emu drawing tests of 2026-11-21 (E-M5 III 1.7), one function each; usage: python3 demos.py OUTDIR [name...]
Names: prims, palette, ownpal, orders, anim. Each writes a session script + JSON call files and PNG shots into OUTDIR/name."""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osdlab import Script, VRAM
L2 = 0x621d9634                      # layer 2 (pool 0x0b00) VRAM records; layers 0/1 at VRAM + 16 * (4 * layer + buffer)
def vi(layer, buf=0): return L2 + 16 * buf if layer == 2 else VRAM + 16 * (4 * layer + buf)
def rect(s, x, y, w, h, c, layer, buf=0): return s.call(0x60c952fb, {'d0': x, 'd1': y, 'a1': w, 'a0': vi(layer, buf)}, [h, c, layer])

def prims(out):                      # bars, a box pair with opacity 16 / 7, a curve of dots, a block copy
    s = Script(out).tok('wait:3000').start()
    s.line(100, 80, 200, 0, 13, 1).line(100, 80, 0, 120, 13, 1).line(100, 80, 200, 120, 86, 1)
    s.rect(360, 80, 160, 120, 23, 1).rect(420, 120, 160, 120, 24, 1)
    for i in range(0, 300, 2): s.dot(100 + i, int(320 + 50 * math.sin(i / 300 * 4 * math.pi)), 85, 1)
    s.rect(450, 300, 100, 60, 81, 1).blockcopy(450, 300, 560, 300, 100, 60, 1)
    return s.end().update(0).tok('wait:200', 'shot:prims.png')

def palette(out):                    # every entry of layers 0 and 1 as a swatch + the VSC palette words
    s = Script(out).tok('wait:3000').start()
    for L, y0 in ((0, 60), (1, 270)):
        for c in range(128): s.rect(40 + (c % 32) * 20, y0 + (c // 32) * 50, 18, 45, c, L)
    return s.end().update(0).tok('wait:200', 'shot:palette.png', 'read:0x9c000800:0x1800')

def ownpal(out):                     # GPISetPalette: red ramp alpha 255..64 into layer 1 entries 120-126
    s = Script(out).tok('wait:3000')
    data = b''.join(struct.pack('<I', (a << 24) | 0xff2020) for a in (255, 224, 192, 160, 128, 96, 64))
    s.call(0x60c94f90, {'d0': 120, 'd1': 7, 'a0': 'scratch', 'a1': 'scratch+96'}, None, scratch=256, frame=[0, 0],
           mem=[['scratch+72', '=scratch+80'], ['scratch+80', struct.pack('<H', 1).hex()], ['scratch+96', data.hex()]])
    s.start()
    for i in range(7): rect(s, 60 + i * 80, 270, 75, 120, 120 + i, 1)
    return s.end().update(0).tok('wait:200', 'shot:ownpal.png')

def orders(out):                     # one box per layer, then each of the six GPISetOsdOrder codes
    s = Script(out).tok('wait:3000').start()
    rect(s, 100, 100, 250, 200, 11, 0); rect(s, 200, 150, 250, 200, 86, 1); rect(s, 300, 200, 250, 200, 5, 2)
    s.end().update(0).tok('wait:200')
    for a, b in ((0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)):
        s.call(0x60c95b1b, {'d0': a, 'd1': b}).update(0).tok('wait:200', f'shot:order{a}{b}.png', 'read:0x9c0001a4:4')
    return s

def anim(out):                       # double-buffered moving box on layer 2: draw in buffer 0/2, erase with 127, flip
    s = Script(out).tok('wait:3000'); prev = {0: None, 2: None}
    for i in range(12):
        b = 0 if i % 2 == 0 else 2
        x, y = 120 + i * 40, int(200 + 80 * math.sin(i / 11 * 2 * math.pi))
        s.start()
        if prev[b]: rect(s, *prev[b], 80, 80, 127, 2, b)
        rect(s, x, y, 80, 80, 5, 2, b)
        s.end().update(0 if b == 0 else 1).tok('wait:40', f'shot:f{i:02d}.png')
        prev[b] = (x, y)
    return s

def pictext(out):                    # native icons with gpiDrawBitmap (one remapped to entry 22) and own text with DrawText
    s = Script(out).tok('wait:4000').start()
    s.bitmap(100, 100, 0xa38927b8).bitmap(300, 100, 0xa38927b8, remap8=[22] * 256)
    s.bitmap(100, 250, 0xa30e85f8).bitmap(200, 250, 0xa3c1a48c)   # stream addresses from the picture table (om-emu run)
    s.text(60, 380, 760, 430, 'Hello from the camera font 0123', colour=5)
    return s.end().update(0).tok('wait:300', 'shot:pictext.png')

if __name__ == '__main__':
    out = sys.argv[1]; names = sys.argv[2:] or ['prims', 'palette', 'ownpal', 'orders', 'anim', 'pictext']
    for n in names:
        recs, bad, err = globals()[n](os.path.join(out, n)).run()
        print(n, 'ok' if not bad else bad[:2])
