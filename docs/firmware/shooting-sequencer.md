# Shooting sequencer (E-M5 III 1.7)

## State table
- Stock table **0x6044f9e4**: 34 × 20-byte entries `{id, name, fn, evA, evB}`, states 0-33 (31-33 PhotoInMovie). [code]
- Dispatcher loads at 0x602a0f9f / 0x602a139c; range check **0x602a1347** (`cmp N`); state change store
  0x602a13b4 (d2 old, d0 new). [code]
- **Adding states works** (state test 1): table copied to 0x600d0200 with extra entries, loads repointed, range check
  raised. [camera]
- Current Live ND line (E2r → E10f): 38 entries at 0x600d0200; 34 = StlTakeCave (copy of StlTake 0x602b34c6),
  35-37 = DigitalNd / DigitalNdDarkRdy / DigitalNdEnd; range check `cmp 37`; chooser default `mov 34` at 0x602b3464,
  so **every single shot passes state 34**. HHHR plans state 38. Ask before moving anything in 0x600d0200-0x600d0800. [code]
- Relevant native states: 15 StlUhs, 25 HsContTake, 29 HsContEnd (0x602b5058), tripod High Res 25-30. OM-5 state 34
  = PixShiftSrHandHeldEnd; OM-5 Live ND states 31-33 = DigitalNd (0x602b9265) / DarkRdy / End (table 0x60468e74). [code]

## Still-shot chooser and routes
- Chooser **0x602b3441**: route 4 → state 15 **StlUhs**, route 3 → 25 HsContTake, else 34 (only when 0x62110344 == 0). [code]
- Route byte 0x6211020e, loaded at Standby entry 0x602b2263 from the shot message (byte 10; OM-5 byte 11 =
  continue_mode). [code]
- Observed routes: silent single 0, silent seq L 1, silent/mech seq H 3, Pro Cap L 1, Pro Cap H 3; no drive mode gives
  2 or 4 natively on E-M5 III. Forcing 4 at Standby works. [camera]
- Route 4 (StlUhs) is a **burst path**, fixed **60 fps** whatever Tv; frames clamp to ~1/60. Burst fps = UHS fps
  picked from {60,30,20,15} (0x601dca90) by 0x602bb29a, only when UHS type ctx+1990 (0x6211033a) == 2; stored at
  0x62110488. [camera]+[code]
- OM-5 enters DigitalNd only with continue_mode 4 and Live ND flag ctx+2196 (Standby byte 15); its DigitalNd sends its
  own type-7 request: kind 0x400, +20 = 1, fps 0. The E-M5 kind function 0x602ba4d5 lacks 0x400, but the E-M5 sensor
  side already handles kind 0x400 / fps 0 identically. [code]

## StlUhs stream mechanics
- Template 0x602b4876: +0 supplier 0x602b4978, +4 completion 0x602b49cb, +8 per-component 0x602b4a54. [code]
- Completion runs in **interrupt context**; it posts ev63 (a0 = entry), then ev85 (record) for frames ≥ 2; frame 1
  goes via msg 0x62110588 (type 24). [camera]+[code]
- ev63 0x602b4f16 re-queues an entry per frame (refill) then prepares (EXIF 0x602c0f6a); ev65 0x602b5062 row release
  (0x602b1348) + notify 0x602b4e68; ev85 0x602b50e4 → development queue (0x602c2295); ev80 frees development objects.
  Event table pairs from 0x6044e8a4 (ev63 slot word 0x6044e8a8, ev85 0x6044e8e8). [code]
- Row manager: the stream allocator keeps 1 in reserve; rows must come back **per frame** or the stream stalls at 4;
  `0x6210f448` = allocated count; refill request 0x602ae9ce(0). Notifying "row done" for undeveloped frames reboots. [camera]
- Stop flag f59a request / f59c ack; cleanup 0x602b4bc4 drains the queue; per-burst frame limit 600 (0x602b2807). [code]
- Single-drive streams end after 1 frame; nothing in the Standby/shot struct distinguishes single from H burst
  (decided elsewhere, unfound). [camera]

## Exposure record
- One exposure record per shot, R = *(*(0x6210fb6c)+60), filled at StlRdy1 0x602b29b9 by 0x602c0cb0: +6 Tv
  (prop 41002), +8 Sv (41034), +10 Av (41018). Tv = APEX × 256. [code]
- E-M5 has the OM-5 Live ND plumbing **compiled in but switched off**: take-param +119/+120 = 0 at 0x604492ed; stubs
  0x602292fd/0x60229301 identity, 0x60229305 returns 0; AE ids 299-302 records at 0x60547f54. [code]

## Sensor requests
Type-7 sender 0x601fce30 (11 callers in section 1, so hooks there need a boot guard). Live view mode 9 MSPD 120 fps,
half-press mode 0 HSSC 60, shutter mode 14 STILL fps 0 with set Tv (0x602b321b, 0x602b0adc burst; 0x602b9d20 single). [camera]
.
