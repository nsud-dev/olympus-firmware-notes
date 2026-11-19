# IBM Rhapsody and the OXF framework

*Background for the [guides](README.md) · 2026-11-19.*

Much of the camera's application code was not written by hand in the usual sense. It was drawn as UML diagrams in IBM
Rhapsody and generated as C++. Knowing that explains why large parts of the firmware look so regular: hundreds of small
classes with the same shape, state machines everywhere, and a lot of "Notify…Observer" classes that do almost nothing.

## What Rhapsody is

Rhapsody is a model-driven development tool for embedded and real-time software. It began at I-Logix in the 1990s,
went to Telelogic in 2006 and to IBM in 2008, and is still sold as IBM Engineering Rhapsody. Engineers model the system
in UML or SysML: class diagrams for structure, and **statecharts** (hierarchical state machines with events, guards and
actions) for behaviour. Rhapsody then generates C, C++, Java or Ada from the model. It is common in automotive,
aerospace and consumer electronics, where the same behaviour has to run reliably on small RTOS targets.

(Background from IBM's public documentation, not from the firmware.)

## What OXF is

The generated code doesn't run on its own. It needs a small runtime library, the **Object eXecution Framework (OXF)**,
which supplies:

- **Reactive objects** (`OMReactive`): any class with a statechart. Each one has a current state and handles one event
  at a time, run to completion.
- **Active objects / threads** (`OMThread`): an event queue plus a task that takes events off the queue and dispatches
  them to the reactive objects it owns.
- **Events and timeouts** (`OMEvent`, `OMTimeout`): events are small objects posted to a queue; a timeout is an event
  the framework posts after a delay, which is how "wait 500 ms in this state" is modelled.
- **Containers** (`OMList`, `OMUList`, ...): simple lists and maps used by generated code for associations.
- **An OS adapter**: one layer that maps threads, queues, semaphores and timers onto the real operating system. Porting
  OXF to a new RTOS means writing this layer.

## What we see in the E-M5 III

Read off the E-M5 III 1.7 main program ([OS and framework](../firmware/os-and-framework.md#the-framework-rhapsody-oxf)):

- The OXF headers are compiled in from `base_framework/include/rhapsody/oxf/`, including the OS adapter **`itronos.h`**,
  so OXF runs on top of the camera's μITRON. The runtime sources `omreactive.cpp` and `omthread.cpp` are named in
  strings. [code]
- Olympus configured a fixed pool of reactive objects. The firmware has "too many active" and "underflow" messages for
  it. [code]
- Generated state-entry methods keep Rhapsody's `<state>_entdef` naming, for example
  `CmpPCom_PlayCommonComponent::draw_folder_frames_entdef`. [code]
- The capture components (`CapTak_Take`, `CapThr_ThroughImage`, ...) and the `Cmp*` components are this kind of code.
  `CapThr_ThroughImage` (live view), for example, is a singleton whose behaviour is a state word plus tables of
  {state, handler} pairs. [code]
- The **observer pattern** shows up everywhere: about 300 `*Observer` names, such as
  `CapTak_NotifyTakeComplateObserver`. Each is a tiny class whose only job is to forward one notification ("take
  complete", "AF locked") to whoever subscribed. Most of them are one function long. [code]

## What is not Rhapsody

The lower layers are ordinary hand-written C: the shooting sequencer (`takepic.c` and its 34-state table), recording
(`rec_*.c`), file numbering (`dcf*.c`), the SD driver, and the image-engine drivers. The usual picture is generated C++
for application behaviour ("what should the camera do now?") calling hand-written C for mechanisms ("take this exposure",
"write this file"). [inferred] from module names and code style.

## Why it matters when reading the code

- **Most of a generated class is boilerplate.** Constructors, `getInstance` singletons, factories and observers are
  noise. The behaviour lives in the event handlers and state-entry methods.
- **Control flow goes through queues.** A method that "takes a picture" often only posts an event. The work happens
  later, on another task, when that event is dispatched. Following a call graph alone will lose our notes; you have to
  follow the event.
- **State machines have a recognisable shape.** You'll see a current-state field, a switch or table on it, and
  entry/exit actions. Once you spot one, the rest of the class reads quickly.

How `CapTak_Take::takePicture` hands its event to the C sequencer is still open
(research gaps).
