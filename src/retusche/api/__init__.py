# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The HTTP surface: its shape, its refusals and the description of both.

Three modules and no endpoint. `retusche.api.surface` holds the version the
path carries and the rule for what may change under it. `retusche.api.refusal`
holds the one shape every refusal takes and the closed set of machine-readable
reasons it carries. `retusche.api.description` builds the interface description
from those two rather than from a document somebody keeps in step by hand.

The endpoints are #47, #48 and #49, and the framework that serves them is
chosen there. What is decided here is what they are all held to:
`docs/decisions/0003-api.md` argues it, and the description is where an
integration reads it.
"""

from __future__ import annotations

from retusche.api.description import (
    DESCRIPTION_PATH,
    interface_description,
    render_description,
)
from retusche.api.refusal import (
    STATUS_FOR_REASON,
    Reason,
    Refusal,
    RefusalError,
)
from retusche.api.surface import (
    API_MAJOR_VERSION,
    PATH_PREFIX,
)

__all__ = [
    "API_MAJOR_VERSION",
    "DESCRIPTION_PATH",
    "PATH_PREFIX",
    "STATUS_FOR_REASON",
    "Reason",
    "Refusal",
    "RefusalError",
    "interface_description",
    "render_description",
]
