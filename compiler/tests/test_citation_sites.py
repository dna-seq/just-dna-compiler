"""The citation sites, and what the compiler owes each of them (RM47 + RM46 + RM132).

Until 0.6 a citation could only name a variant, so `studies.csv` was the only place a module could
say where a claim came from and a bin *boundary* — the most interpretive number the format carries —
had nowhere to cite. `MeasureBinRow.pmid` is the second site and `PharmVariantRow.pmid` the third,
both reached by the same rule: a row cites when its claim is finer-grained than `studies.csv`'s key.
The same-release obligation is what most of this file is about: a citation site the enricher and the
compiler do not read is evidence the format never checks, which is worse than the honest gap it
replaced. Since 0.7 the set of sites is derived rather than listed, and the equality below is what
keeps it honest.

Expectations are computed from the real reference examples at runtime; nothing is a count read off a
data dump.
"""

import csv
import io
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    _BINNING_TABLE_KINDS,
    _CITING_TABLE_KINDS,
    _TABLE_KINDS,
    _check_quoted_article_licenses,
    _cross_check_literature,
    _source_checks,
    binning_citations,
    compile_module,
    load_binning_rows,
    load_citing_rows,
    reverse_module,
    split_cited_literature,
    table_citations,
    validate_spec,
)
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.pgx import PharmVariantRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import StudyRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HTT = _EXAMPLES / "htt_repeat_expansion"
_SLCO1B1 = _EXAMPLES / "pgx_slco1b1_simvastatin"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    "genome_build: GRCh38\n"
)
#: A real pair: PMID 8458085 is the CAG-threshold literature the HTT example's README points at.
_PMID = "8458085"
#: The SEARCH Collaborative Group's SLCO1B1 paper — the evidence behind the simvastatin myopathy
#: rows in the `pgx_slco1b1_simvastatin` example, and a claim `studies.csv` cannot ground on its own
#: because the same variant carries efficacy and metabolism rows that paper is not about.
_PGX_PMID = "18650507"


def _spec_with_cited_bins(tmp_path: Path, *, pmid: str | None = _PMID) -> Path:
    """The HTT repeat table with a boundary citation written onto every resolved bin."""
    spec = tmp_path / "cited"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    source = (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(source)))
    fieldnames = [*rows[0].keys(), "pmid"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "pmid": "" if row["unresolved"] == "true" else (pmid or "")})
    (spec / "repeat_alleles.csv").write_text(buffer.getvalue(), encoding="utf-8")
    return spec


def _spec_with_cited_pharm_rows(
    tmp_path: Path, *, pmid: str = _PGX_PMID, name: str = "cited_pharm"
) -> Path:
    """The SLCO1B1/simvastatin example with a `pmid` written onto the toxicity rows only.

    Onto *some* rows rather than all of them on purpose: the toxicity claim is what the SEARCH paper
    established, and the efficacy and metabolism rows for the same variant are about other work. That
    asymmetry is the whole reason the column exists — one `studies.csv` row keyed `(variant_key,
    pmid)` would attach that paper to every drug, genotype and phenotype category recorded here.
    """
    spec = tmp_path / name
    spec.mkdir()
    for filename in ("module_spec.yaml", "licensing.csv", "resolution.csv"):
        source = _SLCO1B1 / filename
        if source.is_file():
            (spec / filename).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO((_SLCO1B1 / "pharm_variants.csv").read_text())))
    fieldnames = [*rows[0].keys(), "pmid"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {**row, "pmid": pmid if row["phenotype_category"] == "Toxicity" else ""}
        )
    (spec / "pharm_variants.csv").write_text(buffer.getvalue(), encoding="utf-8")
    return spec


def _plain_pharm_spec(tmp_path: Path, name: str = "plain_pharm") -> Path:
    """The same example verbatim — no `pmid` header at all, which is every module published to date."""
    spec = tmp_path / name
    spec.mkdir()
    for source in _SLCO1B1.glob("*.csv"):
        (spec / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (spec / "module_spec.yaml").write_text(
        (_SLCO1B1 / "module_spec.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return spec


# ── the column itself ───────────────────────────────────────────────────────────────────────────


def test_a_cited_bin_round_trips_through_compile_and_reverse(tmp_path: Path) -> None:
    """The third touch point is the one that gets missed: a column absent from the reverse writer
    round-trips as silent data loss. Binning kinds go through the generic writer, so this proves the
    generic path really does carry the new column rather than assuming it."""
    spec = _spec_with_cited_bins(tmp_path)
    authored = (spec / "repeat_alleles.csv").read_text(encoding="utf-8")

    out = tmp_path / "out"
    assert compile_module(spec, out).success
    back = tmp_path / "back"
    reverse_module(out, back)

    reversed_rows = list(csv.DictReader(io.StringIO((back / "repeat_alleles.csv").read_text())))
    authored_rows = list(csv.DictReader(io.StringIO(authored)))
    assert [r["pmid"] for r in reversed_rows] == [r["pmid"] for r in authored_rows]

    # And recompiling the reversed spec is a fixed point on the authored identity (P7).
    again = tmp_path / "again"
    assert compile_module(back, again).success
    import json
    first = json.loads((out / "manifest.json").read_text())
    second = json.loads((again / "manifest.json").read_text())
    assert first["content_signature"] == second["content_signature"]


def test_the_pointer_changes_the_content_signature(tmp_path: Path) -> None:
    """It is authored data, so it must be inside the authored identity — an optional column left
    unset is omitted from the hash, but one an author filled is content."""
    import json
    uncited = tmp_path / "plain"
    uncited.mkdir()
    (uncited / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (uncited / "repeat_alleles.csv").write_text(
        (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    cited = _spec_with_cited_bins(tmp_path)

    assert compile_module(uncited, tmp_path / "a").success
    assert compile_module(cited, tmp_path / "b").success
    first = json.loads((tmp_path / "a" / "manifest.json").read_text())["content_signature"]
    second = json.loads((tmp_path / "b" / "manifest.json").read_text())["content_signature"]
    assert first != second


def test_binning_citations_normalizes_and_dedupes(tmp_path: Path) -> None:
    """One normalizer for both sites, so a `[PMID: N]` bin pointer and a bare `N` study cell cannot
    become two spellings of one citation."""
    spec = _spec_with_cited_bins(tmp_path, pmid=f"[PMID: {_PMID}]")
    assert binning_citations(load_binning_rows(spec)) == [_PMID]


def test_load_binning_rows_reads_only_binning_kinds(tmp_path: Path) -> None:
    """The public accessor exists so the enricher does not import a private tuple or keep its own
    list of the kinds; it must answer with the binning tables and nothing else."""
    spec = _spec_with_cited_bins(tmp_path)
    (spec / "haplotypes.csv").write_text(
        "haplotype_name,gene,allele,rsid\n*2,CYP2C19,A,rs4244285\n", encoding="utf-8"
    )
    loaded = load_binning_rows(spec)
    assert set(loaded) == {"repeat_alleles.csv"}


def test_load_binning_rows_resolves_a_table_exactly_as_the_compiler_does(tmp_path: Path) -> None:
    """An authored table has one legal name in one legal place, so this reader must agree with the
    compile-side loops. Resolving it through the *sidecar* resolver instead would let the enricher
    write `literature.csv` rows for citations the compiler never sees, which `_cross_check_literature`
    then reports as orphans — the cross-check contradicting the pass that produced its input."""
    spec = _spec_with_cited_bins(tmp_path)
    split = spec / "derived"
    split.mkdir()
    (split / "repeat_alleles.csv").write_text(
        (spec / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (spec / "repeat_alleles.csv").unlink()

    assert load_binning_rows(spec) == {}
    assert validate_spec(spec).warnings is not None
    # And what the compiler sees is the same nothing: no binning table, hence no grounding finding.
    assert not any("grounding evidence" in w for w in validate_spec(spec).warnings)


# ── the same-release obligation: the compiler must read the new site ────────────────────────────


def test_a_bin_cited_paper_is_not_an_orphan_in_literature_csv() -> None:
    """Reading only `studies.csv` would report every threshold-grounding citation as stale.

    Demonstrated on the shape that actually breaks: a module cites one paper from `studies.csv` and
    another from a bin, and the sidecar covers both. Blind to the second site, the compiler calls the
    bin's citation an orphan — evidence the format ships and then reports as stale."""
    other = "9545397"
    studies = [StudyRow(rsid="rs1800562", pmid=other)]
    rows = [LiteratureRow(pmid=other, exists=True), LiteratureRow(pmid=_PMID, exists=True)]
    bins = {
        "repeat_alleles.csv": [
            RepeatAlleleRow(
                gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant",
                pmid=_PMID,
            )
        ]
    }
    blind = _cross_check_literature(rows, studies, {})
    assert any(_PMID in w and "no study, bin or pharm row in this module cites" in w for w in blind)

    seeing = _cross_check_literature(rows, studies, bins)
    assert not any("no study, bin or pharm row in this module cites" in w for w in seeing)

    # RM79 gave that finding teeth, so the stakes are now higher than a warning: blind to the bin,
    # the compiler would **discard** the very row the threshold's evidence lives in. The split reads
    # every citation site for exactly this reason.
    _kept_blind, dropped_blind = split_cited_literature(rows, studies, {})
    assert [r.pmid for r in dropped_blind] == [_PMID]
    kept_seeing, dropped_seeing = split_cited_literature(rows, studies, bins)
    assert dropped_seeing == [] and {r.pmid for r in kept_seeing} == {other, _PMID}


def test_a_nonexistent_bin_citation_is_still_reported() -> None:
    """The existence finding is about the article, so it does not depend on which site cited it."""
    rows = [LiteratureRow(pmid=_PMID, exists=False)]
    findings = _cross_check_literature(rows, [], {})
    assert any("PubMed has no record of" in w for w in findings)


def test_a_cited_bin_clears_the_grounding_warning_end_to_end(tmp_path: Path) -> None:
    """Demonstrated on the old shape too: the identical table without the column still warns."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (plain / "repeat_alleles.csv").write_text(
        (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert any("grounding evidence" in w for w in validate_spec(plain).warnings)

    cited = _spec_with_cited_bins(tmp_path)
    assert not any("grounding evidence" in w for w in validate_spec(cited).warnings)


def test_a_subject_less_study_row_is_not_an_orphan(tmp_path: Path) -> None:
    """RM47's other half: a citation row grounding the module names no variant, and a row that
    references nothing cannot reference something missing."""
    spec = tmp_path / "grounded"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "repeat_alleles.csv").write_text(
        (_HTT / "repeat_alleles.csv").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (spec / "studies.csv").write_text(
        f'rsid,chrom,pmid,conclusion\n,,{_PMID},"defines the CAG thresholds"\n', encoding="utf-8"
    )
    result = validate_spec(spec, strict=True)
    assert result.valid, result.errors
    assert not any("reference variants not in variants.csv" in w for w in result.warnings)


def test_two_subject_less_rows_citing_one_paper_are_still_a_duplicate(tmp_path: Path) -> None:
    """`(None, pmid)` is a real key: the same claim written twice is a duplicate, and one such row
    is all the relaxation was for."""
    spec = tmp_path / "dupe"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,gene,genotype,weight,state,conclusion\n"
        "rs1800562,HFE,A/A,1.0,risk,C282Y homozygote\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        f"rsid,chrom,pmid,conclusion\n,,{_PMID},first\n,,{_PMID},second\n", encoding="utf-8"
    )
    assert any("Duplicate (variant, pmid)" in w for w in validate_spec(spec).warnings)


# ── RM46: per-article terms, and the notice that never gates ────────────────────────────────────


def test_quoting_a_noncommercial_article_warns_and_never_gates(tmp_path: Path) -> None:
    """It follows the ClinVar `clin_sig` precedent: warning in both modes, because refusing would
    make the format arbitrate a copyright question."""
    studies = [
        StudyRow(rsid="rs1800562", pmid=_PMID, provenance_quote="a passage from the paper")
    ]
    rows = [LiteratureRow(pmid=_PMID, exists=True, license="cc by-nc", commercial_use=False)]
    findings = _check_quoted_article_licenses(rows, studies)
    assert len(findings) == 1
    assert "cc by-nc" in findings[0]
    assert "forbids commercial reuse" in findings[0]

    spec = tmp_path / "quoted"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,gene,genotype,weight,state,conclusion\n"
        "rs1800562,HFE,A/A,1.0,risk,C282Y homozygote\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        f'rsid,pmid,conclusion,provenance_quote\nrs1800562,{_PMID},x,"a passage from the paper"\n',
        encoding="utf-8",
    )
    (spec / "literature.csv").write_text(
        "pmid,doi,pmcid,exists,license,commercial_use\n"
        f"{_PMID},,,true,cc by-nc,false\n",
        encoding="utf-8",
    )
    for strict in (False, True):
        result = validate_spec(spec, strict=strict)
        assert result.valid, (strict, result.errors)
        assert any("forbids commercial reuse" in w for w in result.warnings), strict


def test_naming_a_noncommercial_article_without_quoting_it_is_silent() -> None:
    """Citing an id costs nothing under any licence; copying the words is the act in question."""
    studies = [StudyRow(rsid="rs1800562", pmid=_PMID)]
    rows = [LiteratureRow(pmid=_PMID, exists=True, license="cc by-nc", commercial_use=False)]
    assert _check_quoted_article_licenses(rows, studies) == []


def test_unknown_terms_withhold() -> None:
    """`None` is never `False` — an article whose licence could not be established says nothing."""
    studies = [StudyRow(rsid="rs1800562", pmid=_PMID, provenance_quote="a passage")]
    rows = [LiteratureRow(pmid=_PMID, exists=True)]
    assert _check_quoted_article_licenses(rows, studies) == []


def test_the_notice_is_aggregated_by_licence() -> None:
    """One line per licence, never one per citation: a panel cites in the hundreds."""
    pmids = ["8458085", "9545397", "21551363"]
    studies = [StudyRow(rsid="rs1800562", pmid=p, provenance_quote="q") for p in pmids]
    rows = [
        LiteratureRow(pmid=p, exists=True, license="cc by-nc", commercial_use=False) for p in pmids
    ]
    findings = _check_quoted_article_licenses(rows, studies)
    assert len(findings) == 1
    assert all(p in findings[0] for p in pmids)


@pytest.mark.parametrize("layer", ["literature", "annotation"])
def test_an_uncorroborable_layer_is_never_an_orphan(layer: str) -> None:
    """No fact table's `source` column can corroborate either layer, so a declaration at one is
    uncorroborable rather than stale — and for `literature` that is now unconditional (RM46), since
    `literature.csv`'s `source` names a bibliographic registry rather than a licensed source."""
    rows = [SourceRow(source="pubmed", layer=layer)]
    assert _source_checks(rows, set()) == []


def test_a_frequency_declaration_nothing_uses_still_warns() -> None:
    """The exemption is narrow by construction: `frequencies.csv` IS machine-written with a `source`
    column naming a licensed source, so a stale declaration there really is stale."""
    rows = [SourceRow(source="gnomad", layer="frequency")]
    warnings = _source_checks(rows, set())
    assert any("no table in this module uses" in w for w in warnings)


def test_the_literature_registry_is_not_reported_as_undeclared(tmp_path: Path) -> None:
    """RM46's reported defect: the enricher wrote `source=pubmed` into every literature row, had no
    terms constant for it, and the finding landed on the author of every literature-enriched module.
    The article's terms are recorded per row instead, so `pubmed` never enters the used set."""
    spec = tmp_path / "enriched"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,gene,genotype,weight,state,conclusion\n"
        "rs1800562,HFE,A/A,1.0,risk,C282Y homozygote\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        f"rsid,pmid,conclusion\nrs1800562,{_PMID},x\n", encoding="utf-8"
    )
    (spec / "literature.csv").write_text(
        f"pmid,exists,source,status\n{_PMID},true,pubmed,resolved\n", encoding="utf-8"
    )
    (spec / "sources.csv").write_text(
        "source,layer,license,commercial_use\nclinvar,annotation,Public domain,true\n",
        encoding="utf-8",
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert not any("pubmed" in w for w in result.warnings), result.warnings


# ── S56: the sidecar's quote counter against the quotes the table actually carries ───────────────


def test_a_stale_quote_counter_is_reported_with_both_numbers() -> None:
    """The shape four published modules are in: quotes written after the literature pass ran.

    `literature.csv` is merge-not-clobber, so the row that recorded `quotes_authored=0` survives every
    later run and the module compiles green while contradicting its own `studies.csv`. The finding
    names both numbers, because "these disagree" leaves an author guessing which side to trust.
    """
    studies = [
        StudyRow(rsid="rs1800562", pmid=_PMID, provenance_quote="a located passage"),
        StudyRow(rsid="rs1799945", pmid=_PMID, provenance_quote="another located passage"),
    ]
    stale = [LiteratureRow(pmid=_PMID, exists=True, quotes_authored=0)]
    findings = _cross_check_literature(stale, studies, {})
    assert any(
        "quotes_authored disagrees" in w and "records 0 but 2 quote(s) cite it" in w
        for w in findings
    ), findings

    current = [LiteratureRow(pmid=_PMID, exists=True, quotes_authored=2)]
    assert not any("quotes_authored disagrees" in w for w in _cross_check_literature(
        current, studies, {}
    ))


def test_a_regex_counts_as_an_authored_locator_here_too() -> None:
    """`quotes_authored` is what the pass counts, and the pass counts both locators.

    A module using `provenance_regex` alone would otherwise be reported stale on every compile — a
    finding no edit could clear, which this project treats as a defect wherever it appears.
    """
    studies = [StudyRow(rsid="rs1800562", pmid=_PMID, provenance_regex="located.{0,20}passage")]
    rows = [LiteratureRow(pmid=_PMID, exists=True, quotes_authored=1)]
    assert not any(
        "quotes_authored disagrees" in w for w in _cross_check_literature(rows, studies, {})
    )


def test_a_bin_only_citation_carries_a_denominator_of_zero_rather_than_being_skipped() -> None:
    """A bin cites but cannot quote, so its literature row is current at zero and must not warn.

    Walking `bin_rows` directly to find the pmids reaches kinds that have no `pmid` column at all
    (`DiplotypeRow`), which is why this goes through `binning_citations` — the same helper the orphan
    split uses.
    """
    bins = {
        "repeat_alleles.csv": [
            RepeatAlleleRow(
                gene="HTT", repeat_unit="CAG", measure_min=40, conclusion="fully penetrant",
                pmid=_PMID,
            )
        ]
    }
    rows = [LiteratureRow(pmid=_PMID, exists=True, quotes_authored=0)]
    assert not any(
        "quotes_authored disagrees" in w for w in _cross_check_literature(rows, [], bins)
    )


# ── RM132: the third citation site, and the registry that will find the fourth ──────────────────


def test_the_citing_kinds_are_exactly_the_table_kinds_declaring_a_pmid() -> None:
    """The registry, as an equality over the walked set rather than a floor.

    A hand-kept list is what RM40/RM41 named and what this replaces, but a *derived* one still has a
    derivation that can be wrong in either direction: a kind silently escaping the literature
    cross-check is RM47's failure again, and a kind wrongly joining it would make the compiler read
    citations off a table that does not cite.

    **Stated, not re-derived.** Recomputing the set the way the module computes it and comparing the
    two is a check that agrees with itself — it passes for any derivation, including a wrong one, and
    for a hardcoded tuple. So the ground truth here is written out: these five kinds and no others,
    with `binning` and `citing` split so a member moving between them is visible. The membership
    *rule* is then asserted against each model separately, which is the part a new kind has to obey.
    """
    citing = {csv_name for csv_name, _model in _CITING_TABLE_KINDS}
    binning = {csv_name for csv_name, _model in _BINNING_TABLE_KINDS}
    assert citing == {
        "activity_phenotype.csv", "copynumbers.csv", "repeat_alleles.csv", "heteroplasmy.csv",
        "pharm_variants.csv",
    }
    assert binning < citing
    assert citing - binning == {"pharm_variants.csv"}

    # And the rule that decides membership, per model: a kind cites exactly when it declares the
    # column. Written as a per-kind equality so the failure names the kind, and so a table kind added
    # with a `pmid` and left out of the set fails here rather than going quietly uncross-checked.
    for csv_name, _parquet, model in _TABLE_KINDS:
        assert (csv_name in citing) == ("pmid" in model.model_fields), csv_name


def test_a_cited_pharm_row_round_trips_through_compile_and_reverse(tmp_path: Path) -> None:
    """The third touch point: a column absent from the reverse writer is silent data loss.

    `pharm_variants.csv` goes through the generic materializer and the generic writer, so this proves
    the generic path really carries the new column rather than assuming it — and the recompile is
    asserted byte-for-byte on the parquet, not only on the authored identity, because a column that
    reversed into a different *cell* would still hash equal under `exclude_none`.
    """
    spec = _spec_with_cited_pharm_rows(tmp_path)
    authored = list(csv.DictReader(io.StringIO((spec / "pharm_variants.csv").read_text())))
    assert {r["pmid"] for r in authored} == {_PGX_PMID, ""}, "the fixture must exercise both cells"

    out = tmp_path / "out"
    assert compile_module(spec, out).success
    back = tmp_path / "back"
    reverse_module(out, back)
    reversed_rows = list(csv.DictReader(io.StringIO((back / "pharm_variants.csv").read_text())))
    assert [r["pmid"] for r in reversed_rows] == [r["pmid"] for r in authored]

    again = tmp_path / "again"
    assert compile_module(back, again).success
    assert (again / "pharm_variants.parquet").read_bytes() == (
        out / "pharm_variants.parquet"
    ).read_bytes()
    first = json.loads((out / "manifest.json").read_text())
    second = json.loads((again / "manifest.json").read_text())
    assert first["content_signature"] == second["content_signature"]
    assert first["artifact"]["digest"] == second["artifact"]["digest"]


def test_a_module_that_never_writes_the_column_keeps_its_content_signature(tmp_path: Path) -> None:
    """P8: optional with respect to every published module.

    The two specs differ only in that one carries a `pmid` header with every cell empty, which is what
    a reversed pre-0.7 module looks like the moment it is recompiled under 0.7. `exclude_none=True` is
    the mechanism, and the point of running it rather than citing it is that the signature is computed
    over the *parsed rows*: an empty cell that parsed to `""` instead of `None` would break this.
    """
    without = _plain_pharm_spec(tmp_path, name="without")
    rows = list(csv.DictReader(io.StringIO((without / "pharm_variants.csv").read_text())))
    assert "pmid" not in rows[0], "the untouched fixture must predate the column"

    with_empty = _spec_with_cited_pharm_rows(tmp_path, pmid="", name="with_empty")
    assert compile_module(without, tmp_path / "a").success
    assert compile_module(with_empty, tmp_path / "b").success
    first = json.loads((tmp_path / "a" / "manifest.json").read_text())["content_signature"]
    second = json.loads((tmp_path / "b" / "manifest.json").read_text())["content_signature"]
    assert first == second

    # And a filled cell IS content, or the column would be outside the authored identity.
    cited = _spec_with_cited_pharm_rows(tmp_path, name="cited")
    assert compile_module(cited, tmp_path / "c").success
    third = json.loads((tmp_path / "c" / "manifest.json").read_text())["content_signature"]
    assert third != first


def test_a_pharm_cited_paper_is_not_an_orphan_in_literature_csv() -> None:
    """The compiler half of the same-release obligation, on the shape that actually breaks.

    A module cites one paper from `studies.csv` and another from a `pharm_variants.csv` row, and the
    sidecar covers both. Blind to the third site the compiler calls the pharm row's citation an
    orphan — and since RM79 gave that finding teeth, it does not merely report it: it **discards** the
    literature row the claim's evidence lives in.
    """
    other = "9545397"
    studies = [StudyRow(rsid="rs1800562", pmid=other)]
    rows = [LiteratureRow(pmid=other, exists=True), LiteratureRow(pmid=_PGX_PMID, exists=True)]
    pharm = {
        "pharm_variants.csv": [
            PharmVariantRow(
                rsid="rs4149056", gene="SLCO1B1", genotype="C/C", drug="simvastatin",
                phenotype_category="Toxicity", conclusion="higher myopathy risk", pmid=_PGX_PMID,
            )
        ]
    }
    blind = _cross_check_literature(rows, studies, {})
    assert any(
        _PGX_PMID in w and "no study, bin or pharm row in this module cites" in w for w in blind
    )
    seeing = _cross_check_literature(rows, studies, pharm)
    assert not any("no study, bin or pharm row in this module cites" in w for w in seeing)

    _kept_blind, dropped_blind = split_cited_literature(rows, studies, {})
    assert [r.pmid for r in dropped_blind] == [_PGX_PMID]
    kept_seeing, dropped_seeing = split_cited_literature(rows, studies, pharm)
    assert dropped_seeing == [] and {r.pmid for r in kept_seeing} == {other, _PGX_PMID}


def test_a_pharm_only_citation_carries_a_denominator_of_zero_rather_than_being_skipped() -> None:
    """`provenance_quote` did not follow the `pmid` to this site, so a pharm row cites and cannot
    quote — its literature row is current at zero and must not be reported as a stale counter."""
    pharm = {
        "pharm_variants.csv": [
            PharmVariantRow(
                rsid="rs4149056", gene="SLCO1B1", genotype="C/C", drug="simvastatin",
                conclusion="higher myopathy risk", pmid=_PGX_PMID,
            )
        ]
    }
    rows = [LiteratureRow(pmid=_PGX_PMID, exists=True, quotes_authored=0)]
    assert not any(
        "quotes_authored disagrees" in w for w in _cross_check_literature(rows, [], pharm)
    )


def test_the_public_readers_answer_over_every_citing_kind(tmp_path: Path) -> None:
    """What the enricher reaches through, end to end on a real spec directory.

    `load_binning_rows`/`binning_citations` stay narrow — a caller asking for the binning kinds is
    asking about thresholds — so a module citing only from `pharm_variants.csv` is *invisible* to
    them, and that is exactly why the pass now reads the wider pair. Both halves are asserted so the
    narrowing cannot be mistaken for a bug and "fixed" by widening the old symbols.
    """
    spec = _spec_with_cited_pharm_rows(tmp_path, pmid=f"[PMID: {_PGX_PMID}]")
    assert set(load_citing_rows(spec)) == {"pharm_variants.csv"}
    assert table_citations(load_citing_rows(spec)) == [_PGX_PMID]
    assert load_binning_rows(spec) == {}
    assert binning_citations(load_citing_rows(spec)) == []


def test_both_call_sites_hand_the_pharm_rows_to_the_cross_check(tmp_path: Path) -> None:
    """The wiring, not the function — and they are two different call sites.

    `_cross_check_literature` reading three sites is worth nothing if the caller hands it two, and
    the compiler calls it twice: once in the pre-flight, over `loaded_kinds`, and once inside the
    fact-table loop, over `kind_rows`. `validate_spec` reaches only the first and `compile_module`
    reaches both, so the parity rule this repo audits **by check** wants both commands asserted.

    The stake is higher than a warning: since RM79 the compiler *discards* an uncited literature row,
    so a caller that withheld the pharm rows would drop the evidence for the claim from the artifact
    and report it stale on the way out.
    """
    grounding, orphan = "8458085", "9545397"  # both real; the second is cited from nowhere
    spec = _spec_with_cited_pharm_rows(tmp_path, name="wired")
    # A subject-less study row, which RM47 made legal: it puts a citation into `cited` from a site
    # other than the one under test. Without it this module cites nothing when the pharm rows are
    # withheld, and `split_cited_literature` deliberately discards nothing in that case — so a blind
    # caller would go quiet rather than misreport, and the control would pass for the wrong reason.
    (spec / "studies.csv").write_text(
        f'rsid,chrom,pmid,conclusion\n,,{grounding},"grounds the module"\n', encoding="utf-8"
    )
    (spec / "literature.csv").write_text(
        f"pmid,exists\n{grounding},true\n{_PGX_PMID},true\n{orphan},true\n", encoding="utf-8"
    )

    def _uncited(warnings: list[str]) -> set[str]:
        # Every matching line, never the first: the check runs on both sides and de-duplicates on the
        # message, so a caller that withheld the rows on one side alone emits a *second*, differently
        # worded line beside the correct one. Reading only the first would report the healthy half and
        # call the blind half green — which is the exact shape this test exists to catch.
        return {
            found
            for w in warnings
            if "no study, bin or pharm row in this module cites" in w
            for found in (grounding, _PGX_PMID, orphan)
            if found in w
        }

    validated = validate_spec(spec)
    assert validated.valid, validated.errors
    assert _uncited(validated.warnings) == {orphan}

    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success, result.errors
    assert _uncited(result.warnings) == {orphan}

    # And the pharm-cited row survived into the artifact while the orphan did not (RM79) — the stake
    # that makes this wiring more than a warning. Withheld, the evidence for the claim would be the
    # row dropped.
    kept = pl.read_parquet(out / "literature.parquet")
    assert set(kept["pmid"].to_list()) == {grounding, _PGX_PMID}
