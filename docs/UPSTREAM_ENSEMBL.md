# Upstream ledger — Ensembl

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. Ensembl is a web service, not a package: there is no clone, no tag and
no watcher. It is a **standing watch**, re-checked by hand monthly or on any Ensembl dev-list post. Handed over by
the lead on 2026-11-04 (the maintainer: "hand it to liaison, absolutely"), from the lead's probe of Ensembl's newer
API surfaces.

## Marks

- **Last checked:** 2026-11-04 (the lead's probe, by curl). Next due: 2026-12-04, or earlier on a dev-list post.
- **In use:** REST release 116, dbSNP 156 (`/info/rest`, `/info/data`).

## What we use of it

| Ours | Theirs | What it decides |
| --- | --- | --- |
| `enricher/src/just_dna_enricher/ensembl.py`, `currency.py` | `rest.ensembl.org` `/variation/human/{rs}`, `/info/rest` | live rsID resolution, and the currency check's release label |
| `enricher/src/just_dna_enricher/grch37.py` | `grch37.rest.ensembl.org` `/overlap/region`, `/sequence/region` | placing GRCh37 coordinates |
| the HF dataset `just-dna-seq/ensembl_variations` (→ `ensembl_variations_split` with RM372, 0.8) | built from Ensembl's variation release | the snapshot leg of the resolver chain |

Nothing calls LD, VEP or `ftp.ensembl.org`. The GraphQL leg (`beta.ensembl.org/api/graphql/variation`) is removed on
`build/RM267-gaps`, which merges into 0.8.

## Measured 2026-11-04 (the lead, curl)

- REST is up: release 116, dbSNP 156, rate limit 55000 per 3600 s. `/ld`, `/sequence/region` and `/vep/human/id`
  answer 200; the LD populations are 1000G subpopulations (CEU, YRI, …), not superpopulations.
- `beta.ensembl.org` returns 301 to `www.ensembl.org`, the GraphQL path included.
- `www.ensembl.org/api/graphql/variation` is `0.1.0-beta` with three query fields (`version`,
  `variant(by_id{genome_id,variant_id})`, `populations`). It refuses a bare rsID (`VARIANT_ID_NOT_FOUND`) and needs
  `chrom:pos:rsid`; it failed to place the indel rs72613567; it has no LD, sequence or consequence query.
- Refget is not live: `www.ensembl.org/api/refget/service-info` 404, `refget.ensembl.org` 503.

## Read, not measured

The Ensembl dev-list notice of 2025-09-08: release 116 (spring 2026) freezes the current APIs, MySQL and FTP.
Existing endpoints stay "until equivalent functionality exists"; new data goes only to the new platform.
ensembl.org redirects to the new site in summer 2026, and legacy tools (VEP included) are sunset at parity. No
retirement date was found for `rest.ensembl.org`.

## The watch

Each re-check looks for:

1. a retirement notice or date for `rest.ensembl.org` or `grch37.rest.ensembl.org`;
2. the GraphQL API growing past its three query fields, or accepting a bare rsID;
3. refget coming up;
4. the new platform's FTP layout stabilising;
5. **the real trigger: a dbSNP release past 156.** REST is frozen at 156, so newer rsIDs and merges will exist only
   on the new platform; the resolver chain and the HF snapshot builder then need a plan item.

When one fires, it is filed as an RM through the lead. Until then, nothing is owed.

## Verdicts

None yet: nothing has fired.

## Outbound

None.
