# Model training: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [Model training](model-training.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the training of our own detection models for the
[network engine program](nn-engine-program-technical.md). We use PyTorch, our own code and public data. No vendor
weights, tables or pictures are used for training. The E-M1X network appears only as a benchmark, scored through our
own reference model of its arithmetic.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: green = measured on our E-M5 III using test firmware,
blue = read in our own code and training runs, grey = inferred or planned.

## OWN-1 network

| part | design |
|---|---|
| input | 480 × 480, 3 or 4 planes (R, G, B, optional depth or motion) |
| stem | 3 × 3 conv, stride 2 |
| body | stem 8 wide, then depthwise-separable blocks widening 16, 32, 64, 96, 128 |
| heads | stride 16 (30 × 30) and stride 32 (15 × 15), upsample and concat between them |
| outputs | per anchor: box x, y, w, h, objectness, part scores (body, head, eye) |
| cost | 68.2 million multiply-adds at 480 (30.3 million at 320), about 104,000 weights |

*The OWN-1 network.[^fw1]*

- **No normalisation layers.** A data-dependent init scales each conv to unit output spread on real pictures. See
  [Init from data](#design-notes).[^fw1]
- **Box decode.** It follows a YOLO-style form. x and y are offsets from the cell centre. w and h are linear in the head
  value times the anchor. Anchors come from IoU k-means over training boxes.[^fw1]

## Quantisation and integer training

```
pseudocode: from float model to camera model
train in float32 (YOLO-style loss with ignore regions for unlabelled parts)
calibrate on up to 768 training pictures: record each layer's range before the activation
for each layer:
    fold per-channel scales into int16 weights and int16 biases in output units
    pick one shift so every term and running partial stays within 24,000
give each head output its own scale
export
check: the integer model on the PC equals the engine program's output, every buffer, byte for byte
```

- **Integer model.** float64 code that follows the engine contract exactly. That means rounding half to even per term,
  a 32-bit sum, int16 saturation and an optional leaky slope.[^fw1]
- **Calibrate before the activation, not after.** Pre-activation negatives and head values passed int16 in the first
  smoke net.[^fw1]
- **The 24,000 cap matters.** With 64 calibration pictures and a 30,000 cap, unseen pictures reached 34,674. That would
  overflow the 16-bit running sum.[^fw1]
- **Head scales must be free.** Pinned to a fixed decode scale, confident birds pushed head terms to 68,200, and integer
  eye AP fell from 0.52 to 0.19. With free scales the largest term is 23,865, and integer matches float.[^fw1]
- **Camera check.** The trained bird model's camera output decodes to the PC reference. On the test picture that is body
  1.000, head 0.952 and eyes 0.574 and 0.307.[^cam1]

## Picture database

There is one manifest per source. For each picture it lists which subjects are boxed (known 1) and which a person
verified absent (known 0). Recipes cut YOLO-format training sets from it. Class -1 marks an ignore region, used where
parts such as heads and eyes are not labelled.[^fw1]

| source | licence | use |
|---|---|---|
| Open Images V7 | CC BY 4.0 (annotations), pictures listed CC BY 2.0 | 34,741 bird pictures and 10,504 verified bird-free in train |
| COCO 2017 | CC BY 4.0 (annotations) | people, cats, dogs, negatives |
| CUB-200-2011 | non-commercial research | close bird photos with part points |
| AP-10K | CC BY 4.0 | animal keypoints (candidate) |

*Picture sources and their licences.[^fw1]*

NABirds and GOT-10k are non-commercial and not used.[^fw1]

The birds v2 recipe has 87,874 train pictures, half with birds and half verified bird-free. It trains 40 epochs at 480
in 1 h 54 min.[^fw1]

## Design notes

The architecture, a depthwise-separable detector with YOLO-style heads, is standard. So is the conversion to integers,
by post-training calibration with per-channel scales folded into weights. What is less usual is that the model, the
quantiser and the engine program were designed together, and that the camera's arithmetic is reproduced exactly.[^fw1]

**The quantiser protects a hardware shortcut.** The engine program adds per-channel terms with a saturating 16-bit add.
That is only exact while every running partial stays inside int16. So the quantiser bounds not only each layer's
outputs but every term and every running partial, in the order the program adds them, at 24,000. With 64 calibration
pictures and a 30,000 cap, an unseen picture reached 34,674 and would have broken the shortcut. Up to 768 pictures and
the lower cap hold it.

**Calibrate before the activation.** Leaky layers make negatives small after the activation, but the engine must hold
the value before it. Our first net was calibrated after the activation, and its pre-activation values passed int16.
Calibrating before it fixed that. The E-M1X network also keeps its pre-activation values inside int16.

**Free scales for the head.** Pinning the head to one decode scale let confident subjects push head terms to 68,200.
Integer eye AP fell from 0.52 to 0.19 while float looked fine. Each head output now has its own scale. The largest term
is 23,865, and integer matches float.

**A bit-exact integer model as the evaluator.** A float64 model follows the engine contract exactly, including rounding
per term, saturation order and leaky with floor. All accuracy numbers on these pages are its numbers, so they are the
camera's numbers. The camera's output on a test picture decodes to the same boxes and scores.[^cam1]

**Scoring the vendor network the same way.** We wrote our own integer reference of the E-M1X network from our reading
of its layer table. It is bit-exact against our decode model, which reproduces the camera's kept bird boxes on all 30
outputs of one camera run.[^cam2] Both networks are then scored on the same pictures with the same decode, so the
comparison is like for like.

**Init from data.** OWN-1 has no normalisation layers. Without them an untrained net shrinks its signal through its 28
conv layers and sits on a long plateau. So before training, each conv's weights and bias are scaled once, layer by
layer, to unit output spread on 32 real pictures. The head layers then start 10 times smaller with zero bias.

**Verified absence.** Public sets label what is present, not what was checked absent. Our database records both. A
training set takes as many verified subject-free pictures as positives. Parts that are not labelled, such as a bird's
eye in COCO, become ignore regions with class -1. So the loss neither rewards nor punishes them. Together with the
larger database, this took false birds on bird-free pictures from 41% to 7%.

**Loss spikes.** Some batches spiked to millions and recovered. Almost all of a spike batch's loss is the head range
penalty, from one picture whose head outputs sit 50 to 555 times past the limit. A linear penalty did not stop it, so
the penalty is a symptom, not the cause. The same pictures are ordinary with the finished weights, and each spike names
a different picture. So the blow-up is a passing training instability. Tests of bf16 autocast against float32 and of
skipping spike steps are running.

**Crops as a second view.** The live mod runs a 320 × 320 crop pass around a found subject. Trained on full frames
only, the model lost head and eye detail on crops. Cropping half the training batches lifted the crop pass from 0.71 to
0.94 body AP on CUB, and cost 0.01 on full frames.

**One net per subject group.** A shared bird, cat and dog net cost 0.04 bird AP. The OM-1 also offers one menu entry
per group. So birds, animals and people each get their own net, swapped in when the menu changes.[^inf1]

## Benchmark

Both networks are scored with integer arithmetic, the same decode and the same suppression (best class, IoU about
0.45). Head and eye boxes on CUB follow rules fitted to the E-M1X network's own boxes, so body is the fairest
row.[^fw1]

| | E-M1X | OWN-1 v1 (CUB only) | OWN-1 v2 (database) |
|---|---:|---:|---:|
| body AP50 / recall at 0.1 false per picture | 0.712 / 0.648 | 0.513 / 0.449 | 0.680 / 0.601 |
| head AP50 | 0.512 | 0.483 | 0.595 |
| eye AP50 | 0.148 | 0.204 | 0.255 |
| bird-free pictures with a false bird, score 0.3 / 0.5 | 42.5% / 23.9% | 41.4% / 25.2% | 6.8% / 2.9% |
| CUB test body AP50 | 0.947 | 0.902 | 0.905 |

*Bird test on 8,000 held-out pictures (4,000 with birds, 4,000 without, Open Images, CUB and COCO).[^fw1]*

| run | result |
|---|---|
| birds, cats and dogs in one net | bird 0.596 (bird-only 0.637), false birds halved, cat 0.355, dog 0.463 |
| birds v3 (loss normalised by batch) | same as v2 |
| birds 1.5× wider (133 million) | eye 0.295 against 0.255, body and head unchanged |
| crop fine-tune (half the batches cropped to 320) | crop pass body 0.714 → 0.940 on CUB, full pass -0.01 |
| per-tap rounding, leaky 1/8 | no measurable change |
| people (COCO val) | body 0.35, head 0.36 |
| animal net (cats and dogs as one body class, as the OM-1 animal entry) | body AP 0.746, false animals in 4.2% of animal-free pictures, on its own test |
| combined bird model (crop fine-tune, leaky 1/8, per-tap rounding) | CUB crop pass body, head and eye 0.942, 0.602 and 0.238 (v2 0.714, 0.395 and 0.146), full frame unchanged |

*Other training runs.[^fw1]*

## Open questions

| item | state |
|---|---|
| loss spikes | one picture per spike batch drives head outputs far past range (50× to 555×). Checking bf16 autocast and update size. |
| body AP above the E-M1X network | 0.03 behind |
| per-group nets | animals trained (body only, no cat or dog head or eye labels yet). People planned. |
| medium and small animals | almost never found |

*Work still open.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in our own code and training runs, 2026-11-24 to 2026-11-27.
[^cam1]: Measured on our E-M5 III using test firmware, 2026-11-25.
[^cam2]: Measured on our E-M5 III using test firmware, 2026-11-24, and checked against our decode model.
[^inf1]: Planned, not yet built.

