# C++ shooting layer: technical notes

<!-- house style -->
> **Technical reading.** The detailed version of [C++ shooting layer](cpp-shooting-layer.md), for readers who want the internals.

*Last reviewed 2026-11-27.*

This page covers the generated C++ application code that sits above the C shooting sequencer. It describes the class
tree and its vtables, the shooting component and its "sequence parts", and the capability objects (`CapTak_Take` and
friends). It also traces how a take-picture call reaches the C [sequencer](shooting-sequencer.md). All of it is desk
research, with no camera runs.[^fw1]

Addresses are E-M5 III 1.7 block0 addresses unless the OM-5 II 1.1 is named. The OM-5 II addresses refer to its
expanded block0.

The small numbers after a fact link to [Sources and dates](#sources-and-dates), which say how the fact is known and when.
On the notes site the number's colour shows the evidence: blue = read in the firmware, grey = inferred.

## How classes were recovered

- **Vtables** are runs of code pointers in read-only data. A constructor loads the start address with
    `mov imm32,dN` and stores it at `(this)`.[^fw1]
- The pointer in the object points straight at slot 0. There is no offset-to-top word and no RTTI, and the image has
    no type-info names.[^fw1]
- **Slots point at indirect-call entries.** That is the `movm [...],(sp)` + `add -N,sp` prologue 2 to 6 bytes in front
    of the body. The body is what direct `call` instructions reach, because they save registers themselves.[^fw1]
- **Parents** come from constructor chains. A constructor calls its base constructor first, which stores the base
    vtable. Then it stores its own. For example the `CapTak_Take` constructor calls its base, then runs
    `mov <vtable>,d0; mov d0,(a2)`. Embedded members (observers) are constructed afterwards.[^fw1]
- **Names** come from the assert file-name string (`CapTak_Take.cpp` and so on) that each source file puts in front of
    its read-only data. Method names come from our symbol table.[^fw1]
- The scanner found 4,305 candidate tables on the E-M5 III and 4,510 on the OM-5 II, many of them plain pointer tables.
    **225 vtables (OM-5 II 224) descend from OXF's `OMReactive`**, so they are Rhapsody reactive classes.[^fw1]

## The class tree

The tree below shows the main classes with their slot counts in brackets (E-M5 III).[^fw1]

```
OMReactive (omreactive.cpp, 35 slots)                     Rhapsody OXF
└─ Com_TransitionBase (44)                                 Olympus base: state, transitions, trace
   ├─ Lyb_TransitionBase (48)                              "layer" base
   │  ├─ Lyb_CameraBaseLayerBase (50) ── Cab_CameraBase (53)
   │  │  └─ Lyb_ModeManageLayerBase (50) ── Mod_CategorySwitcher (57) ── ModSht_ShootMode (58), ModPly_PlayMode, ModFnc_FunctionMode
   │  │     └─ Lyb_CategoryManageLayerBase (50) ── Ctg_ComponentSwitcher (57) ── CtgStl_StillImageShooting (59), CtgDis_Display, CtgFnc_Function
   │  │        └─ Lyb_ComponentManageLayerBase (50) ── Cmp_ComponentManagerWithBoot (60)
   │  │           │                                        ├─ (Cmp_ShootingComponentBase, abstract) ── Cmp_StillShootingComponentBase (132)
   │  │           │                                        │                                            └─ CmpSht_ShootingComponent_NEW (132)
   │  │           │                                        ├─ Cmp_PlayerComponentBase (61), CmpFnc_FunctionComponent (60) ...
   │  │           └─ CmpSdw_ShutdownComponent (51)
   │  └─ Lyb_CapabilityManagerLayerBase (48)
   │     ├─ CapTak_Take (84), CapRec_Record (52), CapBuf_BufferManager (51), CapFls_Flash (62),
   │     │  CapMed_MediaManager, CapPow_Power, CapBoo_BootManager, CapHis_Histogram, CapIod_IODevice ...
   │     └─ Cap_CapabilityManagerBase (48) ── CapAef_AEAFCtrl (48), CapMov_MovieRecorderSLR (58) ...
   ├─ Com_ManagersSubTransition (53)                       controllers owned by a component
   │  ├─ CmpShc_ShootingSequence (53) ── CmpShc_ShootingSequenceBase (~200)
   │  ├─ CmpShc_ZoomRequest, CmpCtr_LiveViewZoomController, CmpCtr_RecViewController
   │  ├─ CmpSts_RecordController, CmpSts_AEAFLockController, CmpSts_CombineShootingController, CmpSts_MultiExposure...
   │  └─ Com_HlsMainEventDispatcher, Com_ActiveTransitionManagerBufferd, CmpCst_* (Bluetooth, GPS, media mount)
   ├─ CmpSqp_SequencePartsBase (~2,440) ── 9 or 10 "sequence parts" subclasses (below)
   └─ CapAef_AEAFLock (44)
```
*The C++ class tree on the E-M5 III, slot counts in brackets. Vtable addresses for both bodies are in our class list.*

- The `Lyb_*` chain is strictly linear: **camera → mode → category → component → capability**.[^fw1]
- A mode (shoot, play, function) switches categories. A category (still shooting, display, function) switches
    components. Components use capabilities.[^inf1]
- The naming (`Cab`, `Mod`, `Ctg`, `Cmp`, `Cap`, `Dev`) follows the same layers. The inheritance is read in the code.
    The roles are inferred from the names and the `*Switcher` classes.[^inf1]
- Each layer object has a factory class (`Mod_ShootModeFactory`, `Ctg_StillShootingFactory`,
    `Cmp_ShootingComponentFactory` and so on) with a 35-slot vtable.[^fw1]
- About 300 `*Observer` classes (`CapTak_NotifyTakeComplateObserver`, `CmpShc_ObserverNotifyAFLockDone` and so on)
    are tiny 7 to 8 slot classes outside the `OMReactive` tree. They are embedded as members of the object they report
    for.[^fw1]
- `CapThr_ThroughImage` (live view, [OS and framework](os-and-framework.md#source-file-and-module-names)) is a
    singleton with its own state tables rather than a `Lyb` subclass.[^fw1]

## Which task runs it

The application event loop is the HLS_EVENT task. `appevent::Wait_Event` has one caller, in `OlyHfwEventManager.cpp`,
and reads the app event queue (id 6).[^fw1] See also: [Button press](../guides/button-press.md).

The C++ components react to those app events through `Com_HlsMainEventDispatcher` and the per-state handler matrices
of `CmpSqp_SequencePartsBase` ([shooting sequencer](shooting-sequencer.md#component-level-sequence-state-cmpsqpcmpshc)).
That they all run on the HLS_EVENT task is inferred, because no second our notes with shooting objects was
found.[^inf1]

## The shooting component and its sequence parts

`CmpShc_ShootingSequenceBase` owns the component-level state (`getSeqStateId`, ids 1 STANDBY to `0x13` MOV_END, see the
sequencer page). It also owns one **sequence parts** object at +0xb10, chosen by a sequence id.[^fw1]

`createSequenceParts` picks the part.[^fw1]

- It is called from `initComponents` with 0, and from a virtual "change sequence" method.
- It switches on id 1 to 13 through a table and fetches a singleton with `getInstance`.
- It then hands the part about 40 controller pointers (record, multi-exposure, combine, e-portrait and so on).

| id | E-M5 III 1.7 part (slots overridden) | OM-5 II 1.1 part (slots overridden) |
|---|---|---|
| 1, 4, 5, 6, other | Base (plain shooting) | Base |
| 2 | Otwb, one-touch WB (33) | Otwb (35) |
| 3 | PictBkt, picture bracketing (10) | PictBkt (10) |
| 7 | Panorama (59) | Panorama (59) |
| 8 | Eportrait, e-Portrait (44) | Eportrait (44) |
| 9 | 3D (2) | MultiExposure (93) |
| 10 | MultiExposure (94) | AfFineTune (11) |
| 11 | PhotoSession (67) | ZeroLag, Pro Capture (153) |
| 12 | AfFineTune (11) | **HandheldHighRes (15)** |
| 13 | ZeroLag, Pro Capture (146) | **DigitalNDFilter, Live ND (14)** |

*Sequence parts by id on both bodies, read from each body's part table.[^fw1]*

- Each part is a subclass of `CmpSqp_SequencePartsBase`, with about 2,440 slots (OM-5 II about 2,410).[^fw1]
- Most slots are the event × state handler matrix (`errorHandler<Event>In_<STATE>`, `rcv<Event>In_<STATE>`). So a part
    overrides only the handlers its feature changes. The counts in the table are the slots that differ from the base
    vtable.[^fw1]
- **Live ND and Handheld High Res are thin at this layer**, with 14 and 15 overridden handlers on the OM-5 II.[^fw1]
    Their real work sits in the C sequencer and image pipeline, as on the OM-5
    ([Live ND port layers](live-nd-port-layers.md)).[^inf1]
- The ids are **renumbered between bodies**. A mod that forces a part must use the body's own id.[^fw1]

### Which setting picks the part

`Cmp_StillShootingComponentBase::changeSequence` asks `getSequenceIdAndAttribute` for the current id and the wanted id.
When they differ it calls the change method, which calls `createSequenceParts`. A second caller switches away from
PictBkt (id 3).[^fw1]

The wanted id comes from one function, which tests settings with the setting getter in a fixed order. The first match
wins.[^fw1]

| order | E-M5 III test (setting id, name from the [OM-5 settings map](../bodies/settings-map-om5-technical.md)) | id | OM-5 II test | id |
|---|---|---|---|---|
| 1 | take-function state 3 is 1 (`TraShareTakeStatus::getTakeFuncState`) | 10 MultiExposure | same | 9 |
| 2 | 602 `MODE_FOCUS_BASE` = 1 | 12 AfFineTune | same | 10 |
| 3 | a status function returns 2 or 3 | 2 Otwb | status returns 2, 3 or 4 | 2 |
| 4 | a parts check (vtable +200 with `0x10000200`) is true | 1 Base | (not present) | |
| 5 | 458 `MODE_TAKE_FUNC` = 7 or 8 | 9 3D | (not present) | |
| 6 | 109 `MODE_SCENE_NAVIGATION` = 1 and 24 `MODE_EXPOSE` = 67 | 8 Eportrait | same | 8 |
| 7 | 458 `MODE_TAKE_FUNC` = 1 | 7 Panorama | same | 7 |
| 8 | 404 `MODE_BRACKET_PICT_ONOFF` = 1 | 3 PictBkt | same | 3 |
| 9 | 562 `MODE_PHOTO_SESSION` ≠ 0 | 11 PhotoSession | (not present) | |
| 10 | 1150 `MODE_ZERO_TIME_LAG` = 1 | 13 ZeroLag | 1184 = 1 | 11 |
| 11 | | | 755 `MODE_PIXSHIFT_SR` = 1 and 1708 = 1 | 12 HandheldHighRes |
| 12 | | | 1709 = 1 (755 off) | 13 DigitalNDFilter |
| else | | 1 Base | | 1 |

*Order of the tests that pick the part. Function addresses are in the [address reference](#address-reference).[^fw1]*

- Ids 1184, 1708 and 1709 are OM-5 II setting ids. They are not in the OM-5 map, so their names are open.[^fw1]
- That 1184 is Pro Capture (zero time lag), 1708 the handheld choice of High Res and 1709 Live ND on follows from the
    part they select.[^inf1]
- So a mod can force a part by setting its trigger. But the part then also expects its own controllers and
    menus.[^inf1]

## How a take-picture reaches the C sequencer

This closes a gap in the [Taking a photo](../guides/taking-a-photo.md) guide. It was traced statically on the
E-M5 III.[^fw1]

1. `CapTak_Take::takePicture` and its variants (continuous, auto, dark frame, Live Bulb, WB sample) all call one core,
   with a mode in d0.
2. The core reads settings and logs `[takePic]`. Then it calls the C API in `api_rec.c`, either the take-picture API
   (API id `0x20013`) or a second function for the other path.
3. The take-picture API allocates a 76-byte request block from the exec pool. It fills it with the caller argument,
   the reply queue id (6) and flags. Then it calls the API dispatcher **with message type 11**.
4. The dispatcher takes a slot in the exec pool (255 × 48 bytes). It looks up the type's queue in one table
   (type 11 → queue **`0x60`**) and its handler in another. It writes the message with `OlyQeWrCpu`.
5. Queue `0x60` is the **sequencer's input queue**. The sequencer task binds it to its event flag `0x49` at start. On
   flag bit 1 it drains the queue, then runs the current state's event list (`{u32 event, u32 handler}` pairs in the
   state table).
6. Back in C++, the core allocates a 44-byte event with the OXF allocator (with file and line). The event carries a
   callback and is posted through slot 1 of the object at `CapTak_Take`+0xb2c.

Results come back to the C++ side as app events on queue 6, the reply queue in the request.[^fw1] The reply meanings
are inferred.[^inf1]

### The request inside the sequencer

The sequencer loop reads 16-byte messages from queue `0x60`. **Word +8 is the event id.**[^fw1]

- The event id is matched against the current state's **queue-event list** (state record +12, `{u16 event, u32 handler}`
    pairs, ending at `0xffff`). Internal events (flag bit 0) use the other list at +16.[^fw1]
- The API message is `{+0 reply queue, +4, +8 type, +12 request*}`. So **a take-picture request is queue event
    11**.[^fw1]

Event 11 is handled in three states.[^fw1]

- **RdyTrig2Wait** (5) and RdyFastTrig2Wait (6). The handler keeps the request in RAM and goes to state 7 RdyFcsTake.
- **Standby** (11). The handler stores the request pointer and goes to state 12 StlRdy1.

One function unpacks the message for these handlers.[^fw1]

- It copies the 16-byte message into request+44 and clears request+60 to +69.
- For events 11 and 12 it calls a further function with request+0, the take parameters from `CapTak_Take`.

So the request pointer, which the [sequencer page](shooting-sequencer.md#the-exposure-record) uses for the exposure
record (`*(*(request pointer)+60)`), points at the `api_rec` request block.[^fw1] Standby's entry reads the route byte
from byte 10 of the take-parameter struct it is handed. That this is the struct at request+0 is inferred.[^inf1]

Other events reach the same queue.[^fw1]

- Queue event 18 (RdyTrig2Wait → 7, Standby → burst set-up) is posted by other senders, not by `api_exec`. Type 18
    goes to queue `0x31`.
- Other `api_exec` types also land on queue `0x60`, such as type 6 (API `0x200dc`). Type 12 (7 rec APIs), 13, 25, 30
    and others go to other queues.
- Other C++ to sequencer posts use the same queue, such as event 14. It is posted from an `api_rec` function (API
    `0x2006b`) and from sequencer code.

**OM-5 II: same chain.** `CapTak_Take::takePicture` calls a core, then the `api_rec` take-picture API (API `0x20013`),
which sends message type 11 through the dispatcher.[^fw1]

## OM-5 II comparison

- Same framework, same layer bases, and the same slot counts for every class in our class list except two. The
    sequence parts base drops from 2,481 to 2,408 slots, and the shooting-sequence base changes too.[^fw1]
- 225 reactive classes on the E-M5 III against 224.[^fw1]
- Source files only on the E-M5 III are `CmpSqp_SequenceParts3D`, `CmpSqp_SequencePartsPhotoSession` and
    `CmpSts_ObserverNotifySavePhotoSession`.[^fw1]
- Only on the OM-5 II are `CmpSqp_SequencePartsDigitalNDFilter`, `CmpSqp_SequencePartsHandheldHighRes`,
    `CmpSts_ObserverNotifyHighResPreProgress` and `TraShareStatus`.[^fw1]
- The OM-5 II also drops the assert strings of most `*Factory.cpp` files, but the factory classes are still
    there.[^fw1]
- So on the OM-5 II, Live ND and Handheld High Res are full sequence parts of the shooting component, as the
    E-M5 III's Pro Capture is. On the E-M5 III, High Res tripod and the burst paths live only in the C
    sequencer.[^fw1]

## Open questions

- Names of the OM-5 II setting ids 1184, 1708 and 1709. An OM-5 II settings map would settle them.
- The reply events on queue 6, and who posts queue event 18.
- Roles of the 35 `OMReactive` slots and the 44 `Com_TransitionBase` slots (dispatch, state entry, trace).

## Address reference

E-M5 III 1.7 block0 addresses. OM-5 II 1.1 addresses are in their own column.

| item | E-M5 III | OM-5 II |
|---|---|---|
| `OMReactive` (framework root) vtable | `0x60bbeb48` | `0x60c78794` |
| `Com_TransitionBase` vtable | `0x60bb7b1c` | `0x60c71598` |
| `CapTak_Take` constructor | `0x608c3284` | |
| its base constructor call, own vtable | `call 0x60a7a0be`, `0x60b2be1c` | vtable `0x60be8180` |
| `appevent::Wait_Event`, its caller | `0x602e2f49`, `0x607cac58` | |
| app event queue id (u16, holds 6) | `0x60040f24` | |
| `getSeqStateId` | `0x607c4d23` | |
| `createSequenceParts`, part table | `0x6093ebc8`, `0x60b56d24` | `0x609f78fd`, `0x60c16384` |
| "change sequence" method | `0x6093e118` | |
| `CmpSqp_SequencePartsBase` constructor, vtable | `0x60976080`, `0x60b76224` | vtable `0x60c32a1c` |
| `changeSequence` | `0x609687e1` | |
| `getSequenceIdAndAttribute`, current id | `0x6093de57`, `0x6097aae0` | |
| second caller (away from PictBkt) | `0x6093fb3b` | |
| wanted-id function | `0x6097b7ca` | `0x60a2f08b` |
| setting getter | `0x602e69f9` | |
| `getTakeFuncState` | `0x607c4cba` | `0x608562bb` |
| Otwb status function | `0x607c4d2c` | `0x6085633c` |

*Class tree, task and sequence parts.*

| item | E-M5 III | OM-5 II |
|---|---|---|
| `CapTak_Take::takePicture` | `0x608c4e66` | `0x6096e342` |
| continuous, auto variants | `0x608c4f02`, `0x608c4ea8` | |
| take core | `0x608c52ae` | `0x6096e7a5` |
| `api_rec` take picture (API `0x20013`), other path | `0x60302f93`, `0x6030791e` | `0x6031587c` |
| exec pool alloc, exec pool | `0x602e4302`, `0x6211e7f8` | |
| API dispatcher | `0x602e43f6` | `0x602f2207` |
| type → queue table, type → handler table | `0x604de358`, `0x604de408` | |
| `OlyQeWrCpu` | `0x600514a2` | |
| queue `0x60` id (u16) | `0x60040fd8` | |
| sequencer task, flag binding | `0x602a0f90`, `0x602a0ee6` → `0x600515ca` | |
| queue drain | `0x60227e18` | |
| state table | `0x6044f9e4` | |
| OXF event allocator, callback | `0x60a95b9b`, `0x60302f8e` | |
| sequencer loop, message read | `0x602a10fc`, `0x60227dab` | |
| RdyTrig2Wait event 11 handler, request kept at | `0x602c49ec`, `0x62111bac` | |
| Standby event 11 handler, request pointer | `0x602b255f`, `0x6210fb6c` | |
| message unpacker, take-parameter call | `0x602a14d5`, `0x602b205b` | |
| event 18 handlers: RdyTrig2Wait, Standby | `0x602c3d91`, `0x602b264f` | |
| event 14 poster, `api_rec` caller (API `0x2006b`) | `0x602a1564`, `0x60306202` | |

*The take-picture path.*

## Sources and dates

The small numbers in the text point here. Each note says how a fact is known and when.

[^fw1]: Read in the firmware of the E-M5 III 1.7 and the OM-5 II 1.1, 2026-11-25. Desk research, no camera runs.
[^inf1]: Inferred, 2026-11-25.

