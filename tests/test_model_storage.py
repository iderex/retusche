# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the model store refuses, and what it says when it refuses it.

Three properties are worth more than the rest of this file. A fetch that would
put the store over the operator's ceiling is refused before it starts, and its
message carries both numbers, so the operator can tell which of the two repairs
applies. A fetch onto a volume with less free space than the artefact needs is
refused for a different reason with a different message, because sending
somebody to edit a budget that was never the problem is worse than not answering
at all. And an identifier that would become a path outside the store never
becomes a path.

The near miss most of the identifier cases are aimed at is not a name full of
punctuation, which nobody writes. It is the plausible one: `Lama-Large`, which
is one directory on the machine it was written on and two on the machine it is
deployed to, and `weights/lama`, which reads like a namespace and is a
separator.

Free space is the only thing here a temporary directory cannot arrange, so it is
the only thing supplied by the test rather than measured. Everything else runs
against real files under `tmp_path`.

No device, no display, no elevation and no network is needed by anything here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from retusche.models.registry import Access, Licence, ModelEntry
from retusche.models.storage import (
    INCOMING_SUFFIX,
    ModelStore,
    NotEnoughSpaceError,
    NotInstalledError,
    OverDiskBudgetError,
    UnusableIdentifierError,
    free_bytes_at,
)
from retusche_contracts.engine import Operation

_HEX = "ab" * 32
_OTHER_HEX = "cd" * 32


def _entry(
    identifier: str = "lama-large",
    size_bytes: int = 1000,
    digest_hex: str = _HEX,
) -> ModelEntry:
    """One complete entry, with only the fields this module reads varying.

    Built here rather than imported from the registry's own tests, so a change
    to what that file considers a good entry cannot silently change what this
    one is asserting about a budget.
    """
    return ModelEntry(
        identifier=identifier,
        source="https://example.invalid/resolve/" + "0" * 40 + "/weights",
        digest="sha256:" + digest_hex,
        size_bytes=size_bytes,
        device_memory_bytes=2000,
        engine="fake",
        operations=frozenset({Operation.ERASE}),
        licence=Licence(identifier="apache-2.0", url="https://example.invalid/l"),
        access=Access(gated=False, obtain=""),
    )


def _install(store: ModelStore, entry: ModelEntry, size: int) -> Path:
    """Put an artefact of a stated size where a finished fetch would leave it."""
    path = store.artefact_path(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    return path


def _plenty(_: Path) -> int:
    """A volume with more room than any fixture here asks for."""
    return 1_000_000_000


def test_the_layout_is_one_directory_per_model_and_one_file_per_digest(
    tmp_path: Path,
) -> None:
    """The path an operator is told to look at is the path the store uses."""
    store = ModelStore(tmp_path / "store", budget_bytes=10_000)
    entry = _entry()

    assert store.directory_for("lama-large") == tmp_path / "store" / "lama-large"
    assert store.artefact_path(entry) == tmp_path / "store" / "lama-large" / _HEX


def test_the_artefact_name_drops_the_algorithm_prefix(tmp_path: Path) -> None:
    """A colon is not a character a file name may carry on both platforms."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    assert ":" not in store.artefact_path(_entry()).name


def test_an_unfinished_fetch_never_has_the_finished_name(tmp_path: Path) -> None:
    """The property the suffix exists for, asserted rather than described."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    entry = _entry()

    incoming = store.incoming_path(entry)

    assert incoming != store.artefact_path(entry)
    assert incoming.name.endswith(INCOMING_SUFFIX)
    assert incoming.parent == store.artefact_path(entry).parent


def test_a_re_pinned_entry_is_a_different_file_in_the_same_directory(
    tmp_path: Path,
) -> None:
    """New bytes under one identifier do not overwrite the old artefact."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    old = _entry(digest_hex=_HEX)
    new = _entry(digest_hex=_OTHER_HEX)

    assert store.artefact_path(old) != store.artefact_path(new)
    assert store.artefact_path(old).parent == store.artefact_path(new).parent


def test_holds_answers_for_the_exact_digest_and_not_for_the_identifier(
    tmp_path: Path,
) -> None:
    """Answering yes on the identifier alone hands a loader the old weights."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    installed = _entry(digest_hex=_HEX)
    re_pinned = _entry(digest_hex=_OTHER_HEX)
    _install(store, installed, size=10)

    assert store.holds(installed)
    assert not store.holds(re_pinned)


def test_an_empty_store_holds_nothing_and_is_not_an_error(tmp_path: Path) -> None:
    """The state before the first model is installed is an ordinary one."""
    store = ModelStore(tmp_path / "absent", budget_bytes=10_000)

    assert store.installed() == ()
    assert store.used_bytes() == 0


def test_installed_lists_the_directories_and_ignores_loose_files(
    tmp_path: Path,
) -> None:
    """A file dropped in the store's root is not a model that is installed."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    _install(store, _entry(identifier="sdxl-inpaint"), size=10)
    _install(store, _entry(identifier="lama-large"), size=10)
    (tmp_path / "notes.txt").write_text("left here by somebody", encoding="utf-8")

    assert store.installed() == ("lama-large", "sdxl-inpaint")


def test_used_bytes_counts_what_is_there_rather_than_what_was_declared(
    tmp_path: Path,
) -> None:
    """A store filled with half-written fetches is a full store.

    The entry declares a thousand bytes and the file on disk is four hundred, so
    a number read off the declaration would be wrong in the direction that keeps
    a budget green while a disk fills.
    """
    store = ModelStore(tmp_path, budget_bytes=10_000)
    entry = _entry(size_bytes=1000)
    _install(store, entry, size=400)
    incoming = store.incoming_path(entry)
    incoming.write_bytes(b"\0" * 250)

    assert store.used_bytes() == 650


def test_room_is_given_when_the_artefact_fits_the_budget_and_the_disk(
    tmp_path: Path,
) -> None:
    """The path that returns, so the refusals below are attributable."""
    store = ModelStore(tmp_path, budget_bytes=10_000, free_space=_plenty)

    store.room_for(_entry(size_bytes=1000))


def test_an_artefact_larger_than_the_whole_budget_is_refused_before_a_fetch(
    tmp_path: Path,
) -> None:
    """Both numbers, and the fact that removing other models would not help."""
    store = ModelStore(tmp_path, budget_bytes=500, free_space=_plenty)
    entry = _entry(size_bytes=1000)

    with pytest.raises(OverDiskBudgetError) as refusal:
        store.room_for(entry)

    assert refusal.value.budget_bytes == 500
    assert refusal.value.used_bytes == 0
    assert "1000" in str(refusal.value)
    assert "500" in str(refusal.value)
    assert "does not fit in the whole budget" in str(refusal.value)


def test_an_artefact_that_fits_only_once_something_is_removed_is_refused(
    tmp_path: Path,
) -> None:
    """A different sentence, because a different repair is the one available."""
    store = ModelStore(tmp_path, budget_bytes=1500, free_space=_plenty)
    _install(store, _entry(identifier="lama-large"), size=1000)

    with pytest.raises(OverDiskBudgetError) as refusal:
        store.room_for(_entry(identifier="sdxl-inpaint", size_bytes=1000))

    assert refusal.value.used_bytes == 1000
    assert "removing a model this host no longer needs" in str(refusal.value)


def test_the_budget_refusal_happens_with_nothing_written(tmp_path: Path) -> None:
    """Refused before it starts means there is nothing to clean up."""
    store = ModelStore(tmp_path, budget_bytes=500, free_space=_plenty)
    entry = _entry(size_bytes=1000)

    with pytest.raises(OverDiskBudgetError):
        store.room_for(entry)

    assert store.installed() == ()
    assert not store.directory_for(entry.identifier).exists()


def test_a_volume_with_less_free_than_the_artefact_needs_is_refused(
    tmp_path: Path,
) -> None:
    """The disk, not the budget, and the message says which."""
    store = ModelStore(tmp_path, budget_bytes=10_000, free_space=lambda _: 999)
    entry = _entry(size_bytes=1000)

    with pytest.raises(NotEnoughSpaceError) as refusal:
        store.room_for(entry)

    assert refusal.value.free_bytes == 999
    assert refusal.value.measured_at == tmp_path
    assert "raising the budget does not create space" in str(refusal.value)


def test_free_space_equal_to_the_artefact_is_enough(tmp_path: Path) -> None:
    """The boundary, read the way the refusal's own comparison reads it."""
    store = ModelStore(tmp_path, budget_bytes=10_000, free_space=lambda _: 1000)

    store.room_for(_entry(size_bytes=1000))


def test_the_budget_is_asked_before_the_disk(tmp_path: Path) -> None:
    """An artefact failing both is refused by the operator's own number.

    The order is the whole of this test. A caller told about a full disk when
    their ceiling was the thing refusing them goes and looks at the wrong
    machine.
    """
    store = ModelStore(tmp_path, budget_bytes=500, free_space=lambda _: 0)

    with pytest.raises(OverDiskBudgetError):
        store.room_for(_entry(size_bytes=1000))


def test_an_installed_model_is_asked_neither_question(tmp_path: Path) -> None:
    """Nothing is fetched, so nothing can exceed anything by not fetching it.

    The budget here is below what is already installed and the disk is reported
    full, which is the state after an operator lowers a ceiling under models
    they already have. Asking about one of those models is not an error.
    """
    store = ModelStore(tmp_path, budget_bytes=10, free_space=lambda _: 0)
    entry = _entry(size_bytes=1000)
    _install(store, entry, size=1000)

    store.room_for(entry)


def test_removal_reports_what_it_freed(tmp_path: Path) -> None:
    """The number an operator asked for, measured before the delete."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    entry = _entry(identifier="lama-large", size_bytes=1000)
    _install(store, entry, size=700)
    store.incoming_path(entry).write_bytes(b"\0" * 300)

    freed = store.remove("lama-large")

    assert freed == 1000
    assert store.installed() == ()
    assert store.used_bytes() == 0


def test_removal_leaves_the_other_models_alone(tmp_path: Path) -> None:
    """One directory per model is what makes a removal a local act."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    _install(store, _entry(identifier="lama-large"), size=100)
    _install(store, _entry(identifier="sdxl-inpaint"), size=200)

    store.remove("lama-large")

    assert store.installed() == ("sdxl-inpaint",)
    assert store.used_bytes() == 200


def test_removing_something_that_is_not_installed_is_refused(tmp_path: Path) -> None:
    """Refused rather than reported as zero bytes freed."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    with pytest.raises(NotInstalledError) as refusal:
        store.remove("lama-large")

    assert "nothing was removed and nothing was freed" in str(refusal.value)


def test_removing_the_same_model_twice_is_refused_the_second_time(
    tmp_path: Path,
) -> None:
    """The second call is the one an operator makes when they are not sure."""
    store = ModelStore(tmp_path, budget_bytes=10_000)
    _install(store, _entry(identifier="lama-large"), size=100)

    assert store.remove("lama-large") == 100
    with pytest.raises(NotInstalledError):
        store.remove("lama-large")


@pytest.mark.parametrize(
    "identifier",
    [
        "weights/lama",
        "weights\\lama",
        "Lama-Large",
        "lama large",
        "lama:large",
        "lama*",
    ],
)
def test_an_identifier_that_cannot_be_a_directory_name_is_refused(
    tmp_path: Path, identifier: str
) -> None:
    """Each of these is a plausible thing to write and none may become a path."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    with pytest.raises(UnusableIdentifierError):
        store.directory_for(identifier)


@pytest.mark.parametrize("identifier", ["..", ".", ".hidden"])
def test_an_identifier_starting_with_a_dot_is_refused(
    tmp_path: Path, identifier: str
) -> None:
    """`..` climbs out of the store and the rest hide from the listing."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    with pytest.raises(UnusableIdentifierError) as refusal:
        store.directory_for(identifier)

    assert "begins with a dot" in str(refusal.value)


def test_the_empty_identifier_is_refused(tmp_path: Path) -> None:
    """It would name the store's own root, and removing it would take all of it."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    with pytest.raises(UnusableIdentifierError) as refusal:
        store.directory_for("")

    assert "the empty string is not one" in str(refusal.value)


def test_the_refusal_names_the_characters_it_refused(tmp_path: Path) -> None:
    """A message saying only that a name is wrong sends nobody anywhere."""
    store = ModelStore(tmp_path, budget_bytes=10_000)

    with pytest.raises(UnusableIdentifierError) as refusal:
        store.directory_for("lama/large*")

    assert "'*', '/'" in str(refusal.value)


def test_removal_refuses_the_same_identifiers_an_install_would(
    tmp_path: Path,
) -> None:
    """A removal accepting what an install refused is a route out of the store.

    `..` as an identifier resolves to the store's parent, which under a
    temporary directory is somebody else's directory and under a real
    deployment is whatever the operator put the store inside.
    """
    store = ModelStore(tmp_path / "store", budget_bytes=10_000)
    store.root.mkdir()
    outside = tmp_path / "important"
    outside.mkdir()

    with pytest.raises(UnusableIdentifierError):
        store.remove("..")

    assert outside.is_dir()


def test_free_space_is_measured_on_the_volume_that_would_hold_the_store(
    tmp_path: Path,
) -> None:
    """The real measurement, which is what a deployment gets by default."""
    assert free_bytes_at(tmp_path) > 0


def test_free_space_is_answerable_before_the_store_directory_exists(
    tmp_path: Path,
) -> None:
    """The ordinary state before the first model, and the reason for the parent.

    A check that could not answer here would push the space question to after
    the fetch, which is the thing the check exists to move earlier.
    """
    assert free_bytes_at(tmp_path / "not-created-yet") > 0


def test_the_default_measurement_is_the_real_one(tmp_path: Path) -> None:
    """A store built without a free-space argument asks the filesystem.

    Asserted by letting the budget pass and watching the disk check not refuse,
    on a runner that has room. The number itself is the machine's and is not
    asserted here.
    """
    store = ModelStore(tmp_path, budget_bytes=10_000)

    store.room_for(_entry(size_bytes=1000))
