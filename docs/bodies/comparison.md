# Body comparison

All bodies here use the same container, the MN103/AM33-2 control CPU and block0 base 0x60021020. [code]

| | E-M5 III | OM-5 | OM-5 II | E-M1 III | OM-1 | OM-1 II | PEN-F |
|---|---|---|---|---|---|---|---|
| file / fw | E_137 1.7 | E_144 1.2 | E_148 1.1 | E_139 1.6 (1.4) | E_143 1.9 | E_146 1.3 | E_122 3.1 |
| magic | OE 13 70 | OE 14 40 | OE 14 80 | OE 13 90 | OE 14 30 | OE 14 60 | OE 12 20 |
| TruePic | VIII | IX | IX | IX | X | X | VII |
| blocks | 5 | 5 | 5 | 6 | 6 (+sub-CPU) | 6 | 4 |
| block0 LZ4 sections | none | 2 | 2 | 2 | none (32 MB) | none | none |
| buffer map / DRAM class | 1 GB | 1 GB | 1 GB | 2 GB | 2 GB | 2 GB | ? |
| MN103 cores seen | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-2 | CPU0-3 | CPU0-3 | ? |
| ARM | A9, Linux 4.4 | A9, 4.4 | A9, 5.10 | A9, 4.4 | A53, 4.14 | A53, 4.14 | ? |
| Wi-Fi | CYW43455 | CYW43455 | CYW43439 | CYW43455 | CYW43455 | CYW43455 | ? |
| setting IDs | 0-1649 | 0-1892 | more | | | | |
| English GUI lang index | 8 | 5 | 5 | 8 | | | |
| DSP jobs 11/12 | absent | yes | yes | yes | new gen (no match) | new gen | ? |
| Live ND | plumbing off (ported by us) | ND2-16 | ND2-16 (ND64/128 strings only) | yes, 32-frame table | ND2-64 | ND2-128 | no |
| Live GND | no | no | UI only (stubs) | no | no | **yes** (`iseq_half_nd`) | no |
| HHHR | tripod HR only; ARM `hhhr` present | yes (50 MP) | yes (jobs 14/15 changed) | yes | yes | yes | no |
| Starry Sky AF | no | yes | yes + start triggers | yes | yes | yes | no |
| DL subject detect | no | dead code | dead code + menu | dead code | **yes** (CPU3 + DML) | yes | no |
| USB webcam (UVC) | no (ported partly) | yes | yes | no | ? | ? | no |
| USB-C / PD | no (micro-USB) | yes | yes | yes | yes | yes | no |
| function match → E-M5 III | — | 82% | 77% | 83% | not measured | | |

? = not checked. Donor rules: **OM-5 1.2** for code, memory model and DSP jobs (Live ND, HHHR, Star AF, AF features);
OM-5 II only for what it adds; E-M1 III for hook placement (its fcs is a superset of E-M5's); OM-1/OM-1 II for logic/maths
references only (ND32+, Live GND) since their DSP jobs and memory don't fit.

## Why not just cross-flash the OM-5 image?
Different model id in every header (updater very likely rejects it), different block 3 loader, USB-PD code for absent
hardware, different SD-pin GPIO setup, 5 factory calibration entries the E-M5 III never got, different settings store.
Each is fixable piece by piece (which is what porting does), but a whole-image flash risks a brick with no known recovery
outside block0. [code] for the differences, [inferred] for the outcome.
OM-5 = E-M5 III-class hardware + USB-C/PD running the E-M1 III software branch.

