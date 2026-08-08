# Quality parity

This file holds the branch-protection side of the parity work. It says which
published check names are proposed as merge conditions for the default branch,
which are proposed as advisory, and what has actually been observed of each one.

It changes nothing. Requiring a check is an act on the repository rather than a
change in the tree, and the command in the next section is what says whether
that act has been taken.

The second half of the file is the map: every line of the gate this project is
held to, matched here, replaced by a named counterpart, or dropped, with the
reason and the issue that delivers it.

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

Every failing run this repository has recorded, not a sample. The list grows,
so the command is the authority and what follows is what it printed at the
commit that added this paragraph:

    gh api --paginate "repos/iderex/retusche/actions/runs?per_page=100" --jq '.workflow_runs[] | select(.conclusion=="failure") | "\(.name)\t\(.id)\t\(.event)"'
    unicode-guard	31111491469	pull_request
    Workflow Security Analysis	31111490977	pull_request
    Pull request checks	31111490893	pull_request
    unicode-guard	31111477192	push
    Pull request checks	31097485489	pull_request
    Pull request checks	31097265500	pull_request
    line-endings	31095816028	push
    line-endings	31095690232	push

A workflow run is not a check name, so a run that holds more than one job is
read at the job level:

    gh api "repos/iderex/retusche/actions/runs/31097265500/jobs" --jq '.jobs[] | "\(.name)\t\(.conclusion)"'
    lint	failure
    type-check	success

    gh api "repos/iderex/retusche/actions/runs/31111490893/jobs" --jq '.jobs[] | "\(.name)\t\(.conclusion)"'
    type-check	failure
    lint	success

Five published names have been watched refusing something: `lint`,
`line-endings`, `type-check`, `Reject Trojan Source Unicode` and
`Audit workflows (zizmor)`. Each refused a near miss written to make it refuse,
each went green again when the fixture came out, and each entry below cites the
run. The remaining names have only ever been seen passing.

Every one of those near misses was refused by its own gate and by no other. On
the head that carried all three of the most recent ones, the checks that had
nothing to do with them stayed green:

    gh api "repos/iderex/retusche/commits/f5a0b07c3e9646e41157dbb5bebcb9318a64d0e6/check-runs?per_page=100" --jq '.check_runs[] | "\(.name)\t\(.conclusion)"' | sort
    Audit workflows (zizmor)	failure
    DCO sign-off	success
    dependency-review	success
    line-endings	success
    line-endings	success
    lint	success
    Reject Trojan Source Unicode	failure
    Reject Trojan Source Unicode	failure
    type-check	failure
    zizmor	success

That matters more than the count of red runs. A fixture that reddens three gates
at once proves that something is wrong, not that each gate refuses the thing it
names.

The reason each entry carries its observation at all: a check that has never
failed is one whose failure path has not run, and requiring it makes a merge
depend on behaviour nobody has seen. That is not an argument against requiring
the remaining ones. It is the thing to do before the act is taken, and each
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
Green observed on the same head. Red observed at run `31111490893`, job
`type-check`, on a module whose annotation said it returned text and whose body
returned the number it was given. The fixture was removed once the run existed.

`DCO sign-off`, declared in `.github/workflows/dco.yml`. This is the term on
which a change from outside is accepted. A term that does not block a merge is
not a term. Green observed on the same head. Red not observed, and it is the
awkward one to observe: the job reads every commit in the pull request, so a red
run is produced by one commit without the trailer and is cleared only by
rewriting the branch, which is why no run has produced one so far.

`Reject Trojan Source Unicode`, declared in
`.github/workflows/unicode-guard.yml`. Bidirectional control characters make a
diff read differently from what it does, which is the one defect class a reviewer
cannot catch by reading more carefully. Green observed on the same head. Red
observed twice on one head, runs `31111491469` and `31111477192`, on a tracked
file carrying a right-to-left override in the middle of a sentence. The fixture
was removed once the runs existed. Published twice per head, as above, and both
copies refused it.

`Audit workflows (zizmor)`, declared in `.github/workflows/zizmor.yml`. The
workflows hold the only credentials this repository has, and this is the job that
judges them. Green observed on the same head. Red observed at run `31111490977`,
on a job declaring no permissions block and checking out with the token left in
`.git/config`, which is what copying a job out of a tutorial produces. The
fixture was removed once the run existed.

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
on the same head. Red not observed, and the head that reddened the audit is the
evidence for keeping it advisory: `Audit workflows (zizmor)` refused the near
miss on `f5a0b07c3e9646e41157dbb5bebcb9318a64d0e6` and `zizmor` reported success
on the same commit, in the listing above. Requiring this name would have let
that change through.

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

## The gate this one is derived from

The standard is not invented here. It is what stands in front of the default
branch of the public repository `iderex/jellyfin-plugin-sso`, read rather than
remembered:

    gh api repos/iderex/jellyfin-plugin-sso/rulesets --jq '.[] | "\(.id) \(.name)"'
    18802863 Protect main and 5.0

    gh api repos/iderex/jellyfin-plugin-sso/rulesets/18802863 --jq '{enforcement, bypass:.bypass_actors, required:[.rules[].parameters.required_status_checks[]?.context]}'
    {"enforcement":"active","bypass":[],"required":["build","ABI floor build","Package (JPRM) / Build package","Package (JPRM) / Generate SBOM","CodeQL","Analyze (csharp)","DCO sign-off","Deterministic PR-hygiene checks","Enforce greppable invariants","Reject Trojan Source Unicode","Audit workflows (zizmor)","prettier","dependency-review"]}

That output moves when that repository changes, so it is the authority and the
entries below are what it printed when they were written. Re-run it before
arguing with a line of the map.

Parity is not thirteen names copied across. That repository builds a plugin
binary for a plugin catalogue, in a different language, and several of its
required names are about exactly that. This one is a service that takes
untrusted image bytes, holds a device budget and writes into somebody's photo
library, so it needs gates that one has no reason to have.

## Every required name of that gate, mapped

One of matched, replaced or not applicable, with the reason and the issue that
delivers it. Where nothing delivers an entry, it says so rather than naming an
issue that does not cover it.

`build`. Replaced. There is nothing to compile here, so what that name proves,
that the tree still turns into the artefact somebody runs, is split in two: the
environment resolving from the lock file and the suite executing against it is
#5, and the artefact an operator actually runs is the container image in #87.

`ABI floor build`. Not applicable. It proves a plugin still compiles against the
oldest host it claims to support, and this project links into no host. The
nearest constraint is the interpreter series, pinned in `pyproject.toml` rather
than floored, which is a property of the lock file and not a check. Nothing
delivers a counterpart and nothing should.

`Package (JPRM) / Build package`. Not applicable. It packages a plugin for a
catalogue this project does not publish to. The two things it would otherwise
stand for are the image in #87 and the release route in #89, and neither is a
counterpart to it.

`Package (JPRM) / Generate SBOM`. Replaced by the bill of materials and the
third-party notices in #72. The name is different because the artefact is, and
the obligation is wider here: the notices an operator must ship are a licence
question as well as a supply-chain one.

`CodeQL`. Replaced by the code scanning gate for this language, #76. The same
tool family with a different language pack, and the published name will differ
because the job that produces it is declared here rather than there.

`Analyze (csharp)`. Replaced by the same entry. It is CodeQL's per-language job
name rather than a second control, and that ruleset lists both because both
names are published. Whether this project ends up publishing one name or two is
#76's to answer and #86's to require.

`DCO sign-off`. Matched, under the same name, declared in
`.github/workflows/dco.yml`. It is already in the tree. Making it a condition of
the merge rather than a job beside it is #86.

`Deterministic PR-hygiene checks`. Replaced in part and dropped in part. The
half that judges stored bytes is the `line-endings` job, already here. The half
that judges the pull request itself has no mechanism here. The issue and
pull-request templates are in `.github/`, under #12, and a template is a prompt
rather than a check: nothing refuses a body that ignores one. That is a gap in
the map and it is written as one.

`Enforce greppable invariants`. Replaced by #80. The same idea with a different
scanner, because the invariants worth grepping for in a Python service are not
the ones worth grepping for in a plugin.

`Reject Trojan Source Unicode`. Matched, under the same name, declared in
`.github/workflows/unicode-guard.yml`. Already here. Requiring it is #86.

`Audit workflows (zizmor)`. Matched, under the same name, declared in
`.github/workflows/zizmor.yml`. Already here. Requiring it is #86.

`prettier`. Replaced in part. Python formatting is held by the `lint` job, which
is already here. Everything that is not Python, which is most of what prettier
covers there, is the documentation lint in #82 and does not exist yet.

`dependency-review`. Matched, under the same name, declared in
`.github/workflows/dependency-review.yml`. Already here. Requiring it is #86.

## The practices that gate does not require

Read rather than remembered, because a repository grows workflows:

    gh api "repos/iderex/jellyfin-plugin-sso/actions/workflows?per_page=100" --jq '.workflows[] | "\(.name)\t\(.path)"'

Mapped the same way, and only the ones that judge quality. The publishing
workflows in that list are a plugin catalogue's route to its users. They are not
applicable for the same reason the packaging names above are, and what stands
where they would is the release route in #89 with upgrades in #90.

`Stryker mutation testing`. Replaced by #78. A coverage floor says which lines
ran and never whether anything was asserted about them, and this is the control
that separates the two.

`Fuzz (SharpFuzz)`. Replaced by #79, and promoted rather than copied. There the
fuzzed surface is a token parser. Here it is an image decoder taking bytes from
a stranger, which is the sharpest edge this project has, and it is listed again
under the additions below for that reason.

`E2E Login Harness`. Replaced by #59, which proves the round trip against a real
library instance rather than against a stub. The hardware harness in #85 is the
other half: the register for everything that cannot run on a machine with no
device.

`Wiki Lint`. Replaced by #82, which is the same control over the documents that
live in this tree rather than in a wiki.

`Repo Invariant Lint (Opengrep)`. This is the required entry above, and it
appears here only because the workflow list carries it. It is #80.

`Scorecard supply-chain security`. Matched, under the name `Scorecard analysis`,
already here and already advisory. The section above says why it is not a merge
condition, and the reason is a property of what it judges rather than a lack of
confidence in it.

`Automatic Dependency Submission`. Matched. It runs here as `update-uv-graph`
and is advisory for the reason the section above gives.

`Dependabot Updates`. Matched. `.github/dependabot.yml` configures it over the
action pins and over `uv.lock`, so a version change arrives as a pull request
that meets the whole gate. The check name it publishes under is not observed
here, because nothing has run yet; the rest of the control it stands for, a lock
file that cannot drift and artefacts that trace back to a commit, is #81.

`.NET`. Replaced by the `type-check` and `test` jobs, which is where that
language's build and test verbs live here. #5 delivers the second.

## What this project needs that gate does not have

Three because of what this project is, and each is a gate rather than a practice.

The input-decoding fuzz gate, #79. This service decodes image bytes that arrive
from outside it, through a wrapper around a C library. Every other control in
this map judges code somebody wrote here. This one judges what happens when the
bytes are hostile, and #51 is the surface it fuzzes.

The headless conformance gate, #84. The whole suite is meant to run with no
display, no elevation and no device present. The `test` job prints what the
runner had and refuses nothing, so a test that quietly needs one of the three
passes on a machine that has it and fails on a machine that does not. #84 turns
those printed facts into a property.

The import boundary, #7. The process that accepts HTTP may not reach a
machine-learning runtime, a model library or the worker package, because a
native tensor library that dies takes the process down with it and the queue has
to survive that. The gate this map is derived from has no counterpart, because
nothing there runs two processes for that reason. #83 is the wider architecture
conformance suite that boundary is the first rule of.

Two more follow from the same argument, and they are named so this list is not
read as complete. The model licence audit, #43 and #71, because this project
hands an operator weights whose terms are not this project's to grant. And the
transparency marking, #70, because what this service produces is generated
content and the marking is an obligation rather than a feature.

## Which of these are merge conditions here

The split is written in the two sections above, `Proposed required set` and
`Advisory set`, and is not restated. What the split is made on is worth saying
once.

A name is proposed as a condition of the merge when it is published on every
pull-request head, when it judges the change rather than the repository, and
when its refusal path has been watched running. The first two are properties of
the check and are settled by reading the workflow. The third is an observation,
which is why each entry carries one and why the entries without one say so.

A name is advisory when it fails any of those three. Two advisory entries fail
the first, appearing on the default branch and not on a pull request. One fails
it conditionally, which is the worse case, and the section above carries the run
where that name reported success on a commit its own audit refused.

Nothing in this map is a merge condition today, because every entry that is not
already in the tree names an issue that has not landed, and no entry that is in
the tree has been required yet. What guards the branch is whatever the command
at the top of this file prints, and so far it has printed no required status
check at all.
