# `scripts/` — the operator-facing drivers

Shell and Python entry points a **person running a deployment** invokes. Each is a thin driver over a
CLI command that already exists: the decisions live in the package, and anything a script decided for
itself would be a second source of truth nothing tests.

| Script | What it drives |
|---|---|
| [`rebuild-caches.sh`](rebuild-caches.sh) | `just-dna-enricher cache rebuild` over every lane the registry carries — acquire, build, and with `--publish` upload. Writes each lane into `<base>/<lane>/`, never over a live cache; from a checkout, pass `data/caches`. |
| [`build-dists.sh`](build-dists.sh) | `uv build --package` for every workspace member (read from `[tool.uv.workspace] members`) into a freshly wiped `dist/`, since a bare `uv build` at the workspace root fails. **Exit 3 when a wheel's non-`.py` files are over `WHEEL_NONPY_ALARM_PCT` percent of its bytes** (default 3, just above the enricher's 2.6% at 0.8.0), with those files listed: a sign that a build exclusion is missing. A share rather than a size, so growing source never trips it. Run it before `uv publish`. |
| [`check-zensical.sh`](check-zensical.sh) | Asks whether Zensical can build the docs site yet — the one measurement that would reverse the ProperDocs choice. Exit 0 still blocked, **exit 3 it can**. Ephemeral `uv run --with` install, so it cannot alter `uv.lock` or the `docs` group it probes against. Scheduled fortnightly by `.github/workflows/zensical-watch.yml`; safe to run by hand any time. |
| [`gen_api_pages.py`](gen_api_pages.py) | The docs site's home page and its API reference, written into the build. **The one file here a person does not run** — `properdocs build` does, through the `mkdocs-gen-files` plugin. It is here rather than in `.claude/` because no agent needs it either, and the only other home is a loose module in the repository root. |

**This is not `.claude/`, and the split is by audience rather than by file type.** `.claude/` holds
**agent tooling** — the `RMn` allocator, the consumer-suggestion ledger and archiver, the suggestion
watcher — which exists to make a Claude session's work reproducible and which a deployment never
runs. A script here is the other way round: an operator runs it, and no agent needs it. Put a new one
in whichever of the two an actual reader would look in.

**Build *output* is not here either.** Every builder's `--out` defaults to `data/repro/<lane>/`
(`civic reproduce` to `data/repro/civic_reproduce/`), which the workspace git-ignores wholesale along
with the rest of `data/`; the default comes from one `locations.repro_out` and a test refuses a builder
that spells its own. Nothing a command generates belongs in the repository root, and a command that
wrote three and a half megabytes into it once needed its own `.gitignore` line to say so.
