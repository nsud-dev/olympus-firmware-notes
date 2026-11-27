# Audio: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Audio](audio.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers how the E-M5 III 1.7 records and plays sound. It describes the external codec chip and its control
bus, the serial audio port and the sample converter in the main chip, and the audio tasks. It also covers the codec
register scripts (power, record, play, limiter, wind filter, plug-in power), beeps, the `aud` debug shell and the
hand-off of PCM into the movie file. The OM-5 II 1.1 program is compared at the end. Everything here is desk research.
Nothing was run on the camera.

Addresses are E-M5 III 1.7 block0 addresses (base `0x60021020`) unless the OM-5 II is named. They are listed in the
[address reference](#address-reference). Codec register names follow the public WM8962 register map and are inferred
like the chip itself.[^inf2]

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred.

## Layers

| layer | parts | what |
|---|---|---|
| UI and apps | `CapAud_AudioCtrl.cpp`, `CapPcs_PlayControlSound.cpp`, `OlyHfwOpeSndCtl*`, the `SoundCtrl::*` API | beeps, voice memos, slideshow music, mic device changes, level meter |
| clients | MVR (movie), `REC_SOUND` (voice memo), `PLAY_SOUND`, `MOVP_AUDIO` and `move_if_aud.c` (playback, edit) | send commands to the audio tasks |
| audio API | send and wait (trace id `0x8010`), send (`0x8011`), WAV info (`0x8021`), mixer open, run and close (`0x8070` to `0x8072`) | thin wrappers, all traced through one trace function |
| audio tasks | CPU0 `AUD_MAIN` and five helpers, CPU2 `AUD_WAKEUP` and `AUD_LEVEL_MONITOR` (see [Tasks](#tasks)) | message loop, record and play sequences |
| sequences | `aud_seq_*` | power, device change, play, record, WAV chunks, slate tone |
| codec scripts | a dispatcher, a runner and 37 lists | register write lists per state (see [Codec register scripts](#codec-register-scripts)) |
| codec bus | a queue, a sender and a single-access function | SPI on serial channel 3, 4 MHz |
| serial audio port | its driver, IRQ 23 | I2S-type port with a ping-pong DMA per direction |
| sample converter | `sca_drv_*`, IRQ 24 | memory-to-memory mix, gain and format conversion |

*The audio layers from the apps down to the hardware.[^fw1] Addresses are in the [address reference](#address-reference).*

## Codec chip and control bus

The codec is an external chip with 16-bit registers. The program keeps a shadow of `0x301` 16-bit registers, filled at
start from a default table. Register writes go through one write function, called with a register and a value. It
refuses addresses above `0x4d00`.[^fw1]

**Bus.** The codec is driven over SPI on serial channel 3.[^fw1]

- A write is queued as a 6-byte entry {u16 type, u32 frame}. The queue holds up to 1,400 entries. Type 0 is a register
  write, type 1 a delay.
- The sender takes channel 3 of the serial driver. It sets the channel up with a 4,000,000 Hz clock and a 4-byte
  frame, and drives chip select on pin `0x6b`.
- Channel 3 is a logical channel. The channel map sends it to port 1, block `0x98200000`.[^fix1] See also:
  [small devices](small-devices-technical.md#serial-channels).

**Frame format.** A frame is 32 bits. Bit 31 = read, bits 30-16 = register address, bits 15-0 = data. A read sends the
same frame with bit 31 set and returns the data word.[^fw1]

**Pin `0x74`** is driven around codec power changes. Pin `0x6b` doubles as chip select.[^fw1] What pin `0x74` does
(reset, power or mute) is open.

**Which chip.** The firmware never names it. The register layout matches the public register map of the **Wolfson (now
Cirrus Logic) WM8962** codec.[^inf1] The evidence is this.

- The SPI format above, a read/write bit, a 15-bit address and 16-bit data.[^fw1]
- The script names "notch" and "retune". "ReTune" is the Wolfson/Cirrus Logic name for its EQ.[^fw1]
- A program upload of 1,097 writes into registers `0x2000` to `0x24f4` at power-on, a DSP instruction and coefficient
  RAM.[^fw1]
- The registers the scripts touch: `0x00`/`0x01` input PGA, `0x11`-`0x13` ALC, `0x19`/`0x1a` power, `0x7c`-`0x81`
  clocking and PLL, `0x9b`-`0xa2` FLL, `0x108`-`0x10f` filters, `0x114`-`0x119` DRC, `0x300` and `0x40d` DSP
  control.[^fw1]

A read of the chip-ID register over the Wi-Fi shell (`aud ic` and an address, see [Debug shell](#debug-shell-aud))
would settle it.

**Calibration trims.** One function reads property `0x3af9` index 0 and 1, one signed value per channel. It looks the
value up in a table and writes registers `0x101`/`0x104` and the top five bits of `0x10d`/`0x10f`.[^fw1] This reads
as a per-body microphone level trim.[^inf1]

## Codec register scripts

Each state is a list of 20-byte entries, run by one runner function.[^fw1]

```
{u16 reg, u16 value, u16 shift, u16 mask, u8 mode, u8 source, u16 property, u16 index, u16 mask2, u32 hook}
```

- **Mode.** 0 writes the field, 1 only updates the shadow, 2 waits `value` ms, 3 calls the hook, 4 writes the value as
  is.
- **Source.** 0 is the constant, 1 a property (read through the property getter), 2 the hook.

So most tuning (ALC, DRC, ADC volume) comes from properties, not from the lists.[^fw1]

The dispatcher takes a command number, looks it up in its command table and runs these lists.[^fw1]

| cmd | lists (entries) | meaning |
|---|---|---|
| 1 | poweron_0 (28), poweron_1 (1,097), notch_48k (72), retune_48k (132), poweron_2 (33) | power on, clocks, DSP program upload, default filters |
| 2 | poweroff (10) | power off |
| 21 / 22 | output_vol (13) / input_vol (16) | volume |
| 31 | play_rec_ready_48k_0 (16) or rec_ready_96k_0 (16) + notch_96k + retune_96k, rec_ready_end (6), then one rec_start list | record start |
| 32 | rec_end (7) | record end |
| 41 | play_rec_ready_48k_0 or play_rec_ready_96k_0, play_ready_end (3), play_start_hp (15) or play_start_spk_48k / 96k (59) | play start |
| 42 | play_end_hp (3) / play_end_spk (5) | play end |
| 71 | spk_mute_on / spk_mute_off (1 each) | speaker mute |
| 81 | change_to_spk (3) / change_to_hp (28) | output device change |
| 91 | change_to_mic_internal / general / ic_recorder, limit on or off (66-74) | input device change during recording |
| 51, 61, 62, 72 | no list | handled in code |

*Codec commands and the register lists each one runs.[^fw1]*

Record-start lists exist for three inputs × limiter on/off, all at 48 kHz. They are `rec_start_internal_mic_*`,
`rec_start_general_mic_*` and `rec_start_ic_recorder_*`. 96 kHz uses the same start lists after the 96 kHz ready, notch
and retune lists.[^fw1]

## Inputs, gain and processing

**Devices.** The `aud` shell help names the devices.[^fw1]

- Input devices (`aud set_mic`): 0 internal mic, 1 external mic, 2 general mic, 3 IC recorder.
- Output devices (`aud set_dev`): 0 speaker + line, 1 speaker, 2 line, 4 HDMI, 8 headphone, 12 headphone + HDMI.

Which of these the E-M5 III body wires is not settled by the code, because the lists are shared with other bodies.

**Socket evidence in stock 1.7.** These show what the program supports, not what this body has wired.[^fw1]

- A headphone state exists end to end. There is an event `EV_EXTERNAL_HEADPHONE`, a getter
  `CameraCommon::getHeadPhoneState`, a headphone volume timer and a slideshow step that restores the headphone volume.
- `stb_ext_microphone.c` is not the 3.5 mm jack. It is a command handler (`0x2000` to `0x2002`) in the
  external-accessory protocol (`stb_external.c`), so it talks to a smart accessory microphone.
- Plain jack detection was not found by name.

**Calibration properties.** The names come from the property table, and all three are stored in FLASH.[^fw1]

- `PRM_AUD_SIGNAL_DIFF_INMIC` `0x3af9` (4 bytes) is the internal-mic left/right trim read by the trim function above.
- `PRM_ADJ_AUDIO_CORRECT` `0x5bec` (21 bytes).
- `PRM_AUDIO_RMS` `0x03fa` (6 bytes).

The ALC, DRC, wind and gain properties are not in that name table.

**Recording volume.** A hook writes registers `0x00`/`0x01`, a 6-bit PGA.[^fw1]

- Level + 10 indexes property `0x3811` (left) / `0x3821` (right) for the internal mic and `0x6421` / `0x6431` for the
  other mics. So the menu's −10 to +10 maps to 21 table entries.
- The IC recorder uses the fixed properties `0x3b61` / `0x3b71`.
- Registers `0x20`/`0x21` (input mixer) also switch between internal and external.

**Volume limiter.** The "limit_on" and "limit_off" lists differ in two register groups.[^fw1]

- The ALC registers `0x11`-`0x13`, from properties `0x4951`, `0x4961`, `0x4971`, `0x4981`, `0x3451` and `0x3461`.
- The DRC registers `0x114`-`0x117`, from properties `0x74a2` to `0x74f2` and `0x7512`.

Property `0x7512` holds the DRC fields per case. Index 0-3 is limiter on, 4-7 limiter off and 8-11 speaker playback.
ADC volume (`0x15`/`0x16`) comes from `0x3832`/`0x3842` index 0-2 by input.[^fw1]

**Stock quirk.** In stock 1.7, `rec_start_internal_mic_limit_off_48k` reads the **limiter-on** DRC fields (`0x7512`
index 0-3). Every other "limit_off" list reads index 4-7. The OM-5 II 1.1 list reads 4-7.[^fw1] So on the stock body,
starting a recording with the internal mic and the limiter off loads part of the limiter-on DRC set. It stays until a
device change re-applies the off set.[^inf1]

**Wind noise filter.** The hook `aud_soundic_windcut` reads setting `0x7871` (`PRM_MODE_WIND_NOISE_DECREASE`).[^fw1]

- Values 0 / 2 / 6 / 10 = off / low / standard / high pick index 0-3 at 48 kHz or 4-7 at other rates.
- The coefficient comes from property `0xdac4`[index] and goes to register `0x109`.
- Register `0x108` = 3 (both channels on) for inputs 0 and 2, and 0 for input 3 (IC recorder).

So the wind filter is the codec's high-pass filter with a per-rate cut-off.[^fw1]

**Plug-in power.** Three hooks use one plug-in power flag. Register `0x19` gets `0xfe` (bit 1 set) for the internal
mic always. For inputs 2 and 3 it gets `0xfe` only when plug-in power is on, else `0xfc`.[^fw1] Bit 1 is the mic
bias.[^inf2]

**Notch and "retune" lists.** These lists (72 and 132 writes per rate) load filter coefficients at power-on and on a
rate change.[^fw1] A notch is a fixed-frequency cut, likely for a body noise such as the IS or AF motor.[^inf1]

## Serial audio port `0x9bf00000` (IRQ 23)

Its driver is the only user of the block. It uses interrupt line 23 at level 3, set up with five callbacks.[^fw1]

| reg | use |
|---|---|
| `+0x00` | control: bits 0-2 format (from the open request), bit 3 / 4 clock or enable, bit 5 transmit run, bit 6 receive run |
| `+0x04` | frame format words (bits 0-16 common, 20-24 transmit, 25-29 receive) |
| `+0x08`, `+0x54`, `+0x58`, `+0x6c` | further format fields from the open request |
| `+0x0c` | receive control (bit 2 continue), `+0x10` / `+0x14` receive buffer A / B address, `+0x18` / `+0x1c` sizes, `+0x20` receive status (bit 0 / 1 buffer A / B done, write `0x100` / `0x200` to arm A / B, bit 24 start) |
| `+0x30` | transmit control (bit 2 continue), `+0x34` / `+0x38` transmit buffer A / B, `+0x3c` / `+0x40` sizes, `+0x44` transmit status (bits 0 / 1 / 5 / 4, write `0x400` / `0x800` to arm A / B) |
| `+0x2c` = `0xf`, `+0x50` = `0x38` | interrupt enables at set-up |
| `+0x70`, `+0x74` | transmit clock options, bit 0 of `+0x74` output enable |

*Registers of the serial audio port.[^fw1]*

- **Play** uses the transmit side, with port commands 1 open, 7 start and 4 stop.[^fw1]
- **Record** uses the receive side, with commands 2, 8 and 5.[^fw1]
- **Refill.** Each side refills the idle buffer from the interrupt, stepping through a ring of buffers.[^fw1]
- **Port clocks.** One function sets six clock dividers (ids 0, 7, 2, 3, 4, 5) and gates `0x11`, `0x12` and
  `0x1c`.[^fw1] This is the `AIO` clock group of the `per clk` list.[^inf1]

## Sample converter `0x9c600000` (IRQ 24)

The driver functions are called `sca_drv_*`, names from its trace strings. The block's clock gate is bit 23 of the
system clock-gate words. It uses interrupt line 24 at level 5.[^fw1]

- **Channels.** Three channels: input 1 at `+0x20`-`+0x28`, input 2 at `+0x2c`-`+0x34`, output at `+0x38`-`+0x48`.
  Each has an address, a format word (bit 4 = not 8-bit, bit 0 = mono) and a length.[^fw1]
- **Control.** `+0x18` packs the three channel modes. `+0x00` bits 0 / 4 reset. `+0x08` = 7 and `+0x0c` = 1 start a
  job.[^fw1]
- **Mix and filter.** Mix registers `+0xfc`-`+0x188` are zeroed by `sca_drv_MixRegSetup`. Filter registers are set by
  `sca_drv_FilterRegSetup`.[^fw1]

`aud_seq_sca_open` logs "1./2./Out. ch_num, bit_depth". `aud_seq_sca_exec` logs per input the address, length,
endian, digital volume and filter pattern, plus a fade flag.[^fw1] So the block mixes two PCM streams into one with
gain, fades and format or rate conversion, memory to memory.[^inf1]

**Users.** Movie editing and playback use it through `move_if_aud.c` / `movp_if_aud.c`, which open it with two
2-channel 16-bit inputs and a 2-channel 16-bit output.[^fw1] The play sequences use it too
(`sca_drv_Play_Update`).[^fw1] Mixing a beep over movie sound is the likely use of the second input.[^inf1]

## Tasks

| core | task (id) | what |
|---|---|---|
| 0 | `AUD_MAIN` (`0x5a`) | message loop. Starts the tasks below, then serves messages 2 to `0x89` from its message table. |
| 2 | `AUD_WAKEUP` (`0x2017`) | runs codec command 1 (power-on with the 1,097-write DSP upload) at start-up, then posts a call back to CPU0[^inf1] |
| 0 | `AUD_COPY_DATA` (`0x59`) | copies and converts PCM between the port ring and the client buffers ("CVT / RING / WAV" fields) |
| 2 | `AUD_LEVEL_MONITOR` (`0x200d`) | level meter (`SoundCtrl::startLevel/getLevel/endLevel`) |
| 0 | `AUD_WATCH_DOG` (`0x07`) | re-initialises the codec after a fault ("video on(wd) - static electricity" in the shell help)[^inf1] |
| 0 | `AUD_LATE_RISER` (`0x31`) | debug. Plays `HOGE.WAV`, records 48 kHz 16-bit or 96 kHz 24-bit. |
| 0 | `REC_SOUND` (`0x22`), `PLAY_SOUND` (`0x1d`) | voice memo recorder, sound player |
| 0 | `MOVE_AUDIO` (`0x53`), `MOVP_AUDIO` (`0x50`). CPU2 `MOVP_AUDIO_SUB` | movie edit and playback audio |
| 1 | `AVM_P1_AUDIO`, `AVM_P2_AUDIO`, `AVM_DMY_AUDIO` | movie file audio streams |

*Audio tasks by core. Task ids and entries from [CPU1 and CPU2](cpu1-cpu2-technical.md).[^fw1]*

`AUD_WAKEUP` means the slow SPI upload runs on CPU2.[^inf1] The tasks share the data queues `AUD_SND_DTQ`,
`AUD_RCV_DTQ` and `AUD_iSND_DTQ` and the event flag `AUD_REF_FLG`.[^fw1]

## Sample rates and formats

**48 kHz, 16-bit stereo** is the default everywhere. **96 kHz, 24-bit stereo** exists in the codec scripts, the record
and play sequences and the debug recorder.[^fw1]

**Movie audio.** The movie recorder sets 2 channels, 16 bits and 48000 Hz unless byte `+0xd` of the movie settings
record is set. Then it sets 24 bits and 96000 Hz. That byte is copied from byte `+0x16` of the settings message. The
AVM filler then writes LPCM with bitrate = bits × rate × 2.[^fw1] Which menu item sets the byte, and whether any
E-M5 III menu does, is open. See also: [movie encoder stack](../firmware/movie-stack-technical.md#audio-filler-0x603ed33a).

**Where the 96 kHz flag comes from.** The settings message is built from the movie recorder's per-mode record. The
record is `0x408` bytes per mode, with a u16 mode index.[^fw1]

- The message's byte `+0x16` is copied from record `+0x310` (sub-record `+0x2bc`, field `+0x54`).[^fw1]
- Nothing in the movie code range writes `+0x310` by name. So the record is likely filled as a block from a CPU0
  settings message.[^inf1]
- The CPU0 side, and so the menu item, is still open.

**96 kHz clips.** The album code (`albm`) keeps `audio_quality` per clip (1 = 48kHz16bit, 2 = 96kHz24bit) and refuses
to mix qualities in one album. The web server reports it per file, from file info `+0x6c`.[^fw1] So a 96 kHz clip is a
supported file type, whatever sets it.

**OM-5 II 1.1 guard.** The same message builder exists, with its fields moved down one byte. The movie-recorder setup
picks 96 kHz / 24-bit only when two conditions hold. Otherwise it forces 48 kHz / 16-bit.[^fw1]

- The record's new u16 at `+0x06` (from message `+0x06`) is 0.
- Its flag byte `+0x0f` (from message `+0x17`) is set.

What `+0x06` holds is open, for example a frame-rate or output mode that cannot carry 96 kHz. The OM-5 II also logs
the HDMI audio formats `DISP_HDMI_48KHZ_16BIT_2CH` / `DISP_HDMI_96KHZ_24BIT_2CH`.[^fw1]

**Voice memo.** `REC_SOUND` has the same 48 kHz 16-bit / 96 kHz 24-bit switch, on its request `+0xf6`. WAV files carry
the chunks ICRD, etim, erel, ecor and emdl (`command_rec_wav_style`).[^fw1]

**From recording to the MOV file.** Recorded PCM leaves the CPU0 audio tasks and reaches the CPU1 AV framework.[^inf1]
The objects on the way are these.[^fw1]

1. `CAvpiAsoAudioSource`, with an external-interface bridge and proxy (`CAvpiAsoExtIfBridge`, `CAvpiAsoExtIfProxy`).
2. `CAvpiAenAudioEncode` (LPCM, no compression).
3. `CAvpiM4mMp4TrakAudio` in the MOV muxer.

The kernel objects `AUD_BRIDGE_LITE_CPU0`, `AUD_BRIDGE_LITE_CPU1`, `AUD_BRIDGE_EXEC`, `AUD_BRIDGE_POST` and
`MOV_ENC_AUDIO_CPU1` name the crossing.[^fw1] The demuxer accepts `lpcm`, `sowt` and `twos` sample entries.[^fw1]

## Beeps and system sounds

- **Sound kinds.** There are 18, with a volume parameter each. The table holds a name and a "short sound" flag per
  kind. They are `PRM_AUD_SHUT1-3_VOL` (shutter sounds), `CSHUT1-3`, `EFFECT1-3`, `EVENT1`, `ERASE1`, `SELF`
  (self-timer), `AFOK` (focus beep), `BGM` (slideshow music), `WARNING`, `START1`, `MOVRECS` (movie start) and
  `ADJVOICE` (service voice).[^fw1]
- **Volumes.** Each play sets four volumes, speaker, video (line), HDMI and headphone
  (`app_control_sound_set_sound_volume`, `VOL_Play`).[^fw1]
- **Slideshow music.** 5 built-in BGM resources plus imported sounds (`SoundCtrl::startImportSound` and the
  `OlyHfwOpeSndCtl` import calls).[^fw1]
- **HDMI audio.** `display_set_hdmi_sound_format` and the EDID audio block parser
  (`LPCM %02dkHz %02dbit %02dch`).[^fw1]

## Debug shell `aud`

The user shell has an `aud` command. Its read-only items are useful for a camera check over the
[Wi-Fi shell](../features/wifi-debug-shell-technical.md).[^fw1]

| command | does |
|---|---|
| `aud ic [reg]` / `read_reg` | read a codec register |
| `aud status` | codec registers and task status |
| `aud get_dev`, `aud get_vol`, `aud get_mem` | current output device, volumes, buffer addresses |
| `aud log 0..3` | print / clear / start / stop the access log |
| `aud debug MODE` | message levels |

*Read-only `aud` commands.[^fw1]*

Commands that change state are not for a first check. They are `write_reg`, `poweron`, `poweroff`, `video_on`,
`video_off`, `rec` (records to `AUD_DEBUG_BUFF_ADDR`), `play`, `play_wav`, `ld_bgm`, `set_vol`, `set_dev`, `set_mic`,
`sound`, `repeat` and `detect` (fakes a headphone insert). `dbgaud` is a separate tool for
`CapAud_AudioCtrl`.[^fw1]

## OM-5 II 1.1 compared

The OM-5 II uses the same codec and the same scripts. 34 of the 37 lists are identical, entry for entry. The serial
audio port and converter registers are the same.[^fw2]

The differences are these.[^fw2]

- Two new one-write lists, `asic_master_i2s_48k` / `_96k` (register `0x07` = `0x0002` / `0x000a`). The register is
  the audio interface format.[^inf1]
- `play_start_hp` adds two writes and writes `0x45` at once instead of only shadowing it.
- The IC-recorder start lists add the mic-power hook.
- `rec_start_internal_mic_limit_off_48k` reads the limiter-off DRC fields, so the stock quirk above is fixed.

New strings are an `aud mic_gain` shell parameter, USB audio (`usb_audio_update_audio`, webcam audio), an HDMI EDID
audio format change notice, `mvr extif` debug and a movie "audio format" setting.[^fw1]

## Open questions

- Confirm the codec part with a chip-ID register read (`aud ic`) over the Wi-Fi shell.
- Which inputs and outputs this body wires (internal mic, 3.5 mm mic jack, speaker, HDMI). The code carries all of
  them.
- What pin `0x74` does, and the exact serial-port format fields (`+0x04`, `+0x08`, `+0x54`, `+0x58`).
- The CPU0 code and menu item that set the 96 kHz / 24-bit flag (movie record `+0x310`, message `+0x16`), and what the
  OM-5 II's new guard field `+0x06` holds. The chain below that is traced.
- What the notch filter removes. The property values (ALC, DRC, wind coefficients) were not decoded.
- Whether the stock limiter quirk is audible. Record a test clip with the internal mic, limiter off.

## Address reference

E-M5 III 1.7 block0 addresses unless the OM-5 II is named.

| item | address |
|---|---|
| `CapAud_AudioCtrl.cpp` | `0x60880026` |
| MVR movie clients | `0x6033db51`, `0x6033dc69` |
| `REC_SOUND`, `PLAY_SOUND` | `0x6040f73c` (voice memo code `0x6040fxxx`), `0x612c1236` |
| audio API: send and wait, send, WAV info | `0x607b8ef3`, `0x607b8f73`, `0x607b929f` |
| audio API: mixer open, run, close | `0x607b9598`, `0x607b95d9`, `0x607b961b` |
| audio API trace function | `0x607b976f` |
| `aud_seq_*` sequences | `0x607bbe2d` to `0x607bf495` |
| codec script dispatcher, command table | `0x60794ddc`, `0x6079d3f4` |
| codec script runner, property getter | `0x60795573`, `0x6005ce6b` |
| the 37 codec lists | `0x60795d0c` to `0x60a9fb14` |

*Layers, API and codec scripts.*

| item | address |
|---|---|
| codec register shadow | `0xa269a568` |
| default register table, filled by | `0x6079c79c`, `0x60794dad` |
| register write (reg, value), frame builders | `0x607957b9`, `0x607bfef0` |
| codec bus queue, add to queue | `0xa269848c`, `0x60794628` |
| codec bus sender | `0x60794674` |
| serial driver: take channel, set up | `0x6007046e` (channel 3), `0x60070816`, `0x600708ef` |
| chip select pin `0x6b` low, high | `0x60794d5d`, `0x60794d68` |
| codec single access (read) | `0x60794a1e` |
| pin `0x74` writes | `0x60794d28`, `0x60794d42` |
| logical-to-port channel map | `0x600c2580` |
| calibration trim, trim table | `0x607956a5`, `0x6079cd9e` |
| property name table | `0x613a929a` |
| recording volume hook | `0x607bf9e2` |
| wind filter hook (`aud_soundic_windcut`) | `0x607bfb86` |
| plug-in power hooks, flag | `0x607bfd63`, `0x607bfc9c`, `0x607bfd24`, flag `0xa269ab6c` |
| `EV_EXTERNAL_HEADPHONE` | `0x60aa93e0` |
| `CameraCommon::getHeadPhoneState`, called from | `0x60aaac3a`, `0x6025e7b8` |
| `stb_ext_microphone.c` | `0x6017335c` to `0x60173848` |

*Codec chip, bus and processing.*

| item | address |
|---|---|
| serial audio port block | `0x9bf00000` |
| port driver | `0x607b8ac2` to `0x607b8ee4` |
| port interrupt handler, set-up | `0x607b88e8`, `0x607b8d10` |
| play: port commands 1, 7, 4 from | `0x607bd68d`, `0x607bd6b4`, `0x607bd6c3` |
| record: port commands 2, 8, 5 from | `0x607bec4d`, `0x607bec7d`, `0x607bec8c` |
| buffer refill: transmit, receive | `0x607b8772`, `0x607b8821` |
| port clocks, divider and gate functions | `0x607bff83`, `0x60073606`, `0x60071fa6` |
| sample converter block | `0x9c600000` |
| `sca_drv_*` | `0x607baa4c` to `0x607bbdf9` |
| converter clock gate (bit 23) | `0x9880014c` / `0x988001c8` |
| converter interrupt handler | `0x607bb643` |
| movie edit and playback open of the converter | `0x612e486b` |

*Serial audio port and sample converter.*

| task | entry |
|---|---|
| `AUD_MAIN`, message table | `0x607941bb`, `0x60a97d34` |
| `AUD_WAKEUP`, cross-core call it posts | `0x60794510`, `0x6005730b` |
| `AUD_COPY_DATA` | `0x607b702f` |
| `AUD_LEVEL_MONITOR` | `0x607ba099` |
| `AUD_WATCH_DOG` | `0x607c20ac` |
| `AUD_LATE_RISER` | `0x607b7d31` |
| `REC_SOUND`, `PLAY_SOUND` | `0x6040f73c`, `0x612c1236` |
| `MOVE_AUDIO`, `MOVP_AUDIO`, `MOVP_AUDIO_SUB` | `0x612eeb8d`, `0x612cdf60`, `0x612ce8fc` |
| `AVM_P1_AUDIO`, `AVM_P2_AUDIO`, `AVM_DMY_AUDIO` | `0x603f480a`, `0x603f4912`, `0x603f0ce6` |

*Task entries.*

| item | address |
|---|---|
| movie settings record (byte `+0xd`) | `0xa265d492` |
| movie recorder: rate and depth set | `0x60321914`, `0x603358f7` |
| copy of message `+0x16` | `0x60339305` |
| settings message builder | `0x60325946` |
| per-mode record base, mode index | `0xa26591f4`, `0xa26591a8` |
| album `audio_quality` help | `0x60748730` |
| web server file info read | `0x61210a32` |
| MOV demuxer sample entries | `0x61195ba1` |
| sound kind table | `0x60a982b8` |
| `VOL_Play` | `0x607bf2dc` |
| `aud` help | `0x6147223d` |
| OM-5 II: message builder | `0x6033c2bb` |
| OM-5 II: movie-recorder setup | `0x60337f0b` |
| OM-5 II: guard field `+0x06`, flag `+0x0f` | `0xa26e94bc`, `0xa26e94c5` |
| OM-5 II: HDMI audio format log | `0x60bb0858` |

*Sample rates, beeps and the debug shell.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware, 2026-11-25.
[^fw2]: Read in the OM-5 II 1.1 firmware and compared list by list on the expanded RAM image (`audio_tables.py --diff`), 2026-11-25.
[^inf1]: Inferred, 2026-11-25.
[^inf2]: Inferred from the public WM8962 register map, 2026-11-25.
[^fix1]: Corrected 2026-11-25. An earlier version mapped serial channel 3 to block `0x98600000`.

## History

- 2026-11-25: serial channel 3 was first read as block `0x98600000` from the serial-port table. It is a logical channel
  that maps to port 1, block `0x98200000`.

