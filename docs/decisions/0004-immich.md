# 0004. Integrating with Immich: a new asset, not a modified one

An edit produces a new asset in the library, carrying the original's
associations and stacked with it. The original file is never modified and never
replaced. The library's own edit surface is not used at all.

This record is written from the published specification rather than from a
running server, so every claim below carries the query that produced it and
nothing is asserted about behaviour the specification does not state.

## Reading the specification

One fetch, and every query below runs against it:

    gh api repos/immich-app/immich/contents/open-api/immich-openapi-specs.json \
      -H "Accept: application/vnd.github.raw" --jq '.info.version'
    3.1.0

That file moves, so what was read is pinned by its blob identity rather than by
the sentence above:

    gh api repos/immich-app/immich/contents/open-api/immich-openapi-specs.json --jq '{sha: .sha, size: .size}'
    {"sha":"bc3bf82094a2791b8bd6cb35278ac12905c0ded9","size":781123}

A reader re-running these gets whatever is current. Where the current answer
differs from what is quoted here, the quote is the older reading and not a
correction to make silently.

Every later query is written against these two, so the queries stay readable and
each one is still a whole command:

    SPEC='repos/immich-app/immich/contents/open-api/immich-openapi-specs.json'
    RAW='Accept: application/vnd.github.raw'

## The finding that decides the shape

The library's non-destructive edit chain cannot carry a generated image. Its
whole action vocabulary is three geometric operations:

    gh api "$SPEC" -H "$RAW" --jq '.components.schemas.AssetEditAction'
    {"description":"Type of edit action to perform","enum":["crop","rotate","mirror"],"type":"string"}

There is no action that means "these pixels". So an edited photograph cannot be
expressed as an edit on the source asset, whatever else is decided, and it has
to arrive as an asset of its own. Everything else in this record follows from
that one enum.

The same surface is also the least settled thing in the area, which is a second
reason to stay off it but not the reason:

    gh api "$SPEC" -H "$RAW" --jq '[["put","/assets/{id}/edits"]][] as [$m,$p] | .paths[$p][$m] | "\($m|ascii_upcase) \($p) \(.operationId) \(.["x-immich-state"]) \(.["x-immich-permission"] // "none")"'
    PUT /assets/{id}/edits editAsset Beta asset.edit.create

## The path

Four calls, in this order. Each one is documented Stable, and the permission
column is what an operator's API key has to carry:

    gh api "$SPEC" -H "$RAW" --jq '[["get","/assets/{id}"],["get","/assets/{id}/original"],["post","/assets"],["put","/assets/copy"],["post","/stacks"],["get","/server/version"]][] as [$m,$p] | .paths[$p][$m] | "\($m|ascii_upcase) \($p) \(.operationId) \(.["x-immich-state"]) \(.["x-immich-permission"] // "none")"'
    GET /assets/{id} getAssetInfo Stable asset.read
    GET /assets/{id}/original downloadAsset Stable asset.download
    POST /assets uploadAsset Stable asset.upload
    PUT /assets/copy copyAsset Stable asset.copy
    POST /stacks createStack Stable stack.create
    GET /server/version getServerVersion Stable none

Read. `GET /assets/{id}` for the metadata and `GET /assets/{id}/original` for
the bytes, which the specification describes as downloading the original file
and returns as `application/octet-stream`. Nothing on the read side writes.

Write. `POST /assets` uploads the result as a new asset. It takes a multipart
body and three fields are required:

    gh api "$SPEC" -H "$RAW" --jq '{content: (.paths["/assets"].post.requestBody.content | keys), required: .components.schemas.AssetMediaCreateDto.required}'
    {"content":["multipart/form-data"],"required":["assetData","fileCreatedAt","fileModifiedAt"]}

The two timestamps are the source's, not the moment of the edit. An edited
photograph that sorts to the top of the library rather than sitting beside its
original would be a defect the operator sees before anything else.

Inherit. `PUT /assets/copy` moves the source's associations onto the new asset.
It needs the two identifiers and everything else is a flag defaulting to on:

    gh api "$SPEC" -H "$RAW" --jq '{required: .components.schemas.AssetCopyDto.required, flags: (.components.schemas.AssetCopyDto.properties | to_entries | map(select(.value.type == "boolean")) | map("\(.key)=\(.value.default) \(.value.description)"))}'
    {"flags":["albums=true Copy album associations","favorite=true Copy favorite status","sharedLinks=true Copy shared links","sidecar=true Copy sidecar file","stack=true Copy stack association"],"required":["sourceId","targetId"]}

The `sharedLinks` flag is the one worth a decision rather than a default. Copying
a shared link makes the edited image reachable from a URL somebody was given for
the original, which is a disclosure the operator did not perform. The integration
sends `sharedLinks: false` and says so where the setting is documented; the other
four keep their defaults.

Group. `POST /stacks` puts the two into one stack so the library shows one
photograph. Order matters and the specification states it:

    gh api "$SPEC" -H "$RAW" --jq '.components.schemas.StackCreateDto'
    {"properties":{"assetIds":{"description":"Asset IDs (first becomes primary, min 2)","items":{"format":"uuid","pattern":"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})$","type":"string"},"minItems":2,"type":"array"}},"required":["assetIds"],"type":"object"}

The edited asset goes first, so it is the one the library shows and the original
is the version underneath it.

The `stack` flag on the copy call is a different thing and does not replace this
step. Its description is "Copy stack association", which carries the source's
existing stack membership onto the new asset; it does not create a stack between
the source and the target. Both are needed and they do not overlap.

## The version range

The integration targets a server whose major version matches the specification
read above, which is major 3. The check has a route that runs before anything
else, because it is the one operation in this record that needs no permission at
all:

    gh api "$SPEC" -H "$RAW" --jq '.components.schemas.ServerVersionResponseDto.required'
    ["major","minor","patch","prerelease"]

Outside the range, the integration refuses rather than proceeds. A major below
the tested one is refused because nothing read here promises an operation
survives a major change. A major above it is refused for the same reason, and
refusing is the choice that fails visibly instead of writing something wrong
into somebody's library. A higher minor within the tested major is accepted and
recorded, on the reading below.

Where that check lives and what it prints is #60. This record fixes the rule and
builds nothing.

## The alternative that was rejected

Replacing the original file in place is not available. No path in the
specification offers it:

    gh api "$SPEC" -H "$RAW" --jq '[.paths | keys[] | select(test("replace"; "i"))]'
    []

It would not be chosen if it were. An operator's photograph is the thing this
project is trusted with, and a generative edit is exactly the operation most
likely to produce a result somebody wants to undo an hour later. A route that
overwrites the original makes that undo impossible and makes every failure mode
of this service, a crashed worker, a half-written file, a wrong mask, land on
data the operator cannot get back. The new-asset path costs disk and costs
nothing else.

## What is assumed and not verified

Marked here rather than buried, and each one stays marked until the round-trip
harness in #59 runs against a real instance.

That a `Stable` operation is not removed or changed incompatibly within a major
version is read from the shape of the `x-immich-state` and `x-immich-history`
annotations. No written stability policy was located to confirm it, and the
version rule above rests on it.

That `PUT /assets/copy` leaves the source asset untouched is read from its
description, "Copy asset information like albums, tags, etc. from one asset to
another", and from its returning 204 with no body. Not verified against a
running server.

That uploading with the source's `fileCreatedAt` places the new asset beside the
original in the library's timeline is an inference from the field name and not a
statement the specification makes.

That a stack created with the edited asset first shows that asset in list views
is read from "first becomes primary" and not observed.

Nothing here is verified against a running Immich server. This record is a
reading of a published specification, and the harness in #59 is what turns any
of it into a measurement.

## What this does not decide

Which operations the integration exposes, and whether the trigger surface inside
the library is built at all, is #58. What the client is written in and how it is
structured is #56 and #57. The plugin question, and whether building against
that project's plugin package reaches its licence into this repository, is named
in #94 and is not answered here.
