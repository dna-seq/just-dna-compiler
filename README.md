# just-dna-format

[![CI](https://github.com/dna-seq/just-dna-format/actions/workflows/ci.yml/badge.svg)](https://github.com/dna-seq/just-dna-format/actions/workflows/ci.yml)

The **module format** for just-dna annotation modules — the declarative schema/contract, its
reference compiler, and the network tier that feeds them — as a uv workspace publishing three
packages, in dependency tiers (`enricher → compiler → format`):

| Package | Path | What it is | Deps |
|---|---|---|---|
| [`just-dna-format`](schema) | `schema/` | The schema + integrity contract: the authored DSL spec, the compiled `manifest.json`, digests, identity/versioning. | pydantic + cryptography |
| [`just-dna-compiler`](compiler) | `compiler/` | The transform: a composed spec directory → a parquet artifact + `manifest.json`. Pure-Python and duckdb-free since 0.5. | + polars, pyyaml, typer |
| [`just-dna-enricher`](enricher) | `enricher/` | The network tier: produces the injected `resolution.csv` the compiler consumes, and carries the drafting/publishing surface. The **only** package that fetches. | + httpx, tenacity, huggingface-hub, duckdb, ga4gh.vrs, platformdirs, python-dotenv |

**Why three packages, one repo.** `just-dna-format` stays dependency-light so *anyone* — a thin API,
a webui client, a downloader that only verifies a digest — can depend on it for the cost of
`pydantic` (+ `cryptography`, for Ed25519 signature verification). `just-dna-compiler` adds the
transform and nothing that reaches the network. Fetching, HuggingFace and every source convention
live in `just-dna-enricher`, which depends inward, so its weight never enters the compile path
(CONSTITUTION Goal 2 + the 0.5 amendment). Consumers pick the tier they need:

- verify-only client → `just-dna-format`
- compile / recompile (marketplace, pipelines) → `just-dna-compiler` (pulls `just-dna-format`)
- resolve, draft from a source, publish → `just-dna-enricher` (pulls both)
- none of them pulls Dagster or LLM SDKs — those stay in `just-dna-pipelines`.

Co-locating them keeps the schema and the compiler that targets it in one place (no cross-repo
fetch to understand the contract), while uv still builds and publishes three independent
distributions.

## Develop

```bash
uv sync              # installs all three members + dev tools into one workspace venv
uv run pytest        # runs the schema/, compiler/ and enricher/ suites
```

Build all distributions: `uv build --all-packages`.

## Authoring a module

Authoring is `just-module-creator`'s job — its `/create-module` skill is the door into the stage
skills that scaffold, draft, curate, enrich, compile and publish a module against these packages.
This repository documents the *format*; worked modules to copy from are in
[`reference_examples/`](reference_examples/), each with a README naming what it exercises.

## Design docs

Start with the charter, then the roadmap, then the tier your task touches. `CLAUDE.md` carries the
full map of `docs/` with a grep hint per file.

- [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) — the durable charter: nine principles, goals and
  non-goals, rules only. Wins over any plan; the reasoning behind each amendment is in
  [`CONSTITUTION_AMENDMENTS_HISTORY.md`](docs/CONSTITUTION_AMENDMENTS_HISTORY.md).
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — open items only, plus the idea-book and the reserved-namespace
  and 1.0-cleanup trackers. Deferred items sit in [`ROADMAP_0_8.md`](docs/ROADMAP_0_8.md) and
  [`ROADMAP_1_0.md`](docs/ROADMAP_1_0.md), shipped ones with their rationale in
  [`ROADMAP_HISTORY.md`](docs/ROADMAP_HISTORY.md); [`RM_TOC.md`](docs/RM_TOC.md) indexes every item.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — what shipped, newest first.
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md), [`docs/COMPILER.md`](docs/COMPILER.md),
  [`docs/ENRICHER.md`](docs/ENRICHER.md) — one reference per tier.
- [`docs/MODULE_LIFECYCLE.md`](docs/MODULE_LIFECYCLE.md) — origin → publish → a consumer's join, and
  what a second pass moves.
- [`docs/INTEGRATION_0_7.md`](docs/INTEGRATION_0_7.md) — the surface delta a consumer upgrading from
  0.6.6 checks against (0.5.4 → 0.6 is [`INTEGRATION_0_6.md`](docs/INTEGRATION_0_6.md)).
- [`docs/FAQ.md`](docs/FAQ.md) — settled questions, most of them a repair somebody proposed that was
  checked and refused.
- [`docs/USE_CASES.md`](docs/USE_CASES.md) → [`docs/REFERENCE_EXAMPLES.md`](docs/REFERENCE_EXAMPLES.md)
  — the same use cases as questions and as answers; the latter indexes the worked modules under
  [`reference_examples/`](reference_examples), each with a README naming what building it broke.
- [`docs/AGENT_NOTES.md`](docs/AGENT_NOTES.md) — the long-form gotcha book behind `CLAUDE.md`'s one-line
  rules.
- [`docs/CONSUMER_SUGGESTIONS.md`](docs/CONSUMER_SUGGESTIONS.md) — the open inbox for consumer repos
  (empty means nothing is owed); answered items and the runbook sit beside it.
- `docs/proposals/`, `docs/probes/`, `docs/history/`, `docs/audit/` — closed design threads, probe
  rounds, the pre-0.6 halves of the history files, and a dated code-first re-derivation. Records,
  not contracts.

Operator drivers live in [`scripts/`](scripts/README.md); everything a command generates lands under
`data/`, which is git-ignored whole.
