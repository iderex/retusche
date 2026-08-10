# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What the path promises, and what may change while it stays the same.

The surface is versioned in the path. `PATH_PREFIX` is the one place that
string is written, so an endpoint cannot be mounted at a version nobody
declared and the description cannot advertise a different one from the router.

The compatibility rule is prose, and `docs/decisions/0003-api.md` is where it is
argued. Nothing here refuses a breaking change: a check that read two versions
of this surface and judged one against the other would need the previous one to
compare against, and there is no previous one. What this module does hold is the
number, in a single place, so raising it is a change to one line that a reviewer
sees rather than a string edited in whichever files somebody remembered.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "API_MAJOR_VERSION",
    "PATH_PREFIX",
]

#: The major version the path carries. Only the major number appears in a URL:
#: a caller pins the promise, and a promise is either kept or it is not, so
#: there is nothing for a minor number to say to a client. What the release
#: version says, and how it relates to this one, is #89's.
API_MAJOR_VERSION: Final = 1

#: Where every endpoint is mounted. Built from the number above rather than
#: written beside it, because two spellings of one version is the drift this
#: whole module exists to make impossible.
PATH_PREFIX: Final = f"/api/v{API_MAJOR_VERSION}"
