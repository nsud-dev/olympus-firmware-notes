# USB webcam

The OM-5 has a built-in USB webcam mode and the older E-M5 Mark II could be used as a webcam, but the E-M5 III
can't. This was the first feature the project tried to bring over.

**Status: parked.** Webcam test 1 passed (the camera enumerates as a UVC webcam) and test 2c passed (it streams its own
picture over UVC and survives a replug). Streaming the real live view failed, because the camera turns its shooting
pipeline off while USB is connected; fixing that is a large change, so the work is parked.

Terms: **UVC** = USB Video Class, the standard webcam protocol; **UAC** = USB Audio Class; **iso / bulk** = USB transfer
types (webcams normally stream isochronously); **MVR** = the movie recorder module; **PID** = the USB product id.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

Parked by the maintainer on 2026-10-20. Don't restart without the maintainer asking. Section 9 lower 0x613bb000-0x613d4000 stays reserved for it.

## What we learned
- The E-M5 III never had USB webcam support. camecon (PID 0x130) has no command handler; the orphaned PTP mode 6 does file
  and remote ops only; no OM-D live-view ops (0x948x). It has to be ported. [camera] (USB tests 1-4)
- Donor: OM-5 1.2 native **UVC 1.0 MJPEG 1280×720 29.97/25 fps**, iso EP 0x85 (3×1024), UAC1 stereo 48 kHz EP 0x86;
  descriptors 0x60f76da4, builder 0x60cdb87f, `LINK_PROTOCOL_WEB_CAMERA = 8`, PID 0x139. Frames come from the **movie
  recorder (MVR)** via a 6-slot ring (0x60ce02cb/0x60ce0304/0x60ce0374). [code]
- E-M5 III DWC3 driver has no iso path, so we streamed over **bulk IN 0x86** (UVC allows it). [code]

## Builds and results

Tests 2 to 2d were built with the maintainer's own tool; we reviewed them and checked the bytes.

| build | what | result |
|---|---|---|
| webcam test 1 | PID 0x139 + UVC config descriptor via wrapper 0x613bb000 | **passed**: Mac lists a UVC camera [camera] |
| test 2 / 2b / 2c (the maintainer's tool) | probe/commit, SET_INTERFACE, bulk fixed 160×120 JPEG; 2b status-mask fix; 2c EndTransfer on reset | **2c passed**: own picture over UVC, survives replug [camera] |
| test 2d | 34 ms native timer pacing | 21.6 fps [camera] |
| live-view 2 | native movie USB output, 320×240 JPEG | **failed**: Photo Booth froze, camera shows "One moment..." (USB-connected state turns the shooting pipeline off) [camera] |
- uvc.log (2026-10-20): first open streams unpaced (~2400 fps, many packets dropped as `MissingFIDFlip`); on Photo Booth reopen the
  host never calls startStream, so the black picture is host-side; app restart/sleep needs camera deselect/reselect. The picture
  appeared only in movie mode. [camera]
- Bugs found in review and fixed: DEPEVT status mask, EndTransfer on reset/disconnect, pacing gate = period (see [gotchas](../reference/gotchas.md)). [camera]
- 0x60022e5c clock = 1 µs; timer create 0x6006be97 takes ms; native periodic timer type 128 → USB msg 0x03fe0001 → worker detour 0x60c2e2d6 (2d). [code]
- Fix would need keeping the camera in shooting mode while USB is connected (big UI/state work). Best flashed states: 2d / 2c.
- No-patch fallback: Wi-Fi live view (OI.Share `remocon`) into a virtual webcam on the Mac. [inferred]

