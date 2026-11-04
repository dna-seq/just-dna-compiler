"""RM342: the manifest records the toolchain that wrote the bytes, and the sweep names it as a reason.

From polars 2 the parquet footer names the polars release that wrote it, so two installs of one
`compiler_version` mint different `artifact.digest`s for equal content. `compilation.toolchain` records
which Python and which polars wrote these bytes, and wherever a fresh compile is compared with a recorded
digest a difference the two toolchains explain is reported as `toolchain_differs` rather than as a
plain mismatch. Every expected version here is read from the running interpreter, never typed.
"""

from __future__ import annotations

import copy
import platform
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.sweep import (
    ModuleOutput,
    changed_manifest_fields,
    compare_module,
    compare_outputs,
    measurement_json,
    read_output,
)
from just_dna_format.manifest import TOOLCHAIN_DIFFERS, read_manifest

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_EXAMPLE = _EXAMPLES / "hfe_hemochromatosis"


def _running_toolchain() -> dict[str, str]:
    return {"polars": pl.__version__, "python": platform.python_version()}


def test_compile_stamps_the_running_toolchain(tmp_path: Path) -> None:
    result = compile_module(_EXAMPLE, tmp_path / "out")
    assert result.success, result.errors

    manifest = read_manifest(result.output_dir / "manifest.json")

    assert manifest.compilation.toolchain == _running_toolchain()


def test_the_toolchain_survives_a_round_trip_and_moves_no_digest(tmp_path: Path) -> None:
    """Principle 7: compile → reverse → compile in one environment is a fixed point, toolchain included."""
    first = compile_module(_EXAMPLE, tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert first.success and second.success, (first.errors, second.errors)

    one = read_manifest(first.output_dir / "manifest.json")
    two = read_manifest(second.output_dir / "manifest.json")

    assert one.compilation.toolchain == two.compilation.toolchain == _running_toolchain()
    assert one.artifact.digest == two.artifact.digest
    assert one.content_signature == two.content_signature


# ── the sweep ────────────────────────────────────────────────────────────────────────────────────


def _pair(tmp_path: Path) -> tuple[ModuleOutput, ModuleOutput]:
    """Two real compiles of one spec, the second restamped as a different release.

    The two compiles share one environment, so their digests agree; each test then moves the digest
    and the recorded toolchains by hand, which is the one thing a single interpreter cannot produce.
    """
    before = read_output(compile_module(_EXAMPLE, tmp_path / "before").output_dir)
    after = read_output(compile_module(_EXAMPLE, tmp_path / "after").output_dir)
    after = ModuleOutput(
        name=after.name, manifest=copy.deepcopy(after.manifest), parquet_schemas=after.parquet_schemas
    )
    after.manifest["compilation"]["compiler_version"] = "just-dna-compiler 99.0.0"
    return before, after


def _move_digest(output: ModuleOutput) -> None:
    output.manifest["artifact"]["digest"] = "sha256:" + "f" * 64


def test_a_digest_moved_under_a_different_polars_is_reported_as_toolchain_differs(tmp_path: Path) -> None:
    before, after = _pair(tmp_path)
    _move_digest(after)
    after.manifest["compilation"]["toolchain"]["polars"] = "1.39.0"

    delta = compare_module(before, after)

    assert delta.axes["parquet_bytes"] is True
    assert delta.toolchain_differs is True
    assert delta.bytes_reason == TOOLCHAIN_DIFFERS
    measurement = compare_outputs({"hfe": before}, {"hfe": after})
    assert measurement.moved_under_other_toolchain == (after.name,)
    assert measurement.modules == ("hfe",)
    assert TOOLCHAIN_DIFFERS in measurement.evidence
    assert measurement_json(measurement)["per_module"][0]["bytes_reason"] == TOOLCHAIN_DIFFERS
    assert measurement_json(measurement)["moved_under_other_toolchain"] == [after.name]


def test_a_manifest_recording_no_toolchain_keeps_the_plain_movement(tmp_path: Path) -> None:
    """An older manifest is the unknown arm: nothing explains the movement, so nothing is claimed."""
    before, after = _pair(tmp_path)
    _move_digest(after)
    del before.manifest["compilation"]["toolchain"]

    delta = compare_module(before, after)

    assert delta.axes["parquet_bytes"] is True
    assert delta.toolchain_differs is None
    assert delta.bytes_reason is None
    measurement = compare_outputs({"hfe": before}, {"hfe": after})
    assert measurement.moved_under_other_toolchain == ()
    assert TOOLCHAIN_DIFFERS not in measurement.evidence


def test_the_same_toolchain_and_a_different_digest_keeps_the_plain_movement(tmp_path: Path) -> None:
    before, after = _pair(tmp_path)
    _move_digest(after)

    delta = compare_module(before, after)

    assert delta.axes["parquet_bytes"] is True
    assert delta.toolchain_differs is False
    assert delta.bytes_reason is None


def test_a_different_toolchain_with_equal_digests_names_no_reason(tmp_path: Path) -> None:
    """The reason explains a movement; with no movement there is nothing for it to explain."""
    before, after = _pair(tmp_path)
    after.manifest["compilation"]["toolchain"]["python"] = "3.0.0"

    delta = compare_module(before, after)

    assert delta.axes["parquet_bytes"] is False
    assert delta.toolchain_differs is True
    assert delta.bytes_reason is None


def test_the_toolchain_never_counts_as_a_changed_manifest_field(tmp_path: Path) -> None:
    """It moves whenever the install does, the `compiler_version` trap one field over."""
    before, after = _pair(tmp_path)
    after.manifest["compilation"]["toolchain"] = {"polars": "1.39.0", "python": "3.0.0", "pyarrow": "1.0"}

    assert changed_manifest_fields(before.manifest, after.manifest) == ()
    del after.manifest["compilation"]["toolchain"]
    assert changed_manifest_fields(before.manifest, after.manifest) == ()
