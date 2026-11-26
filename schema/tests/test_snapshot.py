"""The reference-snapshot contract (RM303): the layout names, `SnapshotRelease`, `read_release`.

`release.json` had six parties and no model, and its keys drifted: `rows` beside `row_count`,
`licence` beside `license`, and a ClinVar builder that wrote no `dataset` at all, which reached
`cache status` as a blank label. These tests pin the three rules the model exists for:

- **Old spellings are read, never written.** A published snapshot keeps its old keys; the model reads
  them into the canonical field, and anything written through the model carries the canonical one only.
- **Unstated is `None`, never a default.** A key the file does not carry stays `None`, and a key the
  builder recorded as `null` (an unknown it chose to state) survives a write.
- **Absent and unreadable are both `None`** from `read_release`, as they were when it returned a dict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from just_dna_format.snapshot import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_ROOT_FILENAMES,
    SnapshotRelease,
    begin_block_write,
    begin_snapshot_write,
    clinvar_release_label,
    holds_snapshot_payload,
    is_whole_build,
    parse_release,
    read_release,
    release_is_unreadable,
    release_label,
    write_release,
)


def _release_file(directory: Path, payload: object) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / RELEASE_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    return directory


def test_absent_and_unreadable_are_both_none(tmp_path: Path) -> None:
    assert read_release(tmp_path / "nowhere") is None
    assert read_release(tmp_path) is None
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / RELEASE_FILENAME).write_text('{"dataset": ', encoding="utf-8")
    assert read_release(broken) is None
    assert read_release(_release_file(tmp_path / "list", ["dataset"])) is None

    # A typed key holding the wrong kind of value costs that key, never the record: the label survives,
    # and the record is reported as not read whole, so a merging writer leaves it alone.
    mistyped = _release_file(
        tmp_path / "mistyped", {"dataset": "civic_01-Sep-2026", "parents": {"x": "not-a-block"}, "licence": 7}
    )
    partial = read_release(mistyped)
    assert partial is not None
    assert (partial.dataset, partial.parents, partial.license) == ("civic_01-Sep-2026", None, None)
    assert release_is_unreadable(mistyped) is True


def test_an_unstated_key_is_none_and_never_a_default(tmp_path: Path) -> None:
    release = read_release(_release_file(tmp_path / "bare", {"built_at": "2026-11-04T00:00:00Z"}))
    assert release is not None
    unset = set(SnapshotRelease.model_fields) - {"built_at"}
    assert {name: getattr(release, name) for name in unset} == dict.fromkeys(unset)
    # …and an empty file is a readable statement that says nothing, which is not the same as absent.
    empty = read_release(_release_file(tmp_path / "empty", {}))
    assert empty is not None
    assert empty.dataset is None


@pytest.mark.parametrize(
    ("old", "canonical", "value"),
    [
        ("rows", "row_count", 33_500_000),
        ("rows", "row_counts", {"mitomap_mutations_coding_control.parquet": 2118}),
        ("licence", "license", "CC0-1.0"),
    ],
)
def test_an_old_spelling_reads_into_the_canonical_field_and_is_never_written(
    tmp_path: Path, old: str, canonical: str, value: object
) -> None:
    release = read_release(_release_file(tmp_path / "old", {old: value, "dataset": "x_1"}))
    assert release is not None
    assert getattr(release, canonical) == value
    assert old not in (release.model_extra or {})

    out = tmp_path / "rewritten"
    out.mkdir()
    written = json.loads(write_release(out, release).read_text(encoding="utf-8"))
    assert written == {canonical: value, "dataset": "x_1"}


def test_the_canonical_spelling_wins_when_a_file_states_both(tmp_path: Path) -> None:
    release = read_release(_release_file(tmp_path / "both", {"license": "MIT", "licence": "CC0-1.0"}))
    assert release is not None
    assert release.license == "MIT"
    assert "licence" not in (release.model_extra or {})


def test_lane_specific_keys_ride_in_extra_and_survive_a_rewrite(tmp_path: Path) -> None:
    """`builder` is acmg's module path, not a version, so it is no alias of `builder_version`."""
    stated = {
        "builder": "just_dna_enricher.acmg_build",
        "doi": "10.1016/j.gim.2025.101454",
        "gene_count": 84,
        "sf_version": "3.3",
        "notice": {"nested": [1, 2]},
    }
    release = read_release(_release_file(tmp_path / "acmg", stated))
    assert release is not None
    assert release.builder_version is None
    assert release.sf_version == "3.3"
    assert release.model_extra == {k: v for k, v in stated.items() if k != "sf_version"}
    out = tmp_path / "out"
    out.mkdir()
    assert json.loads(write_release(out, release).read_text(encoding="utf-8")) == stated


def test_a_stated_null_survives_a_write_and_an_unstated_key_is_not_invented(tmp_path: Path) -> None:
    """`exclude_unset`: pubmind records `source_url: null` on a local build, and that null is a claim."""
    release = SnapshotRelease(dataset="pubmind_ca224ebf5ef3", source_url=None, input_rows=909_224)
    written = json.loads(write_release(tmp_path, release).read_text(encoding="utf-8"))
    assert written == {"dataset": "pubmind_ca224ebf5ef3", "source_url": None, "input_rows": 909_224}


def test_write_release_is_sorted_and_newline_terminated(tmp_path: Path) -> None:
    text = write_release(tmp_path, SnapshotRelease(dataset="b", built_at="a", zeta=1)).read_text()
    assert text.endswith("}\n")
    assert list(json.loads(text)) == sorted(json.loads(text))


class TestClinVarLabel:
    """ClinVar wrote `clinvar_file_date` and no `dataset`; the date is the old spelling of its label."""

    def test_the_label_formula(self) -> None:
        assert clinvar_release_label("2026-06-27", "sha256:ab") == "clinvar_2026-06-27"
        assert clinvar_release_label(" ", "sha256:ab12") == "clinvar_sha256:ab12"
        assert clinvar_release_label(None, "ab12") == "clinvar_sha256:ab12"
        assert clinvar_release_label(None, None) is None
        assert clinvar_release_label("", "") is None

    def test_an_old_clinvar_release_reads_its_label(self, tmp_path: Path) -> None:
        old = {"clinvar_file_date": "2026-06-27", "source_sha256": "20f5", "record_count": 4431781}
        release = read_release(_release_file(tmp_path / "dated", old))
        assert release is not None
        assert release.dataset == clinvar_release_label("2026-06-27", "20f5")
        undated = read_release(_release_file(tmp_path / "undated", {**old, "clinvar_file_date": None}))
        assert undated is not None
        assert undated.dataset == "clinvar_sha256:20f5"

    def test_nothing_else_is_given_a_clinvar_label(self, tmp_path: Path) -> None:
        """Keyed on the key ClinVar alone writes — a bare digest is no evidence of ClinVar."""
        release = read_release(_release_file(tmp_path / "other", {"source_sha256": "20f5"}))
        assert release is not None
        assert release.dataset is None

    def test_a_stated_dataset_is_never_rederived(self, tmp_path: Path) -> None:
        stated = {"clinvar_file_date": "2026-06-27", "dataset": None, "source_sha256": "20f5"}
        release = read_release(_release_file(tmp_path / "stated", stated))
        assert release is not None
        assert release.dataset is None


def test_the_payload_predicate_reads_the_payload_not_the_directory(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert holds_snapshot_payload(empty) is False
    assert holds_snapshot_payload(tmp_path / "missing") is False

    only_release = _release_file(tmp_path / "described", {"dataset": "x"})
    assert holds_snapshot_payload(only_release) is False

    data = tmp_path / "parquet" / SNAPSHOT_DATA_DIRNAME
    data.mkdir(parents=True)
    (data / "chr1.parquet").write_bytes(b"PAR1PAR1")
    assert holds_snapshot_payload(tmp_path / "parquet") is True

    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "one.parquet").write_bytes(b"PAR1PAR1")
    assert holds_snapshot_payload(bare) is True

    named = _release_file(tmp_path / "named", {})
    assert holds_snapshot_payload(named, payload_filename="acmg_sf.csv") is False
    (named / "acmg_sf.csv").write_text("gene\n", encoding="utf-8")
    assert holds_snapshot_payload(named, payload_filename="acmg_sf.csv") is True


def test_the_description_is_the_last_root_file() -> None:
    """RM199: `release.json` must never arrive before the bytes it describes."""
    assert SNAPSHOT_ROOT_FILENAMES[-1] == RELEASE_FILENAME


def test_the_release_label_is_the_stated_dataset_or_none(tmp_path: Path) -> None:
    assert (
        release_label(_release_file(tmp_path / "stated", {"dataset": " mane_grch38_v1.5 "}))
        == "mane_grch38_v1.5"
    )
    assert release_label(_release_file(tmp_path / "blank", {"dataset": "  "})) is None
    assert release_label(_release_file(tmp_path / "null", {"dataset": None})) is None
    assert release_label(_release_file(tmp_path / "unstated", {"built_at": "x"})) is None
    assert release_label(tmp_path / "absent") is None
    old_clinvar = _release_file(tmp_path / "clinvar", {"clinvar_file_date": "2026-06-27"})
    assert release_label(old_clinvar) == "clinvar_2026-06-27"


def test_a_snapshot_built_from_several_inputs_states_its_provenance_per_input(tmp_path: Path) -> None:
    """MANE's shape, found by reading the real snapshot: one URL and one digest per downloaded file."""
    stated = {
        "source_url": {"summary": "https://ftp.ncbi.nlm.nih.gov/x.summary.txt.gz", "changed": None},
        "source_sha256": {"summary": "d10a", "README_versions.txt": "2c9c"},
        "rows": {"summary": 19437, "changed": 120},
    }
    release = read_release(_release_file(tmp_path / "mane", stated))
    assert release is not None
    assert release.source_url == stated["source_url"]
    assert release.source_sha256 == stated["source_sha256"]
    assert release.row_counts == stated["rows"]


def test_unreadable_is_told_apart_from_absent(tmp_path: Path) -> None:
    assert release_is_unreadable(tmp_path / "absent") is False
    assert release_is_unreadable(_release_file(tmp_path / "fine", {"dataset": "x"})) is False
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / RELEASE_FILENAME).write_text("{not json", encoding="utf-8")
    assert release_is_unreadable(broken) is True


# ── RM369: the keys a reader acts on are typed ───────────────────────────────────────────────────


def test_the_keys_a_reader_acts_on_are_typed_and_an_old_value_reads_through_the_type(tmp_path: Path) -> None:
    """Open Targets' part counts and ClinVar-GKM's release and VRS version were extras, read untyped.

    A count spelled as a numeric string reads as the number (pydantic's lax mode, the same rule every
    typed key already had); a value of the wrong kind costs that key and never the record.
    """
    stated = {
        "dataset": "opentargets_26.09",
        "parts_read": {"variant": "3"},
        "parts_total": {"variant": 7},
        "source_release": "2026-10-20",
        "vrs_version": "2.0",
    }
    release = read_release(_release_file(tmp_path / "typed", stated))
    assert release is not None
    assert release.parts_read == {"variant": 3}
    assert release.parts_total == {"variant": 7}
    assert release.source_release == "2026-10-20"
    assert release.vrs_version == "2.0"
    assert not (set(stated) & set(release.model_extra or {}))

    wrong = {"dataset": "clinvar_gkm_2026-10-20", "vrs_version": 2, "parts_total": "seven"}
    directory = _release_file(tmp_path / "wrong", wrong)
    release = read_release(directory)
    assert release is not None
    assert release.dataset == "clinvar_gkm_2026-10-20"
    assert release.vrs_version is None
    assert release.parts_total is None
    assert release_is_unreadable(directory) is True


# ── RM369: a build withdraws the description before the bytes move, and describes them last ───────


def test_a_snapshot_write_withdraws_the_record_first_and_describes_last(tmp_path: Path) -> None:
    directory = _release_file(tmp_path / "snap", {"dataset": "old"})
    write = begin_snapshot_write(directory)
    assert not (directory / RELEASE_FILENAME).exists()
    path = write.commit(SnapshotRelease(dataset="new"))
    assert path == directory / RELEASE_FILENAME
    assert json.loads(path.read_text(encoding="utf-8")) == {"dataset": "new"}


def test_a_build_that_fails_inside_the_window_leaves_no_description(tmp_path: Path) -> None:
    """Restoring the old record would describe bytes the failed build may have changed; absent is unknown."""
    directory = _release_file(tmp_path / "snap", {"dataset": "old"})
    with pytest.raises(OSError):
        begin_snapshot_write(directory)
        raise OSError("no space left on device")
    assert read_release(directory) is None
    assert release_label(directory) is None


def test_a_snapshot_write_makes_a_new_directory(tmp_path: Path) -> None:
    directory = tmp_path / "fresh" / "snap"
    begin_snapshot_write(directory).commit(SnapshotRelease(dataset="x"))
    assert release_label(directory) == "x"


def test_a_block_write_withdraws_its_own_block_only(tmp_path: Path) -> None:
    """ClinVar's citations half: the records' provenance survives, and the old citations block does not."""
    stated = {"dataset": "clinvar_2026-06-27", "citations": {"row_count": 1}}
    directory = _release_file(tmp_path / "snap", stated)
    write = begin_block_write(directory, "citations")
    during = read_release(directory)
    assert during is not None
    assert during.dataset == "clinvar_2026-06-27"
    assert "citations" not in (during.model_extra or {})
    assert write.commit({"row_count": 2}) is True
    after = json.loads((directory / RELEASE_FILENAME).read_text(encoding="utf-8"))
    assert after == {"dataset": "clinvar_2026-06-27", "citations": {"row_count": 2}}


def test_a_block_write_leaves_an_unreadable_record_alone(tmp_path: Path) -> None:
    directory = tmp_path / "broken"
    directory.mkdir()
    (directory / RELEASE_FILENAME).write_text("{not json", encoding="utf-8")
    write = begin_block_write(directory, "citations")
    assert write.commit({"row_count": 2}) is False
    assert (directory / RELEASE_FILENAME).read_text(encoding="utf-8") == "{not json"


def test_a_block_write_with_no_record_writes_one_with_the_block(tmp_path: Path) -> None:
    """Partial provenance beats none, as the citations build always said."""
    directory = tmp_path / "bare"
    directory.mkdir()
    assert begin_block_write(directory, "citations").commit({"row_count": 2}) is True
    assert json.loads((directory / RELEASE_FILENAME).read_text(encoding="utf-8")) == {
        "citations": {"row_count": 2}
    }


# ── 0.9 (RM430 decision 6): one parser for the record's content, which a remote reader shares ────────

#: Old spellings, a ClinVar date with no `dataset`, a recorded `null` and a key the model does not
#: type: every rule the record's reading applies.
_EVERY_RULE = {
    "licence": "CC0-1.0",
    "rows": 12,
    "clinvar_file_date": "2026-11-01",
    "source_sha256": "sha256:" + "ab" * 32,
    "built_at": None,
    "builder": "just_dna_enricher.clinvar_build",
}

#: The same record stated in the canonical spellings, independently of the parser under test.
_EVERY_RULE_READ = SnapshotRelease(
    license="CC0-1.0",
    row_count=12,
    clinvar_file_date="2026-11-01",
    source_sha256="sha256:" + "ab" * 32,
    built_at=None,
    builder="just_dna_enricher.clinvar_build",
    dataset="clinvar_2026-11-01",
)


@pytest.mark.parametrize("as_bytes", [True, False], ids=["bytes", "str"])
def test_parse_release_reads_the_content_as_read_release_reads_the_file(
    tmp_path: Path, as_bytes: bool
) -> None:
    directory = _release_file(tmp_path / "snap", _EVERY_RULE)
    text = (directory / RELEASE_FILENAME).read_text(encoding="utf-8")
    parsed = parse_release(text.encode("utf-8") if as_bytes else text)
    assert parsed == _EVERY_RULE_READ
    assert read_release(directory) == _EVERY_RULE_READ
    assert parsed.model_fields_set == _EVERY_RULE_READ.model_fields_set


def test_a_record_json_loads_reads_stays_readable(tmp_path: Path) -> None:
    """An unpaired surrogate escape: `json.loads` reads it, pydantic's JSON parser refuses it.

    The record was read with `json.loads` before 0.9, so a file holding one was readable whole; the
    shared parser keeps it so, rather than turning a readable snapshot into an unstated one.
    """
    content = '{"dataset": "x_1", "note": "\\ud800"}'
    assert parse_release(content).dataset == "x_1"
    directory = tmp_path / "snap"
    directory.mkdir()
    (directory / RELEASE_FILENAME).write_text(content, encoding="utf-8")
    assert release_label(directory) == "x_1"
    assert release_is_unreadable(directory) is False


@pytest.mark.parametrize(
    "content",
    [b"{not json", b"", b"\xff", '{"dataset": ', b"[1]", b'"dataset"'],
    ids=["not_json", "empty", "not_utf8", "truncated_text", "a_list", "a_string"],
)
def test_parse_release_answers_none_for_an_unreadable_record_and_warns_naming_the_source(
    content: bytes | str, caplog: pytest.LogCaptureFixture
) -> None:
    """Lenient as `read_release` is (RM430, 2026-11-17): the same bytes give the same answer on every route."""
    with caplog.at_level("WARNING"):
        assert parse_release(content, source="hf://example/release.json") is None
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    assert "Could not read hf://example/release.json (" in caplog.records[0].getMessage()
    assert "treating the release as unstated" in caplog.records[0].getMessage()


def test_parse_release_drops_a_mistyped_key_with_a_warning_as_read_release_does(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A mistyped key costs that key, on the fetched bytes exactly as on the file."""
    directory = _release_file(tmp_path / "snap", {"dataset": "x_1", "row_count": "many", "licence": "MIT"})
    content = (directory / RELEASE_FILENAME).read_bytes()
    with caplog.at_level("WARNING"):
        parsed = parse_release(content)
    assert parsed is not None
    assert (parsed.dataset, parsed.row_count, parsed.license) == ("x_1", None, "MIT")
    assert parsed == read_release(directory)
    assert [r.getMessage() for r in caplog.records][0] == (
        f"{RELEASE_FILENAME}: row_count do not fit the snapshot record; read as unstated."
    )
    assert release_is_unreadable(directory) is True


def test_read_release_warns_with_the_path_through_the_shared_parser(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`read_release` hands its path to `parse_release`, so its warnings still name the file."""
    directory = _release_file(tmp_path / "snap", {"dataset": "x_1", "row_count": "many"})
    with caplog.at_level("WARNING"):
        assert read_release(directory).dataset == "x_1"
    path = directory / RELEASE_FILENAME
    assert (
        caplog.records[0].getMessage()
        == f"{path}: row_count do not fit the snapshot record; read as unstated."
    )


@pytest.mark.parametrize(
    ("read", "total", "expected"),
    [
        ({}, {}, None),
        (None, {"study": 2}, None),
        ({"study": 2}, {"other": 2}, None),
        ({"study": 2}, {"study": 2, "other": 1}, None),
        ({"study": 2}, {"study": 2}, True),
        ({"study": 0}, {"study": 2, "other": 1}, False),
    ],
)
def test_is_whole_build_withholds_unknown_part_counts(read, total, expected) -> None:
    record = SnapshotRelease(parts_read=read, parts_total=total)
    assert is_whole_build(record) is expected
    assert is_whole_build(json.loads(record.to_json())) is expected


def test_is_whole_build_refuses_a_contradictory_record() -> None:
    read = {"study": 2}
    total = {"study": read["study"] - 1}
    with pytest.raises(ValueError) as refused:
        is_whole_build(SnapshotRelease(parts_read=read, parts_total=total))
    assert str(refused.value) == f'parts_read["study"] is {read["study"]}, above parts_total {total["study"]}'


def test_is_whole_build_names_every_short_dataset_in_order() -> None:
    read = {"study": 1, "complete": 2, "l2g": 0, "unknown": 3}
    total = {"study": 2, "l2g": 1, "complete": read["complete"]}
    short = {}
    assert is_whole_build({"parts_read": read, "parts_total": total}, short_reads=short) is False
    assert list(short.items()) == [(name, (read[name], total[name])) for name in ("l2g", "study")]
