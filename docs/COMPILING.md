# Compile a module

A spec directory in, a parquet artifact plus `manifest.json` out. This page is the operator's order of
operations; [COMPILER.md](COMPILER.md) is the reference behind it — the validation ceiling, the full
pipeline, the resolution matrix and the warning-text catalogue a consumer greps.

## The spec directory

```text
my_module/
├── module_spec.yaml     the header: title, name, genome_build, defaults
├── variants.csv         one CSV per table kind — only the kinds you use
├── weights.csv
├── resolution.csv       injected by the enricher, not authored by hand
└── sources.csv          who the data came from and what you may do with it
```

**One CSV = one concern.** A module includes only the table kinds it needs; there is no schema where
a PGx module carries GWAS columns on every row. `just-dna-compiler template <kind>` prints a
header-only CSV generated from the live models, and `requirements <kind>` says what you must supply:

```bash
just-dna-compiler template repeat_alleles.csv > repeat_alleles.csv   # requirements go to stderr
just-dna-compiler requirements variants.csv
just-dna-compiler scaffold ./my_module      # the whole directory, stubs included; never overwrites
```

`describe <kind>` emits the full machine description — columns, options, requirements — and
`reference` prints the authoring reference for every model at once. Those four commands are the
schema's own voice; a hand-written column table beside them goes stale on the next release.

## Validate first

```bash
just-dna-compiler validate ./my_module
```

`validate` refuses everything `compile` refuses, except the checks that need resolved coordinates, and
it writes nothing. Use it as the fast loop while authoring.

`hint` is the other read-only tool and the more interesting one: it inspects your authored rows and
reports what is wrong, what the model will rewrite, and **what is deliberately left to you**. It writes
nothing — the corrected text goes to stdout for you to use or ignore.

```bash
just-dna-compiler hint ./my_module
```

A hint never fills a cell that a cross-examining check reads. That is not a limitation to work around;
a tool that filled it would be manufacturing the agreement the check exists to test.

## Compile

```bash
just-dna-compiler compile ./my_module ./out
```

| Flag | What it does |
|---|---|
| `--strict` | all-or-nothing: refuse rather than emit an artifact with unresolved positions |
| `--no-resolve` | do not use the injected `resolution.csv` at all |
| `--compression` | parquet codec, default `zstd`. Changes `artifact.digest`, never `content_signature` |
| `--compiled-by` | the provenance tag `verify` checks by default (e.g. `marketplace-server`) |
| `--strip-identity` / `--authority-key` | drop authority-owned identity keys on the way out |

The compiler **never reaches the network** (Principle 2). Every coordinate it did not get from you
came out of the injected `resolution.csv`; with nothing injected it skips resolution and says so in a
warning rather than going to look.

### What `--strict` actually decides

`--strict` is about *unresolved rows*, not about warnings in general. Most checks report in both
modes, because a report and a refusal answer different questions — and a few are documented as
**never** escalating under strict, the ClinVar `clin_sig` cross-check among them: a source re-curating
its own call is not grounds to refuse someone else's build.

Where the compiler cannot establish something, it withholds. It does not guess, and it does not write
the opposite value.

## Read the manifest

```json
{
  "artifact": {
    "digest": "sha256:7a4fb1…",
    "files": [{"name": "haplotypes.parquet", "sha256": "sha256:a9367c…", "size": 4086}]
  },
  "content_signature": "sha256:343333…",
  "compilation": {
    "compile_success": true,
    "compiled_by": null,
    "compiler_version": "just-dna-compiler 0.7.0",
    "warnings": ["…"]
  }
}
```

Every warning the compile emitted is carried into `compilation.warnings`, so the consumer reads the
same sentence you did. Those texts are an API — they are catalogued in
[COMPILER.md § Warning texts](COMPILER.md) precisely because integrations grep them.

## Sign it

```bash
just-dna-compiler keygen --out ./keys/private.pem   # unencrypted PKCS#8; refuses to overwrite
just-dna-compiler sign ./out --private-key ./keys/private.pem
just-dna-compiler verify ./out --public-key <base64-raw-public>
```

The signature covers `artifact.digest`, which covers every file's hash. Signing is the last step,
because anything that rewrites a parquet invalidates it.

## Close the authoring phase

```bash
just-dna-compiler close ./my_module --by "your name" --private-key ./keys/private.pem
```

Authoring has an end. `close` writes a `closure` block into the module's `verification.json`, naming
the hash of `module_spec.yaml` and the authored CSVs **as they stand right now**, with newlines
normalized. Edit any of them afterwards and the hash moves, the compiler drops the closure, and the
module is open again. That is the point.

Three things about it worth knowing before you run it:

- **`validate` will never do it for you**, however cleanly it passes. A record stamped by whatever
  happened to run says only that something ran.
- **`--private-key` is what turns *someone closed this* into *this party closed this***, using the same
  key `sign` uses on a compiled artifact.
- **It refuses on a spec that does not validate, and does not refuse on warnings.** An unresolved rsID
  or an ungrounded threshold is a legitimate state to call finished.

`reverse` deliberately refuses to reproduce somebody else's closure into a spec it reconstructed — it
holds no authority to declare another party's work finished, and it says so at the time.

## Reverse and recompile

```bash
just-dna-compiler reverse ./out ./spec-again
just-dna-compiler compile ./spec-again ./out-again    # reproduces ./out
```

`compile → reverse → compile` reproduces the module, or `--strict` refuses. That is charter Principle
7 and it is pinned by tests, which is what makes an artifact a safe thing to edit: you can always get
the authored form back.

Row **order** is preserved through the round trip because parquet bytes depend on it. Column order and
cell formatting are normalized rather than preserved — that asymmetry is intended.

## Where to go next

- **[COMPILER.md](COMPILER.md)** — the reference: validation ceiling, pipeline, resolution matrix,
  deterministic ordering, every warning text.
- **[Resolve, draft and enrich](ENRICHING.md)** — producing the `resolution.csv` this page injects.
- **[CLI reference](https://just-dna.life/just-dna-compiler/cli/)** — every command and
  flag, generated from the tools themselves. It is written at build time from the live command tree,
  so it exists on the site and not in this repository.
