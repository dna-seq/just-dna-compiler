"""The two refusals the injected table itself raises, asked on both sides and keyed on the right key.

**Two defects, one root** (RM207). `resolve_from_table` walked `patched` — the post-expansion rows —
and looked each one's `variant_key` up in a table keyed by the key the *author* wrote. For a row the
fill merely completes those are the same string and the check worked. For a row the table expands they
are not: the expansion rewrites `variant_key` to the locus's `ga4gh:VA.…` id, so the lookup missed and
the refusal its own comment calls "fatal in BOTH modes" never fired. A module carrying a withdrawn
rsID on an expanded variant compiled clean.

And the check lived only inside `resolve_from_table`, which only `compile_module` calls — so on the
rows where it *did* fire, `validate` reported the spec valid in both modes and a plain `compile`
refused it. That is the sequence `@validate-refuses-all` exists to stop, and the standing exemption
does not cover it: the check reads the injected table's own columns, needs no `output_dir`, no
reference and no *resolved* row, which is the exact test the pre-flight applies when deciding what it
owes (`unresolved_subjects` beside it was factored out for the same reason, S76).

**Both are measured against a real reference example with one column changed**, not a hand-built spec.
`hfe_hemochromatosis` is used because it ships a real `resolution.csv` the enricher wrote — including
one rsID-keyed row, which is what makes the expansion case constructible without inventing a table.
The expected values are computed from the fixture at runtime; nothing here is a count read off a dump.

The ambiguous arm rides along because it is the same loop and the same key bug, one severity down:
`strict`-only, so `validate --strict` is where it has to appear.
"""

import csv
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)
    return spec


def _rows(spec: Path) -> list[dict[str, str]]:
    with (spec / "resolution.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(spec: Path, rows: list[dict[str, str]]) -> None:
    with (spec / "resolution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mark(spec: Path, column: str, value: str) -> str:
    """Set `column` to `value` on the fixture's first resolution row; return the key it is under."""
    rows = _rows(spec)
    rows[0][column] = value
    _write(spec, rows)
    return rows[0]["variant_key"]


def _expand_with(spec: Path, column: str, value: str) -> str:
    """Give the one rsID-keyed row a second usable locus carrying `column=value`.

    Two loci under one authored key is what makes `resolve_from_table` *expand*, which is what
    rewrites `variant_key` — so this is the shape the lookup used to miss. The key returned is the
    authored one, which is what the table is keyed by and therefore what the message names.
    """
    rows = _rows(spec)
    rsid_keyed = next(r for r in rows if r["variant_key"].startswith("rs"))
    second = dict(rsid_keyed)
    second["start"] = str(int(rsid_keyed["start"]) + 4)
    second["locus_index"] = "1"
    second["vrs_id"] = ""
    second[column] = value
    _write(spec, [*rows, second])
    return rsid_keyed["variant_key"]


def _findings(spec: Path, tmp_path: Path, *, strict: bool) -> tuple[list[str], list[str]]:
    """`(validate errors, compile errors)` for one spec, at one mode."""
    report = validate_spec(spec, strict=strict)
    result = compile_module(spec, tmp_path / f"out-{strict}", strict=strict)
    return list(report.errors), list(result.errors)


@pytest.mark.parametrize("strict", [False, True])
def test_a_withdrawn_rsid_refuses_at_validate_in_both_modes(tmp_path: Path, strict: bool) -> None:
    """The fatal-in-both-modes refusal, on a row the fill merely completes."""
    spec = _spec(tmp_path)
    key = _mark(spec, "rsid_status", "withdrawn")

    validate_errors, compile_errors = _findings(spec, tmp_path, strict=strict)

    assert [e for e in validate_errors if "WITHDRAWN" in e], validate_errors
    assert all(e.startswith(f"resolution: {key}:") for e in validate_errors if "WITHDRAWN" in e)
    # The parity rule as an equality rather than "validate also said something": a green pre-flight
    # is the defect, and so is a pre-flight that refuses for a different reason than the compile.
    assert set(validate_errors) == set(compile_errors)


@pytest.mark.parametrize("strict", [False, True])
def test_the_refusal_survives_the_row_being_expanded(tmp_path: Path, strict: bool) -> None:
    """The half that used to compile clean: the expansion rewrites the key the lookup used."""
    spec = _spec(tmp_path)
    authored_key = _expand_with(spec, "rsid_status", "withdrawn")

    validate_errors, compile_errors = _findings(spec, tmp_path, strict=strict)

    withdrawn = [e for e in validate_errors if "WITHDRAWN" in e]
    assert withdrawn, "an expanded row's withdrawn locus is invisible again"
    # The AUTHORED key, which is what the table is keyed by — the bug was naming (and looking up)
    # the `ga4gh:VA.…` id the expansion had just minted.
    assert all(e.startswith(f"resolution: {authored_key}:") for e in withdrawn), withdrawn
    assert set(validate_errors) == set(compile_errors)


def test_an_ambiguous_locus_refuses_at_validate_under_strict_only(tmp_path: Path) -> None:
    """One severity down, same loop, same key: `strict` refuses and `best_effort` carries the pick."""
    spec = _spec(tmp_path)
    _mark(spec, "status", "ambiguous")

    lenient_validate, lenient_compile = _findings(spec, tmp_path, strict=False)
    strict_validate, strict_compile = _findings(spec, tmp_path, strict=True)

    assert not [e for e in lenient_validate if "ambiguous" in e]
    assert not [e for e in lenient_compile if "ambiguous" in e]
    assert [e for e in strict_validate if "ambiguous" in e], strict_validate
    assert set(strict_validate) == set(strict_compile)


@pytest.mark.parametrize("strict", [False, True])
def test_the_finding_is_published_once_though_both_sides_ask(tmp_path: Path, strict: bool) -> None:
    """`compile_module` runs the pre-flight and then resolves, so the sentence is reachable twice.

    It is safe to ask on both sides precisely because neither message embeds a count
    (`@no-rerun-with-counts`) — so the two are byte-identical and dedup on the message works. A
    future edit that interpolated a total into either sentence would publish two numbers, and this is
    what would catch it.
    """
    spec = _spec(tmp_path)
    _mark(spec, "rsid_status", "withdrawn")

    result = compile_module(spec, tmp_path / "out", strict=strict)

    withdrawn = [e for e in result.errors if "WITHDRAWN" in e]
    assert len(withdrawn) == 1, withdrawn


def test_the_untouched_example_still_compiles(tmp_path: Path) -> None:
    """The floor under all of the above: the fixture is clean, so a refusal means the edit caused it."""
    spec = _spec(tmp_path)
    assert validate_spec(spec, strict=True).valid
    assert compile_module(spec, tmp_path / "out", strict=True).success
