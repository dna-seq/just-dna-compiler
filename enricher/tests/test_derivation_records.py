"""Release facts for re-deriving the enricher's tables, independently of a recompile."""

import tomllib
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from runpy import run_path

import pytest
from just_dna_compiler.hints import DERIVED_TABLE_MODELS
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.derivation_records import (
    DERIVATION_RECORDS,
    VALID_ENRICHER_DERIVATION_CAUSES,
    DerivationChange,
    needs_rederive,
    newest_rederive_release,
    rederive_reasons,
)
from just_dna_format.identity import parse_version
from just_dna_format.layout import sidecar_key
from just_dna_format.release_records import RELEASE_RECORDS, needs_recompile
from pydantic import ValidationError

from enricher.tests.test_ensembl_split_release import _cache_with, _manifest, _new_release, _old_release


def test_coverage_matches_tagged_enricher_versions_and_the_installed_version() -> None:
    installed = version("just-dna-enricher")
    assert installed in DERIVATION_RECORDS
    # importlib-mode pytest also runs this tier alone, with schema/tests off its import path.
    history = run_path(str(Path(__file__).resolve().parents[2] / "schema/tests/test_first_seen.py"))
    tags = history["_release_tags"]()
    if not tags:
        pytest.skip("the complete release tags are unavailable")
    expected = {installed}
    earlier = set()
    for tag in tags:
        project = history["_git"]("show", f"{tag}:enricher/pyproject.toml")
        if parse_version(tag[1:]) >= parse_version("0.8.0"):
            assert project is not None, tag
            expected.add(tomllib.loads(project)["project"]["version"])
        elif project is not None:
            earlier.add(tomllib.loads(project)["project"]["version"])
    assert set(DERIVATION_RECORDS) == expected
    assert set(rederive_reasons("0.0.0", "0.8.0").unknown_releases) == earlier


def test_split_snapshot_labels_come_from_the_lanes_and_only_drive_rederivation(tmp_path: Path) -> None:
    new = _new_release()
    lane = LANES_BY_NAME["ensembl"]
    changes = rederive_reasons("just-dna-enricher 0.7.3", "0.8.0", "resolution.csv")
    ((release, move),) = changes.changes
    assert (release, move.lane, move.cause) == ("0.8.0", lane.name, "lane_moved")
    assert set(move.items) == {"RM267", "RM372"}
    assert move.old_release == lane.release_label(_cache_with(tmp_path / "old", _old_release(), None))
    assert move.new_release == lane.release_label(_cache_with(tmp_path / "new", new, _manifest(new)))
    assert changes.unknown_releases == ()
    assert needs_rederive("0.7.0", "0.8.0", "resolution.csv") is True
    assert needs_rederive("0.7.3", "0.8.0", "resolution.csv") is True

    compiled = needs_recompile("0.7.0", "0.8.0")
    cut = RELEASE_RECORDS["0.8.0"]
    earlier = needs_recompile("0.7.0", cut.previous)
    assert compiled.declared == (*cut.declared, *earlier.declared)
    for axis, value in cut.axes.items():
        pair = (value, earlier.axes[axis])
        expected = True if True in pair else None if None in pair else False
        assert compiled.axes[axis] is expected
    assert all(change.target != move.table for change in compiled.declared)


def test_rsid_correction_and_kept_table() -> None:
    assert needs_rederive("0.8.4", "0.8.5", "resolution.csv") is True
    ((release, fix),) = rederive_reasons("0.8.4", "0.8.5", "resolution.csv").changes
    assert (release, fix.cause, fix.items, fix.table) == (
        "0.8.5",
        "derivation_corrected",
        ("RM438",),
        "resolution.csv",
    )
    # RM432: offline over an unreadable constraint snapshot, 0.8.4 wrote `not_found` gene rows; 0.8.5 writes none.
    assert {(change.table, change.items) for _, change in rederive_reasons("0.8.4", "0.8.5", "gene_metrics.csv").changes} == {
        ("gene_metrics.csv", ("RM432",))
    }
    assert needs_rederive("0.8.9", "0.8.10") is False
    assert needs_rederive("0.8.5", "0.8.6") is False
    assert needs_rederive("0.8.5", "0.8.7", "resolution.csv") is False
    assert needs_rederive("0.8.6", "0.8.7", "licensing.csv") is True
    assert rederive_reasons("0.8.6", "0.8.7", "licensing.csv") == rederive_reasons(
        "0.8.6", "0.8.7", "sources.csv"
    )


def test_unknown_and_matching_changes_are_both_reported_in_release_order() -> None:
    answer = rederive_reasons("0.8.2", "0.8.9", "resolution.csv")
    assert [(release, change.items) for release, change in answer.changes] == [
        ("0.8.5", ("RM438",)),
        ("0.8.9", ("RM448",)),
    ]
    assert answer.unknown_releases == ("0.8.3", "0.8.8")
    assert needs_rederive("0.8.2", "0.8.9", "resolution.csv") is True
    assert needs_rederive("0.8.2", "0.8.4", "resolution.csv") is None
    assert needs_rederive("0.8.7", "0.8.8") is None
    assert needs_rederive("0.8.7", "0.8.8", "frequencies.csv") is None


def test_uncovered_ends_and_empty_span() -> None:
    assert needs_rederive("0.7.1", "0.7.3") is None
    assert rederive_reasons("0.7.1", "0.8.0").unknown_releases == ("0.7.2", "0.7.3")
    assert needs_rederive("0.7.1", "0.8.0", "frequencies.csv") is None
    assert needs_rederive("0.7.3", "0.8.0", "frequencies.csv") is False
    future = "99.0.0"
    assert needs_rederive(future, future) is False
    assert needs_rederive("0.9.0", future) is None
    assert future in rederive_reasons("0.8.4", future).unknown_releases
    assert needs_rederive("0.8.4", future, "resolution.csv") is True


@pytest.mark.parametrize("reader", [needs_rederive, rederive_reasons])
def test_invalid_span_or_table_refuses(reader: Callable[..., object]) -> None:
    with pytest.raises(ValueError):
        reader("0.8.10", "0.8.9")
    with pytest.raises(ValueError, match="0.8.x"):
        reader("0.8.x", "0.9.0")
    with pytest.raises(ValueError, match="variants.csv"):
        reader("0.8.9", "0.8.10", "variants.csv")


def test_newest_is_the_last_possible_change_for_every_table(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in DERIVED_TABLE_MODELS:
        table = sidecar_key(name)
        possible = [
            v
            for v, changes in DERIVATION_RECORDS.items()
            if changes is None or any(c.table == table for c in changes)
        ]
        assert newest_rederive_release(name) == max(possible, key=parse_version, default=None)
    monkeypatch.setitem(DERIVATION_RECORDS, "0.8.10", None)
    assert newest_rederive_release("resolution.csv") == "0.8.10"
    monkeypatch.setattr("just_dna_enricher.derivation_records.DERIVATION_RECORDS", {"0.8.0": ()})
    assert newest_rederive_release("resolution.csv") is None
    with pytest.raises(ValueError, match="variants.csv"):
        newest_rederive_release("variants.csv")


def test_model_covers_the_writers_round_trips_and_is_frozen() -> None:
    assert VALID_ENRICHER_DERIVATION_CAUSES == {"lane_moved", "derivation_corrected"}
    for name in DERIVED_TABLE_MODELS:
        change = DerivationChange(table=name, cause="derivation_corrected", items=("RM438",))
        assert change.table == sidecar_key(name)
        assert DerivationChange.model_validate_json(change.model_dump_json()) == change
        with pytest.raises(ValidationError):
            change.table = name


@pytest.mark.parametrize(
    "fields",
    [
        {"cause": "lane_moved", "lane": "ensembl"},
        {"cause": "lane_moved", "new_release": "GRCh38"},
        {"cause": "lane_moved", "lane": "unknown", "new_release": "GRCh38"},
        {"cause": "lane_moved", "lane": "ensembl", "new_release": "  "},
        {"old_release": "GRCh38"},
        {"new_release": "GRCh38"},
        {"lane": "ensembl"},
        {"cause": "correction"},
        {"table": "variants.csv"},
        {"items": ()},
        {"items": ("S156",)},
    ],
)
def test_model_refuses_invalid_change(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DerivationChange.model_validate(
            {"table": "resolution.csv", "cause": "derivation_corrected", "items": ("RM438",), **fields}
        )


@pytest.mark.parametrize(
    ("previous", "release", "table", "items"),
    [
        ("0.8.0", "0.8.1", "resolution.csv", {"RM398", "RM400"}),
        ("0.8.0", "0.8.1", "sources.csv", {"RM398"}),
        ("0.8.1", "0.8.2", "gene_metrics.csv", {"RM410", "RM417"}),
        ("0.8.3", "0.8.4", "gwas_effects.csv", {"RM428"}),
        ("0.8.6", "0.8.7", "sources.csv", {"RM442"}),
        ("0.8.8", "0.8.9", "resolution.csv", {"RM448"}),
        ("0.8.10", "0.9.0", "gene_metrics.csv", {"RM454"}),
    ],
)
def test_release_names_the_items_that_changed_the_table(
    previous: str, release: str, table: str, items: set[str]
) -> None:
    reasons = rederive_reasons(previous, release, table)
    assert {item for _, change in reasons.changes for item in change.items} == items
    assert reasons.unknown_releases == ()
