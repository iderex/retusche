# Quality parity

This file holds the branch-protection side of the parity work. It says which
published check names are proposed as merge conditions for the default branch,
which are proposed as advisory, and what has actually been observed of each one.

It changes nothing. Requiring a check is an act on the repository rather than a
change in the tree, and the command in the next section is what says whether
that act has been taken. The mapping of this project's gates onto the gate they
are derived from is issue #75 and is not written here.

## What guards the default branch today

Read rather than remembered:

    gh api repos/iderex/retusche/rulesets --jq '.[] | "\(.id) \(.name)"'
    20481970 gate

    gh api repos/iderex/retusche/rulesets/20481970 --jq '{enforcement, bypass:.bypass_actors, rules:[.rules[].type]}'
    {"bypass":[],"enforcement":"active","rules":["deletion","non_fast_forward","pull_request"]}

Deletion is refused, a force push is refused, a change arrives through a pull
request, and no status check is a condition of the merge. That was the right
state while no check existed. This file is the proposal for what replaces it,
and it has replaced nothing.

## A check name is matched literally

A required status check is named by string. Rename a job and it publishes a
different name; the ruleset goes on waiting for the old one, and the gate stops
standing in front of anything while the ruleset still lists it. Nothing reports
that. So the names below are quoted exactly, and a rename is a change to this
file and to the ruleset together.

A job that declares `name:` publishes that string. A job that does not publishes
its job id.

    git grep -nE '^    name: ' origin/main -- .github/workflows/
    origin/main:.github/workflows/dco.yml:24:    name: DCO sign-off
    origin/main:.github/workflows/scorecard.yml:50:    name: Scorecard analysis
    origin/main:.github/workflows/unicode-guard.yml:23:    name: Reject Trojan Source Unicode
    origin/main:.github/workflows/zizmor.yml:41:    name: Audit workflows (zizmor)

Those four are the declared names. The rest of what a pull request publishes
comes from a job id, and two names come from no file in this tree at all:
`zizmor` is created by code scanning when the audit uploads its SARIF under that
category, and `update-uv-graph` comes from the dependency graph workflow GitHub
runs for this repository.

This file is not the authority for what exists. That is printed, per commit, by

    gh api "repos/iderex/retusche/commits/<sha>/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"'

The names below are quoted because a ruleset matches a string, so a name is an
interface and not a description. Where this file and that command disagree, the
command is right and this file is stale.

## Where the names appear, and where they do not

On the head of a pull request, `5aa60dd5f3836e85863c55736b34374021d7fdf7`:

    gh api "repos/iderex/retusche/commits/5aa60dd5f3836e85863c55736b34374021d7fdf7/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort
    Audit workflows (zizmor)	success
    DCO sign-off	success
    dependency-review	success
    line-endings	success
    line-endings	success
    lint	success
    Reject Trojan Source Unicode	success
    Reject Trojan Source Unicode	success
    type-check	success
    zizmor	success

On the head of the default branch, `9e4a32648962`:

    gh api "repos/iderex/retusche/commits/9e4a32648962/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort
    Audit workflows (zizmor)	success
    line-endings	success
    Reject Trojan Source Unicode	success
    Scorecard analysis	success
    update-uv-graph	success

The two sets differ, and only the first one matters for a merge condition. A
name that never appears on a pull request head can never answer one.

Two names appear twice in the first listing. `line-endings` and
`Reject Trojan Source Unicode` are declared on both `push` and `pull_request`
against every branch, and a branch push and the pull request opened from it
share a head commit, so each publishes two check runs under one name. What a
ruleset does when two runs carry the name it matches has not been measured here,
and it is worth measuring before either of those two is required.

## What has been observed

Every workflow run this repository has recorded, not a sample:

    gh api --paginate "repos/iderex/retusche/actions/runs?per_page=100" --jq '.workflow_runs[].conclusion' | sort | uniq -c
          4 failure
        116 success

    gh api --paginate "repos/iderex/retusche/actions/runs?per_page=100" --jq '.workflow_runs[] | select(.conclusion=="failure") | "\(.name)\t\(.id)\t\(.head_sha)"'
    Pull request checks	31097485489	37cbf0e3f53266507aeda7e0b84be3f8218a8724
    Pull request checks	31097265500	670f5f992510941e6615e891e3e1f55d0318564c
    line-endings	31095816028	911a8b4de4541885728c96b4f186daca111f5822
    line-endings	31095690232	0dac0b2362b2688561f97b5af08a73258f31929e

A workflow run is not a check name, so the two pull-request failures are read at
the job level:

    gh api "repos/iderex/retusche/actions/runs/31097265500/jobs" --jq '.jobs[] | "\(.name)\t\(.conclusion)"'
    lint	failure
    type-check	success

    gh api "repos/iderex/retusche/actions/runs/31097485489/jobs" --jq '.jobs[] | "\(.name)\t\(.conclusion)"'
    type-check	success
    lint	failure

Two published names have been watched refusing something: `lint` and
`line-endings`. Both refused a near miss written to make them refuse, and both
went green again when it was removed. Every other name in this repository has
only ever been seen passing.

That is the reason each entry below carries its observation. A check that has
never failed is one whose failure path has not run, and requiring it makes a
merge depend on behaviour nobody has seen. It is not an argument against
requiring these checks. It is the thing to fix before the act is taken, and each
entry says what would produce the missing observation.

## Proposed required set

Each entry gives the exact published name, why it belongs in front of the branch
rather than beside it, and what has been observed.

`lint`, the job id in `.github/workflows/pull-request.yml`. Formatting and
the lint rules are the only judgement in this tree that reaches every tracked
Python file, and both halves are repairable by one command, so a red run costs a
contributor nothing but a rerun. Green observed on
`5aa60dd5f3836e85863c55736b34374021d7fdf7`. Red observed twice, runs
`31097265500` and `31097485489`.

`line-endings`, the job id in `.github/workflows/line-endings.yml`. It reads
what git stores rather than what is on disk, so it is the one gate whose verdict
does not move with the contributor's platform, and a stored carriage return is
the defect that silently changes bytes a later test will assert on. Green
observed on the same head. Red observed twice, runs `31095690232` and
`31095816028`. Published twice per head, which is the duplicate-name question
above.

`type-check`, the job id in `.github/workflows/pull-request.yml`. Strict
typing is the only thing standing behind the contract package's declarations
while there is no suite, and a break there reaches every layer that imports it.
Green observed on the same head. Red not observed. What would produce it: a
tracked module carrying an annotation that strict mypy refuses, landed as a near
miss and removed once the run is recorded.

`DCO sign-off`, declared in `.github/workflows/dco.yml`. This is the term on
which a change from outside is accepted. A term that does not block a merge is
not a term. Green observed on the same head. Red not observed, and it is the
awkward one to observe: the job reads every commit in the pull request, so a red
run is produced by one commit without the trailer and is cleared only by
rewriting the branch, which is why no run has produced one so far.

`Reject Trojan Source Unicode`, declared in
`.github/workflows/unicode-guard.yml`. Bidirectional control characters make a
diff read differently from what it does, which is the one defect class a reviewer
cannot catch by reading more carefully. Green observed on the same head. Red not
observed. What would produce it: a tracked file carrying a bidi override,
landed as a near miss and removed. Published twice per head, as above.

`Audit workflows (zizmor)`, declared in `.github/workflows/zizmor.yml`. The
workflows hold the only credentials this repository has, and this is the job that
judges them. Green observed on the same head. Red not observed. What would
produce it: a step referring to an action by tag instead of by commit, which the
audit refuses at the severity the job already runs at.

`dependency-review`, the job id in
`.github/workflows/dependency-review.yml`. It answers only on a pull request,
which is exactly where a dependency arrives. Green observed on the same head.
Red not observed. What would produce it: a dependency with a published advisory
added to the lock file on a branch, and removed once the run is recorded.

## Advisory set

These are not proposed as merge conditions, and the reason is a property of each
one rather than a lack of confidence in it.

`zizmor`, created by code scanning rather than by a job. It reports the same
audit as `Audit workflows (zizmor)`, but it exists only when the SARIF upload
runs, and `.github/workflows/zizmor.yml` skips that upload where the token cannot
write security events. A required check that is not published at all on those
pull requests is a merge that cannot complete, and the refusal it carries is
already carried by the job name above, which runs in every case. Green observed
on the same head. Red not observed.

`Scorecard analysis`, declared in `.github/workflows/scorecard.yml`. It is
triggered by `branch_protection_rule`, by a schedule and by a push to the default
branch, and by nothing on a pull request. It does not appear in the pull-request
listing above and does appear in the default-branch listing, which is the
observation rather than a reading of the file. It scores the repository over
time; it does not judge a change. Green observed on `9e4a32648962`. Red not
observed.

`update-uv-graph`, from the dependency graph workflow GitHub runs for this
repository. No file in this tree declares it, so nothing here can keep its name
stable, and it appears on the default branch rather than on a pull request head.
Green observed on `9e4a32648962`. Red not observed.

## What this file does not settle

Which checks the ruleset requires is decided by the maintainer and applied to the
repository. This file is the proposal and the evidence behind it. The state of
the ruleset is whatever the command at the top prints on the day it is run.
