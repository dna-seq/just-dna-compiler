"""The 0.5 derived-fact sidecars in the compiler: digest safety, round-trip, cross-checks, verify.

The two properties that matter most are opposites of each other, and both are pinned here:

* adding a sidecar must leave the SNP core's bytes **completely unchanged** (it is additive — a
  consumer that does not want frequencies must not see a different `weights.parquet`); and
* the sidecar's own parquet must enter `artifact.digest`, because a module carrying frequency data
  genuinely is different content from one that does not.
"""

import csv
import hashlib
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.frequency import FrequencyRow
from just_dna_format.integrity import frequency_signature, source_signature
from just_dna_format.layout import preferred_spelling
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
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
_SICKLE_G = derive_vrs_allele_id("11", 5227002, "T", "G")  # the same site's other ALT
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


# One row per cited article, not per variant — the grain that distinguishes this sidecar from the
# other two. The `quotes_found` cell for the paywalled citation is deliberately EMPTY (null = never
# checked), not 0 (checked, absent); several assertions below turn on that difference.
_LITERATURE = (
    "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
    "12345678,10.1234/2013/999990,,true,false,1,,pubmed,resolved,\n"
    "23456789,10.1000/example,PMC1234567,true,true,1,1,pubmed,resolved,\n"
)


def _spec(
    tmp_path: Path,
    *,
    frequencies: bool = False,
    gene_metrics: bool = False,
    literature: bool = False,
    sources: str | None = None,
    license: str | None = None,
) -> Path:
    # Deterministic directory name: `hash()` is per-process randomized for str, which would make the
    # path differ run to run for no reason.
    variant = hashlib.sha256(f"{sources}|{license}".encode()).hexdigest()[:8]
    spec = tmp_path / (
        f"spec_{int(frequencies)}{int(gene_metrics)}{int(literature)}_{variant}"
    )
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(
        _YAML + (f"license: {license}\n" if license else "")
    )
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if frequencies:
        (spec / "frequencies.csv").write_text(_FREQUENCIES)
    if gene_metrics:
        (spec / "gene_metrics.csv").write_text(_GENE_METRICS)
    if literature:
        (spec / "literature.csv").write_text(_LITERATURE)
    if sources is not None:
        (spec / "sources.csv").write_text(sources)
    return spec


# ── additive: the SNP core does not move ────────────────────────────────────────────────────────


def test_sidecars_leave_the_snp_core_byte_identical(tmp_path: Path) -> None:
    bare = compile_module(_spec(tmp_path), tmp_path / "o_bare", resolve_with_ensembl=False)
    rich = compile_module(
        _spec(tmp_path, frequencies=True, gene_metrics=True, literature=True),
        tmp_path / "o_rich", resolve_with_ensembl=False,
    )
    assert bare.success and rich.success, (bare.errors, rich.errors)
    for name in ("weights.parquet", "annotations.parquet", "studies.parquet"):
        assert (tmp_path / "o_bare" / name).read_bytes() == (tmp_path / "o_rich" / name).read_bytes()
    # ...but the artifact identity DOES differ, because the module genuinely carries more content.
    assert bare.manifest.artifact.digest != rich.manifest.artifact.digest
    assert bare.manifest.frequency is None and bare.manifest.gene_metrics is None
    assert bare.manifest.literature is None


def test_sidecar_csvs_are_not_hashed_as_raw_inputs(tmp_path: Path) -> None:
    """They are fact-hashed like `resolution.csv`, not byte-hashed like an authored CSV.

    Byte-hashing a multi-producer table would make a reverse→recompile cycle "change the hash" over
    nothing but column order and timestamps.
    """
    result = compile_module(
        _spec(tmp_path, frequencies=True, gene_metrics=True, literature=True), tmp_path / "out",
        resolve_with_ensembl=False,
    )
    input_names = {entry.name for entry in result.manifest.inputs}
    assert not {"frequencies.csv", "gene_metrics.csv", "literature.csv"} & input_names
    artifact_names = {entry.name for entry in result.manifest.artifact.files}
    assert {"frequencies.parquet", "gene_metrics.parquet", "literature.parquet"} <= artifact_names


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
    spec = _spec(tmp_path, frequencies=True, gene_metrics=True)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    freq, genes = result.manifest.frequency, result.manifest.gene_metrics
    assert freq.row_count == 3 and freq.variant_count == 2
    assert freq.datasets == ["gnomad_v4.1_joint"]
    assert freq.populations == ["global", "afr"]      # canonical order, not alphabetical
    assert genes.genes == ["HBB", "MTHFR"]
    assert genes.datasets == ["gnomad_v4.1_constraint"]

    # The recorded signatures are the producer-independent fact-hashes, recomputable by a consumer.
    with (spec / "frequencies.csv").open(newline="") as handle:
        rows = [FrequencyRow(**{k: (v or None) for k, v in r.items()}) for r in csv.DictReader(handle)]
    assert freq.signature == frequency_signature(rows)
    assert genes.signature is not None and genes.signature.startswith("sha256:")


def test_fact_signature_ignores_provenance_but_not_the_dataset(tmp_path: Path) -> None:
    """The two halves of what `dataset`-in-the-fact-set is for."""
    base = {"variant_key": "k", "population": "global", "allele_count": 1, "allele_number": 10}
    same_facts_other_producer = [
        FrequencyRow(**base, dataset="gnomad_v4.1_joint", source="gnomad", fetched_at="2026-01-01"),
    ]
    hand_filled = [FrequencyRow(**base, dataset="gnomad_v4.1_joint", source="manual")]
    other_release = [FrequencyRow(**base, dataset="gnomad_v2.1.1_joint", source="gnomad")]

    assert frequency_signature(same_facts_other_producer) == frequency_signature(hand_filled)
    assert frequency_signature(other_release) != frequency_signature(hand_filled)


# ── round-trip (Principle 7) ────────────────────────────────────────────────────────────────────


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec(tmp_path, frequencies=True, gene_metrics=True, literature=True)
    first = compile_module(spec, tmp_path / "o1", resolve_with_ensembl=False)
    reverse_module(tmp_path / "o1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "o2", resolve_with_ensembl=False)

    assert second.success, second.errors
    for name in ("frequencies.csv", "gene_metrics.csv", "literature.csv"):
        assert (tmp_path / "rev" / name).exists()
    # The recomputable column must NOT come back as an authored one.
    header = (tmp_path / "rev" / "frequencies.csv").read_text().splitlines()[0]
    assert "allele_frequency" not in header
    for name in ("frequencies.parquet", "gene_metrics.parquet", "literature.parquet"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.frequency.signature == second.manifest.frequency.signature
    assert first.manifest.gene_metrics.signature == second.manifest.gene_metrics.signature
    assert first.manifest.literature.signature == second.manifest.literature.signature


# ── the citation sidecar's own properties ───────────────────────────────────────────────────────


def test_the_literature_block_never_reports_unchecked_quotes_as_missing(tmp_path: Path) -> None:
    """The counter that would be easiest to get wrong, and the most misleading if it were.

    The fixture authors one quote per citation, of which only the open-access one could be checked.
    `quotes_found` must be 1 of 2 authored with 1 open-access article — NOT 1 of 2 read as "half the
    quotes are wrong", which is what summing a null as zero would imply.
    """
    result = compile_module(
        _spec(tmp_path, literature=True), tmp_path / "out", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    block = result.manifest.literature
    assert (block.row_count, block.resolved_count, block.missing_count) == (2, 2, 0)
    assert block.open_access_count == 1
    assert (block.quotes_authored, block.quotes_found) == (2, 1)
    # The unchecked quote is legible as unchecked: authored − found equals the non-open-access count.
    assert block.quotes_authored - block.quotes_found == block.row_count - block.open_access_count
    # And it is stated rather than only inferable from the arithmetic above (S56).
    assert block.quotes_unchecked == 1


def test_a_module_where_nothing_was_checked_does_not_publish_a_confident_zero(tmp_path: Path) -> None:
    """S56's second half: the per-row guard is right and does not survive the aggregation.

    `quotes_found` sums the rows that answered, so over rows that are *all* null the sum is 0 — which
    is the exact sentence `_literature_block`'s docstring calls the most misleading thing it could
    say, arriving one aggregation later. Reproduced here as the state four published modules are in:
    two quotes authored, no fulltext ever retrieved. `quotes_unchecked` is what separates it from a
    module where both quotes were checked and neither was found.
    """
    spec = _spec(tmp_path, literature=True)
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
        "12345678,10.1234/2013/999990,,true,false,1,,pubmed,resolved,\n"
        "23456789,10.1000/example,,true,false,1,,pubmed,resolved,\n",
        encoding="utf-8",
    )
    nothing_checked = compile_module(spec, tmp_path / "a", resolve_with_ensembl=False)
    assert nothing_checked.success, nothing_checked.errors
    block = nothing_checked.manifest.literature
    assert (block.quotes_authored, block.quotes_found) == (2, 0)
    assert block.quotes_unchecked == 2

    # The module it must not be confusable with: both checked, neither found.
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
        "12345678,10.1234/2013/999990,PMC999990,true,true,1,0,pubmed,resolved,\n"
        "23456789,10.1000/example,PMC1234567,true,true,1,0,pubmed,resolved,\n",
        encoding="utf-8",
    )
    checked_and_missing = compile_module(spec, tmp_path / "b", resolve_with_ensembl=False)
    assert checked_and_missing.success, checked_and_missing.errors
    other = checked_and_missing.manifest.literature
    assert (other.quotes_authored, other.quotes_found) == (2, 0)
    assert other.quotes_unchecked == 0
    # Identical on the pair a reader would look at; separated only by the new counter.
    assert (block.quotes_authored, block.quotes_found) == (other.quotes_authored, other.quotes_found)
    assert block.quotes_unchecked != other.quotes_unchecked


def test_a_nonexistent_citation_recorded_by_the_enricher_surfaces_at_compile(tmp_path: Path) -> None:
    """The compiler cannot ask PubMed anything, but the enricher already wrote down the verdict —
    so an offline compile can still tell the author their citation does not resolve."""
    spec = _spec(tmp_path, literature=True)
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at\n"
        "12345678,,,false,,,,pubmed,not_found,\n"
        "23456789,,,true,,,,pubmed,resolved,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success                                  # a warning, not a refusal
    assert any("PubMed has no record of" in w for w in result.warnings)
    assert result.manifest.literature.missing_count == 1


def test_an_uncited_citation_is_reported_and_left_out_of_the_artifact(tmp_path: Path) -> None:
    """RM79: dead weight is discarded at compile, and `literature.csv` keeps it.

    `literature.csv` is merge-not-clobber, so a citation the author has since deleted from
    `studies.csv` leaves its row behind — that pin is what makes a re-run cheap and it stays. What
    changed is that the row no longer travels into the parquet or the manifest, where nothing joins
    to it.

    **What this settles is a disagreement between two honest counters.**
    `manifest.literature.missing_count` counted `exists is False` over every row in the table while
    the `citation_existence` verification record counted the module's *current* citations, so the two
    could differ in a published manifest with nothing wrong in the module. Filtering makes them the
    same subject by construction rather than documenting a discrepancy a reader must reconcile.
    """
    spec = _spec(tmp_path, literature=True)
    (spec / "literature.csv").write_text(
        _LITERATURE + "34567890,,,true,,,,pubmed,resolved,\n"
    )
    before = (spec / "literature.csv").read_bytes()
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)

    assert result.success                                   # a warning, not a refusal
    warning = next(w for w in result.warnings if "no study or bin in this module cites" in w)
    assert "34567890" in warning
    # The warning reports an action taken, not a nag about a file the author should tidy.
    assert "left out of the artifact" in warning

    # The artifact carries the cited rows only — computed from the fixture rather than hardcoded, so
    # adding a row to `_LITERATURE` cannot quietly turn this into a weaker assertion.
    import csv as _csv

    with (spec / "studies.csv").open() as handle:
        cited = {row["pmid"] for row in _csv.DictReader(handle)}
    kept = pl.read_parquet(tmp_path / "out" / "literature.parquet")
    assert set(kept["pmid"].to_list()) == cited
    assert result.manifest.literature.row_count == len(cited)
    assert "34567890" not in kept["pmid"].to_list()
    # … and the CSV is byte-identical, because that is the pin.
    assert (spec / "literature.csv").read_bytes() == before


def test_a_module_that_cites_nothing_keeps_its_whole_literature_table(tmp_path: Path) -> None:
    """The guard that stops the filter emptying a table it cannot judge.

    With no citation anywhere, "the sidecar is stale" and "the citations are not authored yet" are
    indistinguishable, and discarding on the first reading would delete an entire enrichment pass's
    output. The orphan check has always had this guard; the filter inherits it rather than
    re-deriving it.
    """
    from just_dna_compiler.compiler import split_cited_literature
    from just_dna_format.literature import LiteratureRow

    rows = [LiteratureRow(pmid="29165669", exists=True), LiteratureRow(pmid="34567890", exists=True)]
    kept, dropped = split_cited_literature(rows, [], {})
    assert [r.pmid for r in kept] == ["29165669", "34567890"] and dropped == []


def test_the_literature_fact_hash_ignores_open_access_and_coverage(tmp_path: Path) -> None:
    """An embargo lifting must not move a module's signature — nothing about the module changed.

    This is the concrete reason `is_open_access` and the quote counters sit outside the fact set.
    """
    from just_dna_format.integrity import literature_signature
    from just_dna_format.literature import LiteratureRow

    base = {"pmid": "29165669", "doi": "10.1093/nar/gkx1153", "pmcid": "PMC5753237", "exists": True}
    before = [LiteratureRow(**base, is_open_access=False, quotes_authored=1, quotes_found=None)]
    after = [LiteratureRow(**base, is_open_access=True, quotes_authored=1, quotes_found=1,
                           source="pubmed", fetched_at="2026-08-01T00:00:00Z")]
    assert literature_signature(before) == literature_signature(after)

    # ...but a different article genuinely is different content.
    other = [LiteratureRow(**{**base, "doi": "10.9999/other"})]
    assert literature_signature(other) != literature_signature(before)


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


def test_an_indel_id_warns_in_both_modes_and_is_never_duplicated(tmp_path: Path) -> None:
    """An indel's id cannot be recomputed without a sequence proxy — a limit of this tier, not a defect.

    So it warns in `best_effort` *and* in `strict`, which is the repair for a real regression: minting
    indel ids online is what `just-dna-enricher` is for, and while this escalated under `--strict` the
    enricher produced modules its own compiler refused. Two reference examples stopped compiling in the
    mode their READMEs document. `strict` means *reproducible artifact* — these bytes are injected and
    the compile is deterministic, so the artifact reproduces perfectly; only the verification is out of
    reach, and the remedies the old error offered were to lower the guarantee or delete a correct id.

    The assertions also pin the wording (*unverifiable*, never a "mismatch" — nothing was compared, so
    no verdict was reached) and the count, because the pass runs twice: once in the `validate_spec`
    pre-flight `compile_module` performs, once on its own resolved rows.
    """
    indel_id = "ga4gh:VA.LNB3XTeT4xdXxnKyg_RjJhLp5RnUlMpL"
    spec = _with_resolution(tmp_path, indel_id, ref="C", alts="CA")

    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
        assert result.success, result.errors
        unverifiable = [w for w in result.warnings if "could not be verified" in w]
        assert len(unverifiable) == 1, unverifiable
        assert "not a single-base substitution" in unverifiable[0]
        assert "does not match" not in unverifiable[0]


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
    base = {"variant_key": "k", "chrom": "11", "start": 5227002, "ref": "T", "alts": "A"}
    return ResolutionRow(**{**base, **kw})


_WRONG_ALLELE = _MTHFR  # a well-formed VA, but for a different allele


@pytest.mark.parametrize(
    ("label", "row_kwargs", "outcome"),
    [
        # "pass" | "warn" | "error" — and it is ONE column, not one per mode, which is the property
        # this table now pins: severity here follows whose limit the finding is, never the mode.
        ("no vrs_id — nothing to check",
         {"vrs_id": None}, "pass"),
        ("correct substitution — verified",
         {"vrs_id": _SICKLE}, "pass"),
        ("tampered substitution — deterministic, so corruption",
         {"vrs_id": _WRONG_ALLELE}, "error"),
        # ---- the tier's own limits: warnings, in both modes -------------------------------------
        # Each of these is unverifiable because *this compiler* cannot reach a reference sequence, and
        # no edit an author could make to the module would change that. They used to be errors under
        # `--strict`, which made the enricher's own online indel minting produce artifacts its own
        # compiler refused (`pathogenic_clinvar`: 185 alleles; `shox_par1`: 2).
        ("indel — needs a sequence proxy, so unverifiable",
         {"ref": "C", "alts": "CA", "vrs_id": _SICKLE}, "warn"),
        ("off-assembly contig — no refget accession",
         {"chrom": "GL000009.2", "start": 100, "vrs_id": _SICKLE}, "warn"),
        ("position past the end of the contig",
         {"chrom": "MT", "start": 999999, "vrs_id": _SICKLE}, "warn"),
        ("non-GRCh38 build — no refget table (must not raise)",
         {"genome_build": "GRCh37", "vrs_id": _SICKLE}, "warn"),
        # A symbolic allele with a *stored* id moved out of this block in R2-5 — see the error section
        # below. Its **absence** is still the tier's limit and still lives here, which is the whole
        # asymmetry: an unminted id on such a row is honest, and a recorded one is a false claim.
        # `*` (RM59) joins them, one axis over (R2-6). Not a variant at all — it records that an
        # overlapping deletion left the position uncallable in the sample — so there is no sequence to
        # digest, and the indel branch it used to fall into offers a remedy (re-run online) that can
        # never apply. Same severity as its neighbours, and the *stored*-id question the symbolic
        # branch records is identical here and equally not answered by this row.
        ("unobservable-allele marker — the callability axis, not a gap in the identity scheme",
         {"alts": "*", "vrs_id": _SICKLE}, "warn"),
        # ---- the row contradicting itself: errors, in both modes ---------------------------------
        # Not a limit of this tier. The row asserts an identity while withholding the very thing that
        # identity is a digest of, so nothing anywhere could ever check it.
        ("position-only — an id recorded against no ALT",
         {"alts": None, "vrs_id": _SICKLE}, "error"),
        ("no coordinate — an id recorded against no place",
         {"chrom": None, "start": None, "vrs_id": _SICKLE}, "error"),
        # R2-5, settled 2026-08-15. Tier-blame is for a finding **no authored edit could clear** (P5),
        # and deleting the cell clears this one — which is the test it was failing while filed there.
        # Nothing mints a VA for a symbolic allele, so a recorded one names a *different* allele: a
        # false content-addressed claim, catchable offline, exactly this block's shape. Gated until now
        # on the minting question, now answered in the grammar — `validate_vrs_allele_id` makes the
        # column `ga4gh:VA.`-only, so a present id here cannot be anything but a VA for another allele.
        ("symbolic allele with a stored id — an id for an allele that has no content to address",
         {"ref": "N", "alts": "<DEL:4977>", "vrs_id": _SICKLE}, "error"),
        # A multi-allelic site is now verified allele by allele. It used to be a blanket
        # "unverifiable" on the grounds that a VA names one allele — true, and the reason `vrs_id` is
        # a parallel array of `alts` rather than a scalar; with the pair aligned there is nothing left
        # to be unsure about, and 909 of 1,613 rows in a real module stop being unverifiable.
        ("multi-allelic, every allele named — verified",
         {"alts": "A,G", "vrs_id": f"{_SICKLE},{_SICKLE_G}"}, "pass"),
        ("multi-allelic with a hole — the named allele verifies, the hole is a non-event",
         {"alts": "A,CA", "vrs_id": f"{_SICKLE},"}, "pass"),
        ("multi-allelic, an id recorded against the indel member — unverifiable, not a mismatch",
         {"alts": "A,CA", "vrs_id": f"{_SICKLE},{_MTHFR}"}, "warn"),
        ("multi-allelic, right length and wrong order — the desync the count check cannot see",
         {"alts": "A,G", "vrs_id": f"{_SICKLE_G},{_SICKLE}"}, "error"),
    ],
)
def test_vrs_verify_matrix(label: str, row_kwargs: dict, outcome: str) -> None:
    """Three outcomes, never conflated: verified / mismatch / **unverifiable**.

    Two distinctions the table encodes. An indel is *never* reported as a mismatch — this tier cannot
    recompute one, so it can only say it did not check. And an unverifiable allele's severity comes
    from **whose limit** it is, not from the mode: the tier's own limits warn, a row that records an id
    against no ALT or no coordinate is an error. Both are mode-independent, which is why the expectation
    is a single column and the assertion runs it under both.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids

    errors, warnings = _verify_vrs_ids([_res_row(**row_kwargs)])
    actual = "error" if errors else ("warn" if warnings else "pass")
    assert actual == outcome, f"{label}: expected {outcome}, got {actual}"


def test_vrs_coverage_counts_alleles_and_groups_the_gaps_by_reason() -> None:
    """Absence is invisible to `_verify_vrs_ids` by design — this is the pass that sees it.

    Verification only ever looks at ids that are *there*, so a table where nothing was minted is
    reported as flawless. That was tolerable while a VA was decorative; it is not now that a consumer
    may key on one, and the number that matters is the *shortfall*, stated rather than implied.

    Denominator is alleles, not rows: the multi-allelic row below is two identities.
    """
    from just_dna_compiler.compiler import _vrs_coverage, _vrs_coverage_warnings

    rows = [
        _res_row(vrs_id=_SICKLE),                                   # named
        _res_row(alts="A,G", vrs_id=f"{_SICKLE},"),                 # one named, one hole
        _res_row(vrs_id=None),                                      # mintable, nobody minted it
        _res_row(ref="C", alts="CA", vrs_id=None),                  # indel: enricher's job
        _res_row(chrom=None, start=None, vrs_id=None),              # nothing to mint from
    ]
    alleles, identified, gaps = _vrs_coverage(rows)

    assert (alleles, identified) == (6, 2)
    assert sum(gaps.values()) == alleles - identified
    # Three *classes*, each once — not one line per row, and not one line per distinct allele pair.
    assert len(gaps) == 3
    assert any("computable offline" in reason for reason in gaps)
    assert any("indel or MNV" in reason for reason in gaps)
    assert any("no coordinate" in reason for reason in gaps)

    warnings = _vrs_coverage_warnings(rows)
    assert "2/6" in warnings[0] and "33%" in warnings[0]
    assert len(warnings) == 1 + len(gaps)


def test_a_symbolic_allele_is_its_own_gap_class_never_an_indel() -> None:
    """RM5 shipped the symbolic grammar in 0.6 and this pass was never told (D1-2, compiler half).

    The ledger quotes the *enricher's* copy of the same blind spot; this is the compiler's own, which
    says it in different words and is fixed on its own.

    `<DEL:4977>` fell through to the `is_substitution` branch and was reported as *"an indel or MNV:
    justification needs the reference sequence, so only the enricher can mint it (re-run it online)"*
    — false on every clause. A symbolic allele names a structural *event*, not a sequence, so there is
    nothing to justify against a reference and nothing for a content-addressed id to be a digest of:
    no id is mintable by any tier, online or off. The remedy it offered was the enricher run that
    crashed on the same allele (D1-1).

    Two classes here, not one bucket, because the remedies differ absolutely: an indel is one online
    enricher run away from an id, and a symbolic allele is permanently without one.
    """
    from just_dna_compiler.compiler import _vrs_coverage

    rows = [
        _res_row(ref="N", alts="<DEL:4977>", vrs_id=None),   # the MT common deletion, as authored
        _res_row(ref="C", alts="CA", vrs_id=None),           # a real indel: the enricher's job
    ]
    alleles, identified, gaps = _vrs_coverage(rows)

    assert (alleles, identified) == (2, 0)
    assert len(gaps) == 2, f"symbolic and indel must not share a bucket: {gaps}"
    symbolic = [reason for reason in gaps if "symbolic" in reason]
    assert len(symbolic) == 1, gaps
    reason = symbolic[0]
    assert "indel" not in reason and "MNV" not in reason
    # The half that made the old message actively harmful: it named a remedy, and the remedy is both
    # impossible and (at the time) a crash. Keyed on the remedy rather than on the word "online",
    # because the new line says "offline or online" — a denial of both, which is the sentence that
    # stops a reader trying the run the old one recommended.
    assert "re-run" not in reason and "enricher" not in reason


def test_the_unobservable_marker_is_its_own_gap_class_never_an_indel() -> None:
    """`*` had the symbolic blind spot one axis over, and it stopped being hypothetical (R2-6).

    0.6 gave the symbolic class its own permanent reason here and guarded `*` and `.` on the enricher
    side; neither of these two compiler functions was told, so a `*` reaching `resolution.csv`'s
    `alts` would have been reported as *"an indel or MNV … re-run it online"* — the same false class
    D1-2 had just fixed for symbolic alleles, with a remedy that can never work.

    Filed when it had no instantiation and upgraded when it turned out to have one: `*` **passes**
    `LiteralSequenceExpression`'s `^[A-Z*\\-]*$`, so before the enricher guard an unobservable allele
    reaching the minter would have been normalized and handed a content-addressed id for a state that
    is not a sequence. *"Nothing produces it today"* is a fact about the wiring, never the function.

    Three classes, not two: `*` is kept apart from the symbolic bucket by the P5 split the predicates
    already make — `parse_symbolic_allele` asks *which variant is this, unspelled*, while
    `is_unobservable_allele` asks *whether the call could see an allele at all*.
    """
    from just_dna_compiler.compiler import _vrs_coverage

    rows = [
        _res_row(alts="*", vrs_id=None),                    # the callability marker
        _res_row(ref="N", alts="<DEL:4977>", vrs_id=None),  # a structural event
        _res_row(ref="C", alts="CA", vrs_id=None),          # a real indel: the enricher's job
    ]
    alleles, identified, gaps = _vrs_coverage(rows)

    assert (alleles, identified) == (3, 0)
    assert len(gaps) == 3, f"the three classes must not share a bucket: {gaps}"
    unobservable = [reason for reason in gaps if "unobservable" in reason]
    assert len(unobservable) == 1, gaps
    reason = unobservable[0]
    # The half that made the old message harmful: it named a remedy, and the remedy cannot apply.
    assert "indel" not in reason and "MNV" not in reason, reason
    assert "online" not in reason and "re-run" not in reason, reason
    # …and it is not folded into the symbolic sentence either, which would answer a different question.
    assert "structural event" not in reason, reason

    # The *verify* side says the same thing, and it needs asserting separately: the severity matrix
    # above already read "warn" for this row before the fix, because the indel branch it fell into is
    # also `_BLAME_TIER` — so severity could not have caught this and only the reason can.
    from just_dna_compiler.compiler import _BLAME_TIER, _recompute_vrs_id

    recomputed, why, blame = _recompute_vrs_id(_res_row(alts="*", vrs_id=_SICKLE), "*")
    assert recomputed is None and blame == _BLAME_TIER
    assert "unobservable" in why and "indel" not in why and "MNV" not in why, why


def test_the_vrs_id_column_is_allele_ids_only() -> None:
    """The grammar question RM78's severity change was gated on, settled (R2-5).

    Both `vrs_id` columns are described as *"GA4GH VRS allele id (`ga4gh:VA.…`) — one per ALT"*, and
    only the lenient well-formedness check ran — so a `ga4gh:SL.…`, a *sequence-location* id naming a
    place rather than an allele, loaded cleanly and then failed downstream as a **mismatch**
    ("recomputed and different, so corruption"), which is an error in both modes with the wrong
    explanation. Tightening therefore makes no passing module fail; it moves a confident wrong
    diagnosis to load time and names the type it got.

    No instantiation, which is the test this repo applies to a tightening: nothing mints a non-VA into
    either column, and a probe across all sixteen reference examples found 844 ids, every one a VA.
    """
    from just_dna_format.frequency import FrequencyRow
    from just_dna_format.vrs import validate_vrs_id

    location_id = "ga4gh:SL." + _SICKLE.split(".", 1)[1]

    with pytest.raises(ValueError, match="allele id"):
        _res_row(vrs_id=location_id)
    with pytest.raises(ValueError, match="allele id"):
        FrequencyRow(variant_key="k", population="nfe", source="gnomad", vrs_id=location_id)
    # The message names the type it got, so the author is not left comparing digests.
    with pytest.raises(ValueError, match="SL id"):
        _res_row(vrs_id=location_id)

    # The lenient checker keeps its documented job — rejecting the malformed, not the unfamiliar —
    # because "is this a well-formed VRS id" and "may this column hold one" are different questions.
    assert validate_vrs_id(location_id) == location_id
    # …and a multi-allelic cell is checked member by member, so one bad member is enough.
    with pytest.raises(ValueError, match="allele id"):
        _res_row(alts="A,G", vrs_id=f"{_SICKLE},{location_id}")


def test_an_absent_id_on_a_symbolic_allele_stays_a_warning() -> None:
    """The asymmetry the R2-5 escalation must not flatten: absence is a limit, a claim is a claim.

    Escalating the *stored*-id case would be wrong to generalize. A symbolic allele with **no** id is
    the ordinary, correct state — no tier can mint one — so it stays a coverage warning in both modes,
    which is what keeps a structural module compilable. What changed is only the row that records an
    identity it cannot have.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids, _vrs_coverage_warnings

    row = _res_row(ref="N", alts="<DEL:4977>", vrs_id=None)
    errors, warnings = _verify_vrs_ids([row])
    assert errors == [] and warnings == []          # nothing recorded, so nothing to verify
    assert any("symbolic" in w for w in _vrs_coverage_warnings([row]))


def test_the_symbolic_gap_reason_is_one_constant_string() -> None:
    """Grouped by *class*, so two symbolic alleles are one line — the rule that keeps this readable.

    Interpolating the token would reproduce the 40-lines-each-naming-a-different-indel wall that
    `_vrs_gap_reason` exists to prevent, and a structural module carries many spellings at once.
    """
    from just_dna_compiler.compiler import _vrs_coverage

    _alleles, _identified, gaps = _vrs_coverage([
        _res_row(ref="N", alts="<DEL:4977>", vrs_id=None),
        _res_row(chrom="22", start=42126499, ref="A", alts="<DUP:16000>", vrs_id=None),
        _res_row(chrom="22", start=42126499, ref="A", alts="<CNV:TR:30>", vrs_id=None),
    ])
    assert len(gaps) == 1 and sum(gaps.values()) == 3


def test_a_symbolic_allele_on_a_non_grch38_module_reports_the_permanent_reason() -> None:
    """Both facts are true of this row; only one of them is permanent, and that is the one to print.

    A GRCh37 row has no refget table (RM15, a release away from being answered) *and* a symbolic ALT
    (never answerable). Telling its author to wait for multi-build minting would be advice for an
    allele that still has no id afterwards, so the symbolic branch sits ahead of the accession lookup
    in both `_vrs_gap_reason` and `_recompute_vrs_id` — the one branch those two functions must order
    identically, since they otherwise interleave their checks differently.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids, _vrs_coverage

    row = _res_row(ref="N", alts="<DEL:4977>", genome_build="GRCh37", vrs_id=None)
    _alleles, _identified, gaps = _vrs_coverage([row])
    assert len(gaps) == 1 and "symbolic" in next(iter(gaps))

    # A *stored* id on the same row is an error since R2-5 — the row's own contradiction rather than
    # the tier's limit — but the ordering property under test is unchanged and is what is asserted:
    # whichever channel it comes out of, the sentence must name the symbolic allele and not the build.
    errors, warnings = _verify_vrs_ids([_res_row(
        ref="N", alts="<DEL:4977>", genome_build="GRCh37", vrs_id=_SICKLE
    )])
    assert not warnings
    assert "symbolic" in errors[0] and "GRCh37" not in errors[0]
    # "minted upstream by the enricher" is the indel branch's promise and is false here.
    assert "enricher" not in errors[0]


def test_the_manifest_records_vrs_coverage_as_two_counts(tmp_path: Path) -> None:
    """Recorded, not only warned about: a terminal warning is gone by the time anything consumes this.

    Two counts rather than a ratio or a bool, for the same reason `fully_resolved` sits beside
    `resolution_mode`: a consumer deciding whether it can key on the VA needs the shortfall's size, and
    "complete" is then derived (`identified == alleles`) rather than stored twice. Both `0` means no
    resolution table was present — nothing attempted, which is not nothing achieved.
    """
    covered = compile_module(_with_resolution(tmp_path, _SICKLE), tmp_path / "c").manifest
    assert (covered.compilation.vrs_alleles, covered.compilation.vrs_alleles_identified) == (1, 1)

    gap = compile_module(
        _with_resolution(tmp_path, "", ref="C", alts="CA"), tmp_path / "g"
    ).manifest
    assert (gap.compilation.vrs_alleles, gap.compilation.vrs_alleles_identified) == (1, 0)

    bare = compile_module(_spec(tmp_path), tmp_path / "b", resolve_with_ensembl=False).manifest
    assert (bare.compilation.vrs_alleles, bare.compilation.vrs_alleles_identified) == (0, 0)


def test_full_vrs_coverage_says_nothing() -> None:
    """A complete table produces no line at all — a warning that always fires is not a warning."""
    from just_dna_compiler.compiler import _vrs_coverage_warnings

    assert _vrs_coverage_warnings([_res_row(vrs_id=_SICKLE)]) == []
    assert _vrs_coverage_warnings([]) == []


@pytest.mark.parametrize("strict", [False, True])
def test_a_coverage_gap_never_refuses_a_compile(tmp_path: Path, strict: bool) -> None:
    """Warning in both modes, and the reason is the same one that keeps `not_covered` out of strict.

    An indel offline and a build with no refget table are fixable by no authored edit, so refusing
    would make such a module uncompilable rather than telling its author anything. What `strict` does
    refuse is a stored id it cannot confirm — a claim, not an absence. Proven with a row that has no
    id at all *and* no way to mint one here.
    """
    spec = _with_resolution(tmp_path / ("s" if strict else "b"), "", ref="C", alts="CA")
    result = compile_module(spec, tmp_path / ("o" if strict else "ob"), strict=strict)

    assert result.success, result.errors
    assert any("VRS allele identity covers" in w for w in result.warnings)


def test_unverifiable_never_reported_as_a_mismatch() -> None:
    """Wording matters here: claiming a mismatch would assert a verdict that was never reached."""
    from just_dna_compiler.compiler import _verify_vrs_ids

    _errors, warnings = _verify_vrs_ids([_res_row(ref="C", alts="CA", vrs_id=_SICKLE)])
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


# ── the alleles a module names must be alleles its loci actually have ────────────────────────────


def _variant(**kw):
    from just_dna_format.spec import VariantRow

    base = {"genotype": "A/T", "state": "risk", "conclusion": "c"}
    return VariantRow(**{**base, **kw})


@pytest.mark.parametrize(
    ("label", "variant_kwargs", "table", "expected"),
    [
        ("authored alleles agree with the genotype",
         {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A"}, {}, "pass"),
        ("authored alleles contradict the genotype",
         {"chrom": "11", "start": 5227002, "ref": "C", "alts": "G"}, {}, "finding"),
        # The motivating real-world bug: a paper reports alleles on the gene's strand while dbSNP
        # reports the forward strand, so `A/G` gets authored at a `C>T` locus. Complementing the
        # genotype gives exactly {T,C} — which is why it looks plausible and compiles clean today.
        ("strand-flipped genotype (A/G authored at a C>T locus)",
         {"chrom": "11", "start": 5227002, "ref": "C", "alts": "T", "genotype": "A/G"}, {}, "finding"),
        ("hemizygous single allele, present",
         {"chrom": "MT", "start": 100, "ref": "A", "alts": "T", "genotype": "T"}, {}, "pass"),
        ("hemizygous single allele, absent",
         {"chrom": "MT", "start": 100, "ref": "A", "alts": "T", "genotype": "C"}, {}, "finding"),
        ("phased genotype is split on the pipe like any other",
         {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A", "genotype": "A|T"}, {}, "pass"),
        ("ref authored but no alts — {ref} alone would flag every het row",
         {"chrom": "11", "start": 5227002, "ref": "T"}, {}, "pass"),
        ("nothing known about the alleles at all",
         {"rsid": "rs334"}, {}, "pass"),
        ("effect_allele names an allele the locus does not have",
         {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A", "effect_allele": "G"}, {}, "finding"),
        ("effect_allele names the reference, which is a real allele",
         {"chrom": "11", "start": 5227002, "ref": "T", "alts": "A", "effect_allele": "T"}, {}, "pass"),
    ],
)
def test_allele_membership_matrix(
    label: str, variant_kwargs: dict, table: dict, expected: str
) -> None:
    """Severity is the mode ladder in both provenance cases — warn in best_effort, error in strict.

    The escalation the draft plan wanted (authored contradiction ⇒ error in *both* modes) is unsafe,
    and the reason is not obvious: `ref`/`alts` in `variants.csv` are not necessarily human-authored.
    `reverse_module` writes them too, so a one-to-many rsid reverses into N rows that each carry their
    own locus's alleles beside the single genotype the author wrote. See the round-trip test below.
    """
    from just_dna_compiler.compiler import _check_allele_membership

    variant = _variant(**variant_kwargs)
    for strict in (False, True):
        errors, warnings = _check_allele_membership([variant], table, strict=strict)
        got = errors if strict else warnings
        other = warnings if strict else errors
        if expected == "pass":
            assert not got and not other, f"{label} (strict={strict}): expected silence, got {got or other}"
        else:
            assert got, f"{label} (strict={strict}): expected a finding, got none"
            assert not other, f"{label} (strict={strict}): finding landed in the wrong channel"


def test_resolved_alleles_are_unioned_across_a_one_to_many_rsid() -> None:
    """The regression this check was nearly shipped without.

    A one-to-many rsid keeps ONE authored genotype while resolving to several loci, so a per-locus
    comparison flags every sibling the genotype was never about. Checked against the real shape:
    `rs281864532` in `reference_examples/pathogenic_clinvar/` resolves to both `GTT>G` and `GT>G`, and
    its authored genotype `G/GT` belongs to the second. Per-locus that is one finding; unioned it is
    correctly none.
    """
    from just_dna_compiler.compiler import _allowed_alleles, _check_allele_membership
    from just_dna_format.resolution import ResolutionRow

    loci = [
        ResolutionRow(variant_key="rs281864532", rsid="rs281864532", chrom="11",
                      start=5226925, ref="GTT", alts="G", locus_index=0),
        ResolutionRow(variant_key="rs281864532", rsid="rs281864532", chrom="11",
                      start=5226926, ref="GT", alts="G", locus_index=1),
    ]
    variant = _variant(rsid="rs281864532", genotype="G/GT")
    table = {"rs281864532": loci}

    allowed, provenance = _allowed_alleles(variant, table)
    assert provenance == "resolved"
    assert allowed == {"G", "GT", "GTT"}          # the union, not either locus alone
    assert not {"G", "GT"} <= {"G", "GTT"}        # ...and the first locus alone would NOT cover it

    assert _check_allele_membership([variant], table, strict=True) == ([], [])


def test_a_locus_that_cannot_host_the_genotype_is_not_expanded_onto(tmp_path: Path) -> None:
    """The fabrication this check originally surfaced, now prevented at the source.

    A one-to-many rsid carries ONE authored genotype onto N loci. `rs999` here resolves to `A>T` and
    `C>G`; the authored `A/T` can only be true of the first. Expanding onto both wrote a row asserting
    an allele the locus does not have, and reverse then emitted that fabrication as authored data.
    The incompatible locus is dropped instead — and because dropping it makes the compile
    unreproducible from the injected table, `strict` refuses rather than silently pruning.
    """
    spec = tmp_path / "expand"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs999,A/T,risk,two loci,HBB\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs999,12345678\n")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
        "rs999,rs999,5,500,A,T,GRCh38,0,manual,resolved,\n"
        "rs999,rs999,6,600,C,G,GRCh38,1,manual,resolved,\n"
    )
    first = compile_module(spec, tmp_path / "out1")
    assert first.success, first.errors
    assert any("cannot host the authored genotype" in w for w in first.warnings)

    weights = pl.read_parquet(tmp_path / "out1" / "weights.parquet")
    assert weights.height == 1                       # only the locus that can host A/T
    assert weights["chrom"].to_list() == ["5"]

    strict = compile_module(spec, tmp_path / "out_strict", strict=True)
    assert not strict.success
    assert any("cannot host the authored genotype" in e for e in strict.errors)

    # ...and the authored shape survives the round-trip: one rsid-only row, no fabricated coordinates.
    reversed_spec = tmp_path / "rev"
    reverse_module(tmp_path / "out1", reversed_spec)
    rows = list(csv.DictReader((reversed_spec / "variants.csv").read_text().splitlines()))
    assert len(rows) == 1
    assert rows[0]["rsid"] == "rs999" and rows[0]["chrom"] == ""
    again = compile_module(reversed_spec, tmp_path / "out2")
    assert again.success, again.errors
    assert first.manifest.artifact.digest == again.manifest.artifact.digest


def test_the_reference_example_trips_no_allele_finding() -> None:
    """The real module, through the real code path: silence on genuine data.

    A lint that fires on the repo's own dogfood is worse than no lint. This one did, on three rows,
    until the union semantics above were fixed.
    """
    from just_dna_compiler.compiler import _check_allele_membership, _load_csv_rows
    from just_dna_format.resolution import ResolutionRow
    from just_dna_format.spec import VariantRow

    example = Path(__file__).resolve().parents[2] / "reference_examples" / "pathogenic_clinvar"
    variants, verrors, _ = _load_csv_rows(example / "variants.csv", VariantRow, "variants.csv")
    rows, rerrors, _ = _load_csv_rows(example / "resolution.csv", ResolutionRow, "resolution.csv")
    assert not verrors and not rerrors
    table: dict[str, list[ResolutionRow]] = {}
    for row in rows:
        table.setdefault(row.variant_key, []).append(row)

    assert len(variants) > 300, "guard: the example should be the full HBB panel"
    assert _check_allele_membership(variants, table, strict=True) == ([], [])


# ── ACMG BA1: a 'pathogenic' variant that is common in a general population ──────────────────────


def _ba1_spec(tmp_path: Path, name: str, clin_sig: str, freq_rows: str) -> Path:
    spec = tmp_path / name
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene,clin_sig\n"
        f"11,5227002,T,A,A/T,risk,Sickle-cell,HBB,{clin_sig}\n"
    )
    (spec / "studies.csv").write_text(
        "chrom,start,ref,pmid\n11,5227002,T,12345678\n"
    )
    (spec / "frequencies.csv").write_text(_freq_csv(freq_rows))
    return spec


def _recorded_faf95(key: str) -> float:
    """The real gnomAD v4.1 popmax filtering AF from the committed payload — never hardcoded."""
    import json

    assets = Path(__file__).resolve().parents[2] / "assets"
    payload = json.loads((assets / "gnomad_v4.1_variant_payload.json").read_text())
    return payload["data"][key]["joint"]["faf95"]["popmax"]


def test_sickle_cell_sits_just_under_the_ba1_threshold(tmp_path: Path) -> None:
    """Real numbers decide this test, and they are interesting: rs334's filtering AF is ~0.0482 in
    African-ancestry groups — just *below* ACMG's 5% line. So the default must stay silent on the
    canonical pathogenic-and-common variant, and a slightly stricter threshold must speak."""
    faf = _recorded_faf95("sickle")
    assert 0.04 < faf < 0.05, f"fixture drift: rs334 faf95 is {faf}"

    row = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,afr,3949,41442,,,{faf},gnomad_v4.1_joint,,,gnomad,resolved,\n"

    quiet = compile_module(
        _ba1_spec(tmp_path, "quiet", "pathogenic", row), tmp_path / "q", resolve_with_ensembl=False
    )
    assert quiet.success
    assert not any("BA1" in w for w in quiet.warnings)

    loud = compile_module(
        _ba1_spec(tmp_path, "loud", "pathogenic", row), tmp_path / "l",
        resolve_with_ensembl=False, ba1_threshold=0.04,
    )
    assert loud.success            # warning only, in both modes
    assert any("BA1" in w for w in loud.warnings)


def test_ba1_fires_on_a_genuinely_common_allele_called_pathogenic(tmp_path: Path) -> None:
    """MTHFR C677T's real filtering AF is ~0.47. Calling that `pathogenic` is exactly what BA1 is for."""
    faf = _recorded_faf95("mthfr")
    assert faf > 0.4, f"fixture drift: rs1801133 faf95 is {faf}"

    spec = tmp_path / "mthfr"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene,clin_sig\n"
        "1,11796321,G,A,A/G,risk,Reduced activity,MTHFR,pathogenic\n"
    )
    (spec / "studies.csv").write_text("chrom,start,ref,pmid\n1,11796321,G,23456789\n")
    (spec / "frequencies.csv").write_text(_freq_csv(
        f"{_MTHFR},rs1801133,1,11796321,G,A,GRCh38,amr,19200,62494,,,{faf},"
        f"gnomad_v4.1_joint,,,gnomad,resolved,\n"
    ))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success
    assert any("BA1" in w and "stand-alone evidence" in w for w in result.warnings)


def test_ba1_says_nothing_about_a_variant_the_module_does_not_call_pathogenic(tmp_path: Path) -> None:
    """The rule is about pathogenic claims. A common allele called `benign` is simply consistent."""
    faf = _recorded_faf95("mthfr")
    row = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,afr,3949,41442,,,{faf},gnomad_v4.1_joint,,,gnomad,resolved,\n"
    result = compile_module(
        _ba1_spec(tmp_path, "benign", "benign", row), tmp_path / "out", resolve_with_ensembl=False
    )
    assert result.success
    assert not any("BA1" in w for w in result.warnings)


# ── sources.csv: licensing as data, and the gate ────────────────────────────────────────────────
_SRC_HDR = "source,layer,license,attribution,share_alike,commercial_use,declared_use\n"
_CLINPGX_DECLARED = (
    _SRC_HDR + "clinpgx,annotation,CC-BY-SA-4.0,ClinPGx,true,false,non_commercial\n"
)
_CLINPGX_UNDECLARED = _SRC_HDR + "clinpgx,annotation,CC-BY-SA-4.0,ClinPGx,true,false,unstated\n"


def test_sources_sidecar_materializes_and_summarizes(tmp_path: Path) -> None:
    result = compile_module(
        _spec(tmp_path, sources=_CLINPGX_DECLARED), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert (tmp_path / "o" / "sources.parquet").is_file()
    block = result.manifest.sources
    assert block.signature is not None  # recomputed against the CSV in the next test
    assert block.sources == ["clinpgx"] and block.layers == ["annotation"]
    assert block.attributions == ["ClinPGx"]
    assert block.commercial_use is False
    assert block.declared_uses == ["non_commercial"]


def test_sources_signature_matches_a_runtime_recomputation(tmp_path: Path) -> None:
    spec = _spec(tmp_path, sources=_CLINPGX_DECLARED)
    result = compile_module(spec, tmp_path / "o", resolve_with_ensembl=False)
    with (spec / "sources.csv").open(encoding="utf-8", newline="") as handle:
        parsed = [SourceRow(**{k: (v or None) for k, v in rec.items()})
                  for rec in csv.DictReader(handle)]
    assert result.manifest.sources.signature == source_signature(parsed)


def test_adding_sources_leaves_the_snp_core_byte_identical(tmp_path: Path) -> None:
    """Principle 3: a module that does not carry the table must be completely unaffected."""
    bare = compile_module(_spec(tmp_path), tmp_path / "o_bare", resolve_with_ensembl=False)
    withsrc = compile_module(
        _spec(tmp_path, sources=_CLINPGX_DECLARED), tmp_path / "o_src", resolve_with_ensembl=False
    )
    assert bare.success and withsrc.success
    for name in ("weights.parquet", "annotations.parquet", "studies.parquet"):
        assert (tmp_path / "o_bare" / name).read_bytes() == (tmp_path / "o_src" / name).read_bytes()
    assert bare.manifest.sources is None            # absent table → absent block
    assert bare.manifest.artifact.digest != withsrc.manifest.artifact.digest  # different content


# The refusal matrix, exactly as documented. `commercial_use` / `declared_use` / expected outcome.
@pytest.mark.parametrize(
    "commercial_use,declared_use,compiles",
    [
        ("false", "non_commercial", True),   # forbids, declared → allowed
        ("false", "unstated", False),        # forbids, no declaration → refuse
        ("false", "commercial", False),      # forbids, contradicted → refuse
        ("", "unstated", True),              # unknown terms → warn, never refuse
        ("true", "unstated", True),          # permissive
    ],
)
def test_license_gate_matrix(
    tmp_path: Path, commercial_use: str, declared_use: str, compiles: bool
) -> None:
    csv_text = _SRC_HDR + f"clinpgx,annotation,CC-BY-SA-4.0,ClinPGx,true,{commercial_use},{declared_use}\n"
    result = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success is compiles, (result.errors, result.warnings)
    if not compiles:
        assert any("licensing" in e for e in result.errors)


def test_gate_refuses_in_best_effort_too(tmp_path: Path) -> None:
    """Not a `strict` concern: strict means 'reproducible artifact', which this is unrelated to."""
    spec = _spec(tmp_path, sources=_CLINPGX_UNDECLARED)
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"o_{strict}", resolve_with_ensembl=False,
                                strict=strict)
        assert not result.success


def test_gate_writes_nothing_when_it_refuses(tmp_path: Path) -> None:
    """The gate sits before `output_dir.mkdir()` — a refusal must leave no artifact behind."""
    out = tmp_path / "o_refused"
    result = compile_module(
        _spec(tmp_path, sources=_CLINPGX_UNDECLARED), out, resolve_with_ensembl=False
    )
    assert not result.success
    assert not out.exists()


def test_a_coordinate_only_source_does_not_taint(tmp_path: Path) -> None:
    """The false-viral case the per-layer split exists to prevent."""
    csv_text = _SRC_HDR + "cpic,resolution,CC-BY-SA-4.0,CPIC,true,false,unstated\n"
    result = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    block = result.manifest.sources
    assert block.share_alike_layers == ["resolution"]
    assert "annotation" not in block.noncommercial_layers
    assert block.commercial_use is True   # a fact, not expression — the module stays sellable


def test_a_hand_declared_literature_service_is_not_an_orphan(tmp_path: Path) -> None:
    """S23. `studies.csv` carries the module's literature evidence and has no `source` column — by the
    same design that exempts the annotation layer — so a literature-layer declaration beside it can
    never be corroborated and must not be reported as unused.

    The defect was the *incentive*, which this asserts in both directions: declaring the service (what
    `MISPLACED_COLUMN_REASONS['source']` instructs) warned, while omitting it was silent, so an author
    following the warning deleted their own provenance."""
    csv_text = (
        _SRC_HDR
        + "europepmc,literature,,Europe PMC,,,unstated\n"
        + "pubmed,literature,,NCBI PubMed,,,unstated\n"
    )
    declared = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert declared.success, declared.errors
    assert not [w for w in declared.warnings if "no table in this module uses" in w]

    # And the rows are still carried — exempt from the orphan check is not dropped from the artifact.
    assert {"europepmc", "pubmed"} <= set(declared.manifest.sources.sources)


def test_a_frequency_declaration_with_no_frequencies_is_still_an_orphan(tmp_path: Path) -> None:
    """The exemption is not a general softening: a `frequency`-layer row is corroborable, because
    `frequencies.csv` is machine-written and carries a `source` column. With no such table there is
    genuinely nothing the declaration describes, which is what the warning is for."""
    csv_text = _SRC_HDR + "gnomad,frequency,,gnomAD,,true,unstated\n"
    result = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert [w for w in result.warnings if "no table in this module uses" in w]


def test_a_permissive_source_cannot_launder_a_restricted_one(tmp_path: Path) -> None:
    """Most-restrictive-wins, module-wide."""
    csv_text = (
        _SRC_HDR
        + "ensembl,resolution,,Ensembl,false,true,unstated\n"
        + "clinpgx,annotation,CC-BY-SA-4.0,ClinPGx,true,false,non_commercial\n"
    )
    result = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert result.manifest.sources.commercial_use is False


def test_unknown_terms_leave_the_verdict_undetermined(tmp_path: Path) -> None:
    """Null is not permission: an unreadable licence must not resolve to `true`."""
    csv_text = (
        _SRC_HDR
        + "ensembl,resolution,,Ensembl,false,true,unstated\n"
        + "pharmvar,annotation,CC-BY-SA-4.0,PharmVar,true,,unstated\n"
    )
    result = compile_module(
        _spec(tmp_path, sources=csv_text), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert result.manifest.sources.commercial_use is None
    assert result.manifest.sources.unknown_terms_sources == ["pharmvar"]


def test_declared_license_conflict_warns_in_both_modes(tmp_path: Path) -> None:
    """Two legal claims disagreeing is not the compiler's to arbitrate — the second deliberate
    non-escalation, after the ClinVar clin_sig cross-check."""
    spec = _spec(tmp_path, sources=_CLINPGX_DECLARED, license="MIT")
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"o_lic_{strict}", resolve_with_ensembl=False,
                                strict=strict)
        assert result.success, result.errors
        assert any("declares license" in w for w in result.manifest.compilation.warnings)
    assert result.manifest.license == "MIT"   # author-declared, copied through


def test_undeclared_and_orphan_sources_warn(tmp_path: Path) -> None:
    # The orphan is declared at a **fact** layer: that is the case the check can actually decide, by
    # reading the fact tables' own `source` columns.
    csv_text = _SRC_HDR + "notused,frequency,CC0,,false,true,unstated\n"
    result = compile_module(
        _spec(tmp_path, frequencies=True, sources=csv_text), tmp_path / "o",
        resolve_with_ensembl=False,
    )
    assert result.success, result.errors
    warnings = result.manifest.compilation.warnings
    assert any("no table in this module uses" in w for w in warnings)   # orphan: notused
    assert any("has no row for" in w and "gnomad" in w for w in warnings)  # undeclared: gnomad


def test_an_annotation_layer_source_is_never_called_an_orphan(tmp_path: Path) -> None:
    """The annotation tables carry no `source` column, so "unused" is undecidable there.

    Every drafted module hit this: `clinvar_draft`/`pgx_draft` write exactly one annotation-layer row —
    the row the licence gate keys on — and the check reported that load-bearing row as probably stale.
    """
    result = compile_module(
        _spec(tmp_path, sources=_CLINPGX_DECLARED), tmp_path / "o", resolve_with_ensembl=False
    )
    assert result.success, result.errors
    assert not any(
        "no table in this module uses" in w for w in result.manifest.compilation.warnings
    )
    # …and it still governs the gate, which is the reason not to let it look ignorable.
    assert result.manifest.sources.commercial_use is False


_RESOLUTION_HDR = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
)


def _with_links(spec: Path, rows: str) -> Path:
    """Drop a `resolution.csv` carrying explicit `source`/`authority` cells into an existing spec."""
    (spec / "resolution.csv").write_text(_RESOLUTION_HDR + rows)
    return spec


def test_a_resolution_link_is_not_a_source_name(tmp_path: Path) -> None:
    """RM33: `resolution.csv`'s `source` names the LINK, `sources.csv`'s names the licensed source.

    Compared by string, every enriched module warned that `ensembl-rest` has no terms recorded — a
    finding about a name that is not a source at all. The first half of this test is the old shape (no
    `authority`), and it must produce **no** claim about `ensembl-rest`; the second half is what the
    enricher writes now, and the declared `ensembl` row must satisfy it.
    """
    rows = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,ensembl-rest,{{authority}},resolved\n"
    declared = _SRC_HDR + "ensembl,resolution,Apache-2.0,Ensembl,false,true,unstated\n"

    # Old shape: the link is recorded, the authority is not. Nothing may be said about `ensembl-rest`.
    legacy = _with_links(_spec(tmp_path, sources=declared), rows.format(authority=""))
    result = compile_module(legacy, tmp_path / "o_legacy")
    assert result.success, result.errors
    legacy_warnings = result.manifest.compilation.warnings
    assert not any("ensembl-rest" in w for w in legacy_warnings)
    # …and the declared row is not called an orphan either: the module did use Ensembl, and a table
    # that cannot say so is exactly the gap the column closes. (This is the residual honest cost of an
    # old resolution.csv: it says nothing rather than something wrong.)
    assert any("no table in this module uses" in w and "ensembl" in w for w in legacy_warnings)

    # New shape: the authority joins `sources.csv`, so neither warning fires.
    current = _with_links(
        _spec(tmp_path, sources=declared, license="MIT"), rows.format(authority="ensembl")
    )
    result = compile_module(current, tmp_path / "o_current")
    assert result.success, result.errors
    warnings = result.manifest.compilation.warnings
    assert not any("ensembl-rest" in w for w in warnings)
    assert not any("no table in this module uses" in w for w in warnings)
    assert not any("has no row for" in w for w in warnings)


def test_a_resolution_authority_with_no_terms_row_still_warns(tmp_path: Path) -> None:
    """The check keeps its teeth: an authority the module never declared is a real finding."""
    rows = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,gnomad,gnomad,resolved\n"
    spec = _with_links(_spec(tmp_path, sources=_CLINPGX_DECLARED), rows)
    result = compile_module(spec, tmp_path / "o")
    assert result.success, result.errors
    assert any(
        "has no row for" in w and "gnomad" in w for w in result.manifest.compilation.warnings
    )


def test_authored_and_reversed_links_declare_no_authority(tmp_path: Path) -> None:
    """`authored`/`reversed` have no external source, and `None` must contribute nothing.

    Otherwise the module would be told to record terms for its own bytes — and after a round-trip,
    where every row's `source` is `reversed`, for the compiler itself.
    """
    rows = (
        f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,authored,,resolved\n"
        f"{_MTHFR},rs1801133,1,11796321,G,A,GRCh38,0,reversed,,resolved\n"
    )
    spec = _with_links(_spec(tmp_path, sources=None), rows)
    result = compile_module(spec, tmp_path / "o")
    assert result.success, result.errors
    assert not any("has no row for" in w for w in result.manifest.compilation.warnings)


def test_authority_is_outside_the_resolution_fact_set(tmp_path: Path) -> None:
    """Provenance, like `rsid_status`: adding it must not move `resolution_signature`."""
    rows = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,ensembl-rest,{{authority}},resolved\n"
    without = _with_links(_spec(tmp_path, sources=None), rows.format(authority=""))
    with_it = _with_links(_spec(tmp_path, license="MIT"), rows.format(authority="ensembl"))
    a = compile_module(without, tmp_path / "o_a")
    b = compile_module(with_it, tmp_path / "o_b")
    assert a.success and b.success, (a.errors, b.errors)
    assert (
        a.manifest.compilation.resolution_signature
        == b.manifest.compilation.resolution_signature
    )


def test_reverse_does_not_re_emit_the_authority_column(tmp_path: Path) -> None:
    """Reverse emits facts and discards provenance — a reversed table has no authority to name."""
    rows = f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,0,ensembl-rest,ensembl,resolved\n"
    spec = _with_links(_spec(tmp_path, sources=None), rows)
    assert compile_module(spec, tmp_path / "orig").success
    reverse_module(tmp_path / "orig", tmp_path / "rev")
    header = (tmp_path / "rev" / "resolution.csv").read_text().splitlines()[0]
    assert "authority" not in header and "source" in header
    assert ResolutionRow(variant_key="x").authority is None


def test_sources_roundtrip_is_lossless(tmp_path: Path) -> None:
    """Principle 7 over the new table, including the tri-state nulls."""
    csv_text = (
        _SRC_HDR
        + "ensembl,resolution,,Ensembl,false,true,unstated\n"
        + "pharmvar,annotation,CC-BY-SA-4.0,PharmVar,true,,unstated\n"
    )
    spec = _spec(tmp_path, sources=csv_text)
    first = compile_module(spec, tmp_path / "orig", resolve_with_ensembl=False)
    reverse_module(tmp_path / "orig", tmp_path / "reversed")
    # Reverse regenerates a spec, so it writes the *preferred* spelling — asked of `layout` rather
    # than spelled out here, or this assertion pins whichever name happens to be current (RM51).
    assert (tmp_path / "reversed" / preferred_spelling("sources.csv")).is_file()
    second = compile_module(tmp_path / "reversed", tmp_path / "recompiled",
                            resolve_with_ensembl=False)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.sources.signature == second.manifest.sources.signature
    # The unknown stays unknown — a round-trip must not turn null into false.
    assert second.manifest.sources.commercial_use is None
    orig = pl.read_parquet(tmp_path / "orig" / "sources.parquet")
    recompiled = pl.read_parquet(tmp_path / "recompiled" / "sources.parquet")
    assert orig.equals(recompiled)


def test_discarding_uncited_literature_converges_on_the_round_trip(tmp_path: Path) -> None:
    """A narrowing that reaches a fixed point on lap two, which is what makes it safe (RM79).

    `reverse_module` rebuilds `literature.csv` from the parquet, so a reversed copy carries the kept
    rows only. That is not a Principle 7 breach — `literature.csv` is a machine-written derived
    sidecar, not an authored value, which is the reading RM69 established for `resolution.csv` — but
    it is only tolerable because it **converges**: everything in the parquet is cited by construction,
    so the second lap discards nothing and every signature holds. A narrowing that kept narrowing, or
    that oscillated, would be a defect whatever the sidecar's status.

    The author's own file is untouched by any of this; only a reverse into a fresh directory produces
    the trimmed copy, and re-running the enricher restores the rows the way it does for every derived
    sidecar.
    """
    spec = _spec(tmp_path, literature=True)
    (spec / "literature.csv").write_text(_LITERATURE + "34567890,,,true,,,,pubmed,resolved,\n")

    first = compile_module(spec, tmp_path / "one", resolve_with_ensembl=False)
    assert first.success
    reverse_module(tmp_path / "one", tmp_path / "back")

    # The reversed spec carries the kept rows and not the orphan …
    reversed_pmids = pl.read_parquet(tmp_path / "one" / "literature.parquet")["pmid"].to_list()
    assert "34567890" not in reversed_pmids

    second = compile_module(tmp_path / "back", tmp_path / "two", resolve_with_ensembl=False)
    assert second.success
    # … lap two discards nothing, so the finding is gone rather than repeating …
    assert not [w for w in second.warnings if "no study or bin in this module cites" in w]
    # … and the literature identity is a fixed point across it.
    assert second.manifest.literature.signature == first.manifest.literature.signature
    assert second.manifest.literature.row_count == first.manifest.literature.row_count
    assert (
        pl.read_parquet(tmp_path / "two" / "literature.parquet")["pmid"].to_list()
        == reversed_pmids
    )


def test_carried_vrs_ids_are_grouped_by_reason_not_reported_per_allele() -> None:
    """The better-resolved module must not be the loud one (S67).

    Which path an allele takes is decided by whether the enricher minted an id for it and by nothing
    else: `_vrs_coverage` aggregates the alleles with **no** id, and this pass used to emit one line
    per id **present**. So noise ran inversely to how well-resolved a module was — the reported pair
    was a 101-row module producing 80 of its 85 warnings here against a 57,595-row module producing
    one aggregated line, with the three findings its author could act on at positions 83, 84 and 85.

    Twelve indels, one cause. The assertion is that the count survives the grouping: this is not a
    cap, and an author who wants the coverage number still has it.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids

    rows = [
        _res_row(variant_key=f"11:{5227000 + i}:C:CA", ref="C", alts="CA", vrs_id=_SICKLE)
        for i in range(12)
    ]
    errors, warnings = _verify_vrs_ids(rows)
    assert errors == []
    assert len(warnings) == 1, f"twelve alleles, one cause, one line — got {len(warnings)}"

    line = warnings[0]
    assert line.startswith("12 allele(s):"), line
    assert "could not be verified" in line and "carried unverified" in line
    # Three named, then the remainder counted — the `summarize_ref_mismatches` shape.
    assert "11:5227000:C:CA" in line and "and 9 more" in line


def test_grouping_keeps_distinct_reasons_distinct() -> None:
    """Aggregation groups by cause, so two causes never collapse into one line.

    The failure this guards is the tempting cheap version — "collapse the VRS warnings" — which would
    hide that a module has two different problems, and the reasons have different remedies. That is
    `_vrs_coverage_warnings`' own argument for grouping by why rather than reporting a bare total.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids

    indels = [_res_row(variant_key=f"11:{5227000 + i}:C:CA", ref="C", alts="CA", vrs_id=_SICKLE)
              for i in range(4)]
    other_build = [_res_row(variant_key=f"11:{5228000 + i}:T:A", genome_build="GRCh37",
                            vrs_id=_SICKLE) for i in range(2)]
    _errors, warnings = _verify_vrs_ids(indels + other_build)

    assert len(warnings) == 2, warnings
    # Descending count, so the biggest group leads — the same order the coverage half emits.
    assert warnings[0].startswith("4 allele(s):") and warnings[1].startswith("2 allele(s):")
    reasons = {w.split("— ", 1)[1] for w in warnings}
    assert len(reasons) == 2, f"two causes must not collapse into one: {reasons}"


def test_a_row_blamed_finding_stays_per_row() -> None:
    """`_BLAME_ROW` is an error, is rare, and names a row contradicting itself — it does not group.

    Explicitly excluded from the aggregation by the reporter, and correctly: a per-reason line for an
    error the author must fix individually would remove the one thing they need, which is which row.
    """
    from just_dna_compiler.compiler import _verify_vrs_ids

    rows = [_res_row(variant_key=f"k{i}", chrom=None, start=None, vrs_id=_SICKLE) for i in range(3)]
    errors, warnings = _verify_vrs_ids(rows)
    assert warnings == []
    assert len(errors) == 3, "an error naming a row must stay one line per row"
    assert {f"k{i}" for i in range(3)} == {e.split(":", 1)[0] for e in errors}


def test_a_gene_cell_that_looks_like_a_list_is_named(tmp_path: Path) -> None:
    """A composite `gene` becomes a third gene in the registry index, and nothing noticed (S72).

    Since RM121 made `stats.genes` what a gene index is fed from, `module_stats` doing `genes.add`
    on the raw cell publishes `IFNL3;IFNL4` beside `IFNL3` and `IFNL4` — a search term nobody will
    type. `VariantRow.gene` is `str | None` with no validator, and neither is any other kind's.

    Reported on 33 rows sharing one value, straight out of a ClinPGx export, so the warning
    aggregates by **cell**: 33 lines saying one thing is the shape this repo keeps having to undo.
    """
    from just_dna_compiler.compiler import _check_composite_gene_cells

    class _Row:
        def __init__(self, gene):
            self.gene = gene

    rows = [_Row("IFNL3;IFNL4") for _ in range(33)] + [_Row("IFNL3"), _Row("IFNL4"), _Row(None)]
    warnings = _check_composite_gene_cells([], {"pharm_variants.csv": rows})

    assert len(warnings) == 1, "one line per module, not per row"
    assert "'IFNL3;IFNL4' (33 row(s))" in warnings[0]
    # Reports, never repairs: the composite may legitimately name the locus.
    assert "Nothing is split here" in warnings[0]

    assert _check_composite_gene_cells([], {"pharm_variants.csv": [_Row("IFNL3")]}) == []


def test_row_count_is_family_independent(tmp_path: Path) -> None:
    """`variant_count: 0` is narrow rather than wrong, and nothing published the honest number (S72).

    The scalar counters describe `variants.csv` alone, so a `pharm_variants`-led module reported
    `variant_count: 0` beside 1,482 rows with the real number only in the undocumented `table_rows`.
    `row_count` is that number, and it must count the SNP core too: `variants.csv` and `studies.csv`
    sit **outside** `_TABLE_KINDS`, so summing the kind counts alone reports 0 for a variants-led
    module — the same defect one family over, which is how the first draft of this got it wrong.
    """
    from just_dna_compiler.compiler import validate_spec

    examples = Path(__file__).resolve().parents[2] / "reference_examples"

    table_led = validate_spec(examples / "cyp2c19_star_alleles").stats
    assert table_led["variant_count"] == 0, "the premise: this module has no variants.csv"
    assert table_led["row_count"] == sum(table_led["table_rows"].values())
    assert table_led["row_count"] > 0

    variant_led = validate_spec(examples / "hfe_hemochromatosis").stats
    assert "table_rows" not in variant_led, "the premise: this module has no kind tables"
    assert variant_led["row_count"] >= variant_led["variant_count"] + variant_led["study_count"] > 0
