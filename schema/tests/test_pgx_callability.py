"""`requires_callable` on the two PGx tables that name a locus (0.7, RM70).

CPIC's star-allele system assumes a position it did not call is reference — that assumption is what a
`*1` call rests on, and until now it lived only in the upstream's prose, because `requires_callable`
was a `VariantRow` column and no PGx table could state it.

The decision is deliberately narrow and the narrowness is what these tests pin. The column landed on
`HaplotypeRow` and `PharmVariantRow` because each of those rows **names a locus**, so a callability
claim on one is about a position the row itself states. `DiplotypeRow` names a star-allele *pair*, not
a locus, so the same column there could only mean "the variants defining these two haplotypes were
callable" — a fact about `haplotypes.csv` restated one table over, free to drift the moment a
definition is edited. One concept, one home. And `callable_from` does **not** travel with the flag:
the two are different axes, one saying a proof is required and the other saying where the proof lives,
and a row may legitimately require one without knowing where the evidence sits.
"""

import pytest
from just_dna_format.integrity import content_signature
from just_dna_format.pgx import DiplotypeRow, HaplotypeRow, PharmVariantRow
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.spec import VariantRow
from pydantic import ValidationError

#: The two PGx models that name a locus, with a minimal valid row for each. Both halves of every test
#: below run over this, so a third table gaining the column cannot be pinned on one and missed on the
#: other.
_LOCUS_ROWS: dict[type, dict[str, object]] = {
    HaplotypeRow: {"haplotype_name": "*2", "rsid": "rs1799853", "allele": "T", "gene": "CYP2C9"},
    PharmVariantRow: {
        "rsid": "rs9923231",
        "gene": "VKORC1",
        "genotype": "C/C",
        "drug": "warfarin",
        "conclusion": "reference homozygote",
    },
}


@pytest.mark.parametrize("model", list(_LOCUS_ROWS), ids=lambda m: m.__name__)
def test_a_pgx_locus_row_distinguishes_unstated_callability_from_a_stated_false(model: type) -> None:
    """The house algebra, on the column that names it: `None` is not `False`.

    The distinction is the entire point of the item. A star-allele module recording CPIC's assumption
    writes `false` — *an uncalled position may be read as reference here* — and that is a claim a
    consumer is entitled to act on. A module that has not thought about callability writes nothing,
    and a consumer must not read the blank as permission. Collapsing the two would hand every
    unconsidered row the assumption CPIC states deliberately.
    """
    base = _LOCUS_ROWS[model]
    unstated = model(**base)
    stated_false = model(**base, requires_callable=False)
    stated_true = model(**base, requires_callable=True)

    assert unstated.requires_callable is None
    assert stated_false.requires_callable is False
    assert stated_true.requires_callable is True
    assert unstated.requires_callable is not stated_false.requires_callable


@pytest.mark.parametrize("model", list(_LOCUS_ROWS), ids=lambda m: m.__name__)
def test_an_unset_callability_column_leaves_a_published_modules_content_signature_alone(
    model: type,
) -> None:
    """P3/P8's additive test, run rather than asserted: the rows a module published before 0.7 hash
    exactly as they did.

    `content_signature` normalizes each row through `model_dump(mode="json", exclude_none=True)`, so
    an optional column left unset drops out of the hash input entirely. That is what makes the
    addition free for every already-published module — and it is a property of the *default*, so it
    breaks the moment someone gives the field a `False` default instead of `None`, which is precisely
    the mistake the tri-state rule exists to prevent.
    """
    csv_name = "haplotypes.csv" if model is HaplotypeRow else "pharm_variants.csv"
    unstated = model(**_LOCUS_ROWS[model])
    stated_false = model(**_LOCUS_ROWS[model], requires_callable=False)

    assert "requires_callable" not in unstated.model_dump(mode="json", exclude_none=True)
    assert "requires_callable" in stated_false.model_dump(mode="json", exclude_none=True)
    # A module that never wrote the column hashes as it always did; one that wrote `false` does not.
    assert content_signature({csv_name: [unstated]}) != content_signature({csv_name: [stated_false]})


def test_a_diplotype_refuses_a_callability_claim_because_it_names_no_locus() -> None:
    """One concept, one home — pinned, with the reason in the failure it produces.

    `extra="forbid"` on `AuthoredModel` is the mechanism, so the refusal is generic; what this test
    fixes is that `DiplotypeRow` stays outside the column's home. A diplotype's callability is a
    property of the defining variants in `haplotypes.csv`, and the moment it is *also* stateable here
    the two can disagree about one fact, with nothing able to say which is right.
    """
    pair = {"gene": "CYP2C9", "haplotype_a": "*1", "haplotype_b": "*2", "conclusion": "IM"}
    assert DiplotypeRow(**pair).gene == "CYP2C9"  # the row itself is fine
    with pytest.raises(ValidationError) as exc:
        DiplotypeRow(**pair, requires_callable=False)
    assert "requires_callable" in str(exc.value)


@pytest.mark.parametrize("model", list(_LOCUS_ROWS), ids=lambda m: m.__name__)
def test_callable_from_does_not_travel_to_a_pgx_table_with_the_flag(model: type) -> None:
    """The two are different axes, and only one of them moved.

    `requires_callable` says a proof is required; `callable_from` says which VCF field the proof lives
    in. A star-allele curator can state the first from the upstream's own prose and has no basis for
    the second, so shipping both would have charged the author full price for a column nothing can
    fill. `VariantRow` keeps both, which is what makes this an omission rather than a retirement.
    """
    assert "callable_from" in VariantRow.model_fields
    assert "callable_from" not in model.model_fields
    with pytest.raises(ValidationError):
        model(**_LOCUS_ROWS[model], callable_from="FORMAT/DP")


def test_exactly_three_row_models_carry_a_callability_flag() -> None:
    """A walked registry, asserted as an equality — never a floor, and never a count in prose.

    The scoping decision is the item: two PGx tables and not three. Stated as "at least these three"
    it would pass with the column silently added to `DiplotypeRow` or to a future table that names no
    locus, which is the one outcome the design rejected. Walked over `_ALL_MODELS` so a model added
    without being registered cannot hide either.
    """
    carriers = {
        name for name, model in _ALL_MODELS.items() if "requires_callable" in model.model_fields
    }
    assert carriers == {"VariantRow", "HaplotypeRow", "PharmVariantRow"}
