# What the logs contain

This page is generated from `retusche.logging.fields` and
`retusche.logging.records`, and the suite refuses a committed copy that differs
from what the declaration produces. Edit the declaration, not this file.

It is written to be copied into a deployment's own record of processing. What
it describes is the log this service produces. Where those lines are then sent,
how long they are kept and who reads them are the operator's decisions and are
not visible from here.

## What a line is

One JSON object per line, with sorted keys. Two keys are always present:

- `event`, the name of what happened, as a dotted lower-case token such as
  `job.state-changed`
- `level`, one of the values in the table below

Everything else is a declared field from the tables further down, and there is
no message. A log line is not a sentence with values pushed into it, which is
the arrangement by which a filename, a prompt or a caller's own text arrives in
a log without anyone deciding it should. `retusche.logging.records.record`
refuses an event name that is not that shape and refuses a field the
declaration does not carry, so a line carrying something else cannot be built
rather than being unlikely.

## Levels

The level decides whether a line is written. It does not decide what a line may
carry: the field check happens when the line is built, before any level is
compared, so there is no setting at which the service starts logging picture
content. Raising the level shows more lines of the kinds below, and never
another kind.

The level is the `log_level` setting, in `docs/configuration.md`.

| Level | What it carries |
| --- | --- |
| `debug` | Detail an operator turns on while working out what happened. |
| `info` | The service doing what it is for. |
| `warning` | Something an operator should look at before it becomes a failure. |
| `error` | Work that did not happen, or a component that has stopped. |

## The fields

Grouped by category. The categories are the rule and are closed: a field
belongs to one of them or it is not logged. The fields are what the service
produces today, and the list grows with it.

### identifier

A name this service or its caller assigned. Never a name a person chose for a file.

- `job_id`. Which job a line is about. It is the only thing that ties a refusal, a state change and an ending together, so a line without it describes an event nobody can follow up. Value: the identifier `retusche.queue.store` holds a job under.
- `engine_id`. Which engine a line is about, as the engine names itself in `retusche_contracts.engine.Capabilities`. Value: the identifier an engine declares in its capabilities.

### state

Where something is, drawn from a declared enumeration.

- `job_state`. Where the job is. Drawn from the state table rather than written, so a log reader and the store cannot disagree about what the states are. Value: a value of `retusche.queue.states.JobState`.
- `previous_job_state`. Where the job was before the move this line records. A state change is two states, and a log carrying only the new one cannot answer whether a move was the legal one. Value: a value of `retusche.queue.states.JobState`.
- `priority`. Which kind of work the job is. It decides the order, so a line about a long wait is not readable without it. Value: a value of `retusche.queue.ordering.Priority`.
- `operation`. What was asked for. An operation is a declared set of three, not a description of the edit. Value: a value of `retusche_contracts.engine.Operation`.

### duration

How long something took, in milliseconds.

No field is declared under this category yet, because nothing in this tree produces one. A field declared before there is a value for it is a name a reader would trust with nothing behind it.

### size

How much of something there is, as a whole number.

- `queue_position`. How far back the job sits in the order in force. Produced by `retusche.queue.ordering.position_of`. Value: jobs considered ahead of this one.
- `queue_depth`. How many jobs are waiting in all. The number an operator watches to see pressure before a caller reports it. Value: jobs waiting, this one included.
- `image_width_pixels`. How wide the image was. A size, and deliberately not the image: the two numbers are what the device memory estimate is derived from, and they say nothing about what is in the picture. Value: pixels.
- `image_height_pixels`. How tall the image was. The other half of the shape. Value: pixels.
- `device_memory_estimate_bytes`. What the job was expected to need, as `retusche_contracts.engine.DeviceMemoryEstimate` reported it. Value: bytes of device memory.
- `device_memory_budget_bytes`. The ceiling the estimate was compared against. A refusal that names one number and not the other cannot be acted on. Value: bytes of device memory.

### model

Which model, by its registry identifier.

- `model_id`. Which weights were involved. It is what makes a result explainable later, and it is a registry key rather than a path on the operator's disk. Value: the identifier a `models/registry/` entry is declared under.

### error-reason

Why something ended badly, drawn from a declared enumeration rather than from an exception's message.

- `terminal_reason`. Why a job ended. The enumeration separates a refusal from a breakage and a cancellation from a shutdown, which is the distinction an operator reading a list of endings needs and the one a message would blur. Value: a value of `retusche.queue.states.TerminalReason`.

## What is deliberately not logged

None of the following has a field, at any level, in any line. What refuses them
is that the field list above is closed and is checked when a line is built, not
a rule that consults this list.

The image, in whole or in part. A thumbnail in a log is the photograph in the log. There is no size at which an image becomes an operational record.

The mask. A mask says which part of the picture somebody wanted gone. On its own it describes the subject's outline, and beside the image size it locates them.

The prompt. A prompt is written by a person about a specific photograph and is frequently about who is in it. `retusche.queue` records it against the job so a result can be explained, under the retention the job record has; the log has a different retention and a different audience.

Paths and names inside the operator's photo library. A library file name is usually a person and a date. The identifiers above answer every question a path would, and they answer it without carrying a name nobody chose to publish.

Location, capture time and the rest of the image metadata. Where and when a photograph was taken is the field that turns an operational log into a movement record. Nothing in this service needs it to describe its own work.

The operator's credentials, in any rendering. A value declared as a secret is handed over as `retusche.config.secret.Secret`, which renders as `<redacted>` wherever it is printed. That is the defence; keeping the field out of this list as well is the second one.

## What this page does not establish

That every part of this service logs through the declaration above. Nothing in
this tree logs at all yet: the module and its refusals exist, and the first log
site arrives with the component that has something to say. A check that refuses
a logging call made outside this module is issue #80, and until it lands, what
stands behind the claim is review.

That the lines are kept safely once they leave this process. A log written to a
file an operator ships elsewhere is subject to whatever that destination does,
and nothing here reaches it.

That an operator's own duties are discharged. This page says what the service
produces. Which of it is personal data in a given deployment, on what basis it
is processed, and for how long it is kept are decisions the operator makes.
`docs/legal/data-protection.md` is where the boundary between the two is drawn.
