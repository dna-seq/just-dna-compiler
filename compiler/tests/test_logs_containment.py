"""RM348 — `logs/` discovery stops trusting the filesystem.

RM338 widened what ships from `logs/` and RM337 named what stays behind, but both read whatever the
filesystem handed them, and a published file is permanent. Four instances of one class: a symlinked
`*.log` shipped even when it pointed outside the module; a `logs/` that is itself a symlink was walked
and everything under it shipped; text had no size ceiling and was read whole; and an unreadable file
raised out of the compile. The rule now: every path discovery considers must lie where it says it lies
inside the spec directory, so a symlink at any level stays behind with the symlink reason; every file
has one ceiling, `LOG_MAX_BYTES`, read from `stat` before any byte; and a file the compile cannot read
stays behind with its own reason. An explicit `log_files` list is unaffected.
"""

import os
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    LOG_IMAGE_MAX_BYTES,
    LOG_MAX_BYTES,
    LOG_NOT_SHIPPED_PHRASE,
    LOG_NOT_SHIPPED_REASONS,
    _log_left_behind_reason,
    compile_module,
)

_APOE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"
_CODE = "log_file_not_shipped"


def _apoe(tmp_path: Path) -> Path:
    spec = tmp_path / "apoe_epsilon"
    shutil.copytree(_APOE, spec)
    (spec / "logs").mkdir(exist_ok=True)
    return spec


def _outside(tmp_path: Path) -> Path:
    """A directory beside the module holding valid files of every shipping kind."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.log").write_text("not for publishing\n")
    (outside / "ledger.json").write_text('{"token": "not for publishing"}')
    (outside / "notes.md").write_text("# not for publishing\n")
    return outside


def _findings(warnings: list[str]) -> dict[str, str]:
    """`{path: line}` for every `log_file_not_shipped` line; the path is what precedes the phrase."""
    lines = [w for w in warnings if LOG_NOT_SHIPPED_PHRASE in w]
    by_path = {line.split(f" {LOG_NOT_SHIPPED_PHRASE}: ", 1)[0]: line for line in lines}
    assert len(by_path) == len(lines), "one finding per path, never two"
    return by_path


def _arms(line: str) -> set[str]:
    return {arm for arm, phrase in LOG_NOT_SHIPPED_REASONS.items() if phrase in line}


def _lock(path: Path, mode: int = 0) -> bool:
    """Make `path` unreadable; whether that took (root reads anything, and some filesystems ignore it)."""
    is_dir = path.is_dir()
    path.chmod(mode)
    return not os.access(path, os.R_OK | (os.X_OK if is_dir else 0))


def test_rm348_a_symlinked_log_under_logs_stays_behind(tmp_path: Path) -> None:
    spec = _apoe(tmp_path)
    outside = _outside(tmp_path)
    (spec / "logs" / "authoring.log").write_text("drafted rs429358\n")
    (spec / "logs" / "secret.log").symlink_to(outside / "secret.log")
    # A link that stays inside the module is refused too: the rule is "a symlink", not "outside".
    (spec / "logs" / "again.log").symlink_to(spec / "logs" / "authoring.log")
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success and result.manifest is not None, result.errors
    assert {e.name for e in result.manifest.logs} == {"logs/authoring.log"}
    assert not (out / "logs" / "secret.log").exists()
    assert not (out / "logs" / "again.log").exists()
    found = _findings(result.warnings)
    assert set(found) == {"logs/secret.log", "logs/again.log"}
    assert all(_arms(line) == {"symlink"} for line in found.values()), found


def test_rm348_a_symlinked_top_level_log_stays_behind(tmp_path: Path) -> None:
    spec = _apoe(tmp_path)
    outside = _outside(tmp_path)
    (spec / "run.log").write_text("aggregate run transcript\n")
    (spec / "linked.log").symlink_to(outside / "secret.log")
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success and result.manifest is not None, result.errors
    assert {e.name for e in result.manifest.logs} == {"run.log"}
    assert not (out / "linked.log").exists()
    found = _findings(result.warnings)
    assert set(found) == {"linked.log"}
    assert _arms(found["linked.log"]) == {"symlink"}


def test_rm348_a_logs_dir_that_is_a_symlink_is_not_walked(tmp_path: Path) -> None:
    spec = tmp_path / "apoe_epsilon"
    shutil.copytree(_APOE, spec)
    shutil.rmtree(spec / "logs", ignore_errors=True)
    outside = _outside(tmp_path)
    (spec / "logs").symlink_to(outside, target_is_directory=True)
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success and result.manifest is not None, result.errors
    assert result.manifest.logs == []
    assert not (out / "logs").exists()
    # One finding, naming `logs` itself: nothing under it is listed, since it is never walked.
    found = _findings(result.warnings)
    assert set(found) == {"logs"}
    assert _arms(found["logs"]) == {"symlink"}
    assert result.manifest.compilation.warnings_summary[_CODE] == 1


def test_rm348_a_path_under_a_linked_directory_is_judged_a_symlink(tmp_path: Path) -> None:
    # Discovery does not descend into a linked directory (it names the link itself), so this arm is
    # driven directly: a file whose own entry is not a link, but which is reached through one.
    spec = _apoe(tmp_path)
    outside = _outside(tmp_path)
    (spec / "logs" / "linked").symlink_to(outside, target_is_directory=True)
    for name in ("secret.log", "ledger.json", "notes.md"):
        path = spec / "logs" / "linked" / name
        assert not path.is_symlink()
        reason = _log_left_behind_reason(path, spec / "logs", spec)
        assert reason is not None and _arms(reason) == {"symlink"}, (name, reason)


def test_rm348_text_and_log_share_the_image_ceiling(tmp_path: Path) -> None:
    spec = _apoe(tmp_path)
    # Sparse files: the size is what `stat` reports, and none of these is read to decide it.
    for rel, size in {
        "logs/big.log": LOG_MAX_BYTES + 1,
        "logs/big.txt": LOG_MAX_BYTES + 1,
        "logs/edge.txt": LOG_MAX_BYTES,
        "logs/edge.log": LOG_MAX_BYTES,
        "huge.log": LOG_MAX_BYTES + 1,
    }.items():
        with (spec / rel).open("wb") as handle:
            handle.truncate(size)
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert result.success and result.manifest is not None, result.errors
    assert {e.name for e in result.manifest.logs} == {"logs/edge.txt", "logs/edge.log"}
    found = _findings(result.warnings)
    assert set(found) == {"logs/big.log", "logs/big.txt", "huge.log"}
    for line in found.values():
        assert _arms(line) == {"oversize"}, line
        assert f"({LOG_MAX_BYTES + 1} bytes, and the ceiling is {LOG_MAX_BYTES})" in line


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file whatever its mode")
def test_rm348_an_unreadable_file_stays_behind_instead_of_raising(tmp_path: Path) -> None:
    spec = _apoe(tmp_path)
    locked = {
        "logs/locked.log": b"a log the compile cannot read\n",
        "logs/locked.json": b'{"ok": 1}',
        "logs/locked.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 16,
        "locked.log": b"a top-level log the compile cannot read\n",
    }
    for rel, data in locked.items():
        (spec / rel).write_bytes(data)
        if not _lock(spec / rel):
            pytest.skip("this filesystem ignores the mode, so nothing can be made unreadable")
    (spec / "logs" / "authoring.log").write_text("drafted rs429358\n")
    # A directory the walk cannot list hides its files: it is named in their place. One has no
    # permission at all; the other may be listed but not searched, which hides its files just the same.
    sealed = {"logs/sealed": 0, "logs/listed-not-searched": 0o444}
    for rel, mode in sealed.items():
        (spec / rel).mkdir()
        (spec / rel / "ledger.json").write_text('{"ok": 1}')
        if not _lock(spec / rel, mode):
            pytest.skip("this filesystem ignores the mode, so nothing can be made unreadable")
    for strict in (False, True):
        out = tmp_path / f"out-{strict}"
        result = compile_module(spec, out, strict=strict)
        assert result.success and result.manifest is not None, result.errors
        assert {e.name for e in result.manifest.logs} == {"logs/authoring.log"}
        found = _findings(result.warnings)
        assert set(found) == set(locked) | set(sealed)
        assert all(_arms(line) == {"unreadable"} for line in found.values()), found
        assert result.manifest.compilation.warnings_summary[_CODE] == len(locked) + len(sealed)
    for rel in sealed:
        (spec / rel).chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a directory whatever its mode")
def test_rm348_an_unreadable_logs_dir_is_named(tmp_path: Path) -> None:
    spec = _apoe(tmp_path)
    (spec / "logs" / "authoring.log").write_text("drafted rs429358\n")
    if not _lock(spec / "logs"):
        pytest.skip("this filesystem ignores the mode, so nothing can be made unreadable")
    result = compile_module(spec, tmp_path / "out")
    (spec / "logs").chmod(0o755)
    assert result.success and result.manifest is not None, result.errors
    assert result.manifest.logs == []
    found = _findings(result.warnings)
    assert set(found) == {"logs"}
    assert _arms(found["logs"]) == {"unreadable"}


def test_rm348_an_explicit_list_still_ships_a_link(tmp_path: Path) -> None:
    # The rule is discovery's; an explicit `log_files` list ships what it names, as before.
    spec = _apoe(tmp_path)
    outside = _outside(tmp_path)
    (spec / "logs" / "secret.log").symlink_to(outside / "secret.log")
    result = compile_module(spec, tmp_path / "out", log_files=[spec / "logs" / "secret.log"])
    assert result.success and result.manifest is not None, result.errors
    assert [e.name for e in result.manifest.logs] == ["logs/secret.log"]
    assert _findings(result.warnings) == {}


def test_rm348_a_failed_open_is_the_unreadable_arm_whoever_runs_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The mode-based tests skip as root, where CI often runs. This one makes the open itself fail for
    # chosen paths, so the arm, and the compile surviving it, are exercised on every runner. Only the
    # filesystem's answer is replaced; the verdict and the compile run as they do for real.
    spec = _apoe(tmp_path)
    refused = {"logs/a.log", "logs/b.json", "logs/c.png", "top.log"}
    for rel in refused:
        (spec / rel).write_bytes(b"\x89PNG\r\n\x1a\n" if rel.endswith(".png") else b"{}\n")
    (spec / "logs" / "authoring.log").write_text("drafted rs429358\n")
    real_open = Path.open

    def refusing_open(self: Path, *args: object, **kwargs: object):  # noqa: ANN202
        if self.name in {Path(rel).name for rel in refused}:
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refusing_open)
    result = compile_module(spec, tmp_path / "out")
    assert result.success and result.manifest is not None, result.errors
    assert {e.name for e in result.manifest.logs} == {"logs/authoring.log"}
    found = _findings(result.warnings)
    assert set(found) == refused
    assert all(_arms(line) == {"unreadable"} for line in found.values()), found


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a directory whatever its mode")
def test_rm348_a_top_level_directory_named_log_stays_silent(tmp_path: Path) -> None:
    # A top-level `*.log` that is a directory is not a log, readable or not: it was skipped without a
    # word before RM348, and an unreadable one is not turned into a finding about logs.
    spec = _apoe(tmp_path)
    (spec / "archive.log").mkdir()
    if not _lock(spec / "archive.log"):
        pytest.skip("this filesystem ignores the mode, so nothing can be made unreadable")
    result = compile_module(spec, tmp_path / "out")
    (spec / "archive.log").chmod(0o755)
    assert result.success, result.errors
    assert _findings(result.warnings) == {}


def test_rm348_the_old_ceiling_name_still_reads() -> None:
    # `LOG_IMAGE_MAX_BYTES` is on `main`, which a 0.7 patch publishes, so 0.8 keeps it as an alias.
    assert LOG_IMAGE_MAX_BYTES == LOG_MAX_BYTES
