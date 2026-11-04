"""The meta-table's row model and its member grammar (RM28 / RM323 / RM324 / RM327 / RM330, 0.8).

`meta.csv` maps a composite statement — one or more members, each an item of a single-statement table —
to a finding and/or the per-locus facts. Every member is written in one grammar,
`table[column=value, column=value]`, and members are joined by `&` at bracket depth 0
(`proposals/PROPOSAL_0_8_PT2.md` §3 items 1–6). These tests pin the model half: the parser, the key, and
every refusal that needs no other table. The refusals that need the module (a `tier` with no scale, a
member matching nothing, an ambiguous locus) are pinned against the real compile path in the compiler's
`test_meta_compile.py`.
"""

import pytest
from just_dna_format.meta import (
    META_MEMBER_TABLES,
    MetaMember,
    MetaRow,
    MetaSelectorError,
    member_rank,
    normalize_members,
    parse_members,
)
from just_dna_format.pgx import DiplotypeRow
from just_dna_format.spec import VariantRow
from pydantic import ValidationError


def _row(**cells: str) -> MetaRow:
    return MetaRow.model_validate(cells)


# ── the grammar ──────────────────────────────────────────────────────────────────────────────────


def test_one_member_parses_into_table_and_conditions() -> None:
    (member,) = parse_members("variants[variant_key=rs429358, genotype=C/C]")
    assert member == MetaMember("variants", (("variant_key", "rs429358"), ("genotype", "C/C")))


def test_members_split_on_ampersand_at_depth_zero_only() -> None:
    """RM253's DPYD names carry `&` inside a value, and a phased genotype carries `|`: both are data."""
    members = parse_members(
        "allele_function[gene=DPYD, allele=c.1129-5923C>G&c.1236G>A(HapB3)] & variants[variant_key=rs1, genotype=A|G]"
    )
    assert [m.table for m in members] == ["allele_function", "variants"]
    assert dict(members[0].conditions)["allele"] == "c.1129-5923C>G&c.1236G>A(HapB3)"
    assert dict(members[1].conditions)["genotype"] == "A|G"


def test_a_value_may_carry_spaces() -> None:
    (member,) = parse_members("diplotypes[gene=TPMT, phenotype=Poor Metabolizer]")
    assert dict(member.conditions)["phenotype"] == "Poor Metabolizer"


@pytest.mark.parametrize(
    ("cell", "char"),
    [
        ("variants[gene=A[1]]", "["),
        ("variants[gene=A]]", "]"),
        ("variants[gene=a=b]", "="),
        ("variants[gene=APOE,TOMM40]", ","),
    ],
)
def test_a_forbidden_character_in_a_value_is_refused_naming_it(cell: str, char: str) -> None:
    with pytest.raises(MetaSelectorError) as info:
        parse_members(cell)
    assert repr(char) in str(info.value)


@pytest.mark.parametrize(
    ("cell", "phrase"),
    [
        ("studies[pmid=123]", "selectors over studies.csv are out of bounds"),
        ("haplotypes[haplotype_name=*2]", "not a member table"),
        ("frobnicate[gene=A]", "not a member table"),
        ("variants[colour=blue]", "variants.csv has no column 'colour'"),
        ("variants[gene!=APOE]", "negation is out of bounds"),
        ("variants[start>=100]", "ranges are out of bounds"),
        ("variants[start<100]", "ranges are out of bounds"),
        ("variants[gene=A] | variants[gene=B]", "OR is out of bounds"),
        ("variants[diplotypes.gene=APOE]", "joins across tables are out of bounds"),
        ("variants[]", "names no condition"),
        ("variants[gene=]", "empty value"),
        ("variants[gene=A] & ", "an empty member"),
        ("variants gene=A", "is not table[column=value"),
        ("variants[gene=A, gene=B]", "names column 'gene' twice"),
        ("variants[gene=A] & variants[gene=A]", "names one member twice"),
    ],
)
def test_each_bound_is_refused_with_its_own_message(cell: str, phrase: str) -> None:
    with pytest.raises(MetaSelectorError) as info:
        parse_members(cell)
    assert phrase in str(info.value)


def test_variant_key_is_selectable_though_the_compiler_stamps_it() -> None:
    """`variants[variant_key=…]` is the canonical locus member; an authored-only roster would refuse it."""
    (member,) = parse_members("variants[variant_key=rs10455872]")
    assert member.conditions == (("variant_key", "rs10455872"),)


def test_member_tables_are_the_four_the_pm_set() -> None:
    assert set(META_MEMBER_TABLES) == {"variants", "diplotypes", "pharm_variants", "allele_function"}
    assert META_MEMBER_TABLES["variants"] is VariantRow


# ── the key ──────────────────────────────────────────────────────────────────────────────────────


def test_member_order_and_condition_order_do_not_change_the_key() -> None:
    a = normalize_members("variants[genotype=C/T, variant_key=rs1] & allele_function[gene=APOE, allele=ε4]")
    b = normalize_members("allele_function[allele=ε4, gene=APOE] & variants[variant_key=rs1, genotype=C/T]")
    assert a == b


def test_the_row_key_is_members_trait_sex_and_drug_and_the_cell_stays_verbatim() -> None:
    row = _row(members="variants[genotype=C/T, variant_key=rs1]", tier="A")
    assert row.members == "variants[genotype=C/T, variant_key=rs1]"
    assert row.members_key == normalize_members(row.members)
    assert MetaRow._KEY_FIELDS == ("members_key", "trait_efo_id", "sex", "drug")


def test_drug_is_free_text_as_on_diplotypes() -> None:
    """`drug` is the drug the statement is about, open text as `DiplotypeRow.drug` is, first in 0.8.0."""
    assert _row(members="variants[variant_key=rs1]", tier="A", drug="azathioprine").drug == "azathioprine"
    assert _row(members="variants[variant_key=rs1]", tier="A").drug is None
    assert MetaRow.model_fields["drug"].annotation == DiplotypeRow.model_fields["drug"].annotation
    assert MetaRow.model_fields["drug"].json_schema_extra == {"first_seen": "0.8.0"}


# ── the model's refusals ─────────────────────────────────────────────────────────────────────────


def test_a_row_stating_no_finding_and_no_fact_is_refused_as_empty() -> None:
    with pytest.raises(ValidationError, match="states no finding and no fact"):
        _row(members="variants[variant_key=rs1]", trait_efo_id="EFO_0000001", pmid="12345678")


def test_trait_role_without_a_trait_is_refused() -> None:
    with pytest.raises(ValidationError, match="trait_role says how a trait is reached"):
        _row(members="variants[variant_key=rs1, genotype=A/A]", trait_role="mediator", direction="risk")


def test_trait_role_is_closed_on_mediator() -> None:
    with pytest.raises(ValidationError, match="trait_role must be one of"):
        _row(
            members="variants[variant_key=rs1, genotype=A/A]",
            trait_efo_id="EFO_0000001",
            trait_role="outcome",
            direction="risk",
        )


def test_sex_is_closed_on_male_and_female() -> None:
    assert _row(members="variants[variant_key=rs1]", tier="A", sex="male").sex == "male"
    with pytest.raises(ValidationError, match="sex must be one of"):
        _row(members="variants[variant_key=rs1]", tier="A", sex="m")


@pytest.mark.parametrize(
    "member",
    [
        "variants[flags=legacy_longevitymap]",
        "variants[gene=APOE]",
        "pharm_variants[variant_key=rs1]",
        "diplotypes[gene=TPMT, phenotype=Poor Metabolizer]",
    ],
)
def test_a_direction_row_refuses_a_member_that_fixes_no_allele(member: str) -> None:
    with pytest.raises(ValidationError, match="fixes no allele"):
        _row(members=member, trait_efo_id="EFO_0000001", direction="risk")


@pytest.mark.parametrize(
    "member",
    [
        "variants[variant_key=rs1, genotype=C/T]",
        "variants[variant_key=rs1]",  # a bare locus: allele-bearing when its rows share one effect_allele
        "diplotypes[gene=APOE, haplotype_b=ε4]",
        "pharm_variants[variant_key=rs1, genotype=C/T]",
        "allele_function[gene=APOE, allele=ε4]",
    ],
)
def test_a_direction_row_accepts_an_allele_bearing_member(member: str) -> None:
    assert _row(members=member, trait_efo_id="EFO_0000001", direction="risk").direction == "risk"


def test_the_direction_vocabulary_is_the_shared_one() -> None:
    with pytest.raises(ValidationError, match="direction must be one of"):
        _row(members="variants[variant_key=rs1, genotype=C/T]", direction="harmful")


def test_flags_split_like_variants_flags() -> None:
    assert _row(members="variants[variant_key=rs1]", flags="ap:weak|hallmark:x").flags == [
        "ap:weak",
        "hallmark:x",
    ]


def test_pmid_and_doi_follow_the_study_rules() -> None:
    row = _row(members="variants[variant_key=rs1]", tier="A", pmid="30642433", doi="10.1000/xyz")
    assert (row.pmid, row.doi) == ("30642433", "10.1000/xyz")
    with pytest.raises(ValidationError, match="doi must contain a DOI token"):
        _row(members="variants[variant_key=rs1]", tier="A", doi="not-a-doi")


def test_a_selector_error_reaches_the_row_with_its_message() -> None:
    with pytest.raises(ValidationError, match="selectors over studies.csv are out of bounds"):
        _row(members="studies[pmid=1]", tier="A")


def test_an_authored_members_key_is_overwritten_like_every_stamped_column() -> None:
    """`variant_key`'s rule (`reject_compiler_filled`'s docstring): a stamped value is ignored, never trusted."""
    row = _row(members="variants[variant_key=rs1]", tier="A", members_key="anything")
    assert row.members_key == "variants[variant_key=rs1]"


# ── precedence ranks ─────────────────────────────────────────────────────────────────────────────


def test_rank_orders_concrete_over_locus_over_more_conditions_over_fewer() -> None:
    target = {"variant_key": "rs1", "genotype": "A/G"}
    concrete = member_rank(parse_members("variants[variant_key=rs1, genotype=A/G]")[0], target)
    locus = member_rank(parse_members("variants[variant_key=rs1]")[0], target)
    two = member_rank(parse_members("variants[gene=ADARB1, flags=legacy]")[0], target)
    one = member_rank(parse_members("variants[flags=legacy]")[0], target)
    assert concrete > locus > two > one


def test_a_concrete_member_is_the_full_key_of_the_row_it_matches() -> None:
    """A diplotype key carries `trait_efo_id`/`drug`/`clinical_context`; an empty one need not be named."""
    member = parse_members("diplotypes[gene=APOE, haplotype_a=ε2, haplotype_b=ε4]")[0]
    target = {"gene": "APOE", "haplotype_a": "ε2", "haplotype_b": "ε4", "trait_efo_id": None}
    with_trait = {**target, "trait_efo_id": "EFO_1"}
    assert member_rank(member, target)[0] == 3
    assert member_rank(member, with_trait)[0] == 1
