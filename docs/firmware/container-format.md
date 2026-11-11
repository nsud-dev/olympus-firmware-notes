# Firmware container (.BIN)

Olympus ships firmware updates as one `.BIN` file per camera model. This page explains how that file is put together:
the blocks inside it, the light obfuscation over each block (it is not encryption), the checksum the camera checks, and
what each block holds on the E-M5 III. It is the first thing you need to understand before patching anything.

Our tool `olyfw.py` does all of this: unpack, repack and fix checksums. See the tools page.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## Blocks

The file is a series of blocks placed back to back. Each block is: [code]

`0x20-byte plain header | obfuscated payload | 0x20-byte plain trailer`

- The header is 8 little-endian 32-bit words: magic, 0, address, payload size, version, type, id, checksum (0 in the
  header). The trailer repeats the header with the checksum filled into its last word. [code]
- **Checksum:** the trailer's last word is chosen so that the 32-bit little-endian sum of header + **decoded** payload +
  trailer is 0 (mod 2^32). [code]
- **Obfuscation, not encryption:** every byte is inverted, then the bytes in each 16-byte group are shuffled in a fixed
  pattern. There is no key. [code] In code:
  `P = {0:[2,0,3,1], 4:[1,3,0,2], 8:[3,2,1,0], 12:[2,0,1,3]}`, `enc[base+j] = ~plain[base+P[base][j]]`.
- Block 2 contains nested sub-blocks with the same header format, but they aren't obfuscated a second time. Only the
  E-M5 sub-block 0x452e0000 has its own checksum (`olyfw.py repack` fixes it). [code]
- The camera accepted every repacked image we gave it, including ones with the same version number as the installed
  firmware. [camera]

## Which camera a file is for

The first bytes of each block (the "magic") name the camera model:

| body | file | magic | blocks |
|---|---|---|---|
| E-M5 III 1.7 | OLY_E_137_1700 | `OE 13 70` | 5 |
| E-M1 III 1.4 / 1.6 | OLY_E_139_1400/1600 | `OE 13 90` | 6 (block 5 at 0x08000000) |
| OM-5 1.2 | OLY_E_144_1200 | `OE 14 40` | 5 |
| OM-5 II 1.1 | OLY_E_148_1100 | `OE 14 80` | 5 |
| PEN-F 3.1 | OLY_E_122_3101 | `OE 12 20` | 4 |
| OM-1 1.9 | OLY_E_143_1900 | `OE 14 30` | 6 (block 5 = sub-CPU firmware) |
| OM-1 II 1.3 | OLY_E_146_1300 | `OE 14 60` (the last block carries the OM-1 magic) | 6 |

[code] `olyfw.py` checks for the E-M5 magic; `olyfw_any.py` reads it from the file; `olyfw_multi.py` takes it per block
(needed for the OM-1 II).

## What is in each block (E-M5 III 1.7)

| # | file offset | header addr | payload | type | contents |
|---|---|---|---|---|---|
| 0 | 0x0000000 | 0x40780000 | 0x17dffc0 | 0x100 | **the main MN103 program** (code, strings, menus) |
| 1 | 0x17e0000 | 0x42160000 | 0x1dfffc0 | 0x101 | GUI resources; entries 1-34 are languages (8 = English); ~6.7 MB of zeros at the end |
| 2 | 0x35e0000 | 0x43f60000 | 0x31fffc0 | 0x106 | 13 sub-blocks: image-engine resources (bank 6 = 0x8007 jobs), the `MODE_*` key table 0x45e20000, the ARM image 0x45ef4000, and a 2.3 MB sub-block at 0x45b20000 (unidentified) |
| 3 | 0x67e0000 | 0x00000000 | 0x3ffc0 | 0x10e | small loader / debug monitor (body-specific) |
| 4 | 0x6820000 | 0x47180000 | 0x8fffc0 | 0x102 | high-entropy data (JPEG sample images in other bodies) |

[code]

## Compressed sections (`olycompress`, LZ4)

Some newer bodies compress parts of their main program. The E-M1 III, OM-5 and OM-5 II block0 each hold two
`olycompress` sections: a 16-byte tag, u32 compressed size, u32 decompressed size, 8 zero bytes, then LZ4 **block** data.
Each one expands **in place at the same address**, driven by a load table at 0x60028000. The E-M5 III, PEN-F and OM-1
have none. [code]

- OM-5 1.2: 0x60847000 (expands to 0x477800 bytes), 0x60cbe800 (to 0x685000). E-M1 III: 0x60803000, 0x60c6c000. [code]
- **Always analyse a donor body on the expanded image**. Our early "50%
  match" numbers came from unexpanded images. [code]

