# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Orchestration layer: HTTP surface, job model, model management, library client.

This package must stay importable in a process that listens on a socket, so it
may depend on ``retusche_contracts`` and nothing heavier. It may not import
``retusche_worker`` or any machine-learning runtime; issue #7 holds the test
that refuses such an import.
"""

__all__ = ["__version__"]

__version__ = "0.0.0"
