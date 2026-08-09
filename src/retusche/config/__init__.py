# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Configuration: one declared surface, validated whole, refused when wrong.

`retusche.config.settings` is where every setting is declared and is the only
place one may be. `retusche.config.loading` reads the three sources and refuses
the whole configuration at once. `retusche.config.secret` holds the type a value
declared as a secret is handed over in, which renders as `REDACTED` however it
is formatted. `retusche.config.reference` writes the operator reference page
from the declaration, so the page cannot describe a surface that has moved.

Nothing here reads a file or the process environment on its own. The loader is
handed the text and the mapping, because the entry point that would fetch them
is not in this tree and a module that reaches for `os.environ` is one the suite
cannot exercise without arranging the host.
"""

from __future__ import annotations

from retusche.config.loading import (
    Configuration,
    ConfigurationError,
    load,
)
from retusche.config.reference import reference_markdown
from retusche.config.secret import REDACTED, Secret
from retusche.config.settings import (
    ENVIRONMENT_PREFIX,
    SETTINGS,
    Kind,
    Setting,
    environment_name,
)

__all__ = [
    "ENVIRONMENT_PREFIX",
    "REDACTED",
    "SETTINGS",
    "Configuration",
    "ConfigurationError",
    "Kind",
    "Secret",
    "Setting",
    "environment_name",
    "load",
    "reference_markdown",
]
