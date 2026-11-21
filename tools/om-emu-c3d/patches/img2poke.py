#!/usr/bin/env python3
"""Write an om-emu session script that pokes a 32-bit RGBA picture into the E-M5 III's IMG2 layer and shoots it.

The layer is the one the camera's c3d engine draws into: 256 x 256 at (432, 112) of the rear screen, buffer A at
0xa4423ec0, 4 bytes a pixel: byte 0 alpha (0 transparent .. 255 opaque, straight), then B, G, R. Stock firmware enables
it when the Color Creator editor opens, so the script opens that editor with INFO after the pokes (om-emu recomposes the
screen only when the GUI updates it, so poke before the INFO press, or press a key after poking).

usage: img2poke.py PICTURE.raw OUT.script [SHOT.png]
  PICTURE.raw: 262144 bytes in the layer's format (a dump of the camera's c3d draw buffer works)
  then: node emu/bin/session.mjs --model E137 --out DIR --script OUT.script   (with patches/0001 applied)
"""
import sys

BUF_A, SIZE = 0xa4423ec0, 256 * 256 * 4
OPEN = ['ok', 'right', 'right', 'right', 'ok'] + ['right'] * 7 + ['wait:1000']   # SCP > Picture Mode > Color Creator


def main(a):
    if len(a) not in (2, 3):
        sys.exit(__doc__)
    d = open(a[0], 'rb').read()
    if len(d) != SIZE:
        sys.exit(f'{a[0]}: {len(d)} bytes, want {SIZE}')
    out = list(OPEN)
    out += [f'write:0x{BUF_A + o:x}={d[o:o + 4096].hex()}' for o in range(0, SIZE, 4096)]
    out += ['info', 'wait:2000', f'shot:{a[2] if len(a) == 3 else "img2.png"}']
    open(a[1], 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
