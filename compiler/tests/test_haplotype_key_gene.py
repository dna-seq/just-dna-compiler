"""RM356: a `haplotypes.csv` row's identity carries its `gene`, under "both stated and different".

`HaplotypeRow._KEY_FIELDS` is `(haplotype_name, variant_key, allele)`, and the duplicate rule read it as
plain tuple equality. The UGT1A genes share exons 2-5, so two genes' `*2` can be defined by the same
variant and allele, and the second gene's row was refused as a duplicate of the first. Same class as
RM351, which made the cross-table checks key a named allele on `(gene, allele)`.

`gene` is optional on the row, so it splits two rows only when **both** state it and the stated values
differ (`@absent-is-not-different`): an unstated gene is unknown, and unknown cannot establish that two
rows are about two genes. The relation is therefore not an equality — a gene-less `*2` collides with
UGT1A1's and with UGT1A6's, which do not collide with each other — so every site that decides "same
row" (the compile/validate refusal, the drafting merge, the hints lint) asks one predicate,
`same_row`, over the unchanged key.

The rows below are the UGT1A *shape* written on a real module's variant: two gene symbols defining one
name by one allele at one position. They are not a claim about either gene's real definitions.
"""

import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.draft import append_rows, natural_key
from just_dna_compiler.hints import inspect_rows, key_fields
from just_dna_format.base import authored_field_names
from just_dna_format.pgx import HaplotypeRow
from just_dna_format.reference import _ALL_MODELS

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HEADER = "haplotype_name,rsid,chrom,start,ref,allele,gene\n"
_ROW = "e4,rs429358,19,44908684,T,C,{gene}\n"
_DUPLICATE = "haplotypes.csv: duplicate row for key"

#: (first gene, second gene, refused). Five arrangements: only both-stated-and-different is legal.
_ARRANGEMENTS = [
    pytest.param("UGT1A1", "UGT1A6", False, id="both-stated-different"),
    pytest.param("UGT1A1", "UGT1A1", True, id="same-gene-twice"),
    pytest.param("UGT1A1", "", True, id="stated-then-unstated"),
    pytest.param("", "UGT1A1", True, id="unstated-then-stated"),
    pytest.param("", "", True, id="neither-stated"),
    pytest.param("UGT1A1", "ugt1a1", True, id="one-gene-two-spellings"),
]


def _spec_with(tmp_path: Path, *genes: str) -> Path:
    """`apoe_epsilon` with its `haplotypes.csv` replaced by one `e4` row per gene given."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / "apoe_epsilon", spec)
    (spec / "haplotypes.csv").write_text(
        _HEADER + "".join(_ROW.format(gene=g) for g in genes), encoding="utf-8"
    )
    return spec


def _row(gene: str) -> HaplotypeRow:
    return HaplotypeRow(
        haplotype_name="e4",
        rsid="rs429358",
        chrom="19",
        start=44908684,
        ref="T",
        allele="C",
        gene=gene or None,
    )


@pytest.mark.parametrize(("first", "second", "refused"), _ARRANGEMENTS)
def test_validate_refuses_only_what_is_not_both_stated_and_different(
    tmp_path: Path, first: str, second: str, refused: bool
) -> None:
    result = validate_spec(_spec_with(tmp_path, first, second))
    duplicates = [e for e in result.errors if _DUPLICATE in e]
    assert bool(duplicates) is refused, result.errors
    if refused:
        # The refusal is byte-identical to the pre-RM356 one (`@warning-text-is-api`): the gene is not
        # added to the message, and the key it prints is the unchanged three-member tuple.
        (message,) = duplicates
        assert message == f"{_DUPLICATE} {natural_key(_row(second))}"
        assert natural_key(_row(second)) == ("e4", "rs429358", "C")


def test_a_gene_less_row_collides_with_both_genes_that_do_not_collide_with_each_other(
    tmp_path: Path,
) -> None:
    """The relation is not transitive, so no hashable key can carry it: UGT1A1 and UGT1A6 coexist, and a
    third row naming no gene is a duplicate of either."""
    assert validate_spec(_spec_with(tmp_path / "a", "UGT1A1", "UGT1A6")).valid
    result = validate_spec(_spec_with(tmp_path / "b", "UGT1A1", "UGT1A6", ""))
    assert [e for e in result.errors if _DUPLICATE in e] == [f"{_DUPLICATE} ('e4', 'rs429358', 'C')"]


@pytest.mark.parametrize(("first", "second", "refused"), _ARRANGEMENTS)
def test_compile_agrees_with_validate(tmp_path: Path, first: str, second: str, refused: bool) -> None:
    """`@validate-refuses-all`: both run the same table check, and compile refuses exactly what
    validate does."""
    compiled = compile_module(_spec_with(tmp_path, first, second), tmp_path / "out")
    assert compiled.success is not refused, compiled.errors
    assert bool([e for e in compiled.errors if _DUPLICATE in e]) is refused


@pytest.mark.parametrize(("first", "second", "refused"), _ARRANGEMENTS)
def test_drafting_merges_on_the_same_rule(tmp_path: Path, first: str, second: str, refused: bool) -> None:
    """`append_rows` can never write a row the compiler then refuses: a second gene's row is added, and
    every arrangement the compiler refuses is reported against the existing row instead."""
    spec = _spec_with(tmp_path, first)
    report = append_rows(spec, "haplotypes.csv", [_row(second)])
    if refused:
        assert report.added == []
        assert len(report.already_present) + len(report.differs) == 1
    else:
        assert [o.status for o in report.outcomes] == ["added"]
    assert validate_spec(spec).valid


def test_a_drafted_table_re_drafts_to_the_same_rows(tmp_path: Path) -> None:
    """The lap test the RM356 entry asks for: re-running a draft over the rows it already wrote adds
    nothing, for two genes on one variant as for one."""
    spec = _spec_with(tmp_path, "UGT1A1", "UGT1A6")
    before = (spec / "haplotypes.csv").read_bytes()
    report = append_rows(spec, "haplotypes.csv", [_row("UGT1A1"), _row("UGT1A6")])
    assert [o.status for o in report.outcomes] == ["already_present", "already_present"]
    assert (spec / "haplotypes.csv").read_bytes() == before


def test_drafting_catches_a_duplicate_inside_one_batch(tmp_path: Path) -> None:
    spec = _spec_with(tmp_path, "UGT1A1")
    report = append_rows(spec, "haplotypes.csv", [_row("UGT1A6"), _row(""), _row("UGT1A6")])
    # UGT1A6 is new; the gene-less row collides with the existing UGT1A1 row (`_compare` does not count a
    # cell the incoming row leaves empty as a difference); the second UGT1A6 is the first one again.
    assert [o.status for o in report.outcomes] == ["added", "already_present", "already_present"]
    assert validate_spec(spec).valid


@pytest.mark.parametrize(("first", "second", "refused"), _ARRANGEMENTS)
def test_the_lint_surface_agrees(first: str, second: str, refused: bool) -> None:
    report = inspect_rows("haplotypes.csv", _HEADER + _ROW.format(gene=first) + _ROW.format(gene=second))
    duplicates = [f for f in report.findings if f.message.startswith("duplicate of row")]
    assert bool(duplicates) is refused


@pytest.mark.parametrize(
    ("genes", "refused_rows"),
    [
        pytest.param(("UGT1A1", "", "UGT1A6"), [1, 2], id="unstated-between"),
        pytest.param(("UGT1A1", "UGT1A6", ""), [2], id="unstated-last"),
        pytest.param(("", "UGT1A1", "UGT1A6"), [1, 2], id="unstated-first"),
    ],
)
def test_lint_and_compile_refuse_the_same_rows_when_the_relation_is_not_transitive(
    tmp_path: Path, genes: tuple[str, ...], refused_rows: list[int]
) -> None:
    """Three rows are where a non-transitive relation can tell two sites apart: with the gene-less row in
    the middle, UGT1A6 collides with it and not with UGT1A1. Every row colliding with some earlier row is
    refused, at compile and in the lint alike, so a refused row stays in its bucket at both."""
    linted = inspect_rows("haplotypes.csv", _HEADER + "".join(_ROW.format(gene=g) for g in genes))
    assert sorted(f.row for f in linted.findings if f.message.startswith("duplicate of row")) == refused_rows
    result = validate_spec(_spec_with(tmp_path, *genes))
    assert len([e for e in result.errors if _DUPLICATE in e]) == len(refused_rows)


def test_the_published_key_names_the_column_that_splits_it() -> None:
    """S48: a tool reading `key_fields` would otherwise keep telling a UGT1A author the two rows
    collide. The column is published beside the key, not inside it, because inside it would say an
    absent gene is a distinct value."""
    key = key_fields("haplotypes.csv")
    assert key is not None
    assert key.columns == ("haplotype_name", "variant_key", "allele")
    assert key.distinct_when_stated == ("gene",)


def test_two_genes_on_one_variant_round_trip(tmp_path: Path) -> None:
    """P7 on the newly legal arrangement: compile -> reverse -> compile reproduces the artifact."""
    spec = _spec_with(tmp_path, "UGT1A1", "UGT1A6")
    first_compile = compile_module(spec, tmp_path / "out1")
    assert first_compile.success, first_compile.errors
    reverse_module(tmp_path / "out1", tmp_path / "spec2")
    second_compile = compile_module(tmp_path / "spec2", tmp_path / "out2")
    assert second_compile.success, second_compile.errors
    first, second = (json.loads((tmp_path / d / "manifest.json").read_text()) for d in ("out1", "out2"))
    assert first["artifact"]["digest"] == second["artifact"]["digest"]
    assert first["content_signature"] == second["content_signature"]


def test_every_distinct_when_stated_column_is_an_optional_authored_field_outside_the_key() -> None:
    """Walked over every model the format publishes, never a hand-kept list (`@registry-completeness`).

    A declared column must be one an author writes, must be optional (a required one is always stated,
    so it belongs in `_KEY_FIELDS` as a plain member), and must not already be a key member."""
    declaring = {
        name: model for name, model in _ALL_MODELS.items() if getattr(model, "_KEY_DISTINCT_WHEN_STATED", ())
    }
    assert set(declaring) == {name for name, model in _ALL_MODELS.items() if model is HaplotypeRow}
    for name, model in declaring.items():
        for column in model._KEY_DISTINCT_WHEN_STATED:
            assert column in authored_field_names(model), (name, column)
            assert not model.model_fields[column].is_required(), (name, column)
            assert column not in model._KEY_FIELDS, (name, column)
            # `_distinct_when_stated` compares as a gene symbol; another kind of column needs its own rule.
            assert column == "gene" and model.model_fields[column].annotation == str | None, (name, column)


@pytest.mark.parametrize(
    "example", sorted(p.parent.name for p in _EXAMPLES.glob("*/haplotypes.csv")), ids=str
)
def test_a_module_with_no_gene_conflict_compiles_to_the_same_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example: str
) -> None:
    """Recompile stability, measured on the same toolchain: every reference example carrying a
    `haplotypes.csv` compiles to the same `artifact.digest` and `content_signature` with the RM356
    declaration as with the pre-RM356 key (the declaration emptied). The key feeds neither the parquet
    row order nor `content_signature`; this is what shows it rather than says it."""
    with_gene = compile_module(_EXAMPLES / example, tmp_path / "with")
    assert with_gene.success, with_gene.errors
    monkeypatch.setattr(HaplotypeRow, "_KEY_DISTINCT_WHEN_STATED", ())
    without = compile_module(_EXAMPLES / example, tmp_path / "without")
    assert without.success, without.errors
    first, second = (json.loads((tmp_path / d / "manifest.json").read_text()) for d in ("with", "without"))
    assert first["artifact"]["digest"] == second["artifact"]["digest"]
    assert first["content_signature"] == second["content_signature"]
