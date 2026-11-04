"""The static half of RM367: which path asks each check, and where a compile may refuse.

`test_one_verdict.py` runs both commands over a corpus and compares what they said. A corpus finds what
its fixtures reach; these walk the code, so a check added to one path, a refusal placed after the first
write, or a flag one entry point never forwards fails here on the day it is written, whatever the corpus
holds. Every assertion is an equality over a walked set (`@registry-completeness`).
"""

import ast
import inspect
import re
from pathlib import Path

from just_dna_compiler import cli
from just_dna_compiler.compiler import check_paths, pipeline, validate

#: What counts as a check: a callee named like one, plus the shared steps that judge without the name.
_CHECK = re.compile(
    r"^_?(check|cross_check|cross_validate|verify|validate)_|_(checks|warnings|errors|error|refusals|refusal)$"
    r"|^(read_resolution|resolve_variants|identity_after_resolution|ploidy_after_resolution|apply_overrides"
    r"|build_meta|discover_logs|ancillary_errors|load_authored_table|_load_csv_rows|_locate_sidecar)$"
)
#: The pre-flight itself, which the compile calls and which is not a check of its own.
_NOT_A_CHECK = {"_validate_spec"}


def _function(module: object, name: str) -> ast.FunctionDef:
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _callee(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _checks(function: ast.FunctionDef) -> set[str]:
    """Every check the function calls, its nested closures included."""
    names = {_callee(n) for n in ast.walk(function) if isinstance(n, ast.Call)}
    return {n for n in names if n and _CHECK.search(n) and n not in _NOT_A_CHECK}


def test_the_roster_is_what_the_two_paths_call() -> None:
    compiled = _checks(_function(pipeline, "compile_module"))
    preflight = _checks(_function(validate, "_validate_spec"))
    assert compiled - preflight == set(check_paths.COMPILE_ONLY), (
        "a check asked on the compile path only must be asked by the pre-flight too, or entered in "
        f"check_paths.COMPILE_ONLY with its reason: {sorted(compiled - preflight)}"
    )
    assert preflight - compiled == check_paths.PREFLIGHT_ONLY, sorted(preflight - compiled)
    assert all(reason.strip() for reason in check_paths.COMPILE_ONLY.values())


def test_the_walk_sees_the_checks_it_is_about() -> None:
    """The walk is only as good as its pattern: pin that it sees the checks RM367 moved, on both paths."""
    both = _checks(_function(pipeline, "compile_module")) & _checks(_function(validate, "_validate_spec"))
    moved = {
        "read_resolution",
        "resolve_variants",
        "unplaced_refusal",
        "identity_after_resolution",
        "ploidy_after_resolution",
        "ancillary_errors",
        "_source_checks",
        "_cross_check_frequencies",
        "_check_ba1_lint",
        "_cross_check_clinical_assertions",
        "_cross_check_gwas_effects",
    }
    assert moved <= both, sorted(moved - both)


# ── every refusal before the first write ─────────────────────────────────────────────────────────

#: Calls that put a byte under `output_dir`.
_WRITES = {
    "write_parquet",
    "write_manifest",
    "copyfile",
    "_collect_logs",
    "_collect_provenance",
    "_collect_logo",
    "_collect_readme",
}


def _is_refusal(node: ast.Call) -> bool:
    if _callee(node) != "CompilationResult":
        return False
    return any(
        kw.arg == "success" and isinstance(kw.value, ast.Constant) and kw.value.value is False
        for kw in node.keywords
    )


def _mkdir_line(function: ast.FunctionDef) -> int:
    lines = [
        n.lineno
        for n in ast.walk(function)
        if isinstance(n, ast.Call)
        and _callee(n) == "mkdir"
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "output_dir"
    ]
    assert len(lines) == 1, lines
    return lines[0]


def test_every_compile_refusal_comes_before_the_output_directory() -> None:
    """A refusal after `output_dir.mkdir()` leaves a half-written artifact behind (RM367).

    Before the fix this named the fact-table loop's four refusals (spelling, load, overlay, check) and the
    three ancillary files' (provenance, logo, readme): seven returns placed after the SNP core and the
    table kinds were already on disk.
    """
    function = _function(pipeline, "compile_module")
    mkdir = _mkdir_line(function)
    late = sorted(
        n.lineno
        for n in ast.walk(function)
        if isinstance(n, ast.Call) and _is_refusal(n) and n.lineno > mkdir
    )
    assert not late, f"compile_module refuses after output_dir.mkdir() (line {mkdir}) at line(s) {late}"
    early = sorted(
        n.lineno
        for n in ast.walk(function)
        if isinstance(n, ast.Call) and _callee(n) in _WRITES and n.lineno < mkdir
    )
    assert not early, f"compile_module writes before output_dir.mkdir() (line {mkdir}) at line(s) {early}"


# ── a flag reaches every entry point that owes it ────────────────────────────────────────────────


def _keywords_passed(function: ast.FunctionDef, callee: str) -> set[str]:
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call) and _callee(n) == callee]
    assert len(calls) == 1, f"{function.name} calls {callee} {len(calls)} time(s)"
    return {kw.arg for kw in calls[0].keywords if kw.arg is not None}


def test_the_compile_forwards_every_preflight_option_it_takes() -> None:
    """A compile option the pre-flight also takes is forwarded, or the pre-flight answers another compile."""
    shared = set(inspect.signature(pipeline.compile_module).parameters) & set(
        inspect.signature(validate._validate_spec).parameters
    )
    shared -= {"spec_dir", "authority_keys"}  # positional
    # `ensembl_cache` reaches it as `legacy_reference`: the pre-flight needs only to know one is held.
    shared |= {"legacy_reference"}
    assert _keywords_passed(_function(pipeline, "compile_module"), "_validate_spec") == shared


def test_the_validate_command_exposes_every_validate_spec_option() -> None:
    """`@off-switch-needs-a-probe`: `validate` lacked `--no-resolve`, so it could not pre-flight
    `compile --no-resolve` at all, and the two disagreed under `--strict`."""
    expected = set(inspect.signature(validate.validate_spec).parameters) - {"spec_dir"}
    assert _keywords_passed(_function(cli, "validate"), "validate_spec") == expected
