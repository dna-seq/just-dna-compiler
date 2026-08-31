#!/usr/bin/env python3
"""Allocate the next `RMn`, and **reserve** it so two sessions cannot take the same number.

The consumer-suggestion ledger (`triage-state.py`) has an allocator for `Sn` because the id is
written into a document; `RMn` had none. `docs/RM_TOC.md` is the complete index of every item, but an
index is not an allocator: nothing *claims* a number, so two sessions grepping "the highest in use" a
minute apart both read the same answer and both write it.

**That is a reproduced incident, not a hypothesis.** On 2026-09-01 two sessions sharing this working
tree filed different work as RM159 a minute apart, and the tree carried two RM159 entries pointing at
different items — see git `741ec59`, which renumbered one of them to RM161. Grepping cannot fix this,
because the gap between *reading* the maximum and *writing* the entry is exactly where the other
session reads. The reservation has to be a single atomic write.

So this tool does both halves:

* **Scan** `docs/` for every `RM<digits>` and compute the lowest free number. Found rather than
  remembered, and over the whole tree rather than one file: an item is referenced from proposals,
  probes and the changelog, and a scanner that read only the index would hand out a number some other
  document already uses.
* **Reserve** it by appending a placeholder line to `docs/RM_TOC.md` under an advisory `flock`, so the
  read and the write are one critical section. The next session's scan then sees the number as taken,
  because the placeholder contains it.

**The lock is on `docs/`, the directory — never on `RM_TOC.md`.** Two reasons, and the second is
measured rather than assumed. A lockfile left behind by the kill this guards against would block every
later run, and the staleness rule that repairs that is a clock (`@flock-not-a-lockfile`). And `flock`
binds an *inode*: an editor or an atomic writer that renames a new file over `RM_TOC.md` leaves the
holder locking an unlinked inode while a second process locks the new one and acquires immediately —
verified in a sandbox before this was written. Locking the containing directory is stable across that,
and it is the same idiom `just_dna_enricher.transaction.spec_lock` uses for `enrich`.

The reservation is a real index row, marked `🔷 reserved`, so a number that is claimed and then
abandoned is **visible** rather than silently burned. Fill it in when the item is written; delete the
line if the work is dropped. It is deliberately not a separate state file: a side-car the index cannot
see is how a number goes missing, which is the failure `RM_TOC.md` itself exists to prevent.

This file is Python with a `.py` extension for a reason — see the `bash` trap in
docs/CONSUMER_TRIAGE_LOOP.md § 6. Run it, never `bash` it.

Usage:
    .claude/rm-next.py                 # reserve the next number and print it
    .claude/rm-next.py --dry-run       # print what it would reserve, write nothing
    .claude/rm-next.py --note "..."    # a few words on what it is for, into the placeholder
    .claude/rm-next.py --release       # release a reservation you are not going to use
"""

import os
import pathlib
import re
import sys

try:
    import fcntl as _FCNTL
except ImportError:  # pragma: no cover - non-POSIX; the degradation is announced, never silent
    _FCNTL = None

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"
TOC = DOCS / "RM_TOC.md"

#: Every `RM<digits>`, anywhere. Deliberately not anchored to an index row: the number must be free
#: across every document, and a reference in a proposal or a probe is a use.
RM_RE = re.compile(r"\bRM(\d+)\b")

#: The reservation row. `🔷` distinguishes it from the index's own ✅/⏳/🔲/✖ states at a glance, and
#: the marker is what a later scan counts, so it must contain the number literally.
RESERVED_MARK = "🔷 **reserved**"
RESERVED_RE = re.compile(r"^- 🔷 \*\*reserved\*\* \*\*RM(\d+)\*\*")

#: Where a reservation is appended. A heading rather than the file's end, because the end of RM_TOC.md
#: is a prose section ("Where an item comes from") and a row landing under it would read as part of it
#: — the furniture hazard the triage loop's own § 6 records.
ANCHOR = "## ⏳ Open, no release decided"

LOCK_UNAVAILABLE = (
    "advisory locking is unavailable for {docs} ({why}), so this reservation is NOT excluded from a "
    "concurrent one. Check `grep -n 'RM{n}' docs/RM_TOC.md` before writing the entry."
)


def used_numbers() -> dict[int, str]:
    """`{number: first file it was seen in}` for every `RMn` mentioned anywhere under `docs/`.

    A reservation placeholder counts as used, which is the whole mechanism: the row contains the
    number, so the next scan cannot hand it out again.
    """
    seen: dict[int, str] = {}
    for path in sorted(DOCS.rglob("*.md")):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            # Unreadable is not absent. A file this cannot open may hold the very number about to be
            # handed out, so it is reported rather than skipped silently.
            print(f"warning: could not read {path}, so its numbers are unknown", file=sys.stderr)
            continue
        for found in RM_RE.finditer(text):
            seen.setdefault(int(found.group(1)), str(path.relative_to(DOCS.parent)))
    return seen


def next_free(used: dict[int, str]) -> int:
    """The lowest unused number above the current maximum.

    **Above the maximum, never filling a gap.** There are no gaps today (RM1–RM161 are all in use),
    but a gap can only mean an item was withdrawn — and its number stays referenced in whatever
    argued the withdrawal, so reusing it would make two different items answer to one id in the
    record. Same rule as `Sn`: ids are never reused.
    """
    return max(used, default=0) + 1


def reservations(text: str) -> dict[int, str]:
    """`{number: the row}` for every reservation currently standing in the index."""
    out: dict[int, str] = {}
    for line in text.splitlines():
        found = RESERVED_RE.match(line)
        if found:
            out[int(found.group(1))] = line
    return out


def _row(number: int, note: str | None) -> str:
    what = note.strip() if note and note.strip() else "claimed, entry not yet written"
    return (
        f"- {RESERVED_MARK} **RM{number}** — {what}. Claimed by an allocator run so a concurrent "
        f"session cannot take the same number; replace this line with the item's real index row, or "
        f"delete it if the work is dropped (`.claude/rm-next.py --release`)."
    )


def _tombstone(number: int) -> str:
    """What a released reservation leaves behind: a row that still *contains* the number.

    It has to contain it literally, because `used_numbers` is a scan — a tombstone the scanner cannot
    see is the same as a deleted row, which is the bug this replaced.
    """
    return (
        f"- ✖ **RM{number}** — reserved and released without an item being written. The number is "
        f"spent rather than free: ids are never reused, so a later reference to RM{number} can only "
        f"mean this."
    )


def _insert(text: str, row: str) -> str:
    """Put `row` directly under the open-items heading, or at the end if that heading is gone.

    The fallback is announced rather than silent: a renamed heading means the reservation lands
    somewhere a reader is not looking, and finding that out from a misplaced row later is worse.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(ANCHOR):
            # After the heading and the blank line that follows it, before the first row.
            at = i + 1
            while at < len(lines) and not lines[at].startswith("- "):
                at += 1
            lines.insert(at, row)
            return "\n".join(lines) + "\n"
    print(
        f"warning: no {ANCHOR!r} heading in {TOC.name}; appending at the end of the file instead",
        file=sys.stderr,
    )
    return text.rstrip("\n") + "\n" + row + "\n"


class _Unlocked:
    """The degradation, carried as a value so the caller reports it rather than assuming a lock."""

    def __init__(self, why: str) -> None:
        self.why = why


def _lock(fd: int) -> _Unlocked | None:
    """Take the exclusive lock, or say why not. Never returns a false "we have it"."""
    try:
        _FCNTL.flock(fd, _FCNTL.LOCK_EX)
    except OSError as exc:
        # A network filesystem may refuse or emulate `flock`. Blocking (not `LOCK_NB`) on purpose:
        # the critical section is a file read plus one append, so a wait is milliseconds, and a
        # refusal here would send a caller off to allocate by hand — which is the failure mode.
        return _Unlocked(str(exc))
    return None


def allocate(note: str | None, dry_run: bool) -> int:
    """Reserve and return the next number, holding `docs/` for the read-and-append."""
    if _FCNTL is None or dry_run:
        used = used_numbers()
        number = next_free(used)
        if dry_run:
            print(f"--dry-run: would reserve RM{number} (nothing written)", file=sys.stderr)
            return number
        print("warning: " + LOCK_UNAVAILABLE.format(docs=DOCS, why="this platform has no fcntl",
                                                    n=number), file=sys.stderr)
        TOC.write_text(_insert(TOC.read_text(), _row(number, note)))
        return number

    fd = os.open(DOCS, os.O_RDONLY)
    try:
        degraded = _lock(fd)
        # **Everything below is inside the critical section**, and the scan has to be too: reading the
        # maximum outside the lock and appending inside it is the same race with a smaller window.
        used = used_numbers()
        number = next_free(used)
        if degraded is not None:
            print("warning: " + LOCK_UNAVAILABLE.format(docs=DOCS, why=degraded.why, n=number),
                  file=sys.stderr)
        TOC.write_text(_insert(TOC.read_text(), _row(number, note)))
        return number
    finally:
        # Closing releases the lock; an explicit LOCK_UN first would be a second way to do one thing.
        os.close(fd)


def release(number: int) -> int:
    """Drop a standing reservation, leaving a tombstone so the number is never handed out again.

    **The tombstone is the whole point, and the first cut of this got it wrong.** Deleting the row
    outright made the number free again — the next scan found nothing containing it — so a released
    RM10 was immediately re-reserved as RM10. That contradicts the rule `next_free` states and `Sn`
    has always followed: an id that was claimed is spent, because whatever argued the withdrawal
    refers to it by number, and a reused id makes two different items answer to one name in the
    record. Verified by releasing and re-allocating, which is how the defect surfaced.
    """
    fd = os.open(DOCS, os.O_RDONLY) if _FCNTL is not None else None
    try:
        if fd is not None:
            _lock(fd)
        text = TOC.read_text()
        standing = reservations(text)
        if number not in standing:
            print(f"RM{number} is not a standing reservation in {TOC.name}", file=sys.stderr)
            return 1
        kept = [
            _tombstone(number) if line == standing[number] else line
            for line in text.splitlines()
        ]
        TOC.write_text("\n".join(kept) + "\n")
        print(f"released RM{number} — the number stays spent, so the next allocation moves past it")
        return 0
    finally:
        if fd is not None:
            os.close(fd)


def main() -> int:
    argv = sys.argv[1:]
    flags = {a for a in argv if a.startswith("--")}
    note = None
    if "--note" in argv:
        at = argv.index("--note")
        if at + 1 >= len(argv):
            print("--note needs a value", file=sys.stderr)
            return 2
        note = argv[at + 1]

    if "--release" in flags:
        rest = [a for a in argv if not a.startswith("--") and a != note]
        if len(rest) != 1:
            print("usage: .claude/rm-next.py --release RM161", file=sys.stderr)
            return 2
        return release(int(rest[0].removeprefix("RM")))

    if "--list" in flags:
        standing = reservations(TOC.read_text())
        if not standing:
            print("no standing reservations")
            return 0
        for number in sorted(standing):
            print(standing[number])
        return 0

    number = allocate(note, dry_run="--dry-run" in flags)
    used = used_numbers()
    print(f"highest in use: RM{max(used, default=0)}", file=sys.stderr)
    print(f"RM{number}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
