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


def test_every_atlas_client_import_is_guarded_against_every_failure() -> None:
    """A module-scope `atlas_client` import must survive an absent client AND an unusable one.

    Walked rather than listed, because the fault escaped through `alphagenome_check` and then through
    `expression` — a second guard nobody had looked at, found only because the first was fixed — and
    then, with both catching `(ImportError, RuntimeError)`, through protobuf's `VersionError`, which
    is neither (S107, RM254). So the handler is no longer a set of names each guard spells for
    itself: it is `ATLAS_IMPORT_FAILURES`, bound once in `atlas_protos`, and every guard — module
    scope or the lazy one inside `_atlas_client_or_none` — must name it.
    """
    problems: list[str] = []
    # Recursive since RM260 made `cli` and `enrich` packages; `generated/` is protoc output, not ours.
    for module in sorted(p for p in _SRC.rglob("*.py") if "generated" not in p.relative_to(_SRC).parts):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        guarded: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            imports = [
                stmt
                for stmt in node.body
                if isinstance(stmt, ast.ImportFrom) and (stmt.module or "").endswith("atlas_client")
            ]
            if not imports:
                continue
            guarded.update(id(stmt) for stmt in imports)
            caught = {
                name.id
                for handler in node.handlers
                if handler.type is not None
                for name in ast.walk(handler.type)
                if isinstance(name, ast.Name)
            }
            if "ATLAS_IMPORT_FAILURES" not in caught:
                problems.append(
                    f"{module.name}:{imports[0].lineno}: guard catches {sorted(caught)}, not "
                    f"`ATLAS_IMPORT_FAILURES` — the bindings raise three different types when they "
                    f"cannot load, and a guard spelling its own subset has let one through twice"
                )
        for stmt in tree.body:
            if isinstance(stmt, ast.ImportFrom) and (stmt.module or "").endswith("atlas_client"):
                problems.append(
                    f"{module.name}:{stmt.lineno}: imports atlas_client at module scope without a "
                    f"try/except, so an unusable optional extra kills every command in this tier"
                )
    assert not problems, "\n".join(problems)


def test_the_failure_tuple_names_protobufs_own_error() -> None:
    """`VersionError` subclasses `Exception` directly; a tuple without it is the S107 hole."""
    from just_dna_enricher.atlas_protos import ATLAS_IMPORT_FAILURES

    assert ImportError in ATLAS_IMPORT_FAILURES and RuntimeError in ATLAS_IMPORT_FAILURES
    try:
        from google.protobuf.runtime_version import VersionError
    except ImportError:
        return
    assert VersionError in ATLAS_IMPORT_FAILURES
    assert not issubclass(VersionError, (ImportError, RuntimeError)), "then the old guards would have held"


def test_the_protobuf_floor_is_the_gencode_stamp() -> None:
    """The grpcio rule again, for protobuf: `protoc` stamps the protobuf it generated against into
    `atlas_service_pb2.py`, whose first statement refuses an older runtime. A floor below the stamp
    lets a co-install pinning `protobuf<7` resolve and die at import (S107)."""
    from just_dna_enricher.atlas_protos import gencode_protobuf_version

    op, floor = _requirement(_PYPROJECT["project"]["optional-dependencies"]["atlas"], "protobuf")
    assert op == ">=", f"the runtime protobuf requirement is {op!r}; the house spelling is a >= floor"
    stamped = gencode_protobuf_version()
    if stamped is None:
        return  # an un-built checkout; the declaration above is still checked
    assert floor == ".".join(map(str, stamped)), (
        f"the bindings were generated against protobuf {stamped} but the [atlas] floor is {floor}"
    )


def test_a_protobuf_runtime_older_than_the_gencode_does_not_kill_the_entrypoint() -> None:
    """S107 as a process: the gencode check raises `VersionError` at import, and the console
    entrypoint must still come up with the Atlas client marked unavailable. Run in a subprocess so
    the patched protobuf and the half-imported modules never reach this interpreter."""
    import subprocess
    import sys

    from just_dna_enricher.atlas_protos import gencode_protobuf_version

    if gencode_protobuf_version() is None:
        return  # no bindings to fail on
    script = (
        "from google.protobuf import runtime_version as rv\n"
        "def _refuse(*a, **k):\n"
        "    raise rv.VersionError('Detected incompatible Protobuf Gencode/Runtime versions (simulated)')\n"
        "rv.ValidateProtobufRuntimeVersion = _refuse\n"
        "import just_dna_enricher.cli\n"
        "import just_dna_enricher.alphagenome_check as a, just_dna_enricher.expression as e\n"
        "print(a.ATLAS_CLIENT_AVAILABLE, e.ATLAS_CLIENT_AVAILABLE)\n"
    )
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    assert run.stdout.split() == ["False", "False"], run.stdout


def test_the_absence_names_a_runtime_older_than_the_gencode(monkeypatch) -> None:
    """The third absence has its own sentence, with both numbers and the fix that applies."""
    import importlib.util

    from just_dna_enricher import atlas_protos

    if importlib.util.find_spec("grpc") is None or atlas_protos.gencode_protobuf_version() is None:
        return
    monkeypatch.setattr(atlas_protos, "gencode_protobuf_version", lambda entry=None: (7, 35, 1))
    monkeypatch.setattr(atlas_protos, "protobuf_runtime_version", lambda: (6, 33, 6))
    reason = atlas_protos.client_absence()
    assert reason is not None and "6.33.6" in reason and "7.35.1" in reason and "protobuf<7" in reason
    monkeypatch.setattr(atlas_protos, "protobuf_runtime_version", lambda: (7, 36, 1))
    assert atlas_protos.client_absence() is None


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
