"""The integration doc may not state a registry's size; it must send the reader to the constant (RM223).

`INTEGRATION_0_7.md` is the document a consumer reads *once*, at upgrade time, and then acts on. It
carried four counts that were already wrong when a downstream repository measured them against the
installed packages: `ARTIFACT_PARQUETS` as 22 where it is 23, `VALID_WARNING_CODES` as 72 in one § and
71 in another where it is 73, and the authoring reference as "31 models, up from 28" where it renders
32. Three of the four moved for one reason — the AlphaGenome round landed `expression_effects` after
the numbers were taken — and none was noticed here, because **nothing walks this file**.
`test_counted_prose.py` reads `SCHEMAS.md` and `COMPILER.md` and stops there.

That is the whole finding. The document's own § 8 already states the rule ("a counted claim in prose
rots exactly like a hand-kept list"), and §§ 2.2 and 2.3 already tell the reader to derive from
`ARTIFACT_PARQUETS` and `OVERRIDABLE_TABLES` — the advice was right and was sitting one paragraph
above the numbers contradicting it.

**Why this forbids the shape rather than checking the values.** Asserting that each spelled number
equals its constant keeps the sentences true and keeps the pattern, so the fifth registry to gain a
member rots a fifth sentence. The property that has to hold is that the document does not make the
claim: a reader told to walk the constant cannot be misled by a stale copy of it. After RM223 the
document states no sizes at all, so there is nothing left to value-check here — the absence *is* the
invariant.

**Why templates rather than proximity.** The first draft of this guard flagged any number near a
registry name and failed on five legitimate sentences, three of them written by RM223 itself: a
frozen *before* value ("goes 19 →"), an enumerated delta, and the document quoting its own stale word
back while explaining the defect. A guard that refuses prose the document genuinely needs gets worked
around rather than obeyed, so a number counts as a claim only in the three shapes that actually
assert a current size, and `_EXCUSED` names what makes a nearby number something else.

Binding on the **noun** and not only on the constant's name is what reaches the third defect: "71
warning codes" named no constant at all, which is precisely why nothing caught it.
"""

import re
from pathlib import Path

import pytest
from just_dna_compiler.compiler import ARTIFACT_PARQUETS
from just_dna_format import vocab
from just_dna_format.reference import authoring_reference

_DOC = Path(__file__).resolve().parents[2] / "docs" / "INTEGRATION_0_7.md"

#: Nouns this document uses for what a registry holds, and the registry that decides how many.
_NOUNS: dict[str, str] = {
    "warning codes": "VALID_WARNING_CODES",
    "models": "authoring_reference()['models']",
    "overridable tables": "OVERRIDABLE_TABLES",
    "verification checks": "VALID_VERIFICATION_CHECKS",
}
# "parquets" is deliberately **not** here. The document legitimately counts the parquets inside a
# built artifact ("8,812,917,339 rows over 24 parquets"), which is a measurement of a snapshot and
# not a claim about `ARTIFACT_PARQUETS`; the arrow and parenthesis templates already cover the
# registry wherever the document names it. A noun that cannot tell the two apart belongs in neither.

#: Constants whose size may not be stated beside their own name.
_REGISTRIES = ("ARTIFACT_PARQUETS", "VALID_WARNING_CODES", "OVERRIDABLE_TABLES")

_WORDS = (
    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen"
    r"|sixteen|seventeen|eighteen|nineteen|twenty|twenty-one|twenty-two|twenty-three|twenty-four"
    r"|twenty-five|thirty|thirty-one|thirty-two|thirty-three"
)
_NUM = r"(?:\d+|" + _WORDS + r")"
_REGS = "|".join(_REGISTRIES)
_NOUN_ALT = "|".join(sorted(_NOUNS, key=len, reverse=True))

#: The three shapes in which a number asserts a registry's *current* size.
_TEMPLATES: tuple[tuple[str, str], ...] = (
    (
        r"`(?:" + _REGS + r")`[^\n]{0,20}\(\s*" + _NUM + r"\s*(?:members?|entries)",
        "a parenthesised size beside the constant",
    ),
    (
        r"`(?:" + _REGS + r")`[^\n]{0,40}→\s*\d+\b",
        "the destination of a growth arrow written as a literal",
    ),
    (
        # `[.\d]` in the look-behind keeps a section number out: "### 2.2 Parquets" once matched
        # here as "2 Parquets", which is the heading above the § this guard exists for.
        r"(?<![\w`.\d])" + _NUM + r"\s+(?:new\s+|more\s+)?(?:" + _NOUN_ALT + r")\b",
        "a bare count of a registry's contents",
    ),
)

#: What makes a nearby number something other than a current-size claim.
_EXCUSED = re.compile(
    r"""(?:
          len\(            # derived from the constant, which is the repair
        | up\s+from        # an explicit before-value
        | said\s           # the document quoting its own stale prose back
        | was\s
        | ["'“]       # a quoted word
    )""",
    re.VERBOSE | re.IGNORECASE,
)


def _claims(text: str) -> list[str]:
    """Every phrase in `text` that states a registry's current size."""
    found: list[str] = []
    for pattern, why in _TEMPLATES:
        for hit in re.finditer(pattern, text, re.IGNORECASE):
            context = text[max(0, hit.start() - 45) : hit.end() + 10]
            if _EXCUSED.search(context):
                continue
            found.append(f"{why}: ...{context.strip()}...")
    return found


@pytest.fixture(scope="module")
def doc() -> str:
    return _DOC.read_text(encoding="utf-8")


def test_the_document_still_points_at_the_constants(doc: str) -> None:
    """The floor. A renamed constant would otherwise make this file vacuously green."""
    missing = [name for name in _REGISTRIES if name not in doc]
    assert not missing, (
        f"{missing} are no longer named in INTEGRATION_0_7.md. Either the document stopped sending "
        "the reader to them (the defect RM223 fixed) or they were renamed and this list needs it too."
    )


def test_no_registry_size_is_stated_in_prose(doc: str) -> None:
    """The rule § 8 of that document states about itself, enforced against the document."""
    claims = _claims(doc)

    assert not claims, (
        "INTEGRATION_0_7.md states a registry's current size instead of sending the reader to the "
        "constant:\n"
        + "\n".join(f"  - {c}" for c in claims)
        + "\n\nDelete the number and name the constant (RM223: four such counts were already wrong "
        "when a consumer measured them against the installed packages)."
    )


def test_the_guard_catches_all_four_sentences_it_was_written_for() -> None:
    """The reach, pinned on the real pre-RM223 text rather than on invented examples."""
    for sentence in (
        "Three new files, so `ARTIFACT_PARQUETS` goes 19 → 22",
        "Also new: `VALID_WARNING_CODES` (72 members) and `CARRIED_WARNING_CODES` (11),",
        "three new closed vocabularies, and 71 warning codes.",
        "walks now renders **31 models**",
    ):
        assert _claims(sentence), sentence


def test_the_prose_the_document_legitimately_needs_stays_writable() -> None:
    """The other direction, and why this guard is templates rather than proximity.

    Three of these five are sentences RM223 itself wrote while explaining the defect.
    """
    for sentence in (
        "Derive from `ARTIFACT_PARQUETS`, which RM194 extended.",
        "`VALID_WARNING_CODES` is new in 0.7.0.",
        "so `ARTIFACT_PARQUETS` goes 19 → `len(ARTIFACT_PARQUETS)`.",
        'this line said "three" while the release shipped four',
        "it said 31 while the release shipped 32",
    ):
        assert not _claims(sentence), sentence


def test_the_registries_this_guard_speaks_for_are_real() -> None:
    """A live cross-check, so the guard cannot outlive what it protects.

    Not an assertion about the numbers — the absence of numbers is what this file defends. What is
    asserted is that each registry is real and non-empty, so a deleted or renamed one fails here
    rather than silently narrowing the guard to nothing.
    """
    sizes = {
        "ARTIFACT_PARQUETS": len(ARTIFACT_PARQUETS),
        "VALID_WARNING_CODES": len(vocab.VALID_WARNING_CODES),
        "authoring_reference()['models']": len(authoring_reference()["models"]),
    }
    assert all(size > 0 for size in sizes.values()), sizes
