# 0005. The job store: SQLite in one file, administered by nobody

Jobs are kept in a single SQLite database file, written by the standard
library's `sqlite3` module, in write-ahead logging mode with `synchronous` set
to `FULL`. There is no server to install, no schema for an operator to migrate
by hand today, and no runtime dependency added to the project.

The store keeps the job model in `retusche.queue`: an identifier, a state and,
where the state is terminal, the reason it ended. What it does not keep is
result files, which are #36's, and the fields that reconstruct a request, which
are #24's.

## What the choice is between

Four routes were considered for a record that has to outlive the process that
wrote it.

**A file per job, written and renamed atomically.** No dependency at all, and
the format is readable with a text editor, which is a real advantage the day
somebody has to look. It costs the properties this issue is about. There is no
transaction across a read and a write, so the check that a move is legal and the
write that applies it cannot be one operation, and two writers interleaved
produce a state neither of them asked for. Listing jobs by state means reading
every file. And durability becomes this project's own problem: the rename, the
directory `fsync` and the ordering between them have to be right on every
platform this runs on, which is a thing to get wrong quietly.

**SQLite in one file.** Transactions, so the read, the check and the write are
one thing. Crash-safe by design rather than by this project's own care. In the
standard library, so it adds no distribution to the lock file and nothing to the
dependency surface reachable from a socket, which is the constraint
`docs/architecture.md` puts on the orchestration layer. An operator installs
nothing and administers nothing: the file appears where the configuration points
and a backup is a copy of it.

**PostgreSQL, or another server database.** Everything SQLite gives, plus
concurrent writers from several processes and a network boundary. It costs the
operator a second service to run, back up and upgrade, in a project whose whole
proposition is that it sits quietly beside a photo library on one host. It also
costs a runtime dependency and a driver in the process that listens on a socket.
Nothing in the plan needs a second writing process: one lane runs at a time
(#27) and the queue is one process.

**In memory, with no store at all.** Named to be ruled out. The issue this
record belongs to exists because a queue that does not survive a restart loses
work an operator was told had been accepted.

## Why the second one

The three rules this repository is written under decide it more than the feature
comparison does. A move that is not in the transition table has to be refused
rather than noticed, and a refusal is only a refusal if the write it would have
made cannot land; that is a transaction, and the file-per-job route does not
have one. A claim that a job survives a restart has to be produced by something
rather than asserted, and a store that can be opened twice over one path is
something a test can produce it from.

The means check `CONTRIBUTING.md` asks for, on this artefact. The means is the
standard library's `sqlite3` module, and it fits because it adds no language, no
runtime and no dependency the tree does not already carry; because the suite
that already exists tests it with no parallel apparatus, a temporary directory
being all it needs; and because the property this issue is about, a move that is
either applied or refused, is one SQLite can be held to and a directory of files
cannot.

## What an unclean stop leaves

The pair of settings is what decides this, and both are set when the store is
opened.

Write-ahead logging means a commit appends to a `-wal` file beside the database
and the database file is brought up to date later. A process that dies leaves
the `-wal` file behind, and the next connection replays it, so a committed
transaction is still committed. `synchronous = FULL` means the commit is flushed
before it is reported as committed, so a power loss cannot acknowledge a write
that never reached the platter.

What is lost is the transaction that had not committed, and nothing else. Since
every move is one transaction, that is at most one move, and the job is left in
the state it was in before it.

**This is SQLite's stated guarantee and not a measurement made here.** No test in
this repository kills a process, cuts power or fills a disk.
`tests/test_job_store.py` says so in its own docstring rather than leaving it to
be assumed, and what it does measure is narrower: that a committed row is in the
file rather than in the object that wrote it, readable by a second store and by
a connection that never saw the writer. A test that proves the crash case needs
to stop a process without letting it clean up, and that is not built here.

## What an operator has to administer

Nothing, today. The file is created when it is first opened. There is no user,
no port, no daemon and no configuration beyond where the file goes, which
arrives with the configuration layer in #62; until then the path is an argument.

Two things an operator will eventually be owed, neither of which is in this
record. A backup instruction, which belongs with the operator guide in #61 and
is one sentence because the answer is to copy the file and the two beside it.
And a schema change route, which does not exist because the schema has not
changed yet; the first change that needs one is where it is designed, and
writing a migration framework before there is a migration is the habit the
means check exists against.

## What was not evaluated

No throughput or latency measurement was made, of this store or of any
alternative. Nothing above rests on one. The queue this store serves runs one
job at a time on a device where the work is seconds long, so a store that can
answer thousands of writes a second and one that can answer tens are not
distinguishable at this scale, and a number produced here would be a number
about a benchmark rather than about the service.

Concurrency across several writing processes is not evaluated either, because
nothing in the plan has two. The connection is used from the thread that opened
it, which is `sqlite3`'s default. The day a second writer exists, this record is
where the reasoning that ruled a server database out has to be read again.

## What would reverse it

A second process that has to write jobs, or a deployment shape where the store
must live away from the host doing the work. Either makes the middle option's
cost worth paying. Neither reverses the job model itself, which is why the
states and the transitions are in a module that names no store.
