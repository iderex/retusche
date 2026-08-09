# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Shapes, and the one rule that turns them into pixels.

A caller who wants to erase a lamppost has a rectangle around it, not a byte per
pixel. Rasterising here rather than in each integration is the difference
between one meaning for that rectangle and one meaning per integration, and the
disagreements between them all live at the edge, which is where a mask is read
most closely.

The rule
--------
A PIXEL IS COVERED WHEN ITS CENTRE IS INSIDE THE SHAPE. The centre of the pixel
in column ``c`` and row ``r`` is at ``(c + 0.5, r + 0.5)``, so a shape's own
coordinates name the grid lines between pixels rather than the pixels.

That makes every shape half-open on its far side and makes the arithmetic come
out whole: a rectangle at ``x = 2`` with ``width = 3`` covers columns 2, 3 and 4
and never column 5, and two rectangles laid side by side cover each column once.
The alternative, a pixel covered when the shape touches it at all, grows every
shape by a pixel on each side and makes two abutting rectangles overlap on the
seam.

The half offset also buys something worth naming: a pixel centre never lands on
a whole-numbered boundary, so for a shape whose coordinates are whole numbers,
``<`` and ``<=`` at that boundary select the same pixels. The off-by-one this
kind of code usually carries cannot be written here. What can still be written
wrong is the arithmetic inside the comparison and the point being sampled, and
those are what the suite is aimed at.

A shape may hang off the canvas and is clipped. A shape that is wholly off it is
refused, because it is a caller's coordinate mistake and the mask it produces is
empty, which reads as a different mistake by the time anything else sees it.

Feathering
----------
``feather_pixels`` is a whole number of pixels, and it is measured OUTWARD from
the covered region: a feather of 2 makes the mask two pixels wider on every
side than the shape. Zero, the default, is a hard edge.

Distance is Chebyshev, so the ramp is square rather than round: a pixel is at
distance ``d`` when it is ``d`` steps away counting a diagonal step as one. A
round ramp would need a distance transform and would still be an approximation
of a blur nobody specified; a square one is exactly reproducible in one sentence
and its corners are the only place it differs.

The value on ring ``d`` is ``255 * (feather + 1 - d) // (feather + 1)``, integer
division, so a feather of 1 puts 127 around the shape and a feather of 3 puts
191, 127 and 63. Every one of those pixels is INSIDE the edit, because the
contract's rule is that anything non-zero is: see `retusche.masking.mask`. A
feather widens what is edited. It does not make an edge tentative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from retusche.masking.mask import CHANGE, KEEP, MaskError
from retusche_contracts.engine import MaskBuffer

__all__ = [
    "MAX_FEATHER_PIXELS",
    "Ellipse",
    "Polygon",
    "Rectangle",
    "Shape",
    "rasterise",
]

MAX_FEATHER_PIXELS = 254
"""The widest ramp whose outermost ring is still a pixel inside the edit.

At 255 the last ring computes to zero under the rule above, and a zero is the
one value that means keep. A mask silently one ring narrower than the feather
asked for is worse than a refusal, so the refusal is here.
"""


@runtime_checkable
class Shape(Protocol):
    """A region, asked two questions: where it might be, and what it contains."""

    def pixel_bounds(self) -> tuple[int, int, int, int]:
        """The half-open column and row range that can hold a covered centre.

        ``(left, top, right, bottom)``, with ``right`` and ``bottom`` one past
        the last. Outside it nothing is covered, so it bounds the scan; it may
        be generous and may not be short.
        """
        ...

    def contains(self, x: float, y: float) -> bool:
        """Whether the point is inside this shape, half-open on the far side."""
        ...


@dataclass(frozen=True, slots=True)
class Rectangle:
    """An axis-aligned box, from ``(x, y)`` across ``width`` and ``height``."""

    x: int
    y: int
    width: int
    height: int

    def pixel_bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


@dataclass(frozen=True, slots=True)
class Ellipse:
    """The ellipse inscribed in the box ``(x, y, width, height)``.

    Declared by its box rather than by a centre and two radii so that it lands
    on the same grid as `Rectangle`. A centre written as a whole number would
    sit on the line between two pixels, and the shape would be a half pixel from
    where a caller drew it in whichever direction the arithmetic fell.
    """

    x: int
    y: int
    width: int
    height: int

    def pixel_bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def contains(self, x: float, y: float) -> bool:
        radius_x = self.width / 2
        radius_y = self.height / 2
        offset_x = (x - (self.x + radius_x)) / radius_x
        offset_y = (y - (self.y + radius_y)) / radius_y
        return offset_x * offset_x + offset_y * offset_y <= 1.0


@dataclass(frozen=True, slots=True)
class Polygon:
    """A closed outline through whole-numbered vertices, in order.

    Inside is decided by the even-odd rule: a ray cast from the point crosses
    the outline an odd number of times. Where the outline crosses itself, that
    makes the overlap a hole rather than a doubly filled region, which is the
    convention every drawing surface a caller will have used takes.
    """

    points: tuple[tuple[int, int], ...]

    def pixel_bounds(self) -> tuple[int, int, int, int]:
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def contains(self, x: float, y: float) -> bool:
        inside = False
        previous_x, previous_y = self.points[-1]
        for current_x, current_y in self.points:
            if (current_y > y) != (previous_y > y):
                crossing_x = (previous_x - current_x) * (y - current_y) / (
                    previous_y - current_y
                ) + current_x
                if x < crossing_x:
                    inside = not inside
            previous_x, previous_y = current_x, current_y
        return inside


def rasterise(
    shapes: tuple[Shape, ...],
    width: int,
    height: int,
    feather_pixels: int = 0,
) -> MaskBuffer:
    """The mask covering every shape, on a ``width`` by ``height`` canvas.

    Shapes are combined by union: a pixel covered by any of them is covered.
    Overlap is not counted twice, because coverage is a property of a pixel and
    not of how many shapes reached it.

    The result is a mask and not yet an accepted one. Whether it may be used
    against a given image is `retusche.masking.mask.read_mask_for_image`, which
    is the one place that decision is made.
    """
    _refuse_canvas(width, height)
    _refuse_feather(feather_pixels)
    if not shapes:
        raise MaskError(
            "no shape was given, so this would rasterise to a mask that leaves "
            "every pixel alone. An empty request is refused where it is "
            "written rather than where its consequences are read."
        )
    covered = _covered_pixels(shapes, width, height)
    values = bytearray(width * height)
    for index in covered:
        values[index] = CHANGE
    _apply_feather(values, covered, width, height, feather_pixels)
    return MaskBuffer(data=bytes(values), width=width, height=height)


def _covered_pixels(shapes: tuple[Shape, ...], width: int, height: int) -> set[int]:
    """The indices every shape covers, refusing one that covers nothing."""
    covered: set[int] = set()
    for position, shape in enumerate(shapes):
        left, top, right, bottom = shape.pixel_bounds()
        reached = 0
        for row in range(max(top, 0), min(bottom, height)):
            centre_y = row + 0.5
            offset = row * width
            for column in range(max(left, 0), min(right, width)):
                if shape.contains(column + 0.5, centre_y):
                    covered.add(offset + column)
                    reached += 1
        if reached == 0:
            raise MaskError(
                f"shape {position}, a {type(shape).__name__} whose bounds are "
                f"{(left, top, right, bottom)}, covers no pixel of a "
                f"{width}x{height} canvas. A shape placed off the canvas, or "
                f"one thinner than the gap between two pixel centres, produces "
                f"an empty region, and an empty region is indistinguishable "
                f"from a shape that was never sent."
            )
    return covered


def _apply_feather(
    values: bytearray,
    covered: set[int],
    width: int,
    height: int,
    feather_pixels: int,
) -> None:
    """Write the ramp outward from ``covered``, one Chebyshev ring at a time."""
    frontier = covered
    reached = set(covered)
    for distance in range(1, feather_pixels + 1):
        ring = _neighbours(frontier, width, height) - reached
        value = CHANGE * (feather_pixels + 1 - distance) // (feather_pixels + 1)
        for index in ring:
            values[index] = value
        reached |= ring
        frontier = ring


def _neighbours(indices: set[int], width: int, height: int) -> set[int]:
    """Every pixel one step from one of ``indices``, diagonals counted as one."""
    found: set[int] = set()
    for index in indices:
        row, column = divmod(index, width)
        for row_step in (-1, 0, 1):
            neighbour_row = row + row_step
            if not 0 <= neighbour_row < height:
                continue
            for column_step in (-1, 0, 1):
                neighbour_column = column + column_step
                if 0 <= neighbour_column < width:
                    found.add(neighbour_row * width + neighbour_column)
    return found


def _refuse_canvas(width: int, height: int) -> None:
    """Refuse a canvas that is not one."""
    if width <= 0 or height <= 0:
        raise MaskError(
            f"a {width}x{height} canvas holds no pixel, so nothing rasterised "
            f"onto it can be a mask of an image. The canvas is the image's own "
            f"size, and an image of no size is refused where it is decoded."
        )


def _refuse_feather(feather_pixels: int) -> None:
    """Refuse a ramp that is negative or wider than its outermost ring."""
    if feather_pixels < 0:
        raise MaskError(
            f"feather_pixels is {feather_pixels}, and a feather is a whole "
            f"number of pixels measured outward from the shape. There is no "
            f"inward feather here: shrinking the edited region is a smaller "
            f"shape, which the caller already has."
        )
    if feather_pixels > MAX_FEATHER_PIXELS:
        raise MaskError(
            f"feather_pixels is {feather_pixels}, and the widest ramp whose "
            f"outermost ring is still inside the edit is "
            f"{MAX_FEATHER_PIXELS}. Beyond it that ring computes to "
            f"{KEEP}, which is the value meaning keep, so the mask would be "
            f"narrower than the feather asked for and nothing would say so."
        )
