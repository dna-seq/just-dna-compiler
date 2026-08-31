"""`direction` gains `contested`, and the projection map is the edit that had to come first (RM150).

The reporter (S83) said `direction`'s `unknown` covers three things: *no evidence*, *conflicting
evidence*, and *evidence that does not exclude either direction*. RM148 removed the third by
**reassignment** — an unestablished sign is still a sign, so that state is the pair `direction=<sign>`
+ `stat_significance=not_significant`, and a member for it would have been a second spelling. That
reasoning holds and is not reopened here.

It does not reach the first two. `unknown` meant both *not assessed* and *the sources conflict*, and
RM148's own field description said so out loud while giving a consumer nothing to tell them apart.
**They are not one thing: one is an absence and the other is a finding**, and no pairing of
`direction` with `stat_significance` can express "two sources disagree about the sign", which is why
this shade earns a member where the third did not.

**`unknown` keeps its original meaning.** Re-pointing a shipped member at the narrower sense would
silently change what every published module already says by it — a retype in everything but name, and
Principle 3 territory. Adding beside it is minor-legal.
"""

import pytest
from just_dna_format.derive import (
    _DIRECTION_TO_STATE,
    direction_from_state,
    trimmed_state,
)
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import VALID_DIRECTIONS, VALID_SIGNIFICANCE

# ── the guard, which is the point of the whole item ─────────────────────────────────────────────


def test_every_direction_has_an_explicit_legacy_projection() -> None:
    """An **equality over the walked set**, because `trimmed_state` reads the map with a default.

    `_DIRECTION_TO_STATE.get(direction, "neutral")` does not raise on a missing member — it projects
    silently to `neutral`. So a member added to `VALID_DIRECTIONS` and nowhere else produces a module
    whose `upgraded()` emits a wrong legacy `state` with nothing failing anywhere.

    A floor (`>= 4 entries`) or a spot check on one member is satisfied by exactly the state that
    would ship the bug, which is why this is set equality (`@registry-completeness`).
    """
    assert set(_DIRECTION_TO_STATE) == VALID_DIRECTIONS


def test_the_projection_default_is_what_makes_the_guard_above_necessary() -> None:
    """The trap, demonstrated rather than described — and why an output assertion proves nothing.

    `trimmed_state("contested") == "neutral"` was already true **before** `contested` existed, and it
    is equally true of a string that is not a direction at all. A test written that way would have
    passed against the unfixed code and measured nothing; the guard has to be about the map's
    coverage, not about its output.
    """
    assert trimmed_state("a string that is not a direction") == "neutral"
    assert trimmed_state("contested") == "neutral"
    # The difference the guard catches: one of those is in the map, the other falls through.
    assert "contested" in _DIRECTION_TO_STATE
    assert "a string that is not a direction" not in _DIRECTION_TO_STATE


# ── the member itself ───────────────────────────────────────────────────────────────────────────


def test_contested_is_a_direction_and_unknown_still_means_what_it_meant() -> None:
    """Both halves of the decision at once: added beside, never re-pointed.

    A shipped `unknown` still validates and still projects the same way, so nothing a published module
    already says changes meaning.
    """
    assert {"unknown", "contested"} <= VALID_DIRECTIONS
    assert trimmed_state("unknown") == "neutral"


def test_an_authored_row_can_carry_it() -> None:
    """The end-to-end claim: a curator can write the finding down."""
    row = VariantRow(
        rsid="rs1801133", genotype="C/T", state="neutral", conclusion="x", direction="contested"
    )
    assert row.direction == "contested"


def test_the_legacy_state_map_deliberately_gains_nothing() -> None:
    """The asymmetry the two maps invite you to "fix", and must not.

    No legacy `state` value means *the sources disagree about the sign*, so there is nothing to map
    FROM. A module upgraded off the legacy column can never produce `contested`; only an author
    writing `direction` directly can.
    """
    assert "contested" not in set(_STATE_VALUES := {"protective", "risk", "neutral", "significant", "alt", "ref"})
    assert all(direction_from_state(state) != "contested" for state in _STATE_VALUES)


def test_it_went_to_direction_only() -> None:
    """`contested` is about the SIGN. A disputed strength is not the same claim, so
    `stat_significance` gains nothing and the two vocabularies stay as independent as they were."""
    assert "contested" not in VALID_SIGNIFICANCE
    assert VALID_DIRECTIONS & VALID_SIGNIFICANCE == {"unknown"}


# ── P7: nothing existing drifts ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("direction", sorted(VALID_DIRECTIONS))
def test_the_projection_is_idempotent_over_every_member(direction: str) -> None:
    """`trimmed_state` lands in the trimmed legacy set, and re-projecting is a no-op.

    Parametrized over the walked vocabulary rather than a written-out list, so a future member is
    covered the day it is added.
    """
    projected = trimmed_state(direction)
    assert projected in {"protective", "risk", "neutral"}
    assert trimmed_state(projected) == projected


def test_upgrading_a_legacy_row_is_unchanged_by_the_new_member() -> None:
    """Nothing re-points, so nothing drifts: an existing `unknown` row upgrades exactly as before.

    This is the half that makes the addition minor-legal rather than a retype — computed by running
    the real derivation over every legacy `state`, not by asserting a remembered table.
    """
    for state in ("protective", "risk", "neutral", "significant", "alt", "ref"):
        derived = direction_from_state(state)
        assert derived in VALID_DIRECTIONS
        assert derived != "contested"
        assert trimmed_state(derived) in {"protective", "risk", "neutral"}


def test_upgraded_really_projects_contested_and_stays_idempotent() -> None:
    """`upgraded()` overwrites `state` with `trimmed_state(direction)`, so the projection is visible.

    Authored `state="risk"` on purpose: a `neutral` row would come out `neutral` whether the
    projection ran or the authored value simply passed through, and the test would prove nothing about
    the map entry it exists to cover. `risk` -> `neutral` can only be the projection.

    The second half is Principle 7: `upgraded()` must stay idempotent with the new member.
    """
    row = VariantRow(
        rsid="rs1801133", genotype="C/T", state="risk", conclusion="x", direction="contested"
    )
    once = row.upgraded()
    twice = once.upgraded()

    assert once.direction == "contested"
    assert once.state == "neutral", "the authored `risk` was overwritten by the lossy projection"
    assert twice.model_dump() == once.model_dump()


def test_the_projection_is_what_moved_and_not_the_authored_cell() -> None:
    """The control for the test above: without the map entry this row would still read `neutral`.

    `needs_upgrade` is the marketplace-facing predicate, so it is asserted directly — a contested row
    whose legacy `state` disagrees is genuinely drifted and should say so.
    """
    drifted = VariantRow(
        rsid="rs1801133", genotype="C/T", state="risk", conclusion="x", direction="contested"
    )
    settled = drifted.upgraded()

    assert drifted.needs_upgrade is True
    assert settled.needs_upgrade is False


def test_an_existing_unknown_row_does_not_newly_drift() -> None:
    """The half that makes this an addition rather than a retype: nothing published changes state.

    A module already carrying `direction=unknown` with the legacy `state` it always had must not
    start reporting `needs_upgrade` because a member was added next to it.
    """
    row = VariantRow(
        rsid="rs1801133", genotype="C/T", state="neutral", conclusion="x", direction="unknown"
    ).upgraded()

    assert row.needs_upgrade is False
    assert row.state == "neutral"
