# 0002. The engine: an own pipeline behind an interface, not a wrapped application

retusche loads and runs models itself, in a worker process, through the
maintained model libraries. Every engine sits behind one narrow interface, so an
adapter to an external application can be added later without touching the API
or the queue.

The interface exists in either direction. Whether an engine runs models in this
project's own worker or adapts an external application, it is reached the same
way, so nothing in this record decides whether the interface is built. Issue #14
is where it is defined, and `docs/engine-interface.md` carries the reasoning
behind its shape.

## The five reasons, in the order they carry weight

The closest existing fit is unmaintained. The tool whose scope matches this
project most nearly, an object-removal and inpainting server, is archived and
read-only:

    gh api repos/Sanster/IOPaint --jq '{archived,pushed_at,license:.license.spdx_id}'
    {"archived":true,"license":"Apache-2.0","pushed_at":"2025-04-29T02:13:17Z"}

Wrapping it would put an unmaintained project at the load-bearing layer of a
project whose whole point is that an operator can keep running it.

The licence of a wrapped application would decide this repository's licence by
side effect. The most widely deployed graph-based stack is copyleft:

    gh api repos/comfyanonymous/ComfyUI --jq .license.spdx_id
    GPL-3.0

Whether that is acceptable is the maintainer's decision, and an engineering
choice should not make it silently. The libraries the own pipeline needs are
permissive:

    gh api repos/huggingface/diffusers --jq .license.spdx_id
    Apache-2.0

What a wrapper would buy is mostly plumbing this project has to own anyway. The
device-considerate queue, the memory budget, cancellation and model residency
are the layer retusche exists to build. An application that has its own queue
does not hand those over, it competes with them, and the operator ends up
running two schedulers over one device.

Cancellation and a memory budget need control inside the denoising loop, not
around it. The library path exposes exactly that, as a flag the loop reads
between steps:

    curl -s https://raw.githubusercontent.com/huggingface/diffusers/v0.39.0/src/diffusers/pipelines/stable_diffusion/pipeline_stable_diffusion_inpaint.py | grep -nE 'if self\.interrupt'
    1264:                if self.interrupt:

An HTTP call into another application gives a request that can be abandoned, not
work that stops.

The second-order stacks are full applications with their own storage, their own
web interface and their own update cadence. A permissively licensed one exists:

    gh api repos/invoke-ai/InvokeAI --jq .license.spdx_id
    Apache-2.0

and it is still a heavier thing to install beside a photo library than a worker
process.

## What this gives up

Every model family a wrapped application would have supported on day one has to
be brought up here one at a time. The graph-based stack's ecosystem of community
extensions is not available. And the burden of tracking upstream changes in the
model libraries falls on this project rather than on a wrapper.

## What was not evaluated

No performance comparison was made between an own pipeline and any wrapped
application. Throughput, latency, memory behaviour and output quality of the two
routes are not evaluated on this route, and no sentence above rests on such a
measurement. The five reasons are about maintenance, licensing, layering and
where control has to sit, and they should be read as such.

The licence values above are what the hosting API reported for each repository
at the time the commands were run. They are the project licences, not the
licences of any model weights, which are a separate question held by #43 and
#71.

## What would reverse it

An adapter engine behind the same interface, if a specific model family turns
out to be reachable only through an external application, or if the maintenance
cost of the own pipeline exceeds what this project can carry. Neither reverses
the interface, which is why the interface is the part built first.
