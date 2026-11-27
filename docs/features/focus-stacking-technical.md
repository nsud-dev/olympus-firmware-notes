# Focus stacking: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Focus stacking](focus-stacking.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

Focus stacking takes a series of shots at different focus distances and merges them in the camera into one picture
that is sharp from front to back. The stock E-M5 III only allows it with a short list of Olympus lenses. This was the
project's first patch. It removes the lens check so stacking works with any lens. This page also covers a follow-up
study on letting you choose how many shots go into a stack.

**Status: done, working on the camera.**

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = seen on our camera, blue = read in the firmware,
grey = inferred, amber = a correction.

## Lens check

**How to find it.** The check is the function that prints the debug string
`fcs_check_focus_stacking_enable stacking`. Search block0 for that string and follow the one function that references
it. It has a single caller, in the focus-stacking setup path.[^fw1]

**What it does.** It starts with result = 0 and makes two calls.[^fw1]

1. The first is a lens-type check shared with eight other callers. It reads the same lens-info field the
   Panasonic-lens test reads.
2. The second returns 1 when the attached lens carries a per-lens "supports stacking" flag.

Each call is followed by a compare and a short forward `bne` to the return. Only if both pass does it set
result = 1.[^fw1]

**The patch.** Turn the `bne` after the second call into two `nop`s. Any lens that passes the lens-type check is then
allowed. The first check stays, because eight other features use it. The original IDA patch, made before this project,
did the same. We recreated it, flashed it, and it works.[^cam1]

### Other bodies

The same function exists on the OM-5 1.2, OM-5 II 1.1, E-M1 III 1.6, OM-1 1.9 and OM-1 II 1.3. It is found by the same
debug string and has the same two-call shape and the same branch. So the one-branch change would carry over. It has not
been tried on any of them. The PEN-F 3.1 has no in-camera stacking.[^fw2]

See also: [body comparison](../bodies/comparison-technical.md#our-features-on-the-other-bodies).

### As a card mod

The same change, applied in RAM at start-up by our mod loader, works without a patched firmware.[^cam2]

## Shot count

**The count is a setting, not a constant.** When focus bracketing and stacking are both on, the shooting sequence reads
`_bracketMaxShootCount` from setting 1448 (saved property `0x9842`). The OM-5 1.2 uses the same property as its setting
1459 `MODE_FOCUS_STACKING_NUMBER`. The E-M5 III has the setting and its saved value, but no menu row.[^fw3]

How to find it: the `_bracketMaxShootCount` symbol string leads to the sequence step. Setting 1448 has one getter.
Listing its callers gives every place that reads the count. There are 12 reads, 10 through the getter and 2 in an
interlock.[^fw3]

### The OM-5 menu row

The OM-5's menu offers 3 to 8 shots (six options).[^fix1] The row is row 2 of its Focus BKT page, titled "Set number of
shots". The E-M5 III has that string and the per-setting object for 1448 already.[^fw3]

Adding the row is a data change to the E-M5 III's Focus BKT page record and its copy. It needs one more row in the
list, plus one case in that page's viewer function.[^fw3]

How to find them: the page record is the one whose row list includes the Focus BKT rows. The viewer is the function
that greys out "Set number of shots" while stacking is on.

### Other settings that touch the count

- An interlock sets the count to 8 for one particular value of setting 24, and to its default otherwise. The OM-5 has
  the identical function.[^fw3]
- Setting 1549 is the effective focus-bracketing shot count. An interlock copies 1448 into it when focus BKT and
  stacking are both on, and setting 858 otherwise.[^fw3]
- The Focus BKT viewer blanks "Set number of shots" (858) while stacking is on. This is why the count has to be set
  with stacking off.[^fw3]

### Going above 8

Going above 8 needs wider arrays. The combine controller keeps 9 buffer handles in its object (OM-5: 16). DevRec
`recordMediaFocusStacking` clips to 9 (OM-5: 16). 9 is 8 frames plus the composite.[^fw3][^inf1]

So 3 to 8 shots is a menu row (or a forced value) only. 9 to 15 also needs those arrays, the compositor and the memory
checked.[^inf1]

### The merge

The native stack merge is request engine type 5 (shot kind 19). Its first step accepts 3 to 15 frames plus a reference
index, so the merge chain itself allows 15.[^fw4] It aligns each frame with motion vectors and an image-engine job 4
warp. It merges with jobs 5, 3, 6 and 7. The output is 4480 × 3360.[^fw4][^inf2]

See also: [image engine](../hardware/image-engine.md).

## Shot count on the camera

A test build made stacking use "Set number of shots", clamped to 3 to 8. Every native read of setting 1448 goes to one
small routine that returns the clamped value. 1448 itself is never written.[^fw1]

The same hooks also run as a card mod, together with the any-lens change as a second card mod. Our mod loader loads both
from the card, with nothing else flashed.[^cam2]

1. Set 5 shots with stacking off.
2. Switch stacking on.
3. The camera takes 5 frames and the composite, and stacking works on a lens stock refuses.[^cam2]

The native menu greys out "Set number of shots" while stacking is on. An OM-5-style row was the next step.[^cam2]

## Older bodies

- **E-M5 II 4.1.** In-camera stacking code is present (`MODE_FOCUS_STACKING_ONOFF`, `MODE_FOCUS_STACKING_ENABLED_LENS`,
  `DevRec_Rec::recordMediaFocusStacking`, "Wait For Combining Finish"). The E-M5 III-shaped
  `fcs_check_focus_stacking_enable` was not found by shape (best 13 of 25 instructions). So the lens gate needs its own
  trace before a patch. Whether the stock menu offers stacking was not checked.[^fw5]
- **E-M5 (Mark I) 2.3.** It has no stacking or focus-bracket strings. There is nothing to patch.[^fw5]

See also: [older bodies](../bodies/comparison-technical.md#older-bodies-e-m5-ii-and-e-m5-mark-i).

## Open questions

- The compositor behind `evTraCmpSts_StartCombine` was the next thing to find for counts above 8.[^inf1]

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware.
[^cam1]: Seen on our E-M5 III, 2026-10-19, with the recreated patch flashed.
[^fw2]: Read in the firmware of each body, 2026-11-20.
[^cam2]: Seen on our E-M5 III, 2026-11-22, with the changes loaded as card mods by our mod loader.
[^fw3]: Read in the firmware, 2026-11-05.
[^fix1]: Corrected 2026-11-05. The first reading was 3 to 15 shots. See [History](#history).
[^inf1]: Inferred, not traced or tested, 2026-11-05.
[^fw4]: Read in the firmware, 2026-11-06.
[^inf2]: Inferred, not traced or tested, 2026-11-06.
[^fw5]: Read in the firmware of the E-M5 II 4.1 and E-M5 Mark I 2.3, 2026-11-21.

## History

- 2026-11-05: the OM-5 menu was first thought to offer 3 to 15 shots. It offers 3 to 8.

