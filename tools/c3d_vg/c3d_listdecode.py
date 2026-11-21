#!/usr/bin/env python3
"""Decode DMP SMAPH-F VG command lists (E-M5 III c3d GPU) into register writes.

usage: python3 -I c3d_listdecode.py DUMP.txt

DUMP.txt is the om-emu capture format (`# list N ...` headers, an `ADDR N bytes` line per list, then hex words).
Word format, read from the Color Creator capture of 2026-11-21 (notes docs/hardware/c3d-gpu.md section 12):

    header = id << 16 | byte_mask << 12 | (count - 1) << 3 | 4 | consecutive << 1

followed by `count` data words; commands are packed with no padding (only the list end is padded to 8 bytes). `consecutive` set
means the words go to id, id+1, ...; clear means all go to id (a FIFO, e.g. the 256-entry table at 0x188).
A word with bit 2 clear where a header is due (seen right after a write of 1 to 0x006) starts an inline packet of
that many words, itself included: small path data. Anything else is printed raw.
"""
import re, sys

NAMES = {  # from the om-emu captures of 2026-11-21 (notes docs/hardware/c3d-gpu.md section 12); [inferred] where marked ?
    # list 0: geometry stage
    0x002: 'path segments address (1 byte per segment)', 0x003: 'draw mode | segment count',
    0x004: 'path coordinates address (float x, y)', 0x005: 'datatype | coordinate count',
    0x006: 'start', 0x040: 'coverage width (x4 with antialiasing)', 0x041: 'matrix 3x3 (OpenVG m[0..8])',
    0x05a: 'stroke {0, 0, width/2, ~miter limit x width/2}',
    0x05e: 'scale', 0x05f: 'bias', 0x063: 'mode 2?', 0x065: 'draw flags: b8 fill, b13 antialias, b16-17 cap, b20-21 join', 0x066: '?',
    0x080: 'coverage set-up (b15 of word 0 alternates)', 0x085: 'draw tag (sequence number)',
    # list 1: pixel stage
    0x0a0: 'coverage set-up; word 5 b1 antialias, b8 non-default path?', 0x0a6: 'draw tag (matches 0x085)',
    0x0c0: 'scissor x, y (max << 16 | min)', 0x100: 'scissor on', 0x1a0: 'byte 2 = blend mode - 0x2000',
    0x1a5: 'blending on',
    0x185: 'paint colour ABGR8888', 0x188: '256-entry ramp (gamma?)', 0x1a3: 'surface size h<<16|w',
    0x1a4: 'destination surface address',
}


def decode(words):
    i, out = 0, []
    while i < len(words):
        h = words[i]
        if h == 0:
            out.append('  00000000  pad')
            i += 1
            continue
        if not h & 4 and 0 < h < 0x1000:
            pk = words[i:i + h]
            out.append(f'  {h:08x}  packet x{h}: ' + ' '.join(f'{w:08x}' for w in pk[1:]))
            i += h
            continue
        if not h & 4 or not (h >> 12) & 15:
            out.append(f'  {h:08x}  raw')
            i += 1
            continue
        rid, mask, n, cons = h >> 16, (h >> 12) & 15, ((h >> 3) & 0x1ff) + 1, (h >> 1) & 1
        data = words[i + 1:i + 1 + n]
        shown = ' '.join(f'{w:08x}' for w in data[:9]) + (' ...' if n > 9 else '')
        out.append(f'  {h:08x}  reg {rid:#05x}{"+" if cons else ""} mask {mask:x} x{n}: {shown}'
                   f'{"  (" + NAMES[rid] + ")" if rid in NAMES else ""}')
        i += 1 + n
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cur = []

    def flush():
        if cur:
            print('\n'.join(decode(cur)))
            cur.clear()

    skip = False
    for line in open(sys.argv[1]):
        if re.match(r'\s+[0-9a-f]{8}( |$)', line) and not re.search(r'bytes', line):
            if not skip:
                cur += [int(x, 16) for x in line.split()]
            continue
        flush()
        m = re.match(r'\s+(\w+) \d+ bytes', line)
        # requests built by 0x611a151d carry small constants, not a list address: not a command list
        skip = (bool(m) and int(m.group(1), 16) < 0x10000) or 'data at' in line  # memory dumps: not lists
        print(line.rstrip() + ('  (not a command list: skipped)' if skip else ''))
    flush()


if __name__ == '__main__':
    main()
