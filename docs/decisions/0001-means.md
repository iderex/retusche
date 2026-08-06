# 0001. The means: language, runtime and toolchain

Python for both layers, one toolchain, with the engine running in its own
operating-system process rather than in its own language.

Two layers are involved and they do not have to share a language. The heavy
runtime is the engine worker, which loads model artefacts and runs them. The
orchestration layer is the HTTP surface, the job model, model management and the
photo-library client, and it is the process that listens on a socket.

## What each layer is made of

Both layers are Python, on one interpreter series, built and locked by one tool.

The interpreter is pinned to a single minor series rather than to a floor, in
the project file and in the lock file that is resolved from it:

    git grep -n 'requires-python' -- pyproject.toml uv.lock
    pyproject.toml:12:requires-python = "==3.14.*"
    uv.lock:3:requires-python = "==3.14.*"

A floor lets two machines resolve the same lock file against different
interpreters and get different wheels, which is the thing the lock exists to
prevent.

The environment and the lock come from uv, which is also what the pull-request
job installs before it runs anything:

    git grep -n 'astral-sh/setup-uv' -- .github/workflows/
    .github/workflows/pull-request.yml:41:        uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
    .github/workflows/zizmor.yml:56:        uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0

The distribution is built by hatchling, declared as the build backend:

    git grep -n 'build-backend' -- pyproject.toml
    pyproject.toml:38:build-backend = "hatchling.build"

The type gate is mypy, pinned to an exact version rather than a range, because a
type checker that moves under a range decides different things about unchanged
code on different days:

    git grep -n 'mypy==' -- pyproject.toml
    pyproject.toml:30:dev = ["mypy==2.3.0"]

The two dependency sets are declared apart, as the `orchestrator` and `worker`
extras, so that a package added for the engine never becomes reachable from the
process that listens on a socket by having been installed for something else.
Both sets are empty today.

## Can the means carry a property a machine can refuse

Partly today, and the gap is named rather than glossed.

A refusable property exists in the tree already. The type gate runs over `src`
in strict mode and the pull-request job refuses a suppression that names no
reason, so the boundary between a considered suppression and one added to turn a
build green is decided by a check and not by a reviewer's patience.

A proof that runs does not exist yet. There is no test runner in the tree, no
test directory and no coverage measurement:

    git ls-files -- 'tests/**' | wc -l
    0

Issue #5 builds the harness and the floor. Issue #7 builds the import-boundary
test, and until it lands the boundary that pays for a dynamically typed network
surface is a sentence in a document, which refuses nothing. Both are open, and
this record does not claim what they will deliver.

A claim citing the command behind it is a property of how things are written
here rather than of the language, and Python does not obstruct it. Every fact in
this record carries the command that produced it.

## Is anything outside this repository forcing it

For the worker layer, yes. The editing model families ship as artefacts that the
maintained loaders read, and those loaders are Python:

    gh api repos/huggingface/diffusers --jq '{language, license: .license.spdx_id}'
    {"language":"Python","license":"Apache-2.0"}
    gh api repos/onnx/onnx --jq '{language, license: .license.spdx_id}'
    {"language":"Python","license":"Apache-2.0"}

For the orchestration layer, no. Nothing outside this repository requires it to
be Python, and that is the half this record actually decides. It is held to the
smallest surface the decision allows: the force applies to the worker package,
and the orchestration layer takes the same language because sharing one costs
less here than the alternative below, not because it had to.

## Does it add a language, a runtime or a dependency the tree does not carry

It adds none. The tree is one language today:

    gh api repos/iderex/retusche/languages
    {"Python":12369}

The cost this choice does carry is a network-facing process in a dynamically
typed language, and it is not paid by saying so. It is paid by strict typing
from the first module rather than switched on later, by a lint gate (#3), by a
test floor (#5), and by the import boundary (#7) that keeps a deep-learning
framework out of the process holding the socket.

## Is the result testable by the suite that will exist

Yes, and by one suite rather than two. One language means one runner, one
coverage report and one dependency-review surface. The fake engine (#15) is
written in the same language as the real ones and reached through the same
contract package, so covering the orchestration layer with the heavy runtime
stubbed (#95) needs no parallel apparatus.

The exception is deliberate and stays outside the unit suite: a test that needs
a real device is not a unit test. It belongs to the hardware harness (#85) and
is skipped by name rather than by accident (#84).

## The alternative that was rejected

A compiled orchestrator, Go or Rust, driving a Python worker over a wire
contract.

It buys a smaller surface reachable from the socket, a static type system that
holds at run time rather than only at check time, and a single binary for the
operator to run.

It costs a second toolchain, a second suite and a second dependency-review
surface. It costs a wire format that has to be designed and versioned before a
single feature exists, at the moment when least is known about what crosses it.
And it costs the fake engine its cheapness: a fake that has to satisfy a wire
contract in another language is a second implementation rather than a class in
the same suite.

What would reverse it: the API being meant to face an untrusted network rather
than a host-local integration, or the import boundary in #7 turning out not to
be holdable, which would remove the answer this record gives to the cost it
names.

## What was not evaluated

No performance comparison was run between the two options, and nothing above
rests on one. Throughput, latency and memory behaviour of a compiled
orchestrator against this one are not evaluated on this route. The argument is
about dependency surface, toolchain count and testability, and it should be read
as such.

## How the later records are named

`docs/decisions/NNNN-short-name.md`. Four digits, zero padded, allocated in
ascending order, followed by a short hyphenated name. The number belongs to the
record and never moves once the record has landed; a decision that is later
overturned is superseded by a new record that names the old one rather than
edited into agreement with the outcome.
