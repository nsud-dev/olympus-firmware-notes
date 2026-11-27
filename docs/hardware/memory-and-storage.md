# Memory and storage controllers

<!-- human page -->
<!-- house style -->

## Key points

- The camera keeps its firmware and settings on a 128 MB raw flash chip and works in about 1 GB of DRAM.
- The firmware fixes small read errors on the flash and moves worn blocks to spare ones by itself.
- Normal running may write the flash only inside four windows, and our code must stay out of the spare blocks.
- The debug shell's `flash` command can erase the whole data area and must never be run.

The E-M5 Mark III has two kinds of memory. The flash chip keeps the firmware and the settings when the camera is off.
The DRAM is the working memory while the camera runs. Each has its own controller inside the main chip.

This page explains how both controllers work and what that means for safe patching. Everything here comes from
reading the firmware and from one flash backup made on our camera. Nothing was written to the camera.

## Flash chip

The flash holds 128 MB. It is raw NAND, the same kind of memory as in a memory card, without a card's own controller.

- It is split into 1024 blocks of 128 KB.
- Each block has 64 pages of 2 KB.
- Each page has 128 extra bytes for error correction.

The camera can only erase a whole block and only write a whole page.

The main chip's flash controller copies pages to and from DRAM by itself. The processor never reads the flash
directly. Flash "addresses" are only names for a place on the chip. Reading such an address like memory would trip the
chip's access monitor and reset the camera.

## Error correction

Flash cells slowly lose or gain charge. The controller fixes small numbers of wrong bits on every read.

It checks each 1 KB piece of a page on its own. By our reading it can fix at least 14 wrong bits per piece. When a read
needed more than 13 fixes, the firmware copies that block to a fresh spare block. This keeps worn data from getting
worse.

## Bad blocks

Every NAND chip has a few blocks that stop working. The firmware keeps a table that sends each bad block to a spare
one.

- 22 blocks near the end of the chip are spares. The table is stored three times right after them.
- A block is moved when a read needs too many fixes or when the chip stops answering during a write or erase.
- As read, the firmware does not notice a write the chip reports as failed, only a chip that stops answering.
  Firmware updates read everything back and compare, so they catch it.

## Writing safely

Normal running may write only inside four windows. A write anywhere else resets the camera at once.

The last window also covers the spare blocks and the bad-block table. The guard does not protect them.

> [!WARNING]
> Our code must never write into the spare blocks or the bad-block table. The technical page gives the address
> where they start.

While the flash is busy, the firmware most likely holds off the watchdog. The driver probably also lifts the chip's
write protection only while it writes or erases.

The OM-5 Mark II program has wider windows, made for a bigger chip. Its own data stays below the spare blocks on the
E-M5 III.

> [!WARNING]
> The debug shell's `flash` command can erase the whole data area, including the factory calibration. It must never
> be run.

## DRAM

The camera has about 1 GB of DRAM, by our reading. The controller drives two 16-bit channels, which together make a
32-bit bus.

The memory runs at 1536 million transfers a second, the fastest of 16 fixed settings. The controller itself runs at a
quarter of that. By our estimate that gives a peak of about 6 GB a second.

The memory is DDR3, set to the timings of the DDR3-1600 grade. The boot code writes standard DDR3 settings that show
this. The values are read in the firmware. Reading them as DDR3 settings is our interpretation.

The boot code before block0 sets the memory up with fixed values. It does not test the memory or detect its size.

## Standby

In standby the DRAM keeps its contents by refreshing itself. The clocks and most of the chip are switched off.

The code that does this runs from a tiny 8 KB memory inside the main chip, because the DRAM cannot be used then. On
wake-up the firmware turns the memory clock back on and re-tunes the connection to the DRAM.

## DRAM users

The controller lists 78 named "agents". Each is a part of the chip that reads or writes DRAM on its own, such as the
cores, the display unit, the image pipeline, USB and the card slots.

A built-in counter can measure reads, writes and lost time per channel. It is a debug feature.

## Status

- The flash driver is mapped. Read, write, erase, error correction and bad-block handling are understood.
- The DRAM controller is mapped. Its registers, channels, clocks and standby mode are known.
- The OM-5 Mark II 1.1 program uses the same flash driver.
- There was no camera test. One existing flash backup was read.

## Open questions

- What each timing field means. The raw values are on the technical page.
- The exact error-correction strength. The layout of the spare bytes points to 16 bits per 1 KB piece, by our reading.
- The part numbers of the flash and DRAM chips. A board photo would answer this.

## Further reading

- [Memory and storage controllers: technical notes](memory-and-storage-technical.md) has the registers, the driver
  functions, the flash addresses and the write-guard windows.
- [Memory map](memory-map.md) shows where the DRAM and the flash names sit in the address space.
- [Caches and the access monitor](caches.md) explains the monitor that resets the camera on a stray read.
