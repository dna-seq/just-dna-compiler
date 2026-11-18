"""The Ensembl rsID index (0.9, RM431 ask 4): a derived, local-only lane, rsID → (chrom, start).

Built from a split core attested by its manifest (`ensembl_split_core`, the enricher conftest: RM381's
real slice plus the non-nucleotide rows and an rsID at two loci), and read by `resolver.lookup_loci`,
which must answer exactly as its scan does, only from fewer row groups. Every expected answer is the
scan's own, computed in the test with no index in place.
"""

import ast
import json
import logging
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher import download, ensembl_rsid_index_build, locations, remote, resolver
from just_dna_enricher.caches import CACHE_LANES, LANES_BY_NAME, RebuildRequest, rebuild_lane
from just_dna_enricher.cli import app
from just_dna_enricher.ensembl_rsid_index_build import (
    INDEX_BUCKET_WIDTH,
    INDEX_FILE_PATTERN,
    INDEX_GLOB,
    RsidIndexError,
    build_rsid_index,
    core_pin,
)
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS, resolve_ensembl_rsid_index_reference
from just_dna_enricher.resolver import lookup_loci
from just_dna_format.snapshot import read_release, release_label
from typer.testing import CliRunner

#: The release RM381's slice was copied from (its README), which the fixture core states.
ENSEMBL_SPLIT_RELEASE = "ensembl-variation-2026_07_13-vep116.0"
#: Every rsID the fixture core holds, by kind, plus one it does not (a miss) and one not of the `rs` form.
MULTI_ALT = "rs1555461597"  # GTT>G, GTT>GT, GTT>GTTT at 16:23635706
TWO_LOCI = "rs1603142144"  # X:10277 and an N-masked Y:10277
NON_NUCLEOTIDE = "rs1553186440"  # `<.>`: in the snapshot, placed nowhere (RM271)
MISS = "rs1"
NOT_RS = "COSV12345"
ASKED = [MULTI_ALT, TWO_LOCI, NON_NUCLEOTIDE, "rs267607291", "rs2100212723", MISS, NOT_RS]


@pytest.fixture
def core(ensembl_split_core, tmp_path: Path) -> Path:
    return ensembl_split_core(tmp_path / "ensembl_variations")


@pytest.fixture
def index(core: Path, tmp_path: Path) -> Path:
    return build_rsid_index(core, tmp_path / "ensembl_rsid_index").out_dir


def _lookup(core: Path) -> tuple:
    """`lookup_loci` for every asked rsID: loci, candidates, warnings and the non-nucleotide collector."""
    collected: set[str] = set()
    loci, candidates, warnings = lookup_loci(core, ASKED, [], non_nucleotide=collected)
    return loci, candidates, [str(w) for w in warnings], collected


# ── the build ───────────────────────────────────────────────────────────────────────────────────


def test_the_index_holds_every_rsid_locus_of_the_core_once_sorted_by_rsid(core: Path, index: Path) -> None:
    con = duckdb.connect()
    expected = con.execute(
        f"SELECT DISTINCT CAST(substr(id, 3) AS UBIGINT), chrom, start FROM read_parquet('{core}/data/*.parquet') "
        "ORDER BY 1, 2, 3"
    ).fetchall()
    built = con.execute(f"SELECT rs, chrom, start FROM read_parquet('{index}/data/{INDEX_GLOB}')").fetchall()
    assert built == expected, "every (rsID, chrom, start) of the core once, in rsID order"
    release = read_release(index)
    assert release is not None and release.row_count == len(expected)
    assert release.parents == {"ensembl": {**core_pin(core), "path": str(core)}}
    assert release_label(index) == ENSEMBL_SPLIT_RELEASE, "the index states the core release it indexes"


def test_the_parent_pin_is_the_release_and_the_attested_files(
    core: Path, ensembl_split_core, tmp_path
) -> None:
    pin = core_pin(core)
    assert pin is not None and pin["release_id"] == ENSEMBL_SPLIT_RELEASE
    same_label_other_bytes = ensembl_split_core(tmp_path / "other", drop=(MULTI_ALT,))
    other = core_pin(same_label_other_bytes)
    assert other is not None and other["release_id"] == pin["release_id"]
    assert other != pin, "one label over different bytes is another parent (RM445's sticky label)"


def test_a_core_its_manifest_does_not_name_cannot_be_indexed(tmp_path: Path, core: Path) -> None:
    (core / "manifest.json").unlink()
    with pytest.raises(RsidIndexError, match="manifest"):
        build_rsid_index(core, tmp_path / "index")
    with pytest.raises(RsidIndexError):
        build_rsid_index(tmp_path / "absent", tmp_path / "index2")


def test_a_core_whose_chromosome_spans_two_files_is_refused(core: Path, tmp_path: Path) -> None:
    """The build drops duplicates one file at a time, which is whole only with one chromosome per file."""
    source = core / "data" / "homo_sapiens-chr16.parquet"
    twin = core / "data" / "homo_sapiens-chr16b.parquet"
    twin.write_bytes(source.read_bytes())
    manifest = json.loads((core / "manifest.json").read_text())
    entry = next(e for e in manifest["files"] if e["path"] == "data/homo_sapiens-chr16.parquet")
    manifest["files"].append({**entry, "path": "data/homo_sapiens-chr16b.parquet"})
    (core / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RsidIndexError, match="chromosome 16 is in both"):
        build_rsid_index(core, tmp_path / "index")
    assert not (tmp_path / "index" / "data").exists(), "a refused build moves nothing into place"


# ── the reader ──────────────────────────────────────────────────────────────────────────────────


def test_lookup_loci_through_the_index_answers_exactly_as_its_scan(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, index: Path
) -> None:
    scanned = _lookup(core)
    assert scanned[0][MULTI_ALT] and len(scanned[0][TWO_LOCI]) == 1 and NON_NUCLEOTIDE in scanned[3]
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    assert _lookup(core) == scanned


def test_the_reader_consults_the_index_rather_than_scanning(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, index: Path
) -> None:
    """An index whose payload omits an rsID (its pin unchanged) hides it: the index is what was read."""
    path = index / "data" / INDEX_FILE_PATTERN.format(bucket=int(MULTI_ALT[2:]) // INDEX_BUCKET_WIDTH)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_parquet('{path}') WHERE rs <> {int(MULTI_ALT[2:])}) TO '{path}.tmp' (FORMAT parquet)"
    )
    Path(f"{path}.tmp").replace(path)
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    loci, _, warnings = lookup_loci(core, [MULTI_ALT], [])
    assert loci == {} and any(MULTI_ALT in str(w) for w in warnings)


def test_an_index_of_another_core_is_refused_and_the_core_is_scanned(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    ensembl_split_core,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    built_from = ensembl_split_core(tmp_path / "older", drop=(MULTI_ALT,))
    index = build_rsid_index(built_from, tmp_path / "ensembl_rsid_index").out_dir
    core = ensembl_split_core(tmp_path / "ensembl_variations")
    scanned = _lookup(core)
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.resolver"):
        assert _lookup(core) == scanned, "a refused index is not read: the scan answers"
    refusals = [r.getMessage() for r in caplog.records if "rsID index" in r.getMessage()]
    assert refusals and "cache rebuild --only ensembl_rsid_index" in refusals[0]
    assert str(index) in refusals[0] and str(core) in refusals[0]


def test_an_index_that_cannot_be_read_is_no_answer_and_the_core_is_scanned(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    core: Path,
    index: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An index being rebuilt in place loses its files for a moment; its pin still matches."""
    scanned = _lookup(core)
    for path in (index / "data").glob(INDEX_GLOB):
        path.write_bytes(b"PAR1 not a parquet file")
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.resolver"):
        assert _lookup(core) == scanned
    assert any("could not be read" in r.getMessage() for r in caplog.records)


def test_the_refusal_names_a_rebuild_into_the_place_the_reader_looks(tmp_path: Path) -> None:
    from_lane = resolver._rebuild_instruction(tmp_path / "ensembl_rsid_index")
    assert from_lane == (
        f"Rebuild it in place with `just-dna-enricher cache rebuild --only ensembl_rsid_index --out {tmp_path}`."
    )
    elsewhere = resolver._rebuild_instruction(tmp_path / "my-index")
    assert "--out <dir>" in elsewhere and locations.ENSEMBL_RSID_INDEX_CACHE_VAR in elsewhere


def test_the_command_the_refusal_names_rebuilds_the_index_where_the_reader_looks(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, ensembl_split_core, tmp_path: Path
) -> None:
    """Run as printed: an index of an older core is rebuilt in place, and the reader takes it again."""
    older = ensembl_split_core(tmp_path / "older", drop=(MULTI_ALT,))
    index = build_rsid_index(older, tmp_path / "ensembl_rsid_index").out_dir
    core = ensembl_split_core(tmp_path / "ensembl_variations")
    scanned = _lookup(core)
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    assert resolver._rsid_index_beside(core) is None, "the older core's index is refused"
    command = resolver._rebuild_instruction(index).split("`")[1].split()
    assert command[:2] == ["just-dna-enricher", "cache"]
    result = CliRunner().invoke(app, command[1:])
    assert result.exit_code == 0, result.output
    assert resolver._rsid_index_beside(core) is not None, "the rebuilt index pins the core beside it"
    assert _lookup(core) == scanned


def test_a_core_with_no_manifest_is_scanned_whatever_index_is_present(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, index: Path
) -> None:
    scanned = _lookup(core)
    (core / "manifest.json").unlink()
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    assert _lookup(core) == scanned


# ── the lane ────────────────────────────────────────────────────────────────────────────────────


def test_the_lane_is_derived_local_only_and_never_remote() -> None:
    lane = LANES_BY_NAME["ensembl_rsid_index"]
    assert lane.parents == ("ensembl",)
    assert lane.ensure is None and lane.publish_repo is None and lane.unpublished
    assert lane.rebuild is not None
    assert "ensembl_rsid_index" not in SNAPSHOT_REPO_IDS
    assert "ensembl_rsid_index" not in remote.REMOTE_LANES
    names = [lane.name for lane in CACHE_LANES]
    assert names.index("ensembl") < names.index("ensembl_rsid_index"), "a parent precedes its child"


def test_no_pull_builds_it_so_enrich_with_download_pays_nothing() -> None:
    """`ensure_snapshot` and every other `ensure_*` live in `download`, which never names the lane."""
    tree = ast.parse(Path(download.__file__).read_text(encoding="utf-8"))
    named = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not {name for name in named if "rsid_index" in name}
    assert "ensembl_rsid_index" not in Path(download.__file__).read_text(encoding="utf-8")


def test_cache_rebuild_builds_it_from_the_parent_on_disk(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    outcome = rebuild_lane(LANES_BY_NAME["ensembl_rsid_index"], RebuildRequest(out_dir=tmp_path / "out"))
    assert outcome.built is True, outcome.detail
    assert resolve_ensembl_rsid_index_reference(tmp_path / "out", load_dotenv_file=False) == tmp_path / "out"
    assert json.loads((tmp_path / "out" / "release.json").read_text())["parents"]["ensembl"][
        "release_id"
    ] == (ENSEMBL_SPLIT_RELEASE)


def test_a_rebuild_with_no_parent_is_could_not_run_naming_it(no_ambient_caches, tmp_path: Path) -> None:
    outcome = rebuild_lane(LANES_BY_NAME["ensembl_rsid_index"], RebuildRequest(out_dir=tmp_path / "out"))
    assert outcome.built is None and "ensembl" in outcome.detail


def test_the_builder_is_its_own_module_and_reads_with_duckdb() -> None:
    tree = ast.parse(Path(ensembl_rsid_index_build.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "duckdb" in imported
    assert not {name for name in imported if name.startswith("polars")}, (
        "a runtime reader imports helpers from here, so the module stays off the [dev] extra"
    )
