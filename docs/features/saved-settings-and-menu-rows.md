# Saved settings and menu rows

<!-- house style -->
> **Technical reading.** The detailed version of [Settings and menus](../guides/settings-and-menus.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

A feature added to the camera's firmware needs somewhere to keep its settings, and a menu entry to change them. This
page describes a method that does both on the E-M5 III (firmware 1.7).

- **Native menu rows.** New rows and a new menu page look and behave like the camera's own. The first use is a
  **Live ND Shooting** row in Shooting Menu 2, right after High Res Shot, where the OM-5 has it. Pressing right opens
  a page with Live ND Shooting (Off/On), ND Number (ND2/4/8/16) and LV Simulation (Off/On).
- **Settings kept across power-off.** The values sit in an unused part of the camera's own saved settings, so the
  camera saves and reloads them itself. There is no card file and no new flash writer.

The method works on the camera.[^cam1] The rows appear in the right place, the page opens, and values set on the page
are still there after power-off and power-on. That is one camera and one owner so far.

Terms used here:

- **Store 50** is the camera's store of user settings, a 256 KB image in RAM that is saved to flash as one piece.
- **Setting id** is the number the menu code uses to name one setting. Live ND on the OM-5 is 1681.
- **Section** is one of the ten parts of the main program that load in the background after power-on.
  See [Boot and sections](../firmware/boot-and-sections.md).

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred or seen in an emulator.

## Where the values live

The store-50 live image is in RAM and is `0x40000` bytes long. At boot the camera loads the whole saved bank into it.
At power-off the save routine compares the **whole** image with the bank and writes it if anything differs. The stock
records end well before the end of the image, and stock code never reads the rest. So bytes written into that unused
tail are saved and restored by the camera itself.[^fw1] [^cam1]

The block used here starts at image offset `+0x39f00`.

| offset | size | meaning |
|---|---:|---|
| +0 | 4 | marker `MOD\x01` (`0x4d4f4401`). Anything else means "not set up yet". |
| +4 | 1 | Live ND on/off (1 = on) |
| +5 | 1 | ND number, 1-4 = ND2/ND4/ND8/ND16 |
| +6 | 1 | LV Simulation (1 = on) |
| +8..+0x47 | 64 | 16 words reserved for tuning values |

*The saved block in the unused tail of store 50.*

On the first menu use after a flash, if the marker is missing, the code writes the defaults (Off, ND8, Off). It also
zeroes the reserved words and writes the marker. Code that reads the block range-checks every value, because the tail
of a camera that never ran this code holds leftover bytes.[^fw1] [^cam1]

New settings don't go into the store's record list, for two reasons.[^fw1]

- Values in the store are packed in record order without ids, so inserting a record shifts every later one.
- Appending at the end is safe, but the property table the store uses sits in memory that loads before everything
  else and has no room left. Moving it means changing the earliest boot copy.

The unused tail needs none of that.

These are the limits of the method.[^inf1]

- A battery pull loses changes made since the last save. The camera saves at power-off.
- A settings reset or the stock restore file does not clear the tail. The marker and range checks cover that.
- Firmware without this code ignores the block.

## How the menu rows are added

The E-M5 III menu is built from data tables. They are tab lists, page records, screen and controller tables, value
lists and a string table. The new rows are mostly new copies of these tables in free space. The counts and base
pointers in the stock code are changed to point at the copies.[^fw1]

- **Tab placement.** A tab page holds at most 7 rows. To fit Live ND Shooting after High Res Shot in Shooting Menu 2,
  RC Mode moves to the end of Shooting Menu 1.[^fw1] [^cam1]
- **New page.** One more page record, controller and submenu entry (counts 124 to 125, 169 to 170, 146 to 147), so the
  row's RIGHT key opens a native page.[^fw1] [^cam1]
- **New setting ids 16000-16002.** The menu getter and setter get a short hook. Ids 16000-16002 read or write the
  bytes in the saved block, and every other id runs the stock code.[^fw1] [^cam1]
- **Value pickers.** Option-value records (Off/On, ND2-ND16) go into the menu's option hash on first use.[^fw1] [^cam1]
- **New text.** A hook on the string lookup answers string ids 4000-4015 from a new table. So rows, titles and help
  lines show new text.[^fw1] [^cam1]

Where a row sits and where its value is stored are independent. A row reaches its value through its setting id. So a
row can go where the OM-5 has it while the value lives at the end of the store.[^fw1]

## Where the code goes: the boot lesson

The menu getter and setter are already called during boot, before the menu is ever opened. That decides where the new
code may sit.[^cam1]

Sections become **ready** in number order, 1 to 10. The code reads them in number order too.[^fw2] Until a section is
ready, the loader keeps a memory access monitor over it and everything after it. Any access there stops the
boot.[^fw1]

See also: [CPU1 and CPU2](../hardware/cpu1-cpu2.md#loading-the-program-sections).

- **First placement.** The code sat in the gap after section 7 and was called from hooks in section 2. Section 7
  becomes ready late, so the boot-time hook reached it too soon. The camera boot-looped, with the stabiliser starting
  and stopping repeatedly. It was recovered by flashing the previous firmware from the card. An emulator that does not
  model the monitor ran it fine.[^cam2]
- **Working placement.** Code and tables sit in the free space after **section 3**, with the section-3 end constant
  raised to cover them. The getter and setter hooks first go to a small guard at the end of section 2. The guard tests
  the ready bit for section 3 and runs the stock code until that bit is set. The string hook sits in section 6, which
  is ready after section 3, so it needs no guard. The option records are linked on first use rather than from a boot
  hook. The camera boots normally.[^cam1]

> [!WARNING]
> A hook may reach code in another section only if that section becomes **ready** before the hook can run, or if the
> hook tests the section's ready bit first. Checking the read order is not enough. Our first placement broke this
> rule and the camera boot-looped.[^cam2]

## Custom Menu letter

The mod loader adds a letter **K. Mods** after J2 in the Custom Menu (gear tab). It has one row per mod found on the
card plus a Wi-Fi Shell row, each with the stock Off/On list. It works in om-emu.[^emu1]

A new letter needs one entry in each of the tables below. Each is a copy of the stock table plus one entry, in free
space, with the stock code's pointer and count moved to the copy.[^fw1] [^emu1]

- **Letter id lists** (u16 ids, 21 letters). Add letter id 3293, which the firmware already knows but never
  shows.[^fw1] [^emu1]
- **Letter glyphs** {id, glyph, selected glyph}, 22 entries.[^fw1] [^emu1]
- **Letter to page key**, 21 entries. K gets the unused key 103.[^fw1] [^emu1]
- **Preview records** and **open-page records**, 24 each, 20 B {id, rows, title kind, title, items, aux}. Title kind
  5 takes 8-bit text, not UTF-16.[^fw1] [^emu1]
- **Page row lists** {key, n, -> {cond, n, -> ids}}, 24 entries. The row count is written at run time, after the card
  scan.[^fw1] [^emu1]
- **Letter to controller** {id, controller, 0}, 24 entries. The value is a controller id, not an index. The controller
  table (169 × 36 B) gets controller 86 for key 103. Without it the page opens empty.[^fw1] [^emu1]
- **Row kinds** {id, kind}, 90 entries. Kind 1 gives the Off/On list. A row id missing here gets a +2..-2 level
  slider.[^fw1] [^emu1]
- **Letter pictures.** The letter cell draws one picture per letter from 32 picture lists of 16 B entries (21 used,
  padded with zero entries). It also uses 32 widget templates whose count byte goes 21 to 22. K uses two retired
  picture ids (`0x129e`, `0x1289`). The loader fills their slots in the RAM picture table at start-up. Without the
  22nd entry the cell shows the A1 picture.[^fw1] [^emu1]
- **Values and text** use the same getter, setter and string hooks as the Live ND rows, with setting ids 16100-16106
  and string ids 4100-4109. Row names come from the mods' file headers at run time.[^fw1] [^emu1]

> [!WARNING]
> On the camera the loader worked, but MENU reset the camera. The cause was extending the letter-cell picture lists.
> Without that edit the menu works.[^cam3]

See also: [Gotchas](../reference/gotchas.md).

### Scrolling page

One letter page holds more rows than fit on screen and scrolls natively.[^emu2]

- The K page has 1 + 2 × 10 static row ids.
- The shown count (Wi-Fi + m mod rows + m "Load:" rows) is written at run time.
- The getter, setter and string hooks map row r to its mod at run time. So the shown rows are always a prefix of the
  static list.

### Cursor on the first row

In om-emu the page first opened with the cursor on its last row, and a camera run showed the same bug.[^emu2] [^cam3]
The cause and fix are in the controller-init table.[^fw1] [^emu2]

- A page's controller needs an entry in the controller-init table, which has 49 entries of {u16 ctl, 0, init}, one
  reader and one count byte.
- Without one it gets the default init. That hands the list constructor the raw controller words {key, items}.
- The list reads items != 0 as "entered from below". Flag (64) is set, so the cursor goes to the last shown row.
- Stock list pages (J2, ctl `0x58`) use the stock list init, which passes {key, direction}.
- Adding {ctl, 0, stock list init} makes the page open on its first row.

### Value column and scroll bar

Right-aligned values touch the scroll bar of a page with more than 7 rows. No stock custom-menu page scrolls on this
body. Our own "On" and "Off" strings with three trailing spaces clear it. Help strings need "\r\n" line breaks, at
about 30 characters per line.[^emu2] [^cam3]

### Letter cell

A letter missing from the letter picture and group table gets a blank cell. That table has 25 entries of {id, sel pic,
normal pic, group} and two readers. Adding the letter gives a cell with a stand-in picture. There is no K picture
without the letter-cell list edit, which reset MENU.[^emu2]

### A second letter

A second letter (3295/3292) shows its rows, but RIGHT does not open it. Letter 3296 is not shown at all.[^emu2] A
second new letter never reaches the page-open code on RIGHT. We tried ids 3295/3292, ctl 82/98/103/43, keys
129/107/112 and group 10/11.[^emu2]

## Older bodies

- **E-M5 II 4.1** has the same `MODE_*` key-table design, with 4,192 names in block 2, and the same `SubApp`/`OlyApi`
  layers. So the method carries over.[^fw3] The saved-values store differs. There is no "acc flash write" settings
  image, as on the PEN-F. New addresses are needed throughout.[^inf2]
- **E-M5 (Mark I) 2.3** has no `MODE_*` key table and an older framework, with no Rhapsody OXF. It needs a re-port from
  scratch.[^fw3]

See also: [Older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Credits

The idea of keeping mod settings in the unused tail of the camera's own settings image comes from the Caduceus E-P7
project's internal-storage notes, which follow the Caduceus OM-3 port. This page applies it to the E-M5 III, adds
native menu rows, and reports the camera result.

## Address reference

Runtime addresses in block 0 (load base `0x60021020`), E-M5 III 1.7.

| item | address |
|---|---|
| store-50 live image (`0x40000` bytes) | `0x623d1000` |
| saved block (image offset `+0x39f00`) | `0x6240af00` |
| save routine at power-off | `0x6005aaaf` |
| menu getter, setter | `0x602e6a02`, `0x602e6f11` |
| menu option hash | `0x62118d08` |
| string lookup | `0x60c9350c` |

*Saved settings and the menu hooks.*

| item | address |
|---|---|
| free space after section 3 | `0x605d4000` to `0x605da000` |
| section-3 end constant, raised from `0x605d4000` to `0x605da000` | `0x60045e1d` |
| section ready bits (section 3 is bit `0x04`) | `0xa26565c0` |

*Boot placement.*

<details><summary>Custom Menu letter tables and code</summary>

| item | address |
|---|---|
| letter id lists | `0x6106a6f4`, `0x6106a6fc` |
| letter glyphs | `0x610974aa` |
| letter to page key | `0x61097456` |
| preview records | `0x61097270` |
| open-page records | `0x610780e0` |
| page row lists | `0x6106a824` |
| letter to controller | `0x61070d04` |
| controller table | `0x61064b98` |
| row kinds | `0x610783d8` |
| RAM picture table pointer | `0x61eb7628` |
| controller-init table | `0x6105e7fc` |
| controller-init reader, count byte | `0x60d59309`, `0x60d59330` |
| default controller init | `0x60d5939c` |
| stock list init | `0x60d5945c` |
| list constructor | `0x60d620e7` |
| letter picture and group table | `0x610782c0` |
| its readers | `0x60d7552a`, `0x60d75749` |
| page-open code | `0x60d6cbb0` |

*Tables and code for the Custom Menu letter.*

</details>

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^fw2]: Read in the firmware, 2026-11-25.
[^fw3]: Read in the firmware, 2026-11-21.
[^cam1]: Seen on our E-M5 III using test firmware, 2026-11-19.
[^cam2]: Seen on our E-M5 III using test firmware, 2026-11-19. The first placement boot-looped.
[^cam3]: Seen on our E-M5 III using test firmware, 2026-11-22, in camera runs of the mod loader's menu letter.
[^emu1]: Seen in om-emu, 2026-11-22.
[^emu2]: Seen in om-emu, 2026-11-22. The scrolling page, cursor, value column, letter cell and second letter tests.
[^inf1]: Inferred, not traced or tested.
[^inf2]: Inferred, 2026-11-21.

## History

- 2026-11-25: an earlier note said sections were read in the order 1, 7, 2 and so on. The code reads them in number
  order.

