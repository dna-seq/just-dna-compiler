"""Authoring hints — facts about authored cells, with nothing written (0.5).

What is pinned here is the partition the module exists for: a hint that *normalizes* what the author
already typed is applied, and a hint that would fill a cell a Class-2 redundancy check cross-examines
is never applied. Plus the mechanical guarantees — same row count and order out as in, every applied
change listed, no file touched.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.draft import DRAFTABLE, DraftError, model_for, stub_template
from just_dna_compiler.hints import (
    ALTERATION_KINDS,
    REDUNDANCY_BEARING,
    describe_table,
    field_options,
    inspect_rows,
)
from just_dna_format.base import authored_field_names, field_vocabularies

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_row_count_and_order_survive(kind: str) -> None:
    """`csv_out` is the input's shape: same header, same number of rows, same order."""
    text = stub_template(kind)
    report = inspect_rows(kind, text)
    assert report.header == text.splitlines()[0].split(",")
    assert len(report.csv_out) == len(text.splitlines())
    assert report.rows_in == len(text.splitlines()) - 1


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_hinting_writes_nothing_to_disk(kind: str, tmp_path: Path) -> None:
    """The primary MUST-NOT, asserted by bytes rather than by review."""
    path = tmp_path / kind
    path.write_text(stub_template(kind))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    inspect_rows(kind, path.read_text())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


def test_only_normalizations_are_applied_and_all_are_listed() -> None:
    """Every difference between input and output is an applied alteration, and vice versa."""
    text = "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n"
    report = inspect_rows("diplotypes.csv", text)
    assert {a.column for a in report.applied} == {"haplotype_a", "haplotype_b"}
    assert all(a.kind == "normalized" for a in report.applied)

    before = next(csv.DictReader(io.StringIO(text)))
    after = next(csv.DictReader(io.StringIO("\n".join(report.csv_out))))
    differing = {c for c in before if before[c] != after[c]}
    assert differing == {a.column for a in report.applied}


def test_a_silent_model_rewrite_is_surfaced_before_it_surprises_anyone() -> None:
    """`DiplotypeRow` canonicalizes the pair on load; the author is told, not ambushed."""
    report = inspect_rows("diplotypes.csv", "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n")
    rendered = next(csv.DictReader(io.StringIO("\n".join(report.csv_out))))
    assert (rendered["haplotype_a"], rendered["haplotype_b"]) == ("*1", "*4")


def test_redundancy_bearing_cells_are_never_filled() -> None:
    """The whole partition: a coordinate is left empty and explained, never supplied.

    Filling it would make `resolution._verify` compare a source against itself — and for an
    rsid-only row that check does not even run, so the row would go from honestly unverified to
    apparently verified."""
    report = inspect_rows("variants.csv", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    assert report.unchanged
    assert not [a for a in report.alterations if a.column in REDUNDANCY_BEARING and a.applied]
    explained = {f.column for f in report.findings if f.level == "info"}
    assert {"chrom", "start", "ref"} <= explained


def test_an_out_of_vocabulary_value_is_reported_with_the_options() -> None:
    report = inspect_rows(
        "variants.csv", "rsid,genotype,state,conclusion,direction\nrs1801133,A/G,risk,c,sideways\n"
    )
    assert any(f.column == "direction" and f.level == "error" for f in report.findings)
    options = {o.column: o.options for o in report.options}
    assert "sideways" not in options["direction"]
    assert sorted(options["direction"]) == options["direction"]


def test_a_duplicate_row_is_caught_with_the_compilers_own_key() -> None:
    text = (
        "rsid,genotype,state,conclusion\n"
        "rs1801133,A/G,risk,first\n"
        "rs1801133,A/G,risk,second\n"
    )
    report = inspect_rows("variants.csv", text)
    assert any("duplicate of row 0" in f.message for f in report.findings)


def test_a_shipped_binning_module_hints_clean() -> None:
    """Real data: the HTT example must produce no error and no coverage warning."""
    text = (_EXAMPLES / "htt_repeat_expansion" / "repeat_alleles.csv").read_text()
    report = inspect_rows("repeat_alleles.csv", text)
    assert [f for f in report.findings if f.level == "error"] == []
    assert [f for f in report.findings if f.level == "warning"] == []
    assert report.unchanged


def test_overlapping_bins_are_reported_via_the_schemas_own_checker() -> None:
    """Computed by calling `validate_bins`, not by hardcoding what it says."""
    text = (
        "measure_kind,measure_min,measure_max,conclusion,unresolved,gene,repeat_unit\n"
        "repeat_count,10,20,low,false,HTT,CAG\n"
        "repeat_count,15,25,overlapping,false,HTT,CAG\n"
        "repeat_count,,,not measured,true,HTT,CAG\n"
    )
    report = inspect_rows("repeat_alleles.csv", text)
    assert any(f.level == "error" for f in report.findings)


def test_a_binning_table_without_the_sentinel_is_flagged() -> None:
    text = (
        "measure_kind,measure_min,measure_max,conclusion,unresolved,gene,repeat_unit\n"
        "repeat_count,10,20,low,false,HTT,CAG\n"
    )
    report = inspect_rows("repeat_alleles.csv", text)
    assert any(f.column == "unresolved" and f.level == "warning" for f in report.findings)


def test_an_unreplaced_stub_is_reported_as_a_stub() -> None:
    report = inspect_rows("variants.csv", stub_template("variants.csv"))
    assert any("template stub" in f.message for f in report.findings)


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_describe_table_covers_exactly_the_authored_surface(kind: str) -> None:
    """Asserted against the marker, so a newly compiler-managed field needs no test edit."""
    described = [c["name"] for c in describe_table(kind)["columns"]]
    assert described == authored_field_names(model_for(kind))


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_field_options_match_the_models_markers(kind: str) -> None:
    expected = field_vocabularies(model_for(kind))
    assert {o.column: o.options for o in field_options(kind)} == {
        c: m["options"] for c, m in expected.items()
    }


def test_every_alteration_kind_is_a_declared_member() -> None:
    report = inspect_rows("diplotypes.csv", "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n")
    assert {a.kind for a in report.alterations} <= ALTERATION_KINDS


def test_the_report_serializes_deterministically() -> None:
    text = "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n"
    assert inspect_rows("diplotypes.csv", text).to_json() == inspect_rows("diplotypes.csv", text).to_json()


def test_a_headerless_row_is_read_against_the_models_column_order() -> None:
    """What a caller pasting one row from a template actually has."""
    header = stub_template("pgs.csv").splitlines()[0].split(",")
    row = ["PGS000135"] + [""] * (len(header) - 1)
    report = inspect_rows("pgs.csv", ",".join(row))
    assert report.rows_in == 1
    assert [f for f in report.findings if f.level == "error"] == []


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(DraftError, match="not an authored table"):
        inspect_rows("nonsense.csv", "a,b\n1,2\n")
