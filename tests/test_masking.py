# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""What a mask is, what is refused, and where the rasterisation rule lands.

The three mistakes #46 names are each written here on purpose rather than
described. The off-by-one is a mask one pixel narrower than its image, which is
what a caller gets from a rounding error in whatever produced it. The inverted
mask is the complement of a small object, which is a valid mask nothing can tell
from an intended one, and the test says so instead of pretending to catch it.
The anti-aliased edge is a ramp of values between the two extremes, and the
thing worth asserting about it is that every one of those pixels is inside the
edit.

The rasterisation tests are at the edges by construction: a shape one pixel
wide, a shape abutting another, a shape whose far side falls exactly on a pixel
boundary. A rasteriser tested only in the middle of a large rectangle is one
whose off-by-one is still there.

No device, no display and no elevation is needed by anything here.
"""

from __future__ import annotations

import pytest

from retusche.masking import (
    CHANGE,
    KEEP,
    MAX_FEATHER_PIXELS,
    Ellipse,
    MaskError,
    Polygon,
    Rectangle,
    Shape,
    rasterise,
    read_mask_for_image,
)
from retusche_contracts.engine import ImageBuffer, MaskBuffer


def _image(width: int, height: int) -> ImageBuffer:
    """Three channels of nothing, because no test here reads a pixel of it."""
    return ImageBuffer(
        data=bytes(width * height * 3), width=width, height=height, channels=3
    )


def _mask(width: int, height: int, value: int) -> MaskBuffer:
    return MaskBuffer(
        data=bytes([value]) * (width * height), width=width, height=height
    )


def _columns(mask: MaskBuffer, row: int) -> str:
    """One row as a string, so an assertion about an edge reads as a picture."""
    start = row * mask.width
    return "".join(
        "." if value == KEEP else ("#" if value == CHANGE else "+")
        for value in mask.data[start : start + mask.width]
    )


def test_a_mask_matching_its_image_is_read_rather_than_refused() -> None:
    mask = bytearray(4 * 3)
    mask[0] = CHANGE
    mask[5] = CHANGE
    reading = read_mask_for_image(
        MaskBuffer(data=bytes(mask), width=4, height=3), _image(4, 3)
    )
    assert reading.width == 4
    assert reading.height == 3
    assert reading.total_pixels == 12
    assert reading.changed_pixels == 2
    assert reading.partial_pixels == 0
    assert reading.changed_fraction == pytest.approx(2 / 12)
    assert reading.is_binary
    assert not reading.covers_everything


@pytest.mark.parametrize(
    ("mask_width", "mask_height"),
    [(63, 64), (65, 64), (64, 63), (64, 65)],
)
def test_a_mask_off_by_one_in_any_direction_is_refused_naming_both_sizes(
    mask_width: int, mask_height: int
) -> None:
    """The off-by-one, which is the mistake this refusal exists for.

    A mask one pixel out is not nearly right. Every row after the first is read
    from the wrong offset, so the edit lands somewhere the caller did not put
    it, in a way that looks like the model wandering rather than the request
    being wrong.
    """
    with pytest.raises(MaskError) as refusal:
        read_mask_for_image(_mask(mask_width, mask_height, CHANGE), _image(64, 64))
    message = str(refusal.value)
    assert f"{mask_width}x{mask_height}" in message
    assert "64x64" in message


def test_a_mask_whose_bytes_do_not_match_its_declared_shape_is_refused() -> None:
    with pytest.raises(MaskError) as refusal:
        read_mask_for_image(
            MaskBuffer(data=bytes(4 * 3 - 1), width=4, height=3), _image(4, 3)
        )
    assert "12 bytes" in str(refusal.value)
    assert "carries 11" in str(refusal.value)


@pytest.mark.parametrize(("width", "height"), [(0, 3), (3, 0), (-1, 3)])
def test_a_mask_declaring_no_pixels_is_refused(width: int, height: int) -> None:
    with pytest.raises(MaskError) as refusal:
        read_mask_for_image(
            MaskBuffer(data=b"", width=width, height=height), _image(3, 3)
        )
    assert f"{width}x{height}" in str(refusal.value)


def test_a_mask_of_zeroes_is_refused_here_and_defined_by_the_contract() -> None:
    """Refused here, defined there, and the two are not in conflict.

    `tests/contract/` holds a clause requiring an engine to accept a mask of
    zeroes and return the image unchanged. That clause is about an engine
    reached directly, by the contract suite and by the hardware harness. This
    refusal is about a request reaching the queue, where a run that returns its
    input has still held the one lane on the device.
    """
    with pytest.raises(MaskError) as refusal:
        read_mask_for_image(_mask(8, 8, KEEP), _image(8, 8))
    assert "64" in str(refusal.value)


def test_a_mask_covering_everything_is_accepted_and_says_so() -> None:
    reading = read_mask_for_image(_mask(8, 8, CHANGE), _image(8, 8))
    assert reading.covers_everything
    assert reading.changed_fraction == 1.0
    assert reading.changed_pixels == 64


def test_one_non_zero_pixel_is_enough_for_a_mask_to_be_accepted() -> None:
    """The boundary of the empty refusal, one pixel on the accepted side."""
    mask = bytearray(8 * 8)
    mask[63] = 1
    reading = read_mask_for_image(
        MaskBuffer(data=bytes(mask), width=8, height=8), _image(8, 8)
    )
    assert reading.changed_pixels == 1
    assert reading.partial_pixels == 1
    assert not reading.is_binary


def test_an_anti_aliased_edge_is_inside_the_edit_and_is_counted_apart() -> None:
    """The ramp is coverage, never doubt: every value above zero is edited.

    A painting surface that anti-aliases what it draws puts a ramp around every
    shape. The mask is then wider than the shape by the width of that ramp, and
    the count below is how a caller learns that without comparing results.
    """
    row = bytes([KEEP, 1, 64, 128, 200, CHANGE, CHANGE, KEEP])
    reading = read_mask_for_image(MaskBuffer(data=row, width=8, height=1), _image(8, 1))
    assert reading.changed_pixels == 6
    assert reading.partial_pixels == 4
    assert not reading.is_binary
    assert reading.changed_fraction == pytest.approx(6 / 8)


def test_an_inverted_mask_is_valid_and_only_its_fraction_gives_it_away() -> None:
    """No reading of the bytes tells intent, and this test states the limit.

    The complement of a small object is a legitimate mask: it is what "change
    the background" means. It is also what a caller sends when their tooling
    inverted the mask, and the two are byte-for-byte the same request. What is
    offered is the fraction, so a surface can ask a person before the device is
    spent.
    """
    intended = bytearray(bytes(16 * 16))
    for row in range(4, 8):
        for column in range(4, 8):
            intended[row * 16 + column] = CHANGE
    inverted = bytes(KEEP if value else CHANGE for value in intended)
    drawn = read_mask_for_image(
        MaskBuffer(data=bytes(intended), width=16, height=16), _image(16, 16)
    )
    complement = read_mask_for_image(
        MaskBuffer(data=inverted, width=16, height=16), _image(16, 16)
    )
    assert drawn.changed_pixels + complement.changed_pixels == 256
    assert drawn.changed_fraction == pytest.approx(16 / 256)
    assert complement.changed_fraction == pytest.approx(240 / 256)


def test_a_rectangle_covers_its_own_columns_and_never_the_next_one() -> None:
    """The half-open rule, at the only place it can be seen."""
    mask = rasterise((Rectangle(x=2, y=0, width=3, height=1),), 8, 1)
    assert _columns(mask, 0) == "..###..."


def test_two_abutting_rectangles_meet_without_overlapping_or_leaving_a_gap() -> None:
    left = rasterise((Rectangle(x=0, y=0, width=4, height=1),), 8, 1)
    right = rasterise((Rectangle(x=4, y=0, width=4, height=1),), 8, 1)
    both = rasterise(
        (
            Rectangle(x=0, y=0, width=4, height=1),
            Rectangle(x=4, y=0, width=4, height=1),
        ),
        8,
        1,
    )
    assert _columns(left, 0) == "####...."
    assert _columns(right, 0) == "....####"
    assert _columns(both, 0) == "########"


def test_a_rectangle_one_pixel_wide_covers_exactly_one_pixel() -> None:
    mask = rasterise((Rectangle(x=5, y=0, width=1, height=1),), 8, 1)
    assert _columns(mask, 0) == ".....#.."


def test_a_rectangle_hanging_off_the_canvas_is_clipped_rather_than_refused() -> None:
    mask = rasterise((Rectangle(x=-3, y=-3, width=5, height=5),), 4, 4)
    assert _columns(mask, 0) == "##.."
    assert _columns(mask, 1) == "##.."
    assert _columns(mask, 2) == "...."


@pytest.mark.parametrize(
    "shape",
    [
        Rectangle(x=20, y=0, width=4, height=4),
        Rectangle(x=-9, y=0, width=4, height=4),
        Ellipse(x=30, y=30, width=6, height=6),
        Polygon(points=((20, 20), (24, 20), (24, 24))),
    ],
)
def test_a_shape_wholly_off_the_canvas_is_refused_by_position(
    shape: Shape,
) -> None:
    with pytest.raises(MaskError) as refusal:
        rasterise((shape,), 8, 8)
    assert "shape 0" in str(refusal.value)
    assert type(shape).__name__ in str(refusal.value)


def test_the_refusal_names_which_shape_of_several_missed_the_canvas() -> None:
    with pytest.raises(MaskError) as refusal:
        rasterise(
            (
                Rectangle(x=0, y=0, width=2, height=2),
                Rectangle(x=40, y=40, width=2, height=2),
            ),
            8,
            8,
        )
    assert "shape 1" in str(refusal.value)


def test_rasterising_no_shape_at_all_is_refused() -> None:
    with pytest.raises(MaskError) as refusal:
        rasterise((), 8, 8)
    assert "no shape" in str(refusal.value)


@pytest.mark.parametrize(("width", "height"), [(0, 8), (8, 0), (8, -1)])
def test_a_canvas_that_holds_no_pixel_is_refused(width: int, height: int) -> None:
    with pytest.raises(MaskError) as refusal:
        rasterise((Rectangle(x=0, y=0, width=1, height=1),), width, height)
    assert f"{width}x{height}" in str(refusal.value)


def test_an_ellipse_is_the_one_inscribed_in_its_box() -> None:
    """A circle of diameter 6, checked as a picture rather than as a count."""
    mask = rasterise((Ellipse(x=1, y=1, width=6, height=6),), 8, 8)
    assert [_columns(mask, row) for row in range(8)] == [
        "........",
        "..####..",
        ".######.",
        ".######.",
        ".######.",
        ".######.",
        "..####..",
        "........",
    ]


def test_a_polygon_is_filled_by_the_even_odd_rule() -> None:
    triangle = Polygon(points=((0, 0), (8, 0), (0, 8)))
    mask = rasterise((triangle,), 8, 8)
    assert [_columns(mask, row) for row in range(8)] == [
        "#######.",
        "######..",
        "#####...",
        "####....",
        "###.....",
        "##......",
        "#.......",
        "........",
    ]


def test_a_polygon_crossing_itself_leaves_the_overlap_empty() -> None:
    """Even-odd, which is what makes a ring drawn as one outline a ring.

    Both squares are traced the same way round, and the seam between them is
    walked out and back so its crossings cancel. Under the winding rule this
    would be a filled square; under even-odd the inner square is a hole, and a
    caller who drew a frame around something gets a frame.
    """
    ring = Polygon(
        points=(
            (0, 0),
            (8, 0),
            (8, 8),
            (0, 8),
            (0, 0),
            (2, 2),
            (2, 6),
            (6, 6),
            (6, 2),
            (2, 2),
        )
    )
    mask = rasterise((ring,), 8, 8)
    assert [_columns(mask, row) for row in range(8)] == [
        "########",
        "########",
        "##....##",
        "##....##",
        "##....##",
        "##....##",
        "########",
        "########",
    ]


def test_a_feather_of_zero_is_a_hard_edge_and_is_the_default() -> None:
    with_default = rasterise((Rectangle(x=3, y=0, width=2, height=1),), 8, 1)
    with_zero = rasterise(
        (Rectangle(x=3, y=0, width=2, height=1),), 8, 1, feather_pixels=0
    )
    assert with_default.data == with_zero.data
    assert _columns(with_default, 0) == "...##..."


def test_a_feather_widens_the_mask_outward_by_its_own_number_of_pixels() -> None:
    mask = rasterise((Rectangle(x=3, y=0, width=2, height=1),), 12, 1, feather_pixels=3)
    assert _columns(mask, 0) == "+++##+++...."
    assert list(mask.data[:8]) == [63, 127, 191, 255, 255, 191, 127, 63]


def test_every_feathered_pixel_is_inside_the_edit() -> None:
    """The ramp is coverage. A feather makes the edit wider, not softer."""
    hard = rasterise((Rectangle(x=4, y=4, width=2, height=2),), 16, 16)
    feathered = rasterise(
        (Rectangle(x=4, y=4, width=2, height=2),), 16, 16, feather_pixels=2
    )
    hard_reading = read_mask_for_image(hard, _image(16, 16))
    feathered_reading = read_mask_for_image(feathered, _image(16, 16))
    assert hard_reading.changed_pixels == 4
    assert feathered_reading.changed_pixels == 36
    assert feathered_reading.partial_pixels == 32
    assert not feathered_reading.is_binary


def test_a_feather_is_square_because_the_distance_is_chebyshev() -> None:
    mask = rasterise((Rectangle(x=2, y=2, width=1, height=1),), 5, 5, feather_pixels=1)
    assert [_columns(mask, row) for row in range(5)] == [
        ".....",
        ".+++.",
        ".+#+.",
        ".+++.",
        ".....",
    ]


def test_a_feather_running_off_the_canvas_is_clipped() -> None:
    mask = rasterise((Rectangle(x=0, y=0, width=1, height=1),), 3, 3, feather_pixels=2)
    assert [_columns(mask, row) for row in range(3)] == [
        "#++",
        "+++",
        "+++",
    ]
    assert list(mask.data) == [255, 170, 85, 170, 170, 85, 85, 85, 85]


@pytest.mark.parametrize("feather", [-1, MAX_FEATHER_PIXELS + 1])
def test_a_feather_outside_what_a_ramp_can_carry_is_refused(feather: int) -> None:
    with pytest.raises(MaskError) as refusal:
        rasterise((Rectangle(x=0, y=0, width=2, height=2),), 8, 8, feather)
    assert str(feather) in str(refusal.value)


def test_the_widest_permitted_feather_still_ends_inside_the_edit() -> None:
    """The boundary of that refusal, on the accepted side.

    The outermost ring at 254 computes to 1, which is inside the edit. One more
    would compute to 0, which is the value meaning keep, and that is the whole
    reason for the limit.
    """
    mask = rasterise(
        (Rectangle(x=0, y=0, width=1, height=1),),
        MAX_FEATHER_PIXELS + 1,
        1,
        MAX_FEATHER_PIXELS,
    )
    assert mask.data[0] == CHANGE
    assert mask.data[1] == 254
    assert mask.data[MAX_FEATHER_PIXELS] == 1
    assert KEEP not in mask.data


def test_a_rasterised_mask_is_accepted_by_the_reader_for_a_matching_image() -> None:
    """The two halves meet: what geometry produces is what validation accepts."""
    mask = rasterise((Ellipse(x=2, y=2, width=4, height=4),), 10, 10)
    reading = read_mask_for_image(mask, _image(10, 10))
    assert reading.is_binary
    assert 0 < reading.changed_fraction < 1


def test_a_rasterised_mask_is_refused_against_an_image_of_another_size() -> None:
    mask = rasterise((Rectangle(x=0, y=0, width=2, height=2),), 10, 10)
    with pytest.raises(MaskError):
        read_mask_for_image(mask, _image(10, 11))
