# Glossary (Olympus naming and our shorthand)

| term | meaning |
|---|---|
| **TruePic VII/VIII/IX/X** | marketing name for the whole image-processor SoC (control CPUs + image engine + more), not one core |
| **dc13** | the SoC's device-tree name (`panasonic,dc13`, later `ntcj,dc13`) |
| **ntcj** | DT vendor prefix on newer bodies; probably Nuvoton Technology Japan (ex-Panasonic chips) |
| **MN103 / AM33-2** | Panasonic control CPU family running the main program |
| **CPU0..CPU3** | MN103 cores; OM-1 adds CPU3 (drives the DML) |
| **DML** | deep-learning hardware block on OM-1 (`CLKDML`) |
| **DSP / image engine / job** | our name for the engine that runs microcode "jobs" (job 11 = Live ND merge, ...) |
| **bank 6 / resource 0x8007** | block-2 resource holding job programs |
| **ISC** | Inter System Communication, Panasonic mailbox between MN103 and ARM |
| **CA9** | the Cortex-A9 ARM core (`TSK_CA9PWR_MNGR`) |
| **μITRON** | the RTOS on the MN103 |
| **OXF / Rhapsody** | IBM Rhapsody framework generating the C++ state machines |
| **olycompress** | LZ4-block compressed sections in some block0s |
| **block0..5** | container blocks: main program, GUI, resources, loader, data, sub-CPU |
| **section 1-10** | RAM load units of block0, loaded in the background at boot |
| **slack / cave** | 0xFF space after a section's end, used for our code once the end constant is raised |
| **boot guard** | our check that a target section is ready before a hook jumps into it |
| **DIGITAL_ND / DigitalNd / iseq_nd** | Live ND (states DigitalNd/DigitalNdDarkRdy/DigitalNdEnd; image-sequencer module iseq_nd) |
| **iseq_ndlv** | Live ND live-view preview (job 12) |
| **digital_nd_tv / real_tv** | Live ND displayed total time vs per-frame shutter time |
| **frame_max** | LV-preview frame count (30 × digital time) |
| **light / dark frames** | exposures vs dark frames for NR in the ND/GND modules |
| **DIGITAL_GND / iseq_half_nd** | Live GND (OM-1 II engine; OM-5 II UI only) |
| **pixshift SR / iseq_pixshift_sr** | High Res Shot; handheld = HHHR (state PixShiftSrHandHeldEnd) |
| **HHHR** | Handheld High Res |
| **mdet** | motion-detect module (tracking, HHHR motion estimation, DL subject detect on newer bodies) |
| **LAF / EMS / PDT** | parts of the mdet tracker generation |
| **Astro AF / fcs_astro** | Starry Sky AF |
| **fcs** | focus control task / module |
| **take_focus** | AF sequencer layer |
| **copt** | cooperative IS (Sync IS) flag reported by the lens |
| **ColorCreator2 / MonochromeCreator** | PEN-F Color / Monochrome Profile Control |
| **StlUhs** | still "ultra-high-speed" burst state (route 4) we use for Live ND frames |
| **HsContTake / HsContEnd** | high-speed continuous states (route 3) |
| **StlTake / StlTakeCave** | native single take state / our copy at state 34 |
| **Standby / route byte** | shot message at Standby; byte 10 (OM-5 11, "continue_mode") picks route 0-4 |
| **HSSC / MSPD / STILL** | sensor modes: half-press 60 fps / live view 120 fps / still capture |
| **type-7 request** | camera sensor-mode request message (0x601fce30) |
| **kind 0x400** | OM-5 Live ND sensor request kind (allows fps 0 = long frames) |
| **prop / setting** | property id (value store) vs menu setting id; mapped by a table |
| **MODE_*** | settings key names in block 2 |
| **PRM_*** | factory calibration entries |
| **camecon / pcmlink / TPC** | USB camera-control class / PCM-recorder-HID class / USB personality class |
| **M block** | Live ND's RAM log/state area 0xa07b4800 |
| **LNDM3.ARM / LND3B7** | Live ND request file on card / log file written by the next silent single |
| **letter (U..Z, F, G...)** | the 1-byte request selecting a test variant or ND level |
| **armed** | our gate: request letter + S/M mode; hooks do nothing unless armed |
| **E2..E10f, M0..M3, stage 1-3U** | Live ND build series (OM-5 base E/M; E-M1 III base stages) |
| **H0..H6, G0..G3, S0..S4, U1..U3** | planned test stages for HHHR, Live GND, Star AF, menus |
| **bdelta** | build stored as a delta vs stock 1.7 |
