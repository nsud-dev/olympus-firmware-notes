#!/usr/bin/env python3
"""Olympus E-M5 Mark III (OLY_E_137_*.BIN) firmware unpack / repack.

Container: a sequence of blocks. Each block is
    0x20-byte plain header | payload (obfuscated) | 0x20-byte plain trailer
The trailer is a copy of the header whose last u32 is a checksum chosen so the
u32 little-endian sum of (header + decoded payload + trailer) == 0 mod 2^32.

Payload obfuscation: every byte is inverted (~b), and the bytes inside each
16-byte group (aligned to the block start) are shuffled with a fixed table.

Header (8 x u32 LE): magic 'OE\\x13\\x70', 0, address, payload_size,
version, type, id, checksum (0 in the header copy).

Usage:
    olyfw.py info   FW.BIN
    olyfw.py unpack FW.BIN OUTDIR     # writes blockN_<addr>.bin (decoded) + layout.json
    olyfw.py repack OUTDIR NEW.BIN    # re-encodes, recomputes checksums
"""
import json, os, struct, sys
import numpy as np

MAGIC = b'OE\x13\x70'
HDR = 0x20
# within each 16-byte group: enc[base + j] = ~plain[base + P[base][j]]
P = {0: [2, 0, 3, 1], 4: [1, 3, 0, 2], 8: [3, 2, 1, 0], 12: [2, 0, 1, 3]}


def _check16(n):
    if n % 16:
        raise ValueError('payload length must be a multiple of 16')


def decode(buf):
    _check16(len(buf))
    b = (~np.frombuffer(buf, np.uint8)).reshape(-1, 16)
    out = np.empty_like(b)
    for base, p in P.items:
        for j in range(4):
            out[:, base + p[j]] = b[:, base + j]
    return out.tobytes


def encode(buf):
    _check16(len(buf))
    b = np.frombuffer(buf, np.uint8).reshape(-1, 16)
    out = np.empty_like(b)
    for base, p in P.items:
        for j in range(4):
            out[:, base + j] = b[:, base + p[j]]
    return (~out).tobytes


def sum32(buf):
    return int(np.frombuffer(buf, '<u4').astype(np.uint64).sum) & 0xffffffff


def fix_checksum(hdr, plain_payload, trl):
    """Return trailer with its last word set so the block sums to zero."""
    s = sum32(hdr + plain_payload + trl[:-4])
    return trl[:-4] + struct.pack('<I', (-s) & 0xffffffff)


def parse_hdr(h):
    f = struct.unpack('<8I', h)
    return dict(addr=f[2], size=f[3], version=f[4], type=f[5], id=f[6], checksum=f[7])


def blocks(fw):
    off = 0
    while off < len(fw):
        h = fw[off:off + HDR]
        if h[:4] != MAGIC:
            raise ValueError(f'no block header at {off:#x}')
        info = parse_hdr(h)
        end = off + HDR + info['size'] + HDR
        yield off, end, info
        off = end


def cmd_info(path):
    fw = open(path, 'rb').read
    for i, (a, b, h) in enumerate(blocks(fw)):
        trl = fw[b - HDR:b]
        plain = decode(fw[a + HDR:b - HDR])
        ok = sum32(fw[a:a + HDR] + plain + trl) == 0
        print(f'block{i}: file {a:#09x}-{b:#09x} addr {h["addr"]:#010x} size {h["size"]:#x} '
              f'ver {h["version"]:#x} type {h["type"]:#x} checksum {parse_hdr(trl)["checksum"]:#010x} '
              f'{"OK" if ok else "BAD"}')
        # nested blocks inside the decoded payload
        j = plain.find(MAGIC)
        while j != -1 and j + HDR <= len(plain):
            sub = parse_hdr(plain[j:j + HDR])
            k = j + HDR + sub['size']
            if k + HDR > len(plain) or plain[k:k + 4] != MAGIC:
                break
            st = sum32(plain[j:k + HDR]) == 0
            cs = parse_hdr(plain[k:k + HDR])['checksum']
            print(f'    sub @payload+{j:#x}: addr {sub["addr"]:#010x} size {sub["size"]:#x} '
                  f'type {sub["type"]:#x} id {sub["id"]:#x} checksum {cs:#010x} '
                  f'{"sum-OK" if st else ("no-checksum" if cs == 0 else "BAD")}')
            j = plain.find(MAGIC, k + HDR)


def cmd_unpack(path, outdir):
    fw = open(path, 'rb').read
    os.makedirs(outdir, exist_ok=True)
    layout = []
    for i, (a, b, h) in enumerate(blocks(fw)):
        name = f'block{i}_{h["addr"]:08x}.bin'
        open(os.path.join(outdir, name), 'wb').write(decode(fw[a + HDR:b - HDR]))
        layout.append(dict(file=name, header=fw[a:a + HDR].hex, trailer=fw[b - HDR:b].hex, **h))
    json.dump(layout, open(os.path.join(outdir, 'layout.json'), 'w'), indent=1)
    print(f'wrote {len(layout)} blocks to {outdir}')


def cmd_repack(outdir, path):
    layout = json.load(open(os.path.join(outdir, 'layout.json')))
    out = bytearray
    for blk in layout:
        plain = open(os.path.join(outdir, blk['file']), 'rb').read
        hdr, trl = bytes.fromhex(blk['header']), bytes.fromhex(blk['trailer'])
        if len(plain) != parse_hdr(hdr)['size']:
            raise ValueError(f'{blk["file"]}: size changed; keep patches in place')
        # nested sub-blocks that carry a checksum get it recomputed too
        plain = bytearray(plain)
        j = plain.find(MAGIC)
        while j != -1:
            sub = parse_hdr(plain[j:j + HDR]); k = j + HDR + sub['size']
            if k + HDR > len(plain) or plain[k:k + 4] != MAGIC:
                break
            if parse_hdr(plain[k:k + HDR])['checksum'] != 0:
                plain[k:k + HDR] = fix_checksum(bytes(plain[j:j + HDR]), bytes(plain[j + HDR:k]), bytes(plain[k:k + HDR]))
            j = plain.find(MAGIC, k + HDR)
        plain = bytes(plain)
        out += hdr + encode(plain) + fix_checksum(hdr, plain, trl)
    open(path, 'wb').write(out)
    print(f'wrote {path} ({len(out)} bytes)')


if __name__ == '__main__':
    c = sys.argv[1:]
    {'info': lambda: cmd_info(c[1]), 'unpack': lambda: cmd_unpack(c[1], c[2]),
     'repack': lambda: cmd_repack(c[1], c[2])}[c[0]]
