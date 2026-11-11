# USB

This page covers the camera's USB hardware and the different USB modes it can present to a computer (storage, MTP,
remote control and so on). It matters mainly for the webcam work: the OM-5 can act as a USB webcam (UVC, "USB Video
Class") and the E-M5 III can't, and this page records what the E-M5 III's USB side has and lacks.

Terms used here:

- **PID** (product id) and **VID** (vendor id) are the numbers a USB device reports so the computer knows what it is.
  Olympus's VID is 0x07b4, and each USB mode has its own PID. [camera]
- **PTP** is the Picture Transfer Protocol that cameras use for tethering; it works through numbered "operations".
- **TPC** is the firmware's name for its USB "personality" classes (storage, MTP, camera control, ...).
- **Bulk / isochronous / EP0**: USB transfer types. Video streaming normally uses isochronous transfers.

Tags: **[code]** read in the firmware, **[camera]** seen on a real E-M5 III, **[inferred]** not traced or tested.

## The controller

- The USB controller is a Synopsys **DWC3** (DWC_usb3) at **0x98f0c000** (GCTL 0xc110, DCFG 0xc700, DCTL 0xc704, DSTS
  0xc70c, DEPCMD 0xc80c+16n), at the same address on the E-M5 III, OM-5 and E-M1 III. [code]
- The E-M5 III driver supports **bulk and EP0 only**; there is no isochronous code. The OM-5 adds the isochronous path
  and the UVC/UAC (video/audio) classes: ~78 OM-5-only functions, ~22 KB in 0x60cd0000-0x60ce9000. [code]
- The OM-5 and E-M1 III add USB-C / USB-PD (power delivery) code and registers 0x98f10044-4c that the E-M5 III, with
  its micro-USB port, never touches. [code]

## USB modes and their PIDs (E-M5 III, VID 0x07b4)

| what | PID | notes |
|---|---|---|
| Storage | 0x012e | |
| MTP | 0x012f | |
| camera control (camecon) | 0x0130 | enumerates as "Olympus E-M1"; every PTP operation returns 0x2005 [camera] |
| hidden USB Mode value 1 | 0x0132 | a **HID** PC remote (zoom frame, AFL), not tethering [camera] |
| OM-5 webcam | 0x0139 | UVC; we injected it on the E-M5 III (webcam test 1) [camera] |

How a menu choice becomes a USB device: the menu value goes to internal 0x621de554 (0x60c56ccc), then to a TPC class
(api_comm 0x602d78b0 / 0x602d79b7), then to a PID (TPC_ON switch 0x6129ece5), then to a config descriptor (dispatcher
0x60c31082/0x60c31090). Forcing camecon TPC 6/7 fell through to a junk PID 0xf102. [code]

Other tables and details:

- USB Mode option table 0x61074fd2: Auto 0, Storage 4, MTP 1, icon-only 2, Print 6, PCM Recorder 85. A runtime filter
  hides some of these slots; we never found it. [code]
- The debug console's `usb tpc` table 0x60e5c868: storage 0, mtp 4, camecon 7, print 1, pcmlink 8. [code]
- 2026-11-05: the `tpc` PTP responder registers two vendor operations, **0x94B5** (receive a console line, then run it or
  post it to the user shell) and **0x94B6** (return the captured output), gated on session flag 0x62358c58. A lead only;
  USB work stays parked. [code]
- The PTP mode index is 0x6235a002. An orphaned DeviceInfo list 6 (0x613ae1f6) has vendor operations 0x9116-0x9125 and
  0x902c-0x902f. There are no OM-D 0x948x (live view / capture) operations anywhere, so there is no hidden tethered live
  view to unlock. [camera] (test 4)
- Endpoints: EP0, bulk OUT 0x05, **bulk IN 0x86**, interrupt 0x83. [code]
- A USB firmware update is started by block0 itself (`start_usb_firmup` 0x609ee601). [code]
- On macOS 15 and later, list USB devices with `system_profiler SPUSBHostDataType` (SPUSBDataType comes back empty).
  [camera]

