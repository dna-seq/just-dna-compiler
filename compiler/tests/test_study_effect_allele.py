"""`StudyRow.effect_allele` — the column a study's magnitude is stated relative to (0.6, RM91).

`VariantRow` has carried `effect_allele` since 0.3 because `ref`/`alts` plus the sign of the magnitude
cannot recover which allele the claim is about, and `_check_allele_membership` says in its own message
that naming the wrong one *inverts* the conclusion rather than breaking it. `StudyRow` states a
magnitude too — `effect_size` + `effect_measure`, there since 0.3 — and had no such column, so every
study row in the format asserted an effect relative to nothing.

The two halves pinned here are the column (it must survive the round trip, which is the touch point
that gets missed) and the check (it must fire on a contradiction and **withhold** on an unresolvable
row, rather than reading "I cannot tell" as "wrong").

Coordinates are the real GRCh38 HFE locus already in `reference_examples/hfe_hemochromatosis/`:
`rs1800562` at 6:26092913, `G>A` — the C282Y substitution. Real because a substitution has no spelling
freedom for a wrong allele to hide behind, which is what makes the negative case decidable at all.
"""

from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm91\n"
    "  title: RM91\n"
    "  description: what a study's effect size is relative to\n"
    "  report_title: RM91\n"
    "genome_build: GRCh38\n"
)

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs1800562,6,26092913,G,A,A/A,risk,C282Y homozygote,HFE\n"
)

#: A real PMID, cited so the mandatory-grounding rule is satisfied by evidence rather than by a stub.
_PMID = "16199547"

#: The injected table for the same locus. `A` is an allele here; `T` is not, and cannot be — a
#: substitution locus admits no reconciliation that would make it one.
_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,authored,resolved\n"
)

_STUDIES_HEADER = "rsid,pmid,effect_size,effect_measure,effect_allele\n"


def _spec(
    directory: Path,
    *,
    study_rows: str,
    resolution: str | None = _RESOLUTION,
    variants: str = _VARIANTS,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(variants)
    (directory / "studies.csv").write_text(_STUDIES_HEADER + study_rows)
    if resolution is not None:
        (directory / "resolution.csv").write_text(resolution)
    return directory


# ── the column ──────────────────────────────────────────────────────────────────────────────────


def test_the_effect_allele_reaches_the_parquet_and_survives_the_round_trip(tmp_path: Path) -> None:
    """compile → reverse → compile, byte-identical.

    This is the `@three-touch-points` test: the model, the `studies.parquet` record dict + schema, and
    the reverse writer's hand-kept `fieldnames` list. A column missing from the third reaches the
    parquet and then **vanishes** on reverse — the round trip still passes if you only check that the
    recompile succeeds, so the assertion has to be that the value is still there and that the digest
    is unchanged.
    """
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,A\n")
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors

    studies = pl.read_parquet(tmp_path / "a1" / "studies.parquet")
    assert "effect_allele" in studies.columns
    assert studies["effect_allele"].to_list() == ["A"]

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    reversed_csv = (tmp_path / "rev" / "studies.csv").read_text()
    assert "effect_allele" in reversed_csv.splitlines()[0]

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    round_tripped = pl.read_parquet(tmp_path / "a2" / "studies.parquet")
    assert round_tripped["effect_allele"].to_list() == ["A"]


def test_an_unset_effect_allele_leaves_the_authored_identity_alone(tmp_path: Path) -> None:
    """The P3/P8 property: an optional column nobody sets is omitted from `content_signature`.

    Two modules whose `studies.csv` differ only by the presence of the *column* — not a value — must
    hash equal, because `model_dump(exclude_none=True)` drops an unset cell. This is what makes the
    addition minor-legal rather than merely additive-looking.
    """
    with_column = _spec(tmp_path / "with", study_rows=f"rs1800562,{_PMID},1.7,OR,\n")
    without = tmp_path / "without"
    without.mkdir()
    (without / "module_spec.yaml").write_text(_SPEC_YAML)
    (without / "variants.csv").write_text(_VARIANTS)
    (without / "studies.csv").write_text(
        f"rsid,pmid,effect_size,effect_measure\nrs1800562,{_PMID},1.7,OR\n"
    )
    (without / "resolution.csv").write_text(_RESOLUTION)

    a = compile_module(with_column, tmp_path / "oa")
    b = compile_module(without, tmp_path / "ob")
    assert a.success and b.success, (a.errors, b.errors)
    assert a.manifest.content_signature == b.manifest.content_signature


# ── the check: fires on a contradiction ─────────────────────────────────────────────────────────


def _findings(result) -> str:
    return " ".join(result.errors) + " " + " ".join(result.warnings)


def test_a_wrong_study_effect_allele_warns_in_best_effort(tmp_path: Path) -> None:
    """`T` is not an allele of a `G>A` locus, and the message must say what is at stake.

    Warning rather than error here, because severity is the mode ladder — the same one the variant-side
    check uses, and for its stated reason: the resolving source's allele list can be incomplete, so a
    gap in ClinVar must not sink a correct module by default.
    """
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,T\n")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    text = _findings(result)
    assert "effect_allele 'T'" in text
    assert "inverts the study's finding" in text


def test_the_same_row_refuses_the_compile_under_strict(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,T\n")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert not result.success
    assert any("effect_allele 'T'" in e for e in result.errors)


def test_validate_refuses_what_compile_refuses(tmp_path: Path) -> None:
    """`@parity-by-check`. A mode ladder left compile-only lets `validate --strict` call a module
    valid that `compile --strict` then rejects — the exact defect the 2026-08-07 audit fixed for
    `_verify_vrs_ids` and `_check_p_value_num`, and that `_check_allele_membership` itself had."""
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,T\n")
    strict = validate_spec(spec, strict=True)
    assert not strict.valid
    assert any("effect_allele 'T'" in e for e in strict.errors)
    lenient = validate_spec(spec)
    assert lenient.valid
    assert any("effect_allele 'T'" in w for w in lenient.warnings)


def test_a_correct_effect_allele_is_silent(tmp_path: Path) -> None:
    """The tautology guard: a check that cannot pass is not a check."""
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,A\n")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert "effect_allele" not in _findings(result)


# ── the check: withholds on everything it cannot decide ─────────────────────────────────────────


def test_an_unresolvable_study_row_withholds_rather_than_reporting(tmp_path: Path) -> None:
    """No `resolution.csv` means no evidence, and unknown is not false.

    The tempting implementation compares against the row's own `ref` — but a `StudyRow` has `ref`
    without `alts` (it is there so a position-only row keeps an identifier), so `{ref}` alone would
    flag every study of a non-reference allele, which is most of them. `T` is wrong at this locus and
    must still produce nothing here, because nothing in scope can say so.
    """
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},1.7,OR,T\n", resolution=None)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert "effect_allele" not in _findings(result)


def test_a_study_row_naming_no_variant_is_skipped(tmp_path: Path) -> None:
    """Since RM47 a study row need not name a variant at all — it derives no key, so there is no
    locus to compare against and the row passes through untouched."""
    spec = _spec(
        tmp_path / "spec",
        study_rows=f"rs1800562,{_PMID},1.7,OR,A\n,{_PMID},0.4,beta,T\n",
    )
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert "effect_allele 'T'" not in _findings(result)
