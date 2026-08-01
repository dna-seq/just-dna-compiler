# Next step — validation tightening (draft plan, T1–T4)

Successor to the gnomAD/VRS work in 0.5. Where that round *added* facts, this one *checks* them. The
organising idea is the one written up in [docs/COMPILER.md](docs/COMPILER.md) § *What the compiler can
and cannot validate*: the compiler proves an artifact well-formed and self-consistent, never true, and
several of its blind spots are closable by the enricher — the only tier that can compare authored data
against reality. This plan closes the reachable ones.

**Budget:** roughly one gnomAD-sized effort for T1–T3, with T4 a small add-on.

**Shape every item must follow** (established by the gnomAD round, not re-litigated here):

- **reports, never repairs** — rewriting an authored value destroys the evidence of an upstream bug;
- **severity follows the mode** — `best_effort` warns, `strict` refuses;
- **batched + paced + tenacity** for anything on the network, with an injectable clock so tests do not
  really sleep;
- **offline skips with a warning** — a check that cannot run is not a check that passed;
- **recorded fixtures, never fabricated** — the gnomAD round found three real quirks a hand-written
  fixture would have omitted;
- **new columns are provenance** unless they are genuinely facts about the module (see T4's note on
  why external time-varying state must stay out of the fact sets).

---

## T1 — offline compiler checks (hours)

Pure validate-by-redundancy on data the module already carries. No network, no new dependency, no new
file. Verified absent from the current code before listing.

| # | Check | Why |
|---|---|---|
| 1.1 | genotype alleles ⊆ `{ref} ∪ alts` | A genotype `A/G` at a `C>T` locus compiles clean today. |
| 1.2 | `effect_allele ∈ {ref} ∪ alts` | Only grammar-checked now. A wrong effect allele **silently inverts** `direction`/`effect_size` — high clinical impact, trivial to catch. |
| 1.3 | ACMG BA1 lint: `clin_sig` pathogenic + AF over a threshold | Newly possible because `frequencies.csv` exists. Threshold is disease-specific, so **warning only**, documented and overridable. |

**Severity:** 1.1 and 1.2 are errors (an impossible genotype is malformed data, not a judgement call);
1.3 is a warning. **Best ratio in the whole plan** — start here.

---

## T2 — clinical cross-check against the ClinVar snapshot (~1 day, offline)

Compare authored `clin_sig` against the ClinVar snapshot's own `clin_sig`, which `clinvar_build`
already materialises and the snapshot is already provisioned for the resolver link. **Zero new
infrastructure, zero egress.**

This is the cheapest bite out of the largest blind spot ("is the annotation right?"). It cannot say the
annotation is *correct* — ClinVar is not truth either — but a module calling a variant `benign` that
ClinVar calls `pathogenic` is a discrepancy an author must see.

- Compare on `variant_key` + allele, not rsID (an rsID spans alleles — see CLAUDE.md).
- Report the pair and ClinVar's `review_stars`, so a 1-star conflict reads differently from a 4-star
  practice-guideline conflict. **Never** overwrite the authored value.
- Severity: warning in `best_effort`. In `strict`, warn too — a curator may legitimately disagree with
  ClinVar, and failing the compile would make the format arbitrate a clinical dispute, which is
  precisely what the data-agnostic charter forbids. **This is the one item where strict does not
  escalate**, and the reason should be documented at the call site.

---

## T3 — the literature pack (~3–5 days, network)

Closes "does the citation exist?" and partially "does the study support the row?". All endpoints
verified working; the notes below record what the probes actually returned.

### 3.1 PMID / DOI existence
`esummary.fcgi?db=pubmed`, batched. A nonexistent PMID returns a record carrying an `error` key
(`"cannot get document summary"`) — clean detection. **The DOI comes back free** in `articleids`.

### 3.2 PMID ↔ DOI cross-derivation
The ID converter **moved**: `ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` now 301s to
`https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/`. Batched; returns `doi`, `pmid` **and
`pmcid`** (the key to 3.3). Pass `tool=` and `email=` — the service warns without them.

- Filling an **absent** optional `doi` is enrichment, and belongs in the sidecar (below), not written
  back into `studies.csv`.
- An authored DOI that **contradicts** the PMID's DOI is a finding: report, never repair.
- Unblocks the 1.0 **doi-first** tracker item (`pmid` required → require ≥1 of `{doi, pmid}`).

### 3.3 Provenance quote vs fulltext
Two steps, and the first is what makes this tractable:

1. One batched Europe PMC call —
   `search?query=EXT_ID:… OR EXT_ID:…&resultType=core` — returns `pmcid` **and `isOpenAccess`**, so
   coverage is known *before* fetching anything.
2. For the open-access subset only, `…/{PMCID}/fullTextXML` (200, ~160 KB), strip tags, match
   `provenance_quote` / `provenance_regex`.

**Coverage is genuinely partial and that is not a failure.** Of three real PMIDs probed, only one was
open access — including both of this repo's own examples, which are not. The pass must report
*"checked 12 of 30; 18 have no retrievable fulltext"* and never treat unavailability as a negative
result. A quote that is a faithful paraphrase will also not match, so: **warning only, in both modes.**

### Architecture: a `literature.csv` sidecar
These checks produce findings *and* derivable values. The enricher has never written into an authored
file and should not start (see the co-authoring note in [docs/ROADMAP.md](docs/ROADMAP.md)). A sidecar
keeps the established pattern:

```
pmid, doi, pmcid, exists, is_open_access, quote_found, dataset, source, status, fetched_at
```

Fact-hashed like the others, compiled to an optional parquet, out of `_INPUT_FILES`.

---

## T4 — identifier hygiene (~2 days, network)

### 4.1 Trait ontology currency (OLS4)
`ols4/api/ontologies/efo/terms?iri=…` gives existence, `is_obsolete`, **and `term_replaced_by`**.

> **This check already paid for itself, before being built.** Probing it turned up `EFO_0001645` —
> the canonical trait example in `spec.py`'s `trait_efo_id` description, in `vocab.py`'s CURIE comment
> *and its author-facing error message*, in `REFERENCE_EXAMPLES.md`, and in a compiler test fixture —
> **obsolete**, replaced by `MONDO_0005010`. Now fixed: the grammar examples use `EFO_0004340` (body
> mass index, current, and an EFO id suits a field named `trait_efo_id`), and the two
> coronary-artery-disease examples use `MONDO_0005010`, which is what EFO actually redirects CAD to.
> Note that the obvious alternative, `EFO_0001360` (type 2 diabetes), is **also obsolete** — picking a
> replacement by memory would simply have swapped one retired term for another, which is the argument
> for shipping the check rather than doing this by hand.

### 4.2 Gene symbol currency (HGNC)
Use the **exact** endpoints, not `search/` (which is fuzzy — `BRCA1` returns 19 hits including
`ABRAXAS1`): `fetch/symbol/{g}` for currency and `fetch/prev_symbol/{g}` for retirement.
Probed: `fetch/symbol/MLL` → 0 found, `fetch/prev_symbol/MLL` → `KMT2A`.

Value beyond tidiness: it disambiguates the gene-metrics `not_found` path, which today cannot tell
"gnomAD has no constraint for this gene" from "this symbol was retired years ago".

### 4.3 dbSNP obsolescence — three states, and one that hides two meanings

The probe resolved the open question, and not the way it first looked. Observed shapes:

| State | NCBI `esummary db=snp` | Ensembl REST |
|---|---|---|
| **live** | `snp_id` == requested, `merged_sort='0'` | `name` == queried |
| **merged** | `snp_id` != requested, `merged_sort='1'` | `name` != queried, **or HTTP 400** |
| **absent** | `{'uid': …, 'error': 'cannot get document summary'}` | HTTP 400, `"not found for human"` |

> **Use NCBI as the oracle, not Ensembl.** Ensembl resolves *some* merges (`rs77121243` → `rs334`) and
> **400s on others** (`rs3216883`, which dbSNP correctly reports as merged into `rs3051860`), so
> Ensembl alone would misclassify a merged rsID as unresolvable. `esummary db=snp` is batched
> (~200/request) and authoritative. Ensembl's `name` is opportunistic bycatch — and note that
> `_loci_from_rest` already receives it and throws it away, so capturing it costs nothing.

**The important finding: `absent` conflates two materially different problems, and the APIs cannot
separate them.** Some rsIDs were *withdrawn* after the fact for mapping or clustering errors —
`rs11273140` is a real example — and its response is **byte-identical** to a never-assigned id
(`rs2000000000`): same `error` string from `esummary`, `count=0` from `esearch`, the same Ensembl 400.
For an author these mean opposite things:

- *never assigned* → a typo; fix the identifier;
- *withdrawn* → the variant itself was retracted, so **the annotation built on it may be worthless**.

Routes checked and rejected for telling them apart: `esearch` (no `withdrawn` filter — the phrase is
not indexed), and `latest_release/misc/rs_unsupported_b157.txt`, which looks promising but is a
**build-157 incident list** (16,292 rsIDs that lost their ClinVar observations to a one-off XML parsing
bug) rather than a general history — `rs11273140` is not in it. If separating the two ever becomes
worth it, it needs a historical dbSNP dump, not the live API; the current `latest_release/` tree
exposes only `JSON/`, `VCF/` and `misc/`.

**So the message must name both readings and assert neither.** Something like *"dbSNP has no record of
rs11273140 — it was either never assigned (a typo) or has been withdrawn, and these are
indistinguishable through the API. If withdrawn, the annotation resting on it should be re-examined."*
Claiming "typo" would be guessing, and guessing here sends an author to fix the wrong thing.

**Severity:** merged → warn / **fail in strict**; absent → the same ladder, since under either reading
the module rests on an identifier dbSNP will not serve. Not escalated beyond strict, because absent has
benign causes too (a very new rsID, or API lag).

> Beware the sampling trap this probe fell into: `rs999999999` looks synthetic but is a **real** variant
> (chr6:58247859). Pick negative-test rsIDs by checking them, not by looking implausible — and take
> `rs11273140` / `rs2000000000` as the committed withdrawn / never-assigned fixtures.

**The collision this forces** is written up in [docs/ROADMAP.md](docs/ROADMAP.md) § *the stale-identifier
collision* and must be read before implementing. In brief: never write the updated rsID into the
artifact. `weights.parquet` carries both `variant_key` and `rsid`, so an auto-update is not a one-time
digest move but an **identity migration performed by a network lookup** — reverse would emit the new
rsID into `variants.csv`, the next compile would key on it, and `variant_key` itself would change with
no authored edit anywhere. Hence: report, warn, and let `strict` push the fix to an authored edit.

New columns `rsid_current` + `rsid_status` (`live|merged|absent`) go **outside**
`RESOLUTION_FACT_FIELDS`, beside `rsid_alternates`. They describe time-varying *external* state; inside
the fact set they would make `resolution_signature` change when dbSNP merges something, with no change
to the module — the signature would stop being reproducible from the module's own content.

---

## Sequencing

1. **T1** — hours, offline, no new surface. Do first.
2. **T2** — one day, offline, uses infrastructure already provisioned.
3. **T3** — the largest piece; introduces `literature.csv` and its parquet.
4. **T4** — smallest network add-on; 4.1's finding is worth applying to the docs immediately.

## Deliberately out of scope

- **Enricher co-authoring** (permission-gated writes to authored files) — parked with reasoning in
  ROADMAP; the blocker is that `content_signature` is *defined* as reference-independent.
- **Fetching to complete the compiler's verifier.** The compiler's VRS check is partial by design; the
  fix for an unverifiable indel is not to give the compiler sequence access.
- **Adjudicating clinical disagreement.** T2 reports a ClinVar conflict; it never decides who is right.
