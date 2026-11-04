"""Every `*_FACT_FIELDS` tuple partitions its model: a column is in the fact set or named outside it.

**RM365.** Each derived table's fact signature hashes a hand-kept tuple of columns, and every one of
those tuples is introduced by a comment of the shape *"everything but the provenance columns"* — a
claim of completeness that nothing walked. Only `CLINICAL_ASSERTION_FACT_FIELDS` had an equality
against its model; the others had spot checks (`"rsid_status" not in …`). So a column added to a fact
model and forgotten in its tuple stays out of the signature silently, with nobody having decided it
should, and a column left out on purpose carries its reason only if somebody wrote one down.

**The exemption list is the comment that already exists, not a second list here.** Every column of
the model is either in the tuple or named, in backticks, in the comment block directly above the
tuple's assignment — the place each module already argues its exclusions (`trait` in `gwas.py`,
`disease_label` in `gene_validity.py`). Measured on `0.8` this found fifteen columns outside their
signatures with no word about them (ten of `resolution.csv`'s cross-references and verdicts, the DOI
half of `literature.csv`'s existence check and its `quote_source`, `rsid` on `consequences.csv`,
`producer` on a verification record), and seven provenance columns referred to only as "the provenance
columns". Each is now named with the reason the maintained docs give, or, where none was ever
recorded, says so.

What this does **not** do is move a column into a fact set: that would change every signature on disk
for that table, which is a corrected derivation a release has to declare (Principle 3), not a test fix.
"""

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import just_dna_format
import pytest
from just_dna_format import integrity, verification
from just_dna_format.reference import _ALL_MODELS


def _fact_field_lists() -> dict[str, tuple[tuple[str, ...], str]]:
    """`{name: (fields, the comment block directly above its assignment)}` for every module-level
    `*_FACT_FIELDS` tuple in the package, found by walking the sources rather than by a list."""
    found: dict[str, tuple[tuple[str, ...], str]] = {}
    for info in pkgutil.walk_packages(just_dna_format.__path__, "just_dna_format."):
        module = importlib.import_module(info.name)
        lines = Path(module.__file__).read_text(encoding="utf-8").splitlines()
        for node in ast.parse("\n".join(lines)).body:
            target = node.target if isinstance(node, ast.AnnAssign) else None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
            if not (isinstance(target, ast.Name) and target.id.endswith("_FACT_FIELDS")):
                continue
            if not isinstance(node.value, ast.Tuple):
                continue
            above: list[str] = []
            index = node.lineno - 2
            while index >= 0 and lines[index].lstrip().startswith("#"):
                above.insert(0, lines[index])
                index -= 1
            found[target.id] = (getattr(module, target.id), "\n".join(above))
    return found


_LISTS = _fact_field_lists()


def _owner(fields: tuple[str, ...]):
    owners = [model for model in _ALL_MODELS.values() if set(fields) <= set(model.model_fields)]
    assert len(owners) == 1, f"{fields} fits {[m.__name__ for m in owners]}, expected exactly one model"
    return owners[0]


def test_the_walk_found_every_list_a_signature_hashes() -> None:
    """The lists walked here are exactly the ones the signatures import — so a signature over a tuple
    defined somewhere this walk does not look cannot leave its table unchecked."""
    used = {
        name
        for source in (integrity, verification)
        for name in re.findall(
            r"\b([A-Z_]+_FACT_FIELDS)\b", Path(source.__file__).read_text(encoding="utf-8")
        )
    }
    assert set(_LISTS) == used, sorted(set(_LISTS) ^ used)


#: A sentence that excludes: the words each module already uses to say a column is not in the set.
_EXCLUDING = re.compile(r"\b(out|outside|excluding|except|everything but|not here)\b", re.IGNORECASE)


def _named_as_outside(comment: str) -> set[str]:
    """Backticked names in the sentences of `comment` that say something is OUT of the set.

    Per sentence, not per comment: "`dataset` is inside" names `dataset` too, and a column a sentence
    calls *inside* must not count as declared outside — or deleting it from the tuple would pass."""
    text = " ".join(line.lstrip().lstrip("#:").strip() for line in comment.splitlines())
    return {
        name
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if _EXCLUDING.search(sentence)
        for name in re.findall(r"`(\w+)`", sentence)
    }


@pytest.mark.parametrize("name", sorted(_LISTS))
def test_every_column_is_in_the_fact_set_or_named_outside_it(name: str) -> None:
    fields, comment = _LISTS[name]
    model = _owner(fields)
    outside = set(model.model_fields) - set(fields)
    named = _named_as_outside(comment)
    unnamed = sorted(outside - named)
    assert not unnamed, (
        f"{model.__name__} has columns outside {name} that no sentence of the comment above it excludes: "
        f"{unnamed}. Either the column is a fact (add it to the tuple — which moves every signature on "
        f"disk, so it is a declared correction) or it is outside on purpose (say why, in that comment)."
    )
    assert len(fields) == len(set(fields)), f"{name} names a column twice"
