# Repository layout

This is the map a reader places a change on before opening a module. It
describes the shape the plan builds towards. Where a part of that shape is not
in the tree yet, this document says so rather than describing it in the present
tense; the issue that builds it is named instead.

What exists today is the package skeleton and six things inside it: the engine
interface, in `retusche_contracts`; one implementation of that interface, in
`retusche.testing`, which reaches no device; the job model, in `retusche.queue`,
which is the states a job moves through and a durable store for them; the model
registry's shape, in `retusche.models`, which is what a model entry declares and
what an incomplete one is refused for; the mask, in `retusche.masking`, which is
what a caller may send and where a shape's edge lands; and the configuration
surface, in `retusche.config`, which is every setting declared in one place and
a load that refuses the whole of a wrong one. The tree holds no HTTP surface, no
admission control, no lane, no result store, no download path, and no engine
that reaches a model. `models/registry/` holds no model, for a reason that
directory's own README states, and `retusche.config` declares two settings for a
reason its own module says.

## The packages

**`retusche`** is the orchestration layer. It is the process that listens on a
socket. It holds the HTTP surface, the job model, model management, the mask
rules a request is judged against, the configuration surface, and the
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

This is the plan, not a description of running code. Two components below are in
the tree, the mask rules and the job store, and each is marked where it appears;
nothing else is, and each of those is named with the issue that builds it.

A caller sends an image reference and a mask to the editing endpoint (#47, #48,
#49). The orchestration layer decodes and validates the request, refusing a mask
that is not one, which is `retusche.masking` and is in the tree, and an image
whose format, size or decoding is outside what is accepted (#51). It records a
job in the durable job store, which is `retusche.queue` and is in the tree, and
answers with the job identifier; the caller polls or is notified (#52).

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

## The other two directions

The boundary above is one of three dependency rules this document states. The
other two are that the worker does not import the orchestrator and that the
contract imports neither of its users. Both were sentences nothing refused, on
packages that already exist, while the section above pointed at a test that
passes them: the walk permits every socket-safe root to reach every other, and it
never seeds the worker at all. So a contract module recording the version it was
built against, or an engine reaching for the test double as a fallback, went
through the formatter, the linter, the type checker and the suite.

`tests/conformance/` holds those two now, off
`[tool.retusche.layer-imports]` in `pyproject.toml`, and it refuses a package
under `src/` that no rule judges, so the next package to arrive is judged rather
than assumed. Which sets are declared, and what the walk can and cannot see, are
in that directory's own modules and in the project file rather than repeated
here. `tests/conformance/test_the_layer_rules_bite.py` is where each refusal is
shown to happen against a tree built to break exactly that rule.

Two rules #83 asks for are still absent, and neither is held by anything above.
The integration package not being imported by the queue is a direction inside
`retusche`, and these rules judge roots, so holding it needs an order declared
within one package and nothing reads one. And every configuration setting
appearing in a generated reference now has a surface to be a rule about:
`retusche.config` declares the settings and `tests/test_configuration.py`
refuses a committed reference page that differs from what the declaration
produces. That is a test beside the package rather than a conformance rule, and
whether it belongs among these is #83's to decide.

## The checks

This document does not list them. A list here drifts against the workflows it
describes, and the drift is invisible until somebody trusts the list.

    gh pr checks <number>

prints what a change actually has to pass. `CONTRIBUTING.md` says which of them
has a local equivalent.
