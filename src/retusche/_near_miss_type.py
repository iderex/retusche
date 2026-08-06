"""A near miss for the strict type gate, removed once the red run is recorded.

The mistake is the one a reader skims past: the annotation says the function
hands back text and the body hands back the number it was given.
"""


def widen(value: int) -> str:
    return value
