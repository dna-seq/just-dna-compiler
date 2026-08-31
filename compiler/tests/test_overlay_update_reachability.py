"""An overlay `update` on a row the compiler drops used to warn on the second lap only (RM137).

`reverse_module` rebuilds a derived table from the artifact, and **two** of the eight overridable
tables are rebuilt from something narrower than the file the compiler read: `literature.csv` loses its
uncited rows before the parquet (`@uncited-literature-dropped`) and is rebuilt *from* that parquet, and
`resolution.csv` has no parquet at all and is rebuilt from the SNP core, which re-emits only positioned
rows. An `update` naming such a row therefore matched on lap 1 and reported on lap 2, so a module and
its own `compile → reverse → compile` disagreed on `manifest.compilation.warnings` — a published field,
and one RM126 made load-bearing.

**"Count it over the overlay's own rows" is the decision, and reachability is what that means in
code.** Counting the overlay's `update` rows outright is a tautology (`@tautology-zero`); counting the
ones that reached nothing is the lap-dependent original. The stable quantity is a property of the
*target*: could an artifact of this module carry that row at all? That is computable from data which
survives the round trip, so it answers the same on both laps whether or not the row is there to match.

**The other six tables are untouched**, and that is principled rather than a shortcut: they rebuild
whole, so an `update` reaching nothing there is already unmatched on both laps. The predicate is only
defined where the loss is.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    cited_pmids,
    compile_module,
    literature_target_survives,
    reverse_module,
    split_cited_literature,
    validate_spec,
)
from just_dna_format.overrides import LOSSY_OVERLAY_TABLES, OVERRIDABLE_TABLES
from just_dna_format.vocab import ACTIONABLE_WARNING_CODES, VALID_WARNING_CODES

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HEADER = [
    "table", "subject", "member", "field", "operation", "value", "reason", "decided_by",
    "decided_at",
]
_UNREACHABLE = "no artifact of this module can carry"
_SHORT_TABLE = "though this module could carry it"


def _example(tmp_path: Path, name: str = "hboc_palb2") -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / name, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    return spec


def _write_overlay(spec: Path, rows: list[list[str]]) -> None:
    with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        writer.writerows(rows)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _uncited_pmid(spec: Path) -> str:
    """A `literature.csv` PMID no study and no citing table names — the row the compiler drops.

    Appended to the real sidecar rather than invented in a bare fixture, because the drop only happens
    to a row the *table* carries, and merge-not-clobber leaving such a row behind is precisely how one
    arises in the wild.
    """
    rows = _read(spec / "literature.csv")
    assert rows, "the fixture must carry a literature sidecar"
    fields = list(rows[0])
    orphan = {k: "" for k in fields}
    orphan.update({k: v for k, v in rows[0].items() if k in {"source", "status", "dataset"}})
    orphan["pmid"] = "99999999"
    with (spec / "literature.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([*rows, orphan])
    return "99999999"


# ── the ground truth: the fixture really does carry a droppable row ─────────────────────────────


def test_the_row_this_is_about_really_is_dropped_before_the_parquet(tmp_path: Path) -> None:
    """Grounding. Without this the tests below could pass against a row nothing ever drops."""
    spec = _example(tmp_path)
    pmid = _uncited_pmid(spec)
    from just_dna_compiler.compiler import load_csv_rows
    from just_dna_format.literature import LiteratureRow
    from just_dna_format.spec import StudyRow

    rows, errors, _ = load_csv_rows(spec / "literature.csv", LiteratureRow, "literature.csv")
    assert not errors, errors
    studies, errors, _ = load_csv_rows(spec / "studies.csv", StudyRow, "studies.csv")
    assert not errors, errors

    kept, dropped = split_cited_literature(rows, studies, {})

    assert pmid in {r.pmid for r in dropped}
    assert pmid not in {r.pmid for r in kept}


# ── the defect, and the fix, over the real laps ─────────────────────────────────────────────────


def test_an_update_on_a_dropped_row_says_the_same_thing_on_both_laps(tmp_path: Path) -> None:
    """The reproduction, end to end — and the assertion is **equality between laps**, not a count.

    Before RM137 lap 1 warned zero times and lap 2 once. Asserting "lap 2 warns" would have passed on
    the broken code; the property is that the two agree, so it is compared directly.
    """
    spec = _example(tmp_path)
    pmid = _uncited_pmid(spec)
    _write_overlay(
        spec,
        [["literature.csv", pmid, "", "license", "update", "CC-BY-4.0",
          "the publisher page states CC BY, the source recorded none", "curator", "2026-08-31"]],
    )

    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors

    lap1 = [w for w in first.manifest.compilation.warnings if _UNREACHABLE in w]
    lap2 = [w for w in second.manifest.compilation.warnings if _UNREACHABLE in w]

    assert lap1 == lap2, "a module and its own round trip must agree on this published field"
    assert lap1, "and the finding is reported, not merely suppressed into silence"
    assert (
        first.manifest.compilation.warnings_summary.get("overlay_update_target_unreachable")
        == second.manifest.compilation.warnings_summary.get("overlay_update_target_unreachable")
        == 1
    )


def test_the_lap_dependent_warning_no_longer_fires_for_that_row(tmp_path: Path) -> None:
    """The other half: `overlay_update_unmatched` is what used to move, so it must be silent here.

    It is not suppressed — the row is reported by the code above. This asserts the two codes do not
    both fire for one overlay row, which would trade an unstable finding for a doubled one.
    """
    spec = _example(tmp_path)
    pmid = _uncited_pmid(spec)
    _write_overlay(
        spec,
        [["literature.csv", pmid, "", "license", "update", "CC-BY-4.0",
          "the publisher page states CC BY, the source recorded none", "curator", "2026-08-31"]],
    )
    compile_module(spec, tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")

    summary = second.manifest.compilation.warnings_summary
    assert summary.get("overlay_update_unmatched") is None
    assert summary.get("overlay_update_target_unreachable") == 1


def test_a_cited_pmid_the_table_lacks_is_the_other_reading(tmp_path: Path) -> None:
    """The reachable half, and it is **not** "a typo" — that framing was the entry's, and it is wrong.

    A mistyped PMID is also an uncited one, so a mistake lands in the unreachable bucket. What this
    bucket really means is narrower and more useful: the subject *is* cited, so an artifact could carry
    the row, and the sidecar simply does not have it — re-run the enricher.
    """
    spec = _example(tmp_path)
    cited = _read(spec / "studies.csv")[0]["pmid"]
    literature = {r["pmid"] for r in _read(spec / "literature.csv")}
    if cited in literature:
        pytest.skip("this example's literature sidecar already covers its first study")
    _write_overlay(
        spec,
        [["literature.csv", cited, "", "license", "update", "CC-BY-4.0",
          "the publisher page states CC BY, the source recorded none", "curator", "2026-08-31"]],
    )

    result = compile_module(spec, tmp_path / "art")

    assert any(_SHORT_TABLE in w for w in result.warnings)
    assert not any(_UNREACHABLE in w for w in result.warnings)


# ── the predicate's own rules ───────────────────────────────────────────────────────────────────


def test_the_predicate_mirrors_the_drops_empty_cited_guard() -> None:
    """`split_cited_literature` discards NOTHING when the module cites nothing, and so must this.

    Without the mirror, a module with no citations would mark every literature correction unreachable —
    a **stable false positive** on every healthy overlay row, which is worse than the unstable true one
    this item is about.
    """
    survives = literature_target_survives([], {})

    assert survives("12345678") is True
    assert survives("anything at all") is True


def test_the_predicate_and_the_drop_read_one_shared_set(tmp_path: Path) -> None:
    """They must not be two statements of one rule — the drift would be silent and self-inflicted.

    Computed from the real fixture rather than asserted as a constant: for every PMID the sidecar
    carries, *kept by the drop* and *survives by the predicate* have to be the same answer.
    """
    spec = _example(tmp_path)
    _uncited_pmid(spec)
    from just_dna_compiler.compiler import load_csv_rows
    from just_dna_format.literature import LiteratureRow
    from just_dna_format.spec import StudyRow

    rows, _, _ = load_csv_rows(spec / "literature.csv", LiteratureRow, "literature.csv")
    studies, _, _ = load_csv_rows(spec / "studies.csv", StudyRow, "studies.csv")
    kept, _ = split_cited_literature(rows, studies, {})
    survives = literature_target_survives(studies, {})

    assert cited_pmids(studies, {}), "the fixture cites something, or the guard above applies instead"
    assert {r.pmid for r in kept} == {r.pmid for r in rows if survives(r.pmid)}


# ── scope, and the registry obligations ─────────────────────────────────────────────────────────


def test_only_the_two_lossy_tables_are_in_scope() -> None:
    """The other six rebuild whole on a reverse, so their unmatched warning is already lap-stable.

    Asserted as an equality over the walked registry rather than by naming two strings, so a table
    added to `OVERRIDABLE_TABLES` has to face the question deliberately (`@registry-completeness`).
    """
    assert LOSSY_OVERLAY_TABLES == {"literature.csv", "resolution.csv"}
    assert LOSSY_OVERLAY_TABLES <= set(OVERRIDABLE_TABLES)


def test_the_new_code_is_published_and_actionable() -> None:
    """Actionable, not carried: the author can fix the subject, cite the PMID, or drop the overlay row.

    Carried membership is a claim about *remediation* — a limit of this tier or a fact of a source —
    and this is neither. It is a fact about the module's own shape.
    """
    assert "overlay_update_target_unreachable" in VALID_WARNING_CODES
    assert "overlay_update_target_unreachable" in ACTIONABLE_WARNING_CODES


def test_the_pre_flight_reports_what_the_compile_reports(tmp_path: Path) -> None:
    """`@parity-by-check`. The split happens late in both functions, from the same inputs."""
    spec = _example(tmp_path)
    pmid = _uncited_pmid(spec)
    _write_overlay(
        spec,
        [["literature.csv", pmid, "", "license", "update", "CC-BY-4.0",
          "the publisher page states CC BY, the source recorded none", "curator", "2026-08-31"]],
    )

    checked = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "art")

    from_validate = [w for w in checked.warnings if _UNREACHABLE in w]
    assert from_validate, checked.warnings
    assert from_validate[0] in compiled.manifest.compilation.warnings
    # And reported once, though two passes computed it — the message dedup.
    assert len([w for w in compiled.manifest.compilation.warnings if _UNREACHABLE in w]) == 1


def test_a_module_with_no_overlay_reports_nothing(tmp_path: Path) -> None:
    """A check that cannot fail must not report (`@tautology-zero`), and neither may this one."""
    result = compile_module(_example(tmp_path), tmp_path / "art")

    assert result.success, result.errors
    assert not any(_UNREACHABLE in w or _SHORT_TABLE in w for w in result.warnings)
