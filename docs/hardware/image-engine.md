# Image engine

<!-- human page -->
> The dense reference for this page is [Image engine: technical notes](image-engine-technical.md).

The image engine is the part of the camera's chip that does the heavy pixel work. It develops raw frames, resizes
pictures and merges several frames into one. It does not run the camera's main program. Instead, the main processor
hands it a small program and a page of settings, starts it, and waits for it to finish.

We call it "the DSP", and its programs "jobs". Most of what follows is common to every Olympus and OM System body from
the E-M5 II onwards. The differences between cameras are collected at the end.

## Status

- **Running jobs works.** We can load a job, give it its settings and run it on the E-M5 III, including jobs copied
  from the OM-5.
- **We know what most of the E-M5 III's own jobs do.** Jobs 0 to 10 are mapped, some firmly and some by inference.
- **The program format is partly understood.** We know how instructions are laid out, how branches work and roughly
  what the main fields do. The instruction set as a whole is not decoded.
- **Two of our ports depend on it.** Live ND uses the OM-5's job 11 to merge frames. Handheld High Res Shot needs
  jobs 14 to 17.

## How a job runs

The job programs are stored in the firmware file. At start-up the camera copies them into memory.

To run one, the main processor does four things.

1. It fills in a **record**, a block of memory that says where the input frames are, where the output goes and how
   big the frames are.
2. A small **setter** function for that job copies the record into the engine's **parameter window**. That is a range
   of addresses the engine reads its settings from.
3. The setter also tells the engine where the job's program is.
4. The main processor starts the engine and waits. The engine raises an interrupt when it is done.

Each job has a time limit, from 4 ms for the quickest to 4 seconds for raw development. A job that overruns is treated
as failed.

The engine has two slots, so two jobs can be set up side by side. A lock per slot keeps two tasks from using the same
slot at once.

## The E-M5 III's own jobs

| job | what it does | how sure |
|---|---|---|
| 0 | image processing for autofocus | likely |
| 1 | unknown | |
| 2 | combines 2 or 3 raw frames, used by Live Composite | likely |
| 3, 5, 6, 7 | steps of the in-camera focus-stack merge | strong |
| 4 | aligns a frame to a reference using motion vectors | read in the code |
| 8 | fast memory copy | read in the code |
| 9 | raw development, in 8 strips | likely |
| 10 | a fixed filter or resampler | read in the code |
| 11 to 17 | empty placeholders | read in the code |

Two findings stand out.

**The camera already aligns frames.** Job 4, together with the motion detector, lines one frame up with another. The
in-camera focus stacking uses it. That is the missing piece for hand-held multi-frame features, such as a hand-held
Live ND or noise reduction from several frames.

**There is no averaging job.** Nothing in the E-M5 III averages, subtracts or takes the minimum of frames. So Live ND
still needs the OM-5's job 11.

The empty placeholders are telling as well. The E-M5 III still has time limits listed for jobs 11 to 17. The framework
was never cut down, only the programs were left out.

## The programs

A job program is a list of wide instructions, each 320 bits long. Each instruction controls many parts of the
engine at once, rather than doing one small step. This style is called horizontal microcode.

What we have worked out by comparing the programs of five cameras:

- The instructions are not scrambled or encrypted. The same instruction looks the same wherever it appears.
- Every program starts with the same few instructions and ends with a special "end" instruction.
- Jumps use absolute instruction numbers. When one version of a program grows, every jump past the change moves by
  exactly the size of the change. That is how we found the jump field.
- Each instruction drives two identical **lanes**, which look like two matching datapaths. Each lane picks from 15
  registers, with one more value meaning "unused".
- A few bits carry small numbers such as frame sizes and counts.

## Testing on the camera

To learn what the fields do, we ran the OM-5's job 11 on small test images, changing one part of one instruction each
time. Over four rounds that came to more than 1,600 runs. Not one of them hung or crashed the engine.

The runs showed:

- which field picks the output register and which picks the inputs
- where the black level and the clipping level come from
- a gain step that scales brightness around the black level, which is the natural place for an ND brightness setting
- that job 11's output is exactly the average of its inputs, in the camera's own packed 12-bit raw format

Merging 16 full-size frames takes about 143 ms.

## Running a job safely

One lesson came straight from the camera. Before a job runs, a check function looks at its record. If it refuses the
record, the engine's worker task stops for good. The camera then freezes the next time anything uses the engine, and
only taking the battery out helps.

So every change to a record has to be checked against that function's rules first. Program addresses also have to be
in the right memory range, or the camera resets.

## Other cameras

### E-M1 III, OM-5 and OM-5 II

The same engine as the E-M5 III, with the same jobs 0 to 10 byte for byte. On top of those they add:

| job | what it does |
|---|---|
| 11 | Live ND photo merge, the average of up to 32 frames |
| 12 | Live ND live-view preview |
| 14 to 17 | Handheld High Res Shot |
| 18 | unknown |

The OM-5 II's High Res jobs differ slightly from the OM-5's. The image-engine data shared by all jobs is identical on
the E-M5 III, E-M1 III and OM-5, so anything that draws on it is already in the E-M5 III.

### PEN-F and E-M5 II

An older generation with the same program format. The empty placeholder and the memory-copy job are byte for byte the
same as the E-M5 III's. The other programs are their own. Across 112 fields, these older programs use nothing the
newer ones do not. Whether a newer job would run on this older engine has not been tested.

### OM-1 and OM-1 II

A new engine. None of their job programs match any of the above, so OM-1 jobs cannot be used on the E-M5 III.

### E-M5 (Mark I)

No programs of this format at all.

## Where it comes from

No vendor or core name appears anywhere in the firmware. The chip belongs to Panasonic's "dc13" family, the same line
as the Lumix Venus Engine, and the engine looks like Panasonic's own design rather than licensed DSP. An old Matsushita
patent describes a program-controlled image processor with a sequencer and two matched pipelines, which fits what we
see. We do not use Lumix firmware, because Panasonic's licence forbids reverse engineering it.

## Further reading

- [Live ND](../features/live-nd.md) uses job 11.
- [Handheld High Res Shot](../features/hhhr.md) needs jobs 14 to 17.
- [Taking a photo](../guides/taking-a-photo.md) shows where raw development fits in a still shot.
- [Frame pools and memory](../guides/frame-pools-and-memory.md) covers the buffers the jobs read and write.
