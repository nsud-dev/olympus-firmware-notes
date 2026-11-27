# Geotagging and the hot shoe: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Geotagging and the hot shoe](geotagging-and-hotshoe.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page asks whether the hot shoe can carry a link to peripherals such as a GPS receiver, so photos get geotagged. It
also covers the GPS handling already in the E-M5 III firmware and the real-time Bluetooth location of newer bodies. It
is read-only research. Nothing was built or flashed for the question.

Addresses are file offsets in the E-M5 III 1.7 block0 unless stated. For the code part, the address is the offset plus
`0x60021020`. They are collected in the [address reference](#address-reference).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred.

## Summary

- **Geotagging already exists on the stock E-M5 III, the slow way.** OI.Share records a GPS track on the phone and
  sends it to the camera over Wi-Fi. The camera writes the GPS IFD into the matching photos itself. It needs no work,
  so test it first.[^fw1]
- **Real-time geotagging over Bluetooth is an OM-5 feature** (`BleLocation`).[^fw1] The OM-5 is our usual donor, with
  the same MN103 and the same ARM and Bluetooth chip. Porting it rides on the same work as the Bluetooth remote
  (RM-WR1) port. It is **feasible but big**.[^inf1] This is the recommended route if the Wi-Fi method is not good
  enough.
- **The hot shoe does have a data link**, but it is the Olympus flash serial bus, not an accessory port.[^fw1]
    - A shoe GPS would need custom hardware that speaks an undocumented protocol, plus a new device type in the
      firmware.
    - It is **possible, but the hardest and riskiest route**, and it takes the shoe away from a flash.[^inf1]

## Hot shoe

### No accessory port

The E-M5 III has no Accessory Port (AP2). That was the extra connector under the shoe on the original E-M5 and older
PENs, used by the VF-2 viewfinder, the SEMA-1 mic adapter and the PP-1 Penpal.[^fw1]

- Neither the E-M5 III nor the OM-5 / E-M1 III block0 has an `ACC_PORT` or accessory-port string.[^fw1]
- `PER_ACC*` (`per_acc.c`, `PER_ACC_SPI`) is the body's **accelerometer** on SPI, not an accessory.[^fw1]

### Flash serial link

The shoe's flash contacts carry a **bidirectional serial link** (`stb_external.c`, `TX_DATA`/`RX_DATA` dumps,
`sio time out`).[^fw1]

- **Detection.** The camera identifies what is attached: `ext strobe detected ID`, `ext microphone detected` and
  `ext microphone disconnect`.[^fw1]
- **Device info.** It reads the maker code, firmware type, firmware and hardware version and serial number from the
  device (`stb maker_code` ... `stb serial_number`).[^fw1]
- **Device classes.** The driver knows these.[^fw1]
    - external flash
    - external **microphone** (`stb_ext_microphone.c`, debug command `stbd mic` start/stop/slate tone)
    - external **LED video light** (`Ext LED ILLUMINATOR`, `stbd ill`)
- The microphone class is shared code.[^fw1] Whether any accessory for this body uses it is unknown.[^inf1]
- **Firmware updates.** The link is rich. The camera **updates flash firmware over the shoe** (`stb_ext_firmup.c`,
  `STB_FIRMUP_START TRANSMIT`).[^fw1]
- **EEPROM and RAM access.** The `stb ext` debug command can read and write the flash's EEPROM and RAM
  (`20:EEREAD 21:EESET 22:EEWRITE 23:EECLEAR 33:RAM WRITE 34:RAM READ`).[^fw1]
- **Other bodies.** The same strings are in the OM-5, OM-5 II, E-M1 III, OM-1 and OM-1 II. The PEN-F has the firmup
  path but no external microphone.[^fw1]
- **GPIO names** on the flash side are `PER_GIO_FLIGBT_SEL`, `PER_GIO_EXFLCNDS`, `PER_GIO_PWCNTEXFL`,
  `PER_GIO_EXFLCH`, `PER_GIO_FLCCHG` and `PER_GIO_FLCFULL`.[^fw1]
- **Protocol.** The pin-level protocol (clock, levels, framing) is not known. The link is serial channel 13.[^fw2] It
  is set up at about 20.8 kbit/s.[^inf2]

See also: [flash and hot shoe](../hardware/flash-technical.md#hot-shoe-link), which has the full map.

### Debug commands

These user-shell commands are read-only: `stbd state`, `stbd qlog show`, `stbd fls_inf`, `stbd gior <port>` and
`stb ext 0` (INFO).[^fw1] See also: [Wi-Fi debug shell](wifi-debug-shell.md).

> [!WARNING]
> Do not use `giow`, `ext 20-34`, `manual`, `full` or `flscont` (they fire the flash), or anything firmup.

## GPS handling in the E-M5 III firmware

### OI.Share and OI.Track over Wi-Fi

This is a live feature.[^fw1]

- The OI.Share capability XML advertises `<oitrackversion>3.10` and `<support func="gps"/>`.
- **CGIs.**
    - `req_storegpsinfo`: the phone uploads a GPS track, saved as `GPSLOG`, mode new or append.
    - `req_attachexifgps`: the camera matches photos to the track (`pos_log_analyze`, which prints latitude and
      longitude as ddmm/ssss).
    - `get_gpsdivunit`, `get_agpsinfo` and `do_cgi_update_agpsassistdata`.
- **Writer.** The playback editor `play_gps.c` writes the tags: `play_gps_edit_file/rawfile/mpofile` and
  `play_exif_rebuild_gpsifd`. So JPEG, ORF and MPO files all get the GPS IFD after the fact.
- The user shell command `pos` (`[dbg] [time] [analyze] [save] [diff] [alloc] [free] [inid] [getlist]`) drives the
  same module.

### Tough-series GPS framework

A built-in GPS framework from the Tough series is present but dormant.[^fw1]

- `GpsCtrl::startGPS/updateGPS/getGPSdata/startLogger/getLandMarkList/startCompass/startToughGear`.
- `GPS_STATE_*`, log intervals, and a GPS module firmware update (`[firmup]TYPE_GPS`).
- `Maintenance::getGpsModuleVersion`.

It is inherited from the TG platform. The E-M5 III has no GPS module. So this is the camera-side API a GPS source
would feed, not a driver we can use as it is.[^inf1]

### What is missing

The E-M5 III has no `BleLocation`, no `GPS_BLE.LOG`, no `GPS_RMC` and no `gps exif` setting.[^fw1]

## Bluetooth location in newer bodies

| body | `BleLocation` | `GPS_BLE.LOG` | `GPS_RMC` | `startGPSPositioning` |
|---|---|---|---|---|
| E-M5 III 1.7 | - | - | - | - |
| E-M1 III 1.6 | - | - | - | - |
| OM-5 1.2 | yes | yes | yes | - |
| OM-5 II 1.1 | yes | yes | yes | - |
| OM-1 1.9 / OM-1 II 1.3 | yes | yes | yes | yes |

*Bluetooth location strings by body, read in each body's firmware.[^fw1]*

### OM-5

- The OM-5 has a BLE handler `[BLE_HDLR] _chk_gps_pram`, the debug command `set gps exif 0/1`, `gps_info`, the
  fields `.gps_exif` and `GPS_RMC`, the log file `GPS_BLE.LOG` and `GPS_PROXY`.[^fw1]
- The phone (OM Image Share) sends its position over BLE while the camera shoots, and the camera writes it at
  capture.[^fw1]
- The OM-3 manual describes the user side, under "Adding position information" (learning.omsystem.com). Bluetooth
  is set to `OnC`, and a lit P icon means a position is available.

### OM-5 Bluetooth bridge

- The OM-5 `blebridge` (ARM, `/usr/bin` in the LZO rootfs) has **no** GPS strings.[^fw1]
- It differs from the E-M5 III one only by the bonding, pairing and advertise timer.[^fw1]
- So the location is an opaque GATT payload, forwarded on ISC channel 28 and parsed on the MN103.[^inf1]

See also: [ARM coprocessor](../hardware/arm-coprocessor-technical.md#bluetooth-le).

## Routes

| route | what it needs | effort | risk |
|---|---|---|---|
| A. Stock OI.Share track + Wi-Fi attach | nothing | none | none (stock) |
| B. Port OM-5 BLE location | OM-5 BLE userland on the ARM (or a ch-28 shim), OM-5 BLE handler modes (~12.8 KB vs 3.6 KB), position store, GPS IFD at capture (capture-time EXIF hook, the playback writer already exists), settings bit. Shares steps with the RM-WR1 remote port. | big | medium: block2 ARM rootfs change. BLE stays phone-dependent. |
| C. Shoe GPS | custom hardware on the flash contacts, reverse the flash serial protocol (logic analyser on an FL-LM3), new device class in `stb_external`, feed `GpsCtrl` or a capture hook | biggest | hardware: wrong levels on shoe pins can damage the body. The shoe is no longer free for a flash. |
| D. Card/GPX after shooting | desktop tool matching a GPX to EXIF times | none in firmware | none (not a firmware feature) |

*The four routes to geotagged photos on the E-M5 III, with effort and risk.*

Route B is the route we would take.[^pol1]

## Bluetooth geotag trace

### OM-5 path

The OM-5 path runs from the Bluetooth bridge to the shot record in these steps.[^fw1]

1. The blebridge write handler maps characteristic index `0x6b` to ISC channel 28, code **19**. The payload is the 11
   written bytes.
2. The MN103 receive function copies them into a buffer.
3. `_chk_gps_pram` validates them (reference bytes 0 and 1, a degree byte and 24-bit little-endian minutes × 100000).
4. A converter turns them into a 28-byte position. `gps_main_set_locate` stores it, with a u16 status beside it.
5. At capture, the per-shot info fill calls `gps_main_get_exif_param` through a wrapper. It writes the status 'A' or
   'V' (+4460), N or S (+4393), the latitude rationals (+4396), E or W (+4420) and the longitude rationals (+4424) into
   the shot record.

Only latitude, longitude and status are written. There is no altitude and no GPS time.[^fw1]

### E-M5 III side

- **Present.** The EXIF side is already there.[^fw1]
    - The same GPS tag fetcher exists, with fields at record +2089, +2092, +2116, +2120 and +2156 (the OM-5 offsets
      minus 2304).
    - The GPS-IFD decision exists.
    - The E-M5 III's per-shot info fill matches the OM-5's.
- **Missing.** The position store, the code-19 receive (in the E-M5 III's `ble_handler_main`) and the `0x6b`
  characteristic in blebridge.[^fw1] The E-M5 III write handler knows only indexes `0x0c` and `0x0f`, and sends codes
  6, 7, 3 and 4.[^fw1]
- That the record base in the fetcher is the info-fill record is inferred, still to check.[^inf1]

## Older bodies

BLE geotagging can't come to the E-M5 II or the E-M5 Mark I.[^fw3]

- The E-M5 II has no BLE, only old OBEX-style Bluetooth strings, and no ARM.
- The E-M5 Mark I has no radio code.

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i), the full comparison.

## Open questions

- Does OM Image Share send its position to an E-M5 III, or does the app gate it by model?
- Does BLE stay connected while shooting? The OM-5 has a REMOCON mode. The E-M5 III has connect and transfer modes
  only.
- Route A on the camera is still to do. OI.Share "Add location" or a track log, then send to the camera. That confirms
  the track-attach path end to end, with no flash.
- A read-only Wi-Fi shell check is still to do, with and without an FL-LM3 on the shoe: `stbd state`,
  `stbd qlog show`, `stb ext 0` and `stbd fls_inf`. It would show the detected ID and the message log on the shoe bus.

## Address reference

E-M5 III 1.7 block0 file offsets unless an address is named, or the OM-5 is named.

| item | file offset |
|---|---|
| `PER_ACC_SPI` | `0x9ee64` |
| `stb_external.c` serial link strings | `0x1c2f3c`-`0x1c3330` |
| `stb maker_code` ... `stb serial_number` | `0x1c320e` |
| `stbd mic` debug command | `0x1430641` |
| `stb_ext_firmup.c`, `STB_FIRMUP_START TRANSMIT` | `0x1c2be0`-`0x1c2e65` |
| `stb ext` command list | `0x14309d7` |
| flash-side GPIO names | `0x1c2368` |
| OI.Share capability XML | `0x12dabec` |
| `play_gps_edit_*`, `play_exif_rebuild_gpsifd` | `0x1391120`-`0x1392246` |
| user shell `pos` command | `0x12e3fd6` |
| `GpsCtrl::*` | `0xa8b478` |
| `[firmup]TYPE_GPS` | `0xe3e9e4` |

*E-M5 III hot shoe and GPS strings, as file offsets in block0.*

| item | offset or address |
|---|---|
| `[BLE_HDLR] _chk_gps_pram` string (RAM image offset) | `0x15c767c` |
| `GPS_BLE.LOG` string (RAM image offset) | `0x15c85f2` |
| blebridge write handler (ARM) | `0xb25c` |
| MN103 receive | `0x6151b702` |
| receive buffer | `0xa25fc452`-`0xa25fc45c` |
| `_chk_gps_pram` | `0x6151bbf7` |
| position converter | `0x6151bc95` |
| `gps_main_set_locate` | `0x6151d17d` |
| stored position / status u16 | `0xa272ee94` / `0xa272eeac` |
| per-shot info fill | `0x602c91f8` |
| `gps_main_get_exif_param` (via `0x6021386c`) | `0x6021369c` |

*OM-5 1.2 Bluetooth location path. The first two rows are offsets in the expanded RAM image.*

| item | address |
|---|---|
| GPS tag fetcher | `0x6030555c` |
| GPS-IFD decision | `0x6031b87d` |
| per-shot info fill | `0x602bd435` |
| `ble_handler_main` | `0x612fa355` |

*E-M5 III 1.7 geotag path, block0 addresses.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware of the E-M5 III 1.7 and newer bodies (OM-5 1.2 as an expanded RAM image and its ARM rootfs), 2026-11-17.
[^fw2]: Read in the firmware, 2026-11-25.
[^fw3]: Read in the E-M5 II and E-M5 Mark I firmware, 2026-11-21.
[^inf1]: Inferred, 2026-11-17.
[^inf2]: Inferred, 2026-11-25.
[^pol1]: Decision, 2026-11-17.

