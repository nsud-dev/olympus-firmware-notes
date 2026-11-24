# Sensor and calibration

<!-- human page -->
> The dense reference for this page is [Sensor and calibration: technical notes](sensor-technical.md).

This page describes the image sensor as the firmware sees it. It covers the sensor's size, how a raw frame sits in
memory, the calibration stored for each camera at the factory, and the modes the sensor runs in.

The E-M5 III and the OM-5 use the same sensor. That is one reason features from the OM-5 port across so well.

## Size

The sensor reads out 5240 by 3912 pixels and delivers a 20-megapixel picture of 5184 by 3888. Some of its pixels are
phase-detect autofocus pixels.

Tripod High Res Shot builds pictures of 10368 by 7776. The OM-5's hand-held High Res adds a slightly larger 10416 by
7824.

## A raw frame in memory

A raw frame is the sensor's data before any processing. Each pixel holds one colour value, in the usual Bayer pattern
of red, green and blue.

The camera stores 12 bits per pixel, packed tightly. Every 16 bytes hold 10 pixels plus one spare byte. A full frame
takes about 32 MB, and each row takes 8384 bytes.

A few details matter when you work with these frames:

- Black is about 256 and full white is 4095.
- The frame is stored upside down compared with the picture.
- The black level and white balance are filled in late, when the picture's metadata is written, not when the shot is
  set up.

## Factory calibration

Every camera is measured at the factory, and the results are stored in the camera. They include maps of defective
pixels, black levels, dark shading and saturation.

The E-M5 III has 173 calibration entries. 172 of them are identical in the OM-5, down to their position and size. The
OM-5 adds five more, for things like the eye sensor's distance, and one audio entry grows. That near-perfect match is
strong evidence that the two cameras share their imaging hardware.

## Sensor modes

The firmware switches the sensor between modes by sending it a request. Each request names a mode, a frame rate and an
exposure.

| use | mode | notes |
|---|---|---|
| live view | MSPD | 120 frames per second, reading every third line and column |
| half-press | HSSC | 60 frames per second |
| shutter | STILL | full sensor, every pixel |
| 4K movie | MOVIE_4K | a crop from the middle of the sensor, every pixel |
| Cinema 4K movie | MOVIE_C4K | the full sensor width, every pixel |
| Full HD movie | HSHR | a band of the sensor at half resolution |
| Wi-Fi remote live view | MOVIE_HQ | the full area at half resolution |

There are about twenty modes in all. Some read every pixel, and others combine pixels in 2 by 2 or 3 by 3 blocks to
read faster. A rough estimate puts a full readout of every pixel at about 23 frames per second.

So 4K is a crop, about 1.27 times narrower than the full sensor. Cinema 4K uses the full width and scales it down.

Live ND on the OM-5 uses one more kind of request, a long-exposure frame. The E-M5 III's sensor code already understands
it.

## Other cameras

The OM-5 and E-M1 III have the same sensor readouts and the same geometry as the E-M5 III.

## Further reading

- [Taking a photo](../guides/taking-a-photo.md) shows when the sensor switches modes during a shot.
- [Movie recording](../features/movie.md) covers how movies are recorded.
- [Image engine](image-engine.md) explains what happens to a raw frame next.
