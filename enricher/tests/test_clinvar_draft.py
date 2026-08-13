"""ClinVar → variants.csv (0.5.1, RM26) — gene-panel drafting with the zygosity left to a human.

Real snapshot where one is present, expectations computed. What is pinned: identity is filled whole
or not at all, `genotype` is always a stub, rows land in their gene's block, and a re-run after the
human decides adds nothing.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.draft import PartialRow, RowOutcome
from just_dna_enricher.clinvar_draft import (
    DEFAULT_CLIN_SIG,
    _identity_cells,
    _refusal_summary,
    _row_cells,
    _study_rows,
    draft_gene_panel,
    sole_expressible_genotype,
)
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from just_dna_format.vrs import in_pseudoautosomal_region
from pydantic import ValidationError
from just_dna_format.layout import SOURCES_CSV, preferred_spelling

#: The licence sidecar's current filename, derived rather than named: it gained a second
#: spelling in 0.6 (RM51) and the older one retires at 1.0, so a literal here would pin a test
#: to whichever spelling happened to be current when it was written.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "interim" / "clinvar"
_needs_snapshot = pytest.mark.skipif(
    not (_SNAPSHOT / "data").is_dir(),
    reason="no local ClinVar snapshot (build it with `just-dna-enricher clinvar build`)",
)

_RECORD = {
    "chrom": "1", "start": 11796321, "ref": "G", "alt": "A", "rsid": "rs1801133",
    "gene": "MTHFR", "clin_sig": "pathogenic", "review_stars": 2,
    "condition": "Homocystinuria", "variation_id": "3520",
}


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


def test_identity_is_the_rsid_or_the_whole_coordinate_never_a_subset() -> None:
    """A lone `alts` on a position-only row mints a VRS id instead of `chrom:start:ref`, so a
    partial coordinate would silently change which variant the row *is*."""
    assert _identity_cells(_RECORD) == {"rsid": "rs1801133"}
    positional = {**_RECORD, "rsid": ""}
    assert _identity_cells(positional) == {
        "chrom": "1", "start": 11796321, "ref": "G", "alts": "A"
    }
    assert _identity_cells({**positional, "ref": ""}) is None  # incomplete → refused, not partial


def test_only_the_sources_own_call_is_folded_never_invented() -> None:
    cells = _row_cells(_RECORD)
    assert cells["clin_sig"] == "pathogenic"
    assert cells["state"] == "risk" and cells["pathogenic"] is True
    assert cells["clinvar"] is True
    assert "benign" not in cells
    # nothing ClinVar does not publish
    for never in ("weight", "direction", "effect_size", "effect_measure", "trait_efo_id",
                  "acmg_sf", "curator", "method", "genotype"):
        assert never not in cells


def test_an_unmapped_call_leaves_state_to_the_human() -> None:
    cells = _row_cells({**_RECORD, "clin_sig": "uncertain_significance"})
    assert "state" not in cells and "pathogenic" not in cells


@_needs_snapshot
def test_a_real_panel_drafts_stubs_in_gene_blocks(tmp_path: Path) -> None:
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    assert result.added_for("variants.csv") > 0
    rows = _rows(tmp_path / "variants.csv")
    assert len(rows) == result.added_for("variants.csv")
    # grounding evidence is drafted alongside, from ClinVar's own literature links
    assert result.added_for("studies.csv") > 0
    # every drafted row is a stub, for the gene asked for, with an identity
    assert {r["genotype"] for r in rows} == {TEMPLATE_PLACEHOLDER}
    assert {r["gene"] for r in rows} == {"MTHFR"}
    assert all(r["rsid"] or (r["chrom"] and r["start"] and r["ref"]) for r in rows)
    assert {r["clin_sig"] for r in rows} <= DEFAULT_CLIN_SIG
    # a source rows were copied out of must be accounted for
    assert (tmp_path / _LICENCE_CSV).is_file()


@_needs_snapshot
def test_a_second_gene_lands_in_its_own_block_and_a_re_run_adds_nothing(tmp_path: Path) -> None:
    draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    draft_gene_panel(tmp_path, ["BRCA1"], snapshot=_SNAPSHOT)
    genes = [r["gene"] for r in _rows(tmp_path / "variants.csv")]
    blocks = [g for i, g in enumerate(genes) if i == 0 or genes[i - 1] != g]
    assert len(blocks) == len(set(blocks)), "each gene must occupy one contiguous block"

    before = (tmp_path / "variants.csv").read_bytes()
    again = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    assert again.added == 0 and again.already_present > 0
    assert (tmp_path / "variants.csv").read_bytes() == before


@_needs_snapshot
def test_widening_an_earlier_gene_inserts_into_its_block_without_touching_cells(
    tmp_path: Path,
) -> None:
    """The delegated-insertion case: new rows for a gene already drafted must join it, and every
    row they push down keeps its cells byte-for-byte."""
    draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    draft_gene_panel(tmp_path, ["BRCA1"], snapshot=_SNAPSHOT)
    before = _rows(tmp_path / "variants.csv")
    before_cells = {tuple(r.items()) for r in before}

    result = draft_gene_panel(
        tmp_path, ["MTHFR"], snapshot=_SNAPSHOT,
        clin_sig=frozenset({"benign", "likely_benign"}),
    )
    assert result.added_for("variants.csv") > 0
    report = result.reports[0]
    assert report.shifted, "the later gene's rows should have moved down"

    after = _rows(tmp_path / "variants.csv")
    genes = [r["gene"] for r in after]
    blocks = [g for i, g in enumerate(genes) if i == 0 or genes[i - 1] != g]
    assert len(blocks) == len(set(blocks))
    assert len(after) == len(before) + result.added_for("variants.csv")  # nothing lost or doubled
    assert before_cells <= {tuple(r.items()) for r in after}  # and nothing rewritten


@_needs_snapshot
def test_an_unstated_use_is_fine_because_clinvar_is_public_domain(tmp_path: Path) -> None:
    """Unlike CPIC/ClinPGx, nothing here forbids sale — so the draft proceeds and the terms are
    still recorded, because attribution is asked for even when permission is not."""
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, declared_use="commercial")
    assert not result.skipped and result.added_for("variants.csv") > 0
    sources = _rows(tmp_path / _LICENCE_CSV)
    assert any(s["source"] == "clinvar" for s in sources)


@_needs_snapshot
def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, dry_run=True)
    assert result.added_for("variants.csv") > 0
    assert not (tmp_path / "variants.csv").exists()
    assert not (tmp_path / "studies.csv").exists()
    assert not (tmp_path / _LICENCE_CSV).exists()


# ── finding the snapshot (0.5) ───────────────────────────────────────────────────────────────────
#
# `snapshot` used to be a required argument, so the published snapshot could not reach an author: they
# had to build 4.4M records from a 200 MB VCF, or already know the cache path. Since the citations table
# is what makes a drafted panel compilable — `studies.csv` is mandatory and the VCF carries no PMIDs —
# and that table now travels with the published snapshot, the drafting path has to be able to get it.


def test_an_explicit_snapshot_is_taken_as_given(monkeypatch, tmp_path: Path) -> None:
    """The inject-only escape hatch: an explicit path is never second-guessed and nothing is resolved."""
    from just_dna_enricher import clinvar_draft

    def explode(*_a, **_k):
        raise AssertionError("an explicit --snapshot must not consult the cache or the network")

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", explode)
    monkeypatch.setattr(clinvar_draft, "ensure_clinvar_snapshot", explode)
    reference, warnings = clinvar_draft._resolve_snapshot(
        tmp_path / "explicit", offline=False, download=True
    )
    assert reference == tmp_path / "explicit" and warnings == []


def test_a_cached_snapshot_is_used_without_downloading(monkeypatch, tmp_path: Path) -> None:
    from just_dna_enricher import clinvar_draft

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: tmp_path / "cached")
    monkeypatch.setattr(
        clinvar_draft, "ensure_clinvar_snapshot",
        lambda *_a, **_k: pytest.fail("provisioned despite a usable cache"),
    )
    reference, warnings = clinvar_draft._resolve_snapshot(None, offline=False, download=True)
    assert reference == tmp_path / "cached" and warnings == []


def test_no_cache_provisions_the_published_snapshot(monkeypatch, tmp_path: Path) -> None:
    from just_dna_enricher import clinvar_draft

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: None)
    monkeypatch.setattr(clinvar_draft, "ensure_clinvar_snapshot", lambda: tmp_path / "fetched")
    reference, warnings = clinvar_draft._resolve_snapshot(None, offline=False, download=True)
    assert reference == tmp_path / "fetched" and warnings == []


def test_offline_without_a_snapshot_refuses_and_says_how_to_get_one(monkeypatch) -> None:
    """Drafting from no snapshot is not a degraded result, it is no result — so it raises rather than
    returning an empty draft that looks like "ClinVar has nothing for this gene"."""
    from just_dna_enricher import clinvar_draft
    from just_dna_enricher.clinvar_draft import ClinVarDraftError

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: None)
    monkeypatch.setattr(
        clinvar_draft, "ensure_clinvar_snapshot",
        lambda *_a, **_k: pytest.fail("--offline reached the network"),
    )
    with pytest.raises(ClinVarDraftError, match="no ClinVar snapshot found"):
        clinvar_draft._resolve_snapshot(None, offline=True, download=True)


def test_the_refusal_names_the_switch_that_actually_stopped_it(monkeypatch) -> None:
    """Both `--offline` and `--no-download` close this path, and the message used to name only the
    first — so an author who passed the second was told to drop a flag they had not used, and after a
    failed *provisioning attempt* (neither flag set) it named one nobody could drop."""
    from just_dna_enricher import clinvar_draft
    from just_dna_enricher.clinvar_draft import ClinVarDraftError

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: None)
    monkeypatch.setattr(
        clinvar_draft, "ensure_clinvar_snapshot",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("HF unreachable")),
    )
    with pytest.raises(ClinVarDraftError) as offline:
        clinvar_draft._resolve_snapshot(None, offline=True, download=True)
    with pytest.raises(ClinVarDraftError) as no_download:
        clinvar_draft._resolve_snapshot(None, offline=False, download=False)
    with pytest.raises(ClinVarDraftError) as tried_and_failed:
        clinvar_draft._resolve_snapshot(None, offline=False, download=True)

    assert "Drop --offline" in str(offline.value)
    assert "Drop --no-download" in str(no_download.value)
    # Nothing was blocking: the request was made and failed, so no flag is named and the reason is.
    assert "Drop --" not in str(tried_and_failed.value)
    assert "HF unreachable" in str(tried_and_failed.value)


def test_a_failed_provisioning_refuses_with_the_reason_attached(monkeypatch) -> None:
    """HF has gone dark mid-demo; the refusal has to say that is what happened, not just "not found"."""
    from just_dna_enricher import clinvar_draft
    from just_dna_enricher.clinvar_draft import ClinVarDraftError

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: None)

    def boom():
        raise RuntimeError("HF unreachable")

    monkeypatch.setattr(clinvar_draft, "ensure_clinvar_snapshot", boom)
    with pytest.raises(ClinVarDraftError, match="HF unreachable"):
        clinvar_draft._resolve_snapshot(None, offline=False, download=True)


# ── an undecided clinical call: drafted with a second stub, not silently dropped ─────────────────
#
# `--clin-sig uncertain_significance` used to drop **every** row, reporting only a raw
# `state: Field required` — one identical line per row, 26 of them for a two-gene panel. The
# underlying decision was right (`_STATE_BY_CLIN_SIG` folds only the four decided calls, because
# `VALID_STATES` has no "undecided" member and every candidate asserts something ClinVar did not);
# what was wrong is that the row was thrown away and the reason never stated.


def test_an_undecided_call_stubs_state_instead_of_refusing_the_row(tmp_path: Path) -> None:
    """The defect, demonstrated on the shape that produced it: the row must survive."""
    record = {**_RECORD, "clin_sig": "uncertain_significance"}
    cells = _row_cells(record)
    # The old path: `state` absent from an otherwise complete row, and `state` is required —
    # so building the row *without* stubbing it is exactly the refusal that used to happen.
    assert "state" not in cells
    with pytest.raises(ValidationError):
        VariantRow(**cells, genotype="A/G")
    # The fix: stub it, like `genotype`, and the row validates by omission.
    partial = PartialRow(
        model=VariantRow, cells=cells, stubbed=("genotype", "state"),
        match_on=("rsid", "chrom", "start", "ref", "alts"),
    )
    assert partial.validation_errors() == []


def test_a_decided_call_is_not_given_a_state_stub(tmp_path: Path) -> None:
    """Otherwise the fix would make work where the source already answered."""
    partial = PartialRow(
        model=VariantRow, cells=_row_cells(_RECORD), stubbed=("genotype",),
        match_on=("rsid", "chrom", "start", "ref", "alts"),
    )
    assert partial.validation_errors() == []
    assert _row_cells(_RECORD)["state"] == "risk"


def test_refusals_are_grouped_by_reason_with_a_count_never_one_line_per_row() -> None:
    """The aggregation rule, which this provider family has now needed five times."""
    invalid = [
        RowOutcome(("rs1", "", "", "", ""), "invalid", {"errors": (None, "state: Field required")}),
        RowOutcome(("rs2", "", "", "", ""), "invalid", {"errors": (None, "state: Field required")}),
        RowOutcome(("rs3", "", "", "", ""), "invalid", {"errors": (None, "genotype: bad allele")}),
    ]
    lines = _refusal_summary(invalid)
    assert len(lines) == 2, "one line per reason, not per row"
    by_reason = {line.split(" — ")[1].split(".")[0]: line for line in lines}
    assert by_reason["state: Field required"].startswith("2 row(s) not drafted")
    assert "rs1, rs2" in by_reason["state: Field required"]
    assert by_reason["genotype: bad allele"].startswith("1 row(s) not drafted")


def test_a_long_refusal_list_is_capped_because_it_is_context_not_a_worklist() -> None:
    invalid = [
        RowOutcome((f"rs{i}", "", "", "", ""), "invalid", {"errors": (None, "same reason")})
        for i in range(20)
    ]
    (line,) = _refusal_summary(invalid)
    assert line.startswith("20 row(s) not drafted")
    assert "and 14 more" in line


@_needs_snapshot
def test_an_undecided_panel_drafts_every_row_and_explains_the_state_stub(tmp_path: Path) -> None:
    """End to end on real records. XG has 1★+ uncertain variants; before the fix this drafted zero
    variant rows and emitted one raw pydantic line per record."""
    result = draft_gene_panel(
        tmp_path, ["XG"], snapshot=_SNAPSHOT,
        clin_sig={"uncertain_significance"}, min_review_stars=1,
    )
    rows = _rows(tmp_path / "variants.csv")
    assert result.added_for("variants.csv") == len(rows) > 0
    assert result.invalid == 0, "nothing may be refused for a call the provider can stub"
    assert {r["clin_sig"] for r in rows} == {"uncertain_significance"}
    # both columns are stubbed, and nothing else is
    assert {r["genotype"] for r in rows} == {TEMPLATE_PLACEHOLDER}
    assert {r["state"] for r in rows} == {TEMPLATE_PLACEHOLDER}
    assert {r["conclusion"] for r in rows} != {""}, "the transcription still happened"

    # exactly one line explains the state stub, and it names the call rather than repeating per row
    state_lines = [w for w in result.warnings if "`state` placeholder" in w]
    assert len(state_lines) == 1
    assert "uncertain_significance" in state_lines[0]
    assert "no member meaning 'undecided'" in state_lines[0]

    # and the compiler refuses, naming both columns — the stub's whole purpose
    errors = compile_module(tmp_path, tmp_path / "out").errors
    assert any("genotype, state" in e for e in errors), errors


@_needs_snapshot
def test_the_genotype_worklist_covers_the_rows_added_and_no_others(tmp_path: Path) -> None:
    """It used to be handed every candidate record, so a "3 row(s) carry a placeholder" header was
    followed by a 27-line worklist naming rows that had been refused or were already present."""
    first = draft_gene_panel(tmp_path, ["XG"], snapshot=_SNAPSHOT,
                             clin_sig={"uncertain_significance"}, min_review_stars=1)
    worklist = [w for w in first.warnings if w.strip().startswith("genotype for ")]
    assert len(worklist) == first.added_for("variants.csv")

    # A re-run adds nothing, so the worklist must be empty — the work is already on the author's desk.
    again = draft_gene_panel(tmp_path, ["XG"], snapshot=_SNAPSHOT,
                             clin_sig={"uncertain_significance"}, min_review_stars=1)
    assert again.added_for("variants.csv") == 0
    assert not [w for w in again.warnings if w.strip().startswith("genotype for ")]
    assert not [w for w in again.warnings if "`state` placeholder" in w]


@_needs_snapshot
def test_added_is_reported_per_table_because_a_total_matches_neither(tmp_path: Path) -> None:
    """`draft-panel` writes two tables, so the rolled-up `added` counts rows from both — which is what
    made the CLI print "added 7 row(s)" for 3 variants and 4 studies."""
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    variants, studies = result.added_for("variants.csv"), result.added_for("studies.csv")
    assert variants > 0 and studies > 0
    assert result.added == variants + studies
    assert result.added != variants, "the total is not the variant count — hence the per-table report"
    assert {r.csv_name for r in result.reports} == {"variants.csv", "studies.csv"}


# ── non-diploid contigs: the placeholder protects a decision that does not exist there (S6) ──────


def test_the_mitochondrial_genotype_is_written_because_only_one_is_expressible() -> None:
    """MT is haploid: `A/G` there asserts a second copy that is not present."""
    mt = {**_RECORD, "chrom": "MT", "start": 3243, "ref": "A", "alt": "G", "gene": "MT-TL1"}
    assert sole_expressible_genotype(mt) == "G"
    assert _row_cells(mt)["genotype"] == "G"
    # …and a diploid contig is untouched: the zygosity there is a real judgement.
    assert sole_expressible_genotype(_RECORD) is None
    assert "genotype" not in _row_cells(_RECORD)


def test_chr_y_is_decided_per_locus_because_par1_and_par2_are_diploid() -> None:
    """`XG` and `SPRY3` straddle a PAR boundary, so a contig-wide verdict is wrong for half of either.

    The expectation is computed from the same predicate the compiler's ploidy check uses rather than
    hardcoded, so a corrected PAR interval moves both together.
    """
    par = {**_RECORD, "chrom": "Y", "start": 500_000, "ref": "C", "alt": "T"}   # inside PAR1
    outside = {**_RECORD, "chrom": "Y", "start": 2_787_207, "ref": "G", "alt": "A"}  # SRY
    assert in_pseudoautosomal_region("Y", par["start"]) is True
    assert in_pseudoautosomal_region("Y", outside["start"]) is False

    assert sole_expressible_genotype(par) is None, "diploid here — the author still decides"
    assert sole_expressible_genotype(outside) == "A"


def test_an_undecidable_ploidy_keeps_the_placeholder() -> None:
    """Three-valued, and only `False` writes: `None` means the question could not be put."""
    no_position = {**_RECORD, "chrom": "Y", "start": None, "ref": "G", "alt": "A"}
    assert sole_expressible_genotype(no_position) is None
    multi_allelic = {**_RECORD, "chrom": "MT", "start": 3243, "ref": "A", "alt": "G,T"}
    assert sole_expressible_genotype(multi_allelic) is None


@_needs_snapshot
def test_a_mitochondrial_panel_drafts_compilable_rows_and_says_what_it_committed_to(
    tmp_path: Path,
) -> None:
    """The whole point: no placeholder to expand, so the consumer never writes the impossible pair."""
    result = draft_gene_panel(tmp_path, ["MT-TL1"], snapshot=_SNAPSHOT, min_review_stars=1)
    rows = _rows(tmp_path / "variants.csv")
    assert rows and result.added_for("variants.csv") == len(rows)
    assert TEMPLATE_PLACEHOLDER not in {r["genotype"] for r in rows}
    assert all("/" not in r["genotype"] and r["genotype"] for r in rows)
    # every written genotype is the record's own ALT, matched back through the row's identity
    assert not [w for w in result.warnings if w.strip().startswith("genotype for ")]

    # one aggregated line, naming the contig and the reading — never one per row
    notice = [w for w in result.warnings if "non-diploid contigs" in w]
    assert len(notice) == 1
    assert f"{len(rows)} row(s)" in notice[0] and "MT" in notice[0]
    assert "heteroplasmy.csv" in notice[0]


@_needs_snapshot
def test_the_compiler_accepts_what_the_provider_wrote_for_a_haploid_contig(tmp_path: Path) -> None:
    """The rows the old draft produced were refused (placeholder) or wrong (`A/G` on MT). Neither now.

    Demonstrated against the compiler's own non-diploid guardrail: the drafted rows raise no ploidy
    warning, while the two-allele spelling of the same rows does.
    """
    draft_gene_panel(tmp_path, ["MT-TL1"], snapshot=_SNAPSHOT, min_review_stars=1)
    (tmp_path / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: mt\n  title: MT\n  description: d\n"
        "  report_title: MT\n",
        encoding="utf-8",
    )
    drafted = compile_module(tmp_path, tmp_path / "out", resolve_with_ensembl=False)
    assert drafted.success, drafted.errors
    assert not [w for w in drafted.warnings if "not diploid" in w]

    # the same rows written the way a diploid fill would have written them
    text = (tmp_path / "variants.csv").read_text()
    header, *body = text.splitlines()
    genotype_at = header.split(",").index("genotype")
    faked = [header]
    for line in body:
        cells = line.split(",")
        cells[genotype_at] = f"{cells[genotype_at]}/{cells[genotype_at]}"
        faked.append(",".join(cells))
    (tmp_path / "variants.csv").write_text("\n".join(faked) + "\n", encoding="utf-8")
    diploid = compile_module(tmp_path, tmp_path / "out2", resolve_with_ensembl=False)
    assert [w for w in diploid.warnings if "not diploid" in w], "the guardrail must still fire"


# ── ClinVar files non-PMIDs under PubMed, and one used to kill a whole panel ─────────────────────


def test_a_citation_that_is_not_a_pmid_is_skipped_and_counted_not_raised() -> None:
    """Variation 12606 cites `168335863` — nine digits, where PubMed is at eight.

    The refusal is right (`StudyRow.pmid` cannot key on it); raising it out of a panel draft was not.
    The demonstration is the old behaviour on the same input: constructing the row directly still
    raises, so the skip is doing real work rather than describing an impossibility.
    """
    with pytest.raises(ValidationError):
        StudyRow(rsid="rs104894228", pmid="168335863")

    records = [{**_RECORD, "variation_id": "12606", "rsid": "rs104894228"}]
    links = {"12606": ["168335863", "20613862"]}
    rows, dropped, unusable = _study_rows(records, links, 3, set())

    assert [r.pmid for r in rows] == ["20613862"], "the usable citation still lands"
    assert (dropped, unusable) == (0, 1)


@_needs_snapshot
def test_the_two_citation_shortfalls_are_reported_apart(tmp_path: Path) -> None:
    """A cap is a choice this run made; an unusable id is a defect in the source. Different sentences."""
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, max_citations=1)
    capped = [w for w in result.warnings if "--max-citations" in w]
    unusable = [w for w in result.warnings if "is not a\nPMID" in w or "is not a PMID" in w]
    assert len(capped) == 1
    assert not unusable, "MTHFR has no malformed citation; the sentence must not appear anyway"


# ── the API and the CLI describe the same command (RM4) ──────────────────────────────────────────


#: The two parameters the CLI spells differently, because a repeatable flag reads as the singular and
#: `--use` is the word the licence gate uses. Written out rather than inferred: a rename on either
#: side should fail this test and be looked at, which is the whole point of checking parity at all.
_CLI_SPELLINGS = {"genes": "gene", "declared_use": "use"}


def test_every_draft_panel_parameter_is_reachable_from_the_command_line() -> None:
    """`download` was a parameter of `draft_gene_panel` that `draft-panel` never exposed, so a
    documented behaviour ("provision the published snapshot when there is no local one") could be
    turned off from Python and not from the tool. Checked as a set rather than for that one flag:
    the next parameter added without a flag is the same defect, and this is what notices it.
    """
    import inspect

    from just_dna_enricher.cli import draft_panel_

    api = {
        _CLI_SPELLINGS.get(name, name)
        for name in inspect.signature(draft_gene_panel).parameters
    }
    assert api <= set(inspect.signature(draft_panel_).parameters)


def test_no_download_refuses_instead_of_provisioning(monkeypatch, tmp_path: Path) -> None:
    """The flag reaching the resolver through the command rather than around it."""
    from just_dna_enricher import clinvar_draft
    from just_dna_enricher.cli import app
    from typer.testing import CliRunner

    monkeypatch.setattr(clinvar_draft, "resolve_clinvar_reference", lambda: None)
    monkeypatch.setattr(
        clinvar_draft, "ensure_clinvar_snapshot",
        lambda *_a, **_k: pytest.fail("--no-download provisioned a snapshot"),
    )
    result = CliRunner().invoke(
        app, ["draft-panel", str(tmp_path), "--gene", "HBB", "--no-download"]
    )
    assert result.exit_code == 1
    assert "no ClinVar snapshot found" in result.output
