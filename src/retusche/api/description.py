# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The interface description, built from the surface rather than beside it.

An integration builds against a description, so the description is the thing
that has to be true. Written by hand it is true on the day it is written and
slowly stops being: a field is renamed, a refusal gains a code, and nothing in
the tree notices, because a document is not run by anything.

So it is generated here from the same declarations the service answers with,
committed to the tree at `DESCRIPTION_PATH`, and compared against a fresh
generation by the suite. A change to the surface that leaves the committed file
alone is a red run, which is the only reason to keep a copy of a generated thing
under version control at all: an integrator reads it without installing this
project, and a reviewer sees the diff of what a change promises.

What is in it today
-------------------
The refusal shape, the closed set of reasons, the status each is answered with,
and the path the surface is mounted at. No endpoint: they are #47, #48 and #49,
and each of them extends this document rather than starting one. A description
that arrived with the first endpoint would have been written to fit that
endpoint, and the second would have had to argue its way out of it.

What it is not
--------------
It is not a claim that anything serves these paths. Nothing here runs an HTTP
server, and which framework does is chosen with the first endpoint. The document
describes the promise; the endpoints keep it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

from retusche.api.refusal import STATUS_FOR_REASON
from retusche.api.surface import API_MAJOR_VERSION, PATH_PREFIX

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "DESCRIPTION_PATH",
    "interface_description",
    "render_description",
]

#: Where the generated document is committed, relative to the repository root.
#: The suite resolves it from there; nothing at runtime reads the file, because
#: the service answers from the declarations and not from a copy of them.
DESCRIPTION_PATH: Final = "docs/api/openapi.json"

#: The OpenAPI revision this document is written to. 3.1 rather than 3.0 for
#: one reason that matters here: 3.1's schemas are JSON Schema, so a nullable
#: field is a type union a validator already understands instead of a keyword
#: only OpenAPI tooling reads.
_OPENAPI_VERSION: Final = "3.1.0"


def _default_statuses() -> Mapping[str, int]:
    """The real mapping, keyed by the wire string the description carries."""
    return {reason.value: status for reason, status in STATUS_FOR_REASON.items()}


def interface_description(
    statuses: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Build the description from the surface's own declarations.

    `statuses` is the refusal vocabulary, wire string to status. It is a
    parameter rather than a read of the module constant so the suite can build
    a description of a surface this one is not, and show that the committed
    file stops matching. A generator nothing can make disagree is a generator
    whose comparison proves nothing.
    """
    vocabulary = _default_statuses() if statuses is None else statuses
    reasons = sorted(vocabulary)
    return {
        "openapi": _OPENAPI_VERSION,
        "info": {
            "title": "retusche",
            "summary": "Self-hosted backend for generative photo editing.",
            "version": str(API_MAJOR_VERSION),
            "license": {"name": "AGPL-3.0-only", "identifier": "AGPL-3.0-only"},
        },
        "servers": [{"url": PATH_PREFIX, "description": "The versioned surface."}],
        # Empty rather than absent. An absent key reads as a document that
        # forgot to say; an empty one says there are no endpoints yet.
        "paths": {},
        "components": {
            "schemas": {
                "Refusal": {
                    "type": "object",
                    "description": (
                        "The body of every refusal. Branch on reason; show "
                        "message; never parse message."
                    ),
                    "required": ["reason", "message", "parameter"],
                    "additionalProperties": False,
                    "properties": {
                        "reason": {"type": "string", "enum": reasons},
                        "message": {"type": "string", "minLength": 1},
                        "parameter": {
                            "type": ["string", "null"],
                            "description": (
                                "The input the refusal is about, or null where "
                                "it is about none."
                            ),
                        },
                    },
                }
            },
            "responses": {
                "Refused": {
                    "description": "The request was refused.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Refusal"}
                        }
                    },
                }
            },
        },
        # An extension because OpenAPI has nowhere to say it outside a response
        # this document has no endpoint to hang. A caller reading the status off
        # the wire needs none of it; a caller generating a client from this file
        # ahead of the endpoints does.
        "x-retusche-refusal-status": {reason: vocabulary[reason] for reason in reasons},
    }


def render_description(description: Mapping[str, object]) -> str:
    """Render the document to the exact bytes the committed file holds.

    Sorted keys and a fixed indent, so a regeneration that changed nothing
    produces no diff, and one that changed something produces a diff about the
    change rather than about dictionary ordering.
    """
    return json.dumps(description, indent=2, sort_keys=True) + "\n"
