"""Smoke tests for the Typer CLI (`just_dna_compiler.cli`) — the thin shell over the Python API.

Asserts exit codes (0 success / 1 failure, for CI/registry gating) and the key stdout lines, across
validate / compile / reverse, including `--strict` and `--strip-identity`.
"""

from pathlib import Path

from just_dna_compiler.cli import app
from typer.testing import CliRunner

runner = CliRunner()

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_STUDIES = "rsid,pmid\nrs1801133,9545397\n"
_POSITIONED = (
    "rsid,chrom,start,ref,genotype,state,conclusion,gene\n"
    "rs1801133,1,11856378,A,A/G,risk,MTHFR risk,MTHFR\n"
)
_RSID_ONLY = "rsid,genotype,state,conclusion,gene\nrs1801133,A/G,risk,MTHFR risk,MTHFR\n"


def _spec(d: Path, variants: str, *, module_extra: str = "") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML + module_extra, encoding="utf-8")
    (d / "variants.csv").write_text(variants, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return d


def test_validate_ok(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _POSITIONED)
    result = runner.invoke(app, ["validate", str(spec)])
    assert result.exit_code == 0, result.output
    assert "valid" in result.stdout


def test_validate_authority_keys_fail_then_strip(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _POSITIONED, module_extra="  namespace: acme\n  owner: acme\n")
    # Without injection the stray identity keys trip extra=forbid → exit 1.
    assert runner.invoke(app, ["validate", str(spec)]).exit_code == 1
    # With --strip-identity they are stripped before validation → exit 0.
    ok = runner.invoke(app, ["validate", str(spec), "--strip-identity"])
    assert ok.exit_code == 0, ok.output


def test_compile_prints_digest(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _POSITIONED)
    result = runner.invoke(app, ["compile", str(spec), str(tmp_path / "out"), "--no-resolve"])
    assert result.exit_code == 0, result.output
    assert "digest: sha256:" in result.stdout
    assert (tmp_path / "out" / "manifest.json").is_file()


def test_compile_strict_fails_on_unresolved(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _RSID_ONLY)
    result = runner.invoke(app, ["compile", str(spec), str(tmp_path / "out"), "--no-resolve", "--strict"])
    assert result.exit_code == 1


def test_signature_command_prints_sha(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _POSITIONED)
    result = runner.invoke(app, ["signature", str(spec)])
    assert result.exit_code == 0, result.output
    assert "sha256:" in result.stdout


def test_reverse_roundtrips(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", _POSITIONED)
    runner.invoke(app, ["compile", str(spec), str(tmp_path / "out"), "--no-resolve"])
    result = runner.invoke(app, ["reverse", str(tmp_path / "out"), str(tmp_path / "rev"), "--version", "1.2.3"])
    assert result.exit_code == 0, result.output
    assert "version: 1.2.3" in (tmp_path / "rev" / "module_spec.yaml").read_text(encoding="utf-8")
