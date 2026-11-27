# Flash and hot shoe: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Flash and hot shoe](flash.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 drives a flash. It describes the strobe (STB) modules and tasks, the flash timing
block and its interrupt, the hot-shoe serial link, through-the-lens (TTL) pre-flash metering, the light-value
calculation, wireless RC flash, the sync sources tied to the shutter, flash firmware update over the shoe and the
`stbd` and `stb` debug shell. It also notes where the OM-5 II 1.1 program has the same code.

Everything here was read in the firmware. Nothing has been run on the camera yet.[^fw1]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred.

## Modules

The source file names come from the firmware's assert and trace strings. The code ranges come from our module list and
are in the [address reference](#address-reference).[^fw1]

<details><summary>The 20 flash modules and what each holds</summary>

| module | what |
|---|---|
| `stb_adj.c` | flash adjustment data, `stb_expose_get_wb_gain` (flash WB) |
| (calc, no file name) | `stb_calc_evaluation_*`, `stb_calc_light_value_*`, `stb_calc_metering_*`: the TTL maths |
| (ccd expose) | `stb_expose_frame_param`, `stb_expose_ccd_*`: sensor frame settings for metering frames |
| charge control | task STB_CHARGE, `stb_chg_main`, `stb_control_charge_*` |
| flash control | `stb_control_flash_*`, RC timing (`stb_control_flash_rc_iocontrol`: dt1-dt6, tm1-tm3), pre-time and HD counts |
| state / queue log | `stbd state`, `stbd qlog` |
| `stb_debug.c` | `stbd` debug commands |
| flash timing driver | registers of the flash timing block, its ISR (below). No file name string. |
| `stb_ext_firmup.c` | flash firmware update over the shoe |
| `stb_ext_microphone.c` | shoe microphone class |
| shoe serial glue | serial channel 13 set-up, TX/RX dump |
| `stb_external.c` | task STB_EXTERNAL: shoe device detection, commands, info, illuminator, `stb ext` |
| `stb_redeye.c` | red-eye pre-flashes |
| `stb_seq_expose.c` | expose result (pre1/pre2 GV, on-time, autosv, stbtv) |
| `stb_seq_flash.c` | `stb_seq_flash_main`, RC command parameters, input/output dumps |
| `stb_seq_metering.c` | pre-flash metering frames |
| task STB_SEQ | flash sequencer task loop |
| `stb_util.c` | face/AF coordinate helpers |
| `strobe.c` | `strobe_light_exec` (device, select) |
| C++ side | `CapFls_Flash` (`checkChargeState`), `CapFls_Notify*Observer` (charge, RC mode, STB mode, pop-up, external STB), `CmpSqp_SequencePartsBase::checkStrobeChargeState`. The shooting layer's view of the flash. |

*Flash modules in E-M5 III 1.7 block0, in address order.[^fw1]*

</details>

See also: [C++ shooting layer](../firmware/cpp-shooting-layer-technical.md).

## Tasks

The flash tasks are started from the section-2 task start list. Each is started by a task id held in a 16-bit
word.[^fw1]

| task | job |
|---|---|
| STB_CHARGE (`STB_CH` queue) | charge on, off, pause, restart and target for the internal and external units. Body `stb_chg_main`. |
| STB_EXTERNAL | shoe link: wake, detect, command queue, info |
| STB_SEQ | the flash sequence for a shot: pre-flash metering, light calculation, main flash, RC commands |
| `STBD_POST` | message post used by `strobe.c` and the debug commands |

*Flash tasks. Their id words and entry points are in the [address reference](#address-reference).[^fw1]*

The lock `STB_GIO` guards the flash GPIOs.[^fw1]

`stbd qlog` logs these queue commands.[^fw1]

- External com: ComOff, Com_On, ComPau, ComRes, ComOnc.
- Charge: ChgOff, Chg_On, ChgPau, ChgRes, ChgTgt.
- Others: BakOff, Bak_On, CheOff, Che_On, IllOff and Ill_On (AF illuminator), InfExp, ModSet, GetSta, Firmup, NonCom.

## The flash timing block 0x9b900000

The flash timing block is a small block of the system-on-chip (SoC) that times flash pulses. Only the flash timing
driver touches it. All 69 references sit in the driver's range.[^fw1]

### Interrupt

The first time the driver opens, it registers its interrupt service routine (ISR) on line 1, level 0, on the current
core.[^fw1] Before that it calls a clock and reset enable function twice, with (0,4,1) and (6,1,1). The lens driver
probably uses the first one too.[^inf1] Then it clears `+0x00` and `+0x04`.[^fw1]

The ISR reads the status at `+0x08` and the enable at `+0x0c`. It handles bits `0x1`, `0x10` and `0x100`, which are
cleared by writing 1. Then it calls a callback stored in the driver's state.[^fw1] This confirms line 1's owner in the
interrupt list.[^fw1]

See also: [Interrupts, timers and DMA](interrupts-timers-dma-technical.md).

### Registers

The register map comes from the field widths the driver clamps to. The names come from the driver's own debug strings
where they exist.

| offset | written from | meaning |
|---|---|---|
| `+0x00`, `+0x04` | 0 at open | reset or enable[^inf1] |
| `+0x08` / `+0x0c` | ISR | interrupt status / enable, bits `0x1`, `0x10`, `0x100` (`0x110` set on stop)[^fw1] |
| `+0x10` | `STB_REG_FLS_FLASH1` | flash-1 control. Bits 0-2 output select (cfg byte 2 bits 1/2/4), bits 4-6 trigger source 1-4 (cfg byte 0), bit 12 (cfg byte 3), bits 16-17 (cfg byte 1).[^fw1] Trigger-source values are in [Sync with the shutter](#sync-with-the-shutter).[^fw2] |
| `+0x14` | cfg +4, 1..32767 | pulse count or step[^inf1] |
| `+0x18`, `+0x1c`, `+0x20` | cfg +8/+12/+16, 18-bit | delay, on time and quench time in clock ticks[^inf1] |
| `+0x24` / `+0x28` | write 1 / bit 1 | start / busy[^inf1] |
| `+0x2c`, `+0x30` | arm: bit 0. Start-enable bits `0x1`, `0x10`, `0x100`, `0x1000`, `0x10000` by mode 0-4. | arm and start select[^fw1] |
| `+0x38`, `+0x3c`, `+0x44`-`+0x4c`, `+0x70` | RC config (cfg byte and halfword fields) | RC pulse-train set-up[^inf1] |
| `+0x50` | `STB_REG_FLS_WC` | second unit "WC". Bit 0 start, bits 4-7 and 8-11 from cfg +20/+22.[^fw1] |
| `+0x54`-`+0x68` | 6 pairs (13-bit, 8-bit<<16) | WC windows, likely in sensor lines. The sequencer works in `hd_cnt` and `hd_us`.[^inf1] |
| `+0x74`-`+0x98` | 10 pairs (15-bit, 9-bit<<16) | RC pulse table (width, count)[^inf1] |

*Registers of the flash timing block, as offsets from its base.*

The OM-5 II has the same driver with the same 38 register offsets. Its ISR is also on line 1, level 0.[^fw1]

## Hot-shoe link

The camera talks to a device on the hot shoe over serial channel 13 of the generic serial driver, `PER_SIO`. Which
hardware serial unit channel 13 maps to is held in a RAM table, so it can't be read from the image.[^fw1] The OM-5 II
uses channel 13 too.[^fw1]

### Port set-up

The port set-up fills a structure for channel 13.[^fw1]

- The 16-bit field at +6 is `0x300`.
- The 32-bit field at +8 is 20833. This is most likely the bit rate, 20.8 kbit/s.[^inf1]
- A TX-done callback and an RX callback are registered. The RX callback is the `RX_DATA` dump.
- Opening retries five times, 10 ms apart.

### Packets

Each transfer uses one buffer.[^fw1]

- The TX length is at +10 and the RX length at +12.
- Up to 200 TX bytes sit at +14 and the RX bytes at +214.
- RX is armed before TX, so a command and its reply are one exchange.
- The debug dumps are `TX_DATA`, `RX_DATA`, `com 10 rx_data`, `round 6/23 rx_data` and `round 11/24 tx_data`, for
  command numbers 10, 6/23 and 11/24.

### Wake and power

The log points are `WAKE_S` and `WAKE_E`, `EXPW_ON` and `EXPW_OFF` (power to the shoe), `EXCH_OFF`, `TX_ST`,
`sio time out`, and `[stb_ext_wait]` with `wait time com to x` and `x to com`.[^fw1] The last two are probably the
wait times between a command and the flash trigger.[^inf1]

The `stbd gior` list names the flash GPIOs.[^fw1]

- `PER_GIO_FLIGBT_SEL`, the IGBT select.
- `PER_GIO_EXFLCNDS`.
- `PER_GIO_PWCNTEXFL`, external flash power.
- `PER_GIO_EXFLCH`.
- `PER_GIO_FLCCHG`, charge.
- `PER_GIO_FLCFULL`, charge full.

Their port numbers and pin levels are not known.

### Detection and device info

The firmware logs `ext strobe detected ID`, `ext microphone detected` and disconnect events. Then it reads the device
info: maker code, firmware type, firm-up id, firmware and hardware version (BCD), extension and serial number.[^fw1]

The sequencer input keeps these fields for the external unit: `mode`, `bounce`, the GV limits for pre1 and pre2 in
normal and red-eye use, `pre_max`, `fp_min` and `fp_max` (the Super FP range), `id`, `code`, `firm_version` and
`damage`.[^fw1]

The firmware knows three device classes on the shoe.[^fw1]

- A flash.
- A microphone, in `stb_ext_microphone.c`.
- An LED video light, through `stbd ill`, `video_light` and `illum_video_quantity`.

### External commands

The `stb ext` command table lists the commands the camera can send to a shoe device.[^fw1]

<details><summary>The 19 shoe device commands</summary>

| number | command |
|---|---|
| 0 | INFO |
| 1 | STOP |
| 2 | START |
| 3 | PAUSE |
| 4 | RESTART |
| 9 | EXT_TEST |
| 10 | ONCE |
| 20 | EEREAD |
| 21 | EESET |
| 22 | EEWRITE |
| 23 | EECLEAR |
| 24, 25 | EEPROM 5-word write, read |
| 30 | RESET |
| 31 | READY_VOLTAGE |
| 32 | MAX_VOLTAGE |
| 33, 34 | RAM WRITE, RAM READ |
| 35 | SET AUTO (ISO, F-number) |
| 36 | SET MANUAL TIME (µs) |

*Shoe device commands from the `stb ext` table.[^fw1]*

</details>

`mode_en` turns TTL, AUTO and MANUAL on or off. The short codes are BON/BOF, EON/EOF, ION/IOF, MST, PA2, RE2, CHP and
CHR.[^fw1]

### Flash firmware update

`stb_ext_firmup.c` updates a flash's firmware over the shoe.[^fw1]

1. It sends a header with the maker, firmware, id, hardware, minor, major, extension, start address and size.
2. It sends START, then START TRANSMIT.
3. It ends with END, or ABORT.

## A flash shot

`stb_seq_flash_main` runs in the STB_SEQ task. Its input dump and output dumps give the data flow. The names below are
read in the firmware.[^fw1] The order is inferred.[^inf1]

1. **Input** from the exposure side. It holds Tv, Av, Sv, the Tv limits, `synchro_scan_shutter`, `sv_target`, flash on
   or off, the special and continuous take type and the face list (up to n faces with position, size and confidence).
   It also holds the flash mode settings (`mode_select`, `mode_redeye`, `mode_stb_slow`, `mode_stb_quantity`,
   `mode_stb_2nd` = second curtain, `mode_bracket_fl` and others), the RC settings and the external unit info above.
2. **Pre-flash metering** (`stb_seq_metering.c`). The sensor captures a **normal** frame with no flash and pre-flash
   frames **pre1** and **pre2** at two GV levels. Red-eye uses its own pre1 and pre2 levels. Each frame has its own Tv,
   Sv, gains and an AE area in sensor lines (`vd_area`, `hd_area_*`, `flash_delay_hd_cnt`, `pre_tv`). The pre-flash is
   timed inside the frame by line count. The metering waits for the lens aperture first (`wait_lens_aperture_post`).
   The results are `stbdata0` and `stbdata1` per frame, and face-expanded areas.[^fw1]
3. **Evaluation** (`stb_calc_evaluation_*`). It picks the pre frame to use (`select_frame`). It takes pre2 if pre1 is
   too weak, and checks saturation. It builds the AF-area mask, the area weights and the face areas.[^fw1]
4. **Light value** (`stb_calc_light_value_*`). It computes a target total from the normal and pre data (`stae_*` =
   strobe AE) for all, AF and face areas. Then it clips `main_gv_cap` to the unit's GV range.[^fw1] There is one
   variant per device.
    - **int** gives an on-time in µs from the table `stb_tbl`.
    - **ext** gives `ext_stb_gv`, sent over the shoe.
    - **rc** gives `rc_stb_gv`.
    - **commander**.

    Sv balance and Sv-up raise the ISO when the flash runs out (`flash_under`).[^fw1]
5. **Output.** `STB_EXPOSE` holds select, autosv, stbtv, check lamp, over/under, `stb_ae_ratio`, second curtain and
   `stb_ttl_direct_flash`. `STB_SETTING` holds `on_time` (µs), `ext_stb_gv`, `sync`, `select_frame`, `type`,
   `device`, `flash_stop_enable`, `igbt_out_type`, `hd_us`, `vd_us` and `radio_com_time`.[^fw1]
6. **Main flash.** The driver arms the flash timing block with the trigger source and times. The shutter fires it, as
   described below.[^inf1]
7. **White balance and EXIF.** The flash WB gain comes from `stb_expose_get_wb_gain`. The EXIF-side values are
   `teijouhosei` and `flash_under_flag`.[^fw1]

See also: [Exposure and white balance](../firmware/exposure-technical.md#flash-metering-is-separate).

## Sync with the shutter

The debug command `stbd manual [select] [inttime] [extgv] [sync]` names four sync sources.[^fw1]

- **00 STXIN**, the X contact input.
- **01 MSHDRV**, the mechanical shutter drive.
- **10 INROKOU**. The name is untranslated. It is probably the sensor-timed trigger used without a mechanical first
  curtain.[^inf1]
- **11 FWTRIG**, the firmware trigger.

Its select values are 01 internal, 02 external, 04 general (X) and 15 all.[^fw1]

`stbd flscont` takes select 4 = X, 8 = Sync and 12 = X+Sync. So the block has two outputs, X and a second sync
line.[^fw1]

`stbd manual` prints `STB_STX EN` and `STB_CURTAIN1_RUN` ("0: stx active / 1: stx inactive"). So the X input is the
first-curtain-run signal from the shutter.[^fw1] The shutter driver has `SET_SYNC A/B` steps.[^fw1] See also:
[Shutter](shutter-technical.md).

### Sync request to trigger source

The flash control code keeps a configuration for the timing block and prints its fields. Byte 0 is `stb_flash sync`,
byte 1 is `stselectcsb` and byte 2 is `stb_flash stchange`. A converter turns the request's sync word (+28) into
byte 0.[^fw2]

| request sync | `stbd manual` name | byte 0 | `+0x10` bits 4-6 | `+0x30` start bit |
|---|---|---|---|---|
| `0x000` | STXIN (X contact) | 1 | 1 | `0x1` |
| `0x001` | MSHDRV (shutter drive) | 3 | 3 | `0x100` |
| `0x010` | INROKOU | 4 | 4 | `0x1000` |
| `0x011` | FWTRIG (firmware trigger) | 0 | 0 | `0x10000` |
| `0x111` | (no name) | 2 | 2 | `0x10` |

*How a sync request becomes a trigger source in the timing block.[^fw2]*

The `stbd manual` help writes the sync values as 00, 01, 10 and 11. They match the request words `0x000`, `0x001`,
`0x010` and `0x011`.[^fw2]

- The outputs (byte 2) come from bits of request +16. Bit 1 sets output 1. Bits 2 and 4 set output 2.[^fw2]
- Request bit 16 picks the multi-pulse path instead of a single flash. That path writes up to 6 pulses to `+0x50` and
  the `+0x54` to `+0x68` pairs.[^fw2]
- Which shot types use the multi-pulse path, among Super FP, pre-flash and RC, is not traced. Pre-flash and FP are the
  likely ones.[^inf1]

### Sync speed and slow limit

The still exposure mode record, printed as `EXP_MODE`, holds `stb_sync` (+16), `stb_sync_prm` (+18) and
`shutter_stb_limit` (+28) next to `stb_slow`, `stb_fp` and `stb_expose`.[^fw1] These are most likely the X-sync and
flash slow-limit menu values.[^inf1] Their writer was not found in the always-loaded code.
`synchro_scan_shutter` and `ae_flash_point_tv` reach the flash sequence as inputs.[^fw1]

## Wireless RC flash

The RC settings are `mode_stb_rc_mode`, `_fp` (Super FP), `_ch` (channel), `_level` (command light level) and groups A
to D. Each group has a mode, a compensation (`rc_rev_*`) and a quantity (`rc_quantity_*`).[^fw1]

The command is light pulses from the commander flash on the shoe, sent in two bursts.[^fw1]

1. The **first** burst comes before the pre-flash. It carries the command, the light level, `rc_stb_gv`, the channel,
   the FP flag, the group modes, and `tm1` and `tm2` in µs.
2. The **late** burst comes after metering. It carries the light quantity per group and `tm3`.

`stb_control_flash_rc_iocontrol` sets dt1-dt6 and tm1-tm3.[^fw1] These probably fill the pulse-table registers `+0x74`
to `+0x98`.[^inf1]

`radio_com_time` and `radio_level` probably belong to radio wireless, a radio commander on the shoe.[^inf1]

## Debug shell

`stbd` is a user shell command. Its subcommands are `init`, `con`/`coff`/`cpau`/`cres`, `cloop`, `manual`, `full`,
`state`, `qlog [show|real|sender]`, `ext`, `ill`, `set`, `size`, `fls_inf`, `gior`/`giow`, `igbt [0 GIO / 1 IGBT]`,
`flscont <select> <count> <interval>`, `dbglog`, `dbgall` and `mic`.[^fw3]

- **Read-only:** `state`, `qlog show`, `size`, `fls_inf`, `gior`, `ext 0`.
- **Fire or write (don't use):** `manual`, `full`, `flscont`, `giow`, `igbt`, the charge commands, `ext 1-36`, `mic`.


## Open questions

- The pin-level shoe protocol (clock, levels, which pin carries data) and the meanings of the command bytes. It needs a
  logic analyser on an FL-LM3, or the `stbd qlog real` and `TX_DATA` dumps over the Wi-Fi shell (read-only, with a
  flash attached).
- The hardware serial unit behind channel 13. Reading the serial channel table on the camera would settle it.
- Who writes `stb_sync` and `shutter_stb_limit` in the exposure mode record, and which shutter `SET_SYNC` step drives
  the STXIN input.

## Address reference

E-M5 III 1.7 block0 addresses (file offset + `0x60021020`) unless the OM-5 II is named. OM-5 II addresses use the same
base in its expanded block0.

<details><summary>Module code ranges</summary>

| module | code |
|---|---|
| `stb_adj.c` | `0x60167cff`–`0x60168c9d` |
| (calc, no file name) | `0x60168c9d`–`0x6016c7c7` |
| (ccd expose) | `0x6016c7c7`–`0x6016cff2` |
| charge control | `0x6016cff2`–`0x6016db29` |
| flash control | `0x6016db29`–`0x6016f64d` |
| state / queue log | `0x6016f64d`–`0x6016fbaa` |
| `stb_debug.c` | `0x6016fbaa`–`0x60170e30` |
| flash timing driver | `0x60170e30`–`0x60172573` |
| `stb_ext_firmup.c` | `0x60172573`–`0x60173036` |
| `stb_ext_microphone.c` | `0x6017335c`–`0x60173848` |
| shoe serial glue | `0x60173ab2`–`0x60173cca` |
| `stb_external.c` | `0x60173cca`–`0x60178bda` |
| `stb_redeye.c` | `0x60178938`–`0x60178bda` |
| `stb_seq_expose.c` | `0x60178c1c`–`0x60179914` |
| `stb_seq_flash.c` | `0x60179af8`–`0x6017b88e` |
| `stb_seq_metering.c` | `0x6017ca1c`–`0x6017dc3d` |
| task STB_SEQ | `0x6017dfc3` |
| `stb_util.c` | `0x6017e1b1`–`0x6017e9fa` |
| `strobe.c` | `0x6017f0fb`–`0x6017f5d9` |
| `CapFls_Flash::checkChargeState` | `0x608e3ddb` |
| `CmpSqp_SequencePartsBase::checkStrobeChargeState` | `0x6099351d` |

*Flash modules and C++ entry points.*

</details>

| item | address |
|---|---|
| section-2 task start list | `0x6019cb00`–`0x6019cb4a` |
| STB_CHARGE id words (start list / module), entry | `0x60040b58` / `0x60040fce`, `0x6016cd32` area |
| STB_EXTERNAL id words, entry | `0x60040bea` / `0x60040fd0`, `0x601746db` area |
| STB_SEQ id word, entry | `0x60040bec`, `0x6017dfc3` |
| `STBD_POST` | `0x6017ebda` |
| lock `STB_GIO` id word, user | `0x60040ef4`, `0x6017e198` |
| `stbd qlog` | `0x601e328c` |

*Tasks, lock and queue log.*

| item | address |
|---|---|
| flash timing block | `0x9b900000` |
| ISR registration, ISR | `0x6017104f`, `0x60171866` |
| current-core function used at registration | `0x60069ec9` |
| clock and reset enable function | `0x60071fa6` |
| clear of `+0x00` and `+0x04` | `0x601718f1` |
| ISR callback | stored at `(*0x620f911c)+12` |
| `STB_REG_FLS_FLASH1` print | `0x6017169a` |
| `STB_REG_FLS_WC` print | `0x601717c4` |
| OM-5 II driver, ISR, registration | `0x60183900`–`0x60184200`, `0x6018416f`, `0x6018396e` |

*Flash timing block and its driver.*

| item | address |
|---|---|
| `PER_SIO` open, close | `0x6007046e`, `0x600705cd` |
| `PER_SIO` transfer, receive set-up, send, mode | `0x60073bf2`, `0x60073d19`, `0x60073d03`, `0x60073d2f` |
| serial channel table (RAM) | `0xa26431f8` |
| OM-5 II channel 13 use | `0x60186af5` |
| shoe port set-up, its structure | `0x60173e67`, `0x620f9488` |
| TX-done callback, RX callback | `0x60173af8`, `0x60173b48` |
| open retry | `0x60173ed4` |
| `stbd gior` list | `0x601e3388` |
| `stb ext` command table | `0x614519f7` |

*Hot-shoe link.*

| item | address |
|---|---|
| `stb_seq_flash_main` | `0x60179b67` |
| input dump | `0x6017b849` |
| timing-block configuration | `0x620f8c1c` |
| configuration field print | `0x6016e2db` |
| sync word to byte 0 converter | `0x6016e688` |
| multi-pulse path | `0x6016e33e` |
| still exposure mode record pointer, `EXP_MODE` print | `0x621694b8`, `0x61429cd2` |

*Flash shot and sync.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, desk research 2026-11-25. No camera runs.
[^fw2]: Read in the firmware, 2026-11-25, in a follow-up pass.
[^fw3]: Read in the firmware's help strings, 2026-11-25.
[^inf1]: Inferred, not traced to the end, 2026-11-25.

## History

- 2026-11-25: interrupt line 132 was taken for the flash. It is the display (TFT) driver. Corrected in the follow-up
  pass.

