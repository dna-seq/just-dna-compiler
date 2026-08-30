"""The sweep instrument and the release gate (RM126).

The instrument is the thing that keeps the record table from being a hand-kept map: the measurement
forces the declaration rather than the author remembering to write one. So these tests run the real
`compile_module` over real spec directories and read the real parquets, rather than asserting over a
constructed pair of manifest dicts — a differ that agrees with a fixture it was written beside is not
evidence of anything.

Two of them are the ones a reviewer should look at first. The **noise** test compiles the same spec
twice and asserts the sweep reports nothing moved, which is only true because `compilation.compiled_at`
and `compilation.compiler_version` are excluded — leave `compiler_version` in and every record fires on
every module in every release, which is the false-positive class the interval shape exists to avoid.
The **roster boundary** test builds a module whose sole row naming a gene is dropped for carrying a
lengthless symbolic allele, and shows `manifest.stats.genes` legitimately and permanently disagreeing
with a recomputation from the authored rows — with `compilation.dropped_rows` as the counter that makes
the condition checkable.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from just_dna_compiler.cli import app
from just_dna_compiler.compiler import compile_module, module_stats, spec_tables
from just_dna_compiler.sweep import (
    DEGENERATE_INTERVAL_PHRASE,
    NO_MODULES_PHRASE,
    NO_RECORD_PHRASE,
    OVERDECLARED_NOTE_PHRASE,
    UNDECLARED_AXIS_PHRASE,
    UNDECLARED_FIELD_PHRASE,
    UNDECLARED_KIND_PHRASE,
    UNMEASURED_MODULE_PHRASE,
    WRONG_PREVIOUS_PHRASE,
    WRONG_VERSION_PHRASE,
    ModuleOutput,
    build_outputs,
    changed_manifest_fields,
    compare_module,
    compare_outputs,
    gate_findings,
    measurement_json,
    read_output,
    read_outputs,
)
from just_dna_format.release_records import (
    AUTHORED_ROW_DERIVED_FIELDS,
    RECOMPILE_DRIVING_AXES,
    DeclaredChange,
    ReleaseRecord,
)
from just_dna_format.vocab import VALID_RELEASE_OUTPUT_AXES
from typer.testing import CliRunner

runner = CliRunner()

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm126\n"
    "  title: RM126\n"
    "  description: release record sweep\n"
    "  report_title: RM126\n"
    "genome_build: GRCh38\n"
)
_VARIANTS_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene,effect_allele\n"
#: Real ClinVar GRCh38 records, reused from `test_symbolic_alleles.py` so no coordinate is invented.
#: `rs1667266283` is a 926 bp MSH2 deletion; `rs2469808710` a GLI2 deletion at chr2:120926480, spelled
#: here **without** its length, which is the defect that makes the compiler drop the row.
_USABLE_MSH2 = (
    "rs1667266283,2,47475521,G,<DEL:926>,<DEL:926>/G,risk,a 926 bp MSH2 deletion,MSH2,<DEL:926>\n"
)
_LENGTHLESS_GLI2 = (
    "rs2469808710,2,120926480,A,<DEL>,<DEL>/A,risk,a deletion with no stated length,GLI2,\n"
)


def _sole_gene_dropped_spec(directory: Path) -> Path:
    """A module where GLI2 is named by exactly one row, and that row cannot survive the compile."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(_VARIANTS_HEADER + _USABLE_MSH2 + _LENGTHLESS_GLI2)
    # A real PMID already cited by `reference_examples/hfe_hemochromatosis`; grounding is mandatory
    # whenever `variants.csv` is present and nothing here tests citation content.
    (directory / "studies.csv").write_text(
        "rsid,pmid\nrs1667266283,16199547\nrs2469808710,16199547\n"
    )
    return directory


def _first_example() -> Path:
    found = sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file())
    assert found, f"no reference examples discovered under {_EXAMPLES}"
    return found[0]


def _as_output(name: str, manifest: dict[str, Any]) -> ModuleOutput:
    """A manifest-only output, for the cases that are about the differ and not about parquet."""
    return ModuleOutput(name=name, manifest=manifest, parquet_schemas={})


# ── the noise set is itself a registry ───────────────────────────────────────────────────────────


def test_compiling_one_spec_twice_moves_no_axis(tmp_path: Path) -> None:
    """The instrument's own false-positive floor, measured on a real module rather than argued.

    Two compiles of one spec differ in `compilation.compiled_at` and in nothing else that matters, so
    a sweep that counted every published manifest field would report a change here — and would then
    report one on every module in every release, for every consumer, forever.
    """
    spec = _first_example()
    first = read_output(compile_module(spec, tmp_path / "a").output_dir)
    second = read_output(compile_module(spec, tmp_path / "b").output_dir)

    assert set(compare_module(first, second).axes.values()) == {False}

    # Two compiles inside one second carry the same timestamp, so the run above cannot *by itself*
    # prove the exclusion did any work. Move the two environment stamps on a real manifest and ask
    # again: this is the case that fires on every release for every consumer if it is not excluded.
    second.manifest["compilation"]["compiled_at"] = "2020-01-01T00:00:00Z"
    second.manifest["compilation"]["compiler_version"] = "just-dna-compiler 0.0.1"
    second.manifest["compilation"]["compiled_by"] = "somebody else"
    delta = compare_module(first, second)

    assert first.manifest["compilation"]["compiled_at"] != second.manifest["compilation"][
        "compiled_at"
    ]
    assert set(delta.axes) == set(VALID_RELEASE_OUTPUT_AXES)
    assert set(delta.axes.values()) == {False}
    assert delta.manifest_fields == ()


def test_the_compiler_version_never_counts_as_a_changed_manifest_field() -> None:
    """It moves on every release by construction; counting it would make the record tautological."""
    before = {"compilation": {"compiler_version": "just-dna-compiler 0.6.1", "warnings": ["a"]},
              "artifact": {"digest": "sha256:aa", "files": []},
              "content_signature": "sha256:bb",
              "stats": {"genes": ["HFE"]}}
    after = {"compilation": {"compiler_version": "just-dna-compiler 0.6.6", "warnings": ["b"]},
             "artifact": {"digest": "sha256:cc", "files": [{"name": "x"}]},
             "content_signature": "sha256:dd",
             "stats": {"genes": ["HFE"]}}

    assert changed_manifest_fields(before, after) == ()


def test_a_real_published_field_does_count() -> None:
    """The converse, so the exclusion above is not simply switching the check off."""
    before = {"stats": {"genes": [], "gene_count": 0}}
    after = {"stats": {"genes": ["CYP2C19"], "gene_count": 1}}

    assert changed_manifest_fields(before, after) == ("stats.gene_count", "stats.genes")


def test_a_block_appearing_where_there_was_a_null_is_reported() -> None:
    """A new manifest block is a change, and it must not vanish because one side has no such path."""
    assert changed_manifest_fields({"literature": None}, {"literature": {"quotes_unchecked": 0}}) == (
        "literature",
        "literature.quotes_unchecked",
    )


# ── the warnings axis, and the seam RM131 fills ──────────────────────────────────────────────────


def test_the_warnings_axis_is_reported_and_is_not_a_recompile_driver() -> None:
    """`compilation.warnings` is a published manifest field and must not reach `manifest_fields`.

    RM131 restructures that channel and RM134 adds checks, so a sweep folding warnings into the
    manifest-field set would fire on essentially every module in 0.7 and mint a PATCH across a whole
    catalogue for a reworded message. `warnings_added`/`warnings_removed` are kept apart here because
    RM131's `carried` split is what will make the two decidable — a finding the author cannot clear
    moving is noise, one they can clear appearing is not.
    """
    before = {"compilation": {"compiler_version": "just-dna-compiler 0.6.1", "warnings": ["old"]},
              "artifact": {"digest": "sha256:aa"}, "content_signature": "sha256:bb"}
    after = {"compilation": {"compiler_version": "just-dna-compiler 0.6.1", "warnings": ["new"]},
             "artifact": {"digest": "sha256:aa"}, "content_signature": "sha256:bb"}
    delta = compare_module(_as_output("m", before), _as_output("m", after))

    assert delta.axes["warnings"] is True
    assert delta.axes["manifest_fields"] is False
    assert delta.manifest_fields == ()
    assert delta.warnings_added == ("new",) and delta.warnings_removed == ("old",)
    assert "warnings" not in RECOMPILE_DRIVING_AXES


# ── the end-to-end instrument over the real corpus ───────────────────────────────────────────────


def test_the_sweep_over_the_real_corpus_reports_a_measured_zero_with_its_denominator(
    tmp_path: Path,
) -> None:
    """Built by discovery, both sides from one spec root, and the evidence carries the denominator.

    A release where nothing moved must record a measured zero *with its evidence*, never silence —
    so the sentence the record will carry has to name what was compared and how many of it moved.
    """
    before = build_outputs(_EXAMPLES, tmp_path / "before")
    after = build_outputs(_EXAMPLES, tmp_path / "after")
    measurement = compare_outputs(before, after)

    assert measurement.modules == tuple(sorted(before))
    assert measurement.unmeasured == ()
    assert set(measurement.axes.values()) == {False}
    assert measurement.moved_counts == dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, 0)
    assert f"{len(measurement.modules)} reference module(s)" in measurement.evidence
    assert f"content_signature 0/{len(measurement.modules)}" in measurement.evidence
    assert measurement_json(measurement)["axes"] == measurement.axes
    # Both sides are this compiler, so the interval is degenerate and no record can come out of it.
    with pytest.raises(ValueError, match="cannot mint a record"):
        measurement.as_record(version=measurement.after, previous=measurement.before)


def test_a_side_stamped_with_two_releases_is_refused(tmp_path: Path) -> None:
    """A tree compiled by two compilers is not a side of an interval."""
    outputs = build_outputs(_EXAMPLES, tmp_path / "mixed")
    name = min(outputs)
    outputs[name].manifest["compilation"]["compiler_version"] = "just-dna-compiler 0.0.1"

    with pytest.raises(ValueError, match="must be one release"):
        compare_outputs(outputs, outputs)


def test_read_outputs_refuses_a_directory_with_nothing_compiled_in_it(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="no compiled modules"):
        read_outputs(tmp_path / "empty")


# ── the gate ─────────────────────────────────────────────────────────────────────────────────────


def _measurement(tmp_path: Path, **moved: bool):
    """A real measurement over the corpus, with the axes overridden to the case under test.

    Real modules and a real evidence sentence, so only the axis values are synthetic — which is the
    part the gate reads.
    """
    before = build_outputs(_EXAMPLES, tmp_path / "before")
    base = compare_outputs(before, before)
    axes = dict(base.axes)
    axes.update(moved)
    return replace(base, axes=axes, before="1.0.0", after="1.0.1",
                   manifest_fields=("stats.genes",) if axes["manifest_fields"] else ())


def test_the_gate_fails_a_release_with_no_record_at_all(tmp_path: Path) -> None:
    findings, notes = gate_findings(_measurement(tmp_path), "1.0.1", {})

    assert notes == []
    assert len(findings) == 1
    assert NO_RECORD_PHRASE in findings[0]


def test_the_gate_refuses_a_sweep_that_did_not_measure_the_release_being_gated(
    tmp_path: Path,
) -> None:
    """The likeliest operator error, and it used to gate green.

    The documented sequence is bump → `uv sync` → measure. Run it before `uv sync` propagates the
    bump and `--spec-root` builds the AFTER tree with the *previous* release still installed: both
    sides are one compiler, every axis reads `False`, and a gate checking only the interval's lower
    end finds nothing wrong with a release it never measured. That is a false green in the one
    mechanism the whole item rests on, so the upper end is checked too — and a degenerate interval is
    refused outright rather than being allowed to read as a measured zero.
    """
    stale = _measurement(tmp_path)
    stale = replace(stale, before="0.6.6", after="0.6.6")
    record = ReleaseRecord(
        version="0.7.0",
        previous="0.6.6",
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
        evidence="a record whose lower end matches the stale sweep",
    )
    findings, _ = gate_findings(stale, "0.7.0", {"0.7.0": record})

    assert any(DEGENERATE_INTERVAL_PHRASE in f for f in findings)
    assert any(WRONG_VERSION_PHRASE in f for f in findings)


def test_the_gate_refuses_a_release_whose_sweep_could_not_measure_every_module(
    tmp_path: Path,
) -> None:
    """A module that compiled on one side only is a module the sweep says nothing about.

    Under the one-spec-root sequence there is no innocent reading: both sides see the same specs, so
    a module missing from one is a compile that failed. Rolling it into an all-`False` result over
    its surviving neighbours is the silence this whole surface exists to replace, and
    `SweepMeasurement`'s own docstring says so.
    """
    measurement = replace(_measurement(tmp_path), unmeasured=("cyp2c19_star_alleles",))
    record = ReleaseRecord(
        version="1.0.1",
        previous="1.0.0",
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
        evidence="claims a measured zero over what survived",
    )
    findings, _ = gate_findings(measurement, "1.0.1", {"1.0.1": record})

    assert any(UNMEASURED_MODULE_PHRASE in f and "cyp2c19_star_alleles" in f for f in findings)


def test_the_gate_refuses_a_sweep_with_no_module_in_common(tmp_path: Path) -> None:
    """A 0/0 denominator is not a measured zero. `@tautology-zero`, one surface over."""
    empty = replace(_measurement(tmp_path), modules=(), per_module=())
    findings, _ = gate_findings(empty, "1.0.1", {})

    assert any(NO_MODULES_PHRASE in f for f in findings)


def test_the_gate_accepts_the_stamped_spelling_of_the_release_it_gates(tmp_path: Path) -> None:
    """`release_version` exists so one convention does not become three; the gate uses it too."""
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    record = ReleaseRecord(
        version="1.0.1", previous="1.0.0", axes=axes, evidence="measured zero"
    )
    bare, _ = gate_findings(_measurement(tmp_path), "1.0.1", {"1.0.1": record})
    stamped, _ = gate_findings(
        _measurement(tmp_path), "just-dna-compiler 1.0.1", {"1.0.1": record}
    )

    assert bare == stamped == []


def test_a_measurement_cannot_mint_a_record_for_an_interval_it_did_not_take(tmp_path: Path) -> None:
    """`as_record`'s `evidence` names the interval it measured; the fields must not contradict it.

    The record it *does* mint carries an empty `declared` list on purpose — the gate then refuses it
    until somebody says whether each movement was a correction or an addition, which is the whole
    mechanism that keeps this from being a map maintained by memory.
    """
    before, after = _restamped_pair(tmp_path, "0.6.1", "0.6.6")
    measurement = compare_outputs(read_outputs(before), read_outputs(after))

    minted = measurement.as_record(version="0.6.6", previous="0.6.1")
    assert minted.declared == []
    assert minted.evidence == measurement.evidence
    with pytest.raises(ValueError, match="cannot mint a record"):
        measurement.as_record(version="2.0.0", previous="0.6.1")


def test_the_gate_fails_a_measured_move_no_record_declares(tmp_path: Path) -> None:
    """The mechanism in one test: the measurement forces the declaration.

    Two findings, not one, and they are different refusals — the record's *axis* says the value did
    not move, and nothing says whether it was wrong or merely absent.
    """
    record = ReleaseRecord(
        version="1.0.1",
        previous="1.0.0",
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
        evidence="claims nothing moved",
    )
    findings, notes = gate_findings(
        _measurement(tmp_path, manifest_fields=True), "1.0.1", {"1.0.1": record}
    )

    assert notes == []
    assert any(UNDECLARED_AXIS_PHRASE in f and "manifest_fields" in f for f in findings)
    assert any(UNDECLARED_KIND_PHRASE in f for f in findings)
    assert any(UNDECLARED_FIELD_PHRASE in f and "stats.genes" in f for f in findings)


def test_the_gate_passes_a_release_whose_record_covers_the_measurement(tmp_path: Path) -> None:
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    axes["manifest_fields"] = True
    record = ReleaseRecord(
        version="1.0.1",
        previous="1.0.0",
        axes=axes,
        manifest_fields=["stats.genes"],
        declared=[
            DeclaredChange(
                axis="manifest_fields",
                target="stats.genes",
                kind="correction",
                detail="the published value was wrong",
            )
        ],
        evidence="measured",
    )
    findings, notes = gate_findings(
        _measurement(tmp_path, manifest_fields=True), "1.0.1", {"1.0.1": record}
    )

    assert findings == []
    assert notes == []


def test_a_declaration_the_sweep_did_not_see_is_a_note_and_not_a_failure(tmp_path: Path) -> None:
    """The reference corpus is sixteen modules; a real correction can land on a shape none of them
    has, so over-declaring must not block a release. It is still reported, so it is not invisible."""
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    axes["parquet_schema"] = True
    record = ReleaseRecord(
        version="1.0.1",
        previous="1.0.0",
        axes=axes,
        manifest_fields=["stats.categories"],
        declared=[
            DeclaredChange(axis="parquet_schema", target="pgs.parquet", kind="addition", detail="d")
        ],
        evidence="measured elsewhere",
    )
    findings, notes = gate_findings(_measurement(tmp_path), "1.0.1", {"1.0.1": record})

    assert findings == []
    assert any(OVERDECLARED_NOTE_PHRASE in n and "parquet_schema" in n for n in notes)
    assert any(OVERDECLARED_NOTE_PHRASE in n and "stats.categories" in n for n in notes)


def test_the_gate_refuses_a_record_measured_against_a_different_release(tmp_path: Path) -> None:
    """A record whose interval is not the one that was swept describes something else entirely."""
    record = ReleaseRecord(
        version="1.0.1",
        previous="0.9.0",
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
        evidence="measured against the wrong side",
    )
    findings, _ = gate_findings(_measurement(tmp_path), "1.0.1", {"1.0.1": record})

    assert any(WRONG_PREVIOUS_PHRASE in f for f in findings)


# ── the CLI, and the one stream discipline `--json` exists for ──────────────────────────────────


def _restamped_pair(tmp_path: Path, before_release: str, after_release: str) -> tuple[Path, Path]:
    """Two output trees holding the SAME real compiled module, stamped as two releases.

    Real manifests and real parquets, with one cell moved — which is the only way to exercise the
    gate's passing path offline: measuring a genuine interval needs the previous release installed,
    and that is a release-sequence operation rather than a test.
    """
    spec = _first_example()
    trees = []
    for side, release in (("before", before_release), ("after", after_release)):
        module_dir = tmp_path / side / spec.name
        result = compile_module(spec, module_dir)
        assert result.success, result.errors
        manifest_path = module_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["compilation"]["compiler_version"] = f"just-dna-compiler {release}"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        trees.append(tmp_path / side)
    return trees[0], trees[1]


def test_the_json_output_is_the_whole_of_stdout_even_with_the_gate_running(tmp_path: Path) -> None:
    """`--json`'s caller is a release script piping to `jq`, so nothing may join the document.

    The gate has prose of its own — notes and a success line — and printing either after the blob
    breaks exactly the consumer the flag exists for. Asserted by parsing stdout, not by reading the
    code: a note appended to stdout would still *look* fine in a terminal.

    The 0.6.1 → 0.6.6 record declares movements this pair did not make, so the run emits notes and
    a success line and still exits 0 — the case that would corrupt the stream.
    """
    before, after = _restamped_pair(tmp_path, "0.6.1", "0.6.6")
    result = runner.invoke(
        app, ["sweep", str(before), str(after), "--json", "--release", "0.6.6"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["before"] == "0.6.1" and payload["after"] == "0.6.6"
    assert payload["axes"] == dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    assert OVERDECLARED_NOTE_PHRASE in result.stderr
    assert "covers the measurement" in result.stderr


def test_without_json_the_gate_prose_reaches_the_terminal(tmp_path: Path) -> None:
    """The converse, so the stream discipline above is not simply silencing the gate."""
    before, after = _restamped_pair(tmp_path, "0.6.1", "0.6.6")
    result = runner.invoke(app, ["sweep", str(before), str(after), "--release", "0.6.6"])

    assert result.exit_code == 0, result.output
    assert OVERDECLARED_NOTE_PHRASE in result.stdout
    assert "covers the measurement" in result.stdout


def test_the_gate_exits_one_for_a_release_the_table_has_no_record_of(tmp_path: Path) -> None:
    """The mechanism the coordinator relies on at cut time: no record, no release."""
    build_outputs(_EXAMPLES, tmp_path / "before")
    build_outputs(_EXAMPLES, tmp_path / "after")
    result = runner.invoke(
        app, ["sweep", str(tmp_path / "before"), str(tmp_path / "after"), "--release", "0.7.0"]
    )

    assert result.exit_code == 1
    assert NO_RECORD_PHRASE in result.stderr


# ── the roster's conditional boundary ────────────────────────────────────────────────────────────


def test_a_module_that_lost_its_sole_gene_row_disagrees_with_the_recomputation(
    tmp_path: Path,
) -> None:
    """The roster's condition, demonstrated rather than asserted (S65's third constraint).

    `validate_spec` computes `stats` over the full row set; `compile_module` re-derives them over the
    survivors when the symbolic-allele drop removed something. So a consumer recomputing from the
    stored authored rows gets the **pre-drop** answer, `manifest.stats` is the post-drop one, and for
    a module that lost the sole row naming a gene the two disagree permanently, under any compiler.
    A roster that said *pure function of the authored rows* without this would send a registry to
    spend a version number on a module that is perfectly current.

    `compilation.dropped_rows` is what makes it checkable rather than a story: their guard used to
    discriminate on `variant_count`, and a drop inside a kind table moved no published counter at all.
    """
    spec = _sole_gene_dropped_spec(tmp_path / "spec")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors

    rows, _build = spec_tables(spec)
    recomputed = module_stats(rows.get("variants.csv", []), rows)

    assert recomputed["genes"] == ["GLI2", "MSH2"], "the authored rows name both genes"
    assert result.manifest.stats.genes == ["MSH2"], "the artifact holds only what survived"
    assert recomputed["genes"] != result.manifest.stats.genes
    # And the condition is checkable from the manifest alone, which is the whole point.
    assert result.manifest.compilation.dropped_rows, "the counter that says the recomputation is stale"
    assert sum(result.manifest.compilation.dropped_rows.values()) == 1


def test_the_roster_agrees_with_the_manifest_when_nothing_was_dropped(tmp_path: Path) -> None:
    """The other side of the condition, over the real corpus: with `dropped_rows` empty, every
    conditional roster entry recomputes to exactly what the manifest published."""
    checked = 0
    covered = 0
    for spec in sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file()):
        result = compile_module(spec, tmp_path / spec.name)
        assert result.success, result.errors
        if result.manifest.compilation.dropped_rows:
            continue
        covered += 1
        rows, _build = spec_tables(spec)
        recomputed = module_stats(rows.get("variants.csv", []), rows)
        for entry in AUTHORED_ROW_DERIVED_FIELDS:
            if entry.condition is None or not entry.field.startswith("stats."):
                continue
            key = entry.field.removeprefix("stats.")
            assert recomputed[key] == getattr(result.manifest.stats, key), f"{spec.name}.{key}"
            checked += 1
    conditional_stats = [
        entry for entry in AUTHORED_ROW_DERIVED_FIELDS
        if entry.condition is not None and entry.field.startswith("stats.")
    ]
    # An equality over what was walked, not a floor plus a modulo: `checked > 0` passes on one
    # example and the modulo passes on any whole multiple, so together they can still be blind to
    # a corpus that silently stopped covering most of the specs.
    assert covered > 0, "no example reached the nothing-was-dropped branch"
    assert checked == covered * len(conditional_stats)
