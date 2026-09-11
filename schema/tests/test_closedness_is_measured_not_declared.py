"""A vocabulary's `closed` flag must match what its validator actually does (RM225).

`actionability` has now had its closedness mis-stated in **three** places, each written by somebody
reading the one before it:

1. `reference.py` filed the axis under `open_recommended` while `VariantRow` rejected a non-member.
   That one was caught and fixed, and `reference.py` still carries the incident note.
2. `vocab.py`'s comment above the set said "the field is not built yet, so this is not enforced" —
   untrue from the moment `VariantRow.actionability` shipped in 0.4.0.
3. `base.vocabulary`'s own docstring listed the set among the `closed=False` "recommended-but-open"
   ones — inside the helper that *defines* what `closed` means.

The constant's name carried it too: `ACTIONABILITY_SEED` reads as "suggestions you may extend", which
is exactly what the validator refuses. It is now `VALID_ACTIONABILITY` with the old name kept as a
working alias (P3).

**Closedness is the property a consumer acts on** — "pick one of these" versus "these are
suggestions" — so a marker that lies about it is worse than no marker. Fixing the three sentences
fixes the instances; this file is the class. It **measures** each field's closedness by handing its
validator a value that is certainly not a member and seeing whether it is refused, then compares that
against the `closed` flag the marker publishes. Nothing here reads a comment, a name, or a document.
"""

import importlib
import inspect
import pkgutil

import just_dna_format
import pytest
from just_dna_format import base, vocab
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import ACTIONABILITY_SEED, VALID_ACTIONABILITY
from pydantic import BaseModel

#: A value no real vocabulary contains. If a set ever legitimately holds this, the probe is wrong and
#: the resulting failure is the right outcome — it is unreadable, not silently passed over.
_CERTAINLY_NOT_A_MEMBER = "zzz-not-a-member-zzz"


def _marked_fields() -> list[tuple[type[BaseModel], str, dict]]:
    """Every field carrying a `vocabulary` marker, with the marker."""
    found: list[tuple[type[BaseModel], str, dict]] = []
    seen: set[type[BaseModel]] = set()
    for info in pkgutil.iter_modules(just_dna_format.__path__):
        module = importlib.import_module(f"just_dna_format.{info.name}")
        for obj in vars(module).values():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj.__module__ == module.__name__
                and obj not in seen
            ):
                seen.add(obj)
                for name, field in obj.model_fields.items():
                    extra = field.json_schema_extra
                    if isinstance(extra, dict) and isinstance(extra.get("vocabulary"), dict):
                        found.append((obj, name, extra["vocabulary"]))
    return found


def _refuses(model: type[BaseModel], name: str, value: str) -> bool:
    """Does this field's validator reject `value`?"""
    try:
        for validator in model.__pydantic_decorators__.field_validators.values():
            if name in validator.info.fields:
                func = validator.func
                (func.__func__ if hasattr(func, "__func__") else func)(model, value)
        return False
    except Exception:
        return True


def test_there_are_marked_vocabularies_to_check() -> None:
    """The floor. A marker rename would otherwise make every assertion below vacuous."""
    assert len(_marked_fields()) >= 10


@pytest.mark.parametrize("closed_flag", [True, False])
def test_the_closed_flag_matches_what_the_validator_does(closed_flag: bool) -> None:
    """The class, not the instance: measured closedness must equal published closedness.

    Split by flag so a failure names which direction drifted — a set claiming to be open while its
    validator refuses (the `actionability` case, three times over) reads differently from one
    claiming to be closed while anything passes.
    """
    mismatched = []
    for model, name, marker in _marked_fields():
        if bool(marker.get("closed")) is not closed_flag:
            continue
        if _refuses(model, name, _CERTAINLY_NOT_A_MEMBER) is not closed_flag:
            mismatched.append(f"{model.__name__}.{name}")

    assert not mismatched, (
        f"these fields publish closed={closed_flag} and their validators disagree: {sorted(mismatched)}. "
        "Closedness is what a consumer acts on, so the marker and the validator may not drift "
        "(RM225 — `actionability` had this wrong in three separate places)."
    )


def test_actionability_is_closed_and_says_so() -> None:
    """The specific case, pinned, because it is the one that kept coming back."""
    marker = VariantRow.model_fields["actionability"].json_schema_extra["vocabulary"]
    assert marker["closed"] is True
    assert _refuses(VariantRow, "actionability", _CERTAINLY_NOT_A_MEMBER)


def test_the_old_constant_name_still_resolves() -> None:
    """P3: anything superseded is kept as a working derived alias, not deleted inside the major."""
    assert ACTIONABILITY_SEED is VALID_ACTIONABILITY
    assert "actionable" in ACTIONABILITY_SEED


def test_no_comment_in_vocab_asserts_actionability_is_unenforced() -> None:
    """The sentence itself, since a comment is what misled a reader twice.

    **This test failed on its own author's first run**, exactly as RM218's did: the replacement
    comment explains the defect by quoting the stale claim verbatim, so a bare substring check
    flagged the fix as the bug. That is the second time a prose guard has caught the prose written to
    satisfy it, and the lesson both times is the same — write the guard before the replacement text.

    So the rule is not "this string is absent" but "no occurrence *asserts* it": a mention wrapped in
    `used to say "…"` is the document describing its own history, which is what the repository asks
    for, while a bare one is the claim coming back.
    """
    source = inspect.getsource(vocab)

    stale = "the field is not built yet"
    for index, line in enumerate(source.splitlines(), start=1):
        if stale not in line:
            continue
        assert "used to say" in line, (
            f"vocab.py:{index} states the stale claim rather than quoting it as history: {line.strip()!r}"
        )


def test_the_sets_the_vocabulary_helper_calls_open_are_open() -> None:
    """Instance #3, which is the one nothing could have caught: prose inside the defining helper.

    `base.vocabulary`'s docstring names the "recommended-but-open" sets by constant, and it listed
    `ACTIONABILITY_SEED` among them — a closed set, named as open, in the docstring of the function
    that defines what `closed` means. The marker was right the whole time and every tool reads the
    marker, so nothing failed; a person reading the docstring was the one misled.

    This walks the names out of that docstring and measures each one, so the sentence cannot name a
    closed set again. It is deliberately tolerant about *which* names appear — adding a genuinely
    open set to the prose is fine — and strict about what they must be.
    """
    doc = inspect.getdoc(base.vocabulary) or ""
    opening = doc.index("recommended-but-open sets (")
    listed = doc[opening + len("recommended-but-open sets (") : doc.index(")", opening)]
    names = [n.strip().strip("`") for n in listed.replace("\n", " ").split(",") if n.strip()]

    assert names, f"no constants parsed out of the docstring; the sentence moved: {listed!r}"

    wrongly_called_open = []
    for name in names:
        members = getattr(vocab, name, None)
        if members is None:
            continue
        for model, field, marker in _marked_fields():
            if set(marker.get("options", ())) == set(members) and marker.get("closed"):
                wrongly_called_open.append(f"{name} (closed on {model.__name__}.{field})")

    assert not wrongly_called_open, (
        f"`base.vocabulary`'s docstring calls these open and they are closed: {wrongly_called_open}. "
        "That is RM225's third instance — the drift written into the docstring that defines the flag."
    )
