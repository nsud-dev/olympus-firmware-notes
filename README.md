# Olympus firmware notes

Notes and tools from taking apart the firmware of the Olympus OM-D E-M5 Mark III (firmware 1.7).

The E-M5 III shares a lot of hardware with newer bodies like the OM-5 and E-M1 III, but it never got some of their
features. I wanted to understand how the camera works and whether some of those features could run on it. Along the
way I've compared it with the OM-5, OM-5 II, E-M1 III, OM-1 and PEN-F.

**There's no firmware in this repo.** No firmware images, decoded blocks, disassembly, decompiled vendor code or
patched builds. It's my own write-up of how things work, plus my own tools. To follow along you'll need your own copy
of the stock firmware from OM System.

This isn't affiliated with or endorsed by OM Digital Solutions or Olympus. Modifying camera firmware can brick your
camera and will void the warranty. Nothing here is a ready-made patch, so use it at your own risk.

New here? Start with the [overview](docs/overview.md), a plain tour of everything looked at so far and where each
feature stands.

This is a spare-time project, so progress can be slow. I have family commitments, and several test builds are waiting
to be flashed and tried on the camera.

## What's here

- **[docs/](docs/README.md)**: how the firmware and hardware work. Covers the firmware container format, boot and
  section loading, recovery, the MN103 CPU, the memory map, the image engine, the ARM co-processor, the display, USB,
  the stabiliser, the shooting sequencer, settings and menus, patching techniques, and studies of individual features.
- **tools/**: `olyfw.py` unpacks and repacks E-M5 III `.BIN` files and fixes their checksums. `ptpinfo.py` asks a
  connected camera for its PTP device info.
- **Ghidra support** lives in its own repo, [ghidra-mn103](https://github.com/nsud-dev/ghidra-mn103). It's a
  processor module for the MN103 CPU that runs most of the camera.

## Reading the notes

- Claims are tagged by how sure I am. **[camera]** means I saw it on a real E-M5 III, **[code]** means I read it in
  the firmware, and **[inferred]** means the evidence points that way but I haven't traced or tested it.
- Addresses are for the MN103 side of **E-M5 III firmware 1.7**, loaded at `0x60021020`, unless a page says
  otherwise. To get a file offset in the decoded block, subtract `0x60021020`.
- Some pages mention working notes that aren't published.

## Related projects

- [fishcu/oly_fw_analysis](https://github.com/fishcu/oly_fw_analysis): research across several bodies, with the PEN-F
  in depth, and an MN103 emulator harness.
- [cakelesscoder/caduceus-ep7](https://github.com/cakelesscoder/caduceus-ep7): firmware patches for the PEN E-P7.

## AI disclosure

Much of the analysis, the tools and the writing here was done with an AI assistant (Anthropic's Claude), with me
directing it, checking the results and testing on my own camera. Anything tagged **[camera]** was tested on real
hardware. Treat **[code]** and **[inferred]** as research notes that may contain mistakes, and please open an issue if
you find one.

## Licences

- `docs/`: CC BY 4.0
- `tools/`: MIT
