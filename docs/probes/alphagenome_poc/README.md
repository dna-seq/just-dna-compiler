# A minimal AlphaGenome Atlas client — the blueprint, test-proven

**Not a shipped surface, and not adopted.** Nothing in `just-dna-enricher` imports this, it sits
outside `testpaths` so `uv run pytest` does not collect it, and no `RMn` covers it. It exists to
turn one sentence of [ALPHAGENOME_ATLAS.md § 6.2](../ALPHAGENOME_ATLAS.md) into something a test
can fail: **the Atlas service is reachable on `grpcio` + `protobuf` alone.**

That claim was first written here as *"a 22 MB client exists and is not declarable"*. Reading the
upstream repository showed the second half was wrong — `github.com/google-deepmind/alphagenome` is
Apache-2.0 and ships the `.proto` sources its own wheel generates bindings from, so the light path
is declarable after all. This directory is what that costs.

## Run it

```bash
uv run --with grpcio-tools python docs/probes/alphagenome_poc/generate.py
uv run --with grpcio-tools pytest docs/probes/alphagenome_poc/ -vvv
```

Twenty of the twenty-three tests need no network and no key. The three live ones need both
`ALPHAGENOME_API_KEY` and the repo's opt-in switch `JUST_DNA_NETWORK_TESTS=1`
(`@network-tests-optin`); they are skipped otherwise.

## What it costs

| | |
| --- | --- |
| declared runtime dependencies | **`grpcio`, `protobuf`** |
| build-time only | `grpcio-tools`, declared nowhere |
| vendored source | **28 KB** — three Apache-2.0 `.proto` files in [`docs/vendor/alphagenome_protos/`](../../vendor/alphagenome_protos/) |
| installed size | **22 MB**, against 255 MB for `uv add alphagenome` |
| decode | `struct.unpack` from the standard library — not even numpy |

## What the tests actually pin

Four of them carry the argument; the rest keep the client honest.

- **`test_imports_stay_within_the_declared_floor`** walks the client's AST and asserts its
  third-party imports are exactly `{grpc, docs}`. An AST walk rather than a `sys.modules` check,
  because by the time the module is imported another test's heavier import would already be
  resident and the assertion would pass for the wrong reason. This is what makes "22 MB, not
  255 MB" a property of the code instead of a claim in prose.
- **`test_bindings_regenerate_from_the_vendored_sources`** regenerates into a scratch directory.
  The repository carries `.proto` *sources*, not generated code, so the bindings are reproducible
  from what is committed rather than from what a wheel happened to ship.
- **`test_the_generated_bindings_do_not_shadow_the_upstream_package`** is the one that came out of
  a real mistake. protoc bakes the staged path into every cross-import, so staging at upstream's
  own `alphagenome/protos/` produces a package literally named `alphagenome` — which shadows the
  real wheel for anyone who installs both, and fails with an import error far from its cause. The
  sources are staged under the full package path instead, so the cross-imports read
  `from docs.probes.alphagenome_poc.generated._alphagenome_atlas_protos import …`: unambiguous,
  unshadowable, and importable without a `sys.path` insertion.
- **`test_the_api_reproduces_the_downloaded_file`** is the finding that matters most for adoption.
  It asserts the Atlas returns what the 88.5 GB AVI artifact contains — `raw` to 5e-6 and the
  derived `PHRED` to 1e-4 — so the download and the RPC are one source. If it ever fails, they
  have diverged and § 6.4 needs re-measuring.

## The three-valued part

The error hierarchy is not decoration. The service says no in three different ways and each has a
different remedy:

| what happened | type | remedy |
| --- | --- | --- |
| transport failed | `AtlasUnavailable` | retry |
| `REF` disagrees with GRCh38 | `AtlasRefMismatch` | fix the caller's data — and the server names the real base |
| an indel | `AtlasNotScored` | none: the answer does not exist |

`AtlasNotScored` deliberately does **not** derive from `AtlasRefused`, so an `except AtlasRefused`
cannot swallow it. A caller that recorded "no score" for a variant the service never claimed to
have scored would be `@unreachable-not-absent` in one line, and
`test_not_scored_is_not_a_refusal` is what stops it. `test_handler_order_is_not_load_bearing_by_accident`
enumerates the ladder, because `AtlasRefMismatch` being a subclass makes a caller's `except`
**order** load-bearing (`@client-exception-contract`).

## What it does not do

- **No interval RPC.** `ListDenseVariantScores` needs an `x-goog-fieldmask` header and 32 bp
  chunking; hand-built requests returned `INVALID_ARGUMENT` and the § 6.5 motif measurement was
  taken through the SDK instead. Adding it here is the obvious next step and was not taken, since
  nothing needs it yet.
- **No retry loop.** The vendored `grpc_service_config.json` carries upstream's policy and is
  passed to the channel, but nothing here layers `tenacity` on top the way the enricher's own
  clients do (`@retry-attempt-floor`). Adoption would.
- **No caching, no rate limiting, no `SourceRow`.** Every one of those is a real requirement for a
  shipped enricher lane (`@write-the-sourcerow`, `@shared-pacing-gate`) and every one is absent,
  because this proves reachability and nothing else.

## The cost this blueprint hides

Generated code has no compile-time signal when the service's protos move. Upstream regenerates on
every release; a vendored copy goes stale silently, and the failure surfaces as a decode error or a
missing field rather than a build break. [`PROVENANCE.txt`](../../vendor/alphagenome_protos/PROVENANCE.txt)
records the commit the three files came from (`aa6fc8f`, 2026-09-08) so re-vendoring is a diff, but
noticing that it is *due* is manual. That is the price of the light path, and it is the reason
§ 6.2 lists four shapes and picks none.
