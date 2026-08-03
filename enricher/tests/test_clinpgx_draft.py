"""ClinPGx → pharm_variants.csv (0.5, RM26) — the second drafting provider.

Built against the **real snapshot** when one is present, so the expectations are computed from the
data rather than read off a dump. What is pinned: the five-part key (so a re-run adds nothing), one
row per drug in a `;`-joined annotation, the `CC` → `C/C` re-spelling, and that everything the
grammar cannot hold is skipped with a warning rather than coerced.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import _load_csv_rows, validate_spec
from just_dna_compiler.draft import natural_key
from just_dna_enricher.clinpgx_draft import (
    _authored_genotype,
    _meets_level,
    _rows_from_snapshot,
    _split_drugs,
    draft_pharm_variants,
)
from just_dna_format.pgx import PharmVariantRow

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "interim" / "clinpgx"
_needs_snapshot = pytest.mark.skipif(
    not (_SNAPSHOT / "data" / "annotations.parquet").is_file(),
    reason="no local ClinPGx snapshot (build it with `just-dna-enricher clinpgx build`)",
)

_RECORDS = [
    {"annotation_id": "1", "rsid": "rs6265", "genotype": "CC", "evidence_level": "3",
     "phenotype_category": "Efficacy", "drugs": "citalopram;paroxetine"},
    {"annotation_id": "2", "rsid": "rs1", "genotype": "*1", "evidence_level": "1A",
     "phenotype_category": "Toxicity", "drugs": "codeine"},
    {"annotation_id": "3", "rsid": "rs2", "genotype": "del/del", "evidence_level": "4",
     "phenotype_category": "Efficacy", "drugs": "warfarin"},
    {"annotation_id": "4", "rsid": "", "genotype": "AG", "evidence_level": "1A",
     "phenotype_category": "Efficacy", "drugs": "warfarin"},
]


def test_a_concatenated_genotype_becomes_the_authored_form() -> None:
    assert _authored_genotype("CC") == "C/C"
    assert _authored_genotype("TC") == "C/T"  # unphased calls are alphabetical
    # anything that is not two unambiguous bases is declined, never guessed
    assert _authored_genotype("*1") is None
    assert _authored_genotype("del/del") is None
    assert _authored_genotype("CAT") is None


def test_one_annotation_naming_several_drugs_becomes_one_row_each() -> None:
    rows, _ = _rows_from_snapshot(_RECORDS[:1], genes=(), drugs=(), min_evidence_level=None)
    assert [r.drug for r in rows] == ["citalopram", "paroxetine"]
    # they share the annotation, and still key distinctly — the drug is part of the key
    assert len({natural_key(r) for r in rows}) == 2
    assert {r.annotation_id for r in rows} == {"1"}


def test_what_the_grammar_cannot_hold_is_skipped_with_a_reason() -> None:
    rows, warnings = _rows_from_snapshot(_RECORDS, genes=(), drugs=(), min_evidence_level=None)
    assert {r.rsid for r in rows} == {"rs6265"}
    joined = " ".join(warnings)
    assert "diplotypes.csv" in joined      # the star allele is routed, not dropped silently
    assert "RM5" in joined                 # the symbolic allele is a known gap
    assert "no rsID" in joined


def test_the_evidence_floor_keeps_unknown_levels() -> None:
    """An unknown level is kept: dropping it would silently hide an annotation we cannot rank."""
    assert _meets_level("1A", "3") and _meets_level("3", "3")
    assert not _meets_level("4", "3")
    assert _meets_level(None, "1A") and _meets_level("weird", "1A")


def test_split_drugs_keeps_first_occurrence_order() -> None:
    """Emitted order is digest-visible, so it must be stable and not set-derived."""
    assert _split_drugs("b;a;b;c") == ["b", "a", "c"]
    assert _split_drugs(None) == []


def test_a_commercial_declaration_refuses_before_reading_anything(tmp_path: Path) -> None:
    """ClinPGx forbids sale, and the terms are accepted by taking the data — so nothing is read."""
    with pytest.raises(Exception):
        draft_pharm_variants(
            tmp_path, snapshot=tmp_path / "nonexistent", declared_use="commercial"
        )


def test_unstated_use_skips_rather_than_refusing(tmp_path: Path) -> None:
    result = draft_pharm_variants(tmp_path, snapshot=tmp_path / "nonexistent")
    assert result.skipped and result.warnings
    assert not (tmp_path / "pharm_variants.csv").exists()


@_needs_snapshot
def test_drafting_the_real_snapshot_is_re_runnable_and_reloads(tmp_path: Path) -> None:
    """Real data, expectations computed: draft, reload through the compiler, then re-run and add none."""
    first = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    assert first.added > 0
    path = tmp_path / "pharm_variants.csv"
    rows, errors, _ = _load_csv_rows(path, PharmVariantRow, "pharm_variants.csv")
    assert errors == []
    assert len(rows) == first.added
    # every drafted row really is about the drug asked for, and carries the full key
    assert {r.drug for r in rows} == {"simvastatin"}
    assert len({natural_key(r) for r in rows}) == len(rows)
    # a source consulted must be accounted for
    assert (tmp_path / "sources.csv").is_file()

    before = path.read_bytes()
    again = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    assert again.added == 0
    assert sum(len(r.already_present) for r in again.reports) == len(rows)
    assert path.read_bytes() == before


@_needs_snapshot
def test_a_drafted_pgx_module_validates(tmp_path: Path) -> None:
    """The point of the whole exercise: what is drafted is a module, not a pile of rows."""
    (tmp_path / "module_spec.yaml").write_text(
        "schema_version: '1.0'\n"
        "module:\n  name: clinpgx_demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    )
    draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    result = validate_spec(tmp_path)
    assert result.valid, result.errors
