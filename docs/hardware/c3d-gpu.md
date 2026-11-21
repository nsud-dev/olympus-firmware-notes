# The c3d GPU (DMP SMAPH-F, OpenVG)

The camera has a second drawing engine besides the 2D OSD engine: a small **vector GPU** from DMP (Digital Media
Professionals), core name **SMAPH-F**, driven through DMP's **OpenVG 1.1 + EGL** library. Only the colour-wheel
editors use it (Color Creator, and the Color/Mono Profile editors we added). This page goes from the GUI's request down
to the GPU's registers and back up to the screen. The overview of both engines is on
[Graphics pipeline](graphics-pipeline.md); the how-to view is the guide [Drawing to the screen](../guides/drawing-to-the-screen.md).

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.
Addresses are E-M5 III 1.7 block0 VMAs. First pass 2026-11-21; disassembly with the
project's mn10300 objdump over; the entry-point table dump is
.

## The whole path

```
 GUI screen ── BackGroundCtrl ── bridge ──► c3d_main task (mailbox 0x60041054, 49 commands)
                                               │ START / UPDATE / END / UP_POST / END_POST per draw kind
                                               ├──► c3d_exe task (mailbox 0x6004123c, 11 commands)
                                               │       EGL + OpenVG calls (renderers 0x60c26879..)
                                               │         └─► DMP client library ──► DMP_RD_MGR task ──► GPU 0x9c200000
                                               │                                       (command lists, fill, copy)
                                               │       eglSwapBuffers ──► draw buffer A or B (256x256x4)
                                               └──► display task (mailbox 0x60041034)
                                                       DISP_SET_LAYER_CUSTOM (6), DISP_UPDATE_SCREEN_IMG (18)
                                                         └─► VSC image plane IMG2 over live view, at (432,112)
```

## 1. Tasks and commands

- **Three c3d modules**, named by their debug dumps: `c3d_main` (front end), `c3d_exe` (the drawing task),
  `c3d_buff_wrapper` (the two draw buffers) plus `c3d_lib_if`, `c3d_update` and `c3d_debug`. [code]+[camera]
  2026-11-21 (`c3d dbgall`)
- **c3d_main** task loop 0x60c279d5 receives on mailbox **0x60041054**; command word 0..48 through jump table
  0x60e580b4. Commands come in groups of five per draw kind: `base+0` START, `+1` UPDATE, `+2` END, `+3` UP_POST,
  `+4` END_POST (each fifth slot is invalid). Kinds in order: PART_COLOR (0), COLOR_CREATER (5), COLOR_CREATER2 (10),
  MONOCHROME_CREATER (15), SHADING_CREATER (20), ART_FILTER (25), TOUGH_GEAR (30), SCN_TOP (35), SELECT_SHOOTING (40);
  45..48 are shared commands (46 = the "various draw" block the Color Creator keys send; 48 = draw-address request
  0x60c2823b). [code] 2026-11-21 (names at 0x60e55613..0x60e556be)
- **c3d_exe** task 0x60c25bde receives on mailbox **0x6004123c**; c3d_main forwards with 0x60c283b9(cmd, block).
  Commands (table 0x60e55ab8): **1 START** (byte 0 of the block = kind 1..9: CP, CC, CC2, MC, SC, ART, TG, ST, SS),
  **2 END**, **3..11 DRAW** for kinds 1..9 (renderers below). [code] 2026-11-21
  - START: takes a work buffer for the kind (table 0x60e55a94: 7 MB for CP/CC/MC, 6.2 MB for CC2/SC, 12 MB ART, 9 MB TG,
    10 MB ST/SS; allocator 0x603f84b8), hands it to the DMP memory manager (0x60c26155 -> 0x60c24bf5), runs EGL setup
    0x60c26187 with the surface size from the block (+12 width, +14 height), then the kind's resource setup (table
    0x60e55a70: textures, paths, paints). Answer: 0x60c273e3 posts {code 1} to mailbox [0x60041222]. [code]
  - END: frees textures/paths/paints (0x60c2676b), EGL teardown 0x60c26337, DMP memory teardown, answer {code 2},
    releases the work buffer. [code]
  - Every command whose message carries a reply mailbox gets a 12-byte answer from the loop end (0x60c25f91). This
    answer is what clears the GUI's busy word 0x61600ba0 (our notes). [code]+[camera]
- c3d's EGL/VG state lives at 0x6253c4a0: display +0, config +4, context +8, window surface +0xc, native display
  +0x10, native window +0x14, surface width/height +0x18/+0x1c (used by every `vgClear`), texture handles +0x20 (3
  slots), texture buffers +0x2c, then path/paint handles 0x6253c4d8..0x6253c4f8. [code] 2026-11-21

## 2. The OpenVG and EGL library

- Block0 holds DMP's EGL 1.4 and OpenVG 1.1 client with **147 entry points** in one `eglGetProcAddress` table at
  **0x6028c1d4**: 8-byte records `{char *name, void *func}`, 44 egl* names (0x6028c1d4..0x6028c32c), then 103 vg* /
  vgu* names (0x6028c3bc..0x6028c6ec) including the VGU utilities (vguLine, vguRect, vguRoundRect, vguEllipse, vguArc,
  vguPolygon, warp helpers) and 7 DMP calls. [code] 2026-11-21
- Calling convention gotcha: the table holds each function's `movm` entry (for `calls`). Direct `call` sites use the
  address after the prologue, e.g. vgDrawPath 0x611bc4f3 is called as 0x611bc4f8, vgClear 0x611bc2d3 as 0x611bc2d8.
  Search for callers in the range func..func+8. [code] 2026-11-21
- **The c3d task is the only caller**: every direct call into the library comes from 0x60c2622f..0x60c277bb. [code]
- Extension strings: EGL `EGL_DMP_display_query EGL_DMP_commandbuffer_attributes EGL_DMP_colorbuffer_format_attribute
  EGL_DMPX_query_cross_error EGL_DMPX_dump_reference_colorbuffer EGL_NV_native_query`, platforms `EGL_DMP_platform_dmpnative`
  / `eglnative`; VG `VG_DMP_LA_88 VG_DMP_image_native_format(_direct_load) VG_DMP_color_buffer_dither
  VG_DMP_draw_subimage VG_DMP_multi_draw_image VG_DMP_draw_path_data VG_DMP_debug_query VG_DMP_path_native_format_direct_load
  VG_DMPX_clear_linear_gradient_vertical VG_DMPX_paint_non_affine_matrix VG_DMPX_max_cross_config`; vendor
  "Digital Media Professionals Inc.", renderer "SMAPH-F". Strings name the sources `src/egl/client/dmpdrvconf.c`,
  `dmpdevconf.c`, `src/vg_client_rmif.c`, `src/rm_swap_buffers.c`. [code] 2026-11-21

Entry points c3d uses (table address = entry for `calls`; c3d's call sites in brackets): [code] 2026-11-21

| call | address | c3d sites |
|---|---|---|
| eglGetDisplay / eglInitialize / eglBindAPI(0x30a1 OpenVG) | 0x6119b381 / 0x6119b3a5 / 0x6119c902 | EGL setup 0x60c26187 |
| eglChooseConfig / eglCreateContext / eglCreateWindowSurface / eglMakeCurrent | 0x6119b882 / 0x6119d4d9 / 0x6119c2e2 / 0x6119db21 | same |
| eglSwapBuffers | 0x6119e454 | 0x60c263ab (the "submit" 0x60c2639f every renderer ends with) |
| eglDestroySurface / eglDestroyContext / eglTerminate / eglReleaseThread / eglGetError | 0x6119c732 / 0x6119d87e / 0x6119b461 / 0x6119cb0c / 0x6119b35c | teardown 0x60c26337, error log |
| vgSeti / vgSetf / vgSetfv / vgSetParameteri / vgSetParameterfv | 0x611bbb10 / 0x611bbaf4 / 0x611bbb2c / 0x611bbcb8 / 0x611bbd7f | 16 / 1 / 5 / 1 / 1 |
| vgLoadIdentity / vgTranslate / vgScale / vgRotate / vgGetMatrix | 0x611bba32 / 0x611bba8e / 0x611bbaa8 / 0x611bbadc / 0x611bba5e | 7 / 7 / 1 / 3 / 2 |
| vgClear | 0x611bc2d3 | 5 (one per renderer) |
| vgCreatePath / vgAppendPathData / vgModifyPathCoords / vgTransformPath / vgPointAlongPath / vgClearPath / vgDestroyPath | 0x611bc304 / 0x611bc3d0 / 0x611bc3f5 / 0x611bc416 / 0x611bc476 / 0x611bc332 / 0x611bc34e | 8 / 6 / 3 / 1 / 1 / 1 / 4 |
| vgDrawPath | 0x611bc4f3 | 0x60c26aaf, 0x60c26f7c, 0x60c27370 |
| vgCreatePaint / vgSetPaint / vgDestroyPaint | 0x611bc53e / 0x611bc584 / 0x611bc555 | 8 / 3 / 5 |
| vgCreateImageDataDMP / vgDrawSubImageDMP / vgDestroyImage | 0x611bcfcb / 0x611bce25 / 0x611bc636 | texture load 0x60c2751a / sprite draw 0x60c27697, 0x60c276f9 / free |

Never called by stock code but present and callable: vgDrawImage, vgImageSubData, vgWritePixels, vgCopyImage,
vgGaussianBlur, vgConvolve, vgColorMatrix, vgLookup, masks, fonts/glyphs, vgu shapes, vgMultiDrawImageDMP,
vgDrawPathDataDMP. [code]

- **EGL setup values** (0x60c26187): config attributes 0x60e56c2c `{EGL_CONFIG_ID 0x3028, 2}`; native window
  attributes 0x60e56c38 `{0x8000, 0x8002}`; context attributes 0x60e56c44 = the DMP command-buffer sizes
  `{0x3ff7: 0x40000, 0x3ff8: 0x40000, 0x3ff9: 0x20000, 0x3ffa: 0x20000}` (two 256 KB and two 128 KB buffers). The native
  display/window come from Olympus' platform layer (0x611c025b, 0x611c0aa0). [code] 2026-11-21

## 3. The GPU and its registers

- **Register base 0x9c200000**, stored at 0x6241bb00 by the render-manager init 0x611c60fc; accessors read
  0x611c63eb(off) / write 0x611c63f6(off, value). All GPU register traffic goes through these two. [code] 2026-11-21
- The render manager is its own task, **DMP_RD_MGR** (entry 0x611c6090, priority 55, 2 KB stack), created by c3d_exe's
  init with flag `FLG_DMP_RM` and ten semaphores `SEM_DMP_RM`; it takes requests (12 types, 0x611c6401) and logs them as
  `[kick VG]`, `[kick PSC] dst=`, `[kick PPF] src= dst=`, and interrupts as `[int VG]`, `[int PPF]`, `[int PSC]`. [code]
- Register map, as written by the driver [code] 2026-11-21:

| offset | unit | use |
|---|---|---|
| +0x10 / +0x14 / +0x18 / +0x1c | **PSC** memory fill | start, end, value, control (0x0f100201 / 0x0f100211 start; 0 = clear) (0x611c6203) |
| +0xe0 / +0xe4 / +0xe8 / +0xec | PSC, second set | written by the same request when its mode word is set |
| +0x34 | status | cleared at init |
| +0x58 | status | bit 26 polled while waiting for the VG core (0x611c6391) |
| +0xc00 / +0xc04 | **PPF** copy engine | source / destination address |
| +0xc08 / +0xc0c | PPF | output / input size (h << 16 \| w) |
| +0xc10 | PPF | flags (bit 3 = plain copy using +0xc20..+0xc28) |
| +0xc18 | PPF | 1 = start; 0 = acknowledge |
| +0xc1c | PPF | 0x8000 at init |
| +0xc20 / +0xc24 / +0xc28 | PPF | copy size / source and destination line gaps |
| +0x1020 | VG core | interrupt acknowledge (0) |
| +0x10d0 / +0x10d4 / +0x10dc | **VG command list 0** | kick (1) / address / size in 8-byte units (request words / 2) |
| +0x10e0 / +0x10e4 / +0x10ec | VG command list 1 | kick / address / size |
| +0x1214 | VG core | 0xffff or 0x100ffff before a list; 0x1000000 while waiting |
| +0x1248 / +0x1298 | VG core | 1 at init / 0 before each list |

- The external units' names (PSC fill, PPF transfer) and the PPF register order match DMP's PICA200 as documented by
  the Nintendo 3DS homebrew community; the VG core's own registers (+0x1000 up) do not. So treat the 3DS documents as a
  hint for PSC/PPF only. [inferred] 2026-11-21
- Command-list contents (the VG core's opcode format) are built inside the client library (`vg_client_rmif.c`) and
  have not been decoded. [open]

## 4. Surfaces, buffers and pixel formats

- The EGL window surface is the c3d draw area; `c3d_buff_wrapper` keeps **two draw buffers** (Color Creator: A
  0xA4423EC0, B 0xA45792C0, 0x40000 B each) and flips between them (`g_ucDrawBuffFlg`); `c3d_lib_if` holds the
  current one with **format 7**. [camera] 2026-11-19 (`c3d dbgall`)
- Draw-buffer pixel bytes: byte 0 alpha, bytes 1-3 colour (decoded as B, G, R), straight 256 × 256, no padding.
  [camera] 2026-11-19
- Textures (atlas sheets) are created with `vgCreateImageDataDMP(0x401, w, h, data, size, 7)` (0x611bcfd0 call in the sheet
  loader 0x60c27449): the bytes are handed over in the GPU's own layout (`VG_DMP_image_native_format`), so sheet bytes
  are copied, not converted. [code] (2026-11-19)
- Sprites are drawn with `vgDrawSubImageDMP` from those sheets; rect tables per atlas in block0. [code]

## 5. How the layer reaches the screen

- `c3d_main` picks a **layer geometry** per kind and device (0x60c282bc: 24-byte record from **0x60e57198** + mode × 240,
  or by display setting for kind 9) into `g_stLayerInfo` 0x621db65c: source w/h, line jump, target w/h, target x/y,
  format, buffer size. Color Creator on the rear screen: 256 × 256, line 256, at (432, 112), **format 4**, 0x40000 B.
  [code]+[camera] 2026-11-21
- `c3d_exe_bridge_disp_init` 0x60c255c3 sends the display task (mailbox **0x60041034**) **command 17
  DISP_UPDATE_SCREEN_OSD**, **18 DISP_UPDATE_SCREEN_IMG** (40-byte record 0x621db538: device mask, image slots, format 4)
  and **6 DISP_SET_LAYER_CUSTOM** (80-byte record 0x621db570 with the geometry). The per-frame flip 0x60c257c1 sends
  command 18 again with the new buffer. Device mask from the device kind (0x60c258d1: masks 1, 2, 4, 8, 16, 32; 1 = TFT, 2 = EVF as in the display task). [code] 2026-11-21
- DISP_SET_LAYER_CUSTOM's per-channel handler 0x60190ad9 programs image plane 0 from record +8 and plane 1 from
  record +12; c3d fills only +12 (pointer 0x621db5c0), so **the c3d layer is VSC plane IMG2**, over live view (IMG1)
  and under the OSD planes. VSC plane calls: 0x60044226 / 0x600445ba / 0x6004486d / 0x600449c2 (channel, plane 0..2).
  [code] 2026-11-21. The OM-3 uses IMG2 too (om-emu). ~~Which VSC format register value "format 4" becomes is [open].~~
  It becomes IMGPLANE2 = 0x301100 (VSC format 3, per-pixel alpha), registers in [graphics pipeline](graphics-pipeline.md) 6a. [emu] 2026-11-21
- Display task command names (handler table 0x601e7fe0, cmd - 2, dispatch 0x6017fad2; logged as `[DISP] <COM> :...`): 4
  SET_CPDATA, 6 SET_LAYER_CUSTOM, 8 SET_QUALITY, 9/21/25 SET_HI_SH, 10/46 SET_EG_PK, 13-16 HISTOGRAM_SET/START/STOP/
  CALC_END, 17 UPDATE_SCREEN_OSD, 18 UPDATE_SCREEN_IMG, 28 SET_LAYER_CUSTOM_VSYNC, 30 SET_AUTO_DIMMER, 32 FPS_CHANGE,
  33-36 the `_SUB` variants. [code] 2026-11-21
- Before a layer appears, the GUI's background type must keep the planes on (our notes: kinds 5/6 switched O1-O3
  off; type 0 keeps them). See UI drawing lessons. [camera]

## 6. Debug hooks already in the firmware

- User shell `c3d dbginfo` / `c3d dbgall` print every module's state and the command history. [camera]
- `c3d test <n> <0|1|2|Y|m>` (c3d_debug.c 0x60c24e76): `<n>` is parsed into 0x621db534 (also `g_ulDeviceKind`);
  0/1/2 post a 16-byte message with word 3 = n to c3d_main / c3d_exe / the reply mailbox; `Y` writes 4 MB from address
  n to the card as `vg.out`; `m` runs 0x60c24dcf. So the shell can send c3d commands without a build. [code] 2026-11-21;
  exact argument order [inferred], and the shell cuts lines at 31 characters.

## 7. Can we draw our own?

Yes in principle, with no new driver work: c3d already brings up EGL, an OpenVG context, a 256 × 256 surface and the IMG2
layer for any kind it starts, and every stock renderer is a plain sequence of OpenVG calls ending in eglSwapBuffers.
Unused kind slots exist: the E-M5 III's TG renderer 0x60c27096 is a print-and-return stub, as CC2/MC/SC were before the
looks port. [code]+[inferred] 2026-11-21

First plan [inferred]:
1. Use a stub kind (TG, or a new kind beside the profile editors) and put our own renderer in it: `vgClear`, build one
   path with `vgAppendPathData` (or `vguRoundRect` / `vguEllipse`), one solid paint (`vgSetParameteri` type colour,
   `vgSetParameterfv` colour, `vgSetPaint`), `vgDrawPath` fill and stroke, then the stock submit 0x60c2639f.
2. Start it exactly as the camera-proven profile editors do: the screen's kind (kind table 0x61101974 via
   `chgBackGround` 0x60e1d57c), `OlyApiBackGroundCtrl` start 0x6083e6c6 / end 0x6083e342, a background type that keeps
   O1-O3 on, a big enough work buffer (table 0x60e55a94), and per-key updates through BackGroundCtrl cmd 5 -> 0x607f384a
   -> bridge 0x602fccc9 (c3d_main command 46). Or post START/UPDATE to c3d_main from the shell with `c3d test` for a
   first look. [camera] (our notes; UI drawing lessons)
3. Check with `file memdump` of the draw buffer (our notes recipe) before worrying about the screen.
Geometry rows per mode (table 0x60e57198, {src w, src h, line, dst w, dst h, x, y, format}): 0 CP 192² at (500,144);
1 CC, 2 CC2, 3 MC 256² at (432,112); 4 SC 80 × 352 at (613,64); 5 ART, 7 ST, 8 SS 720 × 480 full screen; 6 TG
480 × 480 shown 638 × 480 at (160,0) (the VSC scales it). All format 4. [code] 2026-11-21

**"Draw a circle" example, smallest stub: kind 7 TOUGH_GEAR (TG)** [inferred] 2026-11-21. Its c3d_exe draw case
(command 9) is the stub 0x60c27096; its START case (0x60c26746) only loads sheet row 6; c3d_main commands are 30 START,
31 UPDATE, 32 END; work buffer 9 MB. Renderer: `vgClear(0, 0, w, h)`; `p = vgCreatePath(0, 3 (float), 1.0, 0.0, 0, 0,
all caps)`; `vguEllipse(p, cx, cy, d, d)`; `paint = vgCreatePaint`; `vgSetParameteri(paint, 0x1a00 type, 0x1b00
colour)`; `vgSetParameterfv(paint, 0x1a01 colour, 4, rgba)`; `vgSetPaint(paint, 2 fill)`; `vgDrawPath(p, 2 fill)` (VG_STROKE_PATH = 1, VG_FILL_PATH = 2);
then submit (`call 0x60c2639f` from asm, or eglSwapBuffers from C, section 11). No GUI screen starts TG, so borrow the profile editors' start path or the shell `c3d test`
route; its 480 × 480 surface is stretched to 638 wide on the rear screen.

Transparency comes free (per-pixel alpha); animation = an UPDATE per frame (each goes through one flip; rate not measured).

### 7b. Two ways to drive it (2026-11-21)

There are two ways to use this: everything the Olympus driver offers, or the vector library driven directly. Note
that the E-M5 III has **no OpenGL ES** driver: its GPU library is OpenVG + EGL only (the PEN-F carries OpenGL ES 1.1).
[code]

**How tied the DMP library is to c3d** [code] 2026-11-21. The library calls back into c3d glue, so it is not a free-standing driver:
- memory: every allocation goes to 0x60c24c3c(type, size). Type 0x8000 (an EGL window colour buffer) returns c3d's two
  draw buffers in turn (0xa25c2b00 / 0xa25c2b04, counter 0xa25c2b08; set by 0x60c24cd0 at c3d_main START); every other
  type comes from the DMP heap (0x60c24c20 -> 0x611beb7b) that START built over the work buffer (0x60c24bf5: first
  512 KB reserved, the rest heap via 0x611bea11). The callback tables (0x60e55408 / 0x60e5542c) treat all 9 kinds alike;
  outside a kind (0x6253c478 = 0) a window buffer would come from the heap and never reach the screen. [code]
- completion: the platform layer reports through 0x60c27828 (codes 0..6 -> 4..10, posted by 0x60c273e3); render-manager
  task priorities through 0x60c27898; a context pointer through 0x60c2788f. [code]
- platform init is reference-counted (0x611c01ec / 0x611c0222, count 0x61ec7c50); the native display is 0
  (0x611c025b); the native window is created by 0x611c0aa0(display, width, attributes {0x8000, 0x8002}). [code]

**Route 1, the Olympus driver** [inferred]: use c3d as it is. Pick a kind, size its work buffer, load sheets, and write a
renderer that uses any of the 147 calls (paths, vgu shapes, paints, gradients, images, sprites, masks, blur, colour
matrix). c3d does EGL setup, the layer, flips and answers. This is what the profile editors do on the camera.

**Route 2, drive OpenVG yourself** [inferred]: because of the glue above, the practical way is a **"script kind"**: a
renderer in a stub kind (TG) that reads a small command buffer posted with each UPDATE (records `{op, args}` for clear,
path from segments + coords, paint colour or gradient, matrix, draw path, draw image rect) and makes the matching
OpenVG calls, then the submit. Callers can then draw anything without writing MN103 renderers, and the same buffer
format can feed the om-emu stand-in. Running EGL from our own task beside c3d is not recommended: the memory and
window-buffer callbacks key off c3d's current kind and buffers, and c3d's START/END create and destroy the display.

**Route 3, the GPU directly** [open]: build VG command lists ourselves and kick them at +0x10d0. Needs the opcode
format; not decoded.

## 8. Other bodies

Same library position and table where named; checked by the table scan of
on each block0 (expanded images for compressed bodies). [code] 2026-11-21

| body | VG core | proc table (vgDrawPath entry) | vgDrawPath | c3d kinds present |
|---|---|---|---|---|
| E-M5 III 1.7 | SMAPH-F | 0x6028c54c | 0x611bc4f3 | all 9 |
| E-M1 III 1.6 | SMAPH-F | 0x6028ed50 | 0x613884f3 | all 9 |
| OM-5 1.2 | SMAPH-F | 0x60293d50 | 0x613dacf3 | 5 (no CC, CC2, MC, SC) |
| OM-5 II 1.1 | SMAPH-F | 0x60293d50 | 0x613dacf3 | 5 |
| OM-1 1.9 | "K3000", VG 1.1 | 0x603986a0 | 0x617a0910 | all 9 |
| OM-1 II 1.3 | "K3000" | 0x603986a0 | 0x617aa910 | 5 |
| PEN-F 3.1 | "SMAPH-H VG" 1.1 plus "SMAPHA-H" OpenGL ES-CM 1.1 | no egl/vg name table | — | older c3d |

The OM-1 family's `VG_DMP_image_standard_format_direct_load` replaces `native_format`, so texture bytes may differ there.
The PEN-F also carries an OpenGL ES 1.1 driver. [code]
- **E-M5 II 4.1 / PEN-F 3.1:** the same DMP OpenVG set (`vgCreateImageDataDMP`, `vgDrawPathDataDMP`, `c3d_exe_bridge_disp_init`). **E-M5 (Mark I) 2.3:** a GPU (`play_gpu.c`, `c3d_dbg`) but no OpenVG names. [code] 2026-11-21, see [older bodies](../bodies/comparison.md#older-bodies-e-m5-ii-and-e-m5-mark-i-2026-11-21)


## 4b. Objects: contexts, handles, paths, paints (2026-11-21)

Read from the client library; offsets are from the object pointer. [code] 2026-11-21 unless tagged.
- **Arguments**: non-pointers take d0, d1 and pointers a0, a1; leftovers of either kind fill the other kind's free registers (sections 10, 11);
  floats travel as integer bits. With no pointer arguments that is plain d0, d1, a0, a1, e.g. `vgCreatePath(format d0, datatype d1, scale a0, bias a1, segHint, coordHint, caps on the stack)`. [code]
- **Current context:** each API wrapper first calls 0x611bb962 (our notes state -> current VG context). Context +28 =
  shared VG state S; S+40 = path pool (object pool at +12), S+44 = paint pool (at +4); **S+128 = fill paint, S+132 =
  stroke paint** (set by vgSetPaint 0x611a2110). Errors: 0x611bb8f8(ctx, VG error code). [code]
- **Handles:** pool id in bits 16..24, generation in bits 28..31; `0x611b9a52(pool, handle)` returns the object or 0.
  New objects come from `0x611b97d8(pool, 0, &handle)`. [code]
- **Path** [code] (create 0x611b2723): +8 handle, +16 format (must be 0, standard), +20 datatype (0..3 = S8/S16/S32/F),
  +24 scale, +28 bias (floats), +32 segment hint, +36 coord hint, +40 capabilities & 0xfff, +68 **coordinate buffer**,
  +92 **segment buffer**, +116 0. A buffer is {+0 memory block, +4 used count, +12 capacity, +16 data pointer, +20 second
  pointer} (grow 0x611b2573). Segments are the standard OpenVG command bytes and coordinates are kept in the path's own
  datatype (size per datatype from table 0x611d374c), as passed to vgAppendPathData (0x611b2c36 checks bit 1 =
  APPEND_TO, validates each byte & 0x1e <= 24, sums coords per segment from table 0x611d375c). So an emulator can read
  a path straight from these two buffers at vgDrawPath time.
- **Paint** (144 B, init 0x611a1f9c): +0 reference count, +4 handle, **+8 type** (0x1b00 colour by default), **+12
  packed colour** (red in bits 0-7 ... alpha in bits 24-31; default 0xff000000 = opaque black), **+16..+28 colour as
  four floats R, G, B, A** (vgSetColor 0x611a21f3 writes both forms; vgSetParameterfv colour writes the floats),
  +112 0x1c00 (ramp spread pad), +76 0x1d00 (pattern tiling), +96 premultiplied ramp 1, +40/+64 1.0; gradient and
  pattern fields +68..+108 not traced. [code]; meaning of the non-colour defaults [inferred] from the OpenVG enums.
- **Matrices:** S+256 = `VG_MATRIX_MODE` (0x1400 path, 0x1401 image, 0x1402 fill, 0x1403 stroke, 0x1404 glyph); the five
  3 × 3 float matrices sit at **S+708 + (mode & 15) × 36** (path S+708, image S+744, fill S+780, stroke S+816), stored in
  `vgLoadMatrix` order {sx, shy, w0, shx, sy, w1, tx, ty, w2} (vgLoadIdentity 0x611be4b6, vgTranslate builds
  {1,0,0, 0,1,0, tx,ty,1} and multiplies 0x611be663). c3d switches with `vgSeti(0x1100, 0x1401)` before sprites. [code]
- **Images:** pool S+36 (objects at +12). `vgCreateImageDataDMP(format d0, width d1, data a0, height a1, data size,
  allowed quality)` (internal 0x611ae6de) checks the size is exactly w × h × bpp / 8 (format 12: w × h / 2), max
  8192 × 8192, and creates the object (0x611a77af) then loads the data (0x611a789a). c3d's sheets use format **0x401**
  (bit 10 = DMP native layout of format 1, sRGBA_8888) and quality 7. Image object: +12 allowed quality, +28 VG format,
  +32 internal format code (0x611a770f), +36 from 0x611a7688, +44 parent (self for a root image), +52 data handle,
  **+56 / +58 width / height**, +60 / +62 allocated width / height, **+72 stride** (allocated width × bpp / 8), +78 bits
  per pixel, +88 filter, +92 / +112 storage records. [code] 2026-11-21; meaning of +32/+36/+92/+112 [inferred]
- **Sprites:** `vgDrawSubImageDMP(image d0, x d1, y a0, w a1, h stack)` (0x611bce25 -> 0x611ab1a6) checks the rect lies
  inside the image and draws it through the image matrix (S+744). c3d's helper 0x60c276a1 does LoadIdentity, Translate,
  Scale, then draws rect {x, y, w, h} (u16s from the sprite table) from atlas handle 0x6253c4c0[atlas]. [code] 2026-11-21
- **Sheet loading** (0x60c27449, our notes [code]): per atlas, buffer from the c3d heap (size + 1024), pixels by the
  resource reader 0x60167060, then `vgCreateImageDataDMP(0x401, w, h, data, size, 7)`; handle to 0x6253c4c0[atlas],
  buffer to 0x6253c4cc[atlas]. Whether the library copies the pixels or keeps the buffer is [open] (c3d keeps the buffer
  until END, which suggests it may be referenced).

## 9. The Olympus driver, kind by kind (2026-11-21)

Everything a c3d draw kind is made of, from the E-M5 III 1.7 tables. Use this to read a stock kind or to add one.
[code] 2026-11-21 unless tagged.

| # | kind | surface (START) | layer on rear screen | work buffer | sheets (atlas: size) | sprite list | UPDATE block | renderer (c3d_exe cmd) |
|---|---|---|---|---|---|---|---|---|
| 1 | PART_COLOR (CP) | 192 × 192 | 192² at (500,144) | 7 MB | 0: 512 × 512 | 19 sprites, atlas 0 | 4 B (hue) | 0x60c26879 (3) |
| 2 | COLOR_CREATER (CC) | 256 × 256 | 256² at (432,112) | 7 MB | 0: 512 × 512 | 4 sprites, atlas 0 | 4 B | 0x60c2698d (4) |
| 3 | COLOR_CREATER2 (CC2) | 256 × 256 | 256² at (432,112) | 6.2 MB | none | none | 13 B | stub 0x60c26bdb (5) |
| 4 | MONOCHROME_CREATER (MC) | 256 × 256 | 256² at (432,112) | 7 MB | none | none | 2 B | stub 0x60c26beb (6) |
| 5 | SHADING_CREATER (SC) | 80 × 352 | 80 × 352 at (613,64) | 6.2 MB | none | none | 1 B | stub 0x60c26bfb (7) |
| 6 | ART_FILTER (ART) | 720 × 480 | full screen | 12 MB | 1: 1024 × 1024 | 189 sprites, atlas 1 | 36 B | 0x60c26c0b (8) |
| 7 | TOUGH_GEAR (TG) | 480 × 480 | 638 × 480 at (160,0) | 9 MB (pool 3) | none | none | 4 B | stub 0x60c27096 (9) |
| 8 | SCN_TOP (ST) | 720 × 480 | full screen | 10 MB | 2: 1024 × 512 | 2 sprites, atlas 2 | 4 B | 0x60c270a6 (10) |
| 9 | SELECT_SHOOTING (SS) | 720 × 480 | full screen | 10 MB | 2: 1024 × 512 | 46 sprites, atlas 2 | 30 B | 0x60c2717a (11) |

Where each column lives:
- **c3d_main START** (commands 0, 5, 10 ... or 45 with the kind in byte 0 of the block): waits until no kind is active
  (state word 0xa25c2be0 = 0), records kind, surface size and reply mailbox (0x60c2841f), installs the **two draw-buffer
  addresses the caller passes** (block +4 -> 0x60c24cd0 -> 0xa25c2b00/04), then sends c3d_exe START. Surface sizes are
  constants in the START cases (0x60c27f73..0x60c27fd6). [code]
- **c3d_main UPDATE** (1, 6, 11 ...): only when the state word equals that kind; copies the caller's block (sizes above) to
  0xa25c2b6c..0xa25c2bac and sends c3d_exe the draw command. **UP_POST** (3, 8 ...) / 48 store the drawn buffer address
  (0x621db674) and answer the caller with it; **END** (2, 7 ...) sends c3d_exe END and clears the state word. [code]
- **Layer geometry**: table 0x60e57198, 240 B per mode (section 5). **Work buffer**: table 0x60e55a94 (section 1). [code]
- **Sheets**: loader rows 0x60e56be4 (8 B {ptr, count} per mode -> {u16 atlas, u16 w, u16 h} records), byte size per atlas
  0x60e55af4 (atlas 0 1 MB, 1 4 MB, 2 2 MB), loaded by 0x60c27449 from block 2 group 5. [code]
- **Sprites**: type table 0x60e56b58 (8 B {ptr, u16 count} per kind) -> records {u32 sprite id, u16 rect, u16 atlas};
  atlas rect tables 0x60e56320 (8 B {ptr, count} per atlas) -> rects {u16 x, y, w, h}. Lookup 0x60c275cb(kind, id, out)
  refuses ids >= 261. Drawing: `0x60c2764e(kind, id, x, y)` = LoadIdentity, Translate(x, y), vgDrawSubImageDMP;
  `0x60c276a1(kind, id, x, y, scale)` adds Scale(scale, 1.0). [code]
- **Paints**: `0x60c275a0(paint, r, g, b, a)` sets type colour (0x1a00 = 0x1b00) and colour (0x1a01) floats. [code]
- **START resources** (c3d_exe START, table 0x60e55a70): CC and CC2 build two paths and two or three colour paints, MC
  one path and two paints (handles in 0x6253c4d8..0x6253c4f8), ART and SS build one more path (0x60c27766: a 5-segment
  path with float coords); all then load their sheet row. [code]
- **What the stock renderers call**, in order (useful as templates) [code]:
  - CP [code]: clear colour (vgSetfv 0x1121), vgClear, matrix mode image, sprite, rotate by the hue around the centre, sprite
    (the hue marker), submit.
  - CC: as CP, plus a path whose coordinates are rewritten each frame (vgModifyPathCoords), vgSetPaint + vgDrawPath for the
    arc, vgTransformPath / vgPointAlongPath to place the cursor on it, sprites, submit.
  - ART: up to 9 icon sprites scaled per layout, a rotating wheel sprite, one drawn path (the selection band), submit.
  - ST: clear, two sprites (cursor), submit. SS: sprites for icons, one drawn path, more sprites, submit.

### Adding your own drawing on the Olympus driver [inferred] 2026-11-21

Built on the camera-proven profile editors (our notes), which did exactly this for CC2 and MC:
1. **Pick a stub kind**: CC2, MC, SC or TG (the editors use CC2/MC; TG is free). Point its c3d_exe draw stub at your
   renderer (`call renderer; ret`, 10 bytes, as the editors do).
2. **Surface and layer** come with the kind (table above); change the geometry row (0x60e57198) only if you need another
   size or position.
3. **Memory**: make sure the work buffer (0x60e55a94) covers your sheets and paths; the editors needed 10-12 MB.
4. **Artwork** (optional): add a sheet row (0x60e56be4), an atlas size (0x60e55af4), a sprite list (0x60e56b58) and atlas
   rects (0x60e56320); raise the id limit at 0x60c275de; put the sheet in block 2 group 5. Paths and paints need none.
5. **Renderer**: clear, draw with any OpenVG calls (section 2), end with the submit (eglSwapBuffers, section 11). Data comes in the kind's
   UPDATE block (a0 = the copied block).
6. **Start it from the GUI**: screen kind table 0x61101974 via `chgBackGround` 0x60e1d57c, `OlyApiBackGroundCtrl` start
   0x6083e6c6 / end 0x6083e342, background type that keeps O1-O3 on, per-key updates through BackGroundCtrl cmd 5 ->
   0x607f384a -> bridge 0x602fccc9 (UI drawing lessons). [camera]
7. **Check**: `c3d dbgall` (state, history) and `file memdump` of the draw buffer before worrying about the screen. [camera]

## 10. Running it in om-emu: facts found (2026-11-21)

- **Arguments (Olympus ABI):** [code] integers fill d0 and d1. Pointers take a0 and a1 first, and integers then fill the
  a registers that are left. Examples: `vgSetParameteri(obj, type, value)` puts value in a0;
  `vgSetParameterfv(obj, type, count, values)` puts values in a0 and count in a1; `vgModifyPathCoords` puts its data
  pointer in a0 and the segment count in a1. Stack arguments start at the caller's (4,sp) (0x60c27511, 0x60c274cb).
  So `vgPointAlongPath(path, start, x*, y*, numSegs, distance, tx*, ty*)` has x* in a0 and y* in a1.
  [emu]
- **Native image layout (format 0x401):** [code]
  - 4 bytes per texel: A, B, G, R.
  - 8×8 tiles, in rows of tiles. Inside a tile, Morton (Z) order, x bit first.
  - The first tile row is VG y 0 (the bottom), so the sheets are stored bottom-up.
  - Verified on E-M5 III atlas 0. [code]+[emu]
- **Block2 offsets:** group-table addresses are flash addresses. In the unpacked block2 body (32-byte OE head
  stripped), flash address A is at file offset A − 0x43f60000 − 32. Group 5's own OE head sits at 0x45320000. Its
  entries {flash address, size} follow: atlas 0 at 0x45320800 (1 MB), atlas 1 at 0x45420800 (4 MB), atlas 2 at
  0x45820800 (2 MB). [code]
- **Resource reader 0x60167060:** arguments are (category d0, entry d1, dest a0, 0 in a1, size on the stack). It
  returns in a0 a {pointer, size} record. [code]
- **CPU split:** [code] c3d_exe (queue 0x100f) and c3d_sub (queue 0x1002) are CPU-1 tasks; c3d_main (queue 158) is on CPU 0.
  c3d_exe's init creates the DMP driver task (entry 0x611c6090). [emu]
- **c3d_sub** (entry 0x60c28732): command 1 is init, command 2 does nothing, and command 3 is the GPU's frame-done.
  When c3d_exe's draw flag 0x6253c479 is set, command 3 posts command 48 to c3d_main. Command 48 sends c3d_main's
  deferred answer to the GUI's request (command 46 is saved at 0x621db678). [code]+[emu]
- **Calls per Color Creator frame:** about 53 (clear, wheel sprite, inner-circle stroke, rotate, TransformPath,
  8 × PointAlongPath, 9 dot and handle sprites, swap). [emu]
- **Two entries per library function** [code]+[emu] 2026-11-21: the proc-table address is the `calls` entry: it runs
  the function's own prologue (`movm` and/or `add -n,sp`). Stock code uses `call` to the address just after that
  prologue, because `call label,[regs],n` does that work itself. So both ways work for library functions. A stock
  helper that has no prologue can only be entered with `call`. Example: the submit 0x60c2639f (`call ..,[],4`).
  Entered with `calls`, its `ret [],4` takes the return address from the caller's (4,sp). This crashed the first TG
  example in om-emu; it now uses eglSwapBuffers through 0x6119e454.
  private notes (prologue, ret)
- **Own renderer verified in om-emu** [emu] 2026-11-21: the TG example (PR #36 .o, loaded by
  `om-emu/c3d/elfload.mjs`, `TG_OBJ=`) draws its panel, dot and arc. Every argument arrives in the expected register,
  vguRoundRect/Ellipse/Arc included (path d0, x d1, y a0, w a1, the rest from (4,sp)), and the UPDATE angle reaches
  vgRotate. Not verified: the screen position (the GUI still opens Color Creator's layer).

- **The real library runs in om-emu** [emu] 2026-11-21: with the stand-in off (`C3D_NATIVE=1`) and 0x611c5fed hooked
  to dump both lists and return 0 (no DMP_RD_MGR task, no busy bit or interrupt), the stock library ran 4 Color Creator
  frames without waiting on the GPU. Captures: private notes (+0x10dc holds the size in 8-byte units, see section 12b).
- **ART's band is fixed at 80 px** [code] 2026-11-21: the renderer's only path (0x60c26ee3..0x60c26f7c) is
  (0,0)-(0,80)-(W,80)-(W,0), black at 50 %, under the thumbnails. Photos of the camera's normal shooting screen and ART
  select [camera] 2026-11-21: the 80-px thumbnail band matches; live view keeps its full width and is not
  scaled; it stops at the top of the thumbnail band (about y 400), and the thumbnails sit on black. The darker strip
  under the "Soft Focus" title is the bottom ~50 px of live view (y ~350-400), dimmed. (An earlier note here said live
  view shrank to ~672 x 400; that misread a photo.) The emulator has no live-view pipeline and its IMG1 area stays
  720 x 480, so neither shows there. Which unit cuts and dims live view is [open].

## 11. Driving the library yourself (2026-11-21)

The second route of section 7b: your own renderer calls OpenVG directly instead of the stock sprite helpers.
[code] 2026-11-21 unless tagged.

- **Where you may call it**: only inside a c3d renderer, which c3d_exe calls with a0 = the copied UPDATE block after
  setting the draw flag 0x6253c479. c3d_exe owns the EGL display (0x6253c4a0), the window surface (0x6253c4ac) and the
  current VG context; the GUI task has none. [code]
- **End of frame**: the stock submit 0x60c2639f is `eglSwapBuffers(*0x6253c4a0, *0x6253c4ac)` (0x6119e454). Call it
  last, so the frame-done path of section 10 answers the GUI. [code] From C call eglSwapBuffers itself
  (`c3d_submit` in the header): 0x60c2639f has no prologue and must be entered by `call`; through a pointer (`calls`)
  its `ret [],4` returns to a stack word (crash seen in om-emu). [code] (om-emu run 2026-11-21)
- **Paint modes**: VG_STROKE_PATH = 1, VG_FILL_PATH = 2 (stock ART fills with 2 at 0x60c26f6b). vgSet state such as
  the stroke width carries over between frames, so set it every frame. [code]
- **Objects per frame or kept**: paths and paints made in a renderer can be destroyed at the end of the frame (the
  example does this). To keep them between frames, make them on the first frame and drop the handles when the kind ends:
  c3d_exe END frees the context's pools. [inferred]
- **Example**: `example_tg_renderer.c` (same folder) draws a half-transparent rounded panel, a circle that moves with UPDATE
  byte 0 and a stroked arc on the free TG kind, with vguRoundRect, vguEllipse, vguArc, colour paints and vgDrawPath.
  Wiring: point the TG draw stub 0x60c27096 at it (section 9 how-to, step 1). Compiles clean (no AM33-only opcodes, no soft-float calls). **Runs in om-emu** (2026-11-21, our notes): arguments arrive as expected for every call including vguRoundRect/Ellipse/Arc, and the UPDATE
  angle reaches vgRotate; two bugs found there were fixed (PR #36). Screen position and camera not yet checked.
  [inferred]
- **Still unread** [code]: arguments of vgDrawSubImagesDMP, vgMultiDrawImageDMP, vgDrawPathDataDMP,
  vgDrawPathDataArraysDMP, vgCreatePathDataDMP and the egl*DMP / *NV queries (no stock caller).

## 12. Raw command lists: what is known so far (2026-11-21)

Route 3 (section 7b): build the VG core's command lists ourselves. Work in progress; opcodes not decoded yet. [code] 2026-11-21
unless tagged.

- **Submission path**: the client library posts requests to DMP_RD_MGR with 0x611c5fed(count, requests): d0 is the
  **number of requests** (1 in every capture), a0 the array. 0x611c65e0 copies each into a 20-slot queue of 112-byte
  slots (0x6241bb28), so the caller's copy may live on the stack; when the queue is full it waits (0x611c70c1) and
  retries. Request {+0 flags, +4 type, +40 payload}; types 1, 8 and 10 are VG list kicks (table 0x611d3b6c -> 0x611c6437), 3 is a PSC
  fill, 4 a PPF copy, 7 a wait/flush. The VG kick request is built by 0x611a131c (type 1, 8 or 10 from caller flags) and
  its payload filled by 0x611a633b: {list 0 address, list 0 words, list 1 address, list 1 words}. RD_MGR 0x611c6179
  writes them to +0x10d4 / +0x10dc (words / 2, so 8-byte units) / +0x10d0 = 1 and +0x10e4 / +0x10ec / +0x10e0. [code]
- **Two lists per submit**: each VG context owns a command-buffer object at context +944 (100 B, made by 0x611a6244)
  holding two rings (at +0 and +44), each {+0 size in words, +4 base address, +8 word pointer, +12 limit, +16 last
  end, +20 write index (words), +24 start index, +28 minimum free, +36/+37 flags, +40 pending link}. Sizes come from
  the context's +60..+80. [code]
- **List format so far**: 32-bit words, padded to an even number of words (8-byte steps). Each list ends with the pair
  **0x00081004, 1**, written by 0x611a63bb, plus a zero pad word when needed; a ring wrap writes a link pair
  {(index << 2) | 3, base address}. [code] The pair form {header, value} and a header with a low 16-bit register id
  (0x1004) look like a register-write stream, as on DMP's PICA200; this is not yet confirmed. [inferred]
- **Captured lists** (our notes, real DMP library on Color Creator's first frame, 2026-11-21:
; decoder). 20 type-1 submits for
  one frame. [code]
- **Header format** [code]: `id << 16 | byte mask << 12 | (count - 1) << 3 | 4 | consecutive << 1`, then `count` data
  words. Commands are packed with no padding; only the list end is padded to 8 bytes. Consecutive set = the words go to id, id+1, ... (the 3x3 matrix,
  0x0041f046 = 9 words); clear = all words go to one id (the 256-entry table, 0x0188f7fc). The end pair 0x00081004, 1
  is a write of 1 to register 0x008 with byte mask 1. A word with bit 2 clear where a header is due starts an **inline
  packet** of that many words (itself included), seen right after the start write (0x006 = 1): small path data, e.g.
  `00000009 07090702 ...` = segment bytes 02 07 09 07 (MOVE_TO, HLINE_REL, VLINE_REL, HLINE_REL) then coordinates.
  With this rule every word of the 4-frame Color Creator capture parses. [code]
- **Registers seen**, meaning from values only [inferred]:

| id | values seen | likely meaning |
|---|---|---|
| 0x002 / 0x004 | 0xa48468c0 / 0xa4846900; for a path 0xa48e7900 / 0xa48e7940 | addresses: image source, or a path's segment / coordinate data in GPU memory |
| 0x003, 0x063 | 0x10000002 (image), 0x10000012 (path in memory), 5 (inline path) | draw mode |
| 0x005 | 0xd0000004, 0xd000004e, 0x80000005 | format word; low bits = coordinate count for an inline path (5) |
| 0x006 | 1 | start the primitive; a raw packet follows |
| 0x040 | 0x04000400 (256 px surface), 0x07800780 (480 px); 0x01e001e0 with antialiasing off | **coverage width in samples**: surface width x 4 with antialiasing, x 1 without (probe, below) |
| 0x041 (+8) | 3x3 float matrix, written 2-3 times per draw | transform stack: identity, then translate (128,128), (124,124) for the Color Creator arc |
| 0x05e / 0x05f | 1.0f / 0 | scale / bias |
| 0x065 | 0x2100 fill, 0x2000 stroke, 0x0100 fill without antialiasing; byte 2 0x01 round cap, 0x10 round join | **draw flags**: bit 8 fill (clear = stroke), bit 13 antialiasing, bits 16-17 cap, bits 20-21 join (probe) |
| 0x080 (+4) | 0xe0000000 / 0xe0008000, 0, 0x00f80008 (0x00e00020 without AA), coverage width, 0 | coverage set-up; bit 15 of word 0 alternates draw to draw (ping-pong buffer) |
| 0x085 | 0xffff, 0x10001, 0x10002 | draw sequence tag |
| 0x1a3 | 0x01000100 (CC), 0x01e001e0 (TG) | **surface size** h << 16 \| w |
| 0x140, 0x184, 0x186, 0x187, 0x190, 0x1a2, 0x1c0 | 0, 0x07000000 | output stage set-up (second list) |
| 0x188 | 256 rising values 0..0xff, concave | output colour table, looks like a gamma (linear to sRGB) curve |

- **When lists are sent**: the draws of a frame are queued and submitted at eglSwapBuffers (TG example: one list
  pair per frame, after the swap); vgClear goes separately as a fill request (0x611a151d, constants 0x3fde/0x3094). [code]
- **Image draws**: the 14 short lists (0x004, 0x005, 0x002, 0x003, then a matrix) come after the sheet image calls
  and repeat the same source and identity matrix, so they may be image set-up rather than the sprite draws. [inferred]
- **Two lists per frame = two stages** [code]: list 0 is the **geometry stage** (per draw: tag 0x085, matrices 0x041,
  path or image source, mode, start 0x006); list 1 is the **pixel stage** (per draw: destination 0x1a4, paint colour
  0x185, rectangle 0x0a0, tag 0x0a6 matching 0x085), set-up and the 0x188 table first, and the end pair last. Draw N in
  list 0 and draw N in list 1 carry the same tag (0x10001, 0x10002, ...). From the TG example capture (3 draws a frame).
- **Path data in GPU memory** [code] (TG example: vguRoundRect, vguEllipse, vguArc, 2026-11-21):
  - [code] 0x002 = **segment buffer**: one byte per segment, standard OpenVG segment codes as the path holds them (relative
    codes stay relative: vguRect gives `02 07 09 07 00`), with arcs turned into cubics: round rect = `02 06 0c 0c 0c 08 0c 0c 0c 06 0c 0c 0c 08 0c 0c 0c 00` (MOVE, HLINE, 3 CUBIC, VLINE, ...,
    CLOSE). 0x003 = 0x10000000 | segment count (0x12 = 18).
  - [code] 0x004 = **coordinate buffer** (segment buffer + 0x40): float32 x, y pairs in path user space, e.g. the round rect
    starts (56, 40), (424, ...). 0x005 = 0xd0000000 | coordinate count (0x4e = 78 = 2 + 4 + 12 cubics x 6).
  - [code] The ellipse is MOVE + 6 CUBIC + CLOSE (0x10000008), the 90-degree arc MOVE + 3 CUBIC (0x10000004), starting at
    (106.07, -106.07) = 150 at -45 degrees.
  - [code] Coordinates stay in user space; the transform is the 0x041 matrix. Rotating by 30 degrees changes only the matrix
    (first element 0x3f5db3d7 = cos 30), not the path data.
  - Small paths may be sent inline instead: mode 5 and an inline packet after the start (Color Creator).
- **Paint and stroke** [code]: 0x185 = paint colour as ABGR8888 (panel 0x80000000 = black at 50 %, dot 0xff0099ff =
  (1.0, 0.6, 0), arc 0xe6ffffff = white at 90 %). Stroked draws add 0x05a (4 words: 0, 0, 4.0 = half the line width,
  15.49) and use 0x065 = 0x2000 instead of 0x2100 for fills. [code]
- **Register probe** [code] 2026-11-21 (private notes: 13 draws of one square, one OpenVG setting changed
  per draw, diffed against the first):

| setting changed | registers that changed |
|---|---|
| paint alpha 0.5 | 0x185 colour 0xff0000ff -> 0x800000ff (ABGR) |
| blend SRC / MULTIPLY | 0x1a0 byte 2 = blend mode - 0x2000 (SRC_OVER 1, SRC 0, MULTIPLY 5); 0x1a5 = 0 for SRC (blending off); 0x0a0 word 5 bit 8 set |
| antialiasing off | 0x065 bit 13 cleared; 0x040 and 0x080 coverage width / 4 (so antialiasing is 4 samples across); 0x0a0 word 5 bit 1 cleared |
| stroke, width w | 0x065 bit 8 cleared; 0x05a = {0, 0, w/2 (+0.0005), about miter limit x w/2} (w 2: 1.0, 3.875; w 6: 3.0, 11.62) |
| round cap / round join | 0x065 bits 16-17 = 1 / bits 20-21 = 1 |
| miter limit 10 | 0x05a word 3: 11.62 -> 29.85 |
| scissor rectangle (0, 0, 120, 120) | pixel list adds 0x0c0 = {0x00770000, 0x00770000} (max 119 << 16 \| min 0, for x and y) and 0x100 = 1 |
| translate (10, 20) | 0x041 words 6-7 = 10.0, 20.0 (the matrix is stored as OpenVG's m[0..8]) |
| fill rule even-odd | nothing (a convex square needs no rule) |

  The scissor enable itself was not tested (our probe set the wrong parameter number), so 0x100 may follow the rectangles
  rather than VG_SCISSORING. [inferred]
- **A hand-made list matches the library's** [code] 2026-11-21: private notes writes
  a list pair that fills one rectangle, from a captured frame as template. Against the library's own lists for the
  same shape (vguRect(140, 140, 200, 200), green fill;) the pixel list is identical word for
  word, and the geometry list differs only in the path buffer addresses and the path encoding (4 absolute LINE_TOs
  against vguRect's relative HLINE/VLINE). om-emu has no GPU model, so whether the GPU draws it is a camera test.

### 12b. Building and kicking a list yourself [inferred] 2026-11-21

1. **Memory**: put the two lists and the path buffers in GPU-visible memory the library is not using (the c3d work
   buffer, section 9). Segment bytes at P, float coordinates at P + 0x40.
2. **Geometry list**: copy a captured frame's set-up (tag 0x085 = 0xffff, identity matrices, scale/bias 0x05e, stride
   0x040 twice), then per draw: 0x063 = segment count, matrix 0x041, 0x004 = P + 0x40, 0x005 = 0xd0000000 | coordinate
   count, 0x002 = P, 0x003 = 0x10000000 | segment count, 0x065 = 0x2100 (fill) or 0x2000 + 0x05a (stroke), 0x066,
   0x080 rectangle, 0x006 = 1, then 0x085 = 0x10000 + draw number. Pad the list to an even word count.
3. **Pixel list**: the captured set-up (0x140 ... 0x188 table, 0x1a3 = surface size), then per draw the captured block
   with 0x1a4 = destination surface, 0x185 = colour ABGR8888, 0x0a6 = the draw's tag, 0x1a6 = 1; end with 0x008 = 1.
4. **Kick**: post one request {+0 flags, +4 type 1, +40 {list0, words0, list1, words1}} with 0x611c5fed(1, &request)
   from the c3d_exe task while the library is idle (between frames), or write +0x10d4/+0x10dc (words / 2) and
   +0x10e4/+0x10ec, then +0x10d0 = 1, from code that owns the GPU (the render manager is the only writer in stock).
   The other request fields (+8 ... +36, filled by 0x611a12d0) are best copied from a captured request.
5. **Check on the camera**: draw into the TG surface and read it back with `file memdump` before showing it (section 9
   step 7). Not yet run.

## Open questions
- VG command-list opcode format, and how `vg_client_rmif.c` builds lists. [open]
- ~~VGPath / VGPaint object layouts~~ section 4b (2026-11-21), images and matrices too.
- ~~What VSC format value IMG2 gets for c3d format 4, and IMG2's register block.~~ Answered 2026-11-21 in om-emu: format 3, map in [graphics pipeline](graphics-pipeline.md) 6a.
- Flip rate: how many UPDATEs per second c3d can sustain (animation). [open]
