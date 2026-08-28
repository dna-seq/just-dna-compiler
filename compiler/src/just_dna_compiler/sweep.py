"""
The instrument behind the release record (RM126): measure what a release changed about compiled
output, and fail a release whose measurement carries no declaration.

`just_dna_format.release_records` holds the table and the pure function a consumer reads. This module
holds the half that cannot live in the format tier, because producing a record means **compiling**.

**Why a measurement and not a hand-kept map.** The map was the first thing everybody proposed and the
first thing rejected: it is the defect wearing a public name. Five of the six RM104–RM111 fixes were a
derived value restated by hand, and a per-release map of what a release changed is that shape exactly.
So the sweep measures, the gate refuses a measured change nobody declared, and the declaration is
forced by the measurement rather than remembered by the author.

**What it compares.** Two trees of *compiled output* — one produced by the previous release, one by
this one, from **the same spec inputs**. Feeding each side its own tree's `reference_examples/` would
measure spec drift as compiler drift; the discipline is one spec root, two compilers. The comparison
itself needs only this tier: a manifest is JSON and a parquet schema is a polars read.

**Scope, and it is narrower than "what a release changed".** Compiler-derived outputs only. The
enricher's sidecars are **unmeasured**, which is not the same claim as unchanged, and
`release_records` says so in the record it publishes.

Run it in the release sequence, not as an ordinary test: it needs the previous release actually
installed. COMPILER.md § The release-record sweep carries the exact command sequence.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
from just_dna_format.release_records import (
    EXCLUDED_MANIFEST_FIELDS,
    RELEASE_RECORDS,
    ReleaseRecord,
    release_version,
)
from just_dna_format.vocab import VALID_RELEASE_OUTPUT_AXES

from just_dna_compiler.compiler import compile_module

logger = logging.getLogger(__name__)

# ── Gate findings a caller keys on. A phrase is an API here for the same reason a warning's is:
# the release sequence greps them, and a CI job that pins one must not break on a reword. ─────────
NO_RECORD_PHRASE = "has no release record"
UNDECLARED_AXIS_PHRASE = "moved and the release record does not record it moving"
UNDECLARED_FIELD_PHRASE = "moved and the release record does not list it"
UNDECLARED_KIND_PHRASE = "moved and nothing declares it a correction or an addition"
WRONG_PREVIOUS_PHRASE = "was measured against a release the record does not name"
OVERDECLARED_NOTE_PHRASE = "is declared and this sweep did not see it move"


@dataclass(frozen=True)
class ModuleOutput:
    """One compiled module as the sweep reads it: the manifest, and every parquet's column types."""

    name: str
    manifest: dict[str, Any]
    parquet_schemas: dict[str, dict[str, str]]

    @property
    def compiler_version(self) -> str | None:
        compilation = self.manifest.get("compilation")
        return compilation.get("compiler_version") if isinstance(compilation, dict) else None


@dataclass(frozen=True)
class ModuleDelta:
    """What moved for one module across the interval, per axis."""

    name: str
    axes: dict[str, bool]
    manifest_fields: tuple[str, ...]
    warnings_added: tuple[str, ...]
    warnings_removed: tuple[str, ...]


@dataclass(frozen=True)
class SweepMeasurement:
    """The union across every module the sweep could measure, plus the ones it could not.

    `unmeasured` is not cosmetic. A module present on one side only is a module this sweep says
    nothing about, and rolling it silently into an all-`False` result would be the silence the record
    exists to replace.
    """

    before: str
    after: str
    axes: dict[str, bool]
    manifest_fields: tuple[str, ...]
    modules: tuple[str, ...]
    unmeasured: tuple[str, ...]
    per_module: tuple[ModuleDelta, ...]

    @property
    def moved_counts(self) -> dict[str, int]:
        """How many of the measured modules moved on each axis — the denominator is `modules`.

        Computed and **published**, not computed and discarded: an axis that reads `False` on the
        record is a measured zero, and a zero with no denominator beside it is the shape a consumer
        cannot check.
        """
        return {
            axis: sum(1 for delta in self.per_module if delta.axes[axis])
            for axis in sorted(self.axes)
        }

    @property
    def evidence(self) -> str:
        """The sentence a `ReleaseRecord.evidence` carries — what was compiled, and what was not."""
        counts = ", ".join(
            f"{axis} {moved}/{len(self.modules)}" for axis, moved in self.moved_counts.items()
        )
        parts = [
            f"{len(self.modules)} reference module(s) compiled under {self.before} and {self.after} "
            f"from one spec root, so the compiler is the only variable",
            f"modules moved per axis: {counts}",
        ]
        if self.unmeasured:
            parts.append(f"unmeasured (present on one side only): {', '.join(self.unmeasured)}")
        return "; ".join(parts)

    def as_record(self, version: str, previous: str) -> ReleaseRecord:
        """The measured half of a record, ready for the declared half to be written onto it.

        Produces a record with an **empty** `declared` list on purpose: the gate then refuses it
        until somebody says whether each moved value was wrong or merely absent, which is the whole
        mechanism that keeps this from becoming a map somebody maintains by memory.
        """
        return ReleaseRecord(
            version=version,
            previous=previous,
            axes=dict(self.axes),
            manifest_fields=list(self.manifest_fields),
            declared=[],
            evidence=self.evidence,
        )


def _parquet_schema(path: Path) -> dict[str, str]:
    """`{column: dtype}` for one parquet, read without materialising a row."""
    schema = pl.scan_parquet(path).collect_schema()
    return {name: str(dtype) for name, dtype in schema.items()}


def read_output(module_dir: Path) -> ModuleOutput:
    """Read one compiled module directory — `manifest.json` plus every parquet beside it."""
    manifest = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))
    schemas = {path.name: _parquet_schema(path) for path in sorted(module_dir.glob("*.parquet"))}
    return ModuleOutput(name=module_dir.name, manifest=manifest, parquet_schemas=schemas)


def read_outputs(root: Path) -> dict[str, ModuleOutput]:
    """Every compiled module under `root`, keyed by directory name."""
    found = {
        child.name: read_output(child)
        for child in sorted(root.iterdir())
        if child.is_dir() and (child / "manifest.json").is_file()
    }
    if not found:
        raise ValueError(f"no compiled modules found under {root}")
    return found


def build_outputs(spec_root: Path, out_root: Path) -> dict[str, ModuleOutput]:
    """Compile every spec directory under `spec_root` into `out_root/<name>/` with THIS compiler.

    Discovery rather than a list, the same rule `test_reference_examples_roundtrip` follows: a spec
    added without being added here is a spec nobody sweeps, and adding one is precisely when a new
    shape arrives.
    """
    specs = sorted(d for d in spec_root.iterdir() if (d / "module_spec.yaml").is_file())
    if not specs:
        raise ValueError(f"no module specs found under {spec_root}")
    built: dict[str, ModuleOutput] = {}
    for spec in specs:
        result = compile_module(spec, out_root / spec.name)
        if not result.success:
            logger.warning("sweep: %s did not compile: %s", spec.name, "; ".join(result.errors))
            continue
        built[spec.name] = read_output(out_root / spec.name)
    return built


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """A manifest as `{dotted path: leaf}`, with a **list treated as a leaf**.

    Indexing into a list would make an inserted element rename every path after it, so a list is
    compared whole — which is also what a consumer keying on `stats.genes` actually reads.
    """
    if isinstance(value, dict):
        flat: dict[str, Any] = {}
        for key, inner in value.items():
            flat.update(_flatten(inner, f"{prefix}.{key}" if prefix else str(key)))
        return flat
    return {prefix: value}


def _is_excluded(path: str) -> bool:
    return any(
        path == excluded or path.startswith(f"{excluded}.") for excluded in EXCLUDED_MANIFEST_FIELDS
    )


#: `None` is a legitimate manifest value — an unset optional block reads as `null` — so a missing key
#: must be a *different* value from a present `null`. `dict.get(path)` cannot tell them apart, and
#: with it a block appearing where there was a `null` (`literature: null` → the RM119 counters) reads
#: as unchanged on the `literature` path itself. `None` is never absent, the same way it is never
#: `False`.
_ABSENT: object = object()


def changed_manifest_fields(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, ...]:
    """The published manifest paths that moved, with `EXCLUDED_MANIFEST_FIELDS` never among them."""
    flat_before = _flatten(before)
    flat_after = _flatten(after)
    paths = set(flat_before) | set(flat_after)
    moved = {
        path
        for path in paths
        if not _is_excluded(path)
        and flat_before.get(path, _ABSENT) != flat_after.get(path, _ABSENT)
    }
    return tuple(sorted(moved))


def _warning_lists(manifest: dict[str, Any]) -> list[str]:
    compilation = manifest.get("compilation")
    return list(compilation.get("warnings", [])) if isinstance(compilation, dict) else []


def compare_module(before: ModuleOutput, after: ModuleOutput) -> ModuleDelta:
    """The per-axis movement for one module.

    **The `warnings` axis is computed apart and reported apart**, and it is not folded into
    `manifest_fields` however published `compilation.warnings` is. A release that reworks the warning
    channel would otherwise report *a manifest field changed* on every module in a catalogue, and a
    registry acting on that mints an immutable PATCH for a message change.

    Today the axis fires on any change to the set. **When RM131's `carried` split lands it becomes
    the discriminator this needs**: a finding the author cannot clear moving is noise, and one they
    can clear appearing is not. The seam is here — `warnings_added` and `warnings_removed` are kept
    separately for exactly that, so classifying them is a change to this function and to nothing
    else.
    """
    before_warnings = set(_warning_lists(before.manifest))
    after_warnings = set(_warning_lists(after.manifest))
    fields = changed_manifest_fields(before.manifest, after.manifest)
    axes = {
        "parquet_schema": before.parquet_schemas != after.parquet_schemas,
        "parquet_bytes": (
            before.manifest.get("artifact", {}).get("digest")
            != after.manifest.get("artifact", {}).get("digest")
        ),
        "content_signature": (
            before.manifest.get("content_signature") != after.manifest.get("content_signature")
        ),
        "manifest_fields": bool(fields),
        "warnings": before_warnings != after_warnings,
    }
    return ModuleDelta(
        name=after.name,
        axes=axes,
        manifest_fields=fields,
        warnings_added=tuple(sorted(after_warnings - before_warnings)),
        warnings_removed=tuple(sorted(before_warnings - after_warnings)),
    )


def _release_of(outputs: dict[str, ModuleOutput], side: str) -> str:
    """The compiler version every module on one side was stamped with, refusing a mixed tree.

    A tree compiled by two different releases is not a side of an interval, and averaging it would
    put a version number on the record that nothing actually produced.
    """
    stamped = {output.compiler_version for output in outputs.values()}
    if len(stamped) != 1 or None in stamped:
        raise ValueError(
            f"the {side} tree is stamped with {sorted(str(v) for v in stamped)} — a sweep side must "
            "be one release"
        )
    # `compiler_version` is stamped as `just-dna-compiler 0.6.1`; the record table is keyed on the
    # bare SemVer, and one helper in the format tier decides which is which for every caller.
    return release_version(stamped.pop())


def compare_outputs(
    before: dict[str, ModuleOutput], after: dict[str, ModuleOutput]
) -> SweepMeasurement:
    """Union the per-module deltas into the measurement one release record carries."""
    shared = sorted(set(before) & set(after))
    unmeasured = sorted(set(before) ^ set(after))
    deltas = tuple(compare_module(before[name], after[name]) for name in shared)
    axes = {
        axis: any(delta.axes[axis] for delta in deltas) for axis in sorted(VALID_RELEASE_OUTPUT_AXES)
    }
    fields: set[str] = set()
    for delta in deltas:
        fields.update(delta.manifest_fields)
    return SweepMeasurement(
        before=_release_of(before, "before"),
        after=_release_of(after, "after"),
        axes=axes,
        manifest_fields=tuple(sorted(fields)),
        modules=tuple(shared),
        unmeasured=tuple(unmeasured),
        per_module=deltas,
    )


def gate_findings(
    measurement: SweepMeasurement,
    version: str,
    records: dict[str, ReleaseRecord] | None = None,
) -> tuple[list[str], list[str]]:
    """`(findings, notes)` — the release gate. A non-empty `findings` fails the release.

    A finding is a measured movement no declaration covers. A **note** is the other direction — a
    declaration this sweep did not see move — and it is deliberately not a failure: the reference
    corpus is sixteen modules and a real correction can land on a shape none of them has.

    The gate runs in the bump → `uv sync` → tag sequence rather than as an ordinary test, because it
    needs the previous release actually installed.
    """
    table = RELEASE_RECORDS if records is None else records
    record = table.get(version)
    if record is None:
        return (
            [
                f"{version} {NO_RECORD_PHRASE}: a release that changed compiled output must declare "
                "what it changed, and a release where nothing moved must record the measured zero "
                "with its evidence"
            ],
            [],
        )

    findings: list[str] = []
    notes: list[str] = []
    if record.previous != measurement.before:
        findings.append(
            f"the sweep {WRONG_PREVIOUS_PHRASE}: measured {measurement.before} → "
            f"{measurement.after}, record {version} names {record.previous}"
        )

    declared_axes = {change.axis for change in record.declared}
    for axis in sorted(VALID_RELEASE_OUTPUT_AXES):
        if measurement.axes[axis] and record.axes.get(axis) is not True:
            findings.append(f"axis {axis!r} {UNDECLARED_AXIS_PHRASE}")
        if measurement.axes[axis] and axis not in declared_axes:
            findings.append(f"axis {axis!r} {UNDECLARED_KIND_PHRASE}")
        if record.axes.get(axis) is True and not measurement.axes[axis]:
            notes.append(f"axis {axis!r} {OVERDECLARED_NOTE_PHRASE}")

    listed = set(record.manifest_fields)
    for field in measurement.manifest_fields:
        if field not in listed:
            findings.append(f"manifest field {field!r} {UNDECLARED_FIELD_PHRASE}")
    for field in sorted(listed - set(measurement.manifest_fields)):
        notes.append(f"manifest field {field!r} {OVERDECLARED_NOTE_PHRASE}")
    return findings, notes


def measurement_json(measurement: SweepMeasurement) -> dict[str, Any]:
    """The measurement as plain JSON, so a release script can diff or archive it."""
    return {
        "before": measurement.before,
        "after": measurement.after,
        "axes": dict(measurement.axes),
        "manifest_fields": list(measurement.manifest_fields),
        "modules": list(measurement.modules),
        "unmeasured": list(measurement.unmeasured),
        "evidence": measurement.evidence,
        "per_module": [
            {
                "name": delta.name,
                "axes": dict(delta.axes),
                "manifest_fields": list(delta.manifest_fields),
                "warnings_added": list(delta.warnings_added),
                "warnings_removed": list(delta.warnings_removed),
            }
            for delta in measurement.per_module
        ],
    }
