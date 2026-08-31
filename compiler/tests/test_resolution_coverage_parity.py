"""`validate` reports resolution coverage, so it stops blessing what `compile` refuses (0.7, S76).

The standing parity rule is that a check which is pure computation over injected or authored bytes,
needing no `output_dir`, belongs in `validate_spec` too — and that what stays compile-only is a check
reading **resolved** rows. Coverage sat on the edge of that exemption and was read as being inside it:
whether the injected table *can* place an authored row is arithmetic over bytes already loaded, and
answering it needs no resolution to have run.

The cost was the exact shape the rule exists to stop. A spec whose `resolution.csv` covers some of its
variants — an `enrich` killed partway, or a table injected for a subset — passed `validate --strict`
clean and was refused by `compile --strict`, sending the author looking for a change they had not made.
It was reported as the loud half of a suspected silent failure, and the silent half did not reproduce:
a re-run gap-fills the missing subjects, on 0.7 and on 0.6.6 both. What was real is that nothing said
so until the compile.

The fixture is the real GRCh38 HFE locus, `rs1800562` at 6:26092913 `G>A` (C282Y), plus a second row
the table deliberately does not cover.
"""

from pathlib import Path

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_compiler.resolution import unresolved_subjects
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: cover\n"
    "  title: Coverage\n"
    "  description: resolution coverage parity\n"
    "  report_title: Coverage\n"
    "genome_build: GRCh38\n"
)

_VARIANTS = (
    "rsid,gene,genotype,weight,state,conclusion\n"
    "rs1800562,HFE,A/A,-1.0,risk,C282Y homozygote\n"
    "rs1799945,HFE,C/G,-0.5,risk,H63D heterozygote\n"
)

_HEADER = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"

#: Covers the first rsID only — the reporter's 201-of-263 shape, at two rows.
_PARTIAL = _HEADER + "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,authored,resolved\n"

_WHOLE = _PARTIAL + "rs1799945,rs1799945,6,26091179,C,G,GRCh38,0,authored,resolved\n"

_UNCOVERED = "rs1799945"


def _spec(directory: Path, *, resolution: str | None, variants: str = _VARIANTS) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(variants, encoding="utf-8")
    (directory / "studies.csv").write_text("rsid,pmid\nrs1800562,16199547\n", encoding="utf-8")
    if resolution is not None:
        (directory / "resolution.csv").write_text(resolution, encoding="utf-8")
    return directory


def _unplaced(result) -> list[str]:
    return [w for w in result.warnings if "not found in resolution table" in w]


# ── the parity itself ───────────────────────────────────────────────────────────────────────────


def test_strict_validate_refuses_a_partial_table_with_the_compile_s_own_error(tmp_path: Path) -> None:
    """The defect, stated as the property it violated: the two commands must give one answer.

    Asserting the error strings are **equal** rather than that both are non-empty is the point — a
    pre-flight that refuses for its own differently-worded reason still sends the author hunting, and a
    second implementation of "which rows are unplaceable" would drift from the first at the next
    change to `_usable_loci`.
    """
    spec = _spec(tmp_path / "spec", resolution=_PARTIAL)

    validated = validate_spec(spec, strict=True)
    compiled = compile_module(spec, tmp_path / "out", strict=True)

    assert not compiled.success
    assert not validated.valid
    assert validated.errors == compiled.errors
    assert _UNCOVERED in validated.errors[0]


def test_a_complete_table_is_green_on_both_sides(tmp_path: Path) -> None:
    """The discriminating half: the check must not refuse a module that is actually covered.

    Without this the test above passes for a check that refuses everything, which is the failure mode
    a coverage assertion cannot see on its own.
    """
    spec = _spec(tmp_path / "spec", resolution=_WHOLE)

    validated = validate_spec(spec, strict=True)
    compiled = compile_module(spec, tmp_path / "out", strict=True)

    assert compiled.success, compiled.errors
    assert validated.valid, validated.errors
    assert _unplaced(validated) == []


def test_best_effort_warns_on_both_sides_with_the_identical_sentence(tmp_path: Path) -> None:
    """The mode ladder's lower rung, and the message contract under it.

    `rsid_unresolved` is a phrase a consumer greps, so the pre-flight reuses the sentence
    `resolve_from_table` already emits rather than writing a second one that means the same thing.
    """
    spec = _spec(tmp_path / "spec", resolution=_PARTIAL)

    validated = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out")

    assert validated.valid
    assert compiled.success, compiled.errors
    assert _unplaced(validated) == _unplaced(compiled)
    assert _unplaced(compiled) == [
        f"{_UNCOVERED}: not found in resolution table, position remains unset"
    ]


def test_the_finding_is_reported_once_though_two_passes_produce_it(tmp_path: Path) -> None:
    """`@no-rerun-with-counts`'s companion: dedup on the message, and prove the count.

    `compile_module` runs the pre-flight in best_effort whatever its own mode, so both passes reach
    this finding for the same subject. Appending blind published every one twice — measured at 24 for
    12 subjects on a real example while this was being built — and `warnings_summary` is where that
    surfaces, because a consumer reads the count rather than the list.
    """
    spec = _spec(tmp_path / "spec", resolution=_PARTIAL)
    compiled = compile_module(spec, tmp_path / "out")

    found = _unplaced(compiled)
    assert len(found) == len(set(found)) == 1
    assert compiled.warnings_summary["rsid_unresolved"] == 1


# ── the three states of the table, which are not two ────────────────────────────────────────────


def test_no_table_at_all_is_reported_as_nobody_asked_rather_than_per_row(tmp_path: Path) -> None:
    """Unreachable is not absent, and the pre-flight makes the compile's own distinction.

    With a table present, a row it does not cover is absent from something that was consulted and is
    named. With no table, nothing was consulted: the compile says so once, and the pre-flight must not
    instead blame a file that does not exist, once per variant. Both still refuse under `strict` —
    the artifact is unreproducible either way, and that severity is not what this splits.
    """
    spec = _spec(tmp_path / "spec", resolution=None)

    validated = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out")

    assert _unplaced(validated) == []
    assert validated.warnings_summary["resolution_not_injected"] == 1
    assert validated.warnings_summary == {
        k: v for k, v in compiled.warnings_summary.items() if k in validated.warnings_summary
    }
    assert not validate_spec(spec, strict=True).valid


def test_no_resolve_suppresses_the_check_the_way_it_suppresses_the_fill(tmp_path: Path) -> None:
    """The master switch means the same thing on both sides of the parity.

    `--no-resolve` turns resolution off entirely, so every variant compiles unpositioned **by
    request**. Reporting each one unplaceable there would restate that request once per row, and the
    existing `resolution_disabled` warning already says it once with the row count in it.
    """
    spec = _spec(tmp_path / "spec", resolution=_PARTIAL)

    validated = validate_spec(spec, strict=True, resolve_with_ensembl=False)

    assert _unplaced(validated) == []
    assert validated.valid, validated.errors


# ── the shared predicate ────────────────────────────────────────────────────────────────────────


def test_the_predicate_is_the_one_resolution_applies(tmp_path: Path) -> None:
    """Shared rather than restated, which is what keeps the two sides from drifting apart.

    Three table states a naive membership test gets wrong and `_usable_loci` does not: a `not_found`
    sentinel is a recorded answer of *no locus*, a row under another build is not this module's, and a
    row with no `chrom` places nothing. All three leave the subject unplaceable.
    """
    variants = [
        VariantRow(rsid="rs1800562", genotype="A/A", weight=-1.0, state="risk", conclusion="c"),
    ]

    def _table(**overrides) -> dict[str, list[ResolutionRow]]:
        fields = {
            "variant_key": "rs1800562",
            "rsid": "rs1800562",
            "chrom": "6",
            "start": 26092913,
            "ref": "G",
            "alts": "A",
            "genome_build": "GRCh38",
            "locus_index": 0,
            "source": "authored",
            "status": "resolved",
        }
        fields.update(overrides)
        return {"rs1800562": [ResolutionRow(**fields)]}

    assert unresolved_subjects(variants, _table(), "GRCh38") == []
    assert unresolved_subjects(variants, {}, "GRCh38") == ["rs1800562"]
    assert unresolved_subjects(variants, _table(status="not_found"), "GRCh38") == ["rs1800562"]
    assert unresolved_subjects(variants, _table(genome_build="GRCh37"), "GRCh38") == ["rs1800562"]

    # A non-GRCh38 module: `resolve_from_table` skips wholesale rather than resolving less, so naming
    # every row here would restate that skip once per row and blame the table for a limit of the tier.
    assert unresolved_subjects(variants, {}, "GRCh37") == []


def test_a_row_that_authors_its_own_coordinate_needs_no_table(tmp_path: Path) -> None:
    """The other half of the predicate: coverage is about rows that need placing.

    A coordinate-authored module carries its positions already, so an empty table leaves nothing
    unplaceable — and a check that read "not in the table" as "unresolved" would refuse every such
    module under `strict`.
    """
    spec = _spec(
        tmp_path / "spec",
        resolution=None,
        variants=(
            "rsid,chrom,start,ref,alts,gene,genotype,weight,state,conclusion\n"
            "rs1800562,6,26092913,G,A,HFE,A/A,-1.0,risk,C282Y homozygote\n"
        ),
    )

    validated = validate_spec(spec, strict=True)
    assert validated.valid, validated.errors
    assert _unplaced(validated) == []
