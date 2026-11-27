# Settings map E-M5 III ↔ OM-5

<!-- human page -->
<!-- house style -->

## Key points

- The E-M5 III and the OM-5 share about 2,000 settings, and most of them differ only in their number.
- A saved settings image can't be copied from one camera to the other, because each camera resets an image with the
  other's layout to its defaults.
- A settings image can be converted between the two layouts on a PC in both directions, with a value falling back to
  the factory value where the target camera lacks that choice.
- The map comes from reading both firmware files and has not been tried on a camera yet.

The OM-5 is the E-M5 III's successor and runs almost the same firmware. This page compares the two cameras' settings
one by one. It also explains how saved settings could move from one camera to the other, in both directions. It is
meant for anyone who owns both cameras or moves between them.

Nothing on this page has been tried on a camera yet. The map comes from reading both firmware files.

## Saved settings

Each menu row has a **setting id**, a number the menus use. Behind it sits a **property**, the stored value itself.
The camera saves all its properties as one block of 256 KB, the settings image. The values sit one after another in a
fixed order, without labels. Only the firmware's own list says which value is which.

That is why you can't copy a settings image from one camera to the other. The OM-5 stores 77 more values than the
E-M5 III, and some of them sit in the middle of the list. Every value after such a spot moves. The firmware guards
against this. Each camera marks its image with its own layout number and resets everything on an image with another
number. So a foreign image is never misread. The settings are reset to their defaults.

## Shared settings

- **About 2,000 settings exist on both.** For 1,824 of them only the number changed. The first 760 numbers are
  identical. From there on the OM-5 counts one lower, and further shifts follow where it added settings.
- **209 settings work the same but offer other choices or start from another factory value.** For example, the
  OM-5's Super Control Panel offers one more layout, the OM-5 has more custom buttons, and its picture review time has another factory value.
- **2 settings moved to another stored value.** Both are the "change" variants of the AF area and AF frame position.
- **20 settings store another setting's number as their value.** These are mostly dial assignments, such as "the
  main dial changes ISO in S mode". The OM-5 split ISO, aperture, shutter and white balance into separate still and
  movie settings. So the E-M5 III's "ISO" becomes the OM-5's "ISO (still)" in those lists.

## Settings on one camera only

- **OM-5 only (327 settings).** Live ND, hand-held High Res, Starry Sky AF, subject detection, My Menu, separate
  still and movie values for exposure and white balance, custom AF area sizes, extra custom buttons, interval
  shooting extras, a temperature unit and the GPS logger. 79 of these use a value the E-M5 III already stores but has
  no menu row for.
- **E-M5 III only (18 settings).** A High Res option for RAW editing (the OM-5 keeps it elsewhere), and 17 settings at
  the end of the E-M5 III's list that we could not name yet.

## Conversion

A settings image can be converted from one camera's layout to the other's on a PC. It works both ways. Every value
is read with the source camera's list, translated where needed, and written out with the target camera's list. We
checked these rules with a converter of our own.

- Values both cameras understand are copied.
- A value the target camera doesn't offer falls back to the target's factory value.
- Dial and button assignments are translated to the other camera's numbers.
- Where the OM-5 split one setting into still and movie, both halves get the E-M5 III's value.
- The custom modes C1 to C4 are moved too. They are stored by setting number, so each entry is renumbered.
- Settings only one camera has are dropped or left at the factory value.

A test with made-up settings went from the E-M5 III to the OM-5 and back. It lost one value, which the OM-5 does not
offer.

The same comparison gives a checklist of every setting that differs from the other camera's factory values. With
that list you can set up the other camera by hand, with nothing changed on either camera.

Getting a settings image out of a camera and back in is the harder part, and we have not done it. Setting the
camera up by hand from the checklist always works.

## Credits

Built by the project from both stock firmware files. The idea of keeping card-mod values inside the camera's own
settings image came from earlier project work on [saved settings and menu rows](../features/saved-settings-and-menu-rows.md).

## Further reading

- [Settings map E-M5 III ↔ OM-5: technical notes](settings-map-om5-technical.md) has the firmware tables, the full map
  and the conversion rules, with their addresses.
- [Saved settings and menu rows](../features/saved-settings-and-menu-rows.md) explains how our card mods keep values in
  the settings image.
- [Settings and menus](../firmware/settings-and-menus.md) covers setting ids and properties.

