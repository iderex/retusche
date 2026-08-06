# Text fidelity: line endings, encoding and exact bytes

An image pipeline is tested with bytes that have to be exact. A tool that
rewrites a line ending on the way into git deletes a byte a fixture existed to
prove, and nothing announces it: the test still runs, it just tests a different
input than the one written down. This note says where that is decided, what
refuses it, and how a test embeds bytes that must survive.

## The three places a line ending is decided

The editor writes it. `.editorconfig` declares LF and UTF-8 for every file, with
markdown exempted from trailing-whitespace trimming because two trailing spaces
are a line break there. Nothing reads that file except editors that choose to,
so it declares an intention and refuses nothing.

Git normalises it. `.gitattributes` declares text and binary per type. Text
types are stored with LF whatever the platform that wrote them; binary types are
marked so no filter touches them at all.

The guard refuses what survived both. `.github/workflows/line-endings.yml` has
two legs and each reads what is stored rather than what is checked out.

## Why the guard reads the index and not the working tree

The obvious spelling of this check greps the files on disk. That spelling reds
the build for a contributor on a platform that checks out with carriage returns,
on a tree they have not modified, for a fault that exists nowhere except in
their own working copy. It also passes on a tree that stores CRLF whenever the
checkout happens to convert it back, which is the failure it was written to
catch.

So both legs read git rather than the disk. The first greps blobs at `HEAD`. The
second reads the index column of `git ls-files --eol`. The working tree is the
contributor's business, and `.gitattributes` therefore sets no `eol=` outside
shell scripts, where a carriage return lands inside the shebang and the
interpreter is not found.

`CONTRIBUTING.md` carries the command that shows this holds on a checkout that
does carry carriage returns.

## Why there are two legs

The first leg cannot see a file marked `binary` in `.gitattributes`. That macro
implies `-diff`, and `git grep -I` skips a file with `-diff`. This is correct for
a real image fixture, whose bytes are not text and must not be judged as text.
It is not correct for a source file somebody declared binary, which is a
one-line change to `.gitattributes` and an easy accident when a directory is
declared rather than a type.

The second leg is not fooled by the declaration, because `git ls-files --eol`
reports what the blob actually holds. A file git detects as binary from its
content reads `i/-text` and is not judged. A text file hidden behind a binary
declaration still reads `i/crlf` and is refused.

## Embedding exact bytes in a test

Base64 in source, decoded at the point of use, with the decoded bytes stated
beside it:

    from base64 import b64decode

    # b"first\r\nsecond\r\n": CRLF, which the loader must reject.
    CRLF_INPUT = b64decode("Zmlyc3QNCnNlY29uZA0K")

Three spellings were available and this is the one that survives the toolchain.

An actual carriage return typed into the source file does not survive at all.
The file is tracked text, `text=auto` normalises it on the way into git, and the
byte is gone before the test ever runs. This is the spelling the convention
exists to prevent, and it fails silently.

An escape sequence, `b"first\r\nsecond\r\n"`, does survive git: the file holds a
backslash and an `r`, which are two ordinary characters and no filter touches
them. It does not survive a reader. Inside a multi-line literal there is no way
to see which line breaks are escapes and which are real, an editor that trims
trailing whitespace changes bytes nobody meant to change, and a formatter that
rewraps a long string does the same. The literal stops being a statement about
bytes and becomes a statement about how the file happened to be laid out.

Base64 is one token. It has no whitespace, no line structure and nothing a
formatter or an editor can rewrite without changing the token visibly. The
comment beside it says what it decodes to, so the reader does not have to run
anything to know what is being tested, and the two can be checked against each
other.

The rule is for bytes that must be exact. An ordinary string in a test is an
ordinary string, and writing it in base64 makes it unreadable for no gain.

## What this does not cover

Encoding is declared and refused by nothing. `.editorconfig` says UTF-8 and
`.gitattributes` sets no `working-tree-encoding`, so a tracked file holding
invalid UTF-8 would pass every check in this repository today. What the tree
does refuse is a narrower thing and a different concern: `unicode-guard.yml`
refuses bidirectional and invisible control characters, which is about source
that renders differently from how it executes.

The guard says nothing about a working tree. A file on disk with CRLF is not a
finding, and that is deliberate rather than an oversight.

The binary exemption is decided by content, not by declaration. A fixture that
is genuinely binary but happens to hold no byte that git reads as binary is
judged as text by the second leg. No such fixture is in the tree, and the repair
if one arrives is to say so where it is added rather than to widen the guard.
