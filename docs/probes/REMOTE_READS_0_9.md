# Remote snapshot reads: local disk, the registry's proxy, Hugging Face (trial, 2026-11-15)

The pm's trial before 0.9's design of RM430 and RM431. The maintainer set the read order on desk #261: local disk,
then the registry's proxy, then Hugging Face, and asked that the remote steps be measured ("remote reads from hugging
would be slow (measure)"). This measures all three on the same real lookups. A subagent ran it; its scripts and raw
rows stayed in the pm's scratchpad and are not kept. Every number below was measured unless it says *extrapolated*.

## Setup

- 2026-11-15, 18:03 to 18:30 UTC; `main` at `b49ff8e1`; just-dna-enricher 0.8.7, duckdb 1.5.5 (httpfs), httpx 0.28.1.
- A shared, loaded machine: everything at `nice -n 19`, serially. The local leg was re-run at a load of about 8 and
  the tables use the re-run; the first run, at a load of about 33, gave identical answers 1 to 20 times slower.
- **Local disk**: the public readers (`clinvar.lookup_loci`, `clinvar.lookup_clin_sig`, `resolver.lookup_loci`) over
  `resolve_*_reference()`. Open Targets and ClinPGx have no public keyed reader, so plain duckdb `WHERE` SQL.
- **Proxy**: `POST https://module-polygon.just-dna.life/api/v1/lanes/{lane}/{table}`, anonymous, one keep-alive
  `httpx.Client`, a 1 s pause before each request. The rows were loaded into an in-memory table with the local schema
  and run through the same reader SQL, so answers compare.
- **Hugging Face**: the readers' own SQL on a fresh `duckdb.connect(':memory:')` per call, as the readers do, over
  `read_parquet('hf://datasets/<repo>/data/*.parquet')`. Run over the local glob, this mirror gave byte-identical
  answers to the public readers on all 34 ClinVar and Ensembl lookups. Anonymous. Bytes and requests are counted
  from duckdb's HTTP log; the count agreed with Hugging Face's own quota header (397 counted, 396 consumed).
- Lookups, fixed before timing: ClinVar by ten rsIDs (rs429358, rs7412, rs1801133, rs334, rs113993960, rs80357906,
  rs1800562, rs4988235, rs121913529, rs6025), singly and as one batch; `lookup_clin_sig` over the 13 alleles the local
  snapshot gives them; five positions (19:44908684, 19:44908822, 1:11796321, 1:169549811, 6:26092913) for ClinVar and
  Ensembl, singly and as a batch; Ensembl by rsID; Open Targets `variants` at 19:44908684; ClinPGx `annotations` for
  rs4244285. "Warm" is the median of 3 repeats.

## Results

Times are per lookup, in seconds. HF bytes are range bytes fetched; proxy bytes are on the wire (gzip).

| Lookup | Local | Proxy | Hugging Face |
|---|---|---|---|
| ClinVar, one rsID | 0.04 | 0.27–0.36, ≤1 kB | 7.2–10.6 (warm 7.4), 21.6 MB, 95 requests |
| ClinVar, 10 rsIDs batched | 0.08 | 0.30 | 4.2, 31.5 MB |
| ClinVar `lookup_clin_sig`, one allele | 0.03 | 0.22–0.29 | 3.3–4.3, 1.3–2.6 MB |
| ClinVar `lookup_clin_sig`, same, one duckdb connection kept open | – | – | 1.25 warm (2.58 cold), +7.6 kB a repeat |
| ClinVar by position, one | 0.03 | (as above) | 2.4–3.5, 1.1–2.3 MB |
| Ensembl by position, one, the reader's glob | 0.09 | 0.27 | 7.0–28.7, about 10 MB, 185–1,168 requests |
| Ensembl by position, one, only that chromosome's file | – | – | 2.8, 4.0 MB, 63 requests |
| Ensembl, 5 positions batched, glob | 0.29 | 0.35 | 8.1, 140 MB, 193 requests |
| Ensembl, 5 positions batched, the 3 files they need | – | – | 2.8, 42.5 MB, 51 requests |
| Ensembl by rsID, one | 9.4 | 21.5 (answered 200) | – |
| Ensembl by rsID, 10 | 13.2–13.6 | – | *extrapolated* from one file: about 250 s, 10.7 GB, 2,800 requests |
| Open Targets, one position | 0.03 | 0.29 | 2.1 warm, 1.9 MB |
| ClinPGx, one rsID (21 rows) | 0.02 | 0.24 | 1.8, 0.6 MB (the whole file) |

## Findings

1. **The proxy is 10 to 30 times faster than Hugging Face and 3 to 10 times slower than local disk**: 0.22 to 0.37 s
   per request whatever the lookup or batch size, about 1 kB on the wire. A batch costs what a single does.
2. **Hugging Face's anonymous quota binds before its speed does**: 3,000 requests per 300 s per IP (`ratelimit-policy:
   "fixed window";"resolvers";q=3000;w=300`). The trial was refused twice (429, `retry-after` 46 and 72 s). Over the
   reader's glob one Ensembl chr1 lookup costs 1,168 requests and one ClinVar rsID lookup 95, so an anonymous client
   gets about 2 Ensembl or about 30 ClinVar lookups per 5 minutes. duckdb surfaces the 429 as a generic `HTTPException`
   with no `Retry-After` in it.
3. **The glob is the cost.** Every call over `data/*.parquet` pays at least 26 HEADs plus each file's footer. Reading
   only the chromosome file a key names cuts requests 3 to 20 times and time about 3 times.
4. **ClinVar by rsID reads the whole `rsid` column (21.6 MB) on every remote call**: the ClinVar files hold about one
   row group each, so nothing prunes.
5. **A kept connection halves Hugging Face's time** (2.58 s to 1.25 s); the readers open a new one per call.
6. **Ensembl by rsID is slow on every route**: 9 to 14 s locally (the missing index, RM405), 21.5 s on the proxy, and
   about 10.7 GB extrapolated on Hugging Face. RM431's rsID index is what makes it remote-capable at all.
7. **The registry lead's numbers reproduce**: `lookup_clin_sig` 3.3 to 4.3 s and 1.3 to 2.6 MB against their 3.1 s and
   2.4 MB; Ensembl by position 2.8 s and 4.0 MB from one file against their 3.5 s and 5.4 MB. Their Ensembl figure is
   the one-file shape, not the reader's glob.
8. **The local ClinVar cache disagrees with Hugging Face and the proxy, under the same release label.** In
   `lookup_clin_sig` the `condition` field differs on 12 of 13 alleles (reordered on 8, different content on 4);
   `clin_sig`, review status, stars and `variation_id` agree. The local `release.json` is byte-identical to Hugging
   Face's (`clinvar_2026-11-01`, 4,608,075 records, written 2026-11-08) and the pull record lists all 26 parquet files,
   but the local parquet files date from 2026-08-31, hold 4,431,781 rows, and differ in size from the published ones.
   An observation, not a diagnosis; handed to triage the same evening.
9. **The test server's proxy serves an older ClinPGx copy**: all 21 rows carry `pharmgkb.org` URLs where the published
   snapshot and the local copy carry `clinpgx.org`. Every other column matched, and every reply said
   `served_from: "local"`. Told to the registry's lead.
10. **The proxy answered an Ensembl lookup by `id` alone with 200** (21.5 s), where its contract says Ensembl takes
    chrom + start only (`422 remote_needs_position`). The lane listing advertises `id` as a key, presumably because the
    server reads its own snapshot. Told to the registry's lead, who answered the same night that this is by design and
    registry 0.32.1 documents it: on a box that holds the lane an rsID key works at the cost of a full scan; remotely it
    stays 422. Their 0.32.1 also matches a chrom + start batch as pairs, which ends finding 11's over-fetch.
11. **A chrom + start batch over-fetches on the proxy**: it is `chrom IN (…) AND start IN (…)`, so 13 alleles returned
    22 rows; one position returns every allele there. The client-side filter got every answer right.
12. **Not measured**: the proxy reading Hugging Face itself (every reply was `served_from: "local"`), and the limits a
    Hugging Face token buys.

## What 0.9's design may take from this

The trial's suggestions, for the lead to weigh; none is decided.

- Keep local disk first (about 10 times the proxy, 100 times Hugging Face) and prefer the proxy strongly over Hugging
  Face; Hugging Face, anonymous, is a last resort.
- Proxy: connect timeout about 3 s, read about 10 s; never send an rsID-only Ensembl key remotely. Fill requests up to
  the 100-value limit, one chromosome per request to limit the cross-product, over one keep-alive client.
- Hugging Face: open the chromosome file the key names rather than the glob; one connection per process; a 429 is
  could-not-ask, honouring `Retry-After`, never a tight retry; count requests, not bytes; take an optional token.
- Refuse Ensembl by rsID on Hugging Face until RM431's index exists.
- Record which route answered, and the proxy's `served_from`, on every lookup: findings 8 and 9 are two routes
  disagreeing under labels that look the same, so one release label is not one set of bytes.
