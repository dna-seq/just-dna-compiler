"""Every drafter goes through the scaffold, and no drafter hand-lists what the scaffold derives (RM228).

Drafting grew one provider at a time, and seven modules independently reimplemented the same four
decisions. Two guards, because they catch different evasions: the **registry** test catches a new
provider that opts out of the scaffold entirely, and the **AST** test catches an existing one that
joins the registry and then keeps its own copy of a rule anyway.

The rule they enforce is the split in `drafting`'s module docstring: the model's requirement is
**derived**, always, and a provider's own source precondition is **declared with a reason**. What
made this necessary is that a hand-kept list could hold both and nobody could tell which clause was
which — `mitomap_draft` gated *identity* on `clin_sig`, a column the model does not require, and it
read like every other line beside it.
"""

import ast
from pathlib import Path

import pytest
from just_dna_enricher.drafting import DRAFT_PROJECTIONS, DRAFT_PROVIDERS
from just_dna_format.base import IDENTITY_FIELDS

_SRC = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"

#: Functions that write the licence/currency half of a draft. A provider calls these through the
#: scaffold so the covered-predicate and the stale-label withdrawal cannot drift apart again.
_PROVENANCE_CALLS = {"merge_sources_file", "withdraw_stale_dataset", "record_source_terms"}


def _draft_modules() -> list[Path]:
    return sorted(_SRC.glob("*_draft.py"))


def test_every_draft_module_is_in_the_registry() -> None:
    """A new `*_draft.py` cannot arrive without declaring itself — `@registry-completeness`."""
    on_disk = {path.stem for path in _draft_modules()}
    registered = {provider.module for provider in DRAFT_PROVIDERS.values()}

    assert on_disk == registered, (
        f"unregistered drafters: {sorted(on_disk - registered)}; "
        f"registered but absent: {sorted(registered - on_disk)}"
    )


def test_the_projection_map_is_the_registry_and_not_a_second_copy() -> None:
    """`DRAFT_PROJECTIONS` is derived, so the two can no longer disagree."""
    expected = {name for name, p in DRAFT_PROVIDERS.items() if p.kind == "projection"}

    assert set(DRAFT_PROJECTIONS) == expected
    for name in expected:
        provider, projection = DRAFT_PROVIDERS[name], DRAFT_PROJECTIONS[name]
        assert projection.table == provider.table
        assert projection.checked == provider.checked
        assert projection.identity == provider.identity


def test_a_projection_identity_that_differs_from_match_on_states_why() -> None:
    """The one real divergence (`pubmind`) is a field with a reason, not a paragraph in a comment."""
    divergent = [p for p in DRAFT_PROVIDERS.values() if p.projection_identity is not None]

    assert divergent, "the pubmind case disappeared; if that is deliberate, delete this test with it"
    for provider in divergent:
        assert provider.projection_identity != provider.match_on, provider.name
        assert len(provider.projection_identity_reason) > 40, provider.name


def test_every_precondition_states_a_reason_about_its_source() -> None:
    """A precondition with no reason is indistinguishable from a misread of the model.

    That is not hypothetical: `mitomap_draft` required `clin_sig` for *identity*, which the model
    does not require at all, and the line was indistinguishable from the coordinate clauses beside it.
    """
    for provider in DRAFT_PROVIDERS.values():
        if provider.precondition is None:
            continue
        assert len(provider.precondition.reason) > 40, (
            f"{provider.name}'s precondition needs a reason naming the fact about its source"
        )
        assert provider.precondition.fields, provider.name


def _string_tuples(tree: ast.AST) -> list[tuple[list[str], int]]:
    """Every tuple/list/set literal of two or more string constants, with its line."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(values) >= 2 and len(values) == len(node.elts):
                found.append((values, getattr(node, "lineno", 0)))
    return found


@pytest.mark.parametrize("path", _draft_modules(), ids=lambda p: p.stem)
def test_no_drafter_hand_lists_the_identity_columns(path: Path) -> None:
    """The mitomap shape, refused structurally.

    A literal listing two or more `IDENTITY_FIELDS` inside a drafter is either a private `_MATCH_ON`
    (now a registry field) or a hand-written identity rule (now derived). Walked off
    `base.IDENTITY_FIELDS` rather than a list here, so the guard inherits the schema's answer.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    identity = set(IDENTITY_FIELDS)

    offenders = [
        (values, line)
        for values, line in _string_tuples(tree)
        if len([v for v in values if v in identity]) >= 2
    ]

    assert not offenders, (
        f"{path.name} hand-lists identity columns at line(s) "
        f"{[line for _v, line in offenders]}: {[v for v, _l in offenders]}. "
        "`match_on` is a `DRAFT_PROVIDERS` field and the identity rule is derived by "
        "`drafting.skip_reason`; a literal here is the copy that drifts (RM228)."
    )


@pytest.mark.parametrize("path", _draft_modules(), ids=lambda p: p.stem)
def test_no_drafter_writes_its_licence_row_directly(path: Path) -> None:
    """The covered-predicate and the stale-label withdrawal travel together or not at all.

    Three providers wrote the licence row themselves and two of those forgot `withdraw_stale_dataset`
    entirely, so a re-curation left a stale release label with nothing to notice it. Routing the
    write through the scaffold is what makes the pair inseparable.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    direct = called & _PROVENANCE_CALLS
    assert not direct, (
        f"{path.name} calls {sorted(direct)} directly. Draft provenance goes through "
        "`drafting.record_draft_provenance`, which writes the row only when this run covered "
        "something and withdraws a stale dataset label in the same breath (RM228)."
    )
