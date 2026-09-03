"""The derived MITOMAP-miss lane, its parent guard and its staleness pin — RM171.

**Every assertion here is a relationship, and that is the entry's central rule rather than a style
preference.** "16" was a fact about one join against one ClinVar vintage; a test that pinned it would
have to be edited every time either parent moved, and would be silently wrong in between. So: a miss
key is *absent from the parent*, a photocopy key is *present*, a rated miss's `clin_sig` is *the
normalizer's image of its bracket*, and the four buckets *partition* the source rows. All four stay
true when both parents are rebuilt.

Both parents are synthesised here — a small ClinVar chrMT snapshot cut through `clinvar_build`'s own
VCF path, and the MITOMAP corpus `conftest.py` holds — so the join runs against the real code and
against neither the 63 MB dump nor the 200 MB VCF.
"""

import dataclasses
import gzip
import json
import shutil
from pathlib import Path

import pytest
from just_dna_enricher import caches, clinvar_build
from just_dna_enricher.caches import (
    CACHE_LANES,
    LANES_BY_NAME,
    RebuildRequest,
    lane_name,
    rebuild_lane,
)
from just_dna_enricher.clin_sig import normalize_clin_sig
from just_dna_enricher.mitomap import MITOMAP_VCEP_CLASSES, MitomapError, parse_status
from just_dna_enricher.mitomap_build import build_snapshot
from just_dna_enricher.mitomap_miss_build import (
    BUCKETS,
    MISS_PARQUET,
    build_miss_snapshot,
    parent_pin,
    stale_parents,
)

pl = pytest.importorskip("polars")


# ── the two parents ─────────────────────────────────────────────────────────────────────────────
#
# ClinVar's chrMT rows are chosen against the MITOMAP fixture to exercise all four buckets and the
# one trap: 8993 T>C is a *different allele at the same position* as MITOMAP's 8993 T>G, so a
# position-level join would report a photocopy where the exact one correctly reports a miss.

_CLINVAR_VCF = """##fileformat=VCFv4.1
##fileDate=2026-06-27
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
MT\t3460\t9999\tG\tA\t.\t.\tALLELEID=1;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel;GENEINFO=MT-ND1:4535
MT\t114\t9998\tC\tT\t.\t.\tALLELEID=2;CLNSIG=Benign;CLNREVSTAT=criteria_provided,_single_submitter
MT\t8993\t9997\tT\tC\t.\t.\tALLELEID=3;CLNSIG=Uncertain_significance;CLNREVSTAT=criteria_provided,_single_submitter
MT\t3243\t9996\tA\tG\t.\t.\tALLELEID=4;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
MT\t1555\t9995\tA\tG\t.\t.\tALLELEID=5;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
"""


def _write_clinvar(tmp_path: Path, vcf_text: str = _CLINVAR_VCF) -> Path:
    """A real ClinVar snapshot, built through the real builder from a five-record chrMT VCF."""
    vcf = tmp_path / "clinvar.vcf.gz"
    # The VCF columns above are written CHROM POS ID REF ALT ... with a placeholder ID, which is the
    # shape `_iter_records` reads; the fields are tab-separated exactly as ClinVar's are.
    with gzip.open(vcf, "wt", encoding="utf-8") as handle:
        handle.write(vcf_text)
    clinvar_build.build_snapshot(vcf, tmp_path / "clinvar")
    return tmp_path / "clinvar"


@pytest.fixture
def parents(tmp_path: Path, mitomap_dump: Path):
    """`(mitomap_dir, clinvar_dir)` — both parents built through their own builders."""
    build_snapshot(
        mitomap_dump, tmp_path / "mitomap", source_last_modified="Mon, 24 Aug 2026 05:01:10 GMT"
    )
    return tmp_path / "mitomap", _write_clinvar(tmp_path)


# ── the join ────────────────────────────────────────────────────────────────────────────────────


def test_a_miss_key_is_absent_from_the_parent_and_a_photocopy_key_is_present(
    parents, tmp_path: Path
) -> None:
    """The two assertions the whole lane rests on, checked against the parent rather than a list."""
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    clinvar = pl.read_parquet(clinvar_dir / "data" / "clinvar-chrMT.parquet")
    keys = set(zip(clinvar["start"], clinvar["ref"], clinvar["alt"], strict=True))

    for row in frame.iter_rows(named=True):
        key = (row["start"], row["ref"], row["alt"])
        if row["bucket"] == "photocopy":
            assert key in keys, f"{key} is a photocopy and the parent does not carry it"
            assert row["clinvar_variation_id"], "and it names the record it is a copy of"
        elif row["bucket"] in ("rated_miss", "unrated_miss"):
            assert key not in keys, f"{key} is a miss and the parent carries it"
        else:
            assert row["bucket"] == "unmintable"
            assert row["key_shape"] is None, "a row with no key has no key shape either"


def test_a_different_allele_at_the_same_position_is_a_miss_not_a_photocopy(
    parents, tmp_path: Path
) -> None:
    """No position-level fallback: collapsing onto one would hide a real increment or invent one.

    The fixture's 8993 is the case — MITOMAP publishes `T>G` there and this ClinVar publishes `T>C`.
    """
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    row = frame.filter((pl.col("start") == 8993) & (pl.col("alt") == "G")).to_dicts()[0]
    assert row["bucket"] != "photocopy"
    assert row["clinvar_variation_id"] is None
    clinvar = pl.read_parquet(clinvar_dir / "data" / "clinvar-chrMT.parquet")
    assert 8993 in clinvar["start"].to_list(), "the position IS in the parent, which is the point"


def test_every_source_row_lands_in_exactly_one_bucket(parents, tmp_path: Path) -> None:
    """A partition, asserted rather than trusted to the branches that produce it."""
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    assert set(result.buckets) == set(BUCKETS)
    assert result.accounts_for_every_row(frame.height)
    assert dict(sorted(frame["bucket"].value_counts().iter_rows())) == {
        name: count for name, count in sorted(result.buckets.items()) if count
    }


def test_a_rated_miss_carries_the_normalizers_image_of_a_documented_bracket(
    parents, tmp_path: Path
) -> None:
    """§8's assertion, over whatever the join produced rather than over a named row."""
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    rated = frame.filter(pl.col("bucket") == "rated_miss")
    assert rated.height, "the fixture has to produce one for this assertion to mean anything"
    for row in rated.iter_rows(named=True):
        assert row["status_bracket"] in MITOMAP_VCEP_CLASSES
        assert row["clin_sig"] == normalize_clin_sig(row["status_bracket"])
        assert parse_status(row["status"]).bracket == row["status_bracket"]


def test_an_undocumented_bracket_and_a_bare_confirmation_token_are_both_unrated(
    parents, tmp_path: Path
) -> None:
    """`[VUS*]` never produces a `clin_sig`, and neither does `Cfrm` on its own.

    The two halves are here together because they are the same refusal reaching the miss set by two
    routes, and the counting half is what keeps a rated-miss figure from silently including them.
    """
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    assert frame.filter(
        pl.col("withheld_bracket").is_not_null() & pl.col("clin_sig").is_not_null()
    ).is_empty()
    tokens = frame.filter(
        pl.col("status_bracket").is_null() & pl.col("status_confirmation").is_not_null()
    )
    assert tokens.height, "the fixture carries bare confirmation tokens"
    assert tokens.filter(pl.col("clin_sig").is_not_null()).is_empty()
    withheld_and_missing = frame.filter(
        (pl.col("bucket") == "unrated_miss") & pl.col("withheld_bracket").is_not_null()
    )
    assert result.withheld_in_miss == dict(
        sorted(withheld_and_missing["withheld_bracket"].value_counts().iter_rows())
    )


def test_the_colon_deletions_are_unmintable_rather_than_missing(parents, tmp_path: Path) -> None:
    """They are not misses and not photocopies: the join has no key to ask the question with."""
    mitomap_dir, clinvar_dir = parents
    result = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    frame = pl.read_parquet(result.parquet_file)
    deletions = frame.filter(pl.col("allele_defect") == "right_anchored_deletion")
    assert deletions.height, "the fixture carries one"
    assert set(deletions["bucket"].to_list()) == {"unmintable"}
    assert result.unmintable["right_anchored_deletion"] == deletions.height


def test_a_rebuild_from_the_same_parents_is_byte_identical(parents, tmp_path: Path) -> None:
    """Principle 7, over a derived artifact: the same two parents give the same bytes."""
    mitomap_dir, clinvar_dir = parents
    first = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "a")
    second = build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "b")
    assert first.parquet_file.read_bytes() == second.parquet_file.read_bytes()


def test_an_absent_clinvar_parent_is_refused_rather_than_making_everything_a_miss(
    parents, tmp_path: Path
) -> None:
    """The most confident wrong answer this lane could produce, refused where it would be produced."""
    mitomap_dir, _ = parents
    empty = tmp_path / "no-clinvar"
    (empty / "data").mkdir(parents=True)
    with pytest.raises(MitomapError, match="clinvar-chrMT.parquet"):
        build_miss_snapshot(mitomap_dir, empty, tmp_path / "miss")


# ── the parent pin ──────────────────────────────────────────────────────────────────────────────


def test_the_release_json_pins_both_parents(parents, tmp_path: Path) -> None:
    mitomap_dir, clinvar_dir = parents
    build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    release = json.loads((tmp_path / "miss" / "release.json").read_text())
    assert set(release["parents"]) == {"mitomap", "clinvar"}
    assert release["parents"]["mitomap"]["dataset"] == "mitomap_2026-08-24"
    assert release["parents"]["clinvar"]["clinvar_file_date"] == "2026-06-27"
    for name, directory in (("mitomap", mitomap_dir), ("clinvar", clinvar_dir)):
        recorded = {k: v for k, v in release["parents"][name].items() if k != "path"}
        assert recorded == parent_pin(directory)


def test_a_parent_that_moved_makes_the_child_stale_and_the_child_says_which(
    parents, tmp_path: Path
) -> None:
    """A ClinVar rebuild without a child rebuild is detectable, which is what the pin is for."""
    mitomap_dir, clinvar_dir = parents
    build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    assert stale_parents(tmp_path / "miss") == {}

    # ClinVar rebuilt from a newer file: same directory, a different release.
    _write_clinvar(
        tmp_path,
        _CLINVAR_VCF.replace("##fileDate=2026-06-27", "##fileDate=2026-09-01")
        + "MT\t8618\t9994\tT\tTT\t.\t.\tALLELEID=6;CLNSIG=Likely_pathogenic\n",
    )
    moved = stale_parents(tmp_path / "miss")
    assert set(moved) == {"clinvar"}, "and MITOMAP, which did not move, is not named"
    pinned, current = moved["clinvar"]
    assert pinned["clinvar_file_date"] == "2026-06-27"
    assert current["clinvar_file_date"] == "2026-09-01"


def test_a_parent_that_is_gone_is_not_reported_as_a_parent_that_moved(
    parents, tmp_path: Path
) -> None:
    """Two different instructions — rebuild the child, or provision the parent — stay apart."""
    mitomap_dir, clinvar_dir = parents
    build_miss_snapshot(mitomap_dir, clinvar_dir, tmp_path / "miss")
    shutil.rmtree(clinvar_dir)
    assert stale_parents(tmp_path / "miss") == {}


def _unresolvable(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Make one lane resolve to nothing, as it does on a machine that never provisioned it.

    `dataclasses.replace` rather than `setattr`: `CacheLane` is frozen, which is the point of it —
    the registry is not something a caller mutates — so the substitution goes into the lookup the
    guard reads.
    """
    lane = dataclasses.replace(LANES_BY_NAME[name], resolve=lambda *args, **kwargs: None)
    monkeypatch.setitem(caches.LANES_BY_NAME, name, lane)


# ── the registry ────────────────────────────────────────────────────────────────────────────────


def test_a_derived_lane_with_an_absent_parent_could_not_run_rather_than_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`built=None`, naming the parent — never `False`, and never an empty increment.

    `False` would file another lane's absence as this lane breaking, and an empty miss would be the
    strongest possible claim (MITOMAP publishes nothing new) derived from a comparison that never
    ran. Both are wrong in a way nothing downstream could notice.
    """
    _unresolvable(monkeypatch, "mitomap")
    _unresolvable(monkeypatch, "clinvar")
    lane = LANES_BY_NAME["mitomap_miss"]
    outcome = rebuild_lane(lane, RebuildRequest(out_dir=tmp_path / "out"))
    assert outcome.built is None
    assert outcome.label == "not run"
    assert "mitomap" in outcome.detail and "clinvar" in outcome.detail
    assert not (tmp_path / "out").exists(), "and nothing was written"


def test_the_guard_names_only_the_parent_that_is_missing(
    parents, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per parent, not per lane: an operator holding one of two needs to be told which is which."""
    mitomap_dir, _ = parents
    _unresolvable(monkeypatch, "clinvar")
    lane = LANES_BY_NAME["mitomap_miss"]
    outcome = rebuild_lane(
        lane, RebuildRequest(out_dir=tmp_path / "out", parents={"mitomap": mitomap_dir})
    )
    assert outcome.built is None
    assert "clinvar build" in outcome.detail
    assert "mitomap build" not in outcome.detail


def test_the_adapter_runs_once_both_parents_are_supplied(parents, tmp_path: Path) -> None:
    mitomap_dir, clinvar_dir = parents
    outcome = rebuild_lane(
        LANES_BY_NAME["mitomap_miss"],
        RebuildRequest(
            out_dir=tmp_path / "out", parents={"mitomap": mitomap_dir, "clinvar": clinvar_dir},
        ),
    )
    assert outcome.built is True, outcome.detail
    assert (tmp_path / "out" / "data" / MISS_PARQUET).is_file()
    assert "photocopy" in outcome.detail


def test_every_parent_precedes_its_child_in_the_registry() -> None:
    """`cache prepare` walks `CACHE_LANES` top to bottom, so the order is load-bearing.

    A child listed before a parent would be provisioned from caches that arrive a moment later, and
    the run would report a lane that could not run on the one pass that was meant to fix it.
    """
    order = {lane.name: index for index, lane in enumerate(CACHE_LANES)}
    for lane in CACHE_LANES:
        for parent in lane.parents:
            assert parent in order, f"{lane.name} names a parent the registry does not have"
            assert order[parent] < order[lane.name], f"{parent} must come before {lane.name}"


def test_a_lane_name_may_be_written_with_a_hyphen_and_comes_back_declared() -> None:
    """A closed vocabulary accepts `-` for `_` and **returns the declared member**.

    Both halves matter: a caller that merely calls a normalizer and keeps its own spelling has done
    nothing, which is the slip this rule exists for.
    """
    assert lane_name("mitomap-miss") == "mitomap_miss"
    assert lane_name("MITOMAP-MISS") == "mitomap_miss"
    assert lane_name("drug-labels") == "drug_labels"
    assert lane_name("clinvar") == "clinvar"
    assert lane_name("nosuch") is None
    assert lane_name("mitomap_miss") in LANES_BY_NAME
