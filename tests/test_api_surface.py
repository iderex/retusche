# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""The surface's promises, and the check that the committed description keeps them.

The last two tests are a pair and neither means much alone. The first compares
the committed document against a fresh generation, which is the drift check the
issue asks for. The second builds a description of a surface this one is not and
shows the comparison going red, because a check that has never been seen to fail
is a check nobody has reason to trust.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest

from retusche.api import (
    API_MAJOR_VERSION,
    DESCRIPTION_PATH,
    PATH_PREFIX,
    STATUS_FOR_REASON,
    Reason,
    Refusal,
    RefusalError,
    interface_description,
    render_description,
)

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent


def _committed_description() -> str:
    """The document as it is stored, read as text so the comparison is textual."""
    return (_REPO_ROOT / DESCRIPTION_PATH).read_text(encoding="utf-8")


def test_the_path_prefix_is_built_from_the_declared_version() -> None:
    """One version, one place. A second spelling is what this refuses."""
    assert PATH_PREFIX.removeprefix("/api/v") == str(API_MAJOR_VERSION)


def test_every_reason_is_answered_with_a_declared_status() -> None:
    """No default, so a reason added without a status cannot reach the wire."""
    assert set(STATUS_FOR_REASON) == set(Reason)


def test_a_refusal_reports_the_status_its_reason_declares() -> None:
    refusal = Refusal(reason=Reason.UNKNOWN_JOB, message="No job by that identifier.")

    assert refusal.status == STATUS_FOR_REASON[Reason.UNKNOWN_JOB]


def test_a_refusal_about_one_input_names_it() -> None:
    refusal = Refusal(
        reason=Reason.UNSUPPORTED_REQUEST,
        message="This engine takes no prompt.",
        parameter="prompt",
    )

    assert refusal.as_payload() == {
        "reason": "unsupported_request",
        "message": "This engine takes no prompt.",
        "parameter": "prompt",
    }


def test_a_refusal_about_no_input_carries_the_field_as_null() -> None:
    """Present and null, so a client reads one shape and never asks about a key."""
    refusal = Refusal(reason=Reason.INTERNAL, message="Something went wrong.")

    assert refusal.as_payload() == {
        "reason": "internal",
        "message": "Something went wrong.",
        "parameter": None,
    }


@pytest.mark.parametrize("message", ["", "   "])
def test_a_refusal_without_a_sentence_is_refused(message: str) -> None:
    """A code with nothing to show is the failure the shape exists against."""
    with pytest.raises(RefusalError, match="carries no sentence"):
        Refusal(reason=Reason.INVALID_MASK, message=message)


@pytest.mark.parametrize("parameter", ["", "  "])
def test_a_refusal_naming_a_blank_parameter_is_refused(parameter: str) -> None:
    """Blank is not the same statement as absent, and it serialises just as well."""
    with pytest.raises(RefusalError, match="blank parameter"):
        Refusal(
            reason=Reason.INVALID_MASK,
            message="The mask is not one this service accepts.",
            parameter=parameter,
        )


def test_the_description_enumerates_every_reason_and_its_status() -> None:
    """What a caller branches on, without reading a sentence of prose."""
    description: Any = interface_description()

    schema = description["components"]["schemas"]["Refusal"]
    assert schema["properties"]["reason"]["enum"] == sorted(
        reason.value for reason in Reason
    )
    assert description["x-retusche-refusal-status"] == {
        reason.value: status for reason, status in STATUS_FOR_REASON.items()
    }


def test_the_description_mounts_the_surface_at_the_declared_prefix() -> None:
    description: Any = interface_description()

    assert [server["url"] for server in description["servers"]] == [PATH_PREFIX]


def test_the_committed_description_matches_the_code() -> None:
    """The drift check. A surface that moved without the document is red here."""
    assert _committed_description() == render_description(interface_description())


def test_the_drift_check_refuses_a_description_the_committed_file_does_not_carry() -> (
    None
):
    """The near miss: one reason code added and the document left alone.

    The vocabulary is a parameter for exactly this, so the surface described
    here differs from the real one by the smallest thing a change to
    `Reason` would do.
    """
    widened = {
        **{reason.value: status for reason, status in STATUS_FOR_REASON.items()},
        "quota_exhausted": 429,
    }

    assert _committed_description() != render_description(
        interface_description(widened)
    )


def test_the_committed_description_is_the_json_it_claims_to_be() -> None:
    """Read back rather than assumed: the file an integrator opens has to parse."""
    assert json.loads(_committed_description())["openapi"] == "3.1.0"
