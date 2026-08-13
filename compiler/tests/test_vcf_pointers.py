"""A VCF field is identified by namespace and described by cardinality; a bare token carries neither.

RM53/RM54/RM61. The two shipped examples that used these columns were both wrong, in the way that
costs a wrong answer rather than a parse error: `mt_heteroplasmy` wrote `source_field=AF` meaning this
person's heteroplasmy fraction, where the spec's `AF` is the cohort frequency of the same ALT — both
floats in `[0, 1]`, both bin cleanly, and one of them reassures a carrier on the strength of how rare
the variant is in a reference panel. `htt_repeat_expansion` pointed four thresholds at a repeat-count
field with nowhere to say *the larger of the two alleles*, which is the clinical rule for a dominant
expansion.

Every failing case here is demonstrated against the **old** authored spelling, rebuilt from the real
reference example rather than invented, so the test shows the defect rather than asserting that it
used to exist.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _check_vcf_pointers, compile_module, validate_spec
from just_dna_format.base import SHARED_VOCABULARIES
from just_dna_format.binning import MeasureBinRow, RepeatAlleleRow
from just_dna_format.reference import _ALL_MODELS, authoring_reference
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import (
    ELEMENT_RULE_MEANINGS,
    VALID_ELEMENT_RULES,
    VCF_COLLIDING_KEYS,
    VCF_COLLISION_REASONS,
    VCF_FIELD_NUMBER,
    VCF_NAMESPACES,
    VCF_NUMBER_MEANINGS,
    VCF_POINTER_COMPANIONS,
    VCF_POINTER_FIELDS,
    is_multi_valued_number,
    match_vocab,
    split_field_pointer,
    validate_field_token,
    vcf_field_number,
)
from pydantic import ValidationError

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HTT = _EXAMPLES / "htt_repeat_expansion"
_MT = _EXAMPLES / "mt_heteroplasmy"


def _copy_spec(source: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.is_file():
            (dest / child.name).write_bytes(child.read_bytes())
    return dest


def _rewrite(path: Path, **cells: str) -> None:
    """Set `cells` on every data row of a CSV, dropping any column mapped to `None`."""
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    assert rows, path
    fieldnames = [f for f in rows[0] if not (f in cells and cells[f] is None)]
    for row in rows:
        for column, value in cells.items():
            if value is not None:
                row[column] = value
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _pointer_findings(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "VCF pointer cell(s)" in w]


# ── RM61: the grammar describes VCF field names, and used to refuse two the spec names by hand ──


def test_the_spec_reserves_two_key_shapes_the_old_grammar_refused() -> None:
    """`1000G` and a dotted key are both legal per §1.6.1.8, and both used to raise."""
    for legal in ("1000G", "gnomAD.AF", "INFO/1000G", "FORMAT/my.caller.field"):
        assert validate_field_token(legal, "source_field") == legal


def test_widening_only_every_shape_that_validated_before_still_does() -> None:
    """P3 on the grammar itself: the old language is `[A-Za-z_][A-Za-z0-9_]*`, `|`-joined."""
    old_language = ("REPCN", "AF", "DP", "CN|DS", "_x9", "GQ|FT|DP")
    for token in old_language:
        assert validate_field_token(token, "source_field") == token
        assert all(namespace is None for namespace, _key in split_field_pointer(token))


def test_the_pointer_is_still_a_pointer_and_not_an_expression() -> None:
    """The whole reason these columns were a bare token (P1) — widening must not open a grammar."""
    for illegal in ("AD[1]", "max(AD)", "AD > 3", "FORMAT/", "/DP", "INFO/DP/2", "AD 1", ""):
        with pytest.raises(ValueError, match="pointer, not an expression"):
            validate_field_token(illegal, "source_field")


def test_the_namespace_is_matched_as_the_spec_and_bcftools_spell_it() -> None:
    """Unlike the `-`/`_` slip `match_vocab` absorbs, there is no established lowercase spelling."""
    assert split_field_pointer("INFO/DP") == [("INFO", "DP")]
    with pytest.raises(ValueError):
        validate_field_token("info/DP", "source_field")
    # A key that merely *looks* like a namespace stays a key — nothing is stripped by accident.
    assert split_field_pointer("INFO") == [(None, "INFO")]
    assert split_field_pointer("INFOX/DP") == [(None, "INFOX/DP")]


def test_alternation_is_fallback_between_fields_never_indexing() -> None:
    assert split_field_pointer("INFO/DP|FORMAT/DP") == [("INFO", "DP"), ("FORMAT", "DP")]
    assert split_field_pointer("CN|DS") == [(None, "CN"), (None, "DS")]


# ── RM53: the namespace, and the collision warning ──────────────────────────────────────────────


def test_the_collision_set_is_spec_derived_and_every_member_states_both_readings() -> None:
    assert set(VCF_COLLISION_REASONS) == set(VCF_COLLIDING_KEYS)
    for key, reason in VCF_COLLISION_REASONS.items():
        assert "INFO/" in reason and "FORMAT/" in reason, key
    # Each colliding key is one the reserved tables actually carry, so the two constants describe the
    # same document rather than drifting into two opinions.
    for key in VCF_COLLIDING_KEYS:
        assert any(f"{ns}/{key}" in VCF_FIELD_NUMBER for ns in VCF_NAMESPACES), key


def test_the_reported_case_mt_heteroplasmy_as_it_shipped(tmp_path: Path) -> None:
    """Both pointer cells wrong, in two different columns, on a module that compiled green."""
    spec = _copy_spec(_MT, tmp_path / "mt")
    _rewrite(spec / "heteroplasmy.csv", source_field="AF", source_element=None)
    _rewrite(spec / "variants.csv", callable_from="DP")

    findings = _pointer_findings(validate_spec(spec).warnings)
    assert len(findings) == 1, findings  # one aggregated line, not one per row
    collision = findings[0]
    heteroplasmy_rows = len(list(csv.DictReader((spec / "heteroplasmy.csv").open())))
    variant_rows = len(list(csv.DictReader((spec / "variants.csv").open())))
    assert f"heteroplasmy.csv source_field=AF ({heteroplasmy_rows} row(s))" in collision
    assert f"variants.csv callable_from=DP ({variant_rows} row(s))" in collision
    assert VCF_COLLISION_REASONS["AF"] in collision
    assert VCF_COLLISION_REASONS["DP"] in collision


def test_the_correction_the_shipped_examples_are_now_silent() -> None:
    """Every example in the tree, so a future one authored with a bare colliding key is caught."""
    for spec in sorted(d for d in _EXAMPLES.iterdir() if (d / "module_spec.yaml").is_file()):
        assert _pointer_findings(validate_spec(spec).warnings) == [], spec.name


def test_a_bare_non_colliding_key_is_accepted_in_silence(tmp_path: Path) -> None:
    """The warning is keyed on the collision set, not on the absence of a namespace — a bare key
    stays legal and means unqualified, which is the whole reason this is a warning and not a
    refusal."""
    spec = _copy_spec(_MT, tmp_path / "mt")
    _rewrite(spec / "variants.csv", callable_from="GQ")
    assert not [w for w in _pointer_findings(validate_spec(spec).warnings) if "callable_from" in w]


def test_the_collision_half_covers_every_pointer_column_not_just_the_one_with_a_companion() -> None:
    """`callable_from=DP` is the same error `source_field=AF` is, one column over — so the two halves
    of the check read different constants on purpose."""
    assert set(VCF_POINTER_FIELDS) == {"source_field", "callable_from", "quality_from"}
    declared = {
        field
        for model in _ALL_MODELS.values()
        for field in VCF_POINTER_FIELDS
        if field in model.model_fields
    }
    assert declared == set(VCF_POINTER_FIELDS), "a pointer column nothing declares is a stale name"
    assert set(VCF_POINTER_COMPANIONS.values()) < set(VCF_POINTER_FIELDS)


# ── RM54: cardinality, the element rule, and what the check declines to say ─────────────────────


def test_cardinality_is_three_valued_and_the_third_value_is_the_common_one() -> None:
    # Qualified: looked up directly, and the two namespaces genuinely disagree about CN.
    assert vcf_field_number("INFO", "CN") == "A"
    assert vcf_field_number("FORMAT", "CN") == "1"
    # Bare + colliding + namespaces agree → settled cardinality even though the meaning is not.
    assert vcf_field_number(None, "AD") == "R"
    # Bare + colliding + namespaces disagree → withhold.
    assert vcf_field_number(None, "CN") is None
    # Bare + colliding + only one namespace reserves it → withhold. `FORMAT/AF` is emitted by every
    # caller and reserved by none, so reading INFO/AF's `A` as the bare key's answer would answer a
    # question about a field the spec never described.
    assert vcf_field_number(None, "AF") is None
    # Bare + not a collision → the single reserved entry is the answer; no INFO table defines GQ.
    assert vcf_field_number(None, "GQ") == "1"
    # A caller's own key is not the spec's, and asserting a cardinality for it would be a source
    # convention wearing a fact.
    assert vcf_field_number(None, "REPCN") is None
    assert is_multi_valued_number(None) is False


def test_the_reported_case_a_pointer_at_a_value_list_with_no_rule(tmp_path: Path) -> None:
    """A `Number=R` field returns one value per allele, reference first — none of them the answer."""
    spec = _copy_spec(_HTT, tmp_path / "htt")
    _rewrite(spec / "repeat_alleles.csv", source_field="FORMAT/AD", source_element=None)

    findings = _pointer_findings(validate_spec(spec).warnings)
    assert len(findings) == 1, findings
    finding = findings[0]
    rows = len(list(csv.DictReader((spec / "repeat_alleles.csv").open())))
    assert "repeat_alleles.csv source_field=FORMAT/AD (Number=R" in finding
    assert VCF_NUMBER_MEANINGS["R"] in finding
    assert f"{rows} row(s), source_element empty" in finding
    # The trap is named where the author is standing, not only in the vocabulary docs.
    assert "reference is element zero" in finding
    assert "largest_alt" in finding


def test_an_element_rule_silences_it_and_that_is_the_authored_fix(tmp_path: Path) -> None:
    spec = _copy_spec(_HTT, tmp_path / "htt")
    _rewrite(spec / "repeat_alleles.csv", source_field="FORMAT/AD", source_element="largest_alt")
    assert _pointer_findings(validate_spec(spec).warnings) == []


def test_it_declines_to_ask_where_no_column_could_answer(tmp_path: Path) -> None:
    """`callable_from` has no companion column in 0.6, so a multi-valued target there must NOT warn:
    a finding whose remedy is a column the schema does not have is one no author could clear."""
    spec = _copy_spec(_MT, tmp_path / "mt")
    _rewrite(spec / "variants.csv", callable_from="FORMAT/AD")
    assert "callable_element" not in VariantRow.model_fields
    assert is_multi_valued_number(vcf_field_number("FORMAT", "AD"))
    assert _pointer_findings(validate_spec(spec).warnings) == []


# ── the vocabulary, and the trap written into it ────────────────────────────────────────────────


def test_every_element_rule_says_whether_the_reference_counts() -> None:
    """"Larger" has two answers on a `Number=R` field, so a member silent about it repeats the defect
    one level down. Totality is what makes the map the answer rather than a partial gloss."""
    assert set(ELEMENT_RULE_MEANINGS) == set(VALID_ELEMENT_RULES)
    for member, meaning in ELEMENT_RULE_MEANINGS.items():
        assert "reference" in meaning.lower(), member


def test_the_ranging_rules_come_in_pairs_and_the_pair_is_the_answer() -> None:
    ranging = {m for m in VALID_ELEMENT_RULES if not m.endswith("_alt") and m != "reference"}
    assert {f"{m}_alt" for m in ranging} <= VALID_ELEMENT_RULES
    for member in ranging:
        assert "included" in ELEMENT_RULE_MEANINGS[member]
        assert "skips element zero" in ELEMENT_RULE_MEANINGS[f"{member}_alt"]


def test_it_is_a_named_rule_set_and_never_an_index() -> None:
    """P1: `AD[1]` is the first line of an expression grammar. Every member is a bare identifier."""
    for member in VALID_ELEMENT_RULES:
        assert member.replace("_", "").isalpha(), member


def test_the_vocabulary_reaches_an_author_through_the_reference_surface() -> None:
    reference = authoring_reference()
    assert reference["vocabularies"]["source_element"] == sorted(VALID_ELEMENT_RULES)
    assert reference["vocabulary_notes"]["source_element"] == dict(ELEMENT_RULE_MEANINGS)
    described = reference["models"]["RepeatAlleleRow"]
    element = next(f for f in described if f["name"] == "source_element")
    assert element["options"] == sorted(VALID_ELEMENT_RULES)
    assert element["closed"] is True


def test_a_separator_slip_canonicalizes_like_every_other_closed_vocabulary() -> None:
    assert match_vocab("largest-alt", VALID_ELEMENT_RULES) == "largest_alt"
    row = RepeatAlleleRow(
        gene="HTT", repeat_unit="CAG", measure_kind="repeat_count", measure_min=40,
        conclusion="x", source_field="FORMAT/REPCN", source_element="largest-alt",
    )
    assert row.source_element == "largest_alt", "the stored cell is always the declared spelling"


def test_a_non_member_is_refused_with_the_full_list() -> None:
    with pytest.raises(ValidationError, match="source_element must be one of"):
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_kind="repeat_count", measure_min=40,
            conclusion="x", source_field="FORMAT/REPCN", source_element="max",
        )


def test_an_element_rule_with_nothing_to_qualify_is_refused() -> None:
    """The rule says *which* value of a field; with no field beside it the cell names nothing."""
    with pytest.raises(ValidationError, match="there is no field for it to select from"):
        RepeatAlleleRow(
            gene="HTT", repeat_unit="CAG", measure_kind="repeat_count", measure_min=40,
            conclusion="x", source_element="largest",
        )
    # The converse is the ordinary case and must stay legal — a scalar field needs no selection, and
    # demanding one would break every module carrying a pointer today (P3).
    assert RepeatAlleleRow(
        gene="HTT", repeat_unit="CAG", measure_kind="repeat_count", measure_min=40,
        conclusion="x", source_field="FORMAT/REPCN",
    ).source_element is None


def test_every_companion_in_the_map_is_actually_enforced() -> None:
    """The relation the check reads and the vocabulary the validator enforces must not drift: a map
    entry nothing validates would let a novel value through the surface that advertises the set."""
    for element_field, pointer_field in VCF_POINTER_COMPANIONS.items():
        assert SHARED_VOCABULARIES[element_field] is VALID_ELEMENT_RULES
        owners = [m for m in _ALL_MODELS.values() if element_field in m.model_fields]
        assert owners, element_field
        for model in owners:
            assert pointer_field in model.model_fields, (model.__name__, pointer_field)
    assert "source_element" in MeasureBinRow.model_fields


# ── severity and mode ───────────────────────────────────────────────────────────────────────────


def test_both_findings_warn_in_strict_too_and_never_refuse(tmp_path: Path) -> None:
    """A widened grammar that then refused the old spelling under `strict` would break P3, and
    `strict` means *reproducible artifact* — an unqualified pointer reproduces perfectly."""
    spec = _copy_spec(_MT, tmp_path / "mt")
    _rewrite(spec / "heteroplasmy.csv", source_field="AD", source_element=None)
    _rewrite(spec / "variants.csv", callable_from="DP")
    for strict in (False, True):
        result = validate_spec(spec, strict=strict)
        assert result.valid, (strict, result.errors)
        assert len(_pointer_findings(result.warnings)) == 2, result.warnings


def test_compile_reports_it_once_not_twice(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` itself, so a check living in both places has to be
    de-duplicated on the message the way `_check_contig_ploidy` is."""
    spec = _copy_spec(_MT, tmp_path / "mt")
    _rewrite(spec / "variants.csv", callable_from="DP")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert len(_pointer_findings(result.warnings)) == 1, result.warnings


def test_nothing_authored_means_nothing_reported() -> None:
    assert _check_vcf_pointers([], {}) == []
