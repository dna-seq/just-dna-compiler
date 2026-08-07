"""The drafting mechanism (`just_dna_compiler.draft`, 0.5).

What is actually being pinned here is the *append* semantics, so the tests are sequences rather than
single calls: a helper that works once and then self-defuses would pass a one-shot test and still make
a multi-gene module unbuildable, which is the failure mode this design exists to avoid.
"""

import csv
import io
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    _load_csv_rows,
    compile_module,
    reverse_module,
    validate_spec,
)
from just_dna_compiler.draft import (
    DRAFTABLE,
    DraftError,
    append_rows,
    authoring_requirements,
    blank_template,
    field_category,
    model_for,
    natural_key,
    required_fields,
    stub_template,
)
from just_dna_format.base import authored_field_names
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: drafted\n  title: Drafted\n  description: d\n  report_title: Drafted\n"
    "genome_build: GRCh38\n"
)


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    return spec


def _function(gene: str, allele: str, **kw) -> AlleleFunctionRow:
    return AlleleFunctionRow(gene=gene, allele=allele, **kw)


# ── the append sequence ─────────────────────────────────────────────────────────────────────────


def test_drafting_a_second_gene_adds_to_the_first(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    first = append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*2", function_status="no_function"),
        _function("CYP2C19", "*17", function_status="increased_function"),
    ])
    assert len(first.added) == 2 and first.written
    after_first = (spec / "allele_function.csv").read_text(encoding="utf-8")

    second = append_rows(spec, "allele_function.csv", [
        _function("CYP2D6", "*4", function_status="no_function"),
    ])
    assert len(second.added) == 1

    text = (spec / "allele_function.csv").read_text(encoding="utf-8")
    # The first gene's bytes are still there, unchanged and still first: appending must not reorder,
    # because authored row order is preserved through compile → reverse and parquet bytes depend on it.
    assert text.startswith(after_first)
    assert [line.split(",")[1] for line in text.strip().splitlines()[1:]] == ["*2", "*17", "*4"]


def test_re_drafting_the_same_gene_adds_nothing_and_is_not_an_error(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    rows = [_function("CYP2C19", "*2", function_status="no_function")]
    append_rows(spec, "allele_function.csv", rows)
    before = (spec / "allele_function.csv").read_text(encoding="utf-8")

    again = append_rows(spec, "allele_function.csv", rows)
    assert again.added == [] and len(again.already_present) == 1
    assert not again.written
    assert (spec / "allele_function.csv").read_text(encoding="utf-8") == before


def test_a_row_that_disagrees_is_reported_and_left_alone(tmp_path: Path) -> None:
    # The line between drafting and co-authoring: appending new rows is fine, editing a cell a human
    # wrote is not. What the source now says about an existing row is a finding, not an edit.
    spec = _spec(tmp_path)
    append_rows(spec, "allele_function.csv", [_function("CYP2C19", "*2", function_status="no_function")])
    before = (spec / "allele_function.csv").read_text(encoding="utf-8")

    report = append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*2", function_status="decreased_function"),
    ])
    assert len(report.differs) == 1
    outcome = report.differs[0]
    assert outcome.differences["function_status"] == ("no_function", "decreased_function")
    assert "left unchanged" in str(outcome)
    assert (spec / "allele_function.csv").read_text(encoding="utf-8") == before


def test_unset_source_columns_are_not_counted_as_disagreement(tmp_path: Path) -> None:
    # A scaffold that fills three of twelve columns is not claiming the other nine are empty.
    spec = _spec(tmp_path)
    append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*2", function_status="no_function", activity_value=0.0),
    ])
    report = append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*2", function_status="no_function"),  # no activity_value
    ])
    assert report.differs == [] and len(report.already_present) == 1


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    rows = [_function("CYP2C19", "*2", function_status="no_function")]
    report = append_rows(spec, "allele_function.csv", rows, dry_run=True)
    assert len(report.added) == 1
    assert not report.written
    assert not (spec / "allele_function.csv").exists()
    # …and the real run then does exactly what the dry run said it would.
    assert len(append_rows(spec, "allele_function.csv", rows).added) == 1


def test_a_duplicate_inside_one_batch_is_caught_too(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    report = append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*2", function_status="no_function"),
        _function("CYP2C19", "*2", function_status="no_function"),
    ])
    assert len(report.added) == 1 and len(report.already_present) == 1


# ── keys, headers, and what the compiler then thinks ────────────────────────────────────────────


def test_the_keys_are_the_compilers_own(tmp_path: Path) -> None:
    # Reusing `_TABLE_DUPE_KEYS` is what guarantees an append cannot create a row the compiler will
    # reject as a duplicate. A parallel key definition here would drift.
    assert natural_key(_function("CYP2D6", "*4")) == ("CYP2D6", "*4")
    assert natural_key(VariantRow(rsid="rs1", genotype="A/G", state="risk", conclusion="c")) == (
        "rs1", "A/G",
    )
    assert natural_key(StudyRow(rsid="rs1", pmid="12345678")) == ("rs1", "12345678")
    # A binning row has no equality key on purpose: its duplicate rule is overlap, judged at compile.
    assert natural_key(RepeatAlleleRow(
        gene="HTT", repeat_unit="CAG", measure_min=40, conclusion=">=40"
    )) is None


def test_an_unkeyed_kind_is_appended_and_the_overlap_is_left_to_the_compiler(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    report = append_rows(spec, "repeat_alleles.csv", [
        RepeatAlleleRow(gene="HTT", repeat_unit="CAG", measure_min=27, measure_max=35, conclusion="i"),
        RepeatAlleleRow(gene="HTT", repeat_unit="CAG", measure_min=36, measure_max=39, conclusion="r"),
    ])
    assert [o.status for o in report.outcomes] == ["appended_unkeyed"] * 2


def test_a_new_column_widens_the_header_without_reformatting_existing_cells(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").write_text(
        "gene,allele,function_status\nCYP2C19,*2,no_function\n", encoding="utf-8"
    )
    report = append_rows(spec, "allele_function.csv", [
        _function("CYP2D6", "*4", function_status="no_function", activity_value=0.0),
    ])
    assert report.header_extended == ["activity_value"]
    lines = (spec / "allele_function.csv").read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "gene,allele,function_status,activity_value"
    assert lines[1] == "CYP2C19,*2,no_function,"  # gains an empty cell, nothing else changes


def test_a_drafted_table_compiles_and_round_trips(tmp_path: Path) -> None:
    # The real contract: what the helper writes must be a module, not just a plausible CSV.
    spec = _spec(tmp_path)
    append_rows(spec, "allele_function.csv", [
        _function("CYP2C19", "*1", function_status="normal_function", activity_value=1.0),
        _function("CYP2C19", "*2", function_status="no_function", activity_value=0.0),
    ])
    append_rows(spec, "diplotypes.csv", [
        DiplotypeRow(gene="CYP2C19", haplotype_a="*1", haplotype_b="*2", phenotype="IM",
                     conclusion="intermediate metabolizer", recommendation_strength="moderate"),
    ])
    assert validate_spec(spec).valid

    out = tmp_path / "out"
    first = compile_module(spec, out, resolve_with_ensembl=False)
    assert first.success, first.errors
    reverse_module(out, tmp_path / "reversed")
    second = compile_module(tmp_path / "reversed", tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert pl.read_parquet(out / "diplotypes.parquet")["recommendation_strength"].to_list() == [
        "moderate"
    ]


def test_appending_does_not_move_an_already_compiled_digest_for_untouched_rows(tmp_path: Path) -> None:
    # Appending must be strictly additive to the artifact: the rows that were there compile to the
    # same bytes in the same order, so only the new row's contribution is new.
    spec = _spec(tmp_path)
    append_rows(spec, "allele_function.csv", [_function("CYP2C19", "*2", function_status="no_function")])
    before = compile_module(spec, tmp_path / "a", resolve_with_ensembl=False)
    original = pl.read_parquet(tmp_path / "a" / "allele_function.parquet")

    append_rows(spec, "allele_function.csv", [_function("CYP2D6", "*4", function_status="no_function")])
    after = compile_module(spec, tmp_path / "b", resolve_with_ensembl=False)
    grown = pl.read_parquet(tmp_path / "b" / "allele_function.parquet")

    assert before.manifest.artifact.digest != after.manifest.artifact.digest  # new content, new digest
    assert grown.head(original.height).equals(original)  # …but the old rows are untouched and first


# ── the SNP core, whose model carries compiler-managed columns ──────────────────────────────────
#
# Every test above drafts into a PGx or binning table, and none of those models has a field the
# compiler stamps. `VariantRow` has two (`variant_key`, `authored_ident`), and rendering them wrote a
# `variants.csv` the compiler then refused to load — the list-typed `authored_ident` came back as the
# bare string `rsid`. RM26 roadmaps a ClinVar → `variants.csv` provider, so this is the path next.


def _variant(rsid: str, genotype: str, **kw) -> VariantRow:
    # A negative weight for a `risk` state: the sign convention is positive=protective, and the
    # compiler warns on the mismatch.
    return VariantRow(
        rsid=rsid, genotype=genotype, **{"state": "risk", "weight": -0.5, "conclusion": "c", **kw}
    )


def _study(rsid: str, pmid: str) -> StudyRow:
    return StudyRow(rsid=rsid, pmid=pmid, conclusion="grounding evidence")


def test_a_drafted_variants_table_reloads_and_compiles(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    append_rows(spec, "variants.csv", [
        _variant("rs1801133", "C/T", gene="MTHFR"),
        _variant("rs334", "A/A", gene="HBB"),
    ])
    append_rows(spec, "studies.csv", [_study("rs1801133", "12345678"), _study("rs334", "23456789")])
    header = (spec / "variants.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert {"variant_key", "authored_ident"}.isdisjoint(header)

    # The real contract: what was written is a module, not merely a plausible CSV.
    assert validate_spec(spec).valid
    out = tmp_path / "out"
    first = compile_module(spec, out, resolve_with_ensembl=False)
    assert first.success, first.errors
    # The stamped identity still reaches the artifact — it is derived, not authored.
    weights = pl.read_parquet(out / "weights.parquet")
    assert weights["variant_key"].to_list() == ["rs1801133", "rs334"]
    assert weights["authored_ident"].to_list() == [["rsid"], ["rsid"]]


def test_drafting_into_variants_round_trips_to_the_same_digest(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    append_rows(spec, "variants.csv", [_variant("rs1801133", "C/T")])
    append_rows(spec, "studies.csv", [_study("rs1801133", "12345678")])
    out = tmp_path / "out"
    first = compile_module(spec, out, resolve_with_ensembl=False)
    assert first.success, first.errors
    reverse_module(out, tmp_path / "reversed")
    second = compile_module(tmp_path / "reversed", tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest


def test_a_file_missing_its_final_newline_keeps_its_last_row_intact(tmp_path: Path) -> None:
    # A hand-authored CSV often has no trailing newline; appending onto it would glue the first new
    # row to the author's last one — corrupting a row this module promises never to touch.
    spec = _spec(tmp_path)
    path = spec / "variants.csv"
    path.write_bytes(b"rsid,genotype,state,weight,conclusion\nrs334,A/A,risk,1.0,sickle cell")
    report = append_rows(spec, "variants.csv", [_variant("rs1801133", "C/T")])

    assert report.header_extended == []  # the header already fits, so this is the append branch
    assert path.read_bytes().startswith(
        b"rsid,genotype,state,weight,conclusion\nrs334,A/A,risk,1.0,sickle cell"
    )  # the author's bytes, untouched
    rows, errors, _ = _load_csv_rows(path, VariantRow, "variants.csv")
    assert errors == []
    assert [(r.rsid, r.conclusion) for r in rows] == [
        ("rs334", "sickle cell"),
        ("rs1801133", "c"),
    ]


def test_a_zero_byte_file_is_drafted_into_rather_than_refused(tmp_path: Path) -> None:
    # A bare `touch` has no header to key against and no rows to lose, so it is the absent case.
    spec = _spec(tmp_path)
    path = spec / "variants.csv"
    path.write_bytes(b"")
    append_rows(spec, "variants.csv", [_variant("rs1801133", "C/T")])
    rows, errors, _ = _load_csv_rows(path, VariantRow, "variants.csv")
    assert errors == []
    assert [r.rsid for r in rows] == ["rs1801133"]


def test_a_source_naming_fewer_identity_columns_is_not_a_disagreement(tmp_path: Path) -> None:
    # The author wrote rsid + coordinate; the source names only the rsid. `authored_ident` therefore
    # differs between the two rows, but that is a fact about how each was written, not a claim about
    # the variant — reporting it would put a `differs` on every hand-annotated row.
    spec = _spec(tmp_path)
    append_rows(spec, "variants.csv", [
        _variant("rs1801133", "C/T", chrom="1", start=11796321, ref="G"),
    ])
    report = append_rows(spec, "variants.csv", [_variant("rs1801133", "C/T")])
    assert [o.status for o in report.outcomes] == ["already_present"]
    assert report.differs == []


# ── templates and misuse ────────────────────────────────────────────────────────────────────────


def test_blank_template_comes_from_the_live_model(tmp_path: Path) -> None:
    header = blank_template("repeat_alleles.csv").strip().split(",")
    assert header == authored_field_names(model_for("repeat_alleles.csv"))
    assert {"gene", "repeat_unit", "conclusion"} <= set(header)
    assert set(required_fields("repeat_alleles.csv")) <= set(header)


def test_a_template_never_offers_a_compiler_managed_column() -> None:
    # `variant_key`/`authored_ident` are stamped by `_freeze_identity` and never written back by
    # `reverse_module`, so a template that listed them would invite an author to fill a column the
    # compiler overwrites — and `authored_ident` is a `list[str]`, so the rendered cell would not even
    # reload. Asserted against the marker, so a newly-marked field is covered without editing this.
    header = blank_template("variants.csv").strip().split(",")
    assert header == authored_field_names(VariantRow)
    assert {"variant_key", "authored_ident"}.isdisjoint(header)
    assert {"rsid", "genotype", "state", "conclusion"} <= set(header)


def test_an_unknown_table_kind_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DraftError) as exc:
        append_rows(tmp_path, "pasta_recipes.csv", [])
    assert "not an authored table" in str(exc.value)


def test_an_invalid_existing_file_stops_the_draft(tmp_path: Path) -> None:
    # Keying against a file that does not parse would silently treat every row as new and duplicate
    # the whole table.
    spec = _spec(tmp_path)
    (spec / "allele_function.csv").write_text("gene,allele\n,\n", encoding="utf-8")
    with pytest.raises(DraftError) as exc:
        append_rows(spec, "allele_function.csv", [_function("CYP2C19", "*2")])
    assert "does not validate" in str(exc.value)


# ── the shipped reference example (real data, not a fixture) ────────────────────────────────────


def test_the_htt_reference_example_compiles_and_is_a_fixed_point(tmp_path: Path) -> None:
    """`reference_examples/htt_repeat_expansion/` is the binning family's first real compiled module.

    The quantity/binning path had no dogfood before this — §4–§8 of REFERENCE_EXAMPLES.md were
    sketches — and it is where the sharp edges are: inclusive bounds, the mandatory `unresolved`
    sentinel, and a module with no variants and therefore no studies.
    """
    example = Path(__file__).resolve().parents[2] / "reference_examples" / "htt_repeat_expansion"
    assert not (example / "variants.csv").exists()  # one CSV = one concern
    assert not (example / "studies.csv").exists()   # required only where variants are

    validation = validate_spec(example)
    assert validation.valid, validation.errors

    first = compile_module(example, tmp_path / "out", resolve_with_ensembl=False)
    assert first.success, first.errors
    reverse_module(tmp_path / "out", tmp_path / "reversed")
    second = compile_module(tmp_path / "reversed", tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature


def test_the_htt_bins_cover_every_count_with_exactly_one_answer(tmp_path: Path) -> None:
    """The property the table exists to have: any count a caller can report selects one bin, and a
    caller that reports nothing selects the sentinel rather than falling through to 'normal'."""
    from just_dna_compiler.compiler import _load_csv_rows

    example = Path(__file__).resolve().parents[2] / "reference_examples" / "htt_repeat_expansion"
    rows, errors, _ = _load_csv_rows(example / "repeat_alleles.csv", RepeatAlleleRow, "repeat_alleles.csv")
    assert not errors, errors

    resolved = [r for r in rows if not r.unresolved]
    sentinels = [r for r in rows if r.unresolved]
    assert len(sentinels) == 1 and sentinels[0].measure_min is None

    def selected(count: int) -> list[str]:
        return [
            r.conclusion for r in resolved
            if (r.measure_min is None or count >= r.measure_min)
            and (r.measure_max is None or count <= r.measure_max)
        ]

    for count in (6, 26, 27, 35, 36, 39, 40, 120):
        assert len(selected(count)) == 1, (count, selected(count))
    # …and the clinically load-bearing boundaries land where the literature puts them.
    assert "reduced penetrance" in selected(36)[0]
    assert "fully penetrant" in selected(40)[0]
    assert "intermediate" in selected(27)[0]


# ── Templating: stubs, the three-way field split, and the placeholder guard (0.5) ────────────────
# The bug this section exists for: `blank_template` emitted every authored column and
# `required_fields` named only the field-local required ones, so an author who filled exactly what
# they were told to fill got a compile error about `measure_kind`/`unresolved` — columns that have a
# default but reject the `None` an empty cell becomes. Every test here is parametrized over
# `DRAFTABLE`, so a new table kind is covered without editing them.

#: One valid value per stubbed column, for filling a template in the tests below. Domain constants,
#: which CLAUDE.md's testing rules explicitly allow hardcoding — unlike row counts.
_FILL = {
    "rsid": "rs1801133", "genotype": "A/G", "state": "risk", "conclusion": "an interpretation",
    "pmid": "12345678", "gene": "HTT", "repeat_unit": "CAG", "haplotype_name": "*4",
    "haplotype_a": "*1", "haplotype_b": "*4", "pgs_id": "PGS000135", "drug": "warfarin",
    "tissue": "blood", "reference_sequence": "NC_012920.1",
}
_FILL_BY_KIND = {
    # `allele` is a star-allele here and a nucleotide on HaplotypeRow — same name, different grammar.
    "allele_function.csv": {"allele": "*4"},
    "haplotypes.csv": {"allele": "A"},
}


def _fill(kind: str, text: str) -> str:
    """Replace every placeholder in a stub template with a valid value, preserving row order."""
    rows = list(csv.DictReader(io.StringIO(text)))
    fieldnames = list(rows[0])
    values = {**_FILL, **_FILL_BY_KIND.get(kind, {})}
    for row in rows:
        for column, cell in row.items():
            if cell == TEMPLATE_PLACEHOLDER:
                row[column] = values.get(column, "1")
        if row.get("unresolved") == "false" and not row.get("measure_min"):
            row["measure_min"] = "1"  # a resolved bin needs at least one bound
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_an_unreplaced_stub_never_loads(kind: str, tmp_path) -> None:
    """The whole point of a sentinel over a blank cell: it cannot reach a compiled module, and it
    says so by name rather than as a type error about a column the author never wrote."""
    path = tmp_path / kind
    path.write_text(stub_template(kind))
    rows, errors, _ = _load_csv_rows(path, model_for(kind), kind)
    assert rows == []
    assert errors and all(TEMPLATE_PLACEHOLDER in e for e in errors)


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_a_filled_stub_loads_with_no_errors(kind: str, tmp_path) -> None:
    """The regression that matters: replacing only the stubbed cells must be enough.

    On the pre-0.5.1 generator this failed for all four binning kinds — `measure_kind` and
    `unresolved` have defaults, so nothing told the author to fill them, and an empty cell arrives as
    `None` rather than as the default."""
    path = tmp_path / kind
    path.write_text(_fill(kind, stub_template(kind)))
    rows, errors, _ = _load_csv_rows(path, model_for(kind), kind)
    assert errors == []
    assert rows


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_defaulted_columns_are_written_out_not_left_blank(kind: str) -> None:
    """A `defaulted` column is written with its default; an `optional` one is left empty."""
    model = model_for(kind)
    requirements = authoring_requirements(kind)
    header, first, *_ = stub_template(kind).splitlines()
    cells = dict(zip(header.split(","), next(csv.reader([first])), strict=True))
    for column, rendered in requirements["defaulted"].items():
        assert cells[column] == rendered, f"{kind}:{column} should carry its default"
        assert field_category(model, column) == "defaulted"
    # An identity column is field-level optional (`rsid` has a default of None) but is stubbed,
    # because a model validator requires one of the groups. Exclude the group actually offered.
    offered_identity = set(requirements["any_of"][0]) if requirements["any_of"] else set()
    for column in requirements["optional"]:
        if column in offered_identity:
            assert cells[column] == TEMPLATE_PLACEHOLDER
            continue
        assert cells[column] == "", f"{kind}:{column} is optional and should be blank"


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_a_stub_offers_exactly_the_authored_surface(kind: str) -> None:
    """Asserted against the marker, so a newly compiler-managed field is covered without an edit."""
    header = stub_template(kind).splitlines()[0].split(",")
    assert header == authored_field_names(model_for(kind))


def test_a_stub_asks_for_one_identity_group_not_every_alternative() -> None:
    """`rsid` OR `chrom`+`start` — stubbing both would tell the author to supply two identities."""
    header, first, *_ = stub_template("variants.csv").splitlines()
    cells = dict(zip(header.split(","), next(csv.reader([first])), strict=True))
    assert cells["rsid"] == TEMPLATE_PLACEHOLDER
    assert cells["chrom"] == "" and cells["start"] == ""


def test_a_binning_stub_carries_the_mandatory_unresolved_companion() -> None:
    """A binning table without the sentinel is incomplete by contract, so the template supplies it
    rather than letting the author meet that rule as a compile error about a row they never wrote."""
    rows = list(csv.DictReader(io.StringIO(stub_template("repeat_alleles.csv"))))
    assert [r["unresolved"] for r in rows] == ["false", "true"]
    sentinel = rows[-1]
    assert sentinel["measure_min"] == "" and sentinel["measure_max"] == ""


def test_authoring_requirements_names_what_required_fields_cannot() -> None:
    """The three shapes of requiredness, and the two `required_fields` alone cannot express."""
    reqs = authoring_requirements("repeat_alleles.csv")
    assert set(reqs["always"]) == set(required_fields("repeat_alleles.csv"))
    assert reqs["defaulted"] == {"measure_kind": "repeat_count", "unresolved": "false"}
    assert authoring_requirements("variants.csv")["any_of"] == [["rsid"], ["chrom", "start"]]
