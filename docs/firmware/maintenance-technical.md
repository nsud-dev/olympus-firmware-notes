# Maintenance layer: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Maintenance layer](maintenance.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the service side of the firmware. That is where the camera keeps its factory data, pixel-defect
maps, fault (damage) history and counters, and how faults are recorded. It also covers the self-adjust, pixel-mapping
and life-test modules. The work is desk research with no camera runs and no flash writes.[^fw1]

A read-only tool, `health.py`, reads out every store below from a flash dump.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, amber = a correction.

## Maintenance stores

All maintenance stores are property stores with a get and a set function.[^fw1] See also:
[Settings and menus](settings-and-menus.md).

- Each flash bank has an 8-byte header `{u16 store id, u16 check, u32 save counter}`. The bank sums to 0 as u16
  words.[^fw1]
- The load rejects a bank whose id or sum is wrong. It then starts the store from its defaults.[^fw1]
- The save writes stores 17, 50 and 63 only when their image differs from the bank.[^fw1]
- **The fd1 and fd2 saves do not compare. They rewrite the whole bank and bump its counter on every adjust-group
  save.**[^fix1]

| store | id | size | layout | holds |
|---|---|---|---|---|
| adjust (factory calibration) | 17 (`0x11`) | 128 KB | tagged records | serials, sensor OB and gains, WB, IS centre, accelerometer, eye sensor, audio |
| **fd1** (first defects) | 2 | 384 KB (`0x60000`) | packed | pixel-defect list 1, phase-detect pixel defects, saturation levels, on-sensor AF tables |
| **fd2** (defects 2-13) | 1 | 1.375 MB (`0x160000`) | packed | pixel-defect lists 2-13, vertical-defect compensation |
| user settings | 50 (`0x32`) | 256 KB | packed | every menu setting, and the **damage history** (below) |
| counters | 63 (`0x3f`) | 64 KB | packed | shutter count R and counters S, U, B |

*The maintenance stores. Flash banks, set-up functions and RAM copies are in the address reference.[^fw1]*

See also: [where R is stored](../hardware/shutter-technical.md#where-r-is-stored).

Packed means values in registry order without ids. Each value is aligned to its own size (u16 on 2, u32 on 4).[^fw1]

- The defect registries are plain `{u16 prop, u16 count}` lists with no defaults. The store-50 and store-63
  registries are not like that.[^fw1]
- Two more registries and a 56-byte store have no flash bank.[^fw1]
- So flash window A is entirely maintenance and settings data.[^fw1]

### fd1 and fd2 contents

The names come from the adjust CSV index.[^fw1]

| prop | name | count × size | in |
|---|---|---|---|
| `0x7044` | PRM_CCD_FIRST_PIXELDEFECT_ADDRESS | 10400 × u32 | fd1 |
| `0x7054` | PRM_CCD_FIRST_PIXELDEFECT_SIZE | 24 × u32 (entry counts per list) | fd1 |
| `0x7064` / `0x7072` | PRM_CCD_FIRST_VERTICALDEFECT_ADDRESS / SIZE | 1 / 1 | fd1 |
| `0x7192` | PRM_CCD_SATURATION_LEVEL | 23 × u16 | fd1 |
| `0xb94a` / `0xb95a` | PRM_AF_ZAF_RL_TABLE / PRM_AF_ZAF_TB_TABLE | 49152 × u16 each | fd1 |
| `0xb964` / `0xb974` | PRM_CCD_FIRST_PD_PIXELDEFECT_ADDRESS / SIZE | 400 × u32 / 4 × u32 | fd1 |
| `0x7144`, `0x7154` | PRM_CCD_FIRST_PIXELDEFECT_ADDRESS2, 3 | 52000, 5200 × u32 | fd2 |
| `0x7a64`–`0x7af4` | PRM_CCD_FIRST_PIXELDEFECT_ADDRESS4-13 | 9 × 30000 and 6500 × u32 | fd2 |
| `0x7b02` / `0x7b12` / `0x7b22` | PRM_COMP_VERTICALDEFECT_LEVEL / X / CNT | 250, 250, 1 × u16 | fd2 |

*Properties in the two defect stores.[^fw1]*

- Each defect list is sorted by its low halfword. An entry is a u32 with bit 31 set and two packed
  coordinates.[^inf1] Which half is x and what bits 16-30 hold is not traced.
- `0x7054` holds the used length of each list. Entries 11-22 equal the filled lengths of the 12 fd2 lists
  exactly.[^fw1] The last entry (201180) is total-like but does not match a simple sum.[^fw2]
- The "ZAF" RL and TB tables (right-left and top-bottom) are the on-sensor phase-detect AF calibration.[^inf2] So fd1
  is AF calibration as well as defect data.
- The camera's own debug names are `CAM.Defect1` (fd1, factory), `SELF.Defect2` (self-adjust) and
  `CAM.DefectAll`.[^fw1] The self-adjust items `ADJ_SLF_DEFECT1` and `DEFECT2` (below) fill them.
- During section loading at boot, one function loads fd1 and another loads fd2. They set ready bits `0x800` and
  `0x1000` in the progress word.[^fw1]

### Writers of the defect maps

The save request takes a `{u16 type, ...}` record. With type 1 and halfword +4 set, it saves the **adjust group**.[^fw1]

1. Store 17, only if changed.
2. fd1, unconditionally.
3. fd2, unconditionally.

The save request has 20 callers. Among them are the shell `w`, the `acc flash write` path, the power-down path and
code in the adjust-command area.[^fw1]

Checked request by request, only these set type 1 with +4.[^fw1]

- The shell commands `w` / `acc_adj` (in the shell table) and one more shell path.
- The adjust-property setter. It is used for destination area `0x0aa2` and Hebrew mode `0xbbc1`, as on the OM-5.
- The adjust-command dispatcher. It builds the store mask from bits 1/2/8/16. Replies use PTP-style codes `0x2001` /
  `0x201d`.

So the dispatcher is the service-tool command path. Self-adjust and Pixel Mapping likely share it.[^inf1]

Power-down, the record path and the settings saves do **not** set +4.[^fw1] Type 0 reloads stores. A separate
function resets all stores and restarts.[^fw1] So nothing in ordinary shooting or power-off writes the defect
maps.[^fw1]

The flash guard allows window A while the camera runs normally.[^fw1] See also:
[Recovery](recovery-technical.md).

## Damage (fault) history

### Where it is stored

- The history is **property `0x8072`, 5 × u16, in user-settings store 50** (packed offset 912). It is not in the
  counter store and not in the calibration store.[^fw1]
- Shell `damage` prints the number of non-zero entries and each entry. Its strings are `damage num:` and
  `damage info:`, and its usage is `[DAMAGE COMMAND] get`. It only reads.[^fw1]
- `Maintenance::getDamageInfo` / `clearDamageInfo` (`OlyApiMaintenance.cpp`) and the hidden page `Damage Info` read
  and clear the same history.[^inf3]

### How a fault is recorded

1. **Report.** The report function takes the code and has 35 call sites. It does nothing until the damage system is
   up. A halfword flag marks that, and while it is unset the function prints `damage_info uninitialized!`.[^fw1]
2. It looks the code up in the **damage-code list** (342 u16 codes, 0-ended). A code not in the list is
   ignored.[^fw1]
3. It then looks in the **exception list** (290 codes). A listed code is recorded silently (`[damage info]:Damage
   OFF`). Any other code is a **fatal damage** (`[damage info]:Damage ON : %x`).[^fw1]
4. **Record.** The record function takes the code and a fatal flag. It adds the code to the 5-slot history under a
   lock. It fills the first empty slot, skips a code equal to the newest entry and drops the oldest when full.[^fw1]
5. If the code is fatal, it posts event `0x040b0080` with the code.[^fw1] The camera then shows its damage screen and
   powers off. The strings for this are `return from shutDown : Power OFF by DAMAGE`,
   `API_SHUTDOWN_REASON_DAMAGE = 0x02`, `EV_DAMAGE_OCCURRED` and `startDamageSubAppStateMisc`.[^fw3]

The history is saved with store 50. So it reaches flash at the next settings save (power-down).[^inf1]

### Fatal and silent codes

The 52 fatal codes are these.[^fw1]

`0e19 1f60 3402 3404 3406 3408 340a 3b13 3c85 4782 5c81 5e02 5f02 5f04 5f05 5f08 5f0a 5f0c 5f0e 5f10 8222 8223
8227 8233 8234 8235 8236 823f 8241 8261 8262 8263 8267 8805 8807-880d 8903-890b 9601 9602`

The 290 silent ones include the codes below and the whole block `a601-a6ff`.[^fw1]

`0e18 1700-1703 2c00 2c01 2c04 2c40 2e0c 2e0d 310e-3110 3b83 5f20 5f21 6002 6004 8228-822a 823c 8264-8266 8281-8283
8806 8f01 9603 9604 9701 9702`

Known groups and callers are below.[^fw1]

| codes | reported by |
|---|---|
| `0x88xx` / `0x89xx` | the shutter (mec driver). One function reports `0x8806` at once, unless property `0xc222` is 2. It parks the others for the still sequence to report. |
| `0x310f` / `0x3110` | boot, after the step with argument `0x9004` fails |
| `0x823f` / `0x8241` / `0x8262` | code after an error from one function. Which device it opens is an open question. |
| `0x2c00` / `0x2c01` | two functions next to `stb_debug.c`, likely the flash unit[^inf1] |
| `0x3b83` | one function |
| the code in its message (+8) | the power-down path, when bit 1 of its flags is set |

*Known fault code groups and where they are reported.[^fw1] The address reference has each caller.*

See also: [Shutter damage state](../hardware/shutter-technical.md#damage-state).

- Codes `0x1a80` and `0x1a81` (`api_*.c`) are not in the list, so they are never recorded.[^fw1]
- What each code means is not traced. The `a6xx` block (all silent) is the largest group.[^fw1]

### OM-5 II

The OM-5 II uses the same mechanism.[^fw1]

- Its code list has 343 codes and its exception list 291.
- The only difference is one extra silent code, **`0x3108`**. The fatal set is identical.
- Property `0x8072` (5 × u16) is in its settings store (id `0x17`).

### Shutter "disabled" flag

The shutter damage state starts at 2 (DISABLE) if property `0x7261` is non-zero.[^fw1] See also:
[Shutter damage state](../hardware/shutter-technical.md#damage-state).

Property `0x7261` is in a registry that has no flash bank (default 0). So it is most likely a fixed value in the
program, not a stored flag.[^inf1] Property `0xc222` is in the same table (default 1).[^fw1]

## Self-adjust

Self-adjust is the factory and service adjustment menu.[^fw1]

- The API is `OlyApiSelfAdjust.cpp`, with `SelfAdjust::execute`, `getMenuItem`, `getResultInfo`, `turnOnLed`,
  `playSoundAsync` and more.
- The GUI is `userGuiSelfAdjust`.
- The states are `ID_ST_SELFADJ_*`, the events `EVT_SELF_ADJ_*` and the sub-app
  `startSelfAdjustMenuSubAppStateMisc`.

The shell `sdk api` help lists 45 items. They are the same in the OM-5 II.[^fw1]

| range | items |
|---|---|
| 0-9 | AF LED check, BC gain start/1/2, BC centre and centre MTN (IS), camera, camera ISO and ISO wait, camera spectra |
| 10-13 | camera BV, dark noise, **DEFECT1, DEFECT2** (pixel-defect lists, fd1 and fd2) |
| 14-22 | accelerometer (simple, temperature start/through, 1-4) |
| 23-27 | USF (dust-reduction ultrasonic filter) pre, main 1/2, end |
| 28-34 | audio (rec, start, main, calc), touch panel |
| 35-36 | parameter download / upload (`PRMDOWNLOAD` `0x10000a00`, `PRMUPLOAD` `0x10000b00`) |
| 37-44 | QC checks: SDIO, self (keys, dials, LED), PBH (keys, dial) |

*The 45 self-adjust items.[^fw1]*

The GUI shows a release count and an adjust count (`SetReleaseCount`, `SetSelfAdjustCount`). It has a serial-number
entry screen (`UpdateSelfAdjustSerial`, alphabet 0-9 A-Z).[^fw1] Running items writes calibration (the adjust
group).[^inf1] It is not to be run.

## Pixel mapping

- The API is `OlyApiPixelMapping.cpp`, with `PixelMapping::execute` and `canPixelMapping`.[^fw1]
- Wi-Fi has the event `EV_WIFI_REQ_PIXELMAPPING`, and `PIXELMAPPING_REQ 14` / `PIXELMAPPING_COMPLETE 15`.[^fw1]
- The sensor side is `cam_defect*.c` (shell `cam defect [Mode] [Proc] [clip_y]`).[^fw1]
- The AF defect build is `fcs_ip_defect_pixel` (`[FCS_IP_DEFECT_PIXEL]build done. cnt =`).[^fw1]
- Error prints are `**ERR_NEAR_DEFECT**` and `**ERR_DEFECT_COUNT**`.[^fw1]

Results go to fd1 and fd2 through the adjust-group save.[^inf4]

## Life tests

The life tests are `OlyApiLifeTest.cpp` and a sequencer.[^fw1]

- `OlyApiLifeTest.cpp` has `LifeTest::execute`, `getLifeTestMode`, `getLifeTestCount`, `abortLifeTest` and `reset`.
- The sequencer is the 424-function `OlyHfwOpeLifTst*.cpp`.

| mode | number |
|---|---:|
| LED on / blink / off | 3–5 |
| sleep time | 15 |
| control shutter | 17 |
| camera mode | 21 |
| ISO | 22 |
| durable shutter | 230 |
| ND filter | 232 |
| aperture | 233 |
| anti-shake | 245 |
| focus | 246 |
| mirror frame 1 / 2 | 247 / 250 |
| lens cover | 248 |
| flash strobe | 249 |
| CCD | 251 |
| AF LED | 256 |
| battery life | 301 |
| movie sound | 302 |
| AF shutter sound | 303 |
| self-time check | 999 |

*Life test modes.[^fw1]*

Each endurance loop reads the damage list after each cycle and stops on a hit. The print is `>>> SHUTTER_LIFETEST
ERROR : GetDamage`, and the same for strobe, ND filter, mirror frames, lens cover, focus, CCD, aperture and
anti-shake.[^fw1]

The tests are started from the debug menu (`Life Test Start`). The callbacks are `CBC_LIFE_TEST` start, end, cycle end
and charge.[^fw1] These tests wear the camera on purpose. They are not to be run.

## Maintenance API

`OlyApiMaintenance.cpp` is a singleton.[^fw1] It provides the following.

- API version, system names and versions, shipping info.
- `getMaintenanceData`, the R/S/C/U/V/B/L page. See also:
  [where they are read](../hardware/shutter-technical.md#where-they-are-read).
- Serial number, and damage info get and clear.
- Firmware update (file and card, battery check).
- GPS module version.
- Destination (sales region) get, set and change.

The maintenance modes are RELEASE, STROBE, CLEANING, USF, LIVEVIEW, LIFE_TEST and BLUR.[^fw1] Wi-Fi can start a
maintenance session (`EV_WIFI_REQ_START_MAINTENANCE`, `notifyStartWiFiMaintenance`).[^fw1]

## Read-only health checks

These are safe ways to read the camera's health. None of them write anything.[^fw1]

- From a flash dump (FDMP `FL0.BIN`), `health.py` decodes stores 17, fd1, fd2, 50 (damage history) and 63.
- Over the Wi-Fi debug shell, use `damage` (history), `mec info` (shutter damage state) and `sdk` (maintenance page
  counters).

> [!WARNING]
> Avoid `mec dmgclear/dmgset`, any self-adjust item, the life tests and the `flash` commands.

## Open questions

- What each damage code means, and which device each group belongs to.
- Which device the code after the `0x823f` / `0x8241` / `0x8262` error opens.
- The bit layout of a defect entry, the meaning of size-table entry 23, and what fills each of the 13 lists.
- Which of the 20 adjust-group save callers are Pixel Mapping and self-adjust.
- Whether the body runs pixel mapping by itself. No automatic caller of the defect-map save was found.[^fw1]

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 II 1.1 is named.

| store | flash | set up at | object | RAM |
|---|---|---|---|---|
| adjust (17) | `0x40060000` | `0x6005bfe7` | `0xa2637864` | `0xa276e000` |
| fd1 (2) | **`0x40080000`** | `0x6005c279` | `0xa2637878` | `0xa278e000` |
| fd2 (1) | **`0x400e0000`** | `0x6005c37d` | `0xa263787c` | `0xa27ee000` |
| user settings (50) | `0x40240000` / `0x40280000` | `0x6005bfe7` | `0xa2637870` | |
| counters (63) | `0x402c0000` / `0x402e0000` | `0x6005bfe7` | `0xa263786c` | |

*Maintenance store banks, set-up functions and RAM.*

| item | address |
|---|---|
| property get / set | `0x6005ce6b` / `0x6005cf1c` |
| store save (stores 17, 50, 63) | `0x6005aaaf` |
| fd1 save / fd2 save | `0x6005ab3d` / `0x6005ab8c` |
| defect registries | `0x600bd008`, `0x600bd038` |
| registries without a flash bank | `0x60079310` at `0xa263785c`, `0x60090164` at `0xa2637860` |
| 56-byte store without a flash bank | `0x60079294` |
| registry holding properties `0x7261` and `0xc222` | `0x60090164`, installed at `0xa2637860` |
| flash window A | `0x40060000` to `0x40300000` |
| adjust CSV index | `0x613a929a` |
| defect debug name strings | `0x613a4fb6` to `0x613a500e` |
| fd1 load / fd2 load at boot | `0x600455e5` / `0x60045652` |
| progress word | `0xa265658c` |

*Stores and loading.*

| item | address |
|---|---|
| save request | `0x6005d4c9` |
| `acc flash write` path | `0x60062e44` |
| power-down path | `0x60128eb1` |
| other callers | `0x61232b3f` to `0x61233fce`, `0x612a729b` |
| shell `w` / `acc_adj` | `0x60062706` |
| shell table | `0x614452cc` |
| other shell path | `0x6006437e` |
| adjust-property setter | `0x602e8306` (via `0x60878e66`) |
| adjust-command dispatcher | `0x61231eaf`, `0x61234f7b`, `0x61236d39` |
| store mask builder | `0x61232cab` |
| record path (no +4) | `0x603045c1` |
| settings saves (no +4) | `0x602e74cc`, `0x602e7556`, `0x601fc960` |
| type 0 reload | `0x6005d771` |
| reset all stores and restart | `0x6005bba6` |

*Adjust-group save and its callers.*

| item | address |
|---|---|
| user-settings registry | `0x60098998` |
| shell `damage` handler | `0x60163489` |
| `damage num:` / `damage info:` strings | `0x601e0270` |
| non-zero entry count | `0x60163505` |
| `OlyApiMaintenance.cpp` name strings | `0x60ab2c6c` / `0x60ab2c87` |
| hidden page `Damage Info` | `0x60808e37` |
| report function | `0x60023e60` |
| damage-system-up halfword | `0x8ff001a4` |
| function that sets it | `0x60023e55` |
| damage-code list | `0x601e02a0` |
| exception list | `0x601e054e` |
| record function | `0x60023f09` |
| fatal event post | `0x60046008` |

*Damage history.*

| codes | reporter | address |
|---|---|---|
| `0x8806` and parked `0x88xx` | shutter reporter | `0x60227262` |
| parked shutter codes | park variable | `0x62107954` |
| parked shutter codes | still sequence | `0x602b86a0` |
| `0x310f` / `0x3110` | boot | `0x600218c1`, `0x60021cc7` |
| `0x310f` / `0x3110` | failing boot step | `0x60021f26` |
| `0x823f` / `0x8241` / `0x8262` | reporters | `0x6011359f` to `0x60113963` |
| `0x823f` / `0x8241` / `0x8262` | function returning the error | `0x6005f9c9` |
| `0x2c00` / `0x2c01` | reporters | `0x6016cf28`, `0x6016dbcf` |
| `0x3b83` | reporter | `0x6042545f` |
| `0x1a80` / `0x1a81` (never recorded) | caller | `0x603132b8` |
| message code | power-down path | `0x60128eb1` |

*Fault code reporters.*

| item | address |
|---|---|
| report region (OM-5 II) | `0x60024485` |
| damage flag (OM-5 II) | `0x8ff001a0` |
| code list, 343 codes (OM-5 II) | `0x601f5284` |
| exception list, 291 codes (OM-5 II) | `0x601f5534` |
| settings registry (OM-5 II) | `0x600a0668` |

*OM-5 II damage history.*

| item | address |
|---|---|
| `OlyApiSelfAdjust.cpp` names | `0x60ab2828` to `0x60ab2acc` |
| `userGuiSelfAdjust` prints | from `0x61105524` |
| `ID_ST_SELFADJ_*` states | `0x610fad7b` |
| shell `sdk api` help | `0x60aed2xx` |
| `OlyHfwOpeLifTst*.cpp` sequencer | `0x60b04501` |
| life test modes | `0x60af219d` |
| `Life Test Start` | `0x610b4928` |
| `OlyApiMaintenance.cpp` singleton | `0x61e9b87c` |
| maintenance modes | `0x60af288c` |

*Self-adjust, life tests and the maintenance API.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25.
[^fw2]: Read in the firmware, partly inferred, 2026-11-25.
[^fw3]: Strings read in the firmware, 2026-11-25. The chain from the event to the power-off is inferred.
[^fix1]: Corrected on 2026-11-25. Read in the firmware. See [History](#history).
[^inf1]: Inferred, not traced to the end, 2026-11-25.
[^inf2]: Inferred from the names and the 2 × 49152 size, 2026-11-25.
[^inf3]: Inferred, 2026-11-25. The API was not traced to the property.
[^inf4]: Inferred, 2026-11-25. It matches the DEFECT1 and DEFECT2 items and the save counters.

## History

- 2026-11-25: corrected. The fd1 and fd2 saves do not compare before writing. They rewrite the whole bank on every
  adjust-group save.

