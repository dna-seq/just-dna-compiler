"""RM337 — a coded warning names each file under `logs/` that discovery leaves behind, and why.

RM338 widened what ships from `logs/` (checked text and images) and left everything else behind
without a word. The registry compiles a module by discovery on its own server, so an author uploading a
`notes.svg` or a ledger with one bad line learned nothing until the published version turned out not to
carry it. `log_file_not_shipped` is that word: one finding per file, in both modes, never a refusal,
naming the path and the reason.

The reason comes from the same function that decides the verdict (`_log_left_behind_reason`), so the
two cannot drift; and its arms are walked here pairwise, because a later arm inheriting an earlier
arm's sentence raises nothing and reads as a diagnosis (`@answered-is-not-absent`).
"""

import itertools
import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.cli import app
from just_dna_compiler.compiler import (
    LOG_IMAGE_MAX_BYTES,
    LOG_NOT_SHIPPED_PHRASE,
    LOG_NOT_SHIPPED_REASONS,
    _log_left_behind_reason,
    compile_module,
)
from typer.testing import CliRunner

_APOE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"
_CODE = "log_file_not_shipped"

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 32

#: Files under `logs/` that ship (RM338's decision): no warning names any of them.
_SHIPPED: dict[str, bytes] = {
    "logs/authoring.log": b"2026-11-04 drafted rs429358\n",
    "logs/legacy.log": "café\n".encode("latin-1"),
    "logs/trace/session-a.jsonl": b'{"event": "search"}\n\n{"event": "fetch"}\n',
    "logs/run.json": b'{"tool": "draft", "rows": 2}',
    "logs/notes.md": "# Notes\n\nThe ε4 allele.\n".encode(),
    "logs/notes.txt": b"plain notes\n",
    "logs/fig.png": _PNG,
    "logs/photo.jpg": _JPEG,
    "logs/.history/old.log": b"a hidden .log ships, as it always did\n",
}

#: Files under `logs/` that stay behind, each with the arm that must explain it.
_LEFT_BEHIND: dict[str, tuple[bytes, str]] = {
    "logs/x.svg": (b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', "svg"),
    "logs/data.bin": (b"\x00\x01\x02", "extension"),
    "logs/NOTES": (b"no extension at all\n", "extension"),
    "logs/latin1.txt": ("café\n".encode("latin-1"), "not_utf8"),
    # A byte-order mark then a bad byte at file offset 5: the offset named is the file's own, not one
    # counted from after the mark. The space in the name is part of the path the warning names.
    "logs/bom notes.md": (b"\xef\xbb\xbfab\xff\n", "not_utf8"),
    "logs/bad.json": (b'{"tool": "draft",', "json"),
    "logs/deep.json": (b"[" * 200_000 + b"]" * 200_000, "json"),
    # Line 3 is the first bad one; line 2 is blank and counts as a line all the same.
    "logs/bad.jsonl": (b'{"ok": 1}\n\n{"ok": \n{"ok": 2}\n', "jsonl"),
    "logs/fake.png": (b"GIF89a" + b"\x00" * 32, "magic"),
    "logs/fake.jpg": (_PNG, "magic"),
    "logs/.ipynb_checkpoints/notes-checkpoint.md": (b"# checkpoint\n", "hidden_path"),
    "logs/.hidden.svg": (b"<svg/>", "hidden_path"),
}


def _write(spec: Path, files: dict[str, bytes]) -> None:
    for rel, data in files.items():
        dest = spec / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _apoe_with_logs(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A copy of `apoe_epsilon` carrying every class of file under `logs/`; returns `{left behind: arm}`."""
    spec = tmp_path / "apoe_epsilon"
    shutil.copytree(_APOE, spec)
    _write(spec, _SHIPPED)
    _write(spec, {rel: data for rel, (data, _) in _LEFT_BEHIND.items()})
    expected = {rel: arm for rel, (_, arm) in _LEFT_BEHIND.items()}
    (spec / "logs" / "big.png").write_bytes(_PNG + b"\x00" * (LOG_IMAGE_MAX_BYTES + 1 - len(_PNG)))
    expected["logs/big.png"] = "oversize"
    outside = tmp_path / "outside.json"
    outside.write_text('{"token": "not for publishing"}')
    (spec / "logs" / "linked.json").symlink_to(outside)
    expected["logs/linked.json"] = "symlink"
    # A dangling link named `.log` and a link to a directory are symlinks too, and stay behind.
    (spec / "logs" / "gone.log").symlink_to(tmp_path / "does-not-exist.log")
    expected["logs/gone.log"] = "symlink"
    (spec / "logs" / "elsewhere").symlink_to(tmp_path, target_is_directory=True)
    expected["logs/elsewhere"] = "symlink"
    return spec, expected


def _not_shipped_lines(warnings: list[str]) -> list[str]:
    return [w for w in warnings if LOG_NOT_SHIPPED_PHRASE in w]


def _path(line: str) -> str:
    """The path a finding names: everything before the pinned phrase, spaces included."""
    return line.split(f" {LOG_NOT_SHIPPED_PHRASE}: ", 1)[0]


def test_the_phrase_is_pinned() -> None:
    # A consumer greps the manifest's warnings for it (`@warning-text-is-api`).
    assert LOG_NOT_SHIPPED_PHRASE == "does not ship with the module"


@pytest.mark.parametrize("strict", [False, True], ids=["best_effort", "strict"])
def test_rm337_each_file_left_behind_is_named_once_with_its_reason(tmp_path: Path, strict: bool) -> None:
    baseline = compile_module(_APOE, tmp_path / "baseline", strict=strict)
    spec, expected = _apoe_with_logs(tmp_path)
    result = compile_module(spec, tmp_path / "out", strict=strict)
    assert baseline.success and result.success, result.errors
    manifest = result.manifest
    assert manifest is not None and baseline.manifest is not None

    # What ships is RM338's set, unchanged by the warning.
    assert {e.name for e in manifest.logs} == set(_SHIPPED)

    lines = _not_shipped_lines(result.warnings)
    named = {_path(line) for line in lines}
    assert named == set(expected)
    assert len(lines) == len(expected), "one finding per file, never two"
    for line in lines:
        rel = _path(line)
        own = LOG_NOT_SHIPPED_REASONS[expected[rel]]
        others = {arm for arm, phrase in LOG_NOT_SHIPPED_REASONS.items() if phrase in line}
        assert others == {expected[rel]}, (line, others)
        assert line.startswith(f"{rel} {LOG_NOT_SHIPPED_PHRASE}: ")
        assert own in line

    # The details the reason owes: the first bad `.jsonl` line, and both sizes for an image.
    by_path = {_path(line): line for line in lines}
    assert "line 3" in by_path["logs/bad.jsonl"]
    assert "at offset 3)" in by_path["logs/latin1.txt"]
    assert "at offset 5)" in by_path["logs/bom notes.md"]
    assert str(LOG_IMAGE_MAX_BYTES + 1) in by_path["logs/big.png"]
    assert str(LOG_IMAGE_MAX_BYTES) in by_path["logs/big.png"].replace(str(LOG_IMAGE_MAX_BYTES + 1), "")

    # It reaches the manifest, counted, and nothing else in the channel moved.
    assert manifest.compilation.warnings_summary[_CODE] == len(expected)
    assert _not_shipped_lines(manifest.compilation.warnings) == lines
    assert [w for w in result.warnings if w not in lines] == baseline.warnings
    rest = dict(manifest.compilation.warnings_summary)
    del rest[_CODE]
    assert rest == baseline.manifest.compilation.warnings_summary
    # Actionable: an author clears it by fixing, renaming or removing the file.
    assert not set(lines) & set(manifest.compilation.carried)

    # Neither identity moves: logs are outside the artifact and the authored content.
    assert manifest.artifact.digest == baseline.manifest.artifact.digest
    assert manifest.content_signature == baseline.manifest.content_signature


def test_rm337_the_reason_arms_are_pairwise_distinct(tmp_path: Path) -> None:
    phrases = list(LOG_NOT_SHIPPED_REASONS.values())
    assert len(set(phrases)) == len(phrases)
    for a, b in itertools.permutations(phrases, 2):
        assert a not in b, (a, b)

    spec, expected = _apoe_with_logs(tmp_path)
    logs_dir = spec / "logs"
    # Every arm is reached by at least one file, so the walk is over the arms and not a sample.
    assert set(expected.values()) == set(LOG_NOT_SHIPPED_REASONS)
    for rel, arm in expected.items():
        reason = _log_left_behind_reason(spec / rel, logs_dir)
        assert reason is not None, rel
        hit = {name for name, phrase in LOG_NOT_SHIPPED_REASONS.items() if phrase in reason}
        assert hit == {arm}, (rel, reason)
    for rel in _SHIPPED:
        assert _log_left_behind_reason(spec / rel, logs_dir) is None, rel


def test_rm337_reason_text_is_stable_across_laps(tmp_path: Path) -> None:
    # The text reaches `manifest.json`, which the release sweep compares: it may not carry an
    # interpreter's own error message, only what the bytes decide.
    spec, _ = _apoe_with_logs(tmp_path)
    first = _not_shipped_lines(compile_module(spec, tmp_path / "a").warnings)
    second = _not_shipped_lines(compile_module(spec, tmp_path / "b").warnings)
    assert first == second
    deep = next(line for line in first if line.startswith("logs/deep.json "))
    assert "recursion" not in deep.lower()


def test_rm337_an_explicit_log_files_list_draws_no_warning(tmp_path: Path) -> None:
    # It ships what it names, checked or not, and discovery does not run.
    spec, _ = _apoe_with_logs(tmp_path)
    named = [spec / "logs" / "x.svg"]
    result = compile_module(spec, tmp_path / "out", log_files=named)
    assert result.success and result.manifest is not None
    assert [e.name for e in result.manifest.logs] == ["logs/x.svg"]
    assert _not_shipped_lines(result.warnings) == []
    assert _CODE not in result.manifest.compilation.warnings_summary


def test_rm337_the_top_level_is_out_of_scope(tmp_path: Path) -> None:
    # Beside the spec only `*.log` is discovered (RM338 left the top level as it was), and a file
    # there that is not `*.log` is the spec directory's ordinary tolerance of unknown files, not a log.
    spec = tmp_path / "apoe_epsilon"
    shutil.copytree(_APOE, spec)
    (spec / "notes.md").write_text("# notes\n")
    (spec / "run.json").write_text(json.dumps({"a": 1}))
    result = compile_module(spec, tmp_path / "out")
    assert result.success
    assert _not_shipped_lines(result.warnings) == []


def test_rm337_the_cli_prints_each_finding(tmp_path: Path) -> None:
    spec, expected = _apoe_with_logs(tmp_path)
    for flags in ([], ["--strict"]):
        out = tmp_path / ("out" + "".join(flags))
        result = CliRunner().invoke(app, ["compile", str(spec), str(out), *flags])
        assert result.exit_code == 0, result.output
        printed = [
            line.strip().removeprefix("warning: ")
            for line in result.output.splitlines()
            if LOG_NOT_SHIPPED_PHRASE in line
        ]
        assert {_path(line) for line in printed} == set(expected)
        assert len(printed) == len(expected)
