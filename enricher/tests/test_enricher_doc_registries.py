"""`ENRICHER.md`'s three registries are walked against the code, because nothing walked them before.

**This tier's reference was the only one no test read.** `test_counted_prose.py` reads `SCHEMAS.md`
and `COMPILER.md`, `test_warning_codes.py` reads `COMPILER.md`'s warning catalogue, `test_doc_links.py`
walks every markdown file's links, and `test_module_map.py` walks `SCHEMAS.md`'s module map. The
fastest-moving package in the workspace had none of that, and it showed: twenty-six modules had no row
in the module map, `clinvar_build` had two, `locations` claimed "all **seven** snapshots" against
fifteen `CACHE_LANES`, and the check table was missing `variant_impact_agreement` — a vocabulary
member `vocab.py`'s own comment says was audited *against that table*.

That last one is the reason this file exists rather than a re-count. A reader of a module's
`verification.json` sees `variant_impact_agreement` and comes here to learn what put it; for a release
there was no row to find. Nothing walks prose, so prose is what goes stale
(`@registry-completeness`).

**Two assertion shapes, and the difference is load-bearing.**

The module map is an **equality**: one row per module, both directions entailed. A module with no row
is unreachable from the map, and a row naming no module sends a reader to a file that is not there.
Lengths are compared too, because a duplicated row is two claims about one file and a set comparison
reads it as fine — which is exactly how the second `clinvar_build` row survived.

The check table only gets **containment**, and forcing equality there would be the
`@a-record-written-in-two-passes-drifts-between-them` mistake — asserting equality where only one
direction is entailed makes the test demand false claims. Real rows attest nothing: `Declared use` is
an acquisition gate, `Source coverage` and `Article licence` are recording passes, `Drafted vs
authored rows` runs outside `enrich()` entirely. So the invariant is: every emitting member of
`VALID_VERIFICATION_CHECKS` appears in the fourth column, every `code`-shaped entry in that column is
a member, and the two members the vocabulary marks RESERVED appear nowhere — parsed from `vocab.py`'s
own comments rather than restated here, so retiring a reservation moves one thing.

The licence roster is an **equality** again, for the reason the table states about itself: it says it
is *every* key in `TERMS_BY_SOURCE`, so a row naming something the registry does not hold promises
terms no `SourceRow` can ever carry. It is deliberately not the PGx picture above it, which is scoped
to the PGx sources and dated to its probe.
"""

import re
from pathlib import Path

import just_dna_enricher
from just_dna_enricher import licensing
from just_dna_format import vocab

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent
_VOCAB = Path(vocab.__file__).resolve()
_DOC = Path(__file__).resolve().parents[2] / "docs" / "ENRICHER.md"


def _doc() -> str:
    return _DOC.read_text(encoding="utf-8")


def _mapped_modules() -> list[str]:
    """The first cell of every module-map row, in document order, duplicates kept."""
    section = _doc().split("## Module map")[1].split("\n## ")[0]
    return re.findall(r"^\| `(\w+)` \|", section, re.MULTILINE)


def _package_modules() -> set[str]:
    """Top-level modules only. Subpackages are excluded by the glob, so adding one is a decision."""
    return {p.stem for p in _PACKAGE.glob("*.py")} - {"__init__"}


def _attested_in_the_check_table() -> set[str]:
    """The vocabulary members named in the check table's `Attests as` column."""
    header = "| Check | Compares | Where | Attests as |"
    doc = _doc()
    assert header in doc, f"the check table's header moved or lost a column; looked for {header!r}"
    section = doc.split(header)[1].split("\n\n")[0]
    rows = [line for line in section.split("\n") if line.startswith("| **")]
    assert rows, "the check table lost its rows, or its header moved"
    named: set[str] = set()
    for row in rows:
        cell = row.rstrip().rstrip("|").rsplit("|", 1)[1].strip()
        named |= set(re.findall(r"`(\w+)`", cell.split("*(")[0]))
    return named


def _reserved_members() -> set[str]:
    """Members `vocab.py` marks RESERVED — read from the source, never restated here."""
    lines = _VOCAB.read_text(encoding="utf-8").split("\n")
    return {m.group(1) for line in lines if (m := re.match(r'\s+"(\w+)",\s+# RESERVED', line))}


def test_the_module_map_names_every_module_and_only_modules() -> None:
    listed = set(_mapped_modules())
    present = _package_modules()
    assert listed == present, f"module map drifted: {listed ^ present}"


def test_no_module_is_mapped_twice() -> None:
    rows = _mapped_modules()
    assert len(rows) == len(set(rows)), f"duplicated rows: {sorted({r for r in rows if rows.count(r) > 1})}"


def test_the_vocabulary_marks_exactly_the_two_members_the_doc_calls_reserved() -> None:
    """The parse is load-bearing for the test below, so it is pinned rather than assumed."""
    assert _reserved_members() == {"gene_disease_validity", "dosage_sensitivity"}


def test_every_emitting_check_has_a_row_in_the_table() -> None:
    """`vocab.py` says the set was audited against this table. Make that sentence stay true."""
    expected = set(vocab.VALID_VERIFICATION_CHECKS) - _reserved_members()
    missing = expected - _attested_in_the_check_table()
    assert not missing, f"checks a reader of verification.json cannot look up: {sorted(missing)}"


def test_the_column_names_no_check_that_is_not_a_member() -> None:
    """The other direction of the same join: a row may attest nothing, never something invented."""
    strays = _attested_in_the_check_table() - set(vocab.VALID_VERIFICATION_CHECKS)
    assert not strays, f"not members of VALID_VERIFICATION_CHECKS: {sorted(strays)}"


def test_a_reserved_member_is_claimed_by_no_row() -> None:
    """A reservation exists because no pass puts the check; a row here would report one that did."""
    claimed = _reserved_members() & _attested_in_the_check_table()
    assert not claimed, f"reserved members shown as attested: {sorted(claimed)}"


def _licence_roster() -> set[str]:
    """The source names in `ENRICHER.md`'s complete-roster table."""
    header = "### The complete roster — `TERMS_BY_SOURCE`, every source this tier has terms for"
    doc = _doc()
    assert header in doc, f"the licence roster's heading moved; looked for {header!r}"
    section = doc.split(header)[1].split("\n### ")[0]
    return set(re.findall(r"^\| `(\w+)` \|", section, re.MULTILINE))


def test_the_licence_roster_names_every_source_with_recorded_terms() -> None:
    """A source whose terms are recorded and unlisted is one a reader cannot check before drafting.

    Equality, not containment: the roster's own sentence says it is *every* key in
    `TERMS_BY_SOURCE`, so a row naming something the registry does not hold is as wrong as a missing
    one — it would promise terms no `SourceRow` can ever carry. This is the table the PGx picture
    above it is deliberately *not*: that one is scoped to the PGx sources and dated to its probe.
    """
    listed = _licence_roster()
    recorded = set(licensing.TERMS_BY_SOURCE)
    assert listed == recorded, f"licence roster drifted: {listed ^ recorded}"
