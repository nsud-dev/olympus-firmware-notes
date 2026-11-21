# osdlab: drawing on the GUI layers in om-emu

Our driver for the drawing tests used for the notes page `hardware/osd-drawing.md` and the guide "Drawing your own
graphics" (2026-11-21). It turns drawing operations into om-emu session scripts (`call:@FILE` steps that run the
firmware's own draw calls natively) and takes PNG shots of the composed screen. Facts and the full call list live in
those pages; this folder is only the tooling. It contains no firmware bytes: you need your own firmware file.

## Licence and credit
- Our scripts: MIT. om-emu (the emulator these scripts drive) is by the om-emu contributors, MIT licence.
- `om-emu-shot-fresh.patch` is a one-line change to om-emu's `emu/host/session.mjs`; it is a modification of MIT-licensed
  code and carries om-emu's licence: Copyright (c) 2026 om-emu contributors, MIT (see om-emu's `LICENSE`).

## Set-up
- om-emu clone at `ccfe2e0` (MIT), node 26 (`NODE_BIN`), firmware unpacked with `node emu/bin/fetch-fw.mjs --model E137`
  (and E144/E148/E143/E146/E118/E122 for `bodies.py`).
- Apply `om-emu-shot-fresh.patch` to the clone: om-emu publishes a frame only after GUI steps or engine runs it
  traced itself, and debug `call:` steps count as neither, so `shot:` would show the old screen. With the patch and
  `OM_SHOT_FRESH=1` (osdlab sets it) a `shot:` composes the screen first.
- `OM_EMU=<clone>` if it is not at `~/emu/om-emu`.

## Files
- `osdlab.py`: `Script` (rect, line, dot, blockcopy, start/end, update, raw `call`) and `run`.
- `demos.py OUTDIR [prims palette ownpal orders anim]`: the E-M5 III tests (about 10 s each).
- `demos.py OUT pictext`: native icons with `gpiDrawBitmap` (one through an 8-bit colour remap) and our own text with `DrawText` (`Script.bitmap`, `Script.text`).
- `showcase.py OUT`: the showcase overlay (own palette ramps, see-through rounded panels, histogram bars, a tone curve, a dial, white camera-font text via an own layer-2 ramp).
- `Script.touch(kind, x, y)`: posts a touch to the GUI (TOUCH at (90, 30) lights the Wi-Fi icon box on the shooting screen).
- `bodies.py E144 E148 E143 E146 E118 E122`: the same three boxes on other bodies through their own gpi addresses. E118 (E-M5 II) and E122 (PEN-F) need a runtime image dumped from om-emu (their blocks are compressed) and draw straight into the on-screen buffer.

## Notes
- Every batch of draw calls must sit between `drawOsdStart` (0x607f6de0) and `drawOsdEnd` (0x607f6e55); outside it the
  queue refuses the request and nothing is drawn.
- Calls with a `movm` prologue (no `call` site with a frame, e.g. `GPISetPalette`) need `frame=[0, 0]` in the call file.
