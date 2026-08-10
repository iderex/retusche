# Where the models are kept

Model weights are the largest thing this service puts on your disk, and on the
deployment this project is written for that disk is the one holding your
photographs. This page is the layout under `model_store_path`, written so you
can find a model, back one up, or delete one with a file manager and no help
from the service.

## The layout

    <model_store_path>/
      lama-large/
        3f786850e387550fdab836ed7e6dc881de23001b3b7a86a92b0f68d4b0e1e0c1
      sdxl-inpaint/
        b3a8e0e1f9ab1bfe3a36f231f676f78bb30a519d2b21e6c530c0eee8ebb4a5d0
        c1f0a6b47af0a1e30b0da3fa02a3d9b96b6dd2b6a7d0e5c1e1b0f7a2c8d4e3f2.incoming

One directory per model, named exactly as the model's identifier in the
registry. One file inside it per artefact, named as that artefact's `sha256`
digest with the `sha256:` prefix dropped.

The identifiers above are illustrative. `models/registry/` carries no model
entry yet, so no name on this page is one this project ships.

## Why the file is named after its digest

You can check an artefact without the service. On Linux:

    sha256sum <model_store_path>/lama-large/*

and on Windows:

    Get-FileHash -Algorithm SHA256 <model_store_path>\lama-large\*

The digest it prints is the file's name, and it is also the `digest` field of
that model's entry under `models/registry/`. Three things agreeing is a check
you can run yourself; a file called `model.safetensors` would tell you nothing.

It also means an entry re-pinned to new weights arrives as a second file beside
the first rather than overwriting it, so an artefact something still has open is
never the artefact a fetch writes over.

## A name ending in `.incoming`

An unfinished fetch writes to the artefact's name with `.incoming` after it, and
the finished name is reached by renaming. So a file under the plain digest name
is a whole file, and a file ending in `.incoming` is a fetch that did not
finish, left behind by a power cut, a full disk or a stopped container.

Deleting one is safe and frees its space. It is not resumed by anything today;
what fetches an artefact and verifies it before the rename is issue #39, and
this tree does not carry it yet.

## Backing up and deleting by hand

A model is one directory. Copy it to back it up, delete it to remove it, and the
space comes back at once. Nothing outside that directory refers to it: the
registry entry that names the model is a small file under
`model_registry_path`, and it stays valid whether the artefact is present or
not, which is what makes deleting one recoverable by fetching it again.

There is one thing to know before you delete. Nothing in this service currently
refuses a removal of a model something is using, and deleting the weights out
from under a running job will fail that job. The service cannot see it: whether
weights are loaded is the worker process's own state, and the interface between
the two carries no question about it. Issue #41 records that, and it is the
reason this page says stop the service first if you are not sure.

## The disk budget

`model_disk_budget_bytes` is the most this directory may hold. A fetch that
would put it over is refused before it starts, and the refusal names the size of
the artefact, what the store already holds, and the budget, so you can see which
of the two repairs applies: raise the number, or remove a model you no longer
want.

Free space on the volume is a separate check that runs after the budget one, and
its refusal says so in as many words. Raising the budget does not create space,
and a generous budget on a full disk is an ordinary situation rather than a
contradiction.

Both numbers are counted from the files that are actually there, `.incoming`
ones included, rather than from the sizes the registry declares. A store whose
contents are symbolic links into another tree reads as nearly empty, because a
link is counted as the link and not as what it points at.

## What is not here

No route through the API or a command line removes a model today. The service
has neither surface yet: the endpoints are issues #47 to #49 and the first-run
command is #91. Until one of them exists, the routes are this page and the
directory itself.

The removal the service does hold is `ModelStore.remove` in
`retusche.models.storage`, which deletes one model's directory and answers with
the number of bytes that freed. It is what a surface will call rather than a
surface itself, and it is named here so that the number an operator eventually
reads and the number this page describes are the same one.
