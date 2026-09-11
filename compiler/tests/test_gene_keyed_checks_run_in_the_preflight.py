"""Four warning checks that only ran at compile now run in the pre-flight too (RM211).

`@parity-by-check` says parity is audited **by check, not by table**, and the compile-side per-model
closures are where that keeps failing: a table is loaded in both commands, so a pass auditing table by
table sees it covered and stops. RM93 moved `_check_frequency_arithmetic` out of one such closure for
exactly this reason and **left its sibling behind** — `_check_gene_metrics_arithmetic` is the same
validate-by-redundancy over a sidecar's own numbers, needing no `output_dir`, no reference and no
resolved row, and it stayed compile-only for two releases.

Moved here, with what makes each legal under the standing exemption (*resolved rows* are what stay
compile-only, not the word "resolution"):

- `_check_gene_metrics_arithmetic` — reads one sidecar's own columns and nothing else.
- `_cross_check_gene_metrics` / `_cross_check_gene_validity` — keyed on **gene**, which is authored
  and which nothing fills, so the pre-flight reaches the answer the compile reaches.
- `_check_declared_license_agrees` — `sources.csv` against `module_spec.yaml`'s own `license:`; two
  authored files, no join.

**And five deliberately did not move**, which this file asserts as well, because an exemption nobody
records is re-derived as a bug next round. `_cross_check_frequencies`,
`_cross_check_clinical_assertions`, `_cross_check_gwas_effects` and `_check_ba1_lint` are keyed on
**position or `variant_key`** — an rsID-only authored row has no coordinate until resolution runs, so
asking them early would report every such row as an orphan. `_source_checks` is the other kind: its
`used_sources` is complete only once every sidecar has been read, and `sources.csv` is last in
`_FACT_TABLES` precisely so the compile can ask it against a full set.

No message here embeds a count, which is what makes running them on both sides safe
(`@no-rerun-with-counts`); the fact-table extend site de-duplicates on the message.
"""

import csv
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hboc_palb2"


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)
    return spec


def _rewrite(path: Path, mutate) -> None:
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    mutate(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _both(spec: Path, tmp_path: Path) -> tuple[list[str], list[str]]:
    return (
        list(validate_spec(spec, strict=False).warnings),
        list(compile_module(spec, tmp_path / "out", strict=False).warnings),
    )


def test_the_untouched_example_is_clean_on_these_checks(tmp_path: Path) -> None:
    """The floor: a finding below means the edit caused it, not the fixture."""
    spec = _spec(tmp_path)
    report, compiled = _both(spec, tmp_path)

    for phrase in ("does not equal", "names a gene", "license"):
        assert not [w for w in report if phrase in w], (phrase, report)
    assert validate_spec(spec, strict=False).valid


def test_the_arithmetic_finding_reaches_validate(tmp_path: Path) -> None:
    """RM93's sibling. `obs_lof / exp_lof` made to disagree with `oe_lof`, which is decidable here."""
    spec = _spec(tmp_path)

    def break_ratio(rows: list[dict[str, str]]) -> None:
        rows[0]["obs_lof"] = "10"
        rows[0]["exp_lof"] = "100"
        rows[0]["oe_lof"] = "0.9"  # 10/100 is 0.1
        rows[0]["oe_lof_lower"] = "0.01"
        rows[0]["loeuf"] = "0.95"

    _rewrite(spec / "gene_metrics.csv", break_ratio)
    report, compiled = _both(spec, tmp_path)

    found = [w for w in report if "oe_lof" in w]
    assert found, report
    assert found == [w for w in compiled if "oe_lof" in w]


def test_a_gene_keyed_orphan_reaches_validate(tmp_path: Path) -> None:
    """Keyed on `gene`, which is authored and which resolution never fills."""
    spec = _spec(tmp_path)
    _rewrite(spec / "gene_metrics.csv", lambda rows: rows[0].update({"gene": "NOTAGENEINTHISMODULE"}))
    report, compiled = _both(spec, tmp_path)

    found = [w for w in report if "NOTAGENEINTHISMODULE" in w]
    assert found, report
    assert found == [w for w in compiled if "NOTAGENEINTHISMODULE" in w]


def test_a_gene_validity_orphan_reaches_validate(tmp_path: Path) -> None:
    """The same key, one table over — the two sidecars answer different questions about it."""
    spec = _spec(tmp_path)
    _rewrite(spec / "gene_validity.csv", lambda rows: rows[0].update({"gene": "ALSONOTAGENEHERE"}))
    report, compiled = _both(spec, tmp_path)

    found = [w for w in report if "ALSONOTAGENEHERE" in w]
    assert found, report
    assert found == [w for w in compiled if "ALSONOTAGENEHERE" in w]


@pytest.mark.parametrize(
    "csv_name,mutate,phrase",
    [
        ("gene_metrics.csv", lambda rows: rows[0].update({"gene": "ORPHANGENE"}), "ORPHANGENE"),
        ("gene_validity.csv", lambda rows: rows[0].update({"gene": "ORPHANGENE"}), "ORPHANGENE"),
    ],
)
def test_a_finding_both_sides_make_is_published_once(
    tmp_path: Path, csv_name: str, mutate, phrase: str
) -> None:
    """The other half of moving a check: the compile must not publish it a second time."""
    spec = _spec(tmp_path)
    _rewrite(spec / csv_name, mutate)

    result = compile_module(spec, tmp_path / "out", strict=False)

    assert len([w for w in result.warnings if phrase in w]) == 1, result.warnings


def test_the_position_keyed_cousins_stay_compile_only_and_the_reason_is_the_key(tmp_path: Path) -> None:
    """The exemption, asserted rather than left as prose.

    A frequency row at a coordinate no variant sits at is an orphan **after** resolution. Asking it
    in the pre-flight would report it against unresolved authored rows, so it is compile-only on the
    standing exemption and not by oversight. What this pins is that the compile still finds it — a
    future move of this check would fail here and send the reader to the docstring above.
    """
    spec = _spec(tmp_path)
    _rewrite(spec / "frequencies.csv", lambda rows: rows[0].update({"start": "999888777"}))

    result = compile_module(spec, tmp_path / "out", strict=False)

    assert [w for w in result.warnings if "999888777" in w or "no variant" in w], result.warnings
