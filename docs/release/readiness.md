# Release readiness

The last thing between a build and an operator is a list somebody walks. This
is that list. It is written from the plan rather than from what a release
happens to have handy, so a release cannot quietly skip the parts no workflow
does for it.

Nothing refuses a release that never opened this file. No check reads it, no
ruleset requires it, and the release route in #89 is not built yet. It is an
administrative control, and saying so here is better than leaving a reader to
discover it when a release goes out unwalked.

## How an item is decided

Every item below carries two things: what it asserts, and the route that
decides it. A route is either a command, whose output is pasted into the walk,
or a reading of a named document, whose reader is recorded. An item settled by
opinion is an item that will be settled differently next time, so no item is
written that way.

Three outcomes are allowed for an item, and only three.

Done, with the command output or the name of the person who read the document.

Not done, with the reason. This is a legitimate outcome and it is what an item
whose route does not exist yet gets. Several items below name the issue that
delivers their route, and until that issue lands the honest entry is a reason
and not a tick.

Not applicable, with the reason it does not apply to this release. An upgrade
test has nothing to run against before the first release, and that is the shape
this outcome is for.

Dropping an item from the walk is none of the three. An item that stopped
mattering is removed from this file in a change with a reason in its body, not
omitted from one walk and then from the next.

## Where a walk is recorded

A completed walk is committed as `docs/release/walked/<name>.md` on the branch
the release is cut from, and it names the commit it walked. Recording it in the
tree rather than in a pull-request thread is deliberate: the question a walk
answers later is what was true at a version somebody is still running, and a
thread is not where that is looked up.

`docs/release/walked/not-a-release-2864a7c.md` is a walk of this list against a
commit that is not a release. It exists because a checklist nobody has walked
is a checklist whose items have not been shown to be decidable, and its first
line says what it is so it is not mistaken for a release record.

## The items

### 1. Every gate green on the release commit

Asserts that the release commit is one the published checks passed, rather than
one whose checks were never asked.

Decided by, with the release commit in place of the placeholder:

    gh api "repos/iderex/retusche/commits/<sha>/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort

The output is pasted whole. This file names no check, because a list of names
here drifts against the workflows that publish them, and `docs/quality-parity.md`
is where the names are quoted and where each one's proposed standing is argued.

One trap, measured rather than assumed. A default-branch head and a
pull-request head do not publish the same set: several workflows answer only on
a pull request, and the four names a push produces are not the ten a pull
request does. The walk therefore reads the head of the pull request that became
the release commit, and pastes both listings where the release commit is a merge.

### 2. The hardware harness run on named hardware, with its results recorded

Asserts that the claims only a device can settle, the memory estimate against
the observed peak and the cancellation delay against its stated bound, were
settled on hardware for this release rather than carried over.

Decided by the harness's own command and by the file it writes, both of which
#85 defines. Until #85 lands there is no harness and no command, and the entry
is not done with that reason.

The walk records which hardware it ran on. A measurement without the machine it
came from is not a measurement anyone can compare against next time.

### 3. The library round-trip harness run against a stated library version

Asserts that a full edit against a real photo library instance completed, and
that the original's bytes came back unchanged.

Decided by the harness's own command, which #59 defines, and by the library
version that harness records. Until #59 lands the entry is not done with that
reason.

A green default test run does not answer this item. The default suite drives
recorded fixtures, which proves the client agrees with a specification and not
that it works against an instance.

### 4. The compose example started from scratch, and one edit completed

Asserts that the arrangement an operator is handed actually starts, on a
machine holding none of its state, and that a photograph goes in and a result
comes out.

Decided by starting the example from #88 in an empty directory and driving one
edit through the API, with the commands and their output pasted. From scratch
means no volume, no image cache and no model already present, because the
failure this catches is the one only a first run has.

### 5. The upgrade test run from the previous release

Asserts that an operator on the previous release reaches this one without
losing queued work or hand-editing state.

Decided by the route #90 defines, run from the previous release's artefacts to
this release's. For the first release there is no previous one, and the entry is
not applicable with that reason rather than absent.

### 6. The model licence audit current

Asserts that every model this release offers has its licence read at its origin
and recorded, and that nothing is offered whose licence record is unresolved.

Decided by the audit document and the registry agreeing, which #43 requires a
test to hold, and by the date each entry records against the release date. A
licence read once and never re-read is a fact about the day it was read.

Until #38 and #43 land there is no registry and no audit, and the entry is not
done with that reason.

### 7. The bill of materials and the third-party notices regenerated

Asserts that what ships beside the artefact describes the artefact, rather than
the one before it.

Decided by regenerating both through the route #72 defines and confirming the
tree holds no difference afterwards. `NOTICE.md` is in the tree today and is
about what this project does and does not support; the operator-facing notices
and the bill of materials are #72's and do not exist yet, so the entry is not
done with that reason.

### 8. The transparency marking verified on a produced file

Asserts that an image this release produced carries the mark, read out of the
file rather than out of the code that was supposed to write it.

Decided by producing one image through the release artefact and reading its
metadata back with the command #70 records. `docs/legal/transparency.md` holds
the position the mark implements and is the reading half of this item.

Until #70 lands there is no mark to read and the entry is not done with that
reason.

### 9. The readme, the guide and the model list checked against what the release does

Asserts that the three documents a new operator meets first describe this
release and not the plan for it.

Decided by a reading, and the walk records who read them. The readme is #92's,
the operator guide is #61's, and the model list is generated from the registry
under #71 rather than typed, so the third of the three is checked by
regenerating it and confirming no difference.

A reading is the weakest route on this list and it is here because no command
decides whether a sentence is still true. What makes it a route rather than an
opinion is that the walk names the reader.

## What this checklist does not cover

It does not decide whether a release should happen. It says what is true of one.

It does not cover anything below the items above. A gate that is green says the
gate passed, not that the change is right, and this list inherits every bound
those gates carry.

It does not judge its own coverage. Items were chosen from the plan, and a risk
nobody has written an issue for is a risk this list has no line for.

It does not run itself. Every entry is produced by somebody typing the command
or reading the document, and a walk with a pasted output nobody generated is
indistinguishable in the tree from one that was walked. That is the residual,
and #89 building the release route does not remove it: a workflow can hold item
1 and none of the readings.
