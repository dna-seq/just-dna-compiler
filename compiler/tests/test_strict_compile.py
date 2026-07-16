"""Strict (all-or-nothing) compile — refuse a partial artifact when a position is unresolved.

The failure mode behind "local hash differs from published": an incomplete/absent Ensembl reference
leaves a variant without its coordinate, so the compiled bytes (and `artifact.digest`) are not
reproducible. `strict=True` fails instead of emitting that partial artifact; the default best-effort
mode still emits it (with warnings). No Ensembl cache is needed here — `resolve_with_ensembl=False`
leaves an rsid-only row unresolved, exactly the state strict must catch.
"""

from pathlib import Path

from just_dna_compiler.compiler import compile_module

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_STUDIES = "rsid,pmid\nrs1801133,9545397\n"
_RSID_ONLY = "rsid,genotype,state,conclusion,gene\nrs1801133,A/G,risk,MTHFR risk,MTHFR\n"
_POSITIONED = (
    "rsid,chrom,start,ref,genotype,state,conclusion,gene\n"
    "rs1801133,1,11856378,A,A/G,risk,MTHFR risk,MTHFR\n"
)


def _spec(d: Path, variants: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


def test_strict_fails_on_unresolved_position(tmp_path: Path) -> None:
    out = tmp_path / "out"
    r = compile_module(_spec(tmp_path / "spec", _RSID_ONLY), out, resolve_with_ensembl=False, strict=True)
    assert not r.success
    assert any("unresolved genomic positions" in e for e in r.errors)
    assert not (out / "weights.parquet").exists()  # nothing partial reached disk


def test_non_strict_emits_partial_artifact(tmp_path: Path) -> None:
    # Default best-effort: the rsid-only, unresolved row still compiles (today's behavior).
    r = compile_module(_spec(tmp_path / "spec", _RSID_ONLY), tmp_path / "out", resolve_with_ensembl=False)
    assert r.success, r.errors


def test_strict_passes_when_all_positions_present(tmp_path: Path) -> None:
    r = compile_module(_spec(tmp_path / "spec", _POSITIONED), tmp_path / "out", resolve_with_ensembl=False, strict=True)
    assert r.success, r.errors
    assert (tmp_path / "out" / "weights.parquet").is_file()
