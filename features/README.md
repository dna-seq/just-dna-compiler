# `features/` — the scenario corpus

One structured statement of an expectation, where today there are three: a docstring, a test name, and
a paragraph in a tier reference. This is [RM149](../docs/ROADMAP_0_8.md#rm149--expected-behaviour-lives-in-prose-and-the-prose-is-where-two-readers-split),
drafted on **2026-09-13** and **not reviewed**. Nothing here is a contract yet.

## The direction is code → Gherkin, and that decides everything else

RM149 names two opposite projects with the same output. This corpus is the first: **the feature files
describe what the code does**, derived from the emission site and the maintained reference beside it.
They are not a specification the code is generated from, and there are **no step definitions** — no
`behave`, no `pytest-bdd`, no new dependency in any tier. The `pytest` suite stays the executable
statement of behaviour; this is the readable one, and the guard in
`schema/tests/test_feature_corpus.py` is what keeps the two from drifting apart silently.

So when a scenario and the code disagree, **the code is right and the scenario is the defect** — with
one exception, marked `# DRIFT:`, where the disagreement is between two things that are *both* ours
(a docstring and a reference page, a reference page and the emission site). Those are the findings this
round exists to produce; they are counted in RM149's dated addendum rather than smoothed over here.

## Why it is at the repository root and not in `docs/`

RM149's third open question: a `features/` tree under `docs/` publishes to the site, and a published
surface answers to Principle 3 — additive within a major, every clause a commitment. That is a much
larger thing to take on than an internal corpus, and it is not a decision a drafting round gets to
make. The root keeps it internal and keeps the question open. `mkdocs.yml`'s `nav`/`not_in_nav`
partition covers `docs/` only, so nothing here needs a nav entry; the repository root is curated, and
this directory is the whole of the addition.

## What is in scope, and what deliberately is not

In, because this is where ambiguity has actually cost something (S79, S80, S83):

- **Every member of `vocab.VALID_WARNING_CODES`** — one `Scenario` each, at its emission site, saying
  which mode it fires in, whether it warns or refuses, and whether an author can clear it.
- **The mode ladder and the validate/compile parity rule** — which checks escalate under `strict`,
  which refuse in both modes, and which refusals are `strict`-only.
- **Every member of `vocab.VALID_VERIFICATION_CHECKS`** — with its three outcomes, and its skip
  reasons from `vocab.VALID_VERIFICATION_SKIPS`.
- **The tri-state house algebra** — anything that answers a question gets three `Then`s. A check only
  two can be written for is a finding, not a gap to fill quietly.

Out:

- **Round-trip and idempotency fixed points.** Principle 7 is pinned by assertion (`compile → reverse
  → compile`), and RM149 says plainly that prose adds nothing there. A scenario restating an equality a
  test already computes is the second dialect with none of the benefit.
- **Anything about authoring a module.** That reader is served by `just-module-creator`, and this
  repository carries no authoring document on purpose.

## Reading a scenario

```gherkin
  # source: compiler/src/just_dna_compiler/compiler.py:1208
  @code:contig_ploidy_mismatch @actionable
  Scenario: a two-allele genotype on a contig that is not diploid there
    Given a module whose variants.csv states genotype "A/G" at a chrom=MT locus
    When the module is compiled in best_effort mode
    Then a warning fires whose text contains "is not diploid here"
    And the same warning fires identically under strict
```

Four conventions, each of which the guard enforces:

- **`# source:` is mandatory and is checked.** The file must exist, the line must be inside it, and for
  a `@code:` scenario the emission site must actually name that code. This is what stops a `Then` being
  paraphrased out of a documentation paragraph rather than read off the string the code builds.
- **`# text:` names where the sentence lives, when that is not where the code is named.** A message
  built by one module and wrapped in a `CodedWarning` by another is a real shape here —
  `layout.deprecation_notice` writes the sentence and `_locate_sidecar` gives it its code — and it is
  exactly the boundary where a code goes missing (`@finding-loses-its-code-at-a-boundary`). So the
  scenario names both, and the guard checks the code against the emission site and the phrase against
  the module that actually holds the words.
- **`@code:<member>`** names the warning code, and exactly one scenario claims each member. Beside it,
  **`@carried`** or **`@actionable`** — the two are `vocab.CARRIED_WARNING_CODES` and
  `vocab.ACTIONABLE_WARNING_CODES`, and tagging the wrong one fails the guard rather than misleading a
  reader. Carried means *no edit to the spec directory can clear this*.
- **`@check:<member>`** and **`@skip:<member>`** do the same job for the verification vocabulary, and
  their `# source:` is aligned the same way — against the `ran`/`skipped` call, or for a reason that
  travels as a variable, against the line that decides it. **`@reserved`** marks a check member
  deliberately emitted by nothing, and exempts it from that alignment.

  **A structural scenario carries no registry tag and gets no alignment**, only *the line exists*. That
  is most of the corpus and it is the known weak spot: a `# source:` at a docstring or a branch rots
  when anything above it is edited, and nothing will say so.
- **Every quoted phrase on a `Then`/`And`/`But` step is a real substring of the message**, because a
  warning's text is an API (`@warning-text-is-api`) and a consumer greps it. Where a message
  interpolates, quote the literal part around the hole, never a reconstruction of the whole sentence —
  and never an interpolated *value*, which no literal holds. `Given`/`When` are exempt: those name an
  input, which has no reason to appear in the module's own strings. (The check was keyed on a verb
  before the quote at first and covered 46 of 162 phrases; keyed on the step keyword it covers all of
  them, which is how the three paraphrases in the first draft were found.)

Tags that carry no registry, for reading rather than for the guard: `@strict_only`, `@both_modes`,
`@ladder`, `@refusal`, `@parity`, `@tri_state`.

## Adding to it

A new warning code without a scenario fails `test_feature_corpus.py`, which is the point: the corpus
is a registry over a set that grows, and this project's most-repeated defect is a hand-kept list over
exactly that (`@registry-completeness`). Put the scenario in the file for the tier that emits it, name
the emission site, and quote the phrase rather than describing it.
