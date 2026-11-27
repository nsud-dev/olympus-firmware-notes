# Lens communication: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Lens communication](lens-communication.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 main program talks to a Micro Four Thirds lens. It describes the serial block,
the request queue and tasks, the two-byte wire command set, the focus, aperture and zoom drive calls, and the
`lens_info` record the body keeps for the attached lens. It is static reading only, with no camera runs. Much of it
comes from the strings of the `lens` debug shell in block0.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. Function and variable
addresses are in the [address reference](#address-reference). Offsets into `lens_info` are written `+0x...`.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Layers

| layer | what |
|---|---|
| debug shell `lens` | 34 sub-commands. Prints `lens_info`, sends raw commands, drives focus, zoom and aperture. |
| callers | the AF task `fcs`, the still sequence, power zoom and IS. They build requests. |
| request queue | one `0xa8`-byte request block per command, with a callback on completion |
| tasks | `LENS_MAIN` (task 102), the message server. `LENS_ASKDATA` (task 99), the data-read task. |
| lens data | `lens_info` and `adap_info`, about 113 KB per device, 38 sections |
| low-level driver | the only code that touches the serial block |
| hardware | serial block `0x9bb00000`, a dedicated lens serial controller (not the generic `PER_SIO`) |

*The lens layers from the shell down to the hardware.[^fw1]*

## Lens serial block `0x9bb00000`

**A dedicated controller.** Only the 70 functions of the low-level driver touch `0x9bb00000` to `0x9bb001b8`. No other
block0 code does. It is not the generic `per_sio` driver.[^fw1] The KB had no entry for this block before.

**Open and close.**[^fw1]

- Close registers the interrupt handler on line 3 at level 3. It calls the clock-gate function with (0, 4, 1) and
  (0, `0x10`, 1). It clears `0x9bf00000`/`0x9bf00068` and `0x9bb00000`/`04`.
- Open calls a set-up function with (`0xb8`, 3). It writes the bit timing word `0x9bb00010` as five nibbles from a
  parameter block.

**Device select.** The select function takes a device number. It sets pins `0xb9` (device 0) or `0xba` (device 1),
plus `0xbd`, `0xbb` and `0xb8`. Then it writes a per-device clock value to `0x9bb00030`.[^fw1] Device 0 is the lens
and device 1 the adapter, the same 0/1 split as the `lens_info` getter.[^fw1] That the ids are pin-mux entries is
inferred.[^inf1]

**Sending one command.** The send functions fill the block's registers from the request block and start the
transfer.[^fw1]

| register | written with |
|---|---|
| `0x9bb00048` | request bytes `+10` to `+13`, the first four wire bytes, little-endian |
| `0x9bb0003c` | the byte count, request `+0x14` |
| `0x9bb00054` | an extra length, request `+0xe` |
| `0x9bb0005c` and up | the FIFO window for longer payloads |
| `0x9bb00034` | the frame mode (next table) |
| `0x9bb00164` | `0x3e7011f` |
| `0x9bb001b4` | 2 |
| `0x9bb001b8` | `0x150006` |
| `0x9bb0000c` | `0x3bf` (`0x13bf` for wire `70 c8`) |
| `0x9bb00038` | 1, which starts the transfer |
| `0x9bb00018` | status, read |
| `0x9bb00040` / `0x9bb00008` | the received word, read |

*Registers written and read for one command.[^fw1]*

**Frame mode.** The mode is chosen by the first wire byte.[^fw1]

| first byte | `0x9bb00034` | timing slot | likely meaning |
|---|---|---|---|
| `0xa0`, `0xe0` | `0x21` | 0 | short command, no reply data |
| `0xb0`-`0xb2`, `0x70` | `0x3721` | 1 | drive command with a reply (focus, aperture, LAF) |
| `0xc0`-`0xc3`, `0x80`, `0x81` | `0x421` | 2 | data read ("ask data") |
| `0xd0` / `0xd1` | `0x21` / `0x51` | 3 / 4 | Type-D (two focus groups) |
| `0x60` | `0x2621` | 5 | live-view frame packet (`SET_ACT_LV`) |
| `0xf0` + `0x60`/`63`/`64`/`70`/`73`/`74` | `0x5821` | 7 | private command with payload |
| `0xf0` + `0x61`/`62`/`66`/`71`/`72`/`76` | `0x21` | 6 | private short command |
| `0xf0` + `0x65`/`67`/`75`/`77` | `0x9421` | 8 | private, other format |
| `0x90` + `0x90`-`0x97` | `0x21` / `0x3721` / `0x421` / `0x5821` | 0/1/2/7 | second private set |

*Frame mode and timing slot by first wire byte.[^fw1] The meanings in the last column are inferred.[^inf1]*

**Timing.** Per-slot defaults come from four tables passed to the timing function. The first holds
{600, 250, 250, 400, 250, 250, 400, 250, 250}. `0xd0` uses 750, and `a0 b0`/`b1` use 1000.[^fw1] The unit is
probably µs.[^inf1]

**Command log.** `lens ssc log` prints per command `comtime`, `interval`, `status`, `comptime` [us] and the last
command. Logging is gated by a debug word (the `lens set` and `lens log` flags), and one function is the trace
call.[^fw1]

## Requests, queue and tasks

**Request block.** Each request is an `0xa8`-byte block from the lens heap. The heap has a small pool for blocks up to
`0x100` bytes and a large one for `0x2000`.[^fw1]

- `+0` link or user
- `+4` callback `cb(result, req)`
- `+0x10` **type** (u16)
- `+0x12` flag
- `+0x14` **code** (u16)
- `+0x16` and up, parameters
- `+0x28` and up, the command payload

The post function queues a request or sends it at once.[^fw1]

**Request types.** These come from more than 40 builders. The values are read in the firmware.[^fw1] Their meanings
are inferred from the shell help and the callers.[^inf1]

| type | used for | codes |
|---|---|---|
| 1 | power and state | `a0 b0` / `a0 b1` |
| 2 | aperture | `0x21` `AV_ABS`, 1, `0x2000`-`0x2006` |
| 3 | drive: focus, power zoom, LAF, Type-D, live-view packet | 2 `PLS_ABS`, 3 `DST_ABS`, 4 `PLS_OFST`, `0x11`-`0x15` zoom, `0x60`/`0x63` live-view packet, `0x1000`-`0x1003`, `0x2000`-`0x2002`, `0x3000`-`0x3007` |
| 4 | aperture-module requests | codes 1/2, chosen by bits 1-2 of an aperture state word. The builders share debug flag `0x40000` and the globals of the aperture builders. |
| 6 | ask data (read) | `0x10` `ASK_STATUS_A`, `0x21` `ASK_STATUS`, `0x45` `ASK_STATUS_LV`, `0x51` `ASK_STATUS_LV_PRIVATE` |
| 7 | Sync IS follow-up | after private function 42 (`0x2a`) on a copt lens, sends 7/`0x50` with the aperture value |
| 8 | end | Type-D end and one other builder |
| 9 | still-shooting notices | codes 0-6 / `0x1000`-`0x1006` |

*Request types and their codes. The builders are in the [address reference](#address-reference).*

**Tasks.**[^fw1]

- Static task record 102 is `LENS_MAIN` (prio 25, stack 1792). It is a message server. It reads a queue with
  `OlyQeRdCpu`, runs its handler and answers with `OlyQeWrCpu`.
- Record 99 is `LENS_ASKDATA`, the data-read task.
- The names come from the two task starters, which start ids 102 and 99.
- On the OM-5 II the same tasks are 102 and 100, and record 99 is the AF task `fcs`.

## Command set

**Wire commands are two bytes**, a class byte then a command byte (for example `a0 b1`, `b0 a2`, `c1 80`). One builder
writes `0xa0` to `+18` and `0xb0`/`0xb1` to `+19`. The driver keys the frame mode on `+10` and the sub-command on
`+11`. That proves the two-byte form.[^fw1]

**Command table.** It has 130 entries of 8 bytes, {class, cmd, sub, 0, type u16, code u16}. `lens com` uses it to turn
a typed wire code into a request. It is the best list of commands the body knows.[^fw1]

| class | commands (cmd -> type/code) |
|---|---|
| a0 | f5->6/6, e2->6/0x11, eb->6/0x15, 80->6/0x62, 40->3/0x10, a0->3/0x16, b8-ba->3/0x17-0x19, d0-d5->3/0x11-0x15 (zoom), ae->2/0x41, b0/b1->1/0 |
| b0, b1 | f2->6/0, fe->6/5, a0-a4->3/0-4 (focus), aa/ac/ad->3/8,10,11, d0/d7->2/0,1, d1/d2->2/0x21,0x22 (aperture), dc/dd->2/0x24,0x25. b1 adds ff/88/89->6/0x48-0x4a. |
| b2 | d1/d2/d7 -> 3/0xd-0xf |
| c0, c1 | ask data: f6/f8/f9/fa->1-4, e1->0x10, e6/e8/e9/ea->0x12-0x16, f0/f1->0x20/0x21, fb->0x23, e0->0x30. c1 adds f2->0x41, fc->0x42, 80->0x45, 12->0x46, fe->0x47, 01->0x4d, 20->0x4e, d0->0x4f, 02->0x50, 00->0x51, e2->0x61, f7->0x55, 2f->0x59. |
| c2, c3 | c2 f3->7, c2 f5 sub 6/7->0x43/0x44, c2 e0 sub 2->0x60, c3 f0->0x40 |
| 60 | 80/81/00/01/f0/0a -> 3/0x60,0x61,0x63,0x64,0x65,0x70 (`SET_ACT_LV`, `_EZ`, `_EZ_PRIVATE`) |
| 70, e0 | 70 c2/c4/c6/c7/ca/cb/c8 -> 3/0x3000,0x3002-0x3007. e0 c3 -> 3/0x3001 (LAF). |
| d0, d1 | d0 a7-a9 -> 3/0x2000-0x2002, d1 a7/a8/ac/ad -> 3/0x1000-0x1003 (Type-D), d1 d1/d2/dc/dd/ae/de -> 2/0x2000-0x2006 |
| 80, 81 | 80 12 / 81 12 -> 6/8, 81 e4 -> 6/0x4c |

*The wire command table by class byte.[^fw1]*

**x0 and x1 pairs.** Most commands exist in both b0/b1 and c0/c1, and the x1 set is a superset.[^fw1]

- The encoder picks x1 when a per-device byte is set.
- That byte is set from the lens's reply to ask-data `0x16`. The reply record per device is {u16 a, u16 b}, and the
  flag = a > 1 and 1 ≤ b ≤ 12.
- That x1 is the newer protocol generation is inferred.[^inf1]

**Link speed** per device is a record {u16 kbps, u16 count}. `lens data lens 7` prints it, and `count` is what goes to
`0x9bb00030`.[^fw1]

**Protocol version.** The body also keeps a protocol version per device (`0x0b0a` reads as `0x1000`). It gates
commands on it. Power zoom needs ≥ `0x110a` and the private live-view packet ≥ `0x120a`.[^fw1]

**Modes from the shell help** ("See lens_askdata.h").[^fw1]

- Ask data: `0x00` ALLRESET, `0x10` ASK_STATUS_A, `0x21` ASK_STATUS, `0x45` ASK_STATUS_LV, `0x51`
  ASK_STATUS_LV_PRIVATE.
- Aperture: `0x01` OPEN, `0x21` AV_ABS, `0x22` AV_ABS_RESET.
- Focus: `0x02` PLS_ABS, `0x03` DST_ABS (value/5 mm, `0xffffffff` = infinity), `0x04` PLS_OFST, `0x40`
  ASK_AFL_LD_PLS_C.

## Focus, aperture, zoom and IS drive

**Focus drive API.** The `lens lddrv` shell handler calls these functions. The help text gives the names.[^fw1]

| # | name | request (type / code) |
|---|---|---|
| 0-5 | Sync drive absolute / relative / scan / wobbling / stop / defocus | live-view packet (3 / `0x60`, or `0x63` private) |
| 6 | Async drive absolute | 3 / 2 |
| 7 | Async drive relative | 3 / 4 |
| 8 | Async drive defocus | 3 / 1 |
| 9-12 | LAF change mode / set scan speed / drive absolute / absolute and scan | 3 / `0x3000`, `0x3001`, var |
| 13-17 | Type-D main absolute / main scan / defocus / sub absolute / sub defocus | 3 / `0x2001`, -, `0x2000`, `0x1001`, `0x1000` |
| 18, 19 | Type-D set absolute limit time / end | 3 / `0x10`, type 8 |
| 20 | wait drive absolute | 2 / `0x2004` |

*The focus drive API. Function addresses are in the [address reference](#address-reference).*

**Sync and async drives.** In live view the body sends one packet per sensor frame (class `0x60`, `SET_ACT_LV`) that
carries the focus move. The sync drives fill it.[^fw1] The first sync drive reads `TD_LDmin` at `+0x202e` and the
private-packet bit, bit 27 of `+0x440`.[^fw1] Async drives are single commands for moves outside that rhythm.[^inf1]
`lens sync` controls the frame link (`LENS_SYNC_COM_START/END/PAUSE/RESTART/UPDATE/FIXED/FORCED_ASYNC`, 240 fps
sync/async state).[^fw1] The frame-rhythm reading is inferred.[^inf1]

**LAF and Type-D** are two lens drive families with their own commands (class `0x70`/`0xe0` and `0xd0`/`0xd1`).
Type-D has a main and a sub focus group.[^fw1] That LAF is the linear-motor family is inferred.[^inf1]

**AF callers.** The AF task builds requests directly, with these type/code pairs: 3/`0x2002`, 3/`0x1003`, 3/1,
3/`0x20`, 3/`0x2000`, 3/`0x1000`, 3/2 (absolute), 6/`0x21` (status), 3/10, 3/`0x1002` and 3/`0x10`. It also uses the
`fcs_lens_*` functions.[^fw1] The Starry Sky AF "lens commands 6/7" are probably lddrv 6 and 7, async absolute and
relative.[^inf1]

**Aperture.**[^fw1]

- One builder sends 2/`0x21` (`AV_ABS`), with the target from an aperture getter or from a stored value + 10.
- Others send 2/1, 2/`0x2000` and 2/`0x2004`.
- The shell `lens aperture` goes through its own handler to the aperture code.

**Power zoom (EZ).** The shell `lens zoom` calls the zoom functions (type 3 codes `0x11`-`0x15`, wire `a0 d0`-`d5`).
They run only when ENABLE `ez` (`+0x1bc82`) is set and the protocol version is ≥ `0x110a`. They offer speeds 0-7,
TELE/WIDE, LENGTH and STOP, each sync or async.[^fw1]

**Lens IS.** `lens is` sends Olympus private commands. They are `SetActLV_Private`, `SetISLDsyncAP_Private`,
`SetDataB_Private`, `ContEndB2Async_Private`, `ContAPopn_Private`, `WcontAPopn_Private`, `ContExpEnd_Private`,
`ContIS_Private` and `SetIsAsync_Private`. `lens ois` shows `g_ois_sw_info`, `g_lens_is_mode`,
`g_lens_is_change_exec_cnt` and `g_lens_is_pending_ctrl`.[^fw1] See also: [stabiliser](stabiliser-technical.md).

**Sync IS query.** The query runs only if the Sync IS flag check returns 1. That check is the lens function flag page 2
bit 3, the word at `+0x1bca4` + 4 × page. The query then sends private function **41 (`0x29`)** and stores the reply
byte as the copt flag.[^fix1] So "command 41" is a private function number, not a wire command.

## `lens_info`: what the body knows about the lens

**Pointers.** The body keeps one pointer to `lens_info` and one to the adapter info. A getter takes a device number and
returns them only while the device is connected. The record is about `0x1c000` bytes (about 113 KB).[^fw1]

**Section printers.** `lens data lens N` dispatches through a 38-entry table to the section printers. The field labels
in their strings are Olympus's own names.[^fw1] The table below has the offsets.[^fw1]

<details><summary>All lens_info sections and their fields</summary>

| offset | section | fields (offset: label) |
|---|---|---|
| `0x000` | STATE (0) | `+4` `L_STATUS_M`, `+8` `L_ZMENC`, `+9` `L_FCENC`, `+0xc` `L_OBJdst` (mm), `+0x10` `L_APACTnow`, `+0x12` `L_APACTnow(infinity)`, `+0x14`/`15` `L_DIS_ZMENC/FCENC`, `+0x16` `LAF_DIS_M[8]`, `+0x26` `valid_pls_num`, `+0x27` `pls_sync_state`, `+0x28` `L_PULSE_M[]`, `+0x226` `L_STATUS_EZ`, `+0x228` `L_SPEED_EZ`, `+0x22c` last update time, `+0x230` `L_STATUS_PRIVATE[0]`, `+0x234` `L_IS_STATUS`, `+0x238` `L_IS_MOVESTEP[2]`, `+0x23c` `L_IS_GAVE[2]`, `+0x240` `L_TRC_ZMENC[4]` |
| `0x440` | CHARACTER (1) | `+0x440` `L_REF_M` (capability bits, bit 27 = private live-view packet), **`+0x444` `L_ID[6]`**, `+0x44a` `L_NAME[32]`, `+0x46a` `L_ZMENCdiv`, `+0x46b` `L_ZMENCprm`, `+0x46c` `L_FCENCdiv`, `+0x46d`-`0x46f` `L_DIS_*_N`, `+0x470` `L_FLwide`, `+0x472` `L_FLtele`, `+0x474` `L_SERIAL[12]`, `+0x480` `L_VERSION` |
| `0x484` | CHARACTER_ZM (2) | per zoom step: `L_FLenc`, `L_APmin`, `L_APmax`, `L_APACTmin`, `L_APACTmax`, `L_AFjdg`, `L_LDmaxmin`, `L_DSTmin` |
| `0x684` | MAKERNOTE (4) | `L_BUNKOUTOUKA[]` (spectral transmission), `+0x6c6` `CCIb/g/r`, `+0x6cc` `out_e[]` |
| `0xe18` | DIST (14) | `L_DIS_LD0-2[][]`, `+0xf98` `L_DIS_R`, `L_DIS_M`, `+0x1018` `L_DIS_E0-2` (distortion) |
| `0x10d8` | DIST_PARAM (16) | `dis_c_*`, `dis_d_*`, `dis_m*`, `*_r100` (`+0x10ec`-`0x1eec`) |
| `0x1fec` | SYNC (15) | `L_EXP_FLG`, `L_WOB_AMP_MAX/MIN_15-120Hz`, `L_WOB_MOV_MAX_*`, `L_FOC_MOV_MAX_30-120Hz`, `+0x200e` `L_AP_SPEED_MAX/MIN/SIL[]`, `+0x201a` `L_AP_SW_W/N/T[]`, `+0x202c` `TD_LDmax`, `+0x202e` `TD_LDmin`, `+0x2030` `N_LDPmax`, `+0x2032` `L_FOC_MOV_MIN_TIME` |
| `0x6e4` | LAF (10) | `LAF_TH_PLS[]`, `LAF_MAX/MIN_SPEED[]`, `LAF_Z_POS[]`, `LAF_VH/VL/VV/LED_ADJ_C/UD/LR[][]` (own printer) |
| `0xa58` | TH_PLS (35) | `LAF_TH_PLS_OLYFTS[][]`, `_FC_DIV[][]` |
| `0x2034` | IS (9) | `L_FLact[]_K0-K2` `+0x2034`/`38`/`3c`, `L_LatMAG[]_K1/K2` `+0x2040`/`44`, `L_ObjPRINC[]_K0-K2` `+0x2048`/`4c`/`50`, `L_LDinf[]` `+0x2054`. Macro copy from `+0x24b4`. |
| `0x24d8` | LENS_OIS (25) | `ois_info`. Bit 0 is what the Panasonic lens-IS status check reads. |
| `0x24d9` | LIFTM (17) | `LIFT_K_M[ZMENC_N][FCENC_N]`, 64-byte rows |
| `0x2cda` | WOB_MAG (18) | `L_DeltaMag[]` |
| `0x2d1c` | ZAF (26) | zoom-AF tables: `L_ZAF_*` (`+0x168c` `L_ZAF_C_RAY`, `+0x2d0c` `L_ZAF_AV_POS`, ...), `LAF_TH_PLS_Exact` (`+0x7ef0`), `LIFT_K_POS`/`LIFT_KK` (`+0x7fb0`/`+0x8fb0`), `LENS_SHORTEN_DRIVE_DEF/SEC` (`+0x97b0`/`+0x9870`), LISK and ZAF2 variants (`+0x3498`.., `+0x361e`..). Offsets relative to this base (inferred). Macro copy at `+0xc64c`. |
| `0x15f7c`, `0x16a22` | CA (27) | chromatic aberration tables (normal, macro). CA_PARAM (28) at `+0x174c8` / `+0x17adc`. |
| `0x180f0`, `0x19c20` | MTF (29) | MTF tables |
| `0x1b750` | 3D (21) | `L_CONVERGENCE_ANGLE` .. `L_3D_FLG` |
| `0x1b77c` | EZ (22) | `L_EZenc[]` |
| `0x1b79c`, `0x1b79e` | CURRENT (33), WOB_POSSIBLE (19) | `L_CURRENT_CONSUMPTION[]`, `Wob_Possible[]` |
| `0x1b7e0`, `0x1ba2c` | BLC-IS (31) | BLC-IS data and centre offset, macro copy |
| `0x1bc78` | IS_ERROR (32) | `L_IS_ERR` |
| `0x1bc7c` | ENABLE (30) | bytes: `+0` laf, `+1` th_pls, `+2` is, `+3` is_macro, `+4` wob_mag, `+5` three_d, `+6` ez. Int `+8` zaf, `+0xc` zaf_macro. Bytes `+0x10` ca, ca_macro, mtf, mtf_macro, dis. Int `+0x18` blc_is, `+0x1c` blc_is_macro. Bytes `+0x20` is_error, current_consumption, wob_possible, mag_cng. |
| `0x1bc94` | BLC-IS (31) | `+0x1bc94`, `+0x1bc98` |
| `0x1bca0` | OLY_PRIVATE (23) | `+0x1bca0` function-flag page count, **`+0x1bca4` `L_FuncFlag[page]`** (u32 per page), `L_SetDataFuncFlag[]`, `+0x1bce8` `L_FUNC_FLAG_PANA`, private state from `+0x1bcea`, `L_PRIVATE_ID_DATA` / `L_PRIVATE_ADJ_VERSION` (`+0x104`/`+0x108` into a block at `+0x1bd78`) |
| `0x1be78` | IS_ALGO (34) | `L_IS_ALGO_INFO` |
| `0x1be84` | TRC_CURVE (36) | `L_FC_TRC_CURVE_*` (focus-vs-zoom tracking), `+0x1bf88` |

*Sections of `lens_info`, read from the asm of the section printers.[^fw1]*

</details>

Each optional section is printed only when its ENABLE byte is set. SHADING (5) and FOURTHIRDS (7) print values held
outside `lens_info`.[^fw1]

**`L_ID` (`+0x444`).** Bytes 0-1 select the private set.[^fw1]

- {0, 0} = Olympus (`OLY_PRIVATE_STATE`).
- {2 or 3, 0} = Panasonic (`PANA_PRIVATE_STATE`).
- Anything else = the generic `PRIVATE_STATE`.

That byte 0 is the maker code is inferred.[^inf1] The focus-stacking lens-type check reads the same bytes.[^fw1]

**Function flags.** The flag check takes a page and a mask. It returns 1 when the lens is Olympus-private, the page is
≤ the count at `+0x1bca0` and `L_FuncFlag[page] & mask` is set. Its users test page 1 bit 26 and page 2 bit 3 (Sync
IS).[^fw1]

**Adapter record** (`lens data adapter`). Its fields are `A_STATUS`, `A_ENC`, `A_SBJdst`, `A_DAMAGE`, `A_ID[]`,
`A_NAME[]`, `A_MAG`, `A_APmin`, `A_FLmin/max`, `A_ENCdiv`, `A_SERIAL[]`, `A_VERSION`, `A_FT_VERSION` and `A_DIS_TD[]`.
It covers Four Thirds lenses on an adapter and teleconverters.[^fw1]

**Ghidra structure.** A `lens_info_t` structure with 138 fields is applied in our Ghidra project, so every reader of
the lens record shows named fields. Some inner table offsets are still unnamed.[^fw3]

## Users of the lens record

These uses come from the field names and their readers.[^inf1]

- **AF.** Focus pulse position and limits (`L_PULSE_M`, `L_LDmaxmin`, `TD_LDmax/min`, `N_LDPmax`), speeds
  (`LAF_MAX/MIN_SPEED`, `L_FOC_MOV_MAX_*`), wobbling limits for movie contrast AF (`L_WOB_*`), focus-vs-zoom tracking
  (`L_FC_TRC_CURVE_*`), zoom AF tables (`L_ZAF_*`) and in-focus judgement (`L_AFjdg`).
- **IS.** Actual focal length and principal point (`L_FLact`, `L_ObjPRINC`), lateral magnification (`L_LatMAG`), lens
  IS stroke and sense (`L_IS_STROKE`, `L_IS_SENSE`), the `BLC-IS` block and the Sync IS flag. The IS host module
  `bc_blc_sync` reads `lens algo ver` and `lens_error`.
- **Image processing and EXIF.** Shading, distortion (`L_DIS_*`, `dis_*`), chromatic aberration (`L_CA_*`), MTF
  (`L_MTF_*`), spectral data (`L_BUNKOUTOUKA`) and the MakerNote lens fields (`LensID`, `LensSerialNumber`,
  `LensFirmwareVersion`, distortion and CA coefficients).
- **Lens firmware update** (`LENS_FIRM_UP`, `g_lens_firmup_*`) and **My Favorite lens** records (`lens fav`) also live
  here.

## Debug shell `lens`

The `lens` command has 34 sub-commands.[^fw1] They are set, reset (`LENS_SETUP/SETDOWN/SLEEP_SHIFT/SLEEP_RETURN`),
aperture, still, focus, askdata, ctrl, data, fav, pow, mtdet, llpsw, polling, firmup, zoomdrv, lensmem, sync, state,
cs, ssc, ois, trouble, com, zaf, exif, is, current, lddrv, ldinfo, blcis, zoom, dbginfo and log. The trouble bits are
still disable, manual sink, electric sink, step out and actuator trouble. `lens data lens 255` dumps everything.

The shell is reached from the [Wi-Fi debug shell](../features/wifi-debug-shell-technical.md). Nothing here was run on
the camera.

## Other bodies

The OM-5 II 1.1 lens code matches the E-M5 III's.[^fw2]

- The wire table is identical, entry for entry.
- The `lens` shell has the same sub-commands and data sections. Only the `lens exif` MakerNote printout strings are
  gone.
- The serial block is the same, with the same registers and the same write counts (98 sites).
- 62 of 70 low-level functions match in shape. The rest are reorganised helpers, such as the timing function.
- The `lens_info` layout matches. 31 of the 33 non-empty section printers are identical with offsets, for example
  ENABLE at `0x1bc7c`. The other 2 could not be paired automatically.
- Overall 70% of the lens driver's bytes match by shape, against 49% for all of block0.

## Open questions

- What the ask-data `0x16` reply fields a and b mean (they pick the x1 command set).
- The exact role of request type 4.
- The units of the timing tables.
- Some inner table offsets of `lens_info_t` are still unnamed.
- A read-only check on the camera would confirm `L_ID` and the ENABLE flags. Run `lens data lens 1` and
  `lens data lens 30` over the Wi-Fi shell for one Olympus and one Panasonic lens. No writes, no drive commands.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| `lens` shell strings | `0x601ab16c` to `0x601b1000` |
| `lens` shell dispatcher, code range | `0x600f095e`, `0x600f0000` to `0x60102000` |
| AF task `fcs` lens callers | `0x606b13a2` to `0x606ce201` |
| still sequence | `0x60564f13` to `0x605690b3` |
| power zoom functions | `0x60101377` to `0x601017f5` |
| IS caller (Sync IS query) | `0x600fd973` |
| request post, immediate send | `0x602051f7`, `0x602051ff` |
| `LENS_MAIN` entry, handler, queue id | `0x602024ee`, `0x60202581`, `0x60040f7a` |
| `LENS_ASKDATA` entry | `0x602044b7`, then `0x6021a28e` |
| task starters, id words (102, 99) | `0x60045a77`, `0x60045a92`, `0x60040bd8`, `0x60040bd2` |
| OM-5 II `LENS_MAIN`, `LENS_ASKDATA` entries | `0x6021668f`, `0x60218704` |
| `lens_info` pointer, adapter info pointer | `0xa2643c84`, `0xa2643c8c` |
| getter (dev), connected check (dev) | `0x60209e5b`, `0x601009d9` |
| low-level driver | `0x6021c0cd` to `0x6021e020` |
| lens heap, heap base pointer | `0x6021d75c`, `0x620a77ec` |

*Layers, queue, tasks and record pointers.*

| item | address |
|---|---|
| lens serial block | `0x9bb00000` to `0x9bb001b8` |
| close, interrupt handler | `0x6021c2db`, `0x6021c6ea` |
| IRQ registration, clock gate, set-up call | `0x60069ec9`, `0x60071fa6`, `0x60067959` |
| open | `0x6021c34c` |
| device select, pin function | `0x6021cc36`, `0x600678e3` |
| send one command | `0x6021c58c`, `0x6021cc93`, FIFO fill `0x6021d244` |
| frame mode selection | `0x6021cc93`, `0x6021cfdd`, `0x6021d036` |
| timing tables, timing function | `0x601b118c`, `0x601b119e`, `0x601b11c2`, `0x601b11d4`, `0x6021d0bd` |
| `lens ssc` handler, debug word, trace call | `0x602204ca`, `0x620a7428`, `0x60210f0e` |

*Lens serial block.*

| item | address |
|---|---|
| type 1 builders (`a0 b0` / `a0 b1`) | `0x6021de34`, `0x6021df2f` |
| type 2 `AV_ABS` builder | `0x6021b6ee` |
| type 4 builders | `0x6021acd5` (state word `0x620a7788`), `0x6021ad6d`, `0x6021ae81`. Aperture globals `0x620a7760` to `0x620a778a`. |
| type 7 builder | `0x6021af50` |
| type 8 builders | `0x60219d8d` (Type-D end), `0x6021b68e` |
| type 9 builders | `0x60564f13` to `0x605659c1` |
| two-byte proof builder | `0x60214922` |
| wire command table, `lens com` | `0x601aad5c`, `0x600f7022` |
| encoder, x1 flag byte | `0x60215030`, `0x620a73f0`[dev × 6] |
| x1 flag set, ask-data `0x16` reply handler, reply record | `0x6020a12a`, `0x60217798`, `0x620a73ec`[dev × 6] |
| link speed | `0x620a735c`[dev] |
| protocol version, its writer | `0xa2643c88`[dev], `0x6020d03f` |
| power zoom version check, private live-view packet check | `0x60101607`, `0x60218fed` |

*Requests and the command set.*

| # | function |
|---|---|
| 0-5 | `0x60218fed`, `0x60219247`, `0x602192f0`, `0x60219415`, `0x602194be`, `0x602195ed` |
| 6, 7, 8 | `0x6021971e`, `0x6021978a`, `0x602197f6` |
| 9-12 | `0x60219862`, `0x602198f9`, `0x60219980`, `0x60219a26` |
| 13-17 | `0x60219acc`, `0x60219b3c`, `0x60219bce`, `0x60219c3e`, `0x60219cae` |
| 18, 19 | `0x60219d1e`, `0x60219d8d` |
| 20 | `0x60219e0e` |

*Focus drive API, called from the `lens lddrv` handler `0x600f8160`.*

| item | address |
|---|---|
| AF builders 3/`0x2002`, 3/`0x1003`, 3/1 and 3/`0x20` | `0x606b13a2`, `0x606b167d`, `0x606b17f7` |
| AF builders 3/`0x2000`, 3/`0x1000` | `0x606b1bbe`, `0x606b1e93` |
| AF builders 3/2 absolute | `0x606b2045`, `0x606b2074` |
| AF builders 6/`0x21`, 3/10, 3/`0x1002`, 3/`0x10` | `0x606b2309`, `0x606b2550`, `0x606b26e8`, `0x606b294e` |
| `fcs_lens_*` | `0x606cd083` to `0x606ce201` |
| aperture target, stored value | `0x602035a8`, `0x620a7774` (+10) |
| aperture builders 2/1, 2/`0x2000`, 2/`0x2004` | `0x6021b807`, `0x6021b8bb`, `0x6021ba3d` |
| shell `lens aperture`, aperture code | `0x600f138d`, `0x60202c2f` |
| shell `lens zoom` | `0x600f8c81` |
| Sync IS flag check, flag function | `0x6020d42e`, `0x6020d2cd`(2, 8) |
| private function send, copt flag store | `0x602072f5`, `0x602075d7` |

*AF, aperture, zoom and IS callers.*

| item | address |
|---|---|
| section table (flash copy, runtime) | `0x60250238`, `0x61e8b778` |
| section printers, LAF printer | `0x600f1f45` to `0x600f47e9`, `0x600f61d2` |
| Panasonic lens-IS status check | `0x6020d094` |
| Olympus, Panasonic private-set selection | `0x6020d73a`, `0x6020d782` |
| focus-stacking lens-type check | `0x60206a03` |
| function flag users (page 1 bit 26, page 2 bit 3) | `0x6020d394`, `0x6020d42e` |
| OM-5 II wire table, `lens_info` pointer | `0x601bf998`, `0xa26cf7b8` |
| OM-5 II serial block write sites | `0x6022e000` to `0x6022ffff` |

*`lens_info` and other bodies.*

<details><summary>All 34 lens shell sub-commands</summary>

| sub-command | handler |
|---|---|
| set, reset | `0x600f0efb`, `0x600f12ab` |
| aperture, still, focus | `0x600f138d`, `0x60569464`, `0x600f147e` |
| askdata, ctrl, data | `0x600f1676`, `0x600f179a`, `0x600f1b98` |
| fav, pow, mtdet | `0x600f6ce3`, `0x600f6d4a`, `0x600f6d62` |
| llpsw, polling, firmup | `0x600f6d7a`, `0x600f6d92`, `0x60565f0f` |
| zoomdrv, lensmem, sync | `0x6010122f`, `0x6021d928`, `0x602224cd` |
| state, cs, ssc | `0x601009f7`, `0x600f6e9e`, `0x602204ca` |
| ois, trouble, com | `0x60207a53`, `0x60207af3`, `0x600f7022` |
| zaf, exif, is | `0x600f75ac`, `0x600fa08b`, `0x600f7752` |
| current, lddrv, ldinfo | `0x60207cd0`, `0x600f8160`, `0x600f8924` |
| blcis, zoom | `0x600f8b05`, `0x600f8c81` |
| dbginfo, log | `0x600f0e28`, `0x600f1056` |

*Handlers of the `lens` sub-commands, dispatched from `0x600f095e`.*

</details>

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. Offsets in the `lens_info` table added in a second pass from the asm of the section printers, 2026-11-25.
[^fw2]: Compared with the OM-5 II 1.1 firmware by function shape, 2026-11-25.
[^fw3]: Applied in our Ghidra project, 2026-11-25.
[^inf1]: Inferred, 2026-11-25.
[^fix1]: Read in the firmware, 2026-11-25. Corrects the earlier reading of "command 41" as a wire command.

## History

- 2026-11-25: the Sync IS "command 41" was read as a wire command at first. It is private function number 41.
- 2026-11-25: the meaning of the `L_ID` bytes at `+0x444` was a guess in earlier notes. They are the start of the lens
  ID, and bytes 0-1 select the private set.

