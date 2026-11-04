"""compile_module captures optional run/provenance logs into the module dir + manifest."""

import hashlib
import logging
from pathlib import Path

import pytest
import yaml
from just_dna_compiler.compiler import LOG_IMAGE_MAX_BYTES, compile_module
from just_dna_format.integrity import verify_manifest
from just_dna_format.manifest import read_manifest

_YAML = {
    "schema_version": "1.0",
    "module": {"name": "demo_mod", "title": "T", "description": "D", "report_title": "R"},
}
_VARIANTS = "rsid,genotype,weight,state,conclusion,gene,category\nrs1,A/G,0.1,neutral,ok,G,c\n"
_STUDIES = "rsid,pmid,population,p_value,conclusion,study_design\nrs1,1,T,0.05,E,U\n"


def _spec(tmp_path: Path, *, with_logs: bool) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(yaml.dump(_YAML))
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if with_logs:
        (spec / "run.log").write_text("aggregate run transcript\n")
        (spec / "logs").mkdir()
        (spec / "logs" / "researcher.log").write_text("researcher reasoning\n")
        (spec / "logs" / "reviewer.log").write_text("reviewer verdict\n")
    return spec


def test_no_logs_is_valid(tmp_path: Path) -> None:
    out = tmp_path / "out"
    manifest = compile_module(_spec(tmp_path, with_logs=False), out, resolve_with_ensembl=False).manifest
    assert manifest is not None and manifest.logs == []


def test_logs_discovered_copied_and_hashed(tmp_path: Path) -> None:
    spec = _spec(tmp_path, with_logs=True)
    out = tmp_path / "out"
    manifest = compile_module(
        spec, out, resolve_with_ensembl=False, compiled_by="marketplace-server"
    ).manifest
    assert manifest is not None
    by_name = {e.name: e for e in manifest.logs}
    assert set(by_name) == {"run.log", "logs/researcher.log", "logs/reviewer.log"}

    # Files were copied into the module dir, preserving the logs/ subfolder.
    assert (out / "run.log").is_file()
    assert (out / "logs" / "reviewer.log").is_file()

    # Hashes match the source bytes.
    expected = "sha256:" + hashlib.sha256((spec / "logs" / "reviewer.log").read_bytes()).hexdigest()
    assert by_name["logs/reviewer.log"].sha256 == expected

    # Logs are not part of the compiled-artifact digest.
    assert all(f.name.endswith(".parquet") for f in manifest.artifact.files)

    # Full verify (incl. logs) passes on the untampered module.
    verify_manifest(out, read_manifest(out / "manifest.json"), check_logs=True)


def test_logs_do_not_change_artifact_digest(tmp_path: Path) -> None:
    # Compile the same spec twice, once with logs and once without: identical artifact digest.
    without = compile_module(
        _spec(tmp_path / "a", with_logs=False), tmp_path / "oa", resolve_with_ensembl=False
    ).manifest
    with_logs = compile_module(
        _spec(tmp_path / "b", with_logs=True), tmp_path / "ob", resolve_with_ensembl=False
    ).manifest
    assert without.artifact.digest == with_logs.artifact.digest


# --- RM338: which files under `logs/` ship -------------------------------------------------------

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 32

# Every file RM338's decision ships (path under the spec dir -> bytes). `.log` ships whatever its
# bytes, as it did before RM338: `authoring.log` is ASCII, `legacy.log` carries a latin-1 byte.
_SHIPPED: dict[str, bytes] = {
    "logs/authoring.log": b"2026-11-04 drafted rs429358\n",
    "logs/legacy.log": "café résumé\n".encode("latin-1"),
    "logs/trace/session-a.jsonl": b'{"event": "search", "q": "APOE"}\n\n{"event": "fetch", "pmid": 1}\n',
    "logs/run.json": b'{"tool": "draft", "rows": 2}',
    "logs/notes.md": "# Notes\n\nThe ε4 allele.\n".encode(),
    "logs/notes.txt": b"plain notes\n",
    "logs/fig.png": _PNG,
    "logs/photo.jpg": _JPEG,
    "logs/scan.jpeg": _JPEG,
    "logs/UPPER.JSON": b"[1, 2, 3]",
}

# Every file that stays behind: each fails exactly one check, or carries an extension never shipped.
_LEFT_BEHIND: dict[str, bytes] = {
    "logs/bad.json": b'{"tool": "draft",',
    "logs/bad.jsonl": b'{"ok": 1}\n{"ok": \n',
    "logs/fake.png": b"GIF89a" + b"\x00" * 32,
    "logs/fake.jpg": _PNG,
    "logs/x.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    "logs/latin1.txt": "café\n".encode("latin-1"),
    "logs/latin1.md": "café\n".encode("latin-1"),
    "logs/latin1.json": '{"a": "café"}'.encode("latin-1"),
    "logs/data.bin": b"\x00\x01\x02",
    "logs/archive.zip": b"PK\x03\x04",
}


def _write_files(spec: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        dest = spec / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _png_of_size(spec: Path, rel: str, size: int) -> str:
    """A real PNG of exactly `size` bytes: its magic matches, so only the size check can refuse it."""
    (spec / rel).write_bytes(_PNG + b"\x00" * (size - len(_PNG)))
    return rel


def _rm338_spec(tmp_path: Path) -> tuple[Path, set[str], set[str]]:
    spec = _spec(tmp_path, with_logs=False)
    _write_files(spec, _SHIPPED)
    _write_files(spec, _LEFT_BEHIND)
    shipped = set(_SHIPPED) | {_png_of_size(spec, "logs/edge.png", LOG_IMAGE_MAX_BYTES)}
    left_behind = set(_LEFT_BEHIND) | {_png_of_size(spec, "logs/big.png", LOG_IMAGE_MAX_BYTES + 1)}
    return spec, shipped, left_behind


def test_rm338_logs_dir_ships_content_checked_text_and_images(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spec, shipped, left_behind = _rm338_spec(tmp_path)
    out = tmp_path / "out"
    caplog.set_level(logging.INFO, logger="just_dna_compiler.compiler")
    result = compile_module(spec, out, resolve_with_ensembl=False, compiled_by="marketplace-server")
    assert result.success, result.errors
    manifest = result.manifest
    assert manifest is not None

    assert {e.name for e in manifest.logs} == shipped
    on_disk = {p.relative_to(out).as_posix() for p in (out / "logs").rglob("*") if p.is_file()}
    assert on_disk == shipped

    # Shipped bytes are the source bytes, and every entry verifies.
    for entry in manifest.logs:
        assert (out / entry.name).read_bytes() == (spec / entry.name).read_bytes()
    verify_manifest(out, read_manifest(out / "manifest.json"), check_logs=True)

    # Each newly shipped file that is not `*.log` is named by an info line; nothing left behind is.
    messages = [r.getMessage() for r in caplog.records if r.name == "just_dna_compiler.compiler"]
    named = {rel for rel in shipped | left_behind if any(rel in m for m in messages)}
    assert named == {rel for rel in shipped if not rel.endswith(".log")}


def test_rm338_adds_no_warning(tmp_path: Path) -> None:
    # The warning for what stays behind is RM337's, a minor: this patch adds no warning at all.
    plain = _spec(tmp_path / "a", with_logs=False)
    _write_files(plain, {"logs/authoring.log": _SHIPPED["logs/authoring.log"]})
    baseline = compile_module(plain, tmp_path / "oa", resolve_with_ensembl=False)
    full, _, _ = _rm338_spec(tmp_path / "b")
    widened = compile_module(full, tmp_path / "ob", resolve_with_ensembl=False)
    assert baseline.success and widened.success
    assert baseline.manifest is not None and widened.manifest is not None
    assert widened.warnings == baseline.warnings
    assert widened.manifest.compilation.warnings_summary == baseline.manifest.compilation.warnings_summary


def test_rm338_logs_do_not_change_either_identity(tmp_path: Path) -> None:
    without = compile_module(
        _spec(tmp_path / "a", with_logs=False), tmp_path / "oa", resolve_with_ensembl=False
    ).manifest
    full, _, _ = _rm338_spec(tmp_path / "b")
    with_logs = compile_module(full, tmp_path / "ob", resolve_with_ensembl=False).manifest
    assert without is not None and with_logs is not None
    assert with_logs.logs
    assert without.artifact.digest == with_logs.artifact.digest
    assert without.content_signature == with_logs.content_signature


def test_rm338_top_level_discovery_is_unchanged(tmp_path: Path) -> None:
    # Beside the spec only `*.log` is discovered, as before: the widening is under `logs/` alone.
    spec = _spec(tmp_path, with_logs=False)
    (spec / "run.log").write_text("aggregate\n")
    (spec / "notes.md").write_text("# not a log\n")
    (spec / "run.json").write_text("{}")
    manifest = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False).manifest
    assert manifest is not None
    assert {e.name for e in manifest.logs} == {"run.log"}


def test_rm338_explicit_log_files_are_unaffected(tmp_path: Path) -> None:
    # An explicit list ships what it names, checked or not, and discovery adds nothing to it.
    spec, _, _ = _rm338_spec(tmp_path)
    named = [spec / "logs" / "x.svg", spec / "logs" / "bad.json"]
    manifest = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False, log_files=named).manifest
    assert manifest is not None
    assert [e.name for e in manifest.logs] == ["logs/x.svg", "logs/bad.json"]
