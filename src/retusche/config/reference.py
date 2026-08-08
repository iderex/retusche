# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The operator's reference page, written from the declaration.

`docs/configuration.md` is produced by this module and by nothing else, and the
suite refuses a committed page that differs from what this produces. A reference
page maintained by hand is correct on the day it is written and drifts from the
first setting added afterwards, which is the failure this shape removes: the
page cannot be right about a setting that is not declared and cannot be silent
about one that is.

The cost is paid knowingly and is worth naming. The prose below sits in a module
rather than in the document, which is the wrong place for prose to live if you
are reading the document. The alternative, a hand-written page with a generated
table inside markers, keeps the prose where it belongs and gives up the property:
the sentences around the table are then free to describe a surface that has
moved. The property was chosen, and this paragraph is where the trade is
recorded rather than discovered.
"""

from __future__ import annotations

from retusche.config.settings import SETTINGS, Kind, Setting, environment_name

__all__ = ["reference_markdown"]

_PREAMBLE = """# Configuration

This page is generated from `retusche.config.settings`, and the suite refuses a
committed copy that differs from what the declaration produces. Edit the
declaration, not this file.

## Where a value comes from

Three sources, each overriding the one before it:

1. the configuration file, which is TOML and is a flat table of setting names
2. the environment, where a setting is read from `RETUSCHE_` followed by its
   name in upper case
3. what the command line supplies

The order runs from the least specific intention to the most. A file is written
once for a deployment, a variable is set for a process, and a flag is typed for
a single run, so the later source is the one that was meant more precisely.

## What is refused

Every problem at once, rather than the first one. An operator with four mistakes
in a file corrects them once instead of restarting four times, which matters
because each restart is a deployment.

A name nothing declares, in any source. A misspelled setting would otherwise do
nothing while reading as though it had done something, and the setting it was
meant to be keeps a value nobody chose.

An environment variable starting with `RETUSCHE_` that names no setting. The
limit of that check is the prefix: a variable misspelled outside it, such as
`RETUSHE_JOB_STORE_PATH`, is invisible here and always will be, because a check
that read every variable on the host would refuse the host's own.

A value that is not what its kind says. A whole number written as a word, a
boolean written as `yes`, a path written as a number.

A setting with no default and no value. There is no state in which such a
setting takes something nobody wrote.

## Secrets

A setting declared as a secret never appears in a rendering of the effective
configuration. The redaction is decided by the declaration rather than by
whoever is printing, so a setting that becomes a secret later is redacted
everywhere at once instead of everywhere somebody remembered.

## The settings
"""

_KIND_NOTE = {
    Kind.TEXT: "text",
    Kind.SECRET: "text, and never printed",
    Kind.INTEGER: "a whole number",
    Kind.BOOLEAN: "`true` or `false`",
    Kind.PATH: "a filesystem path",
}


def reference_markdown(settings: tuple[Setting, ...] = SETTINGS) -> str:
    """The whole page, ending with a newline, as the tree carries it."""
    sections = [_PREAMBLE.rstrip("\n")]
    for setting in settings:
        sections.append(_section(setting))
    return "\n\n".join(sections) + "\n"


def _section(setting: Setting) -> str:
    """One setting: its name, what it is, what it is measured in, its default."""
    default = (
        "none, and the service does not start without it"
        if setting.default is None
        else f"`{setting.default}`"
    )
    return (
        f"### `{setting.name}`\n"
        f"\n"
        f"{setting.summary}\n"
        f"\n"
        f"- Kind: {_KIND_NOTE[setting.kind]}\n"
        f"- Unit: {setting.unit}\n"
        f"- Default: {default}\n"
        f"- Environment: `{environment_name(setting)}`"
    )
