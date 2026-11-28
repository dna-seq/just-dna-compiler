"""ClinVar panel provenance from the shipped VCF slice, through the draft and its CLI."""

import csv
from pathlib import Path

import pytest
import yaml
from just_dna_enricher.cli import app
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.clinvar_draft import DEFAULT_CLIN_SIG, draft_gene_panel
from just_dna_format.integrity import sha256_file
from typer.testing import CliRunner

_ROOT = Path(__file__).resolve().parents[2]
_VCF = _ROOT / "assets" / "clinvar_GRCh38_slice.vcf.gz"
_YAML = _ROOT / "reference_examples" / "apoe_epsilon" / "module_spec.yaml"


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    return build_snapshot(_VCF, tmp_path / "clinvar").out_dir


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    path = tmp_path / "panel"
    path.mkdir()
    (path / "module_spec.yaml").write_bytes(_YAML.read_bytes() + b"# author's draft notes\n")
    return path


def _tree(root: Path) -> dict[Path, bytes]:
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_cli_prints_merged_panel_provenance(spec: Path, snapshot: Path) -> None:
    path = spec / "module_spec.yaml"
    original = path.read_bytes()
    asked = ["SAMD11", "HBB", "PALB2"]
    cmd = ["draft-panel", str(spec), "--snapshot", str(snapshot)]
    for gene in asked:
        cmd.extend(["--gene", gene])
    runner = CliRunner()
    blocks = []
    for extra in (["--dry-run"], []):
        run = runner.invoke(app, cmd + extra)
        assert run.exit_code == 0, run.output
        heading = "Paste into module_spec.yaml"
        assert heading in run.stdout
        snippet = run.stdout[run.stdout.index("panel_provenance:", run.stdout.index(heading)) :]
        blocks.append(yaml.safe_load(snippet))
        if extra:
            assert _tree(spec) == {Path("module_spec.yaml"): original}
        assert path.read_bytes() == original
    with (spec / "variants.csv").open() as handle:
        matched = {row["gene"] for row in csv.DictReader(handle)}
    expected = {
        "genes": asked,
        "genes_unmatched": [g for g in asked if g not in matched],
        "significance": sorted(DEFAULT_CLIN_SIG),
        "reference_sha256": sha256_file(_VCF),
    }
    assert matched == {"HBB"}
    assert blocks == [{"panel_provenance": expected}] * len(blocks)

    with path.open("a") as handle:
        handle.write(yaml.safe_dump(blocks[0]))
    pasted = path.read_bytes()
    predicate = frozenset({"likely_benign"})
    second = draft_gene_panel(
        spec, ["samd11", "OR4F5"], snapshot=snapshot, clin_sig=predicate, min_review_stars=0
    )
    with (spec / "variants.csv").open() as handle:
        matched = {row["gene"] for row in csv.DictReader(handle)}
    assert matched == {"HBB", "SAMD11"}
    merged = [*asked, "OR4F5"]
    assert second.panel_provenance.model_dump() == {
        **expected,
        "genes": merged,
        "genes_unmatched": [g for g in merged if g not in matched],
        "significance": sorted(predicate),
    }
    [changed] = [w for w in second.warnings if "significance differs" in w]
    assert all(value in changed for value in DEFAULT_CLIN_SIG | predicate)
    assert path.read_bytes() == pasted


@pytest.mark.parametrize("pins", [("panel",), ("panel_provenance",), ("panel", "panel_provenance")])
def test_panel_provenance_mismatched_pin_refuses_before_writing(
    spec: Path, snapshot: Path, pins: tuple[str, ...]
) -> None:
    authored = sha256_file(_YAML)
    current = sha256_file(_VCF)
    blocks = {}
    for name in pins:
        block = {"reference_sha256": authored if name == pins[0] else current}
        if name == "panel":
            block["source"] = "clinvar"
        blocks[name] = block
    with (spec / "module_spec.yaml").open("a") as handle:
        handle.write(yaml.safe_dump(blocks))
    before = _tree(spec)
    run = CliRunner().invoke(app, ["draft-panel", str(spec), "--gene", "HBB", "--snapshot", str(snapshot)])
    assert run.exit_code == 1
    assert authored in run.output and current in run.output
    assert _tree(spec) == before


def test_panel_provenance_no_matches_migrates_legacy_and_reports_unknown_digest(
    spec: Path, snapshot: Path
) -> None:
    (snapshot / "release.json").unlink()
    path = spec / "module_spec.yaml"
    legacy = {"source": "clinvar", "genes": ["HBB", "BRCA2"]}
    with path.open("a") as handle:
        handle.write(yaml.safe_dump({"panel": legacy}))
    before = _tree(spec)
    with (spec / "variants.csv").open("w") as handle:
        handle.write("gene\nHBB\n")
    result = draft_gene_panel(spec, ["BRCA2", "PALB2"], snapshot=snapshot)
    assert result.panel_provenance.model_dump() == {
        "genes": [*legacy["genes"], "PALB2"],
        "genes_unmatched": ["BRCA2", "PALB2"],
        "significance": sorted(DEFAULT_CLIN_SIG),
        "reference_sha256": None,
    }
    assert any("snapshot does not state a source_sha256" in w for w in result.warnings)
    assert path.read_bytes() == before[Path("module_spec.yaml")]
