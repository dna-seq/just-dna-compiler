"""Every relative link between the repository's markdown files resolves — the file, and the heading.

**Why this is a test and not a script.** `uv run pytest` is the only thing CI runs, so a check that
lives anywhere else runs when somebody remembers it, which is exactly the property that let the defect
accumulate: nineteen `FILE.md#anchor` links pointing at headings that no longer existed, almost all of
them `ROADMAP.md#rm4x-…` pointers to items that had since moved to `ROADMAP_HISTORY.md` (R2-12 in
`docs/probes/DOGFOOD_0_6_FINDINGS.md`). The mechanism is structural rather than careless — this repo
deliberately splits live from historical (ROADMAP/ROADMAP_HISTORY, CONSUMER_SUGGESTIONS and its
history file), so *an item moving between the two* breaks every pointer at it, and the move is the
routine event. `RM_TOC.md` exists because RM33 became unfindable; this is the same failure one
document over.

It sits in `schema/tests/` beside `test_printed_contract.py`, which is the nearest precedent: a guard
over a surface a reader consumes rather than over a tier's behaviour. It imports nothing from any
package and walks the repository the way `compiler/tests/test_build_call_sites.py` does.

Scope is every tracked markdown file, **including the reference-example and package READMEs** — seven
of those link out to `../../docs/ROADMAP.md` and `../../docs/ROADMAP_HISTORY.md`, which is precisely
the live/history pair this guard exists for, so scoping to `docs/` would have excluded the case with
the shortest path to a stale pointer. Dot-directories are skipped, which takes out the agent worktrees
under `.claude/` (whole second checkouts) along with the `create-module` skill, whose markdown carries
no links at all; `data/` and `dist/` are build output.

Three limits worth knowing before reading a failure. A link inside a fenced code block is not a link —
`CONSUMER_TRIAGE_LOOP.md` shows the reply idiom with an elided `#rm45--…` fragment inside a fence — so
fences are blanked first, keeping their newlines so reported line numbers stay true. GitHub
disambiguates repeated headings with a `-1`/`-2` suffix, which `_anchors` does not model; nothing links
to a duplicated heading today, and a failure naming a fragment that ends in a digit is the case to
check by hand before repairing it.

And **a consumer's own words are exempt, because the only repair this guard can ask for there is one
the triage loop forbids.** `CONSUMER_SUGGESTIONS.md` and its history files quote each report
byte-for-byte — the prose is evidence, the reply beneath it is ours — and consumers have started citing
`RMn` items by link, which is exactly the live→history pointer this guard hunts. The two rules collided
head-on: S35's report linked `ROADMAP.md#rm89` while RM89 was open, RM89 shipped, and the pass that
archived the next item silently retargeted the link to keep this test green. That edit moved the
consumer's fingerprint, so the triage ledger reported the section `revised` — our own edit
impersonating a consumer revision, which is the one signal the ledger exists to carry. The link was
also not stale in the sense this guard means: it records where RM89 lived on the day it was written,
and the `**Status —**` reply directly above it carries the current pointer, so a reader is served
without touching the record.

So `_verbatim_lines` exempts everything after a section's `<!-- triaged: … -->` marker, which is where
the reply ends and the quoted report begins, and exempts an unmarked `## Sn` section whole — an
untriaged item is all consumer prose. Our replies stay checked, since they sit above the marker, and
so does every editorial group heading, which sits outside any `## Sn` section. A section that has a
reply but no marker yet is briefly exempt in full; the triage ledger calls that state
`unmarked-reply` and it is meant to be transient.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {"data", "dist", "node_modules"}

# `[text](target)`. It matches a link that wraps across a line because `[^\]]*` and `\s*` both admit a
# newline — no `.` appears in the pattern, so this is not `re.DOTALL` doing the work. Exactly one of
# the nineteen dead links hid from a line-based sweep for that reason (`ROADMAP_HISTORY.md`'s pointer
# at the 1.0 `StudyRow.pmid` entry, whose link text wraps), which is one more than a docs sweep should
# miss; do not narrow those classes.
_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)\s*\)")
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")

# The documents that quote someone else byte-for-byte. Matched by name prefix rather than by path, so
# the guard keeps working when one of them moves out of `docs/` — and, since the history file was split
# at the 0.6 boundary on 2026-08-17, so that the archived half is covered without being named. An
# exact-name set would have left every archived report editable by the next pass that repaired a link,
# which is the failure the exemption exists to prevent and is invisible until the ledger reports the
# section `revised`.
_CONSUMER_PREFIX = "CONSUMER_SUGGESTIONS"
_SECTION = re.compile(r"^## S\d+\b")
_TRIAGE_MARKER = re.compile(r"<!-- *triaged:")


def _files() -> list[Path]:
    # Test the path *relative to the repository root*, never the absolute one: this checkout lives
    # under `/data/`, so filtering on absolute parts skipped every file in the tree and the guard
    # passed by scanning nothing.
    return sorted(
        path
        for path in _ROOT.rglob("*.md")
        if not any(
            part.startswith(".") or part in _SKIP_DIRS
            for part in path.relative_to(_ROOT).parts
        )
    )


def _without_fences(text: str) -> str:
    """Blank fenced blocks, keeping one newline per line so offsets — and line numbers — survive."""
    return _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _anchors(text: str) -> set[str]:
    """GitHub's heading slugs: strip inline markup, lowercase, drop punctuation, spaces to hyphens."""
    out: set[str] = set()
    for line in _without_fences(text).splitlines():
        m = _HEADING.match(line)
        if not m:
            continue
        title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))
        title = title.replace("`", "").replace("*", "").replace("~", "")
        out.add(re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-"))
    return out


def _verbatim_lines(body: str) -> set[int]:
    """1-indexed lines holding a consumer's own words, which this guard may not ask anyone to edit.

    Takes the fence-blanked body so the numbers line up with the ones reported for a link.
    """
    lines = body.splitlines()
    starts = [i for i, line in enumerate(lines) if _SECTION.match(line)]
    out: set[int] = set()
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        marker = next(
            (j for j in range(start, end) if _TRIAGE_MARKER.search(lines[j])), None
        )
        first = start if marker is None else marker + 1
        out.update(range(first + 1, end + 1))
    return out


def test_a_consumers_quoted_prose_is_exempt_and_our_reply_is_not() -> None:
    """The exemption is load-bearing rather than decorative: it tolerates a link that really is dead.

    Computed off the real history file at runtime — no line number is written down here. The case is
    S35, whose report links `ROADMAP.md#rm89` from the days when RM89 was open; RM89 has since moved
    to `ROADMAP_HISTORY.md`, so the anchor genuinely does not resolve and the main guard would report
    it if the line were not a consumer's own words. The second half pins the other side, since an
    exemption that swallowed the replies too would retire the guard over this file entirely.
    """
    path = _ROOT / "docs" / "CONSUMER_SUGGESTIONS_HISTORY.md"
    body = _without_fences(path.read_text())
    exempt = _verbatim_lines(body)

    dead_in_prose: list[str] = []
    live_in_reply = 0
    for match in _LINK.finditer(body):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        filename, _, fragment = target.partition("#")
        resolved = (path.parent / filename).resolve() if filename else path
        if not fragment or not resolved.exists() or resolved.suffix != ".md":
            continue
        line = body.count("\n", 0, match.start()) + 1
        resolves = fragment in _anchors(resolved.read_text())
        if line in exempt and not resolves:
            dead_in_prose.append(target)
        if line not in exempt and resolves:
            live_in_reply += 1

    assert dead_in_prose, (
        "no dead anchor survives inside quoted consumer prose, so this test is no longer "
        "demonstrating what the exemption is for — check whether someone edited a report"
    )
    assert live_in_reply, "the exemption swallowed our own replies; it must not"


def test_every_relative_doc_link_resolves() -> None:
    scanned = _files()
    # A scan of nothing passes every assertion below, which is how the first version of this filter
    # shipped green: it tested the *absolute* path against a `data` exclusion, and this checkout sits
    # under `/data/`. Naming two files the scan must contain — one prose doc, one module README —
    # makes an empty or `docs/`-only sweep a failure rather than a silent pass.
    relative = {path.relative_to(_ROOT).as_posix() for path in scanned}
    assert {"docs/RM_TOC.md", "reference_examples/shox_par1/README.md"} <= relative

    anchors: dict[Path, set[str]] = {}
    findings: list[str] = []

    for path in scanned:
        body = _without_fences(path.read_text())
        exempt = _verbatim_lines(body) if path.name.startswith(_CONSUMER_PREFIX) else set()
        for match in _LINK.finditer(body):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            line = body.count("\n", 0, match.start()) + 1
            if line in exempt:
                continue
            where = f"{path.relative_to(_ROOT)}:{line}"
            filename, _, fragment = target.partition("#")
            resolved = (path.parent / filename).resolve() if filename else path
            if filename and not resolved.exists():
                findings.append(f"{where} -> {target}: no such file")
                continue
            if not fragment or resolved.suffix != ".md":
                continue
            if resolved not in anchors:
                anchors[resolved] = _anchors(resolved.read_text())
            if fragment not in anchors[resolved]:
                findings.append(
                    f"{where} -> {target}: {resolved.name} has no heading with that anchor"
                )

    assert not findings, "dead documentation links:\n" + "\n".join(findings)
