"""The half of the near miss that gets written, removed with it."""

from __future__ import annotations

from retusche._near_miss import describe_size


def test_a_large_image_is_described_as_large() -> None:
    assert describe_size(4_000_000) == "large"
