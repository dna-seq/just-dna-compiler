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


# ── verify / sign: the verify-then-install path (SPEC §5) ───────────────────────────────────────


def _compiled(tmp_path: Path) -> Path:
    spec = _spec(tmp_path / "spec", _POSITIONED)
    out = tmp_path / "out"
    assert runner.invoke(app, ["compile", str(spec), str(out)]).exit_code == 0
    return out


def test_verify_passes_on_a_freshly_compiled_module(tmp_path: Path) -> None:
    out = _compiled(tmp_path)
    result = runner.invoke(app, ["verify", str(out), "--no-require-marketplace"])
    assert result.exit_code == 0, result.output
    assert "verified" in result.stdout
    assert "signature: absent" in result.stdout  # unsigned verifies, and says so


def test_verify_rejects_a_locally_compiled_module_under_the_trust_gate(tmp_path: Path) -> None:
    # The default demands the marketplace stamp; a local build must not pass as a published one.
    result = runner.invoke(app, ["verify", str(_compiled(tmp_path))])
    assert result.exit_code == 1
    assert "VERIFY FAILED" in result.output


def test_verify_catches_a_tampered_artifact(tmp_path: Path) -> None:
    out = _compiled(tmp_path)
    target = out / "weights.parquet"
    target.write_bytes(target.read_bytes() + b"\x00")  # one byte is enough
    result = runner.invoke(app, ["verify", str(out), "--no-require-marketplace"])
    assert result.exit_code == 1
    assert "hash mismatch" in result.output and "weights.parquet" in result.output


def test_sign_then_verify_round_trips_and_a_wrong_key_fails(tmp_path: Path) -> None:
    from just_dna_format.signing import generate_private_key_pem, public_key_b64_from_pem

    out = _compiled(tmp_path)
    pem = generate_private_key_pem()
    key_path = tmp_path / "key.pem"
    key_path.write_bytes(pem)

    signed = runner.invoke(app, ["sign", str(out), "--private-key", str(key_path)])
    assert signed.exit_code == 0, signed.output

    good = runner.invoke(app, [
        "verify", str(out), "--no-require-marketplace",
        "--public-key", public_key_b64_from_pem(pem),
    ])
    assert good.exit_code == 0, good.output
    assert "verified against the pinned key" in good.stdout

    other = runner.invoke(app, [
        "verify", str(out), "--no-require-marketplace",
        "--public-key", public_key_b64_from_pem(generate_private_key_pem()),
    ])
    assert other.exit_code == 1
    assert "VERIFY FAILED" in other.output


def test_a_signature_does_not_survive_editing_the_artifact(tmp_path: Path) -> None:
    # The signature covers `artifact.digest`, which covers every file — so tampering after signing
    # cannot be papered over: the file hash fails first, and the digest would have moved anyway.
    from just_dna_format.signing import generate_private_key_pem, public_key_b64_from_pem

    out = _compiled(tmp_path)
    pem = generate_private_key_pem()
    (tmp_path / "key.pem").write_bytes(pem)
    runner.invoke(app, ["sign", str(out), "--private-key", str(tmp_path / "key.pem")])
    target = out / "studies.parquet"
    target.write_bytes(target.read_bytes() + b"\x00")

    result = runner.invoke(app, [
        "verify", str(out), "--no-require-marketplace", "--public-key", public_key_b64_from_pem(pem),
    ])
    assert result.exit_code == 1


def test_verify_without_a_manifest_is_a_clean_failure(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["verify", str(empty)])
    assert result.exit_code == 1
    assert "no manifest.json" in result.output
