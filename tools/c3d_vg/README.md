# c3d_vg: call the camera's OpenVG library from C

The Olympus c3d task draws the colour wheels with a built-in DMP EGL + OpenVG 1.1 library. This folder lets your own
C code call that library by address.

| file | what it is |
|---|---|
| `c3d_vg_header.py` | makes `c3d_vg.h` from the proc-table listing printed by `../c3d_proctable.py` |
| `c3d_vg.h` | E-M5 Mark III fw 1.7: `NAME_ADDR` for all 147 table entries, and a typed inline wrapper for the 132 whose arguments are known |
| `c3d_listdecode.py` | decodes captured VG command lists (om-emu dump format) into register writes |
| `c3d_rectlist.py` | writes a hand-made list pair that fills one rectangle, using a captured frame as the template |
| `example_tg_renderer.c` | an own renderer for the free Tough Gear draw kind: translucent panel, a circle and an arc turned by the UPDATE angle |
| `aperture_tg_renderer.c` | a richer one: six translucent cubic-curve blades, 60 ticks, counter-turning arcs, an orbiting dot; repeats made with the matrix, so no float arithmetic |

```
python3 -I ../c3d_proctable.py block0_40780000.bin > table.txt
python3 -I c3d_vg_header.py table.txt > c3d_vg.h
mn10300-elf-gcc -O2 -Wall -c example_tg_renderer.c  # Olympus-ABI GCC, plain MN10300: no warnings
```

Rules (notes `docs/hardware/c3d-gpu.md` sections 9 and 11):
- Call the library only from inside a c3d renderer: the c3d_exe task owns the EGL display, surface and VG context.
- End each frame with `c3d_submit` (eglSwapBuffers on c3d's display 0x6253c4a0 and surface 0x6253c4ac). The stock
  submit 0x60c2639f has no prologue: entered through a function pointer (`calls`) it returns to a garbage address.
- OpenVG paint modes: VG_STROKE_PATH = 1, VG_FILL_PATH = 2. Stroke width and other vgSet state carry over between
  frames, so set them every frame.
- No linker: avoid float arithmetic (it calls libgcc soft-float helpers) and keep static data in mind when you place the
  code (the example has one static array, `clear`, as a relocation).
- Other bodies: run both scripts on that body's block0 (or expanded RAM image) and pass the body name as the second
  argument to `c3d_vg_header.py`. The submit address differs per body.

The header holds only addresses and the standard OpenVG/EGL signatures. The example runs in om-emu (2026-11-21, after the two fixes above); it is not tested on a camera yet.

Licence: MIT (our scripts and header). The OpenVG and EGL names and signatures are from the public Khronos specifications.
