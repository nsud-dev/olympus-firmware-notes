# Guides: how the camera works, told start to finish

The rest of this knowledge base is reference: short facts, grouped by subsystem, each with a tag and a source. That
is good for looking something up and hard to read for understanding. These guides are the other half. Each one follows
a single process through the firmware (taking a photo, booting, a button press) and explains what happens and why,
written for someone with an embedded background who is curious how this camera works.


## How guides relate to the reference pages

- **Guides tell the story; facts live on the reference pages.** A guide links to the reference page for every address,
  struct and camera result it relies on. When writing a guide turns up a new fact, it goes on its reference page first
  (with tag, date and source, and a CHANGELOG line), and the guide links to it. That way the two can't drift apart.
- **One body, one version.** Each guide is written for the **E-M5 III fw 1.7**. Every address is a 1.7 block0 VMA unless
  another body is named.
- **Other cameras: "checked on" tables.** Each guide ends with a table of its steps against the other bodies we hold
  firmware for. A cell is **confirmed** (with that body's address), **different** (and how), or **not checked**. Nothing
  is assumed across bodies: the family shares a lot, but a blank cell means we don't know.
- **Gaps are tracked.** What a guide can't explain yet goes in research gaps, the list of open
  questions.


## Addresses and tags stay out of the prose

Main text explains what happens in plain words. Addresses, offsets and confidence tags go in a collapsed
**Where in the firmware** box at the end of each section (`<details>` with a small table), so a curious reader can skip
them and a patcher can expand them. Abbreviations are spelled out on first use, short form in brackets.

## Style

Technical but plain: no scene-setting, no drama. Describe the stock firmware first; how our features change it goes in
a separate section at the end. Readable from start to finish: plain sentences, terms explained when first used, one idea per paragraph,
diagrams where a flow is easier to see than to read. Keep each guide to a 15-20 minute read; put the dense detail on
the reference pages it links to.

## The guides

Start here: [Before you start](before-you-start.md) (the pieces and the words) and
[IBM Rhapsody and OXF](rhapsody-and-oxf.md) (why so much of the code looks generated).

| # | guide | status |
|---|---|---|
| 1 | [Taking a photo, end to end](taking-a-photo.md) | done |
| 2 | [Boot: from power switch to a running camera](boot.md) | done |
| 3 | [The MN103 operating system](operating-system.md) | done |
| 4 | [An MN103 primer](mn103-primer.md) | done |
| 5 | [How the cores talk to each other](cores.md) | done |
| 6 | Timers and time | planned (needs research) |
| 7 | [How a button works](button-press.md) | done |
| 8 | [Live view, from sensor to screen](live-view.md) | done |
| 9 | Anatomy of a feature port (Live ND as the worked example) | planned |
| 10 | Reading the decomp: a field guide | planned |
| 11 | [What's in a firmware file, and how updates and recovery work](firmware-file.md) | done |
| 12 | The image engine | proposed; waits for the image-engine research |
| 13 | Settings and menus | proposed |
| 14 | Frame pools and memory | draft 1 (2026-11-19) |
| 15 | The ARM side | proposed |
| 16 | The sensor and its modes | proposed |
| 17 | Talking to the camera (shells, consoles, logs, card files) | proposed |
