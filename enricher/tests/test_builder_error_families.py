"""RM288: two snapshot builders and the PGx drafter each export their error family as `ERRORS`.

The decision is a **callee-owned tuple**: no base class (that makes a caller's `except` order
load-bearing, `@client-exception-contract`) and no list spelled at each call site (that drifted, and
RM310 was the incident: `caches._rebuild_cpic` named `CpicBuildError` and forgot `CpicError`).

Two halves, both needed. The AST walk says every caller catches the surface's tuple; the stub-driven
tests say the tuple really holds what the surface raises. Either alone passes on a list that drifted.
"""

import ast
from pathlib import Path

import httpx
import pytest
from just_dna_enricher import cpic_build, pgx_draft, pharmvar_build
from just_dna_enricher.cpic import CpicClient, CpicError
from just_dna_enricher.pharmvar import PharmVarClient, PharmVarError

_SRC = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"

#: surface module → the functions a caller reaches it through.
_SURFACES = {
    "cpic_build": {"build_snapshot"},
    "pharmvar_build": {"build_snapshot"},
    "pgx_draft": {"draft_gene"},
}


def _aliases(tree: ast.Module) -> dict[str, str]:
    """Local name → surface module, for `from just_dna_enricher.<m> import <f> [as <alias>]`."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.rsplit(".", 1)[-1]
            for name in node.names:
                if module in _SURFACES and name.name in _SURFACES[module]:
                    out[name.asname or name.name] = module
    return out


def _called_surfaces(body: list[ast.stmt], aliases: dict[str, str]) -> set[str]:
    """The surfaces a `try` body calls directly (a nested `def` is its own scope, and not walked)."""
    found: set[str] = set()
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in aliases:
                found.add(aliases[func.id])
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in _SURFACES
                and func.attr in _SURFACES[func.value.id]
            ):
                found.add(func.value.id)
        stack.extend(ast.iter_child_nodes(node))
    return found


def _caught_families(handlers: list[ast.ExceptHandler]) -> set[str]:
    return {
        node.value.id
        for handler in handlers
        if handler.type is not None
        for node in ast.walk(handler.type)
        if isinstance(node, ast.Attribute)
        and node.attr == "ERRORS"
        and isinstance(node.value, ast.Name)
        and node.value.id in _SURFACES
    }


def _call_sites() -> list[tuple[str, int, set[str], set[str]]]:
    sites = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _aliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                called = _called_surfaces(node.body, aliases)
                if called:
                    sites.append(
                        (str(path.relative_to(_SRC)), node.lineno, called, _caught_families(node.handlers))
                    )
    return sites


def test_every_call_site_catches_the_surfaces_own_tuple() -> None:
    sites = _call_sites()
    # The walk has teeth only if it finds the callers it exists for: caches, the two CLI builders, draft.
    assert {path for path, *_ in sites} >= {"caches.py", "cli/pgx_commands.py", "cli/authoring_commands.py"}
    wrong = [(path, line, sorted(called - caught)) for path, line, called, caught in sites if called - caught]
    assert not wrong, f"a caller spells its own list instead of catching <module>.ERRORS: {wrong}"


def test_no_handler_names_a_member_only_one_family_holds() -> None:
    """`CpicBuildError` belongs to `cpic_build.ERRORS` alone, so naming it bare is the list shape."""
    offenders = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "cpic_build.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                names = {n.id for n in ast.walk(node.type) if isinstance(n, ast.Name)}
                names |= {n.attr for n in ast.walk(node.type) if isinstance(n, ast.Attribute)}
                if "CpicBuildError" in names:
                    offenders.append((str(path.relative_to(_SRC)), node.lineno))
    assert not offenders


# ── what the surfaces raise, driven through their real code ──────────────────────────────────────


def _failing_transport(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(503)


def test_the_cpic_builder_raises_only_its_family(tmp_path: Path) -> None:
    client = CpicClient()
    client._client = httpx.Client(transport=httpx.MockTransport(_failing_transport))
    with pytest.raises(cpic_build.ERRORS) as raised:
        cpic_build.build_snapshot(tmp_path / "out", client=client)
    assert isinstance(raised.value, CpicError)


def test_the_pharmvar_builder_raises_only_its_family(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No key configured is the builder's documented refusal (`@test-no-credential`: set, never deleted)."""
    from just_dna_enricher import pharmvar

    monkeypatch.setenv(pharmvar.API_KEY_ENV, "")
    with pytest.raises(pharmvar_build.ERRORS) as raised:
        pharmvar_build.build_snapshot(tmp_path / "out", client=PharmVarClient(api_key=None))
    assert isinstance(raised.value, PharmVarError)


def _spec(directory: Path, yaml_text: str) -> Path:
    directory.mkdir(parents=True)
    (directory / "module_spec.yaml").write_text(yaml_text, encoding="utf-8")
    return directory


_YAML = "schema_version: '1.0'\nmodule:\n  name: pgx\n  title: P\n  description: d\n  report_title: P\n"


def test_the_drafter_raises_only_its_family(tmp_path: Path) -> None:
    client = CpicClient()
    client._client = httpx.Client(transport=httpx.MockTransport(_failing_transport))

    # CPIC's terms forbid sale, so a commercial declaration is refused before any request.
    with pytest.raises(pgx_draft.ERRORS):
        pgx_draft.draft_gene(_spec(tmp_path / "a", _YAML), "CYP2C9", declared_use="commercial", client=client)
    # A module_spec.yaml whose build cannot be read (a typo'd key) is `source_build_mismatch`'s refusal.
    with pytest.raises(pgx_draft.ERRORS) as unreadable:
        pgx_draft.draft_gene(
            _spec(tmp_path / "b", _YAML + "genome_bild: GRCh37\n"),
            "CYP2C9",
            declared_use="non_commercial",
            client=client,
        )
    assert "genome_build" in str(unreadable.value)
    # And the client's outage.
    with pytest.raises(pgx_draft.ERRORS) as raised:
        pgx_draft.draft_gene(
            _spec(tmp_path / "c", _YAML), "CYP2C9", declared_use="non_commercial", client=client
        )
    assert isinstance(raised.value, CpicError)
