# AF: subject, face and eye detection

Newer OM System bodies can recognise subjects (birds, animals, vehicles) and offer more face and eye options. This page
compares what the E-M5 III, OM-5 and OM-5 II actually contain, and sorts the features into "already there", "portable"
and "needs newer hardware".

The short version: face and eye detection is already on the E-M5 III. A few face and AF options from the OM-5 are
portable. Deep-learning subject detection is not: it needs the OM-1's extra processor and AI hardware block.

Terms: **DL** = deep learning (a neural network); **MDET** = the firmware's motion-detect and tracking module; **C-AF** =
continuous autofocus.

Tags: **[code]** read in the firmware, **[inferred]** not traced or tested.

**Status 2026-11-05:** research done; nothing built.

| feature | E-M5 III | OM-5 1.2 | OM-5 II | port |
|---|---|---|---|---|
| Face/eye detector (`TSK_FACE_FD/MAIN`, FD job) | yes | same | same | nothing to do [code] |
| Face Selection (`MODE_FACE_SELECT`, touch on face select) | no | yes | yes | small-medium code port [code] |
| Face priority release / custom switch | no | yes | yes | small [code] |
| C-AF Center Start / Center Priority | no | yes | yes | medium (AF sequence) [code] |
| New tracker (MDET "LAF", EMS1/EMS2, PDT) | old generation (`mdet_laf` 0x605e8000+) | new (0x6062c000-0x60670000, ~270 KB) | edited | big swap, own region [code] |
| DL subject detection (`MDET_DL_*`, buffer 0x6600, `fcs_coordinate_set_af_point_dl_*`) | absent | dead code, no menu | dead code + full menu | **not portable** |


## Why subject detection can't be ported

- DL subject detect is **dead inherited code** in E-M1 III / OM-5 / OM-5 II: no network executor or weights in any image. `[TARGET_PRIORITY] SUBJECT DETECT` log = face target toggle. [code]
- On OM-1 it runs on **CPU3 + the DML hardware block** with 5 × 9.3 MB weight blobs (block 2 bank 11). E-M5 III has no CPU3 or
  DML. Verdict: OM-1-class hardware; E-M1X (2× TruePic VIII) was the only open case and we judged its file not useful. [code]
- OM-5 II 1.1 in om-emu shows only AF > Face & Eye Detection, no Subject Detection item (2026-11-05); the Human/Birds/Dogs & Cats strings are shared OM-series GUI text. [code]
- E-M1 III 1.6 does **not** ship subject detection: it has the `MODE_SUBJECT_DETECT` key, MDET_DL code and the same "Tracking Subject"/Motorsports/Trains GUI strings as OM-5 1.2 (corrected 2026-11-05: an earlier check, cut short, said it had none of them), but no shipped feature. Among Olympus/OM bodies only the E-M1X (2x TruePic VIII) and the OM-1 family shipped it. [code] for the strings, [inferred] for the product list.
- Weight search (2026-11-05): no non-code blob >100 KB with weight-like entropy in OM-5 / OM-5 II block0 (largest is a 66 KB LUT at OM-5 0x6080f320); block4 is JPEG data; OM-5 II DSP sub-block adds only ~130 KB. The DL RGB prep is movie-recorder info item 27 `MDET_DL_SET_RGB_IMAGE_PRM`. E-M5 III does have a CPU2 (`IMGPRO_MDL_CPU2`). [code]

## Tools and plan

- Plan order: A face select + release priority (OM-5 donor) → B C-AF center start → C tracker swap study.

