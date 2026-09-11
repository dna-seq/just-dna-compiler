# Drafting as a mechanism — what the seven providers taught, and what is still missing

Written after RM228 put all seven `*_draft.py` providers on one scaffold, at the maintainer's ask:
*what patterns emerge, and what more structural or model elements does drafting need to be a mature
mechanism rather than a patchwork of grassroots implementations of the same thing?*

It is deliberately written **after** the migration rather than before it. Four of the findings below
were invisible until the copies were put side by side, and two of them contradicted what this session
predicted, which is the argument for not having written this as a design document up front.

## The four patterns that emerged

**1. A copy drifts in the direction of its author's mental model, not randomly.** Four providers
restated `VariantRow`'s identity rule and each got it wrong *differently*: `clinvar_draft` stricter
(demanding `ref` and `alts`), `clinpgx_draft` narrower (rsID only), `mitomap_draft` wider (adding
`clin_sig`). Every one of those is a faithful description of **that provider's own source**. Nobody
misread the model; they each wrote down the union of two rules and only one of the two was the
model's. That is why the repair is a *split* rather than a shared predicate — a shared predicate
would have deleted three true statements about three snapshots.

**2. The correct-looking implementation is where the subtle bug lives.** Two providers derived their
rule instead of restating it, so "migrate everyone onto the derived one" was the obvious move. It was
wrong: `authoring_requirements`' `any_of` grammar cannot express *`ref`/`alts` require a position*, so
the derived implementation accepts `{"rsid": "rs1", "alts": "G"}` — a partial coordinate the model and
a compile both refuse. The four restatements were visibly suspicious and got read; the derivation
looked principled and did not. **A derivation is only as good as the oracle it derives from**, and an
oracle that answers a *simpler question* than the thing it stands in for is the dangerous kind.

**3. A justification narrower than its scope becomes a blind spot that reads as a decision.** Three
instances in one round. RM208: a roster's `exempt` set, where a guard walking the roster inherited its
exemptions. RM230: an exemption on a *class* argued from what one *method* promises. RM225: a comment
saying a vocabulary "is not enforced" that stayed true-sounding for two releases after the field
shipped. The shape is always the same — a reason written at one scope, applied at a wider one, and
indistinguishable afterwards from a considered choice. **Every exemption should state what the
exempted thing promises, not what one part of it does.**

**4. An import cycle is a diagnosis.** Deriving `DRAFT_PROJECTIONS` from the provider registry created
a cycle the moment the scaffold needed `stamp_draft_digest`. The cycle was not an obstacle to route
around: it was the fact that `draft_digest`, `stamp_draft_digest` and `drafted_unchanged` had been
drafting code living in `provenance.py`. That boundary was only holdable while the registry was a
hand-kept copy — the copy was what kept the modules from needing each other. **A duplicate is load
bearing in the dependency graph, and removing it is what reveals where the boundary actually is.**

## What drafting still lacks

Ordered by how much each would have prevented, not by effort.

**A. There is no `DraftProvider.covered` — every provider still hand-writes the predicate.** This is
the largest remaining hole. "Did this run contribute something?" is asked by all seven, the answer
gates the licence row, and each computes it from its own result shape: `result.report.outcomes` on one,
`result.reports[0].outcomes` on another, `any(r.added for r in reports)` on a third, and two rely on an
early return instead. RM222 was exactly this predicate written wrong once. It is not unified today
because the result types differ, which is the real gap: **the providers have no common result
protocol.** A `DraftResult` protocol exposing `outcomes` would make `covered` a scaffold property and
close the shape RM222 found, permanently.

**B. `PartialRow` construction is still per-provider.** Every drafter builds `PartialRow(model=…,
cells=…, stubbed=…, match_on=…)` itself, and `stubbed` is computed differently in each. The registry
already holds `match_on` and the table; it does not hold the stub set, so `_STUBBED` is still a private
constant in six modules. This is the same shape as `_MATCH_ON` before RM228 and should go the same way.

**C. Nothing derives which `SourceTerms` a provider records.** `DRAFT_PROVIDERS` names the table and
the kind, and then each drafter imports its own `*_TERMS` constant and passes it. The registry could
hold it, and then `record_draft_provenance` would not need `sources` at all for the single-source case.
The multi-source case (`civic_draft` plus the ClinGen Allele Registry) is the reason it was left as a
parameter, and a `secondary_sources` field would cover it.

**D. The `covered` / `drafted` distinction is undocumented outside one docstring.** They are different
questions — *did this run establish the source* versus *did this run add a row* — and the second gates
the stale-label withdrawal while the first gates the licence row. Two providers got this pair right by
copying a third. It belongs in the model, as two properties on a result protocol, not in prose.

**E. There is no dry-run contract.** Every provider takes `dry_run` and each decides independently
what it suppresses. `test_drafting_scaffold.py` cannot check it, because there is nothing declarative
to check against. The audit noted "no `--dry-run` path writes (verified empirically for civic)" — an
empirical check on one provider is what a contract exists to replace.

**F. A provider's *withheld* vocabulary is still a per-module literal.** `mitomap_draft` folds an
unknown member into a member; `civic_draft` keys its counters on strings that only its own warning
formatter reads. A lane-local vocabulary carrying the lane's prefix is already the house rule
(`@a-lane-local-vocabulary-may-not-shadow-a-schema-one`); drafting does not follow it yet.

## The rule this round would write for the next one

**When two implementations of one thing disagree, do not pick the better-looking one — find the
question each is answering.** Four of the seven disagreements here were not errors at all; they were
two different true statements compressed into one expression. The scaffold's value is not that it
removed duplication, it is that it made the two statements separately expressible, so the next reader
can tell a source constraint from a misread of the model without reading three lines further down.
