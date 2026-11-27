# User shell commands: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [User shell commands](shell-commands.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page is the reference for every command of the user shell, the console with the prompt `USR>`. The
[Wi-Fi debug shell](wifi-debug-shell-technical.md) reaches it on port 23, and that page says how to start it. This page
covers what each of the 58 commands of the E-M5 III 1.7 does and which of them write the card or the flash. It also
covers the 5 commands the OM-5 II 1.1 firmware adds.

This is desk research. Nothing was run on the camera.[^fw1] Addresses are E-M5 III 1.7 block0 addresses (base
`0x60021020`) unless the OM-5 II is named. OM-5 II addresses are in the expanded OM-5 II 1.1 block0.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Command table

- **Two copies.** Stock 1.7 holds the 58-entry command table twice. Each entry is 8 bytes, a name pointer and a
  handler.[^fw1]
    - The first copy is read only near the `dbgall` and `usr` code.[^fw1]
    - The second copy is read by the executor and by `help`.[^fw1]
    - Both list the same handlers.[^fw1]
- **Handler call.** The executor splits the line. It calls the handler with the argument vector in a0 and the argument
  count in d0.[^fw1]
- **Sub-commands.** Most handlers compare `argv[1]` with their sub-command words using the firmware's string compare.
  Others walk a sub-command table of (name, handler) or (name, handler, help) entries.[^fw1]
- **OM-5 II 1.1.** The OM-5 II has 63 commands, with a second copy of its table as well.[^fw1] The first 57 entries are
  the stock list in the same order. `syscall` moves to the end, and five commands are new: `ems`, `sys`, `ictlog`,
  `ble` and `gps` (see [OM-5 II additions](#om-5-ii-additions)).[^fw1]

## Write classes

The "writes" column of the reference says what a command can change.

| class | meaning |
|---|---|
| RAM | state in memory only, gone at power-off |
| card | files on the card |
| flash | the camera's NAND (settings, resources or calibration), which survives power-off and may not be restorable |
| hw | drives a motor, the shutter, the flash tube, power or a connection |
| none | read-only, prints only |

*Write classes used in the command reference.*

Sub-command lists come from each handler's string compares and tables.[^fw1] A "writes" entry marked with an
inferred note was read from names and strings but not traced to the end.[^inf1]

## Command reference

The table lists the commands in table order. Handler addresses are in [Address reference](#address-reference).

<details><summary>All 58 user-shell commands of the E-M5 III 1.7</summary>

| command | what it is | sub-commands (main ones) | writes |
|---|---|---|---|
| `echo` | prints its arguments | | none |
| `help` | prints the command list (`help X` reprints it too) | | none |
| `lens` | lens communication ([lens](../hardware/lens-communication-technical.md)) | set reset aperture still focus askdata ctrl data pow mtdet llpsw polling firmup | hw (focus/aperture), flash on the lens (`firmup`) |
| `aud` | audio codec and audio log ([audio](../hardware/audio-technical.md)) | read_reg, ic, log | RAM / codec registers |
| `cam` | sensor and camera driver | poweron poweroff still movie mode lvpd af_clip number exp exp2 sss ... | hw |
| `bas` | **BASIC script engine** (see [Script engine](#script-engine-bas)) | load del stop list | **flash** (`load`, `del`) |
| `pwr` | charger and battery: vbat, battery temperature, charge on/off and judgement | chg_on chg_off chg_jdg_stat chg_jdg_res chg_iic jdg_batt_tmp vbat | hw (charger) |
| `bc` | stabiliser sub-CPU: version, status, clock, reset, boot, parameters ([stabiliser](../hardware/stabiliser-technical.md)) | version clk rst boot getprm ... | hw (`clk`, `rst`, `boot`) |
| `take` | take sequencer state and debug | func dbginfo dbgmode cont_dbgmode ps pe exec ev_qname | RAM |
| `stbd` | flash (strobe) debug ([flash](../hardware/flash-technical.md)) | init con coff cpau cres cloop ... | hw (charges the flash) |
| `per` | peripherals: backup RAM, GPIO, PWM, clocks, pulse counters, A/D, timers ([small devices](../hardware/small-devices-technical.md)) | backup gio pwm clk help pcnt adconv timer microtimer dbgsup usf ... | hw |
| `res` | resource store (fonts, languages, sounds, pictures, lens tables, common block): dump, header | read write erase head | **flash** (`write`, `erase`) |
| `app` | second entry into `api_debug.c` (same words as `api`) | help show dbglvl layer func | RAM |
| `usb` | USB: IP registers, PC reset, PTP mode switch (`usb tpc storage\|mtp\|camecon\|print\|pcmlink\|off`), media | ip top func pcreset tpc media mount | hw (USB mode) |
| `prm` | properties (settings) get/set | getvalues getval getstr setval setstr getval_def clear | **flash** (settings; `clear`) |
| `flash` | NAND test tool ([risks](wifi-debug-shell-technical.md#risks)) | oly fmem mode trace running ... | **flash: erases calibration, never run** |
| `rec` | record task flags, dumps, EXIF dump | write histprm hp dbg tsk out dump exif | RAM, card (`write`), inferred[^inf1] |
| `file` | file system shell | mount umount format pwd cd ls rm rmdir mkdir chmod cat chdev rawread memdump | **card** (`rm`, `format`, `mkdir`) |
| `sc` | heap lists and SC timer timing (see [System heap and timing](#system-heap-and-timing-sc)) | heapshow heaplist phase timing time_m time_mw set | none (timing counters only) |
| `exp` | exposure debug: accel tracking counts and state chart ([exposure](../firmware/exposure-technical.md)) | ... | RAM |
| `dbg` | per-module log switch (adj_slf api aud buf cam demo exp file img lens movp ...), block info, logger | put off info all on check dmyw wi | RAM |
| `ui` | buttons, dials, outputs, LEDs, beeps ([button press](../guides/button-press.md)) | key jog out led sound help | RAM (simulated presses) |
| `mec` | shutter and mechanics ([shutter](../hardware/shutter-technical.md)) | info motor shutter still lsnc dbglog mem test error init dmgclear dmgset | hw, flash (`dmgclear`, `dmgset`), inferred[^inf1] |
| `fcs` | focus (AF) debug: dump flags, IPAF/IAF only, tracking views | dbginfo info cam seq im mov ip set | RAM, card (`set 2` = log file), inferred[^inf1] |
| `dbgall` | runs every module's debug dump. Also `dbgput`, `nmi` | dbgput nmi | RAM |
| `sdet` | scene detection (scene, tone, blue sky, high saturation, near, portrait) | dbginfo exec | RAM |
| `osd` | OSD debug: frame position adjust, edge debug | dbglvl framedbg left right top bottom reset size print edgedbg | RAM |
| `mdet` | detection-unit driver debug (`mdet MODE [OPTIONS]`) | debug, disp debug | RAM |
| `face` | face detection log and test images (`C:\BD_VGA.RAW`, `C:\FDPD_VGA.RAW`) ([face](face-detect-technical.md)) | LOG RESULT, LOG HISTORY | reads card |
| `play` | playback debug: level, dump, YC dump, execute history | dbglv dump yc load hist | RAM, card (`yc`), inferred[^inf1] |
| `mddyna` | **empty template** (see [Empty commands](#empty-commands)) | help sample | none |
| `disp` | display debug levels (through image, HDMI, histogram, auto dimmer, touch) | th hd hst ad tp ... | RAM |
| `tpc` | PTP (ISO 15740) connection: info, database, control, camera control | info db ctrl com util camc fileadd myset dbgall | RAM |
| `sdk` | **high-level service (OlyApi) console** (see [High-level service console](#high-level-service-console-sdk)) | 22 words | RAM, hw (`shutdown`, `sleep`), **card** (`macro rec`) |
| `efct` | screen transition effects (slide, overlap) for TFT/PAL/NTSC | help set coord tft pal ntsc direction start cstart end | RAM |
| `buff` | image buffer info (imgbuff, memory, imgwork, still-memory mode normal/art/high ISO) | | none |
| `api` | OlyApi debug (`api_debug.c`): log level and masks, OSD back layer black | help show dbglvl layer func | RAM |
| `c3d` | c3d GPU debug: file, mount, memdump, test (writes `vg.out`) | help file mount memdump test | card (`test`), inferred[^inf1] |
| `sync` | display sync sequence log (event, device, frame, handles) | osd img | none |
| `usr` | start-up milestone flags and timing (MainStart, CamOnE, LensSetupStart, ThroughStart, 2nd ...), fast-start debug | fast camone log ... | RAM |
| `damage` | damage history ([maintenance](../firmware/maintenance-technical.md)) | get | none (stock `get` only) |
| `spc` | **Wi-Fi SD card (FlashAir) control** (see [Wi-Fi SD card](#wi-fi-sd-card-spc)) | dbg dbg_lv cat print_prm init connect mode_connect disconnect write_mode write_lock write_ssid write_key write_config read_config chk_wifi chk_connected | **card** (FlashAir config) |
| `mcon` | mode-conflict and user-setting tool ([movie stack](../firmware/movie-stack-technical.md)) | show usersetting flag level help | RAM, settings, inferred[^inf1] |
| `wifi` | Wi-Fi start and ARM-side debug ([Wi-Fi shell](wifi-debug-shell-technical.md)) | arm run_cpu sys remocon hardcopy release mngr httpd shell bsdapi stream upnp mdns ptpip; init start info auto | hw (radio) |
| `qr` | QR code generator (pairing codes) | create NAME [MODEL VERSION MODE LEVEL ZOOM] | RAM |
| `olis` | **share order list** (see [Share order list](#share-order-list-olis)) | help dbg set_media init term num get_resrv recon set_file set_list set_list_max cancel cancel_all cancel_all_p init_prm print dump remove | **card** (`IMGSHARE\RESERVE`) |
| `mvr` | movie recorder task: state, history, failsafe and through counts, trace | dbgall dbginfo trace | RAM |
| `pos` | **GPS log tagging** (see [GPS log tagging](#gps-log-tagging-pos)) | dbg time analyze save diff alloc free inid getlist | **card** (`save`) |
| `avm` | AV middleware: rec, debug flags, history per CPU, time ([movie stack](../firmware/movie-stack-technical.md)) | rec debug history time | RAM |
| `iseq` | computational sequences (see [Computational sequences](#computational-sequences-iseq)) | dbgall trace tracelvp traceslave dbginfo dump pkt extif time clear help | RAM, card (`dump`), inferred[^inf1] |
| `img` | **empty**: `clr d0; retf` (the OM-5 II the same) | | none |
| `movp` | movie playback tasks (main, video, audio, external): state and message log | | none |
| `md_sve` | **empty template** (see [Empty commands](#empty-commands)) | help sample | none |
| `digizoom` | digital zoom trace, timer and parameter logs | trace timer param | RAM |
| `zoom` | power zoom: up/down/stop/focal length/speeds, info, debug flag | exec info set | hw (zoom motor) |
| `move` | movie edit tasks (main, video, audio, trim, file read/write, external): state and message log | | none |
| `albm` | **movie album store** (see [Movie albums](#movie-albums-albm)) | lv init getfs geta chke setd dela search next prev first last add ... | **card** (album files) |
| `syscall` | cross-CPU call request rings ([CPU1 and CPU2](../hardware/cpu1-cpu2-technical.md)) | dbgall | none |

*The 58 user-shell commands, read in the firmware.[^fw1] Inferred write classes are marked.*

</details>

## Formerly unknown commands

These commands had no known purpose before this survey.

### Share order list (`olis`)

- `olis` is the **share order list**. It holds the playback "share order" marks that OI.Share later transfers.[^fw1] Its
  handler sits between `mdet_laf.c` and `cam_still.c`.[^fw1]
- It keeps reservations in `:\IMGSHARE\RESERVE` on the card.[^fw1]
- It can list, add (`set_file`, `set_list`), cancel and remove them, per media slot (`set_media`).[^fw1]
- It has debug levels 0 to 2.[^fw1]
- "olis" reads as OLympus Image Share. The link to the share feature is inferred.[^inf1]
- The OM-5 II adds level 3 (trace I/O), `dbgall` and a per-media file listing with folder and file names and
  sizes.[^fw1]

### Movie albums (`albm`)

- `albm` (`albm_if.c`, `albm_main.c`) is the **movie album** store behind playback's Album and
  `AlbumEditView`.[^fw1]
- Albums group movie files by frame rate (24p to 60p), size (HD, FHD, 4K), video quality (N, F, SF) and audio
  (48 kHz/16-bit, 96 kHz/24-bit).[^fw1]
- Its words are listed below.[^fw1]
    - `lv` sets the log level, 0 to 3.
    - `init SLOT`, `getfs`, `geta` and `chke`.
    - `setd` sets the default album. `dela` deletes an album.
    - `search PIC_NO`, and the `next`, `prev`, `first` and `last` handles.
    - `add FILENAME ALBUM_NO POS` adds a file from `C:\DCIM\100OLYMP\`.
- The OM-5 II has the same.[^fw1]

### GPS log tagging (`pos`)

- `pos` (`pos_debug.c`) is **GPS log tagging**.[^fw1]
- `analyze` reads NMEA `$GPGGA` and `$GPRMC` logs from the card and matches them to pictures by time.[^fw1]
- `time YYYYMMDDThhmmss Chhmm` sets the time and offset. `diff` prints it.[^fw1]
- `getlist` lists the matches with latitude and longitude.[^fw1]
- `save MODE YYYYMMDD` writes `C:\gpstest.txt`.[^fw1]
- It needs a large heap block (`scheap large alloc error`).[^fw1]
- The OM-5 II adds `getsns`, which takes a date range like `getlist`.[^fw1]

See also: [geotagging](geotagging-and-hotshoe.md).

### High-level service console (`sdk`)

- `sdk` (`OlyHfwShellCommand.cpp`) is the console of the C++ **high-level service**, the OlyApi framework. It is not a
  GUI event history.[^fw1]
- Its sub-command table holds `help dbglvl debug dump dbgall dbgstate dbgfw shutdown shutdown_api sleep sleep_api
  sleep_off charge_sleep power_info canexec media showtimer macro ca api starttimer stoptimer`.[^fw1]
- The help text also lists three more words.[^fw1]
    - `event $event $value` sends an APPEVENT.
    - `callback $command $status $param` sends a callback to the GUI.
    - `dbgdisp`.
- `dbgall` prints flash, lens and media info and the maintenance counters page
  ([shutter](../hardware/shutter-technical.md)).[^fw1]
- `macro rec/stop/play` records key events (`OlyHfwEventRecorder.cpp`) into `MACRO000.DAT` on the card and replays
  them.[^fw1]
- `sdk api` reaches the 1,138 OlyApi test handlers (linked projects).[^fw1]
- `shutdown_api` and `sleep_api` force power states.[^fw1]
- The OM-5 II has the same word set.[^fw1]

### System heap and timing (`sc`)

- `sc` is the **system heap and timing** tool.[^fw1]
- `heapshow` and `heaplist [count|small|middle|large|custom|apim|napim]` show the heap areas. These are SMALL, SMALL2,
  SMALL3, MIDDLE, MIDDLE2, LARGE and LARGE2, about 786 KB in all (see [memory map](../hardware/memory-map.md)).[^fw1]
- `phase` shows the develop phase.[^fw1]
- `timing show|start|stop|clear`, `time_m` and `time_mw` measure time with the SC timer channels `ttmr_dd1-5` and
  `ttmr_ed1-5`.[^fw1]
- "sc" matches the `scheap` allocator name used elsewhere.[^fw1]
- It is read-only except for the timing counters. The OM-5 II has the same.[^fw1]

### Empty commands

- `mddyna` and `md_sve` are **empty templates**. Their handlers sit between `effect.c` and `GCPnl_Move.cpp`.[^fw1]
- Each prints its name, `mddyna_dbg` or `md_sve__dbg`. `md_sve` also prints `hoge`, the Japanese "foo".[^fw1]
- Then `help` prints `help:` and `sample` prints `sample1:`. There is no other code.[^fw1]
- Their behaviour is byte-identical in the OM-5 II. The names give no feature.[^fw1]
- `img` returns 0 at once (`clr d0; retf`). The OM-5 II's is the same.[^fw1]

### Script engine (`bas`)

`bas` is a **BASIC script engine** with a loader.[^fw1]

- The interpreter knows these statements: `list run new bye next return goto gosub while for print hex chr crlf spc
  input rem shell end`.[^fw1]
- It knows these functions: `abs( rand( getkey( api( sctm( fault( acs( tp( sdk(`.[^fw1]
- It knows key names (`EXEC DOWN LEFT RIGHT INFO MENU TRIG1 TRIG2 ZOOMUP LLPSW POWER` ...), mode names (`MOVIE PANORAMA
  SCENE I_AUTO ARTFILTER MY_MODE1-4` ...) and API names (`GET_DATETIME SET_DATETIME GET_BATTERYLEVEL CLEAR_DAMAGEINFO
  GET_DAMAGEINFO SAVE_USERSETUP SET_CAMERAINFO` ...).[^fw1]
- So a script can press keys, call camera APIs and run shell lines.[^fw1]
- It runs in its own task, fed by the queue "QBASIC" (`cannot write to QBASIC`).[^fw1]

The loader has four words.

- `bas load` reads `RCUOLYMP\R0240001.RCU` from the card. It writes it, up to 16 KB, into a flash resource through the
  resource writer in `res.c` (error `flash_mem:write_error`).[^fw1] That the store is NAND is inferred, because it goes
  through the resource writer.[^inf1]
- `bas list` reads the stored program list (`PROCLIST:`, a resource read of kind 4, 16 KB).[^fw1]
- `bas del` and `bas stop` post DELETE and STOP to the task.[^fw1]
- "RCU" reads as a factory or service remote-control unit script.[^inf1] The same code and strings are in the
  OM-5 II.[^fw1]

Never run `bas load` or `bas del`, because they write flash. Reading `bas list` is the only safe word.

### Wi-Fi SD card (`spc`)

- `spc` drives a **Wi-Fi SD card (Toshiba FlashAir)**.[^fw1]
- It connects and checks the link with `connect`, `mode_connect`, `disconnect`, `chk_wifi` and `chk_connected`.[^fw1]
- It writes the card's own configuration with `write_mode 0|4|7`, `write_lock`, `write_ssid`, `write_key`,
  `write_config`, `read_config` and `print_prm`.[^fw1]
- It writes only the card, not the camera. The OM-5 II has the same.[^fw1]

### Computational sequences (`iseq`)

- `iseq` traces the **computational sequences**.[^fw1]
- The stock func numbers are 1 photo story, 2 swing panorama, 3 handheld high res (pixel shift SR) and 4 digital ND
  filter.[^fw1]
- `extif 4` decodes the ND interface calls `ND_StartNd`, `ND_SetNdHandle`, `PS_ExecNdExposure` and
  `PS_ExecNdLv`.[^fw1]
- So the stock E-M5 III 1.7 keeps a digital ND sequence hook in its tables (see [Live ND](live-nd.md)).[^fw1]
- The OM-5 II renames func 1 "Don't Care" and drops `tracelvp` and `pkt`.[^fw1]

## OM-5 II additions

The OM-5 II 1.1 adds five commands.

| command | what it is |
|---|---|
| `ems` | motion search engine (EMS1/EMS2) driver debug. Its table holds `dbgall que setfunc gvec dump test` (queue info, global vectors, one-shot dump). It is the AF tracking motion unit ([motion unit](../hardware/motion-unit-technical.md)).[^fw1] [^inf1] |
| `sys` | **the system shell's command set in the user shell**. It shifts the arguments and calls the system executor (`ps mdump mdump2 mdump4 mem_get* mem_put* od oserr chgpri heaplist initbuff busmes arbit show_reqq cpulog shelloff wdt flash` and the Oly API test calls).[^fw1] |
| `ictlog` | ICT log, a usage log with start-up and 60 s entries, saved at firmware update and readable over Wi-Fi. Words `init save t1_save t2_save clear t_init addlog cntup create secrecord seccreate secclear getexif locate blesave`.[^fw1] [^inf1] |
| `ble` | Bluetooth LE debug: log level 0 to 3, `gps_info`, `start`/`stop`/`receive`, events, `res_wifi`, remote buttons (`get_btn trig1 trig2`), `get_mac`, accessory version, radio test stubs.[^fw1] |
| `gps` | location from the phone over BLE. It prints latitude, longitude and status, sets the log level and saves `GPS_BLE.LOG` (`gps_main.c`).[^fw1] |

*Commands new in the OM-5 II 1.1 firmware. Handler addresses are in the address reference.*

In the OM-5 II firmware, `sys mdump` and `sys od tsk` work straight from the Wi-Fi shell, with no `:` route.[^fw1] `mem_put*`,
`chgpri`, the `Oly*` calls and `flash` change state. Never run those.[^fw1]

Other OM-5 II changes come from comparing the two command tables.[^fw2]

- `dbg` adds `reboot`, `nmiw`/`nmip`, `dmyp`, `backup`, `pset`/`pget`/`bset` and `first_startup_flag`. Treat all new
  words as writes.
- `flash` adds `erase`, `dump`, `rep` (replace test), `repinfo` and `running`. Still never run it.
- `wifi` adds firmware update CGIs (`fwup_*`), `ictlog`, `seclog`, `isc` and `myset`.
- `mcon` adds `backup`, `dump`, `dump2`, `errorchk`, `errorput`, `dbgput_*` and `usersetting backup`.
- `pwr` is rewritten for the USB-C power IC (`cblk.usb_type`, `sup_dbg`, `sup_off`, `chg_dbgall`).
- `ui led` gains enable and off-time control. `osd` adds `frameshift`, `framepos` and `eye`. `fcs set` adds TRACKING,
  MF ring, face select, ASTRO_AF, HDMI RAW output, focus limit and cluster options.
- `rec` drops `exif`. `face` drops the RAW test-image loader. `c3d` gains a GPU command tester (`C3D_CMD_START` ...).

## Safety summary

> [!WARNING]
> `flash`, `bas load`, `bas del`, `res write`, `res erase` and the `prm` writes change the camera's flash memory. Some of
> that data, such as the calibration, can't be restored. Never run them.

- **Never run.**[^fw1] [^inf1]
    - `flash` (any word), `bas load|del`, `res write|erase`, `prm setval|setstr|clear` and `mec dmgclear|dmgset`.
    - `file rm|rmdir|format|chmod` and `lens firmup`.
    - On the OM-5 II, `sys mem_put*|flash|chgpri|Oly*` and the new `dbg` words.
- **Changes the camera state but not flash.** Use these only with a reason and a plan.[^inf1]
    - `cam`, `mec motor|shutter|test`, `zoom exec`, `stbd con` and `pwr chg_*`.
    - `bc clk|rst|boot`, `usb tpc|pcreset` and `sdk shutdown*|sleep*|charge_sleep`.
    - `ui key|jog` (simulated presses) and `wifi`.
- **Writes the card.** These are safe for the camera. Use a spare card.[^inf1]
    - `sdk macro rec`, `olis set_*|remove|cancel*`, `albm add|dela|init` and `pos save`.
    - `spc write_*`, `fcs set 2` and `c3d test`.
- **Read-only and useful.**[^inf1]
    - `help`, `echo`, `sc heapshow|heaplist`, `sdk dbgall|dbgstate|power_info|media|showtimer` and `buff`.
    - `sync`, `movp`, `move`, `mvr dbginfo`, `avm history`, `syscall`, `damage get` and `take dbginfo`.
    - `bas list`, `olis print|num` and `albm geta`.
    - On the OM-5 II, `sys ps|od|mdump*|oserr`.

## Open questions

- Where `bas load` puts the script (resource kind and NAND address), and whether any boot path runs a stored script.
- What the OM-5 II ICT log records and where it is saved.
- The exact sub-command lists for `cam`, `per` and `lens` beyond the words above. The tables print in full with our
  lister.

## Address reference

E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 II is named.

| item | address |
|---|---|
| command table, first copy | `0x601faae8`, read only at `0x6019a4b0` |
| command table, second copy | `0x601fbe38`, read at `0x6019c827` and `0x6019c887` |
| executor | `0x6019c8d8` |
| string compare | `0x600e173b` |
| OM-5 II command table | `0x60210108`, read at `0x601b15b4` and `0x601b1614` (OM-5 II) |
| OM-5 II second copy | `0x6020eb90` (OM-5 II) |

*Command tables and the executor.*

<details><summary>Handler address of every stock command</summary>

| command | handler | command | handler |
|---|---|---|---|
| `echo` | `0x6019c7c9` | `tpc` | `0x6129e066` |
| `help` | `0x6019c802` | `sdk` | `0x607c2c6c` |
| `lens` | `0x600f095e` | `efct` | `0x60c368ad` |
| `aud` | `0x61433f09` | `buff` | `0x61422e80` |
| `cam` | `0x6140a21f` | `api` | `0x602daaf0` |
| `bas` | `0x60c192dd` | `c3d` | `0x60c24d58` |
| `pwr` | `0x61400e96` | `sync` | `0x605dd76e` |
| `bc` | `0x6010d41b` | `usr` | `0x6019a4f6` |
| `take` | `0x602a158b` | `damage` | `0x60163489` |
| `stbd` | `0x6016fbaa` | `spc` | `0x60c2aca1` |
| `per` | `0x61403371` | `mcon` | `0x61419304` |
| `res` | `0x60167cff` | `wifi` | `0x61217ed8` |
| `app` | `0x602daa9d` | `qr` | `0x612177e8` |
| `usb` | `0x60c30279` | `olis` | `0x6060236a` |
| `prm` | `0x6005b25f` | `mvr` | `0x61419514` |
| `flash` | `0x6005a245` | `pos` | `0x6121276a` |
| `rec` | `0x61423927` | `avm` | `0x603f07f4` |
| `file` | `0x6062d416` | `iseq` | `0x6142c068` |
| `sc` | `0x60101daf` | `img` | `0x6036453a` |
| `exp` | `0x604105e9` | `movp` | `0x6143643d` |
| `dbg` | `0x61401a03` | `md_sve` | `0x60c48545` |
| `ui` | `0x61408cf3` | `digizoom` | `0x6031ee26` |
| `mec` | `0x614068a6` | `zoom` | `0x60298cd5` |
| `fcs` | `0x6142c4c8` | `move` | `0x6143955d` |
| `dbgall` | `0x60199f4f` | `albm` | `0x60650030` |
| `sdet` | `0x603d7560` | `syscall` | `0x60057a1d` |
| `osd` | `0x60c1b9f4` | | |
| `mdet` | `0x6142be3b` | | |
| `face` | `0x603dc463` | | |
| `play` | `0x61435103` | | |
| `mddyna` | `0x60c484c8` | | |
| `disp` | `0x60183af5` | | |

*Stock 1.7 command handlers, in table order down each pair of columns.[^fw1]*

</details>

| item | address |
|---|---|
| `sdk` handler body | `0x6080a1cb` (the handler `0x607c2c6c` leads there) |
| `sdk` sub-command table | `0x60ad328c` |
| `bas` interpreter strings | `0x60e50fb4` to `0x60e51c40` |
| `bas load` 8.3 names | `0x60e51ea8`, `0x60e51eb4` |
| `bas load` code | `0x60c19627` |
| `bas load` resource write | `0x601678b0` (`res.c`) |
| `flash_mem:write_error` | `0x60c197a9` |
| `bas list` resource read | `0x60167060` |
| OM-5 II `img` | `0x6037aea1` (OM-5 II) |

*Sub-command tables, strings and helpers.*

| command | OM-5 II handler | detail |
|---|---|---|
| `ems` | `0x616288ea` | sub-command table `0x616704e8` |
| `sys` | `0x6005839b` | system executor `0x60057248` |
| `ictlog` | `0x6002530d` | |
| `ble` | `0x6151cc8a` | |
| `gps` | `0x6151f9e9` | |

*OM-5 II 1.1 handlers of the five new commands.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25. Desk research only, nothing was run on the camera.
[^fw2]: Read in the firmware, 2026-11-25, by comparing the stock and OM-5 II 1.1 command tables with our lister.
[^inf1]: Inferred from names and strings, not traced to the end, 2026-11-25.

