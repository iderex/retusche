# Copyright (C) 2026 Nils Lehnen
# SPDX-License-Identifier: AGPL-3.0-only

"""Masks: what one is, what is refused, and how a shape becomes one.

`retusche.masking.mask` holds the pixel representation and the refusals.
`retusche.masking.geometry` holds the shapes and the one rasterisation rule.
The endpoints that take a mask are #47, #48 and #49, and the segmentation
assistance that produces a candidate mask from a click is #50; neither is here.
"""

from __future__ import annotations

from retusche.masking.geometry import (
    MAX_FEATHER_PIXELS,
    Ellipse,
    Polygon,
    Rectangle,
    Shape,
    rasterise,
)
from retusche.masking.mask import (
    CHANGE,
    KEEP,
    MaskError,
    MaskReading,
    read_mask_for_image,
)

__all__ = [
    "CHANGE",
    "KEEP",
    "MAX_FEATHER_PIXELS",
    "Ellipse",
    "MaskError",
    "MaskReading",
    "Polygon",
    "Rectangle",
    "Shape",
    "rasterise",
    "read_mask_for_image",
]
