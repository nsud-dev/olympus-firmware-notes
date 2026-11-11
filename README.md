# Olympus firmware research notes (E-M5 Mark III)

Notes and tools from reverse-engineering the firmware of the Olympus OM-D E-M5 Mark III (firmware 1.7), with
comparisons to related bodies (OM-5, OM-5 II, E-M1 III, OM-1, PEN-F). The aim is right to repair and keeping an older
camera useful: understanding how it works, and how features from newer bodies on the same platform could run on it.

**This repository contains no firmware.** No firmware images, decoded blocks, disassembly or decompiled vendor code,
and no patched builds. Everything here is our own description of how the firmware and hardware behave, plus our own
tools. To follow along you need your own copy of the stock firmware from the manufacturer.

Not affiliated with or endorsed by OM Digital Solutions or Olympus. Modifying camera firmware can brick the camera and
void its warranty; nothing here is a ready-made patch, and you use any of it at your own risk.

## Contents

| folder | what |
|---|---|
| [docs/](docs/README.md) | how the firmware, SoC and hardware work: container format, boot and section loading, recovery, CPU, memory map, image engine, ARM co-processor, display, USB, stabiliser, sequencer, settings and menus, patching techniques, feature studies |
| tools/ | `olyfw.py` (unpack / repack / checksum for E-M5 III `.BIN` containers), `ptpinfo.py` (PTP GetDeviceInfo probe) |
| [ghidra-mn103](https://github.com/nsud-dev/ghidra-mn103) (separate repo) | Ghidra processor module for Panasonic MN103 / AM33 / AM33-2 with decompiler support, call-frame handling, its generator and validation suite |

## Conventions in the notes
- Confidence tags: **[camera]** observed on a real E-M5 III, **[code]** read in the firmware, **[inferred]** follows
  from evidence but not traced or tested.
- Addresses are MN103 block0 virtual addresses in **E-M5 III firmware 1.7** (load base `0x60021020`) unless another body
  is named. File offset in the decoded block0 = address − 0x60021020.
- References to "private notes" point to working notes that are not published.

## Licences
- Documentation (`docs/`): CC BY 4.0.
- `tools/`: MIT.
- The Ghidra module lives in its own repo, [ghidra-mn103](https://github.com/nsud-dev/ghidra-mn103), under GPL-3.0-or-later.

## Related public work
- fishcu/oly_fw_analysis: multi-body research notebook (PEN-F in depth), MN103 emulator harness.
- cakelesscoder/caduceus-ep7: firmware patches for the PEN E-P7.
