# Roadmap — 0.9 and later minors

**What this file is.** The open minors' scope: what 0.9 builds, what 0.10 builds right after it, and the methylation
minor that follows, undated. Each item states why it is here. The file is named for the release that will decide its
contents, as [ROADMAP_0_8.md](history/ROADMAP_0_8.md) was; the 0.9 cut moves it to `docs/history/` and opens
`ROADMAP_0_10.md` with what is left.

**The scope, set on 2026-11-16 (the pm).** The maintainer, 2026-11-15: "don't make it too big, these half-a-week
release maraphons bleed me dry, lets make em smaller". So a minor is one theme, every design decision in it made before
its branch, and no new table kind. The cut went to the maintainer's desk as
[#326](https://github.com/winternewt/desk/issues/326) and was applied on its default under the kit's rule of the same
day, that only a real fork goes to the maintainer; it stands until they veto a part of it.

| Minor | Theme | Items |
|---|---|---|
| **0.9** | the enricher reads its reference data wherever it lives: local disk, then the registry's proxy, then Hugging Face (the order set on desk #261); the schema package gains one parsing function | RM430, RM431, RM437, RM443, RM404, RM412's second half |
| **0.10** | a small schema release: four optional additions | RM399 + RM441 (with S156), RM435, RM265, RM385 |
| **methylation** | after 0.10, undated until the PacBio samples are in hand | RM317–RM319, RM433, RM56, RM65, RM66 |
| *parked* | out of 0.9 into [ROADMAP.md](ROADMAP.md#active-items), each with its gate | RM302, RM350, RM294, RM345 + RM286, RM358, RM360 |

**How 0.9 is built: two rules on trial** ([#327](https://github.com/winternewt/desk/issues/327),
[#328](https://github.com/winternewt/desk/issues/328), applied on their defaults; RELEASE_CYCLE.md is unchanged until
the maintainer decides after 0.9). A **blocker** is a defect this release itself introduced that refuses a valid module,
loses data on a round trip, or stops a downstream project from installing or importing the package.

1. **An item that emerges during the build goes to the next minor**, unless it is a blocker, which is fixed in the
   release.
2. **At most two review rounds.** A finding left after the second ships as a known issue in the upgrade notes and is
   filed for the next release, unless it is a blocker.

The pm reports after 0.9 how both went.

**Earlier sizings, for the record.** The file opened on 2026-11-03, when the maintainer scoped 0.8 and sent "the rest"
to 0.9; the pm re-sized it on 2026-11-05 after the 0.8.0 cut ("'Auto-next minor' was a policy when we didn't have a
dedicated decision maker for this"), parking 22 items into ROADMAP.md. Everything here is **additive under Principles
3/4/8**; an item waiting on a version belongs in [ROADMAP_1_0.md](ROADMAP_1_0.md).

**Three of these are not work at all.** RM84's own half shipped in the 0.6 PT2 batch, and only the consumer's
discovery half is open. RM67 is a documented divergence, numbered so it stays findable and does not get re-probed. The
Gherkin corpus (RM149) is **frozen**; its entry says why. All three stay here, so that a reader meets the reasoning
instead of re-deriving it.

Indexed in [RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up.

---

# 0.9's scope — the enricher reads its reference data wherever it lives

The enricher, plus one pure function in the schema package (`parse_release`, RM430 decision 6); the compiler does not move. Six items: RM430, RM431, RM437, RM443, RM404 and RM412's second half. The trial before the design is [REMOTE_READS_0_9](probes/REMOTE_READS_0_9.md).

## RM430 — no snapshot reader takes a remote root: a URL collapses in `Path`, and every resolve, release read and connector checks the local disk

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. The status line below predates this.

**Severity** medium · **Status** open — **a minor, 0.9: a zone the maintainer named on desk #261 (2026-11-15)** · **Owner**
enricher (`locations`, `clinvar`, `resolver`, `gene_metrics`, `cpic`) + format (a bytes-level release parser at most)
· **Motivating case** S145 asks 1 to 3 (CONSUMER_SUGGESTIONS_HISTORY.md) · *related* RM431, RM432, RM339

**The gap.** The registry wants its proxy to answer keyed lookups from a lane's published Hugging Face repo when the
box holds no local snapshot, through these readers rather than a second reader of our layout. Its lead measured
that the keyed SQL already prunes remote row groups (ClinVar `lookup_clin_sig` 3.1 s and about 2.4 MB;
`resolver.lookup_loci` by position 3.5 s and about 5.4 MB of 200 MB). What stops it is path handling, checked here on
`main`. `Path("hf://datasets/a/b")` is `hf:/datasets/a/b`. `locations._resolve_parquet_cache` answers by `is_dir()`
and a glob, so every `resolve_*_reference` gives `None` for a remote root. `just_dna_format.snapshot.read_release`
joins a `Path` and tests `is_file()`. The connectors (`clinvar._connect` and the reporter's list: `resolver._connect`,
`gene_metrics._snapshot_parquet`, `CpicSnapshotClient`) coerce to `Path` and check existence locally.

**The asks.** (1) A remote root survives: a URL string handed back unchanged, or a `remote_reference(lane)` built
from `SNAPSHOT_REPO_IDS`. (2) `release.json` and Ensembl's `manifest.json` are read from a remote root. (3) The
connectors take `str | Path`, leave a URL scheme uncoerced, and let duckdb raise rather than checking the local
disk.

**A charter line for ask 2.** The Constitution's Goals put the snapshot layout and `release.json`'s model in
`just-dna-format`, and say that tier "reads no environment and fetches nothing; where a snapshot lives on a
machine, and how it is fetched, stay in the network tier". So `read_release` itself cannot read through fsspec. The
fetch belongs in the enricher, and the format tier at most gains a parser that takes the record's bytes or text.
Asks 1 to 3 are the ones the reporter says unblock everything else.

**Two facts from the measurement.** The ClinPGx and CPIC mirrors read anonymously. duckdb's `httpfs` must be
installed ahead of time on a server with no route to the extension repository. A remote read that fails is the
case RM432 makes visible.

**Sizing (pm, 2026-11-11): parked until the maintainer names it a zone.** A minor takes only the zones the maintainer
names, and a consumer waiting on it is the case for naming it, not a zone by itself. Put to the maintainer on desk #261
with the recommendation to name asks 1 to 3 alone a 0.9 zone (about a day; it keeps the registry off a second reader
of our layout, which would break silently on our next layout change). **Unparks** when the maintainer names remote
snapshot reads a zone. Built, it lands with RM432's patch already in, so a failed remote read raises rather than
answering empty. On silence it stays parked and returns when 0.9's scope is chosen.

**Unparked into 0.9 by the maintainer, desk #261, 2026-11-15**: "1, 2", so asks 1 to 3 here and RM431's follow-ups
are one 0.9 zone. With one change to ask 3, in their words: "I don't like 'stop checking the local disk' part. Remote
reads from hugging would be slow (measure)". The order of reads they set:

1. **The snapshot on local disk**, if one is there (the fastest).
2. **The registry's proxy**, if it is configured and answers (for clients). Also measured.
3. **Hugging Face**, the third fallback: only when there is no local snapshot, and the proxy is either not configured
   or pacing the caller. The registry must answer 429 to send a client on to this step.

So the connectors keep checking the local disk first; a remote root is a fallback, never a replacement for it. Before
the design, the pm measures steps 2 and 3 against step 1 on real lookups (a trial).

**Step 2's interface, from the registry's lead (2026-11-15, `#agent-chat>upstream`):** the proxy is already live
(registry 0.30+, both servers), so step 2 is a client of a service that exists. Its contract is the registry's
`docs/API-REFERENCE.md` §§ 46–47; in short:

- `GET {base}/api/v1/lanes/{lane}` lists a lane's tables and their key columns. `POST {base}/api/v1/lanes/{lane}/{table}`
  with `{"keys": {"<column>": [values]}}` (values ORed within a column, columns ANDed) answers `lane`, `table`,
  `served_from`, `rows`, `truncated`, `terms`, `unpublished`. Rows are the lane's own parquet columns, unchanged.
- Keys are identifiers only, at most 100 values and 1,000 rows a request. ClinVar by rsID, `variation_id` or
  chrom + start; Ensembl by chrom + start only (an rsID cannot be bounded remotely: RM431's index).
- Configured by one base URL; a bearer token is optional and only gives the caller its own rate bucket.
- **Fall through to Hugging Face** on 429 (`Retry-After`, `X-RateLimit-Bucket`), on 404 `lane_not_available`, on 503
  or 504, and on a timeout or connection error. **Never on 422** (`unknown_key`, `too_many_keys`,
  `remote_needs_position`): the request is wrong, and Hugging Face would refuse it too.
- The server reads its local snapshot, else the lane's published repo, and never calls itself. Their ask: **the proxy
  setting is an explicit parameter or environment variable, unset by default**, so the server never picks it up by
  accident.
- The test server for the trial is `https://module-polygon.just-dna.life` (lane routes live, anonymous).

**The trial (pm, 2026-11-15; `docs/probes/REMOTE_READS_0_9.md`).** Per lookup: local disk 0.02 to 0.1 s, the proxy 0.22
to 0.37 s whatever the batch, Hugging Face 1.8 to 8 s over the readers' glob (Ensembl by position up to 29 s). What
binds on Hugging Face is its anonymous quota, 3,000 requests per 5 minutes per IP: one Ensembl lookup over the glob
cost 1,168 requests, and opening only the chromosome file the key names cut requests 3 to 20 times. Ensembl by rsID
is slow on every route (9 to 14 s locally) until RM431's index exists. Two routes disagreed under one release label:
this machine's ClinVar cache (handed to triage) and the test server's ClinPGx copy (told to the registry).

**Decided for 0.9 (the pm, 2026-11-16), from the trial.** A builder that finds a case these do not cover sends it to
the pm and does not build around it.

1. **Local disk stays first and unchanged.** `resolve_*_reference` keeps its ladder and its answers. A remote root is
   asked only where it answers `None`, and never under `--offline` (zero egress stays zero). `enrich(download=True)`
   still provisions the snapshot locally, as today. The remote routes serve the keyed readers and the `lookup_*`
   functions only; `enrich()` does not read remotely in 0.9. Its first answering link decides `alts`, so a remote
   answer would move what a `download=False` run compiles today, and Hugging Face's anonymous quota (about 2 Ensembl
   or 30 ClinVar lookups per 5 minutes) cannot carry a module's worth of lookups.
2. **The proxy is configured explicitly and is unset by default**, as the registry asked: a `proxy_url` parameter on
   the remote entry point, else `JUST_DNA_SNAPSHOT_PROXY_URL`, read with `env_value` at the call (never `load_env`),
   and an optional bearer token in `JUST_DNA_SNAPSHOT_PROXY_TOKEN`. With neither, the proxy step is skipped.
3. **The proxy client** is one keep-alive `httpx` client, held as a new `LookupClients` field like every other
   client (the `lookup_*` functions read it, which is what that bundle's docstring asks of a field), with a 3 s connect and a 10 s read timeout. Requests fill up to the 100-value limit, one chromosome per
   request. It falls through to Hugging Face exactly on the registry's list (429, 404 `lane_not_available`, 503,
   504, a timeout, a connection error) and raises on 422, which is a wrong request on every route.
4. **Hugging Face** is read through duckdb `httpfs` on one connection per lane per process, kept and closed by its
   holder, never one per call (half the time, measured). A key that names a chromosome opens that chromosome's file
   rather than the glob (3 to 20 times fewer requests). A 429 is could-not-ask, typed as the lane's `*Unavailable`
   subclass; duckdb's exception carries no `Retry-After` (the trial), so the message names Hugging Face's 5-minute
   quota window instead. There is no retry inside the call. A token is read as the downloader already
   reads it (`HF_TOKEN`, else `get_token()`), and none is required.
5. **One release per session.** A session is the life of the object that holds the lane's remote connection: its
   first read reads `release.json` and pins the repository's revision for every later read through it, so a lookup
   session cannot mix two releases. Its holder ends it by closing it; a long-running server that wants a new release
   opens a new holder. Nothing pins for a whole process.
6. **`release.json` remote (ask 2):** the enricher fetches the bytes; the format tier gains only
   `parse_release(text) -> SnapshotRelease | None`, which `read_release` then calls. Nothing in the format tier reads
   a URL (the charter's snapshot-layout goal).
7. **Every answer says where it came from**: the route (`local`, `proxy`, `hf`), the release label read, and the
   proxy's `served_from`, on the lookup's result and in the log. No column and no sidecar moves. This makes an answer
   traceable to its route; it does **not** detect findings 8 and 9, where both copies carried the same label over
   different bytes (RM445's sticky label), and nothing here claims it does (the registry's correction, S34 there).
8. **Which lanes:** those with a published repo in `SNAPSHOT_REPO_IDS`. PharmVar and PubMind are operator-built and
   stay local only. Ensembl by rsID alone is never sent remotely (the proxy refuses it, and Hugging Face would scan
   about 10.7 GB); remotely, Ensembl answers by chrom + start only.

**Rejected:** a format-tier `read_release` that reads through fsspec (the charter keeps fetching out of that tier); a
retry loop on a Hugging Face 429 (the quota window is 5 minutes, and a loop burns the caller's share); the proxy on by
default (the registry's server would call itself).

**Answers to the lead's critic (the pm, 2026-11-16, evening).** These amend the decisions above; where they differ,
these win.

- **The API (B1).** One new public module, `just_dna_enricher.remote`, holds the remote routes. Its holder is
  `RemoteSnapshots(*, proxy_url=None, proxy_token=None, huggingface=True, declared_use="unstated",
  hf_base_url=None)`, a context manager and a new `LookupClients` field, `snapshots`, which is what the `lookup_*`
  functions read. It owns the proxy's `httpx` client (this replaces decision 3's separate field), one duckdb
  connection per lane, the pins and a lock. Its one query method is
  `lookup(lane, table, keys: Mapping[str, Sequence]) -> RemoteAnswer`. The existing readers keep `reference: Path`
  and their return types: each keyed query's SQL is moved to one place that the local reader runs over its glob and
  the holder runs over the remote root, so there is one copy of each query.
- **Where the route lands (B2).** `RemoteAnswer(rows, route, release, served_from, revision)` is new, so nothing is
  retyped. `VariantHint` gains one optional field, `routes: dict[str, RemoteRoute] | None`, keyed by lane and set
  only for lanes answered remotely (additive). `lookup_loci` and `lookup_clin_sig` stay as they are and stay local.
- **Off by default (B3).** No holder, no remote read: every existing call behaves exactly as today, egress included.
  A caller opts in by passing a `LookupClients` whose `snapshots` is set. Within a holder the Hugging Face step is on
  unless `huggingface=False`. In `lookup_variant` the remote step sits where the local cache sits, before live
  Ensembl REST: it is the same data.
- **Licences on the remote routes (A, second half).** A remote read is an acquisition. Before the first remote read
  of a lane in a session, on any route, the holder runs `check_declared_use(lane.terms, declared_use)`: a refusal
  raises, a skip reason makes that lane could-not-ask with the reason, and the local snapshot is still read. So
  `clinpgx`, `cpic` and `drug_labels` stay remote-eligible, gated.
- **Releases (C).** The pin is the Hugging Face repository's revision (a commit), read once per lane per holder. The
  label is `release.json`'s, or for Ensembl `manifest.json`'s `release_id`, parsed from fetched bytes by the
  enricher's own manifest model. Decision 5 narrows to **one release per route per holder**: a 429 can send some keys
  of one session to Hugging Face, so every answer carries its own route, label and revision, and nothing claims the
  session is one release. The proxy's reply carries no label, so a proxy answer's `release` is `None` (withheld,
  never guessed) and `served_from` is kept. The registry accepted adding `release`, `release_unreadable` and, for a
  remote read, `revision` to both lane replies (their S34, a minor of theirs); the client reads them when present.
  A local answer's `revision` is `None`: the pull record keeps no Hub revision, and 0.9 does not add one.
- **Truncation (C).** A reply with `truncated: true` is split in half and asked again, down to one key; a single key
  still truncated is could-not-ask for that key, never absent (`@unreachable-not-absent`).
- **Lifetimes and threads (C).** A connection lives as long as its holder, never the process (decision 4's "per
  process" is withdrawn). Each query runs on its own `cursor()` from the held connection; opening a connection and
  reading a pin happen under the holder's lock.
- **Lanes (D).** Remote-eligible: `ensembl` (chrom + start), `clinvar` (rsID, `variation_id`, chrom + start),
  `constraint` (gene), `opentargets` (chrom + position, RM431 ask 6), `clinpgx`, `cpic`, `drug_labels`, `civic`,
  `clinvar_gkm` (each by the keys of its new keyed function). Not eligible: `mitomap` and `strchive` (no keyed
  reader; STRchive's catalogue is one small file) and `alphagenome_avi` (its one reader is a writing pass, RM431
  ask 7). "One chromosome per
  request" applies to position keys only; gene and rsID keys are batched by value alone. Only Ensembl's
  per-chromosome file names are attested, so only Ensembl opens a chromosome's file; every other lane reads its
  glob.
- **`parse_release` (the lead's wave-0 departure, decided 2026-11-17).** The same bytes give the same answer on
  every route: the public `parse_release` is as lenient as `read_release` (a mistyped key is dropped with a warning,
  an unparsable record is `None`), and `read_release` calls it. The strict form that keeps the reason for
  `release_is_unreadable` stays private. Otherwise a remote read would refuse a `release.json` the local read
  accepts, and the two routes would disagree about the label they exist to report. Built in wave 2.
- **The error (D).** Every remote route raises one new type, `remote.SnapshotRouteUnavailable`, could-not-ask,
  carrying the lane, the route and the cause. The holder translates duckdb's HTTP exception and `httpx`'s errors
  into it. `lookup.py` catches it before its `duckdb.Error` handlers, and an AST guard holds that order
  (`@client-exception-contract`).
- **Tests (H).** The holder builds every remote URL through one function, with `hf_base_url` injectable and
  pointable at a loopback server that serves parquet with HTTP range requests. The network fence gains a duckdb
  case: without `JUST_DNA_NETWORK_TESTS`, the conftest makes that URL builder refuse a non-loopback host, and
  `test_the_network_is_fenced.py` asserts it. The proxy route is tested through an `httpx.MockTransport`.

**Residuals** none yet.

## RM431 — the keyed readers a remote lookup needs: an rsID index for Ensembl, and a key on the whole-table readers

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. The status line below predates this.

**Severity** low · **Status** open — **a minor, 0.9: in RM430's zone by the maintainer's word (desk #261, 2026-11-15)** · **Owner** enricher · **Motivating case** S145 asks 4 to 7 (CONSUMER_SUGGESTIONS_HISTORY.md) ·
*related* RM430, RM405

**The asks, as the reporter measured and read them.** (4) Ensembl by rsID alone cannot prune: the split repo's `id`
column is about 6.1 GB over 25 files, and each row group spans rs1 to rs9…, so `lookup_loci` by rsID reads nearly
everything. Ask: an rsID-sorted index (rsID → chrom, start) published beside it, consulted first. This is RM405's
missing rsID index, met from the remote side. (5) The whole-table readers (`clinpgx.load_snapshot`, the drug-label
reader, the CIViC row reader, `ClinVarGkmWitness.load`) take a key with pushdown. STRchive's 526 KB catalogue stays
whole. (6) Open Targets gets a public keyed function joining on chrom + position, not `variant_id` (about 55 MB read
for one lookup, measured). (7) `alphagenome_check.read_local_scores` lists contig files and reads them without a
local glob or `Path.stem`. Asks 4 to 7 build on RM430. Each is useful without the others, so the pm may split them.

**Sizing (pm, 2026-11-11): parked, not split yet.** Ask 4 is RM405's rsID index and unparks with RM405. Asks 5 to 7
are speed: each is worth building only once a remote lookup through RM430's readers is measured too slow or too large
for the registry's proxy. **Unparks**, per ask, on that measurement, which needs RM430 shipped but not this item.
Splitting waits until one ask unparks alone.

**Unparked into 0.9 by the maintainer, desk #261, 2026-11-15** (option 2, "the follow-ups too"), as RM430's zone.
The measure-first gate above no longer decides whether these are built; the pm's trial for RM430 still orders them.

**Decided for 0.9 (the pm, 2026-11-16).** Built after RM430's remote root, in the order 6, 5, 7, 4 (ask 4 last).

1. **Ask 4, Ensembl by rsID: a local index, never published** (settled the same evening, below). A derived cache lane, `ensembl_rsid_index`, built
   from the pulled split snapshot: rsID → (chrom, start), sorted by rsID so row groups prune. Its parent is the
   Ensembl snapshot's `release_id`, a field, by the derived-lane rule; a moved parent rebuilds it, and the reader
   refuses an index whose parent is not the core it sits beside. `resolver.lookup_loci` by rsID consults it first.
   It is built after `ensure_snapshot` and by `cache rebuild`, and goes through CACHE_SURFACE.md's checklist. It
   answers RM405's local half (9 to 14 s per lookup today) and serves the registry's proxy, whose server holds the
   lane locally.
2. **Ask 6, Open Targets:** a public keyed function joining on chrom + position, not on `variant_id`.
3. **Ask 5, the whole-table readers** (ClinPGx, the drug labels, CIViC rows, `ClinVarGkmWitness`): each gains a
   keyed public function with pushdown beside its loader; the loaders stay as they are.
4. **Ask 7, AlphaGenome:** `read_local_scores` lists contig files through RM430's root, local or remote, and never
   through a local glob or `Path.stem`.

**Publishing the index: not done (the pm, 2026-11-16, on the registry lead's answer).** S145's ask 4 wanted a
published index for a proxy box without the Ensembl lane. The registry's lead: "Local only is enough; publish nothing.
Both proxy boxes hold the Ensembl lane", and a proxying registry is a provisioned box by definition. So no derived
repository is built or published; a box without the lane keeps refusing an rsID-only key remotely
(`remote_needs_position`), which they accept. A future host without the lane is a new filing. The index's size and
build time are measured by its builder, not by a separate trial.

**Answers to the lead's critic (the pm, 2026-11-16, evening).**

- **Ask 4.** The index is a derived lane in a directory of its own, rebuild-only like `mitomap_miss`: no `ensure`, no
  entry in `SNAPSHOT_REPO_IDS`, built by `cache rebuild ensembl_rsid_index` and never inside `ensure_snapshot`, so
  `enrich(download=True)` pays nothing. It is not remote-eligible, which keeps RM430's "Ensembl by rsID never sent
  remotely". It is never published (the registry's lead, the same evening).
- **Ask 6.** `opentargets.lookup_variants(reference, positions: Sequence[tuple[str, int]]) -> dict[tuple[str, int],
  list[dict]]` reads `variants.parquet` by chrom + position; `opentargets.lookup_consequences(reference, variant_ids:
  Sequence[str]) -> dict[str, list[dict]]` reads `consequences` and `members` by the ids the first one found. Plain
  dicts, as `lookup_clin_sig` returns.
- **Ask 5.** The keyed functions run in duckdb (`@duckdb-vs-polars`: a runtime pass), including for the two loaders
  that read with polars today. CIViC's keyed function takes the raising reader's semantics (`civic_draft.py`): a
  lookup reports what it could not read, and the refutation pass keeps its own skipping reader.
- **Ask 7: canceled.** `read_local_scores`' only caller is a writing pass, which stays local (RM430 decision 1), so a
  remote form would have no caller. It returns as a new item if a lookup ever reads AlphaGenome scores.
- **RM412, the lead's default agreed:** `--rehearse-download` without `--dry-run` or `--publish` is refused.

**Residuals** none yet.

## RM443 — `lane_status` resolves every lane from the environment, so a host that passes its lanes' paths explicitly cannot ask it about them

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. The status line below predates this.

**Severity** low · **Status** open — **a minor; the pm sizes** · **Owner** enricher (`caches.lane_status`) ·
**Motivating case** S154 (just-dna-registry, CONSUMER_SUGGESTIONS_HISTORY.md) · *related* RM204, RM176, S91

**The gap.** `lane_status(lanes=None)` calls `lane.resolve()` with no argument and reports `looked_in` from
`os.getenv(lane.env_var)` or `lane.default_dir()`. Every lane's resolver takes the override as its first
argument and a `load_dotenv_file` flag (all seventeen in `CACHE_LANES` on 0.8.6, checked with
`inspect.signature`), so `lane.resolve(path)` is how a host that configures paths in its own settings reaches a
lane. `lane_status` has no way to pass that path. The registry configures lanes that way and never exports them,
because its suite runs two apps in one process. For any lane its operator configured, `lane_status()` reports on
a directory the server never reads: `absent` beside a snapshot the passes use, or `present` for one they do not.
So the registry keeps its own status loop, the second projection of one registry that RM204 was filed to end.

**A second effect of the same call.** With its default `load_dotenv_file=True`, each resolver calls
`locations.load_env()`, which exports the whole nearest `.env` into `os.environ`. That is by design for the cache
resolvers (`load_env`'s docstring says only they call it, RM301), and `lane_status` depends on it: the comment at
its `os.getenv` line says `resolve()` has loaded `.env` by then. For a host that never configures through the
environment, a status call is therefore also an environment write it did not ask for.

**The ask.** S154's candidate: `lane_status(lanes=None, locations: Mapping[str, Path | None] | None = None)`. For
a lane named in `locations`, call `lane.resolve(locations[name])` and report that path as `looked_in`, or the
default ladder when the value is `None`. Lanes not named keep the environment reading. In the same change,
decide whether `load_dotenv_file` passes through. The same mapping would suit `prepare_caches` if it ever takes
one, so the status and provisioning halves read the same directories.

**Sizing facts.** It adds a parameter to a public function, so it is new public surface: a minor under
RELEASE_CYCLE's rule for `main`, the same reading as RM429's field. No schema, manifest or vocabulary moves (P3
additive, P9 not an authored layer). No consumer is blocked: the registry's own loop works and stays until a
minor ships this.

**Sizing (pm, 2026-11-14): parked for 0.9, proposed to ride with RM430.** A minor needs a zone the
maintainer names, and none is named yet. It is about an hour of work and near free (one optional parameter, P9 not
an authored layer). It serves the same consumer and the same need as RM430, the registry reading lanes from
paths it configures itself, so it goes to the maintainer as part of that zone (desk #261) in the 0.9 scope
interview. Nothing waits on it meanwhile: the registry's own status loop works. **Unparks** when 0.9 names
the zone, or on its own when a second host reports the same gap. On `load_dotenv_file`, my default for the build:
pass it through and have `lane_status` pass `False` for a lane named in `locations`, so a host that configures
paths explicitly gets no environment write.

**Decided for 0.9 (the pm, 2026-11-16):** S154's signature as written, `lane_status(lanes=None, locations:
Mapping[str, Path | None] | None = None)`. A lane named in `locations` is resolved with that path and
`load_dotenv_file=False`, and reports that path as `looked_in`; `None` for a named lane means its default ladder,
still without the environment write. Lanes not named keep today's behaviour. `prepare_caches` does not take the
mapping in 0.9 (no caller asked); it is the same shape if one does.

**Residuals** none yet.

## RM437 — the split Ensembl snapshot's `groups/` sidecars have no provisioning route, so a consumer who needs a group must write into the lane's directory itself

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. The status line below predates this.

**Severity** medium · **Status** open — **a minor, 0.9** (its doc half a patch now) · **Owner** enricher (`download._provision_snapshot`, `locations`, `cache pull`) · **Motivating case** S150
(CONSUMER_SUGGESTIONS_HISTORY.md) · *related* RM420, RM339, RM381

**The gap.** The `ensembl` lane pulls `data/*.parquet` only. `locations.py` says so on purpose ("Files outside
`data/` (prepare-annotations' `groups/*`) are the manifest's and not pulled"). The split repo moved every
annotation value (consequence, clinical flags, frequencies) out of the core and into those groups, so a consumer
moving onto the lane as INTEGRATION_0_8 § 3 asks gets `id` and `row_idx` and nothing else. A group joins to the
core on `(chrom, row_idx)`, which holds only within one `release_id`. So the only safe writer is the one that
pulled the core: it checks the group's files against the same manifest, records them in the pull record, and
re-pulls them when the release moves (RM420). A consumer's own downloader into the lane's directory is the
mixed-release shape the lane exists to prevent, and a stale group would join to the wrong variants silently.

**The ask.** An opt-in group selection on the lane (`ensure_snapshot(groups=…)`,
`cache pull --only ensembl --groups …`), attested by the manifest and recorded in the pull record. Also a public
path function for a group's directory, so no reader spells it, and a refusal when a present group's files are not
the core's release. New parameters and a new public name, so a minor.

**Sizing (pm, 2026-11-12): 0.9, with its doc half now.** A real consumer hit it by following our own upgrade note,
so it meets 0.9's "a real run hits it". The pull, attested and recorded per release, is the only safe writer, as the
entry says, so the minor is built in that shape and nothing smaller: no documented "fetch the groups yourself"
recipe, which is the mixed-release shape. **The doc half is a patch, now**, under this number: INTEGRATION_0_8 § 3
says that the lane carries the core only, that a consumer needing consequence, clinical flags or frequencies keeps
its current source for them until 0.9, and why a hand-fetched group is unsafe (a group joins on `row_idx`, which
holds within one release only). It goes with the next patch on `main`.

**Doc half built (lead, 2026-11-13), cut 2026-11-13 as `v0.8.6`:** INTEGRATION_0_8 § 3, just-dna-pipelines step 1, says the lane carries the
core only, to keep the current source for the group values until 0.9, and why a hand-fetched group is unsafe.

**Decided for 0.9 (the pm, 2026-11-16):**

1. `ensure_snapshot(..., groups: Sequence[str] = ())` and `cache pull --only ensembl --groups NAME[,NAME]`. The valid
   names are read from the snapshot's `manifest.json`, never from a hand-kept list; an unknown name is refused
   before any download.
2. Each group's files are checked against the manifest's sha256, recorded in the pull record beside the core's, and
   re-pulled when the release moves (RM420's rule, unchanged).
3. A public `ensembl_group_dir(cache, group) -> Path`, so no reader spells the layout.
4. A reader of a group refuses, with a typed error, when the group's recorded release is not the core's: a group
   joins on `row_idx`, which holds within one release only.
5. Local only in 0.9. Remote reads of a group wait for a caller who asks.

**Answers to the lead's critic (the pm, 2026-11-16, evening).**

- **Licences per group (A, first half).** Yes: a group selection runs `check_declared_use` per group, through the
  same declared-use path `cache pull` uses for gated lanes. `SnapshotManifest` types `groups` (name → its record,
  including `licence`). The enricher maps a licence to terms by its licensor, the text before the colon ("Ensembl
  data", "CADD"), with one terms constant per licensor in `licensing.py`. On the measured manifest Ensembl's is
  unrestricted and CADD's forbids sale; a licensor with no constant is unknown terms, skipped with a reason that
  quotes the licence. So `--groups cadd` downloads under a research use, is refused under a commercial one, and is
  skipped under an unstated one.
- **Names (E).** `core` is not a group name: it is always pulled, and naming it is refused with that sentence. A
  `--groups` beside any lane other than `ensembl` is refused.
- **The release check (E).** The pull record gains each selected group's `release_id`. `ensembl_group_dir(cache,
  group)` is the guard: it raises the typed mismatch error when that release is not the core's, so every reader that
  takes a group's path takes the check with it.
- **Groups are sticky (E).** The pull record names the selected groups. Every later `ensure` of the lane, with or
  without `groups` (so `cache prepare`, a plain `cache pull` and `enrich(download=True)` too), re-pulls those
  groups whenever the core's release moves, so a group cannot go stale behind a new core. Removing a group is not in
  0.9: deleting the lane's directory does it.
- **Fact noted:** the `groups` directory name lives in the enricher.

**Residuals** none yet.

## RM404 — `enrich()` builds its own NCBI client and sequence proxy, so a host cannot pace them with the rest

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. **Order with RM385, which moved to 0.10:** RM404 is built alone in 0.9 and opens `enrich()` to a caller's NCBI client and `SequenceProxy`; RM385, in 0.10, builds its local reference behind that same parameter. The note below about building them together predates this split. The status line below predates this.

**RM407's residual (the lead, 2026-11-07).** RM407 (0.8.1) reads an indel's VRS window once through `SequenceProxy`, but the request under ga4gh's seqrepo proxy still has no timeout; this item's sequence-proxy seam is where that is answered.

**0.9, the pm (2026-11-07), built with RM385.** RM385, already in 0.9 by the maintainer's word, reworks how the enricher gets its `SequenceProxy` (a local reference for offline runs). Accepting the proxy from the caller is near free on that seam, and the eutils client is one more parameter beside the resolver, so deferring RM404 would only mean opening the same signature twice. A real host (the registry) runs its enrichments one at a time because of it. The fewer-entities rule weighs toward taking the whole `LookupClients` bundle over two loose parameters. **Not RM396's unpark condition, the pm's reading:** RM396 is about reading six named clients' intervals and gates by public name; RM404 is about handing clients in, and needs none of those names. RM396 stays parked.

**Its patch half is RM418, the pm (2026-11-07), on the registry's ask to bring RM404 into 0.8.x.** One private, process-wide NCBI pacing gate lets parallel `enrich()` calls in one process share a budget without a client passed in. Handing clients in stays here.

**It also publishes RM401's batching, the pm (2026-11-07).** RM401 and RM403 ship in the next patch with their new names private, because `RELEASE_CYCLE.md` keeps a new public field, function or method off `main`: the batch size is a fixed 20 and the timeout a fixed 120 s, with no settings field; the resolver methods, the two capability protocols, `ask_live_witness` and the retry-logging helpers carry a leading underscore. Making the batch knobs settings fields and the batch capability a public protocol an injected resolver can implement is the same seam as handing clients into `enrich()`, so it is built here rather than filed apart.

**Severity** low · **Status** open — **a minor, 0.9** (new public parameters) · **Owner**
enricher (`enrich()` signature, `identifiers.check_rsids`, `sequences.SequenceProxy`) · **Motivating case** S133
and S157 in CONSUMER_SUGGESTIONS_HISTORY.md · *related* RM396, RM385

**The gap.** `enrich()` takes `resolver=`, `gnomad_client=` and `grch37_client=`, but builds its own eutils client
for the dbSNP check (`check_rsids` takes `client=`, and `enrich` does not pass one through) and a fresh
`SequenceProxy` per call. A host running modules in parallel through one paced bundle cannot share either, and
the registry runs such enrichments one at a time for it. Beneath the proxy, ga4gh's seqrepo REST proxy calls
`requests.get` with no timeout (`ga4gh/vrs/dataproxy.py`, vrs-python 2.3.3, each call marked `noqa: S113`); the
registry counted 141 serial unpaced reads on one module, 36 s.

**What it would be.** `enrich()` accepts the eutils client and the sequence proxy the way it accepts the
resolver, or a whole `LookupClients`; which is the design question, and the fewer-entities rule weighs toward
the bundle. **Residuals, to be stated at closure:** the missing timeout is vrs-python's, upstream of this
repository; a proxy of our own that adds one would be the workaround the house rules refuse. RM396 (public gates
and intervals, parked) unparks when a host needs a second client's pace, which this may meet; that is the pm's
reading.

**S157, the online case of a local reference (the registry, 2026-11-16; triage).** The registry asks to hand
`enrich()` a seqrepo URI or a `SequenceProxy`, so `verify_ref`, left-alignment and the minter read a local seqrepo
with the network up. The `sequences=` parameter decided below answers it as decided, provided the minter takes the
passed proxy (it shares the run's proxy today, `orchestration.py:794`). The cost it removes, measured by the
registry's lead: a 57,756-row ClinVar-scale re-derivation took 6.9 h with `verify_ref=True` and 3.4 h without, the
same table, at about 0.34 s per remote read. A `seqrepo+file://` URI is read by `biocommons.seqrepo`, which the
enricher does not install, so the host's environment carries it. The offline case and a GRCh38 lane stay RM385's.

**Decided for 0.9 (the pm, 2026-11-16):** `enrich(..., clients: LookupClients | None = None, sequences: SequenceProxy
| None = None)`: the bundle for the network clients, whose `eutils` field `check_rsids` is then passed, and the
sequence proxy beside it, because the bundle holds only clients the `lookup_*` functions read (its docstring), and they
read no sequence. The existing `resolver=`, `gnomad_client=` and `grch37_client=` stay and win over the
bundle's field when both are given (additive; no deprecation in 0.9). RM401's knobs become `EnsemblSettings` fields,
`batch_size` (default 20, under the existing ceiling) and `batch_timeout` (default 120 s), and the two capability
protocols become public, `BatchResolver` and `RestBatchWitness`. `ask_live_witness` is public already. The
retry-logging helpers (`net._log_retry`, `_log_give_up`) stay private: an injected client logs its own retries, and
no caller has asked for them. The missing timeout under ga4gh's seqrepo proxy stays vrs-python's: the
liaison files it upstream, and no proxy of ours wraps it.

**Answers to the lead's critic (the pm, 2026-11-16, evening).**

1. Agreed: wave 0 moves `LookupClients` and `CLIENT_FIELDS` to a leaf module, and `lookup.LookupClients` stays
   importable.
2. The placement witness and `check_rsids` both use `clients.eutils` when the caller gives one. `enrich` wraps
   whatever client it uses in its `_RecordedEutils`, so each record is still fetched once (RM398); the wrapper is
   `enrich`'s and is closed by it, and a caller's client is never closed by `enrich`. The docstring says so.
3. Only `BatchResolver` goes public, `runtime_checkable`, with public method names and a public answer type; its
   private names go. `_RestBatchWitness` stays private (one test reads it, and no caller asked). This withdraws the
   decision above that made both public.
4. **One proxy per run (S157, the pm):** a passed `sequences` is the only sequence source the run reads: `verify_ref`,
   left-alignment and the VRS minter all take it, and none builds its own. A test asserts that a run given a proxy
   makes no sequence read through any other.
5. Under `offline=True`, `offline` outranks an injected sequence proxy, as it outranks an injected client today
   (`@gated-source-caches`): `enrich` does not use it and warns once. RM385 (0.10) adds a local reference, a
   different object that this rule can let through by its kind. `SequenceProxy`'s memo gains a lock, because shared
   use across parallel `enrich()` calls is the motivating case.
6. `batch_size` above the 200 ceiling is refused when the settings are built, never clamped silently.

**The builder's readings, placed (the pm, 2026-11-17).** RM404 landed on `0.9` at 3e9b993c.

1. **Confirmed: a caller's resolver is never altered.** Its indel anchor read goes through its own proxy, not the
   passed `sequences`, because no public seam reaches its private read and `enrich` does not reach into a caller's
   object. Answer 4's "no other proxy" holds for the resolver `enrich` builds. The docstring of `sequences` says so: a
   caller who passes both a resolver and a proxy gives the resolver the proxy itself.
2. **Confirmed: a field left unset is built, used and closed by the run**, and never written back onto the caller's
   bundle. The cost, one pacing gate per run for an unset Ensembl, gnomAD or GRCh37 client, is today's; a caller who
   wants one shared gate passes the client.
3. **Flipped: `batch_size` below 1 and a `batch_timeout` of zero or less are refused when the settings are built**,
   as answer 6 refuses a size above 200. Answer 6's "never clamped silently" covers both ends.
4. **Confirmed: the public method is `BatchResolver.resolve_rsids_batched`.** A `runtime_checkable` protocol matches
   by name, and `GnomadClient.resolve_rsids` already has another shape.

**The three 0.9-introduced findings are part of RM404** (the trial rule: a defect in an item's own build is part of
that item), and are fixed before RM404 counts as in:

- **A shared proxy never carries a failure from one run into the next.** It memoizes answers only; a failed read is
  held by the run that saw it, so the warning's "this run" is true. Shared use across parallel runs is answer 5's
  motivating case, which is exactly where the life-long memo silently skips.
- **The proxy's memo is bounded** (least recently used, the size stated in its docstring), since a shared proxy may
  live as long as a service.
- **`EnsemblResolver._base_reader` is built under a lock**, as answer 5 locks the proxy's memo.

**Pre-existing, not 0.9's:** `retired` sticking on a resolver reused across runs (`note_retired` is never cleared)
and live Ensembl answering rs646776 as G,T where `reference_examples/longevity_studies` records A,G,T go to triage as
patches on `main` (the second checks both sides before either moves). `_RecordedEutils` being client and wrapper at
once is a cleanup with no wrong answer behind it: a residual of this entry, no item.

**For the merge of `main` into `0.9` (the pm, 2026-11-17).** RM446 landed on `main` (6318392d): a run reads
`net.retired_mark(client)` where `enrich` picks its Ensembl client, a site RM404 rewrote on `0.9`. The merge keeps that
read at the bundle's pick point, before the run asks, or RM446 is lost in exactly the reused-client case RM404 makes
normal. RM446's three-run test is the check.

## RM412 — a dry run cannot rehearse the download, and the 0.8 line's private names wait for their public ones

**In 0.9's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), the smaller-minors cut, applied on its default under the rule that only a real fork goes to the maintainer. **Which parts:** half 2 whole (the 0.8 line's private names made public), and from half 1 the `--rehearse-download` flag the maintainer named. Half 1's per-lane probe of the source's newest release without its payload (a new `CacheLane` field) is **parked**: **Unparks when** an operator reports a rebuild that downloaded a source only to learn nothing had changed, or a scope the maintainer highlights touches it, or the roadmap is empty. The status line below predates this.

**Open, a minor, 0.9 (the maintainer, 2026-11-07: "inverted --rehearse-download flag in 0.9 along with all this
private-to-public debt").** Owner enricher · *related* RM411, RM413, RM408, RM401, RM403, RM404

**The residual of RM411, RM413 and RM416 (the lead, 2026-11-07).** RM411 left the download rehearsal and the source's
newest release unasked; RM413's gates still read that release off the liaison's hand-kept table, and two lanes
(`opentargets`, `clinvar_gkm`) publish only through a rebuild.

**Two halves, one reason: each is new public surface that patch scope kept off `main`.**

1. **`cache rebuild --dry-run --rehearse-download`**, the opt-in inverse of RM411: a rehearsal that does take the
   source bytes and builds, then rehearses the upload, the old dry run's behaviour, now asked for by name. Beside
   it, the cheaper half the maintainer first asked for ("only download headers/metadata"): per lane, the source's
   newest release and the bytes a build would fetch, asked of the source without the payload. That needs a probe
   per lane (a `CacheLane` field), which `docs/UPSTREAM_DATA_SOURCES.md` measures by hand today.
2. **The 0.8 line's private names made public**: `download._ensure_opentargets_snapshot` (RM408) as
   `ensure_opentargets_snapshot` beside its siblings, a standalone `opentargets publish` and `clinvar-gkm publish`
   for a snapshot already built (both lanes publish only through a rebuild today), and RM401's and RM403's names,
   which RM404 already plans to expose.

**The builder's readings, placed (the pm, 2026-11-17).**

- **Exit code:** a rehearsal that predicts a refused upload exits 0, as `cache rebuild --publish` does; kept. The
  per-lane commands' different exit is class (c) below.
- **(a) and (b) are part of this item, not new items:** a command 0.9 adds is not done while it can publish a
  `--parts`-limited test build to the public repository, or publish an unlabelled snapshot without the warning its
  siblings give. Both new publish commands refuse a snapshot whose `release.json` records `parts_read` below
  `parts_total`, and warn on a missing label as mitomap's and STRchive's do. If the rebuild path can publish a
  partial build too, the same refusal goes there.
- **(c), the near-identical `X publish` commands:** not 0.9 (trial rule 1). An internal refactor with no public
  surface, so a patch on `main` after 0.9 merges; triage files it.
- **(d), a rehearsal predicts only as wide as the dry run:** a residual, said in the flag's help text and stated
  at closure.
- **Follow-up (the pm, 2026-11-17).** A `release.json` that does not parse, or a `parts_read`/`parts_total` present
  but not a number, is refused at the publish gate: present-and-unreadable is the refusal, absent is the unknown arm
  (`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`), so a lane that writes no counts is
  not affected. Placed for later: the gate's home as a public predicate beside `SnapshotRelease` (a new public name
  in the format tier) goes to 0.10; the duplicated "which datasets are short", reading `release.json` apart from the
  bytes then hashed, and the double parse go with class (c) as one patch after 0.9 merges; the dead `--source`
  branch in `_rebuild_opentargets` predates 0.9 and is triage's patch on `main` now.
- **The gate as built (0a1ea872), the builder's readings (the pm, 2026-11-17).**
  1. **Refused: a per-dataset value that is present and not a whole number, `null` included.** No builder writes a
     `null` count, so one is malformed, and the lenient read drops the whole map over it, which let `l2g` at 1 of 12
     publish. This closes the one short read left past the gate.
  2. **Confirmed: whole numbers only.** "Not a number" above meant not a count: `12.0`, `1.5` and `true` are refused
     at the gate, although the lenient reader coerces them.
  3. **Confirmed:** a whole field that is not a map is refused like `"1"`, and an `OSError` reading the file counts
     as unparsable.
  4. **Refused too: a count below zero, and a `parts_total` of zero.** Both read as whole today; neither describes a
     dataset. Part of this item, as a hole in its own gate (trial rule: a defect in an item's own build is part of
     it).
  5. **The reader stays lenient and the gate strict, and the docstring says so.** `opentargets._part_counts`' "a
     wrong-kind count reads as unstated" holds only for a whole field that is not a map; pydantic's lax mode reads a
     per-dataset `"1"`, `1.0` or `true` as 1. The docstring is corrected in this item to say what holds, and that
     the publish gate is where a wrong kind is refused. RM430's `parse_release` keeps that reader's leniency.
  6. **`_PART_COUNT_KEYS`, a hand-kept pair beside the model:** derived from the model in class (c)'s patch after 0.9
     merges; no wrong answer today.

**Decided for 0.9 (the pm, 2026-11-16):** `ensure_opentargets_snapshot` public beside its siblings (the private
name goes: a leading underscore carries no contract);
`just-dna-enricher opentargets publish` and `clinvar-gkm publish` for a snapshot already built, each with the
`--dry-run` its siblings have; `cache rebuild --dry-run --rehearse-download` as half 1's flag. RM401's and RM403's
names are RM404's.

---

# 0.10's scope — a small schema release right after 0.9

Five items, each optional for an author: RM399 with RM441 (one design, which also carries S156's per-table "newest enricher release that could change it"), RM435, RM265 and RM385. RM265's open shape question goes to the maintainer when 0.10 opens, as a fork of its own.

## RM399 — a release cannot declare that a reference snapshot it reads moved, so `needs_recompile` says nothing about re-deriving

**In 0.10's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), item 2, applied on its default. 0.10 is a small minor right after 0.9. The status line below predates this.

**0.9, the pm (2026-11-07).** A real consumer's sweep (S132) read the 0.7 → 0.8 record and heard nothing of a corrected derivation that moved about 38% of insertions on the two chromosomes it measured. Principle 3 asks each release to declare its corrections readable offline, and 0.8 did so in prose only. Near free (P9: format tier, no authored column). Whether the 0.8.0 entry can carry the new field as well is the build's to check; if it can, the registry's sweep across 0.7 → 0.8 says re-derive. Shape, by the fewer-entities rule: a field beside the five axes before a record of its own; a new change kind breaks old readers (INTEGRATION_0_8 § 1.11), so it comes last.

**Severity** medium · **Status** open — **a minor, 0.9** · **Owner** format
(`release_records.py`, `vocab.VALID_RELEASE_CHANGE_KINDS`) with the enricher's default lanes as its subject ·
**Motivating case** S132 in CONSUMER_SUGGESTIONS_HISTORY.md (just-dna-registry's lead, 2026-11-07) · *related*
RM372, RM267, RM126, RM181, RM398

**The gap.** `needs_recompile("0.7.0", "0.8.0")` declares 35 changes and none names RM372's snapshot switch,
`resolution.csv` or a placement. That is the record doing its job: its five axes describe what the compiler
does with a given spec, and a re-derivation changes the spec's derived input, for which the record has no axis.
But 0.8 corrected a derivation there: RM267's insertions now land on dbSNP's event, and the registry measured
roughly 38% of insertions on chr22 and chr9 as naming a different event across the switch. Principle 3 says a
corrected derivation ships in any release but never silently, declared readable offline. 0.8 declares it in
prose (INTEGRATION_0_8 § 1.29, the CHANGELOG), and a consumer's sweep, which reads the record, hears nothing.

**What it would be.** A release states, beside its compiled-output changes, which reference lanes its enricher
now reads at a different release (lane, old label, new label, the items the move corrects), and a reader asking
across a span learns "re-derive" as well as "recompile". Whether that is a member of `release_records`, a field
beside the five axes, or its own small record is the design question, and RM181's provenance tracker is a
different one (what an *edit* moved about a module, not what a *release* moved about its inputs). Nothing here
changes RM372's lane or any digest.

**Sizing.** A new optional field or vocabulary member in the format tier: a minor, and an old-reader break if
it is a new change kind, as `toolchain` was (INTEGRATION_0_8 § 1.11). P9: near free; no authored column.

## RM441 — a release record has no axis for a correction to a derived table, so 0.8.5's reads as "nothing moved" although RM438 corrected `resolution.csv`

**In 0.10's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), item 2, applied on its default. 0.10 is a small minor right after 0.9. The status line below predates this.

**Severity** low · **Status** open — **a minor, 0.9** (built with RM399, one design) · **Owner**
format (`vocab.VALID_RELEASE_OUTPUT_AXES`, `release_records`) + compiler (`sweep`) · **Motivating case** S153
(CONSUMER_SUGGESTIONS_HISTORY.md), S156 · *related* RM399, RM438, RM201, RM120

**The gap.** `VALID_RELEASE_OUTPUT_AXES` is `parquet_schema`, `parquet_bytes`, `content_signature`,
`manifest_fields` and `warnings`. Every one is compiled output, and the sweep measures them by compiling the
reference modules with their committed sidecars. A correction to what the enricher derives (`resolution.csv`, the
fact sidecars) is invisible on that instrument. 0.8.5's record is a measured zero on every axis, and its commit
says RM438's correction "is enricher output the record does not measure". The registry decides what a release
changed by reading the record (`release_records.needs_recompile`), so it reads 0.8.5 as moving nothing, and so does
every consumer that sweeps by the record. RM438 is the kind of change the record exists for: a published value was
wrong, and only some modules can carry it.

**The three asks, and the design points under each.**
1. **An axis for derived tables.** A new member of a closed vocabulary is minor-legal (P3) and not a patch. One
   catch is in the code: `RECOMPILE_DRIVING_AXES` is the vocabulary minus `NON_RECOMPILE_AXES` ("a new axis joins
   the driving set unless it is explicitly excluded"). A derived-table axis added naively would tell a consumer to
   *recompile*, when the action a derived-table correction calls for is to *re-derive* (`enrich(rederive=True)`)
   and then recompile. It needs its own route, a third set or a field saying the action, and not membership in
   the recompile set.
2. **A `requires` that reaches the right modules.** Today's grammar is presence of dotted manifest paths. RM438's
   reach, a module with a coordinate-authored row and no `rsid`, is not spellable in it, so its honest value is
   `None` ("the reach could not be stated", which a consumer keeps). Whether the manifest should carry a path that
   makes it spellable is a second question, priced on its own.
3. **RM438 declared.** Records ship inside the package, so the declaration goes in the next release's record, not
   an amended 0.8.5. Until the axis exists, the measured and declared halves of a record must agree
   (`@a-record-written-in-two-passes-drifts-between-them`). So a `correction` on a compiled axis that the sweep
   measured as zero is not an honest stopgap.

**Meanwhile.** Nothing published needs it. On registry production no row moves, and the five modules still on
pre-0.8 tables are being re-derived on 0.8.5 by hand. The gap is for the next derived-table correction.

**Sizing (pm, 2026-11-12): 0.9, one design with RM399.** RM399 is the same gap from the other side: a release moved
a lane the enricher reads (0.8's snapshot switch), and the record could not say "re-derive". Here the enricher's own
derivation was corrected (RM438), and it cannot say so either. Two fields for one action would be two entities where
one serves (fewer entities), so the record gains **one route**: a reader across a span learns "re-derive", with the
cause named (a lane moved, or a derivation corrected) and the items behind it. Under the asks:

1. **Not a recompile axis.** The route is its own set or field, never a member of `RECOMPILE_DRIVING_AXES`, as the
   entry says; a test holds that "re-derive" is never answered as "recompile".
2. **`requires` stays `None` for RM438**, the honest "the reach could not be stated". A manifest path to make such a
   reach spellable is not part of this item; it comes back only when a consumer shows `None` costing it a needless
   re-derivation.
3. **RM438 is the route's first declaration**, in the record of the release that ships the route, beside RM399's
   0.8 snapshot switch if the build can reach the 0.8.0 entry. Until then the CHANGELOG and INTEGRATION_0_8 carry it
   in prose, and no compiled axis gets a correction the sweep measured as zero.

**A fourth ask, S156 (the registry, 2026-11-16; triage).** The registry's convergence check needs, from the
installed packages and offline, the newest enricher release whose output for a derived table could differ, so that
a text-only enricher patch does not send every module with a reason through a re-derivation. Today nothing says it:
`RELEASE_RECORDS` covers compiled output only, and an enricher-only patch has no record (0.8.1, 0.8.7). One fact
for the design: the records live in `just_dna_format`, and an enricher-only patch does not release the format, so
"every enricher release carries a record" needs either a format release per enricher patch or records that live in
the enricher. A per-table "newest version whose derivation could differ", kept in the enricher beside
`CACHE_LANES`, is readable from the package that moved. The route this item adds answers "re-derive" across a span,
so the build answers S156 from the same place rather than with a second mechanism; which side holds it is the pm's
call in the design. Public surface either way: a minor, as the rest of the item.

**The pm's call (2026-11-16): the enricher holds it.** The fact is about enricher releases, so it ships in the
package that moves: a per-table "newest enricher version whose derivation could differ", beside `CACHE_LANES`, read
offline from the installed enricher. A record in `just_dna_format` would force a format release for every enricher
patch, the opposite of the small patches the maintainer asked for. The release records in the format stay about
compiled output. It rides with RM441 and RM399, one design, in the minor desk #326 places them in (0.10 as proposed).

**Residuals** none yet.

## RM435 — a study row has no direction of its own, so a study that prints its allele and direction but no size puts the direction in free text

**In 0.10's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), item 2, applied on its default. 0.10 is a small minor right after 0.9. The status line below predates this.

**Severity** low · **Status** open — **a minor, 0.9** · **Owner** format
(`spec.StudyRow`) + compiler (the study parquet) · **Motivating case** S148 (CONSUMER_SUGGESTIONS_HISTORY.md) ·
*related* RM91, RM148

**The gap.** A replication table often prints the effect allele, the direction and the P with no effect size: a
look-up in an independent cohort, or a meta-analysis that pools the P and gives each arm's direction without a
pooled estimate. `StudyRow` has `effect_allele` (RM91), and the direction rides on the sign of `effect_size` read
through `effect_measure`. With no size there is no sign. `VariantRow.direction` is the module's call over every
study, not this study's finding. So the study's own direction goes in `conclusion`, free text, which nothing checks
against `effect_allele` or `effect_size`.

**The precedent is already in the schema.** `GwasEffectRow.effect_direction` (since 0.6) is exactly this field on
the derived GWAS table: `increase|decrease` (`VALID_EFFECT_DIRECTIONS`), relative to the row's effect allele, and
"**not clinical direction**". Its description says folding the two together would overload one field with two axes
(P5). The reporter's candidate takes the variant row's vocabulary (`protective|risk|…`). The precedent says the
study-level field should instead be `effect_direction` with the same members and the same meaning. A study reports
which way the allele moves the measured trait. Whether that is protective is the module's call, which
`VariantRow.direction` already makes. Same name, same vocabulary, one meaning across the two tables.

**The ask, in that shape.** Optional `StudyRow.effect_direction`, meaningful only with `effect_allele`, plus a check
when `effect_size` is also stated. The check is a sign test for a signed measure (`beta`) and a test against 1 for a
ratio (`OR`, `HR`, `RR`), and it warns on disagreement. That warning is what the reporter names as making two fields
that can contradict safe. A new optional column is minor-legal (P3, P8), and on the authored layer it is full cost
(P9). The case for paying it is that today the value is written anyway, into a cell nothing can read. It reaches the
study parquet like the other 0.3 columns, through the three touch points `@three-touch-points` names.

**Sizing (pm, 2026-11-12): 0.9.** It is a leftover of longevitymap v2, the last zone the maintainer named: the
reporter is the seat building that module, and the value is being written today into a cell nothing reads, so the
cost is paid either way. Built in the precedent's shape only: the name `effect_direction`, `VALID_EFFECT_DIRECTIONS`,
the warning on a stated size that disagrees, and nothing from `VariantRow.direction`'s vocabulary.

**Residuals** none yet.

## RM265 — the `panel:` deprecation has no "accepted" signal: on the replaced branch the warning fires whether or not you need the three fields it tells you to keep the block for

**In 0.10's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), item 2, applied on its default. 0.10 is a small minor right after 0.9. The status line below predates this.

**Stays in 0.9, the pm (2026-11-05)**: a real run hits it: S114 found the warning on every compile of just-dna-lite's three ClinVar panel modules. The status line below predates this.

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** compiler / format
(`panel:`, the licence row) · **Motivating case** [S114](CONSUMER_SUGGESTIONS_HISTORY.md#s114--the-panel_block_deprecated-replaced-branch-warns-whether-or-not-you-need-the-three-fields-it-says-to-keep-the-block-for-so-there-is-no-way-to-signal-accepted)

**What was confirmed.** Reproduced against all three just-dna-lite ClinVar panel modules and against
the code. `panel_block_deprecated` fires on the `replaced=True` branch (`compiler.py:4231`) for a
module that has done everything the migration asks — its `clinvar/annotation` licence row carries a
non-empty `dataset`, so the block's one machine reader (the enricher's clin_sig cross-check) is
migrated. The message's closing clause, correct since S69, is that `genes`, `significance` and
`reference_sha256` "have no replacement anywhere — keep the block until 1.0 if you need them recorded."
But keeping the block *is* the permanent warning: the block emits `panel_block_deprecated` whether or
not those fields are wanted, and there is no key to say "accepted, I need the three, stop." A consumer
who needs them warns forever; a consumer who wants a clean compile drops provenance the format itself
says has no home. The two outcomes are "warn forever" and "lose data".

**The design question this records.** Is `panel:` deprecated *as a whole*, or only its reader? P3
deprecates in a minor only where the audience can **act** — the replacement exists and the deprecated
thing is not still the only record — and for these three fields on the replaced branch no replacement
exists, which is the state P3 forbids. Two candidate fixes, and the naive one is not free:

- **Give the three fields a non-deprecated home** — a small `panel_provenance:` sub-block, or three
  keys beside `dataset` on the licence row. This is the P3-clean answer: it completes the replacement,
  so the deprecation becomes actionable. Cost is P9-full if authored (a `panel_provenance:` block the
  rare author writes) or P9-half if it rides the machine-written licence row; additive either way, so
  **minor**. It is a schema-shape decision — where the fields live, whether the gene *denominator*
  (S114's one lossy field: `cardio` requested 327 genes, 297 matched a variant, the 30 that matched
  none are absent from `variants.csv`) is a list or a count — and belongs in the version interview,
  not an unattended pass.
- **Fire `panel_block_deprecated` only on the `replaced=False` branch** (patch). Tempting and **not
  free**: it silences a *true* statement on exactly the modules that keep the block for the three
  fields, so they compile clean until 1.0 removes the block under `extra="forbid"` and the data with
  it. P3 requires a major to ship its upgrade procedure; theirs would read "lose the data." So this
  mitigates the noise at the cost of hiding the loss — a stopgap, not the resolution.

**Related.** The idea-book's § D19 (this file) raised the same two candidates against the pre-S69
message; S114 is its sharpened, corpus-backed form. The stale RM4 row in
[ROADMAP_1_0.md](ROADMAP_1_0.md) § the upgrade tracker still tells the author "delete it, nothing
replaces it, consumer: no action needed" — corrected there in the same triage pass as a doc fix,
since that tracker is the procedure P3 turns on.

## RM385 — offline enrich cannot left-align an indel, because `--offline` turns off the reference as well as the network

**In 0.10's scope, the pm (2026-11-16)**: [desk #326](https://github.com/winternewt/desk/issues/326), item 2, applied on its default. 0.10 is a small minor right after 0.9. The status line below predates this.

**RM407's residual (the lead, 2026-11-07).** RM407 (0.8.1) cut an indel's VRS mint to one seqrepo read per locus; a local reference here removes those reads altogether.

**S157 (the registry, 2026-11-16; triage): the online case of the same seam.** With the network up, a deployment
holding a local GRCh38 reference still reads every base over REST; the registry measured a re-derivation at 6.9 h
with `verify_ref=True` against 3.4 h without, the same table. RM404 (0.9) answers the online half with its
`sequences=` parameter. What stays here: the offline run, where `offline` outranks an injected proxy (RM404's
answer 5 to the lead's critic), and the lane with three stages the registry would prefer over a passed URI (open
question 2). One fact for open question 1: a local seqrepo needs `biocommons.seqrepo`, which the enricher's core
dependencies leave out on purpose, so the seqrepo route is a new dependency (or an extra) where a FASTA reader
would not be.

**0.9, by the maintainer's word (2026-11-05)**, relayed by the lead; entry written by the pm.

**Severity** low · **Status** open — **a minor, 0.9** · **Owner** enricher (`sequences.py`) · **Motivating
case** the registry's catalog sweep enriches offline by default, so on 0.8 its indels must be enriched online
(the lead's advice for the registry's M12, 2026-11-05); and S132 (the registry's 0.8 replay, 2026-11-07), where
an offline re-derivation left 23 subjects `undecided` that a local reference would have turned into `respelled`;
and S157 (the registry, 2026-11-16), the online case · *related* RM273, RM270, RM381, RM382, RM404

**The gap.** Every reference base the enricher reads goes through `SequenceProxy`: left-aligning an indel
(`_left_align`, RM273), minting an indel's VRS id, and the reference-allele check. Its default is the public
seqrepo REST service, and `offline=True` makes every read return `None`. So an offline run has no reference
at all, and an indel's caller spelling is withheld rather than produced. Two things are joined here that need
not be: *no network* and *no reference*. `create_dataproxy` already accepts a local seqrepo
(`seqrepo+file:///…`), and `SequenceProxy.uri` is a setting, but `offline` short-circuits before the URI is
looked at, so a local reference cannot serve an offline run today.

**What it would be.** An offline run reads a local reference when one is configured, and only withholds when
none is. "No reference configured" stays a named could-not-ask, never an absence (`@unreachable-not-absent`).

**Open questions, for 0.9's interview.**

1. **Which local reference.** A local seqrepo is what `create_dataproxy` already reads, but it is large and
   needs its own tool to build. A GRCh38 FASTA is the form deployments already hold, and would need a small
   reader of our own. Measure both before choosing (`@probe-the-real-file`).
2. **Where it is configured.** A setting beside the other cache lanes, with the three stages a lane owes
   (`CACHE_SURFACE.md`), or a URI the operator passes. The fewer-entities rule weighs toward the URI.

**Residuals** none yet.

---

# After 0.10: the methylation minor, undated

Its own minor, after 0.10, undated until the PacBio samples are reported in hand ([desk #329](https://github.com/winternewt/desk/issues/329), its default). RM317–RM319, RM433, and the PacBio zone's RM56, RM65 and RM66. The sections below also keep the three items that are not work (RM67, RM84's consumer half, RM149).

## RM317 — FMR1 repeat methylation is in every PacBio TRGT VCF as `FORMAT/AM`, and no module can bin it on a two-allele record

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a `measure_kind` member, the element-rule vocabulary, the host table) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.1, 3, 4.1](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What is real.** TRGT, PacBio's tandem-repeat genotyper and part of the HiFi WGS pipeline since at
least v2.1.0, writes `##FORMAT=<ID=AM,Number=.,Type=Float,Description="Mean methylation level per
allele">`: the mean 5mC level over the CpGs **inside the repeat tract**, one value per called allele.
Open samples exist: NA09237 (male full mutation) is `GT=1`, `MC=898`, `AM=0.85`, reproduced with TRGT
5.1.0, and HG002 (normal male) is `AM=0.1`. `source_field: FORMAT/AM` already passes the pointer
grammar. `fmr1_cgg_repeat` asserts in prose that a full mutation "is methylated and silenced", and this
is the field that can check it.

**What a module cannot do today.**

- **Select the right allele.** HM06968 (female) is `MC=33,112`, `AM=0.90,0.07`: the expanded allele
  is the *unmethylated* one. NA06905 goes the other way. The band means "the methylation of the
  expanded allele", i.e. the `AM` at the index where `MC` is largest. Every element rule picks by the
  field's own values, so none can say it.
- **Name the quantity.** No `measure_kind` is a methylation fraction. `allele_fraction` would put two
  quantities under one name (P5). `repeat_alleles.csv` pins `measure_kind=repeat_count`.
- **Name the absence.** `AM=.` means either no CpG in the span or no MM/ML tags in the BAM, and the
  file cannot tell them apart.

**Scale trap.** TRGT 0.5.0 wrote `AM` as an Integer (values up to 185; probably the 0–255 byte,
unverified). From 0.7.0 it is a Float on `[0, 1]`, and the changelog is silent about the change.

**To design (the 0.8 interview).** The kind's name, audited under P5, and whether the modification
(5mC) is its own axis. Whether `repeat_alleles.csv` hosts a second kind or a sibling table does. How a
cross-field selection is stated without hard-coding TRGT's `MC` into a vocabulary: the probe prices an
optional pointer column naming the selecting field at full cost. And **the band values**: none is
cited yet. The probe quotes sample observations, not boundaries, and a row needs a paper behind it
(`@rm47-bin-cites`).

**Legality and price.** Everything is additive, so it is minor-legal (P3, P6, P8). A kind member is
cheap but a one-way door (P5). The selector column is full cost.

## RM318 — imprinting-region methylation is real in PacBio outputs, but lives in BED and TSV files that no pointer can name

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a new optional region table kind, a non-VCF pointer) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.2–1.4, 3, 4.2](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What is real.** HG002 shows allele-specific methylation at two imprinted regions in public PacBio
pipeline outputs, and MethBat 1.1.0 run on them reports `PASS`:
SNURF:TSS-DMR (15q11–13) hap1 80.1 / hap2 14.6, and KCNQ1OT1:TSS-DMR (11p15 IC2) hap1 15.3 / hap2 86.4,
with pooled values near 49. The consumer holds per-CpG `5mC.bed.gz` (MethBat 1.x) or
`cpg_pileup.*.bed.gz` (pb-CpG-tools 3.x), plus a `profile.tsv`. None of it is in a VCF, and no PacBio
tool writes VCF 4.5 `M5mC`.

**What a row would need.** Every item comes from the probe's measurements:

- a region (chrom, start, end, build), with no `variant_key`;
- a pointer to a BED or TSV column, which `source_field` (a VCF pointer) cannot be widened to without
  overloading it (P5);
- the aggregation from sites to region;
- a row selector (`Total`, or a statement about both haplotypes);
- the unit and the modification;
- a coverage floor, because a missing row is never "unmethylated";
- bands: pooled around 20% and 80%, plus a haplotype-delta band.

**Traps the data showed.**

- **Haplotype labels are not parental.** The same sample has hap1 methylated at SNURF and hap2 at
  KCNQ1OT1, so no band can say "the maternal allele".
- **The scale moved at MethBat 1.0.0** (fractions to percent) under unchanged column names.
- **pb-CpG-tools `model` and `count` modes disagree** (hap2 4.1% vs 16.1% at one CpG). The mode is a
  header line, not a column.
- **The pipeline runs `methbat profile` over CpG islands, never `methbat report`**, so a user holds
  island numbers, not the imprinted regions.
- **H19 had no haplotype rows at all.**

**Not decided, and not to be built on thin air.** The 20%/80% cut-offs are MethBat's defaults, not a
guideline. No clinical source was read. MethBat ships 15 imprinted regions from Mackay et al. 2022
(Table 2), which is the corpus a design would start from.

**Legality and price.** A new optional table kind is minor-legal (P3). Its price is full, and it is the
largest addition in the methylation work. The probe prices a separate pointer column over widening
`source_field`.

## RM319 — PacBio's TRGT carries the repeat count as `FORMAT/MC`, a per-motif String, so `repeat_alleles.csv`'s count half does not reach a PacBio user

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (the consumer contract, possibly the element-rule vocabulary) + the corpus · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO § 4.1, last paragraph](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM433, RM66, RM65, RM164

**What was found.** No PacBio file opened in the probe carries `REPCN`, the ExpansionHunter key that
`fmr1_cgg_repeat` (and the corpus's other repeat examples) point at. TRGT writes the count as `MC`,
`Type=String`, per allele, with `_`-joined per-motif counts inside each allele (`18_8,25_8` at HTT
under TRGT 5.x). A PacBio consumer therefore cannot follow the module's `source_field` at all. An
author who writes `FORMAT/REPCN|FORMAT/MC` hands the consumer a motif-segmented string that no element
rule defines a reading of.

**Why it matters now.** A beneficiary of this work is about to hold PacBio samples, and TRGT is the
repeat caller in PacBio's pipeline. Every `repeat_alleles.csv` module is invisible to them today.

**To decide.**

- Whether this is a consumer-contract rule ("sum the motifs", or "the motif the row's `repeat_unit`
  names") or a vocabulary addition. The second is a minor.
- How it meets RM66, one repeat locus with several motifs: TRGT's per-motif segments are exactly RM66's
  shape.
- Whether the reference examples gain the TRGT alternation.

Measure against the PureTarget VCFs first. The probe lists them, with FMR1, HTT and more.

**Legality.** A contract sentence alone is a patch. A new element rule or pointer shape is a minor. It
is filed against 0.8 because the RM66 overlap wants one decision.

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM433 — AlphaGenome 2's live model service is unused: the only surface that scores an indel

**Severity** low · **Status** open — **a minor, 0.9** (with the methylation zone, RM317 to RM319) · **Owner** enricher (a new client beside
`alphagenome_check`) · **Motivating case** the maintainer's ask through the lead, 2026-11-12 ("yes (to pm)"), after
upstream's v2.0.0 · *related* RM317, RM318, RM319, RM191, RM192, RM193, RM345

**What changed upstream.** AlphaGenome v2.0.0 (2026-11-11) adds `DnaModelServiceV2` (package `v2main`), a
live-prediction service: `PredictVariant`, `ScoreVariant`, `ScoreInterval`, `ScoreIsmVariant`, expression
conditioned on a reference or a single-cell profile, `EncodeCells` embeddings and input gradients. Nothing of ours
uses it. Our Atlas client reads the precomputed `v1main` scores, its three proto files are byte-identical at v2.0.0 to
our pin, and a live `GetDenseVariantScores` on rs4149056 answered on 2026-11-12 (the lead). So nothing breaks and no
patch is owed. The pin-bump trap (at v2.0.0 `protos/dna_model.proto` is a shim importing `protos/v1/dna_model.proto`)
is the liaison's.

**What adopting it would buy.** The Atlas probe's surface table (`docs/probes/ALPHAGENOME_ATLAS.md` § 6.4) has the
model API as the only one of three surfaces that scores an **indel**: the bulk files carry none and the Atlas API
answers `UNIMPLEMENTED`. That was already true of the v1 model service, which we never adopted either, so v2 is not
what opens it. What v2 adds over v1 (read from its protos at the `v2.0.0` tag, 2026-11-12): a **methylation** output
(per-CpG probabilities) with a variant scorer over a window around the variant, the one addition that meets a named
0.9 zone (methylation, RM317 to RM319); single-cell expression and ATAC outputs; conditioning on a single-cell
profile; cell embeddings; and input gradients. PRO-cap is gone. Single-cell outputs, embeddings and gradients have no
table a module could put them in. The terms are the v1 model service's: non-commercial, no training of other models,
not for clinical decisions; commercial use only through Google Cloud. Live predictions get a lower query rate than
Atlas lookups and are meant for small analyses.

**What it costs.** A new client on a different gRPC service with new message types; a decision on what is stored (a
column on an existing derived table, or a lane of its own); and the service's terms, quota and licence. The Atlas
probe's § 2 is the precedent: the artifacts there turned out not to be one licence, and § 7 left the daily quota
unmeasured. A computed prediction is per request, never offline and never reproducible (§ 6.4), so it sits beside
the house rule that a check over a source records what it read.

**Sizing (pm, 2026-11-12, then the maintainer the same day): 0.9, tied to the methylation zone.** First parked,
since no named zone held it. The maintainer then tied it to RM317 to RM319 ("tie the v2 to them"), so it joins the
methylation zone. The tie is complementary, not overlapping. RM317 to RM319 are the **measured** half: a consumer's
PacBio files hold the sample's own methylation, and the module points at it and bins it. v2's methylation scorer is a
**predicted** half: per variant, how the alternate allele shifts methylation at the CpGs near it. That is an annotation
in this format's sense (no sample data), so a module could carry it and a consumer could read it beside their measured
values.

Built in this order, each step allowed to stop the next:

1. **A terms probe** of the model service, in the shape of the Atlas probe's § 2: what the output may be used for,
   stored as and published as. If its output may not be stored in a module, the item shrinks to a live check and the
   methylation half ends there.
2. **A trial** on a handful of variants with a published methylation effect (an mQTL, an imprinting-region variant),
   measured against what is known, plus the live query rate. About two hours with the maintainer's API key.
3. **Only then a design**: where a predicted methylation shift is stored (a derived table or columns, at RM317's
   design interview, so the measured and the predicted halves share their vocabulary).

Indel scoring rides along only if step 2 shows the model service is usable at our scale; it was never v2's to
unlock.

**The trial, run 2026-11-12** ([ALPHAGENOME2_METHYLATION_TRIAL.md](probes/ALPHAGENOME2_METHYLATION_TRIAL.md)):
inconclusive, not negative. Cheap (about 1 s and 1 KB a call, deterministic, no throttling, indels accepted), and
strong only within about 15 bp of the variant. At nine published blood mQTLs its shifts stayed inside its own window
sensitivity (at most 0.046 logit against up to 0.1 of noise); 7 of the 8 readable signs agreed, but 6 of those came
from one locus. The vendored terms allow publishing the scores non-commercially only, with notice and the Use
Restrictions carried as a term, never under CC0 or CC BY. **So step 3 waits** on a second trial with enough loci,
spread across the genome, to tell signal from that noise, run at night; and on the live terms page re-read.

**The second trial, run 2026-11-14** ([§ 7](probes/ALPHAGENOME2_METHYLATION_TRIAL.md#7-trial-2-2026-11-14-a-signal-at-strong-mqtls)):
**a signal at strong mQTLs**, by a rule fixed before scoring. At 42 strong blood mQTLs on 18 chromosomes (ARIES,
middle age), the predicted shift at the published CpG was 27 times the shift at 84 matched non-mQTL variants
(median 0.49 against 0.018 logit, p = 3e-12), and 28 of the 31 readable signs agreed (p = 2e-6). It holds within
about 100 bp of the CpG, likely to 300 bp, and not beyond; trial 1's moderate mQTLs read at the null level, so
moderate effects are untested. Sizes move with the input window (−44% to +103% at 16 kb), signs do not. So what a
module could carry is a **predicted direction** for a variant already known as a strong mQTL, at a named CpG within
300 bp, stamped with model, condition, track and window, never a size and never a score for an arbitrary variant.
The live terms are newer than the vendored copies (Output Terms 2026-10-09, Additional ToS 2026-11-06): still
non-commercial with notice and the Use Restrictions as a term, and training any model on the output is now barred
except AlphaGenome-like ones. **So step 3, the design, is open** and goes to RM317's design interview; a third
trial on moderate mQTLs is the natural next measurement, wanted only if the design needs more than strong leads.

**Residuals** none yet.

## RM56 (policy half) — the rule for a measurement that spans bins

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: the real repeat-caller output it waits on is TRGT's, the same evidence as RM319. The status line below predates this.

**Severity** high on the flagship example · **Status** 0.6 ships withhold plus an explicitly
not-implemented warning; **the policy lands here, gated on real caller output** · **Owner** format
(schema) + compiler

A real repeat call is `RUC=38, CIRUC=-5,5` — `[33,43]`, crossing all three Huntington thresholds, so
`htt_repeat_expansion` says *benign*, *uncertain* and *fully penetrant* at once. 0.6 makes withholding
the stated behaviour and says loudly that no policy exists yet.

**The policy is a closed vocabulary** — withhold / take the worst bin / take the point estimate — stated
by the curator and applied by the consumer. That is annotation rather than measurement, so it stays
legal. **Its grain is deliberately undefined**: per table matches how the decision is actually made (a
stance on a whole disorder), per row is more expressive and nobody has demonstrated the need.

**The prerequisite is a real caller VCF**, so the vocabulary is fixed against what callers emit rather
than against a guess. Same gate as RM65; RM66's evidence arrived separately (see its entry).

**Never** widen the measurement into an interval on the row (`measure_min_observed` and friends): that
puts a *measurement* in the module, which the data-agnostic north star forbids outright.

## RM65 (implementation half) — repeat and copy-number tables are positional

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: its coordinates wait on a real repeat-caller VCF, which TRGT's output (RM319) is. The status line below predates this.

**Severity** medium · **Status** 0.6 corrects the false claim in the code; **the coordinates wait here**
· **Owner** format (schema) + compiler

§5.6 says POS and SVLEN specify the interval a copy number is defined over; §5.7 says a `<CNV:TR>`
record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based callers"*. So
a tandem repeat and a copy-number segment are **loci with coordinates**, emitted at fixed published
positions, and the compiler's claim that these tables are unjoinable *"which is a property of what they
describe rather than a gap"* is false for both. 0.6 fixes the comment.

**Adding the coordinates waits on a real repeat-caller or CNV VCF sample, or a consumer field report.**
Without one it is scaffolding in thin air — and it is not free: it would put two more tables into RM43's
coordinate-filling path, taking that lane from three tables to five.

**And it carries an RM87 obligation, noticed while that lane was being built.** The reverse writer's
positional-table pass hard-codes `locus_index = 0` (`_write_resolution_csv`, the second loop), which is
honest only while those tables never expand — true today, since RM43's fill is one locus per row.
Putting coordinates on the repeat and copy-number tables is exactly what could make one of them expand,
and the `0` would then be a wrong number rather than a trivially correct one. Not a blocker for RM65;
a line whoever implements it must clear.

## RM66 — one repeat locus, several motifs

**Stays in 0.9, the pm (2026-11-05)**: it is in the PacBio zone: TRGT writes several motifs per locus (RM319's `FORMAT/MC`), and STRchive's `locus_structure` already decides it. The status line below predates this.

**Severity** medium · **Status** deferred here; filed beside RM65, but **its evidence has since arrived on its own** (below) · **Owner** format (schema)

§5.7: a `<CNV:TR>` allele *"can encode multiple different repeat motifs in a single allele"* (`RN=3`,
`RUS=CAG,TG,CAGG`). `RepeatAlleleRow` is keyed `(gene, repeat_unit)` and binds one count to one motif.
For HTT the interruption structure `(CAG)n(CAA)(CAG)` is exactly what a modern caller reports as several
`RUS` entries, and the pure-CAG tract length differs from the total — a difference with published effect
on age of onset. The key cannot say which count the thresholds are about, and two motifs for one gene
read as two unrelated groups rather than components of one allele.

A keying change on a shipped table, which is the expensive kind. Filed beside RM65 so both would
arrive with the same evidence — **and they no longer will (2026-09-01,
[RM165](ROADMAP_HISTORY.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring)).**
STRchive publishes `locus_structure` on 23 of 82 loci as typed data with its own three-member
vocabulary, HTT's being exactly the `(CAG)n(CAA)(CAG)` structure above; that is enough to *decide* this
item and not enough to make the answer universal. RM65's prerequisite — a real repeat-caller or CNV
VCF — is still missing, so the two items now wait on different evidence and this one is decidable
first.

## RM67 — polyploid and partially-phased genotypes

**Stays in 0.9, the pm (2026-11-05)**: it is not work, so it is a note here, not a parked item. The status line below predates this.

**Status** **not work** — a documented divergence, numbered so it is findable and not re-probed

VCF 4.4 §7.2 added polyploid partial phasing (`GT |0|0/1/2`), first phasing indicator optional. Our
grammar caps at two alleles and refuses a leading separator (probed: `A/A/G` and `A|G/T` both rejected).

This is a **defensible generalization** — the format annotates human diploid loci, and
`_check_contig_ploidy` already handles the hemizygous and haploid directions. **No change proposed.** The
spec's own polyploid example is a tandem duplication with SNVs on it, which a CNV-aware consumer will
meet, so revisit if one actually does.

**The message changed on 2026-08-14; the decision did not.** Dogfooding a duplicated CYP2D6 — the
spec's own polyploid example — refused the call with a bare restatement of the grammar, so a deliberate
limit read as a syntax error, while every other deliberate refusal in this schema names its own limit
in-line. The arity refusals now carry that sentence: two alleles is a decision, VCF 4.4 §7.2 permits
more, and nothing is queued against it. Recorded as D3-2 in
[DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md).

---

# Vocabulary residue from the 0.7 consumer round

## RM149 — expected behaviour lives in prose, and the prose is where two readers split

**Frozen, decided 2026-11-03.** The maintainer froze the Gherkin work. The verification bench beside the seats kit (`harness/bestiary`) marks all eight of its Gherkin entries retired by their origin, after the acceptance pipeline's originator reversed on it in September 2026, and the same day the maintainer chose TLC model checking over Gherkin for the kit's own acceptance work. Nothing here is built until that is reopened; the status line below predates it.

**What the freeze leaves running, decided 2026-11-03.** The maintainer kept the corpus gate:
`schema/tests/test_feature_corpus.py` still fails a new warning code that has no scenario, so `features/`
keeps growing as text with each new code, and with no runner. The freeze stops the review and the runner work
this entry asked for, not the corpus.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-21; asked by the maintainer
2026-08-31** · **Owner** format + compiler (the test corpus) · **Found by** running the consumer loop

**The ask, verbatim in intent:** express our described scenarios as Gherkin, because the freeform prose
in expected-behaviour descriptions is producing ambiguities faster than it resolves them.

**The evidence for it is this repo's own recent record**, which is what makes this an item rather than a
preference. Three consumer reports in one week were **two readers splitting on one sentence**, none of
them a code defect:

- **S80** — `state`'s six members printed as peers; an agent chose a retired one honestly.
- **S83** — two runs of a byte-identical prompt wrote `risk` and `unknown` for one variant on one body
  of evidence, both green, both defensible against the field description.
- **S79** — a warning's text read as *your declaration is unsupported* when it meant *not universal*.

Each was answered by writing a better sentence. That is three fixes to prose in a week, and the pattern
says the next one is already in flight somewhere.

### What is actually being asked

Not a testing framework — the suite is not the problem, and a `pytest`-to-`behave` migration would be
motion rather than progress. The gap is that a **scenario** — *given a module with a partial
`resolution.csv`, when `validate --strict` runs, then it refuses with the compile's own error* — exists
today as a docstring, a test name, and a paragraph in `COMPILER.md`, and those three can drift from
each other and from the code. A structured form is one statement, and the natural home is a
`.feature`-shaped corpus each side is derived from or checked against.

### Open questions this needs decided before it can be built

- **What is the source of truth.** Gherkin generated *from* the tests is documentation that cannot
  drift; tests generated *from* Gherkin makes the feature files the contract and every existing test a
  migration. These are opposite projects with the same output, and the ask does not say which.
- **What is in scope.** Every check the compiler runs is ~140 warning codes plus a mode ladder. The
  release-gate scenarios, the tri-state outcomes and the parity rules are the parts where ambiguity has
  actually cost something; the round-trip fixed points are already pinned by assertion and would gain
  nothing from prose.
- **Where it lives.** A `features/` tree at the root, per-package, or inside `docs/`. That decides
  whether it ships to consumers — and if it does, it becomes a published surface under P3, which is a
  much larger commitment than an internal one.
- **What it costs the next contributor.** A second dialect to learn beside the docstring convention
  this repo already leans on heavily, and every new check owing a `.feature` clause. That is the P9
  question one layer up: this is a *maintenance* surface, not an authored one, and it is not free.

### Why it is filed rather than started

The three reports above were each fixed by naming what the rule is, and the fix was one string. A
scenario corpus is worth building when the *cost of ambiguity* exceeds the cost of the corpus, and the
measurement that would show that has not been taken — this entry is where it goes when it is. What is
not in doubt is the direction: the recurring failure is real and repeatedly measured, and it is filed
here so the next instance lands against a number rather than as a fourth anecdote.

### Addendum, 2026-09-13 — a first corpus is drafted, and this is the measurement

**Status is still open.** What exists is a draft, unreviewed, at `features/` in the repository root:
12 `.feature` files, 213 scenarios, guarded by `schema/tests/test_feature_corpus.py`. Nothing
about it is a contract yet, and the entry stays here rather than moving to ROADMAP_HISTORY until it has
been read.

**Two of the four blocking questions are answered by the ask itself**, and are recorded in
`features/README.md` as assumptions rather than decisions:

- **Source of truth: code → Gherkin.** The scenarios describe what the code does. No step definitions,
  no `behave`, no `pytest-bdd`, no new dependency in any tier; the `pytest` suite stays the executable
  statement of behaviour and this is the readable one.
- **Where it lives: the repository root, not `docs/`.** That keeps the P3 publishing question *open*
  rather than answering it by side effect, which a drafting round has no standing to do.

**Scope is decided by registry rather than by taste**, which is the third question. Three walked sets
are covered in full: `VALID_WARNING_CODES`, `VALID_VERIFICATION_CHECKS`, `VALID_VERIFICATION_SKIPS`.
Round-trip fixed points are out, on this entry's own argument. **And the scope estimate in the body
above is wrong by a factor of two**: it says *~140 warning codes*, and `VALID_WARNING_CODES` has **73**.
A number in prose beside a registry, in the entry that exists because prose drifts — left in place
above rather than silently corrected, because it is the fourth instance of the shape this round
measured and the most on-the-nose.

**The fourth question — what it costs the next contributor — has a partial answer and it is the
cheaper half of the estimate.** A new warning code without a scenario fails the guard, so the cost is
one scenario per code, not a second dialect to learn: there are no step definitions to write and no
runner to learn. What is *not* yet measured is whether a reviewer finds the scenarios easier to check
than the docstrings they stand beside, and that needs a reader rather than a round.

#### The measurement this entry was waiting for

The case for the corpus was to be made on *the cost of ambiguity exceeding the cost of the corpus*.
Drafting it produced **four findings in the first pass**, two of them code-or-doc defects that were
filed and fixed rather than noted:

| # | finding | disposition |
| --- | --- | --- |
| 1 | **Two of our own documents disagree about whether `strict` builds.** COMPILER.md's validate-by-redundancy table gives the rsid↔coordinate check the severity *warning* with no qualifier; its own mishap matrix gives the same check *⚠️ warning / ❌ refuses*. The matrix is the half the code agrees with. | marked `# DRIFT:` in `features/compiler/mode_ladder.feature`, unrepaired — the round's findings are its output |
| 2 | **The mode ladder is two mechanisms and reads as one.** Four codes flip channel on one sentence; three resolution codes pair a warning with a *different, longer* refusal through `ResolutionOutcome.strict_errors`. Calling those ladder members quotes a text that does not exist; calling them warn-only describes a compile that succeeds. | written down in the same feature; no defect, a distinction nothing stated |
| 3 | **`alphagenome check` with no API key raised instead of recording a skip** — `skipped(CHECK, "unchecked")`, and `"unchecked"` is not a vocabulary member. | **[RM242](ROADMAP_HISTORY.md#rm242--alphagenome-check-without-an-api-key-raised-where-it-was-supposed-to-attest-nobody-asked)**, fixed |
| 4 | **Four per-command attestation counts summing to 17 of 24**, in ENRICHER.md's paragraph that refuses to state a total. | **[RM243](ROADMAP_HISTORY.md#rm243--the-paragraph-that-refuses-to-state-a-total-stated-four-of-them-summing-to-17-of-24)**, fixed |

**What produced each of them is worth separating from the fact that they were produced.** None came
from reading prose more carefully. Finding 1 came from writing the severity down as a table and
noticing two tables; finding 2 from having to name a mechanism in order to tag a scenario; findings 3
and 4 from AST walks the corpus needed anyway — the emission-site check and the skip-reason enumeration.
So the argument this addendum supports is narrower and stronger than *Gherkin is good*: **the act of
deriving a scenario from an emission site is what found things, and the guard is what will keep
finding them.** A corpus of prose scenarios with no grounding check would have found none of the four.

#### The three assertions that make it worth more than the prose — and what each really covers

Each was proven by reintroducing the defect and watching it go red, which is this workspace's standing
requirement. Two of the three were **narrower than they read on the first pass**, and both narrowings
were found by measuring rather than by re-reading, which is worth recording because a guard that
half-covers its subject while the reference claims it covers all of it is worse than no guard:

- **a `@code:X` scenario's `# source:` sits within three lines of X's own `CodedWarning` call.** Held
  from the start.
- **the same alignment for `@check:` and `@skip:`.** *Missing at first*, and it cost precisely what it
  exists to prevent: RM242 and RM243 — the two fixes this round produced — inserted six and eight
  comment lines above referenced sites, eleven `# source:` lines silently began pointing six to eight
  lines early, and the suite stayed green, because those two tags had only *the line is inside the
  file*. The guard now catches all fourteen when the insert is reproduced. Two of the eight skip reasons
  (`tautology`, `not_permitted`) are never passed to `skipped()` as a literal at all — they travel as a
  variable — so the alignment is against any literal naming the reason, which is the better pointer
  anyway: where a reason is *decided* is what a reader wants.
- **every phrase a step quotes as a warning's text is a real substring of a real string literal in the
  module named.** *Keyed on a verb before the quote at first* (`contains`/`says`/`states`), which
  extracted **46 of the 162** quoted phrases — a `Then` also says `saying the flag "…"`, `ends at "…"`,
  `continues "…"`, `offers "…"`. Keyed on the step keyword instead, it now checks **160 of 160** on
  outcome steps, and the widening found three real defects in the corpus. `Given`/`When` stay excluded:
  those name an input value, which has no reason to appear in the module's own strings.

**The residue, measured rather than estimated.** Of 213 scenarios, **108 carry a registry tag and are
aligned; 105 are structural** — pointing at a docstring, a branch or a constant, with no call site to
align against — so they carry only the *line is inside the file* check and will rot on an edit above
them. Measured 2026-09-13 by walking the corpus, because the first draft of this paragraph said
"roughly 130" on an estimate, in the document whose whole subject is unmeasured counts beside
registries. That is a real contributor cost and it belongs in the fourth question's answer above rather
than in a footnote.

One mechanism had to be added rather than worked around: a message built by one module and coded by
another (`layout.deprecation_notice` writes the sentence, `_locate_sidecar` names the code) needs a
`# text:` line, so the code is checked against the emission site and the phrase against the module that
holds the words. That is the boundary where a code goes missing
(`@finding-loses-its-code-at-a-boundary`), and it is better as a checked fact than a convention.

#### What a review should push on

- **Is the root the right home, or should this publish?** Publishing makes every clause a P3
  commitment. The draft assumes not, and the assumption is the thing to overturn first if at all.
- **Are the scenarios readable by someone who did not write them?** That is the whole premise and it
  cannot be self-assessed. If the answer is no, the corpus is a second dialect with none of the benefit
  and this entry should close rather than grow.
- **Should the DRIFT finding be repaired here or filed?** Finding 1 is one sentence in COMPILER.md.
  Leaving it marked was deliberate — a round that silently fixes what it finds cannot be audited — but
  it should not stay marked for long.
- **The corpus has no scenarios for the compiler's `errors` that carry no warning code**, beyond the
  handful written as `@refusal`. Whether a refusal without a code deserves the same coverage as a coded
  warning is an open scoping question the registry cannot answer, because refusals have no registry.

### Second addendum, 2026-09-13 — the second pass, and where coverage was not what the equalities said

**Still open, still a draft.** The corpus is now 13 files and **228 scenarios** — 118 registry-tagged
and aligned, 110 structural — with **182 quoted phrases** on outcome steps. The question this pass put
was the one the first pass could not put to itself: *are all the features covered?* The three registry
equalities said yes and they were answering a narrower question than they read.

**Four findings, and what produced each.** None came from reading the scenarios again; three came from
walking a set the first pass did not walk, and the fourth from reading the residue the first pass
measured and left.

| # | finding | disposition |
| --- | --- | --- |
| 5 | **A code is not a text.** Nine resolution codes are emitted by the compiler's `resolution.py` *and* by the enricher's `resolver.py`, and **seven of the nine pairs are a different sentence**. `rsid_unresolved` is *"not found in resolution table, position remains unset"* in one tier and *"not in the injected Ensembl snapshot"* in the other. The per-code equality accounted for all nine while the corpus held none of the enricher's words for any of them, and a warning's text is an API. | fixed — the equality now keys on `(code, tier)`, and `features/enricher/resolution_warnings.feature` is the nine in the enricher's own words |
| 6 | **The house algebra was covered as a mechanism and not as a value.** `tri_state.feature` had Kleene, the withhold, `classify` and `restate`, and not one of the columns that carries a three-valued answer into an artifact: **five of the nine members** of `VALID_FREQUENCY_STATUS`, `VALID_RESOLUTION_STATUS` and `VALID_AUTHORITY_CALL_STATUS` appeared nowhere in the corpus, `not_covered` among them — the member the gnomAD Y-PAR probe was run to justify. | fixed — six scenarios; the walk that found them (three-member `VALID_*` sets) is recorded as the heuristic it is |
| 7 | **`@ladder` was a judgement written four times over a walkable set.** The mode ladder's first mechanism is `(errors if strict else warnings_out)`, and the codes reachable from a function carrying that shape are exactly the four tagged. | fixed — a fourth registry equality, proven red by untagging `p_value_encodings_disagree` |
| 8 | **Ten `# source:` lines pointed at a blank line, a bare `"""`, a bare `return [` or the middle of a comment — and two pointed at the wrong subject.** *a total function cannot decide a three-valued answer* named a comment about a length constant in `normalize.py` when the rule is `mitomap.vcep_clin_sig`; *an absent input is the unknown arm* named the concordance block in `vocab.py` when the rule is `needs_recompile`. Both scenarios stated their rule correctly and cited the right tag; only the pointer was wrong. | fixed — all ten re-anchored; **not rot**, since no source file here has changed since the corpus was written, so they were authored that way and nothing could say so |

#### Two questions the first addendum left open, now answered with a measurement

- **Refusals without a code have no registry, and the reason is that they have no shape.**
  `compiler.py` alone reaches the error channel from **four** distinct mechanisms — an inline
  `errors.append` of a literal, an `extend` of a helper's returned list, the
  `(errors if strict else …)` selector, and `ResolutionOutcome.strict_errors` — across roughly forty
  sites, against 22 scenarios tagged `@refusal`/`@strict_only`. So the answer to *should a refusal
  without a code get the same coverage as a coded warning* is not *no*; it is that **there is nothing to
  walk**, and inventing a registry so an equality can be written would be the `@registry-completeness`
  defect committed on purpose. It stays a scoping question for a reviewer, now with a number beside it.
- **The phrase check's file scope is correct, and that was measured rather than assumed.** Eight of the
  182 quoted phrases match no message at the site their scenario names but do match another literal in
  the same module. All eight were read: every one is a message built into a variable a few lines away
  (`ambiguous_warnings`, `_verify`, `coordinate_disagreement`, `layout.deprecation_notice`). Tightening
  the check from the module to the call site would need dataflow and would report eight correct
  scenarios as defects. Recorded so the next pass does not re-derive it.

#### What this pass did not touch

The `# DRIFT:` in `mode_ladder.feature` still stands — finding 1 of the first pass, one sentence in
COMPILER.md, and a repair decision rather than a drafting one. And `# anchor: <token>`, a symbol the
guard could grep for instead of a line number, is the obvious repair for the 110 structural scenarios
and is deliberately unbuilt: it is a convention change across the whole corpus and belongs to whoever
reviews it.

**Not to be confused with** `just-module-creator`'s authoring guidance, which is a different
document for a different reader and stays prose. This is about *our* stated behaviour, not an author's.

# The lifecycle items — what writing down the second pass surfaced

Filed on **2026-08-16** out of [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md), which mapped a module from
origin to publish to a consumer's join and found that **the second pass had never been written down at
all**. Four items, none of them a defect in a rule: each is a place where two individually-correct rules
compose into something nobody chose, or where an absence only bites the second time somebody opens a
module. The document keeps the measurements (§5.1 the canary, §6.2 the six-edit consequence matrix, §6.3
what deleting a sidecar costs); these entries keep the decisions and the refused repairs, and do not
restate the numbers.

They were the closing section of that document — an "open questions" list — which is exactly the shape
this repo has twice found to be a backlog nobody reads. A question filed against a release is findable;
a question at the bottom of a prose document is not.

Everything here is legal in a minor.

## RM84 — a module has no version identity on the discovery path, and the publisher is the half we own

**Stays in 0.9, the pm (2026-11-05)**: the open half is the consumer's, so it is a note here, not a parked item. The status line below predates this.

**Severity** medium-high · **Status** **our half SHIPPED in the 0.6 PT2 batch (lane D, 2026-08-17)** —
`upload_module` writes `data/<name>/` and `data/<name>/v<version>/`. **The segment spelling is settled
and both asks are answered** ([S35](CONSUMER_SUGGESTIONS_HISTORY.md), 2026-08-17): `v<version>` verbatim
stays. Only the consumer's discovery half is open, and it is theirs, which is why this entry stays here.
*Previously:* our half taken into 0.6 PT2 on
2026-08-16 ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM84); before that, open — **joint with the
reference consumer, and their half is already agreed in writing** · **Owner** enricher
(`upload.upload_module`) + `just-dna-lite` discovery ·
**Motivating case** a republished module on the HuggingFace path

**Why a partial mitigation does not close it** (S34 §3): the fields a consumer can read today record
*where* a module came from, never *which build* of it. Two uploads under one path are then
indistinguishable on the discovery side, which is the half this item exists for.

### What was observed

[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) traces two
acquisition paths with two entirely different notions of "updated", and neither delivers a notification.
The registry path at least has a per-version audit. The **discovery path has no version identity at
all**: no version in the path, no manifest fetch, no digest check. A republished module keeps the same
URL, so a cached copy shadows it, and the only invalidation is a purge keyed on the *consumer
application's own package version*. Stated plainly: on that path the identity used to detect "the module
changed" is a property of the reader, not of the module. A module republished with new science while the
app stays pinned is invisible; an app patch release with no module change purges everything.

**Half of that is ours.** `just_dna_enricher.upload.upload_module` writes the flat `data/<name>/` layout
— so this tier publishes the shape that cannot express a version, and no amount of consumer-side work
invents one.

### Why it is joint rather than ours alone

A pinning surface is a change to our publisher **and** to their discovery in the same breath: a version
segment nobody reads is dead bytes, and a reader looking for a segment nobody writes finds nothing.
[S34 § 4](CONSUMER_SUGGESTIONS.md) is the consumer's half, already stated: *"If the publisher grows a
version segment we will follow it in discovery; the `vN` fallback in our generic fsspec scan is already
the shape."* That is as close to a pre-agreement as a cross-repo item gets, and it makes this cheaper
than "wants agreeing" implied when it was first written down.

### What is undecided

*Was:* the layout itself — a `vN` segment, a digest segment, or a pointer file — and what happens to
every module already published flat, which is all of them. Whatever is chosen has to leave an
unversioned path working, because that is what is deployed.

**Settled on our side.** The layout is the dual write, decided in PROPOSAL_0_6_PT2 § RM84 and built in
lane D. Nothing already published moves, because the flat path keeps being written and keeps meaning
*latest*. The full behaviour, including the null-version fallback and the two-commit caveat, is
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

### The ask was put, and answered the next day — both questions closed

**Asked** in ENRICHER.md (RM27's shape: a finding about a downstream reader is an explicit ask, never an
implication), delivered there rather than into their tree because `just-dna-lite` carries no consumer
inbox. **Answered as [S35](CONSUMER_SUGGESTIONS_HISTORY.md) on 2026-08-17**, read off their code file
and line rather than recalled.

*(1)* **Their scan matches only `v`-plus-integer** — `^v(\d+)$`, compared with `int()`, so `v1.0.0` does
not match and `v10` would sort under `v9`. **The half that actually decides it is their correction, not
the regex:** that fallback lives only in `_discover_fsspec_source`, the generic github/http/s3 branch.
HuggingFace has its own branch with **no version fallback at all** — so on the path this item is *about*,
no spelling is read today and the segment cannot be chosen to suit one. Their words: S34 § 4's *"the `vN`
fallback in our generic fsspec scan is already the shape"* was accurate about the shape and quoted about
a branch that does not serve HF, and they call that their error rather than a misreading here.
**So `v<version>` verbatim stays** — a bare major segment would still collide two patch releases at one
path, and would buy nothing since the code that would read it is not on this path.

*(2)* **No, and by construction rather than by luck.** Both discovery branches call `fs.ls` at exactly
one level and never `fs.find`, a `**` glob or a recursive listing, and their probe asks `fs.exists` on
named files rather than listing the directory it is probing — so a nested `data/<name>/v<version>/` is
never enumerated and never probed. Verified in their tree by search: no `fs.find`, `recursive=True`,
`maxdepth` or `snapshot_download` against a module path anywhere. The one part of this change that could
have regressed a consumer who never adopts it, and it does not.

**One consequence recorded rather than fixed**, raised by them as a consequence and not an objection:
the dual write doubles the collection's bytes and nothing prunes `data/<name>/v<version>/`, so the repo
grows one full artifact set per release forever. It does not affect discovery. Retention is the
collection owner's decision, not the publisher's; noted in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

**What is left here is theirs and unscheduled:** teach `_discover_hf_source` a versioned fallback, and
replace the regex and `int()` with `just_dna_format.identity.Version`, which already gives them parsing
and ordering. Nothing is broken meanwhile — the flat path resolves and keeps meaning *latest* — so their
`read_module_provenance` states `version: None` for every HF-discovered module, which their report
renders as *Not stated*.

**Confirmed by exhaustive search to have had no `Sn` and no `RMn`** before this entry, which is why it
is filed rather than cross-referenced.

### Two items building this surfaced, filed 2026-08-17 rather than folded in

Both were found by writing the code, not by planning it, and neither is a defect in what shipped —
recorded here because this entry is where a reader meets the publisher.

- **[RM88](history/ROADMAP_HISTORY_0_6.md#rm88--republishing-without-bumping-version-overwrites-a-versioned-path-with-different-bytes)** — the versioned path cannot notice that the version has *not* moved, so a republish
  without a `version:` bump overwrites it with different bytes. Refusing needs a remote read *and* an
  undecided policy (warn / refuse / `--force`), which is why it is an item and not a fix.
- **[RM89](history/ROADMAP_HISTORY_0_6.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all)** —
  `_REQUIRED` still demanded all three SNP-core parquets, so a table-only module could not be published
  at all: seven of the sixteen reference examples, measured. Its open question — what the discovery path
  actually needs open — went to the same team as the two asks above rather than as a third message, and
  **came back with them in S35, so it shipped on 2026-08-17**. Answering it found the larger half:
  `_ALLOW_PATTERNS` carried no 0.4 family and no derived-fact table either, so eight *more* examples
  published a manifest attesting parquets that were never uploaded.
