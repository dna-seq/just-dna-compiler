"""The compiler-visible half of the 0.6 VCF 4.4 round: RM55, RM56, RM57, RM58 and RM65.

Every finding here is a **warning in both modes** and none of them changes a verdict. The properties
that matter are therefore: it fires on a real module, it fires *once* on the compile path (which runs
`validate_spec` internally, so an un-deduplicated check prints twice), `validate` sees exactly what
`compile` sees, and the sentence survives into `manifest.compilation.warnings` — which is the only
place a catalog reindexing from a published manifest can read it (RM44).
"""

from pathlib import Path

import json
import pytest
from just_dna_compiler import compiler as compiler_mod
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.binning import (
    FRACTIONAL_MEASURE_PHRASE,
    SPANNING_MEASUREMENT_PHRASE,
)

_REPO = Path(__file__).resolve().parents[2]
_HTT = _REPO / "reference_examples" / "htt_repeat_expansion"

_YAML = """\
schema_version: "1.0"
module:
  name: vcf_conformance
  title: VCF Conformance Probe
  description: A probe module for the 0.6 VCF 4.4 conformance warnings.
  report_title: VCF probe
  icon: dna
  color: "#b5651d"
defaults:
  curator: audit
  method: literature-review
genome_build: GRCh38
"""

_STUDIES = (
    "chrom,start,ref,rsid,pmid,population,conclusion,study_design\n"
    "6,26093141,G,,8696333,european,C282Y is the major HFE allele,candidate_gene\n"
    ",,,rs113993960,2570460,european,F508del is the common CFTR allele,candidate_gene\n"
)

_VARIANT_HEADER = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene,clin_sig,clinvar,"
    "requires_callable,quality_from,min_quality\n"
)
#: A monomorphic HFE record written the way VCF spells one — `.` in ALT (RM58).
_MISSING_MARKER_ROW = (
    ",6,26093141,G,.,G/G,ref,C282Y absent on a monomorphic record,HFE,benign,true,,,\n"
)
#: The reassurance row whose evidence is the reference record, floored against QUAL (RM57).
_QUAL_FLOOR_ROW = (
    "rs113993960,,,,,G/G,ref,F508del absent,CFTR,benign,true,true,QUAL,30\n"
)
#: The same row done right: a per-sample confidence field.
_GQ_FLOOR_ROW = (
    "rs113993960,,,,,G/G,ref,F508del absent,CFTR,benign,true,true,GQ,30\n"
)


def _spec(tmp_path: Path, variants: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANT_HEADER + variants)
    (spec / "studies.csv").write_text(_STUDIES)
    return spec


def _warnings(spec: Path, tmp_path: Path, *, strict: bool = False) -> list[str]:
    result = compile_module(spec, tmp_path / f"out-{'strict' if strict else 'best'}", strict=strict)
    assert result.success, result.errors
    return list(result.warnings)


def _matching(warnings: list[str], fragment: str) -> list[str]:
    return [w for w in warnings if fragment in w]


# ── RM55 / RM56 on the real flagship module ────────────────────────────────────────────────────


def test_the_shipped_repeat_example_now_says_what_it_cannot_express(tmp_path: Path) -> None:
    """`reference_examples/htt_repeat_expansion` is the module both findings were written about.

    It compiled green under `--strict` stating four thresholds for a measurement VCF 4.4 defines as a
    Float carrying a confidence interval, and said nothing about either. The compile still succeeds —
    neither finding is an authored defect, and refusing would make a correct module uncompilable for a
    reason no edit clears (P5) — but it is no longer silent.
    """
    warnings = _warnings(_HTT, tmp_path)
    assert len(_matching(warnings, FRACTIONAL_MEASURE_PHRASE)) == 1
    assert len(_matching(warnings, SPANNING_MEASUREMENT_PHRASE)) == 1
    for w in _matching(warnings, FRACTIONAL_MEASURE_PHRASE) + _matching(
        warnings, SPANNING_MEASUREMENT_PHRASE
    ):
        assert w.startswith("repeat_alleles.csv: ")


def test_neither_finding_escalates_under_strict(tmp_path: Path) -> None:
    """The `not_covered` class: no authored edit clears either, so `strict` has nothing to demand.

    RM55 needs a schema column that does not exist yet and RM56 needs a policy vocabulary nobody has
    designed. `strict` means *reproducible artifact*, an unrelated axis — and the table reproduces
    exactly, which is why the same two warnings appear and the compile succeeds in both modes.
    """
    lax = _warnings(_HTT, tmp_path, strict=False)
    strict = _warnings(_HTT, tmp_path, strict=True)
    assert _matching(lax, FRACTIONAL_MEASURE_PHRASE) == _matching(strict, FRACTIONAL_MEASURE_PHRASE)
    assert _matching(lax, SPANNING_MEASUREMENT_PHRASE) == _matching(
        strict, SPANNING_MEASUREMENT_PHRASE
    )


def test_the_sentences_reach_the_published_manifest(tmp_path: Path) -> None:
    """A consumer reindexing from a published `manifest.json` has no spec directory left (RM44).

    So the check is not "the CLI printed it" but "the artifact carries it" — pinned by reading the
    manifest back off disk rather than by trusting `CompilationResult`.
    """
    out = tmp_path / "out"
    result = compile_module(_HTT, out)
    assert result.success, result.errors
    published = json.loads((out / "manifest.json").read_text())["compilation"]["warnings"]
    assert _matching(published, FRACTIONAL_MEASURE_PHRASE)
    assert _matching(published, SPANNING_MEASUREMENT_PHRASE)


def test_a_module_with_no_binning_table_says_nothing(tmp_path: Path) -> None:
    """Narrow by construction — the finding is about a kind, so a module carrying none is silent."""
    warnings = _warnings(_spec(tmp_path, _GQ_FLOOR_ROW), tmp_path)
    assert not _matching(warnings, FRACTIONAL_MEASURE_PHRASE)
    assert not _matching(warnings, SPANNING_MEASUREMENT_PHRASE)


# ── RM57: the quality floor that inverts ───────────────────────────────────────────────────────


def test_a_requires_callable_row_floored_against_qual_is_reported(tmp_path: Path) -> None:
    """The row asks a consumer to require evidence that the position *is* variant before saying it is not.

    Aggregated to one line naming the count and an example, not a line per row: a gene panel carries
    hundreds of `requires_callable` rows.
    """
    warnings = _warnings(_spec(tmp_path, _QUAL_FLOOR_ROW), tmp_path)
    found = _matching(warnings, compiler_mod.QUAL_INVERSION_PHRASE)
    assert len(found) == 1
    assert "rs113993960" in found[0]
    assert "MIN_DP" in found[0] and "GQ" in found[0]


@pytest.mark.parametrize(
    "row, expected, why",
    [
        (_GQ_FLOOR_ROW, False, "a per-sample confidence field is the correct spelling"),
        (
            "rs113993960,,,,,G/G,ref,F508del absent,CFTR,benign,true,,QUAL,30\n",
            False,
            "QUAL on a row that is NOT requires_callable is the legitimate combination this "
            "deliberately does not refuse — the row is read against a variant record",
        ),
        (
            "rs113993960,,,,,G/G,ref,F508del absent,CFTR,benign,true,true,DP|QUAL,30\n",
            True,
            "an alternated pointer still names QUAL",
        ),
        (
            "rs113993960,,,,,G/G,ref,F508del absent,CFTR,benign,true,true,qual,30\n",
            True,
            "and a lower-case spelling is the same field",
        ),
    ],
)
def test_the_inversion_check_fires_on_the_pointer_and_not_on_the_mode(
    tmp_path: Path, row: str, expected: bool, why: str
) -> None:
    warnings = _warnings(_spec(tmp_path, row), tmp_path)
    assert bool(_matching(warnings, compiler_mod.QUAL_INVERSION_PHRASE)) is expected, why


# ── RM58: `.` in alts ──────────────────────────────────────────────────────────────────────────


def test_the_missing_marker_is_reported_with_the_two_keys_it_produces(tmp_path: Path) -> None:
    """The identity consequence is the finding, so the message must show it rather than assert it.

    Both keys are computed by the compiler from the row itself, and the test recomputes the
    empty-cell one through the same public helper rather than hardcoding a string.
    """
    from just_dna_format.base import derive_variant_key

    warnings = _warnings(_spec(tmp_path, _MISSING_MARKER_ROW), tmp_path)
    found = _matching(warnings, compiler_mod.MISSING_ALLELE_PHRASE)
    assert len(found) == 1
    assert "6:26093141:G:." in found[0]
    assert derive_variant_key(None, "6", 26093141, "G") in found[0]


def test_a_clean_alts_cell_says_nothing(tmp_path: Path) -> None:
    clean = ",6,26093141,G,A,A/G,risk,C282Y carrier,HFE,pathogenic,true,,,\n"
    warnings = _warnings(_spec(tmp_path, clean), tmp_path)
    assert not _matching(warnings, compiler_mod.MISSING_ALLELE_PHRASE)


def test_the_missing_marker_gets_its_own_clause_and_borrows_neither_other_one() -> None:
    """The conflation this repairs is the one `cpic.unusable_allele_reason` already had to unwind.

    Both "cannot host" sites build their prose per reason present, so a new reason that no branch
    knows would silently produce an empty clause — the failure mode this asserts against, on both
    copies, using the same real values.
    """
    from just_dna_compiler.compiler import _spelling_clauses as compiler_clauses
    from just_dna_compiler.resolution import _spelling_clauses as resolution_clauses

    for clauses in (compiler_clauses, resolution_clauses):
        only_missing = clauses({".": "missing"})
        assert only_missing.strip()
        assert "MISSING marker" in only_missing
        # Neither of the other two consequences may leak onto it: `.` is not an uncertainty and is
        # not a grammar gap, so nothing is ever going to be widened to hold it.
        assert "ambiguity code" not in only_missing
        assert "RM5" not in only_missing

        together = clauses({"Y": "ambiguity", "<DEL>": "notation", ".": "missing"})
        assert "ambiguity code" in together and "RM5" in together and "MISSING marker" in together


# ── validate/compile parity, and the dedup that makes it readable ──────────────────────────────


@pytest.mark.parametrize(
    "row",
    [_MISSING_MARKER_ROW, _QUAL_FLOOR_ROW],
    ids=["RM58 missing marker", "RM57 inverted quality floor"],
)
def test_validate_reports_exactly_what_compile_reports(tmp_path: Path, row: str) -> None:
    """The author's pre-flight must not be quieter than the compile that follows it.

    Both checks are pure computation over authored bytes and need no `output_dir`, which is the
    standing rule for what belongs in `validate_spec` too.
    """
    spec = _spec(tmp_path, row)
    from_validate = set(validate_spec(spec).warnings)
    from_compile = set(_warnings(spec, tmp_path))
    assert from_validate <= from_compile
    for phrase in (compiler_mod.QUAL_INVERSION_PHRASE, compiler_mod.MISSING_ALLELE_PHRASE):
        assert bool(_matching(list(from_validate), phrase)) == bool(
            _matching(list(from_compile), phrase)
        )


@pytest.mark.parametrize(
    "spec_dir_name, phrase",
    [
        ("htt", FRACTIONAL_MEASURE_PHRASE),
        ("htt", SPANNING_MEASUREMENT_PHRASE),
    ],
)
def test_a_check_living_in_both_passes_prints_once(
    tmp_path: Path, spec_dir_name: str, phrase: str
) -> None:
    """`compile_module` runs `validate_spec` internally, so an un-deduplicated check emits twice.

    185 alleles printing 370 lines is the precedent; four bins printing eight is the same defect at a
    scale nobody would notice, which is why it is pinned rather than eyeballed.
    """
    warnings = _warnings(_HTT, tmp_path)
    assert len(_matching(warnings, phrase)) == 1


# ── RM65: the comment the spec contradicts ─────────────────────────────────────────────────────


def test_the_positional_comment_no_longer_claims_repeats_have_no_coordinates() -> None:
    """A claim the spec contradicts is a defect in its own right, even when the fix is a release away.

    VCF 4.4 §5.6 has POS and SVLEN specify the interval a copy number is defined over, and §5.7 says a
    `<CNV:TR>` record's POS and END should match the STR/VNTR catalog — so a repeat and a copy-number
    segment are loci with coordinates, and `repeat_alleles.csv`/`copynumbers.csv` not being joinable is
    a gap in this schema rather than a property of the thing described. The comment still *quotes* the
    old claim, because what it used to say is the point — so the guard is that it survives only as a
    quotation, once, introduced as what was corrected. The two tables staying out of
    `_POSITIONAL_TABLE_KINDS` is correct and stays (the columns are 0.7+ work), which is why that is
    asserted rather than the reverse.
    """
    source = (
        _REPO / "compiler" / "src" / "just_dna_compiler" / "compiler.py"
    ).read_text(encoding="utf-8")
    false_claim = "property of what they describe rather than a gap"
    assert source.count(false_claim) == 1
    preamble = source[max(0, source.index(false_claim) - 400) : source.index(false_claim)]
    assert "used to call them one" in preamble, "the false claim is no longer marked as corrected"
    assert "gap in this schema" in source
    assert "§5.6" in source and "§5.7" in source

    positional = {csv for csv, _model in compiler_mod._POSITIONAL_TABLE_KINDS}
    assert positional == {"heteroplasmy.csv", "haplotypes.csv", "pharm_variants.csv"}
