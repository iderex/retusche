# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The model registry: what a model entry declares, and what is refused.

A model is not a file to download. It has a source, a digest, a size, a device
memory footprint, an engine that can run it, the operations it supports, and a
licence governing what an operator may do with it. All of that is one declared
record, and the licence is the field that must not be optional: weights carry
their own terms, those terms are not the licence of the code that runs them, and
some of them forbid exactly the use an operator has in mind.

The registry is data. One TOML file per model under `models/registry/`, so
adding a model is a reviewable change to a file rather than to code, and two
models arriving at once do not meet in the same file.

Refusable by construction
-------------------------
There is no state in which a model without a recorded licence is loaded.
`ModelEntry` has no default for any field, `Licence` has none either, and the
loader refuses a mapping that omits a key rather than filling one in. A field
that could be defaulted is a field that will be, on the entry where it mattered.

An unknown key is refused as well, which is the half a required-field check
misses. `licence_url` written where `url` was meant satisfies every "is this key
present" test on the keys it does check, and the entry then declares no link to
the terms while looking complete.

What is not judged here
-----------------------
Whether a licence identifier is a real SPDX identifier. Deciding that needs the
SPDX list, which this tree does not carry, and a copy of it here would drift
against the list it was taken from. What is refused instead is the absence: an
empty identifier, and the placeholders somebody writes when they mean to come
back to it. A named non-standard licence is accepted as it stands, because the
weights this project will offer include licences that have no standard
identifier at all.

Whether the engine named by an entry exists. There is no engine in this tree
yet, and a registry that refused every entry until one arrived would be a
registry nothing could be written for. #18 and #19 build the engines, and the
check that an entry names one of them belongs where there is a set to check
against.

Whether the digest is the digest of the artefact at the source. That is a
download and a hash, which is #39's, and nothing here reaches the network.

Whether a source that declares no revision points at something stable. Only two
URL forms declare one at all, and a source written in any other shape carries
nothing for `pinned_revision` to read, so nothing is refused there. What pins
the bytes in that case is the digest alone, which turns a moved artefact into a
verification failure rather than a different result. The revision check is the
half that turns that failure into a refusal before anybody downloads anything,
and it is a floor over the forms this project's sources are written in rather
than a statement about every URL.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import parse_qsl, unquote, urlsplit

from retusche_contracts.engine import Operation

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = [
    "Licence",
    "ModelEntry",
    "RegistryError",
    "entry_from_mapping",
    "load_registry",
    "pinned_revision",
]

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
"""The one digest form entries carry.

Lower case and fixed length so two records of one artefact cannot differ by
spelling, and prefixed with the algorithm so the day a second one is accepted
the existing entries do not have to be guessed at.
"""

_IMMUTABLE_REVISION = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
"""A revision that cannot be moved: a whole commit hash, in lower case.

Forty digits is the sha-1 form and sixty-four the sha-256 one, and both are
accepted because which a host uses is the host's choice rather than this
registry's. An abbreviated hash is not accepted: it is unambiguous in the
repository it was abbreviated against and stops being so as that repository
grows, which is the same defect as a branch name arriving later.
"""

_REVISION_SEGMENTS: Final = frozenset({"blob", "raw", "resolve", "tree"})
"""Path segments after which a model host names the revision it serves from."""

_REVISION_QUERY_KEYS: Final = frozenset({"ref", "rev", "revision"})
"""Query keys that name the same thing where the path does not."""

_PLACEHOLDERS: Final = frozenset(
    {
        "?",
        "n/a",
        "na",
        "none",
        "pending",
        "tbc",
        "tbd",
        "todo",
        "unknown",
        "unspecified",
    }
)
"""Licence identifiers that record that nobody looked.

Compared case-insensitively. This is a floor rather than a guarantee: it holds
the spellings people actually write, and somebody who wants to defeat it can. It
is here because those spellings pass every check that only asks whether a field
is present, and a registry entry saying `TBD` is worse than one that fails to
load, because it ships.
"""

_LICENCE_FIELDS: Final = ("identifier", "url")
_ENTRY_FIELDS: Final = (
    "identifier",
    "source",
    "digest",
    "size_bytes",
    "device_memory_bytes",
    "engine",
    "operations",
    "licence",
)


class RegistryError(Exception):
    """A registry file the loader refuses, with the reason in the message."""


@dataclass(frozen=True, slots=True)
class Licence:
    """The terms the weights themselves are under, and where to read them."""

    identifier: str
    """A standard identifier where one exists, a named licence where none does."""

    url: str
    """Where the text of those terms is published."""


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """One model, complete. Every field is required and none has a default."""

    identifier: str
    """What this project calls the model, and what a request names."""

    source: str
    """Where the artefact is fetched from. #39 verifies what arrives.

    Where the URL declares a revision, that revision is an immutable one, so
    the entry names one artefact rather than whatever a branch points at on the
    day of the fetch."""

    digest: str
    """``sha256:`` and sixty-four lower-case hexadecimal digits."""

    size_bytes: int
    """The artefact on disk, for the disk budget in #41."""

    device_memory_bytes: int
    """The declared footprint of the loaded weights, which admission reads
    before a job reaches the device. Declared here and measured in #85; the two
    are different numbers and this is the declared one."""

    engine: str
    """The ``engine_id`` of the engine that can run this model."""

    operations: frozenset[Operation]
    """What this model can be asked for, from the contract's own enumeration
    rather than from strings this module invents."""

    licence: Licence
    """The terms of the weights. There is no entry without one."""


def entry_from_mapping(raw: Mapping[str, Any], origin: str) -> ModelEntry:
    """One parsed registry file as an entry, or a refusal naming the file.

    ``origin`` is what the message points a reader at. It is passed in rather
    than derived, so this function can be exercised against mappings this
    project's own suite writes, with no file behind them.
    """
    _refuse_unexpected_keys(raw, _ENTRY_FIELDS, origin, "entry")
    raw_licence = _mapping(raw, "licence", origin)
    _refuse_unexpected_keys(raw_licence, _LICENCE_FIELDS, origin, "licence table")
    licence = Licence(
        identifier=_licence_identifier(raw_licence, origin),
        url=_text(raw_licence, "url", origin, "licence."),
    )
    return ModelEntry(
        identifier=_text(raw, "identifier", origin, ""),
        source=_source(raw, origin),
        digest=_digest(raw, origin),
        size_bytes=_positive(raw, "size_bytes", origin),
        device_memory_bytes=_positive(raw, "device_memory_bytes", origin),
        engine=_text(raw, "engine", origin, ""),
        operations=_operations(raw, origin),
        licence=licence,
    )


def load_registry(directory: Path) -> tuple[ModelEntry, ...]:
    """Every entry under ``directory``, by identifier, or the first refusal.

    Read off the directory rather than out of an index file. An index is a
    second place for the set to be declared, and the failure it produces is a
    model present in the tree and absent from every run, which nothing reports.
    """
    entries: dict[str, ModelEntry] = {}
    for path in sorted(directory.glob("*.toml")):
        origin = path.name
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise RegistryError(
                f"{origin}: this registry file is not readable as TOML, so the "
                f"model it declares is in the tree and in no run. {error}"
            ) from error
        entry = entry_from_mapping(raw, origin)
        if entry.identifier in entries:
            raise RegistryError(
                f"{origin}: the identifier {entry.identifier!r} is already "
                f"declared by another file in this registry. Two entries under "
                f"one name means a request names whichever the loader read "
                f"second, and which that is depends on the order of the "
                f"directory."
            )
        entries[entry.identifier] = entry
    return tuple(entries[key] for key in sorted(entries))


def pinned_revision(source: str) -> str | None:
    """The revision a source names, or ``None`` where its form names none.

    Two forms are read. A model host serves a file at a revision under a path
    segment, ``.../resolve/<revision>/<file>`` and its neighbours, and where the
    path does not carry it a query key does. Anything else is a URL this
    registry cannot take a revision out of, and ``None`` says that rather than
    guessing one.

    It is public because the revision an entry pins is the half an operator has
    to be able to compare against what is installed, which is the reporting #44
    asks for and #39 fetches against. A reader that existed only inside the
    refusal below would be reimplemented there.
    """
    parsed = urlsplit(source)
    segments = parsed.path.split("/")
    for index, segment in enumerate(segments[:-1]):
        if segment in _REVISION_SEGMENTS:
            return unquote(segments[index + 1])
    for key, value in parse_qsl(parsed.query):
        if key in _REVISION_QUERY_KEYS:
            return value
    return None


def _refuse_unexpected_keys(
    raw: Mapping[str, Any], expected: tuple[str, ...], origin: str, what: str
) -> None:
    """Refuse a key nothing reads, which is how a required field goes missing."""
    unexpected = sorted(set(raw) - set(expected))
    if unexpected:
        raise RegistryError(
            f"{origin}: the {what} declares keys this registry does not read: "
            f"{', '.join(unexpected)}. A misspelled key is not a spare key: the "
            f"field it was meant to be is then absent, and the entry looks "
            f"complete. The keys read are {', '.join(expected)}."
        )


def _required(raw: Mapping[str, Any], key: str, origin: str, prefix: str) -> Any:
    """The value under ``key``, or a refusal saying what its absence costs."""
    if key not in raw:
        raise RegistryError(
            f"{origin}: this entry declares no {prefix}{key}. Every field of a "
            f"registry entry is required and none of them has a default, "
            f"because a field that can be defaulted is one that will be, on the "
            f"entry where it mattered."
        )
    return raw[key]


def _text(raw: Mapping[str, Any], key: str, origin: str, prefix: str) -> str:
    """A non-empty string, refusing both the wrong type and the empty one."""
    value = _required(raw, key, origin, prefix)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(
            f"{origin}: {prefix}{key} is {value!r}, and a non-empty string is "
            f"what this field is. An empty value records that the field was "
            f"reached for and not filled in, which reads in every later report "
            f"exactly like a field that was answered."
        )
    return value


def _mapping(raw: Mapping[str, Any], key: str, origin: str) -> Mapping[str, Any]:
    """A sub-table, refusing the shape a flattened key would produce."""
    value = _required(raw, key, origin, "")
    if not isinstance(value, dict):
        raise RegistryError(
            f"{origin}: {key} is {value!r} and this registry reads it as a "
            f"table. A licence written as one string carries the terms and not "
            f"where to read them, and an operator cannot check what they were "
            f"told."
        )
    return value


def _licence_identifier(raw: Mapping[str, Any], origin: str) -> str:
    """The licence identifier, refusing the spellings that mean nobody looked."""
    identifier = _text(raw, "identifier", origin, "licence.")
    if identifier.strip().lower() in _PLACEHOLDERS:
        raise RegistryError(
            f"{origin}: licence.identifier is {identifier!r}, which records "
            f"that the licence of these weights has not been established. An "
            f"entry that ships saying this offers an operator a model whose "
            f"terms nobody has read. A standard identifier where one exists, "
            f"and the name of the licence where none does."
        )
    return identifier


def _source(raw: Mapping[str, Any], origin: str) -> str:
    """The source, refusing one whose revision can be moved under the entry."""
    source = _text(raw, "source", origin, "")
    revision = pinned_revision(source)
    if revision is not None and _IMMUTABLE_REVISION.match(revision) is None:
        raise RegistryError(
            f"{origin}: source names the revision {revision!r}, and a branch, a "
            f"tag and an abbreviated hash can all be made to point somewhere "
            f"else after this entry is written. The digest would then refuse "
            f"the artefact that arrives, so the operator who installs this "
            f"model second gets a verification failure and an entry that reads "
            f"as correct. A whole commit hash in lower-case hexadecimal names "
            f"one artefact, and changing which one is then a change to this "
            f"file with a reason in it."
        )
    return source


def _digest(raw: Mapping[str, Any], origin: str) -> str:
    """The digest, in the one form entries carry."""
    digest = _text(raw, "digest", origin, "")
    if _DIGEST.match(digest) is None:
        raise RegistryError(
            f"{origin}: digest is {digest!r}, and this registry carries "
            f"'sha256:' followed by sixty-four lower-case hexadecimal digits. "
            f"Two records of one artefact that differ by spelling are two "
            f"artefacts to everything that compares them. Nothing here checks "
            f"that the digest is the artefact's; that is a download and a hash, "
            f"and it is #39's."
        )
    return digest


def _positive(raw: Mapping[str, Any], key: str, origin: str) -> int:
    """A count of bytes, refusing zero, a negative, and the boolean True."""
    value = _required(raw, key, origin, "")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RegistryError(
            f"{origin}: {key} is {value!r}, and a positive whole number of "
            f"bytes is what this field is. Zero and a missing value are the "
            f"same number to a budget that adds these up, and a budget that "
            f"admits a model of no size admits every model."
        )
    return value


def _operations(raw: Mapping[str, Any], origin: str) -> frozenset[Operation]:
    """The declared operations, read against the contract's own enumeration."""
    value = _required(raw, "operations", origin, "")
    if not isinstance(value, list) or not value:
        raise RegistryError(
            f"{origin}: operations is {value!r}, and a non-empty list is what "
            f"this field is. A model that supports nothing is one the registry "
            f"offers and no request can use."
        )
    declared: set[Operation] = set()
    for entry in value:
        try:
            declared.add(Operation(entry))
        except ValueError as error:
            raise RegistryError(
                f"{origin}: operations names {entry!r}, which is not one this "
                f"project has. The set is Operation in retusche_contracts, "
                f"which is what an engine is asked for and what the queue "
                f"admits against: "
                f"{', '.join(sorted(str(member) for member in Operation))}."
            ) from error
    return frozenset(declared)
