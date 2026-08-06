"""The retention window the orchestration layer reports."""

from __future__ import annotations

import retusche


def test_the_retention_window_is_a_positive_number_of_seconds() -> None:
    assert retusche.default_retention_seconds() > 0
