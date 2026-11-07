"""A recorded locus on a GRCh38 patch or alt contig is left out of a re-derivation, counted (RM400, S132).

Before RM400 the REST rung wrote a mapping on a patch or alt contig (`HSCHR17_1_CTG5`) as a locus. No
snapshot carries one, so a table REST had filled, re-derived from the snapshot, read each such subject as
`lost_allele` although its primary placement had not moved. The registry's gate holds `lost_allele`, and
it refused 4 modules over 11 such subjects. The write half (`test_ensembl_non_nucleotide.py`) stops new
ones; this is the recorded half. The pm's default, taken as is: no new drift arm and no carry reason, the
same filter applied to the recorded side before the comparison, and a count in the report.
"""

import csv
import logging
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.outcome import _drift_case, _rederived_drift
from just_dna_format.base import merge_key
from just_dna_format.resolution import ResolutionRow

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _row(chrom: str, start: int, locus_index: int, *, alts: str = "A", key: str = "rs1") -> ResolutionRow:
    return ResolutionRow(
        variant_key=key,
        rsid=key,
        chrom=chrom,
        start=start,
        ref="G",
        alts=alts,
        genome_build="GRCh38",
        locus_index=locus_index,
    )


def _by_key(rows: list[ResolutionRow]) -> dict[tuple, list[ResolutionRow]]:
    out: dict[tuple, list[ResolutionRow]] = {}
    for row in rows:
        out.setdefault(merge_key(row), []).append(row)
    return out


def test_a_recorded_patch_locus_is_left_out_and_counted_not_called_a_lost_allele() -> None:
    recorded = [_row("17", 100, 0), _row("HSCHR17_1_CTG5", 900, 1)]
    fresh = [_row("17", 100, 0)]
    # The reading RM400 replaces: compared whole, the subject lost an allele it never lost.
    assert _drift_case(recorded, fresh) == "lost_allele"
    drift, compared, off_primary = _rederived_drift(_by_key(recorded), fresh)
    assert (drift, compared, off_primary) == ([], 1, {"rs1": 1})


def test_the_survivors_are_renumbered_so_a_patch_sorting_first_moves_no_index() -> None:
    """`HSCHRX_…` sorts before `X`, so the primary locus was recorded at index 1 and is fresh at 0."""
    recorded = [_row("HSCHRX_2_CTG3", 50, 0), _row("X", 100, 1)]
    drift, _compared, off_primary = _rederived_drift(_by_key(recorded), [_row("X", 100, 0)])
    assert (drift, off_primary) == ([], {"rs1": 1})


def test_a_real_move_on_the_primary_assembly_is_still_reported() -> None:
    recorded = [_row("17", 100, 0), _row("HSCHR17_1_CTG5", 900, 1)]
    drift, _compared, off_primary = _rederived_drift(_by_key(recorded), [_row("17", 300, 0)])
    assert [d.case for d in drift] == ["moved"]
    assert off_primary == {"rs1": 1}


def test_a_subject_recorded_only_off_primary_is_compared_as_before() -> None:
    """Nothing on the primary assembly is left to compare, so the filter does not apply and the change
    is reported as it was; dropping every row would compare an empty answer with the fresh one."""
    recorded = [_row("HSCHR17_1_CTG5", 900, 0)]
    drift, _compared, off_primary = _rederived_drift(_by_key(recorded), [_row("17", 100, 0)])
    assert [d.case for d in drift] == ["moved"]
    assert off_primary == {}


def test_a_row_another_build_or_no_place_names_is_never_called_off_primary() -> None:
    grch37 = ResolutionRow(
        variant_key="rs1", rsid="rs1", chrom="17", start=100, ref="G", alts="A", genome_build="GRCh37"
    )
    _drift, _compared, off_primary = _rederived_drift(_by_key([grch37]), [grch37])
    assert off_primary == {}


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {"id": ["rs1801133"], "chrom": ["1"], "start": [11856377], "ref": ["G"], "alt": ["A"]}
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


@pytest.mark.usefixtures("no_ambient_caches")
def test_a_rederive_over_a_table_rest_filled_off_primary_moves_nothing_and_says_so(
    snapshot: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The registry's case end to end: a 0.7 table holding REST's patch-contig locus beside the primary
    one, re-derived from the snapshot. No drift, one RM400 line, and the committed table is primary-only."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,9545397\n", encoding="utf-8")
    common = {
        "ensembl_cache": snapshot,
        "clinvar_cache": tmp_path / "nowhere",
        "offline": True,
        "download": False,
        "use_gnomad": False,
        "verify_ref": False,
        "verify_rsids": False,
        "verify_clinsig": False,
        "verify_datasets": False,
    }
    enrich(spec, **common)
    table = spec / "resolution.csv"
    with table.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, (primary,) = reader.fieldnames, list(reader)
    # What REST wrote before RM400: the same subject, a second locus on a patch contig.
    patch = {**primary, "chrom": "HSCHR1_1_CTG3", "start": "212341", "locus_index": "1", "vrs_id": ""}
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([primary, patch])

    with caplog.at_level(logging.WARNING):
        result = enrich(spec, rederive=True, **common)

    assert result.rederived == []
    (line,) = [r.getMessage() for r in caplog.records if "RM400" in r.getMessage()]
    assert line.startswith(
        "Re-derivation: 1 recorded locus/loci on 1 of 1 re-asked subject(s) sit on a GRCh38"
    )
    assert "rs1801133" in line
    with table.open(encoding="utf-8", newline="") as handle:
        assert [(r["chrom"], r["locus_index"]) for r in csv.DictReader(handle)] == [("1", "0")]
