"""Near miss for the coverage floor, removed in the commit that ends the proof.

Every line below is executed by the test beside it. What is not executed is one
edge: the path where the condition is false and the label keeps the value it was
given. Line coverage calls this file complete, which is the mistake the floor is
set with branch coverage on to catch.
"""

from __future__ import annotations


def describe_size(pixels: int) -> str:
    label = "small"
    if pixels > 1_000_000:
        label = "large"
    return label
