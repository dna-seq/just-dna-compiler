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

import inspect
from typing import get_origin

import pytest
from just_dna_format import vocab
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import check_vocab, match_vocab
from pydantic import BaseModel


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


# ── RM95: accepting the slip is half the rule; STORING the declared member is the other half ───────


class _FieldInfo:
    """The one attribute the shared validator reads off `ValidationInfo`."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name


def _vocabulary_bound_validators() -> list[tuple[type[BaseModel], str, frozenset[str], object]]:
    """`(model, field, members, validator function)` for every closed-vocabulary field in the schema.

    Discovered through `field_vocabularies` -- the one route to "what may this cell contain" -- and
    through pydantic's own decorator registry, so a model that grows a vocabulary is covered without
    editing this file. Every module that declares a row model is walked, not just the ones on the
    authoring reference.
    """
    from just_dna_format import (
        assertions,
        binning,
        frequency,
        gene_metrics,
        gene_validity,
        gwas,
        literature,
        manifest,
        pgs,
        pgx,
        resolution,
        sources,
        spec,
    )
    from just_dna_format.base import field_vocabularies

    modules = (
        assertions, binning, frequency, gene_metrics, gene_validity, gwas, literature,
        manifest, pgs, pgx, resolution, sources, spec,
    )
    seen: set[tuple[str, str]] = set()
    found: list[tuple[type[BaseModel], str, frozenset[str], object]] = []
    for module in modules:
        for model in vars(module).values():
            if not (isinstance(model, type) and issubclass(model, BaseModel)):
                continue
            if model.__module__ != module.__name__:
                continue  # imported into this module, owned by another
            registry = model.__pydantic_decorators__.field_validators
            for field, marker in field_vocabularies(model).items():
                if not marker.get("closed") or (model.__name__, field) in seen:
                    continue
                for decorator in registry.values():
                    if field in decorator.info.fields:
                        seen.add((model.__name__, field))
                        found.append((model, field, frozenset(marker["options"]), decorator.func))
                        break
    return found


_VOCAB_FIELDS = _vocabulary_bound_validators()


def test_the_vocabulary_bound_fields_are_discovered_not_assumed() -> None:
    """Guard the premise: the walk must actually find the three fields this test was written for."""
    pairs = {(model.__name__, field) for model, field, _members, _func in _VOCAB_FIELDS}
    assert len(pairs) > 20, sorted(pairs)
    assert {("MeasureBinRow", "measure_kind"), ("Contribution", "role")} <= pairs
    assert ("PgsRow", "training_ancestry") in pairs


@pytest.mark.parametrize(
    "model,field,members,func",
    _VOCAB_FIELDS,
    ids=[f"{m.__name__}.{f}" for m, f, _members, _func in _VOCAB_FIELDS],
)
def test_a_vocabulary_bound_validator_returns_the_declared_member(
    model: type[BaseModel], field: str, members: frozenset[str], func: object
) -> None:
    """Every closed-vocabulary validator must **return** `check_vocab`'s result, not merely call it.

    This is the half `test_either_separator_reaches_the_declared_member` above cannot reach: that one
    proves `check_vocab` canonicalizes, and three validators called it for its raising side effect and
    returned the raw input anyway (RM95). `MeasureBinRow.measure_kind` was the visible one --
    `copy-number` was accepted and *stored*, a value not in the vocabulary, inside `content_signature`,
    and every subclass then rejected it against `_EXPECTED_KIND`, naming the canonical form the input
    already denoted. `Contribution.role` and `PgsRow.training_ancestry` had the identical shape and
    were latent only because no member of either vocabulary contains a separator today -- a property
    of the current members, not of the code.

    Drives the validator rather than constructing a row: required fields differ per model and several
    carry format validators of their own, while the defect lives precisely in this return value.
    Subclasses pinning one member (`CopyNumberRow`) reject the others by design, so a rejection is
    only a failure when the *canonical* spelling is rejected too -- which is the asymmetry the bug
    produced and the assertion below reads.
    """
    # The registry hands back a *bound* classmethod, so `cls` is already applied — and applied to the
    # subclass, which is what makes the `_EXPECTED_KIND` half of `MeasureBinRow` readable from here.
    is_list = get_origin(model.model_fields[field].annotation) in (list, list | None)
    takes_info = len(inspect.signature(func).parameters) > 1

    def run(candidate: str) -> str | None:
        value = [candidate] if is_list else candidate
        stored = func(value, _FieldInfo(field)) if takes_info else func(value)
        return stored[0] if isinstance(stored, list) else stored

    for member in sorted(members):
        swapped = member.replace("_", "-") if "_" in member else member.replace("-", "_")
        try:
            canonical = run(member)
        except ValueError:
            continue  # a subclass that pins a different member — not this field's contract
        assert canonical == member, f"{model.__name__}.{field} altered a declared member"
        assert run(swapped) == member, (
            f"{model.__name__}.{field} stored {run(swapped)!r} for input {swapped!r} — a closed "
            f"vocabulary accepts either separator and stores the declared member ({member!r})"
        )
