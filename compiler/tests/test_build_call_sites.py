"""Every place that mints an identity must be told which assembly the row is on.

`derive_variant_key` mints a `ga4gh:VA.…` only when it is handed a **single `alts`**; an rsID
short-circuits first, and no-`alts` / multi-allelic cells fall through to a coordinate key computed
without touching the build. So the whole exposure is: *call sites that pass one `alts` and omit
`build=`*. That is a small, enumerable set, and on 2026-08-06 five of its members were wrong at once —
`reverse_module`'s two writers, `enrich()`, `VrsMinter.mint`, and the gnomAD frequency pass — each
minting a GRCh38 identity for a coordinate on another assembly.

This file pins the property that makes the bug class impossible to reintroduce silently: it reads the
source and fails on a call that supplies an allele without supplying a build. A static check rather than
a behavioural one, deliberately — the behavioural tests
(`test_build_roundtrip.py`, `enricher/tests/test_build_awareness.py`) cover the five known paths, and
what keeps failing here is the *sixth* path someone adds next, which no existing test can anticipate.
"""

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SOURCES = [
    _ROOT / "schema" / "src" / "just_dna_format",
    _ROOT / "compiler" / "src" / "just_dna_compiler",
    _ROOT / "enricher" / "src" / "just_dna_enricher",
]

#: Functions whose 5th positional argument is `alts`, and which mint a VRS id from it.
_MINTERS = {"derive_variant_key"}

#: Call sites that pass an allele without a build and are *correct* anyway, each with the reason.
#: Keeping the exemptions here rather than in the code means adding one is a visible decision.
_EXEMPT = {
    # The stamp-then-restamp pattern, and the reason it exists. `_freeze_identity` is a model validator
    # running at construction, where `module_spec.yaml` is not in scope — there is no build to pass. It
    # writes a *stored field*, so the compiler corrects it after load in `_restamp_for_build`, at both
    # of its load sites plus `enrich()`'s. That correction is what makes this call safe, and it is
    # tested directly in `test_build_roundtrip.py::test_the_two_builds_key_differently`.
    ("spec.py", "_freeze_identity"),
    # RM36: a property has no module in scope *and* no stored field to correct, so unlike the entry
    # above there is nothing for the compiler to fix afterwards. Bounded — never reaches parquet, and
    # grouping stays internally consistent. Removing this entry is how RM36 gets closed.
    ("binning.py", "variant_key"),
}


def _alts_arg(call: ast.Call) -> ast.expr | None:
    """The `alts` argument of a `derive_variant_key` call, positional or keyword, else None."""
    if len(call.args) >= 5:
        return call.args[4]
    for kw in call.keywords:
        if kw.arg == "alts":
            return kw.value
    return None


def _enclosing_name(tree: ast.Module, node: ast.Call) -> str:
    """The nearest enclosing function/property name, for a legible failure message."""
    best = "<module>"
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno)
        ):
            best = parent.name
    return best


def _minting_calls() -> list[tuple[Path, ast.Module, ast.Call]]:
    found = []
    for root in _SOURCES:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if name in _MINTERS and _alts_arg(node) is not None:
                    found.append((path, tree, node))
    return found


def test_the_sweep_actually_finds_call_sites() -> None:
    """Guard the guard: an AST walk that silently matches nothing would pass every assertion below."""
    calls = _minting_calls()
    assert len(calls) >= 5, f"expected the known minting call sites, found {len(calls)}"


def test_every_allele_bearing_call_passes_a_build() -> None:
    """A call handing over an allele mints an identity, and an identity names an assembly.

    A `None` literal for `alts` is not exempt — it cannot mint — but the check is deliberately shallow:
    it asks whether the *call* supplies a build, not whether the value is reachable. A call that can
    never mint costs one keyword argument to satisfy; a call that can, and doesn't, is the bug.
    """
    offenders = []
    for path, tree, call in _minting_calls():
        alts = _alts_arg(call)
        if isinstance(alts, ast.Constant) and alts.value is None:
            continue  # literally cannot mint
        has_build = any(kw.arg == "build" for kw in call.keywords)
        where = (path.name, _enclosing_name(tree, call))
        if not has_build and where not in _EXEMPT:
            offenders.append(f"{path.relative_to(_ROOT)}:{call.lineno} in {where[1]}()")

    assert not offenders, (
        "these calls mint a variant identity from an allele without saying which assembly it is on, "
        "so they take derive_variant_key's GRCh38 default:\n  " + "\n  ".join(offenders)
        + "\nPass build=<the module's genome_build>. If the call genuinely cannot know one, add it to "
          "_EXEMPT with the reason — that is a design decision (see RM36), not a formality."
    )


@pytest.mark.parametrize("filename,funcname", sorted(_EXEMPT))
def test_each_exemption_still_exists(filename: str, funcname: str) -> None:
    """An exemption for a call site that has since moved or been fixed is stale scaffolding, and would
    silently keep excusing whatever takes its place."""
    matches = [
        (p, f) for p, tree, c in _minting_calls()
        if (f := _enclosing_name(tree, c)) == funcname and p.name == filename
    ]
    assert matches, f"_EXEMPT names {filename}:{funcname}(), which no longer makes such a call"
