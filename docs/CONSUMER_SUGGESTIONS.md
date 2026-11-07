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

## S132 — across the 0.7 → 0.8 Ensembl switch, six published insertions now name a different event, and no witness could say which side is right

*From just-dna-registry's lead, 2026-11-07, against just-dna-format / compiler / enricher 0.8.0 as released,
registry 0.28.1. Evidence, tables and scripts: `/data/just-dna-cache/upstream-evidence/registry-replay-2026-11-07/`
on the shared machine (start with `ANALYSIS.md`; `README.md` says what each file is).*

**What we ran.** Our staging box re-derived every published module against your 0.8 Ensembl snapshot
(`ensembl-variation-2026_07_13-vep116.0`, RM372) with `enrich(rederive=True)`, online only for modules carrying
an indel, then recompiled under 0.8.0. That run's report was lost, so we replayed it from each successor's
predecessor on a scratch catalog. The replay is complete (46 modules) and agrees with the original run on every
module: 34 published, 12 refused for drift outside the quiet arms (`respelled`, `gained_allele`, `gained_rsid`).
Two caveats: online answers were asked again on the replay's day, and the snapshot-wide numbers below cover
chr22 and chr9 only.

**What moved.** Every digest, as the 0.8.0 record declares. In `resolution.csv`, 690 subjects drifted. 628 were
`gained_allele` (352 of them rows a 0.7 table held with a position and empty REF/ALT, the rest sites where 0.8
names more ALT alleles) and 22 `respelled`; those published. The 40 subjects behind the 12 refusals are three
different things:

- 11 `lost_allele`: alt-contig placements (`HSCHR17_*_CTG5`, `HG76_PATCH`, `HG2072_PATCH`) that a 0.7 table had
  from live Ensembl REST (`source=ensembl-rest`). Neither snapshot carries alt contigs, the primary placement is
  unchanged, and nothing moved.
- 23 `undecided`: read against the GRCh38 primary assembly, every allele the two snapshots share is the same
  haplotype, so these are respellings. They held only because the run had no sequence access
  (`reference_allele` skipped in 41 of 46 modules).
- 6 `moved`, and these are real. Each is an insertion that the pre-0.8 snapshot placed one base left of where 0.8
  places it, on a different anchor: rs35510806 6:126357184 A>AA → 6:126357185 T>TA, rs5867305, rs11407151,
  rs8176719, rs111299422, rs201136395. Both REF anchors are the true reference
  base, so a REF-allele check passes both. The two are different haplotypes, not two spellings of one event.
  The 1000G GRCh38 call set (positional, no rsIDs) holds the 0.8 event at all six loci and the pre-0.8 event at
  none, so on that evidence 0.8 is right.

It is not confined to our modules. On chr22, of 279,800 single-ALT insertions that pair between the two
snapshots by rsID and inserted sequence, none kept its position: 174,548 moved one base left and 105,252 one
base right. Checked for every pair against the anchor base, all of the left moves are the same haplotype and
none of the right moves is. Where 1000G observes either spelling of a right-moved one, it holds the 0.8
spelling 4,321 times, the pre-0.8 one 914 times and both 81 times; chr9 gives the same proportions (10,842 /
2,605 / 204). So roughly 38% of insertions now name a different event. At the 914 loci 1000G holds the pre-0.8
spelling and not the 0.8 one; whether those are rsID placements 0.8 got wrong or neighbouring variants under
other rsIDs, a positional call set cannot say.

**What your witnesses said.** `needs_recompile("0.7.0", "0.8.0")` declares 35 changes and none names the
snapshot switch, `resolution.csv` or a placement. We read that as the record doing its job: its axes describe
what the compiler does with a spec, and a re-derivation changes the spec's derived input, for which there is no
axis. `placement_agreement` reported 0 findings in all 34 successors, with 4,112 of 4,688 placed rsIDs (87.7%)
holding one witness only; ClinVar placed 127 of the 2,659 successor rows. For the six that moved, ClinVar holds
none, two were compared with Ensembl REST alone (self-consistent, as your RM267 wording says), and four were
unknown because REST timed out. `variant_impact_agreement` is not attested on any successor; it is AlphaGenome's
separate command and scores rather than places. The scale is the underlying problem: the ClinVar VCF carries
2,645,243 distinct rsIDs against 1,172,660,304 records in the 0.8 snapshot, about 0.23%, so it cannot witness
Ensembl placement in general. Even in these clinically skewed modules it holds 22.5% (9/40) of the refused
subjects and 0 of the 6 real moves.

**What we did meanwhile.** Nothing published: the 12 stay refused on staging, and production (still on registry
0.27 and format 0.7) has not run the sweep. Accepting the six moves with `--accept-drift` would mint immutable
successors on the strength of 1000G alone, which is the question this item asks you about.

**Candidate fixes.** (a) A placement witness at dbSNP scale and independent of Ensembl: NCBI dbSNP's GRCh38 VCF
or its SPDI, converted to VCF with the reference, as a snapshot lane that `placement_agreement` reads. That is
the one source that asserts what an rsID is, not only that an event exists at a locus. (b) Until then, a
population call set (gnomAD sites, or 1000G as here) as a positional witness for indels: it settled all six.
(c) A reference-sequence lane, so `reference_allele` and the respelled/moved decision run offline; that alone
would have turned the 23 `undecided` into `respelled`. (d) The 0.8 snapshot's source VCF carries VEP's `SPDI`
in its CSQ fields, and none of the core table or its seven groups keeps it. It is Ensembl's own spelling, so it
normalises rather than witnesses, but it would make (a) a join. (e) A way for a release to declare that a
snapshot it pins moved, so a consumer's `needs_recompile` can say "re-derive" rather than nothing; whether that
belongs in `release_records` or beside it is your call. Not asked: any change to the quiet set. `moved` holding
was correct here.
