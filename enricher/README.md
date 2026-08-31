# just-dna-enricher

The **network tier** of the just-dna workspace. It fills the source-independent resolution table
(`resolution.csv`) that `just-dna-compiler` consumes — Ensembl cache → HuggingFace snapshot → ClinVar
cache → live Ensembl (V2 GraphQL, with a V1 REST fallback on 500/503, and tenacity retries) — then
hands off to a deterministic, offline compile. The ClinVar link sits **after** the Ensembl cache so a
variant both references know keeps its Ensembl `alts`/`source` and no already-compiled module's digest
moves; it is a complementary reference that makes an offline clinical enrich possible without the
14 GB dbSNP cache.

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
just-dna-enricher clinvar build --vcf clinvar.vcf.gz --out cv/   # build the ClinVar snapshot ([dev])
just-dna-enricher clinvar publish cv/              # create-or-update datasets/anon-org/clinvar
```

**Publisher / `[dev]` surface.** Snapshot *download* is part of the runtime enrich chain; the
publisher half is *upload* — pushing a compiled module (parquet + manifest) or a built ClinVar
reference snapshot (`data/*.parquet` + `release.json`) to a HuggingFace dataset repo — plus the
ClinVar *builder* (`clinvar build`, which needs `polars`). Install it explicitly:

```
pip install 'just-dna-enricher[dev]'
# or, in this workspace:
uv sync --package just-dna-enricher --group dev
```

Downstream repos (ensembl-mcp, just-dna-lite/pipelines) adopt this package as the single source of
truth for variant resolution instead of maintaining their own query/download code. Lite's
`pipelines v1-port publish` still has a local copy until it adopts the 0.5 enricher tier; the
canonical publisher API is ``just_dna_enricher.upload``.
