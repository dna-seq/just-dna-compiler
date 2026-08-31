"""Every authored column says which release it appeared in (RM146).

A module authored on 0.6.6 was sent to a registry deployment running 0.6.1, which runs `validate_spec`
server-side and reports its findings verbatim. It said:

    studies.csv line 2 [curator]: Extra inputs are not permitted

`StudyRow.curator` is ours, added in 0.6.5. A genuine typo produces the byte-identical shape —
`[curatr]` — and the two want **opposite actions** from an author: upgrade the reader, or fix the cell.
The finding is pydantic's under `extra="forbid"`, so it cannot be reworded into carrying the
distinction: the information was not in the model at all.

**Declared on the field rather than in a roster**, because a hand-kept list beside a model is a second
statement of one fact and it is the copy that goes stale (`@fieldnames-from-model`). The guard below is
therefore the load-bearing half: an **equality over the walked registry**, so the next column added
cannot omit one. A floor or a count is satisfied by exactly the state that produced the report.

**The backfill was measured, not recalled** — parsed out of each release tag's own sources, per
`(model, field)`. `curator` is why that matters and is asserted below.
"""

import re

import pytest
from just_dna_format.base import field_first_seen, since
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.spec import StudyRow, VariantRow

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

#: Releases that exist, plus the uncut one this work lands in. A field may not claim a version that
#: was never published — the commonest way a hand-edited marker goes wrong is a typo'd number, and
#: nothing else in the model would catch it.
_RELEASES: frozenset[str] = frozenset(
    {
        "0.2.0", "0.3.0", "0.4.0",
        "0.5.0", "0.5.1", "0.5.2", "0.5.3", "0.5.4",
        "0.6.0", "0.6.1", "0.6.2", "0.6.3", "0.6.4", "0.6.5", "0.6.6",
        "0.7.0",
    }
)


# ── the guard ───────────────────────────────────────────────────────────────────────────────────


def test_every_field_of_every_authored_model_declares_a_first_seen() -> None:
    """An **equality over the walked set**, which is the only shape that catches the next omission.

    `>= 400 fields` or `len(...) > 0` would both pass on the tree that shipped the report this item is
    about. The set difference names the offenders, so a failure says which field to fix rather than
    that some field is wrong (`@registry-completeness`).
    """
    missing: list[str] = []
    for model in _ALL_MODELS.values():
        declared = set(field_first_seen(model))
        missing.extend(f"{model.__name__}.{f}" for f in set(model.model_fields) - declared)

    assert missing == [], f"fields with no first_seen: {sorted(missing)}"


def test_the_registry_really_covers_the_authored_surface() -> None:
    """The guard above is only as complete as the registry it walks, so the registry is checked too.

    `GeneMetricsRow` sat outside `_ALL_MODELS` once and its unenforced vocabulary went unnoticed for
    exactly that reason (RM96). A guard over an incomplete registry reports a clean bill about the
    models it happens to know.
    """
    assert len(_ALL_MODELS) >= 31, "the registry lost a model"
    total = sum(len(m.model_fields) for m in _ALL_MODELS.values())
    assert total >= 414, "the authored surface shrank; a removal is major-only under Principle 3"


@pytest.mark.parametrize("label", sorted(_ALL_MODELS))
def test_every_declared_version_is_a_release_that_exists(label: str) -> None:
    """A typo'd version is the one error the model itself cannot catch, so it is caught here."""
    for field, version in field_first_seen(_ALL_MODELS[label]).items():
        assert _SEMVER.match(version), f"{label}.{field} = {version!r} is not a SemVer"
        assert version in _RELEASES, f"{label}.{field} claims {version!r}, which was never published"


# ── the worked example, which is why the answer is per (model, field) ───────────────────────────


def test_curator_answers_differently_on_the_two_models_that_carry_it() -> None:
    """**The case that decides the shape.** `curator` is on `VariantRow` from the 0.2 line and gains
    its `StudyRow` twin only in 0.6.5, so a roster keyed by *column name* would give one answer for
    two facts — and the wrong one for the module in the report.
    """
    assert field_first_seen(VariantRow)["curator"] == "0.2.0"
    assert field_first_seen(StudyRow)["curator"] == "0.6.5"


def test_a_field_added_in_this_release_says_so() -> None:
    """The uncut release is a legal answer: a column that exists in no tag ships in 0.7.0."""
    from just_dna_format.pgx import PharmVariantRow

    assert field_first_seen(PharmVariantRow)["pmid"] == "0.7.0"


# ── the marker's own contract ───────────────────────────────────────────────────────────────────


def test_the_marker_composes_with_the_vocabulary_one() -> None:
    """Both ride in one `json_schema_extra` dict, so a field may carry either or both.

    Asserted over the real models rather than a toy: a field that is both vocabulary-bound and
    versioned must answer both questions, and an implementation that replaced the dict rather than
    merging into it would silently drop the older marker.
    """
    from just_dna_format.base import field_vocabularies

    both = [
        (m.__name__, f)
        for m in _ALL_MODELS.values()
        for f in set(field_vocabularies(m)) & set(field_first_seen(m))
    ]
    assert both, "no field carries both markers, so this test is not measuring anything"
    for label, field in both:
        model = next(m for m in _ALL_MODELS.values() if m.__name__ == label)
        assert field_vocabularies(model)[field]["options"]
        assert field_first_seen(model)[field] in _RELEASES


def test_the_reader_returns_nothing_for_a_model_that_declares_nothing() -> None:
    """Absence is an empty map, never a guess. A consumer asking about an unmarked model gets `{}`
    and can say *this reader cannot tell you*, rather than being handed a fabricated version."""
    from pydantic import BaseModel

    class Bare(BaseModel):
        x: str | None = None

    assert field_first_seen(Bare) == {}


def test_the_marker_is_a_plain_dict_a_consumer_can_read_offline() -> None:
    """The point of the ask: any tool rendering our findings answers *when did this column appear*
    without importing our validators or parsing `model_fields` itself."""
    assert since("0.6.5") == {"first_seen": "0.6.5"}
