"""ClinVar → variants.csv (0.5.1, RM26) — gene-panel drafting with the zygosity left to a human.

Real snapshot where one is present, expectations computed. What is pinned: identity is filled whole
or not at all, `genotype` is always a stub, rows land in their gene's block, and a re-run after the
human decides adds nothing.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_enricher.clinvar_draft import (
    DEFAULT_CLIN_SIG,
    _identity_cells,
    _row_cells,
    draft_gene_panel,
)
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER

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
    assert result.added > 0
    rows = _rows(tmp_path / "variants.csv")
    assert len(rows) == result.added
    # every drafted row is a stub, for the gene asked for, with an identity
    assert {r["genotype"] for r in rows} == {TEMPLATE_PLACEHOLDER}
    assert {r["gene"] for r in rows} == {"MTHFR"}
    assert all(r["rsid"] or (r["chrom"] and r["start"] and r["ref"]) for r in rows)
    assert {r["clin_sig"] for r in rows} <= DEFAULT_CLIN_SIG
    # a source rows were copied out of must be accounted for
    assert (tmp_path / "sources.csv").is_file()


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
    assert result.added > 0
    report = result.reports[0]
    assert report.shifted, "the later gene's rows should have moved down"

    after = _rows(tmp_path / "variants.csv")
    genes = [r["gene"] for r in after]
    blocks = [g for i, g in enumerate(genes) if i == 0 or genes[i - 1] != g]
    assert len(blocks) == len(set(blocks))
    assert len(after) == len(before) + result.added          # nothing lost, nothing duplicated
    assert before_cells <= {tuple(r.items()) for r in after}  # and nothing rewritten


@_needs_snapshot
def test_an_unstated_use_is_fine_because_clinvar_is_public_domain(tmp_path: Path) -> None:
    """Unlike CPIC/ClinPGx, nothing here forbids sale — so the draft proceeds and the terms are
    still recorded, because attribution is asked for even when permission is not."""
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, declared_use="commercial")
    assert not result.skipped and result.added > 0
    sources = _rows(tmp_path / "sources.csv")
    assert any(s["source"] == "clinvar" for s in sources)


@_needs_snapshot
def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, dry_run=True)
    assert result.added > 0
    assert not (tmp_path / "variants.csv").exists()
    assert not (tmp_path / "sources.csv").exists()
