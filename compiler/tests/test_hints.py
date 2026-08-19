"""Authoring hints — facts about authored cells, with nothing written (0.5).

What is pinned here is the partition the module exists for: a hint that *normalizes* what the author
already typed is applied, and a hint that would fill a cell a Class-2 redundancy check cross-examines
is never applied. Plus the mechanical guarantees — same row count and order out as in, every applied
change listed, no file touched.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _FACT_TABLES
from just_dna_compiler.draft import DRAFTABLE, DraftError, model_for, natural_key, stub_template
from just_dna_compiler.hints import (
    ALTERATION_KINDS,
    ATTESTATION_BEARING,
    DERIVED_TABLE_MODELS,
    KEY_RULES,
    REDUNDANCY_BEARING,
    REFUSAL_REASONS,
    Finding,
    HintReport,
    derived_model_for,
    describe_table,
    field_options,
    inspect_rows,
    key_fields,
)
from just_dna_format.base import authored_field_names, field_vocabularies
from just_dna_format.layout import sidecar_spellings
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_row_count_and_order_survive(kind: str) -> None:
    """`csv_out` is the input's shape: same header, same number of rows, same order."""
    text = stub_template(kind)
    report = inspect_rows(kind, text)
    assert report.header == text.splitlines()[0].split(",")
    assert len(report.csv_out) == len(text.splitlines())
    assert report.rows_in == len(text.splitlines()) - 1


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_hinting_writes_nothing_to_disk(kind: str, tmp_path: Path) -> None:
    """The primary MUST-NOT, asserted by bytes rather than by review."""
    path = tmp_path / kind
    path.write_text(stub_template(kind))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*")}
    inspect_rows(kind, path.read_text())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*")} == before


def test_only_normalizations_are_applied_and_all_are_listed() -> None:
    """Every difference between input and output is an applied alteration, and vice versa."""
    text = "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n"
    report = inspect_rows("diplotypes.csv", text)
    assert {a.column for a in report.applied} == {"haplotype_a", "haplotype_b"}
    assert all(a.kind == "normalized" for a in report.applied)

    before = next(csv.DictReader(io.StringIO(text)))
    after = next(csv.DictReader(io.StringIO("\n".join(report.csv_out))))
    differing = {c for c in before if before[c] != after[c]}
    assert differing == {a.column for a in report.applied}


def test_a_silent_model_rewrite_is_surfaced_before_it_surprises_anyone() -> None:
    """`DiplotypeRow` canonicalizes the pair on load; the author is told, not ambushed."""
    report = inspect_rows("diplotypes.csv", "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n")
    rendered = next(csv.DictReader(io.StringIO("\n".join(report.csv_out))))
    assert (rendered["haplotype_a"], rendered["haplotype_b"]) == ("*1", "*4")


def test_redundancy_bearing_cells_are_never_filled() -> None:
    """The whole partition: a coordinate is left empty and explained, never supplied.

    Filling it would make `resolution._verify` compare a source against itself — and for an
    rsid-only row that check does not even run, so the row would go from honestly unverified to
    apparently verified."""
    report = inspect_rows("variants.csv", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    assert report.unchanged
    assert not [a for a in report.alterations if a.column in REDUNDANCY_BEARING and a.applied]
    explained = {f.column for f in report.findings if f.level == "info"}
    assert {"chrom", "start", "ref"} <= explained


def test_every_check_that_reads_an_authored_cell_registers_it() -> None:
    """A Class-2 check must appear in the map, and the enricher's fulltext comparison did not (S11).

    Derived from the models rather than listed here: every column the map names must exist on some
    authored model, and the two provenance columns must be present — they are compared against the
    Europe PMC fulltext by `_study_quote_found`, which is the map's own definition of belonging."""
    authored: set[str] = set()
    for kind in DRAFTABLE:
        authored |= set(authored_field_names(model_for(kind)))
    unknown = sorted(c for c in REDUNDANCY_BEARING if c not in authored)
    assert not unknown, f"the map names columns no authored model declares: {unknown}"
    assert {"provenance_quote", "provenance_regex"} <= set(REDUNDANCY_BEARING)


def test_an_attestation_cell_is_refused_for_the_sharper_reason() -> None:
    """`attestation_bearing` is a fifth reason, not a synonym for the fourth.

    Filling `doi` from the registry that checks it spends a comparison; filling `provenance_quote`
    from a just-fetched fulltext asserts a curator reading that never happened. Both cells are also
    redundancy-bearing, so the sharper token must not be *instead of* that registration — a provider
    consulting only one map has to reach a refusal either way."""
    assert "attestation_bearing" in REFUSAL_REASONS
    assert set(REDUNDANCY_BEARING) >= ATTESTATION_BEARING
    # And nothing fills them today: the hint pass leaves an authored quote exactly as written.
    quoted = "pmid,trait,provenance_quote\n12345678,height,carriers showed a 2.1 cm increase\n"
    report = inspect_rows("studies.csv", quoted)
    assert not [a for a in report.alterations if a.column in ATTESTATION_BEARING and a.applied]
    assert "carriers showed a 2.1 cm increase" in "\n".join(report.csv_out)


_HTT_HEADER = "gene,repeat_unit,measure_kind,measure_min,measure_max,conclusion,unresolved"
# The reported case: an unquoted comma inside `conclusion`, which is what free-text columns invite.
_HTT_RAGGED = (
    f"{_HTT_HEADER}\n"
    "HTT,CAG,repeat_count,,26,Normal range with no expanded allele.,false\n"
    "HTT,CAG,repeat_count,27,35,Intermediate allele, may expand on paternal transmission.,false\n"
)


def test_a_ragged_row_is_named_before_the_error_it_causes() -> None:
    """The shift is reported, and reported first (S18).

    The misdirection is demonstrated, not asserted about: the row really does end up with a type error
    against `unresolved`, a column whose authored value (`false`) is a perfectly good boolean. So the
    field-count finding has to exist *and* precede it, or the author goes and edits the cell they got
    right. Counts are derived from the fixture, never hardcoded."""
    declared = len(_HTT_HEADER.split(","))
    actual = len(next(csv.reader(io.StringIO(_HTT_RAGGED.splitlines()[2]))))
    assert actual == declared + 1, "the fixture must be ragged or it proves nothing"

    report = inspect_rows("repeat_alleles.csv", _HTT_RAGGED)
    row_scoped = [f for f in report.findings if f.row == 1]
    assert row_scoped[0].column is None, "the field count must come before the cell error"
    assert f"{actual} field(s) where the header declares {declared}" in row_scoped[0].message
    assert row_scoped[0].level == "error"
    assert "unquoted comma" in row_scoped[0].message
    # and the misleading type error is still there, against a cell the author wrote correctly
    assert [f.column for f in row_scoped if f.column] == ["unresolved"]


def test_a_short_row_warns_rather_than_errors() -> None:
    """Padding is recoverable and often a trailing comma; a surplus silently discards data."""
    short = f"{_HTT_HEADER}\nHTT,CAG,repeat_count,,26,ok\n"
    report = inspect_rows("repeat_alleles.csv", short)
    counted = [f for f in report.findings if f.row == 0 and f.column is None]
    assert [f.level for f in counted] == ["warning"]
    assert "6 field(s) where the header declares 7" in counted[0].message


def test_a_well_formed_table_is_never_told_about_field_counts() -> None:
    """The guard must be silent on every shipped example, or it is noise."""
    for kind in DRAFTABLE:
        report = inspect_rows(kind, stub_template(kind))
        noisy = [f for f in report.findings if "field(s) where the header declares" in f.message]
        assert not noisy, f"{kind}: {noisy}"


def test_a_finding_carries_both_the_row_index_and_the_file_line() -> None:
    """Two coordinates, both stated (S18): `row` indexes data rows from 0, `line` is what an editor
    shows — 1-based, header included, the same convention `validate`/`compile` print."""
    report = inspect_rows("repeat_alleles.csv", _HTT_RAGGED)
    located = [f for f in report.findings if f.row is not None]
    assert located, "the fixture must produce a row-scoped finding"
    for finding in located:
        assert finding.line == finding.row + 2  # +1 for the header, +1 for 1-based counting
    assert {f.line for f in located} == {3}, "the malformed row is line 3 of the file"
    # A table-scoped finding has neither coordinate, rather than a misleading zero.
    for finding in report.findings:
        if finding.row is None:
            assert finding.line is None


def test_without_a_header_the_line_number_has_no_header_to_count() -> None:
    """A caller pasting one row from a template has no header line, so line 1 is that row."""
    report = inspect_rows("repeat_alleles.csv", "HTT,CAG,repeat_count,,26,ok,notabool\n")
    located = [f for f in report.findings if f.row == 0]
    assert located and all(f.line == 1 for f in located), [(f.row, f.line) for f in located]


def test_an_out_of_vocabulary_value_is_reported_with_the_options() -> None:
    report = inspect_rows(
        "variants.csv", "rsid,genotype,state,conclusion,direction\nrs1801133,A/G,risk,c,sideways\n"
    )
    assert any(f.column == "direction" and f.level == "error" for f in report.findings)
    options = {o.column: o.options for o in report.options}
    assert "sideways" not in options["direction"]
    assert sorted(options["direction"]) == options["direction"]


def test_a_duplicate_row_is_caught_with_the_compilers_own_key() -> None:
    text = (
        "rsid,genotype,state,conclusion\n"
        "rs1801133,A/G,risk,first\n"
        "rs1801133,A/G,risk,second\n"
    )
    report = inspect_rows("variants.csv", text)
    assert any("duplicate of row 0" in f.message for f in report.findings)


def test_a_shipped_binning_module_hints_clean() -> None:
    """Real data: the HTT example must produce no error and no coverage warning."""
    text = (_EXAMPLES / "htt_repeat_expansion" / "repeat_alleles.csv").read_text()
    report = inspect_rows("repeat_alleles.csv", text)
    assert [f for f in report.findings if f.level == "error"] == []
    assert [f for f in report.findings if f.level == "warning"] == []
    assert report.unchanged


def test_overlapping_bins_are_reported_via_the_schemas_own_checker() -> None:
    """Computed by calling `validate_bins`, not by hardcoding what it says."""
    text = (
        "measure_kind,measure_min,measure_max,conclusion,unresolved,gene,repeat_unit\n"
        "repeat_count,10,20,low,false,HTT,CAG\n"
        "repeat_count,15,25,overlapping,false,HTT,CAG\n"
        "repeat_count,,,not measured,true,HTT,CAG\n"
    )
    report = inspect_rows("repeat_alleles.csv", text)
    assert any(f.level == "error" for f in report.findings)


def test_a_binning_table_without_the_sentinel_is_flagged() -> None:
    text = (
        "measure_kind,measure_min,measure_max,conclusion,unresolved,gene,repeat_unit\n"
        "repeat_count,10,20,low,false,HTT,CAG\n"
    )
    report = inspect_rows("repeat_alleles.csv", text)
    assert any(f.column == "unresolved" and f.level == "warning" for f in report.findings)


def test_an_unreplaced_stub_is_reported_as_a_stub() -> None:
    report = inspect_rows("variants.csv", stub_template("variants.csv"))
    assert any("template stub" in f.message for f in report.findings)


def _stub_cells(text: str) -> set[tuple[int, str]]:
    """`(row index, column)` for every cell of `text` still carrying the placeholder."""
    lines = text.splitlines()
    header = next(csv.reader([lines[0]]))
    return {
        (index, column)
        for index, line in enumerate(lines[1:])
        for column, value in zip(header, next(csv.reader([line])), strict=True)
        if value.strip() == TEMPLATE_PLACEHOLDER
    }


def _placeholder_findings(report: HintReport) -> list[Finding]:
    """Every finding either emitter produces about a placeholder, whichever wording it uses."""
    return [
        f for f in report.findings if "template stub" in f.message or TEMPLATE_PLACEHOLDER in f.message
    ]


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_one_stub_cell_yields_exactly_one_finding(kind: str) -> None:
    """One cell, one finding — the whole of D4-2.

    Two layers see the same cell: `_check_placeholders` walks the columns, and the model's own
    `mode="before"` guard raises one row-level `ValueError` naming every stub path, which
    `_validate_row` turned into a second `Finding` with no `column` on it. A freshly drafted panel
    therefore printed two lines per defect. The per-column finding is the one to keep — it names the
    column, so the CLI can print `line 2 [genotype]` — and the guard itself is untouched, since it is
    what makes a generated stub unable to compile.
    """
    text = stub_template(kind, rows=2)
    report = inspect_rows(kind, text)
    cells = _stub_cells(text)
    assert cells, f"{kind} stubs nothing, so this kind proves nothing"
    findings = _placeholder_findings(report)
    assert {(f.row, f.column) for f in findings} == cells
    assert len(findings) == len(cells)
    assert all(f.line == f.row + 2 for f in findings)


def test_a_stub_in_a_vocabulary_column_does_not_also_fail_the_vocabulary() -> None:
    """The second door onto the same defect, and the proof that suppressing it loses nothing.

    An unfilled cell is one fact, so it gets one finding — and the moment it is filled with something
    the vocabulary rejects, the vocabulary error is there again.

    **This used to read "`SourceRow` carries no placeholder guard, so the stub reaches the field
    validators, which quote the token back", and RM76 made that false.** The row now refuses as a
    stub before any field validator runs, which is what closes the hole where a *free-text* column
    (`source`) let `<<REPLACE>>` through to a signed `manifest.sources`. Worth keeping the correction
    visible rather than editing the sentence away: `layer`'s vocabulary really did catch this cell,
    by accident, and reasoning from that accident is how the free-text half stayed open — and how the
    first draft of RM76's own test came out green on the unfixed code."""
    header = "source,layer,license\n"
    report = inspect_rows("sources.csv", f"{header}clinvar,{TEMPLATE_PLACEHOLDER},CC0\n")
    assert [(f.row, f.column, f.message) for f in report.findings if f.row == 0] == [
        (0, "layer", "layer is still a template stub — replace it")
    ]

    filled = inspect_rows("sources.csv", f"{header}clinvar,annotations,CC0\n")  # the member is singular
    assert [(f.row, f.column) for f in filled.findings if f.row == 0] == [(0, "layer")]
    assert "must be one of" in next(f.message for f in filled.findings if f.row == 0)


def test_a_partially_filled_row_reports_only_the_cells_still_stubbed() -> None:
    """The suppression is keyed on the cells actually stubbed, not on the file being a fresh stub."""
    text = (
        "rsid,chrom,start,ref,alts,genotype,weight,state,conclusion\n"
        f"rs1801133,,,,,C/T,0.4,significant,{TEMPLATE_PLACEHOLDER}\n"
        "rs429358,,,,,C/C,0.9,significant,higher risk\n"
    )
    report = inspect_rows("variants.csv", text)
    findings = _placeholder_findings(report)
    assert [(f.row, f.column, f.line) for f in findings] == [(0, "conclusion", 2)]


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_describe_table_covers_exactly_the_authored_surface(kind: str) -> None:
    """Asserted against the marker, so a newly compiler-managed field needs no test edit."""
    described = [c["name"] for c in describe_table(kind)["columns"]]
    assert described == authored_field_names(model_for(kind))


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_field_options_match_the_models_markers(kind: str) -> None:
    expected = field_vocabularies(model_for(kind))
    assert {o.column: o.options for o in field_options(kind)} == {
        c: m["options"] for c, m in expected.items()
    }
    # …including the per-member prose a member name cannot carry: a picker offering `largest` beside
    # `largest_alt` is exactly where "which one counts the reference element" has to be answerable.
    assert {o.column: o.notes for o in field_options(kind)} == {
        c: (dict(m["notes"]) if m.get("notes") else None) for c, m in expected.items()
    }


def test_every_alteration_kind_is_a_declared_member() -> None:
    report = inspect_rows("diplotypes.csv", "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n")
    assert {a.kind for a in report.alterations} <= ALTERATION_KINDS


def test_the_report_serializes_deterministically() -> None:
    text = "gene,haplotype_a,haplotype_b,conclusion\nCYP2D6,*4,*1,PM\n"
    assert inspect_rows("diplotypes.csv", text).to_json() == inspect_rows("diplotypes.csv", text).to_json()


def test_a_headerless_row_is_read_against_the_models_column_order() -> None:
    """What a caller pasting one row from a template actually has."""
    header = stub_template("pgs.csv").splitlines()[0].split(",")
    row = ["PGS000135"] + [""] * (len(header) - 1)
    report = inspect_rows("pgs.csv", ",".join(row))
    assert report.rows_in == 1
    assert [f for f in report.findings if f.level == "error"] == []


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(DraftError, match="not an authored table"):
        inspect_rows("nonsense.csv", "a,b\n1,2\n")


def test_the_derived_roster_is_derived_from_the_compilers_own_fact_tables() -> None:
    """The whole point of S47: a new fact table must not be able to become undescribable.

    Set equality over a walked set, never a floor and never a count — a hand-kept parallel map is the
    defect this closes, so the test that guards it cannot restate the roster either.
    """
    expected = {"resolution.csv"} | {
        spelling for csv_name, _parquet, _model in _FACT_TABLES for spelling in sidecar_spellings(csv_name)
    }
    assert set(DERIVED_TABLE_MODELS) == expected


def test_every_fact_table_resolves_to_the_model_the_compiler_loads_it_with() -> None:
    """Not just *a* model — the same one, so the two surfaces cannot drift."""
    assert all(
        derived_model_for(csv_name) is model for csv_name, _parquet, model in _FACT_TABLES
    )


def test_both_spellings_of_the_licence_table_answer_the_same_model() -> None:
    """A caller holding a `licensing.csv` module must not be told it is not a table of this format."""
    assert derived_model_for("licensing.csv") is derived_model_for("sources.csv")


def test_an_authored_table_is_refused_with_the_route_that_does_answer_it() -> None:
    """A generic rejection is a dead end where a specific one is a fix."""
    with pytest.raises(DraftError, match=r"authored table.*model_for"):
        derived_model_for("variants.csv")
    # …and the authored route really does answer it, which is what makes the message actionable.
    assert model_for("variants.csv") is DRAFTABLE["variants.csv"]


def test_a_name_this_format_does_not_read_at_all_is_refused() -> None:
    with pytest.raises(DraftError, match="not a machine-produced table"):
        derived_model_for("nonsense.csv")


_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def test_no_key_column_is_presented_as_fillable_unless_it_is_a_real_authored_field() -> None:
    """The guard that makes the `effective_*` mapping safe to rely on.

    A key member is either a column the author can fill, or it is flagged in `stamped` — never a bare
    name that resolves to nothing, which is what would be handed to an author as a cell to edit. This
    is the invariant rather than "every member is a model field", because two members legitimately are
    not: `StudyRow.variant_key` is a **property** over the row's identity columns (the other three
    variant-keyed kinds carry it as a stamped *field*), and `CopyNumberRow` keys on a property that is
    mapped back to its authored column. A future property that follows neither route fails here.
    """
    offenders = {
        csv_name: [
            c for c in key.columns
            if c not in model_for(csv_name).model_fields and c not in key.stamped
        ]
        for csv_name in DRAFTABLE
        if (key := key_fields(csv_name)) is not None
    }
    assert {k: v for k, v in offenders.items() if v} == {}


def test_the_copynumber_key_names_the_authored_column_and_never_the_deprecated_one() -> None:
    """S48's actual defect: the consumer's surface said `modifier_cn`, which 0.6 deprecated.

    The property `_KEY_FIELDS` names is mapped back to the *preferred* spelling of the pair, so this
    surface cannot hand an author the half that is removed at 1.0 — and it is not dropped either,
    which would say two rows differing only in modifier dosage are the same row.
    """
    key = key_fields("copynumbers.csv")
    assert key is not None
    assert key.columns == ("gene", "modifier_gene", "modifier_copy_number")
    assert "modifier_cn" not in key.columns
    assert "effective_modifier_copy_number" not in key.columns


def test_no_key_column_is_a_deprecated_column_on_any_kind() -> None:
    """The general form of the case above, so the next deprecation cannot reintroduce it."""
    deprecated = {
        (csv_name, column)
        for csv_name in DRAFTABLE
        if (key := key_fields(csv_name)) is not None
        for column in key.columns
        if column in (fields := model_for(csv_name).model_fields)
        and "DEPRECATED" in (fields[column].description or "")
    }
    assert deprecated == set()


def test_key_fields_and_natural_key_agree_on_real_rows() -> None:
    """One source of truth, pinned against the other reader rather than trusted.

    `natural_key` is the row-level answer and `key_fields` the table-level one; both now read the
    model's `_KEY_FIELDS`, so a drift between them is a bug this asserts away. Real authored rows from
    a reference example, not hand-built ones.
    """
    spec = _EXAMPLES / "cyp2c19_star_alleles"
    checked = 0
    for csv_name in ("haplotypes.csv", "allele_function.csv", "diplotypes.csv"):
        model = model_for(csv_name)
        key = key_fields(csv_name)
        assert key is not None and key.rule == "equality"
        with (spec / csv_name).open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                row = model.model_validate({k: v for k, v in raw.items() if v != ""})
                assert natural_key(row) == tuple(getattr(row, c) for c in key.columns)
                checked += 1
    assert checked > 0


def test_a_binning_kind_names_its_grouping_columns_and_says_the_rule_is_overlap() -> None:
    """`natural_key` returns None there; that is the same fact, not a disagreement."""
    spec_rows = key_fields("activity_phenotype.csv")
    assert spec_rows is not None
    assert spec_rows.rule == "overlap"
    assert spec_rows.columns == ("gene",)


def test_a_derived_table_with_no_declared_key_withholds_rather_than_inventing_one() -> None:
    assert key_fields("frequencies.csv") is None
    assert key_fields("resolution.csv") is None


def test_every_rule_is_a_declared_member() -> None:
    rules = {
        key.rule for csv_name in DRAFTABLE if (key := key_fields(csv_name)) is not None
    }
    assert rules <= KEY_RULES and rules == KEY_RULES


def test_a_stamped_key_member_is_flagged_rather_than_presented_as_fillable() -> None:
    """An author cannot type `variant_key`; it is still part of the key."""
    key = key_fields("haplotypes.csv")
    assert key is not None
    assert "variant_key" in key.columns
    assert key.stamped == ("variant_key",)


def test_describe_table_carries_the_key_its_docstring_has_always_promised() -> None:
    described = describe_table("diplotypes.csv")
    key = key_fields("diplotypes.csv")
    assert key is not None
    assert described["key"] == {
        "columns": list(key.columns), "rule": key.rule, "stamped": list(key.stamped)
    }
