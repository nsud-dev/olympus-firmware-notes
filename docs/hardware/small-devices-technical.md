# Small body devices: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Small body devices](small-devices.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the small devices around the system-on-chip (SoC): the serial channels, the eye sensor, the touch
panel, the accelerometer, the battery charger, the power-sequence chip, the analogue-to-digital (A/D) converter and the
temperatures, the buttons, dials and LEDs, and HDMI. It is desk research in the E-M5 III 1.7 firmware, compared with the
OM-5 1.2 and OM-5 II 1.1 firmware.[^fw1]

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless a body is named. Related pages cover the
[serial ports](interrupts-timers-dma-technical.md), the [buttons](../guides/button-press.md), the
[audio chip](audio-technical.md), the [power block](power-block-technical.md) and
[touch input above the driver](osd-drawing.md#input).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Summary

- **Serial ports.** Most small devices hang off the SoC's serial ports. The firmware addresses them through 13 logical
  channels. A table maps each logical channel to one of 8 physical ports, and several devices share a port.[^fw1]
- **Main I2C bus.** Port 6 (`0x98300000`) carries the touch controller (`0x48`), the accelerometer (`0x6b`), the
  power-sequence chip (`0x30`) and the I/O expander, all at 400 kHz.[^fw1]
- **Second I2C bus.** Port 3 (`0x98600000`) carries the eye sensor (`0x38`) and the battery charger (`0x09`), at
  400 kHz.[^fw1]
- **Port 1.** Port 1 (`0x98200000`) carries three SPI-type links. They go to the rear monitor panel, the EVF panel and
  the audio codec.[^fw1]
- **Touch gestures are decided in the touch controller.** The controller reports a gesture code. The driver only maps
  codes to gesture bits, drops the disabled ones, fixes the coordinates for the swivel screen and filters impossible
  sequences. No tap or double-tap timing exists in the driver.[^fw1]
- **The OM-5 II expects a newer accelerometer.** The OM-5 II 1.1 firmware expects a chip whose WHO_AM_I is `0x70`. The
  E-M5 III's chip answers `0x6a`, the same as the OM-5's. On a mismatch the driver stops and its task returns.[^fw1]
- **Battery.** There is no fuel-gauge chip. The firmware reads the pack voltage and the pack thermistor through the
  SoC's A/D converter and runs a USB charger chip over I2C.[^fw1][^inf1]
- **The OM-5 II.** Everything else here is the same in the OM-5 II 1.1 firmware, with the same channel map and the
  same eye-sensor and touch tables. The exceptions are the charger code, which the OM-5 II extends, and the dial
  table.[^fw1]

## Serial channels

The serial driver has 8 ports (see the interrupts page). It is reached through logical channels. The open call and the
transfer calls take the logical channel and convert it with a lookup. The lookup reads byte 0 of a 2-byte entry in the
channel map. A pointer to the map is set by board variant, and all variants use the same map. Each port has a register
block of `0x84` bytes. The OM-5 II 1.1 firmware has a map, register table and transfer calls with identical contents
at other addresses.[^fw1]

| logical | port | base | bus | device | I2C address (7-bit) |
|---:|---:|---|---|---|---|
| 1 | 1 | `0x98200000` | SPI-type | rear monitor panel control (`display_tft_tx_data_vsc`) | |
| 2 | 1 | `0x98200000` | SPI-type | EVF panel control (`display_bievf_*`: brightness, backlight) | |
| 3 | 1 | `0x98200000` | SPI | audio codec ([audio](audio-technical.md)) | |
| 4 | 2 | `0x98500000` | serial, 100 kHz descriptor | IS sub-CPU link (`bc` host, [stabiliser](stabiliser-technical.md)) | |
| 5 | 3 | `0x98600000` | I2C 400 kHz | eye sensor | `0x38` |
| 6 | 3 | `0x98600000` | I2C 400 kHz, 16-bit words | battery charger | `0x09` |
| 7 | 4 | `0x98400000` | | no user found | |
| 8 | 5 | `0x98700000` | UART | debug console[^inf1] | |
| 9 | 6 | `0x98300000` | I2C 400 kHz | touch controller | `0x48` |
| 10 | 6 | `0x98300000` | I2C 400 kHz | accelerometer | `0x6b` |
| 11 | 6 | `0x98300000` | I2C 400 kHz | power-sequence chip (PWRIC) | `0x30` |
| 12 | 6 | `0x98300000` | I2C 400 kHz | I/O expander ([driver swap](../bodies/expander-driver-swap.md)) | |
| 13 | 7 | `0x9a100000` | UART | hot-shoe accessory port (`stb_external.c`) | |

*Logical serial channels, their ports and devices. Read in the channel map.[^fw1]*

- A per-channel lock serialises each transfer (`PER_SIO LOCK FAIL ERROR`).[^fw1]
- An I2C message is built as {address byte, register, data...}. A read is {address, register, address|1}.[^fw1]
- The `per` shell lists the device drivers by name. They are backup, gio, pwm, clk, pcnt, adconv, timer, microtimer,
  dbgsup, usf, rotate, hproc, rtc, ioexp, ioexpdrv, pwric, eye, acc, acc_adj, slp, ccdtemp, wdt, sio and
  cpudma.[^fw1]

Channel 3 is a logical channel. It maps to port 1 at `0x98200000`, not to the block at `0x98600000`.[^fix2]

## Eye sensor

The eye sensor is on logical channel 5. Its driver runs the `PER_EYE_SENSOR` task with `EYES_*` events and the lock
`PER_EYE_IIC`. Set-up opens channel 5 at 400 kHz. The message builders for the write list and the read list put
address byte `0x70` or `0x71` first.[^fw1]

The register lists hold four kinds of entry.[^fw1]

- **Init.** `0x40` = `0xca`, the thresholds in `0x4b` to `0x4e` and the offset in `0x53` and `0x54`.
- **Start.** `0x41` = `0x42`, `0x42` = `0x02`, `0x43` = `0x21`, `0x4a` = `0x21`, `0x40` = `0x4a`.
- **Thresholds.** Two threshold sets.
- **Read.** The read list {`0x44`, `0x45`}.

That register layout matches the ROHM RPR-0521RS proximity and ambient-light sensor at address `0x38`. It has system
control at `0x40`, mode at `0x41`, proximity data at `0x44` and `0x45`, the interrupt at `0x4a`, the high and low
thresholds at `0x4b` to `0x4e` and the proximity offset at `0x53` and `0x54`. The firmware reads only the proximity
channel.[^inf1]

Two factory values set it up.[^fw1]

- `PRM_PER_EYESENSOR_ADJ_VALUE` (`0xfed2`) sets the near and far thresholds, kept in RAM.
- `PRM_PER_EYESENSOR_CROSSTALK` (`0xfec2`) sets the offset registers.

The board variant selects the default threshold set from a small table.[^fw1]

The sensor's interrupt reaches the driver (`[PER]EYE NOTIFY INT:`). The driver compares the 16-bit reading with the
thresholds and posts near or far to the display side (`EyeSensorFromPer`).[^fw1]

The OM-5 II 1.1 firmware has the same register lists, the same address and the same channel.[^fw1]

## Touch panel

The touch controller is on logical channel 9. The task `touchpanel_main` takes the commands `TP_OPEN`, `CLOSE`,
`SETUP`, `SETUP_AREA` and `CUSTOM`. The I2C write and read both go to address `0x48`, with 16-bit register addresses
(`addr %02x%02x data %02x`). The interrupt comes on a pin-interrupt line.[^fw1]

The event read takes 10 bytes from register `0x0000`.[^fw1]

- Byte 0, low nibble: the touch count.
- Byte 1, low nibble: the event code.
- Bytes 3 to 5 and 7 to 9: two points, 12 bits per axis.
- A zero event code is checked against register `0x1c0a` bit 2.

A gesture mapping turns the controller code into a gesture bit, through a switch table. An enable mask (`TP_MASK`)
gates it.[^fw1]

| controller code | gesture bit | name |
|---|---|---|
| 0 | `0x0001` | LIFTOFF |
| 1 | `0x0020` | CLICK (tap) |
| 2 | `0x0010` | TOUCHDOWN |
| `0x03`–`0x83` (high nibble = direction) | `0x0100` | SLIDE |
| 4 | `0x1000` | FLICK (falls back to LIFTOFF when disabled) |
| 8 | `0x0040` | DCLICK (falls back to CLICK when disabled) |
| `0x90` | `0x0080` | LONGPRESS |

*Controller gesture codes and the gesture bits the driver sets.[^fw1]*

### Where gestures are decided

The driver has no tap, double-tap or long-press timing. The codes above arrive from the controller.[^fw1] The driver
does three small things on top.

- It drops follow-ups that make no sense after the previous gesture. These are TOUCHDOWN after SLIDE, LIFTOFF after
  CLICK, DCLICK, FLICK or LIFTOFF, and LONGPRESS after LIFTOFF, CLICK, DCLICK or FLICK.[^fw1]
- It checks slides against the 720 × 480 screen.[^fw1]
- It flips the coordinates to (719 - x, 479 - y) for the swivelled monitor.[^fw1]

The controller is configured at open with 15 registers in page `0x1c`, from two tables chosen by panel type. These
likely hold its gesture timing.[^fw1][^inf1] The 150 ms and 800 ms tap figures on the [drawing page](osd-drawing.md#input)
come from om-emu's model, not from E-M5 III code.[^emu1]

Above the driver, the HFW callback `touch_panel_notify_callback` turns gesture bits into HFW statuses and the GUI
message (see the drawing page).[^fw1]

The OM-5 II 1.1 firmware has the same switch table and tuning lists. Its `[TP] FW Ver` debug print is gone.[^fw1]

## Accelerometer

The accelerometer is on logical channel 10. Its driver is `per_acc.c` plus a bus layer. The bus layer is named
`PER_ACC_SPI`, but it is I2C on logical channel 10 at 400 kHz. It sets the address `0x6b` (byte `0xd6`).[^fw1]

- **Open.** It reads register `0x0f` and expects `0x6a`. Then it writes `0x10` = `0x10` and `0x0d` = `0x01` and enables
  the interrupt pin 144. On a mismatch it logs `ACC Not-SUCCESS WHOAMI` and returns 2.[^fw1]
- **Sampling.** It reads 14 bytes from `0x20`. These are the temperature (`0x20` to `0x21`), the gyro (`0x22` to
  `0x27`) and the accelerometer (`0x28` to `0x2d`).[^fw1]
- **Chip.** WHO_AM_I `0x6a` at `0x0f`, address `0x6b`, CTRL1_XL at `0x10`, INT1_CTRL at `0x0d` and outputs from `0x20`
  are the ST LSM6DSL (6-axis).[^inf1]
- **Temperature correction.** Factory parameters `PRM_PER_ACC_X/Y/Z/TEMP` and `PRM_PER_ACC_TEMP_C_X/Y/Z` hold 30 values
  each (see [maintenance](../firmware/maintenance-technical.md)).[^fw1]
- **Users.** The level gauge (`OlyHfwOpeLevel::getSlope`, see [display](display.md)) and `per rotate`.[^fw1]

### Other bodies

- **OM-5 1.2** expects `0x6a` too, so it uses the same chip.[^fw1]
- **OM-5 II 1.1** expects `0x70` and writes `0x10` = `0x03`.[^fw1] `0x70` at `0x0f` is the WHO_AM_I of the newer ST
  LSM6DSV family, whose CTRL1 value `0x03` means 15 Hz.[^inf1] In an LSM6DSL, `0x03` in CTRL1_XL leaves the chip powered
  down.[^inf2]
- The E-M5 III and OM-5 II firmware both read the same 14 bytes from register `0x20` and write only `0x10` and `0x0d` = 1 on the open path. So
  the expected ID and the CTRL1 value are the whole chip difference.[^fw2][^inf2]
- The OM-5 II adds an accelerometer log command (`per acc ictlog`, at start-up and every 60 s).[^fw1]
- om-emu models the accelerometer for the E-M5 III and OM-5 firmware only, with id `0x6a` and writes `0x10` = `0x10`
  and `0x0d` = 1. That matches our reading. It does not model the OM-5 II firmware's chip.[^emu1]

### Driver block in the OM-5 II

The OM-5 II 1.1 driver keeps its state in one block.[^fw2]

| offset | content |
|---|---|
| `+0x0c` | ready flag, 1 after a good open |
| `+0x1c` | the 14 raw bytes |
| `+0x2a`, `+0x2c`, `+0x2e` | accelerometer x, y, z (int16) |
| `+0x32` | temperature (int16) |
| `+0x34`, `+0x36`, `+0x38` | gyro x, y, z (int16) |

*The OM-5 II 1.1 accelerometer driver block. Filled by its read callback and parse function.[^fw2]*

### Directions

An axis sign table turns raw readings into roll and pitch. The same code builds it from constants in the E-M5 III 1.7,
OM-5 1.2 and OM-5 II 1.1 firmware.[^fw3]

## Battery and charging

The charger is on logical channel 6. Charger access uses address byte `0x12` (7-bit `0x09`), 16-bit little-endian
words and the lock `PWR_INTCHA_IICWAIT`.[^fw1]

The firmware writes these registers at 36 sites.[^fw1]

| register | use | values |
|---|---|---|
| `0x14` | charge current | 400 or 800 mA |
| `0x15` | charge voltage, two cells | 8344 or 8048 mV |
| `0x3f`, `0x3b` | input current limit | 448 or 1360 mA |
| `0x3c` | | 899 or 931 |
| `0x3d` | | `0xa000` |
| `0x3e` | | 6016 |
| `0x39`, `0x4e` | | `0x1000` |

*Charger registers written by the E-M5 III firmware. It also reads `0x3a` and `0x85`.[^fw1]*

A 7-bit address of `0x09` with that register set matches a Renesas (Intersil) ISL9237/ISL9238-class buck-boost
charger.[^inf1]

The `pwr chg` shell shows the battery state.[^fw1]

- Battery voltage (`vbat16`, `vbat8`).
- Pack thermistor (`btemp thm_ad`).
- Source (1 = AC, 2 = battery).
- Level, and a temperature judgement (`jdg_batt_tmp`).

Battery grip support is off (`pbh not support!`).[^fw1] So the level comes from the voltage through the A/D converter,
with no fuel gauge in the pack.[^inf1]

The OM-5 II 1.1 firmware has 54 charger accesses against 36. It adds an input limit of 628 mA and zero-current states,
which fits the OM-5 II's USB-C power-source logic.[^fw1]

## Power-sequence IC

The power-sequence chip (PWRIC) is on logical channel 11. Its messages start with address byte `0x60` (7-bit `0x30`).
The driver has the commands init, on, off, set_mode, get_id, read and write register, and GPIO sequences (`gior`,
`giorf`, `giow`). Its log strings start with `[PWRIC]`.[^fw1] An earlier, wider driver range also took in the
`per pcnt` and `per pwm` drivers.[^fix1]

- **Power-on.** The `camons` path steps the chip through sequence steps 0 to 5. Each step goes through a wrapper that
  calls the step function with d0 = step and d1 = `0xff`. After step 5 it sets GPIO pin 110.[^fw1]
- **Power-off.** The `camoffs` path runs steps 5 and 4 down, with d1 = 0.[^fw1]

Which supply rails each step switches was not found in the code. The steps are indices into the chip's own
sequence.[^fw1]

## A/D converter and temperatures

The A/D block's results sit at `+0x3c` to `+0x58` of the block. It raises IRQ 163 (see the interrupts page). A request
takes a record {channel, period, count, buffer, callback}.[^fw1] Its users are these.

- Power, for the battery voltage and thermistor.
- `ccdtemp`.
- The key module's analogue keys (`key_matrix_adc`).
- The factory adjust code.

`ccdtemp` covers the imager temperature and a body thermistor (`thermal temp`). It has attention, warning and lock
thresholds per area, named ALEX, CAM, BAT and ACC, and a `Thermal Shutdown` path. It has its own shell.[^fw1]

The imager's own temperature comes from the [sensor](sensor-technical.md). The gyro temperatures come from the IS
sub-CPU.[^fw1]

## Buttons, dials and LEDs

### Buttons

The buttons are covered by the [button guide](../guides/button-press.md). The key image has the groups power (1 byte),
gio (3), dial (2), adc (1) and ext (2) (`key_matrix_*`).[^fw1]

### Dials

The dial code is `ui_jogdial_*`, with `JOG_SendEvent`. The set-up picks a dial table by board variant (8 bytes per
variant, all variants the same). It opens one hardware counter channel per entry. Stock has 3 entries (counter channels
0, 1 and 2), with a shared configuration.[^fw1]

The counter block has 4 channels in 2 units. Channels 0 and 1 are at `+0x00`, and channels 2 and 3 at `+0x80`. The
set-up writes these, per unit.[^fw1]

1. 0 to `+0x00` and `+0x04`. The same function registers the interrupt callback.
2. Configuration words to `+0x20` and `+0x28` per channel, and to `+0x14`.
3. 1 << channel to `+0x08`, also OR'd into `+0x0c`.
4. 1 to `+0x18` per channel and to `+0x10`.

The count is read from `+0x38` per channel. The register names are not known. The block sits next to the PWM block. It
is probably what the `per pcnt` shell calls the pulse counter.[^fw1][^inf1]

Counter channel 0 is the grip dial.[^fw1]

- Its event id `0x02032103` is `JOG_DIAL_GRIP1_SUB`. The SDK names are MAIN 0, SUB 1, GRIP1_SUB 2, GRIP2_MAIN 3 and
  GRIP2_SUB 4.
- It starts only when key line `0x2001` (debug name `EvIC`) reports the accessory. The start sets up pins 64 and 65,
  drives pin 93 high, waits 10 ms, then starts the channel.
- The GUI filter always passes the front and rear dials (`0x02031902` and `0x02031903`). It passes the grip dials only
  when grip state `0x02021001` or `0x02021003` is set.
- The body's own two dials are channels 1 and 2.
- Which accessory the firmware calls grip 1 was not checked.

The OM-5 II 1.1 dial table has only 2 entries, counter channels 1 and 2, and its set-up loop runs twice. The OM-5 1.2
keeps all 3. So the OM-5 II firmware never opens counter channel 0, and it has no grip gate.[^fw1]

### LEDs

Lamp control is in the UI module ("led can not control").[^fw1]

- There are 8 lamp slots, with a configuration pointer and 8 bytes per slot.
- Byte 0 is the type. 1 is a plain GPIO pin, and 2 is a PWM output through `per_pwm_*`.
- The word at `+4` is the pin or channel.

The slots are filled at start-up from a table in initialised RAM data, which is not in the unpacked block. So the pins
need the expanded stock image. `LedScenarioCtrl` and `OlyHfwLedCtrl` drive named scenarios on top.[^fw1] The OM-5 II
1.1 firmware has the same lamp module.[^fw1]

## HDMI DDC, EDID and CEC

HDMI is not on the serial ports. The HDMI transmitter is an on-chip block with 65 references in the code, next to the
`[HDMITOP]` sequence code. The OM-5 II 1.1 firmware references it the same number of times.[^fw1]

**EDID.** The DDC read lands in a 128-byte window inside the HDMI block.[^fw1]

- The firmware checks the fixed EDID header at `+0x00` and `+0x04` (`0x00`, six bytes of `0xff`, `0x00`).
- It sums the 128 bytes. The data is valid when the sum is 0.
- It keeps the manufacturer id (`+0x08` and `+0x09`) and reads the extension count (`+0x7e`).

So the DDC master is in the HDMI block, and the firmware only reads the result.[^fw1]

**CEC.** The CEC registers sit in a small area of the HDMI block.[^fw1][^inf1] Each access opens a gate bit 22 in
`+0x14` first, then reads a byte from bits 16 to 23.[^fw1]

- A `HDMI_CEC` task exists.
- The `disp es` shell sends test messages. These are a power key press, Report Physical Address, Active Source and Set
  OSD Name.
- `disp hd cec_info` shows the logical and physical address and the send queue.

CEC remote buttons reach the UI as key events. The key name table has `Hdmi` (the plug line) and `CEC1` to `CEC9` and
`CECP` after the normal buttons.[^fw1]

## Open questions

- Which rails each step of the power-sequence chip switches.
- The LED pin numbers. The table is in initialised RAM data and needs the expanded stock image.
- The meanings of the CEC registers.

## Address reference

E-M5 III 1.7 block0 addresses unless a body is named.

| item | address |
|---|---|
| serial driver init (interrupts page) | `0x6006e7aa` |
| channel open, transfer calls | `0x60069402`, `0x6007046e`, `0x600705cd` |
| logical-to-port lookup | `0x60070744` |
| channel map, pointer set at, variant pointer | `0x600c2580`, `0x6007045c`, `0x600c25b4` |
| port register blocks | `0x600c1ee8` + `0x84` × port |
| OM-5 II 1.1: map, register table, transfer calls | `0x600d84f4`, `0x600d7e5c`, `0x60074502`, `0x60074661` |
| `per` shell table | `0x61445230` |

*Serial channel code and tables.*

| item | address |
|---|---|
| eye sensor driver | `0x60066d16` to `0x6006783d`, set-up `0x60066d16` |
| eye sensor message builders, write and read | `0x60067043`, `0x60067106` |
| eye sensor register lists | `0x600c0ba0` (OM-5 II 1.1 `0x600d6f40`) |
| eye sensor thresholds in RAM, near and far | `0xa263cf28`, `0xa263cf2a` |
| eye sensor default threshold table | `0x600c0b90` |
| eye sensor interrupt print, display hand-off | `0x600676a2`, `EyeSensorFromPer` `0x6019a9b0` |
| `touchpanel_main` | `0x60197536` |
| touch I2C write, read | `0x601983c2`, `0x6019873a` |
| touch interrupt enable, disable | `0x60067a50`, `0x60067a8d` |
| touch event read | `0x60198ed2` |
| gesture mapping, switch table, enable mask | `0x60197da7`, `0x601fa2d4`, `0x62105d3c` |
| follow-up filter, slide check, coordinate flip | `0x60197ea5`, `0x6019973c`, `0x60199d02` |
| touch tuning tables, panel type | `0x601fa4bf`, `0x601fa4dd`, `0x601810a9` |
| `touch_panel_notify_callback` | `0x608744a2` |
| OM-5 II 1.1: touch switch table, tuning lists | `0x6020e634`, `0x6020e79c` |

*Eye sensor and touch panel.*

| item | address |
|---|---|
| `per_acc.c` | `0x60060975` to `0x60060e28` |
| accelerometer bus layer, address set-up | `0x60062ed8` to `0x6006322e`, `0x60062ed8` |
| accelerometer open, sampling | `0x60060c17`, `0x60060d12` |
| OM-5 II 1.1: driver block | `0x61ed20a0` |
| OM-5 II 1.1: read callback, parse | `0x60065030`, `0x6006504f` |
| axis sign table, filled by | `0x619e2610`, `0x60064c9c` |
| charger access | `0x6005ee5c` |
| `pwr chg` shell | `0x61400e96` |
| PWRIC driver, log string sites | about `0x6006d951` to `0x6006de24`, `0x6006da33`, `0x6006dbf5` |
| `per pcnt` driver, `per pwm` driver | `0x6006d357` to `0x6006d5bb`, `0x6006d669` to `0x6006d8db` |
| PWRIC step wrappers, step function | `0x6004198d` to `0x60041a1b`, `0x60041b24` |
| GPIO set after step 5 | `0x6006791e` via `0x600678e3` |
| power-off steps | `0x60041a76`, `0x60041a8f` |

*Accelerometer, charger and power-sequence chip.*

| item | address |
|---|---|
| A/D block, driver | `0x98c00000`, `0x60063247` to `0x60063717` |
| A/D request | `0x600635c8` |
| A/D users: power, `ccdtemp`, analogue keys, factory adjust | `0x6005d88a`, `0x60064f82`, `0x60120f6f`, `0x61232a89` |
| `ccdtemp`, its shell | `0x60064b63` to `0x600656c9`, `0x61402bc6` |
| `key_matrix_*` | `0x60121569` |
| `ui_jogdial_*`, `JOG_SendEvent` | `0x6011fb60` on, `0x6011fe86` |
| dial set-up, variant table | `0x6011fa9f`, `0x601b7c44` + 8 × variant |
| dial table, shared configuration | `0x601b7c08`, `0x601b7c20` |
| counter block, PWM block | `0x9bd00000`, `0x9bc00000` |
| counter set-up steps 1, 2, 4 | `0x601230ab`, `0x60123116`, `0x60123184` |
| counter read | `0x60123163` |
| OM-5 II 1.1: dial table, set-up loop | `0x601cbb38`, `0x6013088e` |
| OM-5 1.2: dial table | `0x601ca2a8` |
| dial SDK names | `0x60ae0547` |
| grip dial start | `0x6011f8f7` |
| GUI dial filter | `0x607c96aa` |
| lamp control, configuration pointer, start-up table | `0x601223b1`, `0xa26531c4`, `0x61e8c9cc` |
| lamp GPIO set, PWM driver (`per_pwm_*`) | `0x6006791e`, `0x6006d669` on |
| OM-5 II 1.1: lamp string | `0x601cc2d8` |

*Temperatures, buttons, dials and LEDs.*

| item | address |
|---|---|
| HDMI transmitter block | `0x99c07000` |
| HDMI driver, `[HDMITOP]` sequence code | `0x6018b04e` to `0x6018c5e5`, `0x6018ccdc` |
| EDID window | `0x99c07c00` |
| EDID check, checksum | `0x6018ba14`, `0x6018c2cd` |
| CEC register area, CEC code | about `0x99c07a60` to `0x99c07a9c`, `0x6018c2e9` to `0x6018c566` |
| key name table | `0x602512b4` |

*HDMI.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the E-M5 III 1.7 firmware, 2026-11-25, checked against the OM-5 1.2 and OM-5 II 1.1 firmware. Desk research only.
[^fw2]: Read in the OM-5 II 1.1 firmware, 2026-11-26.
[^fw3]: Read in the E-M5 III 1.7, OM-5 1.2 and OM-5 II 1.1 firmware, 2026-11-27.
[^inf1]: Inferred, 2026-11-25.
[^inf2]: Inferred, 2026-11-26.
[^emu1]: From om-emu's model, facts only.
[^fix1]: Corrected 2026-11-25. The earlier driver range `0x6006cccd` to `0x6006de24` also covered the `per pcnt` and `per pwm` drivers.
[^fix2]: Corrected 2026-11-25. The audio page had called channel 3 "block `0x98600000`". It was corrected there.

## History

- 2026-11-25 · The power-sequence chip's driver range was narrowed. The earlier range also covered two other drivers.
- 2026-11-25 · The audio codec's channel 3 was read as a port. It is a logical channel on port 1.

