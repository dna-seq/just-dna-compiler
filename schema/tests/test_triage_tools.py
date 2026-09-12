"""The triage tools agree about where a section ends, and refuse when they cannot.

**Why this is a test and not a note in the runbook.** `.claude/triage-state.py` and
`.claude/triage-archive.py` decide the boundaries of somebody else's prose, and both had their own
copy of the boundary scan. A `#` written at column 1 inside a fenced code block — the natural way to
label a snippet — matched `^#{1,2} ` and ended the section there. Two consequences, both silent:

* the ledger hashed a truncated body, so a fingerprint stopped covering the tail of a report;
* the archiver **cut** at the same line, so a move took half a section and left the rest behind.

The second happened twice in this repository before anyone noticed. `cf4c3bd` split S55 and stranded
76 lines in the inbox, which a later pass swept back under S54 as though the flush-left comment were a
group heading; `e205e4c` split S62 across both documents, where it sat through a release. The
archiver's own verification reported both clean, and it was right to: a fingerprint covers the
consumer's prose, and a truncated span hashes identically either side of the cut. So the property
under test is one nothing else in the loop can observe.

The historical cases are reproduced from their real shapes rather than described, because the runbook
asks for exactly that and because a guard nobody has watched fail is a guess.
"""

import importlib.util
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), CLAUDE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ledger():
    return _load("triage-state")


# The shape that split S62: a python comment at column 1 inside the report's fenced block.
S62_SHAPE = """\
# Consumer suggestions

Preamble.

---

## S62 — a patch changed a published field, and nothing a consumer can read said so

**Status — accepted.** Reply.
<!-- triaged: 0.6.6 · sha 000000000000 -->

Sketch, and the field names matter less than the axes:

```python
from just_dna_compiler import rebuild_hints
rebuild_hints(compiled_under="0.6.1", current="0.6.6")
# RebuildHints(
#     parquet_schema=False,
# )
```

Three properties we would need, in descending order of how much they matter to us:

**Reproduced against** `just-dna-compiler` 0.6.6 installed.
"""


def test_a_flush_left_comment_inside_a_fence_does_not_end_a_section(ledger):
    """The defect itself, on S62's real shape: the span must reach the last line of the report."""
    lines = S62_SHAPE.splitlines()
    ((ident, _, body),) = ledger.sections(lines)
    assert ident == "S62"
    assert body[-1].startswith("**Reproduced against**"), (
        "the span stopped early — everything after it would be left behind by an archive"
    )
    assert any("RebuildHints" in line for line in body)


def test_the_old_boundary_scan_really_did_split_that_shape(ledger):
    """The buggy behaviour, demonstrated rather than asserted about.

    Without this the guard is a claim. `BOUNDARY_RE` is still the ledger's own regex, so this walks
    the exact scan both tools used to run and shows it stopping inside the fence.
    """
    lines = S62_SHAPE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## S62"))
    naive_end = next(
        (j for j in range(start + 1, len(lines)) if ledger.BOUNDARY_RE.match(lines[j])), len(lines)
    )
    assert lines[naive_end].startswith("# RebuildHints("), "expected the scan to stop at the comment"

    fence_aware_end = ledger.boundary_after(lines, start)
    assert fence_aware_end == len(lines)
    lost = lines[naive_end:fence_aware_end]
    assert any(line.startswith("**Reproduced against**") for line in lost), (
        "these are the lines an archive would have stranded in the inbox"
    )


def test_a_heading_swallowed_by_a_fence_is_reported_not_silently_dropped(ledger):
    """S55's symptom: an unmatched closer hid a whole section from the roster."""
    lines = S62_SHAPE.splitlines() + ["", "```", "## S99 — swallowed", "", "Body.", "```"]
    assert [i for i, _, _ in ledger.sections(lines)] == ["S62"], "S99 is invisible, as expected"
    findings = ledger.fence_findings(lines)
    assert any("S99" in f and "inside a fenced block" in f for f in findings), findings


def test_an_unclosed_fence_is_reported(ledger):
    findings = ledger.fence_findings(["# Doc", "", "```python", "x = 1"])
    assert len(findings) == 1
    assert "never closed" in findings[0]


def test_a_sound_document_reports_nothing(ledger):
    assert ledger.fence_findings(S62_SHAPE.splitlines()) == []


@pytest.mark.parametrize(
    "doc",
    [
        "docs/CONSUMER_SUGGESTIONS.md",
        "docs/CONSUMER_SUGGESTIONS_HISTORY.md",
        "docs/history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md",
    ],
)
def test_the_real_documents_are_structurally_sound(ledger, doc):
    """The repair of S55 and S62 stays repaired, and a new report cannot reintroduce the shape."""
    findings = ledger.fence_findings((ROOT / doc).read_text().splitlines())
    assert findings == [], f"{doc}: " + "; ".join(findings)


def test_every_archived_section_is_marked_and_matches(ledger):
    """The §1 lint, as a test: a well-formed archived section reads `current`.

    This is what catches a mis-archive, and it is the check that would have caught S55 vanishing.
    """
    for doc in (
        "docs/CONSUMER_SUGGESTIONS_HISTORY.md",
        "docs/history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md",
    ):
        out = subprocess.run(
            [sys.executable, str(CLAUDE / "triage-state.py"), str(ROOT / doc)],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        ).stdout
        bad = [line for line in out.splitlines() if line and not line.startswith("current")]
        assert not bad, f"{doc}:\n" + "\n".join(bad)


def test_both_tools_derive_the_same_span():
    """The archiver must not carry its own copy of the boundary scan — that is how they drifted."""
    archive = _load("triage-archive")
    ledger = _load("triage-state")
    lines = S62_SHAPE.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## S62"))
    # Behavioural agreement, not object identity: the archiver loads its own instance of the ledger
    # module, so the functions are equal in source and distinct as objects.
    assert archive.boundary_after(lines, start) == ledger.boundary_after(lines, start)
    assert archive.section_span(lines, "S62") == (start, ledger.boundary_after(lines, start))
    source = (CLAUDE / "triage-archive.py").read_text()
    assert "BOUNDARY_RE = re.compile" not in source, (
        "the archiver has re-declared the boundary regex; it must import the ledger's"
    )


def test_the_archiver_refuses_a_document_whose_fences_are_broken(tmp_path):
    """Refuse before writing, because the move's own verification cannot see this."""
    docs = tmp_path / "docs"
    docs.mkdir()
    live = docs / "CONSUMER_SUGGESTIONS.md"
    live.write_text(S62_SHAPE + "\n```\n## S98 — swallowed\n\nBody.\n")
    (docs / "CONSUMER_SUGGESTIONS_HISTORY.md").write_text("# History\n")
    claude = tmp_path / ".claude"
    claude.mkdir()
    for tool in ("triage-state.py", "triage-archive.py"):
        (claude / tool).write_bytes((CLAUDE / tool).read_bytes())

    result = subprocess.run(
        [sys.executable, str(claude / "triage-archive.py"), "S62"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "refusing to archive" in result.stderr
    assert live.read_text().count("## S62") == 1, "the live file must be untouched"


# --- §4's counter reads a fixed field, and this is what makes it a field ------------------------
#
# `CONSUMER_TRIAGE_LOOP.md` § 4 decides when to ask whether the next minor should start by grepping
# `docs/ROADMAP.md` for a release-class token. That counter has now gone blind three times, always in
# the same direction — it reads zero while grounded items sit in the file, and a zero reads as an
# all-clear. First it counted a literal version number that then shipped; then the 2026-08-21 decision
# round rewrote four status lines and pushed the token out of the slot; then RM235 was filed on
# 2026-09-12 with no token at all and the count read 0/0 against a high-severity open item.
#
# Twice the repair was to re-word the rule, which is the repair `@registry-completeness` names as the
# wrong one: a rule stated in prose is only as good as the next person reading it, and the person
# editing a status line is reading `ROADMAP.md`, not the runbook. So the equality is asserted here
# instead — every open item is one the counter can see — and the counter can no longer report its own
# blindness as silence.

#: The token as the §4 greps spell it, split so this line is not itself counted by them.
_CLASS_RE = re.compile(r"\*\*Status\*\* open " + "— " + r"\*\*a (minor|patch)\b[^*\n]*\*\*")
_OPEN_REGION = ("# Active items", "# Not format scope")


def _active_items() -> dict[str, str]:
    """Every `## RMn` section in ROADMAP's open region, as {id: section text}."""
    lines = (ROOT / "docs" / "ROADMAP.md").read_text().splitlines()
    start = lines.index(_OPEN_REGION[0])
    end = lines.index(_OPEN_REGION[1], start)
    heads = [i for i in range(start, end) if re.match(r"^## RM\d+\b", lines[i])]
    if not heads:
        return {}
    spans = list(zip(heads, heads[1:] + [end], strict=True))
    return {lines[a].split()[1]: "\n".join(lines[a:b]) for a, b in spans}


@pytest.fixture
def open_items() -> dict[str, str]:
    """The walked set, with the empty case named rather than asserted away.

    An empty open region is a *good* state and has happened — the 2026-08-21 decision round answered
    all six items standing here in one pass — so a guard that goes red on it would fire on success and
    could only be made green by deleting it. The two assertions below are vacuously true over an empty
    set and correctly so (an empty set has no member the counter cannot see); what a skip preserves is
    the one thing the vacuous pass cannot say, which is that the region headings still resolve. If
    `ROADMAP.md`'s structure moves, `_OPEN_REGION` moves with it and `_active_items` raises here rather
    than quietly walking nothing.
    """
    items = _active_items()
    if not items:
        pytest.skip("no open `## RMn` items in ROADMAP.md to walk — nothing for §4 to count")
    return items


def test_every_open_item_carries_the_release_class_token(open_items):
    """`@registry-completeness`: equality over the walked set, never the counter's own number."""
    items = open_items
    walked = set(items)
    seen = {item for item, text in items.items() if _CLASS_RE.search(text)}
    assert walked == seen, (
        "invisible to §4's counter: "
        + ", ".join(sorted(walked - seen))
        + " — an open item's status reads `**Status** open` then an em dash then, in bold and on the "
        "same line, `a minor, release undecided` or `a patch, …`"
    )


def test_the_counter_the_runbook_publishes_agrees_with_the_walk(open_items):
    """The greps §4 actually runs, run here — a rule and its instrument must not drift apart."""
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text()
    counted = sum(roadmap.count("**Status** open " + "— " + f"**a {klass}") for klass in ("minor", "patch"))
    expected = len(open_items)
    assert counted == expected, (
        f"§4 would count {counted} against {expected} open items; either an item is invisible "
        "to it or prose elsewhere in the file is being counted as one"
    )
