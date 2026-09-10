"""Fetch the Atlas sources and generate their bindings at build time (RM196).

**Why this file exists rather than a plugin.** The bindings must be generated with upstream's
`import "…"` lines rewritten, or the generated package is literally named `alphagenome` and shadows
the real wheel for anyone who installs both. `hatch-protobuf` was measured against that requirement
on 2026-09-10 and has no import rewriting — its options are `generate_grpc`, `generate_pyi`,
`generators`, `import_site_packages`, `library_paths`, `output_path`, `proto_paths` — so the plugin
would produce exactly the artifact the PoC's shadowing test was written to prevent. Upstream builds
its own bindings with a hatchling hook for the same reason.

**Why the backend moved for this package only.** `uv_build` has no build hook. Backends are declared
per package, so `just-dna-format` and `just-dna-compiler` are untouched; only the tier that needs to
run `protoc` changed.

The sources are git-ignored and **not** build-ignored: the repository carries a pin rather than a
copy of somebody else's files, while the sdist and wheel carry the files themselves. A consumer
building from an sdist therefore needs no network and no opinion about upstream.
"""

import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class AtlasProtoHook(BuildHookInterface):
    """Resolve the pinned `.proto` sources, then generate the bindings beside them."""

    PLUGIN_NAME = "atlas-protos"

    def initialize(self, version, build_data):
        # Imported here because a build backend runs before the package is importable in the normal
        # way; `src` on the path is what makes the pins and the rewrite one definition rather than
        # two. Everything this touches is pure standard library plus grpcio-tools.
        src = Path(self.root) / "src"
        sys.path.insert(0, str(src))
        from just_dna_enricher import atlas_protos

        atlas_protos.fetch_protos()
        atlas_protos.generate()

        # `artifacts`, not `force_include`. Both trees are git-ignored and hatchling honours VCS
        # ignores, but they also sit *inside* the declared package — so force-including them adds
        # every file twice and the build fails with "a second file is being added at the same path".
        # `artifacts` is the mechanism for exactly this shape: build-time output that lives in the
        # package tree and is deliberately absent from version control.
        build_data.setdefault("artifacts", []).extend(
            [
                f"/src/just_dna_enricher/{atlas_protos.PROTO_DIRNAME}/",
                "/src/just_dna_enricher/generated/",
            ]
        )
