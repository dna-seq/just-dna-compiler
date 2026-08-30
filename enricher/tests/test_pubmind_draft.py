"""PubMind → variants.csv (RM134 § C) — `draft-panel --source pubmind`.

What is pinned here is what the design decided rather than what the code happens to do: the gene map
is ClinVar's own per-record attribution and never a span, a contested coordinate is withheld with its
PVIDs named, the withheld classes account for every candidate as an equality over the reason set, and
the worklist is a property of the file rather than of the run that wrote it.

Fixtures are built through the builders' own schema so a column rename upstream breaks these tests
rather than silently making them test a different table.
"""

import csv
import io
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.cli import PANEL_SOURCES, app
from just_dna_enricher.licensing import PUBMIND_TERMS, sources_path
from just_dna_enricher.lookup import lookup_variant
from just_dna_enricher.provenance import DRAFT_PROJECTIONS, draft_digest, drafted_unchanged
from just_dna_enricher.pubmind_build import _schema as pubmind_schema
from just_dna_enricher.pubmind_draft import (
    DEFAULT_MIN_CONFIDENCE,
    PUBMIND_WITHHELD_REASONS,
    PubMindDraftError,
    _group_by_key,
    _withhold_reason,
    draft_gene_panel_from_pubmind,
    gene_positions,
    pubmind_dataset_label,
    select_by_positions,
)
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.sources import SourceRow, taints_commercial_use
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from typer.testing import CliRunner

# ── Fixtures, in the real on-disk layouts ───────────────────────────────────────────────────────

#: Two BRCA1 positions ClinVar records, plus one it records for a different gene, so "the map is
#: ClinVar's attribution" is testable rather than assumed.
_CLINVAR = [
    {
        "chrom": "17", "start": 43093220, "ref": "C", "alt": "T", "rsid": "rs80357382",
        "gene": "BRCA1", "clin_sig": "pathogenic", "review_status": "criteria_provided",
        "review_stars": 2, "condition": "Breast-ovarian cancer", "variation_id": "17661",
    },
    {
        "chrom": "17", "start": 43093240, "ref": "G", "alt": "A", "rsid": "rs80357906",
        "gene": "BRCA1", "clin_sig": "uncertain_significance",
        "review_status": "criteria_provided", "review_stars": 1,
        "condition": "Breast-ovarian cancer", "variation_id": "17662",
    },
    {
        "chrom": "17", "start": 43093260, "ref": "A", "alt": "G", "rsid": "rs28897696",
        "gene": "BRCA2", "clin_sig": "benign", "review_status": "criteria_provided",
        "review_stars": 2, "condition": "Breast-ovarian cancer", "variation_id": "17663",
    },
]


def _pubmind_record(**overrides) -> dict:
    record = {
        "chrom": "17", "start": 43093220, "ref": "C", "alt": "T", "pvid": "PV1",
        "clin_sig": "pathogenic", "clin_sig_raw": "Pathogenic",
        "pathogenicity_score": 0.9, "confidence": 2, "derivation": "direct",
    }
    record.update(overrides)
    return record


def _clinvar_snapshot(tmp_path: Path, records: list[dict] | None = None) -> Path:
    root = tmp_path / "clinvar"
    (root / "data").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records if records is not None else _CLINVAR).write_parquet(
        root / "data" / "chr.parquet"
    )
    (root / "release.json").write_text(
        '{"clinvar_file_date": "2026-06-27"}', encoding="utf-8"
    )
    return root


def _pubmind_snapshot(
    tmp_path: Path, records: list[dict], *, dataset: str | None = "pubmind_abcdef123456",
    name: str = "pubmind",
) -> Path:
    """A PubMind snapshot through the builder's own schema, so a rename upstream fails here."""
    root = tmp_path / name
    (root / "data").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records, schema=pubmind_schema()).write_parquet(root / "data" / "pubmind.parquet")
    (root / "release.json").write_text(
        json.dumps({"dataset": dataset, "genome_build": "GRCh38"}), encoding="utf-8"
    )
    return root


def _spec(tmp_path: Path, name: str = "spec") -> Path:
    spec = tmp_path / name
    spec.mkdir(parents=True, exist_ok=True)
    return spec


#: The licence sidecar's current filename, derived rather than named: it gained a second spelling
#: in 0.6 and the older one retires at 1.0, so a literal would pin this file to whichever was
#: current when it was written.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


def _tree(spec: Path) -> dict[str, bytes]:
    """Every byte under a spec directory, so "wrote nothing" is measured rather than sampled."""
    return {
        str(p.relative_to(spec)): p.read_bytes() for p in sorted(spec.rglob("*")) if p.is_file()
    }


def _draft(spec: Path, tmp_path: Path, pubmind: list[dict], **kwargs):
    return draft_gene_panel_from_pubmind(
        spec, ["BRCA1"],
        snapshot=_clinvar_snapshot(tmp_path),
        pubmind_snapshot=_pubmind_snapshot(tmp_path, pubmind),
        **kwargs,
    )


# ── The gene map ────────────────────────────────────────────────────────────────────────────────


def test_the_gene_map_is_clinvars_own_attribution_and_never_a_span(tmp_path: Path) -> None:
    """A min/max span would sweep in the BRCA2 position sitting between the two BRCA1 ones.

    That is the whole reason the map is position-exact: a span invents a boundary this repo
    deliberately does not hold, and the invented boundary writes a `gene` cell that is a false claim.
    """
    reference = _clinvar_snapshot(tmp_path)
    mapping = gene_positions(reference, ["BRCA1"])
    assert set(mapping) == {("17", 43093220), ("17", 43093240)}
    assert all(genes == {"BRCA1"} for genes in mapping.values())
    # the BRCA2 position lies strictly between the two, so any span-based map would include it
    brca2 = next(iter(gene_positions(reference, ["BRCA2"])))
    assert min(p[1] for p in mapping) < brca2[1]


def test_the_map_ignores_the_clinical_dials_because_it_is_a_universe_not_a_selection(
    tmp_path: Path,
) -> None:
    """The uncertain 1-star BRCA1 record is in the map: filtering it would narrow which positions
    PubMind is asked about, invisibly, while looking like a filter on PubMind's own calls."""
    mapping = gene_positions(_clinvar_snapshot(tmp_path), ["BRCA1"])
    assert ("17", 43093240) in mapping


def test_a_gene_clinvar_does_not_record_refuses_with_the_reason_rather_than_drafting_nothing(
    tmp_path: Path,
) -> None:
    result = draft_gene_panel_from_pubmind(
        _spec(tmp_path), ["NOTAGENE"],
        snapshot=_clinvar_snapshot(tmp_path),
        pubmind_snapshot=_pubmind_snapshot(tmp_path, [_pubmind_record()]),
    )
    assert result.reports == []
    assert any("no gene map to ask" in w for w in result.warnings)


def test_a_position_two_requested_genes_claim_leaves_the_cell_empty_and_says_so(
    tmp_path: Path,
) -> None:
    """Both other readings are wrong to write: `BRCA1, BRCA2` is not a symbol any lookup resolves,
    and choosing one is the gene model this pass goes to ClinVar precisely to avoid inventing. The
    row is still drafted — the coordinate is its identity."""
    overlapping = [
        *_CLINVAR,
        {
            "chrom": "17", "start": 43093220, "ref": "C", "alt": "T", "rsid": "rs80357382",
            "gene": "BRCA2", "clin_sig": "pathogenic", "review_status": "criteria_provided",
            "review_stars": 2, "condition": "Breast-ovarian cancer", "variation_id": "17664",
        },
    ]
    spec = _spec(tmp_path)
    result = draft_gene_panel_from_pubmind(
        spec, ["BRCA1", "BRCA2"],
        snapshot=_clinvar_snapshot(tmp_path, overlapping),
        pubmind_snapshot=_pubmind_snapshot(tmp_path, [_pubmind_record()]),
    )
    (row,) = _rows(spec / "variants.csv")
    assert row["gene"] == ""
    assert row["chrom"] == "17" and row["clin_sig"] == "pathogenic"
    (line,) = [w for w in result.warnings if "more than one of the genes" in w]
    assert "17:43093220 C>T" in line and "BRCA1/BRCA2" in line


def test_a_position_one_gene_claims_still_carries_that_gene(tmp_path: Path) -> None:
    """The contrast, so the assertion above is about ambiguity rather than about `gene` never being
    written at all."""
    spec = _spec(tmp_path)
    result = _draft(spec, tmp_path, [_pubmind_record()])
    (row,) = _rows(spec / "variants.csv")
    assert row["gene"] == "BRCA1"
    assert not [w for w in result.warnings if "more than one of the genes" in w]


def test_the_missing_clinvar_snapshot_is_this_passs_own_error_and_says_why_it_needs_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pass owes its caller its own exception type, and an author told 'no ClinVar snapshot' by a
    PubMind command has been handed a puzzle unless the message says what it is wanted for."""
    monkeypatch.setenv("JUST_DNA_CLINVAR_CACHE", str(tmp_path / "empty"))
    with pytest.raises(PubMindDraftError) as excinfo:
        draft_gene_panel_from_pubmind(
            _spec(tmp_path), ["BRCA1"],
            pubmind_snapshot=_pubmind_snapshot(tmp_path, [_pubmind_record()]),
            offline=True,
        )
    assert "names no gene" in str(excinfo.value)


# ── Reading the snapshot ────────────────────────────────────────────────────────────────────────


def test_a_position_between_two_wanted_ones_is_not_returned_by_the_range_query(
    tmp_path: Path,
) -> None:
    """The reader narrows a range query to the exact positions; the range is an implementation
    detail and must not leak a row into the answer."""
    records = [
        _pubmind_record(),
        _pubmind_record(start=43093230, pvid="PV_BETWEEN"),
        _pubmind_record(start=43093240, ref="G", alt="A", pvid="PV2"),
    ]
    reference = _pubmind_snapshot(tmp_path, records)
    found = select_by_positions(reference, [("17", 43093220), ("17", 43093240)])
    assert {r["pvid"] for r in found} == {"PV1", "PV2"}


def test_the_dataset_label_is_read_back_rather_than_re_derived(tmp_path: Path) -> None:
    reference = _pubmind_snapshot(tmp_path, [_pubmind_record()])
    assert pubmind_dataset_label(reference) == "pubmind_abcdef123456"
    unlabelled = _pubmind_snapshot(tmp_path, [_pubmind_record()], dataset=None, name="unlabelled")
    assert pubmind_dataset_label(unlabelled) is None


def test_a_missing_snapshot_names_the_command_that_builds_one(tmp_path: Path) -> None:
    with pytest.raises(PubMindDraftError) as excinfo:
        draft_gene_panel_from_pubmind(
            _spec(tmp_path), ["BRCA1"],
            snapshot=_clinvar_snapshot(tmp_path),
            pubmind_snapshot=tmp_path / "nowhere",
        )
    assert "pubmind build" in str(excinfo.value)


# ── What is written, and what is deliberately not ───────────────────────────────────────────────


def test_identity_is_the_whole_coordinate_and_no_clinvar_flag_is_folded_from_pubmind(
    tmp_path: Path,
) -> None:
    """PubMind has no rsID column, so the coordinate goes in whole; and `clinvar`/`pathogenic`/
    `benign` are ClinVar flags by their own field descriptions, so a PubMind call may not set them —
    a position appearing in ClinVar's gene map says nothing about whether this allele is in ClinVar.
    """
    spec = _spec(tmp_path)
    _draft(spec, tmp_path, [_pubmind_record()])
    (row,) = _rows(spec / "variants.csv")
    assert (row["chrom"], row["start"], row["ref"], row["alts"]) == ("17", "43093220", "C", "T")
    assert row["rsid"] == ""
    assert row["clin_sig"] == "pathogenic"
    assert row["genotype"] == TEMPLATE_PLACEHOLDER
    for never in ("clinvar", "pathogenic", "benign", "phenotype", "weight", "direction"):
        assert row[never] == "", f"{never} was filled from a source that does not state it"
    # `state` is a fold of the source's own call, exactly as it is on the ClinVar path
    assert row["state"] == "risk"
    assert "PV1" in row["conclusion"] and "confidence 2" in row["conclusion"]


def test_the_conclusion_carries_the_derivation_because_no_authored_column_holds_it(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path)
    _draft(spec, tmp_path, [_pubmind_record(derivation="codon")])
    (row,) = _rows(spec / "variants.csv")
    assert "derivation codon" in row["conclusion"]


def test_no_studies_row_is_drafted_and_the_missing_grounding_is_stated(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = _draft(spec, tmp_path, [_pubmind_record()])
    assert not (spec / "studies.csv").exists()
    assert [r.csv_name for r in result.reports] == ["variants.csv"]
    assert any("carries no PMID" in w for w in result.warnings)


# ── Multiplicity: kept, counted, never collapsed ────────────────────────────────────────────────


def test_a_contested_coordinate_is_withheld_and_every_pvid_and_call_is_named(
    tmp_path: Path,
) -> None:
    """Choosing between disagreeing records needs an ordering nobody defined. The disagreement is
    the finding, so no row is written and both calls are reported."""
    spec = _spec(tmp_path)
    result = _draft(
        spec, tmp_path,
        [_pubmind_record(), _pubmind_record(pvid="PV1b", clin_sig="benign", clin_sig_raw="Benign")],
    )
    assert result.withheld["contested_key"] == 1
    assert result.drafted == 0
    (line,) = [w for w in result.warnings if "disagree about" in w]
    assert "17:43093220 C>T" in line
    assert "benign" in line and "pathogenic" in line
    assert not (spec / "variants.csv").exists()


def test_an_agreeing_multi_record_coordinate_is_one_row_that_says_how_many_agreed(
    tmp_path: Path,
) -> None:
    """Agreement is not contestation: several PVIDs saying the same thing collapse to one row, and
    the record count and every PVID stay visible in the transcription."""
    spec = _spec(tmp_path)
    result = _draft(
        spec, tmp_path, [_pubmind_record(), _pubmind_record(pvid="PV1b", confidence=3)]
    )
    (row,) = _rows(spec / "variants.csv")
    assert result.drafted == 1
    assert "2 record(s)" in row["conclusion"]
    assert "PV1" in row["conclusion"] and "PV1b" in row["conclusion"]
    # the best evidence among the agreeing records, never the first one encountered
    assert "confidence 3" in row["conclusion"]


def test_a_filter_cannot_make_a_contested_coordinate_look_uncontested(tmp_path: Path) -> None:
    """The trap this design exists to avoid: if `--clin-sig` or `--min-confidence` ran before the
    contestation test, removing the dissenting record would pick the winner exactly as `mode()`
    would — and the run would report a confident row where the source disagrees with itself.
    """
    dissenting = _pubmind_record(pvid="PV1b", clin_sig="benign", clin_sig_raw="Benign", confidence=0)
    spec = _spec(tmp_path)
    # the dissenter is outside --clin-sig AND below the floor, so either dial would have hidden it
    result = _draft(
        spec, tmp_path, [_pubmind_record(), dissenting],
        clin_sig=frozenset({"pathogenic"}), min_confidence=2,
    )
    assert result.withheld["contested_key"] == 1
    assert result.drafted == 0

    # and the same key with the dissenter genuinely absent does draft, so the assertion above is
    # about contestation rather than about the dials refusing everything
    other = _spec(tmp_path, "spec2")
    assert _draft(other, tmp_path, [_pubmind_record()], min_confidence=2).drafted == 1


# ── The withheld classes ────────────────────────────────────────────────────────────────────────


def test_every_candidate_is_drafted_or_withheld_under_exactly_one_walked_reason(
    tmp_path: Path,
) -> None:
    """An equality over the reason set, never a floor: a sixth reason cannot arrive without joining
    the sum, and a key counted twice or not at all breaks it."""
    records = [
        _pubmind_record(),                                                    # drafted
        _pubmind_record(pvid="PVc", clin_sig="benign", clin_sig_raw="Benign"),  # contested with PV1
        _pubmind_record(start=43093240, ref="G", alt="GA", pvid="PVi", derivation="indel"),
        _pubmind_record(start=43093240, ref="G", alt="A", pvid="PVb",
                        clin_sig="benign", clin_sig_raw="Benign"),            # outside --clin-sig
        _pubmind_record(start=43093240, ref="G", alt="C", pvid="PVn", confidence=None),
        _pubmind_record(start=43093240, ref="G", alt="T", pvid="PVl", confidence=0),
    ]
    result = _draft(_spec(tmp_path), tmp_path, records)
    assert set(result.withheld) == set(PUBMIND_WITHHELD_REASONS)
    assert result.candidates == 5
    assert result.accounts_for_every_candidate()
    assert result.withheld == {
        "contested_key": 1, "indel_derivation": 1, "clin_sig_not_selected": 1,
        "confidence_not_stated": 1, "below_min_confidence": 1,
    }


def test_a_confidence_the_source_did_not_state_is_not_a_confidence_below_the_floor(
    tmp_path: Path,
) -> None:
    """`None` is never `False`, and it is never 0 either: reading an unstated confidence as 0 would
    invent a reading, so the two classes are counted and reported apart."""
    unstated = _pubmind_record(confidence=None)
    below = _pubmind_record(confidence=0)
    assert _withhold_reason(
        _key_of([unstated]), clin_sig=frozenset({"pathogenic"}), min_confidence=1
    ) == "confidence_not_stated"
    assert _withhold_reason(
        _key_of([below]), clin_sig=frozenset({"pathogenic"}), min_confidence=1
    ) == "below_min_confidence"

    result = _draft(_spec(tmp_path), tmp_path, [unstated])
    lines = [w for w in result.warnings if "confidence" in w and "coordinate(s)" in w]
    assert len(lines) == 1
    assert "state no confidence at all" in lines[0]


def test_a_withheld_class_that_withheld_nothing_reports_no_zero(tmp_path: Path) -> None:
    """A check that cannot fail must not report a zero — the counts are still all carried on the
    result, where the accounting equality reads them."""
    result = _draft(_spec(tmp_path), tmp_path, [_pubmind_record()])
    assert result.withheld == dict.fromkeys(PUBMIND_WITHHELD_REASONS, 0)
    assert not [w for w in result.warnings if "0 coordinate(s)" in w]


def test_absence_in_the_corpus_is_reported_as_absence_rather_than_agreement(
    tmp_path: Path,
) -> None:
    """A position PubMind says nothing about means no paper survived their triage — not a benign
    call, and not a disagreement."""
    result = _draft(_spec(tmp_path), tmp_path, [_pubmind_record()])
    (line,) = [w for w in result.warnings if "states nothing at" in w]
    assert line.startswith("PubMind states nothing at 1 of the 2 position(s)")
    assert "not a benign call and not a disagreement" in line
    assert "cannot be reached by gene at all" in line


def test_the_indel_class_names_left_normalization_as_the_reason(tmp_path: Path) -> None:
    result = _draft(
        _spec(tmp_path), tmp_path, [_pubmind_record(ref="C", alt="CT", derivation="indel")]
    )
    (line,) = [w for w in result.warnings if "length-changing" in w]
    assert "left-normalized" in line


# ── The worklist seam (RM71), inherited rather than reproduced ───────────────────────────────────


def test_a_second_run_reprints_the_open_stub_worklist_because_the_stubs_are_still_open(
    tmp_path: Path,
) -> None:
    """The once-only defect RM71 removed on the ClinVar path, inherited here rather than repeated.

    A worklist scoped to `report.added` says nothing on a re-run, because a re-run adds nothing — and
    the alleles a stubbed genotype must be written from were then stated exactly once, in a stream
    the author had no way to ask again.
    """
    spec = _spec(tmp_path)
    first = _draft(spec, tmp_path, [_pubmind_record()])
    worklist = [w for w in first.warnings if w.strip().startswith("genotype for ")]
    assert len(worklist) == first.added_for("variants.csv") == 1

    again = _draft(spec, tmp_path, [_pubmind_record()])
    assert again.added_for("variants.csv") == 0
    assert [w for w in again.warnings if w.strip().startswith("genotype for ")] == worklist


def test_the_worklist_names_pubmind_as_the_publisher_of_the_alleles(tmp_path: Path) -> None:
    """A line reading "ClinVar publishes C>T" about a row ClinVar never spoke of is a false
    attribution in the one place an author cross-references."""
    result = _draft(_spec(tmp_path), tmp_path, [_pubmind_record()])
    (line,) = [w for w in result.warnings if w.strip().startswith("genotype for ")]
    assert "PubMind publishes C>T" in line
    assert "ClinVar publishes" not in line


def test_the_state_stub_line_names_pubmind_and_groups_by_the_call(tmp_path: Path) -> None:
    result = _draft(
        _spec(tmp_path), tmp_path,
        [_pubmind_record(clin_sig="uncertain_significance", clin_sig_raw="Uncertain significance")],
        clin_sig=frozenset({"uncertain_significance"}),
    )
    (line,) = [w for w in result.warnings if "`state` placeholder" in w]
    assert "PubMind states no direction" in line
    assert "uncertain_significance" in line


def test_a_dry_run_appends_nothing_at_all_and_still_answers_the_worklist(tmp_path: Path) -> None:
    """`--dry-run` means here what it means in `draft` and `draft-panel`: the report is the same and
    not one byte moves — including the licence sidecar, which a draft otherwise writes."""
    spec = _spec(tmp_path)
    # A real run first, so the comparison covers a spec that already holds both files a draft writes:
    # an empty directory would pass this assertion without the licence sidecar being tested at all.
    _draft(spec, tmp_path, [_pubmind_record()])
    before = _tree(spec)
    assert {"variants.csv", _LICENCE_CSV} <= set(before)

    second = _pubmind_record(start=43093240, ref="G", alt="A", pvid="PV2")
    result = _draft(spec, tmp_path, [_pubmind_record(), second], dry_run=True)
    assert _tree(spec) == before
    assert result.drafted == 2 and result.added_for("variants.csv") == 1
    # and the worklist still answers, over the file's open stub and the row a real run would add
    assert len([w for w in result.warnings if w.strip().startswith("genotype for ")]) == 2


# ── Licensing, provenance, and the self-agreement trap ──────────────────────────────────────────


def test_the_licence_row_records_null_on_every_term_and_the_draft_is_not_skipped(
    tmp_path: Path,
) -> None:
    """Unknown terms warn and never gate. `check_declared_use` is a gate on *fetching*, and nothing
    is fetched here — the operator built the snapshot themselves — so the reason is reported in the
    source's own words and the rows are written."""
    spec = _spec(tmp_path)
    result = _draft(spec, tmp_path, [_pubmind_record()])
    assert result.added_for("variants.csv") == 1
    assert any("terms of the ANNOVAR-redistributed table could not be established" in w
               for w in result.warnings)

    rows, errors, _ = load_csv_rows(sources_path(spec, error=RuntimeError), SourceRow, "sources.csv")
    assert not errors
    (row,) = [r for r in rows if r.source == PUBMIND_TERMS.source]
    assert (row.license, row.share_alike, row.commercial_use, row.redistribution) == (
        None, None, None, None
    )
    assert row.dataset == "pubmind_abcdef123456"
    assert row.declared_use == "unstated"
    # What § A pinned, restated over the row this provider actually wrote: an unknown does not taint,
    # so the compile does not refuse — `taints_commercial_use` requires an explicit `False`.
    assert taints_commercial_use(row) is False


def test_the_drafted_call_is_an_establishable_copy_that_stops_matching_once_it_is_edited(
    tmp_path: Path,
) -> None:
    """`@draft-digest`: a module drafted from PubMind and then cross-checked against PubMind agrees
    with itself, so the provider stamps a digest of the column the check reads. A match means no
    checked value has moved, which is what lets a check establish the tautology rather than assume it.
    """
    spec = _spec(tmp_path)
    _draft(spec, tmp_path, [_pubmind_record()])
    path = sources_path(spec, error=RuntimeError)
    rows, errors, _ = load_csv_rows(path, SourceRow, "sources.csv")
    assert not errors
    recorded = [r.draft_digest for r in rows if r.source == PUBMIND_TERMS.source]
    assert recorded == [draft_digest(spec, "pubmind")]
    assert drafted_unchanged(spec, "pubmind", rows) is True

    # filling the genotype stub is not an edit to the call, so the copy still stands
    text = (spec / "variants.csv").read_text().replace(TEMPLATE_PLACEHOLDER, "C/T", 1)
    (spec / "variants.csv").write_text(text, encoding="utf-8")
    assert drafted_unchanged(spec, "pubmind", rows) is True

    # editing the cross-examined cell is, and the check then has something real to compare
    edited = (spec / "variants.csv").read_text().replace("pathogenic", "benign")
    (spec / "variants.csv").write_text(edited, encoding="utf-8")
    assert drafted_unchanged(spec, "pubmind", rows) is False


def test_the_projection_is_the_coordinate_because_the_source_states_no_rsid() -> None:
    """The one `DRAFT_PROJECTIONS` identity that is not its provider's `match_on`, deliberately: an
    rs-number an author later adds is a change to the row's spelling, not to the call."""
    projection = DRAFT_PROJECTIONS["pubmind"]
    assert projection.table == "variants.csv"
    assert projection.checked == ("clin_sig",)
    assert "rsid" not in projection.identity
    assert set(projection.identity) == {"chrom", "start", "ref", "alts"}


def test_the_default_confidence_floor_is_a_floor_rather_than_zero() -> None:
    """A confidence-0 row is one paragraph of one paper; the floor is the `min_review_stars`
    analogue and defaults above the bottom of the scale for the same reason."""
    assert DEFAULT_MIN_CONFIDENCE > 0


# ── helpers used by the unit-level assertions above ─────────────────────────────────────────────


def _key_of(records: list[dict]):
    """One `_Key` over `records`, built through the provider's own grouping."""
    (key,) = _group_by_key(records)
    return key


# ── The hint (§ D): reported, never written ─────────────────────────────────────────────────────


def _hint(tmp_path: Path, records: list[dict] | None):
    """`hint variant` at the fixture coordinate, offline, against a PubMind snapshot.

    `records=None` means *no snapshot*: an explicit path that holds no parquet resolves to `None`
    through the same ladder the command uses, so the third state is produced rather than mocked.
    """
    cache = (
        _pubmind_snapshot(tmp_path, records) if records is not None else tmp_path / "no-snapshot"
    )
    return lookup_variant(
        chrom="17", start=43093220, ref="C", alts="T", offline=True, pubmind_cache=cache,
    )


def test_the_hint_reports_pubminds_call_without_filling_the_cell_the_check_reads(
    tmp_path: Path,
) -> None:
    """`@hint-redundancy-bearing`, and sharper here than for ClinVar: `clin_sig` is the cell the
    concordance check cross-examines, so filling it from one of the authorities being compared would
    make the check agree with the source it is checking. There is no digest to rescue it one layer up.
    """
    hint = _hint(tmp_path, [_pubmind_record()])
    assert [r["pvid"] for r in hint.pubmind] == ["PV1"]
    offered = [a for a in hint.alterations if a.source == "pubmind"]
    assert [a.column for a in offered] == ["clin_sig"]
    assert offered[0].after == "pathogenic"
    assert offered[0].applied is False
    assert offered[0].refusal == "redundancy_bearing"


def test_the_hint_says_nobody_asked_rather_than_answering_nothing(tmp_path: Path) -> None:
    """No snapshot is the third state: it is operator-built and there is none to download, so an
    empty answer would otherwise read as 'PubMind states nothing here'."""
    hint = _hint(tmp_path, None)
    assert hint.pubmind == []
    (finding,) = [f for f in hint.findings if "PubMind was not consulted" in f.message]
    assert "$JUST_DNA_PUBMIND_CACHE" in finding.message
    assert finding.level == "info"


def test_an_absence_in_the_corpus_is_told_apart_from_nobody_having_asked(tmp_path: Path) -> None:
    """A snapshot that holds nothing at the allele is a different answer from no snapshot, and the
    two say different things."""
    elsewhere = _pubmind_record(start=43093240, ref="G", alt="A", pvid="PVX")
    hint = _hint(tmp_path, [elsewhere])
    assert hint.pubmind == []
    (finding,) = [f for f in hint.findings if "no paper survived their triage" in f.message]
    assert "not a benign call and not a disagreement" in finding.message
    assert not [f for f in hint.findings if "was not consulted" in f.message]


def test_the_hint_reports_every_record_at_a_contested_position_and_picks_none(
    tmp_path: Path,
) -> None:
    hint = _hint(
        tmp_path,
        [_pubmind_record(), _pubmind_record(pvid="PV1b", clin_sig="benign", clin_sig_raw="Benign")],
    )
    assert {r["pvid"] for r in hint.pubmind} == {"PV1", "PV1b"}
    assert {a.after for a in hint.alterations if a.source == "pubmind"} == {"pathogenic", "benign"}
    (warned,) = [f for f in hint.findings if "own records disagree" in f.message]
    assert warned.level == "warning"
    assert "none is picked" in warned.message


# ── The command surface ─────────────────────────────────────────────────────────────────────────

_runner = CliRunner()


def _invoke(spec: Path, tmp_path: Path, records: list[dict], *extra: str):
    return _runner.invoke(
        app,
        [
            "draft-panel", str(spec), "--gene", "BRCA1",
            "--snapshot", str(_clinvar_snapshot(tmp_path)),
            "--pubmind-cache", str(_pubmind_snapshot(tmp_path, records)),
            "--offline", *extra,
        ],
    )


def test_an_unknown_source_is_refused_by_name_with_the_ones_it_knows(tmp_path: Path) -> None:
    """A closed set, and the refusal lists it: `--source clinsig` is a typo an author can fix from
    the message rather than a stack trace."""
    result = _invoke(_spec(tmp_path), tmp_path, [_pubmind_record()], "--source", "clinsig")
    assert result.exit_code == 1
    output = result.output + (result.stderr or "")
    assert "is not an authority this command drafts from" in output
    for member in PANEL_SOURCES:
        assert member in output


def test_a_dial_belonging_to_the_other_authority_is_named_rather_than_ignored(
    tmp_path: Path,
) -> None:
    """A run that honoured neither the flag nor the author's expectation is the failure worth
    reporting before it happens — and the flag that *does* apply stays quiet."""
    result = _invoke(
        _spec(tmp_path), tmp_path, [_pubmind_record()],
        "--source", "pubmind", "--min-review-stars", "3", "--dry-run",
    )
    assert result.exit_code == 0
    output = result.output + (result.stderr or "")
    assert "--min-review-stars is a --source clinvar dial and does nothing" in output
    assert "--min-confidence is a" not in output


def test_the_clinvar_path_is_untouched_by_the_new_flag(tmp_path: Path) -> None:
    """`--source` defaults to clinvar, and a ClinVar draft still reports ClinVar as the publisher of
    the alleles — the shared worklist is parameterized, not rewritten."""
    result = _runner.invoke(
        app,
        [
            "draft-panel", str(_spec(tmp_path)), "--gene", "BRCA1",
            "--snapshot", str(_clinvar_snapshot(tmp_path)), "--offline", "--dry-run",
        ],
    )
    assert result.exit_code == 0
    output = result.output + (result.stderr or "")
    assert "ClinVar publishes" in output
    assert "PubMind" not in output


def test_one_reader_serves_both_passes_because_the_label_is_a_guard_key(tmp_path: Path) -> None:
    """`pubmind_dataset_label` has exactly one implementation, and both passes get that one.

    The drafter shipped with its own copy, under a comment saying to move the reader out "when a
    third reader lands" — but the `pubmind.py` twin already existed, landed by the concordance lane
    in the same release. Two copies is the specific thing `clinvar_dataset_label`'s docstring calls
    fatal: the label is the key `is_tautological_leg` matches on, so a drafter stamping
    `SourceRow.dataset` with one spelling and a check comparing against the other does not fail — it
    quietly never matches and the guard stops being able to fire.

    They had already diverged. The drafter's copy parsed `release.json` itself and called `.get` on
    whatever came back, so a release file holding a JSON array raised an unhandled `AttributeError`
    instead of withholding; the shared reader routes through `read_release`, which checks the payload
    is a mapping. That is the case asserted below, because it is the one that told them apart.
    """
    from just_dna_enricher import pubmind, pubmind_draft
    from just_dna_enricher.locations import RELEASE_FILENAME

    assert pubmind_draft.pubmind_dataset_label is pubmind.pubmind_dataset_label
    assert pubmind_draft._connect is pubmind._connect

    reference = tmp_path / "snapshot"
    reference.mkdir()
    (reference / RELEASE_FILENAME).write_text('["not", "a", "mapping"]', encoding="utf-8")

    # Withheld, not raised: an unreadable release is an unknown, and `None` is never a label
    # something could match.
    assert pubmind_draft.pubmind_dataset_label(reference) is None
