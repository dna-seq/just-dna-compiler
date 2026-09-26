"""A closed roadmap entry states what it did not fix, and every such remainder has a home that carries it.

**Why this is a test.** RM31 shipped in 0.5 with a paragraph headed *"The residual"*: a consumer joining
an indel genotype against a VCF *"will still miss"*. The paragraph pointed at a parked idea-book bullet
that never mentioned it, and offered consumers a workaround no consumer document ever carried. The
defect then went unowned for three minors and came back as S117, S120 and S121 on 2026-09-27. The sweep
that followed (docs/POSTMORTEM_2026_09_27.md § 4) found the same shape in about one closure in seven:
*"it wants its own item"*, *"filed rather than improvised"* with nothing filed, *"belongs to RMn"* where
RMn was closed and never said so. Every one of those sentences was true when written, and none of
them could fail a build. This module is what makes them able to.

**The rule (M1).** Every `## RMn` entry in `ROADMAP_HISTORY.md` carries one `**Residuals**` paragraph:

- `**Residuals** none`, or
- items separated by ` · `, each either an `RMn` or `won't fix — <reason>`.

An `RMn` item is homed only if **that item's own entry mentions the source** — the source's `RMn`, or
the `Sn` named in the source's `**Motivating case**`. Being open is not the test: RM27 and RM50 were
both pointed at as homes, and both were closed without carrying what pointed at them. Carrying is what
failed, so carrying is what is checked. An unnumbered idea-book bullet is not an `RMn` and cannot be a
home. A `won't fix` needs a reason of at least five words; it is reviewed prose beyond that, and this
module does not pretend to judge it (decided 2026-09-27, recorded in RELEASE_CYCLE.md).

**Legacy entries** (closed before the rule) are listed in `data/residuals_legacy.txt`, and the list is
asserted **exact**: an entry that gains its line must leave the list in the same commit, so the file can
only shrink. `@registry-completeness`: an equality over a walked set, never a floor.

Walks the repository and imports nothing from any package, like `test_doc_links.py`.
"""

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"
_HISTORY = _DOCS / "ROADMAP_HISTORY.md"
_LEGACY = Path(__file__).parent / "data" / "residuals_legacy.txt"

#: Every file that holds an authoritative `RMn` entry, open or closed. An item may have more than one
#: section (an open half and a shipped half); a target is read as the union of its sections.
_ENTRY_FILES = (
    "ROADMAP.md",
    "ROADMAP_0_8.md",
    "ROADMAP_1_0.md",
    "ROADMAP_HISTORY.md",
    "history/ROADMAP_HISTORY_0_6.md",
    "history/ROADMAP_HISTORY_PRE_0_6.md",
    "history/ROADMAP_0_7.md",
)

#: Closures owed a line by another seat, each with who owes it. Not the legacy list: these closed
#: after the rule existed, so they xfail loudly until the line lands and then fail until removed here.
_PENDING: dict[str, str] = {}

_HEADING = re.compile(r"^(#{2,3}) (RM\d+)\b", re.MULTILINE)
_ANY_HEADING = re.compile(r"^#{1,3} ", re.MULTILINE)
_RESIDUALS = re.compile(r"^\*\*Residuals\*\* (.*)$", re.MULTILINE)
_RM = re.compile(r"\bRM\d+\b")
_SN = re.compile(r"\bS\d+\b")
_WONT_FIX = re.compile(r"^won['’]t fix — (.+)$")
_MIN_REASON_WORDS = 5


def _sections(path: Path) -> list[tuple[str, str]]:
    """`(RMn, body)` for every `##`/`###` RM heading in `path`, the body running to the next heading."""
    text = path.read_text(encoding="utf-8")
    starts = [m.start() for m in _ANY_HEADING.finditer(text)] + [len(text)]
    out = []
    for m in _HEADING.finditer(text):
        end = next(s for s in starts if s > m.start())
        out.append((m.group(2), text[m.start() : end]))
    return out


def _entries() -> dict[str, str]:
    """Every RM's authoritative text across all entry files, sections of one RM joined."""
    joined: dict[str, list[str]] = {}
    for name in _ENTRY_FILES:
        for rm, body in _sections(_DOCS / name):
            joined.setdefault(rm, []).append(body)
    return {rm: "\n".join(bodies) for rm, bodies in joined.items()}


def _history() -> dict[str, str]:
    out: dict[str, str] = {}
    for rm, body in _sections(_HISTORY):
        out[rm] = out.get(rm, "") + body
    return out


def _residuals_paragraph(body: str) -> str | None:
    """The `**Residuals**` paragraph: its first line plus continuation lines up to a blank line."""
    m = _RESIDUALS.search(body)
    if m is None:
        return None
    rest = body[m.end() :].split("\n\n", 1)[0]
    return (m.group(1) + rest).replace("\n", " ").strip()


def _motivating_sns(body: str) -> set[str]:
    line = next((ln for ln in body.splitlines() if "**Motivating case**" in ln), "")
    # The case often wraps onto the next line; take the paragraph it starts.
    start = body.find(line)
    para = body[start:].split("\n\n", 1)[0] if line else ""
    return set(_SN.findall(para))


def _legacy() -> set[str]:
    return {ln.strip() for ln in _LEGACY.read_text(encoding="utf-8").splitlines() if ln.strip()}


def _item_problems(source: str, body: str, entries: dict[str, str]) -> list[str]:
    paragraph = _residuals_paragraph(body)
    assert paragraph is not None
    if paragraph == "none":
        return []
    problems = []
    tokens = {source} | _motivating_sns(body)
    for item in (part.strip() for part in paragraph.split(" · ")):
        wont = _WONT_FIX.match(item)
        if wont:
            if len(wont.group(1).split()) < _MIN_REASON_WORDS:
                problems.append(
                    f"{source}: `won't fix` needs a reason of {_MIN_REASON_WORDS}+ words: {item!r}"
                )
            continue
        targets = [rm for rm in _RM.findall(item) if rm != source]
        if not targets:
            problems.append(f"{source}: residual has no home (no RMn, not `won't fix — …`): {item!r}")
            continue
        for target in targets:
            text = entries.get(target)
            if text is None:
                problems.append(
                    f"{source}: residual points at {target}, which has no entry in any roadmap file"
                )
            elif not any(re.search(rf"\b{t}\b", text) for t in tokens):
                problems.append(
                    f"{source}: residual points at {target}, whose entry never mentions "
                    f"{' or '.join(sorted(tokens))} — a pointer that does not carry it"
                )
    return problems


def test_every_closure_states_its_residuals() -> None:
    missing = (
        {rm for rm, body in _history().items() if _residuals_paragraph(body) is None}
        - _legacy()
        - set(_PENDING)
    )
    assert not missing, (
        f"closed entries with no `**Residuals**` paragraph: {sorted(missing, key=lambda r: int(r[2:]))}. "
        "Add `**Residuals** none`, or name each remainder as an RMn whose entry mentions this one, "
        "or `won't fix — <reason>` (RELEASE_CYCLE.md § closing an item)."
    )


def test_legacy_list_is_exact() -> None:
    history = _history()
    lacking = {rm for rm, body in history.items() if _residuals_paragraph(body) is None}
    legacy = _legacy()
    stale = legacy - lacking
    assert not stale, (
        f"{sorted(stale)} are in {_LEGACY.name} but either carry a Residuals line now or are not in "
        "ROADMAP_HISTORY.md at all — remove them from the list (it only shrinks)"
    )
    lines = [ln.strip() for ln in _LEGACY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines == sorted(lines, key=lambda r: int(r[2:])), f"{_LEGACY.name} must stay sorted by number"


def test_every_residual_is_homed() -> None:
    entries = _entries()
    problems = []
    for rm, body in _history().items():
        if _residuals_paragraph(body) is not None:
            problems.extend(_item_problems(rm, body, entries))
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("rm", sorted(_PENDING))
def test_pending_line(rm: str) -> None:
    body = _history().get(rm)
    assert body is not None, f"{rm} is in _PENDING but not in ROADMAP_HISTORY.md — remove it"
    if _residuals_paragraph(body) is None:
        pytest.xfail(_PENDING[rm])
    pytest.fail(f"{rm} now carries its Residuals line — remove it from _PENDING")
