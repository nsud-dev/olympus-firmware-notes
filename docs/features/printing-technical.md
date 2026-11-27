# Printing: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Printing](printing.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 prints. It has three parts: PictBridge, which is direct printing over USB, Digital
Print Order Format (DPOF) print orders on the card, and the print settings. The OM-5 1.2 and OM-5 II 1.1 programs are
compared.

All of it is desk research. There were no camera runs. Module names come from our symbol table's module list. String
sets come from block0 of each of the three programs. No function was disassembled for this page.[^fw1] No mod use is
proposed.[^inf1]

Addresses are E-M5 III 1.7 block0 addresses unless the OM-5 II is named. They are collected in
[Address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Layers at a glance

PictBridge is the CIPA standard DC-001. The printer is a USB host and the camera is a Picture Transfer Protocol (PTP)
device. The two sides exchange XML "scripts" as PTP file objects with fixed names.[^fw1]

The printing code sits in layers, from the menus at the top down to USB.[^fw1]

| layer | files and names | functions | what |
|---|---|---|---|
| GUI | `SS_PICTBRIDGE` state set, 26 `ID_ST_DPS_*` states, `userGuiDps::*` log | (in GUI) | connect wait, picture select, print mode, paper setup, trimming, printing, printer errors |
| app API | `OlyApiEasyPrint.cpp`, `OlyApiCustomPrint.cpp`, `OlyApiReservePrint.cpp` | 3 | `EasyPrint::*`, `CustomPrint::*`, `ReservePrint::*` |
| operation layer | `OlyHfwOpeEasyPrint*.cpp`, `OlyHfwOpeCustomPrint*.cpp`, `OlyHfwOpeRsvPrt*`, `OlyHfwOpePrintRequestEvFw.cpp` | ~120 | print jobs from playback, trimming, print-order edits |
| components | `Cmp_PictBridgeComponent.cpp`, `CmpRPri_ReservePrintComponent.cpp`, 31 `CmpPictBridge_Notify*` observers | 710 + 328 + 31 | PictBridge session state, page and capability changes, print-order edit |
| capability | `CapPbr_PictBridgeCommunicate.cpp`, 17 `CapPbr_Notify*` observers | 402 + 17 | talks DPS: `getCapability`, `startJob`, printer status, DPOF id request |
| device | `DevPic_PictBridgeDpst.cpp` | 8 | wraps the DPS transport for the capability layer |
| DPS engine | task `DPS_MAIN`, events `DPS_APP_EXEC` / `DPS_DPS_EXEC` / `DPS_GET_DPOF_INF` / `DPS_SAICAS_EXEC`, `api_dpst.c` (15 functions) | | builds and parses the XML scripts |
| XML parser | Expat 1.95.5, matched by source[^fw2] | | parses printer scripts |
| transport | DPST queues `QDPSTAPP` / `QDPSTDPS`, `[TPC DPST]` errors | | between the DPS engine and the PTP layer |
| PTP object store | `SAICAS_*` session, read, write, delete handlers | | serves the script files as PTP objects |
| USB | TPC class "print" (`usb tpc` value 1), USB Mode option 6 | | see [USB technical notes](../hardware/usb-technical.md) |

*Printing layers on the E-M5 III, top to bottom. Function counts are module-attributed functions.[^fw1]*

Module-attributed functions across these files add up to about 1,670 in 75 modules.[^fw1]

## PictBridge session

- **Discovery and scripts.** The script file names are `DDISCVRY.DPS`, `HDISCVRY.DPS`, `HREQUEST.DPS`,
  `HRSPONSE.DPS`, `DREQUEST.DPS` and `DRSPONSE.DPS`. The root name is `pictbridge:/`. These are the standard DC-001
  names.[^fw1]
- **Script tags.** `configurePrintService`, `getCapability`, `startJob`, `dpsVersions`, `printServiceAvailable`,
  `paperSizes`, `layouts`, `datePrints`, `fileNamePrints`, `imagesPrinted`, `dpsPrintServiceStatus`, `printInfo`.
  This is the standard DPS 1.0 job vocabulary.[^fw1]
- **Flow seen in the capability log strings.** First `getCapability`. Then `startJob` with `_paperSize`,
  `_datePrint`, `_fileNamePrint` and `_pDpofInfo` per image. Then `PrintCompleted`, or `PrinterError` with
  `ERROR_STATUS_WARNING` (continue possible) or `ERROR_STATUS_FATAL`.[^fw1]
- **Printer errors the app sees.** `API_ERROR_PRINT_PAPER`, `_PRINT_INK`, `_PRINT_JAMMING`, `_PRINTER`,
  `_CONNECT_PRINTER`, `_NO_DPOF`, `_CANNOT_PRINT`.[^fw1]
- **Callbacks.** `CBC_EASY_PRINT`, `CBC_CUSTOM_PRINT` and `CBC_RESERVE_PRINT`, with status codes `CBS_READY_PRINT`,
  `CBS_START_PRINT`, `CBS_END_PRINT`, `CBS_PRINTER_ERROR`, `CBS_RECOVER_PRINTER_ERROR`, `CBS_CHANGE_PRINTER_SETTING`
  and `CBS_GET_PRINT_COUNT`.[^fw1]
- **Enable parameter.** `PRM_MODE_DPS_ENABLE` has id `0x0da1`, is stored in flash and defaults to 1.[^fw1] Its effect
  is untraced.[^inf1]

## Print modes and settings

- **Easy print.** Prints the current playback image with the printer's defaults. Its methods are
  `startEasyPrintService`, `select`, `print`, `abortPrint`, `continuePrint` and `endEasyPrintService`.[^fw1]
- **Custom print.** It has five modes.[^fw1]
    - `PRINT_MODE_NORMAL` 0, selected frames
    - `PRINT_MODE_ALL` 1
    - `PRINT_MODE_MULTI` 2, several images on one sheet
    - `PRINT_MODE_ALL_INDEX` 3, an index sheet
    - `PRINT_MODE_DPOF` 4, print the card's print order
- **Per-job settings.** Paper size and borders (`changePaperSize`, `changeBorderSetting`,
  `TraPrintPaperInfoContainer`), multi count, print count per image, date print, file name print and trimming. Trimming
  sets size and position and has its own preview, `makePreview`. The paper sizes offered come from the printer's
  capability reply.[^fw1]
- **Date stamp values.** `PRINT_NOTHING` 0, `PRINT_DATE` 1, `PRINT_TIME` 2.[^fw1]

## DPOF print orders

- **Edit layer.** `CmpRPri_ReservePrintComponent` and `OlyHfwOpeRsvPrt` provide `start`, `singleMode`, `reservePrint`,
  `changePrintCount`, `changeDatePrint`, `hasReservation`, `eraseReservation` and `canReserve`. Playback flags each
  image with `reservePrint` (`PlaySingleFrame::isReservePrint`).[^fw1]
- **Card file.** The DCF layer writes `MISC/AUTPRINT.MRK`. The `[dpofnode]` and `[dpoftmpnode]` error strings sit right
  after the writer strings.[^fw1] See also: [still image back end](../firmware/still-backend-technical.md).
- **Print from the order.** `PRINT_MODE_DPOF` asks the DPS engine for DPOF info (`DPS_GET_DPOF_INF`). The capability
  layer requests DPOF ids (`CapPbr_NotifyReqDpofID*`).[^fw1]
- **Share order.** The Wi-Fi share order (`olis` shell, `IMGSHARE`) is a separate list, not DPOF.[^fw1] See also:
  [user shell commands](shell-commands-technical.md).

## OM-5 and OM-5 II

| item | E-M5 III 1.7 | OM-5 1.2 | OM-5 II 1.1 |
|---|---|---|---|
| PictBridge cap / component / DPS / Expat strings | yes | yes (same set) | yes (100 of the 103 PictBridge names) |
| `SS_PICTBRIDGE` and `ID_ST_DPS_*` GUI states | yes | yes | **no** |
| PictBridge key-assign handlers (`customKeyAssignment_*_dps*`) | yes | yes | **no** |
| `usb tpc ... print` and USB "print select" handler name | yes | yes | yes |
| DPOF edit layer and `AUTPRINT.MRK` writer | yes | yes | yes |
| `MediaCtrl::erasePrintReservation` (reset all print orders) | no | no | **new** |

*Printing parts in the three programs, from string-set diffs of the three block0 images.[^fw1]*

The OM-5 II moved to the newer menu system and did not carry the PictBridge screens over. The PictBridge engine below
it is still in the image. A new "reset print orders" path was added for the new menu.[^fw1]

Language resources in OM-5 II block1 still hold "Print Order", "Reset Print Orders", "PC/Custom Print" and "Print Mode
Select".[^fw1] Whether the OM-5 II USB menu still offers Print is unchecked. So is whether its print-order screen is
reachable. A menu walk in the om-emu emulator would settle both.[^inf1]

## Open questions

- Which CPU runs `DPS_MAIN`, and the DPS task's message ids.
- What `PRM_MODE_DPS_ENABLE` gates.
- Whether the OM-5 II USB menu and playback menu have Print and Print Order entries (om-emu).

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 II is named. An address followed by "from" is the
start of a run of names.

| layer | item | address |
|---|---|---|
| GUI | `ID_ST_DPS_*` state names | from `0x610fafbf` |
| GUI | `userGuiDps::*` log | `0x61104943` |
| app API | method names | from `0x60ab088f` |
| operation layer | `OlyHfwOpeEasyPrint*.cpp` | `0x607fd8a1` |
| operation layer | `OlyHfwOpeCustomPrint*.cpp` | `0x607f8529` |
| components | `Cmp_PictBridgeComponent.cpp` | `0x60a22ad6` to `0x60a341d2` |
| components | `CmpRPri_ReservePrintComponent.cpp` | `0x60a61b08` to `0x60a6571c` |
| capability | `CapPbr_PictBridgeCommunicate.cpp` | `0x608ff79b` to `0x60905cb1` |
| device | `DevPic_PictBridgeDpst.cpp` | `0x60a93873` |
| DPS engine | task name `DPS_MAIN` | `0x601fc610` |
| DPS engine | `DPS_*` event names | from `0x614412e2` |
| DPS engine | `api_dpst.c` | `0x602e2611` |
| XML parser | Expat 1.95.5 | from `0x60c3ff92` |
| transport | DPST queues `QDPSTAPP` / `QDPSTDPS` | `0x613ab8a0` |
| transport | `[TPC DPST]` errors | `0x613ac195` |
| PTP object store | `SAICAS_*` handler strings | from `0x60e54fbd` |

*Printing layers.*

| item | address |
|---|---|
| discovery and script file names | `0x60e54f6c`, and from `0x60e64570` |
| root name `pictbridge:/` | `0x60e64715` |
| script tags | from `0x60e64d57` |
| capability log strings | from `0x60b45183` |
| `API_ERROR_*` printer errors | from `0x60aa45d1` |
| `CBC_*` callbacks and `CBS_*` status codes | from `0x60aa5309` |
| `PRM_MODE_DPS_ENABLE` | `0x613a96a1` |
| `PRINT_MODE_*` names | from `0x60af31c1` |
| date stamp values | from `0x60aeb9f8` |
| `AUTPRINT.MRK` writer strings | `0x607402e8` |
| `MediaCtrl::erasePrintReservation` (OM-5 II 1.1) | `0x60b55442` |

*PictBridge session, print modes and print orders.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. Module names from the symbol table and string sets from block0 of the
    E-M5 III 1.7, OM-5 1.2 and OM-5 II 1.1 programs. No function was disassembled.
[^fw2]: Read in the firmware. Expat was matched by its source code.
[^inf1]: Inferred. Not traced to the end.

