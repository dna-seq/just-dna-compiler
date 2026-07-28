# just-dna-enricher

The **network tier** of the just-dna workspace. It fills the source-independent resolution table
(`resolution.csv`) that `just-dna-compiler` consumes — cache → HuggingFace snapshot → live Ensembl
(V2 GraphQL, with a V1 REST fallback on 500/503, and tenacity retries) — then hands off to a
deterministic, offline compile.

It is the **only** package in the workspace allowed to fetch: `just-dna-format` and
`just-dna-compiler` stay strictly inject-only (CONSTITUTION Goal 2 + the 0.5 amendment). The
dependency arrow points inward — `enricher → compiler → format` — so `httpx` / `huggingface_hub`
never enter the compile path.

```
just-dna-enricher enrich spec/ --strict            # write spec/resolution.csv
just-dna-enricher enrich spec/ --offline           # cache-only, zero egress
just-dna-enricher enrich-and-compile spec/ out/    # enrich, then compile from resolution.csv
just-dna-enricher upload out/coronary --dry-run    # publisher surface ([dev]): plan an HF upload
just-dna-enricher upload out/coronary              # upload compiled artifacts to the HF collection
```

**Publisher / `[dev]` surface.** Snapshot *download* is part of the runtime enrich chain;
module *upload* (pushing compiled parquet + manifest to a HuggingFace dataset collection) is the
author/publisher half. Install it explicitly:

```
pip install 'just-dna-enricher[dev]'
# or, in this workspace:
uv sync --package just-dna-enricher --group dev
```

Downstream repos (ensembl-mcp, just-dna-lite/pipelines) adopt this package as the single source of
truth for variant resolution instead of maintaining their own query/download code. Lite's
`pipelines v1-port publish` still has a local copy until it adopts the 0.5 enricher tier; the
canonical publisher API is ``just_dna_enricher.upload``.
