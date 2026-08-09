# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the registry loader accepts, and every shape it refuses.

The refusals are the point of this file. A registry that loads a complete entry
is not the property #38 asks for; the property is that there is no state in
which an incomplete one loads, and each way of being incomplete has to be shown
being refused rather than assumed to be.

Every fixture below starts from one entry that loads and breaks exactly one
thing about it, so a refusal is attributable to the change that caused it. A
fixture that broke two would pass for the wrong reason on the day one of the two
stopped being refused.

The near miss the field checks are aimed at is not a missing key, which anybody
would notice. It is the misspelled one: `licence_url` written where `url` was
meant leaves the entry looking complete while it declares no link to the terms.

No device, no display and no elevation is needed by anything here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from retusche.models.registry import (
    Licence,
    ModelEntry,
    RegistryError,
    entry_from_mapping,
    load_registry,
)
from retusche_contracts.engine import Operation

if TYPE_CHECKING:
    from collections.abc import Mapping

_DIGEST = "sha256:" + "ab" * 32
_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def shipped_registry_path() -> Path:
    """Where this repository keeps its registry, off this file's own location.

    Kept here rather than in the shared conftest. One test module needs it, and
    a fixture in the shared file would be a thing every other module carries the
    import cost and the name of.
    """
    return _REPO_ROOT / "models" / "registry"


@pytest.fixture
def shipped_registry(shipped_registry_path: Path) -> Mapping[str, ModelEntry]:
    """The registry as this tree ships it, keyed by identifier."""
    return {entry.identifier: entry for entry in load_registry(shipped_registry_path)}


_COMPLETE = f"""
identifier = "example-erase-small"
source = "https://example.invalid/example/model.onnx"
digest = "{_DIGEST}"
size_bytes = 104857600
device_memory_bytes = 2147483648
engine = "example-erase"
operations = ["erase", "fill"]

[licence]
identifier = "Apache-2.0"
url = "https://www.apache.org/licenses/LICENSE-2.0"
"""


def _complete() -> dict[str, Any]:
    """One entry that loads, parsed fresh so a test cannot mutate another's."""
    return tomllib.loads(_COMPLETE)


def _without(key: str) -> dict[str, Any]:
    raw = _complete()
    del raw[key]
    return raw


def _with(key: str, value: object) -> dict[str, Any]:
    raw = _complete()
    raw[key] = value
    return raw


def _with_licence(**changes: object) -> dict[str, Any]:
    raw = _complete()
    raw["licence"] = {**raw["licence"], **changes}
    return raw


def test_a_complete_entry_loads_with_every_field_read() -> None:
    """The baseline the fixtures below are one change away from."""
    entry = entry_from_mapping(_complete(), "example.toml")
    assert entry == ModelEntry(
        identifier="example-erase-small",
        source="https://example.invalid/example/model.onnx",
        digest=_DIGEST,
        size_bytes=104857600,
        device_memory_bytes=2147483648,
        engine="example-erase",
        operations=frozenset({Operation.ERASE, Operation.FILL}),
        licence=Licence(
            identifier="Apache-2.0",
            url="https://www.apache.org/licenses/LICENSE-2.0",
        ),
    )


@pytest.mark.parametrize(
    "key",
    [
        "identifier",
        "source",
        "digest",
        "size_bytes",
        "device_memory_bytes",
        "engine",
        "operations",
        "licence",
    ],
)
def test_an_entry_missing_any_field_is_refused(key: str) -> None:
    """Every field, one at a time, so none of them is quietly optional."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_without(key), "example.toml")
    assert key in str(refused.value)
    assert "example.toml" in str(refused.value)


def test_the_licence_is_among_the_fields_that_cannot_be_omitted() -> None:
    """Stated on its own because it is the field this issue exists for.

    The parametrisation above covers it, and it covers it because `licence` is
    one string in a list. This says the same thing where a reader deleting that
    string would see it.
    """
    with pytest.raises(RegistryError):
        entry_from_mapping(_without("licence"), "example.toml")


@pytest.mark.parametrize("key", ["identifier", "url"])
def test_a_licence_missing_either_half_is_refused(key: str) -> None:
    """Terms with no link, and a link with no terms, are both incomplete."""
    raw = _complete()
    raw["licence"] = {k: v for k, v in raw["licence"].items() if k != key}
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(raw, "example.toml")
    assert key in str(refused.value)


def test_a_misspelled_key_is_refused_rather_than_ignored() -> None:
    """The near miss: the entry looks complete and declares one field less."""
    raw = _complete()
    raw["licence_url"] = "https://example.invalid/terms"
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(raw, "example.toml")
    assert "licence_url" in str(refused.value)


def test_a_misspelled_key_inside_the_licence_table_is_refused() -> None:
    """The same mistake one level down, where the required half still passes."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(
            _with_licence(link="https://example.invalid/terms"), "example.toml"
        )
    assert "link" in str(refused.value)


@pytest.mark.parametrize("key", ["identifier", "source", "engine"])
@pytest.mark.parametrize("value", ["", "   ", 7])
def test_a_text_field_that_is_empty_or_not_text_is_refused(
    key: str, value: object
) -> None:
    """Present and unanswered reads like answered in every later report."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with(key, value), "example.toml")
    assert key in str(refused.value)


@pytest.mark.parametrize(
    "identifier", ["TBD", "tbd", "  Unknown  ", "n/a", "none", "TODO"]
)
def test_a_placeholder_licence_is_refused(identifier: str) -> None:
    """A registry entry saying TBD ships. One that fails to load does not."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with_licence(identifier=identifier), "example.toml")
    assert "has not been established" in str(refused.value)


def test_a_licence_that_is_a_string_rather_than_a_table_is_refused() -> None:
    """One string carries the terms and not where an operator reads them."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("licence", "Apache-2.0"), "example.toml")
    assert "table" in str(refused.value)


def test_a_named_non_standard_licence_is_accepted() -> None:
    """The other half of the rule, so it refuses absence and not unfamiliarity.

    Some weights this project will offer are under licences that have no
    standard identifier at all. A check that only accepted SPDX identifiers
    would refuse exactly those, which is the set the licence field matters most
    for.
    """
    entry = entry_from_mapping(
        _with_licence(
            identifier="flux-1-dev-non-commercial-license",
            url="https://example.invalid/flux-terms",
        ),
        "example.toml",
    )
    assert entry.licence.identifier == "flux-1-dev-non-commercial-license"


@pytest.mark.parametrize(
    "digest",
    [
        "sha256:" + "AB" * 32,
        "sha256:" + "ab" * 31,
        "ab" * 32,
        "sha512:" + "ab" * 32,
        "sha256:" + "zz" * 32,
    ],
)
def test_a_digest_in_any_other_form_is_refused(digest: str) -> None:
    """Upper case, short, unprefixed, another algorithm, and not hexadecimal."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("digest", digest), "example.toml")
    assert "digest" in str(refused.value)


@pytest.mark.parametrize("key", ["size_bytes", "device_memory_bytes"])
@pytest.mark.parametrize("value", [0, -1, "104857600", 1.5, True])
def test_a_byte_count_that_is_not_a_positive_whole_number_is_refused(
    key: str, value: object
) -> None:
    """Including True, which is an int in Python and a budget of one byte."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with(key, value), "example.toml")
    assert key in str(refused.value)


@pytest.mark.parametrize("value", [[], "erase", {}])
def test_operations_that_are_not_a_non_empty_list_are_refused(value: object) -> None:
    """A model supporting nothing is one the registry offers and nothing uses."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("operations", value), "example.toml")
    assert "operations" in str(refused.value)


def test_an_operation_this_project_does_not_have_is_refused() -> None:
    """The set comes from the contract, so the registry cannot invent one."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("operations", ["erase", "upscale"]), "example.toml")
    assert "upscale" in str(refused.value)
    assert "erase" in str(refused.value)


def _write(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


def test_a_directory_of_entries_loads_in_identifier_order(tmp_path: Path) -> None:
    """Sorted by identifier, so two runs report the same registry the same way."""
    _write(tmp_path, "b.toml", _COMPLETE.replace("example-erase-small", "zebra"))
    _write(tmp_path, "a.toml", _COMPLETE.replace("example-erase-small", "aardvark"))
    assert [entry.identifier for entry in load_registry(tmp_path)] == [
        "aardvark",
        "zebra",
    ]


def test_two_files_declaring_one_identifier_are_refused(tmp_path: Path) -> None:
    """Otherwise a request names whichever the directory happened to yield second."""
    _write(tmp_path, "a.toml", _COMPLETE)
    _write(tmp_path, "b.toml", _COMPLETE.replace("example/model.onnx", "other.onnx"))
    with pytest.raises(RegistryError) as refused:
        load_registry(tmp_path)
    assert "example-erase-small" in str(refused.value)


def test_a_file_that_is_not_toml_is_refused_by_name(tmp_path: Path) -> None:
    """A model in the tree and in no run is the failure this prevents."""
    _write(tmp_path, "broken.toml", "identifier = \nsource =")
    with pytest.raises(RegistryError) as refused:
        load_registry(tmp_path)
    assert "broken.toml" in str(refused.value)


def test_one_incomplete_file_refuses_the_whole_directory(tmp_path: Path) -> None:
    """Loading part of a registry would offer a set nobody declared."""
    _write(tmp_path, "a.toml", _COMPLETE)
    _write(tmp_path, "b.toml", _COMPLETE.replace('identifier = "Apache-2.0"', ""))
    with pytest.raises(RegistryError):
        load_registry(tmp_path)


def test_a_file_that_is_not_toml_at_all_is_left_alone(tmp_path: Path) -> None:
    """Only `.toml` is read, so a note beside the entries is not an entry."""
    _write(tmp_path, "a.toml", _COMPLETE)
    _write(tmp_path, "README.md", "# not an entry")
    assert [entry.identifier for entry in load_registry(tmp_path)] == [
        "example-erase-small"
    ]


def test_the_registry_shipped_in_this_tree_loads(
    shipped_registry: Mapping[str, ModelEntry],
) -> None:
    """Every entry in `models/registry/` loads.

    Today that is an assertion over an empty set, and saying so is the point of
    this docstring: a green line here means the shipped registry holds nothing
    that fails to load, and it does not mean the shipped registry holds
    anything. Which weights are offered is #94's second entry and #43, and an
    entry written before those are answered would answer them by side effect.

    The line becomes load-bearing the moment a file appears in that directory,
    with no change here.
    """
    for identifier, entry in shipped_registry.items():
        assert entry.identifier == identifier
        assert entry.licence.identifier
        assert entry.licence.url


def test_the_shipped_registry_directory_exists_and_is_read(
    shipped_registry_path: Path,
) -> None:
    """The test above over a directory that is not there would pass as loudly."""
    assert shipped_registry_path.is_dir()
    assert (shipped_registry_path / "README.md").is_file()
