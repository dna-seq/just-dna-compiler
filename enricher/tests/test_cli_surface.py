"""Four surface defects with no common cause, and the guards that stop each recurring (RM100).

Filed together because each is a few lines and none was worth its own entry -- not because they share
a root. What they do share is that every one of them is invisible from inside the happy path: a
command that exists through one entry point and not another, a function defined twice, a client leaked
only on the error path, a credential honoured or not by call order.
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.cli import app

_SRC = Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"


def _commands(argv: list[str]) -> set[str]:
    """The top-level command names one entry point advertises."""
    result = subprocess.run(
        [*argv, "--help"], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "COLUMNS": "200"}
    )
    assert result.returncode == 0, result.stderr
    return set(re.findall(r"^\s*│?\s*([a-z][a-z0-9-]+)\s{2,}", result.stdout, re.MULTILINE))


def test_the_module_form_exposes_every_command_the_console_script_does() -> None:
    """`if __name__ == "__main__": app()` must be the LAST thing in `cli.py`.

    It sat two-thirds of the way down, above the `hint` sub-app, `draft-clinpgx`, `draft-panel` and
    `clinvar citations` -- so `python -m just_dna_enricher.cli` called `app()` before those
    registrations had run and advertised 23 of the 26 commands. Harmless through the entry point
    `[project.scripts]` owns, which imports the module fully and then calls `app()`, and wrong for
    anybody invoking the module directly. Measured rather than argued: the two sets are compared.
    """
    script = Path(sys.executable).parent / "just-dna-enricher"
    if not script.exists():
        pytest.skip("console script not installed in this environment")

    from_script = _commands([str(script)])
    from_module = _commands([sys.executable, "-m", "just_dna_enricher.cli"])

    assert from_script, "the help output shape changed; this test is reading nothing"
    assert from_module == from_script, (
        f"the module form is missing {sorted(from_script - from_module)} — a registration sits below "
        f"`if __name__ == '__main__'` in cli.py"
    )


def test_the_main_guard_is_the_last_statement_in_the_cli() -> None:
    """The structural half, so the cause is caught rather than the symptom.

    The test above needs a console script and a subprocess; this one reads the module's AST and would
    fail the moment a command is appended below the guard, which is exactly how the defect arose.
    """
    tree = ast.parse((_SRC / "cli.py").read_text(encoding="utf-8"))
    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert len(guards) == 1, "expected exactly one `if __name__ == '__main__'` block"
    assert tree.body[-1] is guards[0], (
        "`if __name__ == '__main__'` is not the last statement in cli.py, so every registration "
        "below it is invisible to `python -m just_dna_enricher.cli`"
    )


def test_no_module_defines_the_same_function_twice() -> None:
    """`clinvar_build._sha256_file` was defined twice, and the second shadowed the first.

    That is worse than dead code: the dead one returned a bare `str` and looked like the contract, so
    the annotations downstream (`BuildResult.source_sha256`, `_write_release_json`) were written
    against a function that never ran, while the live one could return `None`.

    Walked across the package rather than asserted about one file, because a shadowed definition is
    silent by nature — nothing warns, and the wrong one may be the one being read.
    """
    duplicates: list[str] = []
    for module in sorted(_SRC.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        seen: set[str] = set()
        for node in tree.body:  # module level only; a method may legitimately share a name
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name in seen:
                    duplicates.append(f"{module.name}:{node.lineno}: {node.name}")
                seen.add(node.name)
    assert duplicates == [], "a later definition silently shadows an earlier one:\n" + "\n".join(
        duplicates
    )


def test_the_clinvar_digest_annotations_admit_the_none_it_can_return() -> None:
    """The half a duplicate-definition guard cannot see: the annotations it left behind."""
    from just_dna_enricher.clinvar_build import BuildResult, _sha256_file, _write_release_json

    #: `str | None` however the annotation was spelled — this module has no `from __future__ import
    #: annotations`, so `inspect` hands back the resolved type object rather than the source text.
    optional_str = str | None

    assert inspect.signature(_sha256_file).return_annotation == optional_str
    assert BuildResult.__annotations__["source_sha256"] == optional_str
    assert (
        inspect.signature(_write_release_json).parameters["source_sha256"].annotation == optional_str
    )


def test_every_pass_that_owns_a_client_closes_it_on_the_error_path() -> None:
    """`enrich_gwas` closed its client with a bare `if client is None: catalog.close()` after ~80
    lines of fetching and writing, so any exception in between leaked the httpx client. Every sibling
    pass already used `try/finally`.

    Read structurally: a pass that constructs `client or SomeClient()` must have its close inside a
    `finally`. The behavioural version would need one network double per pass, and the shape is the
    thing that was wrong.
    """
    offenders: list[str] = []
    for module in sorted(_SRC.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            owns = any(
                isinstance(sub, ast.BoolOp)
                and isinstance(sub.op, ast.Or)
                and isinstance(sub.values[0], ast.Name)
                and sub.values[0].id == "client"
                for sub in ast.walk(node)
            )
            if not owns:
                continue
            closes = [
                sub for sub in ast.walk(node)
                if isinstance(sub, ast.Attribute) and sub.attr == "close"
            ]
            if not closes:
                continue
            finalizers = [
                stmt for sub in ast.walk(node) if isinstance(sub, ast.Try) for stmt in sub.finalbody
            ]
            protected = {
                id(inner)
                for stmt in finalizers
                for inner in ast.walk(stmt)
                if isinstance(inner, ast.Attribute) and inner.attr == "close"
            }
            if any(id(c) not in protected for c in closes):
                offenders.append(f"{module.name}:{node.lineno}: {node.name}")
    assert offenders == [], (
        "a pass owning a client closes it outside `try/finally`, so an exception mid-pass leaks the "
        "connection:\n" + "\n".join(offenders)
    )


def test_the_gwas_severity_ladder_is_wired_to_something() -> None:
    """`mode` was accepted and never read while the CLI advertised `--strict` as a severity ladder.

    What `strict` escalates is deliberately **not** `missing`: the Catalog holding nothing for a
    variant is a fact about the variant (recorded as a `not_found` row) and true of most variants, so
    escalating it would refuse nearly every module. It reads the two counts that mean the artifact
    does not hold what the Catalog *did* publish.
    """
    from just_dna_enricher.gwas import GwasError, enrich_gwas

    source = inspect.getsource(enrich_gwas)
    assert 'mode == "strict"' in source, "`mode` is accepted and still never read"
    assert "result.missing" not in source.split('mode == "strict"')[1].split("\n")[0], (
        "strict must not escalate on `missing` — see the docstring"
    )
    assert issubclass(GwasError, RuntimeError)


def test_the_ncbi_credential_is_loaded_where_it_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`@credential-where-read`: a `.env`-only key must not depend on call order.

    `EutilsSettings` read `os.environ` directly, so the key reached it only as a side effect of some
    *unrelated* call resolving a cache path. The live effect was silent and threefold: the rate gate
    stayed at 1 request / 3 s instead of 10 / s. `PharmVarClient` carried the same `load_env()` call
    with a comment describing this exact failure.
    """
    from just_dna_enricher import eutils, literature

    calls: list[bool] = []
    monkeypatch.setattr(eutils, "load_env", lambda *a, **k: calls.append(True))
    monkeypatch.setattr(literature, "load_env", lambda *a, **k: calls.append(True))

    eutils.EutilsSettings()
    assert calls, "EutilsSettings did not load `.env` where it reads NCBI_API_KEY"

    calls.clear()
    literature.CrossrefClient()
    literature.PmcIdConverterClient()
    assert len(calls) == 2, "the two polite-identification clients must each load `.env`"


def test_an_empty_key_still_means_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of `@test-no-credential`, pinned rather than left to convention.

    `load_dotenv` skips a variable that is merely *present*, so `setenv(VAR, "")` is what a test means
    by "no credential" — and every reader here has to treat empty as absent for that to hold.
    """
    from just_dna_enricher.eutils import EutilsSettings

    monkeypatch.setenv("NCBI_API_KEY", "")
    assert EutilsSettings().api_key is None
    assert EutilsSettings().min_request_interval == pytest.approx(1 / 3)


def test_a_leaked_client_is_closed_when_the_gwas_pass_raises(tmp_path: Path) -> None:
    """The behavioural half of the `try/finally`, on the pass that was missing it."""
    from just_dna_enricher.gwas import GwasCatalogClient, enrich_gwas

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: g\n  title: G\n  description: d\n"
        "  report_title: G\n",
        encoding="utf-8",
    )
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs1801133,C/T,risk,x\n", encoding="utf-8"
    )

    def explode(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("egress down", request=request)

    client = GwasCatalogClient()
    client._client = httpx.Client(transport=httpx.MockTransport(explode))

    with pytest.raises(Exception):
        enrich_gwas(spec, client=client, write=False)
    # An injected client is the caller's to close, which is the branch `owned` protects — the pass
    # must not close what it did not open, and must close what it did.
    assert client._client is not None, "an injected client must not be closed by the pass"


# ── `--dry-run` means the same thing in every drafting command (RM71) ────────────────────────────
#
# The fifth surface defect of the same family, and the one RM71 tripped over: a flag that exists on
# one command and not its sibling, or exists on both meaning different things, is invisible from
# inside either. The behavioural half lives beside each provider — a dry run appends nothing and
# still reports what it would have added (`test_pgx_draft`, `test_clinvar_draft`). This half is what
# nothing else can see: that the three commands *declare* one flag rather than three.


def _dry_run_declaration(callback) -> tuple:
    """What one command's `--dry-run` promises: its spellings, its default and its help text."""
    option = inspect.signature(callback).parameters["dry_run"].default
    return tuple(option.param_decls), option.default, option.help


def test_every_drafting_command_declares_the_same_dry_run_flag() -> None:
    """Equality over the walked set, not a spot check on the pair that motivated it.

    The drafting family is read off the CLI's own registry, so a fourth provider fails this test
    until it joins the promise rather than quietly sitting outside it.
    """
    drafting = {
        (command.name or command.callback.__name__): command.callback
        for command in app.registered_commands
        if command.callback.__name__.startswith("draft")
    }
    assert set(drafting) == {"draft", "draft-panel", "draft-clinpgx"}, (
        "a new drafting command has to join this guard, not be exempted by it"
    )

    declared = {name: _dry_run_declaration(callback) for name, callback in drafting.items()}
    assert len(set(declared.values())) == 1, f"the flag means different things: {declared}"

    decls, default, help_text = declared["draft"]
    assert decls == ("--dry-run",) and default is False, "opt-in, and spelled one way"
    assert "write" in help_text and "would" in help_text, (
        "the promise is 'report what would be added; write nothing' — if the wording drifts, the "
        "three have to drift together, which is what the equality above enforces"
    )
