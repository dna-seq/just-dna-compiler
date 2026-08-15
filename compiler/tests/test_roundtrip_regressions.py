"""Round-trip regression tests for the shapes the earlier 0.3/0.4 suite never exercised
(CONSTITUTION Principle 7 — lossless round-trip + idempotency). Each of these round-tripped
*wrongly* before the fix, while the happy path (rsid-keyed, uniform priority, no explicit-False
booleans) stayed green — so the invariant was only nominally "proven by tests".

Covered:
  * position-only variants keep their annotation (gene/phenotype/category) — keyed on variant_key,
    not the (null) rsid;
  * position-only study rows survive reverse → recompile instead of becoming identifier-less;
  * a partially-set `priority` is not fabricated for the rows that never set one;
  * an authored `pathogenic=false` / `benign=false` / `clinvar=false` is preserved (tri-state),
    not collapsed to None;
  * the artifact digest is a fixed point across compile → reverse → compile for all of the above.

All run with resolve_with_ensembl=False (no reference/network)."""

import math
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.spec import VariantRow

_YAML = """\
schema_version: "1.0"
module:
  name: demo_rt
  title: Round-trip Regressions
  description: fixture
  report_title: Report
genome_build: GRCh38
"""


def _write(d: Path, variants: str, studies: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(studies, encoding="utf-8")
    return d


def _roundtrip(tmp_path: Path, variants: str, studies: str) -> tuple[Path, Path]:
    """compile → reverse → recompile; returns (orig_dir, recompiled_dir). Asserts the reversed spec
    re-validates and that the artifact digest is a fixed point."""
    spec = _write(tmp_path / "spec", variants, studies)
    orig = tmp_path / "orig"
    m1 = compile_module(spec, orig, resolve_with_ensembl=False)
    assert m1.success, m1.errors
    reverse_module(orig, tmp_path / "reversed")
    rev_validation = validate_spec(tmp_path / "reversed")
    assert rev_validation.valid, rev_validation.errors
    recompiled = tmp_path / "recompiled"
    m2 = compile_module(tmp_path / "reversed", recompiled, resolve_with_ensembl=False)
    assert m2.success, m2.errors
    assert m1.manifest.artifact.digest == m2.manifest.artifact.digest
    return orig, recompiled


def test_position_only_variant_keeps_annotation(tmp_path: Path) -> None:
    variants = (
        "chrom,start,ref,genotype,state,conclusion,gene,phenotype,category\n"
        "1,100,A,A/G,risk,c,BRCA1,breast cancer,cancer\n"
    )
    studies = "chrom,start,ref,pmid\n1,100,A,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    ann = pl.read_parquet(recompiled / "annotations.parquet")
    row = ann.row(0, named=True)
    assert row["gene"] == "BRCA1"
    assert row["phenotype"] == "breast cancer"
    assert row["category"] == "cancer"
    # variant_key is materialized so the reverse lookup matches a null-rsid row.
    assert row["variant_key"] == "1:100:A"
    assert (
        pl.read_parquet(orig / "annotations.parquet")
        .equals(pl.read_parquet(recompiled / "annotations.parquet"))
    )


def test_poly_effect_annotation_survives_roundtrip(tmp_path: Path) -> None:
    # A genuine poly-effect variant: one locus, two genotype rows with DISTINCT effects
    # (conclusion) AND distinct phenotype/category. Keying annotations on variant_key alone
    # collapsed the second row onto the first, silently overwriting its phenotype/category on
    # reverse. Keyed on the variant-effect pair (variant_key, conclusion, negatives) both survive
    # (Principle 7 — lossless round-trip).
    variants = (
        "rsid,genotype,state,conclusion,gene,phenotype,category\n"
        "rs1,A/G,risk,mild effect,GENE1,MildTrait,catA\n"
        "rs1,A/A,risk,severe effect,GENE1,SevereTrait,catB\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    def by_conclusion(d: Path) -> dict[str, tuple]:
        w = pl.read_parquet(d / "weights.parquet")
        ann = pl.read_parquet(d / "annotations.parquet")
        # join weights → annotations on the variant-effect pair, as reverse does
        merged = {
            (r["variant_key"], r["conclusion"], r["negatives"]): (r["phenotype"], r["category"])
            for r in ann.iter_rows(named=True)
        }
        return {
            r["conclusion"]: merged[(r["variant_key"], r["conclusion"], r["negatives"])]
            for r in w.iter_rows(named=True)
        }

    expected = {"mild effect": ("MildTrait", "catA"), "severe effect": ("SevereTrait", "catB")}
    assert by_conclusion(orig) == expected
    assert by_conclusion(recompiled) == expected


def test_position_only_study_survives_roundtrip(tmp_path: Path) -> None:
    variants = "chrom,start,ref,genotype,state,conclusion\n1,100,A,A/G,risk,c\n"
    studies = "chrom,start,ref,pmid,population\n1,100,A,12345678,EUR\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    s = pl.read_parquet(recompiled / "studies.parquet").row(0, named=True)
    assert s["rsid"] is None
    assert (s["chrom"], s["start"], s["ref"]) == ("1", 100, "A")
    assert (
        pl.read_parquet(orig / "studies.parquet")
        .equals(pl.read_parquet(recompiled / "studies.parquet"))
    )


def test_partial_priority_is_not_fabricated(tmp_path: Path) -> None:
    # r1 sets priority=high, r2 leaves it unset and there is no defaults.priority: the unset row must
    # STAY unset across the round-trip, not inherit r1's value as an inferred default.
    variants = (
        "rsid,genotype,state,conclusion,priority\n"
        "rs1,A/G,risk,c,high\n"
        "rs2,A/G,risk,c,\n"
    )
    studies = "rsid,pmid\nrs1,12345678\nrs2,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    def priorities(d: Path) -> list:
        w = pl.read_parquet(d / "weights.parquet").sort("rsid")
        return w["priority"].to_list()

    assert priorities(orig) == ["high", None]
    assert priorities(recompiled) == ["high", None]


def test_explicit_false_clinvar_booleans_survive(tmp_path: Path) -> None:
    # False is distinct from None ("stated not-pathogenic" vs "unstated"). It must round-trip.
    variants = (
        "rsid,genotype,state,conclusion,clinvar,pathogenic,benign\n"
        "rs1,A/G,risk,c,true,false,true\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    for d in (orig, recompiled):
        w = pl.read_parquet(d / "weights.parquet").row(0, named=True)
        assert w["clinvar"] is True
        assert w["pathogenic"] is False   # NOT None
        assert w["benign"] is True

    # And the read-time alias stays False (the curator's explicit call), not derived-away.
    reversed_row = next(
        r for r in _read_csv(tmp_path / "reversed" / "variants.csv")
    )
    row = VariantRow.model_validate({k: v for k, v in reversed_row.items() if v != ""})
    assert row.pathogenic is False
    assert row.effective_pathogenic is False


def _read_csv(path: Path) -> list[dict]:
    import csv

    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ── 0.5: callable_from (RM6) ────────────────────────────────────────────────────────────────────


def test_callable_from_survives_roundtrip(tmp_path: Path) -> None:
    # `requires_callable` says a negative must be proven; `callable_from` says where the proof is.
    # Both are on the same row, so a consumer can act on the pair without a second lookup.
    variants = (
        "rsid,genotype,state,conclusion,requires_callable,callable_from\n"
        "rs1,A/G,risk,c,true,DP|GQ\n"
        "rs2,A/G,risk,c,true,FT\n"
        "rs3,A/G,risk,c,,\n"
    )
    studies = "rsid,pmid\nrs1,12345678\nrs2,12345678\nrs3,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    for d in (orig, recompiled):
        w = pl.read_parquet(d / "weights.parquet").sort("rsid")
        assert w["callable_from"].to_list() == ["DP|GQ", "FT", None]
    # An absent pointer stays absent rather than being fabricated as a default field name.
    assert pl.read_parquet(orig / "weights.parquet").equals(
        pl.read_parquet(recompiled / "weights.parquet")
    )


def test_callable_from_is_a_pointer_not_an_expression(tmp_path: Path) -> None:
    # Principle 1: the column names *where* the signal lives; it can never become a computation.
    variants = (
        "rsid,genotype,state,conclusion,callable_from\n"
        "rs1,A/G,risk,c,DP > 10\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    spec = _write(tmp_path / "spec", variants, studies)
    result = validate_spec(spec)
    assert not result.valid
    assert any("pointer, not an expression" in e for e in result.errors), result.errors


# ── 0.5: the queryable p-value (authored number in, derived neg_log10_p out) ────────────────────

# Coordinates + alts are carried so a `strict=True` compile has nothing left to resolve and the
# allele-membership check has a locus to check `A/G` against — neither is what these tests are about.
_P_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
    "rs1,1,100,A,G,A/G,risk,c\n"
)


def test_p_value_num_survives_roundtrip_and_neg_log10_is_derived(tmp_path: Path) -> None:
    # The number is authored and must come back unchanged; neg_log10_p is derived on write, so it must
    # be IN the parquet and ABSENT from the reversed CSV (the `allele_frequency` contract).
    studies = (
        "rsid,pmid,p_value,p_value_num\n"
        "rs1,12345678,5e-8,5e-8\n"
        "rs1,22222222,0.03,0.03\n"
    )
    orig, recompiled = _roundtrip(tmp_path, _P_VARIANTS, studies)

    for d in (orig, recompiled):
        rows = pl.read_parquet(d / "studies.parquet").sort("pmid").to_dicts()
        assert [r["p_value_num"] for r in rows] == [5e-8, 0.03]
        # -log10 of each, computed here rather than hardcoded off a data dump.
        assert [round(r["neg_log10_p"], 9) for r in rows] == [
            round(-math.log10(5e-8), 9),
            round(-math.log10(0.03), 9),
        ]

    reversed_studies = _read_csv(tmp_path / "reversed" / "studies.csv")
    assert "neg_log10_p" not in reversed_studies[0]
    assert [float(r["p_value_num"]) for r in reversed_studies] == [5e-8, 0.03]


def test_neg_log10_p_ranks_by_strength(tmp_path: Path) -> None:
    # What the derived column is for: a consumer sorts on it to rank associations.
    studies = (
        "rsid,pmid,p_value,p_value_num\n"
        "rs1,11111111,0.05,0.05\n"
        "rs1,22222222,5e-8,5e-8\n"
        "rs1,33333333,1e-30,1e-30\n"
    )
    spec = _write(tmp_path / "spec", _P_VARIANTS, studies)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    rows = pl.read_parquet(tmp_path / "out" / "studies.parquet").to_dicts()
    by_strength = [r["pmid"] for r in sorted(rows, key=lambda r: r["neg_log10_p"], reverse=True)]
    assert by_strength == ["33333333", "22222222", "11111111"]


def test_p_value_string_and_number_are_cross_checked(tmp_path: Path) -> None:
    # Two encodings of one number: a transcription slip between them is otherwise invisible.
    studies = "rsid,pmid,p_value,p_value_num\nrs1,12345678,5e-8,5e-6\n"
    spec = _write(tmp_path / "spec", _P_VARIANTS, studies)

    lenient = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert lenient.success
    assert any("p_value" in w and "disagree" in w for w in lenient.warnings), lenient.warnings

    strict_run = compile_module(spec, tmp_path / "out_strict", resolve_with_ensembl=False, strict=True)
    assert not strict_run.success
    assert any("disagree" in e for e in strict_run.errors), strict_run.errors


def test_p_value_cross_check_stays_silent_on_indefinite_and_rounded_strings(tmp_path: Path) -> None:
    # A bound, a word, and a rounding are all legitimate; none of them is a disagreement, and
    # reporting them would drown the real finding above in noise.
    studies = (
        "rsid,pmid,p_value,p_value_num\n"
        "rs1,11111111,<0.001,5e-8\n"
        "rs1,22222222,NS,0.03\n"
        "rs1,33333333,5.23e-8,5.2e-8\n"
        "rs1,44444444,,1e-4\n"
    )
    spec = _write(tmp_path / "spec", _P_VARIANTS, studies)
    for strict in (False, True):
        result = compile_module(
            spec, tmp_path / f"out_{strict}", resolve_with_ensembl=False, strict=strict
        )
        assert result.success, result.errors
        assert not [m for m in result.warnings + result.errors if "disagree" in m]


# ── RM80: annotations.parquet carries the genotype that distinguishes its rows ──────────────────
# Reported by a downstream consumer: `variant_key` is not unique in this table and never could be
# (the poly-effect case above is real), so every consumer had to dedup before joining — and the
# authored column that says *which call an annotation applies to* was in no column at all.


def test_annotations_carry_the_genotype_that_distinguishes_their_rows(tmp_path: Path) -> None:
    variants = (
        "rsid,genotype,state,conclusion,gene,phenotype,category\n"
        "rs1,A/G,risk,carrier,GENE1,MildTrait,catA\n"
        "rs1,A/A,risk,affected,GENE1,SevereTrait,catB\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    for d in (orig, recompiled):
        ann = pl.read_parquet(d / "annotations.parquet")
        assert "genotype" in ann.columns
        # The consumer's first option — "unique per variant_key" — is impossible here, which is why
        # the second one is the fix. Both statements are asserted so the reason survives.
        keys = [r["variant_key"] for r in ann.iter_rows(named=True)]
        assert len(set(keys)) == 1 and len(keys) == 2
        by_genotype = {
            r["genotype"]: (r["phenotype"], r["category"]) for r in ann.iter_rows(named=True)
        }
        assert by_genotype == {
            "A/G": ("MildTrait", "catA"),
            "A/A": ("SevereTrait", "catB"),
        }


def test_two_genotypes_sharing_one_conclusion_stay_two_annotation_rows(tmp_path: Path) -> None:
    """The case that forced `genotype` into the KEY rather than merely into the columns.

    Under the old variant-effect key these two rows collapse to one, so a `genotype` column carried
    without being keyed on would have named one genotype while silently standing for both — a
    consumer filtering on it gets a wrong answer instead of a missing one. The old behaviour is
    demonstrated here rather than asserted about: the effect-pair projection really does lose the
    distinction, and the shipped key really does keep it."""
    variants = (
        "rsid,genotype,state,conclusion,gene,phenotype,category\n"
        "rs1,A/G,risk,carrier,GENE1,Trait,cat\n"
        "rs1,A/A,risk,carrier,GENE1,Trait,cat\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    ann = pl.read_parquet(orig / "annotations.parquet")
    effect_pairs = {(r["variant_key"], r["conclusion"], r["negatives"]) for r in ann.iter_rows(named=True)}
    assert len(effect_pairs) == 1, "the old key really is blind to the genotype here"
    assert ann.height == 2, "the shipped key keeps both rows"
    assert {r["genotype"] for r in ann.iter_rows(named=True)} == {"A/G", "A/A"}
    assert (
        pl.read_parquet(orig / "annotations.parquet")
        .equals(pl.read_parquet(recompiled / "annotations.parquet"))
    )


def test_a_phased_genotype_still_finds_its_annotation(tmp_path: Path) -> None:
    """The property RM80's join now depends on, pinned rather than assumed.

    `annotations.parquet` stores the **authored** genotype cell; the reverse probe rebuilds the string
    from `weights.parquet`, which stores an allele list plus a `phased` bit. The two must agree or the
    lookup misses and `gene`/`phenotype`/`category` come back empty — a silent P7 loss.

    Unphased is safe by construction, because the model *rejects* an unsorted pair rather than
    canonicalizing it (`G/A` never reaches a cell), so the fixtures above cannot exercise the risk.
    A phased pair is the case that can: `G|A` keeps its authored order, and reverse must re-emit that
    order rather than sorting it.
    """
    variants = (
        "rsid,genotype,state,conclusion,gene,phenotype,category\n"
        "rs1,G|A,risk,phased effect,GENE1,PhasedTrait,catP\n"
        "rs1,A/G,risk,unphased effect,GENE1,UnphasedTrait,catU\n"
    )
    studies = "rsid,pmid\nrs1,12345678\n"
    orig, recompiled = _roundtrip(tmp_path, variants, studies)

    for d in (orig, recompiled):
        ann = pl.read_parquet(d / "annotations.parquet")
        assert {
            r["genotype"]: (r["phenotype"], r["category"]) for r in ann.iter_rows(named=True)
        } == {"G|A": ("PhasedTrait", "catP"), "A/G": ("UnphasedTrait", "catU")}

    # The reversed CSV kept both annotations: an empty gene/phenotype here is exactly the silent loss
    # a key the probe cannot reproduce would cause.
    reversed_csv = (tmp_path / "reversed" / "variants.csv").read_text(encoding="utf-8")
    assert "PhasedTrait" in reversed_csv and "UnphasedTrait" in reversed_csv
