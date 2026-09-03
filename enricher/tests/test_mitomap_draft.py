"""`draft-panel --source mitomap-miss` — what it writes, and the three buckets it refuses (RM171).

The refusals are the point of this provider and each is asserted separately, because they are three
different arguments: a photocopy is a call an adopted source already publishes, an unrated miss is a
real identity increment with no class to state, and an unmintable row is one the join could not even
ask the question of. Collapsing any two of them would leave a "skipped 1,090" number that tells an
author nothing.
"""

import csv
import json
from pathlib import Path

import pytest
from just_dna_enricher.cli import app
from just_dna_enricher.clin_sig import STATE_BY_CLIN_SIG, normalize_clin_sig
from just_dna_enricher.mitomap import MITOMAP_VCEP_CLASSES
from just_dna_enricher.mitomap_draft import (
    MitomapDraftError,
    draft_panel_from_mitomap_miss,
)
from just_dna_enricher.mitomap_miss_build import CITATIONS_PARQUET
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from typer.testing import CliRunner

pl = pytest.importorskip("polars")


_SPEC = """schema_version: "0.5"
module: mt_probe
version: 1
title: A probe module
genome_build: GRCh38
"""


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "spec"
    directory.mkdir()
    (directory / "module_spec.yaml").write_text(_SPEC, encoding="utf-8")
    return directory


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_only_the_rated_misses_are_drafted_and_every_other_row_is_accounted_for(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    """The partition again, on the drafting side: offered plus withheld is every candidate."""
    result = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    assert result.accounts_for_every_candidate()
    drafted = _rows(spec_dir / "variants.csv")
    assert drafted, "the fixture has to produce a rated miss for this suite to mean anything"

    frame = pl.read_parquet(mitomap_miss_snapshot / "data" / "mitomap_miss.parquet")
    rated = frame.filter(pl.col("bucket") == "rated_miss")
    assert len(drafted) == rated.height
    written = {(row["chrom"], int(row["start"]), row["ref"], row["alts"]) for row in drafted}
    expected = {("MT", r["start"], r["ref"], r["alt"]) for r in rated.iter_rows(named=True)}
    assert written == expected


def test_a_photocopy_is_never_drafted(spec_dir: Path, mitomap_miss_snapshot: Path) -> None:
    """A tautology guard, stated as a set difference rather than as a count.

    Drafting one would attribute ClinVar's own expert-panel call to MITOMAP, and would hand a ClinVar
    concordance check a copy of ClinVar to agree with (`@tautology-zero`).
    """
    draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    written = {(int(row["start"]), row["ref"], row["alts"]) for row in _rows(spec_dir / "variants.csv")}
    frame = pl.read_parquet(mitomap_miss_snapshot / "data" / "mitomap_miss.parquet")
    photocopies = {
        (r["start"], r["ref"], r["alt"])
        for r in frame.filter(pl.col("bucket") == "photocopy").iter_rows(named=True)
    }
    assert photocopies, "the fixture has to contain one"
    assert not (written & photocopies)


def test_every_drafted_clin_sig_is_the_normalizers_image_of_a_documented_bracket(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    frame = pl.read_parquet(mitomap_miss_snapshot / "data" / "mitomap_miss.parquet")
    bracket_by_key = {
        (r["start"], r["ref"], r["alt"]): r["status_bracket"] for r in frame.iter_rows(named=True)
    }
    for row in _rows(spec_dir / "variants.csv"):
        bracket = bracket_by_key[(int(row["start"]), row["ref"], row["alts"])]
        assert bracket in MITOMAP_VCEP_CLASSES
        assert row["clin_sig"] == normalize_clin_sig(bracket)


def test_the_genotype_and_conclusion_cells_are_stubbed_and_the_worklist_says_why(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    """The one decision this adoption cannot make, and the evidence the author needs to make it.

    `clinvar_draft.sole_expressible_genotype` fills the ALT on chrMT and is deliberately not called
    here: ClinVar's record is a claim about an allele, while MITOMAP's is a claim about a literature
    corpus, and its `homo`/`hetero` flags say a share of these variants have been reported only
    heteroplasmically. So the worklist puts those flags in front of the author rather than resolving
    them, and a module drafted from this cannot compile until a human writes the cells.
    """
    result = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    drafted = _rows(spec_dir / "variants.csv")
    assert {row["genotype"] for row in drafted} == {TEMPLATE_PLACEHOLDER}
    assert {row["conclusion"] for row in drafted} == {TEMPLATE_PLACEHOLDER}

    worklist = [note for note in result.warnings if "genotype placeholder" in note]
    assert len(worklist) == 1
    for row in drafted:
        assert f"MT:{row['start']} {row['ref']}>{row['alts']}" in worklist[0]
    assert "heteroplasmic" in worklist[0] and "homoplasmic" in worklist[0]


def test_state_is_folded_where_the_shared_map_has_an_answer_and_stubbed_where_it_does_not(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    """`STATE_BY_CLIN_SIG` is deliberately not total, so both outcomes have to be reachable."""
    draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    folded = unfolded = 0
    for row in _rows(spec_dir / "variants.csv"):
        expected = STATE_BY_CLIN_SIG.get(row["clin_sig"])
        if expected is None:
            assert row["state"] == TEMPLATE_PLACEHOLDER
            unfolded += 1
        else:
            assert row["state"] == expected
            folded += 1
    assert folded and unfolded, "the fixture must exercise both arms"


def test_a_second_run_adds_nothing(spec_dir: Path, mitomap_miss_snapshot: Path) -> None:
    """Drafting appends and matches on the coordinate identity (`@draft-appends`)."""
    first = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    before = (spec_dir / "variants.csv").read_text(encoding="utf-8")
    second = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    assert first.added and second.added == 0
    assert (spec_dir / "variants.csv").read_text(encoding="utf-8") == before


def test_the_studies_are_position_keyed_and_come_from_mitomaps_own_links(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    """A study is evidence about a locus, which is why it carries no `alts` — `clinvar_draft`'s rule.

    And every PMID is one the increment actually carries: a citation invented for a drafted row would
    be the worst possible kind of grounding evidence.
    """
    draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    studies = _rows(spec_dir / "studies.csv")
    assert studies
    assert all(row.get("alts", "") == "" for row in studies)
    known = set(pl.read_parquet(mitomap_miss_snapshot / "data" / CITATIONS_PARQUET)["pmid"].to_list())
    assert {row["pmid"] for row in studies} <= known
    variants = {(row["start"], row["ref"]) for row in _rows(spec_dir / "variants.csv")}
    assert {(row["start"], row["ref"]) for row in studies} <= variants


def test_the_source_row_names_mitomap_and_the_dataset_names_both_parents(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    """The licensed source is MITOMAP; the increment's *identity* is the pair it was derived from."""
    result = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    rows = _rows(spec_dir / "licensing.csv")
    assert [row["source"] for row in rows] == ["mitomap"]
    row = rows[0]
    assert row["layer"] == "annotation"
    assert row["license"] == "CC-BY-3.0"
    assert row["dataset"] == result.dataset
    assert row["dataset"].startswith("mitomap_") and "clinvar_" in row["dataset"]


def test_a_run_that_drafted_nothing_writes_no_source_row(spec_dir: Path, mitomap_miss_snapshot: Path) -> None:
    """A licence row saying "this module uses MITOMAP" would be a claim about a module that does not."""
    result = draft_panel_from_mitomap_miss(spec_dir, ["NOSUCHGENE"], snapshot=mitomap_miss_snapshot)
    assert result.added == 0
    assert result.withheld["gene_not_requested"]
    assert not (spec_dir / "licensing.csv").exists()


def test_the_gene_filter_is_counted_apart_from_the_withholding(spec_dir: Path, mitomap_miss_snapshot: Path) -> None:
    """"The increment has nothing for this gene" and "it has something we would not write" differ."""
    unfiltered = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot, dry_run=True)
    gene = next(
        row["gene"] for row in
        pl.read_parquet(mitomap_miss_snapshot / "data" / "mitomap_miss.parquet")
        .filter((pl.col("bucket") == "rated_miss") & pl.col("gene").is_not_null())
        .to_dicts()
    )
    filtered = draft_panel_from_mitomap_miss(spec_dir, [gene], snapshot=mitomap_miss_snapshot, dry_run=True)
    assert filtered.candidates < unfiltered.candidates
    assert filtered.withheld["gene_not_requested"] > 0
    assert unfiltered.withheld["gene_not_requested"] == 0


def test_a_moved_parent_is_reported_rather_than_drafted_over(
    spec_dir: Path, mitomap_miss_snapshot: Path, tmp_path: Path
) -> None:
    """The child's pin is what makes a stale increment visible at the moment somebody drafts from it."""
    release = json.loads((mitomap_miss_snapshot / "release.json").read_text())
    release["parents"]["clinvar"]["clinvar_file_date"] = "2019-01-01"
    (mitomap_miss_snapshot / "release.json").write_text(json.dumps(release), encoding="utf-8")
    result = draft_panel_from_mitomap_miss(spec_dir, snapshot=mitomap_miss_snapshot)
    assert result.stale and "clinvar" in result.stale
    assert any("clinvar parent has moved" in note for note in result.warnings)
    assert result.added, "reported, not refused — the rows are still the increment against the pin"


def test_no_snapshot_is_nobody_asked_rather_than_an_empty_increment(
    spec_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JUST_DNA_MITOMAP_MISS_CACHE", str(tmp_path / "nowhere"))
    with pytest.raises(MitomapDraftError, match="mitomap miss"):
        draft_panel_from_mitomap_miss(spec_dir)


# ── the command surface ─────────────────────────────────────────────────────────────────────────


def test_the_source_is_reachable_from_the_command_line_by_either_spelling(
    spec_dir: Path, mitomap_miss_snapshot: Path
) -> None:
    runner = CliRunner()
    for spelling in ("mitomap-miss", "mitomap_miss"):
        result = runner.invoke(app, [
            "draft-panel", str(spec_dir), "--source", spelling,
            "--mitomap-miss-cache", str(mitomap_miss_snapshot), "--dry-run",
        ])
        assert result.exit_code == 0, result.output
        assert "would add" in result.output


def test_a_gene_scoped_source_still_needs_a_gene(spec_dir: Path) -> None:
    """`--gene` became optional for one source and stays required for the other three.

    Without this, an unfiltered `--source clinvar` would try to draft a 4.4M-record snapshot.
    """
    result = CliRunner().invoke(app, ["draft-panel", str(spec_dir), "--source", "clinvar"])
    assert result.exit_code == 2
    printed = result.output + (result.stderr if result.stderr_bytes else "")
    assert "needs at least one --gene" in printed


def test_a_clin_sig_dial_is_named_as_inert_under_this_source(spec_dir: Path, mitomap_miss_snapshot: Path) -> None:
    """The increment is already exactly the five documented classes; a filter cannot widen it."""
    result = CliRunner().invoke(app, [
        "draft-panel", str(spec_dir), "--source", "mitomap-miss",
        "--mitomap-miss-cache", str(mitomap_miss_snapshot), "--clin-sig", "pathogenic", "--dry-run",
    ])
    printed = result.output + (result.stderr if result.stderr_bytes else "")
    assert "--clin-sig does nothing" in printed
