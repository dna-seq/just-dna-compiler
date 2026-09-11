"""`SCHEMAS.md` names every vocabulary `vocab` owns (RM217).

Found by the superset sweep of the 2026-09-11 blind re-derivation: eight of `vocab`'s 29
`VALID_*`/`RECOMMENDED_*` frozensets were named nowhere in the maintained format reference, and two —
`RECOMMENDED_ANCESTRY_GROUPS` and `VALID_EFFECT_DIRECTIONS` — appeared in **no** maintained document.
The other six were reachable only from INTEGRATION and ROADMAP_HISTORY, which record one release
rather than describing the tier, so a reader arriving at the reference could not find them at all.

**What the table carries and what it deliberately does not.** Not the members: those are
`authoring_reference()` and the constants themselves, and a hand-kept copy of a member list is exactly
how `SOURCES_FIELDNAMES` lost a column (`@fieldnames-from-model`). What a table can hold without
rotting is the *count*, the *openness* and what the set is for — and the count is asserted here, so
adding a member without touching the doc fails rather than drifting.

**Scoped to `vocab`'s own sets on purpose.** The leaves own their vocabularies (`spec`, `binning`,
`pgx`, `pgs`, `manifest`, `sources`) and a central registry would need `vocab` to import `pgx`, which
is the cycle `base`'s dependency note exists to avoid. Those are reached through the field markers and
`authoring_reference()`; this guard does not pretend otherwise.
"""

import re
from pathlib import Path

from just_dna_format import vocab

_DOC = Path(__file__).resolve().parents[2] / "docs" / "SCHEMAS.md"
_HEADER = "**The roster of `vocab`'s own sets (RM217).**"


def _owned() -> dict[str, frozenset]:
    return {
        name: getattr(vocab, name)
        for name in dir(vocab)
        if name.startswith(("VALID_", "RECOMMENDED_")) and isinstance(getattr(vocab, name), frozenset)
    }


def _rows() -> dict[str, int]:
    doc = _DOC.read_text(encoding="utf-8")
    assert _HEADER in doc, f"the vocabulary roster's heading moved; looked for {_HEADER!r}"
    section = doc.split(_HEADER)[1].split("\n  **")[0]
    return {
        name: int(count) for name, count in re.findall(r"\| `(\w+)` \| (\d+) \((?:open|closed)\)", section)
    }


def test_the_roster_names_every_vocabulary_vocab_owns() -> None:
    listed = set(_rows())
    owned = set(_owned())
    assert listed == owned, f"vocabulary roster drifted: {sorted(listed ^ owned)}"


def test_every_stated_member_count_is_the_real_one() -> None:
    """The one number a table like this can carry, so it is the one that gets asserted."""
    owned = _owned()
    wrong = {
        name: (stated, len(owned[name])) for name, stated in _rows().items() if stated != len(owned[name])
    }
    assert not wrong, f"stated count != actual, as (stated, actual): {wrong}"


def test_openness_matches_the_naming_convention() -> None:
    """`RECOMMENDED_` is the open half and `VALID_` the closed one — the flag is load-bearing.

    `actionability` shipped as an open seed while `VariantRow` rejected non-members, so a tool
    offering a novel value got a rejection it had been told to expect. A table that mislabelled one
    would re-create exactly that.
    """
    doc = _DOC.read_text(encoding="utf-8")
    section = doc.split(_HEADER)[1].split("\n  **")[0]
    for name, openness in re.findall(r"\| `(\w+)` \| \d+ \((open|closed)\)", section):
        expected = "open" if name.startswith("RECOMMENDED_") else "closed"
        assert openness == expected, f"{name} is listed {openness}, expected {expected}"
