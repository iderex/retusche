# Security policy

This backend is built to read photographs out of a photo library and write
results back into it. A vulnerability here is a disclosure risk for pictures
that belong to somebody, not an inconvenience, so there is a way to report one
that does not start by publishing it.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository, from the
Security tab, or directly at

    https://github.com/iderex/retusche/security/advisories/new

That route is enabled here, which is a fact about the repository rather than an
intention stated in this file:

    gh api repos/iderex/retusche/private-vulnerability-reporting
    {"enabled":true}

The report stays private to the maintainer and to whoever the maintainer invites
into it, and it becomes an advisory only when one is published. Do not open a
public issue for a suspected vulnerability. If the private route is unavailable
to you for any reason, open a public issue that says only that you have
something to report and asks for a private channel, with no detail in it.

Include what you would want to receive: what the problem is, how to reach it,
what an attacker gets, and the commit or version you looked at. A proof of
concept helps and is not required.

## What you can expect

A first response within five days of the report arriving, saying that it was
received and read. That is a target rather than a commitment, and a report that
has not been answered in that time has not been dismissed.

After that: an assessment of whether the report is accepted, with the reasoning
either way, and a fix or a stated refusal to fix rather than silence. Where a
fix lands, an advisory is published on this repository naming the versions
affected, and a CVE is requested where the problem warrants one. You are
credited by whatever name you ask for, or not at all if you would rather not be.

Please give the fix a chance to exist before publishing. There is no fixed
embargo period demanded here, because a period this policy cannot enforce is not
worth writing down as though it could be.

## What is in scope

The code in this repository, and its supply chain as this repository controls
it: the dependency set, the lock file and the workflow definitions.

That set is currently smaller than the description above suggests, and the
difference matters to anyone deciding whether to look. There is no HTTP surface,
no queue, no engine and no photo-library client in the tree yet. What exists is
the package skeleton, the contract package and the workflows, which is what
`docs/architecture.md` describes and keeps current. A report against code that
is not here yet is welcome as a design objection on the issue tracker, in the
open, because it is not a vulnerability in anything running.

## What is not in scope

Vulnerabilities in the photo library this project integrates with, in a model
runtime, in a model's weights, or in any other upstream project. Report those to
the project that owns them. If the fault is in how retusche uses one of them,
that is in scope and it belongs here.

The behaviour of a generative model is not in scope as a vulnerability. Output
that is offensive, unexpected, or that reconstructs something the operator did
not want reconstructed, is a property of the model and of the operator's choice
to run it. What this project owes there is transparency about what was
generated (#69, #70) and about which models are offered and under which licences
(#71), not a security advisory.

Findings that consist only of a scanner's output, with no reachable path through
this code, are not in scope. Neither is a missing hardening measure with no
demonstrated consequence, though it is a welcome issue in the open.

## What this project does not promise

retusche makes no security guarantees for a deployment exposed to an untrusted
network unless the operator guide's conditions are met.

Those conditions do not exist yet. The operator guide is issue #61 and is not
written, so there is nothing today that a deployment could satisfy, and the
sentence above therefore reduces to the harder one: for a deployment exposed to
an untrusted network, this project currently promises nothing at all. That is a
statement about the state of the documentation and of the code, and it stops
being true when #61 lands and states conditions, not when this file is reworded.

There are no releases and no tags to support:

    gh api repos/iderex/retusche/releases --jq 'length'
    0
    gh api repos/iderex/retusche/tags --jq 'length'
    0

So there is no supported-version table here. The default branch is the only
thing that exists, and it is the only thing a report can be about. This section
is replaced when the release route (#89) gives versions something to mean.
