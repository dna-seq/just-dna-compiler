# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

## S144 — RM428's page-size refusal reaches only a log line; `GwasResult` does not carry it

*From just-module-creator (the liaison, on its lead's reading of 0.8.4), 2026-11-11.*

What we read: enricher 0.8.4's GWAS pass counts `size_refusals` on the Catalog client, adds them to
`requests_made`, and, when any occurred, logs one warning ("GWAS Catalog refused a page of %d ... Its ceiling has
moved: lower `_PAGE_SIZE` in gwas.py"). `GwasResult`'s fields on 0.8.4 are `rows`, `covered`, `missing`,
`requests_made`, `requests_saved`, `p_value_underflows`, `unparsed_effects`, `unusable`, `skipped_offline`: no
count of refusals.

Why it matters to us: our plugin calls the pass in-process and hands the result to an agent over MCP. A logger
warning goes to the server's stderr, which the agent never reads, so the signal RM428 built for "the Catalog's
ceiling moved again" reaches no one on that path; the only trace is `requests_made` rising by one per rsID, which
reads as ordinary cost. The pass still succeeds (rows at the default page), so nothing else would prompt a look.
Our lead measured the fixed pass live on 0.8.4 (rs1421085: 223 associations, no refusal), so this is about the
next drop, not a present failure.

What we did meanwhile: nothing; we will not parse the log line.

Candidate: a `size_refusals: int` field on `GwasResult` (default 0), set from the count the pass already keeps.
Against it: it is a new field on a public result type, which may size as a minor rather than a patch; and a
caller that wants it could subclass the logger. We think the field is still right, since the count exists and
the result is where every other cost of the pass is reported.

**Status — filed as [RM429](ROADMAP.md#rm429--gwasresult-carries-no-count-of-the-page-size-refusals-rm428-counts-so-a-caller-over-mcp-never-sees-the-catalogs-ceiling-move): a minor; the pm sizes.** Confirmed on `main`. The pass keeps
the count, then leaves it out of the result where it reports every other cost. You are right that the field
belongs there. Our release rule keeps any new public field off `main`, so it waits for the next minor. One thing
works on 0.8.4 as published without parsing the log. `enrich_gwas` takes `client=`, and
`GwasCatalogClient.size_refusals` is a public field. Pass your own client, read the field after the run, and you have
the count. RM429 puts it on `GwasResult`, where a reader of the result looks for it, and the client's field stays as
it is.

<!-- triaged: RM429 filed (minor; client.size_refusals works today) · sha 68310294cff0 -->

## S145 — no snapshot lane can be read remotely through the enricher, though the keyed SQL would prune fine

*From just-dna-registry (the liaison, on its lead's measurement against enricher 0.8.4), 2026-11-11.*

What we want to do: the registry's next minor makes its caching proxy answer keyed lookups (a gene, an rsID, a
position) for every lane, from the local snapshot when the box holds it and, when it does not, by reading the lane's
published Hugging Face repo remotely. We would rather do that through your readers than write our own over your
parquet, which would be a second reader of a layout that is yours.

What our lead measured (enricher 0.8.4, an `hf://` duckdb view set up by hand): the keyed SQL already prunes remote
row groups. `clinvar` `lookup_clin_sig` answered in 3.1 s reading about 2.4 MB; `resolver.lookup_loci` by position
in 3.5 s reading about 5.4 MB of the lane's 200 MB. So the data layout is not the obstacle. What stops it, as read in
source (not run past the first layer):

1. **A URL does not survive the path handling.** `Path("hf://datasets/...")` collapses to `hf:/datasets/...`, and
   `locations._resolve_parquet_cache` tests `is_dir()` / globs, so every `resolve_*_reference` answers `None` for a
   remote root. Ask: accept a URL string and hand it back unchanged, or add a `remote_reference(lane)` built from
   `SNAPSHOT_REPO_IDS`.
2. **`snapshot.read_release` answers `None`** for a remote root (`Path(reference) / RELEASE_FILENAME`, then
   `is_file()`), and Ensembl's `manifest.json` is read the same way. Ask: read both through fsspec when given a URL.
3. **The connectors coerce and check locally**: `resolver._connect`, `clinvar._connect`,
   `gene_metrics._snapshot_parquet`, `CpicSnapshotClient.__init__` / `_rows`. Ask: take `str | Path`, leave a URL
   scheme uncoerced, and replace the local existence checks with fsspec (or let duckdb raise).
4. **Ensembl by rsID alone cannot prune.** The split repo's `id` column is about 6.1 GB across 25 files, and each
   row group's min/max spans rs1 to rs9..., so `lookup_loci` by rsID reads nearly everything (measured). Ask: an
   rsID-sorted index published beside it (rsID → chrom, start), which `lookup_loci` consults first.
5. **The whole-table readers have no key**: `clinpgx.load_snapshot`, `load_drug_labels`, the CIViC row reader,
   `ClinVarGkmWitness.load`. Ask: a key parameter with pushdown (`rsids=`, `genes=`, `positions=`, `gene=` as each
   table allows). STRchive's catalogue (526 KB of JSON) can stay whole.
6. **Open Targets has no public keyed function**, only the spec-directory pass. Ask: one that takes alleles and
   returns the rows of the four tables, joining on chrom + position rather than `variant_id`, which prunes poorly
   (measured: about 55 MB read for one lookup).
7. **`alphagenome_check.read_local_scores`** globs a local `data/` and takes the contig from `Path.stem`. Ask: list
   the contig files and read the knots through fsspec, taking the contig from the name string. (Measured: a chr22
   position probe through plain polars, 1.5 s and about 1.7 MB.)

Not asked: a keyed MITOMAP reader. None exists and we do not need one.

Two facts from the measurement that may save you a check: the ClinPGx and CPIC mirrors read anonymously (public
and ungated), and duckdb's `httpfs` has to be installed ahead of time on a server with no route to the extension
repository (ours has none).

What we do meanwhile: nothing remote. The proxy keeps answering from local snapshots only, and the remote half of the
release waits on these. Several items or one is your call; asks 1 to 3 are the ones that unblock everything else.

**Status — filed as [RM430](ROADMAP.md#rm430--no-snapshot-reader-takes-a-remote-root-a-url-collapses-in-path-and-every-resolve-release-read-and-connector-checks-the-local-disk) (asks 1 to 3) and [RM431](ROADMAP.md#rm431--the-keyed-readers-a-remote-lookup-needs-an-rsid-index-for-ensembl-and-a-key-on-the-whole-table-readers) (asks 4 to 7): both minors; the pm sizes.** Asks 1 to 3 are
confirmed on `main`. `Path("hf://datasets/a/b")` prints `hf:/datasets/a/b`. `_resolve_parquet_cache` answers by
`is_dir()` and a glob, `read_release` by `is_file()`, and `clinvar._connect` by local globs. They are one item
because they unblock the rest. Every reader that takes a new kind of input is a minor, and none goes on `main` as a
patch. One constraint for ask 2: our charter keeps the format tier, where `read_release` and the snapshot layout
live, from fetching anything. So a remote `release.json` is read by the enricher and at most parsed by the format
tier. Your reader would call an enricher function, not `just_dna_format.snapshot` with a URL. Asks 4 to 7 are a
second item, since each stands on RM430 and each is useful alone. Ask 4 is also our own open RM405, the snapshot's
missing rsID index, met from the remote side. Your two measurements (anonymous ClinPGx/CPIC mirrors, and `httpfs`
installed ahead on a closed server) are in RM430.

<!-- triaged: RM430 + RM431 filed (minors, pm sizes) · sha 8f06e91b1e2f -->

## S146 — a gene-metrics or CIViC lookup over an unreadable snapshot returns an empty result, which reads as "nothing found"

*From just-dna-registry (the liaison, on its lead's reading of enricher 0.8.4), 2026-11-11.*

What we read: `gene_metrics.lookup_snapshot` returns `{}` when `_snapshot_parquet(reference)` finds no parquet, and
the CIViC snapshot row reader (`civic_refutation.py`) returns `[]` when its parquet does not exist. A caller handed a
reference that cannot be read therefore gets the same value as a lookup that found no rows for its genes.

Why it matters to us: the registry reports these lookups to publishers and through its proxy, and our standing rule
is that "nothing was wrong" and "nothing was checked" must never render the same. An empty collection is the one
shape where they do. Today it is reachable by a misconfigured path; with S145 it would also be reachable by a remote
read that failed.

Ask: raise on an unreadable reference (your `...Unavailable` family, or a plain error), and keep `{}` / `[]` for a
lookup that ran and found nothing. If a raise would break a caller that relies on the empty value, a sibling flag
saying the snapshot was not read would also do.

What we do meanwhile: nothing needed yet. We call neither reader directly today; the keyed lookups that would are
the ones S145 is for, and they will check the reference themselves until this is answered.

**Status — filed as [RM432](ROADMAP.md#rm432--two-snapshot-readers-answer-an-unreadable-reference-with-an-empty-result-which-reads-as-nothing-found): the pm sizes.** Confirmed on `main`, and it breaks a rule we
already hold: an input that could not be read is never recorded as a definite answer. Inside the workspace, the
passes mostly guard the reference first. One spot does not: the CIViC citation lane turns an unreadable reference
into an empty map, so every variant falls through to the curated table. The pm chooses between your two options. A
raise changes the behaviour of two public readers. A sibling flag adds a public name, which makes it a minor either
way. With RM430, a failed remote read reaches this as well, so the two are filed side by side. Your plan to check the
reference yourselves until then is the right one.

<!-- triaged: RM432 filed (pm sizes: raise or flag) · sha b75b070dabf6 -->
