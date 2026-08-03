"""Scaffolding — de-novo module creation that never touches what already exists (0.5).

Companion to `test_draft.py`, which pins the *append* half. What is pinned here is the refusal
granularity (per file, never per run), the companion-kind rule against the compiler's real
requirement, and the property that ties the whole authoring surface together: a scaffolded module
does not validate until its stubs are replaced, and once replaced it is a compile → reverse →
recompile fixed point.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.draft import DRAFTABLE, DraftError
from just_dna_compiler.scaffold import (
    COMPANION_KINDS,
    MODULE_SPEC,
    module_spec_template,
    scaffold_module,
)
from just_dna_format.spec import ModuleSpecConfig
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER

_FILL = {
    "rsid": "rs1801133", "genotype": "A/G", "state": "risk", "conclusion": "MTHFR C677T",
    "pmid": "12345678", "gene": "HTT", "repeat_unit": "CAG", "haplotype_name": "*4",
    "haplotype_a": "*1", "haplotype_b": "*4", "pgs_id": "PGS000135", "drug": "warfarin",
    "tissue": "blood", "reference_sequence": "NC_012920.1",
}
_FILL_BY_KIND = {"allele_function.csv": {"allele": "*4"}, "haplotypes.csv": {"allele": "A"}}


def _fill_csv(path: Path) -> None:
    rows = list(csv.DictReader(io.StringIO(path.read_text())))
    fieldnames = list(rows[0])
    values = {**_FILL, **_FILL_BY_KIND.get(path.name, {})}
    for row in rows:
        for column, cell in row.items():
            if cell == TEMPLATE_PLACEHOLDER:
                row[column] = values.get(column, "1")
        if row.get("unresolved") == "false" and not row.get("measure_min"):
            row["measure_min"] = "1"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue())


def _fill_module(spec_dir: Path) -> None:
    (spec_dir / MODULE_SPEC).write_text(
        (spec_dir / MODULE_SPEC).read_text().replace(TEMPLATE_PLACEHOLDER, "demo text")
    )
    for path in sorted(spec_dir.glob("*.csv")):
        _fill_csv(path)


def test_a_scaffolded_module_does_not_validate_until_the_stubs_are_replaced(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    scaffold_module(spec_dir, kinds=["variants.csv"], name="demo")
    result = validate_spec(spec_dir)
    assert not result.valid
    # and every complaint is about the placeholder — the scaffold is otherwise structurally complete
    assert result.errors and all(TEMPLATE_PLACEHOLDER in e for e in result.errors)


def test_a_filled_scaffold_compiles_and_is_a_fixed_point(tmp_path: Path) -> None:
    """P7: compile → reverse → compile reproduces the digest, for a module built entirely by tooling."""
    spec_dir = tmp_path / "spec"
    scaffold_module(spec_dir, kinds=["variants.csv"], name="demo")
    _fill_module(spec_dir)
    assert validate_spec(spec_dir).valid

    first = compile_module(spec_dir, tmp_path / "out1").manifest
    reverse_module(tmp_path / "out1", tmp_path / "back")
    second = compile_module(tmp_path / "back", tmp_path / "out2").manifest
    assert first.artifact.digest == second.artifact.digest


def test_scaffolding_never_overwrites_and_refuses_per_file(tmp_path: Path) -> None:
    """Per file, not per run: an existing table must not block a new one from being added."""
    spec_dir = tmp_path / "spec"
    scaffold_module(spec_dir, kinds=["variants.csv"], name="demo")
    before = {p.name: p.read_bytes() for p in sorted(spec_dir.iterdir())}

    again = scaffold_module(spec_dir, kinds=["variants.csv"], name="demo")
    assert again.created == []
    assert {p.name for p, _ in again.refused} == set(before)
    assert {p.name: p.read_bytes() for p in sorted(spec_dir.iterdir())} == before

    added = scaffold_module(spec_dir, kinds=["pgs.csv"])
    assert [p.name for p in added.created] == ["pgs.csv"]
    # the pre-existing files are still byte-identical
    assert all(before[name] == (spec_dir / name).read_bytes() for name in before)


def test_dry_run_writes_nothing_and_predicts_the_real_run(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    planned = scaffold_module(spec_dir, kinds=["pgs.csv"], dry_run=True)
    assert not planned.written
    assert not spec_dir.exists()
    real = scaffold_module(spec_dir, kinds=["pgs.csv"])
    assert [p.name for p in real.created] == [p.name for p in planned.created]


def test_a_zero_byte_file_counts_as_absent(tmp_path: Path) -> None:
    """The same rule `draft.append_rows` applies, so the two never disagree about existence."""
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "pgs.csv").touch()
    plan = scaffold_module(spec_dir, kinds=["pgs.csv"])
    assert [p.name for p in plan.created] == [MODULE_SPEC, "pgs.csv"]


def test_the_companion_rule_matches_the_compilers_own_requirement(tmp_path: Path) -> None:
    """`COMPANION_KINDS` is pinned to the real rule rather than trusted: scaffolding only the kind
    that needs a companion, with the companion suppressed, must fail for that documented reason."""
    for kind, companions in COMPANION_KINDS.items():
        spec_dir = tmp_path / f"spec_{kind.replace('.', '_')}"
        scaffold_module(spec_dir, kinds=[kind])
        for companion in companions:
            (spec_dir / companion).unlink()
        _fill_module(spec_dir)
        errors = validate_spec(spec_dir).errors
        assert any(companion in e for companion in companions for e in errors), (
            f"{kind} was expected to require {companions}, but validation did not say so"
        )


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_every_kind_can_be_scaffolded_and_filled(kind: str, tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    plan = scaffold_module(spec_dir, kinds=[kind], name="demo")
    assert (spec_dir / kind) in plan.created
    _fill_module(spec_dir)
    assert validate_spec(spec_dir).valid, validate_spec(spec_dir).errors


def test_an_unknown_kind_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    with pytest.raises(DraftError, match="not an authored table"):
        scaffold_module(spec_dir, kinds=["nonsense.csv"])
    assert not spec_dir.exists()


def test_the_module_spec_template_round_trips_through_its_own_model() -> None:
    """Generated from the live models, so it carries the current keys and no stale ones."""
    import yaml

    spec = yaml.safe_load(module_spec_template(name="demo"))
    assert spec["module"]["name"] == "demo"
    assert spec["genome_build"] == ModuleSpecConfig.model_fields["genome_build"].default
    # an empty `authorship: []` would claim the module has no contributors — it is omitted instead
    assert "authorship" not in spec
    assert set(spec) <= set(ModuleSpecConfig.model_fields)


# ── The HFE reference example (0.5.1) ───────────────────────────────────────────────────────────
# The first module authored end-to-end with the authoring surface: scaffold → draft-panel → curate →
# enrich → compile. It is pinned here rather than in the enricher suite because the committed
# `resolution.csv` makes it compilable by the compiler alone.

_HFE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def test_the_hfe_example_compiles_and_is_a_fixed_point(tmp_path: Path) -> None:
    assert validate_spec(_HFE).valid, validate_spec(_HFE).errors
    first = compile_module(_HFE, tmp_path / "out1").manifest
    reverse_module(tmp_path / "out1", tmp_path / "back")
    second = compile_module(tmp_path / "back", tmp_path / "out2").manifest
    assert first.artifact.digest == second.artifact.digest


def test_no_drafted_stub_survived_into_the_example() -> None:
    """A shipped module must not carry a placeholder — that is the point of the sentinel."""
    for path in sorted(_HFE.glob("*.csv")) + [_HFE / MODULE_SPEC]:
        assert TEMPLATE_PLACEHOLDER not in path.read_text(), path.name


def test_the_c282y_pair_is_what_makes_the_genotype_a_human_decision() -> None:
    """One allele, one ClinVar call, two genotypes, opposite meaning — the reason `draft-panel`
    stubs `genotype` instead of deriving it from the alt."""
    rows = [
        row
        for row in csv.DictReader(io.StringIO((_HFE / "variants.csv").read_text()))
        if row["rsid"] == "rs1800562"
    ]
    by_genotype = {row["genotype"]: row for row in rows}
    assert set(by_genotype) == {"A/A", "A/G"}
    assert {row["clin_sig"] for row in rows} == {"pathogenic"}   # the allele's call is the same
    assert by_genotype["A/A"]["state"] == "risk"                 # the finding's is not
    assert by_genotype["A/G"]["state"] == "neutral"


def test_a_multi_allelic_rsid_is_carried_by_coordinate_not_by_rsid() -> None:
    """`rs773443949` is both G>A and G>T at 6:26091590; an rsid-only row could name neither, and
    de-duplicating them lost an allele. Both survive here, identified by coordinate."""
    rows = list(csv.DictReader(io.StringIO((_HFE / "variants.csv").read_text())))
    site = [r for r in rows if r["chrom"] == "6" and r["start"] == "26091590"]
    assert {r["alts"] for r in site} == {"A", "T"}
    assert all(r["rsid"] == "" for r in site)


def test_every_study_row_grounds_a_variant_the_module_carries() -> None:
    """The orphan bug this example found: a study must carry the identity its variant row got."""
    from just_dna_format.base import derive_variant_key

    def key(row: dict) -> str:
        return derive_variant_key(
            row["rsid"] or None, row["chrom"] or None,
            int(row["start"]) if row["start"] else None, row["ref"] or None,
        )

    variants = {key(r) for r in csv.DictReader(io.StringIO((_HFE / "variants.csv").read_text()))}
    studies = {key(r) for r in csv.DictReader(io.StringIO((_HFE / "studies.csv").read_text()))}
    assert studies <= variants, studies - variants


# ── The CYP2C19 reference example (0.5.1) ───────────────────────────────────────────────────────
# The PGx counterpart to the HFE panel: drafted complete from CPIC, then curated by *removal*.

_CYP2C19 = Path(__file__).resolve().parents[2] / "reference_examples" / "cyp2c19_star_alleles"


def test_the_cyp2c19_example_compiles_and_is_a_fixed_point(tmp_path: Path) -> None:
    result = validate_spec(_CYP2C19)
    assert result.valid, result.errors
    first = compile_module(_CYP2C19, tmp_path / "out1").manifest
    reverse_module(tmp_path / "out1", tmp_path / "back")
    second = compile_module(tmp_path / "back", tmp_path / "out2").manifest
    assert first.artifact.digest == second.artifact.digest


def test_every_star_allele_it_uses_is_one_it_defines() -> None:
    """The curation the new cross-table warning prompted: CPIC pairs alleles it does not define, and
    a caller can never emit one of those — so the example carries none, and validates clean."""
    def rows(name: str) -> list[dict]:
        return list(csv.DictReader(io.StringIO((_CYP2C19 / name).read_text())))

    defined = {r["haplotype_name"] for r in rows("haplotypes.csv")} | {"*1"}
    used = {r["allele"] for r in rows("allele_function.csv")}
    for row in rows("diplotypes.csv"):
        used.update((row["haplotype_a"], row["haplotype_b"]))
    assert used <= defined, sorted(used - defined)
    assert not [w for w in validate_spec(_CYP2C19).warnings if "not defined in haplotypes.csv" in w]


def test_the_cpic_source_is_recorded_so_the_licence_gate_can_see_it() -> None:
    """CPIC is CC BY-SA with a no-sale clause. A module built from it that records no source leaves
    the compile gate nothing to key on — which is what the provider used to produce."""
    sources = list(csv.DictReader(io.StringIO((_CYP2C19 / "sources.csv").read_text())))
    cpic = [s for s in sources if s["source"] == "cpic"]
    assert cpic, "the module is entirely CPIC-derived and must say so"
    assert cpic[0]["layer"] == "annotation"
    assert cpic[0]["commercial_use"] == "false"
    assert cpic[0]["declared_use"] == "non_commercial"


def test_stripping_the_declaration_makes_the_compile_refuse(tmp_path: Path) -> None:
    """Proves the recorded row is load-bearing rather than decorative."""
    import shutil

    spec = tmp_path / "spec"
    shutil.copytree(_CYP2C19, spec)
    rows = list(csv.DictReader(io.StringIO((spec / "sources.csv").read_text())))
    for row in rows:
        row["declared_use"] = ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (spec / "sources.csv").write_text(buf.getvalue())

    result = compile_module(spec, tmp_path / "out")
    assert not result.success
    assert any("forbid sale" in e for e in result.errors)


def test_drug_columns_are_empty_on_purpose() -> None:
    """This module answers genotype → phenotype and stops. CPIC's prescribing recommendations live
    in a resource the provider does not read, so filling these would mean inventing them."""
    rows = list(csv.DictReader(io.StringIO((_CYP2C19 / "diplotypes.csv").read_text())))
    assert rows
    for column in ("drug", "evidence_level", "recommendation_strength"):
        assert all(not r.get(column) for r in rows), column
