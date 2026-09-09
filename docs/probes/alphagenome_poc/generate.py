"""Generate the Atlas gRPC bindings from the vendored `.proto` sources.

Run it: `uv run --with grpcio-tools python docs/probes/alphagenome_poc/generate.py`

`grpcio-tools` is a **build-time** dependency and deliberately not declared anywhere: the runtime
needs only `grpcio` and `protobuf`. Output goes under `generated/`, which is git-ignored — the
`.proto` sources in `docs/vendor/alphagenome_protos/` are what the repository carries, so a
regeneration is reproducible from what is committed rather than from what a wheel happened to
ship.

Upstream builds the same bindings the same way (`hatch_build.py` calling `grpc_tools.protoc`), so
this is the wheel's own build step run against the wheel's own inputs.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
PROTO_DIR = REPO_ROOT / "docs" / "vendor" / "alphagenome_protos"
OUT_DIR = HERE / "generated"

#: Three of upstream's four. `dna_model_service.proto` drives the *model* service (predictions on
#: demand) and the Atlas surface does not import it, so it is not vendored — a blueprint that
#: carries what it does not use is a blueprint whose dependency claim cannot be checked.
PROTOS = ("atlas_service.proto", "dna_model.proto", "tensor.proto")


#: The staged package directory, and it is deliberately **not** `alphagenome/protos`.
#:
#: protoc derives a binding's Python module path from the `.proto` file's path, and the generated
#: modules then import each other **absolutely** — stage the sources at upstream's own path and the
#: bindings become a package literally named `alphagenome`, which shadows the real wheel for anyone
#: who has both installed. Worse, an absolute import only resolves if its root is on `sys.path`, so
#: the staged path is also what decides whether the client can import its own bindings without a
#: `sys.path` insertion. Both problems have the same fix: stage under the **full package path the
#: bindings will be imported by**, rooted at the repository, so the cross-imports come out as
#: `from docs.probes.alphagenome_poc.generated._alphagenome_atlas_protos import …` — unambiguous,
#: unshadowable, and importable wherever the repository root already is.
STAGE_PREFIX = "_alphagenome_atlas_protos"

#: What `import "…"` lines in the vendored sources say today. Named so the rewrite fails loudly if
#: upstream ever moves its own layout, rather than silently producing bindings that import nothing.
UPSTREAM_IMPORT_PREFIX = "alphagenome/protos/"


def generate(out_dir: Path = OUT_DIR, *, include_root: Path | None = None) -> Path:
    """Build the bindings under a private package path, from the vendored sources.

    The vendored `.proto` files stay **byte-identical to upstream** — the rewrite happens on the
    staged copies, not on what the repository carries — so re-vendoring a newer release is a diff
    rather than a merge. Only the `import "…"` lines move; the protobuf `package` declaration is
    untouched, so descriptor names and therefore the wire format are unchanged.

    `include_root` is protoc's `-I` and defaults to the repository root, which is what makes the
    generated cross-imports fully qualified. A test may point it elsewhere; the bindings are then
    importable by whatever package path that root implies.
    """
    root = include_root or REPO_ROOT
    package_dir = out_dir.relative_to(root) / STAGE_PREFIX
    staged_prefix = f"{package_dir.as_posix()}/"

    staged = root / package_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    staged.mkdir(parents=True)
    for name in PROTOS:
        source = (PROTO_DIR / name).read_text()
        rewritten = source.replace(f'import "{UPSTREAM_IMPORT_PREFIX}', f'import "{staged_prefix}')
        if UPSTREAM_IMPORT_PREFIX in source and rewritten == source:  # pragma: no cover
            raise RuntimeError(f"{name}: import rewrite did not apply")
        (staged / name).write_text(rewritten)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{root}",
            f"--python_out={root}",
            f"--grpc_python_out={root}",
            *(f"{staged_prefix}{name}" for name in PROTOS),
        ],
        check=True,
    )
    for package in (out_dir, staged):
        (package / "__init__.py").touch()
    return out_dir


if __name__ == "__main__":
    print(f"bindings written to {generate()}")
