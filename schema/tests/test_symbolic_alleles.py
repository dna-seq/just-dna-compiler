"""The symbolic/structural allele grammar (0.6, RM5) — the schema half.

What is under test here is the **grammar**: which spellings the authored DSL accepts, what a parse
yields, and where a widening must have left the existing alphabet untouched. What a *compile* does
with a symbolic allele it cannot apply lives in `compiler/tests/test_symbolic_alleles.py`; the split
is the one the implementation makes, and it is forced — a model-level rejection is fatal in both
modes, so a lengthless `<DEL>` has to load before the compiler can warn-and-drop it.

Every allele here is a spelling VCF 4.4 actually defines (§1.4.5, §5.6, §5.7) or one a real source
writes: no invented notation, because the question is what the standard says and not what a grammar
could be made to swallow.
"""

import pytest
from just_dna_format.alleles import (
    RECOMMENDED_SYMBOLIC_SUBTYPES,
    SYMBOLIC_ALLELE_TYPES,
    is_symbolic_allele,
    non_nucleotide_reason,
    parse_symbolic_allele,
    symbolic_allele_defect,
)
from just_dna_format.base import genotype_allele_ok
from just_dna_format.binning import HeteroplasmyRow
from just_dna_format.pgx import AlleleFunctionRow, HaplotypeRow, PharmVariantRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import validate_allele
from pydantic import ValidationError

# ── the closed five, and what a parse yields ────────────────────────────────────────────────────


def test_the_first_level_is_vcfs_closed_five() -> None:
    """VCF 4.4 §1.4.5 lists exactly these as first-level structural types, and RM5 took that set
    whole. A sixth would need the `##ALT=<ID=…>` declaration mechanism the item rejected."""
    assert set(SYMBOLIC_ALLELE_TYPES) == {"DEL", "INS", "DUP", "INV", "CNV"}


def test_every_recommended_subtype_parses_and_names_a_member_of_the_five() -> None:
    """The subtypes the spec recommends are `CNV:TR`, `DUP:TANDEM`, `DEL:ME`, `INS:ME` — so each must
    parse, and each must resolve to a first-level type the closed set holds. Subtypes themselves are
    open (the standard leaves them to the implementation), which is why only the head is checked."""
    for subtype in RECOMMENDED_SYMBOLIC_SUBTYPES:
        parsed = parse_symbolic_allele(f"<{subtype}:30>")
        assert parsed is not None, subtype
        assert parsed.kind == subtype
        assert parsed.type in SYMBOLIC_ALLELE_TYPES
        assert parsed.length == 30


def test_an_unfamiliar_subtype_is_accepted_because_the_standard_leaves_them_open() -> None:
    parsed = parse_symbolic_allele("<DEL:SOMETHING_ELSE:12>")
    assert parsed is not None
    assert (parsed.type, parsed.subtypes, parsed.length) == ("DEL", ("SOMETHING_ELSE",), 12)


def test_the_length_rides_in_the_token_and_is_read_back_as_an_integer() -> None:
    """The design decision the item turned on: SVLEN is `Number=A` in VCF 4.4 — one value per ALT —
    so it belongs to the allele rather than to the row."""
    assert parse_symbolic_allele("<DEL:1500>").length == 1500
    assert parse_symbolic_allele("<CNV:TR:30>").length == 30
    assert parse_symbolic_allele("<DEL>").length is None


def test_case_is_normalized_on_the_parse_and_preserved_on_the_cell() -> None:
    """Matches how nucleotide alleles already behave — `validate_allele` accepts `acgt` and rewrites
    nothing — while `hosting_verdict` compares upper-cased, so a parse has to answer upper-case."""
    parsed = parse_symbolic_allele("<del:tandem:9>")
    assert (parsed.type, parsed.subtypes) == ("DEL", ("TANDEM",))
    assert parsed.text == "<del:tandem:9>"
    assert validate_allele("<del:9>", "allele") == "<del:9>"


# ── the three defects, each with its own answer ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label,allele,expected",
    [
        ("a length makes it usable", "<DEL:1500>", None),
        ("a subtype plus a length", "<CNV:TR:30>", None),
        ("VCF's own bare spelling states no length", "<DEL>", "no_length"),
        ("a zero length states no event either", "<DEL:0>", "no_length"),
        ("a name outside the five", "<FOO:10>", "unknown_type"),
        ("VCF's unspecified allele is not a structural type", "<*>", "unknown_type"),
        # The likeliest symbolic typo there is, and it must not read as an ordinary allele string:
        # `is_symbolic_allele` tests for the *opening* bracket alone, so this is diagnosed rather
        # than handed to the character arithmetic `hosting_verdict`'s guard exists to prevent.
        ("an unterminated bracket", "<DEL", "unknown_type"),
        ("a nucleotide string has no symbolic defect", "ACGT", None),
        ("nor does an ambiguity code", "Y", None),
        ("nor does a repeat notation", "AAAGGGGCG(2)", None),
    ],
)
def test_the_defect_matrix(label, allele, expected) -> None:
    assert symbolic_allele_defect(allele) is expected, label


def test_shaped_like_one_and_being_one_are_different_questions() -> None:
    """`<FOO>` is not a usable allele *and* is unmistakably an attempt at one, which is what lets the
    compiler answer with a diagnosis instead of the generic rejection every unknown value gets.

    The shape test asks only for the **opening** bracket. Requiring the closing one let `<DEL` read as
    an ordinary allele string, so it slipped past `hosting_verdict`'s guard into `parsimony_reduce`,
    where a four-character token gets treated as a four-base sequence. Nothing legal in an allele
    column begins with `<`, so the looser test costs nothing.
    """
    assert is_symbolic_allele("<FOO>") and parse_symbolic_allele("<FOO>") is None
    assert is_symbolic_allele("<DEL") and parse_symbolic_allele("<DEL") is None
    assert not is_symbolic_allele("DELTCT")
    assert not is_symbolic_allele("ACGT")


# ── the classification the two `_spelling_clauses` copies read ──────────────────────────────────


def test_a_well_formed_symbolic_allele_is_its_own_reason_class() -> None:
    """It used to answer `"notation"`, whose message reads *a grammar gap a future release may widen*.
    RM5 is that release, so the sentence became false for the five types and the class had to split —
    otherwise an author is told to wait for something that already happened."""
    assert non_nucleotide_reason("<DEL:1500>") == "symbolic"
    assert non_nucleotide_reason("<CNV:TR:30>") == "symbolic"
    # Still a grammar gap: CPIC's own spellings are not VCF symbolic alleles.
    assert non_nucleotide_reason("DELTCT") == "notation"
    assert non_nucleotide_reason("AAAGGGGCG(2)") == "notation"
    assert non_nucleotide_reason("<FOO>") == "notation"
    # Untouched by the widening.
    assert non_nucleotide_reason("Y") == "ambiguity"
    assert non_nucleotide_reason("ACGT") is None


# ── where the grammar bites: three sites, and the two that were miscounted ──────────────────────


def test_validate_allele_has_two_users_and_both_widened() -> None:
    """`alleles.py` and CLAUDE.md said "exactly one user, `HaplotypeRow.allele`" until RM5. The second
    is `VariantRow.effect_allele`, and a widening applied to one of them would be half a feature."""
    row = HaplotypeRow(haplotype_name="*5", rsid="rs1667266283", allele="<DEL:926>", gene="MSH2")
    assert row.allele == "<DEL:926>"
    variant = VariantRow(
        rsid="rs1667266283", genotype="A/A", state="risk", conclusion="c",
        effect_allele="<DEL:926>",
    )
    assert variant.effect_allele == "<DEL:926>"


@pytest.mark.parametrize(
    "genotype",
    ["<DEL:926>/G", "<DEL:926>|G", "<DEL:926>/<DEL:926>", "<DEL:926>", "<CNV:TR:30>/A"],
)
def test_all_three_arms_of_the_genotype_grammar_admit_a_symbolic_allele(genotype) -> None:
    """Phased, hemizygous and unphased are three code paths that each decided what an allele is; the
    widening had to reach all three, which is why the decision moved into one helper."""
    assert genotype_allele_ok(genotype.split("/")[0].split("|")[0])
    assert VariantRow(
        rsid="rs1", genotype=genotype, state="risk", conclusion="c"
    ).genotype == genotype


def test_the_unphased_sort_rule_still_applies_to_a_symbolic_member() -> None:
    """`<` sorts before `A`, so the canonical spelling of a heterozygous deletion is `<DEL:926>/G`.
    Nothing special was added for it — the existing rule simply covers the new alphabet."""
    with pytest.raises(ValidationError, match="alphabetically sorted"):
        VariantRow(rsid="rs1", genotype="G/<DEL:926>", state="risk", conclusion="c")


def test_a_lengthless_symbolic_allele_LOADS_because_the_compiler_owns_that_refusal() -> None:
    """Forced, not chosen: a model-level rejection surfaces as a load error, which is fatal in both
    modes, and the decided behaviour is warn-and-drop under `best_effort`."""
    assert VariantRow(
        rsid="rs1", genotype="<DEL>/G", state="risk", conclusion="c", effect_allele="<DEL>"
    ).genotype == "<DEL>/G"


def test_an_undeclared_name_is_refused_where_a_column_has_a_grammar() -> None:
    """The closed five, enforced. `<FOO>` is exactly what the rejected `##ALT` declaration mechanism
    would have made authorable, and it is not."""
    with pytest.raises(ValidationError, match="symbolic/structural allele"):
        VariantRow(rsid="rs1", genotype="<FOO>/G", state="risk", conclusion="c")
    with pytest.raises(ValidationError, match="symbolic/structural allele"):
        HaplotypeRow(haplotype_name="*5", rsid="rs1", allele="<FOO>")


def test_ref_and_alts_still_have_no_grammar_at_all() -> None:
    """RM5 widened `validate_allele`; it did **not** give `ref`/`alts` one. Adding a nucleotide
    grammar there stays refused — it would reject `N`, which is real, and break P3 for any module
    that already carries an odd cell. So `<FOO>` reaches the compiler's diagnosis by this route."""
    row = VariantRow(
        chrom="1", start=100, ref="N", alts="<FOO>,Y", genotype="A/A",
        state="risk", conclusion="c",
    )
    assert (row.ref, row.alts) == ("N", "<FOO>,Y")


# ── what the check may read, declared on the models themselves ──────────────────────────────────


def test_every_declared_allele_column_is_a_real_field_of_its_model() -> None:
    """`ALLELE_COLUMNS` is a model-side declaration precisely so the compiler holds no second copy of
    a model's column names — but a declaration naming a column that does not exist would go silently
    blind, which is the same failure by another route."""
    for model in (VariantRow, HaplotypeRow, PharmVariantRow, HeteroplasmyRow):
        assert model.ALLELE_COLUMNS, model.__name__
        missing = [c for c in model.ALLELE_COLUMNS if c not in model.model_fields]
        assert missing == [], (model.__name__, missing)


def test_a_star_allele_name_is_not_a_sequence_and_is_left_out() -> None:
    """`AlleleFunctionRow.allele` is `*4` — an identity, validated by `validate_haplotype_name`. It
    carries no sequence, so scanning it for structural alleles would be scanning the wrong thing."""
    assert AlleleFunctionRow.ALLELE_COLUMNS == ()
    assert AlleleFunctionRow(gene="CYP2D6", allele="*4").allele == "*4"
