# USB

## Controller
- Synopsys **DWC3** (DWC_usb3) at **0x98f0c000** (GCTL 0xc110, DCFG 0xc700, DCTL 0xc704, DSTS 0xc70c,
  DEPCMD 0xc80c+16n), same address on E-M5 III, OM-5, E-M1 III. [code]
- E-M5 III driver has **bulk and EP0 only**, no isochronous code; OM-5 adds the iso path and UVC/UAC class
  (~78 OM-5-only functions, ~22 KB in 0x60cd0000-0x60ce9000). [code]
- OM-5 / E-M1 III add USB-C / USB-PD code and registers 0x98f10044-4c that the E-M5 III (micro-USB) never touches. [code]

## Modes and PIDs (E-M5 III, VID 0x07b4)
| what | PID | notes |
|---|---|---|
| Storage | 0x012e | |
| MTP | 0x012f | |
| camera-control (camecon) | 0x0130 | enumerates as "Olympus E-M1", every PTP op returns 0x2005 [camera] |
| hidden USB Mode value 1 | 0x0132 | **HID** PC-remote (zoom frame, AFL), not tether [camera] |
| OM-5 webcam | 0x0139 | UVC; we injected it on E-M5 III (webcam test 1) [camera] |
- Chain: menu value → internal 0x621de554 (0x60c56ccc) → TPC class (api_comm 0x602d78b0 / 0x602d79b7) → PID
  (TPC_ON switch 0x6129ece5) → config descriptor (dispatcher 0x60c31082/0x60c31090). camecon TPC 6/7 fell to junk
  PID 0xf102. [code]
- USB Mode option table 0x61074fd2 (Auto 0, Storage 4, MTP 1, icon-only 2, Print 6, PCM Recorder 85). A runtime filter
  hides some slots; never found. [code]
- Debug console `usb tpc` table 0x60e5c868: storage 0, mtp 4, camecon 7, print 1, pcmlink 8. [code]
- 2026-11-05: the `tpc` PTP responder registers vendor ops **0x94B5** (receive a console line, run it or post it to the user shell) and **0x94B6** (return captured output), gated on session flag 0x62358c58. Lead only; USB stays parked. [code]
- PTP mode index 0x6235a002; orphaned DeviceInfo list 6 (0x613ae1f6) has vendor ops 0x9116-0x9125, 0x902c-0x902f.
  No OM-D 0x948x (live view/capture) ops anywhere: no tethered live view to unlock. [camera] (test 4)
- Endpoints: EP0, bulk OUT 0x05, **bulk IN 0x86**, interrupt 0x83. [code]
- USB firmware update is started by block0 itself (`start_usb_firmup` 0x609ee601). [code]
- macOS 15+: use `system_profiler SPUSBHostDataType` (SPUSBDataType is empty). [camera]

