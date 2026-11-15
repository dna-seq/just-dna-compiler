# Dreams for just-dna-format (2026-10-19)

A one-time "dream": four model families were each asked, separately and on the same brief, what this
repository should become if every constraint (its rules, its design, cost) were ignored. Each gave
6 to 10 ideas and one bet. This is inspiration, not a plan: nothing here is decided, scheduled or
endorsed.

Two copies were read. Opus read a `git archive` copy of local HEAD (21a5fa3) with genome data and
genome-derived files removed. The outside three read a copy of origin's trunk (b234b0c, five commits
behind: RM314 to RM316 and RM320 are not in it), chosen by file type: code, Markdown, JSON, YAML and
TOML kept; data, logs, notebooks, images and unknown types left out, which also dropped the
reference examples' CSVs and the 13 Gherkin `.feature` files. They ran through Cursor's CLI at medium
effort, read-only (`--mode ask`).

| Model | Ideas | Exit | Time |
|---|---|---|---|
| claude-opus-5-5 (this compiler's own leaf, written before reading the others) | 8 | n/a | n/a |
| gpt-5.6-sol-medium | 8 | 0 | n/a |
| grok-4.7-medium | 8 | 0 | n/a |
| gemini-4-argon-medium | 7 | 0 | n/a |

## Convergence

Themes, with each model's rank for the idea (1 = its most transformative). A dash: not proposed.

| Theme | Opus | Sol | Grok | Argon | Count |
|---|---|---|---|---|---|
| **A. The verdict ships with the module**: the join or an evaluator lives with the format, so two consumers cannot give two answers | 2 (client-side join), 1 (the spec it needs) | 5 (safe executable rules), 2 (one local runtime) | 1 (The Join) | 1 (Kleene VM) | 4 |
| **B. Living modules**: a source changes, a reviewable next version is proposed | 8 | 3 | 3 | 4 (delta streams) | 4 |
| **C. Claims as the unit, with history**: claim-level identity, lineage, a ledger | 5 (transparency log) | 1 (Git for claims) | 3 (validity intervals) | - | 3 |
| **D. Interop out**: GA4GH VA/VRS, Phenopackets, FHIR | 6 | 6 | 7 | - | 3 |
| **E. Cross-domain predicates**: one statement over PGx, PRS, meds, methylation | - | 5 | 2 (decision sentence) | 2 (circuits DAG) | 3 |
| **F. New grains**: multimodal, long-read, family, somatic, pangenome | - | 7 | 8 | 3 (graph walks) | 3 |
| **G. Privacy by construction**: the genome never leaves the device | 2 | 2 | - | 6 (blind evaluation) | 3 |
| **H. Disagreement is data**: competing claims kept, no winner picked | - | 4 | 5 | - | 2 |
| **I. Ground truth**: measure answers against people, not bytes | 4 (truth-set bench) | 8 (outcome network) | - | - | 2 |
| **J. The agent is the author**: rebuild authoring around the seat | 7 (a database, not CSVs) | - | 4 (seat owns a genome-wide module) | - | 2 |
| **K. The caveat binds to the sentence**: ancestry, callability, context decide what renders | 3 (findings schema) | - | 6 (context or silence) | - | 2 |

**All four met on** A and B. A is the strongest: each named "not a runtime" as the constraint to
break, and three gave the same reason in nearly the same words. Grok: the correctness "dies at 'the
consumer joins'"; Argon: `artifact.digest` "guarantees nothing about the clinical answer" if two
consumers join differently; Opus: "the contract is whatever the code does". The roadmap itself parks
the output shape as RM7, "a consumer contract". B rests on one line all four found:
`MODULE_LIFECYCLE.md`'s "No module in this repository has ever had a second version".

**Three met on** C (Opus, Sol, Grok: the module is a snapshot of claims that should each carry their
own history), D (Opus, Sol, Grok; Opus and Grok both read `GKS_SURVEY.md`'s "our core grain has no
GKS counterpart" as an export opportunity, not a gap), E (Sol, Grok, Argon; Grok cites the
constitution's sanctioned non-Turing-complete predicate, Argon names warfarin, RM28's case), F (Sol,
Grok, Argon, from three directions: observation types, read technology, coordinate model) and G
(Opus, Sol, Argon).

**Two met on** H (Sol, Grok; both start from ClinVar disagreement and sources that contradict
themselves), I (Opus technical truth, Sol clinical outcomes), J (Opus, Grok) and K (Opus, Grok).

## Only one saw

- **Opus, a normative spec with a second implementation (1).** Write the artifact's contract apart
  from the pydantic models, grow a conformance corpus from the Gherkin files and reference examples,
  and build a Rust/WASM reader. The repo's own RM149 ("expected behaviour lives in prose, and the
  prose is where two readers split") is the case for it; the habit it breaks is
  `@dogfood-not-validation`, right for a tool and wrong for a format.
- **Opus, a truth-set bench (4).** Run each module against GIAB, 1000 Genomes and GeT-RM / PharmCAT
  consensus calls, and carry the result beside the digest. Integrity proves the bytes; nothing proves
  the answer about a person.
- **Argon, formal verification (5).** Translate a module's tables into SMT and ask a solver whether
  any genotype matches two rows with contradictory `direction`, or falls between star alleles, with
  the counterexample VCF as output. It generalises the hand-written checks (`@jointly-satisfiable`,
  bin tiling) into one engine.
- **Argon, blind evaluation (6).** Compile a module to a PIR or FHE lookup so a proprietary module and
  a private genome meet without either side revealing itself. The only idea aimed at a commercial
  market.
- **Grok, the seat owns the genome-wide module (4).** One "best current claim" module per domain,
  maintained by a seat that may rewrite a cell, every rewrite carrying seat, accession and quote, and
  contested cells shipped contested.
- **Sol, a Personal Genome Operating System (2).** The repositories become internal components behind
  one local-first product: import a genome once, install knowledge packs.

## The bets

- **Opus:** the normative spec with a second, WASM reader: the contract the other ideas need.
- **Sol:** Git for Genomic Claims: modules, reports and registries as views over a claim graph.
- **Grok:** The Join: `join(genome, modules, context) → claim card`, in this repository.
- **Argon:** the Kleene Virtual Machine: a small three-valued evaluator inside `just-dna-format`.

Grok and Argon made the same bet in different dress: Grok as a function every repo calls, Argon as an
evaluation plan compiled into the artifact. Opus's bet is the precondition for theirs (a join needs a
contract that exists apart from one Python package) and its idea 2 is their bet run in a browser.
Sol is alone: it bets on the data model, not on execution.

## Divergence

**Diagnosis.** Opus: the format *is* one implementation, and its contract lives in prose and
validators. Sol: knowledge is living and disputed, and it is stored as versioned files. Grok: a
year of pinned correctness never reaches a person, because the answer is computed in whichever app
last reimplemented the match. Argon: purity pushes the hardest problems (phasing, bin tie-breaks,
Kleene propagation) downstream, and linear coordinates are the wrong substrate for half the gotchas.

**The bets** split two ways: ship the verdict (Grok, Argon, and Opus through its precondition) or
change what a module is (Sol). Grok's and Argon's need only this repository; Opus's needs a second
language; Sol's needs a migration of every module.

**Style of thought.** Grok was the most grounded and the most quotable: nearly every idea cites a
roadmap item or a constitution line (RM7's four states, RM296, RM304, variation-normalizer), in short
hard sentences ("A digest nobody supersedes is a trophy."). Argon was the boldest and the most
technical: formal vocabulary (Kleene algebra, SMT-LIB2, PIR and FHE), many identifiers (RM28, RM181,
RM317 to RM319, the `AGENT_NOTES.md` tags), the furthest leaps, and a few loose citations. Sol was
the most abstract and architectural, with the fewest file references and the most attention to
governance and consent. Opus sat between: anchored on the roadmap's own sentences, the most
standards-minded (GA4GH, GIAB, Certificate Transparency), and the most conservative about breaking
the charter.

## Facts that did not hold

Checked against the copy each model read; an idea itself is not judged.

- **Opus** says it "found no mention of GIAB or a truth set anywhere in the docs". GIAB appears once,
  in `docs/probes/CLAWBIO_SURVEY.md` (another tool's demo), and HG002 is a PacBio sample in RM317 and
  RM318. No truth-set bench exists, so the point holds; "anywhere" does not.
- **Grok** says every module "has been compiled once". `MODULE_LIFECYCLE.md` says compilation is
  "exercised repeatedly" on all sixteen examples; what has never run is a second *version*.
- **Grok** calls enricher co-authoring "the refused" design. It is parked, not refused: "Not in 0.x"
  (`FAQ.md`), under ROADMAP § Parked in 0.5.
- **Grok** sums up the 1.0 plan as "more columns, cleaner requiredness, and a PRS that finally bins".
  `ROADMAP_1_0.md` holds RM52 (upgrade procedure), RM15 (multi-build identity), RM55 (a column
  *removal*), RM81, RM73 and cleanups; the PRS bin table (RM296) is in `ROADMAP.md`, release
  undecided.
- **Grok** contrasts a dispute with "a warning string capped in a manifest". The compiler's VRS
  warnings say "Not a cap and not suppression"; the cap that exists is three citations per variant
  in a drafted `studies.csv`, with the dropped count reported.
- **Argon** lists "CYP2D6 hybrid star-alleles" among `AGENT_NOTES.md`'s gotchas; the file has no
  hybrid entry (the `cyp2d6_structural` example exists). Its other gotchas hold (PAR1/PAR2,
  restamping, ±1 shifts).
- **Argon** quotes the constitution as "A consumer must be able to read a module as plain Parquet".
  The non-goal reads "without executing anything the module ships"; "Plain parquet" is
  `CONSUMING.md`. The substance holds.
- **Argon**'s idea 7 (`mechanistic_priors.csv`) says the format is "curated-catalogue-only". RM23,
  "Computational predictor scores as a table" (SpliceAI, CADD, long-form, licensing "solved"), is
  already on the 0.8 roadmap and the AlphaGenome atlas lane exists; the new part is the calibrated
  likelihood-ratio curves.
- **Argon** says the marketplace "assumes all modules are public". Not checkable from this
  repository; the manifest carries a `licenses` union, and local HEAD (not the trunk copy) adds a
  non-commercial compile for PubMind's table (RM320).
- Held, for the record: "no module has ever had a second version" and "the artifact records no
  predecessor" (Sol, Grok, Argon; `MODULE_LIFECYCLE.md`); "nobody schedules it for you", which Sol
  paraphrases as "nothing schedules re-derivation"; the constitution's bounded predicate and "None
  of these are needed yet" (Grok); RM7's card states `called`, `ambiguous`, `not_assessable`,
  `no_match` and `phase_would_decide`, from S115 (Grok); RM296, RM304, VRS 2.1, variation-normalizer
  refusing names (Grok); RM28 and warfarin, RM181, RM317 to RM319, `@start-1based`,
  `@build-in-manifest-only`, `@jointly-satisfiable`, `requires_callable` (Argon); at HEAD, 69 open
  roadmap items (72 at the trunk), about 82k lines of package Python, 16 reference examples, RM149,
  RM283's fourteen-month-old snapshot, S112, `faf95` on its owning group, "nobody has asked for the
  cascade", "no second implementation of `apply_overrides`" (Opus).
