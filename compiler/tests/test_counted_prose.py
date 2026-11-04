"""The numbers the maintained docs spell out, asserted against the code that fixes them.

**This file exists because the same count went stale twice.** `docs/SCHEMAS.md` said "nine" while
there were seven derived-fact sidecars, and its own § on the hash family carries a note saying so.
Every repair so far has been to re-count and re-write the word, which fixes the instance and not the
class: prose is not walked by anything, so the third drift is discovered the same way the first two
were — by a reader who happens to care.

So the rule the docs state about themselves is enforced here. `SCHEMAS.md` now says the sidecar count
"is `len(_FACT_TABLES)`", and this is what makes that sentence true rather than aspirational.

**The roster assertion is the load-bearing one**, not the numbers. A number can be right while the
list beside it is a function short, and it is the list a reader actually uses — so the fact-signature
family is compared as a **set equality against the code** (`@registry-completeness`: assert an
equality over a walked set, never a floor or a count in prose), and the two spelled-out numbers are
then derived from the roster this test just proved correct.

Reading a maintained doc from a test is not novel here — `test_warning_codes.py` reads
`docs/COMPILER.md` to check the warning-text catalogue against the codes the compiler emits, for the
same reason: a catalogue nothing walks is a catalogue that silently omits.
"""

import re
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _FACT_TABLES, _INPUT_FILES, ARTIFACT_PARQUETS
from just_dna_compiler.compiler.tables import _TABLE_KINDS
from just_dna_format import integrity
from just_dna_format.overrides import OVERRIDABLE_TABLES

_DOCS = Path(__file__).resolve().parents[2] / "docs"

#: Spelled-out numbers as the docs write them. Deliberately small and deliberately not a general
#: number parser: the point is to read the words these two files actually use, and a word outside
#: this map should fail loudly as an unreadable claim rather than be silently skipped.
_WORDS: dict[str, int] = {
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty-one": 21,
    "twenty-two": 22,
    "twenty-three": 23,
    "twenty-four": 24,
    "twenty-five": 25,
    "twenty-six": 26,
    "twenty-seven": 27,
    "twenty-eight": 28,
    "twenty-nine": 29,
    "thirty": 30,
}


def _spelled(doc: str, pattern: str) -> int:
    """The number word a doc uses at `pattern`, which must capture exactly one group."""
    matches = re.findall(pattern, doc, re.MULTILINE)
    assert len(matches) == 1, f"{pattern!r} matched {len(matches)} times, expected exactly 1"
    word = matches[0].lower()
    assert word in _WORDS, f"unreadable number word {word!r} — add it to _WORDS or fix the prose"
    return _WORDS[word]


#: Every `*_signature` in `integrity` that hashes ONE derived sidecar. The three excluded are the
#: shared discipline the others are built on, the authored-content identity half, and the Ed25519
#: verify — none of them a per-table fact hash, which is what the roster in SCHEMAS.md enumerates.
_NOT_PER_TABLE = {"fact_signature", "content_signature", "verify_signature"}


def _per_table_signatures() -> set[str]:
    return {name for name in dir(integrity) if name.endswith("_signature")} - _NOT_PER_TABLE


def test_schemas_states_the_sidecar_count_it_says_it_derives() -> None:
    """`SCHEMAS.md` claims the count is `len(_FACT_TABLES)`. Make the claim true."""
    doc = (_DOCS / "SCHEMAS.md").read_text(encoding="utf-8")
    assert _spelled(doc, r"the \*\*(\w+)\*\* derived-fact sidecars") == len(_FACT_TABLES)
    assert _spelled(doc, r"is the one of those (\w+) a human is expected to write") == len(_FACT_TABLES)


def test_the_hash_family_roster_names_every_per_table_signature() -> None:
    """The roster is the part a reader uses, so it is compared as a set rather than counted.

    A missing entry is the real failure mode — a release lands a sidecar, the number gets bumped
    because bumping a number is easy, and the function nobody added to the list stays invisible.
    """
    doc = (_DOCS / "SCHEMAS.md").read_text(encoding="utf-8")
    section = doc.split("**The fact-signature family**")[1].split("**The verification side**")[0]
    # `fact_signature` is named in that section's opening sentence as the shared discipline the
    # others are built on, not as a roster member — so it is dropped here rather than by narrowing
    # the pattern, which would also drop a real entry the day one is introduced mid-sentence.
    listed = set(re.findall(r"`(\w+_signature)`", section)) - {"fact_signature"}
    expected = _per_table_signatures()
    assert listed == expected, f"hash-family roster drifted: {listed ^ expected}"


def test_the_two_spelled_numbers_agree_with_the_roster() -> None:
    """Derived from the roster the test above proved, so these cannot drift independently of it.

    The family is the per-table functions plus the shared `fact_signature`; the complete total adds
    the two identity halves and the three on the verification side, exactly as the § states its own
    rule.
    """
    doc = (_DOCS / "SCHEMAS.md").read_text(encoding="utf-8")
    family = len(_per_table_signatures()) + 1
    assert _spelled(doc, r"fact-signature family is now \*\*(\w+)\*\*") == family
    assert _spelled(doc, r"^(\w+(?:-\w+)?) functions, in three groups") == family + 2 + 3


@pytest.mark.parametrize(
    ("pattern", "expected", "what"),
    [
        (r"(\w+[- ]?\w*) names\. `LEAD_PARQUETS`", lambda: len(ARTIFACT_PARQUETS), "ARTIFACT_PARQUETS"),
        (
            r"applied to the (\w+) covered derived tables",
            lambda: len(OVERRIDABLE_TABLES),
            "OVERRIDABLE_TABLES",
        ),
    ],
)
def test_compiler_doc_counts_match_the_registries(pattern: str, expected, what: str) -> None:
    """`COMPILER.md` spells out two registry sizes. Both are walked here rather than trusted."""
    doc = (_DOCS / "COMPILER.md").read_text(encoding="utf-8")
    assert _spelled(doc, pattern) == expected(), f"{what} moved and COMPILER.md did not"


def test_the_compiler_doc_diagram_is_artifact_parquets_in_order() -> None:
    """**RM365.** The count beside it was pinned and the list was not, so `COMPILER.md` said "Thirty
    names" under a diagram of twenty-six, in a different order, while claiming *"the diagram above is
    the tuple"*. The diagram is what a reader uses, so it is compared as an ordered list — the tuple's
    order is the `artifact.files` listing order, which is what the section says it shows.
    """
    doc = (_DOCS / "COMPILER.md").read_text(encoding="utf-8")
    section = doc.split("**`ARTIFACT_PARQUETS` is the `artifact.files` listing order**", 1)[1]
    fence = section.split("```", 2)[1]
    drawn = [name for line in fence.splitlines() for name in line.split("←", 1)[0].split()]
    expected = [name.removesuffix(".parquet") for name in ARTIFACT_PARQUETS]
    assert drawn == expected, (
        f"COMPILER.md's diagram is not ARTIFACT_PARQUETS: missing {sorted(set(expected) - set(drawn))}, "
        f"extra {sorted(set(drawn) - set(expected))}, or out of order"
    )


def test_the_compiler_doc_input_files_are_input_files() -> None:
    """The same shape one bullet down (RM365): `_INPUT_FILES` was enumerated in prose and lacked the
    two 0.8 authored tables. The named files plus the table kinds (a stated, pinned number) must be
    exactly the tuple."""
    # Whitespace collapsed first: the clause boundary is a phrase, and a rewrap may break it anywhere.
    doc = " ".join((_DOCS / "COMPILER.md").read_text(encoding="utf-8").split())
    bullet = doc.split("- **`_INPUT_FILES`**", 1)[1].split("— the authored surface", 1)[0]
    named = set(re.findall(r"`([\w.]+\.(?:csv|yaml))`", bullet))
    kinds = re.findall(r"the (\d+) table-kind CSVs", bullet)
    assert kinds == [str(len(_TABLE_KINDS))], (
        f"the bullet's table-kind count {kinds} is not {len(_TABLE_KINDS)}"
    )
    stated = named | {csv for csv, _parquet, _model in _TABLE_KINDS}
    assert stated == set(_INPUT_FILES), (
        f"COMPILER.md's _INPUT_FILES drifted: {sorted(stated ^ set(_INPUT_FILES))}"
    )


#: A total of a walked set, in words or digits, directly before the noun a roster counts.
_A_TOTAL = re.compile(
    r"\b(\d+|"
    + "|".join(sorted(_WORDS, key=len, reverse=True))
    + r")\s+(entries|table kinds|binning kinds|vocabularies|parquets|codes)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize(
    ("doc", "anchor"),
    [
        # RM359: "21 entries today" stood here while the generated list had grown past forty.
        ("SCHEMAS.md", '`authoring_reference()["vocabularies"]` is generated from these markers'),
        ("COMPILER.md", "`LEAD_PARQUETS` is the ones carrying"),
    ],
)
def test_a_generated_roster_is_described_by_its_rule_never_its_total(doc: str, anchor: str) -> None:
    """Where a doc describes a list the code generates, the paragraph states the rule and no total.

    These two had a number nothing re-derived, and both went stale (RM359). Dropping the number is the
    repair `@registry-completeness` prefers to pinning it; this keeps it dropped.
    """
    text = (_DOCS / doc).read_text(encoding="utf-8")
    assert text.count(anchor) == 1, f"{anchor!r} moved in {doc}; re-point this test at the sentence"
    before, after = text.split(anchor)
    # The whole paragraph the anchor sits in, not only its tail: a total in the sentence before is the
    # same claim.
    paragraph = before.rsplit("\n\n", 1)[-1] + anchor + after.split("\n\n")[0]
    assert not _A_TOTAL.search(paragraph), (
        f"{doc} states a total beside a generated roster: {paragraph[:200]!r}"
    )
