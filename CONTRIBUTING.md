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
| Format the tree | `uv run ruff format` |
| Formatting is already what it would be | `uv run ruff format --check` |
| Lint | `uv run ruff check` |
| Type check, strict | `uv run mypy` |
| No carriage return in tracked text | `git grep -nIP '\r' HEAD -- .` |

`uv lock --check` names the repair rather than performing it: it prints
`hint: To update the lockfile, run uv lock` and exits non-zero.

The line-ending scan prints the offending file and line, and prints nothing on
a clean tree. It reads blobs at `HEAD`, not files on disk, which is why it is
the same command everywhere; the section below says what that buys.

One gate is missing from that table and its absence is not an oversight. There
is no test command and no coverage floor, which is issue #5. Until it lands,
running everything in this table is not the same as running everything a change
has to pass, and this file will say so until the row exists.

`uv run ruff format` is the repair and `--check` is the verdict, and they are
the same binary resolved from the same lock file, so the gate and the repair
cannot disagree about what formatted means. The rule set is in `pyproject.toml`
and never on a command line: a flag passed in a workflow is a rule that exists
only where that workflow runs.

The formatter reaches python inside markdown as well as python in a `.py` file,
so a fenced code block in a document is formatted like the code it shows. An
indented block is not, because it is not fenced and nothing declares its
language.

## Line endings and exact bytes

Tracked text is stored with LF. `.gitattributes` declares that per file type and
marks the binary types so no filter touches them, `.editorconfig` asks your
editor to write LF and UTF-8 in the first place, and the `line-endings` check
refuses what got past both.

Your working copy is not judged. If you are on a platform that checks out with
carriage returns, an unmodified tree is still green, because the check reads
what git stores rather than what is on your disk. This is the command that shows
which is which on your own clone:

    git ls-files --eol | head -3

The first column is the stored line ending and the second is your working copy.
`i/lf w/crlf` on every line is a normal, green state, and it is what a Windows
checkout looks like. What would be red is `i/crlf` or `i/mixed` in that first
column, which the check's second leg refuses by name.

A test that has to embed exact bytes writes them as base64 rather than as a
literal, and `docs/text-fidelity.md` says why, along with what these checks do
not cover.

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

Three of them have a local equivalent today, and the name is written here beside
the command because a name you cannot reproduce locally is a name you can only
argue with after a red run.

`type-check` is reproduced by `uv run mypy` plus the two suppression scans in
`.github/workflows/pull-request.yml`. `lint` is reproduced by
`uv run ruff format --check` followed by `uv run ruff check`, in that order,
which is the order the job runs them. `line-endings` is reproduced by the scan
in the table above together with

    git ls-files --eol | grep -E '^i/(crlf|mixed)'

and unlike the other two it needs nothing installed.

The rest read the pull request itself, the workflow files or the advisory
database, and have no local form.

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
