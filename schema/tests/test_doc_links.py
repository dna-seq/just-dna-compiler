"""Every relative link between the prose docs resolves — the file, and the heading it names.

**Why this is a test and not a script.** `uv run pytest` is the only thing CI runs, so a check that
lives anywhere else runs when somebody remembers it, which is exactly the property that let the
defect accumulate: nineteen `FILE.md#anchor` links pointing at headings that no longer existed, almost
all of them `ROADMAP.md#rm4x-…` pointers to items that had since moved to `ROADMAP_HISTORY.md`
(R2-12 in `docs/DOGFOOD_0_6_FINDINGS.md`). The mechanism is structural rather than careless — this
repo deliberately splits live from historical (ROADMAP/ROADMAP_HISTORY, CONSUMER_SUGGESTIONS and its
history file), so *an item moving between the two* breaks every pointer at it, and the move is the
routine event. `RM_TOC.md` exists because RM33 became unfindable; this is the same failure one
document over.

It sits in `schema/tests/` beside `test_printed_contract.py`, which is the nearest precedent: a guard
over a surface a reader consumes rather than over a tier's behaviour. It imports nothing from any
package and walks the repository the way `compiler/tests/test_build_call_sites.py` does.

Scope is the prose docs — `docs/*.md` plus the three at the root. Reference-example READMEs and the
`create-module` skill carry no cross-document links (the skill is barred from naming any path outside
its own directory), so there is nothing there for this to check.

Two limits worth knowing before reading a failure. A link inside a fenced code block is not a link —
`CONSUMER_TRIAGE_LOOP.md` shows the reply idiom with an elided `#rm45--…` fragment inside a fence —
so fences are stripped first. And GitHub disambiguates repeated headings with a `-1`/`-2` suffix,
which `_anchors` does not model; nothing links to a duplicated heading today, and a failure naming a
fragment that ends in a digit is the case to check by hand before repairing it.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"

# `[text](target)` — `re.S` because a link may wrap across a line, which is how five of the nineteen
# hid from the first (line-based) sweep.
_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)\s*\)", re.S)
_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")


def _files() -> list[Path]:
    return sorted(_DOCS.glob("*.md")) + [
        _ROOT / name for name in ("CLAUDE.md", "AGENTS.md", "README.md")
    ]


def _anchors(text: str) -> set[str]:
    """GitHub's heading slugs: strip inline markup, lowercase, drop punctuation, spaces to hyphens."""
    out: set[str] = set()
    for line in _FENCE.sub("", text).splitlines():
        m = _HEADING.match(line)
        if not m:
            continue
        title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))
        title = title.replace("`", "").replace("*", "").replace("~", "")
        out.add(re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-"))
    return out


def test_every_relative_doc_link_resolves() -> None:
    anchors: dict[Path, set[str]] = {}
    findings: list[str] = []

    for path in _files():
        body = _FENCE.sub("", path.read_text())
        for match in _LINK.finditer(body):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            line = body.count("\n", 0, match.start()) + 1
            where = f"{path.relative_to(_ROOT)}:~{line}"
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
