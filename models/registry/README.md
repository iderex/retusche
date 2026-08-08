# The model registry

One TOML file per model. The file name is the operator's convenience; the
identifier inside it is what a request names and what the loader keys on.

`retusche.models.registry` is the authority for which fields exist and what each
one is refused for. This file does not list them, because a list here drifts
against the loader that decides them:

    git grep -n '^_ENTRY_FIELDS\|^_LICENCE_FIELDS' -A 12 -- src/retusche/models/registry.py

What an entry looks like:

```toml
identifier = "example-erase-small"
source = "https://example.invalid/example-erase-small/resolve/main/model.onnx"
digest = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
size_bytes = 1
device_memory_bytes = 1
engine = "example-erase"
operations = ["erase"]

[licence]
identifier = "Apache-2.0"
url = "https://www.apache.org/licenses/LICENSE-2.0"
```

That example is in this document and not in this directory, and it is not a
model: the source does not resolve, the digest is not the digest of anything and
the sizes are placeholders. An example file here would load, and a registry
holding one entry that is not a model is worse than one holding none.

## This directory holds no model yet

Deliberately, and it is not an oversight of the loader.

Which weights this project offers is an open decision, in #94's second entry:
whether models whose weight licence forbids commercial use are offered at all,
offered with the restriction shown and an acknowledgement recorded, or not
distinguished. #43 is where the licences of the models offered at first release
are audited, and it waits on the same answer. Writing an entry here now would
answer both by side effect, which is the way a decision gets made without anyone
making it.

So what is built is the shape and the refusals. `tests/test_model_registry.py`
exercises those against files it writes itself, and it also loads this
directory, which today is an assertion over an empty set and says so in its own
words.
