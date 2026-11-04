"""RM352: the release gate accepts a `toolchain` declaration only when a fixed-compiler sweep backs it.

polars 1 → 2 moves `parquet_bytes` on every module with no value wrong and nothing added. A record can
say so with `kind: toolchain`, and the gate must not take that on trust: a compiler bug moves bytes
without moving content too, and at a cut the compiler version changes together with polars, so a
"toolchains differ" read off the release sweep co-occurs with every move and separates nothing.

The only clean separation is a second sweep where the compiler is **held fixed** and only the toolchain
varies. So the gate reads that measurement's fields, never a sentence in `evidence`
(`@one-side-only-has-two-causes`): both sides stamped with the release being gated, both sides
recording a toolchain and the two differing, `content_signature` unmoved, and every module whose bytes
moved across the release moved under the toolchain alone too.

Real compiles of two reference examples, with the stamps and the digest moved by hand — the one thing a
single interpreter cannot produce. Each refusal below is the passing fixture with ONE condition broken.
"""

from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from just_dna_compiler.cli import app
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.sweep import (
    TOOLCHAIN_ACROSS_COMPILERS_PHRASE,
    TOOLCHAIN_CONTENT_MOVED_PHRASE,
    TOOLCHAIN_NOT_DIFFERENT_PHRASE,
    TOOLCHAIN_UNBACKED_PHRASE,
    TOOLCHAIN_UNEXPLAINED_PHRASE,
    TOOLCHAIN_WRONG_COMPILER_PHRASE,
    UNDECLARED_KIND_PHRASE,
    ModuleOutput,
    SweepMeasurement,
    compare_outputs,
    gate_findings,
    measurement_json,
    read_output,
)
from just_dna_format.release_records import DeclaredChange, ReleaseRecord
from just_dna_format.vocab import VALID_RELEASE_OUTPUT_AXES
from typer.testing import CliRunner

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_MODULES = ("hfe_hemochromatosis", "apoe_epsilon")
_PREVIOUS = "0.7.9"
_RELEASE = "0.8.0"
_OLD_POLARS = "1.44.2"
_NEW_POLARS = "2.1.0"


#: Where the module fixture compiled each example, so the CLI test can copy real parquets.
_COMPILED_DIRS: dict[str, Path] = {}


@pytest.fixture(scope="module")
def compiled(tmp_path_factory: pytest.TempPathFactory) -> dict[str, ModuleOutput]:
    root = tmp_path_factory.mktemp("rm352")
    outputs = {}
    for name in _MODULES:
        result = compile_module(_EXAMPLES / name, root / name)
        assert result.success, result.errors
        _COMPILED_DIRS[name] = result.output_dir
        outputs[name] = read_output(result.output_dir)
    return outputs


def _side(
    compiled: dict[str, ModuleOutput],
    release: str,
    polars: str | None,
    digest: str,
    content: dict[str, str] | None = None,
) -> dict[str, ModuleOutput]:
    """One side of a sweep: the real manifests, restamped. `polars=None` records no toolchain (0.7)."""
    side = {}
    for name, output in compiled.items():
        manifest = copy.deepcopy(output.manifest)
        manifest["compilation"]["compiler_version"] = f"just-dna-compiler {release}"
        if polars is None:
            manifest["compilation"].pop("toolchain", None)
        else:
            manifest["compilation"]["toolchain"] = {"polars": polars, "python": "3.13.1"}
        manifest["artifact"]["digest"] = f"sha256:{name}-{digest}"
        if content and name in content:
            manifest["content_signature"] = content[name]
        side[name] = ModuleOutput(name=name, manifest=manifest, parquet_schemas=output.parquet_schemas)
    return side


@dataclass
class _Cut:
    release: SweepMeasurement
    toolchain: SweepMeasurement


def _cut(
    compiled: dict[str, ModuleOutput],
    tc_before_release: str = _RELEASE,
    tc_before_polars: str | None = _OLD_POLARS,
    tc_before_content: dict[str, str] | None = None,
    after_content: dict[str, str] | None = None,
) -> _Cut:
    """The 0.8 cut's two sweeps, every condition met unless an argument breaks one.

    * release sweep: 0.7.9 (no toolchain recorded) → 0.8.0 on polars 2; bytes moved on every module.
    * toolchain sweep: 0.8.0 on polars 1.44.2 → the same 0.8.0 tree on polars 2.
    """
    previous = _side(compiled, _PREVIOUS, None, "old")
    tc_before = _side(compiled, tc_before_release, tc_before_polars, "polars1", tc_before_content)
    after = _side(compiled, _RELEASE, _NEW_POLARS, "polars2", after_content)
    return _Cut(release=compare_outputs(previous, after), toolchain=compare_outputs(tc_before, after))


def _record(*kinds: str) -> dict[str, ReleaseRecord]:
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    axes["parquet_bytes"] = True
    declared = [
        DeclaredChange(axis="parquet_bytes", target="parquet_bytes", kind=kind, detail=f"a {kind} move")
        for kind in kinds
    ]
    return {
        _RELEASE: ReleaseRecord(
            version=_RELEASE, previous=_PREVIOUS, axes=axes, declared=declared, evidence="synthetic 0.8.0"
        )
    }


def _gate(cut: _Cut, *kinds: str, backed: bool = True) -> list[str]:
    findings, _ = gate_findings(
        cut.release, _RELEASE, _record(*kinds), toolchain_measurement=cut.toolchain if backed else None
    )
    return findings


# ── the measurement records each side's toolchain as a field ─────────────────────────────────────


def test_a_sweep_records_each_sides_toolchain_and_the_unknown_arm(compiled: dict[str, ModuleOutput]) -> None:
    cut = _cut(compiled)

    assert cut.toolchain.before == cut.toolchain.after == _RELEASE
    assert cut.toolchain.before_toolchain == {"polars": _OLD_POLARS, "python": "3.13.1"}
    assert cut.toolchain.after_toolchain == {"polars": _NEW_POLARS, "python": "3.13.1"}
    # A 0.7 tree records none: the unknown arm, never an empty map.
    assert cut.release.before_toolchain is None
    payload = measurement_json(cut.toolchain)
    assert payload["before_toolchain"]["polars"] == _OLD_POLARS
    assert payload["after_toolchain"]["polars"] == _NEW_POLARS


def test_a_side_whose_modules_record_different_toolchains_records_none(
    compiled: dict[str, ModuleOutput],
) -> None:
    """A mixed tree is not one toolchain, so it answers the unknown arm rather than picking one."""
    after = _side(compiled, _RELEASE, _NEW_POLARS, "x")
    after["apoe_epsilon"].manifest["compilation"]["toolchain"]["polars"] = _OLD_POLARS

    assert compare_outputs(after, after).after_toolchain is None


# ── the gate: the one passing case, then each condition broken once ──────────────────────────────


def test_a_backed_toolchain_declaration_passes_the_gate(compiled: dict[str, ModuleOutput]) -> None:
    assert _gate(_cut(compiled), "toolchain") == []


def test_without_the_fixed_compiler_sweep_a_toolchain_declaration_is_refused(
    compiled: dict[str, ModuleOutput],
) -> None:
    findings = _gate(_cut(compiled), "toolchain", backed=False)

    assert any(TOOLCHAIN_UNBACKED_PHRASE in f for f in findings), findings


def test_a_backing_sweep_across_two_compilers_is_refused(compiled: dict[str, ModuleOutput]) -> None:
    """The addendum's arm: comparing across compiler versions cannot separate toolchain from compiler."""
    findings = _gate(_cut(compiled, tc_before_release=_PREVIOUS), "toolchain")

    assert any(TOOLCHAIN_ACROSS_COMPILERS_PHRASE in f for f in findings), findings


def test_a_backing_sweep_of_another_compiler_is_refused(compiled: dict[str, ModuleOutput]) -> None:
    """Fixed, but fixed at the wrong release: it says nothing about the compiler being gated."""
    cut = _cut(compiled)
    stale = compare_outputs(
        _side(compiled, _PREVIOUS, _OLD_POLARS, "a"), _side(compiled, _PREVIOUS, _NEW_POLARS, "b")
    )
    findings, _ = gate_findings(cut.release, _RELEASE, _record("toolchain"), toolchain_measurement=stale)

    assert any(TOOLCHAIN_WRONG_COMPILER_PHRASE in f for f in findings), findings


@pytest.mark.parametrize("polars", [_NEW_POLARS, None], ids=["same", "unrecorded"])
def test_a_backing_sweep_whose_toolchains_do_not_differ_is_refused(
    compiled: dict[str, ModuleOutput], polars: str | None
) -> None:
    """Equal toolchains explain nothing, and an unrecorded one is unknown — neither satisfies the gate."""
    findings = _gate(_cut(compiled, tc_before_polars=polars), "toolchain")

    assert any(TOOLCHAIN_NOT_DIFFERENT_PHRASE in f for f in findings), findings


def test_content_moved_under_the_toolchain_alone_is_refused(compiled: dict[str, ModuleOutput]) -> None:
    """The content-unchanged condition, mutated: a toolchain move is bytes only, by definition."""
    findings = _gate(_cut(compiled, tc_before_content={"apoe_epsilon": "sha256:" + "0" * 64}), "toolchain")

    assert any(TOOLCHAIN_CONTENT_MOVED_PHRASE in f and "apoe_epsilon" in f for f in findings), findings
    assert not any("hfe_hemochromatosis" in f for f in findings), findings


def test_content_moved_across_the_release_is_refused_for_a_module_the_toolchain_claims(
    compiled: dict[str, ModuleOutput],
) -> None:
    """The same condition on the release sweep: a module whose content moved is not a bytes-only move."""
    findings = _gate(_cut(compiled, after_content={"hfe_hemochromatosis": "sha256:" + "1" * 64}), "toolchain")

    assert any(TOOLCHAIN_CONTENT_MOVED_PHRASE in f and "hfe_hemochromatosis" in f for f in findings), findings


def test_a_module_the_toolchain_did_not_move_is_unexplained(compiled: dict[str, ModuleOutput]) -> None:
    """A module whose bytes moved across the release but not under the toolchain moved for a compiler
    reason, and a `toolchain`-only declaration does not cover it."""
    cut = _cut(compiled)
    still = _side(compiled, _RELEASE, _OLD_POLARS, "polars1")
    still["apoe_epsilon"].manifest["artifact"]["digest"] = "sha256:apoe_epsilon-polars2"
    toolchain = compare_outputs(still, _side(compiled, _RELEASE, _NEW_POLARS, "polars2"))
    findings, _ = gate_findings(cut.release, _RELEASE, _record("toolchain"), toolchain_measurement=toolchain)

    assert any(TOOLCHAIN_UNEXPLAINED_PHRASE in f and "apoe_epsilon" in f for f in findings), findings
    assert not any("hfe_hemochromatosis" in f for f in findings), findings

    # Declared beside an addition, the addition covers what the toolchain does not explain.
    covered, _ = gate_findings(
        cut.release, _RELEASE, _record("toolchain", "addition"), toolchain_measurement=toolchain
    )
    assert covered == []


def test_an_undeclared_byte_move_still_names_every_kind_that_could_cover_it(
    compiled: dict[str, ModuleOutput],
) -> None:
    findings = _gate(_cut(compiled))

    assert any(UNDECLARED_KIND_PHRASE in f and "toolchain" in f for f in findings), findings


# ── the CLI carries the second sweep ─────────────────────────────────────────────────────────────


def _write_tree(compiled: dict[str, ModuleOutput], side: dict[str, ModuleOutput], root: Path) -> Path:
    """Real compiled directories (parquets included) with each side's restamped manifest written in."""
    for name, output in side.items():
        shutil.copytree(_COMPILED_DIRS[name], root / name)
        (root / name / "manifest.json").write_text(json.dumps(output.manifest), encoding="utf-8")
    return root


def test_the_cli_reads_the_fixed_compiler_tree_beside_the_release_trees(
    compiled: dict[str, ModuleOutput], tmp_path: Path
) -> None:
    """`--toolchain-before` is the release's compiler on the old toolchain; AFTER is the other side.

    The CLI gates only against the shipped `RELEASE_RECORDS`, which hold no 0.8.0 entry (the cut
    writes it), so this asserts the measurement it carries; the gate itself is asserted above.
    """
    before = _write_tree(compiled, _side(compiled, _PREVIOUS, None, "old"), tmp_path / "before")
    tc_before = _write_tree(compiled, _side(compiled, _RELEASE, _OLD_POLARS, "polars1"), tmp_path / "tc")
    after = _write_tree(compiled, _side(compiled, _RELEASE, _NEW_POLARS, "polars2"), tmp_path / "after")

    result = CliRunner().invoke(
        app, ["sweep", str(before), str(after), "--toolchain-before", str(tc_before), "--json"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert (payload["before"], payload["after"]) == (_PREVIOUS, _RELEASE)
    backing = payload["toolchain_sweep"]
    assert backing["before"] == backing["after"] == _RELEASE
    assert backing["before_toolchain"]["polars"] == _OLD_POLARS
    assert backing["after_toolchain"]["polars"] == _NEW_POLARS
    assert backing["axes"]["parquet_bytes"] is True
    assert backing["axes"]["content_signature"] is False
