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

## S147 — a replication at p < 0.05 has no `stat_significance` level of its own (wish, from longevity-loci)

Relayed by longevity-loci's liaison for its lead, while building the export of its curated longevity rows into a
0.8.4 spec directory (`studies.csv`).

**What we have.** Many longevity loci are discovered genome-wide in one study and replicated in another by a
look-up of the discovery's lead SNP at nominal significance: P 0.002 in CHARGE-EU's 90+ cases (Joshi 2017,
Table 2) for the LPA locus. Our
curation rule (longevity-loci's D11, 2026-11-10) counts such a look-up as an independent replication, the "p <
0.05" of the longevitymap v2 requirements' tier A, and keeps it apart from a look-up that failed.

**What happens on 0.8.4.** `StudyRow.stat_significance` is closed at `significant|suggestive|not_significant|
unknown`. A replication at P 0.002 can only be written `not_significant`, the same value as a look-up at P 0.6,
or `unknown`, which it is not. A reader of `studies.csv` sorting the evidence for a variant by
`stat_significance` sees the replication as a null. `p_value_num` keeps the number, so the information survives,
but the one column meant to carry the verdict says the opposite of what the study reported.

**Meanwhile.** Our export writes `not_significant`, keeps `p_value` exactly, and says "nominal replication
look-up (p < 0.05)" in `statistical_test`.

**Candidate.** An added level, `nominal` (p < 0.05 and above the suggestive line), additive to the vocabulary, so
a 0.8 reader that does not know it treats it as any unknown value would. Against it: if the format keeps
`stat_significance` derivable from `p_value_num` alone, a fifth level adds nothing a reader cannot compute, and
the gap is only in the description, which could then say that `not_significant` covers 1e-5 < p < 0.05 and that
`p_value_num` is the field to read. Either answer settles it for us; what we cannot do is leave a row reading
"not significant" for a study whose authors call it a replication.

**Status — filed as [RM434](ROADMAP.md#rm434--stat_significance-states-no-threshold-so-a-replication-that-passed-its-own-test-reads-as-a-null): a patch (the description) or a minor (a fifth member); the pm sizes.** Confirmed,
and the gap is wider than one level. No threshold behind any `stat_significance` level is written down: not in the
field's description, not in `vocab.py`, and in none of our docs. "`not_significant` covers 1e-5 < p < 0.05" is a
reading of `suggestive` in its GWAS sense, and the format never stated it. So one fix is a patch: say the level is
the verdict at the threshold of the study's **own** test. A pre-specified look-up of one discovery SNP in an
independent cohort has no genome-wide burden, so passing it is `significant`, and `p_value_num` is the number a
reader thresholds on. Your `nominal` stays in the entry for the pm. Your own argument against it carries weight
there, and a fifth member would also bring a threshold convention into the verdict column. Until the pm decides,
`significant` with your `statistical_test` text is a defensible way to write the row, and better than
`not_significant`.

<!-- triaged: RM434 filed (patch description, or a minor member; pm sizes) · sha 6ac6641e124b -->

## S148 — a study that states its allele and direction but no effect size has nowhere to put the direction (wish, from longevity-loci)

Relayed by longevity-loci's liaison for its lead, from the same export as S147.

**What we have.** A replication table often prints the effect allele, the direction and the P, and no effect
size: CHARGE-EU's 90+ look-up for LPA (Joshi 2017, Table 2), and meta-analyses that print a pooled P and the
direction of each arm without a pooled estimate. Our rule (longevity-loci's D13, the person's answer, 2026-11-10)
lets such a study support a tier A or B row on its `effect_allele`, its direction and its P.

**What happens on 0.8.4.** `StudyRow` has `effect_allele` but no direction: the direction is carried by the sign
of `effect_size` relative to `effect_measure`, and with no size there is no sign. The variant row's `direction`
is the module's call over all studies, not this study's finding. So the study's own direction goes into
`conclusion`, free text, where nothing checks it against `effect_allele` or against the variant's `direction`.

**Meanwhile.** Our export writes the direction into the study's `conclusion` cell, in words.

**Candidate.** An optional study-level direction (`effect_direction` or `direction`, on the variant row's
vocabulary), meaningful only with `effect_allele`, and refused, or warned, when `effect_size` is given and its sign
disagrees. Against it: two fields that can contradict each other; a warning on disagreement is what makes it
safe. A narrower alternative is to let `effect_size` carry a sign alone, which the format does not have a way to
state without inventing a magnitude, so we would not ask for that.

**Status — filed as [RM435](ROADMAP.md#rm435--a-study-row-has-no-direction-of-its-own-so-a-study-that-prints-its-allele-and-direction-but-no-size-puts-the-direction-in-free-text): a minor; the pm sizes.** Confirmed: a study row has no direction except the sign
of its `effect_size`. The schema already has this field, one table over. `GwasEffectRow.effect_direction` holds
`increase|decrease`, relative to the row's effect allele, and its description says it is **not** the clinical
direction, so the two axes stay apart (our Principle 5). RM435 proposes that field on `StudyRow`: same name, same
vocabulary. It records which way the allele moves what the study measured. The variant row's
`protective|risk` stays the module's call over all studies. A warning when a stated `effect_size` disagrees is in
the ask, as you proposed: a sign test for `beta`, and a test against 1 for a ratio. A new authored column is a
minor, so it waits for one. `conclusion` in words is the right place meanwhile. If you write it as
"increase"/"decrease" relative to `effect_allele`, a later move into the column is mechanical.

<!-- triaged: RM435 filed (minor, effect_direction as on GwasEffectRow) · sha c68a032251a3 -->
