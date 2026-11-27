# Guides

<!-- house style -->

## Key points

- Each guide follows one process through the E-M5 III firmware 1.7 and explains what happens and why.
- Start with Before you start and Rhapsody and OXF, which cover the pieces and the words the other guides use.
- The exact addresses and details are on the reference pages each guide links to.

These guides explain how processes on the camera work without getting bogged down in reference
material. Each one follows one process through the firmware of the E-M5 III (firmware 1.7). The exact
addresses and details are on the reference pages each guide links to.

## The guides

| guide | what it covers |
|---|---|
| [Before you start](before-you-start.md) | the pieces of the camera and the words the guides use, read this first |
| [Rhapsody and OXF](rhapsody-and-oxf.md) | why so much of the code looks generated |
| [Taking a photo](taking-a-photo.md) | one still photo from half-press to the file on the card |
| [Boot](boot.md) | what runs from power-on until the camera is ready |
| [Operating system](operating-system.md) | tasks, events and queues: the real-time OS under everything |
| [MN103 primer](mn103-primer.md) | the control CPU's instruction set, enough to read the disassembly |
| [Core communication](cores.md) | locks, doorbell interrupts and cross-core calls between the MN103 cores |
| [Buttons](button-press.md) | from a key press to the app reacting |
| [Live view](live-view.md) | how a live-view frame gets from the sensor to the display |
| [Firmware files and updates](firmware-file.md) | the update file, how the camera installs it, and how to recover |
| [Frame pools and memory](frame-pools-and-memory.md) | the address space, the heap and the frame pools that hold images in memory |
| [Settings and menus](settings-and-menus.md) | how a setting gets from a menu row to the saved settings, and how new rows are added |
| [Feature ports](port-anatomy.md) | how a feature is brought over from a newer body, with Live ND as the worked example |
| [Drawing to the screen](drawing-to-the-screen.md) | the GUI layers, the 2D draw engine and the vector GPU that draws the colour wheels |
| [Drawing your own graphics](drawing-your-own.md) | boxes, curves, pictures, text, animation and touch with the firmware's own drawing calls, tried in an emulator |
| [Vector GPU](vector-gpu.md) | three ways to draw with the GPU that draws the colour wheels: the Olympus driver, your own OpenVG code, raw command lists |

*The public guides and what each one covers.*

