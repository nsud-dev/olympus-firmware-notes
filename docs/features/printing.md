# Printing

<!-- human page -->
<!-- house style -->

## Key points

- The camera can print straight to a printer over a USB cable, using the PictBridge standard.
- It can also save a print order on the card for a shop or a printer to read later.
- The OM-5 II program keeps the printing engine and print orders but has no printer screens.
- Everything here comes from reading the firmware, and nothing was tested on the camera.

The camera can print photos in two ways. It can send them straight to a printer over a USB cable. It can also save a
print order on the card for a shop or a printer to read later. This page explains how the program does both. Everything
here comes from reading the firmware. Nothing was tested on the camera.

## Direct printing

Direct printing uses a standard called PictBridge. The printer acts as the computer and the camera acts as a device on
its cable. The two sides swap short text files that ask and answer questions.

A print goes like this.

1. The camera's USB Mode is set to Print, or the user picks Print when the cable goes in.
2. The camera and the printer find each other by reading each other's "discovery" files.
3. The camera asks what the printer can do, for example which paper sizes it takes.
4. The user picks images and settings on the camera.
5. The camera sends a print job. The printer reads each image from the camera and prints it.
6. The printer reports when it is done. It also reports paper, ink and jam problems.

The program reads the printer's text files with a small open-source XML reader called Expat.

## Print modes and settings

The camera offers two kinds of direct printing.

- **Easy print** prints the image on screen with the printer's own default settings.
- **Custom print** lets the user choose the settings.

Custom print has five modes.

- Selected images
- All images
- Several images on one sheet
- An index sheet of all images
- The print order saved on the card

The settings are paper size, borders, number of copies, a date or time stamp, a file name stamp and cropping. The paper
sizes on offer come from the printer.

## Print orders on the card

A print order is a list of images and copies saved on the card. Shops and some printers can read it. The standard for
it is called DPOF.

- The user marks images and copy counts in playback.
- The camera writes the list to a file called `AUTPRINT.MRK` in the card's `MISC` folder.
- Custom print can print straight from this list.

The Wi-Fi share order is a different list. It marks images for sending to a phone and has nothing to do with printing.

## OM-5 II program

The OM-5 II program uses a newer menu system. That menu system has no printer screens.

- The printing engine underneath is still in the program.
- The print order code is still there.
- A new "reset all print orders" step was added for the new menus.

So a camera running that program probably cannot print over USB. Print orders probably still work. Neither was tested.
A look at its menus in the emulator would settle it.

## OM-5

The OM-5 1.2 program has the same printing code and screens as the E-M5 III.

## Status

- The printing code is mapped at the level of its parts.
- No function was read in detail. Printing is not a target for mods. The map exists so the area is known.
- The OM-5 II program has no printer screens. Its printing engine is still there.

## Further reading

- [Printing: technical notes](printing-technical.md) has the program layers, the PictBridge messages and their
  addresses.
- [USB](../hardware/usb.md) covers the USB modes, including Print.
