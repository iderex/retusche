"""Orchestration layer: HTTP surface, job model, model management, library client.

This package must stay importable in a process that listens on a socket, so it
may depend on ``retusche_contracts`` and nothing heavier. It may not import
``retusche_worker`` or any machine-learning runtime, and
``tests/test_import_boundary.py`` walks the import graph of this package and
refuses a chain that reaches one.
"""

__all__ = ["__version__"]

__version__ = "0.0.0"
