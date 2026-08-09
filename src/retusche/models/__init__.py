# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Model management: what models exist, what they cost, and what governs them.

`retusche.models.registry` declares the shape of a registry entry and refuses
one that is incomplete. Fetching an artefact and verifying it is #39, the disk
budget is #41, and the gated-download path is #40; none of them is here yet.
"""

from __future__ import annotations

from retusche.models.registry import (
    Licence,
    ModelEntry,
    RegistryError,
    entry_from_mapping,
    load_registry,
)

__all__ = [
    "Licence",
    "ModelEntry",
    "RegistryError",
    "entry_from_mapping",
    "load_registry",
]
