# RM171 — adopt the increment, never the photocopies

**Subject:** the adoption shape for [ROADMAP_HISTORY.md § RM171](../ROADMAP_HISTORY.md#rm171--mitomaps-curated-mtdna-tables-adopted-as-the-increment-they-carry-over-clinvar).
**Measurements:** [MITOMAP_STATUS](MITOMAP_STATUS.md). Every number this note leans on was measured there; this file does not re-derive them.
**Date:** 2026-09-03.

**Built the same day, and this file became its specification rather than a proposal.** RM171 shipped on
2026-09-03; the record is ROADMAP_HISTORY § RM171 and the five places the build departed from the plan
are a dated addendum on PROPOSAL_0_7_PT3. **§7's open list is superseded by that entry** — items 1, 2,
5, 6, 8 and 9 are closed by the build, and 3, 4 and 7 survive as what the entry still names as open.
**§1's motivating sixteen is six on a rejoin**: all sixteen bracketed-and-absent rows reproduce, but
thirteen of them are the `:` deletions §6 puts in the unmintable count, which is the sharpest available
argument for the rule this note ends on.

The body below is left as written. It is a **design record of a proposed shape**, and where a sentence
here and the shipped entry disagree, the entry wins.

**The proposal this note records.** Adopt MITOMAP's unique increment against the ClinVar cache that is already on disk, never the rows ClinVar already publishes. Derive that increment every rebuild. Do not hardcode "16". Do not map MITOMAP's confirmation token onto `clin_sig`. Do not invent a meaning for `VUS*`.

---

## 0. What is `VUS*`?

A tenth of the 136 bracketed `mmutation` rows write `[VUS*]` instead of `[VUS]` (10 rows). The sibling `rtmutation` table has 13 more. The asterisk is a real distinguishing mark in the data. It is not a rendering glitch of the dump: the rendered wiki page carries both `VUS]` and `VUS*]` in its data cells.

**What it is not.**

- It is not one of the five ClinGen mtDNA VCEP classes. The legend on MITOMAP's wiki documents `P`, `LP`, `VUS`, `LB`, `B`. It does not document the star.
- It is not the legend's own footnote marker. That marker is a diamond (◊), and the legend example writes `"Reported [VUS◊]"` with the diamond *inside* the bracket. The data cells use a literal asterisk on some rows and nothing on others.
- It is not APOGEE's `VUS+` / `VUS-`. Those live on `mitomap.apogee`, a 7-tier in-silico predictor (24,181 rows). They leak into `rtmutation` on one row each. They are a different instrument that happens to share three letters.
- It is not a sixth ACMG class. On the ClinVar overlap, all 10 `VUS*` rows that were in the snapshot matched `uncertain_significance`, exactly as `VUS` did. The star did not move the class.

**Kitchen table.** Some salt bags on the shelf have a star stamped on them. The wall chart says "VUS means we do not know if this is salt or sugar." The chart never mentions the star. Every starred bag that also sits in the supermarket (ClinVar) is labelled "do not know" there too. So the star is real, it only appears on the "do not know" bags, and nobody wrote down what it is for.

**What this proposal does with it.** Withhold. `normalize_clin_sig` is not given a `VUS*` → `uncertain_significance` mapping. A miss row whose only rating is `VUS*` is counted and left without a `clin_sig` fill, the same way an unbracketed row is. Collapsing the star into `VUS` would be inventing a meaning the source did not publish. A later legend, if one turns up, is one function edit.

The three competing readings stay on the table and none of them is taken:

1. The wiki's diamond rendered as `*` in the dump (fails: unmarked `VUS` rows sit beside marked ones on the same page).
2. A real qualifier on some VUS calls (possible; undefined).
3. Confusion with APOGEE's `VUS+`/`VUS-` (fails for `mmutation`: that table has `VUS*`, never `VUS+`).

---

## 1. What this is answering

RM171's remaining question, restated on the measurements, was a binary:

> Does a source that would contribute 16 new expert-panel calls, no genotype, no rsID and a second sibling table earn an adoption, or does ClinVar already carry this content?

That binary is the wrong question. It treats "16" as a fact about MITOMAP. It is a fact about one join against one ClinVar vintage (the 2026-06-27 chrMT snapshot in this checkout). A newer ClinVar moves the 16. A hardcoded list of sixteen alleles is a snapshot of a diff, and a snapshot of a diff is stale the next time either parent is rebuilt.

The right question is: **what does MITOMAP publish that the ClinVar cache does not?** Answer that every time both caches are current, and append only that increment.

Two halves of `status` stay on different axes, which is why a "map `status` onto `clin_sig`" adoption was never the shape:

| token | whose call | maps onto `clin_sig`? |
|---|---|---|
| base (`Reported` / `Cfrm` / `Conflicting reports`) | MITOMAP's own literature-count criterion | **no.** MITOMAP says in as many words that this is not an assignment of pathogenicity |
| bracket (`[P]` / `[LP]` / `[VUS]` / `[LB]` / `[B]`) | ClinGen mtDNA VCEP, scored by McCormick 2020 | **yes, as a normalization.** Same five classes as `VALID_CLIN_SIG` |
| `[VUS*]` | undocumented | **no.** Withhold (§0) |

Of 136 bracketed `mmutation` rows, 120 were already in that ClinVar snapshot, all 120 as `reviewed_by_expert_panel`, 119 agreeing. Those 120 are the same VCEP call arriving by two routes. Drafting them from MITOMAP would write a photocopy and attribute it to the wrong publisher.

The 16 that were absent (`LP` 10, `VUS` 6) are the rated increment on that vintage. They are the motivating case, not the inventory.

---

## 2. Why RM28 does not take this

A predicate (`salt AND pepper = pathogenic, else benign`) needs closed operands. MITOMAP's combination-only tail (18 of the 34 prose rows) names partners that are often not in the dump. "Else benign" over an open set manufactures reassurance the source never published. That is RM28's residue, parked on a corpus, and it is a different item. This note does not reopen it.

---

## 3. The shape: two parents, one derived miss

The enricher already has a cache registry (`caches.CACHE_LANES`, RM176). Each lane has three stages — acquire, build, publish — and every stage it lacks carries its reason as a field. ClinVar is already a lane. MITOMAP is not, and the increment is not a third independent download.

```
mitomap.org dump          ClinVar VCF
        │                       │
   acquire / build         acquire / build
        │                       │
   mitomap snapshot        clinvar snapshot     ← two parent lanes
        └───────────┬───────────┘
                    │ join on exact allele identity
                    ▼
              mitomap-miss snapshot             ← derived child
                    │
                    ▼
         draft --source mitomap-miss
              appends variants.csv + studies.csv
```

**Parents.**

- `clinvar` — already a `CacheLane`. The chrMT parquet is the half this join reads. A rebuild of ClinVar is a rebuild of the parent, not of the miss by itself.
- `mitomap` — a new lane. Acquire is `curl` of `https://mitomap.org/downloads/mitomap.dump.sql.gz` (byte-identical to what RM164 held; no interstitial). Build extracts `mmutation` (and, when the sibling is in scope, `rtmutation`) plus `mmutation_reference` / `reference`. Publish is permitted on the terms already read (MITOWeb CC BY 3.0). `SourceRow.dataset` records the dump's `Last-Modified` and sha256, the same way ClinVar records `clinvar_file_date`.

**Child.** `mitomap-miss` is not a download. Its acquire stage is "both parents are on disk"; if either is absent the rebuild outcome is `built=None` (could-not-run), never a silent empty miss and never a failure of ClinVar. Its build is the join in §4. Its `release.json` pins **both** parent digests, so a ClinVar rebuild without a miss rebuild is a detectable stale child (`@currency-asks-the-source-not-the-cache` applied to a derived lane: the "source" is the two parents).

The registry does not yet have a `parents` field. That is a small additive on `CacheLane` (a tuple of lane names, empty for today's twelve) and a guard that a child cannot rebuild before its parents. Computing the join only at `draft` time, with no published miss snapshot, is the cheaper alternative and is still legal. The published-child form is preferred because the increment then has an identity a currency check can talk about, and because `@write-the-sourcerow` wants a dataset pin for each source a pass consulted.

---

## 4. The join

Identity is the exact allele, the same key [MITOMAP_STATUS](MITOMAP_STATUS.md) §5.2 used:

`(chrom="MT", start=position, ref=refna, alt=regna)`

against ClinVar chrMT `(chrom, start, ref, alt)`. Upper-case both sides. No fuzzy match. No position-only match in the miss set — a position-only hit is a different allele at the same locus, and collapsing it would hide a real increment (or invent one, if the two sources left-align an indel differently). The position-level count in the probe (390 of 602) is a loose bound on under-count, not a join key.

A MITOMAP row is a **miss** when that key is absent from the ClinVar snapshot **and** the row mints a `variant_key` from the published alleles (573 of 602 do; the 24 `:` deletions and the 5 prose / `ref==alt` rows do not).

Three buckets, not one:

| bucket | what it is | what a draft writes |
|---|---|---|
| **photocopy** | exact allele in ClinVar | nothing. The VCEP call is already adopted, with ClinVar's provenance |
| **rated miss** | absent from ClinVar, bracket in `{P, LP, VUS, LB, B}` | a `variants.csv` row, `clin_sig` from `normalize_clin_sig` on the bracket |
| **unrated miss** | absent from ClinVar, no mappable bracket (`VUS*`, no bracket, `Conflicting reports` only, prose tail) | counted. No `clin_sig` fill. A later pass may want the identity; this shape does not invent a class |

The 16 on the 2026-06-27 vintage (`LP` 10, `VUS` 6) land in **rated miss**. They are the worked instance, not a constant. A rebuild against a newer ClinVar may shrink that set, grow it, or move a row from rated miss to photocopy because ClinVar caught up.

The one measured disagreement (MT-ND1 `m.3761C>A`: MITOMAP `[VUS]`, ClinVar `likely_pathogenic`, both expert-panel) is a photocopy in this join — the allele is in ClinVar — and therefore not drafted. Currency of the two copies is RM151's problem, not this lane's.

---

## 5. What a drafted miss row looks like

`draft --source mitomap-miss` appends. It never rewrites (`@draft-appends`).

**`variants.csv`.** Identity from the row as published: `chrom=MT`, `start=position` (1-based, paste it), `ref=refna`, `alts=regna`. `gene` from `locus` where that cell is a single symbol (`MT-ATP8/6` is two genes and withholds). `clin_sig` from the bracket via the one existing normalizer (`@one-normalizer-two-spellings`); `VUS*` does not go through it. `genotype` is required on `VariantRow` and MITOMAP publishes none — `homo`/`hetero` are literature-presence flags, not a called genotype. The cell is stubbed (`unresolved` is the wrong member; a generated stub uses a before-validator the author must replace, `@stub-cannot-compile`). `weight`, `conclusion`, `direction` stay empty. Those are the cells only a pilot settles.

**`studies.csv`.** Every miss row cites. The dump's `reference.nlmid` held a PMID on 4 of 4 sampled values and is empty on 397 of 6,770 reference rows. The draft writes a study row per `(variant_key, nlmid)` where `nlmid` verifies as a PMID, and withholds the rest. Four-of-four is not a total; the first build of this lane owes the rest of that column before it claims "every citation". `literature.csv` describes the paper; the variant row cites.

**`licensing.csv`.** One `SourceRow` for `mitomap` at the annotation layer, `dataset` the dump pin. The miss snapshot's own pin of both parents is recorded there too, so a module compiled from a stale miss is visible. MITOMAP is CC BY 3.0; the compile gate does not fire. `declared_use` stays the author's.

**`rtmutation`.** Same grammar, 494 rows, and the table the repo's only mtDNA module actually uses. The first build of `mitomap-miss` can be `mmutation`-only; the sibling is the same join with a second input table, not a second shape. Shipping `mmutation` and discovering `rtmutation` later is how RM164 happened. Name the table in the snapshot (`@probe-names-the-table`).

---

## 6. What this deliberately does not do

- Map `Reported` / `Cfrm` / `Conflicting reports` onto `clin_sig`. The source declines that judgement.
- Draft the 120 photocopies so a concordance check has something to disagree with. Concordance against ClinVar is already a check; feeding it a copy of itself is a tautology (`@tautology-zero`).
- Left-anchor the 24 `:` deletions in the format or compiler tiers. That needs an rCRS base at `position-1`, which Principle 2 forbids those tiers from fetching. The enricher may do it later, as its own pass, and the miss lane counts them as unmintable until then.
- Close the 18 combination-only prose rows (`Cfrm (in combo with …)`). Those are genotype claims, not allele claims, and they are RM28's corpus if they ever earn a brick.
- Treat "16" as an inventory, a test fixture, or a changelog number. Tests assert relationships: every miss key is absent from the parent ClinVar snapshot; every photocopy key is present; rated-miss `clin_sig` is the normalizer's image of the bracket; a parent rebuild without a child rebuild is stale.

---

## 7. Does this solve RM171?

**It answers the adoption question. It does not close the item.**

What the entry was blocked on: a binary between "adopt `status`" and "ClinVar already has this." This shape dissolves that binary. The bracket is a normalization where it is one of the five documented VCEP classes. The increment is worth drafting. The photocopies are not. The confirmation token is never a `clin_sig`. That is a complete answer to "is `status` mappable, and onto what, for the rows that would actually be new."

What still sits between this note and a closed RM171:

1. **It is unbuilt.** A shape is not a lane, a draft source, or a `SourceTerms` row.
2. **The 16 is one vintage.** The first build owes a rejoin against the ClinVar cache of that day. The methodology is complete; the inventory is not.
3. **`VUS*` is withheld, not understood.** §0 is a refusal to guess. If a MITOMAP page or McCormick 2020 (unread; the probe scoped the documentation finding to four wiki pages) defines the star, the withhold is revisited. Until then a rated-miss count that silently includes those 10 is a lie.
4. **`nlmid` is a sample, not a total.** 4 of 4 PMIDs matched. 397 references have no `nlmid`. The literature append is incomplete until the column is walked.
5. **`genotype` is stubbed.** The source will never fill it. That is honest and it is also why a MITOMAP-drafted module cannot compile until a human writes those cells. Adoption of the increment is not a one-command module.
6. **`rtmutation` is the same shape, not yet in the first increment.** The repo's `mt_heteroplasmy` variants live there. An `mmutation`-only miss would draft nothing those two rows need.
7. **The 250 unbracketed rows that are also absent from ClinVar** are an identity increment without a mappable class. This shape counts them as unrated miss and does not draft a `clin_sig`. Whether their identity is worth a row at all is a second, smaller call, and it can wait.
8. **Terms — discharged, 2026-09-03.** The live page was read from a browser. §9. The 2019 Wayback text was not stale on the licence class (still CC BY 3.0) and was stale on the revision and on one sentence the `SourceTerms` row now has in writing.
9. **Placement of the child** (published `CacheLane` with a `parents` field, versus a draft-time join with no snapshot) is a build choice, not an adoption choice. Either implements §3. The published child is the one this note prefers, for the pin.

So: sufficiently complete to *stop arguing the binary* and to build against. Not sufficiently complete to mark RM171 shipped, and not a reason to put "16" in a constant.

---

## 8. Assertions a first build has to keep

Relationships, never a count copied off this note.

- A miss key is absent from the ClinVar parent at exact `(chrom, start, ref, alt)`.
- A photocopy key is present there.
- Every rated-miss `clin_sig` equals `normalize_clin_sig` of that row's bracket, and the bracket is one of `P`, `LP`, `VUS`, `LB`, `B`.
- `VUS*` never produces a `clin_sig`.
- A confirmation token never produces a `clin_sig`.
- `release.json` on the child names both parent pins; a child whose parent pin does not match the parent on disk is stale, not current.
- Rebuild of the child with either parent absent is `built=None`, not an empty miss.
- Draft appends; a second draft of the same miss set adds no row (`match_on` the identity key).
- The 24 `:` deletions are in the unmintable count, not in the drafted set, until an enricher pass anchors them.

---

## 9. Live terms read, 2026-09-03 — how §7.8 proceeds

`mitomap.org`'s web surface still 403s to `curl` and to the fetch tool. A browser does not. The page was opened in this session, not reconstructed from memory or from the 2026-04-17 Wayback capture.

**What was opened.**

| | |
|---|---|
| terms URL | `https://www.mitomap.org/foswiki/bin/view/MITOWIKI/HelpTerms` |
| title | `HelpTerms < MITOWIKI < Foswiki` |
| topic revision | **r5 - 30 Jun 2026, UnknownUser** |
| attribution URL (the page names it) | `https://www.mitomap.org/MITOMAP/CitingMitomap` |
| that page's revision | **r10 - 30 Jun 2026, UnknownUser** |
| CC deed the badge links | `http://creativecommons.org/licenses/by/3.0/` |

`https://www.mitomap.org/foswiki/bin/view/MITOMAP/HelpTerms` is the wrong web. That topic does not exist; Foswiki offers to create it. The live terms live under **MITOWIKI**, which is also what CitingMitomap's "Terms of Use" link points at. The ROADMAP's `MITOWIKI/HelpTerms` path was already the right one.

**The COPYRIGHT block, as served.**

> All content on Mitomap.org (including MITOWEB, MITOMAP, and MITOMASTER) is licensed under a Creative Commons Attribution 3.0 License, unless otherwise noted.
>
> - Author Ownership: Authors retain the copyright to their contributions.
> - Open Access: Anyone is free to download, reuse, reprint, modify, distribute, or copy the data.
> - Commercial & Clinical Use: Data is 100% free to use for individuals, clinical labs, and commercial services. No special permissions or fees are required.
> - Requirement: You must properly cite the original authors and source as described here: https://www.mitomap.org/MITOMAP/CitingMitomap.

CitingMitomap asks for one of two forms: `MITOMAP (mitomap.org)`, or Lott et al. 2013, *Current Protocols in Bioinformatics*, PMID 25489354.

**What moved since the 2019/Wayback text, and what did not.**

The 2026-04-17 Wayback capture was of **r4, 2019-07-30**. This page is **r5, 2026-06-30** — revised two months after that capture, same day as CitingMitomap r10. The licence class did not move. The wording did.

| | r4 (Wayback 2026-04-17) | r5 (live 2026-09-03) |
|---|---|---|
| licence | Creative Commons Attribution 3.0 | same, badge links the 3.0 deed |
| floor | "except where otherwise noted" | "unless otherwise noted" |
| named products | MITOMAP, MITOMASTER, & MITOWIKI | MITOWEB, MITOMAP, and MITOMASTER |
| commercial use | inferred from CC BY 3.0 | **stated**: individuals, clinical labs, commercial services; no permission, no fee |
| attribution | "original authors and source are cited" | same duty, now a URL to CitingMitomap |

The SOFTWARE section adds that MITOWIKI "has been discontinued due to security concerns." The terms page itself still lives on that web. That is a hosting note, not a terms change.

**What a `SourceTerms` row can now say**, from this read rather than from the Wayback quote:

```
source          mitomap
license         CC-BY-3.0
license_url     http://creativecommons.org/licenses/by/3.0/
attribution     MITOMAP (mitomap.org), or Lott et al. 2013 PMID 25489354
notice          floor: unless otherwise noted. Clinical-lab and commercial use are stated as free.
share_alike     False
commercial_use  True
redistribution  True
```

The compile gate does not fire. `declared_use` stays the author's. `license_sha256` is for the build that captures the page text beside the dump, not for this note.

**The two traps from the 2026-09-02 read still hold**, and the live page does not dissolve them:

1. A search for MITOMAP's licence still surfaces **CC BY-NC**, which is the *NAR article's* licence, not the database's. CitingMitomap lists those papers as *citations*, not as the data terms.
2. **"unless otherwise noted" is the floor.** A per-record note outranks the site default (`@a-hosts-terms-are-not-its-contents-terms`). The licence row is written as a floor, never as "every cell is CC BY 3.0."

**How we proceed.** `MITOMAP_TERMS` may be authored from this read. §7.8 is no longer a blocker. The remaining work in §7 is the build, the vintage rejoin, `VUS*`, `nlmid`, the genotype stub, and whether `rtmutation` enters the first miss. None of those waited on a 403.
