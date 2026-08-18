"""No `except` arm in this package is shadowed by an earlier one in the same `try` (S38).

RM101 gave every raising pass an unavailability **subclass**, which is what keeps `except <Pass>Error`
catching everything it did (P3). It also created a hazard that did not exist while the two types were
unrelated: once `FrequencyUnavailable` is a `FrequencyEnrichmentError`, a handler that lists the parent
first swallows the child, and the narrower arm below it is dead code. Python takes the first matching
clause, so the ordering that used to be arbitrary is now load-bearing.

just-dna-registry hit exactly this upgrading to 0.6.2 (S38): two separate arms, parent first, and the
outage arm went dead. Nothing raised and nothing 500'd — their endpoint reported a clean check while
gnomAD was down, which is the failure RM101 exists to end, reintroduced by the fix for it. That is the
argument for a structural guard rather than a review habit: the defect is invisible at every level
except the shape of the code.

**It walks the package rather than a list** (`@registry-completeness`), and it walks *ours*. We cannot
fix a consumer's handler ordering, but shipping the shape ourselves — in a tier that now carries seven
subclass pairs — would be the same defect one layer down.

**One documented limit.** Only `ast.Name` clause types are resolved, so `except httpx.HTTPError` is not
compared against anything. The hazard S38 names is a same-module pair of our own types, both written as
bare names, and resolving dotted types would mean importing every module under test to ask about its
attributes. A `<bare>` `except:` shadows everything after it and is caught.
"""

from __future__ import annotations

import ast
from pathlib import Path

# The package roots, not their `src/` subtrees: tests are code we ship the shape in too, and the
# measurement this guard's zero is quoted from (S38's reply, the CHANGELOG) walked the wider set.
_PACKAGES = [
    Path(__file__).resolve().parents[2] / pkg
    for pkg in ("schema", "compiler", "enricher")
]

# Builtins we care about as ancestors; anything else unknown simply resolves to no parents, which
# makes the walk silent rather than wrong.
_BUILTIN_BASES = {
    "Exception": ["BaseException"],
    "RuntimeError": ["Exception"],
    "ValueError": ["Exception"],
    "TypeError": ["Exception"],
    "KeyError": ["Exception"],
    "OSError": ["Exception"],
}


def _class_bases(trees: dict[Path, ast.Module]) -> dict[str, list[str]]:
    """Every class declared in the walked sources, mapped to its directly named bases."""
    bases: dict[str, list[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases[node.name] = [b.id for b in node.bases if isinstance(b, ast.Name)]
    return bases


def _ancestors(name: str, bases: dict[str, list[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(bases.get(name, _BUILTIN_BASES.get(name, [])))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(bases.get(current, _BUILTIN_BASES.get(current, [])))
    return seen


def _handler_names(handler: ast.ExceptHandler) -> list[str]:
    clause = handler.type
    if clause is None:
        return ["<bare>"]
    if isinstance(clause, ast.Name):
        return [clause.id]
    if isinstance(clause, ast.Tuple):
        return [e.id for e in clause.elts if isinstance(e, ast.Name)]
    return []


def _shadowed(trees: dict[Path, ast.Module], bases: dict[str, list[str]]) -> list[str]:
    """Arms unreachable because an earlier arm in the same `try` already catches them.

    Comparison is across handlers only. Naming a parent and its child inside one tuple is redundant
    but harmless — both go to the same block — and flagging it would make the guard cry wolf.
    """
    findings: list[str] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            earlier: list[tuple[str, int]] = []
            for handler in node.handlers:
                current = _handler_names(handler)
                for name in current:
                    for previous, line in earlier:
                        if previous == "<bare>" or previous in _ancestors(name, bases):
                            findings.append(
                                f"{path.name}:{handler.lineno} except {name} is unreachable — "
                                f"{previous} at line {line} already catches it"
                            )
                earlier.extend((name, handler.lineno) for name in current)
    return findings


def _parse(paths: list[Path]) -> dict[Path, ast.Module]:
    return {p: ast.parse(p.read_text()) for root in paths for p in sorted(root.rglob("*.py"))}


def test_no_handler_in_the_workspace_is_shadowed_by_an_earlier_arm() -> None:
    trees = _parse(_PACKAGES)
    assert trees, "walked no sources at all — the package layout moved"
    findings = _shadowed(trees, _class_bases(trees))
    assert not findings, "shadowed except arms:\n  " + "\n  ".join(findings)


def test_the_walk_detects_the_shape_it_is_written_for() -> None:
    """The zero above is only worth having if this walk can fail (`@tautology-zero`).

    The snippet is S38's, reduced: the reporter's two arms in their reported order, over the real
    subclass relationship RM101 introduced.
    """
    buggy = ast.parse(
        "class FrequencyEnrichmentError(RuntimeError): pass\n"
        "class FrequencyUnavailable(FrequencyEnrichmentError): pass\n"
        "def run():\n"
        "    try:\n"
        "        pass\n"
        "    except FrequencyEnrichmentError as exc:\n"
        "        return exc\n"
        "    except FrequencyUnavailable as exc:\n"
        "        return exc\n"
    )
    trees = {Path("reported.py"): buggy}
    findings = _shadowed(trees, _class_bases(trees))
    assert len(findings) == 1, findings
    assert "except FrequencyUnavailable is unreachable" in findings[0]

    fixed = ast.parse(
        "class FrequencyEnrichmentError(RuntimeError): pass\n"
        "class FrequencyUnavailable(FrequencyEnrichmentError): pass\n"
        "def run():\n"
        "    try:\n"
        "        pass\n"
        "    except FrequencyUnavailable as exc:\n"
        "        return exc\n"
        "    except FrequencyEnrichmentError as exc:\n"
        "        return exc\n"
    )
    trees = {Path("repaired.py"): fixed}
    assert not _shadowed(trees, _class_bases(trees))


def test_a_parent_and_child_in_one_tuple_is_not_a_finding() -> None:
    """The false positive that would have made the guard unusable.

    `except (FrequencyEnrichmentError, FrequencyUnavailable)` is redundant, not dead: both names route
    to the same block. A guard that reports it is one somebody deletes.
    """
    tupled = ast.parse(
        "class FrequencyEnrichmentError(RuntimeError): pass\n"
        "class FrequencyUnavailable(FrequencyEnrichmentError): pass\n"
        "def run():\n"
        "    try:\n"
        "        pass\n"
        "    except (FrequencyEnrichmentError, FrequencyUnavailable) as exc:\n"
        "        return exc\n"
    )
    trees = {Path("tupled.py"): tupled}
    assert not _shadowed(trees, _class_bases(trees))


def test_a_bare_except_shadows_what_follows_it() -> None:
    bare = ast.parse(
        "class FrequencyEnrichmentError(RuntimeError): pass\n"
        "def run():\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
        "    except FrequencyEnrichmentError:\n"
        "        pass\n"
    )
    trees = {Path("bare.py"): bare}
    findings = _shadowed(trees, _class_bases(trees))
    assert len(findings) == 1 and "<bare>" in findings[0]
