# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: GPL-3.0-only

"""Where this service keeps what it writes.

One module so the layout is stated once, rather than a path literal appearing
next to each thing that writes.
"""

from __future__ import annotations

from pathlib import Path

RESULTS_DIRECTORY = Path("var") / "results"
