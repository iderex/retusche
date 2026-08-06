# Contributing

## Set up the environment

One command, from a fresh clone:

    uv sync

It creates `.venv/` from `uv.lock` and installs this project into it. The
interpreter is pinned to one minor series in `pyproject.toml`, so uv fetches
that interpreter if the machine does not already have it. Nothing else is
installed by hand.

Add `--locked` when you want the command to refuse instead of resolving:

    uv sync --locked

That is what the pull-request job runs, so a `pyproject.toml` and a `uv.lock`
that disagree stop the job rather than quietly installing a set of versions no
other machine would get.

## Run the gates

In the order they should be run.

| What | Command |
| --- | --- |
| Lock file matches the project file | `uv lock --check` |
| Type check, strict | `uv run mypy` |

`uv lock --check` names the repair rather than performing it: it prints
`hint: To update the lockfile, run uv lock` and exits non-zero.

Two gates are missing from that table and their absence is not an oversight.
There is no format command and no lint command, which is issue #3, and there is
no test command and no coverage floor, which is issue #5. Until those land,
running everything in this table is not the same as running everything a change
has to pass, and this file will say so until the rows exist.

## Suppressing a type error

A suppression names the error code and carries the reason on the same line:

    value = untyped_call()  # type: ignore[no-any-return]  # the library ships no stubs, see #NNN

The gate refuses both shorter forms. mypy refuses `# type: ignore` with no
error code, and the pull-request job refuses a coded suppression with nothing
after it. It also prints how many suppressions the tracked tree holds, so a
change that adds one cannot present itself as adding none.

A third-party library that ships no type information is declared once, in the
`[[tool.mypy.overrides]]` block at the foot of `pyproject.toml`, and never
silenced at the import site.

## Published checks

A check name is an interface. A ruleset matches a required status check by its
literal name, so renaming one silently removes whatever gate was matching the
old name.

This file does not list them, because a list in a document drifts against the
thing it describes. The checks a change actually has to pass are printed by:

    gh pr checks <number>

Of those, one has a local equivalent today: `type-check` is reproduced by
`uv run mypy` plus the two suppression scans in
`.github/workflows/pull-request.yml`. The rest read the pull request itself,
the workflow files or the advisory database, and have no local form.

## How a change is made

A change starts from an issue. The issue says what is wrong, what the evidence
is, and what done means. Where the evidence is a number, it carries the command
that produced it.

The default branch takes changes only through a pull request. Its history is not
rewritten: no force push, no rebase of anything already pushed to a shared
branch, no branch deletion except a merged head.

Everything about a change goes in the pull-request body. If the body is wrong or
out of date, edit the body. A comment underneath it is not where a change is
argued.

One topic per pull request and per commit. A commit carrying two unrelated
changes has a message describing one of them.

## Commit messages

State what changed and what failure the change prevents. Where you are
correcting something, say what was wrong and how it was found.

## Sign your work

Every commit carries a `Signed-off-by` trailer matching its author. By adding
it you certify the [Developer Certificate of Origin](DCO), which is the file
the sign-off gate names.

    git commit -s

If you have already committed without it, add it across the branch rather than
by hand:

    git rebase --signoff <base>

That rewrites your own branch, which is allowed; the default branch is what is
never rewritten. The gate reads every non-merge commit in the pull request, so
one commit without the trailer reds the check.
