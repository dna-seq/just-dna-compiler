"""A `-` where a `_` goes is the commonest slip in a hand-written cell, and it is now accepted.

The DSL exists for a human — if this format only wanted machine precision it would ship parquet and
no CSVs at all — so a separator slip in a categorical is an authoring cost the schema should absorb
rather than charge. It was also *inconsistent*: the enricher CLI normalized `--use non-commercial` on
its way in while `SourceRow` refused the identical string in a `licensing.csv` cell, so the surface an
author learns the vocabulary from taught a spelling the file rejected.

`vocab.match_vocab` is the one definition; `check_vocab` runs it, so every closed vocabulary in the
schema gets the behaviour and none of them carries a private copy. The vocabularies are discovered
here rather than listed, so a new one is covered without editing this file.
"""

import pytest
from just_dna_format import vocab
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import check_vocab, match_vocab


def _closed_vocabularies() -> dict[str, frozenset[str]]:
    """Every `VALID_*` frozenset the module exports, found by inspection rather than by a list."""
    return {
        name: value
        for name in dir(vocab)
        if name.startswith("VALID_") and isinstance(value := getattr(vocab, name), frozenset)
    }


def test_the_vocabularies_are_discovered_not_assumed() -> None:
    """Guard the premise of every parametrised test below."""
    found = _closed_vocabularies()
    assert len(found) > 5
    assert "VALID_DECLARED_USE" in found


@pytest.mark.parametrize("name,members", sorted(_closed_vocabularies().items()))
def test_either_separator_reaches_the_declared_member(name: str, members: frozenset[str]) -> None:
    """Written with the other separator, a member still resolves — to its canonical spelling.

    Canonicalizing rather than merely accepting matters: the value is what gets stored, hashed into
    a fact signature and compared by a consumer, so two spellings must not both survive into data.
    """
    for member in members:
        swapped = member.replace("_", "-") if "_" in member else member.replace("-", "_")
        assert match_vocab(member, members) == member
        assert match_vocab(swapped, members) == member
        assert check_vocab(swapped, members, name) == member


@pytest.mark.parametrize("name,members", sorted(_closed_vocabularies().items()))
def test_no_vocabulary_has_two_members_that_differ_only_by_separator(
    name: str, members: frozenset[str]
) -> None:
    """The one shape that would make the swap ambiguous — and it would be a bug in the vocabulary.

    Two members differing only in their separators are two spellings of one thing, which Principle 6's
    closed-vocabulary idiom exists to prevent. Asserted rather than assumed, because the acceptance
    above quietly depends on it.
    """
    folded = [member.replace("-", "_") for member in members]
    assert len(set(folded)) == len(folded)


def test_a_value_that_names_nothing_still_fails_with_the_full_list() -> None:
    """Widening the accepted spellings must not blunt the refusal for a real mistake."""
    with pytest.raises(ValueError) as caught:
        check_vocab("commerical", vocab.VALID_DECLARED_USE, "declared_use")
    assert "declared_use must be one of" in str(caught.value)
    assert "commerical" in str(caught.value)
    assert match_vocab("commerical", vocab.VALID_DECLARED_USE) is None


def test_the_authored_cell_now_agrees_with_the_cli_flag() -> None:
    """The concrete inconsistency, closed: same string, same answer, on both surfaces.

    `--use non-commercial` was always accepted. The identical cell was not, which is the report that
    prompted this.
    """
    row = SourceRow(source="cpic", layer="annotation", declared_use="non-commercial")
    assert row.declared_use == "non_commercial"
    assert row.declared_use in vocab.VALID_DECLARED_USE


def test_none_still_means_unknown_rather_than_a_match() -> None:
    """Tri-state is the house algebra: an absent categorical is not a member and never becomes one."""
    assert check_vocab(None, vocab.VALID_DECLARED_USE, "declared_use") is None
