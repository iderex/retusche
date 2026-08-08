# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Reading the configuration, and refusing the whole of it at once.

Three sources, in this order, each overriding the one before it:

1. the file, which is TOML and is a flat table of setting names
2. the environment, where a setting is read from ``RETUSCHE_`` and its name in
   upper case
3. the overrides, which is what a command line supplies

The order is the usual one and the reason is that the later a source is, the
more specific the intention behind it: a file is written once for a deployment,
an environment variable is set for a process, and a flag is typed for a run. The
command line is a mapping here rather than a parsed ``argv`` because there is no
entry point in this tree yet; whoever builds one passes what it parsed.

Everything is refused at once
-----------------------------
A loader that stops at the first problem makes an operator with four mistakes
restart four times, and each restart is a deployment. So every source is read,
every value is parsed, and the refusal names every problem it found, sorted, in
one message. The property that makes it worth having is not tidiness: it is that
the fourth mistake gets seen, and a loader that fails fast is one where the
fourth mistake is discovered by the operator's fourth attempt.

Fail-closed
-----------
An unknown name is refused rather than ignored, in every source. The typo in a
deployment file is the failure this is for: ``job_store_pth`` silently does
nothing, the setting keeps whatever it would have had, and the operator has a
file that says one thing and a service doing another.

An environment variable carrying the prefix is refused the same way. That one is
narrower than it looks and the limit is stated in
`docs/configuration.md`: only names starting with ``RETUSCHE_`` are looked at,
so a variable misspelled outside the prefix is invisible to this and always will
be.

A setting with no default and no value refuses the load. There is no state in
which such a setting takes a value nobody wrote.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

from retusche.config.settings import (
    ENVIRONMENT_PREFIX,
    SETTINGS,
    Kind,
    Setting,
    environment_name,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "REDACTED",
    "Configuration",
    "ConfigurationError",
    "load",
]

REDACTED = "<redacted>"
"""What a secret reads as everywhere a configuration is rendered."""

Value = str | int | bool | Path
"""What a parsed setting holds. `Path` for a path, `str` for text and secrets."""


class ConfigurationError(Exception):
    """A configuration the service refuses, with every problem in the message."""


class Configuration:
    """The settings, parsed, with the kind checked at every read.

    The accessors are typed rather than one ``get`` returning a union, so a
    caller that reads a path as a number is refused here instead of producing a
    `TypeError` somewhere the setting's name is no longer in scope.
    """

    def __init__(
        self, values: Mapping[str, Value], settings: tuple[Setting, ...]
    ) -> None:
        self._values = dict(values)
        self._settings = {setting.name: setting for setting in settings}

    def text(self, name: str) -> str:
        """The value of a text or secret setting."""
        return cast("str", self._checked(name, (Kind.TEXT, Kind.SECRET)))

    def integer(self, name: str) -> int:
        """The value of an integer setting."""
        return cast("int", self._checked(name, (Kind.INTEGER,)))

    def boolean(self, name: str) -> bool:
        """The value of a boolean setting."""
        return cast("bool", self._checked(name, (Kind.BOOLEAN,)))

    def path(self, name: str) -> Path:
        """The value of a path setting."""
        return cast("Path", self._checked(name, (Kind.PATH,)))

    def effective_lines(self) -> tuple[str, ...]:
        """The configuration in force, one line per setting, secrets redacted.

        Redaction is decided by the kind in the declaration and never by the
        caller, so a setting that becomes a secret later is redacted everywhere
        at once rather than everywhere somebody remembered.
        """
        return tuple(
            f"{setting.name} = {REDACTED}"
            if setting.kind is Kind.SECRET
            else f"{setting.name} = {self._values[setting.name]}"
            for setting in self._settings.values()
        )

    def _checked(self, name: str, kinds: tuple[Kind, ...]) -> Value:
        """The value, once the read agrees with the declaration.

        The cast in each accessor above is sound because `_coerce` is the only
        producer of these values and it produces the type the kind names. The
        check here is on the kind rather than on the object, so the refusal
        names the declaration a caller disagreed with.
        """
        setting = self._settings.get(name)
        if setting is None:
            raise ConfigurationError(
                f"{name} is not a setting this project declares. The declared "
                f"set is retusche.config.settings.SETTINGS, and a name read "
                f"from anywhere else is a setting nothing validated."
            )
        if setting.kind not in kinds:
            raise ConfigurationError(
                f"{name} is declared as {setting.kind} and is being read as "
                f"{kinds[0]}. The declaration is what an operator was told the "
                f"setting is, so it is the declaration that wins."
            )
        return self._values[name]


def load(
    *,
    file_text: str | None = None,
    environment: Mapping[str, str] | None = None,
    overrides: Mapping[str, str] | None = None,
    settings: tuple[Setting, ...] = SETTINGS,
) -> Configuration:
    """The whole configuration, or a refusal naming every problem in it.

    ``file_text`` is the contents of the configuration file rather than its
    path, because reading a file is the entry point's work and this way the
    loader is exercised without one. ``settings`` is a parameter so the suite
    can hold a declaration to a fixture set rather than to whatever the tree
    happens to declare today.
    """
    declared = {setting.name: setting for setting in settings}
    problems: list[str] = []
    raw: dict[str, object] = {}
    for source, values in (
        ("the configuration file", _from_file(file_text, problems)),
        ("the environment", _from_environment(environment or {}, declared, problems)),
        ("the overrides", dict(overrides or {})),
    ):
        for name, value in values.items():
            if name not in declared:
                problems.append(_unknown(name, source, declared))
                continue
            raw[name] = value
    parsed: dict[str, Value] = {}
    for name, setting in declared.items():
        written = raw.get(name, setting.default)
        if written is None:
            problems.append(
                f"{setting.name} has no value and no default, so the service "
                f"does not start without it. Write it in the configuration "
                f"file, or set {environment_name(setting)}. {setting.summary}"
            )
            continue
        try:
            parsed[name] = _coerce(setting, written)
        except ConfigurationError as refusal:
            problems.append(str(refusal))
    if problems:
        raise ConfigurationError(
            f"this configuration was refused, with "
            f"{len(problems)} problem(s) rather than the first one, so a "
            f"deployment is corrected once:\n"
            + "\n".join(f"  - {problem}" for problem in sorted(problems))
        )
    return Configuration(parsed, settings)


def _from_file(file_text: str | None, problems: list[str]) -> dict[str, object]:
    """The file as a flat table, or a problem saying it could not be read."""
    if file_text is None:
        return {}
    try:
        return dict(tomllib.loads(file_text))
    except tomllib.TOMLDecodeError as error:
        problems.append(
            f"the configuration file is not readable as TOML, so nothing in it "
            f"was applied and every setting it carries is at its default or "
            f"absent. {error}"
        )
        return {}


def _from_environment(
    environment: Mapping[str, str],
    declared: Mapping[str, Setting],
    problems: list[str],
) -> dict[str, object]:
    """Every ``RETUSCHE_`` variable, refusing one that names no setting."""
    by_variable = {
        environment_name(setting): setting.name for setting in declared.values()
    }
    found: dict[str, object] = {}
    for variable, value in environment.items():
        if not variable.startswith(ENVIRONMENT_PREFIX):
            continue
        name = by_variable.get(variable)
        if name is None:
            problems.append(
                f"{variable} is set and names no setting this project "
                f"declares. A variable carrying the {ENVIRONMENT_PREFIX} prefix "
                f"and no matching setting is a typo that would otherwise leave "
                f"the setting at whatever it had. The declared variables are "
                f"{', '.join(sorted(by_variable))}."
            )
            continue
        found[name] = value
    return found


def _unknown(name: str, source: str, declared: Mapping[str, Setting]) -> str:
    """The refusal for a name nothing reads, which is how a typo goes silent."""
    return (
        f"{name}, in {source}, is not a setting this project declares. It would "
        f"otherwise do nothing while reading as though it had, and the setting "
        f"it was meant to be would keep the value nobody chose. The declared "
        f"settings are {', '.join(sorted(declared))}."
    )


def _coerce(setting: Setting, written: object) -> Value:
    """One value as its declared kind, or a refusal naming both."""
    if setting.kind is Kind.BOOLEAN:
        return _boolean(setting, written)
    if setting.kind is Kind.INTEGER:
        return _integer(setting, written)
    if not isinstance(written, str):
        raise _refused(setting, written, "a string")
    if setting.kind is Kind.PATH:
        return Path(written)
    return written


def _boolean(setting: Setting, written: object) -> bool:
    if isinstance(written, bool):
        return written
    if written == "true":
        return True
    if written == "false":
        return False
    raise _refused(setting, written, "true or false, spelled in lower case")


def _integer(setting: Setting, written: object) -> int:
    if isinstance(written, bool):
        raise _refused(setting, written, "a whole number and not true or false")
    if isinstance(written, int):
        return written
    if isinstance(written, str) and _is_whole_number(written):
        return int(written)
    raise _refused(setting, written, "a whole number")


def _is_whole_number(written: str) -> bool:
    body = written.removeprefix("-")
    return body.isdigit() and body.isascii()


def _refused(setting: Setting, written: object, wanted: str) -> ConfigurationError:
    return ConfigurationError(
        f"{setting.name} is {written!r}, and this setting is {wanted}. It is "
        f"measured in {setting.unit}."
    )
