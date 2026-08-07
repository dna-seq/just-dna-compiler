# just-dna-format

[![CI](https://github.com/dna-seq/just-dna-compiler/actions/workflows/ci.yml/badge.svg)](https://github.com/dna-seq/just-dna-compiler/actions/workflows/ci.yml)

The **module format** for just-dna annotation modules — the declarative schema/contract, its
reference compiler, and the network tier that feeds them — as a uv workspace publishing three
packages, in dependency tiers (`enricher → compiler → format`):

| Package | Path | What it is | Deps |
|---|---|---|---|
| [`just-dna-format`](schema) | `schema/` | The schema + integrity contract: the authored DSL spec, the compiled `manifest.json`, digests, identity/versioning. | pydantic + cryptography |
| [`just-dna-compiler`](compiler) | `compiler/` | The transform: a composed spec directory → a parquet artifact + `manifest.json`. Pure-Python and duckdb-free since 0.5. | + polars, pyyaml, typer |
| [`just-dna-enricher`](enricher) | `enricher/` | The network tier: produces the injected `resolution.csv` the compiler consumes, and carries the drafting/publishing surface. The **only** package that fetches. | + httpx, tenacity, huggingface-hub, duckdb, ga4gh.vrs |

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

Start at [`.claude/skills/create-module/SKILL.md`](.claude/skills/create-module/SKILL.md) — the command
order end to end, what only a human may decide, the surface of both CLIs, and the gotchas that are not
discoverable from the command output. Two companions sit beside it:
[`TABLES.md`](.claude/skills/create-module/references/TABLES.md) (which table kind a finding belongs in)
and [`SYMPTOMS.md`](.claude/skills/create-module/references/SYMPTOMS.md) (message → cause → action).

It is a Claude Code skill — invoke it with `/create-module` if you use one — but it is plain markdown
written for a human author who installed the packages from PyPI, so read it directly if you do not.
Worked modules to copy from are in [`reference_examples/`](reference_examples/), each with a README
naming what it exercises.

## Design docs

- [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) — the durable charter: goals, non-goals, and the
  invariants every release upholds (declarative-not-code, no-network, backward-compat-within-a-major,
  integrity). Amended only deliberately.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — forward-only and active-only: the open `RMn` items, the
  freeform idea-book, the reserved namespace, and the 1.0-cleanup tracker. Revised often.
  [`docs/RM_TOC.md`](docs/RM_TOC.md) indexes every item, active and shipped.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — release history, newest first.
- [`docs/SCHEMAS.md`](docs/SCHEMAS.md), [`docs/COMPILER.md`](docs/COMPILER.md),
  [`docs/ENRICHER.md`](docs/ENRICHER.md) — one reference per tier.
- [`docs/REFERENCE_EXAMPLES.md`](docs/REFERENCE_EXAMPLES.md) — the worked modules under
  [`reference_examples/`](reference_examples), each with a README naming what building it broke.
