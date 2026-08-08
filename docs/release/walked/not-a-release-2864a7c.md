# A walk of the readiness list against a commit that is not a release

This is not a release record. No release exists:

    gh release list --limit 5 ; echo "exit=$?"
    exit=0

    git ls-remote --tags origin ; echo "exit=$?"
    exit=0

Both printed nothing. What follows is `docs/release/readiness.md` walked
against `2864a7ceae2f52ce2f78b49606d0f04f0c77d8d9`, the head of the default
branch on the day the list landed, so that every item has been shown to be
decidable by the route it names. Seven of the nine come out not done and one
comes out not applicable, which is the state of the tree rather than a defect
in the walk.

The value of walking it early is the part that does not survive being imagined:
item 1 was written with one command and the walk showed it needed two.

## 1. Every gate green on the release commit

Done, and the item was corrected by walking it.

`2864a7c` is a merge commit produced on the server. Read directly, it publishes
the four names that answer a push:

    gh api "repos/iderex/retusche/commits/2864a7ceae2f52ce2f78b49606d0f04f0c77d8d9/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort
    Audit workflows (zizmor)	success
    line-endings	success
    Reject Trojan Source Unicode	success
    Scorecard analysis	success

Read on the head of the pull request it merged, it publishes eleven:

    gh pr view 121 --json headRefOid,mergeCommit --jq '"head=\(.headRefOid) merge=\(.mergeCommit.oid)"'
    head=1ea1859cd83b72d046457f374e52bdd89fb69b60 merge=2864a7ceae2f52ce2f78b49606d0f04f0c77d8d9

    gh api "repos/iderex/retusche/commits/1ea1859cd83b72d046457f374e52bdd89fb69b60/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort
    Audit workflows (zizmor)	success
    DCO sign-off	success
    dependency-review	success
    line-endings	success
    line-endings	success
    lint	success
    Reject Trojan Source Unicode	success
    Reject Trojan Source Unicode	success
    test	success
    type-check	success
    zizmor	success

Seven names appear on one listing and not on the other. A walk that read only
the merge commit would have recorded a green release against a set missing
`lint`, `test` and `type-check`, which is the whole of what judges the code. The
item now says to read both, and this is where that sentence came from.

`docs/quality-parity.md` is the reading half and it is current: it argues each
of these names and it is where a rename has to be reflected.

## 2. The hardware harness run on named hardware, with its results recorded

Not done. There is no harness. `tests/` holds no subdirectory at all, so
`tests/hardware/` is absent rather than empty:

    git ls-tree -d --name-only origin/main:tests ; echo "exit=$?"
    exit=0

#85 delivers it.

## 3. The library round-trip harness run against a stated library version

Not done, and by the same command as item 2: `tests/integration/` does not
exist. #59 delivers it.

## 4. The compose example started from scratch, and one edit completed

Not done. Nothing in the tree describes a container arrangement, and there is
no service to start:

    git ls-tree -r --name-only origin/main | grep -iE 'compose|dockerfile' ; echo "exit=$?"
    exit=1

#88 delivers the example and #87 the image it would start.

## 5. The upgrade test run from the previous release

Not applicable. There is no previous release, by the two commands at the top of
this file. #90 delivers the route, and the first walk that can produce a verdict
here is the second release's.

## 6. The model licence audit current

Not done. There is no registry and no audit document:

    git ls-tree -r --name-only origin/main | grep -iE 'registry|docs/models/' ; echo "exit=$?"
    exit=1

#38 delivers the registry and #43 the audit. #43 also records that whether a
non-commercially licensed model is offered at all is a maintainer decision
raised in #94, so this item cannot be answered before that entry is settled
either.

## 7. The bill of materials and the third-party notices regenerated

Not done. `NOTICE.md` is in the tree and is not this: it states which uses this
project does not support and which capabilities it does not build. No
operator-facing third-party notice file and no bill of materials exist, and
nothing generates either. #72 delivers both.

## 8. The transparency marking verified on a produced file

Not done. Nothing produces an image, so there is no file to read a mark out of.
`docs/legal/transparency.md` is in the tree, which is the reading half of the
item, and #70 owes the mark itself. `NOTICE.md` already says of this that it
describes what is being built rather than what a running service does.

## 9. The readme, the guide and the model list checked against what the release does

Not done, and only one of the three exists. `README.md` is in the tree; the
operator guide is #61's and `docs/operating/` does not exist; the model list is
generated from the registry under #71 and neither exists.

Checking `README.md` alone against a release that cannot be produced would
answer a third of the item, and a third of an item is not the item.

## What this walk establishes, and what it does not

It establishes that every route on the list resolves to a command that runs or
to a document that can be read, and that an item whose route is missing produces
a reason rather than a blank. It found one defect in the list and the fix is in
the list rather than only here.

It establishes nothing about a release. Seven of nine items are not done
because the work they check has not been built, and the two that produced a
verdict are the two that need only the tracker and the tree.
