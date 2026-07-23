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
```

Downstream repos (ensembl-mcp, just-dna-lite/pipelines) adopt this package as the single source of
truth for variant resolution instead of maintaining their own query/download code.
