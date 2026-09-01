"""The STRchive drafting provider (RM165, commit B) — the identity half, and what it refuses to write.

The whole item is a split: the catalogue's identity is drafted and its bands are checked. So the
sharpest test here is a negative — **no drafted row carries a band column** — and it is asserted over
a derived set rather than a list typed beside the provider, because a column added to
`RepeatAlleleRow` later must land on the withheld side by default.

Ground truth comes from the corpus where it can. `htt_repeat_expansion` was authored by a human with
`trait_efo_id=MONDO_0007739`, and the provider derives the same value from STRchive's `mondo` field
independently; `fmr1_cgg_repeat` leaves the trait empty and STRchive names three MONDO ids for that
locus, so the provider withholds it. Neither number is typed into an assertion.
"""

import csv
import os
from pathlib import Path

import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_compiler.draft import DRAFTABLE, authoring_requirements
from just_dna_enricher.licensing import STRCHIVE_TERMS, TERMS_BY_SOURCE, check_declared_use
from just_dna_enricher.strchive import (
    REPEAT_ALLELES_CSV,
    StrchiveCatalogue,
    StrchiveLocus,
    load_strchive_catalogue,
)
from just_dna_enricher.strchive_draft import (
    DRAFTED_COLUMNS,
    WITHHELD_COLUMNS,
    WITHHELD_REASONS,
    _missing_required,
    draft_repeat_loci,
)
from just_dna_format.base import authored_field_names
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.layout import SOURCES_CSV, resolve_sidecar
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER, VALID_DECLARED_USE

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "strchive_loci_slice.json"
_EXAMPLES = _ROOT / "reference_examples"

#: The band columns the measurement was actually about. Named here rather than derived, on purpose:
#: this is the test's claim about what "the band half" means, and deriving it from the provider would
#: make the test agree with the provider by construction.
_BAND_COLUMNS = frozenset({"measure_min", "measure_max", "measure_tiling", "direction", "clin_sig"})


@pytest.fixture(scope="module")
def catalogue() -> StrchiveCatalogue:
    return load_strchive_catalogue(_SLICE)


def _rows(spec: Path) -> list[dict[str, str]]:
    path = spec / REPEAT_ALLELES_CSV
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _spec(tmp_path: Path, name: str = "spec") -> Path:
    spec = tmp_path / name
    spec.mkdir(parents=True, exist_ok=True)
    return spec


def _locus(catalogue: StrchiveCatalogue, locus_id: str) -> StrchiveLocus:
    return next(locus for locus in catalogue.loci if locus.locus_id == locus_id)


# ── the split, in code ──────────────────────────────────────────────────────────────────────────


def test_the_drafted_and_withheld_columns_partition_the_model() -> None:
    """The withheld set is *derived*, so a column added to the kind is withheld by default.

    An equality over the model's own authored fields rather than a floor: a column that appeared in
    neither set would be invisible to the assertion below about band columns.
    """
    authored = set(authored_field_names(RepeatAlleleRow))
    assert set(DRAFTED_COLUMNS) <= authored
    assert set(DRAFTED_COLUMNS) | WITHHELD_COLUMNS | {"conclusion"} == authored
    assert not set(DRAFTED_COLUMNS) & WITHHELD_COLUMNS
    assert _BAND_COLUMNS <= WITHHELD_COLUMNS, sorted(_BAND_COLUMNS - WITHHELD_COLUMNS)


def test_no_drafted_row_carries_a_band_column(tmp_path: Path, catalogue: StrchiveCatalogue) -> None:
    """The refusal the item turns on, asserted on the bytes the provider wrote.

    STRchive is a band coarser than `fmr1_cgg_repeat` at the premutation threshold and its
    `pathogenic_max` would invent a ceiling `htt_repeat_expansion` leaves open. Writing either would
    make the module state the catalogue's tiling as the author's own.
    """
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=catalogue)
    assert result.drafted > 0, "the fixture must produce at least one drafted row"

    for row in _rows(spec):
        carried = {name for name in WITHHELD_COLUMNS if (row.get(name) or "").strip()}
        assert carried == set(), f"{row['gene']}/{row['repeat_unit']} carries {sorted(carried)}"


def test_the_catalogue_ceiling_never_reaches_the_drafted_table(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The same refusal read from the other side: the number itself is nowhere in the file."""
    spec = _spec(tmp_path)
    draft_repeat_loci(spec, catalogue=catalogue)
    text = (spec / REPEAT_ALLELES_CSV).read_text(encoding="utf-8")
    bounds = {
        str(int(band.hi))
        for locus in catalogue.loci
        for band in locus.bands
        if band.hi is not None and float(band.hi).is_integer()
    }
    assert bounds, "the fixture states some upper bounds"
    present = [value for value in bounds if value in text.split(",")]
    assert present == [], present


# ── identity, against the corpus ────────────────────────────────────────────────────────────────


def test_the_drafted_trait_reproduces_the_hand_authored_one(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Independent agreement, which is the strongest evidence a drafting provider can have.

    `htt_repeat_expansion` was authored by a human; the provider derives the same CURIE from
    STRchive's `mondo` list without ever seeing the module.
    """
    authored = {
        row["trait_efo_id"]
        for row in csv.DictReader(
            (_EXAMPLES / "htt_repeat_expansion" / REPEAT_ALLELES_CSV)
            .read_text(encoding="utf-8").splitlines()
        )
        if row["trait_efo_id"]
    }
    assert len(authored) == 1

    spec = _spec(tmp_path)
    draft_repeat_loci(spec, ["HTT"], catalogue=catalogue)
    drafted = [row for row in _rows(spec) if row["gene"] == "HTT"]
    assert [row["trait_efo_id"] for row in drafted] == sorted(authored)


def test_a_locus_naming_several_diseases_has_its_trait_withheld(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Three MONDO ids on one repeat is three diseases, not three names — so no trait is stated.

    And the corpus agrees independently: `fmr1_cgg_repeat` leaves `trait_efo_id` empty on every row.
    """
    locus = _locus(catalogue, "FXS_FMR1")
    assert len(locus.mondo) > 1, "the fixture must keep the multi-disease locus"

    spec = _spec(tmp_path)
    draft_repeat_loci(spec, [locus.gene], catalogue=catalogue)
    assert [row["trait_efo_id"] for row in _rows(spec)] == [""]

    shipped = list(csv.DictReader(
        (_EXAMPLES / "fmr1_cgg_repeat" / REPEAT_ALLELES_CSV).read_text(encoding="utf-8").splitlines()
    ))
    assert {row.get("trait_efo_id") for row in shipped} <= {None, ""}


def test_a_contested_gene_and_motif_key_is_drafted_for_neither_locus(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Picking one would make which locus a row means depend on record order.

    Contestation is decided over the whole admitted set before any row is built, so the gene filter
    below cannot leave one claimant looking uncontested.
    """
    gene = next(
        locus.gene for locus, in ((x,) for x in catalogue.loci)
        if len([o for o in catalogue.loci if o.gene == locus.gene]) > 1
    )
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, [gene], catalogue=catalogue)
    assert result.drafted == 0
    assert result.withheld["contested_key"] == result.candidates
    assert any(gene in warning for warning in result.warnings)


def test_every_candidate_is_drafted_or_counted(tmp_path: Path, catalogue: StrchiveCatalogue) -> None:
    """An equality over the whole admitted set, so a locus cannot vanish between the two.

    `withheld` is keyed on the named reasons rather than one anonymous total — each of the three sends
    the author somewhere different.
    """
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=catalogue)
    assert set(result.withheld) == set(WITHHELD_REASONS)
    assert result.accounts_for_every_candidate(), (result.candidates, result.withheld)
    assert result.candidates == len(catalogue.loci)


# ── appending, and the stub ─────────────────────────────────────────────────────────────────────


def test_a_second_run_appends_nothing_and_rewrites_no_cell(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Drafting appends, never mutates (`@draft-appends`). Asserted on the bytes, not on the report."""
    spec = _spec(tmp_path)
    draft_repeat_loci(spec, catalogue=catalogue)
    first = (spec / REPEAT_ALLELES_CSV).read_bytes()

    again = draft_repeat_loci(spec, catalogue=catalogue)
    assert again.drafted == 0
    assert {o.status for o in again.report.outcomes} == {"already_present"}
    assert (spec / REPEAT_ALLELES_CSV).read_bytes() == first


def test_a_re_draft_after_the_human_filled_the_bands_still_matches(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`match_on` is the identity, not the natural key — which is what makes the stub safe.

    The human's job is to replace `conclusion` and write the bands, and doing it must not make the
    provider think the locus is new. Split into several band rows, too, which is what a real author
    does to a drafted identity row.
    """
    spec = _spec(tmp_path)
    draft_repeat_loci(spec, ["HTT"], catalogue=catalogue)
    rows = _rows(spec)
    header = list(rows[0])
    finished = []
    for lo, hi in ((6, 26), (27, 35)):
        row = dict(rows[0])
        row.update(conclusion=f"{lo} to {hi} CAG", measure_min=str(lo), measure_max=str(hi))
        finished.append(row)
    with open(spec / REPEAT_ALLELES_CSV, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(finished)

    again = draft_repeat_loci(spec, ["HTT"], catalogue=catalogue)
    assert again.drafted == 0, "the finished rows read as the same locus"
    assert len(_rows(spec)) == 2


def test_rows_land_at_the_end_of_a_table_that_already_has_some(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Authored row order is load-bearing for the digest, so an append goes after what is there.

    The starting table is itself drafted and then finished by hand, which is the real sequence: draft
    one gene, write its bands, come back for the rest of the catalogue later.
    """
    spec = _spec(tmp_path)
    first_gene = _locus(catalogue, "HD_HTT").gene
    draft_repeat_loci(spec, [first_gene], catalogue=catalogue)
    header = list(_rows(spec)[0])
    finished = []
    for lo, hi in ((6, 26), (27, 35)):
        row = dict(_rows(spec)[0])
        row.update(conclusion=f"{lo} to {hi} CAG", measure_min=str(lo), measure_max=str(hi))
        finished.append(row)
    with open(spec / REPEAT_ALLELES_CSV, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(finished)
    before = _rows(spec)

    draft_repeat_loci(spec, catalogue=catalogue)
    after = _rows(spec)
    assert after[: len(before)] == before, "an existing cell was rewritten or a row moved"
    assert all(row["conclusion"] == TEMPLATE_PLACEHOLDER for row in after[len(before):])
    # The finished gene is not drafted a second time — `match_on` still recognises it.
    assert [row["gene"] for row in after[len(before):]].count(first_gene) == 0


def test_the_drafted_table_cannot_compile_until_a_human_has_finished_it(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """A generated stub must be unable to compile, and the error must name the column (`@stub-cannot-compile`).

    `repeat_alleles.csv` is in `DRAFTABLE`, so the shared placeholder guard applies; this asserts the
    provider actually reaches it rather than writing a row that quietly validates.
    """
    assert REPEAT_ALLELES_CSV in DRAFTABLE
    spec = _spec(tmp_path)
    draft_repeat_loci(spec, catalogue=catalogue)
    _rows_loaded, errors, _ = load_csv_rows(
        spec / REPEAT_ALLELES_CSV, RepeatAlleleRow, REPEAT_ALLELES_CSV
    )
    assert errors and any("conclusion" in message for message in errors), errors


def test_the_skip_guard_is_the_models_own_requiredness_rather_than_a_copy() -> None:
    """Derived, not restated — the defect that killed `draft --gene CYP2C9`.

    Asserted as an equality against `authoring_requirements`, which is the surface that answers
    requiredness in all three of its shapes, so a column promoted or demoted later moves this guard
    with it instead of leaving it behind.
    """
    requirements = authoring_requirements(REPEAT_ALLELES_CSV)
    expected = [name for name in requirements["always"] if name != "conclusion"]
    assert _missing_required({}) == expected
    assert "conclusion" in requirements["always"], "the stubbed column really is required"
    assert _missing_required(dict.fromkeys(expected, "x")) == []


# ── the licence row ─────────────────────────────────────────────────────────────────────────────


def test_the_terms_are_the_mit_grant_and_the_source_is_registered() -> None:
    """MIT is the one permissive set of terms in this adoption round, so every axis is a fact.

    `None` would mean "could not be established", which is a different and weaker statement than
    "the licence allows it" — and it is what every other axis in this round had to say.
    """
    assert TERMS_BY_SOURCE[STRCHIVE_TERMS.source] is STRCHIVE_TERMS
    assert (STRCHIVE_TERMS.share_alike, STRCHIVE_TERMS.commercial_use, STRCHIVE_TERMS.redistribution) == (
        False, True, True,
    )
    assert STRCHIVE_TERMS.license == "MIT" and STRCHIVE_TERMS.attribution
    # The grant covers every declaration, so the gate never skips and never refuses.
    assert {check_declared_use(STRCHIVE_TERMS, use) for use in VALID_DECLARED_USE} == {None}


def test_the_provider_writes_its_source_row_with_the_release_it_read(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """A pass that carries a source's data into a module writes its `SourceRow` (`@write-the-sourcerow`).

    The compile gate and `manifest.sources` read this file and nothing else, so a source that is only
    *used* is one the module cannot account for. `dataset` carries the release the rows came from,
    which is what makes a later currency check answerable.
    """
    spec = _spec(tmp_path)
    labelled = StrchiveCatalogue(loci=catalogue.loci, dataset="strchive_v0.0.0")
    draft_repeat_loci(spec, catalogue=labelled)

    path = resolve_sidecar(spec, SOURCES_CSV)
    assert path is not None, "the licence table was not written"
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert not errors, errors
    recorded = next(row for row in rows if row.source == "strchive")
    assert (recorded.layer, recorded.dataset) == ("annotation", "strchive_v0.0.0")
    assert recorded.commercial_use is True and recorded.attribution


def test_a_dry_run_writes_no_file_at_all(tmp_path: Path, catalogue: StrchiveCatalogue) -> None:
    """A caller asking for a dry run is asking for no files — the licence row included."""
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=catalogue, dry_run=True)
    assert result.report is not None and not result.report.written
    assert sorted(p.name for p in spec.iterdir()) == []


def test_no_catalogue_is_a_skip_rather_than_a_source_with_nothing_in_it(tmp_path: Path) -> None:
    """Nobody-asked is a third state beside asked-and-failed and asked-and-absent."""
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=None)
    assert result.skipped and result.candidates == 0
    assert any("strchive build" in warning for warning in result.warnings)
    assert sorted(p.name for p in spec.iterdir()) == []


def test_a_run_that_covered_nothing_writes_no_licence_row(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """A pass that contributed nothing writes no `SourceRow` — the converse of the standing rule.

    The row travels to the registry meaning *this module uses this source*. A `--gene` filter that
    matched nothing leaves the module untouched, so claiming it uses STRchive would be a claim about
    a module that does not.
    """
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, ["NOTAGENE"], catalogue=catalogue)
    assert (result.candidates, result.drafted) == (0, 0)
    assert resolve_sidecar(spec, SOURCES_CSV) is None
    assert sorted(p.name for p in spec.iterdir()) == []


def test_a_re_draft_from_a_newer_release_withdraws_the_stale_label(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`merge_sources_file` is never-clobber, which is right for terms and a false claim for `dataset`.

    A module widened from a second release carries rows from both, and one column cannot name two —
    so the label is withdrawn rather than re-labelled, and the empty cell skips nothing downstream.
    """
    spec = _spec(tmp_path)
    first = StrchiveCatalogue(loci=catalogue.loci, dataset="strchive_v0.0.1")
    second = StrchiveCatalogue(loci=catalogue.loci, dataset="strchive_v0.0.2")

    draft_repeat_loci(spec, ["HTT"], catalogue=first)
    path = resolve_sidecar(spec, SOURCES_CSV)
    rows, _errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert next(r for r in rows if r.source == "strchive").dataset == "strchive_v0.0.1"

    result = draft_repeat_loci(spec, ["FMR1"], catalogue=second)
    assert result.drafted == 1
    rows, _errors, _ = load_csv_rows(path, SourceRow, path.name)
    assert next(r for r in rows if r.source == "strchive").dataset is None
    assert any("withdrawn rather than re-labelled" in warning for warning in result.warnings)


def test_a_row_the_model_refuses_is_reported_as_refused(tmp_path: Path) -> None:
    """`invalid` is a third outcome and must not be collapsed into "already present".

    Reported over a locus whose motif the model cannot hold, so nothing is written at all — the one
    run where a false "everything is already there" would be most misleading.
    """
    catalogue = StrchiveCatalogue(loci=(
        StrchiveLocus(
            locus_id="X_Y", gene="Y", reference_motifs=("CAG",), gene_motifs=(),
            bands=(), mondo=("not a mondo id",), ref_copies=None, locus_structure=(), disease=None,
        ),
    ))
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=catalogue)
    assert result.drafted == 0
    assert [o.status for o in result.report.outcomes] == ["invalid"]
    assert any("refused by" in warning for warning in result.warnings)
    assert not any("already in" in warning for warning in result.warnings)
    assert not (spec / REPEAT_ALLELES_CSV).exists()


@pytest.mark.parametrize("published", ["0007739", "MONDO_0007739", "MONDO:0007739"])
def test_a_mondo_id_is_prefixed_once_however_the_source_spells_it(
    tmp_path: Path, published: str
) -> None:
    """STRchive publishes bare digits today, and a CURIE prefix is an encoding rather than a value.

    Blind concatenation makes `MONDO_MONDO:0007739`, which `trait_efo_id` rejects — so a change in
    the source's spelling would turn every drafted row into a refusal.
    """
    catalogue = StrchiveCatalogue(loci=(
        StrchiveLocus(
            locus_id="HD_HTT", gene="HTT", reference_motifs=("CAG",), gene_motifs=(),
            bands=(), mondo=(published,), ref_copies=None, locus_structure=(), disease=None,
        ),
    ))
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=catalogue)
    assert result.drafted == 1, [o.differences for o in result.report.outcomes]
    assert [row["trait_efo_id"] for row in _rows(spec)] == ["MONDO_0007739"]


# ── the columns with nowhere to land ────────────────────────────────────────────────────────────


def test_the_facts_with_no_authored_column_are_counted_rather_than_dropped(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`ref_copies` and `locus_structure` are the RM65/RM66 evidence and neither has a column.

    A number a pass computes and discards is one every reader recomputes, so both are counted against
    the same denominator and said out loud. The expected values are derived from the fixture.
    """
    fractional = sum(
        1 for locus in catalogue.loci
        if locus.ref_copies is not None and not float(locus.ref_copies).is_integer()
    )
    structured = sum(1 for locus in catalogue.loci if locus.locus_structure)
    assert fractional and structured, "the fixture must keep both shapes"

    result = draft_repeat_loci(_spec(tmp_path), catalogue=catalogue)
    assert (result.fractional_ref_copies, result.with_locus_structure) == (fractional, structured)
    assert any("ref_copies" in warning for warning in result.warnings)
    assert any("locus_structure" in warning for warning in result.warnings)


def test_a_fractional_ref_copies_is_never_rounded_into_a_cell(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """It has no home, so the honest outcome is that it is absent — not that it became an integer."""
    spec = _spec(tmp_path)
    draft_repeat_loci(spec, catalogue=catalogue)
    cells = {value for row in _rows(spec) for value in row.values() if value}
    for locus in catalogue.loci:
        if locus.ref_copies is None:
            continue
        assert str(locus.ref_copies) not in cells
        assert str(int(locus.ref_copies)) not in cells


# ── live ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to hit the network"
)
def test_the_whole_published_catalogue_drafts_without_losing_a_locus(tmp_path: Path) -> None:
    """82 loci through the real provider: every one drafted or counted, and no band cell written."""
    from just_dna_enricher.strchive_build import build_strchive_snapshot

    built = build_strchive_snapshot(tmp_path / "snap", release="v2.26.0")
    spec = _spec(tmp_path)
    result = draft_repeat_loci(spec, catalogue=built.out_dir)

    assert result.candidates == built.locus_count
    assert result.accounts_for_every_candidate()
    assert result.dataset == built.dataset
    for row in _rows(spec):
        assert {name for name in WITHHELD_COLUMNS if (row.get(name) or "").strip()} == set()
