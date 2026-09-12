# just-dna-format

A **just-dna annotation module** is a small, self-describing bundle of lookup tables: which variants
matter, what each one means, where the claim came from, and who may redistribute it. This site
documents the format those modules are written in, the compiler that turns an authored spec into a
verifiable artifact, and the network tier that fills in what an author could not know by hand.

A module carries **annotation only** — tables and bounded rules. It holds no sample data, no genotype
under test and no measured value; the consumer supplies the measurement at query time.

## Pick the tier you need

Three packages, published from one workspace, each depending inward. Install the smallest one that
answers your question.

| I want to… | Install | Weight |
|---|---|---|
| Read a compiled module, check its digest, verify a signature | `just-dna-format` | pydantic + cryptography |
| Compile a spec into an artifact, or reverse one back | `just-dna-compiler` | + polars, pyyaml, typer |
| Resolve coordinates, draft rows from a source, publish | `just-dna-enricher` | + httpx, huggingface-hub, duckdb, … |

```bash
uv add just-dna-format        # or just-dna-compiler, or just-dna-enricher
```

`just-dna-compiler` pulls `just-dna-format`; `just-dna-enricher` pulls both. Nothing below the
enricher ever reaches the network, so a verify-only client stays light and a compile is reproducible
offline.

## Start here

<div class="grid cards" markdown>

-   **[Install and first run](GETTING_STARTED.md)**

    Compile a real module and verify it, in four commands.

-   **[Use a compiled module](CONSUMING.md)**

    What is inside the artifact, how to verify it, and how to join it against a genotype.

-   **[Compile a module](COMPILING.md)**

    Spec directory in, parquet plus `manifest.json` out — and what `--strict` refuses.

-   **[Resolve, draft and enrich](ENRICHING.md)**

    Where coordinates come from, how a source becomes draft rows, and what the checks report.

</div>

## Authoring a module

Writing a module from scratch is a separate tool: **`just-module-creator`**, whose `/create-module`
skill walks the scaffold → draft → curate → enrich → compile → publish stages against these packages.
This site documents the *format* those stages target.

To learn by copying, [`reference_examples/`](https://github.com/dna-seq/just-dna-compiler/tree/main/reference_examples)
collects worked modules — star alleles, repeat expansions, mitochondrial heteroplasmy, a PAR boundary,
a GRCh37 build — each with a README naming the case it exercises.

## See it work

```bash
git clone https://github.com/dna-seq/just-dna-compiler && cd just-dna-compiler
uv run just-dna-compiler compile reference_examples/apoe_epsilon /tmp/apoe
uv run just-dna-compiler verify /tmp/apoe --no-require-marketplace
```

That reads a four-file spec — a YAML header plus `haplotypes.csv`, `diplotypes.csv` and an injected
`resolution.csv` — and writes two parquet files and a `manifest.json` carrying the digests. The
[walkthrough](GETTING_STARTED.md) explains each line.
