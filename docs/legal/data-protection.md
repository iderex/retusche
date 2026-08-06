# Data protection

## What this document is

An operator running this service is the one who has to describe their own
deployment: what it processes, where it writes it, how long it keeps it, who
can read it and what leaves the host. This document is the material for that
description.

It is not a privacy policy. This project processes nothing of its own; it is
software an operator runs. It is also not a compliance assessment, and the last
section says which duties it cannot discharge for anyone.

## How to read the claims below

Two kinds of sentence appear here and they are not interchangeable.

A property is enforced by the code or controlled by a setting, and it carries
the command that shows it. An intention is what the plan says and nothing yet
refuses; it names the issue that owes the property. When that issue lands, the
sentence changes into a property with its command beside it.

Today almost everything below is an intention, because the service is not yet
runnable. Stating that once here is more honest than hedging every paragraph.

## What the tree holds today

Read from the default branch rather than from a working copy. Every import in
the tracked source comes from the standard library:

    $ git grep -nE '^[[:space:]]*(import|from) ' origin/main -- 'src/**/*.py'
    origin/main:src/retusche_contracts/__init__.py:10:from retusche_contracts.engine import (
    origin/main:src/retusche_contracts/engine.py:44:from __future__ import annotations
    origin/main:src/retusche_contracts/engine.py:46:import enum
    origin/main:src/retusche_contracts/engine.py:47:from collections.abc import Mapping
    origin/main:src/retusche_contracts/engine.py:48:from dataclasses import dataclass
    origin/main:src/retusche_contracts/engine.py:49:from typing import Protocol, runtime_checkable

The project declares no runtime dependencies:

    $ git show origin/main:pyproject.toml | grep -n '^dependencies'
    17:dependencies = []

And nothing in it reaches a file, a process or an interpreter by the routes
that do not need an import:

    $ git grep -nE '\bopen\(|\bexec\(|\beval\(|__import__|subprocess|threading' origin/main -- 'src/**/*.py' ; echo "exit=$?"
    exit=1

So no photograph reaches this software at all yet: there is no endpoint to send
one to, no decoder to read one with and no writer to put one anywhere. That is
a fact about an unfinished project rather than a property of a finished one,
and the sections below describe the service the plan builds.

## What the service will handle

### The photograph submitted for editing

It is read into memory for the duration of the job and passed to the engine as
raw bytes. Where the result store puts it, how long it stays there and what
removes it is the retention setting in #36, which asks for a stated period and
a removal that actually happens. Who can read it back is #53, which
authenticates a caller and authorises them per job; until that lands, anyone
who can reach the API can read any result.

### The mask

The same lifetime as the request it belongs to. What a mask is, and which ones
are refused, is #46.

### The prompt text

Supplied by the caller for the operations that use one, kept with the job
record so a result can be reconstructed. It is caller-supplied text and can
contain anything the caller typed, including a name.

### The result image

Stored on the same terms as the submitted photograph, under #36. It carries a
mark saying it was artificially generated or manipulated, which is #70, and
whether that mark can be switched off is an open decision in #94.

### The job record

Model identifier, engine, parameters, seed and library versions, kept so a
reported result can be reproduced. #24 states what it has to carry and #26 the
state machine that owns it. It describes the request rather than the picture.

### The logs

#64 asks for logs that say what happened without saying what was in the
picture. That is the property that keeps a log from becoming a second copy of
the personal data, and until #64 lands there is nothing to stop a log line
carrying a prompt or a file name.

### The audit trail

#67 keeps a record of what was edited, which is deliberately a record about
images rather than about the people in them, and #70 asks it to record whether
the transparency mark was applied.

### The credential for the photo library

An operator who connects this service to their library gives it a token for
that library. #63 owns keeping it out of logs and out of a bug report. It is
not a photograph and it is not personal data about a subject, but it is the
key to a library full of both.

## Outbound connections

Three, in the plan. They are listed here with what each one carries, because
a list that said only "none of them carries a photograph" would be false about
the second one.

### To the model host, to fetch weights

Made when a model is downloaded, which is #39, and possibly again where a model
requires terms to be accepted first, which is #40. It carries a request for a
file and it carries no image data. It is switched off by having the models
already present: #42 asks that the service work with no network at all once
they are, so an operator who wants the machine to make no outbound connection
at all installs the weights and stops there.

### To the photo library the operator names

Made when the library integration is configured, which is #56 for reading an
asset and #57 for writing the result back. This connection carries photographs,
in both directions, because reading an asset and returning an edited version is
what the integration is for. It goes to the address in the
operator's configuration, which is the operator's own library. It is switched
off by not configuring the integration, and an unconfigured service makes no
connection to any library.

### To nowhere else

No telemetry, no update check, no crash reporting, no model usage reporting.
Nothing in the plan asks for any of them and no issue on the tracker proposes
one. That is a statement about the plan and not a property of the code: no
check in this repository refuses an outbound connection, so nothing would stop
a fourth one being added except a reader of the diff.

## Biometric identification and face data

The service performs no biometric identification and stores no face data.

It does not compute a face template, it does not match one against another, it
does not cluster pictures by who is in them and it does not estimate age,
emotion or any other attribute of a person. Nothing in the plan asks for it:

    $ gh search issues --repo iderex/retusche --json number,title "biometric"
    68	Write the data protection statement: the photographs stay on the host

The one search hit is the issue that asked for this document.

The nearest thing the plan does contain is mask assistance, #50, where a click
or a box becomes a candidate region using a segmentation model. Segmentation
answers where an object is, not who it is, and it produces a mask rather than
an identity. If that ever changes, or if any component acquires a capability of
this kind, this section names which component and under which setting, and the
change is not made quietly.

## What this project cannot do for an operator

This document describes software. Most of what a deployment owes is about the
deployment, and none of the following is discharged by installing this.

Deciding on what basis the photographs may be processed at all, and recording
that decision. The pictures are already in the operator's library under the
operator's own arrangements; this service reads and rewrites them at the
operator's instruction.

Telling the people in the photographs anything, or answering them when they
ask. Nothing here reaches them and nothing here knows who they are.

Judging whether editing a particular photograph of a particular person is
lawful where the operator is. The notice in NOTICE.md names uses this project
does not support; that is not a legal assessment and it is not a substitute for
one.

Everything that depends on how the deployment is put together: who can reach
the API, over which network, with which retention period, on which machine and
with which backups. Those are settings and infrastructure, and this project can
describe the settings it has but cannot know what was done with them.

Anything about the photo library itself. It is a separate program with its own
storage, its own logs and its own behaviour, and connecting this service to it
does not bring it inside this document.

## Where this is kept true

Each claim above is either a command in this file, a setting named with the
issue that owns it, or an intention marked as one. A claim that stops being
true is a defect in this document, and the repair is to change the sentence
rather than to widen it. The sections that say something is not done are the
ones to be most careful with: when the issue they name lands, they are replaced
by the property and its command, and not by a reassurance.
