"""The MANE snapshot: the numbering frame as a cache rather than a sentence (RM168).

**Every expected value is computed from the fixture at runtime.** The counts this item was decided
on — 19,437 summary rows, 74 MANE Plus Clinical, 120 changed accessions, 222 excluded genes over
seven reasons — are what NCBI served on 2026-09-01, and MANE ships a new release roughly twice a
year. Quoting one into an assertion would convert a live source into a permanently failing test, so
the numbers below are all read back out of the same files the builder read.

Two of the three fixtures are the **whole** upstream file (3.6 KB and 2.0 KB); the summary is a cut
holding the cases the argument turns on — CDKN2A's two rows, RUNX1's one, the VHL transcript the
legacy-insertion probe pins by hand, and two genes that also appear in `changed_select_accessions`
so the cross-table join has positives beside the three negatives.

The live-source test is opt-in behind `JUST_DNA_NETWORK_TESTS=1` (`@network-tests-optin`).
"""

from __future__ import annotations

import csv
import gzip
import json
import os
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_enricher import locations
from just_dna_enricher.cli import app
from just_dna_enricher.licensing import MANE_TERMS, TERMS_BY_SOURCE
from just_dna_enricher.mane_build import (
    MANE_TABLE_NAMES,
    MANE_TABLES,
    MANE_VERSION_LABEL,
    MANE_VERSIONS_FILENAME,
    ManeBuildError,
    ManeUnavailable,
    build_snapshot,
    discover_current_release,
    mane_release_url,
    mane_versions_url,
    parse_ncbi_gene_id,
    parse_versions,
    parse_yes_no,
)
from typer.main import get_command
from typer.testing import CliRunner

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "mane_slice"
SUMMARY = ASSETS / "MANE.GRCh38.v1.5.summary_slice.txt.gz"
CHANGED = ASSETS / "MANE.GRCh38.v1.5.changed_select_accessions.txt.gz"
NOT_IN_MANE = ASSETS / "MANE.GRCh38.v1.5.protein_coding_genes_not_in_mane.txt.gz"
VERSIONS = ASSETS / "README_versions.txt"

_runner = CliRunner()

INPUTS = {
    "summary": SUMMARY,
    "changed_select_accessions": CHANGED,
    "protein_coding_genes_not_in_mane": NOT_IN_MANE,
}


def _raw_rows(path: Path) -> list[dict[str, str]]:
    """The fixture as the source wrote it, `#` and all — the ground truth every count comes from."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        reader.fieldnames = [reader.fieldnames[0].lstrip("#"), *reader.fieldnames[1:]]
        return list(reader)


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> tuple[Path, dict[str, pl.DataFrame], dict]:
    """One build of the fixture, its three frames and its `release.json`."""
    out = tmp_path_factory.mktemp("mane")
    result = build_snapshot(INPUTS, out, versions_file=VERSIONS)
    frames = {
        name: pl.read_parquet(result.parquet_files[name]) for name in MANE_TABLE_NAMES
    }
    release = json.loads((out / "release.json").read_text(encoding="utf-8"))
    return out, frames, release


# ── the normalizers ─────────────────────────────────────────────────────────────────────────────


def test_the_gene_id_normalizer_reads_both_spellings_the_source_uses() -> None:
    """The three files spell one key two ways, and the whole point is that they join.

    Read straight off the fixtures rather than from literals: `summary` writes `GeneID:1029` while
    the other two write a bare number, and a normalizer tested on only one dialect is a join that
    silently never matches (`@one-normalizer-two-spellings`).
    """
    prefixed = {row["NCBI_GeneID"] for row in _raw_rows(SUMMARY)}
    bare = {row["GeneID"] for row in _raw_rows(NOT_IN_MANE)}
    assert all(raw.startswith("GeneID:") for raw in prefixed)
    assert all(raw.isdigit() for raw in bare)
    assert {parse_ncbi_gene_id(raw) for raw in prefixed | bare} == {
        int(raw.removeprefix("GeneID:")) for raw in prefixed | bare
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("", (None, False)), ("Yes", (True, False)), ("No", (False, False)), ("maybe", (None, True))],
)
def test_yes_no_has_three_outcomes_and_counts_the_fourth(raw: str, expected: tuple) -> None:
    """Silence is absence; a token we cannot hold is a finding. `None` is never `False`."""
    assert parse_yes_no(raw) == expected


def test_the_versions_file_is_copied_label_for_label() -> None:
    """A generic parse, so a line MANE adds travels through instead of being dropped.

    The assertion is that the parse round-trips the file's own labels, not that it found three
    particular ones — a reader that knew exactly three names is the thing this avoids.
    """
    text = VERSIONS.read_text(encoding="utf-8")
    parsed = parse_versions(text)
    expected = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in text.splitlines()
        if "\t" in line
    }
    assert parsed == expected
    assert MANE_VERSION_LABEL in parsed


# ── the tables ──────────────────────────────────────────────────────────────────────────────────


def test_every_input_row_reaches_the_parquet(built) -> None:
    """One row out per row in, for all three tables — an equality, not a floor.

    Nothing here is filtered or collapsed, and asserting it over the walked registry is what would
    catch a future drop path added without a counted reason beside it.
    """
    _, frames, release = built
    for name in MANE_TABLE_NAMES:
        assert frames[name].height == len(_raw_rows(INPUTS[name])), name
    assert release["rows"] == {name: frames[name].height for name in MANE_TABLE_NAMES}


def test_the_registry_and_the_written_files_agree(built) -> None:
    """`MANE_TABLES` is what the builder, the CLI and `release.json` all walk.

    An equality over the set rather than a count, so a fourth table cannot be half-added
    (`@registry-completeness`).
    """
    out, frames, release = built
    written = {path.name for path in (out / "data").glob("*.parquet")}
    assert written == {table.parquet for table in MANE_TABLES}
    assert set(frames) == set(MANE_TABLE_NAMES) == set(release["rows"])


def test_mane_status_is_a_column_and_the_plus_clinical_rows_survive(built) -> None:
    """The decision this snapshot turns on: a gene may have two rows, and neither is dropped.

    CDKN2A is the worked case — one MANE Select and one MANE Plus Clinical for GeneID 1029, with
    different CDS numbering. A builder keeping one row per gene would drop the second and hide
    exactly the class a remembered accession hides.
    """
    _, frames, release = built
    summary = frames["summary"]
    raw = _raw_rows(SUMMARY)
    assert release["mane_status_counts"] == {
        status: sum(1 for row in raw if row["MANE_status"] == status)
        for status in {row["MANE_status"] for row in raw}
    }
    # More than one status present at all is what makes the column load-bearing.
    assert summary["mane_status"].n_unique() > 1

    cdkn2a = summary.filter(pl.col("ncbi_gene_id") == 1029)
    assert cdkn2a.height == 2
    assert cdkn2a["mane_status"].n_unique() == 2
    assert cdkn2a["refseq_nuc"].n_unique() == 2

    runx1 = summary.filter(pl.col("symbol") == "RUNX1")
    assert runx1.height == 1, "RUNX1 has one MANE row; the isoform offset is not in MANE and cannot be"


def test_vhl_is_the_transcript_the_legacy_probe_pins_by_hand(built) -> None:
    """The identity protocol's worked case, now readable from a cache instead of a memory."""
    _, frames, _ = built
    vhl = frames["summary"].filter(pl.col("symbol") == "VHL")
    assert vhl.height == 1
    row = vhl.row(0, named=True)
    assert row["mane_status"] == "MANE Select"
    assert row["refseq_nuc"].startswith("NM_000551.")
    assert row["ensembl_nuc"].startswith("ENST00000256474.")


def test_a_gene_absent_from_the_changed_list_has_had_a_stable_frame(built) -> None:
    """The positive statement the cache can make and a memory cannot.

    Computed as a join over the normalized integer key, which is the whole reason the two spellings
    are normalized: the summary says `GeneID:861` and the changed list says `861`.
    """
    _, frames, _ = built
    changed_ids = set(frames["changed_select_accessions"]["ncbi_gene_id"].to_list())
    summary = frames["summary"]
    for symbol in ("RUNX1", "CDKN2A", "VHL"):
        gene_ids = set(summary.filter(pl.col("symbol") == symbol)["ncbi_gene_id"].to_list())
        assert gene_ids and not (gene_ids & changed_ids), symbol
    # And the join is not vacuous: the slice deliberately keeps genes that *are* in the list.
    assert set(summary["ncbi_gene_id"].to_list()) & changed_ids


def test_update_affects_cds_is_a_tri_state_beside_the_source_token(built) -> None:
    """The numbering-frame axis, stated by the source and stored both ways.

    The boolean is what a consumer queries; the raw token is what keeps the mapping auditable, the
    same split `clin_sig`/`clin_sig_raw` established.
    """
    _, frames, release = built
    changed = frames["changed_select_accessions"]
    raw = _raw_rows(CHANGED)
    assert release["update_affects_cds_counts"] == {
        token: sum(1 for row in raw if row["Update_Affects_CDS"] == token)
        for token in {row["Update_Affects_CDS"] for row in raw}
    }
    expected_true = sum(1 for row in raw if row["Update_Affects_CDS"].casefold() == "yes")
    assert changed.filter(pl.col("update_affects_cds")).height == expected_true
    assert (
        changed.filter(pl.col("update_affects_cds").is_null()).height
        == release["unparsable_update_affects_cds"]
        + sum(1 for row in raw if not row["Update_Affects_CDS"].strip())
    )
    # The raw column is the source's own spelling, never re-cased or re-spelled.
    assert set(changed["update_affects_cds_raw"].to_list()) == {
        row["Update_Affects_CDS"] for row in raw
    }


def test_the_exclusion_reason_vocabulary_is_derived_from_the_file(built) -> None:
    """MANE serves `@unreachable-not-absent` itself: no answer, with the reason attached.

    The vocabulary is asserted as an **equality against the file**, never as a list of seven strings
    written down beside it — a hardcoded roster is a registry nothing iterates, and MANE adding an
    eighth reason must show up as a changed count rather than as a silent "other".
    """
    _, frames, release = built
    raw = _raw_rows(NOT_IN_MANE)
    expected = {
        status: sum(1 for row in raw if row["status"] == status)
        for status in {row["status"] for row in raw}
    }
    assert release["excluded_reasons"] == expected
    assert set(frames["protein_coding_genes_not_in_mane"]["status"].to_list()) == set(expected)
    assert sum(expected.values()) == len(raw)
    # `pending MANE review` is a third state beside "excluded for a structural reason" and
    # "MANE answered" — not absent, not decided. Its presence is what makes the column tri-state
    # rather than a yes/no about assembly placement.
    assert "pending MANE review" in expected


def test_a_gene_mane_excluded_is_not_a_gene_mane_answered(built) -> None:
    """The two rosters are disjoint, which is what makes the negative one readable as an answer."""
    _, frames, _ = built
    answered = set(frames["summary"]["ncbi_gene_id"].to_list())
    excluded = set(frames["protein_coding_genes_not_in_mane"]["ncbi_gene_id"].to_list())
    assert not (answered & excluded)


# ── provenance and reproducibility ──────────────────────────────────────────────────────────────


def test_release_json_copies_the_versions_file_rather_than_restating_it(built) -> None:
    """Two of the three labels appear in no filename, which is why the file is copied."""
    _, _, release = built
    assert release["versions"] == parse_versions(VERSIONS.read_text(encoding="utf-8"))
    assert release["mane_release"] == release["versions"][MANE_VERSION_LABEL]
    assert release["dataset"] == f"mane_grch38_v{release['mane_release']}"
    assert release["genome_build"] == "GRCh38"
    assert release["builder_version"] and release["built_at"]


def test_a_local_build_asserts_no_url_it_did_not_fetch(built) -> None:
    """A `README_versions.txt` on disk names a release; it does not name a provenance.

    Writing the versioned URL into a snapshot built from local bytes would state where the bytes came
    from, which this build never saw. Every input is keyed and null rather than the key vanishing:
    unknown, not absent.
    """
    _, _, release = built
    assert release["release_url"] is None
    for field in ("source_url", "source_etag", "source_last_modified"):
        assert set(release[field]) == set(MANE_TABLE_NAMES), field
        assert all(value is None for value in release[field].values()), field
    assert set(release["source_sha256"]) == {*MANE_TABLE_NAMES, MANE_VERSIONS_FILENAME}
    assert all(value is not None for value in release["source_sha256"].values())


def test_a_build_with_no_versions_file_records_an_unknown_release(tmp_path) -> None:
    """An unknown release, never one reconstructed from a filename (the rejected repair)."""
    result = build_snapshot(INPUTS, tmp_path / "snap")
    assert result.release is None
    assert result.dataset is None
    release = json.loads((tmp_path / "snap" / "release.json").read_text(encoding="utf-8"))
    assert release["versions"] == {}
    assert release["release_url"] is None
    assert release["source_sha256"][MANE_VERSIONS_FILENAME] is None


def test_rebuilding_is_byte_identical(tmp_path) -> None:
    """P7: parquet bytes depend on row order, so the order has to be total.

    `built_at` is the only per-run-varying byte and it lives in `release.json`, outside the parquet.
    """
    first = build_snapshot(INPUTS, tmp_path / "a", versions_file=VERSIONS)
    second = build_snapshot(INPUTS, tmp_path / "b", versions_file=VERSIONS)
    for name in MANE_TABLE_NAMES:
        assert first.parquet_files[name].read_bytes() == second.parquet_files[name].read_bytes(), name
    left = json.loads((tmp_path / "a" / "release.json").read_text(encoding="utf-8"))
    right = json.loads((tmp_path / "b" / "release.json").read_text(encoding="utf-8"))
    left.pop("built_at"), right.pop("built_at")
    assert left == right


def test_a_snapshot_missing_a_file_is_refused(tmp_path) -> None:
    """Shipping the summary without the currency check is the defect this item is about."""
    with pytest.raises(ManeBuildError) as excinfo:
        build_snapshot({"summary": SUMMARY}, tmp_path / "snap")
    assert "changed_select_accessions" in str(excinfo.value)


def test_a_cell_the_column_cannot_hold_withholds_and_counts_rather_than_crashing(tmp_path) -> None:
    """A bad *cell* is not a bad *row*, and neither is a traceback.

    Three shapes in one file: a gene id that is not a number, a coordinate that is not (`--5` is the
    one `lstrip("-")` used to let through into `int()` and raise on), and an `Update_Affects_CDS`
    token that is neither `Yes` nor `No`. Each withholds its own value, keeps the row, and lands in
    a counter, so "the source said nothing" stays distinguishable from "the source said something we
    cannot hold".
    """
    raw = _raw_rows(SUMMARY)
    header = list(raw[0])
    broken = raw[0] | {"NCBI_GeneID": "GeneID:not-a-number", "chr_start": "--5", "chr_end": ""}
    summary = tmp_path / "summary.txt"
    with summary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter="\t")
        handle.write("#" + "\t".join(header) + "\n")
        writer.writerows([broken, *raw[1:]])

    changed_raw = _raw_rows(CHANGED)
    changed_header = list(changed_raw[0])
    changed = tmp_path / "changed.txt"
    with changed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=changed_header, delimiter="\t")
        handle.write("#" + "\t".join(changed_header) + "\n")
        writer.writerows([changed_raw[0] | {"Update_Affects_CDS": "Unknown"}, *changed_raw[1:]])

    result = build_snapshot(
        {**INPUTS, "summary": summary, "changed_select_accessions": changed}, tmp_path / "snap"
    )
    assert result.rows["summary"] == len(raw), "a bad cell must not cost the row"
    assert result.rows["changed_select_accessions"] == len(changed_raw)
    assert result.unparsable_gene_id["summary"] == 1
    # `chr_end` is blank, which is an absence rather than a finding, so the row counts once.
    assert result.unparsable_coordinate == 1
    assert result.unparsable_update_affects_cds == 1

    release = json.loads((tmp_path / "snap" / "release.json").read_text(encoding="utf-8"))
    assert release["unparsable_gene_id"]["summary"] == 1
    assert release["unparsable_coordinate"] == 1
    assert release["unparsable_update_affects_cds"] == 1

    frame = pl.read_parquet(result.parquet_files["summary"])
    withheld = frame.filter(pl.col("ncbi_gene_id").is_null())
    assert withheld.height == 1
    assert withheld.row(0, named=True)["chr_start"] is None
    assert withheld.row(0, named=True)["symbol"] == broken["symbol"], "the rest of the row survives"
    # A row with no gene id sorts last, so the order stays total rather than raising on a comparison.
    assert frame["ncbi_gene_id"].to_list()[-1] is None


def test_a_table_with_the_wrong_columns_is_refused_before_any_row(tmp_path) -> None:
    """A header check inside the row loop cannot see an empty table, so it runs on the header."""
    headed = tmp_path / "empty.txt"
    headed.write_text("#NCBI_GeneID\tSymbol\n", encoding="utf-8")
    with pytest.raises(ManeBuildError) as excinfo:
        build_snapshot({**INPUTS, "changed_select_accessions": headed}, tmp_path / "snap")
    assert "Update_Affects_CDS" in str(excinfo.value)


def test_a_ragged_row_is_refused_rather_than_shifted_into_the_frame(tmp_path) -> None:
    """A bad *cell* keeps its row; a bad *field count* does not (`@ragged-csv-row`).

    Both directions, because they arrive by different routes and one of them is invisible to a naive
    reader: a short row leaves nulls in the columns it never reached, and a long one shifts nothing
    but proves the header no longer describes the file.
    """
    raw = _raw_rows(SUMMARY)
    header = list(raw[0])
    for label, line in (
        ("short", "\t".join(raw[0][name] for name in header[:-3])),
        ("long", "\t".join([*(raw[0][name] for name in header), "surplus"])),
    ):
        broken = tmp_path / f"{label}.txt"
        rest = "\n".join("\t".join(row[name] for name in header) for row in raw[1:])
        broken.write_text("#" + "\t".join(header) + "\n" + line + "\n" + rest + "\n", encoding="utf-8")
        with pytest.raises(ManeBuildError) as excinfo:
            build_snapshot({**INPUTS, "summary": broken}, tmp_path / label)
        assert f"header declares {len(header)}" in str(excinfo.value), label


def test_a_file_named_gz_that_is_not_one_fails_as_this_tiers_own_error(tmp_path) -> None:
    """A proxy that decompressed the download and kept the name looks exactly like this.

    Without the translation it escapes as `gzip.BadGzipFile` past the CLI's handler and prints a
    traceback where the operator wanted one line.
    """
    fake = tmp_path / "summary.txt.gz"
    fake.write_bytes(b"#NCBI_GeneID\tsymbol\nGeneID:1\tA1BG\n")
    with pytest.raises(ManeBuildError) as excinfo:
        build_snapshot({**INPUTS, "summary": fake}, tmp_path / "snap")
    assert "really is gzipped" in str(excinfo.value)
    result = _runner.invoke(
        app,
        ["mane", "build", "--summary", str(fake), "--changed", str(CHANGED),
         "--not-in-mane", str(NOT_IN_MANE), "--out", str(tmp_path / "cli")],
    )
    assert result.exit_code == 1
    assert "MANE BUILD FAILED" in result.output + (result.stderr or "")


def test_unavailable_is_a_subclass_so_one_arm_catches_both() -> None:
    """A caller telling an outage from bad data does it by type, never by message text."""
    assert issubclass(ManeUnavailable, ManeBuildError)


# ── licensing ───────────────────────────────────────────────────────────────────────────────────


def test_ncbis_policy_is_recorded_as_unknown_on_every_axis() -> None:
    """A statement that no restriction is imposed is not a grant (`@no-named-licence`).

    Do not "tidy" any of the three to `True`: unknown warns and never gates, and `taints_commercial_use`
    requires an explicit `False`.
    """
    assert TERMS_BY_SOURCE["mane"] is MANE_TERMS
    assert MANE_TERMS.license is None
    assert MANE_TERMS.share_alike is None
    assert MANE_TERMS.commercial_use is None
    assert MANE_TERMS.redistribution is None
    assert MANE_TERMS.license_url and MANE_TERMS.attribution and MANE_TERMS.notice
    # Only NCBI's side of a joint NCBI/EMBL-EBI product was probed, and the notice has to say so
    # rather than leaving a reader to assume the whole product was read.
    assert "EMBL-EBI" in MANE_TERMS.notice


# ── the cache ───────────────────────────────────────────────────────────────────────────────────


def test_the_resolver_finds_a_built_snapshot_and_nothing_else(built, monkeypatch, tmp_path) -> None:
    """Explicit path → `$JUST_DNA_MANE_CACHE` → the shared base, and `None` when there is none."""
    out, _, _ = built
    monkeypatch.setenv("JUST_DNA_MANE_CACHE", "")
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(tmp_path))
    assert locations.resolve_mane_reference(out, load_dotenv_file=False) == out
    assert locations.resolve_mane_reference(load_dotenv_file=False) is None
    monkeypatch.setenv("JUST_DNA_MANE_CACHE", str(out))
    assert locations.resolve_mane_reference(load_dotenv_file=False) == out


def test_a_bare_parquet_is_not_a_mane_snapshot(built, monkeypatch) -> None:
    """Unlike the constraint cache: this one is three tables, and one file is a snapshot missing
    the currency check and the negative roster."""
    out, _, _ = built
    monkeypatch.setenv("JUST_DNA_MANE_CACHE", "")
    lone = out / "data" / "summary.parquet"
    assert locations.resolve_mane_reference(lone, load_dotenv_file=False) is None


def test_release_json_is_readable_by_the_cache_reader(built) -> None:
    """`cache status` labels a snapshot from `dataset`, so the key has to be there and be a string."""
    out, _, _ = built
    payload = locations.read_release(out)
    assert payload is not None
    assert payload["dataset"].startswith("mane_grch38_v")


# ── the command surface ─────────────────────────────────────────────────────────────────────────


def test_the_command_builds_from_local_files_and_prints_what_it_measured(tmp_path) -> None:
    """The counts a reader has to see reach the terminal, not only `release.json`.

    Every assertion is against the JSON the same run wrote, so this cannot drift into a copy of the
    numbers MANE served on one particular day.
    """
    out = tmp_path / "snap"
    result = _runner.invoke(
        app,
        ["mane", "build", "--summary", str(SUMMARY), "--changed", str(CHANGED),
         "--not-in-mane", str(NOT_IN_MANE), "--versions", str(VERSIONS), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    release = json.loads((out / "release.json").read_text(encoding="utf-8"))
    for status, count in release["mane_status_counts"].items():
        assert f"{status} {count}" in result.output
    for reason, count in release["excluded_reasons"].items():
        assert f"{reason} {count}" in result.output
    assert release["dataset"] in result.output
    # The bound the lane exists to state, where an operator will actually see it.
    assert "MANE is the default, not the answer" in result.output
    # A clean file withholds nothing, so the line that would report a residue stays away rather than
    # printing three zeros — the measured zeros are in `release.json` for anyone who wants them.
    assert "withheld cells" not in result.output
    assert release["unparsable_gene_id"] == dict.fromkeys(MANE_TABLE_NAMES, 0)
    assert (release["unparsable_coordinate"], release["unparsable_update_affects_cds"]) == (0, 0)


def test_two_of_the_three_files_is_not_a_snapshot(tmp_path) -> None:
    """Shipping the summary without the currency check is the defect, so the CLI refuses it too."""
    result = _runner.invoke(
        app, ["mane", "build", "--summary", str(SUMMARY), "--out", str(tmp_path / "snap")]
    )
    assert result.exit_code != 0
    assert "notices the frame moving" in result.output + (result.stderr or "")


def test_release_without_download_is_refused_rather_than_believed(tmp_path) -> None:
    """A bare `--release` beside local files would be our claim about somebody else's bytes.

    `--versions` is the honest route, because it is the source's own statement — and parsing the
    release out of a filename is the repair this item explicitly rejected.
    """
    result = _runner.invoke(
        app,
        ["mane", "build", "--release", "1.5", "--summary", str(SUMMARY), "--changed", str(CHANGED),
         "--not-in-mane", str(NOT_IN_MANE), "--out", str(tmp_path / "snap")],
    )
    assert result.exit_code != 0
    assert "README_versions.txt" in result.output + (result.stderr or "")


def test_download_and_local_files_together_are_refused(tmp_path) -> None:
    """Two sources for one input is a build whose provenance nothing can state."""
    result = _runner.invoke(
        app,
        ["mane", "build", "--download", "--summary", str(SUMMARY), "--out", str(tmp_path / "snap")],
    )
    assert result.exit_code != 0
    assert "not both" in result.output + (result.stderr or "")


def test_versions_beside_download_is_refused_rather_than_silently_overwritten(tmp_path) -> None:
    """A download fetches the release's own `README_versions.txt`, so the flag would be ignored.

    Refused for the same reason `--release` without `--download` is: a flag that only means something
    in the other mode is a flag whose failure is silent, and the guard reaches this before any
    network call.
    """
    result = _runner.invoke(
        app,
        ["mane", "build", "--download", "--versions", str(VERSIONS), "--out", str(tmp_path / "snap")],
    )
    assert result.exit_code != 0
    assert "silently overwritten" in result.output + (result.stderr or "")


def test_there_is_no_publish_and_no_use_flag() -> None:
    """No `mane publish`: NCBI grants nothing to permit and refuses nothing to relay, so a command
    that either published or refused would assert an answer nobody has. And no `--use`, because a
    declared-use gate fed an unknown skips every build unconditionally.

    Asserted against the parsed parameter names rather than against the rendered help, which also
    prints the paragraph explaining why the two flags are absent.
    """
    mane = get_command(app).commands["mane"]
    assert set(mane.commands) == {"build"}
    flags = {option for param in mane.commands["build"].params for option in param.opts}
    assert "--use" not in flags
    assert "--offline" not in flags
    assert {"--download", "--release", "--summary", "--changed", "--not-in-mane", "--out"} <= flags


# ── the live source (opt-in) ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to run"
)
def test_current_discovers_a_version_that_resolves_to_a_versioned_directory() -> None:
    """`current/` is read to discover, never to download from.

    The two halves asserted together: the discovered version has to be one the versioned layout
    actually serves, or the pin is a hope rather than a URL.
    """
    release = discover_current_release()
    assert release
    pinned = httpx.get(mane_versions_url(release), timeout=60.0, follow_redirects=True)
    pinned.raise_for_status()
    assert parse_versions(pinned.text)[MANE_VERSION_LABEL] == release
    for table in MANE_TABLES:
        head = httpx.head(
            mane_release_url(release, table.source_suffix), timeout=60.0, follow_redirects=True
        )
        assert head.status_code == 200, table.name
