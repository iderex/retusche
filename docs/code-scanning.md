# Code scanning

`.github/workflows/code-scanning.yml` runs CodeQL over the Python in this
repository on every pull request and on every push to the default branch. This
file says what the gate refuses, what it cannot see, and where a finding is
read.

## Why a second analyser at all

The lint gate already refuses a long list of unsafe calls: `select` in
`pyproject.toml` carries ruff's bandit family, which is what refuses `eval`,
`pickle.loads`, `subprocess` with a shell, a missing certificate check and the
rest of that catalogue. That family matches a call by its name. It cannot
follow a value, so it says nothing about a path assembled from something the
process was given, a regular expression that matches more hosts than its author
meant, or a string that reaches a sink three functions away from where it
arrived.

This project is going to decode image files submitted by strangers and hold a
credential for somebody's photo library. Following the value is the question
worth asking there, and it is the question CodeQL answers.

## What counts as actionable

Any result whose CodeQL rule carries the `security` tag, at any severity.

That is a stronger rule than a severity threshold and it was chosen because the
tree can carry it. There is no backlog of accepted findings here to grandfather
in, so the gate holds the count at zero rather than at a number somebody picked.
A threshold would also have to be defended: the boundary between a 6.9 and a
7.0 is not a boundary anyone in this repository decided.

What retires that choice: the first result that is genuinely not worth fixing.
At that point the honest repair is a severity threshold written down here with
the run that produced the false positive, or a `query-filters` entry naming the
rule and the reason. Dismissing it in the code-scanning tab and leaving this
paragraph as it stands would be neither.

A result whose rule metadata cannot be resolved in the SARIF is treated as
actionable as well. Its tags cannot be read, so it cannot be shown to be
harmless, and a gate that cannot judge fails rather than passes. The same holds
for a missing SARIF, one that does not parse, and one that carries no analysis
run.

## Where the verdict is made

`.github/scripts/code_scanning_gate.py`, called by the last step of the
workflow with the path to the SARIF the analysis wrote. It exits zero when
nothing is actionable and non-zero otherwise, and it prints one line per
actionable result: class, rule, security severity, location, message.

It is a module rather than a shell pipeline because it is the part that has to
be right, and because it takes a file and prints a verdict, so it runs against
a fixture on a workstation exactly as it runs on a runner. That is the only way
the refusing path of this gate can be watched without waiting for a real
finding to appear in real code.

Two limits of that arrangement, both worth stating rather than discovering.
mypy's scope is `src`, declared in `pyproject.toml`, so this module is linted
and formatted by the same gate as everything else and is not type-checked by
it. And the fixtures it has been run against are fixtures: they prove what the
module does with a SARIF, and they say nothing about whether CodeQL writes the
SARIF anyone expects.

## Where a finding is read

The job uploads its SARIF to code scanning under the category
`/language:python`, so a finding appears in the repository's security tab with
its rule, its location and its data-flow path, and stays there until it is
fixed or dismissed. The run log carries the same list in one line per result,
which is what the gate step prints when it refuses.

The upload is skipped where the token cannot write security events, which is a
pull request from a fork and a pull request opened by Dependabot. The gate step
still runs there and still refuses, so the check is never weaker on those pull
requests than on any other. It is the visibility that is weaker, not the
verdict.

## The query set

`security-extended` rather than the default suite. It adds the lower precision
security queries, which is the right trade while the tree is small enough that
a false positive costs one dismissal.

The local threat model is included alongside the default remote one. Under the
remote model the taint sources are the request objects of a web framework, and
this project has no web framework and no HTTP surface yet. An analysis with no
sources is green because it could not see anything, not because there was
nothing to see, and those two states are worth keeping apart. Command line
arguments, environment variables and standard input are what this code reads
today, and the worker process will read its configuration the same way.

## What this gate does not see

It analyses Python. It does not analyse the workflow files, which are audited
by zizmor in `.github/workflows/zizmor.yml` under the check name
`Audit workflows (zizmor)`, and it does not analyse the dependency set, which
is `dependency-review`'s subject.

It does not know what the model weights do. Weights are data this project
downloads and hands to a runtime, and no static analyser here reads them.

It follows values through code it can see. A value crossing a process boundary
into the engine worker, which is the boundary issue #7 builds, leaves what
CodeQL can follow, so a finding is not expected to span the two layers.

A green run says no query in the set matched, and the set is a set of known
mistake shapes. It is not a statement that the code is safe, and no run of this
gate has ever been asked whether it is.

## The check name

`Code scanning (CodeQL)`, declared as the job's `name` in
`.github/workflows/code-scanning.yml`.

A ruleset matches a required status check by that literal string. Renaming the
job publishes a different name, the ruleset goes on waiting for the old one, and
nothing reports that the gate has stopped standing in front of anything. So the
name is changed in this file, in the workflow and in the ruleset together, or
not at all. Whether it becomes a merge condition is `docs/quality-parity.md`'s
subject and is not decided here.
