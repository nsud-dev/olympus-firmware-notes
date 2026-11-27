# Playback and in-camera editing

<!-- human page -->
<!-- house style -->

## Key points

- Playback is the largest part of the firmware by function count, and it is built in seven layers.
- A small engine of six tasks at the bottom loads, decodes, draws and edits pictures.
- In-camera RAW development sends the raw data back through the normal recording pipeline, so an edited raw is
  developed like a new photo.
- The OM-5 II has the same engine and adds RAW development from a computer and star ratings.

Playback is everything the camera does after you press the play button. It shows pictures and movies, zooms in,
shows the histogram and lets you edit. The edits include JPEG edits, RAW development, rotate, protect and share
orders. This is the largest part of the firmware by function count. This page describes how it is built in the
E-M5 III and what changes in the OM-5 II program.

Everything here comes from reading the firmware. Nothing was tested on the camera.

## Layers

Playback code sits in seven layers. The screens are at the top. A small engine written in C sits at the bottom and
talks to the hardware.

| layer | what it does |
|---|---|
| Screens | draw the single picture, index, light box and calendar views and the info overlays |
| Operations | one class per playback screen and per edit |
| Components | 60 named parts such as the index view, the movie player and Edit RAW |
| Capability classes | the image player, play state, movie player, slide show, histogram |
| C interface | builds the requests for the engine and waits for the answer |
| Play engine | six tasks that load, decode, draw and edit |
| Hardware | the image-processing engine, the CIC raw codec, the GPU and the display |

*Playback layers from top to bottom. Names come from the firmware's own log strings and source-file names.*

## Play engine

The engine is six tasks on the main processor core (CPU0). One task receives every request. It passes the request to
a task for loading, drawing and editing, sound or decoding.

| task | what it does |
|---|---|
| PLAY_MAIN | takes every request and passes it on |
| PLAY_LOAD | reads a file and decodes it (JPEG, raw, movie thumbnail, MPO, voice memo) |
| PLAY_IMAGE | draws, edits, edits movies and writes GPS data |
| PLAY_LOADDRAW | loads and draws a picture in one step |
| PLAY_DECODE | decodes large JPEG pictures in strips |
| PLAY_SOUND | plays voice memos |

*The six engine tasks. Every engine function prints its own name when it starts, which let us name 213 of them.*

## Decoding

- **JPEG.** The engine asks the image-processing hardware to decode the picture. Recording uses the same hardware to
  make the JPEG. The call is in the firmware. That it is the decode job is inferred.
- **Raw.** The engine reads the raw file and checks it. Then the CIC raw codec unpacks the sensor data. That is the
  block that packs raw files when you shoot.
- **Movies.** Thumbnails come from a small JPEG inside the movie file. Movie playback runs in its own tasks. They use
  the video hardware that also records movies.

## Edits

One table lists 22 kinds of edit. Each kind calls one function in the engine. RAW development in the camera sends the
raw data back through the normal recording pipeline. So an edited raw is developed like a new photo.

| edit | how it runs |
|---|---|
| Black and white, Sepia, Saturation | one colour function with three modes |
| Trim, Red-eye fix, Shadow adjust, Resize, Aspect, Rotate | one engine function each |
| e-Portrait | its own engine function and a face step |
| Image overlay | combines raw files, with a preview step and a save step |
| Edit RAW and ART bracketing from RAW | unpack the raw, then develop it through the recording pipeline |
| Share order | sets a flag inside the file |
| Protect and erase | handled by the file layer, not the engine |

*The in-camera edits and how the firmware runs each one.*

One edit registers a picture as the opening screen. Two more resize pictures for a target called CUBE, which the
Bluetooth code connects to. Both readings come from the function names only.

## Other users of the engine

The Wi-Fi web server and GPS log tagging use the same engine.

## OM-5 II

- The same six tasks and the same edit table.
- One more edit and two more load kinds. They let a computer develop a raw file with the camera over USB. The
  E-M1 III, OM-5 and OM-1 have this too. The E-M5 III does not.
- Star ratings, with menus to set and reset them and a "delete except rated" option. Only the OM-1 line and the
  OM-5 II have them.
- The playback screens and the classes under them match the OM-1 almost method by method.
- The photo story feature is gone.

## Open questions

- What the recording side does inside each RAW development request type.
- What device CUBE is.

## Further reading

- [Playback and in-camera editing: technical notes](playback-technical.md) has the tasks, request kinds, edit table
  and addresses.
- [Printing](../features/printing.md) covers DPOF and PictBridge, which have their own page.

