# Integrating 0.9 — what changed against the 0.8 surfaces

For the repos that consume this one: **just-dna-registry**, **just-dna-lite**, **just-dna-pipelines** (inside
just-dna-lite) and **just-module-creator**. It answers one question: *given a working 0.8.10 integration, what do I
have to check, and what do I have to change?* § 1 is the surface delta, item by item. § 2 is the upgrade order and
the changes it implies, by surface. § 3 is the same list cut per consumer. § 4 lists the known issues 0.9 ships with.

**What 0.9 is.** One theme, set by the pm on 2026-11-16: *the enricher reads its reference data wherever it lives*,
local disk first, then the registry's proxy, then Hugging Face. Six items: RM430 and RM431 (remote reads and the keyed
readers they need), RM437 (the Ensembl snapshot's optional column groups), RM443 (`lane_status` for a host that passes
its own paths), RM404 (`enrich` takes a host's clients and sequence proxy) and RM412's second half (the 0.8 line's
private names made public, and `--rehearse-download`). **The rescope of 2026-11-26** then built nine of the first
cut's own leftovers in 0.9 rather than shipping them as known issues and patches: RM454, RM458 and RM461 to RM467
(§ 1.13 lists them), and RM470, ClinVar-GKM's new release line, was folded in at the redone cut (§ 1.14). The enricher moves, the format tier gains two functions (`parse_release` and `is_whole_build`),
and **the compiler's source does not move at all**.

**Status: cut as 0.9.0 on 2026-11-26, on the local branch `cut/v0.9.0-2` (off `0.9`).** A first cut, on 2026-11-19
(`cut/v0.9.0`), was never published; the rescope built its leftovers and the cut was redone. All three packages are
`0.9.0` (one number per cut: format changed, so the compiler moves for its floor and the enricher for both), every
intra-workspace floor is `>=0.9.0`, and no third-party floor moved. Publishing to PyPI is the maintainer's; the tag
`v0.9.0` follows the publish. PyPI's latest at the cut is 0.8.10 for all three.

**Pin the release:**

```toml
dependencies = [
    "just-dna-format>=0.9.0",
    "just-dna-compiler>=0.9.0",
    "just-dna-enricher>=0.9.0",
]
```

A consumer that holds only the format tier pins the first line alone, and need not move at all (§ 1). A host whose
CPU lacks AVX-512 or AVX2 pins `just-dna-compiler[compat]` or `just-dna-enricher[compat]` instead (§ 1.15).

**The release record says nothing moves on a recompile.** `release_records.RELEASE_RECORDS["0.9.0"]`, measured at the
cut against compiler 0.8.10 on the 22 reference modules, records every axis unmoved (no `parquet_schema`,
`parquet_bytes`, `content_signature`, `manifest_fields` or `warnings` move), so `needs_recompile(stamp, "0.9.0")`
answers that a 0.8.10 artifact needs no recompile for 0.9's sake. Its evidence also quotes the measurement of `enrich`
(§ 1.11).

**Consumer pre-integration (RELEASE_CYCLE § Minors step 6) runs on the rescoped branch.** The consumers try `0.9`
before it merges into `main`, and the merge waits for their trial ([desk #370](https://github.com/winternewt/desk/issues/370));
the two that reported on the first cut are told what the rescope added and are not asked again. 0.8.10 was published
and tagged before 0.9.0, as fixed. A defect a consumer finds is filed as an `Sn` in
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md), and the release cycle sizes its fix.

[RM_TOC.md](RM_TOC.md) is the per-item record, and the [CHANGELOG](CHANGELOG.md)'s 0.9 heading carries every change
in detail; this file says what a consumer does about them.

---

## 1. The surface delta

### 1.0 No old-reader break: nothing a compiled module carries moved

Checked against `git diff 0.8.10...0.9.0` (the release gate of RELEASE_CYCLE § Minors step 7):

- **No new warning code.** `VALID_WARNING_CODES` is unchanged, and so is every other vocabulary in
  `just_dna_format.vocab`.
- **No new manifest field, parquet, parquet column or `verification.json` reason.** `manifest.py`, `spec.py`,
  `verification.py` and the compiler are untouched; the format tier's one change is a new function (§ 1.1).
- **No new release-change kind.** `RELEASE_RECORDS["0.9.0"]` uses the existing axes and kinds.

So a format reader on any 0.8 release reads every module 0.9.0 compiles, and a 0.9 reader reads every 0.8 module.
The sweep measured the compiled outputs themselves: 22 of 22 reference modules alike between compilers 0.8.10 and
0.9.0 on every axis.

**`rsid_genotype_reads_as_two_events` is not in 0.9 (RM460, for 0.10).** RM449's closure said 0.9 would add the
code and move its mirrored-site sentences to it. It was never in 0.9's scope, and the pm placed it in 0.10 at the cut
(2026-11-19). So 0.9.0 behaves as 0.8.10: RM449's and RM453's sentences borrow `rsid_expanded_to_multiple_loci`, and
`rsid_no_hosting_locus` where an authored coordinate row claims every spelling of the site, and `warnings_summary`
counts a site narrowed to one locus as an expansion. **When the code lands, it is an old-reader break:**
`warnings_summary` validates its keys against the closed `VALID_WARNING_CODES`, so a format reader older than the
release that adds the code refuses a manifest carrying it (`pydantic.ValidationError` on `warnings_summary`; measured
on `hboc_palb2` at 0.8.9, and checked again on format 0.9.0 at this cut). The INTEGRATION file of that minor will tell
consumers to raise their format floor first, as INTEGRATION_0_8 § 1 did.

### 1.1 Format: `snapshot.parse_release` (RM430, no break)

`just_dna_format.snapshot.parse_release(data, *, source="release.json") -> SnapshotRelease | None` reads a
`release.json` from its bytes or text, for a reader that fetched the record rather than opening a file. `read_release`
now calls it with the file's bytes, so the same bytes give the same answer locally and remotely: content that is not
JSON or not a JSON object is `None` with a warning, and a typed key holding the wrong kind of value is dropped with a
warning naming it while every other key, the label included, is still read. It takes no path and fetches nothing (the
charter's snapshot-layout goal). `release_is_unreadable` keeps a private strict reading. **The enricher imports it**,
which is why the enricher's floor on format is `>=0.9.0` (§ 2).

### 1.2 Remote reads: `just_dna_enricher.remote` (RM430, no break; off unless a caller holds one)

A new public module for a box with no local snapshot, reading a lane from the registry's proxy and then from Hugging
Face. **Nothing changes for a caller that does not opt in:** no holder, no remote read, and every existing call reads
and fetches exactly what it did.

- **`RemoteSnapshots(*, proxy_url=None, proxy_token=None, huggingface=True, declared_use="unstated",
  hf_base_url=None)`**, a context manager. The proxy is `proxy_url`, else `$JUST_DNA_SNAPSHOT_PROXY_URL` (token:
  `$JUST_DNA_SNAPSHOT_PROXY_TOKEN`); with neither it is skipped. It is unset by default, as the registry asked, so its
  own server never picks it up by accident.
- **`lookup(lane, table, keys) -> RemoteAnswer`**, where `RemoteAnswer(rows, route)` and `route` is a
  `RemoteRoute(route, release, served_from, revision)`. `route` is `proxy` or `hf`; a proxy answer's `release` and
  `revision` are what the reply states, else `None`; `served_from` is withheld when any reply leaves it unstated, and
  joined in sorted order when the replies state different places.
- **Eligible lanes** (`remote.REMOTE_LANES`): `ensembl` (by `chrom` + `start` only, never by rsID), `clinvar`,
  `constraint`, `clinpgx`, `cpic`, `drug_labels`, `opentargets`, `civic`, `clinvar_gkm`. A gated lane goes through
  `check_declared_use` with the holder's `declared_use` before its first remote read.
- **The proxy** is asked in requests of at most 100 values and one chromosome; a truncated reply is halved down to one
  key, and a single key still truncated is could-not-ask for that key. It falls through to Hugging Face on 429, 503,
  504, 404 `lane_not_available`, a timeout or a connection error, and on a request over its per-request limit.
- **Hugging Face** is read through duckdb's `httpfs` at the commit `main` names at the lane's first read (one pin per
  lane per holder), with the release label from `release.json` (Ensembl: `manifest.json`). **`httpfs` is loaded with
  auto-install off, so install it ahead of time** on every box that reads remotely:
  `python -c "import duckdb; duckdb.connect().install_extension('httpfs')"`.
- **Errors.** Could-not-ask is `remote.SnapshotRouteUnavailable` (`lane`, `route`, `cause`), with the subclass
  `SnapshotRouteRetired` for a 410. A wrong request (a proxy 422, an unknown lane, table or column, a lookup on a
  closed holder) is `ValueError`.
- **`close()` waits for the lookups in flight**, then refuses every later lookup with `ValueError`
  (`remote.HOLDER_CLOSED`). **A host that shares one holder across requests closes it after its last lookup**; a
  lookup that reaches a closed holder, like a proxy 422, raises out of `lookup_variant` as a programming error on the
  host's side, never an `unchecked` finding.
- **`LookupClients.snapshots`** is the new field the `lookup_*` functions read; nothing builds it lazily.
  `lookup_variant` reads a lane remotely in the local snapshot's place, before live Ensembl REST, never under
  `offline=True`, and **`VariantHint.routes: dict[str, RemoteRoute] | None`** is set only for lanes answered
  remotely. A route that could not be asked is a `warning` finding, never an empty answer. `enrich()` does not read
  remotely in 0.9.
- **The remote Ensembl link withholds an rsID's placement**: Ensembl is asked remotely by position only, so its rows
  there give rsID candidates and no locus, and ClinVar, asked next by rsID, places it.
- **`RemoteRoute.release_unreadable`** (RM461) carries the proxy's own boolean about its copy of `release.json` when
  every reply of a split lookup states the same one; a missing, malformed or disagreeing flag, and the Hugging Face
  route, give `None`. A proxy lookup is split along the column holding the most values (`start` on a tie), so a
  request with many values in another column no longer exceeds the per-request limit and falls through.
- **`lookup_variant` asks remote ClinVar twice at most** (RM462): one read by rsID and one by position, the position
  reply also answering the clinical calls. One request is not possible (the proxy matches every column it is given,
  and one Hugging Face read of both questions would lose the keyed row-group pruning).

`LookupClients` and `CLIENT_FIELDS` now live in the leaf module `just_dna_enricher.clients`; `lookup.LookupClients`
and `lookup.CLIENT_FIELDS` still import, as the same objects.

### 1.3 One key compare per column on every route: `key_compare.KEY_COMPARES` (RM430, no break)

The new leaf module `just_dna_enricher.key_compare` holds `KeyCompare` (`fold`, `separator`; `key`, `members`,
`predicate`, `parameter`, `exact`, `described`, `rsid`, `cell_exact`), `EXACT` and **`KEY_COMPARES`** (lane → table →
column), the one registry the local SQL of `clinpgx`, `drug_labels`, `civic_draft` and `cpic` is built from and the
holder reads, so a key answers the same on the local and the remote route. **The registry reads `KEY_COMPARES` from
its release that floors 0.9** (its S36): it is an outside reader's contract now, and stays stable within the 0.9
line.

Two local answers widen, never narrow:

- **cpic's local gene compare now trims** (`lower(trim(gene))`), as every other folded compare does, so a gene cell
  with surrounding whitespace matches where it did not. It can only add a match.
- **`CpicSnapshotClient.partner_genes` no longer lists `None`** as a partner where a recommendation row states no
  gene: the negated compare treats `NULL` as no match, as the old `<>` did.

**`KEY_COMPARES` now covers the local readers too** (RM454): Ensembl's `id` (an rsID read as one), ClinVar's
`rsid`, `chrom`, `gene` and citations, and the constraint, MANE, PharmVar, PubMind and Open Targets keys, beside the
remote lanes. A gene compares by `gene_key` on both sides, the SQL fold derived from it (Unicode whitespace and case
folding included, about 0.6 s once per process), and a contig by the format tier's reading. These answers widen too:
**a constraint lookup finds a gene asked in another case**, and the gene-metrics pass indexes the answer by the same
key, so an authored `BrCa1` resolves offline against the snapshot's `BRCA1` while `gene_metrics.csv` keeps the
authored spelling. A direct `lookup_loci` call spelled `RS334` or `chr11` now matches. A module never sends those
spellings, so no reference module's output moves.

### 1.4 Keyed functions on the whole-table readers (RM431 asks 5 and 6, no break)

Each runs in duckdb beside its loader (the loaders are unchanged), answers `{key as asked: [rows]}` as plain dicts,
and runs one SQL body over the local file and over a remote answer's rows:

| Function | Keys | An absent or unreadable snapshot |
|---|---|---|
| `opentargets.lookup_variants(reference, positions)` | `(chrom, position)`, never `variant_id` | `OpenTargetsError` |
| `opentargets.lookup_consequences(reference, variant_ids)` | `variant_id`; rows tagged with their `table` | `OpenTargetsError` |
| `civic_draft.lookup_genes`, `civic_draft.lookup_rsids` | gene by `gene_key`; rsID | `CivicDraftError` (the raising reader's semantics) |
| `clinvar_gkm.lookup_variants`, `clinvar_gkm.lookup_rsids` | `chrom` + `start`; rsID | `ClinVarGkmError` |
| `clinpgx.lookup_rsids`, `clinpgx.lookup_genes` | rsID; gene, member by member of the `;`-joined cell | `ClinPgxEnrichmentError` |
| `drug_labels.lookup_genes` | gene, member by member of `genes` | `DrugLabelUnavailable` (absent), `DrugLabelError` (unreadable) |

An rsID is read as the local reader reads it (`RS334` and `334` are `rs334`), on every route.

### 1.5 The Ensembl rsID index, a derived local lane (RM431 ask 4, no break)

`ensembl_rsid_index`: rsID → (chrom, start) over the split Ensembl core, sorted by rsID
(`data/ensembl_rsid_index-<bucket>.parquet`, columns `rs`, `chrom`, `start`), so a lookup by rsID prunes instead of
scanning. Measured on the 2026-07-13 release: 6,074 MB, 2,524 s to build (about 11 GB of staging at peak), one rsID
in 0.15 s against 6.2 s scanned.

- **Built only when named**: `just-dna-enricher cache rebuild --only ensembl_rsid_index`
  (`ensembl_rsid_index_build.build_rsid_index`). A bare `cache rebuild` reports it *not run*, `cache prepare` never
  builds it and names the command, and no pull or `enrich(download=True)` pays for it. Never published, not
  remote-eligible. New: `CacheLane.named_only` (the reason; `None` on every other lane) and `RebuildRequest.named`
  (default `True`).
- **It pins the core it was built from** (`release.json` `parents.ensembl`: the manifest's `release_id` and a digest
  of its attested files). `resolver.lookup_loci` by rsID reads it only when it pins the core it was handed; an index
  of another core is refused with a warning naming the rebuild, and the core is scanned.
- **Where it is looked for:** `$JUST_DNA_ENSEMBL_RSID_INDEX_CACHE`, else beside the default caches
  (`locations.ENSEMBL_RSID_INDEX_SUBDIR`, `ENSEMBL_RSID_INDEX_CACHE_VAR`, `resolve_ensembl_rsid_index_reference`,
  `default_ensembl_rsid_index_cache_dir`). A host that passes paths hands it over explicitly:
  **`resolver.lookup_loci(..., rsid_index=)`, `lookup_variant(..., rsid_index=)` and `enrich(..., rsid_index=)`**;
  given, it is the only place looked, never the environment. The CLI takes no `--rsid-index` flag in 0.9 and reads
  the environment.
- **A lookup that scans for want of the index logs once per process, at `info`**, that an index exists and the
  command that builds one there.

### 1.6 Cache status: a new lane state, `stale`, and explicit locations (RM431, RM443; a new vocabulary member)

- **`caches.LANE_STATES` gains `stale`.** `lane_status` and `cache status` said `present`, and `cache prepare` said
  ready, for a derived lane whose parents moved under it, though its reader refuses it. `LaneStatus` gains `stale`
  (the reason) and `CacheLane` gains `stale_reason`, which `ensembl_rsid_index` and `mitomap_miss` state with their
  readers' own verdicts. `cache status` prints `stale` with the reason and the rebuild; `cache prepare` leaves such a
  lane as it is and reports it *unavailable* (`ready=None`, `stale: …`). A parent that is gone is no moved parent: the
  lane stays `present`. **A reader that treats `LANE_STATES` as closed must add the member**; a reader comparing
  `state == "present"` reads a stale lane as not present, which is the intended reading (rebuild it).
- **`caches.lane_status(lanes=None, locations=None)`** (S154): a host that hands each lane's resolver the path it
  configured passes the same mapping, `{lane name: path or None}`. A named lane is resolved with that path and without
  loading `.env`, and reports it as `looked_in`; `None` is the lane's own ladder, still without the load, so a call
  naming every lane leaves `os.environ` untouched. A key naming no lane raises `ValueError`. Without `locations`, the
  call and `cache status` answer as before. **A URL in `locations` raises `ValueError`** too (RM461), naming the
  `RemoteSnapshots` holder as the route for a remote lane, also one a `Path` already collapsed (`hf:/…`): status
  stays a question about the local disk.

### 1.7 The split Ensembl release's column groups are pulled by the lane (RM437, S150, no break)

INTEGRATION_0_8 § 3 told just-dna-pipelines to keep its own source for consequence, clinical flags and frequencies
"until 0.9". 0.9 is the provisioning route:

- **`download.ensure_snapshot(..., groups=(), declared_use="unstated")`** and **`just-dna-enricher cache pull --only
  ensembl --groups NAME[,NAME] [--use …]`** pull the named groups into `groups/<name>/`, each file attested by the
  manifest's sha256, and record each group's `release_id`, files and admitting declaration (`declared_at`) in the pull
  record. Names come from the manifest (`SnapshotManifestGroup`, now typed); `core` and an unknown name are refused
  before any download, and so is `--groups` beside any lane other than `ensembl`
  (`cache_commands.GROUPS_NEED_ENSEMBL_ONLY`).
- **Licensed per group** by its licensor (`licensing.snapshot_group_terms`; `ENSEMBL_TERMS`, the new `CADD_TERMS`):
  `--groups cadd` downloads under a `non-commercial` use, is refused under a commercial one (`REFUSED`, exit 1) and is skipped
  under an unstated one; an unknown licensor is skipped quoting its licence. A group already current is not gated
  again (it fetches nothing).
- **Sticky:** every later `ensure_snapshot` (so `cache prepare`, a plain `cache pull` and `enrich(download=True)` too)
  re-pulls the recorded groups when the core's release moves, under the call's stated use, else the recorded one, and
  says which in its log line.
- **Read a group's path from `locations.ensembl_group_dir(cache, group)`**, never by spelling it: it raises
  `EnsemblGroupReleaseError` unless the group's recorded release is the core's and its directory holds exactly the
  files the manifest attests (eight refusals, one sentence each).
- **An unreadable pull record** is moved aside under a dated name (never deleted), a fresh record naming the lane's
  repository takes its place, and the pull goes on with this call's groups, warning that any group selection it held
  is lost.
- **A group is judged against the release the pull provisions** (RM458, was the first cut's known issue C): the
  core's pull stages the hub's `manifest.json` and `release.json` beside the cache, and the group selection (an
  unknown name, a forbidding use, a group already current) is judged against that staged manifest before any core or
  group byte moves; when the pull keeps the core (a local build, a cache served through an outage), against the
  cache's own. A release transition that drops or relicenses a group refuses before the core is refreshed.
- New for a direct caller: `CacheLane.ensure_takes_declared_use` (`True` for `ensembl` only),
  `download.PULL_RECORD_DECLARED_AT_KEY`, `download.DECLARED_AT_UNRECORDED`, `locations.pulled_groups`.

### 1.8 `enrich` takes the host's clients and sequence proxy (RM404, S133, S157; two new refusals)

- **`enrich(..., clients=None, sequences=None, rsid_index=None)`.** The run reads the bundle's `ensembl`, `gnomad`,
  `grch37` and `eutils`; `resolver=`, `gnomad_client=` and `grch37_client=` still win over the field. **No client the
  caller gave is closed by the run**; an unset field is built and closed by the run and never stored on the bundle. A
  passed `SequenceProxy` is the only GRCh38 reference source the run reads (the reference check, left-alignment, the
  minter, and the anchor base of the resolver the run builds; a resolver the caller gives keeps its own proxy).
  Under `offline=True` the proxy is not used, and the run warns once (`orchestration.OFFLINE_OUTRANKS_SEQUENCES`).
- **`ensembl.BatchResolver`** (`runtime_checkable`, `resolve_rsids_batched(rsids)`) and **`ensembl.RsidAnswer`**: an
  injected resolver with that method is asked in batches. The 0.8 line's private `_BatchResolver`, `_resolve_rsids`
  and `_Answer` are gone.
- **`EnsemblSettings.batch_size`** (default 20) and **`batch_timeout`** (default 120 s) replace the fixed constants.
  **New refusals:** a `batch_size` above Ensembl's ceiling of 200, where 0.8 clamped it silently, and a `batch_size`
  below 1 or a `batch_timeout` not above 0, each `ValueError` when the settings are built and again where the batched
  read uses them.
- **`SequenceProxy` may be shared across threads and runs.** It memoizes answers only (at most 262,144 reads, least
  recently used out first); a failed build or read is held by the run that saw it, through the now public
  **`sequences.held_by_one_run(proxy)`** (RM463): a run calls it once and hands the view to every reader, and wrapping
  a view again returns it. Its failed-build warning now reads
  `Could not reach the sequence service at <uri> (<error>); this read returns no bases, and the build is retried at
  the proxy's next read.`

### 1.9 The 0.8 line's private names made public, and two new publish commands (RM412, no break)

- **`download.ensure_opentargets_snapshot`**, public beside its siblings; `_ensure_opentargets_snapshot` is gone.
- **`just-dna-enricher opentargets publish`** and **`clinvar-gkm publish`** send a snapshot already built, each with
  `--repo`, `--message` and `--dry-run`, and warn on a snapshot with no release label as `mitomap publish` and
  `strchive publish` do.
- **A partial or unreadable snapshot is refused at publish** (`upload.plan_reference_snapshot`,
  `SnapshotNotPublishable`): a dataset with `parts_read` below `parts_total` (an `opentargets build --parts N` test
  build), a `release.json` that does not parse or is not an object, a count that is not a map of datasets to whole
  numbers, a count below zero, a `parts_total` of 0. A record without counts is not refused.
- **`just_dna_format.snapshot.is_whole_build(record)`** (RM465): whether every dataset a `release.json` names was
  read in full, `None` when its part counts cannot say, and `ValueError` for a count that is not a whole number or a
  `parts_read` above its `parts_total` (which published as whole before). The publish gate calls it, and so do Open
  Targets' reader and builder, which took `parts_read >= parts_total` as whole and now refuse an overcount in both
  modes. `read_release` and `parse_release` take an optional `short_reads` list that collects each short dataset.
- **The four per-lane `publish` commands share one body** (RM464): `mitomap`, `strchive`, `opentargets` and
  `clinvar-gkm publish` read `release.json` once and hash and upload those bytes. **A `--dry-run` the gate would
  refuse prints `WOULD BE REFUSED: …` and exits 0**, as `cache rebuild --publish` does; a refused real publish exits 1.
- **`cache rebuild --dry-run --publish --rehearse-download`** downloads and builds for real into `<out>/<lane>`, then
  rehearses the upload instead of sending it. Without both `--dry-run` and `--publish` it is refused (exit 2,
  `cache_commands.REHEARSE_DOWNLOAD_REFUSAL`). Its prediction is only as wide as the dry run's, and its help says so.

### 1.10 Names that are gone

All private, so no contract moved, but a consumer that reached for them breaks: `download._ensure_opentargets_snapshot`
(§ 1.9), `ensembl._BatchResolver`, `_resolve_rsids` and `_Answer` (§ 1.8), and the CIViC, ClinPGx and ClinVar-GKM
readers' private key builders (§ 1.4), `sequences._held_by_one_run` (§ 1.8, now public without the underscore),
`upload._PART_COUNT_KEYS` (derived from `SnapshotRelease` now, § 1.9) and the private hub-manifest read beside the
pull (§ 1.7). `RemoteAnswer.provenance()` existed only on the unreleased branch.

### 1.11 `enrich` without the new arguments writes what 0.8.10 wrote (measured)

The pm asked for a measurement rather than a self-comparing test (round 2, B), and the release record quotes it:

> On five reference examples (pathogenic_clinvar, apoe_epsilon, hboc_palb2, hfe_hemochromatosis, shox_par1), online
> with warm caches, run both as shipped and with resolution.csv removed, 0.9's `enrich` without the new arguments (no
> `clients`, `sequences` or `rsid_index`) wrote byte-identical files to 0.8.10's, clock fields aside.
> `content_signature` was equal in all 10 pairs. `artifact.digest` differed in 3 of 5 examples only through enrich
> timestamps carried into parquet cells; cross-compiling showed both compilers give the same digest for the same
> input.

The clock fields set aside: `verification.json` `produced_at` and every record's `checked_at`;
`clin_sig_authority_calls.csv` and `clin_sig_concordance.csv` `checked_at`; `licensing.csv` `fetched_at`. Its limits:
the live sources reached were dbSNP and the reference sequence; no run reached live Ensembl, gnomAD or the GRCh37
diagnosis; no rsID index was present.

**Since the rescope it is also a test** (RM466): a fixed offline input reaching the Ensembl snapshot, the ClinVar
witness, dbSNP and the sequence is enriched under a fixed clock, and the written tree is compared byte for byte with
goldens recorded from `v0.8.10` (`assets/enrich_v0_8_10/`); `verification.json`'s `producer` is the one field
substituted. The suite holds the claim from now on, not the one-off measurement.

### 1.12 New warning and log texts, pinned (no new code)

Every warning and log text 0.9 adds is pinned by a stable fragment (`enricher/tests/test_every_new_text_is_pinned.py`,
`@warning-text-is-api`). None carries a warning code, and none reaches a compiled module. A consumer that greps the
enricher's log for one quotes the fragment listed there. The walk holds the texts 0.9 added; one over every module,
older texts included, needs a registry of them and is RM469, for 0.10.

### 1.13 What the rescope added (RM454, RM458, RM461–RM467; no break)

Built on `0.9` after the first cut, each decided in the closed
[ROADMAP_0_9.md § The rescope](history/ROADMAP_0_9.md). Seven of them are folded into the sections above; two are new
options:

- **A re-derive scoped to named subjects** (RM467, S160): `enrich(rederive_subjects=[...])`, on the CLI
  `--rederive-subject KEY` (repeatable), re-asks only those `variant_key`s, replacing each subject's loci together,
  and carries every other recorded row of `resolution.csv` byte for byte (quoting, column order and a missing last
  newline included). `EnrichmentResult.reasked` names the subjects compared, and `EnrichmentResult.rederived`
  reports what moved as `SubjectDrift`.
- **Verify passes scoped to the rows a run wrote** (RM467): `enrich(verify_written_only=True)`
  (`--verify-written-only`) runs the row checks over the fresh rows only; each record's `detail` in
  `verification.json` opens `Verification scoped to fresh resolution rows.`, and no field or vocabulary member moves.

Both default off; with neither, `enrich` writes what it wrote before (§ 1.11). A re-derive selected by a declared
correction's reach waits for RM441's record, in 0.10.

The others, by section: RM461 and RM462 in § 1.2, RM454 in § 1.3, RM461's URL refusal in § 1.6, RM458 in § 1.7,
RM463 in § 1.8, RM465 and RM464 in § 1.9, RM466 in § 1.11.

### 1.14 ClinVar-GKM's release line moved to `v1/1.2` (RM470, no break)

ClinVar-GKM froze its `v1/1.1` line on 2026-11-26: its Parquet manifest answers 404, and its index still answers a
stale `latest_release`. 0.8.10's builder reads that line, so `clinvar-gkm build` fails there; the published
`clinvar_gkm` snapshot and every reader of it are unaffected.

- **`clinvar-gkm build` reads `v1/1.2`** (`clinvar_gkm.CLINVAR_GKM_BASE_URL`), whose `allele.parquet` carries typed
  `expressions` and `state` columns in place of the `data` JSON column; an allele file missing them is refused with
  `ClinVarGkmError`, naming the columns.
- **A superseded line is refused by name.** A line index whose stated `status` is not `current` raises
  `ClinVarGkmRetired` (a `ClinVarGkmUnavailable`, so every existing handler still catches it), naming the line, its
  status and its successor; `latest_release_or_none()` withholds and logs that message, so the currency check says
  the lag is unknown instead of reporting the frozen line's release. A manifest 404 asks the line index once and
  raises the same refusal when the index explains it, else the 404 as before.

### 1.15 A `compat` extra for a CPU polars' default runtime refuses (no break)

Added at the redone cut on the maintainer's word (2026-11-26: a server of theirs has no AVX-512).
`just-dna-compiler[compat]` adds `polars[rtcompat]` at the core polars floor (`>=1.42.0`), and
`just-dna-enricher[compat]` is the compiler's extra. Polars loads its compatibility runtime first whenever it is
installed (`polars._plr` tries `compat`, then `64`, then `32`; `POLARS_FORCE_PKG` overrides), so installing the extra
is the whole change: no code moved, and without the extra nothing differs. `compiler/tests/test_compat_extra.py`
holds the two floors equal. Checked by installing `just-dna-compiler[compat]` into a fresh environment from this
tree: `import polars` loaded `_polars_runtime_compat`.

---

## 2. What to change

### Upgrade order

1. **Pins, in tier order, all on `>=0.9.0`.** The enricher floors `just-dna-format>=0.9.0` because it imports
   `parse_release` (§ 1.1), so an install of enricher 0.9 beside format 0.8.x does not resolve. A consumer holding only
   the format tier can stay where it is: nothing a module carries moved (§ 1.0).
2. **`uv lock`**, regenerated, committed with the floors.
3. **No recompile and no re-derivation for 0.9's sake.** The compiler did not move, and the release record measures no
   axis moving on any reference module (§ 1.0). An `enrich` run with neither new argument writes 0.8.10's bytes
   (§ 1.11).
4. **Optional, per box:** install duckdb's `httpfs` before any remote read (§ 1.2); build the rsID index where
   rsID lookups are hot, `just-dna-enricher cache rebuild --only ensembl_rsid_index` (about 42 minutes and 6 GB, § 1.5);
   pull the Ensembl groups a reader needs, `just-dna-enricher cache pull --only ensembl --groups NAME --use non-commercial`
   (§ 1.7).

### Changes, by surface

1. **If you call `lookup_variant` with a holder** (§ 1.2): catch `SnapshotRouteUnavailable` as could-not-ask, and let
   `ValueError` (a wrong request, a closed holder) surface as the defect it is. Close a shared holder only after its
   last lookup.
2. **If you validate `LANE_STATES` as closed, or render `cache status`** (§ 1.6): add `stale`, and read
   `LaneStatus.stale` for the reason.
3. **If you build `EnsemblSettings`** (§ 1.8): a `batch_size` above 200 or below 1, or a `batch_timeout` not above 0,
   now raises instead of being clamped.
4. **If you imported a private name** listed in § 1.10, move to its public successor.
5. **If you read the Ensembl groups**, take their path from `locations.ensembl_group_dir` and stop fetching them
   yourself (§ 1.7).
6. **If you read a gene through cpic** (§ 1.3): a whitespace-padded gene cell now matches, and `partner_genes` no
   longer lists `None`.
7. **If you pass a URL to `lane_status(locations=...)`** (§ 1.6): it raises `ValueError` now; ask a remote lane
   through a `RemoteSnapshots` holder.
8. **If a script reads the exit code of `mitomap|strchive|opentargets|clinvar-gkm publish --dry-run`** (§ 1.9): a
   rehearsal the gate would refuse exits 0 with `WOULD BE REFUSED:`; grep for that, or run without `--dry-run`.
9. **If you read a constraint or gene-metrics answer by gene** (§ 1.3): a gene asked in another case now finds its
   row where it answered `not_found` before.
10. **If you rebuild the `clinvar_gkm` snapshot** (§ 1.14): only 0.9.0 can, since upstream retired the line 0.8.10
    reads; a handler of `ClinVarGkmUnavailable` also receives `ClinVarGkmRetired` for a superseded line.

---

## 3. Per-consumer check / change lists

Written from this repository's own record of each consumer (the liaison's notes, the consumers' suggestions in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md)); no consumer checkout was re-read for this file.

### just-dna-registry (spec storage, catalog, serving)

The consumer 0.9 was built for (S145, S150, S154, S157).

**Change**

1. **The remote route for its proxy hosts' clients** (S145, § 1.2): a host that wants `lookup_variant` to read a lane
   it does not hold passes `LookupClients(snapshots=RemoteSnapshots(...))`, installs `httpfs`, and closes a shared
   holder after its last lookup (a lookup on a closed holder raises, § 1.2).
2. **Read `key_compare.KEY_COMPARES`** from the release that floors 0.9, as its S36 decided, so the proxy folds and
   splits a gene key as the local readers do. Until it does, a 0.9 client with the proxy set and Hugging Face off
   answers could-not-ask on gene lookups for clinpgx, cpic, drug_labels and civic (RM459, § 4).
3. **`lane_status(locations=...)`** (S154, § 1.6) can replace the registry's own status loop over the lanes it
   configures; it writes nothing to `os.environ` for a named lane.
4. **`enrich(clients=..., sequences=...)`** (S133, S157, § 1.8): pass the shared paced bundle and the proxy, and run
   enrichments in parallel. A `seqrepo+file://` URI needs `biocommons.seqrepo` in the host's environment.
5. **`rsid_index=`** on `lookup_variant` and `enrich` (§ 1.5): the proxy hosts hold the Ensembl lane, so building the
   index there serves rsID-only keys, which the proxy still refuses remotely (`remote_needs_position`).

**Check**

6. Its `/caches` view derives its own states and never reads the enricher's, so `stale` (§ 1.6) does not reach it
   unless that changes.
7. If its `version.contract_compatible` compares minors, a 0.9 enricher beside a 0.8 server is a mixed trio; the
   format surface did not move (§ 1.0).
8. The proxy reply's `release`, `release_unreadable` and `revision` (its S34): the client reads all three when
   present, `release_unreadable` into `RemoteRoute.release_unreadable` (RM461, § 1.2).
9. **A scoped re-derive** (S160, § 1.13): `--rederive-subject` and `--verify-written-only` move ~30 rows of 75,000
   without re-asking the whole table.

### just-dna-lite (reference consumer, the annotating engine)

**Change**

1. **Raise the floors together** (§ 2 step 1). Nothing in the compiled artifact moved, so no join, parquet reader or
   warning renderer changes.

**Check**

2. Re-baselined digests stay valid: the 22 reference modules compile to the same bytes under 0.9.0 as under 0.8.10.

### just-dna-pipelines (inside just-dna-lite)

**Change**

1. **The Ensembl group values** (INTEGRATION_0_8 § 3, item 1): consequence, clinical flags and frequencies now come
   through `cache pull --only ensembl --groups …` or `ensure_snapshot(groups=…)`, read through
   `locations.ensembl_group_dir` (§ 1.7). Retire any downloader that writes into the lane's directory, which mixes
   releases.

**Check**

2. Its wrapped enricher CLI gains `cache pull --groups`, `cache rebuild --rehearse-download`, `opentargets publish`
   and `clinvar-gkm publish`, and `cache status` can print `stale`.

### just-module-creator (the MCP authoring plugin)

**Change**

1. **`state == "present"`** in its cache checks reads a stale rsID index as not present and offers a build (§ 1.6),
   which is the right answer; a set check over `LANE_STATES` needs `stale` added.
2. **Repin the trio at the cut**; nothing an author writes changed, so no authoring rule or table description moves.

---

## 4. Known issues

What 0.9 ships with, known and not fixed. Each line names its item; [RM_TOC.md](RM_TOC.md) has its state.

- **With the proxy set and Hugging Face off, gene lookups on clinpgx, cpic, drug_labels and civic answer
  could-not-ask (RM459, for 0.10, waits on the registry's S36).** The registry's proxy compares a cell exactly, so the
  holder does not send it a gene key these lanes fold or split, and asks Hugging Face instead; with Hugging Face off
  that is `SnapshotRouteUnavailable`, saying why. rsID and position lookups are not affected. It clears when the
  registry reads `KEY_COMPARES`.
- **Carried from 0.8, unchanged:** offline enrich cannot left-align an indel (RM385, now in 0.10's scope); placement
  readers that bypass `usable_loci` (RM388, parked); the enricher does not say what compile will refuse (RM390,
  parked). [INTEGRATION_0_8 § 4](history/INTEGRATION_0_8.md#4-known-issues) has the full text of each.

The first cut's other known issues were built in 0.9 by the rescope: RM458 (§ 1.7), RM462 (§ 1.2) and RM454 (§ 1.3).
RM460, `rsid_genotype_reads_as_two_events`, is a code 0.9 does not add rather than a defect (§ 1.0), in 0.10's scope.
