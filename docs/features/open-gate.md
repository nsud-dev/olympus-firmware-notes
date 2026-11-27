# Open gate video

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III could probably record open gate video from the whole 4:3 sensor, at reduced resolution.
- The sensor already has a half-resolution readout of the full area, and the encoder already knows 4:3 picture sizes.
- The open question is how many pixels per second the image pipeline between them can process.
- The limit is probably in the hardware, because the E-M1 III with the same processor has the same movie limits.

"Open gate" means recording video from the whole 4:3 sensor instead of a 16:9 band cut from it. The E-M5 III does
not offer it. This page asks whether its hardware could do it.

## Verdict

Probably yes, at reduced resolution. We found no hard blocker. The sensor and the video encoder can both
handle a 4:3 picture. The open question is how many pixels per second the image pipeline between them can process.

The most promising target is a half-resolution readout of the full sensor area. That would give 2560 × 1920 at 30
frames per second, or 1920 × 1440 at up to 60. A full-resolution 4:3 picture such as 2880 × 2160 would probably
reach only 15 to 24 frames per second.

## Sensor

The sensor driver has a fixed list of 16 readout modes. One of them reads the full 4:3 area with pixels combined
two by two, which gives 2624 × 1960. So the readout that open gate needs already exists.

The camera uses that mode today. It is requested only from the Wi-Fi remote code, most likely for the live view the
phone app shows.

The sensor is not the limit. It already reads full frames 30 times a second for burst shooting.

## Image pipeline

A table tells the pipeline which part of the sensor picture to use for each movie size.

- 4K takes a centre crop of 4088 × 2348 pixels and scales it slightly. This is why 4K has a crop of about 1.27x.
- Cinema 4K takes the full width and scales it down. It is offered at 24 frames per second only.
- Full HD uses a 16:9 band read with pixels combined two by two.

No entry produces a 4:3 video picture. A new one would have to be added, and the same sizes appear as fixed numbers
in many movie modules.

The pipeline's throughput is not known. 4K at 30 frames is about 288 million pixels per second. Cinema 4K at
24 is about 350 million. Full-resolution 4:3 at 24 would need 489 million, which is more than the camera does
anywhere today. The half-resolution mode at 30 needs only 153 million.

## Encoder

The encoder is H.264. Its rate table stops at Level 5.1, which allows 36,864 macroblocks per frame. 2560 × 1920 at
30, 1920 × 1440 at 60 and 2880 × 2160 at 30 all fit inside that.

The encoder's list of picture sizes already contains 2048 × 1536 and 2560 × 1920. So the code already allows for 4:3 sizes.

Playback has a firm limit. The camera's own player refuses any clip taller than 2160 lines. A taller clip would
record but would not play back in the camera.

## Stabilisation

Electronic stabilisation needs spare pixels around the picture. Open gate uses them all. So only the sensor-shift
stabiliser would work.

## Hardware limit or product limit

The limit is probably in the hardware. The E-M1 III was the top model and has the same processor. It has the same 4K crop, the same
24-frames-only Cinema 4K and the same encoder level. Only the OM-1, with a new processor, goes further.

4K at 30 frames uses a crop where the full width would look better. That only makes sense if the full width at 30
frames does not fit the processing budget. The limit could still be heat or memory bandwidth and not a hard wall.

## Other cameras

The OM-5 and the E-M1 III share every table described here. None of the bodies we looked at has open gate, 4:3 movie
or anamorphic modes in its firmware, so there is nothing to copy from a newer model.

## Status

This is research from reading the firmware. Nothing was built or tried on a camera.

## Further reading

- [Open gate video: technical notes](open-gate-technical.md) has the readout modes, the crop table, the encoder limits
  and where each table sits in the firmware.
- [Sensor](../hardware/sensor.md) describes the sensor and its readout modes.
- [Movie recording](movie.md) covers the movie encoder and the recording limit.
