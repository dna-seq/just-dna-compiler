"""Durability for a long `enrich()` run: staged answers, an advisory lock, and a progress unit.

`enrich()` persisted nothing until its tail, so a run killed at minute 29 had written zero bytes and
the whole thirty minutes were gone. The obvious repair — checkpoint the table as it goes — trades away
a property somebody relies on, that a refused `strict` run leaves the module exactly as it was. The
trade is unnecessary: **the run is a transaction.** What goes to disk as the run proceeds is a
*journal of what the network answered*, staged beside the target and never read by anything but the
next run; the table itself is still written once, at the gate, by a writer that renames into place. A
refusal therefore commits nothing — as a written promise rather than an accident of statement order —
and a kill leaves the expensive answers where the next run can pick them up.

Three pieces live here, and they are one unit:

* `ResolutionJournal` — the staged answers. Same directory as the target, because a rename is atomic
  only within a filesystem; `shutil.move` across a partition degrades to copy-then-delete and is not.
  Staging beside the target makes a cross-device move structurally impossible rather than merely
  avoided.
* `spec_lock` — an advisory `flock` over the read-modify-write window. The window is the whole run:
  the table is read at the top and rewritten at the bottom, so two concurrent runs are last-writer-wins
  over a merge and neither knows.
* `SubjectProgress` — `(done, total)` over **subjects**, the keepalive a caller with an idle timeout
  needs.
"""

import csv
import logging
import os
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_format.layout import atomic_writer

# The one sanctioned inline-ish import: an optional platform dependency, guarded at module level.
# `fcntl` is POSIX-only, and the degradation it forces is documented rather than silent — see
# `spec_lock`. Held in a module-level name so a test can reach the unavailable branch.
try:
    import fcntl as _FCNTL
except ImportError:  # pragma: no cover - exercised by monkeypatching `_FCNTL` to None
    _FCNTL = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: Suffix of the staging directory, which is always a **sibling of the target file** rather than a
#: tempdir: `os.replace` is atomic only within one filesystem, and a tempdir may be on another one.
STAGING_SUFFIX = ".staging"

#: The staged answers, inside the staging directory.
JOURNAL_NAME = "answers.csv"

#: Refusal text for a spec directory another live run holds. Pinned by a test: a message a consumer
#: greps is an API, and this one has to be distinguishable from every other `EnrichmentError`.
LOCK_HELD_MESSAGE = (
    "another enrichment run holds {spec_dir}: the whole run is one read-modify-write window over "
    "resolution.csv, so two concurrent runs are last-writer-wins over a merge and neither can see "
    "the other. The lock is held by a live process and is released when it exits — wait for it, or "
    "kill it and re-run (the staged answers survive, so the re-run resumes rather than starting over)."
)

#: Refusal text for a `spec_dir` that is not a directory this process can open. `spec_lock` is the
#: first thing `enrich()` does, ahead of every loader, so without this the caller's own exception type
#: is bypassed by a raw `FileNotFoundError`/`NotADirectoryError` from `os.open`.
LOCK_TARGET_MESSAGE = (
    "{spec_dir} is not a directory this process can open, so the run cannot be excluded from a "
    "concurrent one and there is nothing to enrich. Point at a module spec directory."
)

#: Warning text for a platform or filesystem that will not take the lock. Degradation is documented
#: rather than silent, which the design owes: `flock` is untested here on the network filesystems a
#: consumer may use, and a lock that quietly did nothing would be worse than none at all.
LOCK_UNAVAILABLE_MESSAGE = (
    "Advisory locking is unavailable for %s (%s), so this run is NOT excluded from a concurrent one. "
    "The run still stages and commits atomically — what is missing is only the mutual exclusion, and "
    "on a network filesystem `flock` may be emulated or ignored entirely. Serialize enrichment of one "
    "spec directory yourself where that matters."
)


@dataclass(frozen=True)
class LockStatus:
    """Whether the run holds the advisory lock — true or **unknown**, never false.

    `held=True` is the acquired lock. `held=None` is the degradation: no `fcntl` on this platform, a
    filesystem that refuses the call, or a caller that writes nothing and therefore has no window to
    exclude. There is no `False`, deliberately: a run that finds the lock taken does not proceed
    unlocked, it refuses — so "we asked and were denied" never reaches a caller as a status.
    """

    held: bool | None
    reason: str | None


def staging_dir_for(target: Path) -> Path:
    """The staging directory for `target`, which is always a sibling of `target` itself.

    Dotted so an author's `ls` does not meet it, and named after the file it stages so two sidecars in
    one directory cannot collide. The sibling relationship is the correctness condition rather than a
    convenience — see the module docstring — and a test asserts it structurally rather than by reading
    this docstring.
    """
    target = Path(target)
    return target.parent / f".{target.name}{STAGING_SUFFIX}"


@dataclass
class ResolutionJournal:
    """What the network answered, on disk, in the target's own directory.

    It records the **raw link answers** (`rsid → [locus]`, plus which link said so), not the assembled
    `ResolutionRow`s. That is the load-bearing choice: everything downstream of an answer — the
    allele-aware hosting filter, the pseudoautosomal selection, `locus_index`, the minted VRS ids — is
    recomputed from it, so a resumed run reproduces the table an uninterrupted run produces even when
    the flags changed between the two, and a journal cannot encode a stale derivation. What it cannot
    survive is a different genome build, which is checked rather than assumed.

    Only *positive* answers are journaled. A subject the source said nothing about, or could not be
    asked about, is re-asked on the next run — a failed request is unchecked rather than absent, and
    freezing that into the journal would turn a transient outage into a permanent negative.

    Every `record` rewrites the whole file through `layout.atomic_writer`. The journal is small and a
    network call dwarfs the rewrite, and the alternative — appending — needs a reader that tolerates a
    torn tail, which is a second parser of the same file with a different idea of what a valid row is.
    """

    target: Path
    genome_build: str
    enabled: bool = True
    #: Whether *this* run is a re-derivation. It decides which staged answers may be seeded, and the
    #: rule is one sentence: **a re-derivation resumes only another re-derivation.** A gap-filling
    #: run's staged answers are, after its commit, exactly what produced the recorded table — so a
    #: later `--rederive` seeded from them would compare that table against its own provenance and
    #: report a clean bill for precisely the subjects it was asked to re-check. The reverse direction
    #: is fine and is allowed: an answer a re-derivation obtained is still an answer.
    rederive: bool = False
    #: rsid → (source, [locus dicts]). Insertion-ordered, so the file's row order is the order the
    #: links answered in and a resumed run's journal reads back the same way it was written.
    answers: dict[str, tuple[str, list[dict]]] = field(default_factory=dict)
    #: The rsids whose staged rows were written by a re-derivation, tracked so a rewrite re-emits the
    #: flag it read rather than restamping every row with this run's own.
    _rederived: set[str] = field(default_factory=set)

    _FIELDNAMES = ("rsid", "source", "genome_build", "rederive", "chrom", "start", "ref", "alts")

    @property
    def directory(self) -> Path:
        return staging_dir_for(self.target)

    @property
    def path(self) -> Path:
        return self.directory / JOURNAL_NAME

    def resume(self) -> dict[str, tuple[str, list[dict]]]:
        """Load a previous run's staged answers, or an empty mapping when there are none.

        Two kinds of staged row are skipped rather than seeded, and each says so out loud. A journal
        written under **another genome build** is ignored whole: the coordinates in it name positions
        on a different assembly, and one silently seeded here would be the RM36 defect arriving
        through a new door. And when this run is a **re-derivation**, rows a gap-filling run wrote are
        ignored — see the `rederive` field for why that is the whole point rather than caution.
        """
        if not self.enabled or not self.path.exists():
            return self.answers
        loaded: dict[str, tuple[str, list[dict]]] = {}
        rederived: set[str] = set()
        foreign = 0
        gapfilled = 0
        with self.path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if (row.get("genome_build") or "") != self.genome_build:
                    foreign += 1
                    continue
                rsid = (row.get("rsid") or "").strip()
                if not rsid:
                    continue
                from_rederive = (row.get("rederive") or "").strip() == "1"
                if self.rederive and not from_rederive:
                    gapfilled += 1
                    continue
                if from_rederive:
                    rederived.add(rsid)
                entry = loaded.setdefault(rsid, ((row.get("source") or "").strip(), []))
                entry[1].append(
                    {
                        "chrom": row.get("chrom") or None,
                        "start": int(row["start"]) if (row.get("start") or "").strip() else None,
                        "ref": row.get("ref") or None,
                        "alts": row.get("alts") or None,
                    }
                )
        if gapfilled:
            logger.info(
                "Re-derivation: %d staged answer(s) at %s came from a gap-filling run and are not "
                "seeded — after that run committed they are what produced the recorded table, so "
                "seeding them would compare the table against its own provenance and report no drift "
                "for exactly the subjects being re-checked. Those subjects are asked again.",
                gapfilled, self.path,
            )
        if foreign:
            logger.warning(
                "Staged answers at %s were recorded under a different genome build and are ignored "
                "(%d row(s)): a coordinate is valid on either assembly, it is simply a different "
                "base, so seeding them here would record another build's position as this module's "
                "own. They are re-asked from the sources.",
                self.path, foreign,
            )
        self.answers = loaded
        self._rederived = rederived
        if loaded:
            logger.info(
                "Resuming from %d staged answer(s) at %s — a previous run was interrupted after the "
                "sources answered and before the table was committed, so those subjects are not "
                "asked again.",
                len(loaded), self.path,
            )
        return self.answers

    def record(self, rsid: str, source: str, loci: Iterable[Mapping]) -> None:
        """Stage one link's answer for `rsid`, durably, before the next request is made."""
        if not self.enabled:
            return
        kept = [dict(locus) for locus in loci]
        if not kept:
            return
        self.answers[rsid] = (source, kept)
        if self.rederive:
            self._rederived.add(rsid)
        else:
            self._rederived.discard(rsid)
        self._flush()

    def _flush(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with atomic_writer(self.path, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self._FIELDNAMES))
            writer.writeheader()
            for rsid, (source, loci) in self.answers.items():
                for locus in loci:
                    writer.writerow(
                        {
                            "rsid": rsid,
                            "source": source,
                            "genome_build": self.genome_build,
                            "rederive": "1" if rsid in self._rederived else "",
                            "chrom": locus.get("chrom") or "",
                            "start": "" if locus.get("start") is None else locus["start"],
                            "ref": locus.get("ref") or "",
                            "alts": locus.get("alts") or "",
                        }
                    )

    def discard(self) -> None:
        """Remove the staged answers after a successful commit. The default; `keep_staging` skips it."""
        if not self.directory.exists():
            return
        self.path.unlink(missing_ok=True)
        # Only the directory this class owns, and only when nothing else put a file in it — a `rmdir`
        # that fails on a non-empty directory is the right failure, not something to force past.
        if not any(self.directory.iterdir()):
            self.directory.rmdir()


@contextmanager
def spec_lock(
    spec_dir: Path,
    *,
    enabled: bool = True,
    error: Callable[[str], Exception] = RuntimeError,
) -> Iterator[LockStatus]:
    """Hold an advisory `flock` on `spec_dir` for the whole read-modify-write window.

    **`flock` on the directory's own descriptor, and no lockfile.** A lockfile left behind by exactly
    the kill this transaction exists for would block every subsequent run — a worse unattended failure
    than the one it prevents — and the staleness rule that would fix it is a clock. `flock` dies with
    the process, so there is nothing to go stale and nothing to clean up.

    **Non-blocking, and a refusal rather than a wait.** A run that silently waits half an hour behind a
    zombie is its own unattended failure. The refusal is accurate by construction: the lock is only
    ever held by a live process.

    **The degradation is documented rather than silent.** Without `fcntl` (a non-POSIX platform), or on
    a filesystem that refuses the call — a network mount may return `ENOLCK`/`EOPNOTSUPP`, or emulate
    `flock` in a way that excludes nothing — the run proceeds and says so. `flock` is untested here on
    the network filesystems a consumer may use. `enabled=False` is the caller that writes nothing and
    therefore has no window to exclude; it is not a degradation and warns about nothing.
    """
    spec_dir = Path(spec_dir)
    if not enabled:
        yield LockStatus(
            held=None,
            reason="nothing is written, so there is no read-modify-write window to exclude",
        )
        return
    if _FCNTL is None:
        logger.warning(LOCK_UNAVAILABLE_MESSAGE, spec_dir, "this platform has no fcntl")
        yield LockStatus(held=None, reason="this platform has no fcntl")
        return
    # Checked rather than caught, so the descriptor open below cannot leak `os`'s exception type past
    # the pass that owns this call. This runs before every loader in `enrich()`, so it is the first
    # thing a caller with a wrong path meets.
    if not spec_dir.is_dir():
        raise error(LOCK_TARGET_MESSAGE.format(spec_dir=spec_dir))
    fd = os.open(spec_dir, os.O_RDONLY)
    status = _acquire(fd, spec_dir, error)
    try:
        yield status
    finally:
        # Closing the descriptor releases the lock; an explicit `LOCK_UN` first would be a second way
        # to do the same thing, and a `finally` with one statement in it cannot get them out of order.
        os.close(fd)


def _acquire(fd: int, spec_dir: Path, error: Callable[[str], Exception]) -> LockStatus:
    """Take the lock on `fd`, refuse if a live run holds it, degrade if the filesystem will not."""
    try:
        _FCNTL.flock(fd, _FCNTL.LOCK_EX | _FCNTL.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise error(LOCK_HELD_MESSAGE.format(spec_dir=spec_dir)) from exc
    except OSError as exc:
        logger.warning(LOCK_UNAVAILABLE_MESSAGE, spec_dir, exc)
        return LockStatus(held=None, reason=f"the filesystem refused an advisory lock ({exc})")
    return LockStatus(held=True, reason=None)


class SubjectProgress:
    """`(done, total)` over **subjects**, reported to a caller's callback.

    Subjects, because the incident is an idle timeout: both reported runs died at 1800 s with
    essentially every variant resolved, so what a caller needs is a keepalive with monotonic progress.
    That rules out phases — a twenty-nine-minute phase emits nothing and the timeout fires anyway — and
    it rules out links, whose `total` is not known until resolution finds them. The subject count is
    known before the first call, and subjects are the only unit an author's mental model already has;
    a link count would publish the batched resolver's internals as a contract.

    Monotonicity is structural rather than promised: `done` is the size of a set that only grows, so a
    subject settled twice reports once and a subject settled by two different links cannot double-count.

    The callback is the caller's code and its exceptions are not swallowed. Under the transaction that
    is safe to say: an abort here leaves the staged answers on disk exactly as a kill does.
    """

    def __init__(self, total: int, callback: Callable[[int, int], None] | None) -> None:
        self._total = total
        self._callback = callback
        self._settled: set[str] = set()
        if callback is not None:
            callback(0, total)

    @property
    def settled(self) -> int:
        return len(self._settled)

    def settle(self, keys: Iterable[str]) -> None:
        """Mark subjects answered; report only when the count actually moved.

        The set is updated **before** the callback is consulted, not after it is found absent: a
        tracker with no callback still counts, so `settled` means the same thing whether or not
        anyone is listening. Guarding the update instead would make the property a silent zero — the
        shape a reader trusts precisely because the docstring promises the count only grows.
        """
        before = len(self._settled)
        self._settled.update(keys)
        if self._callback is not None and len(self._settled) > before:
            self._callback(len(self._settled), self._total)
