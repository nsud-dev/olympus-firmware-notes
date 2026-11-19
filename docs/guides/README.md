# Guides

These guides explain how processes on the camera work without getting bogged down in reference
material. Each one follows one process through the firmware of the E-M5 Mark III (firmware 1.7). The exact
addresses and details are on the reference pages each guide links to.

## The guides

| guide | what it covers |
|---|---|
| [Before you start](before-you-start.md) | the pieces of the camera and the words the guides use; read this first |
| [IBM Rhapsody and the OXF framework](rhapsody-and-oxf.md) | why so much of the code looks generated |
| [Taking a photo](taking-a-photo.md) | one still photo from half-press to the file on the card |
| [Boot](boot.md) | what runs from power-on until the camera is ready |
| [The MN103 operating system](operating-system.md) | tasks, events and queues: the real-time OS under everything |
| [An MN103 primer](mn103-primer.md) | the control CPU's instruction set, enough to read the disassembly |
| [How the cores talk to each other](cores.md) | locks, doorbell interrupts and cross-core calls between the MN103 cores |
| [How a button works](button-press.md) | from a key press to the app reacting |
| [Live view](live-view.md) | how a live-view frame gets from the sensor to the display |
| [Firmware files and updates](firmware-file.md) | the update file, how the camera installs it, and how to recover |
| [Frame pools and memory](frame-pools-and-memory.md) | the address space, the heap and the frame pools that hold images in memory |

