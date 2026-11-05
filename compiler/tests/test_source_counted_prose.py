"""Counted prose in the SOURCE, which `test_counted_prose.py` does not reach (RM218).

That file enforces the rule for `docs/` and says why: prose is not walked by anything, so a number
beside a registry goes stale and the drift is found by a reader who happens to care. Its `_DOCS`
constant scopes it to the documentation tree — and the same class was live in `compiler.py` itself:

| claim | where | measured |
| --- | --- | --- |
| "up to twelve in all" | the module docstring | 23 (`len(ARTIFACT_PARQUETS)`) |
| "There are six reasons … a reader needs the six" | `_vrs_gap_reason` | **8** return arms |

`_vrs_gap_reason` is the instructive one. RM5 added the symbolic class and RM59 the unobservable
class, each correctly, and neither moved the number two paragraphs up — which is exactly how the
sidecar count went stale twice in `SCHEMAS.md` before a test was put on it.

**The guard's first catch was the repair's own prose**, which is worth keeping. The replacement
docstring quoted the stale phrase verbatim while explaining it — and a stale figure in quotation marks
two lines below the rule reads to a skimming reader exactly like the rule. The explanation names the
shape now instead of reproducing it.

**The repair is not a third re-count.** Both sentences now state the rule rather than a figure, and
what is asserted here is the property the rule was standing in for. For the parquets that is "the
docstring names the constant"; for the reasons it is `@answered-is-not-absent`'s real requirement —
a verdict function with several arms owes a reason function with the same arms, **pairwise
distinct** — which a number never checked in the first place.
"""

import ast
import importlib
import re
import typing
from pathlib import Path

from just_dna_compiler.compiler import ARTIFACT_PARQUETS

#: The `compiler` package, which was one `compiler.py` until RM260 split it. The module docstring is the
#: package's (`__init__.py`), and a function is looked up across every submodule, so the guard follows a
#: symbol wherever the split put it rather than breaking the day it moves again.
_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "just_dna_compiler" / "compiler"
_SOURCE = (_PACKAGE / "__init__.py").read_text(encoding="utf-8")
_MODULES = [ast.parse(path.read_text(encoding="utf-8")) for path in sorted(_PACKAGE.glob("*.py"))]

#: The same map `test_counted_prose.py` uses, for the same reason: a word outside it should fail
#: loudly as an unreadable claim rather than be silently skipped.
_NUMBER_WORDS = (
    r"seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|twenty-one|twenty-two|twenty-three|twenty-four|twenty-five"
)


def _function(name: str) -> ast.FunctionDef:
    for module in _MODULES:
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
    raise AssertionError(f"{name} is gone from the compiler package; this guard needs re-aiming")


def test_the_module_docstring_names_the_registry_rather_than_a_number() -> None:
    """A count in the file's own opening paragraph is the one a new reader trusts first."""
    docstring = ast.get_docstring(ast.parse(_SOURCE)) or ""

    assert "ARTIFACT_PARQUETS" in docstring, docstring[:400]
    spelled = re.findall(rf"\b({_NUMBER_WORDS})\b in all", docstring, re.IGNORECASE)
    assert not spelled, f"the parquet count is spelled out again: {spelled}"


def test_the_roster_is_still_the_thing_the_docstring_points_at() -> None:
    """Guard the premise: a pointer to a constant that has gone is worse than a stale number."""
    assert len(ARTIFACT_PARQUETS) == len(set(ARTIFACT_PARQUETS)) > 1
    assert all(name.endswith(".parquet") for name in ARTIFACT_PARQUETS)


def test_the_gap_reason_docstring_states_no_arm_count() -> None:
    """It said "six" while the function had eight, twice over two releases."""
    docstring = ast.get_docstring(_function("_vrs_gap_reason")) or ""

    spelled = re.findall(rf"\b({_NUMBER_WORDS})\b\s+reasons?", docstring, re.IGNORECASE)
    assert not spelled, f"the arm count is spelled out again: {spelled}"


def test_every_gap_reason_arm_is_distinct() -> None:
    """The property the number was standing in for, and the one `@answered-is-not-absent` asks for.

    A reason function whose arms collapse tells a reader two different situations are one, which is
    the failure a count could never have caught — eight arms returning six distinct strings would
    have satisfied the old sentence exactly.
    """
    node = _function("_vrs_gap_reason")
    literals = [
        ast.literal_eval(ret.value)
        for ret in ast.walk(node)
        if isinstance(ret, ast.Return)
        and isinstance(ret.value, ast.Constant)
        and isinstance(ret.value.value, str)
    ]
    assert len(literals) >= 4, literals
    assert len(set(literals)) == len(literals), sorted(literals)


# ── RM392: the same class across all three packages, at every registry ────────────────────────────
#
# The two guards above are aimed at two named sites. The audit's second round found the class live at
# registries nobody had aimed a test at: `OVERRIDABLE_TABLES` opened with "**Nine, and the number is a
# decision rather than a count**" over twelve entries, `VALID_CAID_OUTCOME` with "**Three**" over five
# and `VALID_RECOVERY_OUTCOME` with "**Four**" over five — each written correctly, each left behind
# when `skipped_offline` or a sidecar joined the literal under it. So this walks every module-level
# registry in the workspace and reads the comment block directly above it.
#
# **Equality, not absence.** `test_integration_doc_states_no_registry_count.py` forbids the shape in a
# document a consumer reads once; here a comment sits on the literal it counts, and many state a
# correct, load-bearing total ("the three states a lane can be in"). Rewriting every one of those to
# satisfy a ban is the smaller defect traded for a larger diff, so a stated total must EQUAL the
# registry. What makes it walkable is that a total is recognised in two shapes only, both bound to the
# registry's own name rather than to proximity — the proximity draft of RM223's guard failed on five
# legitimate sentences, and the same draft here flagged ~50 sub-counts ("two members from …"):
#
# * the headline idiom, a bold number opening a sentence: `**Nine, and …`, `**Three readings`;
# * a number directly before the registry's own noun — the last word of its name — with only other
#   words of its name between: "the three states" over `LANE_STATES`, "ten ancestry groups" over
#   `RECOMMENDED_ANCESTRY_GROUPS`. "two snapshot witnesses" over `PLACEMENT_WITNESSES` is a sub-count,
#   and `snapshot` is not in the name, so it is not read as a total.
#
# A mapping holds two sets, its keys and its values, and its noun may name either: `SNP_CORE_PARQUETS`
# is keyed by CSV and its "three core parquets" are the values. Both sizes are accepted.

_WORKSPACE = Path(__file__).resolve().parents[2]
_PACKAGE_ROOTS = (
    _WORKSPACE / "schema" / "src",
    _WORKSPACE / "compiler" / "src",
    _WORKSPACE / "enricher" / "src",
)
_UNITS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_TENS = (
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
)
_VALUES = {word: n for n, word in enumerate(_UNITS, 1)} | dict(
    zip(_TENS, (*range(10, 21), 30, 40), strict=True)
)
#: "one" is never a total: every registry walked here holds more than one member, and "one code per
#: remediation" or "**One** sentence per arm" is a statement about a member. It stays a unit of a
#: compound ("twenty-one").
_NUMBER = r"(\d+|(?:" + "|".join((*_TENS, *_UNITS[1:])) + r")(?:-(?:" + "|".join(_UNITS) + r"))?)"


def _value(token: str) -> int:
    token = token.lower()
    if token.isdigit():
        return int(token)
    tens, _, unit = token.partition("-")
    return _VALUES[tens] + (_VALUES[unit] if unit else 0)


def _total_claims(text: str, name: str) -> list[tuple[str, int]]:
    """Every phrase in `text` that states the size of the registry called `name`, with its number."""
    words = [word for word in name.strip("_").lower().split("_") if word]
    stem = words[-1].removesuffix("es") if words[-1].endswith("ses") else words[-1].removesuffix("s")
    noun = rf"(?:{re.escape(stem)}(?:s|es)?)"
    between = "|".join(re.escape(word) for word in words)
    shapes = (
        rf"\*\*{_NUMBER}(?=[,\s])",
        rf"(?<![\w.\-]){_NUMBER}\s+(?:(?:{between})\s+){{0,2}}{noun}\b",
    )
    return [
        (hit.group(0), _value(hit.group(1)))
        for shape in shapes
        for hit in re.finditer(shape, text, re.IGNORECASE)
    ]


def _sizes(registry: object) -> set[int]:
    """The sizes a stated total of `registry` may honestly name."""
    sizes = {len(registry)}  # type: ignore[arg-type]
    if isinstance(registry, dict):
        values: list[object] = []
        for value in registry.values():
            values.extend(value if isinstance(value, (tuple, list, frozenset, set)) else [value])
        if all(isinstance(value, typing.Hashable) for value in values):
            sizes.add(len(set(values)))
    return sizes


def _registry_comment_blocks() -> list[tuple[str, str, object, str]]:
    """`(where, name, registry, comment)` for every module-level sized registry with a comment above it."""
    found: list[tuple[str, str, object, str]] = []
    for root in _PACKAGE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            module_name = ".".join(path.relative_to(root).with_suffix("").parts).removesuffix(".__init__")
            module = None
            for node in ast.parse("\n".join(lines)).body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target = node.targets[0]
                elif isinstance(node, ast.AnnAssign):
                    target = node.target
                else:
                    continue
                if not isinstance(target, ast.Name) or not target.id.strip("_").isupper():
                    continue
                block: list[str] = []
                index = node.lineno - 2
                while index >= 0 and lines[index].lstrip().startswith("#"):
                    block.insert(0, lines[index].lstrip().lstrip("#:").strip())
                    index -= 1
                if not block:
                    continue
                module = module or importlib.import_module(module_name)
                registry = getattr(module, target.id)
                if isinstance(registry, (tuple, list, dict, frozenset, set)) and len(registry) > 1:
                    where = f"{path.relative_to(_WORKSPACE)}:{node.lineno}"
                    found.append((where, target.id, registry, " ".join(block)))
    return found


_BLOCKS = _registry_comment_blocks()


def test_the_walk_reaches_the_registries_it_was_written_for() -> None:
    """The floor, so a broken walk cannot pass by reading nothing."""
    walked = {name for _where, name, _registry, _comment in _BLOCKS}
    assert {"OVERRIDABLE_TABLES", "VALID_CAID_OUTCOME", "VALID_RECOVERY_OUTCOME", "LANE_STATES"} <= walked


def test_a_total_stated_above_a_registry_is_its_size() -> None:
    """Every total a registry's own comment states, against the registry it sits on."""
    wrong = [
        f"{where} {name} (size {sorted(_sizes(registry))}): {phrase!r} says {stated}"
        for where, name, registry, comment in _BLOCKS
        for phrase, stated in _total_claims(comment, name)
        if stated not in _sizes(registry)
    ]
    assert not wrong, (
        "a comment states a registry's size and the registry has moved (RM392). Name the registry or "
        "its rule instead of a number, or correct it:\n" + "\n".join(f"  - {line}" for line in wrong)
    )


def test_the_guard_reads_the_sentences_it_was_written_for() -> None:
    """The reach, pinned on the pre-RM392 text rather than invented examples."""
    assert _total_claims("**Nine, and the number is a decision rather than a count**", "OVERRIDABLE_TABLES")
    assert _total_claims("What one lookup concluded. **Three, and the third", "VALID_CAID_OUTCOME")
    assert _total_claims("Seeded with gnomAD v4's ten ancestry groups", "RECOMMENDED_ANCESTRY_GROUPS")
    assert _total_claims("The three states a lane can be in", "LANE_STATES") == [("three states", 3)]


def test_the_guard_leaves_a_sub_count_alone() -> None:
    """The other direction: a number about something else is not a total of the registry."""
    assert not _total_claims("the two snapshot witnesses", "PLACEMENT_WITNESSES")
    assert not _total_claims("It borrows two members from the resolution table", "VALID_FREQUENCY_STATUS")
    assert not _total_claims("The 0.4 table kinds that can name a locus", "_POSITIONAL_TABLE_KINDS")
    assert not _total_claims("**0.7** added a member", "VALID_SOURCE_LAYERS")
