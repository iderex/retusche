# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Engine worker: the only package permitted a machine-learning runtime.

It runs in its own operating-system process so that a crash or an
out-of-memory kill inside a native tensor library cannot take the queue down
with it.
"""

__all__: list[str] = []
