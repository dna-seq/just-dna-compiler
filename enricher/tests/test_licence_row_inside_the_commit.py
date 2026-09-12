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

**RM232 closed the two exemptions this file had to open.** A drafter's rows do not go through a writer
of its own — they go through the compiler's `draft.append_rows` / `append_partial_rows`, which had no
`before_commit` to hand a callback to, so `civic_citations.draft_civic_citations` and the drafting
scaffold's `record_draft_provenance` recorded the licence row only once the drafted rows were already
renamed into place. Both writers now take the parameter, and the third test below asserts the other
half over a walked set too: **every** `append_*` call under `just_dna_enricher` passes one, so a new
drafter inherits the rule instead of remembering it.
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
}

#: The callbacks themselves (RM232). A function whose whole body IS the merge cannot pass itself to a
#: writer; what it owes instead is that every caller hands it to one, which
#: `test_every_drafted_table_commits_its_licence_row_with_itself` asserts from the other end. Kept
#: apart from the exemptions above rather than merged into them: those write no table at all, these
#: are the row's write, and collapsing the two would let a real straggler hide among them.
_IS_THE_CALLBACK = {
    ("drafting.py", "commit"): "the closure `licence_commit` returns, for every drafter",
    ("civic_citations.py", "_commit_licence"): "this pass's own `before_commit` closure",
}

#: Where a drafted row reaches disk. Both take `before_commit` since RM232.
_DRAFT_WRITERS = {"append_rows", "append_partial_rows"}


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _own_calls(func: ast.FunctionDef) -> list[ast.Call]:
    """Every call `func` makes **itself**, stopping at a nested `def`.

    A closure's calls belong to the closure, which is walked as a function in its own right — without
    this, a pass that moved its merge into a `before_commit` closure still reads as making a bare
    recorder call and the guard flags the very shape it is asking for (RM232).
    """
    calls: list[ast.Call] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if isinstance(node, ast.Call):
            calls.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return calls


def _nested_callbacks(func: ast.FunctionDef) -> list[ast.FunctionDef]:
    """The nested `def`s this function hands to a writer as `before_commit=`.

    A pass may spell its callback as a lambda (the eight of RM231) or as a nested `def` where the
    merge needs more than an expression — `civic_citations` keeps the merged rows on its result. Both
    are the shape this file is asking for, so both have to count as *inside the commit*: resolved by
    name rather than by walking every nested `def`, so a callback that is defined and never passed
    still reads as a bare recorder, which is exactly the bug it would be.
    """
    referenced = {
        kw.value.id
        for call in _own_calls(func)
        for kw in call.keywords
        if kw.arg == "before_commit" and isinstance(kw.value, ast.Name)
    }
    return [n for n in ast.walk(func) if isinstance(n, ast.FunctionDef) and n.name in referenced]


def _effective_calls(func: ast.FunctionDef) -> list[ast.Call]:
    """`func`'s own calls, plus those of the nested `def`s it hands to a writer as `before_commit=`."""
    calls = list(_own_calls(func))
    for callback in _nested_callbacks(func):
        calls.extend(_own_calls(callback))
    return calls


def _all_functions() -> dict[tuple[str, str], ast.FunctionDef]:
    found: dict[tuple[str, str], ast.FunctionDef] = {}
    for path in sorted(_SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                found[(path.name, node.name)] = node
    return found


def _functions_recording_a_licence_row() -> dict[tuple[str, str], ast.FunctionDef]:
    return {
        key: node
        for key, node in _all_functions().items()
        if {_called_name(c) for c in _effective_calls(node)} & _RECORDERS
    }


def _recorder_is_inside_a_writers_commit(func: ast.FunctionDef) -> bool:
    """The merge appears only as a `before_commit=` argument of some call — never as a bare statement."""
    inside: set[int] = set()
    for call in _own_calls(func):
        for kw in call.keywords:
            if kw.arg == "before_commit":
                inside.update(id(c) for c in ast.walk(kw.value) if isinstance(c, ast.Call))
    for callback in _nested_callbacks(func):
        inside.update(id(c) for c in _own_calls(callback))
    bare = [c for c in _effective_calls(func) if _called_name(c) in _RECORDERS and id(c) not in inside]
    return not bare and bool(inside)


def _preflight_precedes_the_write(func: ast.FunctionDef) -> bool:
    lines = {_called_name(c): c.lineno for c in _own_calls(func)}
    if _PREFLIGHT not in lines:
        return False
    writes = [c.lineno for c in _own_calls(func) if any(kw.arg == "before_commit" for kw in c.keywords)]
    return bool(writes) and lines[_PREFLIGHT] < min(writes)


def test_every_pass_that_records_a_licence_row_does_so_inside_its_tables_commit() -> None:
    recorders = _functions_recording_a_licence_row()
    assert recorders, "the walk found nothing — the recorder names moved"
    unknown = set(recorders) - set(_NO_TABLE_OF_ITS_OWN) - set(_IS_THE_CALLBACK)
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
    named = set(_NO_TABLE_OF_ITS_OWN) | set(_IS_THE_CALLBACK)
    assert named <= set(recorders), f"exemptions naming no recorder: {named - set(recorders)}"
    # The nine, by name, so the walk cannot silently shrink. RM231's eight, plus `civic_citations`
    # — which was one of that round's two exemptions until the compiler's writer took the parameter
    # (RM232) and it could hand its merge to the append that lands `studies.csv`.
    assert {key[0] for key in committing} == {
        "enrich.py",
        "assertions.py",
        "gene_metrics.py",
        "frequencies.py",
        "gene_validity.py",
        "gwas.py",
        "clingen.py",
        "expression.py",
        "civic_citations.py",
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


def test_every_drafted_table_commits_its_licence_row_with_itself() -> None:
    """The other half of RM232, from the writer's end rather than the recorder's.

    A drafter has no writer of its own: its rows reach disk through the compiler's `append_rows` /
    `append_partial_rows`. So the rule this file states for a pass — the licence row lands inside the
    table's commit — is, for a drafter, that **every** append carries a `before_commit`. Asserted over
    a walked set rather than a list of the drafters that exist today, because the failure it replaces
    was a provider shipping without the call and nothing noticing (RM228's shape, and RM231 had to
    open two exemptions for it).
    """
    offenders: list[str] = []
    appends = 0
    for (filename, funcname), node in sorted(_all_functions().items()):
        for call in _own_calls(node):
            if _called_name(call) not in _DRAFT_WRITERS:
                continue
            appends += 1
            if not any(kw.arg == "before_commit" for kw in call.keywords):
                offenders.append(f"{filename}:{call.lineno} in {funcname}()")
    assert appends >= len(_DRAFT_WRITERS), "the walk found no appends — the writer names moved"
    assert not offenders, (
        f"these append drafted rows without binding a licence row to the commit, so a refused merge "
        f"leaves the rows on disk with nothing recording what licensed them: {offenders}. Build the "
        f"closure with `drafting.licence_commit(...)` and pass it as `before_commit=`."
    )


def test_the_closure_records_one_row_however_many_tables_a_drafter_writes(tmp_path: Path) -> None:
    """A drafter appending three tables hands the same callable to all three (RM232).

    Binding it to only the first or only the last is the repair that looks equivalent and is not: the
    first may be the run's no-op and the last leaves every earlier table committed unlicensed. Firing
    per table is safe because the merge is never-clobber, and this asserts that rather than trusting
    it — over the real `merge_sources_file`, not a stand-in.
    """
    from just_dna_enricher.drafting import licence_commit
    from just_dna_enricher.licensing import CLINVAR_TERMS, read_sources_file

    class Err(RuntimeError):
        pass

    commit = licence_commit(
        sources=[CLINVAR_TERMS.source],
        spec_dir=tmp_path,
        dataset="2026-09",
        declared_use="unstated",
        error=Err,
    )
    for _ in range(3):
        commit()
    rows = read_sources_file(tmp_path)
    assert [(r.source, r.layer) for r in rows] == [(CLINVAR_TERMS.source, "annotation")]
    assert rows[0].dataset == "2026-09"


def test_the_closure_refuses_a_placeholder_licence_table_before_the_first_append(tmp_path: Path) -> None:
    """S98's own trigger, one layer over: a scaffold's `<<REPLACE>>` row must stop the run up front.

    The pre-flight lives in `licence_commit` rather than in each drafter, so it is inherited. It has
    to fire when the closure is BUILT — a drafter builds it before its first append, so a placeholder
    refuses with the author's tables untouched rather than after the rows are already renamed in.
    """
    from just_dna_enricher.drafting import licence_commit
    from just_dna_enricher.licensing import CLINVAR_TERMS

    class Err(RuntimeError):
        pass

    (tmp_path / "licensing.csv").write_text(
        "source,layer,declared_use\n<<REPLACE>>,<<REPLACE>>,unstated\n", encoding="utf-8"
    )
    with pytest.raises(Err, match="licensing.csv is invalid"):
        licence_commit(
            sources=[CLINVAR_TERMS.source],
            spec_dir=tmp_path,
            dataset=None,
            declared_use="unstated",
            error=Err,
        )


def test_a_dry_run_refuses_an_unreadable_licence_table_rather_than_reporting(tmp_path: Path) -> None:
    """A dry run says what the real run will do, so it must not pass where the real one refuses.

    The pre-flight fires when the closure is built, and a drafter builds it before it knows whether
    this run writes — so `--dry-run` on a scaffold's placeholder table raises. Behaviour change from
    before RM232, pinned here as intended rather than discovered later as a regression.
    """
    from just_dna_enricher.drafting import licence_commit
    from just_dna_enricher.licensing import CLINVAR_TERMS

    class Err(RuntimeError):
        pass

    (tmp_path / "licensing.csv").write_text(
        "source,layer,declared_use\n<<REPLACE>>,<<REPLACE>>,unstated\n", encoding="utf-8"
    )
    with pytest.raises(Err, match="licensing.csv is invalid"):
        licence_commit(
            sources=[CLINVAR_TERMS.source],
            spec_dir=tmp_path,
            dataset=None,
            declared_use="unstated",
            error=Err,
        )
    # And nothing was written on the way to the refusal: a dry run that refuses still writes nothing,
    # which is the property the refusal must not cost.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["licensing.csv"]
