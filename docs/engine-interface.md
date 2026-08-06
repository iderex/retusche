# The engine interface

`retusche_contracts.engine` declares the one interface every engine is reached
through. This note carries the reasoning that does not belong in a docstring.
The declarations themselves are the authority for what the interface is; nothing
here restates them.

## Why the interface exists before any engine

An interface written after the first implementation is a description of that
implementation. The second engine then arrives and either fits the accident of
how the first one worked or forces a change to everything already built against
it. Writing it first costs one round of being wrong on paper, which is the
cheapest place to be wrong.

The engine decision in #13 does not change this. Whether an engine runs models
in this project's own worker or adapts an external application, it is reached
the same way, so the interface is built in either direction.

## Why a memory estimate is required before admission

The alternative is to admit the job, start it, and recover from an
out-of-memory failure when it happens. That is the approach this interface
refuses, for three reasons.

The device is shared. This project is built to run beside a photo library on
hardware an operator already owns, so the graphics card usually has a desktop
session, a transcoder or another service on it. An allocation failure is a
property of the device, not of the process that asked last. Driving the card to
exhaustion to discover a limit can take down the thing sharing it, and that
process gets no explanation. Refusing beforehand keeps the consequence inside
the job that caused it.

Recovery is not reliable at the point where it is needed. Freeing device memory
after a failed allocation means unloading a model and, on some runtimes,
tearing down the context; what is recoverable depends on the runtime, the
driver and where in the pipeline the allocation failed. A design that depends
on recovery working has its correctness resting on the least predictable moment
in the stack. #31 owns what happens when it fails anyway, because it will.

The queue has to answer before it commits. Admission control, the memory budget
and the single lane on the device are all decisions taken while the job is still
waiting: #27, #30 and #34. A decision taken then can only rest on something
answerable then. That is why `estimate_device_memory` takes a `JobDescription`
rather than an `EditRequest`, answers without loading weights, and answers
without touching the device.

The estimate is an upper bound the engine is willing to be held to, and it
carries `is_measured` so a caller can tell a measurement from a formula over the
job's shape. Neither is refused. Being told which one you have is the point.

## Why images cross as bytes

An array or image type in the contract would put a numeric runtime into every
process that imports the contract, including the one that listens on a socket.
`ImageBuffer` and `MaskBuffer` carry raw bytes with the shape stated alongside,
so the contract imports the standard library and nothing else.

The cost is real and is not hidden: both layers convert at their own edge, and
nothing in the type system prevents a buffer whose `data` length disagrees with
its `width`, `height` and `channels`. That check belongs to whoever constructs
the buffer. #46 owns what a mask is allowed to be, and #51 owns the decoding at
the network edge.

## What is not settled here

The failure types say what a caller can distinguish. They do not say what the
queue does with each one: retry, refuse, or fail the job. That is #26 and #31.

Cancellation granularity is a step boundary, with the whole-run worst case
declared per engine in `Capabilities.step_count_is_one`. What the API promises a
caller about cancellation latency is #29, and it cannot promise more than the
engine it is holding.

Nothing here has been measured against a real engine, because no engine exists.
Every number this interface carries is a shape for a number, not a number.
