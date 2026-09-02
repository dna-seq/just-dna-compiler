# `scripts/` — the operator-facing drivers

Shell and Python entry points a **person running a deployment** invokes. Each is a thin driver over a
CLI command that already exists: the decisions live in the package, and anything a script decided for
itself would be a second source of truth nothing tests.

| Script | What it drives |
|---|---|
| [`rebuild-caches.sh`](rebuild-caches.sh) | `just-dna-enricher cache rebuild` over every lane the registry carries — acquire, build, and with `--publish` upload. Writes each lane into `<base>/<lane>/`, never over a live cache. |

**This is not `.claude/`, and the split is by audience rather than by file type.** `.claude/` holds
**agent tooling** — the `RMn` allocator, the consumer-suggestion ledger and archiver, the suggestion
watcher — which exists to make a Claude session's work reproducible and which a deployment never
runs. A script here is the other way round: an operator runs it, and no agent needs it. Put a new one
in whichever of the two an actual reader would look in.

**Reproduction *output* is not here.** A run's working directory goes under `data/repro/<name>/`,
which the workspace git-ignores wholesale along with the rest of `data/` — `civic reproduce` defaults
there. Nothing a command generates belongs in the repository root, and a command that writes three and
a half megabytes into it used to need its own `.gitignore` line to say so.
