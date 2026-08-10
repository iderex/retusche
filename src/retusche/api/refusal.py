# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""One shape for every refusal, and the closed set of reasons it may carry.

A refusal carries two things that are read by two different readers. `reason` is
a stable string an integration branches on. `message` is a sentence for whoever
is looking at a screen, and it may be rewritten in any release, because nothing
is allowed to parse it. Where the refusal is about one named input, `parameter`
says which, so a client can point at the field rather than at the form.

Why the reason is a closed set
------------------------------
An open set is a string each endpoint invents, and two endpoints then refuse the
same condition under two spellings that a client has to learn separately. The
set here is closed and every member stands for a refusal that already exists
somewhere in this tree, named in its comment below. A condition without such a
home is not given a code in advance: a code nothing raises is a promise to a
caller that this service can tell them something it cannot.

Adding a member is a compatible change and removing one is not, which is
`docs/decisions/0003-api.md`'s rule rather than this module's. It follows that a
caller meets codes it has never seen, on a service it did not upgrade in step
with, so the rule the record states for the client side is that an unrecognised
code is read as unclassified and the sentence is what gets shown. Nothing here
can enforce that; it is written where the promise is made.

The status is part of the shape
-------------------------------
An integration that reads the code still has to decide whether to retry, and the
status is what carries that on the wire. `STATUS_FOR_REASON` is the whole of the
mapping and there is no default in it: a reason without a status would answer as
whatever the framework picked, differently per endpoint, which is the same
inconsistency the single shape exists to remove.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "STATUS_FOR_REASON",
    "Reason",
    "Refusal",
    "RefusalError",
]


@unique
class Reason(StrEnum):
    """What a refusal is, in a word a machine reads.

    The value is the wire form and the member name is not, so renaming a member
    is a change to this file alone and rewriting a value is a change to every
    integration.
    """

    #: The selected engine's own declaration does not admit the request.
    #: `retusche_contracts.UnsupportedRequest` is the engine-side refusal this
    #: stands for, and #21 is where the edge learns to refuse before a job is
    #: queued rather than when one runs.
    UNSUPPORTED_REQUEST = "unsupported_request"

    #: The mask is not one this service accepts.
    #: `retusche.masking.MaskError` is the refusal, and what a mask is was
    #: decided in #46.
    INVALID_MASK = "invalid_mask"

    #: The model the request names cannot be served.
    #: `retusche_contracts.ModelNotAvailable` is the refusal.
    MODEL_NOT_AVAILABLE = "model_not_available"

    #: The job does not fit the device memory the operator allowed.
    #: `retusche.queue.OverBudgetError` is the refusal, and the budget it is
    #: measured against was decided in #30.
    OVER_BUDGET = "over_budget"

    #: No job by that identifier. `retusche.queue.UnknownJobError`.
    UNKNOWN_JOB = "unknown_job"

    #: The job is not in a state where the requested move is legal, which is
    #: what cancelling an already finished job asks for.
    #: `retusche.queue.IllegalTransitionError`.
    ILLEGAL_TRANSITION = "illegal_transition"

    #: The service could not classify what went wrong. It carries no detail on
    #: purpose: what a caller would find useful here is also what an attacker
    #: would, and the operator has the log.
    INTERNAL = "internal"


#: The status each reason is answered with. Total over `Reason` by construction
#: and by the test that compares the two sets, so an added member without a
#: status is a red suite rather than a surprise on the wire.
STATUS_FOR_REASON: Final[Mapping[Reason, int]] = {
    # Well formed, and unservable as asked. Not 400: nothing about the request
    # is malformed, and a client that retries after fixing its syntax retries
    # forever.
    Reason.UNSUPPORTED_REQUEST: 422,
    Reason.INVALID_MASK: 422,
    Reason.MODEL_NOT_AVAILABLE: 422,
    # The picture is too large for the memory the operator allowed. A caller
    # can act on this by sending a smaller one, which is why it is not 422.
    Reason.OVER_BUDGET: 413,
    Reason.UNKNOWN_JOB: 404,
    # The job exists and is somewhere else. Retrying the same move never
    # succeeds; reading the job's state says why.
    Reason.ILLEGAL_TRANSITION: 409,
    Reason.INTERNAL: 500,
}


class RefusalError(Exception):
    """A refusal that could not be built, which is a defect in this service."""


@dataclass(frozen=True, slots=True)
class Refusal:
    """The body every endpoint answers a refusal with.

    Frozen because a refusal is answered and not amended, and because the same
    instance is what the log and the response are both built from.
    """

    reason: Reason
    message: str
    parameter: str | None = None

    def __post_init__(self) -> None:
        """Refuse the two shapes that would reach a caller as an empty field.

        A blank message is the failure this class exists against: the caller
        gets a code and nothing to show, and whoever wrote the endpoint has no
        way of knowing, because a blank string serialises perfectly well.
        """
        if not self.message.strip():
            message = f"a {self.reason.value} refusal carries no sentence"
            raise RefusalError(message)
        if self.parameter is not None and not self.parameter.strip():
            message = (
                f"a {self.reason.value} refusal names a blank parameter; "
                "omit the field where the refusal is not about one"
            )
            raise RefusalError(message)

    @property
    def status(self) -> int:
        """The status this refusal is answered with."""
        return STATUS_FOR_REASON[self.reason]

    def as_payload(self) -> dict[str, str | None]:
        """The body, with the fields the description declares and no others.

        `parameter` is present and null rather than absent when the refusal is
        not about one input, so a client reads one shape and never has to ask
        whether a missing key means anything.
        """
        return {
            "reason": self.reason.value,
            "message": self.message,
            "parameter": self.parameter,
        }
