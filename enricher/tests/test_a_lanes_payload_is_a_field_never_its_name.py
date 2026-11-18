"""A lane's root-file payload is a field of the lane, never a rule keyed on its name (RM455).

`cache rebuild --publish` and its `--dry-run` rehearsal chose the payload a snapshot is checked and uploaded by
with `STRCHIVE_CATALOGUE_FILENAME if lane.name == "strchive" else None`, twice. A second lane whose payload is a
named root file (`acmg` already is one, unpublished) would have been judged by parquet under `data/` and refused.
`CacheLane.payload_filename` states it, and the two tests below hold it: the field agrees with what each lane's
own resolver finds, and nothing in the enricher compares `lane.name` with a literal.
"""

import ast
from pathlib import Path

import pytest
from just_dna_enricher.caches import CACHE_LANES, CacheLane
from just_dna_enricher.locations import ACMG_SNAPSHOT_FILENAME, RELEASE_FILENAME, STRCHIVE_CATALOGUE_FILENAME

#: Every root-file payload a resolver here finds by name (`locations._resolve_named_cache`).
ROOT_FILES = (ACMG_SNAPSHOT_FILENAME, STRCHIVE_CATALOGUE_FILENAME)

ENRICHER_SRC = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"


@pytest.mark.parametrize("lane", CACHE_LANES, ids=[lane.name for lane in CACHE_LANES])
@pytest.mark.parametrize("payload", ROOT_FILES)
def test_the_field_names_the_root_file_the_lanes_own_resolver_finds(
    lane: CacheLane, payload: str, tmp_path: Path
) -> None:
    snapshot = tmp_path / lane.name
    snapshot.mkdir()
    (snapshot / RELEASE_FILENAME).write_text("{}\n", encoding="utf-8")
    (snapshot / payload).write_text("x\n", encoding="utf-8")
    found = lane.resolve(snapshot, load_dotenv_file=False) is not None
    assert found == (lane.payload_filename == payload)


def test_the_fields_cover_both_root_file_lanes() -> None:
    # The non-vacuous half: the walk above is not passing because no lane states a payload.
    stated = {lane.name: lane.payload_filename for lane in CACHE_LANES if lane.payload_filename is not None}
    assert stated == {"strchive": STRCHIVE_CATALOGUE_FILENAME, "acmg": ACMG_SNAPSHOT_FILENAME}


def _is_lane_name(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "name"
        and isinstance(node.value, ast.Name)
        and node.value.id == "lane"
    )


def _is_str_literal(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_str_literal(element) for element in node.elts)
    return False


def test_no_lane_is_told_apart_by_comparing_its_name_with_a_literal() -> None:
    found = []
    for path in sorted(ENRICHER_SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            if any(_is_lane_name(o) for o in operands) and any(_is_str_literal(o) for o in operands):
                found.append(f"{path.relative_to(ENRICHER_SRC)}:{node.lineno}")
    assert found == [], "a lane's behaviour belongs on a CacheLane field, never on its name: " + ", ".join(
        found
    )
