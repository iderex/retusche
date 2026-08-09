# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What a mask is, and what is refused before a job is recorded.

A mask says which pixels of a photograph may be changed. Getting it slightly
wrong does not look like a bad request, it looks like a bad model: a mask one
pixel narrower than the image shifts every row against the pixels it was meant
to name, and an inverted mask removes the thing the caller wanted to keep.
Neither produces an error anywhere further down. Both produce a result.

The representations
-------------------
Two, and each says what a value means.

`MaskBuffer` from the engine contract is the pixel representation: one byte per
pixel, ``height * width`` of them, row major. Zero means keep the pixel. Any
non-zero value means the pixel is inside the edit, which is the contract's own
sentence and not this module's to change. What this module adds is what the
values between mean: coverage. 255 is a pixel wholly inside the edit and 128 is
one the edit's boundary passes through, and BOTH ARE INSIDE IT. A ramp is a
statement about how much of a pixel is covered, never about whether it is.

That matters at the edge of a shape and it is the thing an integrator gets
wrong. An anti-aliased outline drawn by a painting tool puts a one or two pixel
ramp around everything it draws, and every pixel of that ramp is edited. The
mask is therefore wider than the shape that was drawn, by exactly the width of
the ramp. `MaskReading` counts those pixels so a caller can see it rather than
infer it from a result.

`retusche.masking.geometry` is the other representation: shapes, rasterised
here rather than by each caller. It exists because asking every integration for
per-pixel bytes means asking every integration to write a rasteriser, and five
rasterisers disagreeing at the edges is five different meanings for one request.

What this module does not do
----------------------------
It does not decode anything. A mask arrives here as bytes whose shape is already
stated, and turning a PNG somebody uploaded into those bytes is #51's, where the
input is untrusted and the decoder is the attack surface.

It does not know what a caller meant. An inverted mask is a valid mask of the
complement, and no reading of the bytes distinguishes one from the other. What
is offered instead is `MaskReading.changed_fraction`, so a surface can put the
number in front of a person before the device is spent on it. That is a
disclosure and not a check, and the suite says so by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from retusche_contracts.engine import ImageBuffer, MaskBuffer

__all__ = [
    "CHANGE",
    "KEEP",
    "MaskError",
    "MaskReading",
    "read_mask_for_image",
]

KEEP: Final = 0
"""The one value that means leave this pixel alone."""

CHANGE: Final = 255
"""Wholly inside the edit. Every value from 1 to 254 is inside it too."""


class MaskError(Exception):
    """A mask this project refuses, with the reason in the message."""


@dataclass(frozen=True, slots=True)
class MaskReading:
    """What a mask says, once it has been accepted.

    Counts rather than a verdict. Every mask that reaches this type has already
    been refused or accepted; what is left is the part a caller has to decide
    about, and a surface showing a person what is about to be edited needs the
    numbers rather than a boolean.
    """

    width: int
    height: int

    changed_pixels: int
    """Pixels the edit reaches: every byte that is not zero."""

    partial_pixels: int
    """Pixels on a coverage ramp: every byte from 1 to 254.

    These are inside the edit and are counted separately because they are the
    ones a caller did not draw. A ramp of two pixels around a shape is a mask
    two pixels wider than the shape.
    """

    @property
    def total_pixels(self) -> int:
        """Pixels in the mask, which is the pixels in the image it matches."""
        return self.width * self.height

    @property
    def changed_fraction(self) -> float:
        """How much of the photograph this edit reaches, from 0.0 to 1.0.

        The number to put in front of a person before a device is spent. An
        inverted mask of a small object reads near 1.0 here, and that is the
        only warning available: see the module docstring.
        """
        return self.changed_pixels / self.total_pixels

    @property
    def is_binary(self) -> bool:
        """True where every byte is `KEEP` or `CHANGE` and nothing between."""
        return self.partial_pixels == 0

    @property
    def covers_everything(self) -> bool:
        """True where no pixel is left alone, so the whole frame is edited."""
        return self.changed_pixels == self.total_pixels


def read_mask_for_image(mask: MaskBuffer, image: ImageBuffer) -> MaskReading:
    """The reading of a mask that may be used on this image, or a refusal.

    The refusals, in the order they are made, because the first one that applies
    is the one whose message a caller sees:

    A mask whose declared shape and carried bytes disagree. Nothing downstream
    reads the length; every index is computed from the width, so a short buffer
    is read off the end of a row and a long one silently drops its tail.

    A mask whose dimensions are not the image's, exactly. Resizing here would
    turn a caller's off-by-one into a soft-focus edit whose boundary is a
    fraction of a pixel away from where they put it, and nothing about the
    result would say so.

    A mask of zeroes. Such a request reaches the device, holds the one lane,
    and returns the photograph it was given. The engine contract separately
    requires an engine to handle a zero mask and leave every pixel alone, and
    that is not a contradiction: an engine is reached from the hardware harness
    and from the contract suite as well as from here, so its behaviour is
    defined for a request this layer does not send it.

    A mask covering everything is NOT refused. It is a real request, it is what
    an operator asking for the whole frame to be regenerated means, and
    `MaskReading.covers_everything` says so to whoever wants to ask again.
    """
    _refuse_shape(mask.width, mask.height, len(mask.data))
    if (mask.width, mask.height) != (image.width, image.height):
        raise MaskError(
            f"the mask is {mask.width}x{mask.height} and the image is "
            f"{image.width}x{image.height}. A mask names pixels of one image "
            f"by position, so a mask of another size names different pixels, "
            f"and resizing it here would move an edit's boundary without "
            f"anything in the result saying it had moved."
        )
    changed = 0
    partial = 0
    for value in mask.data:
        if value != KEEP:
            changed += 1
            if value != CHANGE:
                partial += 1
    if changed == 0:
        raise MaskError(
            f"this mask leaves every one of its {mask.width * mask.height} "
            f"pixels alone, so the edit it describes is the photograph it was "
            f"given. Such a request holds the device for the length of a run "
            f"and returns the input, and the caller reading that result cannot "
            f"tell it from an edit that did nothing."
        )
    return MaskReading(
        width=mask.width,
        height=mask.height,
        changed_pixels=changed,
        partial_pixels=partial,
    )


def _refuse_shape(width: int, height: int, carried: int) -> None:
    """Refuse a declared shape that is not a shape, or bytes that are not it."""
    if width <= 0 or height <= 0:
        raise MaskError(
            f"the mask declares {width}x{height}, and a mask has a positive "
            f"width and a positive height. A dimension of zero describes no "
            f"pixels while carrying the arithmetic of an image that has some."
        )
    declared = width * height
    if carried != declared:
        raise MaskError(
            f"the mask declares {width}x{height}, which is {declared} bytes at "
            f"one byte per pixel, and carries {carried}. Every read of a mask "
            f"computes its index from the width, so a buffer of another length "
            f"is not a smaller mask, it is this mask with rows taken from the "
            f"wrong place."
        )
