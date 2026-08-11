# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What a fetch refuses, and what it leaves behind when it refuses.

Every case here runs against a server this file starts on the loopback
interface. Nothing reaches a network, and the point of using a real server
rather than a stubbed transport is that the code under test opens the URL the
way a deployment will: a stub would prove that the verification arithmetic is
right and say nothing about whether the thing that streams bytes is wired to it.

The two properties worth the most are the ones a hand-written retry loop usually
gets wrong. An artefact that fails verification never acquires the name a loader
opens, and the partial file is gone afterwards, so a second run starts from an
empty directory rather than from somebody else's attempt. And a source that
sends more than the entry declares is cut off rather than read to the end,
because a fetch whose size is decided by the far end is a fetch that fills the
volume the disk budget was protecting.

The near miss the size cases are aimed at is not a server sending nothing, which
fails obviously. It is the one that sends almost the right amount: a transfer cut
short by a dropped connection, which hashes to something plausible and would be
renamed into place by anything that only checked for an exception.

No device, no display, no elevation, and no traffic that leaves the machine.
"""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from retusche.models import fetch as fetch_module
from retusche.models.fetch import (
    DigestMismatchError,
    FetchInProgressError,
    Progress,
    SizeMismatchError,
    UnusableSourceError,
    fetch_artefact,
)
from retusche.models.registry import Access, Licence, ModelEntry
from retusche.models.storage import ModelStore, OverDiskBudgetError
from retusche_contracts.engine import Operation

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

_ARTEFACT = b"the weights, as far as this suite is concerned" * 4
_DIGEST = "sha256:" + hashlib.sha256(_ARTEFACT).hexdigest()
_OTHER_DIGEST = "sha256:" + "cd" * 32


class _Server(ThreadingHTTPServer):
    """A fixture server whose routes the test writes before it starts."""

    routes: dict[str, Callable[[BaseHTTPRequestHandler], None]]


class _Handler(BaseHTTPRequestHandler):
    """Dispatch to whatever the test put at this path, and say nothing else."""

    def do_GET(self) -> None:  # the name the base class dispatches on
        server: _Server = self.server  # type: ignore[assignment]  # set by the fixture
        server.routes[self.path](self)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the suite's output about the suite rather than about a server."""


def _serves(payload: bytes, *, declared: int | None = None) -> Callable[..., None]:
    """A route sending ``payload`` under a stated length.

    ``declared`` is what the header says, which is the length only when the test
    wants the two to agree. Where they do not, the header is the lie a truncated
    transfer tells and the payload is what actually arrives.
    """

    def route(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Length", str(declared or len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    return route


@pytest.fixture
def server() -> Iterator[_Server]:
    """A server on the loopback interface, on a port the machine chooses."""
    instance = _Server(("127.0.0.1", 0), _Handler)
    instance.routes = {}
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=5)


def _url(server: _Server, path: str) -> str:
    """Where the fixture server is listening, for a route the test declared."""
    host, port = server.server_address[:2]
    return f"http://{host}:{port}{path}"


def _entry(
    source: str,
    *,
    digest: str = _DIGEST,
    size_bytes: int = len(_ARTEFACT),
    identifier: str = "lama-large",
) -> ModelEntry:
    """One complete entry, varying only the fields a fetch reads."""
    return ModelEntry(
        identifier=identifier,
        source=source,
        digest=digest,
        size_bytes=size_bytes,
        device_memory_bytes=2000,
        engine="fake",
        operations=frozenset({Operation.ERASE}),
        licence=Licence(identifier="apache-2.0", url="https://example.invalid/l"),
        access=Access(gated=False, obtain=""),
    )


def _store(tmp_path: Path, budget_bytes: int = 1_000_000) -> ModelStore:
    """A store with room, so a refusal below is about the fetch."""
    return ModelStore(tmp_path / "models", budget_bytes, free_space=lambda _: 1_000_000)


def test_a_verified_artefact_lands_under_the_name_a_loader_opens(
    tmp_path: Path, server: _Server
) -> None:
    """The whole path, so every refusal below is attributable to its own case."""
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))

    landed = fetch_artefact(entry, store)

    assert landed == store.artefact_path(entry)
    assert landed.read_bytes() == _ARTEFACT
    assert store.holds(entry)


def test_nothing_is_fetched_for_an_artefact_the_store_already_holds(
    tmp_path: Path, server: _Server
) -> None:
    """A caller may ask for what it has and what it has not in one loop.

    The route is deliberately one that would refuse: reaching it at all is the
    failure this asserts against.
    """
    server.routes["/weights"] = _serves(b"different bytes entirely")
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))
    store.artefact_path(entry).parent.mkdir(parents=True)
    store.artefact_path(entry).write_bytes(_ARTEFACT)

    assert fetch_artefact(entry, store).read_bytes() == _ARTEFACT


def test_a_digest_that_does_not_match_names_both_digests(
    tmp_path: Path, server: _Server
) -> None:
    """A mismatch is answered by retrying or by editing an entry, not one of the two."""
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"), digest=_OTHER_DIGEST)

    with pytest.raises(DigestMismatchError) as refusal:
        fetch_artefact(entry, store)

    assert _OTHER_DIGEST in str(refusal.value)
    assert refusal.value.received_digest == _DIGEST
    assert _DIGEST in str(refusal.value)


def test_a_failed_verification_leaves_nothing_behind(
    tmp_path: Path, server: _Server
) -> None:
    """The property a later run depends on, asserted on the directory itself."""
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"), digest=_OTHER_DIGEST)

    with pytest.raises(DigestMismatchError):
        fetch_artefact(entry, store)

    assert not store.artefact_path(entry).exists()
    assert not store.incoming_path(entry).exists()
    assert store.used_bytes() == 0


def test_a_transfer_cut_short_is_refused_and_removed(
    tmp_path: Path, server: _Server
) -> None:
    """The near miss: a plausible amount of a real artefact, and a header that lies."""
    server.routes["/weights"] = _serves(_ARTEFACT[:-8], declared=len(_ARTEFACT))
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))

    with pytest.raises(SizeMismatchError) as refusal:
        fetch_artefact(entry, store)

    assert refusal.value.received_bytes == len(_ARTEFACT) - 8
    assert not store.incoming_path(entry).exists()
    assert not store.artefact_path(entry).exists()


def test_a_source_sending_more_than_the_entry_declares_is_cut_off(
    tmp_path: Path, server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fetch whose size the far end decides is a fetch that fills the disk.

    The chunk size is reduced for this case so the bound the module states, at
    most one chunk past the declared size, is asserted on a number rather than
    on a megabyte of test data.
    """
    monkeypatch.setattr(fetch_module, "CHUNK_BYTES", 16)
    server.routes["/weights"] = _serves(_ARTEFACT * 4)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))

    with pytest.raises(SizeMismatchError) as refusal:
        fetch_artefact(entry, store)

    assert refusal.value.received_bytes <= len(_ARTEFACT) + 16
    assert not store.incoming_path(entry).exists()


def test_progress_is_reported_as_the_bytes_arrive(
    tmp_path: Path, server: _Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A multi-gigabyte fetch is meant to be distinguishable from a hang.

    The chunk size is reduced here for the same reason: the report is one per
    chunk, so a fixture small enough to read in one would prove only that the
    callback is reachable.
    """
    monkeypatch.setattr(fetch_module, "CHUNK_BYTES", 16)
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))
    seen: list[Progress] = []

    fetch_artefact(entry, store, progress=seen.append)

    assert len(seen) > 1
    assert [report.received_bytes for report in seen] == sorted(
        report.received_bytes for report in seen
    )
    assert seen[-1].received_bytes == len(_ARTEFACT)
    assert seen[-1].total_bytes == len(_ARTEFACT)
    assert seen[-1].entry is entry


def test_a_second_fetch_of_one_artefact_is_refused_rather_than_joining_in(
    tmp_path: Path, server: _Server
) -> None:
    """Two fetches at once, and the second must not write into the first's file.

    The first is held inside its own transfer by an event the second releases,
    so the overlap is arranged rather than hoped for and no sleep decides how
    long it lasts. What is asserted afterwards is that the first one's artefact
    is whole: a second writer would have corrupted it.
    """
    reached = threading.Event()
    release = threading.Event()

    def slow(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Length", str(len(_ARTEFACT)))
        handler.end_headers()
        handler.wfile.write(_ARTEFACT[:10])
        handler.wfile.flush()
        reached.set()
        release.wait(timeout=10)
        handler.wfile.write(_ARTEFACT[10:])

    server.routes["/weights"] = slow
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))
    outcome: list[object] = []

    first = threading.Thread(
        target=lambda: outcome.append(fetch_artefact(entry, store))
    )
    first.start()
    assert reached.wait(timeout=10)

    with pytest.raises(FetchInProgressError) as refusal:
        fetch_artefact(entry, store)

    release.set()
    first.join(timeout=10)

    assert str(store.incoming_path(entry)) in str(refusal.value)
    assert outcome == [store.artefact_path(entry)]
    assert store.artefact_path(entry).read_bytes() == _ARTEFACT


def test_an_incoming_file_left_by_a_killed_run_refuses_the_next_fetch(
    tmp_path: Path, server: _Server
) -> None:
    """The state a power cut leaves, and the refusal that names what to delete."""
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))
    store.incoming_path(entry).parent.mkdir(parents=True)
    store.incoming_path(entry).write_bytes(b"half of something")

    with pytest.raises(FetchInProgressError) as refusal:
        fetch_artefact(entry, store)

    assert "deleting it is safe" in str(refusal.value)
    assert store.incoming_path(entry).read_bytes() == b"half of something"


@pytest.mark.parametrize(
    "source",
    [
        "file:///etc/passwd",
        "ftp://example.invalid/weights",
        "http://example.invalid/weights",
        "gopher://example.invalid/weights",
    ],
)
def test_a_source_this_module_will_not_open_is_refused(
    tmp_path: Path, source: str
) -> None:
    """Plain http off the loopback interface is in this list on purpose."""
    store = _store(tmp_path)

    with pytest.raises(UnusableSourceError):
        fetch_artefact(_entry(source), store)


def test_https_is_accepted_as_far_as_opening_it(tmp_path: Path) -> None:
    """The scheme check passes and the transport is what fails, not the check.

    The host is the loopback address and the port is one nothing listens on, so
    the connection is refused by this machine without a name being resolved and
    without a packet leaving it. A hostname under `.invalid` was the obvious
    choice and is the wrong one: a resolver that answers for it turns this into
    an outbound connection and a sixty-second wait.

    What this establishes is that https is not refused before anything is
    attempted, which the parametrised case above cannot say.
    """
    store = _store(tmp_path)
    entry = _entry("https://127.0.0.1:1/weights")

    with pytest.raises(OSError):  # any transport failure will do
        fetch_artefact(entry, store)

    assert not store.incoming_path(entry).exists()


def test_the_disk_refusal_happens_before_anything_is_opened(
    tmp_path: Path, server: _Server
) -> None:
    """The ceiling from #41 is in front of the fetch rather than beside it."""
    server.routes["/weights"] = _serves(_ARTEFACT)
    store = ModelStore(tmp_path / "models", budget_bytes=8, free_space=lambda _: 10**9)
    entry = _entry(_url(server, "/weights"))

    with pytest.raises(OverDiskBudgetError):
        fetch_artefact(entry, store)

    assert not store.incoming_path(entry).exists()


def test_the_artefact_is_never_written_under_its_final_name_while_growing(
    tmp_path: Path, server: _Server
) -> None:
    """The rename is the only moment the loader's name exists.

    Asserted from inside the transfer rather than after it: the first ten bytes
    have arrived and the artefact's own name must still be absent.
    """
    reached = threading.Event()
    release = threading.Event()

    def slow(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Length", str(len(_ARTEFACT)))
        handler.end_headers()
        handler.wfile.write(_ARTEFACT[:10])
        handler.wfile.flush()
        reached.set()
        release.wait(timeout=10)
        handler.wfile.write(_ARTEFACT[10:])

    server.routes["/weights"] = slow
    store = _store(tmp_path)
    entry = _entry(_url(server, "/weights"))
    worker = threading.Thread(target=lambda: fetch_artefact(entry, store))
    worker.start()
    assert reached.wait(timeout=10)

    mid_transfer = store.artefact_path(entry).exists()

    release.set()
    worker.join(timeout=10)

    assert not mid_transfer
    assert store.holds(entry)
