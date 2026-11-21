#!/usr/bin/env python3
"""Dump the DMP EGL/OpenVG eglGetProcAddress table from an Olympus MN103 block0 image.

usage: python3 -I c3d_proctable.py BLOCK0.bin [BASE] [--xref CALLS.txt]

BLOCK0.bin  block0 as loaded (E-M5 III: the unpacked block0; compressed bodies: the expanded RAM image)
BASE        VMA of file offset 0 (default 0x60021020)
--xref      optional "addr: target,..." call list (from objdump: lines with call/calls) to count callers;
            direct `call` sites enter after the movm prologue, so targets func..func+8 are counted.

Prints one line per entry: table address, function address, name. The table is 8-byte records
{char *name, void *func}; egl* names first, then vg*/vgu*/DMP names after a short gap.
"""
import re, struct, sys, collections

def main():
    argv = sys.argv[1:]
    xf = None
    if '--xref' in argv:
        i = argv.index('--xref'); xf = argv[i + 1]; del argv[i:i + 2]
    a = argv
    if not a:
        sys.exit(__doc__)
    d = open(a[0], 'rb').read()
    base = int(a[1], 16) if len(a) > 1 else 0x60021020
    xref = None
    if xf:
        xref = collections.defaultdict(list)
        for l in open(xf):
            p = l.split()
            if len(p) == 2:
                xref[int(p[1].split(',')[0], 16)].append(int(p[0].rstrip(':'), 16))

    def name_at(va):
        i = va - base
        if not 0 <= i < len(d):
            return None
        j = d.find(b'\0', i, i + 64)
        if j < 0:
            return None
        try:
            s = d[i:j].decode('ascii')
        except UnicodeDecodeError:
            return None
        return s if re.fullmatch(r'(egl|vgu?)[A-Z]\w+', s) else None

    out = []
    for m in re.finditer(rb'(?<=\0)(eglGetError|vgGetError)\0', d):
        k = d.find(struct.pack('<I', m.start() + base))
        while k >= 0:
            o = k
            while True:
                n, f = struct.unpack('<II', d[o:o + 8])
                s = name_at(n)
                if not s:
                    break
                out.append((o + base, f, s))
                o += 8
            k = d.find(struct.pack('<I', m.start() + base), k + 1)
    if not out:
        sys.exit('no table found (wrong base or no DMP library)')
    for ta, f, s in sorted(set(out)):
        extra = ''
        if xref is not None:
            c = [x for k in range(9) for x in xref.get(f + k, [])]
            extra = f'  callers={len(c)} ' + ' '.join(hex(x) for x in sorted(c)[:8])
        print(f'{ta:#010x} {f:#010x} {s}{extra}')

if __name__ == '__main__':
    main()
