"""`SCHEMAS.md`'s module map names every module in the package, and names each one once.

**A map is a registry, and a hand-kept registry loses entries silently** (`@registry-completeness`).
The map is the first thing a reader of this package opens — it is how somebody who does not yet know
where `ExpressionEffectRow` lives finds `expression.py` — so a module missing from it is invisible in
exactly the situation the map exists for. Eight were missing when this test was written: `layout`,
`findings`, `verification` and the five derived-fact row models added between 0.6 and 0.7
(`gene_validity`, `assertions`, `gwas`, `concordance`, `expression`). Every one of them is documented
elsewhere in `SCHEMAS.md`; none of them was reachable from the map.

That is the failure shape to expect, and it is why the assertion is an **equality over a walked set**
rather than a floor: a release adds a module, its own § gets written because that is the interesting
part, and the row nobody added to the table stays missing until a reader happens to count. Nothing
walks prose, so prose is what goes stale — the same argument `test_counted_prose.py` makes about the
numbers one document over, and `test_doc_links.py` beside this file makes about the links.

**Why equality is legal here** where the enricher's check table only gets `⊆`: the map's rule is
one row per module, both directions. A module with no row is unreachable, and a row naming no module
sends a reader to a file that is not there. Duplicates are caught by comparing lengths as well as
sets — `ENRICHER.md` carried two `clinvar_build` rows, which a set comparison reads as fine.

The walk is every top-level `*.py` in the package except `__init__.py`. Subpackages are excluded by
the glob rather than by name, so a future one is a deliberate decision about what the map covers and
not a silent omission.
"""

import re
from pathlib import Path

import just_dna_format

_PACKAGE = Path(just_dna_format.__file__).resolve().parent
_MAP = Path(__file__).resolve().parents[2] / "docs" / "SCHEMAS.md"


def _mapped_modules() -> list[str]:
    """The first cell of every row of the module map, in document order, duplicates kept."""
    doc = _MAP.read_text(encoding="utf-8")
    section = doc.split("## Module map")[1].split("\n## ")[0]
    return re.findall(r"^\| `(\w+)` \|", section, re.MULTILINE)


def _package_modules() -> set[str]:
    return {p.stem for p in _PACKAGE.glob("*.py")} - {"__init__"}


def test_the_map_names_every_module_and_only_modules() -> None:
    listed = set(_mapped_modules())
    present = _package_modules()
    assert listed == present, f"module map drifted: {listed ^ present}"


def test_no_module_is_mapped_twice() -> None:
    """A duplicated row is two claims about one file, and a set comparison cannot see it."""
    rows = _mapped_modules()
    assert len(rows) == len(set(rows)), f"duplicated rows: {sorted({r for r in rows if rows.count(r) > 1})}"
