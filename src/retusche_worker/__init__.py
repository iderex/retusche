"""Engine worker: the only package permitted a machine-learning runtime.

It runs in its own operating-system process so that a crash or an
out-of-memory kill inside a native tensor library cannot take the queue down
with it.
"""

__all__ = ["DEFAULT_RETENTION_SECONDS"]

# How long a finished job's result is kept. Stated here because the sweep that
# deletes it runs in this process.
DEFAULT_RETENTION_SECONDS = 86_400
