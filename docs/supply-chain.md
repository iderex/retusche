# The supply-chain self-audit, and what was done about each finding

`.github/workflows/scorecard.yml` scores this repository against the OpenSSF
supply-chain checks and uploads the result to the code-scanning tab. Running it
is not the control. A job that runs weekly and produces findings nobody reads
looks exactly like a job that runs weekly and finds nothing, and the difference
is this file.

Each finding below is either fixed, or accepted with the reason written out. No
finding is left in a third state.

## Where the list comes from

The workflow runs on a push to the default branch, on a schedule and on a
ruleset change, so the reading below is of the most recent run rather than of a
run this document caused:

    $ gh run list --workflow=scorecard.yml --limit 1 --json databaseId,headSha,conclusion --jq '.[]|"\(.databaseId) \(.headSha) \(.conclusion)"'
    31259002157 a43146dc022a687c1464578901ef0db2249a8958 success

The findings themselves are read from code scanning rather than from the run
log, because that is where they persist and where their state is kept:

    $ gh api "repos/iderex/retusche/code-scanning/alerts?tool_name=Scorecard&per_page=100" --jq '.[] | "\(.rule.id)\t\(.rule.security_severity_level)\t\(.state)"'
    CIIBestPracticesID      low     open
    CodeReviewID    high    open
    MaintainedID    high    open
    SecurityPolicyID        medium  fixed
    FuzzingID       medium  open
    LicenseID       low     fixed
    DependencyUpdateToolID  high    open
    SASTID  medium  fixed
    BranchProtectionID      high    open

That command is how this file is re-derived. The set moves, so a reader checking
whether this document is current runs it rather than counting the entries below.

## Fixed by the tree already

**License** and **Security-Policy**. Both were raised when the repository was
created and both are answered by files that landed afterwards:

    $ git ls-tree --name-only origin/main LICENSE SECURITY.md
    LICENSE
    SECURITY.md

They read `fixed` above, which is code scanning saying the latest analysis no
longer raises them.

**SAST**. Also `fixed`. What satisfied the check is not established here: the
check reads for an analyser over the repository's code, two workflows in this
tree upload SARIF to code scanning,

    $ grep -rl 'upload-sarif' .github/workflows/
    .github/workflows/scorecard.yml
    .github/workflows/zizmor.yml

and neither of those reads this project's Python. So the finding is closed and
the control it stands for is not yet in place. #76 is the code scanning gate
that would put it there, and it is open. Reading this row as covered would be
reading a score rather than a property.

## Fixed here

**Dependency-Update-Tool**, `high`, `no dependency update tool configurations
found`. `.github/dependabot.yml` answers it and is in the tree beside this
record. The reason it is worth fixing rather than accepting is not the score:
every action
in this tree is pinned to a commit sha, and a pinned action that nobody updates
is a dependency frozen at whatever was current on the day somebody wrote the
line, security fixes included. An updater turns that into a pull request that
meets the same gate as any other change.

## Accepted, with the reason

**Branch-Protection**, `high`, score 3. Its warnings are about approvers, stale
review dismissal, codeowners, last-push approval and required status checks on
`main`. Every one of those is a repository setting rather than a file in this
tree, so nothing in a pull request can change any of them and no change here
should claim to. Which checks stand in front of the default branch is #86, and
`docs/quality-parity.md` is the proposal and its evidence. The state of the
ruleset is whatever the command at the top of that file prints on the day it is
run.

**Code-Review**, `high`, `Found 0/13 approved changesets`. Accurate. Changes
here have been landing without a second reader, and the pull-request template
asks each change to say so in its own body for exactly this reason. It is
accepted rather than fixed because the remedy is a reviewer rather than a file,
and a required-approvals setting with nobody to approve is a repository that
cannot merge. Recording it is the honest half that is available.

**Maintained**, `high`, `project was created within the last 90 days`. A
statement about the calendar:

    $ gh api repos/iderex/retusche --jq '.created_at'
    2026-08-05T23:56:28Z

Nothing in the tree can answer it and time will. Accepted.

**Fuzzing**, `medium`, `no fuzzer integrations found`. Correct, and it stays
correct for a while yet. Fuzzing here is #79, and its targets are the image
ingest and mask parsing paths, neither of which exists: the orchestration layer
holds one subpackage and it is the test double.

    $ git ls-tree -d --name-only origin/main:src/retusche
    testing

A fuzz target added now would run against a copy of a validation path rather
than the one a caller reaches, which is the first thing #79's own conditions
refuse. Accepted until there is something taking bytes from a stranger.

**CII-Best-Practices**, `low`, `no effort to earn an OpenSSF best practices
badge detected`. That badge is an enrolment on an external site rather than
anything in this repository, so it is the maintainer's to take and it is not
taken. Accepted as an open decision rather than as a defect.

## What refuses any of this

Nothing. No check reads this file, no check compares it against the current
alert set, and a finding that appears next week appears with every gate green.
The command in the first section is the whole of the mechanism, and it is a
command a person runs. This document is a record, and the register that would
refuse a stale one does not exist here.
