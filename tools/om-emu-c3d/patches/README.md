# om-emu patches: the E-M5 III's 32-bit image layer

Three small changes to the om-emu emulator so it shows the picture layer the camera's vector GPU (c3d) draws into, and
a stand-in for live view under it. Used by the scripts in `../c3d/` and for the notes pages `docs/hardware/c3d-gpu.md`
and `docs/hardware/graphics-pipeline.md`. They contain no firmware bytes: you need your own firmware file.

## Licence and credit
om-emu is by the om-emu contributors, MIT licence. These patches modify MIT-licensed code and carry om-emu's licence:
Copyright (c) 2026 om-emu contributors, MIT (see om-emu's `LICENSE`). Our own scripts here (`apply.sh`,
`img2poke.py`, `vsclog.mjs`): MIT.

## Set-up
- An om-emu clone at commit `ccfe2e0`, node 22 or newer, and the E-M5 III firmware unpacked with
  `node emu/bin/fetch-fw.mjs --model E137`.
- `sh apply.sh OM_EMU_CLONE` applies the three patches in order (0003 builds on 0001).

## The patches
- `0001-kind2-img-planes.patch`: om-emu skipped every IMG plane on the E-M5 III's display controller (kind 2), so the
  layer the c3d GPU draws was never shown. It now draws IMG planes in format 3 (32-bit, per-pixel alpha) at 1:1.
  Format 0 (YC, live view) and scaled planes are still refused.
- `0002-vsc-write-log-hook.patch` + `vsclog.mjs`: logs every changed display-controller register write
  (`node --import vsclog.mjs emu/bin/session.mjs ...`, lines `VSC chN +0xOFF = 0xVAL` on stdout).
- `0003-live-view-backdrop.patch`: om-emu has no live view, so transparent layers showed over plain black. With
  `OM_BACKDROP=FILE.rgb` (720 x 480 raw RGB) the screen compositor starts from that picture. Make one with
  `python3 ../c3d/backdrop.py OUT.rgb [PHOTO | --test]` (default: a generated lake-at-dusk landscape).
- `img2poke.py`: writes a session script that pokes a 256 x 256 picture into the layer and takes a shot.

The patches are ordinary `git diff` output, written so they could be offered to om-emu as they are.
