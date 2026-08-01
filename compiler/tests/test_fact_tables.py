"""The 0.5 derived-fact sidecars in the compiler: digest safety, round-trip, cross-checks, verify.

The two properties that matter most are opposites of each other, and both are pinned here:

* adding a sidecar must leave the SNP core's bytes **completely unchanged** (it is additive — a
  consumer that does not want frequencies must not see a different `weights.parquet`); and
* the sidecar's own parquet must enter `artifact.digest`, because a module carrying frequency data
  genuinely is different content from one that does not.
"""

import csv
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.frequency import FrequencyRow
from just_dna_format.integrity import frequency_signature
from just_dna_format.vrs import derive_vrs_allele_id

_YAML = """\
schema_version: "1.0"
module:
  name: demo_facts
  title: Fact Tables
  description: Sidecar round-trip
  report_title: Fact Tables
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
"""

_VARIANTS = (
    "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "11,5227002,T,A,A/T,risk,Sickle-cell carrier,HBB\n"
    "1,11796321,G,A,A/G,risk,Reduced activity,MTHFR\n"
)

_STUDIES = (
    "chrom,start,ref,pmid,conclusion\n"
    "11,5227002,T,12345678,Sickle-cell trait in carriers\n"
    "1,11796321,G,23456789,Raised homocysteine\n"
)

_SICKLE = derive_vrs_allele_id("11", 5227002, "T", "A")
_MTHFR = derive_vrs_allele_id("1", 11796321, "G", "A")

_FREQUENCIES = (
    "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,allele_number,"
    "homozygote_count,hemizygote_count,faf95,dataset,vrs_id,caid,source,status,fetched_at\n"
    f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,global,4272,1610650,,,,gnomad_v4.1_joint,,,gnomad,resolved,\n"
    f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,afr,3949,41442,,,0.04815774,gnomad_v4.1_joint,,,gnomad,resolved,\n"
    f"{_MTHFR},rs1801133,1,11796321,G,A,GRCh38,global,10,100,,,,gnomad_v4.1_joint,,,gnomad,resolved,\n"
)

_GENE_METRICS = (
    "gene,gene_id,transcript,mane_select,pli,loeuf,oe_lof,oe_lof_lower,lof_z,mis_z,syn_z,oe_mis,"
    "obs_lof,exp_lof,constraint_flags,dataset,source,status,fetched_at\n"
    "HBB,ENSG00000244734,ENST00000335295,true,0.02,1.51,0.83,0.42,0.3,0.9,0.1,0.95,7,8.4,,"
    "gnomad_v4.1_constraint,gnomad-constraint,resolved,\n"
    "MTHFR,ENSG00000177000,ENST00000376590,true,0.001,0.72,0.51,0.35,1.9,1.1,0.2,0.88,20,39.1,,"
    "gnomad_v4.1_constraint,gnomad-constraint,resolved,\n"
)


def _spec(tmp_path: Path, *, frequencies: bool = False, gene_metrics: bool = False) -> Path:
    spec = tmp_path / f"spec_{int(frequencies)}{int(gene_metrics)}"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if frequencies:
        (spec / "frequencies.csv").write_text(_FREQUENCIES)
    if gene_metrics:
        (spec / "gene_metrics.csv").write_text(_GENE_METRICS)
    return spec


# ── additive: the SNP core does not move ────────────────────────────────────────────────────────


def test_sidecars_leave_the_snp_core_byte_identical(tmp_path: Path) -> None:
    bare = compile_module(_spec(tmp_path), tmp_path / "o_bare", resolve_with_ensembl=False)
    rich = compile_module(
        _spec(tmp_path, frequencies=True, gene_metrics=True),
        tmp_path / "o_rich", resolve_with_ensembl=False,
    )
    assert bare.success and rich.success, (bare.errors, rich.errors)
    for name in ("weights.parquet", "annotations.parquet"):
        assert (tmp_path / "o_bare" / name).read_bytes() == (tmp_path / "o_rich" / name).read_bytes()
    # ...but the artifact identity DOES differ, because the module genuinely carries more content.
    assert bare.manifest.artifact.digest != rich.manifest.artifact.digest
    assert bare.manifest.frequency is None and bare.manifest.gene_metrics is None


def test_sidecar_csvs_are_not_hashed_as_raw_inputs(tmp_path: Path) -> None:
    """They are fact-hashed like `resolution.csv`, not byte-hashed like an authored CSV.

    Byte-hashing a multi-producer table would make a reverse→recompile cycle "change the hash" over
    nothing but column order and timestamps.
    """
    result = compile_module(
        _spec(tmp_path, frequencies=True, gene_metrics=True), tmp_path / "out",
        resolve_with_ensembl=False,
    )
    input_names = {entry.name for entry in result.manifest.inputs}
    assert "frequencies.csv" not in input_names
    assert "gene_metrics.csv" not in input_names
    artifact_names = {entry.name for entry in result.manifest.artifact.files}
    assert {"frequencies.parquet", "gene_metrics.parquet"} <= artifact_names


# ── the parquet ─────────────────────────────────────────────────────────────────────────────────


def test_allele_frequency_is_materialized_in_the_parquet_only(tmp_path: Path) -> None:
    spec = _spec(tmp_path, frequencies=True)
    compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    frame = pl.read_parquet(tmp_path / "out" / "frequencies.parquet")

    assert "allele_frequency" in frame.columns
    assert "allele_frequency" not in (spec / "frequencies.csv").read_text().splitlines()[0]
    row = frame.filter(
        (pl.col("variant_key") == _SICKLE) & (pl.col("population") == "afr")
    ).to_dicts()[0]
    assert row["allele_frequency"] == pytest.approx(row["allele_count"] / row["allele_number"])
    assert row["faf95"] == pytest.approx(0.04815774)


def test_manifest_blocks_summarize_the_sidecars(tmp_path: Path) -> None:
    result = compile_module(
        _spec(tmp_path, frequencies=True, gene_metrics=True), tmp_path / "out",
        resolve_with_ensembl=False,
    )
    freq, genes = result.manifest.frequency, result.manifest.gene_metrics
    assert freq.row_count == 3 and freq.variant_count == 2
    assert freq.datasets == ["gnomad_v4.1_joint"]
    assert freq.populations == ["global", "afr"]      # canonical order, not alphabetical
    assert genes.genes == ["HBB", "MTHFR"]
    assert genes.datasets == ["gnomad_v4.1_constraint"]

    # The recorded signatures are the producer-independent fact-hashes, recomputable by a consumer.
    with (tmp_path / "spec_11" / "frequencies.csv").open(newline="") as handle:
        rows = [FrequencyRow(**{k: (v or None) for k, v in r.items()}) for r in csv.DictReader(handle)]
    assert freq.signature == frequency_signature(rows)
    assert genes.signature is not None and genes.signature.startswith("sha256:")


def test_fact_signature_ignores_provenance_but_not_the_dataset(tmp_path: Path) -> None:
    """The two halves of what `dataset`-in-the-fact-set is for."""
    base = dict(variant_key="k", population="global", allele_count=1, allele_number=10)
    same_facts_other_producer = [
        FrequencyRow(**base, dataset="gnomad_v4.1_joint", source="gnomad", fetched_at="2026-01-01"),
    ]
    hand_filled = [FrequencyRow(**base, dataset="gnomad_v4.1_joint", source="manual")]
    other_release = [FrequencyRow(**base, dataset="gnomad_v2.1.1_joint", source="gnomad")]

    assert frequency_signature(same_facts_other_producer) == frequency_signature(hand_filled)
    assert frequency_signature(other_release) != frequency_signature(hand_filled)


# ── round-trip (Principle 7) ────────────────────────────────────────────────────────────────────


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec(tmp_path, frequencies=True, gene_metrics=True)
    first = compile_module(spec, tmp_path / "o1", resolve_with_ensembl=False)
    reverse_module(tmp_path / "o1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "o2", resolve_with_ensembl=False)

    assert second.success, second.errors
    assert (tmp_path / "rev" / "frequencies.csv").exists()
    assert (tmp_path / "rev" / "gene_metrics.csv").exists()
    # The recomputable column must NOT come back as an authored one.
    header = (tmp_path / "rev" / "frequencies.csv").read_text().splitlines()[0]
    assert "allele_frequency" not in header
    for name in ("frequencies.parquet", "gene_metrics.parquet"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.frequency.signature == second.manifest.frequency.signature
    assert first.manifest.gene_metrics.signature == second.manifest.gene_metrics.signature


def test_compiling_twice_is_byte_identical(tmp_path: Path) -> None:
    spec = _spec(tmp_path, frequencies=True, gene_metrics=True)
    a = compile_module(spec, tmp_path / "a", resolve_with_ensembl=False)
    b = compile_module(spec, tmp_path / "b", resolve_with_ensembl=False)
    assert a.manifest.artifact.digest == b.manifest.artifact.digest


# ── cross-checks ────────────────────────────────────────────────────────────────────────────────


def test_orphan_sidecar_rows_warn_but_do_not_fail(tmp_path: Path) -> None:
    """An over-broad sidecar is harmless; failing the compile would punish the author for it."""
    spec = _spec(tmp_path, frequencies=True, gene_metrics=True)
    (spec / "frequencies.csv").write_text(
        _FREQUENCIES
        + "9:99:A:G,,9,99,A,G,GRCh38,global,1,10,,,,gnomad_v4.1_joint,,,gnomad,resolved,\n"
    )
    (spec / "gene_metrics.csv").write_text(
        _GENE_METRICS
        + "NOTINMODULE,ENSG00000000003,ENST3,true,0.1,1.0,0.9,0.5,0.1,0.1,0.1,0.9,1,1.1,,"
        "gnomad_v4.1_constraint,gnomad-constraint,resolved,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success
    assert any("9:99:A" in w for w in result.warnings)
    assert any("NOTINMODULE" in w for w in result.warnings)


def test_invalid_sidecar_row_is_a_compile_error(tmp_path: Path) -> None:
    spec = _spec(tmp_path, frequencies=True)
    (spec / "frequencies.csv").write_text(
        _FREQUENCIES.replace("global,4272", "GLOBAL WITH SPACES,4272")
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not result.success
    assert any("population" in e for e in result.errors)


# ── the VRS verify pass ─────────────────────────────────────────────────────────────────────────


def _with_resolution(tmp_path: Path, vrs_id: str, *, alts: str = "A", ref: str = "T") -> Path:
    spec = tmp_path / f"spec_vrs_{abs(hash((vrs_id, alts, ref)))}"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,caid,"
        "source,status\n"
        f"{_SICKLE},rs334,11,5227002,{ref},{alts},GRCh38,0,{vrs_id},2.0,CA125138,gnomad,resolved\n"
    )
    return spec


def test_a_correct_vrs_id_verifies(tmp_path: Path) -> None:
    spec = _with_resolution(tmp_path, _SICKLE)
    assert compile_module(spec, tmp_path / "ok").success


def test_a_tampered_substitution_id_hard_fails_in_both_modes(tmp_path: Path) -> None:
    """A substitution's VA is deterministic here, so a mismatch can only be corruption."""
    spec = _with_resolution(tmp_path, _MTHFR)  # right shape, wrong allele
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"bad_{strict}", strict=strict)
        assert not result.success
        assert any("does not match the id recomputed" in e for e in result.errors)


def test_an_indel_id_warns_in_best_effort_and_fails_in_strict(tmp_path: Path) -> None:
    """It cannot be recomputed without a sequence proxy, so severity follows the mode.

    best_effort carries it and says so; strict refuses to ship an identity it cannot confirm. Note the
    wording the assertions pin: the finding is *unverifiable*, never a "mismatch" — nothing was
    compared, so no verdict was reached.
    """
    indel_id = "ga4gh:VA.LNB3XTeT4xdXxnKyg_RjJhLp5RnUlMpL"
    spec = _with_resolution(tmp_path, indel_id, ref="C", alts="CA")

    lenient = compile_module(spec, tmp_path / "lenient", strict=False)
    assert lenient.success
    assert any("could not be verified" in w for w in lenient.warnings)

    strict = compile_module(spec, tmp_path / "strict", strict=True)
    assert not strict.success
    assert any("cannot confirm" in e for e in strict.errors)


def test_rows_without_a_vrs_id_are_simply_not_checked(tmp_path: Path) -> None:
    spec = _with_resolution(tmp_path, "")
    assert compile_module(spec, tmp_path / "none", strict=True).success


# ── the ref-disagreement guard the VA switch made necessary ─────────────────────────────────────


def test_two_rows_disagreeing_on_the_reference_base_are_an_error(tmp_path: Path) -> None:
    """A VA addresses the place and the alt, not the ref — so this collision is newly possible.

    The reference base at a position is a single fact, so at most one of these rows can be right;
    catching it preserves the diagnosis the old `chrom:start:ref:alts` key gave for free.
    """
    spec = tmp_path / "spec_ref"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion\n"
        "11,5227002,T,A,A/T,risk,correct ref\n"
        "11,5227002,C,A,A/C,risk,wrong ref at the same place\n"
    )
    (spec / "studies.csv").write_text(_STUDIES)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not result.success
    assert any("Inconsistent reference allele" in e for e in result.errors)


# ── the full VRS verify matrix (every branch, both modes) ───────────────────────────────────────


def _res_row(**kw):
    from just_dna_format.resolution import ResolutionRow
    base = dict(variant_key="k", chrom="11", start=5227002, ref="T", alts="A")
    return ResolutionRow(**{**base, **kw})


_WRONG_ALLELE = _MTHFR  # a well-formed VA, but for a different allele


@pytest.mark.parametrize(
    ("label", "row_kwargs", "best_effort", "strict"),
    [
        # (outcome in best_effort, outcome in strict): "pass" | "warn" | "error"
        ("no vrs_id — nothing to check",
         dict(vrs_id=None), "pass", "pass"),
        ("correct substitution — verified",
         dict(vrs_id=_SICKLE), "pass", "pass"),
        ("tampered substitution — deterministic, so corruption",
         dict(vrs_id=_WRONG_ALLELE), "error", "error"),
        ("indel — needs a sequence proxy, so unverifiable",
         dict(ref="C", alts="CA", vrs_id=_SICKLE), "warn", "error"),
        ("multi-allelic — a VA names one allele",
         dict(alts="A,G", vrs_id=_SICKLE), "warn", "error"),
        ("position-only — no ALT to name",
         dict(alts=None, vrs_id=_SICKLE), "warn", "error"),
        ("no coordinate — nothing to recompute from",
         dict(chrom=None, start=None, vrs_id=_SICKLE), "warn", "error"),
        ("off-assembly contig — no refget accession",
         dict(chrom="GL000009.2", start=100, vrs_id=_SICKLE), "warn", "error"),
        ("position past the end of the contig",
         dict(chrom="MT", start=999999, vrs_id=_SICKLE), "warn", "error"),
        ("non-GRCh38 build — no refget table (must not raise)",
         dict(genome_build="GRCh37", vrs_id=_SICKLE), "warn", "error"),
    ],
)
def test_vrs_verify_matrix(label: str, row_kwargs: dict, best_effort: str, strict: str) -> None:
    """Three outcomes, never conflated: verified / mismatch / **unverifiable**.

    The distinction the table encodes is that an indel is *never* reported as a mismatch — this tier
    cannot recompute one, so it can only say it did not check. `strict` refuses such a row because
    "unchecked" and "correct" are different things; `best_effort` carries it and says so.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids

    for mode, expected in (("best_effort", best_effort), ("strict", strict)):
        errors, warnings = _verify_vrs_ids([_res_row(**row_kwargs)], strict=(mode == "strict"))
        actual = "error" if errors else ("warn" if warnings else "pass")
        assert actual == expected, f"{label} in {mode}: expected {expected}, got {actual}"


def test_unverifiable_never_reported_as_a_mismatch() -> None:
    """Wording matters here: claiming a mismatch would assert a verdict that was never reached."""
    from just_dna_compiler.compiler import _verify_vrs_ids

    _errors, warnings = _verify_vrs_ids(
        [_res_row(ref="C", alts="CA", vrs_id=_SICKLE)], strict=False
    )
    assert "could not be verified" in warnings[0]
    assert "does not match" not in warnings[0]


def test_a_non_grch38_row_with_a_vrs_id_does_not_abort_the_compile(tmp_path: Path) -> None:
    """Regression: `refget_accession` *raises* for an unsupported build, and that escaped the verify
    pass — one unverifiable row crashed the whole compile instead of warning."""
    spec = _with_resolution(tmp_path, _SICKLE)
    text = (spec / "resolution.csv").read_text().replace("GRCh38,0", "GRCh37,0")
    (spec / "resolution.csv").write_text(text)
    result = compile_module(spec, tmp_path / "b37")
    assert result.success
    assert any("could not be verified" in w for w in result.warnings)


def test_verify_warnings_reach_the_manifest(tmp_path: Path) -> None:
    """An unverified identity has to be visible to a consumer, not just on someone's terminal."""
    spec = _with_resolution(tmp_path, _SICKLE, ref="C", alts="CA")
    result = compile_module(spec, tmp_path / "warned")
    assert result.success
    assert any("could not be verified" in w for w in result.manifest.compilation.warnings)


# ── validate-by-redundancy: the sidecars' numbers constrain each other ───────────────────────────


def _freq_csv(*rows: str) -> str:
    header = (
        "variant_key,rsid,chrom,start,ref,alt,genome_build,population,allele_count,allele_number,"
        "homozygote_count,hemizygote_count,faf95,dataset,vrs_id,caid,source,status,fetched_at\n"
    )
    return header + "".join(rows)


def _freq_row(ac: str, an: str, hom: str = "", faf: str = "") -> str:
    return (
        f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,afr,{ac},{an},{hom},,{faf},"
        f"gnomad_v4.1_joint,,,gnomad,resolved,\n"
    )


def test_allele_count_above_allele_number_is_an_error(tmp_path: Path) -> None:
    """Exact integer arithmetic: a count cannot exceed its own denominator."""
    spec = _spec(tmp_path, frequencies=True)
    (spec / "frequencies.csv").write_text(_freq_csv(_freq_row("500", "100")))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not result.success
    assert any("exceeds allele_number" in e for e in result.errors)


def test_impossible_homozygote_count_is_an_error(tmp_path: Path) -> None:
    """Each homozygote contributes two alleles, so 2·hom can never exceed AC."""
    spec = _spec(tmp_path, frequencies=True)
    (spec / "frequencies.csv").write_text(_freq_csv(_freq_row("10", "100", hom="6")))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not result.success
    assert any("contributes two" in e for e in result.errors)


def test_faf95_above_the_point_estimate_warns(tmp_path: Path) -> None:
    """A 95% CI *lower bound* sitting above the point estimate is suspicious but not impossible-by-
    arithmetic (the two can be computed on different denominators), so it warns rather than fails."""
    spec = _spec(tmp_path, frequencies=True)
    (spec / "frequencies.csv").write_text(_freq_csv(_freq_row("10", "1000", faf="0.5")))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success
    assert any("faf95" in w and "lower bound" in w for w in result.warnings)


def test_real_recorded_numbers_pass_every_arithmetic_check() -> None:
    """The checks must not fire on genuine gnomAD output — verified against the recorded payload.

    A redundancy check that flags real data is worse than no check, so this reads the committed
    recording rather than a hand-made row.
    """
    import json

    from just_dna_compiler.compiler import _check_frequency_arithmetic
    from just_dna_enricher.gnomad import _populations_from_joint

    assets = Path(__file__).resolve().parents[2] / "assets"
    joint = json.loads((assets / "gnomad_v4.1_variant_payload.json").read_text())
    rows = [
        FrequencyRow(variant_key=_SICKLE, alt="A", dataset="gnomad_v4.1_joint", **entry)
        for entry in _populations_from_joint(joint["data"]["sickle"]["joint"])
    ]
    assert rows, "fixture should yield population rows"
    errors, warnings = _check_frequency_arithmetic(rows)
    assert (errors, warnings) == ([], [])


def test_gene_metrics_redundancy_catches_a_mismapped_column(tmp_path: Path) -> None:
    """`oe_lof` is by definition `obs_lof / exp_lof`, so the three columns cross-check each other —
    which is what catches a column-mapping slip in a builder."""
    spec = _spec(tmp_path, gene_metrics=True)
    (spec / "gene_metrics.csv").write_text(
        "gene,gene_id,transcript,mane_select,pli,loeuf,oe_lof,oe_lof_lower,lof_z,mis_z,syn_z,oe_mis,"
        "obs_lof,exp_lof,constraint_flags,dataset,source,status,fetched_at\n"
        # obs/exp = 140/175 = 0.8, but oe_lof claims 0.2
        "HBB,ENSG1,ENST1,true,0.02,0.9,0.2,0.1,0.3,0.9,0.1,0.95,140,175,,"
        "gnomad_v4.1_constraint,gnomad-constraint,resolved,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success   # advisory, not fatal
    assert any("same quantity" in w for w in result.warnings)


def test_gene_metrics_interval_must_bracket_the_point_estimate(tmp_path: Path) -> None:
    spec = _spec(tmp_path, gene_metrics=True)
    (spec / "gene_metrics.csv").write_text(
        "gene,gene_id,transcript,mane_select,pli,loeuf,oe_lof,oe_lof_lower,lof_z,mis_z,syn_z,oe_mis,"
        "obs_lof,exp_lof,constraint_flags,dataset,source,status,fetched_at\n"
        "HBB,ENSG1,ENST1,true,0.02,0.5,0.9,0.1,0.3,0.9,0.1,0.95,,,,"
        "gnomad_v4.1_constraint,gnomad-constraint,resolved,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert any("outside its own interval" in w for w in result.warnings)
