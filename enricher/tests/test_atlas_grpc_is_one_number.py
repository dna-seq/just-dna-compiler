"""The Atlas bindings' grpc version is ONE number, and an unimportable client is never fatal (RM247).

**What broke.** `[build-system] requires` resolves in an environment `uv.lock` does not constrain, so
`grpcio-tools>=1.68.0` meant *the newest one on PyPI* generated the bindings. `protoc` stamps its own
version into `atlas_service_pb2_grpc.py` as `GRPC_GENERATED_VERSION`, and those bindings **raise at
import** on a runtime `grpcio` older than the stamp. With the runtime floored at `>=1.68.0` and the
generator floating to 1.84.0, the wheel could not import itself: `cli.py` reaches `atlas_client`
through two module-scope chains, so `enrich`, `draft` and `literature` — none of which touch Atlas —
died on it, and seventeen test modules failed at collection.

Two guards, because the defect had two halves and either alone leaves it reachable:

* the number is written twice in `pyproject.toml` and must agree, and the generated stamp must be it;
* every module-scope `atlas_client` import degrades on **both** exceptions an unusable optional
  dependency can raise. `except ImportError` alone is what let a `RuntimeError` through two guards in
  a row — the second one was found only after the first was fixed, which is why this is a walk rather
  than two edits.
"""

import ast
import re
import tomllib
from pathlib import Path

_ENRICHER = Path(__file__).resolve().parents[1]
_SRC = _ENRICHER / "src" / "just_dna_enricher"
_PYPROJECT = tomllib.loads((_ENRICHER / "pyproject.toml").read_text(encoding="utf-8"))

#: `name<op>version` out of a requirement string, which is all these two declarations ever are.
_REQUIREMENT = re.compile(r"^\s*(?P<name>[A-Za-z0-9._-]+)\s*(?P<op>[<>=!~]+)\s*(?P<version>[^,;\s]+)")


def _requirement(requirements: list[str], name: str) -> tuple[str, str]:
    for raw in requirements:
        match = _REQUIREMENT.match(raw)
        if match and match["name"] == name:
            return match["op"], match["version"]
    raise AssertionError(f"no {name} requirement among {requirements}")


def test_the_build_tool_is_pinned_rather_than_floored() -> None:
    """A floor here is resolved in an isolated env, so it means *newest*, which is the whole defect."""
    op, _version = _requirement(_PYPROJECT["build-system"]["requires"], "grpcio-tools")
    assert op == "==", (
        "`[build-system] requires` must PIN grpcio-tools: that environment is not constrained by "
        "uv.lock, so a floor resolves to the newest release and stamps a binding the runtime floor "
        "cannot import"
    )


def test_the_generator_pin_and_the_runtime_floor_are_the_same_number() -> None:
    """One number written twice. The runtime may be newer than the stamp, never older."""
    _op, built_with = _requirement(_PYPROJECT["build-system"]["requires"], "grpcio-tools")
    op, runtime_floor = _requirement(_PYPROJECT["project"]["optional-dependencies"]["atlas"], "grpcio")
    assert op == ">=", f"the runtime grpcio requirement is {op!r}; the house spelling is a >= floor"
    assert runtime_floor == built_with, (
        f"grpcio-tools is pinned at {built_with} but the runtime grpcio floor is {runtime_floor}: a "
        f"wheel built here would stamp bindings its own floor is allowed to be too old to import"
    )


def test_the_generated_stamp_is_that_number_when_the_bindings_exist() -> None:
    """The tree is git-ignored build output, so this asserts only when a build has produced it.

    Skipping silently on an un-built checkout is deliberate and is not a hole: the two declarations
    above are checked unconditionally, and they are what the build reads. This arm catches the case
    the declarations cannot — a generated tree left behind by an older toolchain, which is exactly
    how the defect survived a `uv sync` and presented as a mystery on one developer's machine.
    """
    stamped = _SRC / "generated" / "_alphagenome_atlas_protos" / "atlas_service_pb2_grpc.py"
    if not stamped.is_file():
        return
    _op, built_with = _requirement(_PYPROJECT["build-system"]["requires"], "grpcio-tools")
    match = re.search(r"GRPC_GENERATED_VERSION\s*=\s*'([^']+)'", stamped.read_text(encoding="utf-8"))
    assert match is not None, f"{stamped} carries no GRPC_GENERATED_VERSION"
    assert match.group(1) == built_with, (
        f"the generated bindings were stamped {match.group(1)} but grpcio-tools is pinned at "
        f"{built_with} — regenerate them (`uv sync --reinstall-package just-dna-enricher`)"
    )


def test_every_atlas_client_import_is_guarded_against_both_failures() -> None:
    """A module-scope `atlas_client` import must survive an absent client AND an unusable one.

    Walked rather than listed, because the fault escaped through `alphagenome_check` and then through
    `expression` — a second guard nobody had looked at, found only because the first was fixed. A
    third importer joins this assertion by existing.
    """

    def _atlas_imports(body: list[ast.stmt]) -> list[ast.ImportFrom]:
        # Module scope is `tree.body` and a `try:` directly in it — never `ast.walk`, which descends
        # into every function and would report the *deliberately* lazy imports inside
        # `_atlas_client_or_none` as unguarded. Those are a different mechanism and already correct.
        return [
            node
            for node in body
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("atlas_client")
        ]

    problems: list[str] = []
    for module in sorted(_SRC.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in tree.body:
            imports = _atlas_imports(node.body if isinstance(node, ast.Try) else [node])
            if not imports:
                continue
            if not isinstance(node, ast.Try):
                problems.append(
                    f"{module.name}:{imports[0].lineno}: imports atlas_client at module scope "
                    f"without a try/except, so an unusable grpcio kills every command in this tier"
                )
                continue
            caught = {
                name.id
                for handler in node.handlers
                for name in ast.walk(handler.type)
                if isinstance(name, ast.Name)
            }
            missing = {"ImportError", "RuntimeError"} - caught
            if missing:
                problems.append(
                    f"{module.name}:{imports[0].lineno}: guard catches {sorted(caught)}, missing "
                    f"{sorted(missing)} — grpc's bindings raise RuntimeError, not ImportError, when "
                    f"the runtime grpcio is older than the generator that stamped them"
                )
    assert not problems, "\n".join(problems)


def test_the_console_entrypoint_imports() -> None:
    """The one thing no other test did: import what the console script imports.

    `[project.scripts]` names `just_dna_enricher.cli:app`, and the suite reached `cli` only through
    tests that import it for their own reasons. Seventeen of them errored at collection when this
    broke, which is loud — but they errored as seventeen unrelated failures rather than as *the
    entrypoint is dead*, and nothing said the latter.
    """
    target = _PYPROJECT["project"]["scripts"]["just-dna-enricher"]
    module_path, _, attribute = target.partition(":")
    module = __import__(module_path, fromlist=[attribute])
    assert getattr(module, attribute) is not None, f"{target} resolves to nothing"
