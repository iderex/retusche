# Notice

This software is developed for lawful use. Operators and users are
responsible for making sure that their deployment and use comply with the
laws that apply to them, including copyright and data protection law. The
project does not endorse or support unlawful use of any kind, and nothing
in it is designed to enable such use. The license contains the full
warranty and liability disclaimer.

## Uses this project does not support

This software removes objects from photographs and invents what stands in
their place. Three uses of that capability are named here rather than left to
be inferred, because a notice that names nothing warns nobody and answers no
feature request.

Presenting an edited image as an unaltered record. An edited photograph is not
evidence of what was in front of the camera, and this project does not support
its use as one in a claim, a report, a listing, a submission or a news item.

Removing rights-management or provenance information from an image. Painting
over a watermark, a credit or a signature in order to detach a picture from
whoever made it is not a supported use, and neither is stripping provenance
metadata by passing a file through this service.

Altering an image of a person in a way they have not agreed to. That covers
placing someone in a situation they were not in, removing or inserting people,
and changing a face or a body. It is the misuse this capability is most
directly suited to, and it is the one an operator should think about before the
others.

These are statements about what this project supports and builds. None of them
is a legal assessment and none of them replaces one.

## What this project does not build

A feature request in any of these directions has a written answer here rather
than an argument later.

No face recognition, face clustering or face swapping. Identifying who is in a
picture is a different capability from editing pixels, and this project does
not acquire it. What it does with a picture instead, and what it keeps, is in
[docs/legal/data-protection.md](docs/legal/data-protection.md).

No tooling aimed at watermarks or provenance data. A general editing capability
can be pointed at a watermark by whoever holds the software; a feature that
does it as a feature is not built here.

No effort to make the output undetectable. The work goes in the opposite
direction, towards marking generated images.

## Transparency marking

Images this service generates are to carry a machine-readable mark saying they
were artificially generated or manipulated. What the mark records, what it
survives and what it cannot do belongs in the transparency document, which does
not exist yet: issue #69 owes the analysis and issue #70 the mark and the
statement of its limits. Until they land, this section describes what is being
built rather than what a running service does, and it does not restate what
that document will say.

## Data protection

What this service handles, where it writes it, what leaves the host and what an
operator still has to do for themselves is in
[docs/legal/data-protection.md](docs/legal/data-protection.md).
