# The Atlas `.proto` sources are not vendored here any more (RM196)

They were, until 2026-09-10. What replaced them is a **pin**: a commit id and a sha256 per file, in
[`enricher/src/just_dna_enricher/atlas_protos.py`](../../../enricher/src/just_dna_enricher/atlas_protos.py).

`fetch_protos()` downloads the five files from `google-deepmind/alphagenome` (Apache-2.0) at
`UPSTREAM_COMMIT` and refuses anything whose digest does not match. `enricher/hatch_build.py` runs
that at wheel-build time and force-includes the result, so **the repository carries the pin and the
distribution carries the files** — a consumer building from an sdist needs neither network nor a copy
of somebody else's source in our history.

**Why the change.** A vendored copy goes stale silently: upstream regenerates on every release, and
nothing in a repository notices that its copy is a release behind. A pinned digest cannot go stale
without saying so, and re-pinning is a two-line diff against a commit rather than a merge.

The rest of `docs/vendor/` is unaffected — the four terms documents and the download page are
**evidence about licensing**, which is exactly the kind of file that should be frozen in the
repository rather than re-fetched.
