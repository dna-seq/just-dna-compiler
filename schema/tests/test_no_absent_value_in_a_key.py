"""An absent cell is never formatted into an identifier (RM361).

`derive_variant_key` wrote an absent `ref` as the Python literal: nine `variant_key`s in
`reference_examples/cpic_gene_pairs` read `13:48037749:None`, naming a reference base called "None".
`coordinate_key` is now the one place a coordinate becomes a key, and the walk below keeps it so: a
pure colon-joined f-string over formatted values, anywhere in the three packages, is a second key
builder that can stringify an Optional.
"""

import ast
import itertools
from pathlib import Path

import pytest
from just_dna_format.base import coordinate_key, derive_variant_key

_ROOT = Path(__file__).resolve().parents[2]


def _colon_joined_fstrings() -> list[str]:
    """Every f-string made only of three or more formatted values separated by `:` — the shape of a
    coordinate key (`chrom:start:ref`), never a sentence. Two values (`chrom:start`) name a locus in a
    message and are left to the messages."""
    found = []
    for module in sorted(_ROOT.glob("*/src/**/*.py")):
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.JoinedStr) or len(node.values) < 5:
                continue
            values, separators = node.values[0::2], node.values[1::2]
            if all(isinstance(v, ast.FormattedValue) for v in values) and all(
                isinstance(s, ast.Constant) and s.value == ":" for s in separators
            ):
                found.append(f"{module.relative_to(_ROOT)}:{node.lineno}: {ast.unparse(node)}")
    return found


def test_no_second_coordinate_key_builder() -> None:
    assert _colon_joined_fstrings() == []


def test_the_walk_sees_the_shape_it_refuses() -> None:
    """Not vacuous: the pre-RM361 spelling is exactly what the walk matches."""
    node = ast.parse('f"{chrom}:{start}:{ref}"').body[0].value
    values, separators = node.values[0::2], node.values[1::2]
    assert all(isinstance(v, ast.FormattedValue) for v in values)
    assert all(isinstance(s, ast.Constant) and s.value == ":" for s in separators)


_CELLS = {"chrom": ["13", None], "start": [48037749, None], "ref": ["G", None], "alts": ["A", "A,T", None]}


@pytest.mark.parametrize(
    "chrom,start,ref,alts",
    list(itertools.product(*_CELLS.values())),
    ids=lambda v: "-" if v is None else str(v),
)
def test_no_key_carries_the_word_none(chrom, start, ref, alts) -> None:
    """Every combination of present and absent cells, through both entry points."""
    for key in (coordinate_key(chrom, start, ref, alts), derive_variant_key(None, chrom, start, ref, alts)):
        assert "None" not in key


def test_a_row_naming_nothing_keys_as_the_empty_string() -> None:
    assert coordinate_key(None, None, None) == "" == derive_variant_key(None, None, None, None)


def test_an_absent_ref_cannot_collide_with_a_present_one() -> None:
    assert coordinate_key("13", 48037749, None) == "13:48037749"
    assert coordinate_key("13", 48037749, None, "A") == "13:48037749::A"
    assert coordinate_key("13", 48037749, None, "A") != coordinate_key("13", 48037749, "A")
