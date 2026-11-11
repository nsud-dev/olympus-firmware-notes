# Live GND (graduated ND)

**Status 2026-11-05:** spec written from the OM-1 II; nothing built.

## Who has it
| body | Live GND |
|---|---|
| OM-1 II fw 1.3 | **real**: module `iseq_half_nd` (gnd_comp, gnd_blend, gnd_lv, calc_comp_prm), states DigitalGnd/DarkRdy/End, AE mode `FULL_LQ_GND` [code] |
| OM-1 1.9 | no |
| OM-5 II 1.1 | **UI only**: settings 2166-2175, props 43329/43345/43361..., interlocks; OlyApiShooting GND methods (+1088..+1124) are empty stubs; no imaging code reads the props [code] |
| E-M5 III, OM-5, E-M1 III | no |

## How the OM-1 II does it [code], method partly [inferred]
- GND k stops (GND2..32 = k 1..5): shoot **N = 2^k frames, each k stops shorter**, composite (keeps sky highlights), then a
  position-dependent gain brings the foreground back up. Sky ends k stops darker, nothing clipped. [code] for N and the shift, [inferred] that frames are shorter
- Parameters (0x60899662, OM-1 II addresses): centre Xc/Yc from border position (±60), angle θ, width from a table of 5/10/20%
  of sensor width (Q15 1638/3276/6553), CoefA = −sin θ·16384, CoefB = cos θ·16384, CoefC = 2(Xc sin θ − Yc cos θ) + Width·K[n];
  GainMin table 1/2..1/32 (Q31), K offsets −0.138..−0.779. [code]
- 2026-11-05: frame count/Tv: `digital_gnd_info` 0x60309326 sets frame_number = 1<<step when prop 43329 is on; real_tv via 0x603092a5 (shift in 1/3, 1/2 or 1 EV units). Calc inputs: 43345 number, 43361 filter, runtime props 43417[0/1] (border X/Y, ±60) and 43394 (angle, degrees), not menu settings. Float helpers: 0x6004c188 fadd, c19b fdiv, c1ad fmul, 0x600487df sin, 0x60048162 cos. Filter widths live in RAM 0xa34fb814, init 0x6089ca7b. [code]
- WB-aware highlight clip: Clip_c = Sat × min(WB_Gr, WB_Gb) / WB_c (0x6089ad87). [code]
- The actual gain curve shape is in OM-1 DSP microcode (not visible, not portable). [code]

## E-M5 III design (proposed)
Reuse the Live ND capture path (N frames, job 11 average) with Tv shortened by k stops, then **our own gain pass** on the merged
Bayer: g = N × G(s), smoothstep in log2 stops, 256-entry LUT; run on the MN103 (or ARM NEON if too slow). Stages G0 (single frame +
gain) → G1 (GND2/4/8) → G2 tuning, GND16, position/angle → G3 menu/LV. GND32 needs 32 frames (doesn't fit). [inferred]

Open: filter order (which width is soft), E-M5 raw origin/margins, MN103 pass speed.

