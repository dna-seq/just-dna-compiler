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


def test_both_blocks_contribute_genes_in_first_seen_order(spec: Path, snapshot: Path) -> None:
    current = ["samd11", "PALB2"]
    legacy = ["SAMD11", "Brca2", "Or4f5"]
    request = ["brca2", "HBB", "BRCA1"]
    blocks = {
        "panel_provenance": {"genes": current, "genes_unmatched": ["HBB"], "significance": ["benign"]},
        "panel": {"source": "clinvar", "genes": legacy, "significance": ["likely_benign"]},
    }
    with (spec / "module_spec.yaml").open("a") as handle:
        handle.write(yaml.safe_dump(blocks))
    result = draft_gene_panel(spec, request, snapshot=snapshot)
    panel = result.panel_provenance
    assert panel is not None
    assert panel.significance == sorted(DEFAULT_CLIN_SIG)
    for block in blocks.values():
        assert any("significance differs" in w and str(block["significance"]) in w for w in result.warnings)
    expected = [*current, *legacy[1:], *request[1:]]
    assert panel.genes == expected
    with (spec / "variants.csv").open() as handle:
        matched = {row["gene"].casefold() for row in csv.DictReader(handle)}
    assert panel.genes_unmatched == [g for g in expected if g.casefold() not in matched]

    blocks["panel_provenance"] = panel.model_dump()
    (spec / "module_spec.yaml").write_bytes(_YAML.read_bytes() + yaml.safe_dump(blocks).encode())
    again = draft_gene_panel(spec, request, snapshot=snapshot)
    assert again.panel_provenance == panel


@pytest.mark.parametrize("pins", [("panel",), ("panel_provenance",), ("panel_provenance", "panel")])
def test_snapshot_without_digest_keeps_authored_pin(
    spec: Path, snapshot: Path, pins: tuple[str, ...]
) -> None:
    (snapshot / "release.json").unlink()
    pin = sha256_file(_VCF)
    blocks = {"panel_provenance": {}, "panel": {"source": "clinvar"}}
    for name in pins:
        blocks[name]["reference_sha256"] = pin
    if len(pins) == 2:
        blocks["panel"]["reference_sha256"] = pin.removeprefix("sha256:").upper()
    with (spec / "module_spec.yaml").open("a") as handle:
        handle.write(yaml.safe_dump(blocks))
    result = draft_gene_panel(spec, ["HBB"], snapshot=snapshot)
    assert result.panel_provenance is not None
    assert result.panel_provenance.reference_sha256 == pin
    assert any("snapshot does not state a source_sha256" in w and "authored" in w for w in result.warnings)


def test_snapshot_without_digest_refuses_conflicting_authored_pins(spec: Path, snapshot: Path) -> None:
    (snapshot / "release.json").unlink()
    current, legacy = sha256_file(_VCF), sha256_file(_YAML)
    blocks = {
        "panel_provenance": {"reference_sha256": current},
        "panel": {"source": "clinvar", "reference_sha256": legacy},
    }
    with (spec / "module_spec.yaml").open("a") as handle:
        handle.write(yaml.safe_dump(blocks))
    before = _tree(spec)
    run = CliRunner().invoke(app, ["draft-panel", str(spec), "--gene", "HBB", "--snapshot", str(snapshot)])
    assert run.exit_code == 1, run.output
    assert current in run.output and legacy in run.output
    assert _tree(spec) == before


@pytest.mark.parametrize("extra_genes", [(), ("HBB",)])
@pytest.mark.parametrize("dry_run", [True, False])
def test_an_unnamed_row_keeps_the_list_and_warns(
    spec: Path, snapshot: Path, dry_run: bool, extra_genes: tuple[str, ...]
) -> None:
    with (_ROOT / "reference_examples" / "hboc_palb2" / "variants.csv").open() as handle:
        row = next(csv.DictReader(handle))
    gene = row["gene"]
    row["gene"] = ""
    with (spec / "variants.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    request = [gene, *extra_genes]
    result = draft_gene_panel(spec, request, snapshot=snapshot, dry_run=dry_run)
    assert result.panel_provenance is not None
    assert result.panel_provenance.genes == request
    # The unnamed row decides nothing: every requested gene stays listed, and the run says why it may overstate.
    # PALB2's only row names no gene, so it stays listed; HBB, when requested, drafts named rows of its own.
    assert result.panel_provenance.genes_unmatched == [gene]
    (warning,) = [w for w in result.warnings if "name no gene" in w]
    assert warning.startswith("1 variants.csv row(s)") and "1 listed gene(s)" in warning
