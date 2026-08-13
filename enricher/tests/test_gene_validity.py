"""The gene-validity pass (0.6, RM24): ClinGen's export and GenCC's, mapped onto one shape.

Both fixtures reproduce the **real files' shapes** rather than tidied versions — ClinGen's four-line
preamble and its two `+++` separator rows, GenCC's thirty-column header with the submitter's
pre-harmonization spelling beside GenCC's own — because every one of those is a thing that breaks a
naive reader, and a tidy CSV would prove nothing about the files actually read. The values are
transcribed from the 2026-08-13 downloads.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.gene_validity import (
    GeneValidityError,
    enrich_gene_validity,
    map_classification,
    map_inheritance,
    parse_clingen_validity,
    parse_gencc,
)
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import VALID_GENE_VALIDITY, VALID_INHERITANCE_MODE

_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

# ClinGen's real layout: a title row, `FILE CREATED:`, the webpage, a `+++` row, the header, another
# `+++` row, then the data. The two RYR1 rows differ only by MOI — the collision that put `moi` in the
# key, reproduced from the release itself.
_CLINGEN_CSV = """\
"CLINGEN GENE DISEASE VALIDITY CURATIONS","","","","","","","","",""
"FILE CREATED: 2026-08-13","","","","","","","","",""
"WEBPAGE: https://search.clinicalgenome.org/kb/gene-validity","","","","","","","","",""
"+++++++++++","++++++++++++++","+++++++++++++","++++++++++++++++++","+++++++++","+++++++++","++++++++++++++","+++++++++++++","+++++++++++++++++++","+++++++++++++++++++"
"GENE SYMBOL","GENE ID (HGNC)","DISEASE LABEL","DISEASE ID (MONDO)","MOI","SOP","CLASSIFICATION","ONLINE REPORT","CLASSIFICATION DATE","GCEP"
"+++++++++++","++++++++++++++","+++++++++++++","++++++++++++++++++","+++++++++","+++++++++","++++++++++++++","+++++++++++++","+++++++++++++++++++","+++++++++++++++++++"
"RYR1","HGNC:10483","malignant hyperthermia susceptibility","MONDO:0007783","AD","SOP9","Definitive","https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_aaa-2019-03-05T160000.000Z","2019-03-05T16:00:00.000Z","Malignant Hyperthermia Susceptibility GCEP"
"RYR1","HGNC:10483","congenital myopathy","MONDO:0019952","AR","SOP9","Moderate","https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_bbb-2019-03-05T160000.000Z","2019-03-05T16:00:00.000Z","Congenital Myopathies GCEP"
"HBB","HGNC:4827","sickle cell anemia","MONDO:0011382","AR","SOP10","Definitive","https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_ccc-2018-06-07T160000.000Z","2018-06-07T16:00:00.000Z","Sickle Cell Disease GCEP"
"ACO2","HGNC:118","mitochondrial disease","MONDO:0044970","AR","SOP8","Definitive","https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_ddd-2022-04-18T160000.000Z","2022-04-18T16:00:00.000Z","Mitochondrial Diseases GCEP"
"ACO2","HGNC:118","mitochondrial disease","MONDO:0044970","AD","SOP8","Limited","https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_eee-2022-04-18T160000.000Z","2022-04-18T16:00:00.000Z","Mitochondrial Diseases GCEP"
"""

_GENCC_HEADER = (
    "uuid,gene_curie,gene_symbol,disease_curie,disease_title,disease_original_curie,"
    "disease_original_title,classification_curie,classification_title,moi_curie,moi_title,"
    "submitter_curie,submitter_title,submitted_as_date,submitted_as_public_report_url,"
    "submitted_run_date\n"
)

# Two submitters disagreeing about one gene-disease pair, which is the thing GenCC exists to publish,
# plus Orphanet's `Supportive` — a grade that has no place on ClinGen's ladder and is a real member.
_GENCC_CSV = _GENCC_HEADER + (
    "GENCC_000101-HGNC_10483-x,HGNC:10483,RYR1,MONDO:0007783,malignant hyperthermia susceptibility,"
    "OMIM:145600,MH,GENCC:100001,Definitive,HP:0000006,Autosomal dominant,GENCC:000101,"
    "Ambry Genetics,2018-03-30 13:31:56,,2020-12-24\n"
    "GENCC_000104-HGNC_10483-x,HGNC:10483,RYR1,MONDO:0007783,malignant hyperthermia susceptibility,"
    "OMIM:145600,MH,GENCC:100003,Moderate,HP:0000006,Autosomal dominant,GENCC:000104,"
    "Labcorp Genetics,2021-05-02 09:00:00,,2026-08-01\n"
    "GENCC_000108-HGNC_4827-x,HGNC:4827,HBB,MONDO:0011382,sickle cell anemia,ORPHA:232,SCA,"
    "GENCC:100009,Supportive,HP:0000007,Autosomal recessive,GENCC:000108,Orphanet,"
    "2019-01-01 00:00:00,,2026-08-01\n"
)

_YAML = """\
schema_version: "1.0"
module:
  name: validity_demo
  title: Validity
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


# ── the mappings ────────────────────────────────────────────────────────────────────────────────


def test_both_submitters_wordings_land_in_the_one_vocabulary() -> None:
    """The whole reason the mapping exists: one filter must not miss the other's rows."""
    assert map_classification("Disputed") == map_classification("Disputed Evidence") == "disputed"
    assert map_classification("Refuted") == map_classification("Refuted Evidence") == "refuted"
    assert map_inheritance("AD") == map_inheritance("Autosomal dominant") == "autosomal_dominant"
    assert map_inheritance("XL") == map_inheritance("X-linked") == "x_linked"
    assert map_inheritance("UD") == map_inheritance("Unknown") == "undetermined"


def test_every_mapped_value_is_a_declared_member() -> None:
    """A mapping that produced a value the model rejects would fail at write time, per row.

    Checked over the whole map rather than a sample, because the failure mode is one entry with a
    typo — which no sample would find.
    """
    from just_dna_enricher.gene_validity import (
        CLASSIFICATION_BY_WORDING,
        INHERITANCE_BY_WORDING,
    )

    assert set(CLASSIFICATION_BY_WORDING.values()) <= VALID_GENE_VALIDITY
    assert set(INHERITANCE_BY_WORDING.values()) <= VALID_INHERITANCE_MODE


def test_an_unmodelled_wording_is_withheld_and_reported_rather_than_guessed_at() -> None:
    """`decode_rating`'s rule: an unknown grade means the source published something this release
    does not model, and placing it on the ladder would be worse than recording nothing."""
    unmapped: set[str] = set()
    assert map_classification("Extremely Definitive", unmapped=unmapped) is None
    assert map_inheritance("Sideways", unmapped=unmapped) is None
    assert unmapped == {"classification='Extremely Definitive'", "moi='Sideways'"}


def test_a_blank_cell_is_an_absence_and_not_an_unmapped_wording() -> None:
    """The distinction this codebase has needed four times: "the source did not say" is not
    "the source said something we cannot hold"."""
    unmapped: set[str] = set()
    assert map_classification("", unmapped=unmapped) is None
    assert map_inheritance(None, unmapped=unmapped) is None
    assert unmapped == set()


# ── the parsers ─────────────────────────────────────────────────────────────────────────────────


def test_the_clingen_preamble_and_separator_rows_are_not_data() -> None:
    assertions, released = parse_clingen_validity(_CLINGEN_CSV)
    assert released == "2026-08-13"
    assert {a.gene for a in assertions} == {"RYR1", "HBB", "ACO2"}
    assert len(assertions) == 5                      # no `+++` row leaked in as a gene


def test_one_gene_disease_pair_with_two_inheritance_modes_stays_two_assertions() -> None:
    """The probe finding: 59 such pairs in the real release, and the reason `moi` is in the key."""
    assertions, _ = parse_clingen_validity(_CLINGEN_CSV)
    aco2 = sorted(
        (a for a in assertions if a.gene == "ACO2"), key=lambda a: a.moi or ""
    )
    assert [(a.moi, a.classification) for a in aco2] == [
        ("autosomal_dominant", "limited"),
        ("autosomal_recessive", "definitive"),
    ]
    assert len({a.disease_id for a in aco2}) == 1     # same disease, genuinely two curations


def test_the_clingen_assertion_id_comes_out_of_the_source_and_is_not_synthesised() -> None:
    assertions, _ = parse_clingen_validity(_CLINGEN_CSV)
    ryr1 = next(a for a in assertions if a.gene == "RYR1" and a.moi == "autosomal_dominant")
    assert ryr1.assertion_id == "CGGV:assertion_aaa-2019-03-05T160000.000Z"
    assert ryr1.report_url.endswith(ryr1.assertion_id)


def test_a_changed_clingen_layout_refuses_rather_than_guessing_at_columns() -> None:
    with pytest.raises(GeneValidityError, match="header cell"):
        parse_clingen_validity('"SOMETHING ELSE","x"\n"A","B"\n')


def test_gencc_keeps_every_submitter_because_the_disagreement_is_the_data() -> None:
    assertions, released = parse_gencc(_GENCC_CSV)
    ryr1 = sorted(
        (a for a in assertions if a.gene == "RYR1"), key=lambda a: a.submitter or ""
    )
    assert [(a.submitter, a.classification) for a in ryr1] == [
        ("Ambry Genetics", "definitive"),
        ("Labcorp Genetics", "moderate"),
    ]
    # The release label is the latest run date the file carries — GenCC publishes no other version.
    assert released == "2026-08-01"


def test_gencc_supportive_is_carried_rather_than_forced_onto_the_ladder() -> None:
    """Orphanet's grade. It is a real member and deliberately off `ORDERED_GENE_VALIDITY`."""
    from just_dna_format.vocab import ORDERED_GENE_VALIDITY

    assertions, _ = parse_gencc(_GENCC_CSV)
    hbb = next(a for a in assertions if a.gene == "HBB")
    assert hbb.classification == "supportive"
    assert "supportive" not in ORDERED_GENE_VALIDITY


def test_a_changed_gencc_layout_refuses_rather_than_guessing_at_columns() -> None:
    with pytest.raises(GeneValidityError, match="gene_symbol"):
        parse_gencc("a,b,c\n1,2,3\n")


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def test_the_pass_writes_only_the_modules_genes_and_reports_the_rest(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["RYR1", "MTHFR"])
    result = enrich_gene_validity(spec, export_text=_CLINGEN_CSV)

    assert result.covered == ["RYR1"]
    # MTHFR has no ClinGen curation, so it gets NO ROW — a curating body's silence means nobody has
    # assessed the gene, which is not a fact about the gene (`clingen.py`'s rule, same argument).
    assert result.missing == ["MTHFR"]
    assert {row.gene for row in result.rows} == {"RYR1"}
    assert result.dataset == "clingen_gene_validity_2026-08-13"

    rows, errors, _ = load_csv_rows(spec / "gene_validity.csv", GeneValidityRow, "gene_validity.csv")
    assert errors == []
    assert [(r.moi, r.classification) for r in rows] == [
        ("autosomal_dominant", "definitive"),
        ("autosomal_recessive", "moderate"),
    ]


def test_the_pass_records_the_source_terms_at_its_own_layer(tmp_path: Path) -> None:
    """A pass that consults a source must write its `SourceRow`, or the module cannot account for it.

    `gene_validity` is a fact layer and cannot taint anything, which is exactly why the row matters:
    what it carries is the attribution ClinGen asks for.
    """
    spec = _spec(tmp_path, ["RYR1"])
    enrich_gene_validity(spec, export_text=_CLINGEN_CSV)
    rows, errors, _ = load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert errors == []
    recorded = {(r.source, r.layer) for r in rows}
    assert ("clingen", "gene_validity") in recorded
    clingen = next(r for r in rows if r.source == "clingen")
    assert clingen.license == "CC0-1.0" and clingen.commercial_use is True


def test_the_gencc_route_records_gencc_terms_and_not_clingens(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["RYR1"])
    result = enrich_gene_validity(spec, source="gencc", export_text=_GENCC_CSV)
    assert result.dataset == "gencc_submissions_2026-08-01"
    rows, _errors, _ = load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert {(r.source, r.layer) for r in rows} == {("gencc", "gene_validity")}


def test_a_rerun_merges_rather_than_duplicating(tmp_path: Path) -> None:
    """Existing rows are authoritative and merged, never clobbered — the standing rule.

    Keyed on the source's own assertion id, so a second run adds nothing and a hand-corrected cell
    survives it.
    """
    spec = _spec(tmp_path, ["RYR1"])
    first = enrich_gene_validity(spec, export_text=_CLINGEN_CSV)
    second = enrich_gene_validity(spec, export_text=_CLINGEN_CSV)
    assert len(second.rows) == len(first.rows)
    assert {r.assertion_id for r in second.rows} == {r.assertion_id for r in first.rows}


def test_both_submitters_can_coexist_in_one_table(tmp_path: Path) -> None:
    """Two authorities answering the same question are separate rows naming their own dataset — the
    shape `gene_metrics.csv` already uses for a gnomAD row beside a ClinGen one."""
    spec = _spec(tmp_path, ["RYR1"])
    enrich_gene_validity(spec, export_text=_CLINGEN_CSV)
    result = enrich_gene_validity(spec, source="gencc", export_text=_GENCC_CSV)
    assert {r.source for r in result.rows} == {"clingen", "gencc"}
    assert len({r.dataset for r in result.rows}) == 2


def test_the_emitted_order_is_deterministic(tmp_path: Path) -> None:
    """Parquet bytes depend on row order, so the writer's order is load-bearing (Principle 7)."""
    spec_a = _spec(tmp_path / "a", ["ACO2", "RYR1", "HBB"])
    spec_b = _spec(tmp_path / "b", ["HBB", "RYR1", "ACO2"])
    rows_a = enrich_gene_validity(spec_a, export_text=_CLINGEN_CSV).rows
    rows_b = enrich_gene_validity(spec_b, export_text=_CLINGEN_CSV).rows
    key = [(r.gene, r.disease_id, r.moi, r.submitter) for r in rows_a]
    assert key == [(r.gene, r.disease_id, r.moi, r.submitter) for r in rows_b]
    assert key == sorted(key)


def test_offline_is_a_no_op_with_a_warning_not_a_failure(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["RYR1"])
    result = enrich_gene_validity(spec, offline=True)
    assert result.skipped_offline and result.rows == []
    assert not (spec / "gene_validity.csv").exists()


def test_an_injected_export_still_wins_under_offline(tmp_path: Path) -> None:
    """Handing over bytes you already hold is not egress, so the inject-only escape hatch stays open."""
    spec = _spec(tmp_path, ["RYR1"])
    result = enrich_gene_validity(spec, offline=True, export_text=_CLINGEN_CSV)
    assert not result.skipped_offline and result.covered == ["RYR1"]


def test_strict_reports_the_uncurated_genes(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["RYR1", "MTHFR"])
    with pytest.raises(GeneValidityError, match="MTHFR"):
        enrich_gene_validity(spec, mode="strict", export_text=_CLINGEN_CSV)


def test_one_unreadable_curation_date_costs_that_cell_and_not_the_export(tmp_path: Path) -> None:
    """A 30,000-row, nineteen-submitter export must not be lost to one malformed cell.

    `classification_date` runs through `normalize_utc_timestamp`, which raises on anything
    `fromisoformat` cannot read — so an unguarded row build turned one bad date anywhere in the file
    into a bare pydantic `ValidationError`, the same traceback class as the `module_genes` bug. A date
    that cannot be read is an *unknown*: withhold the cell, keep the assertion, and report the value
    once — the rule an unrecognised classification wording already follows.

    Watched failing before the fix: `ValidationError: not an ISO-8601 timestamp: 'March 2018'`.
    """
    spec = _spec(tmp_path, ["RYR1", "HBB"])
    broken = _GENCC_CSV.replace("2018-03-30 13:31:56", "March 2018")
    result = enrich_gene_validity(spec, source="gencc", export_text=broken)

    assert {r.gene for r in result.rows} == {"RYR1", "HBB"}          # nothing was lost
    ambry = next(r for r in result.rows if r.submitter == "Ambry Genetics")
    assert ambry.classification_date is None                          # only the cell was withheld
    assert ambry.classification == "definitive"                       # the assertion survived
    assert any("March 2018" in note for note in result.unmapped)      # and it was reported, once
    # A readable date on another row is unaffected.
    labcorp = next(r for r in result.rows if r.submitter == "Labcorp Genetics")
    assert labcorp.classification_date == "2021-05-02T09:00:00Z"


def test_a_broken_variants_csv_fails_as_this_pass_and_not_as_a_borrowed_one(tmp_path: Path) -> None:
    """The gene set comes from `gene_metrics.module_genes`, which raises *its* error type.

    Nothing up this pass's stack catches that, so the CLI printed a pydantic traceback on the
    commonest authoring mistake there is. Demonstrated on the real path rather than asserted: an
    invalid `state` cell, which is exactly what an author typos.
    """
    spec = _spec(tmp_path, ["RYR1"])
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1,A/G,NOT_A_STATE,c,RYR1\n", encoding="utf-8"
    )
    with pytest.raises(GeneValidityError, match="variants.csv is invalid"):
        enrich_gene_validity(spec, export_text=_CLINGEN_CSV)


def test_an_unknown_submitter_refuses_and_names_the_ones_it_has(tmp_path: Path) -> None:
    """HPO is the case this message is really about — a shape that fits, over a link this tier may
    not take the data from."""
    spec = _spec(tmp_path, ["RYR1"])
    with pytest.raises(GeneValidityError, match="hpo"):
        enrich_gene_validity(spec, source="hpo", export_text=_CLINGEN_CSV)
