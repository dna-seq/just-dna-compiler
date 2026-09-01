"""The regulator drug-label builder (RM166), run against a real slice of `drugLabels.zip`.

`assets/clinpgx_drug_labels_slice/` is cut verbatim from the archive ClinPGx published on 2026-08-05
— the same `LICENSE.txt` and `CREATED_<date>.txt` the real download carries, and 27 label rows chosen
to cover all five regulators, all five testing levels, the blank one, both join tiers, and the two
DPYD rows whose `Variants/Haplotypes` cell holds a comma *inside* a token.

**Every expected value is computed from the fixture at runtime.** ClinPGx re-curates labels, so a row
count or a regulator tally typed into an assertion would convert that drift into a permanently red
test. The one thing hardcoded is the source's own column names, which is a domain constant.
"""

import csv
import hashlib
import json
import os
import zipfile
from pathlib import Path

import duckdb
import httpx
import pytest
from just_dna_enricher.drug_labels import (
    LABEL_COLUMNS,
    SOURCE_NAME,
    DrugLabelError,
    DrugLabelUnavailable,
    load_drug_labels,
)
from just_dna_enricher.drug_labels_build import (
    COLUMN_MAP,
    LABELS_MEMBER,
    build_drug_label_snapshot,
    download_drug_labels_zip,
)
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
)

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "clinpgx_drug_labels_slice"


def _rows_from_fixture() -> list[dict[str, str]]:
    """The fixture TSV read independently of the builder, so an assertion has its own ground truth."""
    with open(_SLICE / LABELS_MEMBER, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _archive(tmp_path: Path, *, drop_column: str | None = None) -> Path:
    """The fixture directory as a `drugLabels.zip`, optionally with one column removed.

    Zipped here rather than shipped as a binary so the fixture stays readable in the tree and a
    `git diff` on a re-cut slice shows the rows that moved.
    """

    dest = tmp_path / "drugLabels.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(_SLICE.iterdir()):
            if path.name == LABELS_MEMBER and drop_column is not None:
                rows = _rows_from_fixture()
                names = [name for name in rows[0] if name != drop_column]
                buffer = ["\t".join(names)]
                buffer += ["\t".join(row[name] for name in names) for row in rows]
                archive.writestr(path.name, "\n".join(buffer) + "\n")
            else:
                archive.write(path, path.name)
    return dest


@pytest.fixture
def snapshot(tmp_path: Path):
    return build_drug_label_snapshot(
        _archive(tmp_path), tmp_path / "snap", source_url="file://clinpgx_drug_labels_slice"
    )


def test_the_snapshot_holds_every_row_the_archive_did(snapshot) -> None:
    assert snapshot.label_count == len(_rows_from_fixture())
    assert snapshot.parquet_path.is_file()
    assert snapshot.parquet_path.name.endswith(".parquet")
    assert snapshot.parquet_path.parent.name == SNAPSHOT_DATA_DIRNAME


def test_the_regulators_and_levels_recorded_are_the_ones_the_file_states(snapshot) -> None:
    """A walked set, not a count: a sixth agency must show up as a set difference, not a floor."""
    rows = _rows_from_fixture()
    assert set(snapshot.regulators) == {row["Source"] for row in rows if row["Source"].strip()}
    assert set(snapshot.testing_levels) == {
        row["Testing Level"] for row in rows if row["Testing Level"].strip()
    }


def test_the_license_hash_describes_the_file_as_written(snapshot) -> None:
    """`license_sha256` is over the bytes beside the parquet, never a value copied from anywhere.

    That is the property `clinpgx_draft` relies on: it hashes the written `LICENSE.txt` rather than
    trusting `release.json`, so a truncated copy cannot pin to a hash it does not have.
    """
    license_path = snapshot.out_dir / SNAPSHOT_LICENSE_FILENAME
    assert license_path.is_file()
    expected = "sha256:" + hashlib.sha256(license_path.read_bytes()).hexdigest()
    assert snapshot.license_sha256 == expected
    release = json.loads((snapshot.out_dir / RELEASE_FILENAME).read_text())
    assert release["license_sha256"] == expected


def test_the_release_label_names_this_archive_and_not_the_annotation_lane(snapshot) -> None:
    """`clinpgx_drug_labels_<date>`, never `clinpgx_<date>`.

    ClinPGx's archives do not refresh in lockstep — `clinpgx_build`'s own docstring records
    `relationships.zip` a year ahead of `clinicalAnnotations.zip`, an archive RM175 later found had
    been retired outright — so a label that could be confused with the annotation snapshot's would put
    one archive's date on another's rows.
    """
    created = next(
        path.name for path in _SLICE.iterdir() if path.name.startswith("CREATED_")
    )
    date = created.removeprefix("CREATED_").removesuffix(".txt")
    assert snapshot.created_date == date
    assert snapshot.dataset == f"{SOURCE_NAME}_drug_labels_{date}"
    assert snapshot.dataset != f"{SOURCE_NAME}_{date}"


def test_a_rebuild_is_byte_identical_apart_from_the_release_timestamp(tmp_path: Path) -> None:
    """Principle 7 over the artifact the check reads: only `built_at` may move between two builds."""
    archive = _archive(tmp_path)
    first = build_drug_label_snapshot(archive, tmp_path / "one")
    second = build_drug_label_snapshot(archive, tmp_path / "two")
    assert first.parquet_path.read_bytes() == second.parquet_path.read_bytes()

    releases = [
        json.loads((result.out_dir / RELEASE_FILENAME).read_text())
        for result in (first, second)
    ]
    for release in releases:
        release.pop("built_at")
    assert releases[0] == releases[1]


def test_rows_are_sorted_by_label_id_so_the_order_is_the_builders_and_not_the_files(
    snapshot,
) -> None:
    index = load_drug_labels(snapshot.out_dir)
    ids = [row.label_id for row in index.labels]
    assert ids == sorted(ids)
    assert set(ids) == {row["PharmGKB ID"] for row in _rows_from_fixture()}


def test_the_column_map_and_the_readers_column_list_are_one_registry() -> None:
    """Two hand-kept parallel lists is how `SOURCES_FIELDNAMES` lost a column — assert the equality."""
    assert tuple(COLUMN_MAP.values()) == LABEL_COLUMNS


def test_every_cell_is_stored_verbatim_including_the_flag_shaped_columns(snapshot) -> None:
    """Nothing is coerced: a blank becomes `None`, and a stated cell keeps the source's own string."""
    rows = {row["PharmGKB ID"]: row for row in _rows_from_fixture()}
    con = duckdb.connect(":memory:")
    try:
        cursor = con.execute(f"SELECT * FROM read_parquet('{snapshot.parquet_path}')")
        columns = [description[0] for description in cursor.description]
        stored = [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]
    finally:
        con.close()
    assert columns == list(LABEL_COLUMNS)
    for record in stored:
        source_row = rows[record["label_id"]]
        for source_name, target in COLUMN_MAP.items():
            raw = source_row[source_name].strip()
            assert record[target] == (raw or None)


def test_a_renamed_upstream_column_refuses_rather_than_writing_a_column_of_nulls(
    tmp_path: Path,
) -> None:
    """Structural, so it raises in both modes: a silent null column would read as five silent agencies."""
    archive = _archive(tmp_path, drop_column="Testing Level")
    with pytest.raises(DrugLabelError, match="Testing Level"):
        build_drug_label_snapshot(archive, tmp_path / "snap")


def test_a_file_that_is_not_a_zip_refuses_as_this_modules_own_error(tmp_path: Path) -> None:
    broken = tmp_path / "drugLabels.zip"
    broken.write_bytes(b"not a zip archive")
    with pytest.raises(DrugLabelError):
        build_drug_label_snapshot(broken, tmp_path / "snap")


def test_a_transport_failure_reaches_the_caller_as_a_drug_label_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`httpx`'s exceptions do not leave the downloader (`@client-exception-contract`).

    The half-written `.part` goes with it, so a failed run leaves the directory as it found it.
    """

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "stream", _boom)
    dest = tmp_path / "labels" / "drugLabels.zip"
    with pytest.raises(DrugLabelUnavailable):
        download_drug_labels_zip(dest, "https://api.clinpgx.org/v1/download/file/data/drugLabels.zip")
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_the_live_archive_still_has_the_shape_this_builder_reads(tmp_path: Path) -> None:
    """Opt-in (`JUST_DNA_NETWORK_TESTS=1`): the real download, built end to end.

    Asserts relationships rather than the numbers ClinPGx served on any particular day — the live file
    must be a superset of the fixture's regulators and states no testing level this release cannot
    place, which is what a re-curation would break.
    """
    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("network test; set JUST_DNA_NETWORK_TESTS=1 to run")

    archive, digest = download_drug_labels_zip(tmp_path / "drugLabels.zip")
    result = build_drug_label_snapshot(archive, tmp_path / "snap", source_sha256=digest)
    assert result.label_count > len(_rows_from_fixture())
    fixture = {row["Source"] for row in _rows_from_fixture() if row["Source"].strip()}
    assert fixture <= set(result.regulators)
    assert result.license_sha256 is not None
    assert result.dataset is None or result.dataset.startswith(f"{SOURCE_NAME}_drug_labels_")
