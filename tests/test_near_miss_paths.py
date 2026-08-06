# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The layout this service writes into."""

from __future__ import annotations

from retusche._paths import RESULTS_DIRECTORY


def test_results_are_kept_under_var() -> None:
    assert RESULTS_DIRECTORY.parts[0] == "var"
