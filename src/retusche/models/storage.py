# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Where weights live on disk, what they may take, and how they leave again.

A handful of model families fills tens of gigabytes. The machine this project is
meant to run on is usually the machine holding the photographs, so that space is
taken from the pictures themselves, and a service that fills a disk without
saying anything has made that trade on the operator's behalf.

So there is a ceiling the operator writes down, and every artefact is compared
against it before a byte is fetched. Doing the comparison here rather than
inside the fetch is the whole point: a download refused after four gigabytes
have landed has already spent what the ceiling exists to protect.

The layout
----------
One directory per model, named by the model's identifier, and one file inside it
named by the digest that verifies it::

    <model_store_path>/
      <identifier>/
        <sixty-four hexadecimal digits>

The file is named after the digest rather than after the file name at the
source, and that is three properties rather than a preference. An operator can
check an installed artefact against its registry entry with a hashing tool and
their eyes. An entry re-pinned to new bytes lands beside the old file instead of
over it, so the artefact a running job may still have open is not the one a
fetch overwrites. And the name at the source is written by whoever serves it,
which makes it the wrong thing to build a path out of.

An unfinished fetch carries `INCOMING_SUFFIX`, so it never has the name a loader
looks for. Writing that file is #39's; what is settled here is that the finished
name is reached by a rename rather than by a file that grows into it, which is
the half an operator needs to know that a name ending in `.incoming` is theirs
to delete.

`docs/model-storage.md` is this layout written for somebody standing in the
directory, which is the route these docstrings are not.

What is refused, and what is not
--------------------------------
A model whose artefact alone exceeds the ceiling, and a model that fits the
ceiling only once something else is removed. Both raise rather than returning an
answer, because nothing in this project removes a model on its own: eviction is
#32 and it is about device memory, not disk. A caller told "later" by a system
with no mechanism that produces later is a caller that waits forever.

The disk itself is checked separately and second. The ceiling is a number the
operator chose, and being refused by it is their own decision arriving back at
them; free space is a fact about the machine that can move under a fetch. Neither
check makes the other unnecessary: a generous ceiling on a full disk and a small
ceiling on an empty one are both ordinary.

WHAT IS NOT REFUSED HERE IS REMOVING A MODEL SOMETHING IS USING. #41's fifth
condition asks for it and this module does not do it, because nothing on this
side of the process boundary can answer the question. Whether weights are loaded
is the worker's state, and the engine contract carries no question a caller can
ask about residency: `capabilities`, `estimate_device_memory` and `run`, and none
of the three says what is in memory. The queue cannot answer the other half
either, since `JobRecord` carries a job identifier, a state and a reason and
names no model. So `remove` deletes what it is told to, and a caller holding that
knowledge is the one that must not call it. Putting the question into the
interface reaches every engine and the contract suite, which is why it is #32's
or #17's change rather than one made in passing here.

Nothing here reaches the network. What fetches an artefact into this layout, and
what verifies it against the digest before the rename, is #39.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from retusche.models.registry import ModelEntry

__all__ = [
    "INCOMING_SUFFIX",
    "ModelStore",
    "NotEnoughSpaceError",
    "NotInstalledError",
    "OverDiskBudgetError",
    "StorageError",
    "UnusableIdentifierError",
    "free_bytes_at",
]

INCOMING_SUFFIX: Final = ".incoming"
"""What an unfinished artefact is called while it is still being written.

Declared here rather than in the fetch, because the property belongs to the
directory and not to the download: the name a loader opens is reached by a
rename, so a file under that name is a whole file. A fetch interrupted by a power
cut leaves this suffix behind, and an operator reading the layout page knows what
it is.
"""

_PERMITTED_IN_IDENTIFIER: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-._")
"""What a model identifier may hold if it is to become a directory name.

Lower-case letters, digits, hyphen, dot and underscore. Narrower than what a
registry entry may declare, and deliberately so: the identifier is text somebody
writes in a file, and this is the one place it becomes a path. A separator in it
writes outside the store and `..` climbs out of it. Upper case is refused for a
quieter reason: two identifiers differing only in case are one directory on
Windows and macOS and two on Linux, so a registry that loads everywhere would
install differently in different places.
"""


class StorageError(Exception):
    """Base of everything this module refuses."""


class UnusableIdentifierError(StorageError):
    """The model's identifier cannot be made into a directory name.

    Raised where the identifier becomes a path rather than where the entry is
    read. The registry knows nothing about a filesystem, and a rule about path
    separators written there would be a rule about this module kept somewhere
    else. The cost is stated rather than left to be found: an entry carrying such
    an identifier loads into the registry and is refused when somebody tries to
    install it, which is later than it could be and is the safe direction of
    later.
    """


class OverDiskBudgetError(StorageError):
    """Installing this artefact would put the store over the operator's ceiling.

    Carries the numbers as well as the sentence, so a caller can report the
    shortfall without parsing the message it was handed.
    """

    def __init__(self, entry: ModelEntry, used_bytes: int, budget_bytes: int) -> None:
        super().__init__(_over_budget_message(entry, used_bytes, budget_bytes))
        self.entry = entry
        self.used_bytes = used_bytes
        self.budget_bytes = budget_bytes


class NotEnoughSpaceError(StorageError):
    """The filesystem holding the store has less free than the artefact needs.

    Separate from the budget refusal because the two are corrected by different
    people doing different things. A budget refusal is answered by raising a
    number or removing a model; this one is answered by making room on a disk,
    and reading the second as the first sends an operator to edit a setting that
    was never the problem.
    """

    def __init__(self, entry: ModelEntry, free_bytes: int, measured_at: Path) -> None:
        super().__init__(_no_space_message(entry, free_bytes, measured_at))
        self.entry = entry
        self.free_bytes = free_bytes
        self.measured_at = measured_at


class NotInstalledError(StorageError):
    """Nothing by that identifier is in the store, so nothing was freed.

    Raised rather than answered with zero. A removal quietly reporting zero bytes
    freed reads as a model that took no room, and the two things an operator does
    next are not the same.
    """


def free_bytes_at(path: Path) -> int:
    """Free space on the filesystem that would hold ``path``.

    Measured at the store root where it exists and at its parent where it does
    not, because the root is ordinarily absent before the first model is
    installed and a check that refused to answer there would push the space
    question to after the fetch, which is what this module exists to move
    earlier.

    One level and not a walk. A store root whose own parent does not exist is a
    path the operator has not made, and the filesystem's own error names it
    better than a guess three directories further up would.
    """
    measured = path if path.exists() else path.parent
    return shutil.disk_usage(measured).free


class ModelStore:
    """A directory of installed models, and the ceiling it is held to.

    ``free_space`` is how the filesystem is asked. It is an argument rather than
    a call inside the method so a full disk can be put in front of this without
    filling the disk of whoever is running the suite; the default is the real
    measurement, and it is the only part of this module a temporary directory
    cannot arrange.
    """

    def __init__(
        self,
        root: Path,
        budget_bytes: int,
        free_space: Callable[[Path], int] = free_bytes_at,
    ) -> None:
        self.root = root
        self.budget_bytes = budget_bytes
        self._free_space = free_space

    def directory_for(self, identifier: str) -> Path:
        """Where this model's artefact lives, whether or not it is installed."""
        return self.root / _directory_name(identifier)

    def artefact_path(self, entry: ModelEntry) -> Path:
        """The file a loader opens, once a fetch has finished and renamed."""
        return self.directory_for(entry.identifier) / _artefact_name(entry)

    def incoming_path(self, entry: ModelEntry) -> Path:
        """Where a fetch writes while it is still writing. #39 opens this."""
        artefact = self.artefact_path(entry)
        return artefact.with_name(artefact.name + INCOMING_SUFFIX)

    def holds(self, entry: ModelEntry) -> bool:
        """Whether the finished artefact for this exact entry is already here.

        Exact, because the name is the digest. An entry re-pinned to new bytes is
        a different file in the same directory, and answering yes for it would
        hand a loader the old weights under the new entry's name.
        """
        return self.artefact_path(entry).is_file()

    def installed(self) -> tuple[str, ...]:
        """The identifiers with a directory in the store, sorted.

        Read off the directory rather than out of an index, for the reason the
        registry gives for the same choice: an index is a second place the set is
        declared, and what it produces is a model on the disk that no run knows
        about.
        """
        if not self.root.is_dir():
            return ()
        return tuple(
            sorted(child.name for child in self.root.iterdir() if child.is_dir())
        )

    def used_bytes(self) -> int:
        """What the store is holding now, in bytes, counted from the files.

        Counted rather than declared. `size_bytes` on a registry entry is what
        the artefact is supposed to be, and a budget compared against supposed
        sizes stays green while the disk fills with half-written fetches and
        models no entry names any more.

        A symlink counts as the link and not as what it points at, which is a
        limit rather than a claim: a store whose contents are links into another
        tree reads as nearly empty here, and the operator who built it that way
        is outside what this number describes.
        """
        return _bytes_under(self.root)

    def room_for(self, entry: ModelEntry) -> None:
        """Refuse before a fetch begins, or return and let it begin.

        Two questions in a fixed order. The ceiling first, because it is the
        operator's own decision and refusing on it needs no filesystem at all.
        Free space second, because it is a fact about the machine and the message
        it produces sends somebody somewhere else entirely.

        An entry already installed is asked neither. Nothing would be fetched, so
        nothing can be exceeded by not fetching it, and refusing here would make
        a second call about an installed model fail where the first succeeded.
        """
        if self.holds(entry):
            return
        used = self.used_bytes()
        if used + entry.size_bytes > self.budget_bytes:
            raise OverDiskBudgetError(entry, used, self.budget_bytes)
        free = self._free_space(self.root)
        if free < entry.size_bytes:
            raise NotEnoughSpaceError(entry, free, self.root)

    def remove(self, identifier: str) -> int:
        """Delete this model's directory and answer with what that freed.

        The number is measured before the delete and reported after it, because
        what was asked is how much room came back, and the directory is not there
        to be measured once the answer would be useful.

        What this does not do is refuse a model something is using. The module
        docstring says why, and the short of it is that nothing on this side of
        the process boundary knows.
        """
        directory = self.directory_for(identifier)
        if not directory.is_dir():
            message = (
                f"{identifier!r} has no directory in the model store at "
                f"{self.root}, so nothing was removed and nothing was freed. An "
                f"identifier that was never installed and one removed twice give "
                f"this same refusal, and both are answered by reading the store "
                f"rather than by removing again."
            )
            raise NotInstalledError(message)
        freed = _bytes_under(directory)
        shutil.rmtree(directory)
        return freed


def _directory_name(identifier: str) -> str:
    """The identifier as a directory name, or a refusal naming the character.

    The whole check is here rather than spread over the callers, so `remove` and
    an install refuse the same strings. A removal accepting a name the install
    refused would be a route to deleting a directory the store does not own.
    """
    if not identifier:
        message = (
            "a model identifier is the name of a directory in the store, and the "
            "empty string is not one. An entry declaring it would install into "
            "the store's own root, and removing it would take every other model "
            "with it."
        )
        raise UnusableIdentifierError(message)
    if identifier.startswith("."):
        message = (
            f"{identifier!r} begins with a dot. `.` and `..` are the store's own "
            f"directory and its parent, and a name starting with one is hidden "
            f"from the listing an operator would check the store with, which is "
            f"the wrong property for tens of gigabytes to have."
        )
        raise UnusableIdentifierError(message)
    refused = sorted(set(identifier) - _PERMITTED_IN_IDENTIFIER)
    if refused:
        message = (
            f"{identifier!r} carries {_quoted(refused)}, which a model identifier "
            f"may not, because this is where it becomes a directory name. "
            f"Permitted are lower-case letters, digits, and the hyphen, dot and "
            f"underscore. A separator writes outside the store, and two names "
            f"differing only in case are one directory on some filesystems and "
            f"two on others."
        )
        raise UnusableIdentifierError(message)
    return identifier


def _artefact_name(entry: ModelEntry) -> str:
    """The digest without its algorithm prefix, which is the file's name.

    The prefix is dropped rather than kept because a colon is not a character a
    file name may carry on one of the two platforms this project supports, and
    the algorithm is `sha256:` in every entry the registry accepts.
    """
    return entry.digest.removeprefix("sha256:")


def _bytes_under(directory: Path) -> int:
    """Every file under this directory, counted by what the link itself says.

    A directory that is not there counts as nothing: `Path.walk` yields nothing
    for it rather than raising, which is the answer a store with no models yet
    should give and is the same answer as a store whose directory was removed
    under it.
    """
    total = 0
    for parent, _, names in directory.walk():
        for name in names:
            total += (parent / name).lstat().st_size
    return total


def _over_budget_message(entry: ModelEntry, used_bytes: int, budget_bytes: int) -> str:
    """Both numbers, and which of the two repairs is the one on offer."""
    opening = (
        f"{entry.identifier} is {entry.size_bytes} bytes against a model disk "
        f"budget of {budget_bytes} bytes, with {used_bytes} bytes already in the "
        f"store."
    )
    if entry.size_bytes > budget_bytes:
        return (
            f"{opening} It does not fit in the whole budget, so removing every "
            f"other model would not make room and nothing was fetched. Either "
            f"the budget the operator set is larger, or this is not a model this "
            f"host holds."
        )
    return (
        f"{opening} It fits the budget and not what is left of it, so removing a "
        f"model this host no longer needs makes room for it. Nothing was "
        f"fetched, so nothing is half-written."
    )


def _no_space_message(entry: ModelEntry, free_bytes: int, measured_at: Path) -> str:
    """The shortfall as the filesystem reports it, and where it was asked."""
    return (
        f"{entry.identifier} needs {entry.size_bytes} bytes and the filesystem "
        f"holding {measured_at} reports {free_bytes} free, so the fetch was "
        f"refused before it started rather than failing part way through with a "
        f"partial file to clean up. This is the disk and not the configured "
        f"budget: raising the budget does not create space."
    )


def _quoted(characters: list[str]) -> str:
    """The refused characters, sorted and quoted, so a message is stable."""
    return ", ".join(repr(character) for character in characters)
