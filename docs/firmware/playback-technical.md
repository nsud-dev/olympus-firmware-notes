# Playback and in-camera editing: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Playback and in-camera editing](playback.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the camera shows pictures and movies, and how the in-camera edits work. The edits are JPEG edit,
RAW development, rotate, protect, share and ratings. The work is desk research with no camera runs. It reads the
E-M5 III 1.7 block0 and compares it with the OM-5 II 1.1, OM-5 1.2, E-M1 III 1.6 and OM-1 1.9.[^fw1]

Printing (DPOF and PictBridge) is on its own page.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

See also: [Printing: technical notes](../features/printing-technical.md).

## Layers

Playback code sits in seven layers.[^fw1]

1. GUI viewers (`CPlaySingleFrame`, `CPlayIndex`, ...).
2. The operation layer (`OlyHfwOpePly*`, `OlyHfwOpeEdt*`).
3. 60 named components (`PLAY_INDEX`, `PLAY_EDIT_RAW`, ..., classes `CmpP*` and `CmpE*`).
4. Capability classes (`CapImg_ImagePlayer`, `CapPls_PlayState`, `CapPMov_PlayMovie`, ...).
5. The C API `api_play.c`, with API ids `0x3000c` to `0x300af` and `0x38002` to `0x3800b`.
6. The play engine (`play_*.c`), six CPU0 tasks.
7. Hardware. That is the image-processing request engine, the CIC raw codec, the c3d graphics processor (GPU) and the
   display.

Playback is large. These are the counts of functions with a playback or edit source-file name.[^fw2]

- Components: about 4,300 (play) and 3,000 (edit).
- Capability classes: about 1,400.
- The C engine: about 300.
- `api_play.c`: 147.
- Movie playback `movp_*`: 316.

| layer | E-M5 III examples | role |
|---|---|---|
| GUI viewers | `CPlaySingleFrame` (26 method strings), `CPlayIndex`, `CPlayZoom::setDbZoomInfo`, `CPlayLightBox` | draw the playback screens, info overlays, scroll bars[^fw3] |
| API objects | `OlyApiPlaySingleFrame::startFastZoom` / `zoomImageFast` / `endFastZoom`, `OlyApiPlayMovie`, `OlyApiPlaySelect` | GUI-facing calls[^fw3] |
| operations | `OlyHfwOpePlyCom`, `OpePlySfr` (single frame), `OpePlyIxp` (index), `OpePlyMov`, `OpePlySel`, `OpePlySsh` (slide show), `OpePlyCal`, `OpePlyEvw`, `OpePlyLightBox`, `OpeEdtRaw`, `OpeEdtTrm`, `OpeEdtBty`, `OpeEdtCol`, `OpeEdtSdw`, `OpeEdtRey`, `OpeEdtImgOve`, `OpeEdtMov` | one class per playback screen or edit[^fw1] |
| components | 60 names `PLAY_MODE` ... `PLAY_EDIT_RAW` (in a string table), classes `CmpPls_PlaySingleComponent` (565 functions), `CmpPli_PlayIndexComponent` (550), `Cmp_PlayComponentBase` (514), `CmpPMov` (357), `CmpPSel` (336), `CmpERaw` (332), `CmpETri` (329), `CmpPSld` (313), `CmpECol` (309), `CmpERed` (306), `CmpESha` (302), `CmpPLgh` (291), `CmpEImg` (258), `CmpERot` (238), `CmpPCal` (231), `CmpEAsp` (199), `CmpEPro` (182), `CmpERes` (137), `CmpEMov` (72) | state machines per screen and per edit[^fw1] |
| capability | `CapImg_ImagePlayer` (161 method strings: play buffers, multi-raw preview, raw-edit preview, trimming, HDMI sub display), `CapPls_PlayState` (260 functions), `CapPMov_PlayMovie`, `CapPSld_PlaySlideShow`, `CapGSld_GpuSlideShow`, `CapPlh_PlayHistogram`, `CapPlt_PlayTrimming`, `CapPPnr_PlayPanorama`, `CapPCM_PlayContinuousManager`, `CapBea_BeautyEdit`, `CapFrp_FramePlayer` | wrap the C API[^fw1] |
| C API | `api_play.c` (147 functions), `api_picfile.c`, `api_movie.c`, `api_sound.c` | build requests and send them through a send-and-wait call[^fw1] |
| engine | `play_*.c` (about 295 functions), `playbuff.c` | the tasks in [Play engine tasks](#play-engine-tasks)[^fw1] |

*The playback layers with E-M5 III examples. The address reference lists the code ranges.*

### Zoom and info displays

Zoom ("enlarge") is computed in the component and drawn from the play buffer.[^fw3]

- The component side is `CmpPls::getZoomPosSteps`, `getRotatedZoomPos`,
  `CmpPls_PlaySingleComponent::getActualMagnification` and `getEnlargeInfo`.
- The drawing side is `app_background_enlarge_touch_scroll` and `get_enlarge_preview_pic_size`.

`CmpPls::getZoomPosSteps` picks a step table from the magnification through a `CapPls_PlayState` function.[^fw6] A
band table holds `{u16 min, u16 max, u32 table}` entries, with the magnification stored × 10. Its bands are 1.0,
1.1 to 2.9, 3.0 to 4.9, 5.0 to 9.9, 10 to 14.9 and 15 to 20.0.[^fw6] A second band set is used under another display
condition, chosen by two flags. Its bands are 1.0, 1.1 to 1.5, 1.6 to 2.0, 2.1 to 14.9 and 15 to 20.0.[^fw6]

The step tables are `{step_x, step_y}` pairs. For example, one holds 1,1 / 5,5 / 7,7 / 10,10 and another holds
15,15 / 20,20 / 30,30 / 40,40.[^fw6] That they are scroll steps per band is inferred from the `step_x` / `step_y` log
string.[^inf2]

The histogram comes from `CapPlh_PlayHistogram` / `PlayCommon::getHistogram`. Light box, calendar and event view are
their own components.[^fw3]

## Play engine tasks

The play engine is six CPU0 tasks behind one router task. `PLAY_MAIN` forwards each request to the task that handles
its kind.[^fw1]

| task | id | requests it takes |
|---|---|---|
| `PLAY_MAIN` | `0x1c` | every request, routes by kind |
| `PLAY_LOAD` | `0x1b` | kind 0 (load a file), kind 5 (load from ROM: built-in pictures, BGM) |
| `PLAY_IMAGE` | `0x1a` | kind 1 draw, 2 edit, 8 movie edit, 9 GPS edit, 10 copy picture (kind 7 is routed here but not handled) |
| `PLAY_SOUND` | `0x1d` | kind 4 (voice memo play) |
| `PLAY_LOADDRAW` | `0x84` | kind 11 (load and draw: 0 full image, 1 thumbnail, 2 screen-size picture) |
| `PLAY_DECODE` | `0x83` | 0 JPEG strip decode (`play_img_decode_jpeg_division`), 1 strip draw (`play_draw_normal_division`) |

*The six play engine tasks and the request kinds each takes. Entries and queue id variables are in the address reference.[^fw1]*

All six are CPU0 tasks with priority 53 and 4 KB stacks. Boot creates them.[^fw1]

### Router

`PLAY_MAIN` reads 16-byte messages and looks them up in a 16-slot hash table.[^fw1]

- Each slot is `{u32 key, u32 handler}`. The key is **kind + 1**, because the task adds 1 before the lookup.[^fw1]
- Kind 10000 is a worker's "execute end". `PLAY_MAIN` then sends the 12-byte result to the queue named in the original
  message.[^fw7]

### Request record

The message points to a request record.[^fw1]

- The load kind is at +4 (u16).
- The edit kind is at +6 (u16).
- A file node is at +0. Its byte +88 is the file type, and types 4 and 6 are movies.

### Load kinds

`PLAY_LOAD` looks the load kind up in a table of kinds 0 to 20.[^fw1]

| kind | what is loaded | function |
|---|---|---|
| 0 | full JPEG | `play_load_prim_exec` |
| 1, 8, 16, 19 | thumbnail | `play_load_thumb_exec`, movies `play_load_movie_load_thum` |
| 2 | header | `play_load_header_exec` |
| 3, 9, 15, 18, 20 | screen-size picture | `play_load_playpic_exec`, movies `play_load_movie_load_playpic` |
| 4 | raw header check | (unnamed) |
| 6, 7 | full raw | `play_load_raw_load_prim_raw` |
| 10 | voice memo | `play_sound_load` |
| 11 | multi-picture file (MPO) | `play_load_mpo_exec` |
| 5, 12–14, 17 | invalid | |

*Load kinds in `PLAY_LOAD`'s table.[^fw1]*

### Names

Every engine function logs `<name> in` and `<name> out` through two log functions. So the strings name 213 of
them.[^fw1]

## Decoding

- **JPEG.** `play_img_decode_jpeg` takes a work buffer from an allocator and calls a request builder. That builder is
  in the same family as the record side's `rec_ImgPro_Ycc2Jpeg` builder. So decode, resize and re-encode use the
  image-processing request engine.[^fw4] See also: [Still image back end](still-backend-technical.md).
- **Strips.** Large pictures go to `PLAY_DECODE` in strips ("division"). Small ones decode in place.[^fw3]
- **Raw.** `play_load_raw_load_prim_raw` reads the Olympus raw file (ORF) and checks the header tags. These are the
  packing method, valid bits, WB data and strip offsets. It checks for tripod high-res files
  (`play_util_chk_pixshift_orf`). It then calls `play_cic_decode_raw`, which calls the CIC driver entry. CIC is the
  raw codec block on interrupt 145.[^fw1] See also: [Interrupts, timers and DMA](../hardware/interrupts-timers-dma-technical.md).
- **Movie thumbnails.** Thumbnails and the first frame come from the embedded JPEG (`play_load_movie_*`,
  `play_load_mjpeg_*`).[^fw1]
- **Drawing.** `play_draw_main_exec` (kind 1) and `play_draw_normal_*` copy, scale, rotate and frame play buffers.
  `play_gpu_draw` and `CapGSld_GpuSlideShow` use the GPU.[^fw3]

### Movie tasks

Movie playback itself runs in the `movp_*` code.[^fw1]

- `MOVP_MAIN`, `MOVP_VIDEO` and `MOVP_AUDIO` run on CPU0.
- `MOVP_ASB` runs on CPU2.
- The AVM player tasks `AVM_P1V`, `AVM_P1A`, `AVM_P2V` and `AVM_P2A` run on CPU1. They drive the H.264 unit.
- Movie edits run in `MOVE_MAIN`, `MOVE_VIDEO`, `MOVE_AUDIO`, `MOVE_TRIM`, `MOVE_FILEREAD`, `MOVE_FILEWRITE` and
  `MOVE_TIMELAPSE` (CPU0).

See also: [Movie encoder stack](movie-stack-technical.md).

## Edits

`play_edit_main` looks up the u16 edit kind in a 32-slot table of `{u32 kind, u32 label}` entries. Unknown kinds
return `0x3901`.[^fw1] The table holds 22 edit kinds, and the JPEG edits run in the engine.[^fw1]

| kind | engine function | user feature |
|---|---|---|
| 1, 2, 12 | `play_color_edit` → `play_img_make_monochrome` / `_make_sepia` / `_adjust_vivid` | Black and white, Sepia, Saturation |
| 7 | `play_trimming_edit` | Trim |
| 8 | `play_redeye_edit_main` | Red-eye fix |
| 16 | `play_apical_edit_main` | Shadow adjust |
| 128 | `play_rotate_edit_exec` | Rotate (JPEG and raw files) |
| 129 | `play_resize_main` | Resize |
| 132 | `play_pocket_main` | picture for the CUBE copy. It is set by `api_picfile.c` (API `0x70017`), called from `Cmp_PlayComponentBase::app_select_execute_prep_pic_copy_cube`.[^fw1] It makes a new picture, thumbnail and header. |
| 133 | `play_regist_regist_pic` | opening-screen picture. It writes the picture to flash (`OlyHfwOpeOpnScr::regist`, `LogoScreen::regist`, `CBC_REGIST_USER_IMAGE`, `play_rom_main_exec` "load CONST or REGIST image").[^inf3] |
| 134 / 145 | `play_multi_raw_edit` / `play_multi_raw_save` | Image overlay (preview / save) |
| 135 | `play_change_aspect_edit_main` | Aspect |
| 136 | `play_beauty_edit_main` | e-Portrait |
| 137–140, 152 | `play_cube_bt_resize`, `_resize_save`, `_set_jpeg`, `_jpeg_save`, `_jpeg_resize` | resize and copy to CUBE, a separately mounted media reached through the Bluetooth operation layer (`OlyHfwOpeBlueth::Cube Not Connect`, `cubeMountState`, `api_cube.c`). Present in all five bodies checked. |
| 143 | `play_sns_main` | Share order flag ("update snsflag") |
| 144 | `play_save` (raw mode `0x500`: `play_save_raw`) | save an edited picture |
| 146, 147, 148 | `play_edit_raw_edit` | Edit RAW (current settings, custom, ...) |
| 151 | `play_edit_raw_edit_artbkt` | ART bracketing from RAW |

*Edit kinds in the engine's edit table. The user feature column is read from the function names.[^inf3]*

### RAW development

RAW development (Edit RAW, ART bracketing from RAW) unpacks the raw with CIC. It then sends a develop request to the
record task's queue. So it runs through the same record pipeline as a new photo.[^fw1]

`play_edit_raw_edit` calls `play_rec_raw_edit`, which builds a 212-byte request.[^fw5]

- The develop type is at +72. It is `0x1001`, `0x1004`, `0x100a` or `0x1003`.
- The request carries a progress callback.
- The picture settings are read from properties `0xe2d1`, `0x44c1` and `0x9481`.

The request goes to the record task's queue. The record side (`rec.c`, `REC_MAIN`) develops it like a new photo. The
engine then writes the result as a new file (`play_file_create_file`).[^fw5]

The third argument of `play_rec_raw_edit` picks the develop type.[^fw1]

| caller | argument | develop type |
|---|---:|---|
| Edit RAW (`play_edit_raw_edit`) | 1 | **`0x1003`** |
| image overlay save (`play_multi_raw_save`), which also reads the overlay properties | 2 | **`0x1001`** |
| `play_save_raw` | 3 | **`0x1004`** |
| ART bracketing from RAW (`play_edit_raw_edit_artbkt`) | 4 | **`0x100a`** |

*Develop types by caller.[^fw1]*

On the record side, the send function posts a 16-byte message `{reply queue, -, command 16, request}` and waits on a
temporary queue.[^fw8] `REC_MAIN`'s handler reads it. It copies the request's +72 type to its context +194 and +74 to
+196.[^fw8] It then branches on the type in two places.[^fw8]

- The first compares with `0x1001`, `0x1007`, `0x100c`, `0x1011` and `0x2001` to `0x2008`.
- The second compares with `0x1002`, `0x1005`, `0x1010` and `0x1011`.

So the raw-edit types share the record mode numbers of normal shooting.[^fw8]

### Other edits

- **Movie edit** (kind 8, `play_mov_edit`) and **GPS edit** (kind 9, `play_gps_main_exec`) are separate `PLAY_IMAGE`
  kinds.[^fw1]
- GPS edit rewrites the GPS IFD of JPEG, ORF and MPO files. The `pos` module of the
  [shell commands](../features/shell-commands-technical.md) feeds it from NMEA logs.[^fw1]
- **Protect and erase** are DCF edit commands (`DCFEDIT_LOCK/UNLOCK`, `DCFEDIT_OBJ_DELETE`, `dcfedit.c`), not engine
  edits.[^fw3]
- **Share order** sets a flag in the file (`play_sns_edit_upflag`). The `olis` shell module lists the
  reservations.[^fw1]

## Clients of the engine

| caller | where | what |
|---|---|---|
| C API | `api_play.c` (voice memo API `0x3001f`, API `0x3005b`, API `0x30099`) | GUI playback through the component layers |
| Wi-Fi web server | `httpd_cgi.c` | screennail and resize for downloads |
| Wi-Fi play | `[wifi_play]` | remote playback, EXIF reads |
| GPS log tagging | `pos` | match picture times to a GPS log |

*Code outside the playback screens that calls the play engine.[^fw1]*

## OM-5 II 1.1 compared

The OM-5 II 1.1 has the same six tasks, router and edit table. It adds edit kind 154 and load kinds 21 and 22 for RAW
development driven from a PC over USB. The E-M5 III lacks this, and the E-M1 III, OM-5 and OM-1 have it.[^fw1]

| item | E-M5 III 1.7 | OM-5 II 1.1 |
|---|---|---|
| tasks (id, entry) | MAIN `0x1c` `0x612abd55`, LOAD `0x1b` `0x612bada1`, IMAGE `0x1a` `0x612b589d`, SOUND `0x1d` `0x612c1236`, DECODE `0x83` `0x612af6bb`, LOADDRAW `0x84` `0x612baccc` | MAIN `0x1d` `0x614c9153`, LOAD `0x1c` `0x614da8b3`, IMAGE `0x1b` `0x614d4fba`, SOUND `0x1e` `0x614e155b`, DECODE `0x81` `0x614ccbf3`, LOADDRAW `0x82` `0x614da7bd` |
| router | `0x613ae8b0` | `0x615dc920`, same keys |
| load kinds | 0–20 | 0–22: 21 = full raw, 22 = `play_load_raw_load_prim_raw_send_pc` `0x614dc47f` |
| edit kinds | 22 kinds, max 152 | same 22 plus **154** = `play_edit_raw_edit_send_pc` `0x614ce6fe`, unknown kind returns `0x3902` |
| engine log names | 280 | 351 (adds 71 `*_send_pc` and `play_tpc_rawedit_*` names) |
| component names | 60 | the same 60 |

*The play engine in the E-M5 III 1.7 and the OM-5 II 1.1.[^fw1]*

| feature (marker) | E-M5 III | E-M1 III | OM-5 | OM-1 | OM-5 II |
|---|---|---|---|---|---|
| RAW development from a PC over USB (`play_edit_raw_edit_send_pc`, `play_tpc_rawedit_set_param`, `LINK_PROTOCOL_RAW_EDIT`) | no | yes | yes | yes | yes |
| Ratings (`PlayCommon::setRatingValue`, `DCFEDIT_OBJ_RATING` / `_ALL_` / `_MULTI_RATING`) | no | no | no | yes | yes |
| XMP rating template (`xmp:Rating="0"`) | no | no | yes | yes | yes |
| Photo story (`CapPhs_PhotoSession.cpp`) | yes | yes | yes | no | no |
| `play_icam_*` edit (OM-1 only) | no | no | no | yes | no |

*Feature presence by body.[^fw9]*

Ratings (menus, DCF edit commands, XMP `xmp:Rating`) come from the OM-1 line.[^fw1]

The GUI and capability layers follow the OM-1. They match the OM-1's method by method.[^fw1] Method-name string counts
per class match the OM-1 1.9 almost exactly and differ from the E-M5 III.[^fw1]

| class | E-M5 III | OM-5 II | OM-1 |
|---|---:|---:|---:|
| `CapImg_ImagePlayer` | 161 | 172 | 180 |
| `PlayCommon` | 56 | 92 | 91 |
| `CPlaySingleFrame` | 26 | 51 | 51 |
| `OlyHfwOpePlyLightBox` | 40 | 49 | 49 |

*Method-name string counts per class.[^fw1]*

The [firmware lineage](../bodies/lineage.md) study lists the playback regions the OM-5 II shares only with the OM-1
line. The address reference lists them.[^fw10]

The OM-5 II adds new playback UI text.[^fw1]

- Rating, Rating Selected, Rating Settings, Reset Ratings.
- "Clears Rating of selected images".
- "Delete all images excluding protected images or images with rating flags".
- Information 1-3.
- "Maintains the displayed playback or menu screen when you look through the EVF".

The Rating EXIF tag is described on the still image back end page.[^fw1] See also:
[Still image back end](still-backend-technical.md).

## Open questions

- What each record mode (`0x1001`, `0x1003`, `0x1004`, `0x100a`) does inside `REC_IMAGE`, and how the result returns.
- What device the CUBE media is. A phone transfer target over Bluetooth is the likely reading.[^inf1]
- The JPEG decode job inside the request engine (registers).
- The GPU job details behind `play_gpu_draw`.

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 II 1.1 is named. The OM-5 II addresses are in
[OM-5 II 1.1 compared](#om-5-ii-11-compared).

| item | address |
|---|---|
| `api_play.c` | `0x602f70f1` to `0x60301260` |
| send-and-wait call used by the C API | `0x602e4a80` |
| component name string table | near `0x60b0d9bb` |
| `play_*.c` engine | `0x612abd17` to `0x612c2a00` |
| engine log functions (`in` / `out`) | `0x612aed50`, `0x612aed64` |

*Layers and code ranges.*

| task | entry | queue id variable |
|---|---|---|
| `PLAY_MAIN` | `0x612abd55` | `0x60040fa0` |
| `PLAY_LOAD` | `0x612bada1` | `0x60040fa4` |
| `PLAY_IMAGE` | `0x612b589d` | `0x60040fa2` |
| `PLAY_SOUND` | `0x612c1236` | `0x60040fa8` |
| `PLAY_LOADDRAW` | `0x612baccc` | `0x600410ba` |
| `PLAY_DECODE` | `0x612af6bb` | `0x600410b8` |

*Play engine tasks. Boot creates them at `0x6019d79a` to `0x6019d82e`.*

| item | address |
|---|---|
| `PLAY_MAIN` message buffer | `0xa25c3d90` |
| router hash table | `0x613ae8b0` |
| load kind table | `0x613b443c` |
| `play_load_prim_exec` (kind 0) | `0x612b90c1` |
| `play_load_thumb_exec` | `0x612b8e01` |
| `play_load_movie_load_thum` | `0x612bb212` |
| `play_load_header_exec` | `0x612b8815` |
| `play_load_playpic_exec` | `0x612b8a10` |
| `play_load_movie_load_playpic` | `0x612bb3c0` |
| raw header check (kind 4) | `0x612bc1fc` |
| `play_load_raw_load_prim_raw` | `0x612bc444` |
| `play_sound_load` | `0x612bcb8e` |
| `play_load_mpo_exec` | `0x612bbabf` |
| `play_img_decode_jpeg_division` | `0x612b7986` |
| `play_draw_normal_division` | `0x612b04aa` |

*Router and load kinds.*

| item | address |
|---|---|
| `play_img_decode_jpeg` | `0x612b5ace` |
| work buffer allocator | `0x603f84b8` |
| request builder called for decode | `0x60370e32` |
| `rec_ImgPro_Ycc2Jpeg` builder | `0x60370dc3` |
| `play_cic_decode_raw` | `0x612ad059` |
| CIC driver entry | `0x60c22b6a` |
| CIC block (interrupt 145) | `0x9b700000` |
| `MOVP_MAIN`, `MOVP_VIDEO`, `MOVP_AUDIO` | `0x612ceaaa`, `0x612d67f5`, `0x612cdf60` |
| `MOVP_ASB` | `0x612ce8fc` |
| `AVM_P1V` | `0x603f4788` |
| H.264 unit | `0x99400000` |

*Decoding and movie playback.*

| item | address |
|---|---|
| `play_edit_main` | `0x612b0c4c` |
| edit kind table | `0x613b0444` |
| `play_color_edit` | `0x612ad153` |
| `play_trimming_edit` | `0x612c1333` |
| `play_redeye_edit_main` | `0x612be2d9` |
| `play_apical_edit_main` | `0x612abf88` |
| `play_rotate_edit_exec` | `0x612bff29` |
| `play_resize_main` | `0x612bf11f` |
| `play_pocket_main` | `0x612bdbad` |
| `api_picfile.c` CUBE picture call (API `0x70017`) | `0x602f360e` |
| `play_regist_regist_pic` | `0x612beb46` |
| `play_multi_raw_edit` / `play_multi_raw_save` | `0x612bd71e` / `0x612bda85` |
| `play_change_aspect_edit_main` | `0x612accd6` |
| `play_beauty_edit_main` | `0x612ac5ff` |
| `play_sns_main` | `0x612c0adc` |
| `play_save` | `0x612c0341` |
| `play_save_raw` | `0x612c097f` |
| `play_edit_raw_edit` | `0x612b0e12` |
| `play_edit_raw_edit_artbkt` | `0x612b1015` |
| `play_mov_edit` (kind 8) | `0x612bcf91` |
| `play_gps_main_exec` (kind 9) | `0x612b54ed` |

*Edit functions.*

| item | address |
|---|---|
| `play_rec_raw_edit` | `0x612bddba` |
| progress callback | `0x612bdd6b` |
| record queue | `0x60040fb0` |
| send to the record queue and wait | `0x600548f7` |
| `REC_MAIN` handler | `0x603fb25b` |
| message read | `0x603fb3f0` |
| first type branch | `0x603fb920` |
| second type branch | `0x603fbb33` |

*RAW development and the record side.*

| item | address |
|---|---|
| `CmpPls::getZoomPosSteps` | `0x60916c88` |
| `CapPls_PlayState` band selector | `0x608bd888` |
| band table | `0x60b28448` |
| second band set | `0x60b282dc` |
| display-condition flags | `0x621cd581`, `0x621cd594` |
| step table (1,1 to 10,10) | `0x60b284a8` |
| step table (15,15 to 40,40) | `0x60b284cc` |

*Zoom.*

| item | address |
|---|---|
| `api_play.c` voice memo (API `0x3001f`) | `0x602f91e2` |
| `api_play.c` API `0x3005b` | `0x602fbc68` |
| `api_play.c` API `0x30099` | `0x60301178` |
| `httpd_cgi.c` | `0x6120c18c` ff. |
| `[wifi_play]` | `0x61223801` |
| `pos` GPS log tagging | `0x61213a99`, `0x612141d9` |

*Clients of the engine.*

| classes | region |
|---|---|
| `OlyApiPlayMovie`, `CPlayIndex`, `CPlaySingleFrame` | around `0x60d40000` |
| `CapImg_ImagePlayer` | `0x60900000` to `0x60940000` |
| `CmpPli`, `CmpERaw`, `CmpEImg` | `0x60a80000` |
| `CmpERot`, `CmpETri`, `CmpPLgh` | `0x60ac0000` |
| `userMenuPlay` | `0x60f40000` |
| `dcfedit` | `0x60680000` |

*Playback regions the lineage study lists as shared only by the OM-5 II and the OM-1 line.[^fw10]*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. Disassembly of E-M5 III 1.7 and OM-5 II 1.1 block0, strings of OM-5 1.2, E-M1 III 1.6 and OM-1 1.9.
[^fw2]: Counted in the symbol table's module list, 2026-11-25. Only functions that carry a file name are counted.
[^fw3]: Names read in the firmware, 2026-11-25.
[^fw4]: Calls read in the firmware, 2026-11-25. That this is the decode job is inferred.
[^fw5]: Request read in the firmware, 2026-11-25. The record-side handling is inferred.
[^fw6]: Tables read in the firmware, 2026-11-25.
[^fw7]: Read in the firmware, 2026-11-25. The reply-queue reading is inferred.
[^fw8]: Copy and compares read in the firmware, 2026-11-25. What each mode does inside `REC_IMAGE` is not traced.
[^fw9]: Strings read in block0, 2026-11-25. E-M1 III and OM-5 strings come from the expanded RAM images.
[^fw10]: Read in the firmware for the firmware lineage study.
[^inf1]: Inferred, not traced to the end, 2026-11-25.
[^inf2]: Inferred from the `step_x` / `step_y` log string, 2026-11-25.
[^inf3]: Inferred from function names, 2026-11-25.

