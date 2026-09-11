"""One finding, one sentence, one number — even though both sides ask it (RM210).

`_cross_check_literature` runs on **both** sides of the validate/compile pair, and every message it
builds embeds a **count**. `compile_module` de-duplicates the second run on the message string, which
is safe exactly as long as the two runs see the same input. They did not: the pre-flight was handed
`loaded_kinds` (the tables as loaded) and the compile its own `kind_rows` (the tables after
`_apply_symbolic_drops`). `pharm_variants.csv` is in both `_SYMBOLIC_DROPPABLE_TABLES` and the citing
kinds, so a pharm row that cites a PMID *and* carries an unusable symbolic allele is citing to one
side and gone to the other — and the two sentences differ by a number, so both survive a dedup that
compares strings.

Measured before the repair, on a real reference example plus two rows:

    literature.csv describes 1 citation(s) … ['99999999']
    literature.csv describes 2 citation(s) … ['29165669', '99999999']
    warnings_summary: {'literature_row_uncited': 2}

Two contradictory published claims and a count of two for one finding, which is what
`@no-rerun-with-counts` exists to prevent.

**The repair is to make the inputs agree, not to stop re-running.** Re-running a check on both sides is
the normal case here and the rule says so; what is forbidden is re-running one whose message embeds a
count *over different inputs*. The pre-flight already computed `survivors` — the same post-drop view —
three lines earlier for the positional fill, so the fix was to pass the view that already existed.

**Why the guard is shaped as "how many lines", not "which number".** Asserting the correct count would
pass again the day a third caller appears with a fourth view of the tables. One published line per
finding is the property that actually has to hold, and it holds for every message this function
builds — `literature_row_uncited`, `citation_not_in_pubmed` and the quote-counter finding all share
the input and all embedded a count.
"""

import csv
import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "pgx_slco1b1_simvastatin"

#: The PMID the *droppable* row cites — it is cited pre-drop and orphaned post-drop, which is the whole
#: divergence. The other two are a control: one cited by a surviving row, one cited by nobody.
_CITED_BY_DROPPED = "29165669"
_CITED_BY_SURVIVOR = "11111111"
_CITED_BY_NOBODY = "99999999"


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """The PGx example, plus a pharm row that is droppable **and** citing at the same time.

    `pgx_slco1b1_simvastatin` is used because it is the reference example that ships a real
    `pharm_variants.csv`; the two added cells are the minimum that makes one table both symbolic-
    droppable and a citation site.
    """
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)

    path = spec / "pharm_variants.csv"
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    fieldnames = [*rows[0], *(c for c in ("ref", "pmid") if c not in rows[0])]
    for row in rows:
        row.setdefault("ref", "")
        row.setdefault("pmid", "")
    # A surviving row cites something, so the cited set is non-empty on BOTH sides — otherwise
    # `split_cited_literature`'s "cited empty means discard nothing" guard hides the divergence.
    rows[0]["pmid"] = _CITED_BY_SURVIVOR
    dropped = dict(rows[0])
    dropped.update(
        {
            "genotype": "T/T",
            "annotation_id": "9999999001",
            # A symbolic allele in a REF column: unusable, and `pharm_variants.csv` is droppable.
            "ref": "<DEL>",
            "pmid": _CITED_BY_DROPPED,
            "conclusion": "a row that is droppable and citing at once",
        }
    )
    rows.append(dropped)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    (spec / "literature.csv").write_text(
        "pmid,exists,source,status\n"
        + "".join(
            f"{pmid},true,pubmed,resolved\n"
            for pmid in (_CITED_BY_SURVIVOR, _CITED_BY_DROPPED, _CITED_BY_NOBODY)
        ),
        encoding="utf-8",
    )
    return spec


def _uncited_lines(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "citation(s) no study" in w]


def test_the_premise_holds_a_row_really_is_dropped(spec: Path, tmp_path: Path) -> None:
    """Guard the fixture: with nothing dropped the two sides cannot diverge and this file proves nothing."""
    out = tmp_path / "out"
    result = compile_module(spec, out, strict=False)

    assert result.success, result.errors
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compilation"]["dropped_rows"].get("pharm_variants.csv") == 1, manifest["compilation"]


def test_the_finding_is_published_once(spec: Path, tmp_path: Path) -> None:
    """One line and one summary entry, for one finding."""
    result = compile_module(spec, tmp_path / "out", strict=False)

    lines = _uncited_lines(result.warnings)
    assert len(lines) == 1, lines
    assert result.warnings_summary["literature_row_uncited"] == len(lines)


def test_the_published_line_describes_the_artifact_that_was_built(spec: Path, tmp_path: Path) -> None:
    """Of the two sentences, the surviving one must be the **post-drop** one.

    Publishing the pre-drop count would be honest about a module that was never compiled: the dropped
    row is not in the artifact, so the citation it carried really is orphaned there.
    """
    result = compile_module(spec, tmp_path / "out", strict=False)

    (line,) = _uncited_lines(result.warnings)
    assert _CITED_BY_DROPPED in line, line
    assert _CITED_BY_NOBODY in line, line
    assert _CITED_BY_SURVIVOR not in line, line


def test_validate_and_compile_describe_the_same_module(spec: Path, tmp_path: Path) -> None:
    """The parity the shared input buys: the pre-flight's sentence is the one the compile keeps."""
    report = validate_spec(spec, strict=False)
    result = compile_module(spec, tmp_path / "out", strict=False)

    assert _uncited_lines(report.warnings) == _uncited_lines(result.warnings)
