"""A `--pin` is taken by the lane's build or refused before anything runs (RM416), and gnomAD 4.1.2 (RM410).

Nine rebuild adapters ignored `RebuildRequest.pin`, so `cache rebuild --pin constraint=4.1.2` built 4.1
and said nothing, and the dry run (RM411) printed "would build 4.1.2". The registry of lanes that take a
pin is held equal to the adapters that read one, by an AST walk, so a tenth adapter that ignores it
cannot join the set by a line of prose.
"""

import ast
import gzip
import inspect
import shutil
from pathlib import Path

import pytest
from just_dna_enricher import caches, constraint_build
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest, _rebuild_constraint, rebuild_lane
from just_dna_enricher.cli import app
from just_dna_enricher.gene_metrics import enrich_gene_metrics
from just_dna_format.snapshot import release_label
from typer.testing import CliRunner

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_SLICE = _ASSETS / "gnomad_v4.1_constraint_slice.tsv"


def _reads_the_pin(function) -> bool:
    tree = ast.parse(inspect.getsource(function))
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "pin"
        and getattr(node.value, "id", None) == "request"
        for node in ast.walk(tree)
    )


def test_the_lanes_that_take_a_pin_are_the_adapters_that_read_one() -> None:
    readers = {
        lane.name for lane in caches.CACHE_LANES if lane.rebuild is not None and _reads_the_pin(lane.rebuild)
    }
    assert caches._PINNABLE == readers


def test_a_pin_for_a_lane_that_cannot_take_one_is_refused_before_the_run(tmp_path: Path) -> None:
    """At the command line, before any lane downloads; the message names the lanes that do take one."""
    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(tmp_path), "--only", "clinvar", "--pin", "clinvar=2026-10-01"]
    )
    assert result.exit_code != 0
    assert "clinvar takes no --pin" in result.output
    assert "constraint" in result.output
    assert not tmp_path.joinpath("clinvar").exists()


def test_the_python_route_refuses_it_too(tmp_path: Path) -> None:
    """`prepare_caches` and a host calling `rebuild_lane` reach the same guard, as a failed lane."""
    outcome = rebuild_lane(
        LANES_BY_NAME["mitomap"],
        RebuildRequest(out_dir=tmp_path / "mitomap", declared_use="unstated", pin="2026-11-05"),
    )
    assert outcome.built is False
    assert "mitomap takes no --pin" in outcome.detail
    assert not (tmp_path / "mitomap").exists()


def test_the_constraint_pin_picks_the_release_its_url_and_its_label(monkeypatch, tmp_path: Path) -> None:
    """On the previous `main` the adapter fetched the 4.1 URL whatever the pin said."""
    fetched: list[tuple[str, str]] = []

    def fake_download(dest: Path, url: str = constraint_build.DEFAULT_CONSTRAINT_URL) -> Path:
        fetched.append((dest.name, url))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(dest, "wt", encoding="utf-8") as handle:
            handle.write(_SLICE.read_text(encoding="utf-8"))
        return dest

    monkeypatch.setattr(constraint_build, "download_constraint_tsv", fake_download)
    for pin, name in (
        ("4.1.2", "gnomad.v4.1.2.constraint_metrics.tsv.bgz"),
        ("4.1", "gnomad.v4.1.constraint_metrics.tsv"),
    ):
        out = tmp_path / pin
        outcome = _rebuild_constraint(RebuildRequest(out_dir=out, declared_use="unstated", pin=pin))
        assert outcome.built is True, outcome.detail
        assert fetched[-1] == (
            name,
            f"https://storage.googleapis.com/gcp-public-data--gnomad/release/{pin}/constraint/{name}",
        )
        assert release_label(out) == f"gnomad_v{pin}_constraint"


def test_with_no_pin_the_lane_builds_4_1_2() -> None:
    assert constraint_build.DEFAULT_CONSTRAINT_URL.endswith(
        "release/4.1.2/constraint/gnomad.v4.1.2.constraint_metrics.tsv.bgz"
    )


def test_a_source_file_of_another_release_is_refused_rather_than_relabelled(tmp_path: Path) -> None:
    held = tmp_path / "gnomad.v4.1.constraint_metrics.tsv"
    shutil.copy(_SLICE, held)
    outcome = _rebuild_constraint(
        RebuildRequest(out_dir=tmp_path / "out", declared_use="unstated", pin="4.1.2", source=held)
    )
    assert outcome.built is False
    assert "is gnomAD 4.1, the build is for 4.1.2" in outcome.detail


def test_a_bgzipped_file_builds_the_same_snapshot_as_the_plain_one(tmp_path: Path) -> None:
    """4.1.1 onward ship only `.tsv.bgz`; the reader tells the two apart by the bytes, not the name."""
    packed = tmp_path / "gnomad_v4.1_constraint_slice.tsv.bgz"
    with gzip.open(packed, "wb") as handle:
        handle.write(_SLICE.read_bytes())
    plain = constraint_build.build_snapshot(_SLICE, tmp_path / "plain")
    zipped = constraint_build.build_snapshot(packed, tmp_path / "zipped")
    assert plain.parquet_file.read_bytes() == zipped.parquet_file.read_bytes()
    assert release_label(tmp_path / "zipped") == "gnomad_v4.1_constraint"


def test_a_re_run_over_4_1_rows_against_a_4_1_2_snapshot_changes_nothing(tmp_path: Path) -> None:
    """The pm's sizing of RM410: counting only the current label as done appended a 4.1.2 row beside each
    4.1 one, two pLI values per gene. Any release of the snapshot lane is the pass's own."""
    old = tmp_path / "gnomad.v4.1.constraint_metrics.tsv"
    shutil.copy(_SLICE, old)
    constraint_build.build_snapshot(old, tmp_path / "v4.1")
    new = tmp_path / "gnomad.v4.1.2.constraint_metrics.tsv.bgz"
    with gzip.open(new, "wb") as handle:
        handle.write(_SLICE.read_bytes())
    constraint_build.build_snapshot(new, tmp_path / "v4.1.2")

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion,gene\nrs1,A/G,risk,x,BRCA1\n")
    enrich_gene_metrics(spec, offline=True, constraint_cache=tmp_path / "v4.1")
    before = (spec / "gene_metrics.csv").read_bytes()
    assert b"gnomad_v4.1_constraint" in before

    result = enrich_gene_metrics(spec, offline=True, constraint_cache=tmp_path / "v4.1.2")

    assert [(r.gene, r.dataset) for r in result.rows] == [("BRCA1", "gnomad_v4.1_constraint")]
    assert (spec / "gene_metrics.csv").read_bytes() == before


@pytest.mark.parametrize("lane", sorted(caches._PINNABLE))
def test_the_dry_run_shows_a_pin_only_where_the_build_takes_it(
    lane: str, tmp_path: Path, no_ambient_caches
) -> None:
    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(tmp_path), "--only", lane, "--pin", f"{lane}=X1", "--dry-run"]
    )
    assert "would build X1" in result.output or "not run" in result.output or "skipped" in result.output, (
        result.output
    )
