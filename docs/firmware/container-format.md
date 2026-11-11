# Firmware container (.BIN)

## Blocks
- Back-to-back blocks: `0x20-byte plain header | obfuscated payload | 0x20-byte plain trailer`. [code]
- Header = 8 × u32 LE: magic, 0, address, payload size, version, type, id, checksum (0 in the header). Trailer = the
  header again with the checksum in its last word. [code]
- **Checksum:** the trailer's last word makes the u32-LE sum of header + **decoded** payload + trailer ≡ 0 mod 2^32. [code]
- **Obfuscation, not encryption:** invert every byte, then a fixed shuffle in each 16-byte group:
  `P = {0:[2,0,3,1], 4:[1,3,0,2], 8:[3,2,1,0], 12:[2,0,1,3]}`, `enc[base+j] = ~plain[base+P[base][j]]`. No key. [code]
- Block 2 nested sub-blocks use the same header format but aren't obfuscated again; only E-M5 sub-block 0x452e0000
  has its own checksum (`olyfw.py repack` fixes it). [code]
- The camera accepted every repacked image, including same-version ones. [camera]

## Model magics
| body | file | magic | blocks |
|---|---|---|---|
| E-M5 III 1.7 | OLY_E_137_1700 | `OE 13 70` | 5 |
| E-M1 III 1.4 / 1.6 | OLY_E_139_1400/1600 | `OE 13 90` | 6 (block 5 at 0x08000000) |
| OM-5 1.2 | OLY_E_144_1200 | `OE 14 40` | 5 |
| OM-5 II 1.1 | OLY_E_148_1100 | `OE 14 80` | 5 |
| PEN-F 3.1 | OLY_E_122_3101 | `OE 12 20` | 4 |
| OM-1 1.9 | OLY_E_143_1900 | `OE 14 30` | 6 (block 5 = sub-CPU fw) |
| OM-1 II 1.3 | OLY_E_146_1300 | `OE 14 60` (last block carries OM-1 magic) | 6 |
[code] `olyfw.py` checks the E-M5 magic; `olyfw_any.py` reads it from the file; `olyfw_multi.py` takes it per block (OM-1 II).

## E-M5 III 1.7 layout
| # | file offset | header addr | payload | type | contents |
|---|---|---|---|---|---|
| 0 | 0x0000000 | 0x40780000 | 0x17dffc0 | 0x100 | **main MN103 program** (code, strings, menus) |
| 1 | 0x17e0000 | 0x42160000 | 0x1dfffc0 | 0x101 | GUI resources; entries 1-34 = languages (8 = English); ~6.7 MB zero tail |
| 2 | 0x35e0000 | 0x43f60000 | 0x31fffc0 | 0x106 | 13 sub-blocks: image-engine resources (bank 6 = 0x8007 jobs), `MODE_*` key table 0x45e20000, ARM image 0x45ef4000, a 2.3 MB sub at 0x45b20000 (unidentified) |
| 3 | 0x67e0000 | 0x00000000 | 0x3ffc0 | 0x10e | small loader / debug monitor (body-specific) |
| 4 | 0x6820000 | 0x47180000 | 0x8fffc0 | 0x102 | high-entropy data (JPEG sample images in other bodies) |
[code]

## LZ4 (`olycompress`) sections
- E-M1 III and OM-5/OM-5 II block0 hold two `olycompress` sections: 16-byte tag, u32 compressed size, u32
  decompressed size, 8 zero bytes, LZ4 **block** data. Each expands **in place at the same VMA**. Load table at VMA
  0x60028000. E-M5 III, PEN-F, OM-1 have none. [code]
- OM-5 1.2: 0x60847000 (→0x477800), 0x60cbe800 (→0x685000). E-M1 III: 0x60803000, 0x60c6c000. [code]
- **Always analyse donors on the expanded image**. The early "50% match"
  numbers came from unexpanded images. [code]

Tools: tools page. Sources:,.
