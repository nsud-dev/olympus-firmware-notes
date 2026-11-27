# Audio

<!-- human page -->
<!-- house style -->

## Key points

- Sound passes through an external codec chip, a serial audio port and a sample converter in the main chip.
- The codec is set up from 37 ready-made lists of register writes, one for each situation.
- Movies and voice memos record at 48 kHz 16-bit by default, and a 96 kHz 24-bit mode is built in.
- Everything here comes from reading the firmware, not from tests on the camera.

The camera records sound for movies and voice memos. It plays beeps, shutter sounds, movie sound and slideshow music.
This page explains which parts do that and how the program drives them.

The parts and the program flow are mapped. The codec chip is identified by its register layout, not by name. It looks
like a Wolfson (now Cirrus Logic) WM8962. The OM-5 II program drives audio the same way, with a few small fixes.

## Parts

Sound passes through three parts.

- **The codec.** A separate audio chip next to the main chip. It turns the microphone signal into numbers and numbers
  back into sound for the speaker or a socket. It also does gain, the volume limiter and the wind filter.
- **The serial audio port.** A port in the main chip that streams sound samples to and from the codec. It has one
  channel for recording and one for playing.
- **The sample converter.** A helper unit in the main chip. It mixes two sound streams into one and changes their
  format, for example when a beep plays over movie sound.

The main chip sets the codec up through a separate control line. It writes the codec's settings one register at a
time.

## Codec set-up

The program does not change codec settings one by one in code. It keeps 37 ready-made lists of register writes, one
for each situation.

- **Power on.** About 1,360 writes. Most of them load a small program into the codec's own signal processor.
- **Record start.** One list for each input (built-in mic, external mic, recorder input), with the limiter on or off.
- **Play start.** One list for the speaker and one for headphones.
- **Device change.** Lists for switching microphones or outputs while running.

Many entries in these lists don't hold a fixed value. They look a value up in the camera's settings instead. So the
fine tuning lives in settings tables, and the lists only say where each value goes.

## Recording settings

- **Recording volume.** The menu's −10 to +10 picks one of 21 gain steps. The built-in mic and external mics use
  separate tables.
- **Volume limiter.** It switches the codec's automatic level control and its compressor.
- **Wind noise reduction.** It is a high-pass filter in the codec. Off, low, standard and high each pick a different
  cut-off.
- **Plug-in power.** It turns on the power the codec feeds to an external mic. The built-in mic always gets it.
- **A stock quirk.** With the built-in mic and the limiter off, the stock 1.7 firmware starts recording with part of
  the limiter-on settings. The OM-5 II firmware fixed this. Whether you can hear it is not tested.

## Sample rates

- **48 kHz, 16-bit stereo** is the normal format for movies and voice memos.
- **96 kHz, 24-bit stereo** is built in too. One flag in the movie settings switches to it. Which menu sets that flag
  is not known yet.
- **96 kHz clips are a normal file type.** The clip album and the web server both store and report the audio quality
  of each clip.
- **The OM-5 II adds a check.** It drops back to 48 kHz when a new movie setting is not zero. What that setting is was
  not found.

## Sockets

- **The program supports a headphone output.** It has a headphone event, a headphone state and a headphone volume.
- **It also talks to smart accessory microphones.** This goes through the accessory protocol, not the plain mic jack.
- **Which sockets this body has wired is not settled by the code.** The program is shared with other bodies.
- **Microphone calibration is stored in the camera.** One stored value trims the built-in mic's left and right
  channels.

## Audio tasks

The audio tasks run on all three of the main chip's cores ([CPU1 and CPU2](cpu1-cpu2.md)).

- **CPU0** runs the main audio task. It takes requests from the rest of the camera and runs the record and play steps.
  Helper tasks copy samples, watch the codec for faults and run debug tests.
- **CPU2** loads the codec's program at start-up and runs the level meter.
- **CPU1** writes the recorded sound into the movie file, next to the video. Movie sound is stored as uncompressed
  PCM.

## Beeps and system sounds

The camera knows 18 kinds of sound, each with its own volume setting. Examples are the shutter sounds, the focus beep,
the self-timer, warnings, the start-up sound and the movie start sound. Each sound can go to the speaker, the HDMI
output and the headphone output at different volumes.

## Debug command

The camera's debug shell has an `aud` command. It can read codec registers, show the audio status and list the
current device and volumes without changing anything. It can also play test tones and record to memory. The
read-only commands are a safe first camera check.

## OM-5 II

The OM-5 II program uses the same codec lists, apart from five small changes. It also adds USB audio for the webcam
mode and a check of which audio formats a connected HDMI screen accepts.

## Status

No camera test yet. A read-only check over the Wi-Fi debug shell is the next step. Still open:

- Confirm which codec chip it is, by reading its ID register on the camera.
- Which sockets the E-M5 III actually has wired. The firmware carries code for more than one body.
- Which menu turns on 96 kHz recording, if any.

## Further reading

- [Audio: technical notes](audio-technical.md) has the codec register lists, the port and converter registers, the
  tasks and the address reference.
- [CPU1 and CPU2](cpu1-cpu2.md) explains the cores the audio tasks run on.
