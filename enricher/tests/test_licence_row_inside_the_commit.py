"""A data table never exists on disk without its licence row (S98, RM231).

`alphagenome expression` wrote `expression_effects.csv`, then failed to record its licence row on a
scaffold's placeholder `licensing.csv`, and printed `FAILED` — 12,003 non-commercial rows on disk with
no licence record, which the compile gate (keyed on the licence table and nothing else) then passed as
though they were unrestricted. Eight passes had the same two-step tail. The fix is one primitive: the
licence merge runs **inside** the table's atomic commit (`atomic_writer(before_commit=...)`), so a
failure on either side leaves nothing, and every pass reads the licence table **before** its fetch so
a placeholder fails in a second rather than after a whole-gene query.

Both halves are asserted over a walked set, never a list kept beside the code: every function under
`just_dna_enricher` that records a licence row either passes the merge as `before_commit` to a writer
and pre-reads the table, or is named here with the reason it writes no data table.
"""

import ast
from pathlib import Path

import pytest
from just_dna_enricher import licensing
from just_dna_format.layout import atomic_writer

_SRC = Path(licensing.__file__).parent
_RECORDERS = {"merge_sources_file", "record_source_terms"}
_PREFLIGHT = "require_sources_file"

#: Callers that record a licence row and write **no data table of their own** in that function, so
#: there is nothing for the row to be committed with. Each names why. Equality below, not a subset.
_NO_TABLE_OF_ITS_OWN = {
    ("licensing.py", "record_source_terms"): "the recorder itself",
    ("identifiers.py", "_check_pgs"): "records the PGS Catalog's terms for a CHECK; it writes no table",
    ("clinpgx.py", "enrich_clinpgx"): (
        "records the snapshot's terms for annotation rows that land through the compiler's draft "
        "surface in another function; nothing here to commit them with"
    ),
    # The two below are the same gap one layer over, and it is RM228's to close, not this guard's to
    # hide: drafted rows are appended by the compiler's `draft.append_*` (atomic per file) and the
    # licence row is recorded afterwards, so a refused merge leaves drafted rows with no licence
    # record. The seam this test pins does not reach the compiler's writer.
    ("civic_citations.py", "draft_civic_citations"): (
        "appends through `append_partial_rows`, then records — RM228's gap"
    ),
    ("drafting.py", "record_draft_provenance"): (
        "the scaffold's recorder, called after the drafters append — RM228's gap"
    ),
}


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _functions_recording_a_licence_row() -> dict[tuple[str, str], ast.FunctionDef]:
    found: dict[tuple[str, str], ast.FunctionDef] = {}
    for path in sorted(_SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            calls = {_called_name(c) for c in ast.walk(node) if isinstance(c, ast.Call)}
            if calls & _RECORDERS:
                found[(path.name, node.name)] = node
    return found


def _recorder_is_inside_a_writers_commit(func: ast.FunctionDef) -> bool:
    """The merge appears only as a `before_commit=` argument of some call — never as a bare statement."""
    inside: set[int] = set()
    for call in ast.walk(func):
        if not isinstance(call, ast.Call):
            continue
        for kw in call.keywords:
            if kw.arg == "before_commit":
                inside.update(id(c) for c in ast.walk(kw.value) if isinstance(c, ast.Call))
    bare = [
        c
        for c in ast.walk(func)
        if isinstance(c, ast.Call) and _called_name(c) in _RECORDERS and id(c) not in inside
    ]
    return not bare and bool(inside)


def _preflight_precedes_the_write(func: ast.FunctionDef) -> bool:
    lines = {_called_name(c): c.lineno for c in ast.walk(func) if isinstance(c, ast.Call)}
    if _PREFLIGHT not in lines:
        return False
    writes = [
        c.lineno
        for c in ast.walk(func)
        if isinstance(c, ast.Call) and any(kw.arg == "before_commit" for kw in c.keywords)
    ]
    return bool(writes) and lines[_PREFLIGHT] < min(writes)


def test_every_pass_that_records_a_licence_row_does_so_inside_its_tables_commit() -> None:
    recorders = _functions_recording_a_licence_row()
    assert recorders, "the walk found nothing — the recorder names moved"
    unknown = set(recorders) - set(_NO_TABLE_OF_ITS_OWN)
    committing = {key for key in unknown if _recorder_is_inside_a_writers_commit(recorders[key])}
    stragglers = unknown - committing
    assert not stragglers, (
        f"these record a licence row as a bare step beside their data write, so a refused merge leaves "
        f"the table on disk with no licence record: {sorted(stragglers)}. Pass the merge as "
        f"`before_commit=` to the table's writer, or name the function in _NO_TABLE_OF_ITS_OWN with its reason."
    )
    exempt_but_committing = {
        k
        for k in _NO_TABLE_OF_ITS_OWN
        if k in recorders and _recorder_is_inside_a_writers_commit(recorders[k])
    }
    assert not exempt_but_committing, (
        f"exempt but actually committing — drop the exemption: {exempt_but_committing}"
    )
    assert set(_NO_TABLE_OF_ITS_OWN) <= set(recorders), (
        f"exemptions naming no recorder: {set(_NO_TABLE_OF_ITS_OWN) - set(recorders)}"
    )
    # The eight, by name, so the walk cannot silently shrink.
    assert {key[0] for key in committing} == {
        "enrich.py",
        "assertions.py",
        "gene_metrics.py",
        "frequencies.py",
        "gene_validity.py",
        "gwas.py",
        "clingen.py",
        "expression.py",
    }
    for key in committing:
        assert _preflight_precedes_the_write(recorders[key]), (
            f"{key}: reads the licence table after (or never before) the write — call "
            f"`{_PREFLIGHT}` before the fetch so a placeholder row fails in a second"
        )


def test_a_failing_before_commit_leaves_the_previous_table_byte_for_byte(tmp_path: Path) -> None:
    class Boom(RuntimeError):
        pass

    def refuse() -> None:
        raise Boom("licensing.csv line 2: unreplaced template placeholder")

    target = tmp_path / "table.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(Boom), atomic_writer(target, newline="", before_commit=refuse) as handle:
        handle.write("a,b\n3,4\n")
    assert target.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["table.csv"], "no temp file left behind"

    fresh = tmp_path / "fresh.csv"
    with pytest.raises(Boom), atomic_writer(fresh, newline="", before_commit=refuse) as handle:
        handle.write("a,b\n3,4\n")
    assert not fresh.exists()


def test_before_commit_runs_after_the_bytes_are_down_and_before_the_rename(tmp_path: Path) -> None:
    target = tmp_path / "table.csv"
    seen: list[bool] = []

    def observe() -> None:
        seen.append(target.exists())
        temps = [p for p in tmp_path.iterdir() if p.name != target.name]
        assert len(temps) == 1 and temps[0].read_text(encoding="utf-8") == "a,b\n1,2\n"

    with atomic_writer(target, newline="", before_commit=observe) as handle:
        handle.write("a,b\n1,2\n")
    assert seen == [False], "the callback ran once, with the table not yet renamed into place"
    assert target.read_text(encoding="utf-8") == "a,b\n1,2\n"


def test_a_rename_that_fails_after_the_callback_names_what_it_left_behind(
    tmp_path: Path, monkeypatch
) -> None:
    """The one residual ordering cannot remove — two files are two renames — is at least SAID.

    The licence row's own `os.replace` has returned by the time the table's runs, so a table rename
    that fails leaves a licence row for data that never arrived: conservative, and the error names it,
    which is S98's own closing ask — a partial commit says what it committed."""
    import just_dna_format.layout as layout_module

    target = tmp_path / "table.csv"
    ran: list[str] = []
    real_replace = layout_module.os.replace

    def failing_replace(src, dst):
        if Path(dst) == target:
            raise OSError(28, "No space left on device")
        return real_replace(src, dst)

    monkeypatch.setattr(layout_module.os, "replace", failing_replace)
    with (
        pytest.raises(OSError, match="before_commit side effect .* already landed") as excinfo,
        atomic_writer(target, newline="", before_commit=lambda: ran.append("licence row")) as handle,
    ):
        handle.write("a,b\n1,2\n")
    assert ran == ["licence row"] and not target.exists()
    assert "No space left" in str(excinfo.value.__cause__)
    assert [p.name for p in tmp_path.iterdir()] == [], "the temp is still cleaned up"
