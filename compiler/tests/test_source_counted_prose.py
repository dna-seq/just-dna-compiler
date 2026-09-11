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
import re
from pathlib import Path

from just_dna_compiler.compiler import ARTIFACT_PARQUETS

_SOURCE_PATH = Path(__file__).resolve().parents[1] / "src" / "just_dna_compiler" / "compiler.py"
_SOURCE = _SOURCE_PATH.read_text(encoding="utf-8")

#: The same map `test_counted_prose.py` uses, for the same reason: a word outside it should fail
#: loudly as an unreadable claim rather than be silently skipped.
_NUMBER_WORDS = (
    r"seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|twenty-one|twenty-two|twenty-three|twenty-four|twenty-five"
)


def _function(name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(_SOURCE)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is gone from compiler.py; this guard needs re-aiming")


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
