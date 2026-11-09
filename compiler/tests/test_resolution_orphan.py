"""RM422 (S138): a `resolution.csv` row for a variant no authored table names is reported.

Every check over `resolution.csv` asked about rows an authored table names, so a row whose subject the
author removed was read by nothing: `validate --strict` and `compile --strict` said nothing, and the
compile hashed the file into `manifest.derived`. The reporter's case had no `variants.csv` at all (the
claim moved into `haplotypes.csv` + `diplotypes.csv`), which `cyp2c19_star_alleles` reproduces: a
PGx-only module whose `resolution.csv` places its haplotype loci. Every expected set is read off the
module at runtime.
"""

import csv
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_PHRASE = "no table in this module names"
#: The reporter's removed variant: MTRR's rs1801394 at its GRCh38 position, named by no reference example.
_REMOVED = {"variant_key": "rs1801394", "rsid": "rs1801394", "chrom": "5", "start": "7870860", "ref": "A"}


def _copy(name: str, tmp_path: Path) -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    return spec


def _append_resolution_row(spec: Path, row: dict[str, str]) -> None:
    path = spec / "resolution.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    full = dict.fromkeys(header, "")
    full.update(
        {"alts": "G", "genome_build": "GRCh38", "locus_index": "0", "source": "manual", "authority": "manual"}
    )
    full.update({"status": "resolved"})
    full.update(row)
    with path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=header).writerow(full)


def _orphan_lines(warnings: list[str]) -> list[str]:
    return [w for w in warnings if w.startswith("resolution.csv") and _PHRASE in w]


def test_a_resolution_row_for_a_removed_variant_is_named_in_both_modes(tmp_path: Path) -> None:
    spec = _copy("cyp2c19_star_alleles", tmp_path)
    _append_resolution_row(spec, _REMOVED)
    for strict in (False, True):
        result = validate_spec(spec, strict=strict)
        lines = _orphan_lines(result.warnings)
        assert len(lines) == 1, (strict, result.warnings)
        assert "1 identity(ies)" in lines[0] and "['rs1801394']" in lines[0]
        # A warning in both modes, never an error: a hand-kept row is plausible mid-edit (the pm's condition).
        assert not [e for e in result.errors if "rs1801394" in e]


def test_the_compile_publishes_the_finding_once(tmp_path: Path) -> None:
    spec = _copy("cyp2c19_star_alleles", tmp_path)
    _append_resolution_row(spec, _REMOVED)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert len(_orphan_lines(result.warnings)) == 1, result.warnings


def test_a_study_proxy_is_the_modules_own_subject_until_no_study_names_it(tmp_path: Path) -> None:
    """`enrich` asks for a study's LD proxy (RM331), so its row is the module's own; blank the proxy
    and the same row is an orphan. The second half is what proves the first is not vacuous."""
    spec = _copy("longevity_studies", tmp_path)
    path = spec / "studies.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header, rows = reader.fieldnames, list(reader)
    proxies = sorted({r["proxy_rsid"] for r in rows if r.get("proxy_rsid")})
    assert proxies, "the corpus lost its only study proxy; this test needs another"
    assert _orphan_lines(validate_spec(spec).warnings) == []

    carried = {r.get("rsid") for r in rows} | {r.get("variant_key") for r in rows}
    for row in rows:
        row["proxy_rsid"] = ""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    lines = _orphan_lines(validate_spec(spec).warnings)
    assert len(lines) == 1, lines
    for proxy in proxies:
        if proxy not in carried:
            assert f"'{proxy}'" in lines[0]


@pytest.mark.parametrize(
    "example", sorted(p.name for p in _EXAMPLES.iterdir() if (p / "resolution.csv").exists())
)
def test_no_reference_example_carries_a_resolution_orphan(example: str) -> None:
    """Every shipped example's table was written by `enrich` over its own subjects, so none warns.

    This is the false-positive half: the subject set is the authored tables plus the study proxies,
    the same set `enrich` asks about, and a narrower one would name the example's own rows.
    """
    assert _orphan_lines(validate_spec(_EXAMPLES / example).warnings) == []
