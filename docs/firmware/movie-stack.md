# Movie encoder stack

<!-- human page -->
<!-- house style -->

## Key points

- Movie work is split over two helper cores, and the main core only starts and stops the recording.
- A hardware H.264 block encodes the movie and also decodes movies for playback.
- One short request picks the size, frame rate and compression, and two functions turn it into every encoder and file
  setting.
- The OM-5 II runs the same code on the same hardware, with a few different numbers such as the time limit.

This page explains how the E-M5 III turns live sensor frames into a movie file. It covers which processor core does
what, how the H.264 settings are chosen and how the file is written. It also compares the OM-5 II program.

Everything here comes from reading the firmware. Nothing was tested on the camera.

## Cores

| step | core | what happens |
|---|---|---|
| start and stop | main core | the shooting code starts a recording and listens for "card full" or "write failed" |
| frame preparation | third core | the movie recorder tasks take frames from the image pipeline and build the record request |
| encoding and writing | second core | a command task sets up the encoder, about 20 worker threads run it, and a file task writes to the card |

*Which core does each step of a recording.*

The split matches what the [CPU1 and CPU2](../hardware/cpu1-cpu2.md) page found from the task tables.

## Settings

The recorder sends one small request when recording starts. It holds the movie size, the frame rate, the compression
level and whether the clip is high speed. Two functions on the encoder side expand it into roughly 60 settings.

The main choices are these.

- **Bitrate.** A fixed table gives the bitrate for each size, frame rate and compression level. Full HD runs at 200,
  50, 28 or 16 Mbit/s for All-Intra, Super Fine, Fine and Normal. 4K is fixed at 100 Mbit/s.
- **Frame structure.** All-Intra stores every frame whole. The other levels store a full frame every half second and
  only the changes in between.
- **Compression method.** Most modes use CABAC, the more efficient H.264 option. Cinema 4K and Full HD All-Intra use
  the simpler CAVLC. That is probably to keep up with their higher data rates. The choice is read in the firmware, and
  the reason is inferred.
- **Time limit.** Every normal size gets 30 minutes. Only the two small 640-pixel-wide sizes get two hours. This
  corrects an earlier note that said the two-hour case was an unknown recording type.
- **Colour.** Movies are tagged as standard HD colour (BT.709) with full-range levels.

## File

The camera writes QuickTime MOV files. The sound is uncompressed stereo linear PCM. A maker block in the file carries
"OLYMPUS DIGITAL CAMERA" and private data of up to 100 KB. Each file stops at 4 GB, which fits the limit the encoder
is given. The format is read in the firmware. The 4 GB limit is inferred.

## Encoder hardware

One hardware block handles H.264 both ways. The encoder and the playback decoder call the same small driver library,
and only that library touches the block's registers. The block sits on the second core.

## OM-5 II

The OM-5 II runs the same movie code on the same encoder block. The bitrates for 4K, Cinema 4K, Full HD and HD are the
same. The differences are small.

- There is no 30-minute limit. Every recording gets two hours.
- The file-size limit is far above 4 GB, so long clips probably stay in one file. This is inferred.
- 23.98 frames per second is its own setting instead of being shared with 24.
- The 640-wide sizes have new bitrates.
- The maker block says "OM SYSTEM CAMERA".
- It adds debug code for recording raw movie frames and a buffer for movie streaming.

## Status

Three questions are still open.

- What two rarely used request values are for. A streaming path is the likely user.
- How the encoder block's registers are laid out.
- Whether long OM-5 II clips really stay in one file past 4 GB.

A shell command, `avm debug`, prints every encoder setting while recording. That would confirm this page on the camera
without any firmware change.

## Further reading

- [Movie encoder stack: technical notes](movie-stack-technical.md) has the request fields, the bitrate table and the
  addresses of the request builder, the command task, the setting functions and the encoder block.
- [Movie recording](../features/movie.md) covers the 29:59 limit, the OM-Log400 profile and the sensor modes.
- [CPU1 and CPU2](../hardware/cpu1-cpu2.md) lists the movie tasks on each core.

