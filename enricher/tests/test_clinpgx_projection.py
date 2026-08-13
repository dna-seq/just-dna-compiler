"""The ClinPGx snapshot's own columns, and the two claims a hand-written projection made false (D2).

`load_snapshot` selected six columns by name. The parquet has eleven, and the two it dropped were
`gene` and `annotation_text` — both written by `clinpgx_build` for every record it parses. The
omission then travelled outward as statements about the *source*:

* `clinpgx_draft` refused `--gene` with "the ClinPGx annotation snapshot carries no gene column",
  and `--gene`'s CLI help said "Reserved; the annotation snapshot has no gene column". It has one,
  populated on 15,331 of 16,087 rows in the published release.
* `conclusion` was synthesized as `"ClinPGx 655385012: C/C and warfarin — dosage"` — every word of
  which is already in the other columns of the same row — while the published sentence
  ("Patients with the rs9923231 CC genotype may require an increased dose of warfarin …") sat unread.
  `conclusion` is the column whose job is to say what the module claims, and nothing anywhere flags
  one that is content-free.

This is the *probe the table, not the source* shape with the aggravation that the table was ours. The
fixture below is a real snapshot row rather than an invented one, and the assertions are on the two
columns the projection dropped.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.clinpgx import load_snapshot
from just_dna_enricher.clinpgx_draft import _rows_from_snapshot
from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME

# One real annotation, three genotypes — ClinPGx 655385012 (VKORC1/warfarin, level 1A).
_ROWS = [
    {"annotation_id": "655385012", "subject": "rs9923231", "rsid": "rs9923231", "gene": "VKORC1",
     "genotype": "CC", "evidence_level": "1A", "phenotype_category": "Dosage",
     "drugs": "warfarin", "phenotypes": None,
     "annotation_text": "Patients with the rs9923231 CC genotype may require an increased dose of "
                        "warfarin as compared to patients with the CT or TT genotype.",
     "url": "https://www.clinpgx.org/clinicalAnnotation/655385012"},
    {"annotation_id": "655385012", "subject": "rs9923231", "rsid": "rs9923231", "gene": "VKORC1",
     "genotype": "TT", "evidence_level": "1A", "phenotype_category": "Dosage",
     "drugs": "warfarin", "phenotypes": None,
     "annotation_text": "Patients with the rs9923231 TT genotype may require a decreased dose of "
                        "warfarin as compared to patients with the CC or CT genotype.",
     "url": "https://www.clinpgx.org/clinicalAnnotation/655385012"},
    # A different gene, so `--gene` has something to exclude.
    {"annotation_id": "655385400", "subject": "rs2108622", "rsid": "rs2108622", "gene": "CYP4F2",
     "genotype": "TT", "evidence_level": "1A", "phenotype_category": "Dosage",
     "drugs": "warfarin", "phenotypes": None,
     "annotation_text": "Patients with the rs2108622 TT genotype may have increased warfarin "
                        "dosage requirements as compared to patients with the CC genotype.",
     "url": "https://www.clinpgx.org/clinicalAnnotation/655385400"},
]


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "clinpgx"
    (root / SNAPSHOT_DATA_DIRNAME).mkdir(parents=True)
    pl.DataFrame(_ROWS).write_parquet(root / SNAPSHOT_DATA_DIRNAME / "annotations.parquet")
    (root / "release.json").write_text('{"dataset": "clinpgx_test"}')
    return root


def test_the_reader_returns_the_file_s_columns_not_a_chosen_subset(snapshot: Path) -> None:
    """The projection is the file's. A hand-kept SELECT loses a column exactly as a hand-kept list
    does, with the extra cost that what it dropped is invisible downstream — a reader sees a dict
    that simply does not have the key, and concludes the source does not publish it."""
    rows, _release = load_snapshot(snapshot)
    assert set(rows[0]) == set(_ROWS[0])


def test_the_conclusion_is_the_published_sentence(snapshot: Path, tmp_path: Path) -> None:
    """Verbatim, not summarized: the moment it is reworded it is an interpretation, and the author —
    who owns what the module claims — can no longer see what the source said."""
    rows, warnings = _rows_from_snapshot(
        load_snapshot(snapshot)[0], genes=(), drugs=["warfarin"], min_evidence_level=None
    )
    # Keyed on (rsid, genotype): two of the three fixture rows are `T/T`, at different loci, which is
    # the ordinary shape here and exactly why the bare genotype is not a key.
    by_row = {(r.rsid, r.genotype): r for r in rows}

    assert by_row[("rs9923231", "C/C")].conclusion == _ROWS[0]["annotation_text"]
    assert by_row[("rs9923231", "T/T")].conclusion == _ROWS[1]["annotation_text"]
    assert by_row[("rs2108622", "T/T")].conclusion == _ROWS[2]["annotation_text"]
    # And the old synthesized shape is gone rather than merely joined.
    assert not any(r.conclusion.startswith("ClinPGx ") for r in rows)


def test_the_gene_column_reaches_the_row(snapshot: Path) -> None:
    """`PharmVariantRow.gene` is optional and was left empty on every drafted row while the source
    stated it — a column a human then has to fill from the same file the drafter just read."""
    rows, _ = _rows_from_snapshot(load_snapshot(snapshot)[0], genes=(), drugs=["warfarin"], min_evidence_level=None)
    assert {r.gene for r in rows} == {"VKORC1", "CYP4F2"}


def test_the_gene_filter_is_applied_and_reported(snapshot: Path) -> None:
    """`--gene` used to be silently unapplied, with a warning giving a false reason for it."""
    rows, warnings = _rows_from_snapshot(load_snapshot(snapshot)[0], genes=["VKORC1"], drugs=["warfarin"], min_evidence_level=None)

    assert {r.gene for r in rows} == {"VKORC1"}
    assert not any("carries no gene column" in w for w in warnings)
    assert any("outside --gene" in w for w in warnings)


def test_an_unmatched_gene_yields_nothing_rather_than_everything(snapshot: Path) -> None:
    """The failure mode a silently-ignored filter has: asking for one gene and getting the lot."""
    rows, _ = _rows_from_snapshot(load_snapshot(snapshot)[0], genes=["CYP2C9"], drugs=["warfarin"], min_evidence_level=None)
    assert rows == []
