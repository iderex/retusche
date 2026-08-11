# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Model management: what models exist, what they cost, and what governs them.

`retusche.models.registry` declares the shape of a registry entry and refuses
one that is incomplete. `retusche.models.storage` says where the artefact an
entry names lives on disk, refuses one the operator's ceiling or the disk itself
cannot hold, and removes one that is no longer wanted.

`retusche.models.fetch` is the one thing here that reaches the network. It
streams an artefact into the layout the storage module declares, refuses it on
its length and its digest before anything is renamed, and leaves nothing behind
when it refuses. The gated-download path is #40 and is not here yet.
"""

from __future__ import annotations

from retusche.models.fetch import (
    CHUNK_BYTES,
    DigestMismatchError,
    FetchError,
    FetchInProgressError,
    Progress,
    SizeMismatchError,
    UnusableSourceError,
    fetch_artefact,
)
from retusche.models.registry import (
    Licence,
    ModelEntry,
    RegistryError,
    entry_from_mapping,
    load_registry,
)
from retusche.models.storage import (
    INCOMING_SUFFIX,
    ModelStore,
    NotEnoughSpaceError,
    NotInstalledError,
    OverDiskBudgetError,
    StorageError,
    UnusableIdentifierError,
    free_bytes_at,
)

__all__ = [
    "CHUNK_BYTES",
    "INCOMING_SUFFIX",
    "DigestMismatchError",
    "FetchError",
    "FetchInProgressError",
    "Licence",
    "ModelEntry",
    "ModelStore",
    "NotEnoughSpaceError",
    "NotInstalledError",
    "OverDiskBudgetError",
    "Progress",
    "RegistryError",
    "SizeMismatchError",
    "StorageError",
    "UnusableIdentifierError",
    "UnusableSourceError",
    "entry_from_mapping",
    "fetch_artefact",
    "free_bytes_at",
    "load_registry",
]
