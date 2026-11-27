# Face and eye detection

<!-- human page -->
<!-- house style -->

## Key points

- The camera finds faces with a dedicated detector built into its main chip, not with the image engine, the ARM chip or
  a neural network.
- A second built-in unit finds 38 points inside each face, and the eyes are worked out from these points.
- Both units compare the picture with stored pattern tables that are byte for byte the same on the E-M5 III and the
  OM-5 II.
- Autofocus picks up the results through the same kind of target slots that subject detection uses.

This page explains how the camera finds faces and eyes and how autofocus uses them. It covers the stock E-M5 III 1.7
program, compared with the OM-5 II 1.1 program read from its update file. The two work the same way. Everything here comes from reading the
firmware. Nothing has been tested on the camera yet.

## Detector

The main processor runs two face tasks. One prepares the work and one drives the hardware. On every live-view frame
the display system writes a small copy of the picture for the detector. The face task points the detector at that copy
and starts it.

The detector searches the picture for faces at several sizes and angles. For each face it reports the position, the
size, an angle, a confidence score and the pose. It can also be told the smallest face to look for and which way faces
may be turned.

The second unit runs straight after the first one. It takes each face box and finds 38 points inside it. These are most
likely landmarks such as the corners of the eyes, the nose and the mouth. The camera turns them into a left eye and a
right eye, each with a position, a size and a confidence.

The E-M5 III firmware still contains debug commands named after OKAO Vision, a face recognition library from Omron.
That suggests Olympus licensed it. The OM-5 II firmware removed those commands.

## Pattern tables

The face detector compares the picture with two stored pattern tables of 107 KB and 57 KB. These tables are what
the detector "knows" a face looks like. The camera loads them from the firmware file into memory at power-on. They are
identical on the E-M5 III and the OM-5 II, so the detector has not changed between the two cameras.

The tables are far smaller than a subject-detection neural network, which needs several megabytes. The format
of the tables is not known yet, so it is too early to say whether the detector could learn other subjects.

## Results

The face module keeps its results in a small set of fixed memory records. They hold up to several faces with their
boxes, the chosen main face and its eyes. A separate list holds the boxes that the screen shows.

## Autofocus

Each pass, the focus system copies the main face and its eye into its list of possible targets. A face chosen by
touch has its own place in that list. Subject detection uses the same list and the same record layout.

When the camera picks where to focus, it checks the possible targets in this order.

| order | target | when it applies |
|---|---|---|
| 1 | clipped live view | a special clipped view is active |
| 2 | subject detection | the subject detection switch says yes (always no on the OM-5 II) |
| 3 | face chosen by touch | Face Selection by touch is on and a face is chosen |
| 4 | magnified view | the view is magnified |
| 5 | face or eye | Face Priority is on and a face is found |
| 6 | normal AF area | nothing above applies |

*Targets the camera checks when it picks where to focus, in order. Read in the OM-5 II firmware.*

For a face, the camera also looks at the eye. It uses the eye when the eye is inside the usable area and the sizes
make sense. Otherwise it uses the face.

## Frames on screen

After each detection pass the face module tells the screen's frame layer that new face frames are ready. The frame
layer then draws them from the face module's display list. The exact drawing code is not traced yet.

## Bird boxes

Our bird boxes could be fed into the face path by writing them where the face goes. The camera's own detector rewrites
that place on every pass, so the two would fight. Subject detection is also checked before faces. So the subject
detection route is the better one, and the face path stays a fallback.

## Open questions

- Which code draws the face and eye frames on the screen.
- The format of the pattern tables.
- The exact meaning of the 38 points and some of the small result fields.

## Further reading

- [Face and eye detection: technical notes](face-detect-technical.md) has the detector registers, the result records,
  the autofocus path and the address reference.
- [Face and subject AF options](af-detect.md) sorts the face, eye and subject features by body.
