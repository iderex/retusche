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

import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from retusche.models.registry import (
    Access,
    Licence,
    ModelEntry,
    RegistryError,
    entry_from_mapping,
    load_registry,
    pinned_revision,
)
from retusche_contracts.engine import Operation

if TYPE_CHECKING:
    from collections.abc import Mapping

_DIGEST = "sha256:" + "ab" * 32
_COMMIT = "3f6a1c0d9b8e7a6f5d4c3b2a1908f7e6d5c4b3a2"
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

[access]
gated = false
obtain = ""
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


def _with_access(**changes: object) -> dict[str, Any]:
    raw = _complete()
    raw["access"] = {**raw["access"], **changes}
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
        access=Access(gated=False, obtain=""),
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
        "access",
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
    "source",
    [
        f"https://example.invalid/example-erase-small/resolve/{_COMMIT}/model.onnx",
        f"https://example.invalid/example-erase-small/resolve/{'a1' * 32}/model.onnx",
        f"https://example.invalid/example-erase-small/raw/{_COMMIT}/model.onnx",
        f"https://example.invalid/download?file=model.onnx&revision={_COMMIT}",
    ],
)
def test_a_source_pinned_to_a_whole_commit_hash_is_accepted(source: str) -> None:
    """Both hash lengths, and both forms a revision is written in."""
    assert entry_from_mapping(_with("source", source), "example.toml").source == source


@pytest.mark.parametrize(
    "revision",
    [
        "main",
        "master",
        "v1.4.0",
        _COMMIT[:7],
        _COMMIT.upper(),
    ],
)
@pytest.mark.parametrize("segment", ["resolve", "blob", "raw"])
def test_a_source_naming_a_revision_that_can_move_is_refused(
    revision: str, segment: str
) -> None:
    """The near miss is `resolve/main`, which is what a model host hands you.

    Copying the download URL out of a browser gives that shape, the entry loads
    everywhere it is read, and the digest beside it makes the whole record look
    pinned. `v1.4.0` is the same mistake wearing an immutable-looking name: a
    tag is a pointer and it can be moved. The abbreviated hash is unambiguous in
    the repository it was shortened against and stops being so as that
    repository grows, and the upper-case one is the same defect as an
    upper-case digest, two spellings of one artefact.
    """
    source = f"https://example.invalid/erase/{segment}/{revision}/model.onnx"
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("source", source), "example.toml")
    assert revision in str(refused.value)
    assert "example.toml" in str(refused.value)


def test_a_revision_named_by_a_query_key_is_read_too() -> None:
    """Where the path does not carry it, the query does, and it is read there."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(
            _with("source", "https://example.invalid/download?ref=main"), "example.toml"
        )
    assert "main" in str(refused.value)


@pytest.mark.parametrize(
    "source",
    [
        "https://example.invalid/example/model.onnx",
        "https://example.invalid/example/model.onnx?download=true",
        "https://example.invalid/resolve",
    ],
)
def test_a_source_whose_form_names_no_revision_is_left_alone(source: str) -> None:
    """A URL this registry cannot read a revision out of is not guessed at.

    Including the last one, where the marker segment is the end of the path and
    nothing follows it. Refusing these would be refusing every source that is a
    plain file on a host, and what pins the bytes there is the digest.
    """
    assert entry_from_mapping(_with("source", source), "example.toml").source == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (f"https://example.invalid/erase/resolve/{_COMMIT}/model.onnx", _COMMIT),
        ("https://example.invalid/erase/blob/main/model.onnx", "main"),
        (
            "https://example.invalid/erase/resolve/refs%2Fheads%2Fmain/m",
            "refs/heads/main",
        ),
        ("https://example.invalid/download?rev=main", "main"),
        ("https://example.invalid/download?file=m.onnx", None),
        ("https://example.invalid/erase/model.onnx", None),
    ],
)
def test_the_revision_a_source_names_is_readable_on_its_own(
    source: str, expected: str | None
) -> None:
    """The reader an operator's comparison is built on, asked directly.

    It is separate from the refusal because #44's reporting half needs the
    revision an entry pins rather than a verdict on it, and a reader that only
    existed inside the refusal would be written a second time there.
    """
    assert pinned_revision(source) == expected


def test_every_shipped_entry_pins_an_immutable_reference(
    shipped_registry: Mapping[str, ModelEntry],
) -> None:
    """No entry in this tree names a reference that can move under its digest.

    Today this is an assertion over an empty set, for the reason the load test
    below gives, and it is written so that it becomes load-bearing on the day a
    file appears in that directory rather than being remembered then. The
    loader refuses such an entry, so a moving reference cannot reach the
    directory this reads; asserting it here as well is what the issue asks for
    and it is the line that would survive the loader being widened.
    """
    for entry in shipped_registry.values():
        revision = pinned_revision(entry.source)
        assert revision is None or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision)


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


def test_a_gated_entry_loads_with_what_the_operator_has_to_do() -> None:
    """The entry this field exists for. What is recorded is the step between
    reading the terms and holding the file, and it is a sentence rather than a
    flag, because a flag tells an operator that something is in the way and not
    what to do about it."""
    entry = entry_from_mapping(
        _with_access(
            gated=True,
            obtain=(
                "Sign in at the model host, open the model page, and accept the "
                "licence there. The download stays refused until you have."
            ),
        ),
        "example.toml",
    )
    assert entry.access.gated
    assert "accept the licence" in entry.access.obtain


def test_a_gated_entry_that_says_nothing_about_access_is_refused() -> None:
    """The failure this whole field is for. Without the sentence, the fetch is
    refused at the source and reaches the operator as a transport error, which
    reads like the host being unavailable."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with_access(gated=True, obtain=""), "example.toml")
    assert "example.toml" in str(refused.value)
    assert "transport error" in str(refused.value)


def test_a_gated_entry_whose_instructions_are_whitespace_is_refused() -> None:
    """The one-character version of the same mistake. A space passes every check
    that asks whether the key is present and whether its value is a string."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with_access(gated=True, obtain="   "), "example.toml")
    assert "transport error" in str(refused.value)


def test_an_ungated_entry_carrying_instructions_is_refused() -> None:
    """The contradiction read the other way, and it is what a copied entry
    produces: the instructions survive the copy and the flag does not. One of the
    two fields is wrong and the file cannot say which."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(
            _with_access(gated=False, obtain="Accept the licence at the source."),
            "example.toml",
        )
    assert "not gated" in str(refused.value)
    assert "Accept the licence at the source." in str(refused.value)


@pytest.mark.parametrize("value", ["true", "yes", 1, 0, "no", "false"])
def test_a_gate_that_is_not_a_boolean_is_refused(value: object) -> None:
    """`gated = "no"` is the near miss, and it is worse than a missing key: every
    reading that treats a non-empty string as true reads it as gated, and every
    reading that does not reads it as open."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with_access(gated=value), "example.toml")
    assert "access.gated" in str(refused.value)
    assert "true or false" in str(refused.value)


def test_instructions_that_are_not_a_string_are_refused() -> None:
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with_access(gated=True, obtain=17), "example.toml")
    assert "access.obtain" in str(refused.value)


@pytest.mark.parametrize("key", ["gated", "obtain"])
def test_an_access_table_missing_either_field_is_refused(key: str) -> None:
    raw = _complete()
    del raw["access"][key]
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(raw, "example.toml")
    assert f"access.{key}" in str(refused.value)


def test_an_unknown_key_in_the_access_table_is_refused() -> None:
    """The misspelling that leaves the entry looking complete. `gate` written
    where `gated` was meant declares no gate at all, and the required-key check
    on `gated` is what would then have to catch it."""
    raw = _complete()
    raw["access"] = {"gate": True, "obtain": "Accept the licence at the source."}
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(raw, "example.toml")
    assert "access table" in str(refused.value)
    assert "gate" in str(refused.value)


def test_an_access_written_as_one_value_is_refused() -> None:
    """A gate written as a bare `true` carries whether the model is gated and
    nothing about what to do, which is the half an operator needs."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("access", True), "example.toml")
    assert "access" in str(refused.value)


def test_a_credential_written_into_an_entry_is_refused() -> None:
    """A source credential belongs in configuration and never in the registry,
    which is a reviewable file in a public repository. Nothing special refuses
    it: the entry key check does, because a credential is a key the registry
    does not read."""
    with pytest.raises(RegistryError) as refused:
        entry_from_mapping(_with("token", "hf_examplesecret"), "example.toml")
    assert "token" in str(refused.value)
