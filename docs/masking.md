# What a mask is

`retusche.masking` declares the mask this project accepts and refuses everything
else. This note carries the part an integration author needs before writing
against it: what a value means, where a shape's edge lands, and which requests
come back refused. The module docstrings are the authority for the rules; what
is here is the reasoning and the caller's side of it.

## Two representations, and one meaning

A mask is one byte per pixel, `height * width` of them, row major. That is
`MaskBuffer` in the engine contract and it is what an engine is handed.

Zero means keep the pixel. Any value from 1 to 255 means the pixel is inside the
edit. The contract fixes that much; what this package adds is what the values
between mean, and the answer is coverage. 255 is a pixel wholly inside the edit
and 128 is one the boundary passes through, and both are edited.

That sentence is the one to read twice, because the intuition it displaces is
the common one. A ramp does not make an edge tentative and it does not weight
the result. It says how much of a pixel the region covers, and every covered
pixel is changed. So a mask drawn by an anti-aliasing tool is wider than the
shape it was drawn from, by exactly the width of its ramp.

The other representation is geometry: rectangles, ellipses and polygons, sent
instead of pixels and rasterised here. It exists so that a caller with a
rectangle around a lamppost does not have to write a rasteriser, and so that
several integrations do not each write a different one. The disagreements
between rasterisers are all at the edge, which is where a mask is read most
closely.

## Where an edge lands

A pixel is covered when its centre is inside the shape. The centre of the pixel
in column `c` and row `r` sits at `(c + 0.5, r + 0.5)`, so a shape's coordinates
name the lines between pixels rather than the pixels themselves.

Every shape is therefore half-open on its far side. A rectangle at `x = 2` with
`width = 3` covers columns 2, 3 and 4, and never column 5. Two rectangles laid
side by side cover each column exactly once, with no seam and no overlap. The
alternative rule, where a pixel is covered if the shape touches it at all, grows
every shape by a pixel on each side and makes those two rectangles fight over the
column between them.

A polygon is filled by the even-odd rule, so a ring drawn as a single outline is
a ring rather than a filled square.

A shape may hang off the canvas and is clipped to it. A shape that is wholly off
the canvas is refused, naming which of the shapes sent it was: it is a
coordinate mistake, and the mask it would produce is an empty one, which reads
as a different mistake by the time anything downstream sees it.

## Feathering

`feather_pixels` is a whole number of pixels and it is measured outward from the
shape. A feather of 2 makes the mask two pixels wider on every side. The default
is 0, which is a hard edge.

Distance is Chebyshev, so the ramp is square rather than round: a pixel is at
distance `d` when it is `d` steps away with a diagonal counted as one step. A
round ramp needs a distance transform and is still an approximation of a blur
nobody specified. A square one is reproducible from one sentence, and its
corners are the only place the two differ.

The value on ring `d` is `255 * (feather + 1 - d) // (feather + 1)`. A feather of
1 puts 127 around the shape; a feather of 3 puts 191, 127 and 63. Every one of
those pixels is inside the edit, by the rule above, so a feather widens what is
edited rather than softening it.

The widest feather accepted is 254. At 255 the outermost ring computes to zero,
which is the value meaning keep, and a mask one ring narrower than the feather
asked for is worse than a refusal because nothing says so.

## What comes back refused

A mask whose declared size and carried bytes disagree. Every read computes its
index from the width, so a buffer of another length is not a smaller mask, it is
this mask with its rows taken from the wrong place.

A mask whose dimensions are not the image's, exactly, with both sizes named.
Nothing is resized here. A caller one pixel out has a mask that names different
pixels than the ones they drew, and a silent resize turns that into an edit whose
boundary is a fraction of a pixel from where they put it, with nothing in the
result saying it moved.

A mask of zeroes. The edit it describes is the photograph it was given, and such
a request holds the device for the length of a run to return its own input.

The engine contract separately requires an engine to accept a mask of zeroes and
return the image unchanged, and that is not a contradiction. An engine is also
reached from the contract suite and from the hardware harness, without this
layer in front of it, so its behaviour is defined for a request that does not
arrive from here.

A mask covering everything is not refused. It is a real request: it is what
regenerating the whole frame means. `MaskReading.covers_everything` says so, for
a surface that wants to ask again before spending a device on it.

## What no reading of a mask can tell you

Whether it is inverted. The complement of a small object is a legitimate mask,
because "change the background" is a real request, and it is byte for byte the
same thing a caller sends when their tooling inverted the mask by accident.
Nothing here distinguishes them and nothing could.

What is offered instead is `MaskReading.changed_fraction`, the share of the
photograph the edit reaches. An inverted mask of a small object reads close to
1.0. That is a disclosure for a surface to put in front of a person, not a
check, and calling it one would be worse than not having it.

`MaskReading.partial_pixels` is the same kind of thing for the anti-aliased
edge: it counts the pixels on a ramp, which are the pixels a caller did not draw
and is nonetheless editing.

## What is not here

Decoding. A mask arrives as bytes whose shape is already stated. Turning an
uploaded PNG into those bytes is #51, where the input comes from a stranger and
the decoder is the attack surface.

The endpoints that carry a mask are #47, #48 and #49. Turning a click into a
candidate mask with a segmentation model is #50. Nothing in this package reaches
a device, a network or a model.
