"""Generate the Atlas gRPC bindings from the vendored `.proto` sources (RM192).

Run it as `just-dna-enricher atlas generate`, or directly::

    uv run --with grpcio-tools python -m just_dna_enricher.atlas_protos

`grpcio-tools` is a **build-time** dependency and lives in `[dev]`: the runtime needs only `grpcio`
and `protobuf`, which is the whole claim RM192 rests on. Output goes under `generated/`, which is
git-ignored — the `.proto` sources in `docs/vendor/alphagenome_protos/` are what the repository
carries, so a regeneration is reproducible from what is committed rather than from what a wheel
happened to ship.

Upstream builds the same bindings the same way (`hatch_build.py` calling `grpc_tools.protoc`), so
this is the wheel's own build step run against the wheel's own inputs.

**The generated tree is not in the sdist or the wheel**, and that is RM196 rather than an oversight:
`pip install just-dna-enricher[atlas]` gets `grpcio` and `protobuf` but no bindings and no service
config, so `atlas_client` raises its guarded ImportError until this module has been run from a
checkout. Whether the repository should commit generated code or generate at build time is a
maintainer decision, and this round files it instead of picking one.
"""

import shutil
import subprocess
import sys
from pathlib import Path

#: `…/enricher/src/just_dna_enricher/atlas_protos.py` → the package, `src`, `enricher`, the checkout.
_HERE = Path(__file__).resolve().parent
SRC_ROOT = _HERE.parent
REPO_ROOT = _HERE.parents[2]

#: Upstream source, kept where `docs/vendor/` keeps every other upstream file. Absent in an installed
#: wheel, which is what `_missing_sources` reports and RM196 tracks.
PROTO_DIR = REPO_ROOT / "docs" / "vendor" / "alphagenome_protos"

#: Where the bindings land, and the import root the generated cross-imports resolve against.
OUT_DIR = _HERE / "generated"

#: Three of upstream's four. `dna_model_service.proto` drives the *model* service (predictions on
#: demand) and the Atlas surface does not import it, so it is not vendored — a client that carries
#: what it does not use is a client whose dependency claim cannot be checked.
PROTOS = ("atlas_service.proto", "dna_model.proto", "tensor.proto")

#: Upstream's own retry/backoff policy, vendored beside the protos and handed to the channel. Copied
#: into `generated/` rather than read from `docs/vendor/`: the client must find it at runtime, and
#: an installed package has no `docs/` tree. One directory the runtime needs, not two.
SERVICE_CONFIG_NAME = "grpc_service_config.json"

#: The staged package directory, and it is deliberately **not** `alphagenome/protos`.
#:
#: protoc derives a binding's Python module path from the `.proto` file's path, and the generated
#: modules then import each other **absolutely** — stage the sources at upstream's own path and the
#: bindings become a package literally named `alphagenome`, which shadows the real wheel for anyone
#: who has both installed. Worse, an absolute import only resolves if its root is on `sys.path`, so
#: the staged path is also what decides whether the client can import its own bindings without a
#: `sys.path` insertion. Both problems have the same fix: stage under the **full package path the
#: bindings will be imported by**, rooted at `enricher/src`, so the cross-imports come out as
#: `from just_dna_enricher.generated._alphagenome_atlas_protos import …` — unambiguous,
#: unshadowable, and importable wherever the package itself already is.
STAGE_PREFIX = "_alphagenome_atlas_protos"

#: What `import "…"` lines in the vendored sources say today. Named so the rewrite fails loudly if
#: upstream ever moves its own layout, rather than silently producing bindings that import nothing.
UPSTREAM_IMPORT_PREFIX = "alphagenome/protos/"


def missing_sources(proto_dir: Path = PROTO_DIR) -> tuple[str, ...]:
    """Which vendored inputs are absent — the answer an installed wheel gives for all of them.

    Returned rather than raised so a caller can tell "you are running from a wheel" (everything
    missing) from "upstream renamed a file" (one missing), which are different remedies.
    """
    if not proto_dir.is_dir():
        return (*PROTOS, SERVICE_CONFIG_NAME)
    return tuple(
        name for name in (*PROTOS, SERVICE_CONFIG_NAME) if not (proto_dir / name).is_file()
    )


def generate(out_dir: Path = OUT_DIR, *, include_root: Path | None = None) -> Path:
    """Build the bindings under a private package path, from the vendored sources.

    The vendored `.proto` files stay **byte-identical to upstream** — the rewrite happens on the
    staged copies, not on what the repository carries — so re-vendoring a newer release is a diff
    rather than a merge. Only the `import "…"` lines move; the protobuf `package` declaration is
    untouched, so descriptor names and therefore the wire format are unchanged.

    `include_root` is protoc's `-I` and defaults to `enricher/src`, which is what makes the
    generated cross-imports read `just_dna_enricher.generated…`. A test may point it elsewhere; the
    bindings are then importable by whatever package path that root implies.
    """
    absent = missing_sources()
    if absent:
        raise FileNotFoundError(
            f"the vendored Atlas sources are not here: {', '.join(absent)} missing from "
            f"{PROTO_DIR}. Generation needs the repository checkout; an installed package carries "
            "no docs/vendor tree (RM196)."
        )
    root = include_root or SRC_ROOT
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
    # The channel reads this at connect time, so it has to sit where the runtime looks rather than
    # where the repository keeps upstream files.
    shutil.copyfile(PROTO_DIR / SERVICE_CONFIG_NAME, out_dir / SERVICE_CONFIG_NAME)
    return out_dir


if __name__ == "__main__":
    print(f"bindings written to {generate()}")
