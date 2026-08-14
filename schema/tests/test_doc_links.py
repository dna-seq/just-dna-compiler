"""Every relative link between the repository's markdown files resolves — the file, and the heading.

**Why this is a test and not a script.** `uv run pytest` is the only thing CI runs, so a check that
lives anywhere else runs when somebody remembers it, which is exactly the property that let the defect
accumulate: nineteen `FILE.md#anchor` links pointing at headings that no longer existed, almost all of
them `ROADMAP.md#rm4x-…` pointers to items that had since moved to `ROADMAP_HISTORY.md` (R2-12 in
`docs/DOGFOOD_0_6_FINDINGS.md`). The mechanism is structural rather than careless — this repo
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

Two limits worth knowing before reading a failure. A link inside a fenced code block is not a link —
`CONSUMER_TRIAGE_LOOP.md` shows the reply idiom with an elided `#rm45--…` fragment inside a fence — so
fences are blanked first, keeping their newlines so reported line numbers stay true. And GitHub
disambiguates repeated headings with a `-1`/`-2` suffix, which `_anchors` does not model; nothing links
to a duplicated heading today, and a failure naming a fragment that ends in a digit is the case to
check by hand before repairing it.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {"data", "dist", "node_modules"}

# `[text](target)`. It matches a link that wraps across a line because `[^\]]*` and `\s*` both admit a
# newline — no `.` appears in the pattern, so this is not `re.DOTALL` doing the work. Five of the
# nineteen dead links hid from a line-based sweep for exactly that reason; do not narrow those classes.
_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)\s*\)")
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")


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
        for match in _LINK.finditer(body):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            line = body.count("\n", 0, match.start()) + 1
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
