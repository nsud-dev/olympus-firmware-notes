#!/usr/bin/env python3
"""Write a hand-made VG command-list pair that fills one rectangle, from a captured frame used as a template.

usage: python3 -I c3d_rectlist.py CAPTURE.txt LIST_NO BASE X Y W H ABGR > rect.txt

CAPTURE.txt  om-emu capture (e.g. tg-example-cmdlists.txt); LIST_NO = a frame's list whose first draw is a filled
             path (TG example: list 2, the round-rect panel)
BASE         free GPU-visible memory for the path buffers (segments at BASE, coordinates at BASE + 0x40)
X Y W H      rectangle in surface coordinates (origin bottom left); ABGR = paint colour, e.g. 0xff00ff00

Keeps the template's geometry set-up and first draw (matrices, stride, mode, start) and its pixel stage set-up and
first draw, swaps in a 4-segment rectangle path and the colour, and closes the pixel list with the end pair
0x00081004, 1. Prints the two lists and the path buffer as `ADDR: words`, for an emulator to write and kick
(request {list0, words0, list1, words1} to 0x611c5fed type 1, or +0x10d4/+0x10dc/+0x10d0 directly).
Checked 2026-11-21 against the library's own lists for vguRect(140, 140, 200, 200) filled green: the pixel list is
word-for-word identical and the geometry list differs only in buffer addresses and the path encoding (the library
keeps vguRect's relative HLINE/VLINE segments, 5 coordinates; this script writes 4 absolute LINE_TOs, 8).
Format: notes docs/hardware/c3d-gpu.md section 12. om-emu has no GPU model, so check a list by comparing it with what the
library itself emits for the same shape (vguRect + vgDrawPath fill); proving it draws needs the camera. [inferred]
"""
import re, struct, sys


def load(path, no):
    """Return the two word lists of list NO, with their addresses."""
    out, cur, on = [], None, False
    for line in open(path):
        if line.startswith('# list'):
            on = int(line.split()[2]) == no
            continue
        if not on:
            continue
        m = re.match(r'\s+(\w+) \d+ bytes', line)
        if m and 'data at' not in line:
            cur = [int(m.group(1), 16), []]
            out.append(cur)
        elif 'data at' in line:
            cur = None
        elif cur is not None and re.match(r'\s+[0-9a-f]{8}', line):
            cur[1] += [int(x, 16) for x in line.split()]
    return out


def commands(words):
    """Split into (header, data) commands, packets as (word, rest)."""
    i, out = 0, []
    while i < len(words):
        h = words[i]
        if h == 0:
            i += 1
            continue
        if not h & 4:
            out.append((h, words[i + 1:i + h]))
            i += h
            continue
        n = ((h >> 3) & 0x1ff) + 1
        out.append((h, words[i + 1:i + 1 + n]))
        i += 1 + n
    return out


def first_draw(cmds, end_reg):
    """Commands up to and including the first write to end_reg (set-up plus the first draw)."""
    out = []
    for h, d in cmds:
        out.append((h, d))
        if h & 4 and h >> 16 == end_reg:
            break
    return out


def f32(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def main():
    a = sys.argv[1:]
    if len(a) < 8:
        sys.exit(__doc__)
    cap, no, base = a[0], int(a[1]), int(a[2], 0)
    x, y, w, h = (float(v) for v in a[3:7])
    colour = int(a[7], 0)
    (l0addr, l0), (l1addr, l1) = load(cap, no)[:2]

    segs = bytes([2, 4, 4, 4, 0])                      # MOVE_TO, LINE_TO x3, CLOSE (absolute)
    coords = [x, y, x + w, y, x + w, y + h, x, y + h]
    segwords = [int.from_bytes(segs[i:i + 4].ljust(4, b'\0'), 'little') for i in range(0, len(segs), 4)]
    path = segwords + [0] * (16 - len(segwords)) + [f32(c) for c in coords]

    g = first_draw(commands(l0), 0x006)
    g = [(hd, [base + 0x40] if hd >> 16 == 0x004 else [base] if hd >> 16 == 0x002 else
          [0x10000000 | len(segs)] if hd >> 16 == 0x003 else [len(segs)] if hd >> 16 == 0x063 else [0xd0000000 | len(coords)] if hd >> 16 == 0x005 else d)
         for hd, d in g]
    g.append((0x0085f004, [0x00010001]))             # the library writes the draw tag again after each draw
    p = first_draw(commands(l1), 0x1a6)
    p = [(hd, [colour] if hd >> 16 == 0x185 else d) for hd, d in p] + [(0x00081004, [1])]

    def flat(cmds):
        ws = []
        for hd, d in cmds:
            ws += [hd] + list(d)
        if len(ws) % 2:
            ws.append(0)
        return ws

    w0, w1 = flat(g), flat(p)
    for name, addr, ws in (('list0 (geometry)', l0addr, w0), ('list1 (pixel)', l1addr, w1), ('path', base, path)):
        print(f'# {name} at {addr:#x}, {len(ws)} words')
        for i in range(0, len(ws), 8):
            print(f'{addr + 4 * i:08x}: ' + ' '.join(f'{v:08x}' for v in ws[i:i + 8]))
    print(f'# request payload: {l0addr:#x} {len(w0)} {l1addr:#x} {len(w1)}  (+0x10dc = words / 2)')


if __name__ == '__main__':
    main()
