# Still image back end

<!-- human page -->
<!-- house style -->

## Key points

- After the shutter closes, the camera develops the picture, writes the photo information into the file and saves it
  to the SD card.
- The image-processing hardware makes the JPEG, the thumbnail and the screen preview in one pass, and a separate block
  compresses raw files.
- One function writes the photo information for JPEG and raw files, with a fixed layout for each file type.
- The OM-5 II uses the same design, with a newer EXIF version and the OM SYSTEM name.

After the shutter closes, the camera still has work to do. It turns the raw sensor data into a picture. It encodes a
JPEG or packs a raw file. It writes the photo information (EXIF) into the file. Then it finds a folder and a file name
and writes the file to the SD card. This page describes that part of the E-M5 III firmware.

Everything here comes from reading the firmware. Nothing was tested on the camera.

## Cores and named steps

The recording work runs on the main processor core (CPU0). The third core (CPU2) only helps with white balance and the
review image.

The firmware keeps a list of 209 named recording steps. That list let us find the code for each step.

## Steps for one photo

1. **Develop.** The recording task sends one request to the image-processing hardware. That request produces the
   main JPEG, a small thumbnail and a screen-size preview in one pass.
2. **Raw.** For a raw file, the camera also starts a separate hardware block called CIC. CIC compresses the
   5240 × 3912 sensor frame.
3. **Header.** The camera fills a large block of photo information. Then one function turns it into the EXIF header.
4. **File.** A file task asks the DCF layer for the next folder and file number. The FAT layer reserves space on the
   card. The SD driver writes the data. The layers are read in the firmware, but the exact hand-over between them is
   inferred.

## EXIF header

- The header has the usual parts. They are the main block, the Exif block, GPS, a thumbnail block and Olympus's own
  MakerNote.
- The MakerNote has five sections. They hold the lens and body details, the camera settings, the raw development
  settings, the image processing and the focus information.
- Each file type has its own fixed list of fields. A JPEG has 133 image-processing fields. A raw file has 180.
- Photos taken in Adobe RGB get three extra colour fields and a gamma field. The fields are in the firmware. That
  Adobe RGB is what triggers them is inferred.
- The camera writes EXIF version 2.31.

## JPEG encoder

- A separate JPEG block in the chip encodes the photo.
- It uses the standard tables from the JPEG specification.
- The quality setting scales those tables. A higher scale gives a smaller file with less detail.
- The standard JPEG header uses 4:2:2 colour sampling. The block can also do 4:2:0.
- The OM-5 II uses the same block and the same tables.

## Raw compressor settings

- The raw compressor gets the frame size, the bit depth and 14 small numbers that tune its coder.
- The bit depth tells it how many pixels are packed into each 32-byte block of input.
- What each of the 14 numbers does is still open.

## Files and folders

- The camera writes FAT32 or exFAT cards with the usual DCIM folder names.
- Photos go into `DCIM\100OLYMP` and the following folders up to 999. Files are numbered up to 9999 in each folder.
- The file system code reads FAT12, FAT16, FAT32 and exFAT.
- The file code knows the card's allocation units and speed-class commands. It also has a built-in card speed test.
- When a card error happens, the camera saves the SD controller state and the card's identity in an error log.
- The Wi-Fi debug shell has a `file` command. It can list folders, read sectors and print the card state.

## Card writes

The recording task prepares the file and then hands the data to a file task called FILECLBK. FILECLBK does the actual
writes. Every other part of the camera that touches the card also goes through this task. The hand-over is read in the
firmware. That every other part uses it is inferred.

## SD card controller

- The camera has two SD controllers of the same design.
- The first one serves the card slot. It has extra registers for UHS-II, the faster SD bus with a second row of pins.
- The second one is wired to the Wi-Fi chip. That is partly inferred.
- UHS-II is switched on per card. With a UHS-II card, writes are counted in 2 KB steps.

## OM-5 II

- The recording steps, the raw block and the SD controllers are the same.
- Files carry EXIF version 3.0, an `OM SYSTEM` MakerNote and a star-rating field.
- The Exif block can hold temperature, pressure, water depth and acceleration.
- Photos go into `DCIM\100OMSYS`.

## Status

Two questions are still open.

- What each raw compressor setting does.
- What four of the image units next to the JPEG block do.

## Further reading

- [Still image back end: technical notes](still-backend-technical.md) has the tasks, registers, header layout and
  addresses.
- [CPU1 and CPU2](../hardware/cpu1-cpu2.md) lists the tasks on each core.

