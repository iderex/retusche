# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Model management: what models exist, what they cost, and what governs them.

`retusche.models.registry` declares the shape of a registry entry and refuses
one that is incomplete. `retusche.models.storage` says where the artefact an
entry names lives on disk, refuses one the operator's ceiling or the disk itself
cannot hold, and removes one that is no longer wanted.

The two do not know about each other beyond the entry that passes between them.
Fetching the artefact and verifying it against the digest is #39, and the
gated-download path is #40; neither is here yet, and nothing in this package
reaches the network.
"""

from __future__ import annotations

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
    "INCOMING_SUFFIX",
    "Licence",
    "ModelEntry",
    "ModelStore",
    "NotEnoughSpaceError",
    "NotInstalledError",
    "OverDiskBudgetError",
    "RegistryError",
    "StorageError",
    "UnusableIdentifierError",
    "entry_from_mapping",
    "free_bytes_at",
    "load_registry",
]
