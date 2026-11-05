"""RM308: RM279's conclusion rule at `validate` and `compile`, as `conclusion_names_other_genotype`.

The fixtures are RM279's, quoted from the curated v1 ports a consumer measured (D14), run here through
a real spec directory and a `--strict` compile rather than through the hint surface.
"""

import csv
import io
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm308\n"
    "  title: RM308\n"
    "  description: conclusions checked against their own genotype\n"
    "  report_title: RM308\n"
    "genome_build: GRCh38\n"
)

# coronary rs17514846: the C/C and A/A conclusions are swapped in the source module.
_SWAPPED = [
    ("rs17514846", "A/C", "neutral", "AC genotype carriers have a moderate risk of CAD.", "FURIN"),
    ("rs17514846", "C/C", "neutral", "AA genotype is associated with increased CAD risk.", "FURIN"),
    ("rs17514846", "A/A", "neutral", "CC genotype is not associated with increased risk.", "FURIN"),
]

# thrombophilia rs1799963: the A/A row reuses the heterozygote's sentence.
_COPIED = [
    ("rs1799963", "G/G", "neutral", "GG genotype is not associated with increased risk.", "F2"),
    ("rs1799963", "A/G", "risk", "GA carriers have 2.8x risk of thrombosis.", "F2"),
    ("rs1799963", "A/A", "risk", "GA carriers have 6.74x risk of thrombosis.", "F2"),
]

# rs2943634: a correct row naming its neighbour too, which the looser reading flagged.
_CORRECT = [
    ("rs2943634", "A/A", "protective", "AA genotype is protective, AC carriers less so.", "IRS1"),
    ("rs2943634", "A/C", "neutral", "AC carriers sit between AA and CC.", "IRS1"),
    ("rs2943634", "C/C", "risk", "CC-carriers have higher risk of ischemic stroke.", "IRS1"),
]


#: GRCh38 positions as Ensembl resolves them (copied from real `resolution.csv` rows), so the rows are
#: positioned and a `--strict` compile has nothing left to resolve.
_POSITIONS = {
    "rs17514846": ("15", "90873320", "C", "A"),
    "rs1799963": ("11", "46739505", "G", "A"),
    "rs2943634": ("2", "226203364", "A", "C"),
}


def _spec(directory: Path, rows: list[tuple[str, str, str, str, str]]) -> Path:
    directory.mkdir(parents=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["rsid", "chrom", "start", "ref", "alts", "genotype", "state", "conclusion", "gene"])
    writer.writerows((rsid, *_POSITIONS[rsid], *rest) for rsid, *rest in rows)
    (directory / "variants.csv").write_text(buf.getvalue(), encoding="utf-8")
    # One citation grounding the module as a whole (RM47: a row naming no variant is not an orphan).
    (directory / "studies.csv").write_text("rsid,pmid\n,32067586\n", encoding="utf-8")
    return directory


def _findings(warnings: list[str]) -> list[str]:
    """The finding's sentences. A result's `warnings` are plain strings (the code does not survive the
    pydantic field), so this matches the pinned phrase; `warnings_summary` is where the code is read."""
    return [w for w in warnings if "names another genotype at the locus and never the row's own" in w]


def test_a_swapped_pair_warns_under_a_strict_compile_that_stays_green(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _SWAPPED)
    checked = validate_spec(spec, strict=True)
    assert checked.valid, checked.errors
    compiled = compile_module(spec, tmp_path / "out", strict=True)
    assert compiled.success, compiled.errors

    [finding] = _findings(compiled.warnings)
    assert "2 variants.csv row(s)" in finding and "look swapped" in finding
    assert "rs17514846 C/C names A/A" in finding and "rs17514846 A/A names C/C" in finding
    # Parity by check: the pre-flight carries the same finding, and the compile carries it once.
    assert _findings(checked.warnings) == _findings(compiled.warnings)
    assert compiled.manifest.compilation.warnings_summary["conclusion_names_other_genotype"] == 1


def test_a_copied_conclusion_is_its_own_reason(tmp_path: Path) -> None:
    compiled = compile_module(_spec(tmp_path / "spec", _COPIED), tmp_path / "out")
    assert compiled.success, compiled.errors
    [finding] = _findings(compiled.warnings)
    assert "1 variants.csv row(s)" in finding and "as if copied" in finding
    assert "rs1799963 A/A names A/G" in finding


def test_both_reasons_are_two_findings_under_one_code(tmp_path: Path) -> None:
    compiled = compile_module(_spec(tmp_path / "spec", _SWAPPED + _COPIED), tmp_path / "out")
    assert compiled.success, compiled.errors
    assert len(_findings(compiled.warnings)) == 2
    assert compiled.manifest.compilation.warnings_summary["conclusion_names_other_genotype"] == 2


def test_a_correct_module_is_quiet(tmp_path: Path) -> None:
    compiled = compile_module(_spec(tmp_path / "spec", _CORRECT), tmp_path / "out")
    assert compiled.success, compiled.errors
    assert _findings(compiled.warnings) == []
    assert "conclusion_names_other_genotype" not in compiled.manifest.compilation.warnings_summary
