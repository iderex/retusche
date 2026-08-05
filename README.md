# retusche

A self-hosted backend for generative photo editing: remove objects, fill
gaps, extend images. It runs entirely on your own hardware and plugs into
photo libraries such as Immich or Nextcloud through a small API, so the
pictures never leave the machine they live on.

The building blocks exist as open source: inpainting and outpainting models
and the inference stacks that run them. What is missing, and what this
project builds, is the layer that makes them usable from a photo app: a
masking workflow, a job queue that respects your GPU, model management, and
a clean integration API.

This repository starts with planning. The plan lives on the issue tracker;
every architectural decision is written down there with its reasons before
the code that depends on it exists.

See [NOTICE.md](NOTICE.md) for the intended-use notice.
