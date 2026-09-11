"""The unphased sort rule follows the grammar's own case-insensitivity (RM214).

`vocab.ALLELE_PATTERN` is `^[ACGT]+$` with `re.IGNORECASE`, so a lowercase allele is a deliberately
legal spelling. The ordering rule beside it used a plain `sorted()`, which is ASCII — and ASCII puts
**every** uppercase letter before **every** lowercase one. So `A/g` was accepted and `a/G` refused:
the same unordered pair, two different answers, decided by which half the author happened to shift.

Measured before the repair, all four spellings of one heterozygote:

    A/G  accepted     A/g  accepted
    a/g  accepted     a/G  REFUSED

The key is `str.casefold` and the sort is stable, so every value that sorted before still sorts and
nothing already authored moves. This only stops refusing the mirror spelling.

**What it deliberately does not do**, stated here because the gap is the interesting half: it does not
make the pair *canonical*. `A/g` and `a/G` are both accepted now and hash differently under
`content_signature`, because the cell is stored verbatim — `@verbatim-except-order` normalizes the
ORDER and nothing else. Normalizing allele case would move the signature of every module carrying a
lowercase allele, which is a question about what an identity key means and therefore 1.0 work, not a
minor-release repair. Filed rather than done.
"""

import pytest
from just_dna_format.spec import VariantRow

_COMMON = {"rsid": "rs1801133", "state": "risk", "conclusion": "a conclusion"}


def _genotype(value: str) -> str:
    return VariantRow(genotype=value, **_COMMON).genotype


@pytest.mark.parametrize("value", ["A/G", "A/g", "a/G", "a/g"])
def test_every_case_spelling_of_a_sorted_pair_is_accepted(value: str) -> None:
    """`a/G` is the one that was refused, and the other three are the control around it."""
    assert _genotype(value) == value


@pytest.mark.parametrize("value", ["G/A", "g/A", "G/a", "g/a"])
def test_an_unsorted_pair_is_still_refused_in_every_case_spelling(value: str) -> None:
    """The rule still has teeth: making the sort case-blind must not make it case-*free*."""
    with pytest.raises(ValueError, match="alphabetically sorted"):
        _genotype(value)


def test_the_refusal_names_the_spelling_it_wants() -> None:
    """The message is what an author acts on, and it must suggest a value that validates."""
    with pytest.raises(ValueError) as excinfo:
        _genotype("g/A")

    message = str(excinfo.value)
    assert "'A/g'" in message, message
    assert _genotype("A/g") == "A/g"


def test_the_cell_is_stored_verbatim() -> None:
    """Only the ORDER is normalized. The open half of this item is that these are two signatures."""
    assert _genotype("A/g") == "A/g"
    assert _genotype("a/G") == "a/G"
