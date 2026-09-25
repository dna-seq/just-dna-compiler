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
round exists to produce; they are counted in RM149's dated addenda rather than smoothed over here.

**No `# DRIFT:` stands open today.** The first pass raised one — COMPILER.md's validate-by-redundancy
table and its own mishap matrix disagreeing about whether `strict` builds on an rsid↔coordinate
contradiction — and left it marked deliberately, because a round that silently repairs what it finds
cannot be audited. It was repaired on 2026-09-18 once it had been read. The marker is for the interval
between finding and deciding, and a scenario should not carry one for long.

## Why it is at the repository root and not in `docs/`

RM149's third open question: a `features/` tree under `docs/` publishes to the site, and a published
surface answers to Principle 3 — additive within a major, every clause a commitment. That is a much
larger thing to take on than an internal corpus, and it is not a decision a drafting round gets to
make. The root keeps it internal and keeps the question open. `mkdocs.yml`'s `nav`/`not_in_nav`
partition covers `docs/` only, so nothing here needs a nav entry; the repository root is curated, and
this directory is the whole of the addition.

## What is in scope, and what deliberately is not

In, because this is where ambiguity has actually cost something (S79, S80, S83):

- **Every member of `vocab.VALID_WARNING_CODES`** — one `Scenario` per **emitting tier** (see the
  `@code:` convention below; nine members are emitted by two tiers, which since RM244 speak through one
  builder and differ only in the clauses each can stand behind), at its emission site, saying which mode
  it fires in, whether it warns or refuses, and whether an author can clear it.
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
  # source: compiler/src/just_dna_compiler/compiler/variant_checks.py:199
  @code:contig_ploidy_mismatch @actionable
  Scenario: a two-allele genotype on a contig that is not diploid there
    Given a module whose variants.csv states genotype "A/G" at a chrom=MT locus
    When the module is compiled in best_effort mode
    Then a warning fires whose text contains "is not diploid here"
    And the same warning fires identically under strict
```

Four conventions, each of which the guard enforces:

- **`# source:` names the file and `# anchor:` names the symbol, and both are checked (RM245).** The
  path must exist, the symbol must be a `def` or `class` in it — resolved through `ast`, never grepped,
  since the name appears in its own docstring and in every caller — and for a `@code:` scenario the
  emission site must be **inside that symbol's line range**. This is what stops a `Then` being
  paraphrased out of a documentation paragraph rather than read off the string the code builds.

  **An anchored scenario carries no line number at all**, which is the point rather than a convenience:
  a line is a pointer that rots the next time something above it is edited, and 53 of these anchors had
  silently drifted out of the function they name during one ordinary session of code edits. A symbol
  moves with the thing it names. `# source: <path>:<line>` still exists for the three sites no symbol
  names — two module-level vocabulary constants for `@reserved` members, and a module docstring — and
  there the line is the only pointer there is.

  Carrying both an anchor and a line is refused: the anchor is the pointer, and the line beside it is
  the half that rots.
- **`# text:` names a SECOND module the sentence may come from, searched beside the emission site
  rather than instead of it.** Two shapes need it. A message built by one module and wrapped in a
  `CodedWarning` by another — `layout.deprecation_notice` writes the sentence and `_locate_sidecar`
  gives it its code — which is exactly the boundary where a code goes missing
  (`@finding-loses-its-code-at-a-boundary`). And, since RM244, a sentence **assembled from both**:
  `resolution_findings` owns the skeleton and each tier passes its own clauses as string literals, so
  one scenario legitimately quotes from two files. The union is the point — a check that replaced the
  emission site with the text module would report the caller's own words as missing.
- **`@code:<member>`** names the warning code, and **every tier that emits it owes a scenario there**.
  Not one scenario per member: nine resolution codes are emitted by the compiler's `resolution.py` *and*
  by the enricher's `resolver.py`. Seven of the nine pairs used to be a *different sentence* under the
  same code, which is what a per-member equality could not see; since RM244 the words come from one
  builder in `just_dna_compiler.resolution_findings` and the tiers differ only in the clauses each can
  stand behind. The guard still keys on `(code, tier)` — the tier read off the `# source:` path, never
  off the feature directory, since a scenario is filed with its subject rather than with its emitter —
  because two tiers emitting one code is the thing a reader needs to find, whoever owns the words.
  Beside it,
  **`@carried`** or **`@actionable`** — the two are `vocab.CARRIED_WARNING_CODES` and
  `vocab.ACTIONABLE_WARNING_CODES`, and tagging the wrong one fails the guard rather than misleading a
  reader. Carried means *no edit to the spec directory can clear this*.
- **`@check:<member>`** and **`@skip:<member>`** do the same job for the verification vocabulary, and
  their `# source:` is aligned the same way — against the `ran`/`skipped` call, or for a reason that
  travels as a variable, against the line that decides it. **`@reserved`** marks a check member
  deliberately emitted by nothing, and exempts it from that alignment.

  **A structural scenario carries no registry tag, so nothing checks what its anchor CONTAINS** — only
  that the symbol exists. That is still most of the corpus, and it is still the weaker half: a scenario
  anchored on the wrong function is a claim nothing can test. What it no longer is, since RM245, is a
  pointer that decays on its own — the symbol either exists or the guard says so, where a line number
  quietly meant something else.
- **Every quoted phrase on a `Then`/`And`/`But` step is a real substring of the message**, because a
  warning's text is an API (`@warning-text-is-api`) and a consumer greps it. Where a message
  interpolates, quote the literal part around the hole, never a reconstruction of the whole sentence —
  and never an interpolated *value*, which no literal holds. `Given`/`When` are exempt: those name an
  input, which has no reason to appear in the module's own strings. (The check was keyed on a verb
  before the quote at first and covered 46 of 162 phrases; keyed on the step keyword it covers all of
  them, which is how the three paraphrases in the first draft were found.)

**`@ladder` beside a `@code:` is checked too**, and it is the fourth registry here. A check whose
severity is the compile mode builds a `LadderFinding` — what `best_effort` emits and, where the two
differ, the separate thing `strict` says instead — so the codes are walkable and the tag is asserted
equal to them. Since RM246 that is **one** mechanism and the tag covers all of it; before it, the ladder
was written in three shapes and this equality could only see the four codes in one of them.

The attribution is **per construction, not per function**: a code is a member when its `CodedWarning`
sits inside the `LadderFinding(…)` call. Crediting the enclosing function was right while the ladder was
a whole-check property and became wrong as soon as one function held both kinds — `resolve_from_table`
has two ladder members and nine plain warnings, and the function-scoped walk reported all eleven.

Tags that carry no registry, for reading rather than for the guard: `@strict_only`, `@both_modes`,
`@refusal`, `@parity`, `@tri_state`.

## Adding to it

A new warning code without a scenario fails `test_feature_corpus.py`, which is the point: the corpus
is a registry over a set that grows, and this project's most-repeated defect is a hand-kept list over
exactly that (`@registry-completeness`). Put the scenario in the file for the tier that emits it, name
the emission site, and quote the phrase rather than describing it.
