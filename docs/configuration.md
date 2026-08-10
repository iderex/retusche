# Configuration

This page is generated from `retusche.config.settings`, and the suite refuses a
committed copy that differs from what the declaration produces. Edit the
declaration, not this file.

## Where a value comes from

Three sources, each overriding the one before it:

1. the configuration file, which is TOML and is a flat table of setting names
2. the environment, where a setting is read from `RETUSCHE_` followed by its
   name in upper case
3. what the command line supplies

The order runs from the least specific intention to the most. A file is written
once for a deployment, a variable is set for a process, and a flag is typed for
a single run, so the later source is the one that was meant more precisely.

## What is refused

Every problem at once, rather than the first one. An operator with four mistakes
in a file corrects them once instead of restarting four times, which matters
because each restart is a deployment.

A name nothing declares, in any source. A misspelled setting would otherwise do
nothing while reading as though it had done something, and the setting it was
meant to be keeps a value nobody chose.

An environment variable starting with `RETUSCHE_` that names no setting. The
limit of that check is the prefix: a variable misspelled outside it, such as
`RETUSHE_JOB_STORE_PATH`, is invisible here and always will be, because a check
that read every variable on the host would refuse the host's own.

A value that is not what its kind says. A whole number written as a word, a
boolean written as `yes`, a path written as a number.

A setting with no default and no value. There is no state in which such a
setting takes something nobody wrote.

## Secrets

A setting declared as a secret never appears in a rendering of the effective
configuration. The redaction is decided by the declaration rather than by
whoever is printing, so a setting that becomes a secret later is redacted
everywhere at once instead of everywhere somebody remembered.

The value is also handed to the service in a type that renders as `<redacted>`
whether it is printed, logged, put in an exception or held inside something that
prints itself. That covers the rendering nobody has written yet, which is where
a credential normally leaks. A refusal naming a secret prints `<redacted>` in
place of what was written, so a credential set in the wrong shape is not quoted
back at the operator in the error that refuses it.

What this does not do is protect the value once something has deliberately asked
for it in order to send it, and it is not a defence against reading this
process's memory.

## The settings

### `job_store_path`

Where the durable job store is kept. It is opened at startup and created if it is not there, and it is the record that survives a restart, so it belongs on storage the operator has chosen rather than wherever the process was launched from.

- Kind: a filesystem path
- Unit: a path to a file, absolute or relative to the working directory
- Default: none, and the service does not start without it
- Environment: `RETUSCHE_JOB_STORE_PATH`

### `model_registry_path`

The directory of model entries, one file per model, that the registry is read from. Every model the service will offer is declared there, licence included, and a directory that is not the intended one offers a different set without saying so.

- Kind: a filesystem path
- Unit: a path to a directory, absolute or relative to the working directory
- Default: none, and the service does not start without it
- Environment: `RETUSCHE_MODEL_REGISTRY_PATH`

### `model_store_path`

Where model artefacts are kept. This is the tens of gigabytes, not the small declarations: `model_registry_path` names the directory of entry files and this names the weights those entries point at, and one path answering for both would measure the disk budget over the wrong tree. It has no default on purpose. A default would put a model family wherever the process happened to be started, which on the intended deployment is the volume holding the operator's photographs, and it would do it silently. `docs/model-storage.md` is the layout underneath this path, written so a model can be found, backed up or deleted by hand.

- Kind: a filesystem path
- Unit: a path to a directory, absolute or relative to the working directory
- Default: none, and the service does not start without it
- Environment: `RETUSCHE_MODEL_STORE_PATH`

### `model_disk_budget_bytes`

The most disk the model store may hold. A fetch that would put the store over it is refused before it starts, with both numbers named, because a download refused after four gigabytes have landed has already spent what the ceiling was protecting. The default is thirty-two gibibytes, and it is a choice rather than a measurement: no model entry is in this tree yet, so no artefact size has been read from one. It is set on the side that refuses loudly, since the volume this competes for is usually the one holding the photographs. Free space is checked separately and afterwards: raising this number does not create any.

- Kind: a whole number
- Unit: bytes of disk under the model store
- Default: `34359738368`
- Environment: `RETUSCHE_MODEL_DISK_BUDGET_BYTES`

### `device_memory_budget_bytes`

The most device memory this project will hold at once, weights that stay resident included. It is a ceiling the operator sets and not an amount read off the card, because the card is usually shared with a photo library, a transcoder or a desktop session, and taking what looks free breaks the thing this service was meant to sit politely beside. A job whose estimate does not fit in what is left is refused before it reaches the device, with both numbers named. The default is four gibibytes and it is a choice rather than a measurement: nothing here has yet measured what an engine needs, so it is set on the side that refuses loudly rather than the side that quietly takes somebody else's memory.

- Kind: a whole number
- Unit: bytes of device memory
- Default: `4294967296`
- Environment: `RETUSCHE_DEVICE_MEMORY_BUDGET_BYTES`

### `log_level`

How much the service writes about its own work. It decides which lines are written and never what a line may carry: the fields a line is allowed are checked when the line is built, before any level is compared, so no value here starts logging prompts, paths or picture content. `docs/logging.md` is the field set and is generated from the same declaration the check reads. The default is `info`, which is the service saying what it did without saying it four times; `debug` is for working out what happened and is not meant to be left on, because it multiplies the lines rather than widening them. A value that is not one of the four is refused where the level is read, not by the loader.

- Kind: text
- Unit: one of `debug`, `info`, `warning`, `error`
- Default: `info`
- Environment: `RETUSCHE_LOG_LEVEL`
