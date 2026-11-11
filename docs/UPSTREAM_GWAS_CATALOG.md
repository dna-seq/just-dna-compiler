# Upstream ledger — the GWAS Catalog REST API

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. The source is the NHGRI-EBI GWAS Catalog's REST API v2,
<https://www.ebi.ac.uk/gwas/rest/api/v2>, read by `enricher/src/just_dna_enricher/gwas.py`. It is a live service
with no package, no tags and no clone: there is nothing to pin, and a change reaches every installed release at
once. Added 2026-11-11 after RM428 (S143), where the service lowered its page ceiling and the GWAS pass filled
nothing for days before a consumer noticed.

## Marks

- **News read: 2026-08-19**, "Version 2 of the GWAS Catalog REST API: what's changed from v1?", the newest post on
  <https://www.ebi.ac.uk/gwas/docs/news> on 2026-11-11. That page is the only release channel found: the API has
  no version endpoint (`/v2` answers 404), no changelog (`/gwas/docs/api-changelog/` is a "Page Not Found"), and
  no public repository under the name it once had (`EBISPOT/goci` resolves to nothing).
- **Data release: `2026-10-29`** (Ensembl 116, dbSNP 156, EFO v3.95.0), from
  <https://www.ebi.ac.uk/gwas/api/search/stats>, which `GwasClient.release` reads (RM373).
- **Probe: 2026-11-11 00:26 UTC.** See "The weekly probe" below.

## What we use of it

| Ours | Theirs | What it decides |
| --- | --- | --- |
| `gwas.py:96` `DEFAULT_GWAS_ENDPOINT` | `/gwas/rest/api/v2` | every request |
| `gwas.py:307` `association_pages`, `:124` `_PAGE_SIZE = 500` | `GET /associations?rs_id=&size=`, then `_links.next` | the page size the server accepts; the fallback to no `size` on a first 400 (RM428) |
| `gwas.py:369` | `GET /studies/<accession>/ancestries` | the one fact still behind a second request |
| `gwas.py:292` `release`, `:99` | `GET /gwas/api/search/stats` (`date`) | a row's `dataset` label (RM373) |
| `gwas.py:158` `GwasRetired` | HTTP 410 on the retired v1 paths | a retired path is a fact, never an outage (RM354) |
| `gwas.py:479`–`:562`, `:907`–`:950` | association fields `beta`, `or_per_copy_num`, `p_value`, `pvalue_mantissa`, `pvalue_exponent`, `snp_effect_allele`, `efo_traits`, `accession_id`, `pubmed_id`, `range`, `risk_frequency`, `association_id`, `_embedded`, `page.totalElements` | every cell of `gwas_effects.csv` |
| `gwas.py:128` `DEFAULT_REQUEST_INTERVAL = 1.0` | the throttle | pacing |
| `enricher/tests/test_gwas.py:927` (`@pytest.mark.network`) | the live page ceiling | the opt-in re-measure RM428 added |

## The weekly probe

Run with the dependency bump (`docs/seats/LIAISON.md`); the script is three `curl` calls and changes nothing.

| Question | 2026-11-11 |
| --- | --- |
| `associations?rs_id=rs1421085&size=500` | 200 |
| `…&size=501` | 400 (the ceiling is 500, as RM428 measured on 2026-11-10) |
| no `size` | 200, `page.size` 20, 223 associations |
| legacy `/singleNucleotidePolymorphisms/rs1421085/associations` | 410 |
| `/api/search/stats` `date` | `2026-10-29` |

A ceiling below 500, a different default page, or a legacy path answering anything but 410 goes to the lead the
same day.

## Verdicts

### The throttle is published now; `gwas.py`'s docstring says it is not (2026-11-11)

The v2 documentation page (<https://www.ebi.ac.uk/gwas/rest/api/v2/docs>, "Throttling") reads: "Users of the API
are limited to 15 queries per second to prevent server overload and ensure fair usage. If the limit is exceeded,
the API will slow down subsequent calls." `gwas.py:47`–`:50` says "Rate limits are NOT established. EBI publishes
no numeric budget that could be found", and `:126`–`:127` repeats it.

**Sorted: a document that says what the source no longer does; nothing breaks.** The pass waits one second between
requests, fifteen times under the limit, and an excess is answered by slowing down, not by refusing. The fix is a
docstring, quoting the page and keeping the conservative gate, and it is the lead's. Not measured: whether the
limit is per IP or per client, and when the page began to say it. The page does not state the page ceiling, so
RM428's 500 is still a measured number only.

**Done:** the lead quoted the page in `gwas.py`'s docstring, the constant's comment and `docs/ENRICHER.md`
(7a88e10f, pushed 2026-11-11); the line numbers above are as of fba9a23b.

## Outbound

None.
