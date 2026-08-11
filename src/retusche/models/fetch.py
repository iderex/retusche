# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Fetching an artefact, and refusing to let one become usable unverified.

Weights are a large file pulled from somebody else's server and then opened by
this project's own worker. Between those two sentences is the whole reason this
module exists: an artefact that arrives corrupted, truncated or substituted is
indistinguishable from a good one until something hashes it, and the place to
hash it is before it acquires the name a loader opens.

So nothing here ever writes the artefact's own name. A fetch writes to the
`.incoming` file `retusche.models.storage` declares, checks the length, checks
the digest, and only then renames. A rename within one directory is atomic on
both platforms this project supports, so a concurrent loader sees either no file
or the whole verified one, and never a file that is still growing.

What a failure leaves behind
----------------------------
Nothing. Every refusal below removes the partial file on its way out, so a
second run starts from an empty directory rather than from somebody else's
half-finished attempt. That is the restartable half of #39's second condition,
and it is chosen over a resumable download deliberately: resuming means trusting
that the bytes already on disk came from the same artefact, which is exactly the
thing the digest is here to stop anybody assuming. A fetch that has to start
again costs bandwidth; a resume that appended to the wrong prefix costs the
verification.

The one case that does leave a file is the one no code runs in: a power cut, a
container killed, a process that never gets to its own cleanup. The layout page
tells an operator what a `.incoming` file is and that deleting it is safe, and
the refusal below names that file when a later fetch meets it.

Two fetches at once
-------------------
The `.incoming` file is created exclusively, so the second fetch of one artefact
does not write into the first one's file. It is refused instead of waiting,
because waiting needs a bound and a bound needs a measurement of how long a
fetch takes, which this project does not have. A caller told to try again has
something to do; a caller waiting on an unbounded thing does not.

What is not decided here
------------------------
What opens the file afterwards. #39's fourth condition asks that loading uses a
format and a loader that does not execute code from the artefact, and that a
model whose format cannot avoid it is refused rather than loaded with a warning.
Which formats can be refused is a question about the runtime that loads them,
and no runtime is chosen: #19 picks the diffusion library and is itself waiting
on entry 2 of #94. What can be said without either, and is said here rather than
left to the day somebody meets it, is that the refusal stays a refusal. A
warning on that path is a model somebody loads anyway, and a checkpoint that
executes code on load is arbitrary code from whoever served the file.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit
from urllib.request import urlopen

if TYPE_CHECKING:
    from collections.abc import Callable
    from io import BufferedWriter
    from pathlib import Path

    from retusche.models.registry import ModelEntry
    from retusche.models.storage import ModelStore

__all__ = [
    "CHUNK_BYTES",
    "OWNER_ONLY",
    "DigestMismatchError",
    "FetchError",
    "FetchInProgressError",
    "Progress",
    "SizeMismatchError",
    "UnusableSourceError",
    "fetch_artefact",
]

CHUNK_BYTES: Final = 1 << 20
"""How much is read from the source at a time, and how often progress is said.

A megabyte, which is the bound on how far past the declared size a fetch can
read before it refuses, and the granularity of the progress report. Both are
this number, and that is why it is one number rather than two: a report finer
than the read is a report repeating itself.
"""

OWNER_ONLY: Final = 0o600
"""The mode a fetched file is created with, and the mode the artefact keeps.

While it is being written the file holds bytes nothing has verified yet, and no
other user on the host has any business reading them or, worse, writing them: a
partial file another account can append to is a file whose digest this fetch
would then compute over somebody else's bytes.

The rename carries the mode onto the artefact, so this is the installed file's
mode as well, and it is deliberate there too. The processes that open weights are
this service's own and run as the user that fetched them. A model directory
readable by every account on the machine is a default nobody chose, and the
weights are large enough that a copy of one is not a small thing to take.

Windows honours only the write bit of this number, so what the suite asserts is
the mode this module asks for rather than what a filesystem made of it.
"""

_LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "::1", "localhost"})
"""Where plain HTTP is accepted, and nowhere else.

An artefact fetched over plain HTTP is an artefact anybody on the path can
replace, and the digest turns that into a refusal rather than a compromise. That
is the argument for allowing it at all, and it is not a good enough one for the
open internet: a substituted artefact that fails verification is still a fetch
that cannot succeed, on a schedule chosen by whoever is on the path.

The loopback interface has no path. Nothing is between the two ends, which is
what makes a fixture server in this project's own suite the one place the
weaker scheme costs nothing, and it is the reason this set exists rather than a
flag somebody can set.
"""


class FetchError(Exception):
    """Base of everything this module refuses."""


class UnusableSourceError(FetchError):
    """The entry's source is not something this module will open.

    The registry accepts a source as text and says so: what it refuses is a
    revision that can move under a digest, and it makes no judgement about a
    scheme, because judging a scheme is a decision about what opens the URL and
    nothing there opens anything. This is what opens it.
    """


class SizeMismatchError(FetchError):
    """The source sent a different number of bytes than the entry declares.

    Checked before the digest and raised on both directions, because the two
    say different things. Fewer bytes is an interrupted transfer, more is a
    source that is not serving what the entry describes, and the second is the
    one that would otherwise fill the disk the budget was protecting: a fetch
    reading until the far end stops is a fetch whose size is chosen by the far
    end.
    """

    def __init__(self, entry: ModelEntry, received_bytes: int) -> None:
        super().__init__(
            f"{entry.identifier} declares {entry.size_bytes} bytes and the "
            f"source at {entry.source} sent {received_bytes}. Nothing was "
            f"verified and the partial file was removed, so a later run starts "
            f"from an empty directory rather than from this attempt."
        )
        self.entry = entry
        self.received_bytes = received_bytes


class DigestMismatchError(FetchError):
    """What arrived is not what the registry entry says it should be.

    Both digests are in the message. An operator holding only "verification
    failed" cannot tell a corrupted transfer from an entry pinned to the wrong
    artefact, and those are answered by retrying and by editing a registry file
    respectively.
    """

    def __init__(self, entry: ModelEntry, received_digest: str) -> None:
        super().__init__(
            f"{entry.identifier} was fetched from {entry.source} and hashes to "
            f"{received_digest}, and its registry entry declares "
            f"{entry.digest}. The partial file was removed and nothing was "
            f"moved into place, so no loader can reach these bytes. Either the "
            f"transfer was corrupted, or the artefact at that source is not the "
            f"one this entry was written against."
        )
        self.entry = entry
        self.received_digest = received_digest


class FetchInProgressError(FetchError):
    """Something else is already writing this artefact.

    Names the file, because the one state this cannot tell apart from a live
    fetch is a dead one: a process killed between creating the file and
    removing it leaves the same thing behind, and deleting it is the operator's
    repair.
    """

    def __init__(self, entry: ModelEntry, incoming: Path) -> None:
        super().__init__(
            f"{entry.identifier} is already being fetched: {incoming} exists, "
            f"so another fetch created it and has not finished. This one wrote "
            f"nothing rather than writing into that file. If nothing is "
            f"fetching, the file is left over from a run that was killed and "
            f"deleting it is safe, which is what docs/model-storage.md says."
        )
        self.entry = entry
        self.incoming = incoming


@dataclass(frozen=True, slots=True)
class Progress:
    """How far a fetch has got, as something a caller can render.

    Carries the entry rather than only the numbers, so a caller reporting on
    several fetches does not have to remember which callback belonged to which
    model. The total is the entry's declared size and not a header from the
    source: a length the far end supplies is a number this fetch does not
    trust, and it is the number a refusal above is measured against.
    """

    entry: ModelEntry
    received_bytes: int

    @property
    def total_bytes(self) -> int:
        """What the entry says the whole artefact is."""
        return self.entry.size_bytes


def fetch_artefact(
    entry: ModelEntry,
    store: ModelStore,
    progress: Callable[[Progress], None] | None = None,
) -> Path:
    """Put this entry's artefact in the store, verified, and answer with its path.

    Returns the artefact's path without fetching anything where the store
    already holds it, so a caller may ask for a model it has and a model it has
    not in the same loop.

    Everything else is refused before it is written or removed after it: the
    ceiling and the disk first, through `ModelStore.room_for`, then the scheme,
    then the length, then the digest. The rename into place happens after all of
    them and is the only moment the artefact's own name exists.
    """
    if store.holds(entry):
        return store.artefact_path(entry)
    _refuse_unusable_source(entry)
    store.room_for(entry)
    artefact = store.artefact_path(entry)
    incoming = store.incoming_path(entry)
    artefact.parent.mkdir(parents=True, exist_ok=True)
    handle = _create_exclusively(entry, incoming)
    # Outside the block below on purpose. A second fetch refused because the
    # file already exists must not go on to delete the file the first one is
    # writing into, and that is what a cleanup wrapped around this call would
    # do.
    try:
        with handle:
            digest = _receive(entry, handle, progress)
    except BaseException:
        incoming.unlink(missing_ok=True)
        raise
    if digest != entry.digest:
        incoming.unlink()
        raise DigestMismatchError(entry, digest)
    incoming.replace(artefact)
    return artefact


def _refuse_unusable_source(entry: ModelEntry) -> None:
    """Refuse a scheme this module will not open, naming what it will."""
    parts = urlsplit(entry.source)
    if parts.scheme == "https":
        return
    if parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS:
        return
    message = (
        f"{entry.identifier} names {entry.source}, which this fetch will not "
        f"open. Artefacts are fetched over https, and over plain http only from "
        f"the loopback interface, where nothing is between the two ends. Every "
        f"other scheme reads a file, a share or a service of somebody else's "
        f"choosing under the name of a download."
    )
    raise UnusableSourceError(message)


def _create_exclusively(entry: ModelEntry, incoming: Path) -> BufferedWriter:
    """Open the incoming file, or refuse because something else already did.

    Exclusive creation rather than a lock file, because the file whose absence
    means nobody is fetching is the same file the fetch writes into. A separate
    lock is a second thing to leave behind.
    """
    try:
        descriptor = os.open(incoming, os.O_CREAT | os.O_EXCL | os.O_WRONLY, OWNER_ONLY)
    except FileExistsError as error:
        raise FetchInProgressError(entry, incoming) from error
    return os.fdopen(descriptor, "wb")


def _receive(
    entry: ModelEntry,
    handle: BufferedWriter,
    progress: Callable[[Progress], None] | None,
) -> str:
    """Stream the source into the open file and answer with what it hashed to.

    Reads at most one chunk past the declared size before refusing, so a source
    that never stops sending cannot fill the volume the budget was protecting.
    """
    hasher = hashlib.sha256()
    received = 0
    with urlopen(entry.source) as response:  # noqa: S310  # the scheme is refused above
        while True:
            chunk = response.read(CHUNK_BYTES)
            if not chunk:
                break
            received += len(chunk)
            if received > entry.size_bytes:
                raise SizeMismatchError(entry, received)
            hasher.update(chunk)
            handle.write(chunk)
            if progress is not None:
                progress(Progress(entry=entry, received_bytes=received))
    if received != entry.size_bytes:
        raise SizeMismatchError(entry, received)
    return "sha256:" + hasher.hexdigest()
