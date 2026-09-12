# Install and first run

Four commands to compile a real module and verify it. Everything below was run against the
`reference_examples/apoe_epsilon` module in this repository; the output is quoted as it came back.

## 1. Install

Add the tier you need. Each pulls the ones beneath it, so you never install more than one.

**Read and verify** — `uv add just-dna-format`

:   The schema and integrity contract: the pydantic models for the authored spec and the compiled
    `manifest.json`, the digest helpers, and Ed25519 signature verification. No CLI — it deliberately
    ships none, because Typer would breach its pydantic-plus-cryptography dependency floor.

**Compile** — `uv add just-dna-compiler`

:   Adds the `just-dna-compiler` command. Pure-Python and network-free: it consumes an injected
    `resolution.csv` rather than looking anything up.

**Resolve and draft** — `uv add just-dna-enricher`

:   Adds `just-dna-enricher`. The only package that fetches anything, and the one that *produces* the
    `resolution.csv` the compiler consumes.

## 2. Compile a module

A spec is a directory: one `module_spec.yaml` header plus a CSV per table kind you use.
`apoe_epsilon` uses three.

```bash
uv run just-dna-compiler compile reference_examples/apoe_epsilon /tmp/apoe
```

```text
compiled: /tmp/apoe
digest: sha256:7a4fb109256dae18ba274da44468442dbca290b51ff4f63ae7c62183bc9239f0
content_signature: sha256:343333b67741bec0315d0d43d599be24647ee8162c5baeabf322c62df3190133
resolution_mode: None  fully_resolved: True (over 0 variant row(s))
```

Two digests, and they answer different questions. `digest` covers the emitted **bytes** — recompile
with a different parquet codec and it moves. `content_signature` covers the **claims** — it survives a
recompile, a column reordering and a compiler upgrade, and moves only when an authored value changes.
[Why did my digest move?](FAQ.md) is the long answer.

What landed:

```text
/tmp/apoe/
├── haplotypes.parquet
├── diplotypes.parquet
├── manifest.json
└── README.md
```

One parquet per table kind the module actually uses — a module never carries a foreign domain's
columns. `manifest.json` is the contract: identity, genome build, licence, stats, every file's
`sha256`, and the compiler's own warnings.

## 3. Verify it

```bash
uv run just-dna-compiler verify /tmp/apoe --no-require-marketplace
```

```text
verified: /tmp/apoe
digest: sha256:7a4fb109256dae18ba274da44468442dbca290b51ff4f63ae7c62183bc9239f0  files: 2
signature: absent
```

`verify` re-hashes every file, recomputes `artifact.digest` over the set, and — when you pin a key with
`--public-key` — checks the Ed25519 signature over that digest. It exits 1 on any failure, so it drops
straight into a download script.

!!! warning "`--no-require-marketplace` is not optional for a local build"

    `verify` defaults to demanding `compile_success` **and** `compiled_by=marketplace-server`, because
    its first caller was an install path that trusts one producer. A module you compiled yourself has
    `compiled_by: null` and fails with `VERIFY FAILED: compiled_by is None, expected 'marketplace-server'
    — untrusted`. That is the flag saying so, not a broken artifact.

## 4. Check a spec before compiling

`validate` runs every check `compile` runs, short of the ones that need resolved coordinates, and
writes nothing.

```bash
uv run just-dna-compiler validate reference_examples/apoe_epsilon
```

```text
  warning: VRS allele identity covers 0/2 allele(s) in resolution.csv (0%) — 2 carry no ga4gh:VA. id.
  warning:   2 allele(s): no ALT recorded, and a VRS allele id names exactly one allele
valid: reference_examples/apoe_epsilon
```

A warning is a report, never a repair — the compiler tells you what it could not establish and carries
the text into `manifest.json`'s `compilation.warnings` so a consumer sees the same sentence you did.
`compile --strict` turns the ones about unresolved positions into a refusal instead.

## Round-tripping

A compiled artifact reverses back into the authored spec, and recompiling reproduces it:

```bash
uv run just-dna-compiler reverse /tmp/apoe /tmp/apoe-spec
```

```text
reversed: /tmp/apoe-spec
```

The round trip is lossless and idempotent by charter (Principle 7) and pinned by tests. One thing does
not survive it, on purpose: an authoring **closure** is an attestation about who finished the work, so
`reverse` refuses to forge one and says so at the time.

## Where to go next

- **[Use a compiled module](CONSUMING.md)** — you have an artifact and want to query it.
- **[Compile a module](COMPILING.md)** — the flags, the gate, and what `--strict` refuses.
- **[Resolve, draft and enrich](ENRICHING.md)** — where `resolution.csv` comes from.
- **[What you can build](USE_CASES.md)** — case by case, what is enabled today and what is a gap.
