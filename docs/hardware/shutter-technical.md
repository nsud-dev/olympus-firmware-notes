# Shutter: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Shutter](shutter.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the mechanical shutter driver, which the firmware calls "mec", and its hardware block. It also covers
the still-sequence states that use the driver, the shutter types, the anti-shock flags, the factory timing data, the
shutter count and the shutter damage state. It is desk research. Nothing here was run on the camera.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 1.2 or OM-5 II 1.1 is named. OM-5 II
addresses are in its expanded block0.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred.

## Layers

| layer | where | what |
|---|---|---|
| mec driver | always-loaded code, `0x600e0000`-`0x600ef000` | motor, magnets, sensors, request objects, events (`mec_ev.c`), semaphores (`mec_sem.c`), log (`mec_log`), damage state, release count |
| cam layer | `cam_mec_ctrl.c`, `cam_shutter.c`, `cam_motor.c`, `cam_stl*.c` | still sequence (Ready / Take / TakeEnd / Charge), shutter type per frame |
| shooting sequencer | `takepic.c`, StlTake ([shooting sequencer](../firmware/shooting-sequencer.md)) | drive mode, anti-shock, silent, counters S and B |
| maintenance API | `OlyApiMaintenance.cpp` | counters for the hidden maintenance page, damage info, life tests |

*The software layers that touch the shutter.[^fw1]*

## The hardware block

- **One driver.** The mec driver is the only code that addresses **`0x9ba00000`-`0x9ba004c0`**. There are 358
  absolute operands, all inside the driver, for example `0x9ba00008`, `0x9ba00060` and `0x9ba00434`-`0x9ba004b8`. The
  base `0x9ba0000c` is loaded 15 times.[^fw1]
- **Clock.** The SoC clock list has a **CLKMECHA** entry, shown by the shell's `per clk`.[^fw1] That this clock feeds
  the shutter block is inferred.[^inf1]
- **OM-5 II.** Its mec driver at `0x600f0000` has the same 358 operands.[^fw1]

The register groups below are sorted by the function that touches them.[^fw1] The roles are inferred from the
callers.[^inf1]

| offsets | role |
|---|---|
| `0x000`-`0x004` | block enable on the first and last shutter client |
| `0x030`-`0x038` | set up at client open and after every request post |
| `0x008` | common status or control word, read by most functions |
| `0x05c`, `0x060`-`0x0c4` | written by the request post routine after each request. The step program of the request[^inf1] |
| `0x110`-`0x158`, `0x15c` | motor and PWM side[^inf1] |
| `0x180`-`0x1ac` | the same callers as the motor and PWM group |
| **`0x254`-`0x348`** | **`lsnc`**, two channels `0x78` apart (per-channel words `0x260`/`0x2d8`, `0x274`/`0x2ec`, `0x278`/`0x2f0`) |
| `0x36c`-`0x4cc` | two banks of timing and pulse registers (`0x36c`.., `0x414`..), used by the request handlers |
| `0x4f8`-`0x4fc` | |

*Shutter block register groups. The functions for each group are in the [address reference](#address-reference).[^fw1][^inf1]*

The bit meanings are not mapped. The OM-5 II touches the same offsets.[^fw1]

## Shell command `mec`

The `mec` shell command has a handler table of `{char *name, handler}` pairs and its own help text.[^fw1]

| sub-command | sub-sub-commands |
|---|---|
| info | prints Shutter Client, Damage Info, PCNT, EVENT, SEM, LOG sections |
| motor | open, close, on, off, ready, openchg, closechg, initial, init_on, init_off |
| shutter | open, close, on, off, ready, set, darkset, set_efs, start, stop, 1strun, 2ndrun, prmout |
| still | `mec still [num] [expose_time[us]]`, runs motor and shutter steps in order |
| lsnc | open, close, start, prm_chg, abort, reset, prm_chk, state_chk, pls_cnt_chk |
| dbglog, mem, test, error, init | |
| dmgclear, dmgset | set the damage state to 0 / 1 |

*`mec` sub-commands. Handler and table addresses are in the [address reference](#address-reference).[^fw1]*

- **Shutter syntax.** `mec shutter start [0 Normal, 1 Dark] [Not Run Curtain] [Expose Time ms, none = forever]`,
  `mec shutter set [expose_time us] [0 Normal, 1 Dark]` and `mec shutter 1strun / 2ndrun`. The type print says
  `0 NML, 1 Dark, 2 EFS`.[^fw1]
- **prmout.** `mec prmout [pwm_mode] [bc_mode] [drive_continue_mode]` prints `MEC_CONTROL_PRM`. Its fields are
  MS_AEAFEN, MS_NEXTSEQ, MS_SHTCHGTIMER[0..1], MS_BREAKWAIT, MS_CHG_MG_WAIT, MS_READY_PI_TYP and MS_CHARGE_PI_TYP. Its
  help names the parameters `sht_type` (0 EFS, 1 MECHA), `release_type` (0 HS, 1 NORMAL) and `drive_continue_mode`
  (0 NORMAL, 1 HIGH).[^fw1]
- **lsnc.** `lsnc` is a two-channel pulse generator synced to the sensor. Per channel it has a start/repeat phase, a
  pulse-change count (0 = infinite), VD cycle, VD delay, delay count, and HD and VD polarity (falling, rising,
  both).[^fw1]
- **lsnc is the lens sync generator.** `lsnc start` is also called by the lens-sync code, which prints `SYNC`, Enable /
  Type / Polling / P_wait / Mec and sits next to the lens driver. Its registers are `0x9ba00254`-`0x9ba0034b`.[^fw1] So
  the frame-locked pulse that paces the live-view lens packets comes from the shutter block.[^inf1] See also:
  [lens communication](lens-communication-technical.md).

> [!WARNING]
> These commands move the real shutter. Reading `mec info` is safe. The others are for service use and are not to be
> run from mods.

## Driver internals

- **Init.** The first init sets the damage state (see [Damage state](#damage-state)), sets the shutter-client count to
  0 and sets up the state objects. A second init sets up an object and a release count copy, which is property
  `0x8344`.[^fw1]
- **Shutter client.** A counter of open users. Open adds 1 and powers up on the first user. Close subtracts 1 and
  powers down on the last.[^fw1]
- **Requests.** Public entries build a request from a descriptor and post it. The descriptor table has 111 entries of
  80 bytes each, indexed by index × 80. Word 15 is a kind (1 or 9), word 19 a callback and byte 72 a **count
  flag**.[^fw1]
- **Condition names.** These sit in 39-byte slots: MOTOR_READY A/B, MOTOR_OPEN_CHARGE A-D, MOTOR_CLOSE_CHARGE A-F,
  MOTOR_PWM A, SHUTTER_MOTOR_ON / OFF / CLOSE_CHARGE, MAGNET_BOUND, MAGNET_DARK_BOUND, SHUTTER_MAGNET_ON, MG3_CHANGE,
  SET A/B, DARK_SET A/B, START A/B, SET_SYNC A/B, SHUTTER_MOTOR_MAGNET, INITIAL_INIT_TYPE_COMMON_SEQ and
  INITIAL_INIT_TYPE2. Event objects print as `motor_post`, `sensor_1_pre`, `sensor_2_pre`, `bound_end_pre`, `aeaf_pre`
  and `shutter_post`.[^fw1]
- **What the names show.** The shutter has a charge motor (PWM), at least three magnets (MG3 is named), two
  photo-interrupter sensors and a bounce wait after the curtain run.[^inf1]
- **Log.** `mec_log` writes `LOG` and `CSV` files named `ID_%04X`.[^fw1]

## Still sequence (cam layer)

The event names give one sequence per phase.[^fw1]

| phase | steps (in order of the name table) |
|---|---|
| Ready (STILL_R) | 2nd start, frame-sync interrupt stop, aperture close, exposure delay timer, reset, image start, shutter dark set, **shutter 1st run** |
| Take (STILL_T) | power save on/off, FT capture, DMA shading, VD-reset exposure, VD-reset capture (normal / dark / last), aperture open, last sequence, shutter set dark, **shutter 2nd run**, dark capture |
| Take end (STILL_TE) | aperture open, lens restart, **open charge** |
| Charge ready / end (STILL_CR, STILL_CE) | close charge, aperture close, FT mode change high, send serial, open charge, **mec power on** |
| Expose correct, AEAF | aperture open return/post, half correct, AEAF correct, AEAF enable |

*Still-sequence steps per phase, from the cam layer's event names.[^fw1]*

The status names are STL/RDY, STL/TAK, STL/STP, STL/ABT, STL/CE, STL/CRDY, STL/TE, STL/CAPEN, STL/FCCAP, STL/APREN and
STL/EXPEN.[^fw1]

### Shutter type per shot

- **`cam still` options.** Option 1 has bit 0 dark, bit 1 pack up, bit 2 pack down and **bit 3 antishock**. Option 2
  has continue, fpn, bulb manual, bulb auto, abort ready and abort take.[^fw1]
- **Shutter types in the cam layer.** The still set-up print shows the types the cam layer knows.[^fw1]

| type | bit |
|---|---|
| `efs` | `0x100` |
| `rs` | `0x200` |
| `continue efs_mec` | `0x400` |
| `continue mec_efs` | `0x800` |
| `rs ultra` | `0x1000` |
| `(Digital ND)` with `rs ultra` | `0x80000` |
| L-fastest | `0x40` |

*Shutter types in the still set-up print.[^fw1]*

- **Bursts.** The burst code prints `1ST=EFS` / `1ST=MECHA` and `2ND=MECHA` / `2ND=EFS` per frame.[^fw1] So a burst
  can switch between electronic first curtain and mechanical frames.[^inf1]
- **OM-5 Live ND** forces shutter type 2 (electronic) in code.[^fw1] See also:
  [Live ND](../features/live-nd-technical.md).

### Anti-shock and silent in the drive table

The drive records are 20 records of 64 bytes each.[^fw1]

| words | meaning |
|---|---|
| 0 | sequential |
| 1 | 2 = high speed |
| 3, 4 | self-timer kind (1 = 12 s / 2 s, 5 = custom) and seconds |
| 6 | **anti-shock (♦)** |
| 7 | high res shot |
| 8 | **silent (♥)** |
| 9 | Pro Capture |

*Drive record words.[^fw1]*

- **Which records.** Records 1, 7, 11, 14 and 17 have the anti-shock flag. They are single, sequential L, 12 s, 2 s and
  the custom timer. No high-speed record has it.[^fw1]
- **Anti-shock and EFS.** That anti-shock selects the EFS type is inferred from the `cam still` bit and the EFS
  adjustment data below.[^inf1]
- **OM-5 II.** Its GUI has a `get_1st_normal_antishock` row that the E-M5 III lacks.[^fw1]

## Factory timing data

- **Adjust-store properties.** The adjust-store index (172 rows) lists `PRM_AE_SHTSTTRG` `0x2dea`, `PRM_AE_SHTAFTTRG`
  `0x2dfa` and `PRM_AE_SHTAFTTRG_EFS` `0x331a`. All are 1 byte and in FLASH.[^fw1] They are the shutter start-trigger
  and after-trigger delays, the last one for the electronic first curtain.[^inf1]
- **Self-adjust.** The self-adjust code prints `Adj_Shtafttrg`, `Fast`/`Slow`, `Normal %d,%f` / `EFS %d,%f`,
  `Count,ShutterAdjData`, `ShtTime(%d)` and a test image name `SHTD9360.JPG`.[^fw1] So the factory measures the
  curtain timing per body for normal and EFS shots.[^inf1]

## Shutter count and the other counters

### Where they are read

- The shell's `sdk` system info prints `Maintenance (PAGE 2)` with **R, S, C, U, V, B, L** (`%06d`). Each is
  `Maintenance` vtable slot +44 with index R 0, S 1, C 2, U 3, V 4, L 5, B 6.[^fw1]
- Slot +44 calls a function that fills a struct and picks a field.[^fw1]

| letter | source | increments at |
|---|---|---|
| **R** | property **`0x8344`** (u32) | the mec driver. It adds 1 to its RAM copy, then calls the setter |
| S | property `0x8354` (u32) | `takepic.c`, when bit 3 of halfword +1888 of the shot record is set |
| C | 0 | not used on this body |
| U | property `0x38b4` (u32) | four places in the shot code |
| V | 0 | not used on this body |
| B | property `0x3874` (u32) | `takepic.c`, when halfword +1666 of the shot record is 2 or more |
| L | setting 4514 | |

*The seven maintenance counters, where each comes from and where it is raised.[^fw1]*

Function addresses are in the [address reference](#address-reference).

The increment helper gets the value, adds 1 unless it is `0xffffffff`, and sets it.[^fw1]

- **L is the life-test count.** Setting 4514 is property `0x9464` in the settings map, also in store 63. Most readers of
  setting 4514 are in `OlyHfwOpeLifTstSequence.cpp`.[^fw1] It is 0 on a body that never ran a life test.
- **U, S and B.** U is counted in the shot code (`take` prints, take main and flag manager). S and B are counted
  together in `takepic.c` from two fields of the shot record. Their meanings are not traced.[^fw1]

### When R counts

The post routine adds one to R after posting a request whose descriptor has the count flag (byte 72) set. Four of the
111 descriptors have it, indices 104, 106, 107 and 108.[^fw1]

- **Groups of 8.** The table is built in groups of 8. Code picks a group base (0, 8, 16 ... 104) and adds the
  request's **type byte** (request +4) × 80. The type is checked to be 0 to 6. Types 0, 1 and 4 take one path, and 2,
  3, 5 and 6 the other. Anything else logs error `0x15006001`.[^fw1]
- **Which requests count.** So R counts the group-104 request, sent from four places, with **types 0, 2, 3 and 4**. It
  does not count types 1, 5 and 6.[^fw1]
- **What that means.** The shell prints the shutter type as `0 NML, 1 Dark, 2 EFS`. So a normal or EFS run counts,
  and a dark-frame run (shutter kept shut) does not.[^inf1] Types 3 and 6 take the exposure time minus the value at
  state +72. That fits bulb or time-limited variants.[^inf1]
- **Silent shots.** Because the count is in the mec driver, fully electronic (silent) shots cannot add to R.[^inf1]

### Where R is stored

- **Store 63.** Properties `0x8344` and `0x8354`, `0x38b4` and `0x3874` are in the registry of **store 63**
  (`0x3f`), which has 69 properties up to `0x8344`.[^fw1] It is a separate 64 KB store, not the user settings
  (store 50).
- **In RAM.** The store has an object pointer, a live image and a RAM bank, listed in the
  [address reference](#address-reference).[^fw1]
- **Flash.** There are two banks, **`0x402c0000` and `0x402e0000`**. The bank table entry is
  `{size 0x10000, RAM bank, flash}`. This is the "second store" in data window A.[^fw1]
- **Packed image.** The header is `{u16 store id, u16 check, u32 save counter}`. The values follow in registry order
  **without ids, each aligned to its own size** (u16 on 2, u32 on 4), with strings byte-packed. The whole 64 KB sums
  to 0 as u16 words. R is at image offset 13680, S at 13684, B at 712 and U at 716.[^fw1] This was checked against a
  real flash bank.
- **Save path.** The all-stores save writes it. When that runs is in
  [settings](../firmware/settings-and-menus.md#when-saved-settings-are-written).[^fw1] Whether the
  power-down path saves store 63 is not checked. It probably does, because the save counter was 4118 on one
  body.[^inf1]


### OM-5 and OM-5 II

- **Same counting.** They use the same property ids and the same increment code.[^fw1]
- **Store id.** The OM-5 II keeps the counters in a store with **id `0x4a` (74)**. Its registry has 93 properties up to
  `0x8344`, 24 more than the E-M5 III's 69, inserted ahead of R.[^fw1]
- **Same banks.** It uses the **same flash banks `0x402c0000` / `0x402e0000`**.[^fw1]


## Damage state

- **Values.** The damage state is a halfword. 0 is NORMAL, 1 ERROR and 2 DISABLE. Any other value prints
  `!! DATA BROKEN !!`.[^fw1]
- **At init.** Init sets 2 if the byte behind property **`0x7261`** is non-zero, else 0.[^fw1] `0x7261` sits in a
  registry with no flash bank (default 0). So it is most likely a fixed value in the program, not a stored
  flag.[^inf1] See also: [maintenance](../firmware/maintenance-technical.md#shutter-disabled-flag).
- **Error.** An error sets 1 for the mec error codes `0x8807`, `0x8809`-`0x880d` and `0x8903`-`0x890b`, looked up in a
  hash table of 16 buckets.[^fw1]
- **Refusal.** Every request entry checks the state. If it is not 0, the entry replies with an error instead of
  running.[^fw1]
- **System damage codes.** The system damage-code list (342 codes) contains `0x8805`-`0x880d` and `0x8903`-`0x890b`.
  So mec faults are system "damage" codes that the boot damage report (`[damage info]`) and
  `Maintenance::getDamageInfo` see.[^fw1] The likely split is `0x88xx` for motor and charge and `0x89xx` for magnet
  and curtain.[^inf1]
- **OM-5 II.** It reads the same property `0x7261`.[^fw1]

## Life tests (maintenance layer, shutter part only)

- **Modes.** `OlyApiLifeTest.cpp` has a mode list with CONTROL_SHUTTER 17, **DURABLE_SHUTTER 230**,
  DURABLE_ND_FILTER 232, DURABLE_APERTURE 233, ANTI_SHAKE 245, FOCUS 246, MIRROR_FRAME1/2 247/250, LENS_COVER 248,
  FLASH_STROBE 249, DURABLE_CCD 251, AF_LED 256, BATTERY_LIFE 301 and others.[^fw1]
- **Damage check.** The shutter life test stops on `SHUTTER_LIFETEST ERROR : GetDamage`, so it reads the damage list
  after each cycle.[^fw1] The GUI starts it from the debug menu (`Life Test Start`). Not to be run.

See also: [maintenance](../firmware/maintenance-technical.md), for the damage history, self-adjust, pixel mapping and
life tests.

## Body differences

- **One group fewer.** The OM-5 1.2 and OM-5 II 1.1 have the same descriptor table minus **one group of 8**. All other
  entries are byte-identical, with the count flags at OM-5 II indices 96, 98, 99 and 100.[^fw1]
- **The missing group is dead in the E-M5 III.** E-M5 III groups 40 and 48 are byte-identical. Group 40 is used twice,
  both times in the type-checked picker with the type limited to 0 to 6. **Nothing in the image points into group
  48**, with no 32-bit reference anywhere. Removing either group gives the OM-5 table exactly. The OM-5 code uses the
  same group bases with the same 0 to 6 type check.[^fw1][^fix1]
- **What that means.** So the OM-5 and OM-5 II drive the E-M5 III shutter with the same steps and parameters as stock.
  The difference is an unused leftover in the E-M5 III table, not a hardware difference.[^inf2]
- **Other strings.** The OM-5 and OM-5 II add the condition SHUTTER_MOTOR_CLOSE_CHARGE_CONDITION_B and a
  `DelayInt MEC : CH3` print. The E-M5 III alone has `OBJ_NAME_E_MEC_ADJUST TIMEOUT`. All three have
  `rs ultra (Digital ND)`.[^fw1]

## Open questions

- The physical meaning of each request type.
- The bit meanings inside the shutter block.
- What counters S, U and B count.
- The anti-shock freeze with a pending Live ND log, seen in a Live ND test build. Nothing here explains it. See also:
  [gotchas](../reference/gotchas-technical.md).

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| shutter (MECHA) block | `0x9ba00000`-`0x9ba004c0` |
| mec driver code | `0x600e0000`-`0x600ef000` (OM-5 II `0x600f0000`) |
| `cam` shell help | `0x6144d38a`..`0x6144d570` |
| StlTake | `0x602b34c6` |
| maintenance singleton, vtable | `0x61e9b87c`, `0x60ad61f4` |
| CLKMECHA string | `0x61447fb6` |

*Blocks and layers.*

| offsets | functions |
|---|---|
| `0x000`-`0x004` | `0x600e47c1`, `0x600e489a`, from client open `0x600e2df4` and close `0x600e2e3d` |
| `0x030`-`0x038` | `0x600e4812` |
| `0x05c`, `0x060`-`0x0c4` | `0x600e594e`, `0x600e595a`, written after the post routine `0x600e92f1` |
| `0x110`-`0x158`, `0x15c` | `0x600e557c`, `0x600e5733`, called from `0x600eb5d6`..`0x600eb845` |
| `0x180`-`0x1ac` | `0x600e5749` |
| `0x254`-`0x348` | `0x600e5c73`, `0x600e6428`, `0x600e63fc`, `0x600e6412` |
| `0x36c`-`0x4cc` | `0x600e6449`, `0x600e4b80`, `0x600e70be`, `0x600e70c9`. Request handlers `0x600e406a`-`0x600e40ab` and `0x600ea5e8` |
| `0x4f8`-`0x4fc` | `0x600e5516` |

*Functions per register group.*

| item | address |
|---|---|
| `mec` handler table, help text | `0x61448df8`, `0x6144902c` |
| info, motor, shutter, still, lsnc | `0x614068eb`, `0x6140695c`, `0x61406cd3`, `0x614074b0`, `0x61407521` |
| motor, shutter, lsnc sub-tables | `0x61448e9c`, `0x61448f20`, `0x61448fbc` |
| dbglog, mem, test, error, init | `0x6140806e`, `0x614080fc`, `0x61408114`, `0x61408202`, `0x61408216` |
| dmgclear, dmgset and the functions they call | `0x614081e6`, `0x614081f4`; `0x600e3f09`, `0x600e3f13` |
| `lsnc start` | `0x600e7a11` |
| lens-sync code | `0x60223acd`-`0x60223e35` |

*Shell command `mec`.*

| item | address |
|---|---|
| first init | `0x600e2cd7` |
| second init, object, release count copy | `0x600e8500`, `0x620a3108`, `0x620a311c` |
| damage state, shutter-client count | `0x620a2004`, `0x620a2000` |
| request post routine | `0x600e92f1` |
| descriptor table (111 × 80 bytes), index scaling | `0x6019faa4`, `0x600e85b5` |
| condition names | `0x6019f540`-`0x6019f9d2` |
| `mec_log` file name strings | `0x6019fa28`-`0x6019fa85` |

*Driver internals.*

| item | address |
|---|---|
| still event names | `0x6144a86c`-`0x6144b13c` |
| still status names | `0x6144b929`.. |
| `cam still` help | `0x6144c113` |
| still set-up print | `0x6140afc0` |
| burst per-frame prints | `0x6144ebd1`..`0x6144ed0b` |
| OM-5 Live ND shutter type | OM-5 `0x602c48e6` |
| drive records, descriptor | `0x604b81e4`, `0x604d4ee4` |
| adjust-store CSV index | `0x613a92c1` |
| self-adjust strings | `0x6139f42f`-`0x6139f6db` |

*Still sequence, drive table and factory timing.*

| item | address |
|---|---|
| `sdk` system info, counter strings | `0x6080b66b`, `0x60ad58db`-`0x60ad591d` |
| vtable slot +44, its callee, struct source | `0x6080ec49`, `0x60877a8d`, `0x602e77b4` |
| R increment | `0x600e937d` (RAM copy `0x620a311c`, setter `0x6005cf1c`) |
| S increment | `0x602bac49` |
| U increments | `0x602277ba`, `0x602a286b`, `0x602ad5b9`, `0x60556d5e` |
| B increment | `0x602bac5e` |
| S and B counting | `0x602bac3f` |
| L getter (setting 4514) | `0x602e69f9` |
| increment helper | `0x60228021` |
| life-test readers of setting 4514 | `0x6086174f`, `0x608618b7`, `0x60861958`, `0x60861eaf` |
| U shot code (take main, flag manager) | `0x602a1800`-`0x602a3000` |
| counting descriptors 104, 106, 107, 108 | `0x601a1b24`, `0x601a1bc4`, `0x601a1c14`, `0x601a1c64` |
| type check | `0x600e8617` |
| group-104 senders | `0x600e879a`, `0x600e8cd4`, `0x600e9018`, `0x600e9193` |
| exposure time minus state +72 | `0x600e87cb` |

*Counters and when R counts.*

| item | address |
|---|---|
| store 63 registry | `0x60094134` |
| store 63 object pointer, live image, RAM bank, set-up | `0xa263786c`, `0x623c1000`, `0xa298e000`, `0x6005bfe7` |
| bank table | `0x6002f360` |
| all-stores save, stores | `0x6005bba6`, `0xa2637868`-`0xa2637874` |
| OM-5 II R copy, increment, readers | `0x6205f2a0`, `0x600f60f5`, `0x602f5a97` |
| OM-5 II store 74 registry, bank table, RAM | `0x6009b708`, `0x6002f36c`, `0xa2aa5580` |

*Counter store.*

| item | address |
|---|---|
| damage state print | `0x61406703` |
| `0x7261` pointer getter, registry | `0x6005ce41`, `0x60090164` |
| error setter, hash table | `0x600e3d44`, `0x6019f4a8` |
| request entry check, error reply | `0x600e30ad` and siblings, `0x600ee169` |
| system damage-code list, boot damage report | `0x601e02a0`, `0x60023e60` |
| OM-5 II `0x7261` reader | `0x600efd3f` |
| life-test mode list | `0x60af219d` |
| life-test damage string, GUI start | `0x60b04aa3`, `0x610b4928` |
| group 40 users | `0x600e8708`, `0x600e8748` |
| group 48 (unreferenced) | `0x601a09a4`-`0x601a0c24` |
| OM-5 II type check | `0x600f567a` |

*Damage state, life tests and body differences.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. Desk research, no camera runs.
[^inf1]: Inferred, 2026-11-25.
[^inf2]: Inferred with high confidence, 2026-11-25.
[^fix1]: Corrected 2026-11-25. The older reading is in [History](#history).

## History

- 2026-11-25: the eight E-M5 III-only steps were first placed at descriptor indices 37 to 44. The extra entries are an
  unused duplicate group.
- 2026-11-25: open questions answered the same day. The eight E-M5 III-only steps are an unused duplicate group,
  `lsnc` drives lens sync, L is the life-test count, and R counts group 104 with types 0, 2, 3 and 4.

