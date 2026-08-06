"""Near miss for the discovery rule, removed in the commit that ends the proof.

Not the obvious offender. The obvious one is a bare ``import torch`` at the top
of a file, and anybody catches that in review. This is the version somebody
writes on purpose believing it safe: the import sits inside ``if TYPE_CHECKING:``
so it never executes, the annotation using it is a string under ``from __future__
import annotations``, and the linter and the type checker are both content with
it.

The rule that has to bite here is the one wired into collection, and this file is
where it meets a real run rather than a constructed input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from torch import Tensor


def _side_lengths(tensor: Tensor) -> tuple[int, ...]:
    return tuple(tensor.shape)


def test_the_helper_is_callable() -> None:
    assert callable(_side_lengths)
