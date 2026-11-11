# Sync IS with Panasonic lenses

**Status:** hypothesis study done (2026-11-01); nothing built. Doc: (private link)

- Verdict: a body-only flag patch won't work. Sync IS ("copt" = cooperative internally) is reported **by the lens**:
  0x600fd973 queries lens cmd 41 (0x6020d42e) and stores the reply in copt flag 0x620a688e (get 0x602075ce / set 0x602075d7).
  Panasonic lenses speak Panasonic Dual IS, not copt. [code]
- Panasonic-class test 0x6020d782: lens_info+0x444 byte0 ∈ {2,3} and byte1 ≠ 0 (meaning guessed). Pana status 0x6020d094
  (`L_STAT_PANA`). Non-Pana lenses branch at 0x6021012d. [code]
- Routes: A force flag (very low odds), **B split: lens OIS yaw/pitch + body roll (best bet)**, C implement Panasonic Dual IS (long). [inferred]
- Aperture-ring hack exists in azqeurio/om-c-firmware (dbv0.3.0): read to learn only, never copy; credit and point users there
  (the maintainer, 2026-11-01).
