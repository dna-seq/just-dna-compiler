"""Which curation of a gene-disease claim is the live one, and where nothing can say (RM108).

ClinGen's `assertion_id` **embeds the curation timestamp**
(`CGGV:assertion_…-2019-08-18T160312.829Z`), so a re-curated assertion arrives under a different id,
misses `_merge_key`, and is appended beside the row it replaces. `manifest.gene_validity` then
published a pair as far apart as `["definitive", "refuted"]` with nothing anywhere saying which was
current — `classification_date` and `dataset` were the only discriminators, and no consumer read
either.

**The merge test that existed could not see this at all**, which is why one of the first tests here is
a re-curated export rather than the identical one re-run: `test_a_rerun_merges_rather_than_duplicating`
feeds the same bytes twice, and the same bytes carry the same ids, so the key matches and nothing is
appended. The defect needs two *different* exports of one claim, which is what the real source
produces and what a fixture has to reproduce to be worth anything.

**Nothing is stored.** A `superseded` column would have to be written onto the row already in the
file, and merge-not-clobber forbids this pass editing it — so the marker would be correct on every run
except the one that created the ambiguity. Currency is a total function of the rows present, so it is
derived at every read instead.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_enricher.gene_validity import enrich_gene_validity
from just_dna_format.gene_validity import (
    CURRENT,
    SUPERSEDED,
    GeneValidityRow,
    classify_currency,
    superseded_groups,
    undecidable_groups,
)
from just_dna_format.vocab import CARRIED_WARNING_CODES

_HEADER = (
    '"CLINGEN GENE DISEASE VALIDITY CURATIONS","","","","","","","","",""\n'
    '"FILE CREATED: 2026-08-13","","","","","","","","",""\n'
    '"WEBPAGE: https://search.clinicalgenome.org/kb/gene-validity","","","","","","","","",""\n'
    '"+++++++++++","++++++++++++++","+++++++++++++","++++++++++++++++++","+++++++++","+++++++++",'
    '"++++++++++++++","+++++++++++++","+++++++++++++++++++","+++++++++++++++++++"\n'
    '"GENE SYMBOL","GENE ID (HGNC)","DISEASE LABEL","DISEASE ID (MONDO)","MOI","SOP",'
    '"CLASSIFICATION","ONLINE REPORT","CLASSIFICATION DATE","GCEP"\n'
    '"+++++++++++","++++++++++++++","+++++++++++++","++++++++++++++++++","+++++++++","+++++++++",'
    '"++++++++++++++","+++++++++++++","+++++++++++++++++++","+++++++++++++++++++"\n'
)

_PANEL = "Hereditary Cancer GCEP"


def _clingen(classification: str, date: str, suffix: str) -> str:
    """One BRCA1 curation. The `assertion_id` embeds the timestamp, exactly as the real export does —
    which is the whole reason a re-curation misses the merge key."""
    stamp = date.replace("-", "").replace(":", "").replace(".000Z", ".000Z")
    return (
        f'"BRCA1","HGNC:1100","hereditary breast ovarian cancer syndrome","MONDO:0003582","AD",'
        f'"SOP9","{classification}",'
        f'"https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_{suffix}-{stamp}",'
        f'"{date}","{_PANEL}"\n'
    )


#: The 2019 call and the 2024 re-call of one claim. Two exports, not one export twice — the source's
#: own behaviour, and the only shape that reaches the defect.
_FIRST_CURATION = _HEADER + _clingen("Definitive", "2019-03-05T16:00:00.000Z", "aaa")
_RECURATION = _HEADER + _clingen("Refuted", "2024-07-11T16:00:00.000Z", "bbb")
#: Same claim, same instant, two verdicts: nothing in the rows says which came second.
_TIED_RECURATION = _HEADER + _clingen("Limited", "2019-03-05T16:00:00.000Z", "ccc")
#: A curation the source published with no date at all.
_UNDATED_RECURATION = _HEADER + _clingen("Moderate", "", "ddd")

_YAML = """\
schema_version: '1.0'
module:
  name: gv_currency
  title: GV Currency
  description: currency of a gene-disease curation
  report_title: GV Currency
defaults:
  curator: test
  method: manual
genome_build: GRCh38
"""


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs80357906,A/G,risk,c,BRCA1\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs80357906,12345678\n", encoding="utf-8")
    return spec


def _row(**kwargs) -> GeneValidityRow:
    base = dict(
        gene="BRCA1", disease_id="MONDO:0003582", moi="autosomal_dominant",
        submitter=_PANEL, dataset="clingen_gene_validity_2026-08-13", source="clingen",
        status="resolved",
    )
    return GeneValidityRow(**{**base, **kwargs})


# ── the merge really does append, and the old test could not have seen it ───────────────────────


def test_a_recuration_is_appended_because_the_id_carries_its_own_timestamp(tmp_path: Path) -> None:
    """The finding itself, reproduced end to end against the real merge path.

    Two things are asserted rather than one, because the pair is the defect: the row count grows AND
    the two rows disagree. A count alone would pass on a duplicate of the same verdict.
    """
    spec = _spec(tmp_path)
    first = enrich_gene_validity(spec, export_text=_FIRST_CURATION)
    second = enrich_gene_validity(spec, export_text=_RECURATION)

    assert len(first.rows) == 1
    assert len(second.rows) == 2
    assert {r.classification for r in second.rows} == {"definitive", "refuted"}
    # The ids differ only by the timestamp they embed, which is why the key missed.
    assert len({r.assertion_id for r in second.rows}) == 2


def test_re_running_the_identical_export_still_adds_nothing(tmp_path: Path) -> None:
    """Merge-not-clobber is unchanged, stated here so the test above cannot be read as breaking it.

    This is also the shape of the test that existed and could not see the defect: identical bytes
    carry identical ids, the key matches, and the file does not grow whatever is wrong with it.
    """
    spec = _spec(tmp_path)
    first = enrich_gene_validity(spec, export_text=_FIRST_CURATION)
    again = enrich_gene_validity(spec, export_text=_FIRST_CURATION)

    assert len(again.rows) == len(first.rows) == 1


# ── the derivation, as a function ───────────────────────────────────────────────────────────────


def test_the_newest_curation_is_current_and_the_earlier_one_is_kept() -> None:
    """Newest `classification_date` wins, and nothing is deleted — S45's answer on a weaker signal.

    The date decides *ordering* and nothing else: it never says a classification is right, and both
    rows stay so the drift is visible.
    """
    old = _row(classification="definitive", classification_date="2019-03-05T16:00:00Z")
    new = _row(classification="refuted", classification_date="2024-07-11T16:00:00Z")

    assert classify_currency([old, new]) == [SUPERSEDED, CURRENT]
    # Order-independent: the answer is about the dates, not about where the rows sit in the file.
    assert classify_currency([new, old]) == [CURRENT, SUPERSEDED]


def test_a_lone_assertion_is_current_whether_or_not_it_is_dated() -> None:
    """There is nothing to order it against, so a check here cannot fail (`@tautology-zero`).

    This is what keeps the finding quiet on an ordinary module: almost every real group is a
    singleton, and a warning that fired on all of them would be noise rather than notice.
    """
    assert classify_currency([_row(classification_date="2019-03-05T16:00:00Z")]) == [CURRENT]
    assert classify_currency([_row(classification_date=None)]) == [CURRENT]


def test_a_claim_split_by_inheritance_mode_is_two_claims_not_a_supersession() -> None:
    """The grouping is the source's grain, so ACO2's two MOIs stay two live assertions.

    Getting this wrong would report every one of the 59 real ClinGen pairs that differ only by MOI as
    a superseded curation — the collision that put `moi` in the key in the first place.
    """
    ad = _row(moi="autosomal_dominant", classification_date="2022-04-18T16:00:00Z")
    ar = _row(moi="autosomal_recessive", classification_date="2019-04-18T16:00:00Z")

    assert classify_currency([ad, ar]) == [CURRENT, CURRENT]
    assert superseded_groups([ad, ar]) == []


def test_two_submitters_disagreeing_is_not_a_supersession() -> None:
    """The disagreement GenCC exists to publish must survive: submitter is in the group."""
    ambry = _row(submitter="Ambry Genetics", classification_date="2018-03-30T13:31:56Z")
    clingen = _row(submitter="ClinGen", classification_date="2024-07-11T16:00:00Z")

    assert classify_currency([ambry, clingen]) == [CURRENT, CURRENT]


def test_dataset_is_deliberately_outside_the_grouping() -> None:
    """A re-curation is by definition a later RELEASE of the same claim.

    Including `dataset` — the one difference from `_KEY_FALLBACK_FIELDS` — would put the two rows in
    different groups and answer "nothing was superseded" every single time, which is the failure this
    grouping exists to avoid.
    """
    old = _row(dataset="clingen_gene_validity_2019", classification_date="2019-03-05T16:00:00Z")
    new = _row(dataset="clingen_gene_validity_2024", classification_date="2024-07-11T16:00:00Z")

    assert classify_currency([old, new]) == [SUPERSEDED, CURRENT]


# ── the two edges, both withholding ─────────────────────────────────────────────────────────────


def test_a_tie_on_the_date_orders_nothing_and_names_no_winner() -> None:
    """`None` is the third state: no row is current and no row is superseded.

    Breaking the tie on `assertion_id` was rejected — an identifier carries no chronology, and sorting
    on one manufactures a winner out of a spelling.
    """
    a = _row(classification="definitive", classification_date="2019-03-05T16:00:00Z")
    b = _row(classification="limited", classification_date="2019-03-05T16:00:00Z")

    assert classify_currency([a, b]) == [None, None]
    assert superseded_groups([a, b]) == []
    assert len(undecidable_groups([a, b])) == 1


def test_an_undated_row_makes_its_whole_group_undecidable() -> None:
    """Calling it superseded because a dated sibling exists would assert a fact from an empty cell.

    Note the whole group withholds, not just the undated row: with one row unplaceable, the dated
    one cannot be called current either — being the newest of the rows that *stated* a date is not
    the same as being the newest.
    """
    dated = _row(classification="definitive", classification_date="2024-07-11T16:00:00Z")
    undated = _row(classification="moderate", classification_date=None)

    assert classify_currency([dated, undated]) == [None, None]
    assert len(undecidable_groups([dated, undated])) == 1


def test_the_two_findings_are_reported_apart() -> None:
    """A superseded group and an unorderable one ask the reader for different things.

    One number meaning two facts is the shape `@unreachable-not-absent` is about — the archive having
    moved on is not the archive having said too little to tell.
    """
    rows = [
        _row(gene="BRCA1", classification_date="2019-03-05T16:00:00Z"),
        _row(gene="BRCA1", classification_date="2024-07-11T16:00:00Z"),
        _row(gene="PALB2", classification_date="2020-01-01T00:00:00Z"),
        _row(gene="PALB2", classification_date="2020-01-01T00:00:00Z"),
    ]

    assert [g[0] for g in superseded_groups(rows)] == ["BRCA1"]
    assert [g[0] for g in undecidable_groups(rows)] == ["PALB2"]


# ── the enricher reports it and refuses nothing, in either mode ─────────────────────────────────


@pytest.mark.parametrize("mode", ["best_effort", "strict"])
def test_the_pass_reports_a_supersession_and_raises_in_neither_mode(
    tmp_path: Path, mode: str
) -> None:
    """A curating body re-curating is the source working, not the module being wrong.

    `strict` here is a *report*, not a refusal to have looked — the pass's own argument for `missing`,
    and the stronger form of it: the only edit available to an author is deleting a row, which
    falsifies the record rather than repairing it.
    """
    spec = _spec(tmp_path)
    enrich_gene_validity(spec, export_text=_FIRST_CURATION)
    result = enrich_gene_validity(spec, export_text=_RECURATION, mode=mode)

    assert result.superseded == [f"BRCA1/MONDO:0003582/autosomal_dominant/{_PANEL}"]
    assert result.undecidable == []
    assert len(result.rows) == 2, "both rows are kept — the drift stays visible"


@pytest.mark.parametrize("export", [_TIED_RECURATION, _UNDATED_RECURATION])
def test_the_pass_reports_an_unorderable_claim_as_its_own_thing(tmp_path: Path, export: str) -> None:
    spec = _spec(tmp_path)
    enrich_gene_validity(spec, export_text=_FIRST_CURATION)
    result = enrich_gene_validity(spec, export_text=export)

    assert result.undecidable == [f"BRCA1/MONDO:0003582/autosomal_dominant/{_PANEL}"]
    assert result.superseded == []


def test_an_ordinary_single_curation_reports_neither(tmp_path: Path) -> None:
    """The zero that must not be printed: nothing to say means nothing said."""
    result = enrich_gene_validity(_spec(tmp_path), export_text=_FIRST_CURATION)

    assert result.superseded == []
    assert result.undecidable == []


# ── the compiler warns, publishes the current verdict, and moves no signature ───────────────────


def _compiled(tmp_path: Path, exports: list[str], out: str = "out"):
    spec = _spec(tmp_path)
    for export in exports:
        enrich_gene_validity(spec, export_text=export)
    return spec, compile_module(spec, tmp_path / out)


def test_the_manifest_publishes_the_current_verdict_rather_than_the_pair(tmp_path: Path) -> None:
    """The reported harm, gone: `['definitive', 'refuted']` was the published pair.

    `row_count` is asserted beside it, because the fix must be *which verdict is published* and not
    *a row being dropped* — the rows are all still in the parquet.
    """
    _, result = _compiled(tmp_path, [_FIRST_CURATION, _RECURATION])
    assert result.success, result.errors

    block = result.manifest.gene_validity
    assert block.classifications == ["refuted"]
    assert block.row_count == 2
    assert block.superseded_count == 1


def test_an_unorderable_claim_still_publishes_both_classifications(tmp_path: Path) -> None:
    """Withholding, in the manifest: picking one would name a winner the data does not."""
    _, result = _compiled(tmp_path, [_FIRST_CURATION, _TIED_RECURATION])
    assert result.success, result.errors

    assert result.manifest.gene_validity.classifications == ["definitive", "limited"]
    assert result.manifest.gene_validity.superseded_count == 0


@pytest.mark.parametrize("strict", [False, True])
def test_the_finding_is_a_warning_in_both_modes_and_never_an_error(
    tmp_path: Path, strict: bool
) -> None:
    """`strict` means *reproducible artifact*, which a module carrying two curations still is.

    Asserted as *this finding never becomes an error*, rather than as *the compile succeeds*: this
    fixture injects no `resolution.csv`, so `--strict` refuses it for an unrelated reason, and a
    success assertion would be measuring that instead. The claim under test is that the currency
    finding sits in `warnings` in both modes and contributes nothing to `errors`.
    """
    spec = _spec(tmp_path)
    for export in (_FIRST_CURATION, _RECURATION):
        enrich_gene_validity(spec, export_text=export)
    result = compile_module(spec, tmp_path / "out", strict=strict)

    assert any("superseded and kept" in w for w in result.warnings)
    assert not any("superseded and kept" in e for e in result.errors)
    assert not any("gene_validity" in e for e in result.errors)


def test_the_finding_is_reported_once_though_two_passes_compute_it(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` as its pre-flight, so both reach the same sentence.

    The message embeds a count, which is the case `@no-rerun-with-counts` warns about — a doubled
    line would double `warnings_summary`'s number and the manifest would publish two. Both passes read
    the same post-overlay rows, so the counts agree and the message dedup collapses them; this pins
    that rather than leaving it to be noticed when the number is wrong.
    """
    spec = _spec(tmp_path)
    for export in (_FIRST_CURATION, _RECURATION):
        enrich_gene_validity(spec, export_text=export)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors

    summary = result.manifest.compilation.warnings_summary
    assert summary["gene_validity_superseded"] == 1
    assert sum(summary.values()) == len(result.manifest.compilation.warnings)


def test_both_codes_are_carried_because_no_authored_edit_clears_them() -> None:
    """Membership is a claim about REMEDIATION: the author's only move is falsifying the record."""
    assert {"gene_validity_superseded", "gene_validity_currency_undecidable"} <= CARRIED_WARNING_CODES


def test_the_pre_flight_reports_what_the_compile_reports(tmp_path: Path) -> None:
    """Parity by check (`@parity-by-check`): a green `validate` then a warning is what it prevents."""
    spec = _spec(tmp_path)
    for export in (_FIRST_CURATION, _RECURATION):
        enrich_gene_validity(spec, export_text=export)

    checked = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out")

    superseded = [w for w in checked.warnings if "superseded and kept" in w]
    assert superseded, checked.warnings
    assert superseded[0] in compiled.manifest.compilation.warnings


def test_no_signature_moves_because_nothing_is_stored(tmp_path: Path) -> None:
    """The whole argument for deriving: no column changed, so no existing module recompiles anew.

    Computed by compiling the same spec twice rather than against a recorded constant — a hardcoded
    hash would pass while measuring nothing.
    """
    spec, first = _compiled(tmp_path, [_FIRST_CURATION, _RECURATION], out="a1")
    second = compile_module(spec, tmp_path / "a2")

    assert first.manifest.gene_validity.signature == second.manifest.gene_validity.signature
    assert first.manifest.artifact.digest == second.manifest.artifact.digest


def test_superseded_count_survives_the_round_trip(tmp_path: Path) -> None:
    """The gate the field was accepted under: a derived manifest number must not move on lap 2.

    `gene_validity.csv` is rebuilt whole from `gene_validity.parquet` — no row is dropped on the way,
    unlike `literature.csv` — so the row set is identical and the derivation over it is too. Asserted
    rather than assumed, because a published field that differs between a module and its own round
    trip is exactly what RM137 is filed about.
    """
    spec, first = _compiled(tmp_path, [_FIRST_CURATION, _RECURATION], out="a1")
    assert first.manifest.gene_validity.superseded_count == 1

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors

    assert second.manifest.gene_validity.superseded_count == 1
    assert second.manifest.gene_validity.classifications == ["refuted"]
    assert second.manifest.gene_validity.row_count == 2
    # And the warning too, which is the other half of the same property.
    assert second.manifest.compilation.warnings_summary.get("gene_validity_superseded") == 1
