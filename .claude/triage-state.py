#!/usr/bin/env python3
"""Ledger for the consumer-suggestion triage loop.

Reports, per top-level `## Sn` section of a consumer-notes document, whether it has
been triaged — and if it was, whether the consumer has revised it since.

The ledger is the document itself. A triaged section carries, inside its
`**Status —**` paragraph, a marker holding a fingerprint of the consumer's own text:

    <!-- triaged: 0.5.3 · sha 4f2a1c9d8e07 -->

The fingerprint deliberately excludes every `**Status` paragraph and the marker, so it
covers what the consumer wrote and never what we replied. Re-running after our own
write is therefore a no-op, which is what stops the watcher self-firing forever.

Verdicts:
    new             no marker, no reply       -> triage it
    unmarked-reply  replied before the marker -> backfill the marker (see --backfill)
    revised         marker, fingerprint moved -> consumer edited a replied item, re-triage
    current         marker matches            -> nothing to do

This file is Python with a `.py` extension for a reason — see the `bash` trap in
docs/CONSUMER_TRIAGE_LOOP.md § 6. Run it, never `bash` it.

Usage:
    .claude/triage-state.py [path] [--pending] [--backfill]
    .claude/triage-state.py --next        # the next unclaimed Sn, over the live + history files
"""

import hashlib
import pathlib
import re
import sys

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
DEFAULT_DOC = DOCS / "CONSUMER_SUGGESTIONS.md"

# Every file an `Sn` can be sitting in, found rather than listed: the live inbox, the history file, and
# the archived halves of the history file, which live in a subdirectory and will be joined by more of
# them. `next_id` is wrong the moment one of these is missed — it would hand out an id that is already
# taken — and a hard-coded list is exactly the thing that goes stale when a file is split off.
def corpus() -> list[pathlib.Path]:
    return [DEFAULT_DOC, *sorted(DOCS.rglob("CONSUMER_SUGGESTIONS_HISTORY*.md"))]

# A section is a top-level `## Sn` heading. `###` sub-headings fold into their parent:
# they are part of what the consumer wrote, so they belong in the parent's fingerprint.
SECTION_RE = re.compile(r"^## +S(\d+)\b")
BOUNDARY_RE = re.compile(r"^#{1,2} ")
STATUS_RE = re.compile(r"^\*\*Status\b")
MARKER_RE = re.compile(r"<!-- *triaged:.*?sha +([0-9a-f]{12}) *-->")
# A trailing horizontal rule is punctuation between sections rather than anything the consumer said,
# and dropping one is editorial — so hashing it lets our own separator edit report as `revised`. Same
# family as the marker exclusion. Adopted from the published gist, where a second repo hit it first.
RULE_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")


def sections(lines: list[str]) -> list[tuple[str, int, list[str]]]:
    """Split into (id, 1-based heading line, body lines). Ids repeat if the doc repeats them."""
    out = []
    for start, line in enumerate(lines):
        if not SECTION_RE.match(line):
            continue
        ident = "S" + SECTION_RE.match(line).group(1)
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if BOUNDARY_RE.match(lines[j]):
                end = j
                break
        out.append((ident, start + 1, lines[start + 1 : end]))
    return out


def block_replies(lines: list[str]) -> dict[str, int]:
    """Section ids answered by a `**Status` paragraph in an enclosing `# ` preamble.

    The house convention allows one reply to cover several sections at once — the
    0.5.2 block at the top of the just-dna-lite notes answers S3, S4 and S6 together.
    Such a section carries no reply of its own, so the naive presence test reads it as
    untriaged. Maps id -> last line of the covering paragraph, which is where a
    backfilled marker for it would go.
    """
    covered: dict[str, int] = {}
    for start, line in enumerate(lines):
        if not line.startswith("# "):
            continue
        for i in range(start + 1, len(lines)):
            if BOUNDARY_RE.match(lines[i]):  # preamble ends at the first section
                break
            if not STATUS_RE.match(lines[i]):
                continue
            end = i
            while end + 1 < len(lines) and lines[end + 1].strip() != "":
                end += 1
            for ident in set(re.findall(r"\bS(\d+)\b", " ".join(lines[i : end + 1]))):
                covered.setdefault("S" + ident, end)
    return covered


def reply_end(body: list[str], start: int) -> int:
    """Index of the last line of the reply that begins at `start`.

    **A triaged reply ends at its marker, not at the first blank line.** The documented shape puts
    the reply first in the section and terminates it with the marker, so a reply of several
    paragraphs — which is the normal size for one that has to say what was probed, where it landed
    and why a candidate repair was rejected — is excluded whole. Paragraph-scoped skipping read
    every paragraph after the first as consumer text, so writing a reply immediately reported the
    section `revised`, which is the same self-firing failure the marker exclusion was added to stop.

    With no marker ahead (a reply written before the ledger existed) the reply is taken as the
    single paragraph. That is all that can be inferred, and it fails safe: swallowing the rest of
    the section instead would hash every unmarked reply to the same empty text.
    """
    for i in range(start, len(body)):
        if MARKER_RE.search(body[i]):
            return i
    end = start
    while end + 1 < len(body) and body[end + 1].strip() != "":
        end += 1
    return end


def consumer_text(body: list[str]) -> list[str]:
    """Body with every reply and every marker removed.

    Markers are dropped wherever they appear, not only inside a reply: a section
    answered by a shared block reply carries a standalone one, and hashing it would
    make the section read `revised` from the moment it was marked.
    """
    kept: list[str] = []
    index = 0
    while index < len(body):
        line = body[index]
        if STATUS_RE.match(line):
            index = reply_end(body, index) + 1
            continue
        if MARKER_RE.search(line):
            index += 1
            continue
        kept.append(line)
        index += 1
    return kept


def fingerprint(body: list[str]) -> str:
    """Stable over cosmetic edits: trailing whitespace and blank-line runs are normalized."""
    normalized, blank = [], False
    for line in consumer_text(body):
        stripped = line.rstrip()
        if stripped == "":
            if blank:
                continue
            blank = True
        else:
            blank = False
        normalized.append(stripped)
    while normalized and (normalized[-1] == "" or RULE_RE.match(normalized[-1])):
        normalized.pop()
    text = "\n".join(normalized).strip() + "\n"
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def stored_sha(body: list[str]) -> str | None:
    for line in body:
        found = MARKER_RE.search(line)
        if found:
            return found.group(1)
    return None


def has_reply(body: list[str]) -> bool:
    return any(STATUS_RE.match(line) for line in body)


def classify(body: list[str], block_replied: bool) -> tuple[str, str, str | None]:
    current, stored = fingerprint(body), stored_sha(body)
    if stored is None:
        replied = has_reply(body) or block_replied
        return ("unmarked-reply" if replied else "new"), current, None
    if stored != current:
        return "revised", current, stored
    return "current", current, stored


def next_id() -> tuple[str, dict[str, int]]:
    """The next unclaimed `Sn`, over the live document **and** every history file.

    Computed rather than remembered, because the number is exactly the kind of fact that goes stale:
    once answered items move out, the live file's highest id is not the corpus's highest, and an empty
    inbox would invite `S1` a second time. Scanning the files cannot drift from them — which is why
    `corpus()` globs for the history files rather than naming them.

    Returns `(next, {filename: highest})` so a caller can see where the number came from."""
    highest: dict[str, int] = {}
    for doc in corpus():
        if not doc.is_file():
            continue
        ids = [
            int(SECTION_RE.match(line).group(1))
            for line in doc.read_text().splitlines()
            if SECTION_RE.match(line)
        ]
        if ids:
            highest[doc.name] = max(ids)
    return f"S{max(highest.values(), default=0) + 1}", highest


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if "--next" in flags:
        ident, seen = next_id()
        for name, top in sorted(seen.items()):
            print(f"{name}: highest S{top}", file=sys.stderr)
        print(ident)
        return 0

    doc = pathlib.Path(args[0]) if args else DEFAULT_DOC
    if not doc.is_file():
        print(f"no such document: {doc}", file=sys.stderr)
        return 2

    lines = doc.read_text().splitlines()
    covered = block_replies(lines)
    rows = [(ident, line, *classify(body, ident in covered))
            for ident, line, body in sections(lines)]
    pending = [r for r in rows if r[2] in {"new", "revised", "unmarked-reply"}]

    if "--backfill" in flags:
        return backfill(doc, lines, rows, covered)

    for ident, line, verdict, current, stored in (pending if "--pending" in flags else rows):
        note = f"  (was {stored})" if verdict == "revised" else ""
        if verdict == "unmarked-reply" and ident in covered:
            note = "  (block reply)"
        print(f"{verdict:<15}{ident:<5}{doc.name}:{line}\tsha {current}{note}")

    if not pending:
        print(f"\nnothing pending — {len(rows)} section(s) all current", file=sys.stderr)
    else:
        tally = ", ".join(f"{sum(1 for r in pending if r[2] == v)} {v}" for v in
                          ("new", "revised", "unmarked-reply") if any(r[2] == v for r in pending))
        print(f"\n{len(pending)} of {len(rows)} pending: {tally}", file=sys.stderr)
    return 0


def backfill(doc: pathlib.Path, lines: list[str], rows: list, covered: dict[str, int]) -> int:
    """Stamp a marker onto sections replied to before the ledger existed.

    Only touches `unmarked-reply`, and never invents or edits a reply. A section with
    its own `**Status` paragraph gets the marker appended to it. A section answered by
    a shared block reply gets a standalone marker line at the end of its own body,
    because one paragraph cannot carry four different fingerprints.
    """
    edits = []
    for ident, line, verdict, current, _ in rows:
        if verdict != "unmarked-reply":
            continue
        end, standalone = None, False
        for i in range(line, len(lines)):
            if BOUNDARY_RE.match(lines[i]):
                break
            if STATUS_RE.match(lines[i]):
                end = i
                while end + 1 < len(lines) and lines[end + 1].strip() != "":
                    end += 1
                break
        if end is None and ident in covered:  # shared block reply, mark the section itself
            end, standalone = line, True
            for i in range(line, len(lines)):
                if BOUNDARY_RE.match(lines[i]):
                    break
                if lines[i].strip():
                    end = i
        if end is None:
            print(f"{ident}: reply not located, skipped", file=sys.stderr)
            continue
        edits.append((end, ident, current, standalone))

    for end, ident, current, standalone in sorted(edits, reverse=True):
        marker = f"<!-- triaged: backfilled · sha {current} -->"
        if standalone:
            lines.insert(end + 1, "")
            lines.insert(end + 2, marker)
        else:
            lines[end] = lines[end].rstrip() + " " + marker
        print(f"{ident}: marked sha {current}{' (standalone)' if standalone else ''}")

    if edits:
        doc.write_text("\n".join(lines) + "\n")
    print(f"\n{len(edits)} section(s) marked", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
