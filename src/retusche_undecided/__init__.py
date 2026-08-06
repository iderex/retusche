"""Near miss for the coverage-scope rule, removed in the commit that ends it.

A package arriving under ``src/`` with nobody having said whether it is measured.
It is valid, typed and importable, so no other gate has anything to say about it,
and a report that simply left it out would read exactly like a report where it
was measured and found complete.
"""

__all__: list[str] = []
