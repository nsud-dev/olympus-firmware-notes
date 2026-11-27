# Rhapsody and OXF

<!-- house style -->

*Background for the [guides](README.md).*

## Key points

- Much of the camera's application code was drawn as UML diagrams in IBM Rhapsody and generated as C++.
- The generated code runs on a small runtime library, the Object eXecution Framework (OXF), which here sits on the
  camera's μITRON kernel.
- The lower layers, such as the shooting sequencer, recording and the SD driver, are ordinary hand-written C.
- In generated code the behaviour lives in event handlers and state-entry methods, and work moves through event queues.

Much of the camera's application code was not written by hand in the usual sense. It was drawn as UML diagrams in IBM
Rhapsody and generated as C++. Knowing that explains why large parts of the firmware look so regular. There are
hundreds of small classes with the same shape, state machines everywhere, and a lot of "Notify…Observer" classes that
do almost nothing.

## Rhapsody

Rhapsody is a model-driven development tool for embedded and real-time software. It began at I-Logix in the 1990s,
went to Telelogic in 2006 and to IBM in 2008, and is still sold as IBM Engineering Rhapsody. Engineers model the system
in UML or SysML. Class diagrams give the structure, and **statecharts** (hierarchical state machines with events,
guards and actions) give the behaviour. Rhapsody then generates C, C++, Java or Ada from the model. It is common in
automotive, aerospace and consumer electronics, where the same behaviour has to run reliably on small RTOS targets.

This background comes from IBM's public documentation, not from the firmware.

## OXF

The generated code doesn't run on its own. It needs a small runtime library, the **Object eXecution Framework (OXF)**,
which supplies the following parts.

- **Reactive objects** (`OMReactive`) are the classes with a statechart. Each one has a current state and handles one
  event at a time, run to completion.
- **Active objects** or threads (`OMThread`) are an event queue plus a task. The task takes events off the queue and
  dispatches them to the reactive objects it owns.
- **Events and timeouts** (`OMEvent`, `OMTimeout`) are small objects posted to a queue. A timeout is an event the
  framework posts after a delay, which is how "wait 500 ms in this state" is modelled.
- **Containers** (`OMList`, `OMUList`, ...) are simple lists and maps used by generated code for associations.
- **An OS adapter** is one layer that maps threads, queues, semaphores and timers onto the real operating system.
  Porting OXF to a new RTOS means writing this layer.

## In the E-M5 III

These points are read off the E-M5 III 1.7 main program.

- The OXF headers are compiled in from `base_framework/include/rhapsody/oxf/`, including the OS adapter **`itronos.h`**,
  so OXF runs on top of the camera's μITRON. The runtime sources `omreactive.cpp` and `omthread.cpp` are named in
  strings.
- Olympus configured a fixed pool of reactive objects. The firmware has "too many active" and "underflow" messages for
  it.
- Generated state-entry methods keep Rhapsody's `<state>_entdef` naming, for example
  `CmpPCom_PlayCommonComponent::draw_folder_frames_entdef`.
- The capture components (`CapTak_Take`, `CapThr_ThroughImage`, ...) and the `Cmp*` components are this kind of code.
  `CapThr_ThroughImage` (live view), for example, is a singleton whose behaviour is a state word plus tables of
  {state, handler} pairs.
- The **observer pattern** shows up everywhere, with about 300 `*Observer` names such as
  `CapTak_NotifyTakeComplateObserver`. Each is a tiny class whose only job is to forward one notification ("take
  complete", "AF locked") to whoever subscribed. Most of them are one function long.

<details><summary>Where in the firmware</summary>

| what | where | known from |
|---|---|---|
| OXF headers and OS adapter | `base_framework/include/rhapsody/oxf/itronos.h` | [code] |
| runtime sources | `omreactive.cpp`, `omthread.cpp`, named in strings | [code] |
| reactive-object pool messages | "too many active", "underflow" | [code] |
| `<state>_entdef` naming | e.g. `CmpPCom_PlayCommonComponent::draw_folder_frames_entdef` | [code] |
| live-view singleton, state word and handler tables | `CapThr_ThroughImage` | [code] |
| about 300 `*Observer` names | e.g. `CapTak_NotifyTakeComplateObserver` | [code] |

*Evidence for the OXF findings above.*

Sources: [OS and framework](../firmware/os-and-framework.md#the-framework-rhapsody-oxf).
</details>

## Code outside Rhapsody

The lower layers are ordinary hand-written C. They include the shooting sequencer (`takepic.c` and its 34-state
table), recording (`rec_*.c`), file numbering (`dcf*.c`), the SD driver, and the image-engine drivers. The usual
picture is generated C++ for application behaviour ("what should the camera do now?") calling hand-written C for
mechanisms ("take this exposure", "write this file"). That picture is inferred from module names and code style.

## Reading the code

- **Most of a generated class is boilerplate.** Constructors, `getInstance` singletons, factories and observers are
  noise. The behaviour lives in the event handlers and state-entry methods.
- **Control flow goes through queues.** A method that "takes a picture" often only posts an event. The work happens
  later, on another task, when that event is dispatched. Following a call graph alone will lose our notes. You have to
  follow the event.
- **State machines have a recognisable shape.** You'll see a current-state field, a switch or table on it, and
  entry/exit actions. Once you spot one, the rest of the class reads quickly.

`CapTak_Take::takePicture` hands a shot to the C sequencer by calling the C recording interface (`api_rec.c`). That
interface writes a message into the sequencer task's own queue.

See also: [C++ shooting layer](../firmware/cpp-shooting-layer.md), with the class tree and this route.

## Further reading

- [OS and framework](../firmware/os-and-framework.md#the-framework-rhapsody-oxf), the reference notes on OXF in this
  firmware.
- [Operating system](operating-system.md), the guide to the μITRON kernel that OXF runs on.
- [C++ shooting layer](../firmware/cpp-shooting-layer.md), the generated classes that take a picture.
