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


def test_merge_fills_a_second_record_without_rewriting_the_first(tmp_path: Path) -> None:
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
        ("Previous label", "earlier")
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
