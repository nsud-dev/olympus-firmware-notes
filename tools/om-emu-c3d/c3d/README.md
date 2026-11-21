# c3d in om-emu: run the camera's vector-graphics tasks

Scripts that run the E-M5 III 1.7's c3d tasks (the ones that draw the colour wheels in the Color and Monochrome Profile
editors) inside the om-emu emulator. Facts and addresses live in the notes pages `docs/hardware/c3d-gpu.md` and the guide
"Drawing with the vector GPU"; this folder is only the tooling. It contains no firmware bytes.

| file | what it is |
|---|---|
| `c3drun.mjs` | starts the c3d tasks, presses keys, writes the composed screen after each key and every frame c3d draws |
| `c3dvg.mjs` | our JavaScript stand-in for the camera's EGL/OpenVG library: paths, paints, sprite sheets, matrices, software raster |
| `elfload.mjs` | loads an unlinked mn10300 object (`.o`) into emulator memory, for your own renderer |
| `backdrop.mjs`, `backdrop.py` | a 720 x 480 picture shown in place of live view (needs patch 0003): by default a generated lake-at-dusk landscape (made by the script, no third-party licence), `--test` for the hard-edged checker scene, or your own photo |

## Licence and credit
Our scripts: MIT. om-emu, which they drive, is by the om-emu contributors, MIT licence.

## Set-up
An om-emu clone with `../patches/` applied (`sh ../patches/apply.sh CLONE`), node 22 or newer, the E-M5 III firmware
fetched in om-emu (`node emu/bin/fetch-fw.mjs --model E137`), and block2 unpacked with `tools/olyfw.py` for the sprite
sheets.

    BLOCK2=block2_43f60000.bin node c3drun.mjs CLONE/emu OUT \
      ok right right right ok right right right right right right right info right right

That opens the Color Creator and turns the wheel. Add `BACKDROP=FILE.rgb` for a stand-in live view, and `mode:N` to turn
the mode dial (2 = ART, 3 = SCN).

Two more modes (the head of `c3drun.mjs` has the details):
- `TG_OBJ=renderer.o` (entry `TG_ENTRY`, default `_tg_render`): loads your own renderer, built with
  `c3d_vg.h` from `tools/c3d_vg/`, in place of the empty Tough Gear renderer. Judge the swap files (480 x 480).
- `C3D_NATIVE=1`: the camera's own library runs instead of the stand-in. Each GPU command list it posts goes to
  `OUT/cmdlists.txt` with its path data; decode it with `tools/c3d_vg/c3d_listdecode.py`. Nothing is drawn, because
  om-emu has no GPU model.

Not modelled in the stand-in: gradient and pattern paints, dashes, caps and joins other than round, blend modes other
than source-over, masks, and image formats other than 0x401 and linear RGBA.
