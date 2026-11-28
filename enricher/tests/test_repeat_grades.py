"""RM294 goes through the same offline enrich entry point a repeat module uses."""

import csv
import json
from pathlib import Path

import pytest
from just_dna_enricher import repeat_grades as grades_pass
from just_dna_enricher.cli import app
from just_dna_enricher.download import OpenSnapshotError
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.locations import STRCHIVE_CACHE_VAR, STRCHIVE_CATALOGUE_FILENAME
from just_dna_enricher.repeat_grades import RepeatGradeError, enrich_repeat_grades
from just_dna_enricher.strchive_build import build_strchive_snapshot
from just_dna_format.layout import resolve_sidecar
from typer.testing import CliRunner

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "strchive_loci_slice.json"


def _spec(tmp_path: Path, keys: list[tuple[str, str]]) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "repeat_alleles.csv").write_text(
        "gene,repeat_unit,measure_min,measure_max,conclusion\n"
        + "".join(f"{gene},{unit},{i},{i},Repeat count\n" for i, (gene, unit) in enumerate(keys))
    )
    return spec


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("labelled", [True, False])
def test_enrich_preserves_each_association_and_grade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, labelled: bool
) -> None:
    records = json.loads(_SLICE.read_text())
    # Exercise tomorrow's open wording and a source stating no grade, on real multi-record keys.
    arx = [record for record in records if record["gene"] == "ARX"]
    arx[0]["evidence"].append("New STRchive wording")
    arx[1]["evidence"] = []
    bare = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    bare.write_text(json.dumps(records))
    snapshot = (
        build_strchive_snapshot(tmp_path / "lane", catalogue=bare, release="v2.26.0") if labelled else None
    )
    monkeypatch.setenv(STRCHIVE_CACHE_VAR, str(snapshot.out_dir if snapshot else bare))
    keys = [("ARX", "GCN"), ("ARX", "NGC"), ("DMD", "AAG"), ("EP400", "CAG"), ("HTT", "CAA")]
    spec = _spec(tmp_path, keys + [keys[0]])
    progress = []
    result = enrich(spec, offline=True, progress=lambda done, total: progress.append((done, total)))
    grades = result.repeat_grades
    assert set(grades.missing) == {("HTT", "CAA")} and not grades.could_not_ask
    assert progress == [(done, len(keys)) for done in range(len(keys) + 1)]
    expected = {
        (gene, motif, rec["id"], grade, rec["disease"])
        for gene, motif in keys
        for rec in records
        if gene == rec["gene"]
        and motif in rec["pathogenic_motif_reference_orientation"] + rec["pathogenic_motif_gene_orientation"]
        for grade in rec["evidence"] or [""]
    }
    path = spec / "repeat_grades.csv"
    rows = _rows(path)
    assert {
        tuple(row[k] for k in ("gene", "repeat_unit", "locus_id", "grade", "disease")) for row in rows
    } == expected
    assert len(rows) == len(expected)
    assert {"Refuted", "Provisional"} <= {row["grade"] for row in rows}
    dataset = snapshot.dataset if snapshot else ""
    assert {(row["source"], row["dataset"], row["status"]) for row in rows} == {
        ("strchive", dataset, "resolved")
    }
    licence = resolve_sidecar(spec, "sources.csv")
    assert licence is not None
    (source,) = [r for r in _rows(licence) if r["source"] == "strchive"]
    assert (source["layer"], source["dataset"], source["license"]) == ("repeat_grade", dataset, "MIT")
    before = [(p.stat().st_mtime_ns, p.read_bytes()) for p in (path, licence)]
    enrich(spec, offline=True)
    assert before == [(p.stat().st_mtime_ns, p.read_bytes()) for p in (path, licence)]


def test_offline_cli_reports_could_not_ask(tmp_path: Path, no_ambient_caches: Path) -> None:
    spec = _spec(tmp_path, [("ARX", "GCN")])
    result = CliRunner().invoke(app, ["enrich", str(spec), "--offline"])
    assert result.exit_code == 0, result.output
    assert "could not ask STRchive" in result.output
    assert not (spec / "repeat_grades.csv").exists()
    assert resolve_sidecar(spec, "sources.csv") is None


def test_merge_refreshes_a_records_label_and_release(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("ARX", "GCN")])
    records = [rec for rec in json.loads(_SLICE.read_text()) if rec["gene"] == "ARX"]
    first = records[0]
    derived = spec / "derived"
    derived.mkdir()
    path = derived / "repeat_grades.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("gene", "repeat_unit", "locus_id", "grade", "disease", "source", "dataset"))
        writer.writerow(
            ("ARX", "GCN", first["id"], first["evidence"][0], "Previous label", "strchive", "earlier")
        )
    result = enrich_repeat_grades(spec, catalogue=_SLICE, offline=True)
    assert {(row.locus_id, row.grade) for row in result.rows} == {
        (rec["id"], word) for rec in records for word in rec["evidence"]
    }
    assert {(row["disease"], row["dataset"]) for row in _rows(path) if row["locus_id"] == first["id"]} == {
        (first["disease"], "")
    }
    assert not (spec / "repeat_grades.csv").exists()
    (source,) = _rows(resolve_sidecar(spec, "sources.csv"))
    assert source["dataset"] == ""


def test_provisioning_failure_preserves_existing_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, [("ARX", "GCN")])

    def unavailable() -> Path:
        raise OpenSnapshotError("snapshot fetch interrupted")

    monkeypatch.setattr(grades_pass, "ensure_strchive_snapshot", unavailable)
    path = spec / "repeat_grades.csv"
    path.write_text("gene,repeat_unit,locus_id,grade\nHTT,CAG,HD_HTT,Definitive\n")
    before = path.read_bytes()
    result = enrich_repeat_grades(spec)
    assert result.could_not_ask == [("ARX", "GCN")] and not result.missing
    assert result.reason == "snapshot fetch interrupted"
    assert path.read_bytes() == before and resolve_sidecar(spec, "sources.csv") is None


def test_provisioned_answer_waits_for_the_run_to_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    monkeypatch.setattr(grades_pass, "ensure_strchive_snapshot", lambda: _SLICE)
    preview = enrich_repeat_grades(spec, write=False)
    assert preview.covered == [("HTT", "CAG")]
    assert not (spec / "repeat_grades.csv").exists()
    assert resolve_sidecar(spec, "sources.csv") is None
    # A reachable grade beside a resolution subject that must fail the later strict gate.
    lane = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    lane.write_bytes(_SLICE.read_bytes())
    monkeypatch.setenv(STRCHIVE_CACHE_VAR, str(lane))
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs334,A/T,risk,Carrier\n")
    with pytest.raises(EnrichmentError, match="unresolved"):
        enrich(spec, offline=True, mode="strict")
    assert not (spec / "repeat_grades.csv").exists()
    assert resolve_sidecar(spec, "sources.csv") is None


def test_refused_licence_commit_leaves_no_grade_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])

    def refuse(*args: object, **kwargs: object) -> None:
        raise RepeatGradeError("licence write failed")

    monkeypatch.setattr(grades_pass, "record_table_sources", refuse)
    with pytest.raises(RepeatGradeError, match="licence write failed"):
        enrich_repeat_grades(spec, catalogue=_SLICE)
    assert {p.name for p in spec.iterdir()} == {"repeat_alleles.csv"}


@pytest.mark.parametrize("flag", [[], ["--rederive"]], ids=["ordinary", "rederive"])
def test_release_replaces_all_grades_and_the_licence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: list[str]
) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    record = next(rec for rec in json.loads(_SLICE.read_text()) if rec["gene"] == "HTT")
    source = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    for release, grades in [("v2.26.0", record["evidence"]), ("v2.26.1", ["Moderate"])]:
        record["evidence"] = grades
        source.write_text(json.dumps([record]))
        snapshot = build_strchive_snapshot(tmp_path / release, catalogue=source, release=release)
        monkeypatch.setenv(STRCHIVE_CACHE_VAR, str(snapshot.out_dir))
        run = CliRunner().invoke(app, ["enrich", str(spec), "--offline", *flag])
        assert run.exit_code == 0, run.output
        rows = _rows(spec / "repeat_grades.csv")
        assert [(r["locus_id"], r["grade"], r["dataset"]) for r in rows] == [
            (record["id"], grade, snapshot.dataset) for grade in grades
        ]
        (terms,) = _rows(resolve_sidecar(spec, "sources.csv"))
        assert terms["dataset"] == snapshot.dataset


def test_rederive_records_a_fresh_lookup_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    source = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    source.write_bytes(_SLICE.read_bytes())
    monkeypatch.setenv(STRCHIVE_CACHE_VAR, str(source))
    for day, flag in [(1, []), (2, ["--rederive"])]:
        timestamp = f"2026-11-0{day}T00:00:00Z"
        monkeypatch.setattr(grades_pass, "now_utc_iso", lambda stamp=timestamp: stamp)
        run = CliRunner().invoke(app, ["enrich", str(spec), "--offline", *flag])
        assert run.exit_code == 0, run.output
        assert {r["fetched_at"] for r in _rows(spec / "repeat_grades.csv")} == {timestamp}


def test_padded_grade_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    record = next(rec for rec in json.loads(_SLICE.read_text()) if rec["gene"] == "HTT")
    record["evidence"] = [" Refuted "]
    source = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    source.write_text(json.dumps([record]))
    for _ in range(3):
        enrich_repeat_grades(spec, catalogue=source)
    assert [r["grade"] for r in _rows(spec / "repeat_grades.csv")] == ["Refuted"]


def test_gene_join_preserves_first_authored_spelling(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("htt", "CAG"), ("HTT", "CAG")])
    record = next(rec for rec in json.loads(_SLICE.read_text()) if rec["gene"] == "HTT")
    result = enrich_repeat_grades(spec, catalogue=_SLICE)
    assert result.covered == [("htt", "CAG")] and not result.missing
    assert [(row.gene, row.locus_id, row.grade) for row in result.rows] == [
        ("htt", record["id"], word) for word in record["evidence"]
    ]


def test_contested_module_keys_are_counted_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    records = json.loads(_SLICE.read_text())
    keys = [("ARX", "NGC"), ("ARX", "GCN"), ("HTT", "CAG")]
    spec = _spec(tmp_path, keys + keys)
    expected = {
        key
        for key in keys
        if len(
            {
                r["id"]
                for r in records
                if r["gene"] == key[0]
                and key[1]
                in r["pathogenic_motif_reference_orientation"] + r["pathogenic_motif_gene_orientation"]
            }
        )
        > 1
    }
    source = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    source.write_bytes(_SLICE.read_bytes())
    monkeypatch.setenv(STRCHIVE_CACHE_VAR, str(source))
    run = CliRunner().invoke(app, ["enrich", str(spec), "--offline"])
    assert run.exit_code == 0, run.output
    assert f"{len(expected)} contested" in run.output
    assert set(enrich_repeat_grades(spec, catalogue=source).contested) == expected


def test_answered_absence_retires_last_row_and_licence(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    enrich_repeat_grades(spec, catalogue=_SLICE)
    remaining = [r for r in json.loads(_SLICE.read_text()) if r["gene"] != "HTT"]
    source = tmp_path / STRCHIVE_CATALOGUE_FILENAME
    source.write_text(json.dumps(remaining))
    result = enrich_repeat_grades(spec, catalogue=source)
    assert result.missing == [("HTT", "CAG")]
    assert not _rows(spec / "repeat_grades.csv")
    assert not _rows(resolve_sidecar(spec, "sources.csv"))


def test_removed_module_repeat_keeps_its_record_for_the_orphan_check(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG"), ("ARX", "GCN")])
    enrich_repeat_grades(spec, catalogue=_SLICE)
    before = _rows(spec / "repeat_grades.csv")
    table = spec / "repeat_alleles.csv"
    table.write_text(
        "".join(line for line in table.read_text().splitlines(keepends=True) if not line.startswith("HTT,"))
    )
    enrich_repeat_grades(spec, catalogue=_SLICE)
    assert [r for r in _rows(spec / "repeat_grades.csv") if r["gene"] == "HTT"] == [
        r for r in before if r["gene"] == "HTT"
    ]


def test_offline_rederive_keeps_the_record_and_its_terms(tmp_path: Path, no_ambient_caches: Path) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    original = enrich_repeat_grades(spec, catalogue=_SLICE)
    paths = [spec / "repeat_grades.csv", resolve_sidecar(spec, "sources.csv")]
    before = [path.read_bytes() for path in paths]
    result = enrich(spec, offline=True, rederive=True).repeat_grades
    assert result.could_not_ask == original.covered and not result.missing
    assert result.rows == original.rows
    assert [path.read_bytes() for path in paths] == before


def test_reanswer_repairs_the_release_even_when_grade_rows_agree(tmp_path: Path) -> None:
    spec = _spec(tmp_path, [("HTT", "CAG")])
    snapshot = build_strchive_snapshot(tmp_path / "lane", catalogue=_SLICE, release="v2.26.0")
    enrich_repeat_grades(spec, catalogue=snapshot.out_dir)
    licence = resolve_sidecar(spec, "sources.csv")
    licence.write_text(licence.read_text().replace(snapshot.dataset, "earlier"))
    enrich_repeat_grades(spec, catalogue=snapshot.out_dir)
    assert {r["dataset"] for r in _rows(licence)} == {snapshot.dataset}
