"""RM465. Enricher readers hand snapshot part counts to the format predicate."""

import ast
from pathlib import Path

import just_dna_enricher
import pytest

_FIELDS = {"parts_read", "parts_total"}


def _independent_reads(source: str) -> list[int]:
    tree = ast.parse(source)
    ignored: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            # Constructing a record writes its field names.
            ignored.update(key for key in node.keys if isinstance(key, ast.Constant))
        if isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name)
            and node.func.id == "is_whole_build"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "is_whole_build"
        ):
            for arg in [*node.args, *(kw.value for kw in node.keywords)]:
                if not any(isinstance(child, ast.Compare) for child in ast.walk(arg)):
                    ignored.update(ast.walk(arg))

    # Field declarations and constructor keywords write counts. Attribute loads and literal
    # keys also catch a reader unpacking a map to compare the numbers several lines later.
    return [
        node.lineno
        for node in ast.walk(tree)
        if node not in ignored
        and (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and node.attr in _FIELDS
            or isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in _FIELDS
            or isinstance(node, ast.Constant)
            and node.value in _FIELDS
        )
    ]


def test_every_enricher_part_count_reader_uses_the_predicate() -> None:
    root = Path(just_dna_enricher.__file__).resolve().parent
    modules = sorted(root.rglob("*.py"))
    assert root / "opentargets.py" in modules
    assert {
        str(path.relative_to(root)): lines
        for path in modules
        if (lines := _independent_reads(path.read_text(encoding="utf-8")))
    } == {}


@pytest.mark.parametrize(
    "comparison",
    [
        "return record.parts_read[name] >= record.parts_total[name]",
        'read = record.get("parts_read")\n    return read[name] < record["parts_total"][name]',
        "return parts_read[name] == parts_total[name]",
    ],
)
def test_the_walk_catches_a_comparison_beside_a_predicate_call(comparison: str) -> None:
    assert _independent_reads(
        f"def check(record, name, parts_read, parts_total):\n    is_whole_build(record)\n    {comparison}"
    )
