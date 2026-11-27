# Autofocus and tracking AF

<!-- human page -->
<!-- house style -->

## Key points

- Autofocus is a chain of parts, from the shooting sequence through an AF sequencer and a focus task to the lens
  drive.
- The focus task uses phase detection, which says how far out of focus a spot is and in which direction, and contrast,
  which says how sharp a spot looks.
- C-AF remembers where the lens was over time and predicts where it needs to be next.
- Tracking is a separate module that follows the subject by movement and colour, with no idea what a bird or a car
  looks like.

This page explains how autofocus works in the OM-5 II firmware, with notes on the stock E-M5 III. It then explains how
C-AF with tracking follows a subject and where it is likely to go wrong. Everything here comes from reading the
firmware. Nothing has been tested on the camera yet.

The shooting sequence asks an AF sequencer to focus. The sequencer gives jobs to a focus task. The focus task moves
the lens. The OM-5 II's tracker is a newer generation than the stock E-M5 III's.

## The parts

| part | what it does |
|---|---|
| shooting sequence | reacts to the half-press and starts focusing |
| AF sequencer | decides between single AF and continuous AF and when to start, restart or stop |
| focus task | picks the AF point, reads the focus data and works out where the lens should go |
| focus data | phase-detect and contrast values that the image pipeline produces for every live-view frame |
| lens drive | sends move commands to the lens |
| tracker | follows the subject and reports its position |
| face detector | finds faces and eyes (see [Face and eye detection](face-detect.md)) |

*The parts of the autofocus system and what each does.*

The focus task and the AF sequencer run at a high priority on the main processor. The tracker uses two processor
cores and two special search units in the image pipeline.

## Phase detection and contrast

The sensor has special pixels that see the scene from two sides of the lens. When the image is out of focus, the two
views are shifted against each other. The size and direction of the shift tell the camera how far to move the lens
and which way. This is phase detection. It is fast because one reading is enough.

Contrast works differently. The camera measures how much fine detail an area has. It moves the lens and looks for the
position where detail peaks. The firmware uses three sharpness filters per area for this. Contrast is slower but very
accurate. The camera uses it when phase data is weak, for example in low light or with older lenses.

## Single AF and continuous AF

In single AF the camera focuses once and stops. It most likely uses phase detection to get close and a short contrast
check to finish.

In continuous AF the camera keeps focusing while the button is half-pressed. It keeps a history of lens positions and
times. From that history it fits a smooth curve and predicts where the subject will be at the next frame. That is how
it keeps up with a subject that moves towards or away from the camera.

C-AF also has a lock-on setting with five levels. It decides how long and how big a sudden focus change the camera
ignores. This stops the focus jumping to something that crosses in front of the subject.

## Choosing the focus point

Several sources can propose a target. These are the subject-detection result, a touched face, a face, the tracker and
the normal AF area. A chooser picks one in a fixed order and writes it into one AF point record. The focus task then
reads the focus data at that point.

## Tracking

When C-AF with tracking starts, the tracker takes the subject under the AF point and follows it frame by frame. It uses
several helpers.

- **Motion search.** A hardware unit compares small blocks of the picture between frames. It finds where each block
  moved. It also separates the subject's own motion from camera shake.
- **Colour and size search.** A second hardware unit keeps a model of the subject's colours, brightness and size. It
  checks each frame for the area that matches best.
- **Faces.** When the face detector finds a face on the subject, the tracker can use it.
- **Depth.** The phase-detect data also says how far away each area is. A depth tracker grows a region of similar
  distance around the subject. This helps when something passes in front.
- **Subject detection.** The tracker has a slot for a neural network's detections. In the OM-5 II firmware nothing
  fills it.

Each frame the tracker weighs these helpers, checks how much it trusts each one and picks one position. It also
predicts where the subject will move next. The position goes to the focus task as the tracking AF point.

## The two search units

The motion search unit is not only for tracking. The camera shares it between several jobs. These are flicker
detection, noise reduction, scene detection, subject detection and tracking. Each job has its own preset.

For tracking, the unit gets a small copy of the live-view picture. It cuts the area around the subject into blocks of
a fixed size. For each block it looks a few pixels in every direction in the next frame and reports where the block
went.

The colour and size unit is a template matcher. The tracker stores the subject's colours, brightness and size. The unit
compares that template with the search area and gives a score. The tracker uses the score to decide whether it still
trusts the match.

The stock E-M5 III, the E-M1X and the OM-5 II all have the same two units at the same addresses. The E-M1X's
subject-aware tracking runs on them too. So the hardware is probably not the main limit. The small search picture, the
lack of any idea of what the subject is and the fixed timers are more likely causes.

The tracker already has code to keep a detected subject when the network misses a few frames. It has a separate limit
for each subject type. This is the stability part a trained network would have to work with.

## The two switched-off gates

Two tiny checks in the focus code decide whether subject detection is in charge. The first asks whether the subject
detector is choosing the target right now. The second asks whether tracking that the detector started is still holding
the AF area. On the E-M1X both checks are real. There a small module hands each detected bird or car to the tracker
and switches the checks on. On the OM-5 II, the OM-5 and the stock E-M5 III both checks always answer no, and the
hand-over module is missing. The tracker still has its side of the subject-detection code. So our subject detection
needs three pieces to steer tracking. It needs the checks to say yes, the setters we are restoring, and a hand-over
like the E-M1X one.

## When the tracker gives up

The tracker times how long it has gone without a result it trusts. After half a second it starts searching. About one
second later it gives up and drops the subject. All these limits sit in a table of 274 tuning values. The table is
data, so it could be changed without rewriting the program.

## Limits of tracking

These are likely reasons from reading the code. None has been tested.

- The tracker follows a patch of colour and movement. It does not know what the subject is. Similar colours in the
  background or a crossing object can pull it away.
- The search works on a small picture, about 320 pixels wide. Small or distant subjects cover only a few blocks.
- The OM-5 II program removed the code that lets a subject's body or head steer the AF point. Only one tracking point
  can.
- The timers are short. A subject hidden for more than about a second is lost.
- Tracking and focus are separate. If the tracker is on the wrong thing, the focus system focuses on it accurately.

## Improvement ideas

1. Feed our subject detection into the tracker. The tracker already has the code to combine network detections with
   its own tracking. It needs our detections in its input list and a hand-over like the E-M1X one.
2. Change the tuning table. Longer timers or different trust limits could keep a subject longer. This needs a map of
   what each value does first.
3. Restore the body and head tracking setters from the OM-5, the same way we are restoring the subject-detection ones.
4. Log the tracker on the camera. The firmware has a detailed tracker log built in. A short test would show which of
   the reasons above causes most losses.

## Status

Desk research. Nothing on this page has been tested on the camera yet.

## Further reading

- [Autofocus and tracking AF: technical notes](autofocus-technical.md) has the tasks, the tracker's parts, the tuning
  table and the addresses.
- [Face and eye detection](face-detect.md) covers the face detector and how AF chooses a face.
- [Subject detection research](subject-detection.md) covers the network side, and [Face and subject AF options](af-detect.md) sorts the features by body.
- [Motion search unit](../hardware/motion-unit.md) describes the motion search hardware.
- [Starry Sky AF](starry-sky-af.md) uses the same contrast code.

