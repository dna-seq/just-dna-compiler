# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S41

**Claim ids from here, never from what this file shows.** S1–S40 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

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

---

## S41 — `multi_allelic_rsids` keys `ref` into the site, so a dup/del pair collapses and one ClinVar record is lost

**Status — accepted and fixed in the tree (enricher, uncut; it ships in 0.6.3). Your candidate was
right, and the predicate is now the whole allele event rather than the alt alone.** Reproduced three
ways before touching anything: your `rs80359609` pair through the real `_row_cells` →
`append_partial_rows` path (2 records in, **1 row out**, and the survivor is the 1★ record while the
3★ BRCA2 `ATT>A` is dropped — consequence (1) exactly as you describe it); the predicate in isolation;
and the whole thing against our own `2026-06-27` snapshot over your five named genes.

**Our measurement agrees with yours and adds the number that convinced us.** 17,004 records for
BRCA1/BRCA2/ATM/MLH1/MSH2: 942 rsIDs flagged under the old rule, 1,589 under the new one, and the 647
newly flagged are **exactly** the 647 identities that were collapsing — 725 records dropped, of which
**187 dropped a better-reviewed record than the one kept**. After the fix: 0 collapsed identities, 0
records dropped, and 0 records made unkeyable, which was the one risk in the candidate (a record with
no complete coordinate would become `unkeyable` rather than collapsing; there are none in that
selection, but the test asserts it rather than assuming it).

**One deliberate difference from your wording.** You proposed grouping on `rsid` alone — any rsID
naming more than one record takes coordinate identity. We group on the distinct `(chrom, start, ref,
alt)` events instead, which coincides with yours on real data (every multi-record rsID in that
selection is also multi-allele) but differs on a re-submission: the same allele under a second
`variation_id` is one claim written twice, and moving it to coordinate identity would not separate the
two rows anyway. Flagging only when coordinate identity actually *resolves* the collapse keeps the
predicate true by construction rather than by measurement. Both readings fix your case.

**Your reading of the docstring is the one that settled it.** "More than one alt at one position" was
the correct rule and the code was narrower than its own claim — a differing `ref` breaks an rsid-only
identity exactly as thoroughly as a differing `alt`. Widening also catches a third shape neither of us
listed: **one rsID at two distinct positions**, which the old site key also swallowed, and which is
the direct producer of your consequence (2).

**Six tests, including the one that runs on the real snapshot.** The mirror pair does not collapse;
the pair demonstrably *did* collapse under the old grouping (restated in the test, so the claim is
shown rather than trusted); a re-submitted identical allele still does not flag; one rsID at two
positions flags; the HFE case the predicate was originally written for still fires; and no identity
collapses across your five genes — asserted as a relationship (unique identities == keyable records)
so it holds whatever the snapshot's vintage. All six were run against the unfixed predicate and
watched to fail, the real-data one at exactly 725 dropped records.

**The warning now aggregates.** It listed every flagged rsID, which was right at the one that motivated
it and unreadable at 1,589; it uses the house `examples` helper, so at one rsID the text is
byte-identical to what `reference_examples/hfe_hemochromatosis/README.md` quotes.

**On consequence (2), and this is the part we are not claiming to have fixed.** The 8,231 matchable
rows with wrong labels are a *downstream* effect of the collapse: with each record keeping its own
identity there is no surviving rsID for resolution to pair against two loci, so newly drafted panels
should not produce them. We have not re-measured that end to end on your modules, and we are not going
to assert it from the drafting fix alone — your `_identity_collapse_note` is still the right thing to
run, and if it reports collapses on a panel drafted after this ships, that is a second defect and we
want it as its own item. **Already-published artifacts are not reached by any of this**, which is the
bit worth planning around: they were drafted under the old predicate and need a re-draft.

**Nothing filed.** The repair is legal and additive-in-effect — it writes more rows, moves no schema,
and the drafted output is authored material a human owns rather than a compiled identity — so it is a
fix rather than a roadmap item. `manifest` fields, `content_signature` and every reference example are
untouched; suite 2762 → 2768.
<!-- triaged: 0.6.3 · sha 0b16582fa93d -->

Reported from just-dna-lite, 2026-08-19, during a 0.6 audit of the ten `v1_port` modules. Measured on
enricher 0.6.2 / compiler 0.6.1 / format 0.6.1 against the ClinVar `2026-06-27` parquet snapshot.

**What we ran.** Rebuilt the identity assignment `draft_gene_panel` performs, over the exact record set
`select_by_gene` returns for our three ClinVar panels, and compared drafted identities to input records.

**What we expected.** An rsID naming more than one distinct ClinVar allele takes the coordinate identity,
so no two records share an authored row.

**What happened.** `multi_allelic_rsids` groups on `(rsid, chrom, start, ref)` and fires only on >1 alt
*within* that group. The ordinary ClinVar dup/del mirror pair — `A>AT` and `ATT>A` at one position — is
two groups of one alt each, so the rsID is never flagged, both records reduce to the same rsid signature,
and `append_partial_rows` keeps whichever the selection ordered first.

| module | records dropped | collapsed identities | notes |
|---|---:|---:|---|
| `cancer` | 1,619 | 1,481 | 483 allele events exist nowhere in the artifact — 454 pathogenic, 29 likely-pathogenic, **108 at 3★** — across 63 genes incl. BRCA1, BRCA2, ATM, MLH1, MSH2 |
| `pathogenic` | 3,140 | 2,953 | 100% differ in `ref`; 435 differ in `clin_sig`; 2,378 differ in `condition`; 69 sit at different positions |

Two consequences worse than the dropped row itself:

1. **The survivor is not the better-evidenced record.** `ref` sorts before `review_stars DESC` in
   `select_by_gene`'s ORDER BY, so which record wins is an artifact of allele spelling. On `cancer` the
   kept row is the *lower*-starred one in 400 of 1,481 collapses. `rs80359609` keeps a 1★ `A>AT` and drops
   the 3★ BRCA2 `ATT>A` (Variation 52138).
2. **The dropped record's coordinate comes back wearing the survivor's labels.** Resolution finds both
   loci for the surviving rsID and the compiler pairs every authored genotype with every resolved locus.
   On `pathogenic` that is 10,558 rows, of which **8,231 are matchable** (het or hom-alt, so restoration
   never sees them): **301 state the wrong `clin_sig` for the locus they sit at and 1,453 the wrong
   condition**. `rs761621516` is the sharpest — a GBA1 record at 1:155239968 rendered with GAMT's gene and
   "Parkinson disease, late-onset", and a genotype `C/CGCT` not expressible from its own `ref=GGTA`. The
   compiler flagged that one ("could not be decided here") and kept the locus.

**Candidate fix.** Group on `rsid` alone: any rsID naming more than one record in the selection takes
coordinate identity. The docstring already says the predicate is "more than one alt at one position" —
a differing `ref` at the same position breaks the identity just as thoroughly, and the mirror pair is
common rather than exotic.

**Why we did not work around it locally.** `draft_gene_panel` re-queries the snapshot itself, so the
records are gone before anything on our side sees the drafted rows, and our own `_allele_index` /
`_row_key` key on the same collapsed identity. Meanwhile we detect the condition and report it
(`_identity_collapse_note` in `clinvar_panel.py`) so a build states what it lost instead of shipping the
loss silently. That is a report, not a repair, and it is all a consumer can do from outside.

**Not urgent for restoration.** We checked: the hom-ref half is fully withheld on both modules — the
pre-0.6 `ref`-spelling guard catches 1,296/1,296 on `cancer` and 2,728/2,728 on `pathogenic`, and there
are **zero same-`ref` expansions** in either. The 8,231 matchable rows are the live half, and neither
`locus_count` nor the `ref` guard addresses them, because those rows do match a real call.

## S42 — `ModuleInfo.version` coerces `'abc'` to `'0.0.0'` rather than refusing it

Same audit. `ModuleInfo(version='abc').version` returns `'0.0.0'`. A version is an identity key, and
`0.0.0` is indistinguishable from a deliberate pre-release, so an unparseable string becomes a
plausible-looking claim rather than an error. `1.5` (a float) is refused with an excellent message about
YAML reading `1.10` as `1.1`; `'abc'` is not.

Noting also that CLAUDE.md in our repo carried "an unquoted `1` in YAML loads as an int and is rejected",
which is **not** true on 0.6.1 — `1` coerces to `'1.0.0'`. We have corrected our own doc. The hazard is
the unquoted *decimal*, not the unquoted integer.

## S43 — `clinvar_draft` folds `likely_pathogenic` into `pathogenic=True` and never sets the `likely_pathogenic` column

Same audit, measured on all three of our ClinVar panels.
`clinvar_draft.py` sets `cells["pathogenic"] = True` for both tiers, commented "the 0.3 booleans stay
authoritative and are folded from the same call, never independently". The result is not merely lossy —
it is a wrong assertion on the rows it touches, and the column that exists to carry the distinction is
never written:

| module | `clin_sig=pathogenic` | `clin_sig=likely_pathogenic` | stored `pathogenic` | stored `likely_pathogenic` |
|---|---:|---:|---|---|
| cardio | 75,909 | 39,151 | `true` on both | `false` everywhere |
| cancer | 110,476 | 28,778 | `true` on both | `false` everywhere |
| pathogenic | 402,174 | 214,827 | `true` on both | `false` everywhere |

`manifest.stats.pathogenic_count` reads the boolean and inherits the inflation (cancer 136,662;
pathogenic 611,542). We are not asking for a behaviour change we cannot see the history of — the fold may
well be deliberate 0.3 compatibility. What we would ask is that `likely_pathogenic` either be populated
or be documented as permanently unwritten, because a consumer keying on the column gets 0 of 214,827 and
nothing says so. Our own read path prefers the `clin_sig` column (`_effective_clin_sig`) and is unaffected.

## S44 — `clinpgx_draft` drops MT-RNR1 and every `del`-spelled annotation, including CFTR F508del

Same audit, on our `pharmgkb` module (ClinPGx snapshot, evidence ≥2B).

- **MT-RNR1: 16 annotations / 32 rows, all level 1A**, dropped because the genotype is a single haploid
  allele the drafter cannot pair into a diploid genotype. This is aminoglycoside-induced hearing loss, a
  CPIC guideline. It does not look like a format limit: `split_genotype` handles a one-element list, and
  the format carries a whole `heteroplasmy` family for mtDNA.
- **6 annotations / 19 rows dropped whole for a `del` spelling**, including **CFTR F508del (1A)**,
  DPYD*7 (1A), RYR1 (1A) and ACE (2A). The sharp part is that these annotations also carry
  **pure-nucleotide** genotypes (`CTT/CTT`) which the schema accepts, and those are discarded with them.
  Our module therefore ships 176 CFTR rows and the drug "elexacaftor / tezacaftor / ivacaftor" while
  omitting the most common CF variant.

Also minor, and a one-liner: `sources.parquet.license_sha256` is null on both our rows although the
snapshot ships `LICENSE.txt` and `release.json` states its hash (they match exactly). `SourceTerms.row`
already accepts `license_text=`; the `clinpgx_draft` call passes only `declared_use` and `dataset`. So we
record ClinPGx's terms without pinning them, which is the field's purpose, and `merge_sources_file` is
never-clobber so we cannot patch it afterwards.
