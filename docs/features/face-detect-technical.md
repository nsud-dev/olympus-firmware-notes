# Face and eye detection: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Face and eye detection](face-detect.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page explains how the stock face and eye detection autofocus (AF) works. It was traced in the stock OM-5 II 1.1
program, read from its update file, and checked against the stock E-M5 III 1.7. It is desk research only, with no
camera builds. Addresses are OM-5 II 1.1 block0 addresses (base `0x60021020`) unless the E-M5 III is named. They are
collected in the [address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Summary

- **It runs on dedicated hardware, not the image engine and not the ARM.** Two main-CPU tasks drive two fixed-function
  detector blocks in the system-on-chip (SoC).[^fw1]
    - The face detector block finds the faces.[^fw1]
    - A second block runs right after it and returns 38 points per face. These are facial parts, from which the eyes
      come.[^fw1] That the points are landmarks is a reading.[^inf1]
- **The face detector uses two "dictionaries".** These are pattern tables of 107 KB and 57 KB. They are loaded at
  boot from a block 2 resource and are byte-identical on the E-M5 III and OM-5 II.[^fw1]
- **The E-M5 III has the same hardware and driver.** The register writers match function for function.[^fw1] The
  E-M5 III build still has debug commands named after Omron's OKAO Vision face library (`face okao commands`,
  `okao_pt_version`, `okao_ss_execute`). The OM-5 II build dropped them.[^fw1]
- **The input** is a small YC picture that the display path writes for the face detector on every live-view frame. The
  names are the display driver function `face_upd_by_img1` and the buffers `IMGBUFF_ALOC_FACE` (`0x1600`) and
  `IMGBUFF_ALOC_FACE_YC` (`0x2c00`).[^fw1] That this buffer is the detector's `ulInAddr` is inferred.[^inf1]
- **The results** go into nine 164-byte face-data records, two of them triple-buffered. They are read through one
  getter.[^fw1]
- **AF reads them through one export function.** It copies faces and eyes into the focus module's candidate slots. Those
  are the same 24-byte slot type that the subject-detection (deep learning, DL) branch uses. Face, touch-face and eye
  each have a slot. The AF target chooser tries the DL branch first and face or eye later.[^fw1]
- **The bird-AF fallback.** Writing our box into the face or eye slot and setting the face bit is possible. But the
  native face path rewrites those slots on every pass from the detector's results. So the DL slots, which our bird-box
  test already uses, remain the cleaner route.[^inf1]

## Tasks

| task | id | CPU and priority | OM-5 II 1.1 | E-M5 III 1.7 |
|---|---:|---|---|---|
| `TSK_FACE_FD` | 14 | CPU0, 55 | stack `0xc00` | stack `0x800` |
| `TSK_FACE_MAIN` | 15 | CPU0, 55 | stack `0xb00` | stack `0xb00` |
| `TSK_FACE_BEAUTY` | 4112 | CPU1 task 16 | playback and selfie beauty, not AF | present |

*The face tasks. Entry points and the code that starts them are in the address reference.*

The tasks are records 14 to 16 of the task table.[^fw1] See also:
[OS and framework](../firmware/os-and-framework.md) for the task ids.

- **FD task loop.** The task waits on the queue `FaceQRFd` and copies each message to a buffer. It takes the job mode
  `job[FD_MODE]`. Mode 0 runs a detection pass on a packet. Mode 1 runs a second routine. The
  `--face_fd_main--` debug print counts `FD_count`, `DT_count` and dropped frames.[^fw1]
- **Event and queue names.**[^fw1]
    - Events: `FaceSEFd/WEFd` (FD done), `FaceSEPd/WEPd` (PD done), `FaceSETk` (tracking), `FaceSEMa` (main),
      `FaceSESp/WESp` and `FaceSETs/WETs`.
    - Queues: `FaceQRFd/QWFd`, `FaceQRMa/QWMa` and `FaceQWFb/QRFb` (beauty).
    - Message channels: `FACE_EXEC`, `FACE_POST`, `FACE_FD`, `FACE_MOV`, `FACE_ST`, `FACE_PT`, `FACE_PD` and
      `FACE_BEAUTY`.
- **Public API.** It has 50 small entry functions. Each logs `(2, n)` through a common logger and calls the worker. For
  example, API 35 is `face_get_display_data`. Shooting, playback and the focus interface call them.[^fw1]

## Detector hardware

### Face detector block

The face detector block's driver has functions to set up, enable, start, read results and clear. The E-M5 III has twins
of them. The set-up copies a 54-byte parameter record. The `DtimgParam list` debug function prints its field
names.[^fw1]

| param field (record offset) | register | note |
|---|---|---|
| `ulInAddr` (+0) | +`0x10` | input picture |
| `ulWorkAddr` (+4) | +`0x14` | work buffer |
| `ucDmaMode` (+8) | +`0x18` | |
| `ucVideoFormat` (+9) | +`0x20` (<<8) | |
| `ucByteOrder` (+10), `usLb` (+12, line bytes) | +`0x4004` (hi, lo) | |
| `ulResultAddr` (+16) | +`0x2c` | result buffer |
| `ulDectionary0/1/NAddr` (+20/+24/+28) | +`0x30`/+`0x34`/+`0x38` | pattern tables ("dictionaries") |
| `ucSdCtrl` (+32) | +`0x3c` | |
| `ucRsz_H/V` (+33/+34) | +`0x24`/+`0x28` | resize |
| `usStartX/Y` (+36/+38), `usSizeX/Y` (+40/+42) | +`0x4008`, +`0x400c` | search window |
| `ulTarget` (+44) | +`0x4010` | |
| `ucDtMinSize0/Dir0`, `1`, `N` (+48..+53) | +`0x40c0`/+`0x40c4`/+`0x40c8` | minimum face size and direction per dictionary |

*The face detector's parameter record and the register each field goes to, as offsets from the block base.*

- Start writes +`0x0c` = 0, +`0x3c` = 1, +`0x00` = 1. Clear writes +`0x08` = 3. Enable writes +`0x0c` = 1,
  +`0x04` = 1.[^fw1]
- **Result format.** The result buffer holds a count per class at +4×class. 8-byte entries start at +128, with +320 per
  class. Each entry unpacks into a 16-byte record.[^fw1]
    - x is bits 16-25 and y is bits 0-9.
    - size is word 1 bits 16-24.
    - Four small fields sit in bits 25-28, 12-14, 9-11 and 0-8. They are likely angle, pose and confidence.[^inf1]
- The FD pass reads the result buffer 8 times.[^fw1]
- The debug `face reg` command names the tunables: dma_mode, image, min and threshold. The `face mdm` dump types are
  bayer, yc, track, normalize and fdtop.[^fw1]

### Second block

The second block's driver has functions to set up, start and read status, with twins on the E-M5 III. It uses the same
control registers (+`0x00` start, +`0x04`, +`0x0c`, +`0x3c`). Its parameter record is shorter, with input, work, mode,
format, result, one dictionary, resize and window.[^fw1]

The FD pass calls it after the face pass and waits on `FaceWEPd`. So it is the `FACE_PD` step.[^fw1]

- Its defaults set the work, result and dictionary addresses, mode 1, format 1, +28 = 640 and +30 = 944.[^fw1]
- Its input is a list of face boxes. One function writes one entry per detected face (position, size) into the work
  buffer.[^fw1]
- Its output count is (reg +`0x4004` low byte) − (high byte) + 1. Then each face has 38 packed (x, y) pairs plus one
  word, unpacked into 154-byte records.[^fw1]
- They are read as 38 facial landmarks (eye corners, nose, mouth). The module derives `r_cx/r_cy/r_size`, `l_...`
  and `main_eye` from them.[^inf1]

## Dictionaries

- At boot, the dictionary loader calls `res_size` and `res_read` on resource `0x800b`. Item 1 goes to dictionary 0 and
  item 0 goes to dictionary 1.[^fw1]
- The default parameter builder sets `ulWorkAddr`, `ulResultAddr` and dictionaries 0 and 1 as above. Dictionary N is 0,
  and is later set from a variable. `ucVideoFormat` is 1 and `ulTarget` is 3.[^fw1]
- Resource group `0x800b` maps through the slot table (entry 10 = 7) to block 2 table entry 7.[^fw1]
- Item 0 is `0x1a200` bytes (107 KB, SHA-256 `25cd641b...`). Item 1 is `0xe200` bytes (57 KB, `ada9bca6...`). Both
  have an entropy of about 7.3 bits per byte. **They are byte-identical on both bodies.**[^fw1]
- The tables are read as a boosted-cascade style face detector of the OKAO generation. They are much smaller than
  a subject-detection network, which has several MB of weights. The table format is not decoded, so retraining for other subjects is an
  open question.[^inf1]

## Input picture

- The display driver keeps a face buffer per display channel and updates it with each frame. The functions are
  `face_upd_by_img1 ch / face_adr / dpu_adr` (with an address pair per channel), `face_upd_by_img1_for_th`, `face_upd`
  and `set_face_ctrl ch / mode`. Their callers are the display channel handlers.[^fw1]
- The buffer ids are `0x1600 IMGBUFF_ALOC_FACE` and `0x2c00 IMGBUFF_ALOC_FACE_YC`, and the name `BUFF_FACEYC`
  appears.[^fw1]
- The reading is that the display path writes a reduced YC copy of the live-view frame, and the FD pass points `ulInAddr` at it.
  The face-data records carry the picture geometry (`w`, `h`, `start_x`, `start_y`, `detect_w`, `detect_h`, `scale`,
  `aspect`).[^inf1]

## Results

The face-data records are read through a getter `(type, &ptr)`. There are 9 types of 164 bytes each. Types 0 and 3 are
rings of three. Their index steps through a table holding {1, 2, 0}.[^fw1]

| type | address |
|---:|---|
| 0 | `0xa26ef0cc` + 164 × slot (3 slots) |
| 1 | `0xa26ef4a4` |
| 2 | `0xa26ef5ec` |
| 3 | `0xa26ef2b8` + 164 × slot (3 slots) |
| 4 | `0xa26ef548` |
| 5 | `0xa26ef690` |
| 6 | `0xa26ef87c` |
| 7 | `0xa26ef734` |
| 8 | `0xa26ef7d8` |

*The nine face-data record types and where each sits in RAM.*

- **Record fields** (`tagFACE_DATA`): `addr`, `w`, `h`, `start_x`, `start_y`, `detect_w`, `detect_h`, `scale`,
  `aspect`, the face list and a count at +132.[^fw1]
    - Per face (`pFdFaceResult`): `center_x`, `center_y`, `size`, `angle`, `confidence`, `pose` and `flg`.
    - Eye fields, in another print: `r_cx/r_cy/r_size/r_confidence`, `l_...`, `dir_up_down/left_right/roll` and
      `main_eye`.
- **Display data** (`face_get_display_data`) is made of three parts.[^fw1]
    - `FaceData`: `num` at +20, `w`, `h`, `start_x/y`, `detect_w/h`, `scale`, `aspect` and `lock_st`.
    - `FaceDisplayData[]`: 8-byte entries {cx, cy, width, height}.
    - `FACE_SELECTED_DATA`: `face_select_frame`, cx, cy, width, height, `face_eye_frame` and `eye_cx/cy/width/height`.
- A variable holds the selected face index, with −1 for none.[^fw1]
- Other face-module state is four lists of 8 × 16-byte boxes, cleared per pass, two mode bytes, and a flag set during a
  detection pass and checked by the display getter.[^fw1]

## How AF uses it

1. **Export.** One face tracking info function is the only code outside the face module that reads the face-data
   records (types 0 and 3). It fills the tracking-info struct with `ready`, `scale`, `face_enable`, `eye_enable`,
   `other_num`, the face box in YC and Bayer coordinates, and the eye box in YC and Bayer.[^fw1]
2. **Focus interface.** The focus interface calls it. Its `IFd:` prints are `hyb_result_flag`, `face_search_flag`,
   `face_tracking_lost_flag`, `face_frame_out_flag`, `face_confidence`, `face_roll`, `face_pose`, `face_enable` and
   `eye_enable`.[^fw1]
3. **Candidate slots.** A refresh function with a mode argument fills them.[^fw1]
    - Mode bit `0x10` or `0x40` fills the face slot and the eye slot, and their rectangles.
    - Bit `0x20` fills the touch-face slot.
    - The AF caller passes mode `0x70`.
    - The slots are the same 24-byte type as the DL body and part slots (+1 valid, +12 x, +16 y, +20 w, +22 h).
4. **Enable bits.** One word holds `0x10` face, `0x20` touch face and `0x40` eye.[^fw1]
5. **Target chooser.** It tries these in order.[^fw1]
    1. Clipped live view, when a special clipped view is active (debug tag `C:clip LV`).
    2. DL subject.
    3. Touch face, when bit `0x20` is set and the slot is valid.
    4. Magnified view (debug tag `C:mag`).
    5. Face, when bit `0x10` is set and the face slot is valid.
    6. Otherwise the normal AF area.
6. **Face or eye.** The face and touch-face branches both end in one routine. It reads the eye slot as well, checks the
   point is inside the usable area and compares sizes before it picks the face or the eye.[^fw1]
   The `fcs_coordinate_set_af_point_face`, `_touch_face` and `_eye` setters write the chosen point. They store a source
   kind (1 face, 2 touch face, then eye), a position, a size and an AF grid point.[^fw1]

The candidate slot table has 16 slots, listed in the address reference. They include face, touch face, eye, a second
stubbed source and the DL body and two part slots.[^fw1]

## Frames on screen

- The AF frame display function draws the DL body and part slots and the second slot set. It does not read the face or
  eye slots.[^fw1]
- After it chooses the main face, the face module calls the frame layer's face notify. That sets bit `0x01` in event
  flag 103 when face frames are enabled.[^fw1]
- The same layer has lock-on (bit `0x02`), a bit `0x08` notify and the AF-target list (bit `0x10`).[^fw1]
- The task that waits on flag 103 and draws the faces is not found yet. No code outside the face module reads the face
  records or display lists directly. No pointer to the display-data getter is stored. So the drawer must take the data
  through a face API call by message or through the face tracking info function.[^inf1]

## E-M5 III and OM-5 II

| item | E-M5 III 1.7 | OM-5 II 1.1 |
|---|---|---|
| detector blocks `0x99600000` / `0x99a00000` and drivers | yes (`0x603e105e`, `0x603e886d`) | yes, same code |
| FD and MAIN tasks, ids 14/15 | yes | yes |
| OKAO debug commands | yes (`face okao commands`) | removed |
| `DtimgParam` print | yes | yes |
| face, touch-face and eye candidate slots, `fcs_coordinate_set_af_point_face/_eye` | no, only `fcs_coordinate_set_af_point` | yes |
| face module code | many functions changed (no exact match for the FD task, FD pass, display getter) | |

*What the two bodies share. Found by matching functions between the two firmware files.[^fw2]*

See also: [Subject detection: technical notes](af-detect-technical.md).

## Open questions

- The face-frame drawing task, the waiter on flag 103.
- The four small FD result fields and the order of the 38 points. Which points become the eyes.
- The dictionary format, and the PD dictionary, which no code in the face module fills directly.

## Address reference

OM-5 II 1.1 block0 addresses (base `0x60021020`) unless the E-M5 III is named.

### Tasks and API

| item | OM-5 II 1.1 | E-M5 III 1.7 |
|---|---|---|
| `TSK_FACE_FD` entry | `0x603f9017` | `0x603e144a` |
| `TSK_FACE_MAIN` entry | `0x603f1d2c` | `0x603da587` |
| `TSK_FACE_BEAUTY` entry | `0x606a5005` | |
| code that starts the tasks | `0x601b1ca4` (ids read from `0x60041360`, `0x60041362`, `0x60041a04`) | `0x6019cdfe` |
| task table (records 14–16) | `0x60038b68` | |
| `FaceQRFd` wait | `0x6040308f`, message copied to `0xa26f0f6c` | |
| FD job mode `job[FD_MODE]` / packet | `0x620fd250` / `0x620fd254` | |
| detection pass (mode 0) / mode 1 routine | `0x603fd71a` / `0x603fe057` | |
| event and queue functions | `0x60402e7e`–`0x60403607` | |
| public API entry functions | `0x60401f47`–`0x6040244b` | |
| API logger | `0x603f4075` | |
| API 35 `face_get_display_data` → worker | `0x6040232f` → `0x603f954a` | |
| focus interface callers of the API | `0x6064xxxx`, `0x606e6xxx` | |

*Face tasks, queues and the public API.*

### Detector blocks and dictionaries

| item | OM-5 II 1.1 | E-M5 III 1.7 |
|---|---|---|
| face detector block | `0x99600000` | same |
| driver: set-up, enable, start | `0x603f8a45`, `0x603f8b54`, `0x603f8b8c` | |
| driver: read results, clear | `0x603f8bdc`, `0x603f8c85` | |
| face detector driver twins | | `0x603e105e`, `0x603e11a4` |
| `DtimgParam list` debug function | `0x603fc7c7` | |
| FD pass result reads | `0x603fda30`–`0x603fdb73` | |
| second block | `0x99a00000` | same |
| second block driver: set-up, start, status | `0x604039a6`, `0x60403a98`, `0x60403ae3` | |
| second block driver twins | | `0x603e886d`, `0x603e8960` |
| call from the FD pass | `0x6040000c` → `0x604036ac` | |
| second block defaults | `0x60403661`: work `0xae6f34c0`, result `0xae6f36c0`, dictionary `0xae6f4fc0` | |
| face box list writer | `0x60403767` | |
| dictionary loader (called from `0x60045914`) | `0x603f8cb7` | |
| `res_size` / `res_read` | `0x60179a13` / `0x6017934a` | |
| dictionary 0 / dictionary 1 in RAM | `0xa43a5540` / `0xa4424a00` | |
| default parameter builder | `0x603fec21`: work `0xae6a8740`, result `0xae6f0c40` | |
| dictionary N source | `0x620fdb34` | |
| resource slot table | `0x601f591e` | `0x601e0817` |
| block 2 table entry 7 in flash | `0x44540000` | `0x45d60000` |

*Detector blocks, drivers and dictionaries.*

### Input and results

| item | OM-5 II 1.1 |
|---|---|
| `face_upd_by_img1` | `0x601a6ce6`, address pairs at `0xa26e1144` + 8×ch |
| `face_upd_by_img1_for_th` | `0x601a6d40` |
| `face_upd` | `0x601a6f84` |
| `set_face_ctrl` | `0x601a7077` |
| display channel handlers | `0x601a4b08`–`0x601a61ca` |
| face-data record getter | `0x603fc07d` |
| ring index / step table {1, 2, 0} | `0x620fdb56` / `0x605786c7` |
| face-data records | `0xa26ef0cc`–`0xa26ef920` |
| `tagFACE_DATA` print | `0x603f4d6e` |
| per-face print (`pFdFaceResult`) | `0x6040173f` |
| eye fields print | `0x603f485f` |
| selected face index | `0x620fdbc8` |
| box lists (8 × 16 bytes) | `0xa26f0090`, `0xa26f0110`, `0xa26f01c8`, `0xa26f0248` |
| mode bytes | `0xa26f0300`, `0xa26f0301` |
| detection pass flag | `0x620fe082` |

*Face buffer updates and result records.*

### AF path

| item | OM-5 II 1.1 |
|---|---|
| face tracking info export | `0x605a27fb`, called through `0x605a2b0a` |
| tracking-info struct print | `0x607a6c03` |
| focus interface (`IFd:`) | `0x606e695b` |
| candidate slot refresh | `0x606d8d56` → `0x606da2c6` → `0x606da2e6` / `0x606da59d` |
| touch-face fill | `0x606da6e5` |
| face slot / touch-face slot / eye slot | `0xa2750f2c` / `0xa2750f44` / `0xa2750f5c` |
| face and eye rectangles | `0xa2751050` / `0xa2751080` |
| enable word | `0xa2750ec0`, set at `0x606d8ee9` (face), `0x606d8ef6` (touch face), `0x606d8f03` (eye) |
| target chooser | `0x60720b36` |
| face-or-eye routine | `0x60720f7e` |
| usable-area check | `0x6072394a` |
| setters face / touch face / eye | `0x606d93e5` / `0x606d954f` / `0x606d96b9` |
| source kind | `0xa2751110` |
| position / size | `0xa2751118`–`0xa2751124` / `0xa2751128` |
| AF grid point | `0xa2751112` (`0x606db18b`) |

*Functions and variables on the AF path.*

| branch | check | handler | slot |
|---|---|---|---|
| clipped live view | `0x6071fdad` (`0x606d8f56` = 4: `0x60469e59` & ~2 == 1 and the special-AF state at `*0xa2766080` +132) | `0x607212ed` | `0xa2750fd4` |
| DL subject | `0x6071ff46` | `0x607213ab` | |
| touch face | `0x6071fdc1` | `0x60720f50` | |
| magnified view | `0x6071fd99` (`0x606d8f77` = 8, from the special-AF state +54) | `0x6072134c` | `0xa2750fec` |
| face | `0x6071fdea` | `0x60720f24` | |
| normal AF area | | `0x607210a1` / `0x60720c82` | |

*Target chooser branches in the order they are tried.*

| slot | address |
|---|---|
| getters | `0x606d8da0`–`0x606d8e27` |
| other | `0xa2750f1c`, `0xa2750f26` |
| face | `0xa2750f2c` |
| touch face | `0xa2750f44` |
| eye | `0xa2750f5c` |
| other | `0xa2750f74` |
| second stubbed source | `0xa2750f8c`, `0xa2750fa4`, `0xa2750fbc` |
| other | `0xa2750ec2`, `0xa2750fd4`, `0xa2750ee4`, `0xa2750fec` |
| DL body, part 1, part 2 | `0xa2751008`, `0xa2751020`, `0xa2751038` |

*The candidate slot table in getter order.*

### Frames on screen

| item | OM-5 II 1.1 |
|---|---|
| AF frame display | `0x60721ec1` (callers `0x60740370`, `0x607405f3`, `0x607406e1`), draws through `0x60728b15` |
| main-face choice | via `0x605a6a11` |
| face notify | `0x60046998`, called from `0x60400daf`, `0x603fddd6`, `0x603fe554` |
| event flag 103 id (u16) | `0x6004166a` |
| face frames enable (bit `0x01`) | `0xa264353c` |
| lock-on notify (bit `0x02`) | `0x600469b5` |
| bit `0x08` notify | `0x600469ea` |
| AF-target list notify (bit `0x10`) | `0x60046a1f` |

*The frame layer's notify functions.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware of the OM-5 II 1.1 and the E-M5 III 1.7, 2026-11-24.
[^fw2]: Function matching between the E-M5 III 1.7 and OM-5 II 1.1 firmware, 2026-11-24.
[^inf1]: Inferred, not traced to the end or not tested, 2026-11-24.

