"""ClinGen dosage-sensitivity pass (0.5).

The fixture reproduces the real file's shape rather than a tidied version of it — the comment block
with the release date, the `#`-prefixed header, the non-ordinal codes, and the literal
`"Not yet evaluated"` — because every one of those is a thing that breaks a naive reader, and a
comment-free tidy TSV would prove nothing about the file we actually read.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import _load_csv_rows
from just_dna_enricher.clingen import (
    ClinGenError,
    decode_rating,
    enrich_dosage_sensitivity,
    parse_curation_list,
)
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import DOSAGE_SENSITIVITY_BY_CODE, VALID_DOSAGE_SENSITIVITY

#: The licence sidecar's current filename, derived rather than named: it gained a second
#: spelling in 0.6 (RM51) and the older one retires at 1.0, so a literal here would pin a test
#: to whichever spelling happened to be current when it was written.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

# Columns and values transcribed from ClinGen_gene_curation_list_GRCh38.tsv (2026-08-01 release).
_CURATION_TSV = "#ClinGen Gene Curation Results\n#01 Aug,2026\n#Genomic Locations are reported on GRCh38 (hg38): GCF_000001405.36\n#Gene Symbol\tGene ID\tHaploinsufficiency Score\tHaploinsufficiency Description\tTriplosensitivity Score\tTriplosensitivity Description\nBRCA1\t672\t3\tSufficient evidence for dosage pathogenicity\t0\tNo evidence available\nA4GALT\t53947\t30\tGene associated with autosomal recessive phenotype\t0\tNo evidence available\nHBB\t3043\t40\tDosage sensitivity unlikely\tNot yet evaluated\t\nMTHFR\t4524\t0\tNo evidence available\tNot yet evaluated\t"

_YAML = """\
schema_version: "1.0"
module:
  name: dosage_demo
  title: Dosage
  description: fixture
  report_title: Report
genome_build: GRCh38
"""


def _spec(tmp_path: Path, genes: list[str]) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    rows = "\n".join(f"rs{i + 1},A/G,risk,c,{gene}" for i, gene in enumerate(genes))
    (spec / "variants.csv").write_text(
        f"rsid,genotype,state,conclusion,gene\n{rows}\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text(
        "rsid,pmid\n" + "\n".join(f"rs{i + 1},12345678" for i in range(len(genes))) + "\n",
        encoding="utf-8",
    )
    return spec


def test_codes_decode_to_terms_and_the_mapping_covers_the_vocabulary() -> None:
    ratings, released = parse_curation_list(_CURATION_TSV)
    assert released == "01 Aug,2026"
    assert ratings["BRCA1"].haploinsufficiency == "sufficient_evidence"
    assert ratings["A4GALT"].haploinsufficiency == "autosomal_recessive"
    assert ratings["HBB"].haploinsufficiency == "dosage_sensitivity_unlikely"
    # every code maps into the closed vocabulary, and the vocabulary has no unreachable members
    assert set(DOSAGE_SENSITIVITY_BY_CODE.values()) == set(VALID_DOSAGE_SENSITIVITY)


def test_not_yet_evaluated_is_an_absence_not_a_rating() -> None:
    ratings, _ = parse_curation_list(_CURATION_TSV)
    # 210 of 1,520 genes carry this literal; `int(cell)` on it is the crash this guards.
    assert ratings["HBB"].triplosensitivity is None
    assert ratings["BRCA1"].triplosensitivity == "no_evidence"  # 0 IS a rating — curated, no evidence
    assert decode_rating("Not yet evaluated") is None
    assert decode_rating("0") == "no_evidence"


def test_codes_are_not_stored_raw_because_they_are_not_ordinal() -> None:
    # The whole reason for decoding: 40 ("dosage sensitivity unlikely") outranks 3 ("sufficient
    # evidence") numerically while meaning the opposite, so a consumer sorting raw codes inverts them.
    assert 40 > 3
    ratings, _ = parse_curation_list(_CURATION_TSV)
    stored = {ratings["HBB"].haploinsufficiency, ratings["BRCA1"].haploinsufficiency}
    assert stored == {"dosage_sensitivity_unlikely", "sufficient_evidence"}
    assert not (stored & {"3", "40", 3, 40})


def test_enrich_writes_rows_only_for_curated_genes(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["BRCA1", "HBB", "NOTCURATED"])
    result = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    assert result.covered == ["BRCA1", "HBB"]
    # An uncurated gene gets NO row: "nobody has assessed this" is not a fact about the gene, and a
    # fabricated no_evidence row would assert one.
    assert result.missing == ["NOTCURATED"]
    assert {r.gene for r in result.rows} == {"BRCA1", "HBB"}
    assert all(r.dataset == "clingen_dosage_01 Aug,2026" for r in result.rows)

    written, errors, _ = _load_csv_rows(spec / "gene_metrics.csv", GeneMetricsRow, "gene_metrics.csv")
    assert not errors
    assert {r.gene: r.haploinsufficiency for r in written} == {
        "BRCA1": "sufficient_evidence",
        "HBB": "dosage_sensitivity_unlikely",
    }


def test_existing_rows_from_another_authority_survive(tmp_path: Path) -> None:
    # A gnomAD constraint row and a ClinGen dosage row are two authorities answering different
    # questions about one gene — the pass must add beside it, never key over it.
    spec = _spec(tmp_path, ["BRCA1"])
    (spec / "gene_metrics.csv").write_text(
        "gene,pli,loeuf,dataset,source,status\n"
        "BRCA1,0.99,0.3,gnomad_v4.1_constraint,gnomad-constraint,resolved\n",
        encoding="utf-8",
    )
    result = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    by_dataset = {r.dataset: r for r in result.rows}
    assert set(by_dataset) == {"gnomad_v4.1_constraint", "clingen_dosage_01 Aug,2026"}
    assert by_dataset["gnomad_v4.1_constraint"].pli == 0.99  # untouched
    assert by_dataset["clingen_dosage_01 Aug,2026"].haploinsufficiency == "sufficient_evidence"


def test_enrich_is_idempotent(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["BRCA1", "HBB"])
    first = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)
    before = (spec / "gene_metrics.csv").read_text(encoding="utf-8")
    second = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)
    assert [r.gene for r in second.rows] == [r.gene for r in first.rows]
    assert (spec / "gene_metrics.csv").read_text(encoding="utf-8") == before


def test_strict_refuses_when_a_gene_is_uncurated(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["BRCA1", "NOTCURATED"])
    with pytest.raises(ClinGenError) as exc:
        enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV, mode="strict")
    assert "NOTCURATED" in str(exc.value)


def test_a_changed_file_layout_is_an_error_not_an_empty_table() -> None:
    # Silently returning zero ratings would read as "ClinGen curates nothing", which is worse than
    # failing: the module would compile with every dosage column empty and look correct.
    with pytest.raises(ClinGenError):
        parse_curation_list("Gene Symbol\tScore\nBRCA1\t3\n")


def test_source_row_records_that_clingen_is_sellable(tmp_path: Path) -> None:
    # The exception among annotation-layer sources here: every PGx upstream forbids sale, ClinGen
    # (CC0) does not. That difference only helps if it is recorded rather than assumed.
    spec = _spec(tmp_path, ["BRCA1"])
    row = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV).source_row
    assert (row.source, row.layer) == ("clingen", "annotation")
    assert row.commercial_use is True and row.share_alike is False
    assert row.license == "CC0-1.0"


def test_the_source_row_reaches_sources_csv(tmp_path: Path) -> None:
    # It was returned and never written, so the licensing table stayed silent about a source the
    # module's rows came from. The compile gate reads `sources.csv` and nothing else, and CC0 asks
    # for attribution — both need the row to actually be on disk.
    spec = _spec(tmp_path, ["BRCA1"])
    enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV, declared_use="commercial")

    written, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert not errors
    recorded = {(r.source, r.layer): r for r in written}
    assert ("clingen", "annotation") in recorded
    row = recorded[("clingen", "annotation")]
    assert row.license == "CC0-1.0" and row.commercial_use is True
    assert row.declared_use == "commercial"
    assert row.dataset == "clingen_dosage_01 Aug,2026"  # the terms name the release they justify
    assert row.attribution  # CC0 requests it; the column exists to carry it


def test_a_pass_that_covers_nothing_records_no_licence_row(tmp_path: Path) -> None:
    """S77: the row said *this module uses ClinGen* about a module ClinGen curates no gene of.

    `SIRT6` is not on the curation list, so the pass looked, wrote no `gene_metrics.csv` row, and
    recorded the obligation anyway. Two costs. The declaration travels to the registry and is read as
    a statement about what the module contains, where it is simply false; and it fires
    `declared_license_disagrees` against a module whose declared licence never met ClinGen's, sending
    an author to adjudicate a conflict that does not exist — which two agents were measured doing.

    **The compiler cannot catch this**, which is what makes it the pass's job: `_source_checks`
    exempts the `annotation` layer from its orphan warning by design (RM46), so an annotation-layer
    row nothing uses is silent. Asserting the file's *absence* rather than the row's is deliberate —
    this module has no other source, so a licensing table at all is the over-declaration.
    """
    spec = _spec(tmp_path, ["SIRT6"])
    result = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    assert result.covered == [] and result.missing == ["SIRT6"]
    assert not (spec / _LICENCE_CSV).exists()
    # The terms of what was consulted are still a fact and still returned — a different question from
    # what the module uses, and it keeps a caller able to render them.
    assert result.source_row is not None and result.source_row.source == "clingen"
    # The empty table is still written: an author must be able to see the pass ran and found nothing.
    assert (spec / "gene_metrics.csv").exists()


def test_a_partly_covered_module_still_records_the_row(tmp_path: Path) -> None:
    """The discriminating half: one covered gene is a real use, however many are missing beside it.

    Without this the test above passes for a guard keyed on `missing` instead of `covered`, which
    would drop the declaration from every module carrying one uncurated gene — the dangerous
    direction, since that is a real obligation going unrecorded.
    """
    spec = _spec(tmp_path, ["BRCA1", "SIRT6"])
    result = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    assert result.covered == ["BRCA1"] and result.missing == ["SIRT6"]
    written, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert not errors
    assert ("clingen", "annotation") in {(r.source, r.layer) for r in written}


def test_a_second_run_over_an_already_covered_module_keeps_the_row(tmp_path: Path) -> None:
    """Idempotency across the guard: `covered` is what this run added, and lap 2 adds nothing.

    The row is merge-not-clobber, so the first run's declaration stands — the guard must not read
    "nothing new was covered" as "ClinGen contributed nothing" and leave a module whose
    `gene_metrics.csv` carries ClinGen rows with no terms recorded for them.
    """
    spec = _spec(tmp_path, ["BRCA1"])
    enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)
    second = enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    assert second.covered == []  # already done, so this run added nothing
    written, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert not errors
    assert [(r.source, r.layer) for r in written] == [("clingen", "annotation")]


def test_recording_clingen_does_not_clobber_another_sources_row(tmp_path: Path) -> None:
    # A PGx pass may have written its own terms first. Merging must add beside them — losing a
    # restrictive row would silently make a module look sellable.
    spec = _spec(tmp_path, ["BRCA1"])
    (spec / _LICENCE_CSV).write_text(
        "source,layer,license,commercial_use\ncpic,annotation,CC-BY-SA-4.0,false\n",
        encoding="utf-8",
    )
    enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)

    written, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert not errors
    assert {(r.source, r.layer) for r in written} == {
        ("cpic", "annotation"),
        ("clingen", "annotation"),
    }
    assert {r.source: r.commercial_use for r in written} == {"cpic": False, "clingen": True}
