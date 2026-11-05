"""RM366: a published pair stated by half is reported in both modes, never refused.

`effect_size` without `effect_measure` dates from 0.3, so a module published since may hold it and must
keep validating (P3). The finding is `paired_field_half_stated`, one line per table and column, raised
by the pre-flight `validate` runs and therefore carried by `compile` unchanged.
"""

import csv
import shutil
from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.manifest import read_manifest

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE = _ROOT / "reference_examples" / "longevity_studies"


def _without_measures(tmp_path: Path) -> tuple[Path, int]:
    """The example with `effect_measure` emptied on every study row that states an `effect_size`."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)
    path = spec / "studies.csv"
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    emptied = 0
    for row in rows:
        if (row.get("effect_size") or "").strip():
            row["effect_measure"] = ""
            emptied += 1
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return spec, emptied


def _half_stated(warnings: list[str]) -> list[str]:
    # By the pinned phrase: `ValidationResult.warnings` are plain strings, so a filter on `.code` would
    # pass vacuously. The code itself is read from the manifest's `warnings_summary` below.
    return [w for w in warnings if "Reported rather than refused" in w]


def test_the_example_as_published_states_every_measure() -> None:
    assert _half_stated(validate_spec(_EXAMPLE).warnings) == []


def test_a_magnitude_with_no_measure_is_reported_once_and_the_module_still_validates(tmp_path: Path) -> None:
    spec, emptied = _without_measures(tmp_path)
    assert emptied, "the example must carry an effect_size for this test to mean anything"

    for strict in (False, True):
        result = validate_spec(spec, strict=strict)
        (finding,) = _half_stated(result.warnings)
        assert finding.startswith(
            f"studies.csv: {emptied} row(s) state effect_size with effect_measure empty"
        )
        assert "Reported rather than refused" in finding
        assert not any("effect_measure" in e for e in result.errors)

    out = tmp_path / "out"
    compiled = compile_module(spec, out, resolve_with_ensembl=False)
    assert compiled.success, compiled.errors
    assert len(_half_stated(compiled.warnings)) == 1
    assert read_manifest(out / "manifest.json").compilation.warnings_summary["paired_field_half_stated"] == 1
