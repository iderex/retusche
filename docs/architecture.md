# Repository layout

This is the map a reader places a change on before opening a module. It
describes the shape the plan builds towards. Where a part of that shape is not
in the tree yet, this document says so rather than describing it in the present
tense; the issue that builds it is named instead.

What exists today is the package skeleton and two things inside it: three
packages under `src/`, each with a docstring and a `py.typed` marker and no
runtime dependency in either layer; the engine interface, in
`retusche_contracts`; and one implementation of that interface, in
`retusche.testing`, which reaches no device. The tree holds no HTTP surface, no
queue, no store, and no engine that reaches a model.

## The packages

**`retusche`** is the orchestration layer. It is the process that listens on a
socket. It holds the HTTP surface, the job model, model management and the
photo-library client.

It may depend on `retusche_contracts` and on nothing heavier. It may not import
`retusche_worker`, a machine-learning runtime, or a model library. Two reasons,
and the first is the one that decided it: a crash or an out-of-memory kill
inside a native tensor library takes the whole process down, and the queue has
to survive that. The second is that the dependency surface reachable from a
socket should be as small as the work allows, which it is not if it
transitively pulls in a deep-learning framework.

`retusche.testing` is a subpackage of it, and it holds one implementation of the
engine contract that reaches no device: the thing the suite runs an engine's
part against when there is no engine to run. It is built into the tree and kept
out of the wheel by `[tool.hatch.build.targets.wheel] exclude` in the project
file, because an engine an operator can select that returns derived content
rather than an edited photograph is a failure nothing reports. #15 is where it
is argued.

**`retusche_worker`** is the engine worker. It holds the engine implementations
and it is the only package permitted a machine-learning runtime. It runs in its
own operating-system process, supervised by the orchestration layer, so that it
can be killed and restarted without taking the queue with it.

It may depend on `retusche_contracts`. It may not import `retusche`: a worker
that reaches back into the orchestrator turns two processes into one program
that happens to be split across a pipe.

**`retusche_contracts`** holds the types the two layers exchange and is owned by
neither. It may import neither of the other two. A contract that reaches back
into one of its users has stopped being a contract.

The two dependency sets are declared separately, as the `orchestrator` and
`worker` extras in `pyproject.toml`. Both are empty today. Declaring them apart
before either has an entry is what gives the boundary something to be checked
against later, rather than a convention to be inferred from what happens to be
installed.

## The path a single edit takes

This is the plan, not a description of running code. None of the components
below exists in the tree yet; each is named with the issue that builds it.

A caller sends an image reference and a mask to the editing endpoint (#47, #48,
#49). The orchestration layer decodes and validates the request, refusing a
mask that is not one (#46) and an image whose format, size or decoding is
outside what is accepted (#51). It records a job in the durable job store and
answers with the job identifier (#26); the caller polls or is notified (#52).

Admission control decides when that job reaches the device (#27, #30). One lane
runs at a time, and the memory budget is checked before admission rather than
discovered during it.

The orchestration layer sends the job over the process boundary to the worker,
which loads or reuses the model (#32), runs the engine (#18, #19, #20) and
returns the result over the same boundary. Nothing about the model or the
runtime crosses back except the result and what the contract declares.

The orchestration layer writes the result to the result store, marks the
generated image (#70), records what was edited in the audit trail (#67) and
holds the result for the stated retention period before removing it (#36).

The path crosses the boundary exactly once, in each direction, and the crossing
is the contract package.

## The import boundary

The boundary is the rule that `retusche` must not reach a machine-learning
runtime, a model library, or `retusche_worker`, by any import chain rather than
only directly.

`tests/test_import_boundary.py` holds it, and it runs in the default suite.

The paragraph that stood here said there was no such test, named #7 as where one
would be built, and said of itself that it would be replaced by a pointer to
that test when it existed rather than amended to sound better. The test landed
and the paragraph did not move. So this document went on telling a reader the
boundary was a sentence nothing refused, while a check in the same tree was
refusing violations of it, and the two disagreed for as long as nobody read them
together.

What the walk covers, what it cannot see, and which module roots it refuses are
in that file's own docstring and in `[tool.retusche.import-boundary]` in
`pyproject.toml`. They are not repeated here. A restatement drifts against the
thing it describes, and this section is what the drift looks like once it has
happened.

## The checks

This document does not list them. A list here drifts against the workflows it
describes, and the drift is invisible until somebody trusts the list.

    gh pr checks <number>

prints what a change actually has to pass. `CONTRIBUTING.md` says which of them
has a local equivalent.
