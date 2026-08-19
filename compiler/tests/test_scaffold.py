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
from just_dna_compiler.draft import DRAFTABLE, DraftError, model_for
from just_dna_compiler.scaffold import (
    COMPANION_KINDS,
    MODULE_SPEC,
    companions_for,
    module_spec_template,
    scaffold_module,
)
from just_dna_format.base import field_vocabularies
from just_dna_format.layout import SOURCES_CSV, resolve_sidecar, sidecar_spellings
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
    """A closed-vocabulary column takes a member read off the field's own marker; everything else
    falls back to `"1"`, which is valid for a number or a free string and for nothing else. Derived
    rather than listed, so a new vocabulary column needs no edit here (S21 arrived as `layer: '1'`)."""
    rows = list(csv.DictReader(io.StringIO(path.read_text())))
    fieldnames = list(rows[0])
    from_vocabulary = {
        column: marker["options"][0]
        for column, marker in field_vocabularies(model_for(path.name)).items()
        if marker["closed"] and marker["options"]
    }
    values = {**from_vocabulary, **_FILL, **_FILL_BY_KIND.get(path.name, {})}
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
    # The licence sidecar is not a table a module can consist of — "no recognized table" is the right
    # refusal for a module that is only a licence file — so it is scaffolded beside the SNP core. Every
    # other kind stands alone (S21). Derived from the spellings rather than naming one, because it has
    # two of them since 0.6 (RM51) and a hand-kept name here would have covered only the older one.
    licence_sidecar = kind in sidecar_spellings(SOURCES_CSV)
    kinds = ["variants.csv", kind] if licence_sidecar else [kind]
    plan = scaffold_module(spec_dir, kinds=kinds, name="demo")
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


def _licence_table(spec_dir: Path) -> Path:
    """The module's licence table under whatever spelling and location it keeps it (RM51/RM49).

    Resolved rather than named: these fixtures are real reference examples, and the corpus carries
    both spellings on purpose so neither path goes unexercised.
    """
    found = resolve_sidecar(spec_dir, SOURCES_CSV)
    assert found is not None, f"{spec_dir.name} must carry a licence table"
    return found


def test_the_cpic_source_is_recorded_so_the_licence_gate_can_see_it() -> None:
    """CPIC is CC BY-SA with a no-sale clause. A module built from it that records no source leaves
    the compile gate nothing to key on — which is what the provider used to produce."""
    sources = list(csv.DictReader(io.StringIO(_licence_table(_CYP2C19).read_text())))
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
    rows = list(csv.DictReader(io.StringIO(_licence_table(spec).read_text())))
    for row in rows:
        row["declared_use"] = ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    _licence_table(spec).write_text(buf.getvalue())

    result = compile_module(spec, tmp_path / "out")
    assert not result.success
    assert any("forbid sale" in e for e in result.errors)


def test_the_drug_rows_sit_beside_the_phenotype_rows_not_instead_of_them() -> None:
    """Two questions, two row sets, one table: `_TABLE_DUPE_KEYS` keys on `drug`, so a pair can
    carry both "what phenotype is this" and "what does CPIC advise for clopidogrel"."""
    rows = list(csv.DictReader(io.StringIO((_CYP2C19 / "diplotypes.csv").read_text())))
    plain = [r for r in rows if not r["drug"]]
    drugged = [r for r in rows if r["drug"]]
    assert plain and drugged
    assert {r["drug"] for r in drugged} == {"clopidogrel"}
    # the same pair appears once per question, never twice for the same one
    def pairs(rs):
        return [(r["gene"], r["haplotype_a"], r["haplotype_b"]) for r in rs]

    assert len(set(pairs(plain))) == len(plain)
    assert len(set(pairs(drugged))) == len(drugged)


def test_evidence_level_stays_empty_because_it_is_a_different_axis() -> None:
    """PharmGKB grades the evidence; CPIC grades the action. One column for both would repeat the
    `state`-overloading mistake, so the CPIC provider fills only `recommendation_strength`."""
    rows = [
        r
        for r in csv.DictReader(io.StringIO((_CYP2C19 / "diplotypes.csv").read_text()))
        if r["drug"]
    ]
    # Absent from the header entirely, not merely blank: drafting only adds columns its rows fill,
    # so a column nothing writes never appears — which is the stronger statement.
    assert all(not r.get("evidence_level") for r in rows)
    assert "evidence_level" not in rows[0]
    assert {r["recommendation_strength"] for r in rows} <= {
        "strong", "moderate", "optional", "no_recommendation", ""
    }
    assert any(r["recommendation_strength"] for r in rows)


# ── The APOE example (0.5.1) — the meta-conclusion feasibility probe ─────────────────────────────

_APOE = Path(__file__).resolve().parents[2] / "reference_examples" / "apoe_epsilon"


def test_the_apoe_example_compiles_and_is_a_fixed_point(tmp_path: Path) -> None:
    assert validate_spec(_APOE).valid, validate_spec(_APOE).errors
    first = compile_module(_APOE, tmp_path / "out1").manifest
    reverse_module(tmp_path / "out1", tmp_path / "back")
    second = compile_module(tmp_path / "back", tmp_path / "out2").manifest
    assert first.artifact.digest == second.artifact.digest


def test_a_two_snp_haplotype_needs_no_predicate() -> None:
    """The finding this module exists for. Principle 1's escape-hatch example is `rs429358==C AND
    rs7412==C` — which is ε4 — and `HaplotypeRow` already expresses it as two junction rows, because
    same-strand co-location is what a haplotype table *is*."""
    rows = list(csv.DictReader(io.StringIO((_APOE / "haplotypes.csv").read_text())))
    by_haplotype: dict[str, dict[str, str]] = {}
    for row in rows:
        by_haplotype.setdefault(row["haplotype_name"], {})[row["rsid"]] = row["allele"]
    # every epsilon allele is pinned at BOTH sites — one alone cannot tell ε4 from ε1
    assert all(set(sites) == {"rs429358", "rs7412"} for sites in by_haplotype.values())
    assert by_haplotype["e4"] == {"rs429358": "C", "rs7412": "C"}
    assert by_haplotype["e2"] == {"rs429358": "T", "rs7412": "T"}
    assert by_haplotype["e3"] == {"rs429358": "T", "rs7412": "C"}


def test_every_diplotype_pairs_defined_haplotypes() -> None:
    diplotypes = list(csv.DictReader(io.StringIO((_APOE / "diplotypes.csv").read_text())))
    defined = {r["haplotype_name"] for r in csv.DictReader(io.StringIO((_APOE / "haplotypes.csv").read_text()))}
    used = {h for r in diplotypes for h in (r["haplotype_a"], r["haplotype_b"])}
    assert used <= defined
    # all six pairs over three haplotypes, none repeated
    assert len(diplotypes) == 6
    assert len({(r["haplotype_a"], r["haplotype_b"]) for r in diplotypes}) == 6


def test_the_opposing_diplotype_declares_unknown_rather_than_averaging() -> None:
    """ε2/ε4 carries opposing alleles; the risk is not the sum of its parts, so the module says so
    instead of splitting the difference."""
    rows = {
        (r["haplotype_a"], r["haplotype_b"]): r
        for r in csv.DictReader(io.StringIO((_APOE / "diplotypes.csv").read_text()))
    }
    assert rows[("e2", "e4")]["direction"] == "unknown"
    assert rows[("e3", "e4")]["direction"] == "risk"
    assert rows[("e2", "e3")]["direction"] == "protective"


def test_epsilon_names_are_legal_in_every_pgx_table_now() -> None:
    """The defect this probe found (RM30) and its fix: `AlleleFunctionRow.allele` demanded a leading
    `*` while the other two tables accepted any name, so `e4` was legal in two of three. All three
    now share one rule. APOE still carries no allele-function table — an ε allele has no CPIC
    activity value — but that is now a curation choice rather than something the schema forbade."""
    from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, HaplotypeRow

    HaplotypeRow(haplotype_name="e4", rsid="rs429358", allele="C", gene="APOE")
    DiplotypeRow(gene="APOE", haplotype_a="e3", haplotype_b="e4", conclusion="c")
    AlleleFunctionRow(gene="APOE", allele="e4")
    assert not (_APOE / "allele_function.csv").exists()


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_a_generated_stub_is_refused_for_being_a_stub(kind: str, tmp_path: Path) -> None:
    """The guarantee `stub_template`'s docstring prints, asserted for the first time (RM76).

    That docstring says an unreplaced stub *"**cannot compile** — `vocab.reject_template_placeholders`
    refuses it by name and row, in both modes"*, and until this landed nothing checked it. It held
    only where a model happened to inherit `AuthoredModel`, and `sources.csv` — the one fact sidecar a
    human writes, the only table the compile licence gate reads, and draftable since S21 — did not.

    **The assertion is on the guard's own wording, not merely on a refusal, and the first draft of
    this test got that wrong.** Asserting "some error mentions `<<REPLACE>>`" passed on the *buggy*
    code, because `stub_template` stubs `layer` too and its vocabulary validator quotes the token back
    while rejecting it as a non-member. A guard that is green because a different mechanism happens to
    fire is the S21 / D6-2 / R2-3 shape — a test proving less than its name says — arriving inside the
    repair for one.

    Parametrized over `DRAFTABLE` rather than naming the kinds, because the defect was a model quietly
    outside a set, and a hand-written list would have to be extended by whoever forgot the base class.
    The *loader* is what is exercised, since that is the path a compile takes.
    """
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_compiler.draft import stub_template

    text = stub_template(kind)
    assert TEMPLATE_PLACEHOLDER in text, f"{kind} stubs nothing, so this proves nothing"

    path = tmp_path / kind
    path.write_text(text, encoding="utf-8")
    rows, errors, _ = _load_csv_rows(path, model_for(kind), kind)

    assert any("unreplaced template placeholder" in e for e in errors), (kind, errors)
    # And nothing survived to reach a parquet — a partly-accepted stub file is the silent-success
    # shape, not a milder version of a refusal.
    assert rows == []


def test_a_stub_in_a_free_text_column_alone_is_still_refused(tmp_path: Path) -> None:
    """The exact hole, isolated: `sources.csv` with a valid `layer` and only `source` unfilled.

    This is what was probed on `reference_examples/hfe_hemochromatosis` — the module **compiled green
    under `--strict`** and `manifest.sources` published `"sources": ["<<REPLACE>>"]`, inside the block
    its own `signature` is computed over, so a signed module's attribution ledger named a template
    placeholder as the source it was accounting for. A vocabulary column catches a stub by accident;
    `source` is free text by design, and free text is most of this table.
    """
    from just_dna_compiler.compiler import _load_csv_rows
    from just_dna_format.sources import SourceRow

    path = tmp_path / SOURCES_CSV
    path.write_text(f"source,layer,license\n{TEMPLATE_PLACEHOLDER},annotation,CC0\n", encoding="utf-8")
    rows, errors, _ = _load_csv_rows(path, SourceRow, SOURCES_CSV)

    assert rows == []
    assert any("unreplaced template placeholder" in e and "source" in e for e in errors), errors


def test_studies_beside_a_binning_table_pulls_no_variants_stub(tmp_path: Path) -> None:
    """S49: RM47 made this the *intended* shape, and the scaffold was inviting an empty table into it.

    The premise is checked here rather than assumed — the module really does compile strict-green with
    no `variants.csv` — because that is the whole reason the stub was wrong.
    """
    spec = tmp_path / "smn1"
    plan = scaffold_module(spec, name="smn1_cn", kinds=["copynumbers.csv", "studies.csv"], rows=0)
    assert [f.name for f in plan.created] == [MODULE_SPEC, "copynumbers.csv", "studies.csv"]
    assert plan.warnings == []

    (spec / MODULE_SPEC).write_text(
        "schema_version: '1.0'\nmodule:\n  name: smn1_cn\n  title: SMN1 copy number\n"
        "  report_title: SMN1 copy number\n  description: SMN1 copy-number bins grounded in one study.\n"
        "defaults:\n  curator: probe\n  method: literature\ngenome_build: GRCh38\n",
        encoding="utf-8",
    )
    (spec / "copynumbers.csv").write_text(
        "measure_kind,measure_min,measure_max,gene,phenotype,conclusion,pmid\n"
        "copy_number,0,0,SMN1,Spinal muscular atrophy type I,Homozygous SMN1 deletion,9382095\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        "pmid,conclusion\n9382095,SMN1 copy number correlates with SMA severity\n", encoding="utf-8"
    )
    result = validate_spec(spec, strict=True)
    assert result.valid, result.errors
    assert not any("variants" in w for w in result.warnings)


def test_studies_truly_alone_still_pulls_variants() -> None:
    """The case the pair was added for is unchanged — the condition is "alone", not "never"."""
    assert companions_for(["studies.csv"]) == ["variants.csv"]


def test_variants_pulls_studies_unconditionally() -> None:
    """That direction has no condition: a variant claim needs grounding however the module is composed."""
    assert companions_for(["variants.csv"]) == ["studies.csv"]
    assert companions_for(["variants.csv", "copynumbers.csv"]) == ["studies.csv"]


def test_the_licence_ledger_does_not_count_as_a_recognized_table() -> None:
    """`sources.csv` cannot satisfy composition, so `studies.csv` beside it is still alone."""
    assert companions_for(["studies.csv", SOURCES_CSV]) == ["variants.csv"]


def test_every_table_kind_grounds_a_studies_row_on_its_own() -> None:
    """Set equality over the walked set: a table kind added later must not reintroduce the stub."""
    kinds = {k for k in DRAFTABLE if k not in {"variants.csv", "studies.csv", SOURCES_CSV, "licensing.csv"}}
    assert kinds
    assert {k: companions_for([k, "studies.csv"]) for k in kinds} == dict.fromkeys(kinds, [])


def test_the_companion_mapping_itself_is_unchanged() -> None:
    """The constant still states the pair; only the *application* is conditional (S49)."""
    assert COMPANION_KINDS == {"variants.csv": ("studies.csv",), "studies.csv": ("variants.csv",)}
