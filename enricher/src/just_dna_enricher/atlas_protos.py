"""Fetch the Atlas `.proto` sources and generate the gRPC bindings from them (RM192, RM196).

**The repository carries neither the sources nor the bindings, and that is the point.** Both are
upstream's, both are reproducible from a pinned commit, and a copy of somebody else's file in a
repository is a copy that goes stale silently. What is committed is the *pin* — a commit id and a
sha256 per file, below — which is what makes a fetch verifiable rather than merely convenient.

Three stages, and each has its own failure:

1. **Resolve.** `fetch_protos()` downloads the five files from `google-deepmind/alphagenome` at
   `UPSTREAM_COMMIT` and checks each against `UPSTREAM_SHA256`. A hash mismatch is a refusal, not a
   warning: the whole reason to pin a commit *and* a digest is that a commit id proves what git had
   and a digest proves what arrived.
2. **Generate.** `generate()` stages the sources under a private package path, rewrites their
   `import "…"` lines to match, and runs `protoc`. The rewrite is the safety property — see
   `STAGE_PREFIX`.
3. **Build.** `enricher/hatch_build.py` runs both at wheel-build time, so a released artifact
   carries the sources *and* the bindings even though the repository carries neither. The protos are
   git-ignored and deliberately **not** build-ignored.

Run it as `just-dna-enricher atlas generate`, or directly::

    uv run --with grpcio-tools python -m just_dna_enricher.atlas_protos

`grpcio-tools` is build-time only and lives in `[dev]`; the runtime needs `grpcio` and `protobuf`,
which is the claim RM192 rests on.
"""

import hashlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

#: `…/enricher/src/just_dna_enricher/atlas_protos.py` → the package, then `src`.
_HERE = Path(__file__).resolve().parent
SRC_ROOT = _HERE.parent

#: The upstream commit the pins below were taken from. Apache-2.0, and the same tree the wheel
#: generates its own bindings from.
UPSTREAM_REPO = "google-deepmind/alphagenome"
UPSTREAM_COMMIT = "aa6fc8f6faadcb8c910fa2b85b57386fbd5c7b5d"
#: Three of upstream's four. `dna_model_service.proto` drives the *model* service and the Atlas
#: surface does not import it, so it is not fetched — a client that carries what it does not use is
#: a client whose dependency claim cannot be checked.
PROTOS = ("atlas_service.proto", "dna_model.proto", "tensor.proto")

#: Upstream's own retry/backoff policy, handed to the channel at connect time.
SERVICE_CONFIG_NAME = "grpc_service_config.json"

#: The licence the fetched files are under. Travels with them into the wheel, because a build
#: artifact carrying somebody's Apache-2.0 source carries their notice too.
#: Deliberately outside hatchling's `LICEN[CS]E*` glob, and the reason is metadata rather than a
#: name clash. Hatchling collects licence files for the **package's own** `License-File` metadata, so
#: a fetched file called `LICENSE` is both added twice (the build fails outright) and, worse,
#: advertised as `just-dna-enricher`'s licence — which it is not. This is upstream's notice,
#: travelling with upstream's source because Apache-2.0 requires it to.
LICENSE_NAME = "alphagenome_apache-2.0.txt"

#: Where each pinned file lives in that tree. Per file rather than one directory, because they are
#: not all in one: the protos and the service config sit under `src/alphagenome/protos/` and the
#: Apache-2.0 `LICENSE` is at the repository root. A single-directory assumption 404s on the licence,
#: which is how this was found.
UPSTREAM_PATHS = {
    "atlas_service.proto": "src/alphagenome/protos/atlas_service.proto",
    "dna_model.proto": "src/alphagenome/protos/dna_model.proto",
    "tensor.proto": "src/alphagenome/protos/tensor.proto",
    SERVICE_CONFIG_NAME: "src/alphagenome/protos/grpc_service_config.json",
    LICENSE_NAME: "LICENSE",
}

#: sha256 per file at `UPSTREAM_COMMIT`. **A commit id says what git had; a digest says what
#: arrived.** Both, because the fetch goes over HTTPS to a CDN and the pin is worth exactly what it
#: can be checked against — this is the same reason `SourceRow.license_sha256` exists.
UPSTREAM_SHA256 = {
    "atlas_service.proto": "037e8ca50171582db7bf63780e87cb37d8dfeb2c078573412bdd71c0d69f1ed9",
    "dna_model.proto": "cce623263fe102712673d79ed861a07388b9841ef8bf310edc9f0d9f1154f6d9",
    "tensor.proto": "07779023b2868377cbfc3c2ce96cd266ae425a0a1116aea755691c263d6238f7",
    SERVICE_CONFIG_NAME: "b0ec8e9ff7447a43f98a73822b23c243ef2bdd0063b0720362c9f82d80508d12",
    LICENSE_NAME: "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
}

#: Where the fetched sources land: **git-ignored, and deliberately not build-ignored.** The
#: repository stays free of somebody else's files while a released sdist or wheel carries them, so a
#: consumer building from source needs neither network nor this module's opinion about upstream.
PROTO_DIRNAME = "_atlas_protos"
PROTO_DIR = _HERE / PROTO_DIRNAME

#: Where the bindings land, and the import root their cross-imports resolve against.
OUT_DIR = _HERE / "generated"

#: The staged package directory, and it is deliberately **not** `alphagenome/protos`.
#:
#: protoc derives a binding's module path from the `.proto` file's path, and the generated modules
#: then import each other **absolutely** — stage the sources at upstream's own path and the bindings
#: become a package literally named `alphagenome`, which shadows the real wheel for anyone who has
#: both installed and fails with an import error far from its cause. Staging under the full package
#: path instead makes the cross-imports read
#: `from just_dna_enricher.generated._alphagenome_atlas_protos import …` — unambiguous,
#: unshadowable, and importable without a `sys.path` insertion.
#:
#: **No off-the-shelf build plugin does this.** `hatch-protobuf` was measured against it on
#: 2026-09-10: its options are `generate_grpc`, `generate_pyi`, `generators`,
#: `import_site_packages`, `library_paths`, `output_path` and `proto_paths`, and none rewrites an
#: import. That is why the build hook is thirty lines of our own rather than a dependency.
STAGE_PREFIX = "_alphagenome_atlas_protos"

#: What `import "…"` lines in the upstream sources say. Named so the rewrite fails loudly if
#: upstream moves its own layout, rather than silently producing bindings that import nothing.
UPSTREAM_IMPORT_PREFIX = "alphagenome/protos/"

_RAW = "https://raw.githubusercontent.com"


class ProtoFetchError(RuntimeError):
    """The pinned sources could not be obtained, or arrived as something else."""


def _url(name: str) -> str:
    return f"{_RAW}/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}/{UPSTREAM_PATHS[name]}"


def missing_sources(proto_dir: Path | None = None) -> tuple[str, ...]:
    """Which pinned files are not on disk yet. Empty means `generate()` can run offline."""
    directory = proto_dir or PROTO_DIR
    if not directory.is_dir():
        return tuple(UPSTREAM_SHA256)
    return tuple(name for name in UPSTREAM_SHA256 if not (directory / name).is_file())


def fetch_protos(proto_dir: Path | None = None, *, force: bool = False) -> Path:
    """Download the pinned sources, verifying each against its digest. Idempotent.

    A file already on disk **and matching its pin** is left alone, so a build is offline after the
    first run and a developer's checkout does not re-fetch on every wheel. A file on disk that does
    *not* match is re-fetched rather than trusted: the only thing worse than no pin is a pin nobody
    acts on.
    """
    directory = proto_dir or PROTO_DIR
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in UPSTREAM_SHA256.items():
        target = directory / name
        if not force and target.is_file() and _digest(target) == expected:
            continue
        try:
            with urllib.request.urlopen(_url(name), timeout=60) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProtoFetchError(
                f"could not fetch {name} from {UPSTREAM_REPO}@{UPSTREAM_COMMIT[:7]}: {exc}. "
                "The Atlas sources are not vendored in this repository (RM196); a build needs "
                "network once, and then never again."
            ) from exc
        got = hashlib.sha256(payload).hexdigest()
        if got != expected:
            raise ProtoFetchError(
                f"{name} does not match its pin: expected {expected}, got {got}. A commit id says "
                "what git had and a digest says what arrived; they disagree, so nothing is written."
            )
        target.write_bytes(payload)
    return directory


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(
    out_dir: Path | None = None,
    *,
    include_root: Path | None = None,
    proto_dir: Path | None = None,
) -> Path:
    """Build the bindings under a private package path, from the pinned sources.

    The fetched `.proto` files stay **byte-identical to upstream** — the rewrite happens on staged
    copies — so a re-pin is a diff against a known digest rather than a merge. Only the `import "…"`
    lines move; the protobuf `package` declaration is untouched, so descriptor names, and therefore
    the wire format, are unchanged.
    """
    out = out_dir or OUT_DIR
    sources = proto_dir or PROTO_DIR
    absent = missing_sources(sources)
    if absent:
        fetch_protos(sources)

    root = include_root or SRC_ROOT
    package_dir = out.relative_to(root) / STAGE_PREFIX
    staged_prefix = f"{package_dir.as_posix()}/"

    staged = root / package_dir
    if out.exists():
        shutil.rmtree(out)
    staged.mkdir(parents=True)
    for name in PROTOS:
        source = (sources / name).read_text()
        rewritten = source.replace(f'import "{UPSTREAM_IMPORT_PREFIX}', f'import "{staged_prefix}')
        if UPSTREAM_IMPORT_PREFIX in source and rewritten == source:  # pragma: no cover
            raise ProtoFetchError(f"{name}: import rewrite did not apply")
        (staged / name).write_text(rewritten)

    try:
        subprocess.run(
            [
                sys.executable, "-m", "grpc_tools.protoc",
                f"-I{root}", f"--python_out={root}", f"--grpc_python_out={root}",
                *(f"{staged_prefix}{name}" for name in PROTOS),
            ],
            check=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - grpcio-tools absent
        raise ProtoFetchError(
            "grpcio-tools is not installed. It is build-time only and lives in the [dev] group: "
            "`uv sync` from a checkout, or `pip install grpcio-tools`."
        ) from exc

    for package in (out, staged):
        (package / "__init__.py").touch()
    # The channel reads this at connect time, so it sits where the runtime looks rather than where
    # the sources happen to have been fetched to.
    shutil.copyfile(sources / SERVICE_CONFIG_NAME, out / SERVICE_CONFIG_NAME)
    shutil.copyfile(sources / LICENSE_NAME, out / LICENSE_NAME)
    return out


if __name__ == "__main__":
    print(f"bindings written to {generate()}")
