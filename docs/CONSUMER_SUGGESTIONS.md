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

**Status — accepted as a real defect, filed as [RM103](ROADMAP.md#rm103--a-version-with-no-digits-coerces-to-000-which-is-a-real-version-nobody-wrote)
rather than fixed in this pass, and documented in [SCHEMAS.md](SCHEMAS.md) meanwhile. Your correction
about the unquoted integer is confirmed, and our own docs did not carry the claim.** Reproduced:
`ModuleInfo(version="abc").version` is `"0.0.0"`, as are `draft`, `TBD`, `unreleased` and `-`. We then
took it one step further than the model, and it is worse than your report says — the value **reaches
the published artifact**: a real compile of a reference example with `version: "abc"` writes
`identity.version: "0.0.0"` into `manifest.json`.

**Why it is filed rather than repaired today, and the reason is release sizing rather than doubt.**
Refusing `"abc"` makes a spec that compiles today fail tomorrow, which is the same class as RM50 (a
PMC id refused by name) and RM48 (a wrong-build coordinate) — both shipped in **0.6.0** as minor work,
and both are listed in INTEGRATION_0_6 § 1 under *"two checks can newly refuse an author's spec"*
precisely because a consumer who compiles other people's specs sees CI go red. Legality sizes the
release here; severity would only order it. Given RM17's history — the coercion exists because the
pre-0.4 corpus is full of `v2` and `3`, and 0.6 widened it after **26 of 61** foreign modules refused
on an unquoted integer — we are not going to spring a new refusal on that corpus inside a patch. The
item carries three candidates, including why *coerce to an unmistakable sentinel* is a dead end: every
three-number string is somebody's real version, which is your complaint restated.

**One thing your report will want, because it changes what you can do today.** You tested the model
directly, where the coercion is indeed silent — but the **pipeline is not**. Both `compile_module` and
`validate_spec` already emit a warning naming both values: *"module.version 'abc' was read as SemVer
'0.0.0'. It is advisory either way … but the module now compiles under the coerced value."* We checked
the two for parity and they report it identically, so a build that greps its warnings catches this
now. `ModuleInfo.version_coerced_from` holds the authored string for the same purpose. That is a
mitigation rather than a fix — it does not stop the bad value being published — but it is the
difference between invisible and merely quiet, and it is available before RM103 lands.

**Your correction, checked and standing.** `ModuleInfo(version="1").version` is `"1.0.0"` on 0.6.1, so
"an unquoted `1` loads as an int and is rejected" is indeed false — that was the **pre-0.6** state, and
RM17's widening at `mode="before"` is exactly what fixed it (26 of 61 foreign modules, every one an
integer). We grepped our own documents for the stale claim and none carries it: AGENT_NOTES
`@yaml-version-int`, the CHANGELOG entry and DOGFOOD_0_6_FINDINGS D7-3 all describe the int refusal as
history. You have the hazard right — it is the unquoted **decimal**, which stays refused because YAML
reads `1.10` as `1.1` and the author's text is gone before any validator runs.

**Documented now**: SCHEMAS.md's identity-keys section states the digitless behaviour, that it reaches
`manifest.identity.version`, that both entry points warn, and that RM103 is the open question — so the
next person meets it in the reference rather than in a manifest.
<!-- triaged: uncut · sha bf9b69206ba1 -->

Same audit. `ModuleInfo(version='abc').version` returns `'0.0.0'`. A version is an identity key, and
`0.0.0` is indistinguishable from a deliberate pre-release, so an unparseable string becomes a
plausible-looking claim rather than an error. `1.5` (a float) is refused with an excellent message about
YAML reading `1.10` as `1.1`; `'abc'` is not.

Noting also that CLAUDE.md in our repo carried "an unquoted `1` in YAML loads as an int and is rejected",
which is **not** true on 0.6.1 — `1` coerces to `'1.0.0'`. We have corrected our own doc. The hazard is
the unquoted *decimal*, not the unquoted integer.

## S43 — `clinvar_draft` folds `likely_pathogenic` into `pathogenic=True` and never sets the `likely_pathogenic` column

**Status — the fold is deliberate and stays; the column is worse than you found and is now documented
as permanently unwritten, which is your second option. [SCHEMAS.md](SCHEMAS.md) carries it and three
tests pin it.** Reproduced on our own shipped `hfe_hemochromatosis`, which the drafter produced: its
one `clin_sig=likely_pathogenic` row carries `pathogenic=true`, and `likely_pathogenic` is `False` on
every row of the artifact.

**The fold is 0.3 compatibility, and you were right to suspect it had a history.** `pathogenic` and
`benign` are the legacy booleans P8 pins — required-ish authoritative since 0.3, never demotable
inside a major — and the four-tier distinction lives on `clin_sig`, the orthogonal axis added beside
them. `derive.pathogenic_from_clin_sig` folds both pathogenic tiers to `True` and
`clin_sig_from_booleans` states the loss in its own docstring: *"legacy cannot recover
`likely_pathogenic`/`likely_benign`"*. `clinvar_draft` is doing what the schema says. Your read path
already prefers `clin_sig`, which is the correct one.

**What you found is sharper than "never set by the drafter", and this is the part worth your
attention: `likely_pathogenic` and `likely_benign` cannot be written by anything.** They are parquet
columns with **no authored field behind them** — `VariantRow` declares `pathogenic` and `benign` and
nothing else, so `extra="forbid"` refuses `likely_pathogenic` in a CSV — and the compiler writes the
literal `False` into the parquet at a fixed line. They have been that way since the initial 0.1.0
commit, `reverse` does not read them, and no derivation consults them. So it is not 0 of 214,827 on
your module; it is 0 of every row of every module ever compiled by this project.

**We are not filling them, and the reason is the charter rather than reluctance.** They are published
columns that have always read `False`. Writing `True` — or `None` — into them changes what an existing
reader is told with no way for that reader to notice it changed, which is the silent break P3 exists to
prevent; removing them is major-only for the same reason. So the honest statement for the 0.x line is
the one you offered as your alternative, and it is now in the reference: **permanently unwritten, read
`clin_sig`**. They also went into SCHEMAS.md's tri-state table as its one acknowledged exception —
that table exists to say `None` is never `False`, and these two are a hardcoded `False` sitting in the
middle of it.

**On `pathogenic_count`: your reading is right, and probing it corrected something we would have told
you wrongly.** It counts the folded boolean, so it does include the likely tier — consistent with what
the boolean means, but not with what the name reads as. It also counts **authored `variants.csv` rows,
not parquet rows**, which we only established by writing the test: our first version asserted against
unique rsIDs in the parquet and failed, 13 vs 11, because resolution expands one authored row onto
several loci. Both facts are now in SCHEMAS.md, because the second is the kind of thing a consumer
reconciling a count against an artifact would otherwise chase for an afternoon.

**Three tests**, so the documentation cannot quietly stop being true: the two columns are unauthorable
and always `False` (walking both rather than naming one), a `likely_pathogenic` row reaches the parquet
as `pathogenic=true` on a shipped example, and `pathogenic_count` equals the authored rows carrying the
folded boolean and strictly exceeds the strictly-pathogenic ones. If either column ever becomes
writable, the first test fails and the doc gets rewritten deliberately rather than drifting.

**Nothing filed.** Filling the columns is major-only and there is no 1.0 design question here worth an
`RMn` of its own — the tier axis already exists and already works. If you would rather see the pair
*removed* at 1.0 than left reading `False` forever, say so and we will add it to the 1.0 cleanup
tracker; that is a real choice and it is yours to push on, since you are the consumer who would have
to stop reading them.
<!-- triaged: uncut · sha 27c16dbb010d -->

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

**Status — accepted; both genotype families and the licence pin are fixed in the tree (enricher,
shipping in 0.6.3). The `del`-spelled rows themselves stay skipped, and that half is unchanged and
deliberate.** All four claims reproduced against the provisioned snapshot before anything was
touched.

**The diagnosis you did not quite make, and it is the one that matters: our gate was narrower than
our own schema.** `_authored_genotype` accepted only `CC` — two unseparated bases — reasoning that
the general case needs the resolved ref/alt to disambiguate. That is true of an *unseparated* cell
and false of both shapes you found, because `validate_allele` accepts any `^[ACGT]+$` allele:

- **`CTT/CTT` is already separated by the source.** ClinPGx writes `/` wherever an allele runs past
  one base, so there is no splitting decision to get wrong. You are right that these are discarded
  *with* their `del` siblings — same `annotation_id`, so skipping the annotation took the writable row
  too. That is the F508del loss, and it was pure loss.
- **`A` / `CCCCCCC` is a single haploid allele**, which the grammar already holds and which is how
  ClinPGx spells mtDNA. Your instinct was right and so was your evidence — `split_genotype` handles a
  one-element list. The reasoning is the one `clinvar_draft.sole_expressible_genotype` already
  applies on the ClinVar side: the placeholder protects a zygosity decision, and on a haploid contig
  there is none to protect. Inventing a second allele would have been the error, not writing one.

**Measured after the fix: 158 rows recovered**, 36 at evidence level 1A — MT-RNR1 48 (all 24
annotations, the 1A aminoglycoside set intact), plus HTR2C, ACE, TYMS, IFNL4, GSTM3 and CFTR's
`CTT/CTT`. The unseparated multi-base cell the old rule was guarding against does not occur in the
snapshot at all; every multi-base call arrives slashed. It is still declined.

**What stays skipped, and why we are not moving it.** The `del`-spelled genotypes themselves —
`CTT/del`, `del/del` — still do not get written. Since RM5 the grammar *can* spell `<DEL:1500>`, so
the block is no longer "the format cannot express it"; it is that **ClinPGx publishes no length**, and
a lengthless symbolic allele is a rule the compiler drops. Writing those rows would hand you work the
next command in the workflow undoes. So DPYD\*7, RYR1 and ACE keep their `del` rows skipped — but any
pure-nucleotide sibling under the same annotation now survives, which is the part that was costing you
real findings.

**The general rule is now a test rather than a comment**, because this defect is the kind that
recurs: *every genotype spelling this pass declines must be one `PharmVariantRow` would also refuse*,
walked over the accepted set. The converse stays allowed — that is what keeps `del/del` skipped
deliberately rather than by accident.

**Your one-liner was exactly a one-liner, and it was worse than cosmetic.** `license_sha256` was null
on a **share-alike** source whose `LICENSE.txt` we ship in the snapshot ourselves — so the module
named ClinPGx's terms without pinning them to the text that governed the bytes, which is the entire
purpose of that field. Fixed by passing `license_text=`, read from the snapshot. One deliberate
difference from your framing: we hash **the file**, not `release.json`'s stated hash. The file is what
the module is actually claiming, and hashing it independently means a truncated or tampered copy
cannot pin to a value it does not have. They agree on your snapshot — we checked, byte for byte. An
absent `LICENSE.txt` (an older snapshot, built before the extractor) stays `None` and warns, rather
than inventing a hash.

**You are right that `merge_sources_file` is never-clobber and you cannot patch it afterwards** — so
a module drafted before this fix keeps its null. Delete the sidecar and re-draft to pick it up; that
is the documented way to regenerate after a machinery change.

**Nothing filed.** Four tests: the already-separated form, the haploid form, the never-narrower-than-
the-schema rule, and two against the real snapshot (MT-RNR1 and CFTR present, `del` spellings still
absent; the licence hash computed independently from the file). One existing assertion changed
deliberately — `_authored_genotype("CAT") is None` was the old rule stated as a test, and it is now
the new rule with the reason written next to it.
<!-- triaged: 0.6.3 · sha aae77d27f69b -->

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
