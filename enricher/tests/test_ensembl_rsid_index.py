"""The Ensembl rsID index (0.9, RM431 ask 4): a derived, local-only lane, rsID → (chrom, start).

Built from a split core attested by its manifest (`ensembl_split_core`, the enricher conftest: RM381's
real slice plus the non-nucleotide rows and an rsID at two loci), and read by `resolver.lookup_loci`,
which must answer exactly as its scan does, only from fewer row groups. Every expected answer is the
scan's own, computed in the test with no index in place.
"""

import ast
import json
import logging
import threading
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher import caches, download, ensembl_rsid_index_build, locations, remote, resolver
from just_dna_enricher.caches import CACHE_LANES, LANES_BY_NAME, RebuildRequest, rebuild_lane
from just_dna_enricher.cli import app
from just_dna_enricher.enrich import enrich
from just_dna_enricher.ensembl_rsid_index_build import (
    INDEX_BUCKET_WIDTH,
    INDEX_FILE_PATTERN,
    INDEX_GLOB,
    RsidIndexError,
    build_rsid_index,
    core_pin,
)
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS, resolve_ensembl_rsid_index_reference
from just_dna_enricher.lookup import lookup_variant
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


def test_a_moved_parent_never_rebuilds_the_index_it_is_refused_once_and_the_core_scanned(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    ensembl_split_core,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The pm's reading 3: a 42-minute build inside a lookup is no answer, and neither is a provisioning run.

    The core moved under the index (its bytes differ under the same label). Two lookups and a
    `prepare_caches` leave every byte of the index as it was; the refusal is said once, naming the
    rebuild, and each lookup is the scan's answer.
    """
    stale = build_rsid_index(
        ensembl_split_core(tmp_path / "older", drop=(MULTI_ALT,)), tmp_path / "base" / "ensembl_rsid_index"
    ).out_dir
    core = ensembl_split_core(tmp_path / "ensembl_variations")
    scanned = _lookup(core)
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(stale.rglob("*"))
        if path.is_file()
    }
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(stale))
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.resolver"):
        assert _lookup(core) == scanned
        assert _lookup(core) == scanned
    (refusal,) = [r.getMessage() for r in caplog.records if "rsID index" in r.getMessage()]
    assert refusal.endswith(
        f"Rebuild it in place with `just-dna-enricher cache rebuild --only ensembl_rsid_index --out {tmp_path / 'base'}`."
    )
    (prepared,) = caches.prepare_caches([LANES_BY_NAME["ensembl_rsid_index"]])
    assert prepared.ready is True and prepared.route == "present", (
        "a present index, stale or not, is left alone"
    )
    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(stale.rglob("*"))
        if path.is_file()
    }
    assert after == before, "nothing rebuilt the index"


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


#: The scan note's fixed half, pinned (`@warning-text-is-api`).
SCAN_NOTE = "so rsIDs in the Ensembl core at"


def test_a_lookup_with_no_index_says_once_per_process_that_one_exists_and_how_to_build_it(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    core: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The pm's reading 2: a scan says once that the index exists, with the command run here as printed."""
    monkeypatch.setattr(resolver, "_SCAN_NOTED", threading.Event())
    place = tmp_path / "base" / "ensembl_rsid_index"
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(place))
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    with caplog.at_level(logging.INFO, logger="just_dna_enricher.resolver"):
        scanned = _lookup(core)
        assert _lookup(core) == scanned
    notes = [record for record in caplog.records if SCAN_NOTE in record.getMessage()]
    assert len(notes) == 1, "once per process, not once per lookup"
    assert notes[0].levelno == logging.INFO, "a scan is a normal state, not a fault"
    assert notes[0].getMessage() == (
        f"No rsID index was found at {place}, so rsIDs in the Ensembl core at {core} are looked up by scanning "
        "its whole `id` column. An index (the `ensembl_rsid_index` lane) makes each a pruned read, and it is "
        "built only when named. Build it with "
        f"`just-dna-enricher cache rebuild --only ensembl_rsid_index --out {tmp_path / 'base'}`."
    )
    command = notes[0].getMessage().split("`")[-2].split()
    result = CliRunner().invoke(app, command[1:])
    assert result.exit_code == 0, result.output
    assert resolver._rsid_index_beside(core) is not None, (
        "the printed command built the index the reader takes"
    )
    assert _lookup(core) == scanned


def test_a_scan_says_nothing_where_no_index_could_be_built(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    core: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A core with no manifest cannot be indexed (the builder refuses it), so no command is offered."""
    monkeypatch.setattr(resolver, "_SCAN_NOTED", threading.Event())
    (core / "manifest.json").unlink()
    with caplog.at_level(logging.INFO, logger="just_dna_enricher.resolver"):
        _lookup(core)
    assert not [record for record in caplog.records if "rsID index" in record.getMessage()]


def test_a_core_with_no_manifest_is_scanned_whatever_index_is_present(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, index: Path
) -> None:
    scanned = _lookup(core)
    (core / "manifest.json").unlink()
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    assert _lookup(core) == scanned


# ── the explicit seam (the pm's reading 5): a host that passes lane paths hands the index over too ──


def _drop_from_index(index: Path, rsid: str) -> None:
    """Rewrite the index without `rsid`, its pin unchanged: a lookup that misses it read the index."""
    path = index / "data" / INDEX_FILE_PATTERN.format(bucket=int(rsid[2:]) // INDEX_BUCKET_WIDTH)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_parquet('{path}') WHERE rs <> {int(rsid[2:])}) TO '{path}.tmp' (FORMAT parquet)"
    )
    Path(f"{path}.tmp").replace(path)


def test_an_index_passed_explicitly_is_read_and_the_environment_is_not_asked(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, ensembl_split_core, core: Path, index: Path, tmp_path
) -> None:
    """The environment names an index of another core; the one passed, which pins this core, is read."""
    scanned = _lookup(core)
    stale = build_rsid_index(
        ensembl_split_core(tmp_path / "older", drop=(MULTI_ALT,)), tmp_path / "stale"
    ).out_dir
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(stale))
    collected: set[str] = set()
    explicit = lookup_loci(core, ASKED, [], non_nucleotide=collected, rsid_index=index)
    assert (explicit[0], explicit[1], [str(w) for w in explicit[2]], collected) == scanned
    _drop_from_index(index, MULTI_ALT)
    loci, _, _ = lookup_loci(core, [MULTI_ALT], [], rsid_index=index)
    assert loci == {}, "the index passed is what was read"


def test_an_explicit_place_with_no_index_is_scanned_and_named_never_the_environments(
    no_ambient_caches,
    monkeypatch: pytest.MonkeyPatch,
    core: Path,
    index: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(resolver, "_SCAN_NOTED", threading.Event())
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(index))
    _drop_from_index(index, MULTI_ALT)
    place = tmp_path / "host" / "rsid-index"
    with caplog.at_level(logging.INFO, logger="just_dna_enricher.resolver"):
        loci, _, _ = lookup_loci(core, [MULTI_ALT], [], rsid_index=place)
    assert loci[MULTI_ALT], "scanned: the environment's index (which lacks it) was not read"
    (note,) = [r.getMessage() for r in caplog.records if SCAN_NOTE in r.getMessage()]
    assert f"No rsID index was found at {place}," in note
    assert note.endswith(
        "Build it with `just-dna-enricher cache rebuild --only ensembl_rsid_index --out <dir>` and pass "
        "<dir>/ensembl_rsid_index as `rsid_index`."
    )
    assert locations.ENSEMBL_RSID_INDEX_CACHE_VAR not in note, (
        "a host passing paths is not told to export one"
    )


def test_a_stale_index_passed_explicitly_is_refused_naming_the_rebuild_for_the_caller(
    no_ambient_caches,
    ensembl_split_core,
    core: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stale = build_rsid_index(
        ensembl_split_core(tmp_path / "older", drop=(MULTI_ALT,)), tmp_path / "idx"
    ).out_dir
    scanned = _lookup(core)
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.resolver"):
        collected: set[str] = set()
        loci, candidates, warnings = lookup_loci(core, ASKED, [], non_nucleotide=collected, rsid_index=stale)
    assert (loci, candidates, [str(w) for w in warnings], collected) == scanned
    (refusal,) = [r.getMessage() for r in caplog.records if "rsID index" in r.getMessage()]
    assert str(stale) in refusal and str(core) in refusal
    assert refusal.endswith(
        "Rebuild it with `just-dna-enricher cache rebuild --only ensembl_rsid_index --out <dir>` and pass "
        "<dir>/ensembl_rsid_index as `rsid_index`."
    )


# ── the seam on every entry point that reads the index (the pm, 6e52b9a1 reading 1) ──────────────
#
# The registry's hints call `lookup_variant` and its enrich step calls `enrich(ensembl_cache=)`; neither
# calls `lookup_loci`. Each takes `rsid_index` beside `ensembl_cache` and passes it down: given, it is the
# only place looked in. The environment names an index lacking the rsID asked, so an answer that finds it
# read the index passed, and one that misses it read the environment's.

#: An rsID the fixture core holds at one locus, 11:5226773 TGG>T,TG.
ONE_LOCUS = "rs267607291"


@pytest.fixture
def environment_lacks_it(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> Path:
    """An index of this core, without `ONE_LOCUS`, named by the environment."""
    elsewhere = build_rsid_index(core, tmp_path / "env-index").out_dir
    _drop_from_index(elsewhere, ONE_LOCUS)
    monkeypatch.setenv(locations.ENSEMBL_RSID_INDEX_CACHE_VAR, str(elsewhere))
    return elsewhere


def test_lookup_variant_reads_the_index_passed_beside_the_core_never_the_environments(
    environment_lacks_it: Path, core: Path, index: Path, tmp_path: Path
) -> None:
    nowhere = tmp_path / "no-clinvar"
    asked = {"rsid": ONE_LOCUS, "offline": True, "ensembl_cache": core, "clinvar_cache": nowhere}
    passed = lookup_variant(**asked, rsid_index=index)
    expected = lookup_loci(core, [ONE_LOCUS], [], rsid_index=index)[0][ONE_LOCUS]
    assert expected and passed.loci == expected
    assert lookup_variant(**asked).loci == [], "unpassed, the environment's index (which lacks it) is read"


def test_enrich_reads_the_index_passed_beside_the_core_never_the_environments(
    environment_lacks_it: Path, core: Path, index: Path, tmp_path: Path
) -> None:
    def spec(name: str) -> Path:
        root = tmp_path / name
        root.mkdir()
        (root / "module_spec.yaml").write_text(
            f"schema_version: '1.0'\nmodule:\n  name: {name}\n  title: T\n  description: d\n  report_title: T\n",
            encoding="utf-8",
        )
        (root / "variants.csv").write_text(
            f"rsid,genotype,state,conclusion,gene\n{ONE_LOCUS},T/TGG,risk,c,HBB\n", encoding="utf-8"
        )
        (root / "studies.csv").write_text(f"rsid,pmid\n{ONE_LOCUS},25741868\n", encoding="utf-8")
        return root

    asked = {"offline": True, "ensembl_cache": core, "clinvar_cache": tmp_path / "no-clinvar", "write": False}
    passed = enrich(spec("passed"), rsid_index=index, **asked)
    placed = {(row.rsid, row.chrom, row.start) for row in passed.rows if row.chrom}
    expected = lookup_loci(core, [ONE_LOCUS], [], rsid_index=index)[0][ONE_LOCUS]
    assert placed == {(ONE_LOCUS, locus["chrom"], int(locus["start"])) for locus in expected}
    unpassed = enrich(spec("unpassed"), **asked)
    assert not [row for row in unpassed.rows if row.chrom], "unpassed, the environment's index is read"


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


class _ObservedConnection:
    """A real duckdb connection that records its statements and, at close, its temporary directory."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection
        self.statements: list[str] = []
        self.temp_directory: str | None = None

    def execute(self, sql: str, *args):
        self.statements.append(sql)
        return self._connection.execute(sql, *args)

    def close(self) -> None:
        (self.temp_directory,) = self._connection.execute(
            "SELECT current_setting('temp_directory')"
        ).fetchone()
        self._connection.close()


def test_the_build_spills_into_its_staging_directory_and_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    """The deferred spill fix's test: the sort's temporary directory is inside the output's staging.

    A spill anywhere else lands on whatever disk duckdb defaults to (`.tmp` in the working directory),
    which on the real release was about 11 GB at the peak; inside the staging it is on the output's disk
    and removed with it.
    """
    opened: list[_ObservedConnection] = []
    real_connect = duckdb.connect

    def observed_connect(*args, **kwargs):
        connection = _ObservedConnection(real_connect(*args, **kwargs))
        opened.append(connection)
        return connection

    monkeypatch.setattr(ensembl_rsid_index_build.duckdb, "connect", observed_connect)
    out = tmp_path / "ensembl_rsid_index"
    build_rsid_index(core, out)
    sorting = [c for c in opened if any(sql.lstrip().startswith("COPY") for sql in c.statements)]
    assert len(sorting) == 1, "one connection runs both passes"
    staging = out / ensembl_rsid_index_build._STAGING_DIRNAME
    assert sorting[0].temp_directory == str(staging / "spill")
    assert Path(sorting[0].temp_directory).is_relative_to(staging)
    assert not staging.exists(), "the staging directory, spill included, is removed after the build"


def test_the_builder_is_its_own_module_and_reads_with_duckdb() -> None:
    tree = ast.parse(Path(ensembl_rsid_index_build.__file__).read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "duckdb" in imported
    assert not {name for name in imported if name.startswith("polars")}, (
        "a runtime reader imports helpers from here, so the module stays off the [dev] extra"
    )


# ── built only when named (the pm's reading 2, 2026-11-18) ──────────────────────────────────────

#: The phrase every passed-over route says, pinned (`@warning-text-is-api`): the reason, and the command.
NAMED_ONLY_PHRASE = "built only when named, `cache rebuild --only ensembl_rsid_index`"


def test_a_lane_built_only_when_named_is_rebuild_only_and_states_why() -> None:
    """Walked: such a lane has an adapter and no pull, and its own command is the `--only` that names it."""
    named_only = [lane for lane in CACHE_LANES if lane.named_only is not None]
    assert [lane.name for lane in named_only] == ["ensembl_rsid_index"]
    for lane in named_only:
        assert lane.rebuild is not None and lane.ensure is None, lane.name
        assert lane.build_command == f"cache rebuild --only {lane.name}", lane.name
    assert LANES_BY_NAME["ensembl_rsid_index"].named_only.startswith(NAMED_ONLY_PHRASE)


def test_a_bare_rebuild_does_not_build_the_index_and_says_how(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    """`rebuild_caches(lanes=None)` names no lane: the index is not run, its parent on disk or not."""
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    lane = LANES_BY_NAME["ensembl_rsid_index"]
    monkeypatch.setattr(caches, "CACHE_LANES", [lane])
    (outcome,) = caches.rebuild_caches(out=tmp_path / "out")
    assert outcome.built is None and NAMED_ONLY_PHRASE in outcome.detail
    assert not (tmp_path / "out" / lane.name).exists(), "nothing was built"
    (named,) = caches.rebuild_caches([lane], out=tmp_path / "out")
    assert named.built is True, named.detail


def test_prepare_never_builds_the_index_even_named_and_names_the_rebuild_into_its_place(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    monkeypatch.setenv(locations.CACHE_BASE_VAR, str(tmp_path / "base"))
    lane = LANES_BY_NAME["ensembl_rsid_index"]
    monkeypatch.setenv(lane.env_var, "")
    (outcome,) = caches.prepare_caches([lane])
    assert outcome.ready is None and outcome.route == "none"
    assert outcome.detail == (
        f"{lane.named_only}; build it where it is read with "
        f"`just-dna-enricher cache rebuild --only ensembl_rsid_index --out {tmp_path / 'base'}`"
    )
    assert not (tmp_path / "base" / lane.name).exists(), "prepare built nothing"
    command = outcome.detail.split("`")[-2].split()
    result = CliRunner().invoke(app, command[1:])
    assert result.exit_code == 0, result.output
    (present,) = caches.prepare_caches([lane])
    assert present.ready is True and present.route == "present", "the command built it where prepare looks"


def test_a_bare_cache_rebuild_dry_run_passes_the_index_over_and_a_named_one_would_build_it(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    runner = CliRunner()
    bare = runner.invoke(app, ["cache", "rebuild", "--dry-run", "--out", str(tmp_path / "out")])
    assert bare.exit_code == 0, bare.output
    line = next(line for line in bare.output.splitlines() if line.strip().startswith("ensembl_rsid_index"))
    assert "not run" in line and NAMED_ONLY_PHRASE in line
    named = runner.invoke(
        app, ["cache", "rebuild", "--dry-run", "--only", "ensembl_rsid_index", "--out", str(tmp_path / "out")]
    )
    assert named.exit_code == 0, named.output
    assert "ensembl_rsid_index would build" in " ".join(named.output.split())


def test_prepare_names_the_build_where_the_variable_points_not_the_default(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, core: Path, tmp_path: Path
) -> None:
    """The reader looks where `$JUST_DNA_ENSEMBL_RSID_INDEX_CACHE` points, so that is where the command builds."""
    monkeypatch.setenv(locations.ENSEMBL_CACHE_VAR, str(core))
    lane = LANES_BY_NAME["ensembl_rsid_index"]
    monkeypatch.setenv(lane.env_var, str(tmp_path / "srv" / "ensembl_rsid_index"))
    (named_for_the_lane,) = caches.prepare_caches([lane])
    assert named_for_the_lane.detail.endswith(f"--out {tmp_path / 'srv'}`")
    command = named_for_the_lane.detail.split("`")[-2].split()
    assert CliRunner().invoke(app, command[1:]).exit_code == 0
    assert resolver._rsid_index_beside(core) is not None, "built where the reader looks"
    monkeypatch.setenv(lane.env_var, str(tmp_path / "my-index"))
    (elsewhere,) = caches.prepare_caches([lane])
    assert elsewhere.detail.endswith(
        f"`just-dna-enricher cache rebuild --only ensembl_rsid_index --out <dir>` and point "
        f"${lane.env_var} at <dir>/ensembl_rsid_index"
    )


def test_cache_status_says_an_absent_index_is_built_only_when_named_and_where(
    no_ambient_caches, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lane = LANES_BY_NAME["ensembl_rsid_index"]
    monkeypatch.setenv(lane.env_var, str(tmp_path / "base" / "ensembl_rsid_index"))
    result = CliRunner().invoke(app, ["cache", "status"])
    assert result.exit_code == 0, result.output
    line = " ".join(
        next(
            line for line in result.output.splitlines() if line.strip().startswith("ensembl_rsid_index")
        ).split()
    )
    assert "absent" in line and NAMED_ONLY_PHRASE in line
    assert line.endswith(
        f"`just-dna-enricher cache rebuild --only ensembl_rsid_index --out {tmp_path / 'base'}`"
    )
    assert line.count("cache rebuild --only ensembl_rsid_index") == 2, (
        "the reason's command, then where to run it"
    )
