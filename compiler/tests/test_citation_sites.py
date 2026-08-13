"""The two citation sites, and what the compiler owes each of them (RM47 + RM46).

Until 0.6 a citation could only name a variant, so `studies.csv` was the only place a module could
say where a claim came from and a bin *boundary* — the most interpretive number the format carries —
had nowhere to cite. `MeasureBinRow.pmid` is the second site. The same-release obligation is what
most of this file is about: a citation site the enricher and the compiler do not read is evidence the
format never checks, which is worse than the honest gap it replaced.

Expectations are computed from the real reference examples at runtime; nothing is a count read off a
data dump.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    _check_quoted_article_licenses,
    _cross_check_literature,
    _source_checks,
    binning_citations,
    compile_module,
    load_binning_rows,
    reverse_module,
    validate_spec,
)
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import StudyRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HTT = _EXAMPLES / "htt_repeat_expansion"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    "genome_build: GRCh38\n"
)
#: A real pair: PMID 8458085 is the CAG-threshold literature the HTT example's README points at.
_PMID = "8458085"


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
    assert any(_PMID in w and "no study in this module cites" in w for w in blind)

    seeing = _cross_check_literature(rows, studies, bins)
    assert not any("no study in this module cites" in w for w in seeing)


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
