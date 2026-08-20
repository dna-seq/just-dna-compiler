# Roadmap history — the items that shipped

Split out of [ROADMAP.md](ROADMAP.md), which is **forward-only**: it now carries active work and
nothing else. This file keeps the *rationale* of every `RMn` that shipped from the 0.6 line onward —
the earlier ones are in the archive named below — because a lot of it is reasoning worth not
re-deriving, including one entry that corrects an argument it originally made.

- **[CHANGELOG.md](CHANGELOG.md)** is the release record: what changed, newest first, shared across
  the ecosystem repos. This file is the roadmap-item view of the same events.
- **[RM_TOC.md](RM_TOC.md)** is the complete index of every `RMn`, active and shipped.
- **[COMPILER.md](COMPILER.md)** carries the per-feature coverage table.

`RM1`, `RM2`, `RM3`, `RM8`, `RM9`, `RM18` and `RM19` also shipped, but their entries live in
[USE_CASES.md § Roadmap items surfaced](USE_CASES.md#roadmap-items-surfaced) — where they were
derived — and were never duplicated here.

**The 0.5 line and everything before it moved to
[ROADMAP_HISTORY_PRE_0_6.md](history/ROADMAP_HISTORY_PRE_0_6.md)** on 2026-08-17 — the release narratives
through 0.5.0, and every `RMn` that shipped before 0.6. This file starts at the 0.6 design round.
[RM_TOC.md](RM_TOC.md) indexes both halves plus the open roadmap, so it is where to look an item up.



# The RM10/RM11 session — a downstream MCP surface restated three schema facts it could not generate

Four items from `just-module-creator` on 2026-08-20, filed together because they came out of one work
item: their MCP tools had three answers that **restated** a schema fact instead of generating it, and
they went looking for the public symbol to generate each from. Two of the three had none — which is the
report, and it is the useful shape of it: a consumer who wants to generate rather than restate, blocked
by a private name, will hand-keep the same lines every other consumer hand-keeps and will be the one who
misses the next table. All four are additive or documentation; nothing removed, nothing retyped.

## RM116 — `content_signature` returned only its hash, so anything finer restated the fold

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S53](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**The reporter is specifying the tool MODULE_LIFECYCLE §7 says nothing owns** — *what moved between two
versions of this module* — as a three-level ladder: one signature for whether the content moved,
per-table for where, per-row for what. Levels two and three need the rows `content_signature` hashes,
and it returned the digest alone, so the mapping had to be rebuilt outside against two private things.

**Both halves reproduced before the fix, on `reference_examples/hfe_hemochromatosis`.** Renaming
`sources.csv` to `licensing.csv` and then editing a `notice` cell in it both left `content_signature`
at `sha256:44ad4449…` — the reporter's own measured digest, to the character. And the fold: writing one
`curator` value on every variant row in one copy and the identical value under `defaults:` in another,
`compiler.content_signature` agreed across the pair (correct — RM37) while `integrity.content_signature`
over raw `load_csv_rows` output disagreed, reproducing their `sha256:0b8dd27c…` for the yaml copy.

**The roster half was a documentation defect and the fold half a correctness trap**, which is why the
two land differently. A caller *can* derive the roster publicly — `draft.DRAFTABLE` minus
`layout.SIDECAR_SPELLINGS` — but as the reporter says, that equality is a coincidence two files
maintain rather than a contract, and it breaks in the direction that hashes an extra table. The fold has
no public route at all, and its third line (`None if effective == model_default else effective`) is the
one whose omission produces a signature that *looks* fine.

**Shipped their candidate fix, `compiler.spec_tables(spec_dir) -> (tables, declared_build)`**, with
`content_signature` becoming `_content_signature(*spec_tables(spec_dir))` and no logic moving. Their
rejected alternative is rejected here for their reason: exporting `_TABLE_KINDS` and
`_resolve_spec_defaults` separately hands out three pieces that must be assembled in one order — load
with the declared build injected, fold, then hash — and one function returning the finished mapping
cannot be assembled wrongly. The `ValueError`-on-invalid-CSV contract carries over because one function
is now the other plus a hash, and a test pins that rather than trusting it.

**The documentation half shipped too, since they asked for it either way.** COMPILER.md's public-surface
entry now names which CSVs feed the hash, says the licensing table is outside it and why, and states the
fold with the measured consequence of omitting it.

**Guards.** Four in `compiler/tests/test_content_signature.py`, using the RM37 fixtures that already
model the measured pair: the digest rebuilt from `spec_tables` output over three specs, the fold
**demonstrated** rather than asserted (the raw build is shown to disagree in the same test that shows the
folded one does not), the licence table shown outside the roster in both directions including the
notice-cell edit, and the `ValueError` contract over both functions. 2813 → 2817.

## RM119 — a citation sidecar could contradict its own studies.csv, and the manifest turned it into a confident zero

✅ **Shipped in `just-dna-compiler` + `just-dna-format` on 2026-08-20**, motivating case
[S56](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**Two separable halves, both reproduced against our own tree.**

**The staleness half.** `aggression_anger/literature.csv` records `quotes_authored=0` on all three
rows while its `studies.csv` carries 69 quotes — 65 of them citing pmid 29500382, which is the row
reading zero. All four published modules are in that state, 3,668 quotes and not one counted. The
mechanism is ordinary and is nobody's bug: the literature pass ran while `provenance_quote` was still
empty, wrote what was true then, and the sidecar is merge-not-clobber so every later run keeps the old
row. The module compiles green with a sidecar contradicting the table beside it in the same directory.

**Why the compiler owes this.** Both files are loaded at the same moment and joined on `pmid`, and the
count is arithmetic over rows already in memory. `LITERATURE_FACT_FIELDS`' own comment gives, as the
reason `quotes_authored` is outside the fact hash, that it *"is derivable from `studies.csv`"* — which
is precisely the argument for recomputing it at compile rather than trusting the stored copy. Shipped
as `_check_quote_counter_is_current`, a warning naming both numbers per citation, aggregated to one
line. It reads both citation sites through `binning_citations` — walking `bin_rows` directly reaches
`DiplotypeRow`, which has no `pmid` column, and a suite failure caught that before it shipped.

**The manifest half, and it is the more interesting one.** `_literature_block`'s docstring is right and
its per-row guard works: `quotes_found` sums only non-null rows, because folding a null into zero would
report an unchecked quote as a missing one — *"the single most misleading thing this block could say"*.
What it cannot express is the total over rows that are **all** null: `sum(...)` over an empty selection
is `0`, `Literature.quotes_found` is `int` with `default=0`, and the exact sentence the docstring warns
against is what the block ends up saying one aggregation later. A published manifest read
`quotes_authored: 0, quotes_found: 0` for a module with 69 authored quotes and no fulltext ever
retrieved — indistinguishable from one where every quote was checked and missed.

**Shipped `Literature.quotes_unchecked`** rather than making the pair nullable, which was the
reporter's own preferred option and the right one: a reader needs three states — found, missed, never
asked — and `int | None` collapses the last two back into "no number". Additive, out of
`artifact.digest` like the rest of the block. The reporter's rejected candidate (treat `0` as `null`
when no `quote_source` is set) is rejected for their reason: it silences the report without making the
distinction visible, and guesses the author's intent from the absence of a second field.

Pinned by a pair that is identical on `(quotes_authored, quotes_found)` and separated only by the new
counter, which is the confusion the field exists to end.

## RM120 — the table where the attestation lives could not name its attributor

✅ **Shipped in `just-dna-format` + `just-dna-compiler` on 2026-08-20**, motivating case
[S55](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator — **a retraction of their own S11**.

**The reporter withdrew the argument they gave us for `ATTESTATION_BEARING`, and the withdrawal is
right.** S11 said a passage extracted from a fulltext a tool just fetched *"asserts a curator reading
that never occurred"*, and our own answer turned on the same hinge: *"nothing establishes a human ever
looked."* That sentence names the defect and it is not the one the refusal fixes. It is a **missing
attributor**, not an illegitimate reader — the machine does read the article, so the reading is real
and what the rule protected was a fiction about *who* did it. The column then stayed empty for the only
reader actually present.

**The evidence that this is not academic is RM118.** The refusal did not produce human-located
passages; it produced 3,668 rows of title-as-quote in four published modules with the check green.

**Our own model already disagreed with the argument, in two places the reporter found.**
`Defaults.curator` defaults to the literal `ai-module-creator` — an AI curator is the documented
default for every row rather than an edge case — and `Contribution` carries the whole vocabulary for
saying who did what, with `who` reading *"a name, handle, or model id"* and `kind` laddering
`{human, human_expert, human_certified}` against `{ai}`. `attestation_bearing` was the one place that
then refused the AI contributor a cell.

**Shipped `StudyRow.curator`**, the same field `VariantRow` has had all along, on the table where the
attestation lives. The asymmetry it closes is the reporter's: a variant row could name who decided it
while a quote could not name who located it, though the quote is the attestation of the two. Free text
resolvable against `authorship`, never a `machine_located: bool` — two-valued collapses *an agent found
it and a human confirmed it* into one of two lies and cannot name which agent or which human. It
records the distribution of labour so a reviewer can route scrutiny; it does not move responsibility,
which the human author holds regardless.

**`ATTESTATION_BEARING` is unchanged and stays right for our layer**, which is the reporter's own
reading. A provider still must not fill the quote; what changed is that an author who *does* locate a
passage now has somewhere to say so.

**The interesting half is what wiring it found: `@three-touch-points` undercounts for this writer.**
`_write_studies_csv` names its columns in a `fieldnames` list **and** fills a row dict, and naming a
column in the first but not the second writes the *header* with an empty cell on every row —
`DictWriter` fills a missing key silently. The reversed spec looked right and re-validated, and the
value was gone; only the digest fixed-point assertion caught it. The comment on that list now says so,
and a behavioural guard fills every authored `StudyRow` column and asserts each survives the reverse,
derived from the model so a column added later cannot quietly fall outside it. Both guards were shown
to fail on the buggy code before being kept. 2830 → 2833.

## RM118 — `quotes_found` could not fail on a title, and four published modules are titles

✅ **Shipped in `just-dna-enricher` on 2026-08-20**, motivating case
[S54](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**Measured against our own tree and reproduced here in full.** Four published `antonkulaga/*` modules
carry a `provenance_quote` on every studies row — 3,668 of them — and **exactly one distinct quote per
PMID**: `cognitive_intelligence` 2045 rows / 33 PMIDs / 33 quotes, `risk_impulsivity` 695/19/19,
`big_five_personality` 859/26/26, `aggression_anger` 69/3/3. A passage located for a claim varies row
to row, because different rows cite the same paper for different findings; one string per paper is
structurally a property of the *article*. It is the title, verbatim including the trailing period.

**Why this is a check defect and not only an authoring one.** A title appears in its own fulltext, so
`_study_quote_found` matches, `quotes_found` equals `quotes_authored`, and the module publishes full
quote coverage while establishing nothing about whether any claim is in any paper. The check is
satisfiable from `esummary` metadata without retrieving a word of the article — which is the one thing
the column exists to witness. The reporter's sharpest line is that this is *worse* than the failure S11
was written to prevent: their own ask refused a machine-located passage, and what the refusal produced
instead was a machine-copied title with the check agreeing.

**The discriminator has to be the metadata**, which is the reporter's argument and it is right. A
minimum length does not separate a title from a passage (seventeen words is an ordinary title and an
ordinary sentence), and requiring a `provenance_regex` is no help because a regex is as copyable as a
quote. `CitationHint.title` shipped for S12 and arrives in the same `esummary` response that answers
existence, so the comparison costs no request — and it therefore answers for a **paywalled** article
too, which is exactly where `quotes_found` stays null and a reader has nothing else.

**Shipped** `LiteratureResult.titles_as_quotes` plus a yellow CLI line, warning-only and never an exit
code: whether a title is an acceptable locator is the author's call, and what the tool can honestly say
is that `quotes_found` is not evidence here. Two deliberate narrownesses — normalisation is case,
whitespace and a trailing period and **nothing more**, since a quote *containing* the title is a real
quote of a paper that names itself; and the report fires only when **every** quote for a citation is
the title, since a mixed citation has an author doing the work.

**One correction to the report, and it came from a failing test rather than from reading.** The claim
that a title always appears in its own fulltext is *nearly* true: esummary gives the title with a
trailing period, PMC5753237's JATS body carries it without, and `quote_matches` does not strip one, so
that exact pair misses. The substance is unaffected — the miss is punctuation, not evidence — and both
states are pinned: the finding fires either way, and a module whose two spellings agree gets the green
check the report describes.

## RM115 — a derived sidecar's merge key lived inside the pass that writes it

✅ **Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-20**,
motivating case [S51](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**RM113's question, asked of the machine-produced tables, where the answer was one step further away.**
For an authored kind the key at least existed as a lambda in `_TABLE_DUPE_KEYS`; for a fact sidecar it
existed only as a dict-key expression in the body of the pass that writes it — `existing[(row.gene,
row.dataset)] = row` and seven more like it. `key_fields` already routed derived names through
`derived_model_for` after RM113, so it *would* have answered; the seven models simply declared no key
and it correctly withheld. What shipped is the declarations, plus the half that keeps them honest.

**The reporter's approximation, and why "safe" was not "right".** They derived the subject as the
required members of the fact-field tuple — public pydantic over a public tuple, so it could not silently
drift — and it agreed on five of eight tables. It was coarse on two, and those two are exactly the
tables where one subject legitimately carries several rows: `gene_validity.csv` came out `(gene,
dataset)`, dropping `disease_id`, and `clinical_assertions.csv` came out `(variant_key, dataset)`,
dropping `variation_id`. Coarse is the safe direction for their tool — it reports more rows as ambiguous
and auto-repairs fewer — but it demotes a gene's second real disease assertion into an ambiguity a human
has to adjudicate, on the one table where a gene legitimately carries several. Both reproduced here
before the fix, against the published `*_FACT_FIELDS` tuples.

**Two shapes the obvious design could not express, and both would have been wrong answers rather than
coarse ones.** `resolution.csv`'s key is not a uniqueness constraint at all: one rsID resolves to several
loci, `locus_index` orders them, and the pass replaces the group whole — so `KEY_RULES` gains a third
member, `subject`, and reporting `equality` there would tell a consumer a legal one-to-many file is a
duplicate. And `gene_validity.csv`'s key has **two levels** — the source's own `assertion_id` where it
published one, the gene's grain where it did not — so `TableKey` gains `fallback`, tagged `"id"`/`"grain"`
so a grain tuple can never collide with an id that happens to equal it.

**Shipped.** Seven models declare `_KEY_FIELDS` (`ResolutionRow` also `_KEY_RULE`, `GeneValidityRow`
also `_KEY_FALLBACK_FIELDS`); `base.merge_key(row)` is the row-level answer; `TableKey` carries
`fallback` and `KEY_RULES` carries `subject`; `describe_table`'s `key` block carries `fallback` too.
**Every pass now keys its `existing` map through `merge_key`** — `enrich`, `enrich_frequencies`,
`enrich_gene_metrics`, the ClinGen dosage pass, `enrich_literature`, `enrich_gwas`,
`enrich_gene_validity`, `enrich_clinical_assertions` — which is the half that makes the pass and the
surface unable to disagree, rather than merely agreeing today.

**The rewire found three live restatements of the same fact, and one was a latent break.** Keying the
map off a declared tuple immediately mismatched three *lookup* sites that rebuilt the key positionally:
`covered_keys = {key for key, _population in existing}`, `if (gene, dataset) in existing`, and
`pmid not in existing` — the last of which would have refetched every cited article on every run once
the dict held tuples. All three now read the attribute off the row instead of unpacking a key, which is
the shape that cannot break again when a member is added. That is `@dont-discard-computed`'s neighbour:
a key derived in one place and re-derived positionally in another is the same defect as a hand-kept list.

**Guards.** `enricher/tests/test_merge_keys.py` — the two-level key run rather than read, the `not_found`
row keying apart from every record for its allele, the `subject` rule shown over several loci sharing a
key, every published column asserted to be a real field of the model it keys (both levels), a fallback
declared under a required primary rejected as unreachable, and every published key deduplicating the
real sidecars the reference examples carry. Two existing tests changed meaning rather than being
deleted: the withhold is now shown against a model with no `_KEY_FIELDS` instead of against tables that
have since grown one, and the rule-membership equality walks the derived registry too. 2799 → 2813.

## RM113 — a table kind's natural-key *columns* were not obtainable, only its key *values*

✅ **Shipped in `just-dna-compiler` + `just-dna-format` on 2026-08-20**, motivating case
[S48](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was wrong, and it had already cost a consumer.** `draft.natural_key` answers per **row**,
returning a tuple of *values*, so a tool holding only a table name could not ask which columns those
values came from; `_TABLE_DUPE_KEYS` was private *and* held lambdas, so even reaching in yielded no
column names out of `lambda r: (r.gene, r.allele)`. Every consumer wanting the columns therefore
hand-kept a string — and the reporter's went stale the day 0.6 landed: their surface was telling authors
to key `copynumbers.csv` on `modifier_cn`, whose own description reads *DEPRECATED since 0.6, removed at
1.0*. Reproduced here: the description does say exactly that.

**A promise was already outstanding.** `hints.describe_table`'s docstring has advertised *"the natural
key two rows are the same row by"* since 0.5, and the returned dict never carried it. So this was not a
feature request but an unimplemented sentence, which is why the dict is where it landed.

**The fix that would have been wrong.** Filtering `_KEY_FIELDS` through `model_fields` — which is what
the compiler's own grounding-remedy sentence does, correctly, for a remedy. `CopyNumberRow` keys on
`effective_modifier_copy_number`, a *property* over two columns, so the filter **silently drops the
modifier axis** and the answer becomes "two rows differing only in modifier dosage are the same row."
A wrong answer whose drop is invisible is worse than a refusal, so a derived member is mapped back to
the authored column it coalesces instead — and to the **preferred** spelling, so this surface can never
hand an author the deprecated half of a pair.

**Shipped.** `hints.key_fields(csv_name) -> TableKey | None`, plus the `key` block in
`describe_table`. `TableKey` carries `columns` (author's spelling), `rule`
(`equality`/`overlap`, a `frozenset` vocabulary per Principle 6) and `stamped` (members the compiler
fills, so `variant_key` is named as part of the key but never presented as a fillable cell). `None` for
a kind with no declared key — withheld, not invented.

**The structural half, and the reason this touched the schema tier.** The columns and the key were two
statements of one fact, so eight models now **declare** `_KEY_FIELDS` and both `_TABLE_DUPE_KEYS` and
`_CORE_DUPE_KEYS` are **derived from it** through one `_key_of`. One source of truth: `key_fields` and
`natural_key` cannot disagree, and a test pins them against each other over real authored rows from
`reference_examples/cyp2c19_star_alleles`. The whole suite passing unchanged (2784) is the evidence that
the derivation reproduces every lambda it replaced, including the PGx dedup keys each earned by real
ClinPGx data.

**What the tests found that the design had not.** `variant_key` is a stamped **field** on `VariantRow`,
`HaplotypeRow` and `PharmVariantRow` but a **property** on `StudyRow`. The first guard written asserted
every key column is a `model_fields` member and failed on `studies.csv` — correctly. The invariant worth
pinning is the weaker, truer one: a key member is either an authored column or flagged in `stamped`,
never a bare name resolving to nothing. Two further guards keep the class closed rather than the
instance: no key column on any kind carries a `DEPRECATED` description, and every rule is a declared
vocabulary member.

## RM114 — the scaffold pulled `variants.csv` in behind `studies.csv`, which RM47 made wrong

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S49](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was wrong.** `COMPANION_KINDS["studies.csv"] == ("variants.csv",)` was applied
unconditionally, so `scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` warned that
`variants.csv` was owed and wrote a stub for it — inviting an empty table into a module whose author was
doing the right thing. **RM47 is what made this wrong**: a study row is legal with no variant identity
precisely so a binning module can ground its thresholds through `pmid`, and that is the *intended*
shape. Reproduced both halves — the scaffold really does create the stub, and the resulting
`copynumbers.csv` + `studies.csv` module really does compile **strict-green**, three warnings, none of
them about `variants.csv`.

**The comment was already right.** Its own justification said `studies.csv` *alone* fails with "module
has no recognized table" — true when literally alone, false beside a binning table. So the defect was
that the condition the comment described was never applied, which is why the repair is the comment's own
wording rather than a new rule.

**Shipped.** `scaffold.companions_for(kinds)`, public, applying the condition and used by
`scaffold_module` itself. `studies.csv` pulls `variants.csv` only when no other recognised table was
requested; `variants.csv` still pulls `studies.csv` **unconditionally**, because that direction has no
condition — the compiler wants grounding evidence for a variant claim however the module is composed.
The recognised set is derived from the compiler's own `_TABLE_KIND_CSVS` plus `variants.csv`, mirroring
`if not has_variants and not kind_row_counts` exactly, so a table kind added later counts without an
edit. `sources.csv` is deliberately outside it: a licence ledger is not a table a module can consist of.

**`COMPANION_KINDS` itself is unchanged**, and that is deliberate rather than incidental — the mapping
states a real pair, and a consumer reading it is not wrong about the pair, only about its
unconditionality. The reporter passes the constant through rather than restating it, which was the right
instinct and is why the accessor is public: an internal-only fix would have left their surface giving the
old answer while ours gave the new one.

**Rejected candidate**, the reporter's own blunter option: drop that direction of the pair and let the
"no recognized table" error speak for itself. It loses the help in the one case the pair was added for —
`studies.csv` truly alone — which a test now pins.

## RM112 — the machine-produced tables have no public `csv -> row model` resolver

✅ **Shipped in `just-dna-compiler` on 2026-08-20**, motivating case
[S47](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.

**What was missing.** `draft.model_for` answers for authored kinds and refuses everything else by
design, so a tool asked *"what is in `frequencies.csv`"* — or `resolution.csv`, files an author must
read and must never hand-finish — got `'resolution.csv' is not an authored table of this format`. True,
and useless. The only complete map was `compiler._FACT_TABLES`, private and free to move in a patch.

**Why the four obvious substitutes do not work**, each checked rather than assumed: `hints.model_for`
and `draft.DRAFTABLE` are authored-only; `just_dna_registry.specfiles.FACT_CSVS` is public but is
**names only**, and lives in another package, so a registry release lagging a compiler release makes the
answer lag too; `ARTIFACT_PARQUETS - LEAD_PARQUETS` does not isolate them — measured at **nine** names
against seven fact tables, because `annotations.parquet` and `studies.parquet` are in neither set; and
`authoring_reference()["models"]` is keyed by **model name**, so it answers "what columns does
`GeneValidityRow` have" and cannot answer "which model is `gene_validity.csv`" — which is the direction a
tool caller holding a filename actually needs.

**Shipped.** `hints.DERIVED_TABLE_MODELS` plus `hints.derived_model_for(csv_name)`, the read-only
counterpart to `draft.model_for`. **Derived from `_FACT_TABLES`, never restated** — re-introducing a
hand-kept map in order to publish one would be the defect wearing a public name — with a test asserting
set equality over the walked set, so an eighth fact table fails CI instead of becoming undescribable.
Both spellings of the licence table are keys, exactly as `DRAFTABLE` does it and for the same reason
(`@sidecar-name-and-place`); `sources.csv` is deliberately in both maps, being the one fact table a human
legitimately writes. `verification.json` is excluded: it is the attestation document, not a fact table.
Asking it for an authored name raises with the route that *does* answer — `@specific-rejection`, since
"not machine-produced" is a dead end where "use `model_for`" is a fix.

**What was not done.** `describe_table` still refuses non-authored names. Widening it was tempting and
rejected: a caller today can rely on that refusal, and the reporter had already built the second
read-only route themselves — the missing piece was the map, not the presentation.

# 0.6.2 — the enricher's exception contract, one layer up from RM97

One item, and the first in a while to arrive from the consumer inbox rather than from a doc pass.
**A partial cut**: only `just-dna-enricher` moved, so `just-dna-format` and `just-dna-compiler` stay
at `0.6.1`. The additions are minor-legal — new public names beside the old, nothing removed or
retyped — so the patch number carries them without straining P3.

## RM101 — a pass raises its client's exception type, which its own documented type does not cover

✅ **Shipped in `just-dna-enricher` 0.6.2 on 2026-08-18**, motivating case
[S37](CONSUMER_SUGGESTIONS_HISTORY.md) from just-dna-registry. `@client-exception-contract`, one layer
up from where RM97 left it.

**What was wrong.** RM97 made each *client* raise its own type instead of `httpx`'s. A consumer does
not call a client — they call a **pass**, and the pass's docstring and the CLI handler beside it both
name the pass's type. Five call sites held a client in `try: … finally: close()` with **no `except`**,
so `GnomadError` walked out of `enrich_frequencies` and `enrich_gene_metrics`, and `EutilsError` out
of `enrich_literature` and `check_rsids`. A handler written as
`except FrequencyEnrichmentError` was silent for exactly the failure it was written for.

**It was not only a consumer's problem, and that is what sized the item.** `just-dna-enricher`'s own
`frequencies` command promises `FREQUENCIES FAILED: <reason>` and exit 1; measured on a gnomAD 503 it
printed **nothing at all** and let the exception out. The printed contract was false on the path it
existed for.

**Three of the six sites were reported; three were found by walking.** The report named
`frequencies`, `literature` and the `clingen` conflation. Walking every pass that takes an injected
client added `gene_metrics` and both `identifiers` sites, and walking the *clients* found
`OntologyClient` still leaking a raw `httpx.HTTPStatusError` from both of its methods — a full release
after RM97 declared that class of defect closed. **RM97's own coverage guard is why it survived**: it
walked a hand-written tuple of eight module names and `identifiers` was not one of them.
`@registry-completeness`, in the guard whose job was to prevent exactly this. Both guards now discover
by `pkgutil` walk — one by "owns an `httpx` transport", the other by signature — so a new client or
pass fails the suite by name until it is covered or explicitly exempted.

**The leak was load-bearing in two places, which is the trap worth carrying.** Repairing a client
without grepping for handlers that catch the *leaked* type turns working behaviour off silently. Two
handlers here did exactly that: `cli.py`'s `check-identifiers` caught `httpx.HTTPError` to attest
`unreachable` — on the run its own test calls *"the run where the record matters most is the one with
no report to print"* — and `enrich()` caught `EutilsError` under *"a dbSNP outage does not sink a
finished enrichment"*. Both only ever fired because of the defect. The second was caught by its test;
the first would have been a silent loss of an attestation.

**Why a subclass and not the obvious translation.** `FrequencyUnavailable(FrequencyEnrichmentError)`
and five siblings, after `AcmgListUnavailable`. The reporter proposed flat translation
(`raise FrequencyEnrichmentError(...) from exc`) **and then argued against it themselves**, correctly:
it flattens "your input is wrong" and "the source is down" when every pass here used one type for
both. There is a second reason they did not give, and it is the stronger one — *they had already
compensated* by catching the client's type, so a flat repair would have broken the consumer who filed
the item. A subclass keeps every `except <Pass>Error` working (P3) and makes the narrow catch new
capability rather than a migration. The client's error stays on `__cause__`.

**The conflation half, and its unreported twin.** `ClinGenError` covered "could not fetch the curation
list" *and* "your local `gene_metrics.csv` will not parse" — opposite histories, separable only by
reading `exc.__cause__`. `gene_validity.py` had the identical pair at lines 369 and 437 and nobody had
reported it. Both now raise the `*Unavailable` subclass on the fetch path only. Matching the message
was the alternative and is worse: neither string is in the pinned warning-text catalogue, so a reword
would silently flip a consumer's verdict from "unchecked" to "your table is broken".

**Deliberately untouched.** `enrich_gwas` (client and pass share `GwasError`, so nothing is foreign),
`enrich()` and `enrich_pgx` (both **degrade** rather than raise — the tri-state withhold, which is the
right shape where work worth keeping has already been produced), `Grch37Client` (returns `None`/`[]`
on every transport path and raises nothing), and the two snapshot builders plus `pgx_draft.draft_gene`,
whose callers correctly enumerate the several types they can see. That last group is the *list* shape
the report objected to and RM96 is the lesson for — a real question, wider than this item, and named
in the guard's exemption block rather than left to be rediscovered.

Tests: `enricher/tests/test_pass_exception_contract.py` (new — walks the passes, drives both histories
for the two conflated modules) and the rewritten guard in `test_client_exception_contract.py`. Each
repair was demonstrated failing on the unrepaired code before being asserted.

# 0.6.1 — the eight the documents caught, the two the fixes found, and RM88

**A documentation pass regenerated SCHEMAS/COMPILER/ENRICHER from the source alone on 2026-08-18, read
the result against the shipped documents, and asked which of the two was wrong.** Eight times it was
the code. **RM88 rode along**, closed the same day and for a related reason — detailing it showed the
technical blocker it had been carrying was mispriced, leaving a policy question that took one decision
— and its own entry below carries the half that shipped as an ask rather than a fix. Everything else: no schema surface moves, `schema_version` stays `"1.0"`,
and all sixteen reference examples recompile byte-identical — verified against a worktree at `5c1ea87`,
the state before the first fix, rather than assumed from the absence of a model change.

**Every one of the eight broke a rule this repo had already written down**, and in four of them the
file carrying the violation also carried the rule, sometimes in an adjacent comment: `@validate-refuses-all`,
`@vocab-separator-slip`, `@registry-completeness`, `@client-exception-contract`, `@unreachable-not-absent`,
`@sidecar-name-and-place`, `@credential-where-read`. **That is the finding underneath the eight, and it
is the one worth keeping: the gotcha book is not the thing that catches a regression.** So the durable
half of every item below is a *test*, and in six of the nine that test walks a registry rather than a
list — the `@registry-completeness` shape turned on the guards themselves.

**Five of them were found by the same failure mode, at five different scales**, which is the second
thing worth recording. A hand-kept list stands in for a registry, and then the list is only as complete
as whoever last remembered it: `_ALL_MODELS` missing five row models (RM96), `test_validate_agrees_with_compile`
missing four of the seven fact tables (RM93), `net.py`'s "nine policies" against a tree of twelve
(RM100), the sidecar resolver three passes did not call (RM99), and the client contract two of four
clients honoured (RM97). None of these is a hard bug in a clever place. All five are a number or a list
somebody had to remember.

**What the items said and what was actually there differed five times**, and the differences are folded
into the entries below rather than left as a filing to reconcile. Four made the item bigger — RM93's
guard was missing four fact tables and not one, RM96's registry was missing five models and not three,
RM99 had five more sites in the CLI's own reporting, RM100 stranded a fourth command — and one made a
claim right for a different reason than stated (RM98's `SourceRow`, which follows from `authority`
rather than from `source`). RM100 also grew a fifth defect on 2026-08-18, after four of them had
shipped.

**One consumer-visible surface grows, deliberately and with the trade stated** (RM96): `authoring_reference()`,
`describe`, `requirements` and `json_schemas()` now render 28 models where they rendered 23. That is
additive under Principle 3 and buys guards that cannot miss a model again, which is the trade — a wider
printed reference in exchange for a registry that iterates itself.

The suite went **2568 → 2722**. Every new regression test was demonstrated failing on the pre-fix tree
before being claimed as a guard.

## RM88 — republishing without bumping `version:` overwrites a versioned path with different bytes

✅ **Shipped in `just-dna-enricher` 0.6.1.** [RM84](ROADMAP_0_7.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own)
built the versioned path `data/<name>/v<version>/` and it did exactly what it said. What it could not
do was notice that the version had *not* moved: an author who recompiled a changed module and
republished without editing `version:` overwrote the versioned copy with different bytes, and the path
then named a version whose contents were not the ones that version had. The same lie the flat path
already tells, arriving at the address built to stop telling it — which is why it was worth an entry
rather than a shrug, and also why it was never a defect in RM84.

**The delay was the policy, and the entry's own accounting of the other half was wrong.** It named a
remote read as the first of two blockers, pricing it against "a path whose current cost is one
`upload_folder`". The real cost is `create_repo` plus **two** `upload_folder` calls, in the one tier
permitted to fetch, so one more read was always marginal — the entry's closing line had already
conceded as much ("the check is cheap once the policy is chosen"). Corrected while detailing it on
2026-08-18, which is what left the product question alone as the blocker.

**Refuse unless `--force`**, decided 2026-08-18, over warn-and-proceed and refuse-outright. The flag's
existence is itself the claim that overwriting is sometimes right, and that is the honest position: a
curator re-cutting a draft release is a real workflow, and a gate with no override becomes a gate
people route around.

**Four outcomes, and the third is the one that decided the shape.** No versioned path (the module
states no version) — nothing addressable to collide with. The path is absent — the first publish of
this version, one `file_exists` and no download. **Present with the same digest — proceed**, because
`upload_module` writes two commits and documents a re-run as the recovery when the second fails, so a
gate keying on *presence* would refuse exactly the retry the design depends on. Present with a
different digest — refuse. `artifact.digest` is the comparator because it is a Merkle root over
exactly the attested files, so one small manifest read answers the question a tree listing could only
answer for whatever happens to be LFS-backed.

**It fails open, deliberately.** If the published manifest cannot be read, nothing established a
collision, so nothing asserts one — the house algebra withholds, and the publish proceeds with a
warning. Failing closed would make every network flake demand `--force`, training an author to pass it
by default and turning the gate into one people route around, which is the exact failure the policy
was chosen to avoid. It must not come back through the error path.

**A recompile under a newer compiler trips it, and that is correct rather than a false positive.** P4
scopes byte-reproducibility to a fixed `compiler_version`, so the versioned path really would come to
hold different bytes than the ones it was published with. The refusal says so in its own text, because
*"but I changed nothing"* is the first thing its first user will think.

**Not a repair, and still refused:** making the compiler bump `version:` automatically. A version is an
authored claim about compatibility, and a tool that increments it asserts something only the author
knows — the same move the repo already refused for `SourceRow.dataset` in RM85.

### The half that shipped as an ask instead of a fix

**`upload_folder` adds and replaces; it never removes.** Found while detailing this entry, wider than
the filed defect, and verified off the API contract rather than a live publish. A recompile that stops
emitting a table leaves the previous release's parquet at the path beside a manifest that does not
attest it — so a republish leaves a **union of two releases**, on the **flat path, every time**,
version bumped or not.

**The format's answer is that this does not matter**, and it is the right reading:
`manifest.artifact.files` states which parquets *are* the module, `artifact.digest` is a Merkle root
over exactly those, and an unattested leftover is outside both. A manifest-first reader never sees one
and verification passes, because nothing was corrupted. On that reading the leftover is an inert fossil.

**What stops it being true is the reader**, which
[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) already records,
verified in the consumer's tree rather than inferred: the discovery path adds *"no manifest fetch and
no digest check"*, `verify_manifest` *"has no call sites there"*, and the scan is `fs.ls` at one level
plus `fs.exists` on **named files**. Registry path: inert. Discovery path: a leftover parquet is
indistinguishable from a live one. The concrete failure is a **shape misreport, not corruption**, and
it needs two things at once — a module whose table set *shrank*, read over discovery. A SNP-core module
re-authored as table-only keeps a fossil `weights.parquet` and still probes as a SNP core.

**`delete_patterns` was considered and declined**, which is the part worth recording because it is the
obvious repair:

- **It leaves the nested `v<version>/` archive alone today, and by accident.** HuggingFace filters
  delete patterns with `fnmatch`, whose `*` **crosses path separators** — their own docs warn about it
  — and every member of `_ALLOW_PATTERNS` is a literal basename, so `manifest.json` does not match
  `v1.0.0/manifest.json`. Add one `*.parquet`, a completely reasonable tidy-up of a 28-entry list, and
  a single publish deletes every archived version's parquets. `_SNAPSHOT_ALLOW_PATTERNS` already
  carries two globs, on a path with no nesting, so the habit exists.
- **It would not close the case anyway.** Only a republish cleans a fossil, so every module nobody
  republishes keeps its own; and it does nothing at all for a consumer that probes filenames rather
  than reading the manifest.

A fix whose safety rests on an accident, and which does not close the case, is the wrong half of the
answer. **The right half is the reader**, so it shipped as an explicit ask in
[INTEGRATION_0_6 § 2.8](INTEGRATION_0_6.md#28-the-publisher-path-marketplace--registry) with the
mechanism, the failure and the reasoning — the RM27 shape: a finding about a downstream reader is an
explicit ask, never an implication. One read of `manifest.artifact.files` closes it for good, on every
module including the ones already published, which no publisher-side change can reach.

## RM93 — two checks refuse in `compile` and report nothing in `validate`

✅ **Shipped in 0.6.1.** `@validate-refuses-all`, broken twice, and reproduced against real specs before
being fixed rather than argued from the source.

`_check_study_effect_alleles` sat inside `validate_spec`'s `if variants:` block and ran unconditionally
on the compile side, so it never ran for the one composition it was written for: a module with a table
kind, `studies.csv` and `resolution.csv` and **no** `variants.csv`. The comment three lines above the
call claimed it was "audited by check, not by table (`@parity-by-check`)" while the gate did the
opposite. Measured on `cyp2c19_star_alleles` plus one study row naming `C` at an `A/G` locus:
`validate(strict).valid=True` beside `compile(strict).success=False`. The repair is a move and nothing
more — `membership_table` is filled from `resolution.csv` in the sidecar loop far above and is in scope
whether or not a variant was authored, which is the thing worth checking before assuming the hoist needs
an input rebuilt.

`_check_frequency_arithmetic` was never called from `validate_spec` at all. It lives in a per-model
closure on the compile side, so a pass auditing table by table saw `frequencies.csv` loaded and stopped.
Its integer half returns **errors**, so this was the plain-mode variety of the gap — measured on
`hboc_palb2` with `allele_count=500` against `allele_number=100`.

**The durable half is that the guard now enumerates**, and this is where the item was bigger than filed.
`test_validate_agrees_with_compile.py` walked a literal list of four filenames — **four of the seven
fact tables were missing**, not one — and every case in it was a *row-level pydantic* failure, the kind
both sides already catch, so no table-level check had a path through it at all. Separately, every study
fixture wrote `variants.csv` beside `studies.csv`, so `if variants:` was always true and the shape the
gate excluded was never constructed: the suite only ever asked well-composed questions. The list is now
a module constant checked against `_FACT_TABLES`, and the four missing tables have cases.

## RM94 — the p-value re-run publishes its warning twice into the manifest

✅ **Shipped in 0.6.1.** The compile-side `_check_p_value_num` re-run extended `all_warnings` with no
`if w not in all_warnings` filter, which every neighbouring re-run has, including the study-allele block
four lines above it. Reproduced: one authored disagreement, two byte-identical sentences in
`manifest.compilation.warnings`.

**Why it survived is the part worth keeping.** `@no-rerun-with-counts` guards against a re-run whose
message embeds a count, because the two copies then *disagree* and the manifest publishes two numbers —
a self-contradiction somebody notices. This message carries no count, so the copies agreed and the field
was merely redundant. The wider rule the neighbours already followed is now written beside the fix: **a
check that runs on both sides dedupes on the message, and re-running it is the normal case rather than
the exception.**

**The re-run itself was examined and kept**, against the entry's own suggestion that it might not earn
its place. It does: `compile_module` runs `validate_spec` in best_effort *regardless of this compile's
mode*, so the second pass in the caller's mode is the only thing that lets `--strict` escalate the
warning into a refusal. Dropping it would have disarmed the strict gate silently — which is the answer
to "does this pass need to run twice" that the standing test (does resolution change its input?) does
not reach on its own.

## RM95 — a canonicalized vocabulary value is discarded, so the slip is stored and then rejected

✅ **Shipped in 0.6.1.** `@vocab-separator-slip` says a closed vocabulary accepts `-` for `_` **and
stores the declared member**. `MeasureBinRow._validate_measure_kind` called `check_vocab` for its raising
side effect and returned the uncanonicalized value, so the rule held for every other field and failed
for this one. Both halves of the consequence needed fixing: `measure_kind="copy-number"` validated and
stored `'copy-number'` — a value not in the vocabulary, inside `content_signature` — and `_EXPECTED_KIND`
was compared against that same raw string, so every subclass rejected exactly what the base class had
just accepted, with an error naming the canonical form the input already denoted.
`_validate_measure_tiling`, one line above, always returned the result, which is what makes this a slip
rather than a decision.

`Contribution._check_role` and `PgsRow._validate_ancestry` discarded the same return and are fixed with
it. They were latent only because no member of either vocabulary contains a separator *today* — a
property of the current members, not of the code. The list case in `PgsRow` was the sharpest: it
canonicalized per element and returned the original list, so a slip in a multi-valued cell survived whole.

**The durable half reads storage rather than acceptance.** `test_vocab_separator.py` proved `check_vocab`
canonicalizes and could not see a validator that ignored the answer. It now walks every closed-vocabulary
field in the schema — discovered through `field_vocabularies` and pydantic's own decorator registry, so a
new one is covered without editing the file — and drives each validator with both spellings. Five of its
cases fail on the pre-fix tree: `MeasureBinRow` and all four subclasses.

**No signature moved**: every `measure_kind` across the sixteen reference examples was already canonical,
checked rather than assumed.

## RM96 — the registry an audit iterates was missing five of the models

✅ **Shipped in 0.6.1, wider than filed.** `GeneMetricsRow.status` named the `ResolutionRow` vocabulary
in its own description and enforced nothing, so `status="totally-made-up"` validated while every sibling
fact table refused it. `@registry-completeness` from the other side: the model sat outside
`reference._ALL_MODELS`, so the guard that discovers an unenforced vocabulary *by iterating the registry*
could not see it, and `reference.py` recorded the exclusion in a comment while the enforcement stayed
missing.

**The entry named three models outside the registry. There were five.** `ResolutionRow` was outside too
— the canonical holder of `VALID_RESOLUTION_STATUS`, the vocabulary three of the others point at by name
— and `GwasEffectRow` (RM90) landed outside it a day before the audit that found this. So the registry
was falling behind faster than it was being caught up, which is the argument for the fix being the
registry rather than the validator.

Admitting them turned the existing guards on, which is the point, and they immediately found **seven
fields enforcing a vocabulary without declaring it**: `ResolutionRow.status`/`.rsid_status`,
`FrequencyRow.status`, `GeneMetricsRow.haploinsufficiency`/`.triplosensitivity`,
`LiteratureRow.quote_source`/`.status`. Each now carries its marker, so `authoring_reference()` prints
what each cell may contain instead of leaving a consumer to read `model_fields` — the S21 hole, seven
more times.

**The price was accepted knowingly and is the one consumer-visible change in this release**:
`authoring_reference()`, `describe`, `requirements` and `json_schemas()` render 28 models where they
rendered 23. Additive under Principle 3, no schema surface moves, and `INTEGRATION_0_6 § 7` says so.

Two smaller ones alongside. `GwasEffectRow._check_finite` is registered for `effect_size` *and*
`standard_error` and reported `"effect_size"` for both, sending an author to the column that was fine;
`gene_metrics.py` passes `info.field_name` for the identical validator across nine fields, so the idiom
was one file over. And `start` carried `ge=0` on five of the eight models with a position —
`HaplotypeRow`, `PharmVariantRow` and `HeteroplasmyRow` accepted `start=-5`.

**The bound stays `ge=0` and deliberately does not tighten to `ge=1`.** The entry asked the question, and
the answer was already recorded: VCF 4.4 §1.6.1.2/§5.4.5 permit POS 0 for a **telomeric breakend**, and
[VCF_4_4_AUDIT § 9](probes/VCF_4_4_AUDIT.md) filed it under *checked, and not a finding* — `VariantRow.start`'s
`ge=0` is what lets such a record load, while `derive_vrs_allele_id` returns `None` below 1 rather than
minting an id for a position that does not exist. Tightening would have re-broken something a probe round
deliberately left alone, so the reasoning now sits in a test rather than in a probe document.

## RM97 — two clients leak the transport exception the other two document repairing

✅ **Shipped in 0.6.1.** `@client-exception-contract`: retry, then translate, **both legs**. `cpic.py`
and `pharmvar.py` carried the repair *and* the narrative of why it was needed (R2-13) for a whole release
while `gnomad._post` and `eutils._get` kept the unrepaired shape. Both leaked twice over, not once:
`raise_for_status()` sat outside the `try` **and** `httpx.HTTPStatusError` was in neither retry list, so a
5xx escaped raw and unretried; and the transport leg was re-raised bare on purpose, for the decorator to
match, then escaped just as raw once `reraise=True` exhausted the attempts. gnomAD leaked `ValueError`
from `response.json()` past both, while eutils already translated that one leg — the asymmetry that made
it easy to read as fixed.

Both now use cpic's split. **The one deliberate deviation from copying that idiom verbatim** is that each
client's `429 → RateLimitedError` branch stays inside the retried half and before `raise_for_status()`:
those types are what the retry predicate matches and what drives the pacing, and cpic has no such branch
to copy.

`CpicClient.row_count` bypassed its own `_get` entirely, so the one method with no retry and no
translation was the one the snapshot builder uses to refuse a short read: a transport failure raised raw
httpx past `cli.cpic_build_`'s handler, and a 5xx returned `None`, which the builder reads as *"CPIC gave
no count"* — a wrong answer rather than an error.

**Both call sites the entry names are repaired, not just the clients.** `enrich()`'s `check_rsids` had no
handler at all and runs after every other pass has finished and *before* `resolution.csv` is written, so
an NCBI outage threw away work that had already succeeded. It now warns and continues with no verdicts,
matching the gnomAD block above it — and withholding is the outcome rather than a fallback: `rsid_status`
stays unset, which says nobody asked, where stamping `absent` would assert a negative the run never
established.

**The durable half tests the contract, not the method** — that is the finding underneath the item. One
file parametrized over gnomad / eutils / cpic / `cpic.row_count` / pharmvar, both legs plus the
swallow-into-a-wrong-answer case, with a guard that walks the tier for `*Client` classes so a sixth
cannot ship without joining it (the four left out are *named in the assertion*, not skipped). Nine of its
sixteen cases fail on the pre-fix tree — and the seven that pass are cpic and pharmvar, which is the
finding restated.

## RM98 — two passes record an absence nobody established under `--offline`

✅ **Shipped in 0.6.1.** `@unreachable-not-absent`: unreachable is not absent — write no row, name it
separately, warn in both modes.

`enrich.py` holds that rule twice, in the branches on either side of the one that broke it, each with a
comment spelling out that writing `not_found` would state *"the source was asked and does not have this
rsID"*, a negative nobody established. The branch **between** them did exactly that: with `--offline` and
no Ensembl and no ClinVar cache, it wrote `status="not_found", source="cache"`, naming a cache that was
never opened. `gene_metrics` had the same shape: having logged *"gene metrics will be empty"* it wrote a
`not_found` row per module gene labelled `gnomad_v4.1_constraint`, asserting a release was consulted when
nothing was, three lines below its own comment drawing exactly that distinction.

**The filing's `SourceRow` claim was right for a different reason than stated, and the correction is
worth having**: the fabricated row carries `authority='ensembl'`, and `record_source_terms` keys on
`authority` rather than `source` — so a `SourceRow` for a source never read really did follow, by a route
the entry did not name.

Both passes now compute a *was any route consulted at all* predicate from the gates that already exist —
a resolved cache reference, or `not offline` — and withhold when every gate is shut. The result is named
**separately** rather than folded into a neighbour: `EnrichResult.unconsulted_rsids` and
`GeneMetricsResult.unconsulted` are a third state beside `unreachable_rsids` ("the request was made and
failed") and `missing` ("asked, and the source has none"). Collapsing them would have replaced one small
untruth with another. Both warn in both modes and both stay inside the strict refusal, since a run that
established nothing must still refuse.

**`test_fact_passes.py` pinned the wrong behaviour in two places** — it asserted `[r.status for r in
result.rows] == ["not_found"]`, so it was falsifying the log line rather than the behaviour and the suite
was green either way. Those moved with the fix, and each gained a negative control: offline **with** a
cache that genuinely lacks the rsID still writes `not_found`, because that is a real fact and the repair
must not throw it away. Without those, *"stop writing not_found offline"* would have passed.

The `--offline` case is where this matters most, because it is the mode a consumer runs when they
*cannot* reach the source: the fabricated negative is guaranteed there rather than incidental.

## RM99 — three passes bypass the sidecar resolver, so one family writes to two places

✅ **Shipped in 0.6.1, with five more sites than filed.** `@sidecar-name-and-place`: resolve a sidecar's
name and place through the resolver, and **write to the file you read**. RM49 shipped
`licensing.sidecar_path` for exactly this, and nine `sources.csv` writers were converted to it in one go.
`gene_metrics`, `clingen` and `literature` kept their own `spec_dir / "<name>.csv"` literal.

The sharp part is that it was inconsistent **inside one family**: `gene_validity` — `gene_metrics`'
sibling, sharing `module_genes` — did use the resolver. And `gene_metrics` and `clingen` write the *same
file*, both read-merge-write, so one `enrich` run on one module produced two copies of `gene_metrics.csv`
that each dropped the other authority's rows. That is the both-copies-present collision RM49 made an
error rather than a preference, arrived at by following the documented workflow.

**Five more sites turned up in the reporting layer.** `cli.py` printed `spec_dir / 'resolution.csv'` and
four more like it in its success lines, so even where the pass wrote to the right place the CLI sent the
author to a file that had not changed. Two commands already carried the fix with a comment saying why;
the other five did not — which is the same "the rule is written down beside the violation" shape as the
rest of this release.

`literature.py`'s hand-joined `studies.csv` **read** is deliberately left alone and now says so: that is
an *authored* table living in the spec root, and `sidecar_path` is for the machine-written files RM49
allowed under `derived/`.

**The durable half does not test three passes.** Per-pass repair leaves the next pass free to make the
same choice, and these three were written *after* the rule was.
`test_sidecar_resolution_is_uniform.py` walks the enricher's AST for `spec_dir / "<a sidecar name>"` — an
AST rather than lines, so a filename inside a docstring is not a false positive — with `identifiers.py`'s
documented read-only fallback **named** as the one exemption rather than pattern-matched away. Beside it
the behavioural half: the resolver really does follow `derived/` for every sidecar the schema knows
about, and a flat module still gets the flat path, since `derived/` is tolerated and not canonical. The
roster is checked against `layout.SIDECAR_SPELLINGS`, so a ninth sidecar fails there.

## RM100 — five enricher surface defects with no common cause

✅ **Shipped in 0.6.1.** Filed together because each is a few lines, not because they share a root. What
they do share is that every one is invisible from the happy path — which is why the fifth was still
arriving while the first four were being fixed.

**`python -m just_dna_enricher.cli` was missing commands.** `if __name__ == "__main__": app()` sat
two-thirds down the file, above the `hint` sub-app, `draft-clinpgx`, `draft-panel` and — not in the
filing — `clinvar citations`, so the module form called `app()` before those registrations ran. Measured
before and after: 23 vs 26 top-level commands, now 26 vs 26. The guard is structural as well as
behavioural, since the AST test fails the moment a registration is appended below the block, which is
exactly how this arose.

**`clinvar_build._sha256_file` was defined twice.** The second shadowed the first at module load, so the
one that always ran returned `str | None` while the **dead** one returned `str` — and the annotations
downstream had been written against the dead one. `BuildResult.source_sha256` and
`_write_release_json(source_sha256=)` both said `str` while a `None` really could reach them; both now
say `str | None`, which is the house algebra rather than a typing nicety: an unhashable source file is an
unknown digest, not a missing one.

**`enrich_gwas` leaked its client and ignored `mode`.** The close was a bare `if client is None:
catalog.close()` after ~80 lines of fetching and writing, so any exception in between leaked the httpx
client while every sibling pass already used `try/finally`.

`mode` was accepted and never read while the CLI advertised `--strict` as a severity ladder, so the flag
was inert. **What it escalates is deliberately not `missing`**, and the reasoning sits where the raise is:
the Catalog holding nothing for a variant is a fact *about the variant* — recorded as a `not_found` row,
true of most variants, and the pass's own docstring says so — so escalating it would refuse nearly every
module and mean nothing. `strict` reads the two counts that say the artifact does not hold what the
Catalog **did** publish: associations served without an id to key on, and p-values below float64 whose
queryable number is withheld.

**`NCBI_API_KEY` and `JUST_DNA_CONTACT_EMAIL` were read without `load_env()`** (`@credential-where-read`).
`PharmVarClient` calls it with a comment describing this exact failure; `eutils` and both literature
clients read `os.environ` directly, so a `.env`-only key was honoured or ignored by call order and the
NCBI rate gate silently stayed at 1/3 s instead of 10/s.

That fix immediately broke `test_eutils.py`, and **that is the interesting part rather than collateral**:
it used `monkeypatch.delenv("NCBI_API_KEY")` and passed only because nothing had loaded `.env` yet.
`@test-no-credential` says `setenv(VAR, "")`, never `delenv` — `load_dotenv` skips a variable that is
merely present — and `test_literature_terms.py` states the same rule beside its own fixture. So the rule
was already written, already explained, and already violated one file over; the fix made it fire. Both
call sites move to the documented idiom.

**The fifth, filed after the first four had shipped: `net.py` documented "the nine policies" in two
places while the tree carries twelve**, across nine modules. The guard meant to hold that claim was blind
on both axes at once — `assert len(found) >= 9` is a floor, so three new policies pass it, and it walked
a hand-kept list of seven module names.

The measurement is sharper than the filing. The old walk reported 12, the right number, **by accident**:
it counted a client once per module that *imports* it, so the inflation from double-counting happened to
cancel the two modules it never opened. Filtering by defining module, it saw ten distinct policies and
was blind to `grch37.Grch37Client._get` and `gwas.GwasCatalogClient._get` entirely. **A guard whose number
is right for the wrong reason is worse than one that is merely wrong, because the number reads as
confirmation.**

The fix is an equality over a walked set, not a corrected count: the test discovers modules through
`pkgutil`, filters owners by `__module__` so an import cannot double-count, and asserts set equality
against the twelve by name. The prose loses its number rather than gaining a corrected one, and says why
— a count in a docstring is a registry nothing iterates, which is RM96's finding arriving in a docstring
instead of a `dict`.

# 0.6.0 — the design round, built

**The whole of [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)'s decision list, implemented.** Sixteen items were
argued to a decision on 2026-08-13 — each with the facts probed, the repairs rejected and why, and the
consequences that follow without being chosen — and the eleven that build are below with their original
entries intact. The proposal stays the reasoning document; these are the outcomes, and where the two
disagree the note at the top of each section wins, because several of these entries were written before
the decision and describe a shape that was rejected.

**Landing them cost one charter amendment, which went first and alone.** The Constitution ruled on
whether a change was *legal* and said nothing about what a legal change *cost*, and the absence kept
surfacing as an instinct that there were "too many tables" — right about some additions, wrong about
others, with no stated way to tell which. A schema addition now costs what its layer costs: a parquet
column is approximately free, a derived CSV is half, an authored schema is full. Four of the decisions
below turn on it, and two obviously-worth-building items (RM24, RM25) had looked like creep only because
a machine-written sidecar was being priced as though a human had to learn it.

**The VCF 4.4 cluster shipped with them.** RM53–RM65 came from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md), a
full read of the specification against the schema, and they are not repeated here as sections because
the audit remains their evidence document. Their through-line is worth stating once: *the schema named
a VCF field by a bare token, and a VCF field is not identified by its name* — it is identified by
namespace (INFO and FORMAT collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, new in 4.4, `CN`) and
described by cardinality. Both readings of a colliding key are usually type-compatible, so nothing
detects the confusion: a consumer reads a well-formed number of the wrong kind. Two shipped reference
examples were wrong on exactly this and were re-authored, which is why `mt_heteroplasmy` and
`htt_repeat_expansion` are the only two modules in the corpus whose `content_signature` moved across
the whole batch.

**What the batch cost the corpus, measured rather than assumed.** Across all eleven reference examples:
`content_signature` moved on **two** (the two re-authored above), `artifact.digest` moved on **seven**
(new optional and stamped columns — Principle 4 scopes byte-reproducibility to a fixed
`compiler_version`), `resolution_signature` **gained** a value on the four table-only modules that
carry a `resolution.csv` and no `variants.csv`, which is precisely the hole RM45 closed, and the source
signature moved nowhere. The suite went from 1535 to 2046 tests.

**One pattern showed up three times independently and is now a rule in CLAUDE.md.** Three separate
lanes shipped the same defect and each was caught by its own code review: a check re-run after
resolution counts the *expanded* rows, so an rsID that resolves to several loci produces the same
finding twice with different numbers, message-dedup keys on the sentence and cannot collapse them, and
both reach `manifest.compilation.warnings` — a published field contradicting itself. Measured at
"1 row(s)" beside "2 row(s)", and at 328 beside 337 on `pathogenic_clinvar`. The rule covering it and
its opposite: **re-run a check after resolution exactly when resolution changes its input, and never
when the message embeds a count.**

## RM4 — Native ClinVar gene-panel materialization

✅ **Shipped in 0.6.** Compile-time materialization was dropped rather than built: the mechanism is enricher draft-scaffolding, which already shipped, and the author's no-op over the drafted subset is still an authorial act. `panel:` lost its last consumer and is deprecated (removal at 1.0, tracker line filed); `clinvar_draft` now stamps the ClinVar release into the licence row's `dataset`, and `clinical.tautology_reason` keys on that instead of the authored block — both sides calling one shared label function, because a writer and a reader disagreeing about it would not fail, they would silently never match. The hand-edit hole closed on a mode ladder (`strict` audits every row into copied / authored / conflicting / no_record; `best_effort` keeps the cheap skip plus a notice naming the hole). Two findings the round produced: `merge_sources_csv`'s never-clobber rule is right for terms and wrong for a machine-stamped release label, so the label is now *withdrawn* rather than re-labelled when a module spans two releases; and "copied" had to become allele-exact, since a locus-wide match can be a sibling allele's call (`rs334` carries pathogenic `T>A` beside likely-benign `T>G`). The unrelated surface bug shipped with it: `draft-panel` exposes `--download/--no-download`.

**Severity** medium · **Status** deferred to 0.6+ — the injectable-reference half is unblocked ·
**Owner** format (compiler) + consumer-provided reference · **Motivating case** gene-panel modules
(cardio / cancer / pathogenic)

Compile a `GenePanelSpec` (gene set + significance predicate) into `weights.parquet` at compile
time, gated on a **content-pinned ClinVar reference mixin**. The 0.2 `GenePanelSpec` *interface*
ships and is recorded verbatim; the app-level `gene_panel` adapter in just-dna-lite is the interim
reference implementation. Blocked only by Constitution P2 (no network) — the reference must be
*injected*, not fetched. **0.5 update:** the content-pinned reference now exists as an injectable
artifact — `just-dna-enricher`'s ClinVar snapshot (`clinvar build` → `data/*.parquet` +
`release.json` carrying `source_sha256`/`clinvar_file_date`, feeding
`GenePanelSpec.reference`/`reference_sha256`). What stays parked is the *compile-time
materialization* of a `GenePanelSpec` into `weights.parquet`; the injectable reference half is
unblocked.

## RM5 — Symbolic / structural alleles

✅ **Shipped in 0.6.** The five closed VCF first-level types (`DEL`, `INS`, `DUP`, `INV`, `CNV`) with open subtypes, and nothing above them — the `##ALT` declaration mechanism stayed rejected as unasked extendability. **The one question the decision left open, where the length lives, resolved to *inside the token* (`<DEL:1500>`, `<CNV:TR:30>`) on evidence rather than taste**: VCF carries it as `SVLEN`, which is `Number=A`, so a scalar column cannot describe `alts=<DEL:5>,<DUP:9>` and a parallel array is the desync shape `vrs_id` needed two guards for; and three of the columns holding an allele have no row to hang a length on. A length-less symbolic allele is dropped with a warning saying **dropped** under `best_effort` and refused under `strict` — fatal in both modes on the composite tables, where dropping a row makes a quietly *different* module rather than a smaller one. 5-HTTLPR stays a plain indel and CPIC's IUPAC codes stay unexpressible, both deliberately. Carried the docstring fix: `validate_allele` has two users, not one.

**Severity** medium · **Status** deferred to 0.6+ · **Owner** format (schema) · **Motivating
case** 5-HTTLPR, SNP+SV modules, symbolic-VCF consume

A representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large
indels. **Motivating cases: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a
repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`)
**and ClinPGx's `del`/`ins` genotypes** (177 rows in the release, e.g. `C/del`, `del/del`), which
the PGx passes skip rather than coerce. Also unblocks SV-scale variation and consuming symbolic
VCF alleles (round-2 §1b/3c).

## RM24 — Gene–disease validity as a table

✅ **Shipped in 0.6** as `gene_validity.csv`, a derived fact sidecar with its own signature, manifest block and non-tainting `gene_validity` source layer. **Probing corrected the stated grain twice**: mode of inheritance had to join the key (59 ClinGen gene/disease pairs carry two rows differing only there) and so did `submitter`, because GenCC is a nineteen-submitter aggregate whose *disagreement* is the data and collapsing it would publish one arbitrary verdict as consensus. **HPO ships no route**, a deviation argued in the PR: its licence URL 404s and OBO Foundry records no SPDX id, so its terms cannot be established, and an inject-only tier does not get to assume them.

**Severity** medium · **Status** deferred on the design, not the code · **Owner** format (schema +
compiler) + enricher · **Motivating case** gene-panel triage; lay-language disease naming

(`gene_validity.csv`) — one row per `(gene, disease term, classification, source, dataset)`,
serving **ClinGen** gene-disease validity, **GenCC** aggregate validity and **HPO** gene→phenotype
from one shape. This is a *different grain* from `gene_metrics.csv` (gene × term, not gene), which
is why it is a table rather than more columns; dosage sensitivity went the other way for the same
reason. The cost is the design (getting one shape to fit three submitters' vocabularies), not the
code. All three sources are free, so unlike RM23 this one leaves a module sellable — worth
remembering if the marketplace ever sells modules, since every PGx upstream forbids it.

## RM25 — ClinVar assertion tier as artifact data

✅ **Shipped in 0.6** as `clinical_assertions.csv` — the clinical call, the review wording, the star rating and ClinVar's own VariationID, one row per allele × record. The deciding argument was the house one applied a fourth time: `draft_gene_panel` was already using the star rating as a filter and throwing it away, so every consumer would have recomputed it. A one-star single submission and a practice guideline are no longer flattened to the same `clin_sig`. The cross-check's severity stays parked, deliberately.

**Severity** medium · **Status** deferred as a new table · **Owner** format (schema + compiler) +
enricher · **Motivating case** authorship/assertion-aware scrutiny

A facts sidecar carrying `clin_sig` + `review_status` + `review_stars` + `variation_id` per
variant, so a consumer can route scrutiny by assertion tier at query time (a 1-star submitter and
a practice guideline are not the same claim). Nothing is lost today: `clinical.ClinSigFinding`
**already** reports both fields via its `confidence` property, so this is about persisting the
tier, not discovering it. Deferred as a new table. **Do not confuse this with escalating the
check's severity** — see *Parked in 0.5*.

## RM27 — A redistribution compile gate

✅ **Shipped in 0.6 as record-only, with a named enforcer.** The most-restrictive redistribution verdict is stamped into the manifest and **no gate exists in these four packages** — gating belongs at *publish*, which lives downstream, so the item ships with an explicit ask addressed to the registry in SCHEMAS.md rather than an implication. That is the whole difference from the status quo the item was filed about: a recorded right nobody is told to enforce, versus a recorded right with a named enforcer. `taints_redistribution` no longer describes the design as open.

**Severity** low (after the design) · **Status** deferred — needs the third axis designed first ·
**Owner** format (compiler) + enricher · **Motivating case** OMIM-/dbNSFP-class sources

RM21's gate keys on `commercial_use` + `declared_use`; the 0.5 `redistribution` column is recorded
but **not** gated. Deferred because it is a genuine design question rather than a missing branch:
a redistribution bar is not a *use*, so `declared_use` (`unstated`/`non-commercial`/`commercial`)
is the wrong axis to resolve it against — a module may be built legitimately and still not be
shippable, which is a different verdict from the ones the gate currently issues. Needs the third
axis thought through before code.
## RM43 — Resolution reaches the SNP core only, so a 0.4-led module is rsid-joinable and nothing more

✅ **Shipped in 0.6.** The injected `resolution.csv` is joined onto the three positional kinds before `_build_table` materializes them, in `validate_spec` as well as `compile_module`. Each model gained stamped, parquet-only `variant_key` and `authored_ident`, plus `alts` on `PharmVariantRow`/`HaplotypeRow` filled as **data, not identity** — the key is still derived without it, so the existing "matches at `chrom:start:ref` regardless of allele" contract is unchanged. The reported case closed: `pgx_slco1b1_simvastatin`'s nine rows went from every coordinate null to `12 / 21178615 / T / A,C`. `reverse` rebuilds the lookup table from the positional parquets as a second source, which P7 forces. No `resolution.parquet`. **One deviation worth keeping**: the stamped fields are `Field(exclude=True)`, because declaring them plainly moves `content_signature` on all five positional-table modules — `model_dump(exclude_none=True)` never omits a stamped field, since it is never `None`. That leaves `VariantRow`'s own two inconsistent with the three new ones, grandfathered and filed as a 1.0-cleanup candidate.

**Severity** high (the prerequisites, not the join) · **Status** open — **0.6**, gated on a design
round rather than on a version · **Owner** format (schema) + compiler · **Motivating case** an rsid-authored ClinPGx
module: 1,482 rows, 147 variants, every coordinate null (S9 in
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md))

`compile_module` resolves `variants.csv`; every other table goes through `_build_table`, which is
`model_dump()` → parquet. So a module led by `pharm_variants.csv` or `haplotypes.csv` keeps exactly the
coordinates its author typed, which for an rsid-authored one is none — and a VCF is joined by position,
so the table annotates nothing, silently, as an empty result rather than an error. Reproduced on this
tree's own `reference_examples/pgx_slco1b1_simvastatin/`: 9 rows, all null, while the `resolution.csv`
beside the spec resolves the rsID perfectly well. **0.5.3 made it legible** — the compiler now reports,
per positional table, how many rows cannot be joined and how many of those the injected table could
place — but the fix itself is here.

**The obvious repair is illegal as stated, and that is the part worth recording.** "Join `resolution.csv`
on `variant_key` and fill the empty cells" moves more than the digest the reporter expected: materializing
the coordinate and running `compile → reverse → compile` moves **`content_signature`**
(`sha256:8173dab7…` → `sha256:fb91ffa2…`), because `reverse_module` rebuilds the CSV from the parquet and
a filled coordinate returns as an *authored* one. That is exactly what `VariantRow.authored_ident` exists
to prevent, and no 0.4-family model has an equivalent. So the prerequisite is a stamped
"which identity columns did the author supply" column per positional table — a **new column on an
existing parquet** — which is **0.6 work** since the 2026-08-11 charter amendment, so the prerequisite
is a design round rather than a major bump. What stays major-only is nothing here: the item is gated on
doing the stamped-identity design first, not on a version.

Three more constraints found with it, each of which shapes the design rather than merely costing:

- **`PharmVariantRow` has no `alts` column at all.** A filled row can carry `chrom`/`start`/`ref` and no
  allele, so a positional join lands on the locus and allele matching still goes through `genotype`.
  Adding `alts` is a second new column, and it would make the key allele-specific — which
  `_collect_subjects` deliberately avoids ("a pharm annotation matches a variant at `chrom:start:ref`
  regardless of allele").
- **`variant_key` is a *property* on these models**, so it is materialized in no PGx parquet. A consumer
  cannot join a PGx row to `weights.parquet` on it either — which is a second, smaller instance of the
  same complaint and probably wants solving in the same round.
- **The manifest cannot say any of this.** `fully_resolved` is `all(...)` over `VariantRow`, so it is
  vacuously `true` for a table-only module — against the trust rule its own field comment states — and
  `resolution_signature`/`resolution_sources` stay unset, so the injected table leaves no trace.
  Stamping the signature is itself blocked: `reverse_module` rebuilds `resolution.csv` from
  `weights.parquet` alone, so a table-only module reverses to a spec without one and the round-trip
  fixed point breaks. This half is the same shape as the registry's S8 (a manifest that cannot say a
  check ran) and should be decided with it.

## RM45 — the manifest is rich about resolution and silent about verification, so `unchecked` and `clean` are one state to a downloader

✅ **Shipped in 0.6** as `verification.json` — a derived attestation the enricher writes and the compiler reads, stamping `manifest.verification` or dropping it with a warning when stale. Counts rather than booleans and **two fields rather than one union-typed slot**, so "ran against 0 rows" and "did not run" can never share a value; two closed vocabularies rather than free strings, which would have recreated RM44 one level down; bound to the authored bytes with a **~0.4 s median** proof-of-work, one per sidecar per run, found deterministically so the bytes reproduce. Every field is marked untrusted, in the descriptions *and* in SCHEMAS.md, because a forged pass is worse than silence. **A JSON document rather than a fifth fact CSV**: one attestation over many records is a service row in CSV, and it is the one derived artifact whose human-overridability must not be a feature — which is the mechanism the 0.6 charter amendment asks for. The vocabulary audit moved the set twice: `pgx_evidence_level` and `rsid_coordinate_agreement` were genuinely missing, while lane E's two new passes correctly get no member because they adjudicate nothing, and a test pins that exclusion by name. Wiring it up surfaced two pre-existing holes — the reference-allele and clinical checks each had an internal skip returning an empty list indistinguishable from a clean pass, which is S4's defect surviving inside S4's own machinery. `resolution_signature`/`resolution_sources` are now stamped for table-only modules too, unblocked by RM43.

**Severity** medium (a per-version trust signal nobody can build, and no way to triage what was
published unchecked) · **Status** open — **0.6** · **Owner** format (the manifest shape + vocabulary) +
enricher (the only tier that holds the facts) + compiler (the stamp) · **Motivating case** a catalog
that verifies a module's `clin_sig` on its own deployment has nowhere to record that it did (S8 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Confirmed structurally, which is the strongest form this claim can take.** `Compilation`'s twelve
fields carry nothing about verification. `ResolutionRow`'s eighteen columns are all per-*row*
(`status`, `rsid_status`, `rsid_current`). `EnrichmentResult` holds `clin_sig_not_checked`,
`ref_mismatches`, `stale_rsids` and `vrs`, and dies when the run ends. So a module whose authored
`clin_sig` was cross-checked against ClinVar and one where the check never ran ship **identical**
manifests — not by oversight in some path, but because no field exists that could differ.

**This is S4's own argument one level down.** 0.5.2 accepted that an empty `clin_sig_conflicts` meant
both "compared everything, nothing disagreed" and "never compared", and fixed it — on
`EnrichmentResult`. The layer that outlives the run inherited none of it, so the rule holds in process
memory and nowhere else. The same applies to the reference-allele and rsID-currency passes.

**Legality is not the obstacle, and it is cheaper than the usual case.** The manifest was never inside
`artifact.digest`, and a new optional field is additive and minor-legal (P3, amended 2026-08-11) — so
**0.6, not 1.0**. A manifest field that a *publishing authority* stamps rather than the compiler
deriving is also already this schema's shape: `compiled_by`, `namespace`, `owner`, `published_at` and
`canonical_id` are all that. And the reporter's field shape is right for our own stated reasons —
counts rather than bools, and **two** fields rather than one map with a union-typed value, so "ran
against 0 rows" and "did not run" can never occupy one slot. `vrs_alleles`/`vrs_alleles_identified` is
the precedent; the ACMG pass's `checked: 0` is the other.

**Four things the proposal leaves open, which is what makes this a design round and not a patch:**

1. **The check name is a vocabulary, or this is RM44 again one level down.** A `dict[str, int]` keyed on
   free strings lets the enricher write `clin_sig`, a registry write `clinsig`, and a consumer
   substring-match the difference — an unversioned interface, the exact defect RM44 exists to remove.
   The keys want `frozenset[str]` + a validator (P6), and because vocabulary members are permanent
   within a major (P5) the set has to be audited once against the passes that would plausibly join it:
   reference allele, rsID currency, ACMG SF, identifier/trait currency, quote-checking, dosage
   sensitivity.
2. **The skip *reason* must not be free prose either, for the same reason.** Backfill triage — the
   reporter's own second use case — branches on *why* a pass did not run, so `dict[str, str]` of prose
   relocates the substring matching rather than ending it. The reason wants a small closed vocabulary
   (`tautological`, `no_reference`, `offline`, `not_applicable`) with the sentence *beside* it, not
   instead of it: `clinical.tautology_reason` already writes a good sentence and it is worth keeping as
   human detail rather than promoting to a machine key.
3. **The seam has no channel, and that is the actual work.** `resolution.csv` is the enricher→compiler
   contract and carries per-row facts only; "this pass did not run" is per-pass by nature and has no row
   to attach to — the reporter identifies this precisely. Two routes, and choosing is the design. A new
   sidecar the enricher writes and the compiler reads is consistent with every other injected table
   (and would want its own fact-signature), and it gives the workspace a path it can test end to end.
   An argument on `compile_module` is cheaper and is what the reporter proposes, but then the only
   producer is the caller: the format would declare a field its own reference implementation never
   fills, which is how `VALID_SOURCE_LAYERS` ended up with members no file carried.
4. **The trust rule belongs in the schema's own docs, not in the reporter's caveat.** Their point that a
   forged pass is *worse than silence* is right, and it already has a spelling here — `compiled_by`'s
   description says "foreign values are untrusted". Whatever lands must say the same on each field and
   in SCHEMAS.md, or the first consumer to read `checks_run` off an untrusted manifest believes it.

**Recommended shape: option 2, a `Verification` block.** The reporter's own argument for it is the
stronger one and it is the house pattern — `Frequency` earned a separate block because it has its own
producer, its own release and its own fact-hash, and verification has all three. A `clin_sig` check is
only as good as the snapshot it read, so the block wants that release id, and no existing block has a
home for it; `locations.read_release` (0.5.2) is what makes "verified against ClinVar release X" a
sentence this tier can complete at all. Absent on a module nothing verified, which reads correctly as
*says nothing* rather than as a pass.

**It does not subsume RM44.** S13 offered S8 as the superset and it is not one: `resolution_subjects` is
the denominator of an existing flag about *resolution*, which is not a verification pass. Adopting that
framing would park a one-line additive integer behind this whole round.

## RM46 — a literature source's terms are per-article, so the enricher names a source it cannot record

✅ **Shipped in 0.6** as per-article licence columns on the derived literature row, filled from the Europe PMC response the pass already makes and mapped at read time. No `PUBMED_TERMS` constant: a literature source's terms are per-article, and one `pubmed` row would be right for a module citing only ids and **wrong** for one carrying a quote lifted from a CC-BY-NC article — wrong in the dangerous direction, because that quote is publisher text in the module's own annotation layer. Quoting a restrictive article **warns and gates nothing**, on the clinical-cross-check precedent: arbitrating copyright is the same class of overreach as arbitrating a clinical dispute.

**Severity** low as a symptom (a warning on every literature-enriched module), medium as a hole (a
module quoting a CC-BY-NC article has no way to say so) · **Status** open — **0.6** · **Owner**
enricher (`licensing` + `literature`) · **Motivating case** every literature-enriched module warns
about a source the enricher itself introduced (S10 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced by reading the three pieces.** `enrich_literature` writes `source="pubmed"` into every
`literature.csv` row. `TERMS_BY_SOURCE` has seven members and no `pubmed`, and `record_source_terms`
deliberately *skips* a name it has no terms for ("inventing a row for the rest would be worse than the
compiler's honest warning"). `_source_checks`'s under-declaration branch then names `pubmed` on every
such module. So the tier introduces a source and declines to record it, and the finding lands on the
author. Worth stating precisely, because it bounds the severity: `SourceRow.source` is free text, so an
author *can* hand-write the row and clear the warning. This is not an unclearable finding — it is the
enricher asking the author to write down something only the enricher knows.

**The reporter is right that a `PUBMED_TERMS` constant would be the wrong fix, and this is the part
worth keeping.** A literature source's terms are **per-article, not per-source**: PubMed's *metadata* is
one thing, the *article* belongs to its publisher, and Europe PMC's OA subset spans CC-BY, CC-BY-NC and
bronze. One `pubmed` row would be right for a module that cites only PMIDs and **wrong** for one
carrying a `provenance_quote` lifted from a CC-BY-NC article — and wrong in the dangerous direction,
because that quote is publisher text sitting in the module's own **annotation** layer, which is exactly
where `taints_commercial_use` bites. A row that reads "pubmed, fine" would make such a module look
cleared when it is not, which is worse than today's warning.

**Two other obvious repairs, both wrong.** *Stop writing `source="pubmed"`* — no: `source` is how a
consumer knows which upstream answered, and the existing reasoning for preferring PubMed over Europe PMC
(which "cannot originate a row", since it silently omits ids it does not know) is sound. *Have the
compiler exempt enricher-introduced sources* — no: the compiler would need to hold a list of which
sources a pass introduces, which is a **source convention**, forbidden it since 0.5 (P2) and the exact
mistake RM33 removed. The fix belongs to the tier that both names the source and owns the terms table.

**The shape that matches the facts is the reporter's option 2, and it is the bigger one.** Per-article
terms, either as an additive licence column on `LiteratureRow` (minor-legal) or as `sources.csv` rows
keyed by DOI, plus one decision that is not the enricher's to make alone: whether quoting a CC-BY-NC
article taints the module for sale. That is the *use*-versus-*distribution* axis **RM27** already parks,
so the two want settling together. The tier is closer than it looks: `is_open_access` is already
tri-state on the row, and the pass holds the licence at the moment it would need to record it (Europe
PMC returns `isOpenAccess`; Unpaywall returns a licence id per DOI).

**Interim step, if 0.6 slips:** the reporter's option 1 (a `literature`-layer `pubmed` row for the
*metadata*, plus a documented rule that quoting requires a second `annotation`-layer row for the
article) is defensible — but only if the row's terms are stated as the metadata's and the quoting
obligation is written where an author reads it. Shipped as a bare terms constant it silences the warning
and buys the false clearance above, so it is not a one-liner.

## RM47 — a bin boundary is the most interpretive claim in the format and the only one with nowhere to cite

✅ **Shipped in 0.6.** `MeasureBinRow.pmid` grounds the *boundary* — one optional column on the binning base reaching all four kinds — and `StudyRow`'s subject requirement relaxed so a citation row may name no variant, which only makes previously-*invalid* rows valid. The documented line is **the bin row cites, the citation table describes**, which is what stops `StudyRow`'s provenance column set migrating onto binning rows one column at a time. The same-release obligation was met rather than deferred: `_cross_check_literature` and the enricher's literature pass both read the new site, reached across the tier boundary through new **public** compiler symbols (`load_binning_rows`/`binning_citations`) rather than a private import or a second hand-kept kind list. `htt_repeat_expansion` stays deliberately uncited — the example exists to show the gap.

**Severity** medium (no module is unauthorable, but the claim a reader would most want to check is the
one the schema asks nothing about) · **Status** open — **0.6**, gated on a design round rather than on a
version · **Owner** format (schema) + compiler + enricher (the literature pass) · **Motivating case** an
HTT CAG module whose thresholds had nowhere to record their source (S19 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced on this tree's own reference example.** `reference_examples/htt_repeat_expansion` compiles
green under `--strict` stating four Huntington thresholds — 26/27, 35/36, 39/40 — with no citation
anywhere in the module, and until 0.5.4 nothing said a word. Its README even says *"a module making a
novel claim should carry its evidence"*, which is advice the schema gave the author no way to take.
`StudyRow` identifies its subject by `rsid` **or** `chrom`(+`start`), and a `repeat_alleles.csv` row is
keyed `(gene, repeat_unit)`, so no study row can name one; `MeasureBinRow` has no `pmid`, `doi` or
`evidence_level`. The requirement is enforced exactly where citations usually arrive for free — a
ClinVar-drafted `variants.csv` — and absent where a human made the judgement.

**One correction to the report, and it narrows the item.** The same does *not* hold for
`heteroplasmy.csv`: it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts` since 0.5.1, so a study
row on the same variant identity points at it exactly, and `reference_examples/mt_heteroplasmy` already
does this. What is genuinely unpointable is the three gene-keyed kinds — `repeat_alleles.csv`,
`copynumbers.csv`, `activity_phenotype.csv` — plus a heteroplasmy row that names only a gene. A second
correction in the other direction: `studies.csv` is *not rejected* in a variants-free module. It loads,
validates and materializes `studies.parquet` today, so an author can ground the module as a whole right
now — the row simply has to claim a variant identity the bin does not have (a bare `chrom=4` for HTT),
and nothing ties it to a bound.

**Shipped in 0.5.4 (the reporter's option 2), and it is the interim, not the answer.**
`compiler._check_binning_grounding` warns in both modes when a binning table states thresholds and the
module records no study rows at all, with the message split on whether the rows *could* be pointed at:
the heteroplasmy shape gets a remedy ("fill the identity columns"), the gene-keyed shape gets the honest
statement that no study row can name one of these bins. That turns silence into a visible decision and
changes no schema.

**Four candidate repairs, and none is a one-liner — which is why this is filed rather than fixed.**

- **`pmid`/`doi` on `MeasureBinRow`.** The smallest schema move (a new optional column on the base
  reaches all four kinds, minor-legal under P3) and the only one that grounds a *boundary*, which is what
  was actually asked for. It is also the largest **wiring** move: `literature.csv`, `_cross_check_literature`
  and the enricher's literature pass all read `StudyRow.pmid` and nothing else, so a bin-row PMID would
  be a citation no existence check, no bibliographic check (S12) and no quote check ever reaches —
  grounding that *looks* verified and is not, which is worse than the honest gap. And it starts the
  drift: `studies.csv` carries population, `p_value_num`, `effect_size` and `provenance_quote`, so the
  first author wanting a quote begins growing `StudyRow`'s column set onto a binning table.
- **A generic `subject_key` on `StudyRow`.** Rejected on the binning tables' own stated rule —
  *multicolumn keying, never a packed tuple*. `HTT|CAG` is a second spelling of an identity the columns
  already spell, it can drift from them with nothing to catch it, and P5 gets a field carrying two axes.
- **Key columns on `StudyRow` plus a new `REQUIRED_ANY_OF` alternative.** Legal — the columns are
  optional, and widening an any-of only makes previously-*invalid* rows valid, so no published module
  breaks. But it grounds at table granularity, not at the boundary: a `(gene, repeat_unit)` study row
  still does not say why 36. Making it say so means putting `measure_min`/`measure_max` on the study row,
  i.e. restating the bin inside its own evidence. It also quietly changes a contract consumers read —
  every `studies.parquet` row today carries an rsid or a chrom.
- **A `bin_evidence.csv` join table.** Keeps one-CSV-one-concern and grounds per bound, but the join key
  *is* the bounds, and they are floats: re-authoring `40` as `40.0`, or moving a threshold, silently
  orphans its evidence with no rule able to notice. A join key that is also the data is the shape to
  avoid.

**So the decision to make is which granularity the format promises** — module, table, or boundary — and
every honest repair costs either a duplicated column set or a duplicated key. Settle that first; the
column follows in an afternoon. Whichever wins, the literature pass and `_cross_check_literature` have to
learn about the new PMID site in the same release, or the format ships evidence it does not check.

## RM48 — an hg19 coordinate has no supported path into a GRCh38 module, and liftover is the wrong primitive

✅ **Shipped in 0.6, and the roadmap's stated blocker was false.** Ensembl runs a permanent GRCh37 REST service serving both dbSNP variants and reference bases, and per-contig lengths for both builds are 25 numbers each — no chain file, no provisioned asset, no new licence, so the scope-back condition never triggered. rs-number recovery only, live-only, reporting and never filling. The offline half (a position past its contig's end, a contig only one build names) went into the **compiler**, in `validate_spec` and `compile_module`, as an **error in both modes** — it is provably wrong, the inconsistent-reference-allele class. The online build-guessing half stayed in the enricher. **The round's sharpest finding was about already-shipped code**: run on a real wrong-build scenario, the existing ±1 neighbour check reported "shifted 1 base to the right" for two rows whose true variants are 228 and 411 bases away — a neighbouring base equalling the authored `ref` is a one-in-four coincidence. The new diagnosis supersedes it, but only from its two strong evidence tiers, since a single-base GRCh37 match rests on the same coincidence.

**Severity** low-medium (an authoring gap with a manual workaround, filed as a longshot by the
reporter) · **Status** open — **0.6**, gated on choosing the primitive · **Owner** enricher (the
recovery link + any provisioned asset) + format (`resolution.csv` provenance) · **Motivating case** an
author curating from older literature with hg19 supplementary tables (S22 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Not RM15, and the distinction is the useful part.** RM15 is about supporting another build *as the
module's build* — it changes `variant_key` semantics and every coordinate, which is why it is 1.0. What
is missing here is one-way and authoring-time: the module stays GRCh38, only the author's input is
hg19. It re-keys nothing, needs no GRCh37 refget table, and changes no published identity, so filing it
under RM15 would park an additive tool behind a major-version blocker for no structural reason.

**The reporter argues against their own request, and the argument holds.** Trace when liftover is
actually reachable. If the paper gives an rsID, liftover is unnecessary and worse: authoring the rsID
*produces* the independent second value `resolution._verify` cross-examines. So liftover is only
reachable when there is no rsID and only an hg19 coordinate — and in exactly that case the lifted
coordinate becomes the row's sole identity, with nothing independent to check it against. A liftover
tool is therefore a generator of unverifiable-by-construction identities, which is the hazard class
behind the 3,038-variant off-by-one this tree already paid for. What the author wants is **rsID
recovery**: given an hg19 `chrom:start:ref:alt`, return the rsID or say there is none, so they author
an identity normal resolution can verify. Same input; it converts an unverifiable coordinate into a
verifiable one using machinery the enricher already has.

**Why it is not simply "do rsID recovery, then".** The recovery lookup is against a *build the enricher
does not otherwise touch* — every link is gated on GRCh38 — so it needs either an hg19-keyed dbSNP
surface or a chain file, and a chain file is a provisioned, pinned asset with its own licence and
release, i.e. the whole snapshot apparatus for one authoring convenience. That is the design round, and
it is what the version gate is on. Liftover survives only as the fallback for a locus with no rsID at
all, where it must announce itself rather than emit a coordinate that looks authored.

**One requirement whichever primitive wins, and it is already a shipped lesson.** The outcomes are
**mapped**, **unmapped** and **ambiguous** (a coordinate lifting to several targets), and they must not
collapse — `pyliftover` returns an empty list both for unmapped and for a missing chain file, which is
byte-for-byte the fusing S20 fixed in this same resolution path on the same day. Whatever lands here
returns three states, and the provenance goes in `resolution.csv`'s `source` column rather than being
lost into an ordinary authored coordinate.

## RM50 — PMID and PMCID are one id apart, and only one direction of the conversion exists

✅ **Shipped in 0.6.** `extract_pmids` now declines a digit run whose context spells `PMC` in any spacing, and the refusal **names the id it saw** rather than the one it wanted. This closed a live hazard rather than a cosmetic one: `PMC3110566` never parsed, but **`PMC 3110566` did** — and those digits are a real PMID for an unrelated article, so the outcome turned on a space and the accepted spelling silently cited the wrong paper. A cell that compiled before may refuse now; that is the fix. The PMC id lives on the derived row only, and `hint citation --pmcid` is a **reporting** lookup that never fills `pmid`, because filling it would make the existence check compare a value against the registry that produced it. The authoring half stays 1.0 with the requiredness demotion, since a citation with no PubMed id cannot become legal while P8 holds.

**Severity** medium (the accepted-but-wrong case is a silently misattributed citation — the S12 class)
· **Status** open — the **diagnosis half is an enricher patch and does not wait**; the schema half is
**0.6**, gated on a design round and on the requiredness demotion already queued for 1.0 · **Owner**
enricher (the guard, the reverse lookup) + format (`extract_pmids`' grammar and its message) ·
**Motivating case** raised while reading SCHEMAS.md's own account of the three reference tables
(2026-08-12)

**Three distinct confusions live under one heading, and only the middle one is already tracked.**

**1. A PMCID written where a PMID goes is sometimes accepted, as a different paper.** `StudyRow.pmid`
is free-form and validated through `spec.extract_pmids`, which is `\b(\d{1,8})\b`. Probed:
`PMC3110566` → `[]` and `pmcid: PMC3110566` → `[]` (no word boundary between `C` and a digit), but
`PMC 3110566` → `['3110566']`. The outcome turns on a space. When it is accepted the extracted number
is a **real PMID for an unrelated article** — PMIDs are densely allocated, which is precisely the S12
finding that made `pmid_exists` useless as a fabrication guard and put `title`/`journal`/`year`/
`first_author` on `CitationHint`. The rejected half is barely better: the message says "must contain at
least one PubMed ID" and never says the word PMCID, so it is a generic refusal where a specific one is
a fix — the same shape as `MISPLACED_COLUMN_REASONS` and `reject_reserved` one level down.

**2. A citation with no PMID at all** is *already tracked* and is not re-filed here: [§ 1.0 cleanup —
`StudyRow.pmid` required + PMID-shaped](ROADMAP.md#studyrowpmid-required--pmid-shaped) queues the requiredness
demotion to "≥1 of `{doi, pmid}`", and a PMC-only record (books, NIH reports, some datasets) is largely
covered by it, since such a record normally carries a DOI. What that entry does not say is what
`LiteratureRow` — keyed on `pmid`, digits-only, **required** — is supposed to do with such a row. That
is the piece which has to be decided in the same release, and it is the reason this item exists beside
the tracker entry rather than inside it.

**3. Only one direction of PMID↔PMCID is resolved, and the recorded reason only covers that
direction.** `literature._identifiers` reads `doi` and `pmc` out of the esummary `articleids` block, so
PMID → PMCID arrives free, and `literature.py`'s own docstring records that the **PMC ID converter is
deliberately unused** because of it (and separately that the converter is no existence oracle — its
"invalid article id" is about PMC *membership*). Both statements are true, and neither is about
**PMCID → PMID**, which is the direction the converter actually exists for. So a curator holding a PMC
id has no route through any of the three packages to the `pmid` every table keys on. Do not close this
by quoting the docstring back at it; it answers the other question.

**What can ship without the design round** — enricher plus `extract_pmids`, no schema change, no
verdict changed for anything else: refuse a digit run whose immediate context spells `PMC` in any
spacing, and **name the id that was seen** rather than the one that was missing. And where the record
does resolve, the pass already holds the PMCID from the same esummary response, so comparing it against
the authored digits catches the accepted-with-a-space case for free. Both are diagnosis, never repair —
nothing rewrites an authored cell.

**What needs the design round:** whether a PMCID is an *identity a citation may be authored under*, or
only a cross-reference the enricher fills. Three candidates, with their costs:

- **An optional `StudyRow.pmcid`.** Additive and minor-legal, and it closes the authoring half — but it
  leaves `LiteratureRow`'s key unanswered for a row carrying no PMID, and it puts a second id column on
  a table whose `pmid` is already free-form and may hold several.
- **Resolve every PMCID to a PMID at enrich time and store only PMIDs.** Smallest surface, and it
  silently drops the records that have none: two ways of returning nothing rendered as one sentence,
  which is S20 exactly.
- **Re-key `LiteratureRow` on a general citation id.** The honest shape, and it changes what an existing
  key *means*, so it is 1.0 and not this.

Whichever wins lands **with** the requiredness demotion, not before it — deciding the sidecar's key
while `StudyRow.pmid` is still mandatory answers a question no module can currently ask. Related:
RM47 makes the same observation from the other side, that a new PMID site obliges the literature pass
to learn it in the same release.


# 0.6 dogfooding — the fix round's own findings, repaired

Round 2 of [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) came from *reading the code around each
repair* rather than from building a module, and the thirteen findings that needed action were numbered
RM74–RM79 on 2026-08-14. What follows is what shipped, in the order it was worked.

## RM74 — the drafting providers read their sources wrong, and the test that would have caught one does not run

**Severity** high (one member) · **Status** ✅ shipped · **Owner** enricher · **Found by** code review
during the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-1, R2-11, R2-3

Three defects, one read each and one loop, all in `clinpgx_draft._rows_from_snapshot` and the test file
beside it.

**ClinPGx's `gene` is `;`-multi-valued** (R2-1). Re-probed against the provisioned snapshot before
touching anything: **396 of 16,087 rows** carry a `;` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24,
`CYP2A7P1;CYP2B6` ×18), and `--gene VKORC1` dropped the **3** rows of `rs17886199`, published as
`PRSS53;VKORC1`. The filter now matches per member. The `;` separator was already a named constant —
for `drugs` — which is the part worth keeping: one dialect, two columns, and only one of them read it.

**What is *written* for a plural cell was the one real choice here, and the three candidates are not
equally wrong.** Writing the cell verbatim is what shipped until now, and it is a non-symbol in a
column described as *"Gene symbol, e.g. VKORC1"* — every consumer's gene filter misses it for exactly
the reason ours did. **One row per gene is illegal, not merely undesirable**: `gene` is *outside*
`PharmVariantRow`'s dedup key, so the copies collide on
`(variant_key, drug, genotype, phenotype_category, annotation_id)` and the compiler refuses the module
— which is the structural difference from `drugs`, which *is* in the key and therefore legitimately
becomes one row each. And **picking from the cell alone has no rule to pick by**: the pharmacogene is
first in `CYP3A5;ZSCAN25` and second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`, so
position orders nothing and "the one that matters" is a pharmacological judgement this tier does not
make.

What shipped is the CPIC `gene.chr` move — a **lookup in what the caller already stated**. Under
`--gene VKORC1` the request selects exactly one member and writing it asserts only what the source
asserts. With no request, or with a request selecting two members of one cell, nothing selects, and
the answer is the house one: **withhold, and say which genes the cell named**, aggregated by cell so a
panel-scale draft does not print one line per row. An empty cell reads as *not stated*, which is
weaker than the truth; the joined cell is false about its own column.

**`skipped_unidentified` counted the wrong denominator** (R2-11). The rsID check ran before the
`--gene` filter, so a record with no rsID from an unrequested gene incremented it, and on any
`--gene` draft the "records the source could not identify" number was inflated by the rest of the
database — destroying the one thing it is for, judging whether coverage of *your* gene is poor. The
filter moved above it; every skip counter is now scoped to the requested set.

**A test's stated coverage was not exercised** (R2-3). `test_draft_declared_build.py` built its
fixture with a nested `"location"` key while `cpic.defining_variants` reads `"sequence_location"`, so
the dict was always `{}` and the file's claim to cover "one defining variant carrying a coordinate"
was hollow — the drafted `haplotypes.csv` did not exist and the file passed either way. Third
instance of the class after S21's registry and D6-2's `_MOVABLE`. Fixed with the key **and** an
assertion that the coordinate reaches the file, which is what makes the key load-bearing; demonstrated
by restoring the old key and watching the new assertion fail on a missing `haplotypes.csv`.

## RM75 — a complete result is destroyed by an incidental failure, and one handler cannot see its own case

**Severity** medium · **Status** ✅ shipped · **Owner** enricher · **Found by** code review during the
0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-13, R2-4, R2-2

**A client that leaks its transport library's exception type has no contract** (R2-13). `CpicClient._get`
called `raise_for_status()` and wrapped only *shape* failures into `CpicError`, so once retries were
exhausted a raw `httpx.HTTPStatusError` walked through both of `enrich_pgx`'s per-leg handlers — the
handlers written under the comment *"One source failing must not sink the pass — the other may still
answer"* — and took PharmVar's answer with it. The retrying request is now `_request` and the
translating wrapper is `_get`, in that order, because wrapping *inside* the retry would defeat it:
`retry_if_exception_type` tests `httpx.HTTPStatusError`, and a `CpicError` raised there is a
first-and-final attempt. A test asserts the ladder survived the split, since a decorator on the wrong
half turns three attempts into one and nothing fails.

**The same hole was on the PharmVar leg and the ledger named only CPIC.** Repairing one and not the
other would make that comment true in one direction, so the guarantee would hold or not depending on
which source went down — worse than either state. `PharmVarClient` got the identical split; its 401
branch stays inside `_request`, because that is a *diagnosis* raised before the status check rather
than a translation of one, and it must not be retried.

**An optional message-enrichment call could discard a finished draft** (R2-4). `pgx_draft` asks
`cpic.knows_drug` inside the `try` whose `finally` closes the client — deliberately — but by then the
alleles, diplotypes, defining variants and every recommendation have already returned. `knows_drug`
exists only to tell a typo apart from a real drug CPIC scores in a shape this table cannot hold (F5),
so a transport failure there threw away complete work to improve a sentence about it: the gnomAD rule
(a per-item error must never sink a batch) in a different tier. It is caught now, and the `bool | None`
tri-state that was *designed and never delivered from the live client* is finally reachable from it.

**A third reading of "could not establish" earned its own sentence rather than reusing the second.**
`known is None` already meant "the snapshot's recommendation table cannot answer this", whose remedy is
to go live; a failed request is re-runnable. Folding them would put the snapshot's wording in front of
an author who has no snapshot.

**An ordinary mid-authoring state tracebacked** (R2-2). F1's repair routed `draft` and `draft-panel`
through `source_build_mismatch` → `spec_genome_build`, which deliberately raises `EnrichmentError` on a
present-but-unreadable `module_spec.yaml`. Neither CLI named that exception, so a spec carrying only
`name:` turned `draft-panel --gene PALB2 --offline` into a rich traceback where every other enricher
command exits with a message. The presentation regressed *because* the build defect was fixed, which is
the shape worth naming: a shared precondition added to three providers owes the same addition to each
of their handlers. `_DRAFT_PRECONDITION_ERRORS` is what makes the fourth provider inherit it instead of
rediscovering it.

**And the raise moved to the top of both providers.** It landed *after* `_resolve_snapshot` had
provisioned a published ClinVar snapshot and after every CPIC query, for a check that reads one file
beside the spec. The warning is still appended where it was, so no reported order moved.

## RM76 — an unfinished authoring state passes every gate, including `--strict`

**Severity** high · **Status** ✅ the narrow repair shipped; **the general question is
[RM73](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end)**
· **Owner** format + compiler · **Found by** the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-8

`SourceRow` is a plain `BaseModel`, not an `AuthoredModel`, deliberately and for a stated reason: it is
a machine-produced reference fact, grouped with `ResolutionRow`/`FrequencyRow`/`GeneMetricsRow`/
`LiteratureRow`. S21 then made it **draftable**, also deliberately, because it is *"the only fact
sidecar a human writes"* and the only table the compile licence gate reads. Nobody reconciled the two,
and the gap is exactly the shape of both decisions being right.

Re-probed on `reference_examples/hfe_hemochromatosis` with `source=<<REPLACE>>`: the module **compiles
green under `--strict`** and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]` inside the block
its own `signature` covers. The compiler's only remark on that file was that `sources.csv` is the
deprecated spelling.

**What shipped: the guard, on the model rather than through the base.** `ModuleSpecConfig` is the
precedent — standalone for its own reasons, carrying its own `reject_template_placeholders` all the
same — so the classification stays true and the other four sidecars stay out, since no template is ever
generated for them. It refuses in **both** modes, which is not a choice: a load error is fatal in both,
and it is what every other authored table already does with the same token.

**Why a vocabulary column was hiding it, and why that matters twice.** `layer` refuses `<<REPLACE>>` as
a non-member, so a stub in *that* cell was caught by accident; `source` is free text by design, and
free text is most of this table. The accident is also what made the **first draft of this item's own
test green on the unfixed code** — asserting "some error mentions `<<REPLACE>>`" is satisfied by the
vocabulary message quoting the token back. The test now asserts the guard's own wording, and a second
one isolates the real hole: a valid `layer` with only `source` stubbed. A guard green because a
different mechanism happens to fire is the S21 / D6-2 / R2-3 shape arriving inside the repair for one.

**And the guarantee is now asserted, which it never was.** `draft.stub_template`'s docstring prints
*"an unreplaced stub **cannot compile** — `vocab.reject_template_placeholders` refuses it by name and
row, in both modes"*, and nothing checked it; it held only where a model happened to inherit the right
base. The new test is parametrized over `DRAFTABLE` rather than naming kinds, because the defect was a
model quietly outside a set and a hand-written list would have to be extended by whoever forgot the
base class. One `test_hints` docstring stated the old behaviour as a reason and is corrected in place
rather than deleted — the correction is the useful part.

Nothing in the corpus moved: a `mode="before"` validator that only raises changes no accepted value,
verified against the `artifact.digest` / `content_signature` values recorded independently in
ROADMAP_0_7 and CLAUDE.md.

**What is not closed.** *"A generated stub must be unable to compile"* is now true and now tested, but
it is still a property that holds because each model was individually given the right guard. What marks
authoring as **unfinished** — as opposed to marking one token as unreplaced — reaches this from
underneath, and that is RM73's phase boundary — a sprout repaired a day before its root, which closed on
2026-08-16 with `just-dna-compiler close`. Note what the two do and do not cover between them: a closure
says the author declared *these bytes* final, and the guard here says one particular token cannot survive
into a compile. Neither says a cell is right, and neither is the other's substitute.

## RM77 — the genotype diagnosis tells the author about the wrong thing

**Severity** medium · **Status** ✅ shipped · **Owner** format · **Found by** the 0.6 dogfooding fix
round, 2026-08-14 · **Ledger** R2-9, R2-14

**A genotype pasted out of a VCF was refused without anyone naming allele indices** (R2-9). `GT` is
`0/1`; `genotype` wants the bases. Re-probed on all the spellings: `0/1` and `0|1` fell through to the
nucleotide-grammar wall — a sentence reciting what an allele may be (nucleotides, `*`, a symbolic
token whose first-level type is one of five) that never says the one thing that resolves the cell.
This is the single most likely mistake an author makes here, because pasting the `GT` field is the
obvious first guess.

`0/1/1` was **worse, and 0.6 made it worse**: the ploidy-message fix gave it a confident, correct
explanation of the two-allele ceiling, which is about the wrong thing — that cell's defect is the
notation, not how many alleles it names. A correct sentence aimed at the wrong defect is worse than a
generic one, because it sends the author to change the wrong cell. So the diagnosis runs **ahead of
the arity branch**, and a test pins that a genuinely polyploid call spelled in bases still gets the
ceiling explanation and this one does not.

The repair is CLAUDE.md's standing shape — a generic rejection is a dead end where a specific one is a
fix — and it **changes no verdict**: every cell it matches was already refused. `_GT_INDEX_CELL`
matches a cell whose every member is a digit run or VCF's no-call `.`, which nothing legal can look
like: `ALLELE_PATTERN` is `^[ACGT]+$`, a symbolic allele is bracketed, and `*` is one character. The
message names what to translate *against* (the record's own REF and ALT) and says those cannot be
resolved here, since a genotype cell carries neither. It reaches `PharmVariantRow` for free, because
the grammar has lived on `AuthoredModel` since 0.5 — pinned, since a diagnosis added to one arm of a
shared validator is the drift that move exists to prevent.

**RM63's correction was itself an overclaim, and it is the third turn of one screw** (R2-14). The
comment read *"Read a pipe here as **heterozygous**, phase recorded but unaddressable"*. Probed:
`VariantRow(genotype="C|C")` loads, and `1|1` is an ordinary phased homozygous call, so the sentence
was false of a genotype the model accepts. The history is the finding — the original comment claimed a
pipe encodes which homolog an allele sits on; RM63 refuted that correctly and replaced it with an
unchecked claim about *zygosity*; the 0.6 unit carrying the wording onto the printed `describe` output
dropped the zygosity word and kept the true half, so the **printed contract has been right since then
and only its source was wrong.** A correction is exactly where this happens: the reviewer checks the
claim being removed, not the one going in. The comment now says only what RM63 established, keeps the
history of both wrong versions, and a test pins that `C|C` loads so there is no fourth turn.

## RM78, the two fixes — the unobservable marker, and a guard that answered its own question wrong

**Severity** medium · **Status** ✅ both fixes shipped; **the R2-5 decision stays open in
[ROADMAP.md](ROADMAP.md)** · **Owner** format + compiler · **Found by** the 0.6 dogfooding fix round,
2026-08-14 · **Ledger** R2-6, R2-10

**`*` landed in the compiler's indel bucket** (R2-6). 0.6 gave the symbolic class its own permanent
reason in `_vrs_gap_reason` and `_recompute_vrs_id` and guarded `*` and `.` on the *enricher* side, and
neither compiler function was told — so an unobservable allele in `resolution.csv`'s `alts` was
reported as *"an indel or MNV … re-run it online"*: the same false class D1-2 had just fixed for
symbolic alleles, one axis over, offering a remedy that can never apply.

**Filed as having no instantiation and upgraded when it turned out to have one.** The reasoning was
that nothing writes a `*` there today; the unit fixing D1-1 then probed `LiteralSequenceExpression`'s
pattern — `^[A-Z*\-]*$` — and found `*` **passes**, so before the enricher guard an unobservable allele
reaching the minter would have been normalized and handed a content-addressed id for a state that is
not a sequence. *"Nothing produces it today"* is a fact about the wiring, never about the function:
RM38 and `VALID_RSID_STATUS.withdrawn` already carry the same lesson.

Three classes now, not two, and the split is P5's rather than a convenience: `parse_symbolic_allele`
asks *which variant is this, unspelled*, and `is_unobservable_allele` asks *whether the call could see
an allele at all* — the callability axis. **Severity could not have caught this**, which is why the
test asserts the reason: the indel branch it fell into is also tier-blame, so the verify matrix read
`warn` before the fix and after it.

**`refget_supports_build` answered `True` for the two inputs `refget_accession` raises on** (R2-10).
Its docstring says it is *"the question `refget_accession` raises on"*; for `GRCh37` the two agreed and
for `None` and `""` they did not. Latent, because the one caller filters `if row.genome_build` first —
but it is public in the schema tier and it is the guard a caller reaches for *precisely* to avoid that
exception, so the first caller handing over an unset build got what the guard exists to prevent. Same
class as the `start` docstring: a printed claim the code does not honour, in the tier the other two
build on.

**Which side moved, and why that was the real question.** The old reasoning was *"an unset build is the
format's default, not an unbuilt assembly"* — which imports a fact about the **spec** layer into the
**identity** layer. `ModuleSpecConfig.genome_build` does default to GRCh38, and so does each of these
functions' own *signature*; but an explicitly passed `None` is not an omitted argument, it is a caller
who has not threaded the row's build through — the bug class `test_build_call_sites.py` walks the AST
to prevent. Every other build gate in `vrs` (`in_pseudoautosomal_region`, `par_partner`,
`contig_length`, both minting functions) already withholds on anything that is not literally `GRCh38`,
so answering `True` made this one function the outlier rather than the rule. Both now read one
predicate, so RM15's second table cannot re-open the gap.

## RM78, the decision — a stored VRS id against a symbolic allele is the row's contradiction

**Severity** medium · **Status** ✅ decided and shipped 2026-08-15 · **Owner** format + compiler ·
**Ledger** R2-5

`_recompute_vrs_id` returned **tier-blame** — a warning in both modes — for a symbolic allele carrying
a `ga4gh:VA.…`. Tier-blame exists for a finding **no authored edit could clear** (P5, the rule that
also keeps `not_covered` and the coverage warnings out of the `strict` gate), and deleting the cell
clears this one. So the finding was filed in the class whose own test it fails.

**Decided: escalate to row-blame — an error in both modes — but settle the grammar first.** That order
was the point. The escalation only follows if a present id can *only* be a VA minted for a different
allele, and nothing had established that: `vrs_id` was validated for well-formedness alone
(`ga4gh:<TYPE>.<digest>`, five types), while its description says *"GA4GH VRS allele id
(`ga4gh:VA.…`)"*. Changing severity before answering that would have been a verdict resting on a
premise the schema did not state.

**The grammar step.** `validate_vrs_allele_id` makes `ResolutionRow.vrs_id` and `FrequencyRow.vrs_id`
`ga4gh:VA.`-only, and names the type it got when refusing. Three things about it:

- **It makes no passing module fail.** A `ga4gh:SL.…` already reached `_verify_vrs_ids`, which
  recomputes with `derive_vrs_allele_id` (always a VA), and was reported as a **mismatch** —
  *"recomputed and different, so corruption"* — an error in both modes with the wrong explanation. The
  tightening moves a confident wrong diagnosis to load time.
- **No instantiation**, which is the test this repo applies to a tightening (the IUPAC probe is the
  precedent): nothing mints a non-VA into either column, and a probe across all sixteen reference
  examples found **844 ids, every one `ga4gh:VA.`, zero of the other four types**.
- **`validate_vrs_id` keeps its lenience and its documented reason.** What was wrong was using a
  *format* check where a *column* rule was meant — "is this a well-formed VRS id" and "may this column
  hold one" are different questions, and only the first should be generous.

**The escalation.** With the column VA-only, a recorded id on a symbolic row can only be a VA for some
other allele: a false content-addressed claim, catchable offline, the same class as *inconsistent
reference allele* and *an id recorded against no ALT*. The message says which cell to delete and that
the allele keeps its identity through `variant_key`, so the remedy is one edit and loses nothing.

**The asymmetry that must not be flattened, and it is now pinned by a test.** The *coverage* side
(`_vrs_gap_reason`, `_vrs_coverage_warnings`) still reports a symbolic allele as a permanent gap and
**warns in both modes**. An absent id there is the ordinary, correct state — no tier can mint one — so
refusing would make every structural module uncompilable for a reason no edit could fix, which is the
P5 class this whole item is about. *Absence is a limit; a claim is a claim.* `mt_common_deletion`,
`cyp2d6_structural` and `pathogenic_clinvar` still compile under `--strict`.

## RM79 — two honest counters disagreed, so the compiler stopped carrying the dead weight

**Severity** low · **Status** ✅ shipped 2026-08-15 · **Owner** compiler · **Found by** the 0.6
dogfooding fix round, 2026-08-14 · **Ledger** R2-16

`manifest.literature.missing_count` counted `exists is False` over **every row in `literature.csv`**;
the `citation_existence` verification record counted over the citations the module makes **now**.
`literature.csv` is merge-not-clobber, so it keeps a row for a citation since deleted from
`studies.csv`, and the two numbers then disagreed in a published manifest with nothing wrong in the
module. Each was right about its own subject, which is what made it a decision rather than a repair.

**What the item asked was the wrong question, and probing showed why.** It framed the choice as
*should `manifest.literature` describe the table it is named after, or the module's current
citations?* — and both blocks already publish their own denominator (`row_count`, `subjects`), so a
reader could in principle reconcile them. The thing nobody had decided was upstream of the counting:
**why is a row nothing joins to in the artifact at all?**

**Decided: the compiler discards it, and `literature.csv` keeps it.** A literature row for a citation
no study and no bin names is dead weight — nothing in the module references it, and it is present only
as a side effect of merge-not-clobber. That rule is right and stays: the CSV is the pin that makes a
re-run cheap. Carrying the row onward into `literature.parquet` and `manifest.literature` was a
separate thing nobody had chosen. `split_cited_literature` is the one rule both the check and the
materializer read.

The counters then agree **by construction** rather than by documentation, which is the part worth
having: no reader has to reconcile two numbers, because there is only one subject.

Four things to keep straight:

- **The check sees every row; everything after it sees the kept ones.** Reporting what was dropped
  needs the full list, so the split happens after the cross-check rather than at load — and the
  warning now reports an *action taken* ("left out of the artifact, and left in the CSV") instead of
  nagging about a file the author is not expected to tidy.
- **An empty citation set discards nothing**, and that guard is not the degenerate case it looks like:
  a module citing nothing at all cannot tell "the sidecar is stale" from "the citations are not
  authored yet", and emptying the table on the first reading would delete a whole enrichment pass's
  output. The orphan check already had the guard; the filter inherits it rather than re-deriving it.
- **Both citation sites count** (RM47), and the stakes went up. Blind to bin `pmid`s the compiler used
  to *warn* about a threshold-grounding citation; it would now **discard** the row that evidence lives
  in. `test_citation_sites` pins the split against both sites for that reason.
- **The round trip narrows once and converges.** `reverse_module` rebuilds `literature.csv` from the
  parquet, so a reversed copy carries the kept rows only — a deterministic narrowing of a
  machine-written derived sidecar rather than a P7 breach (the RM69 reading of the principle's letter),
  and lap two discards nothing, so the signature is a fixed point. Pinned by a test, because a
  narrowing that kept narrowing would be a defect whatever the sidecar's status.

Nothing in the corpus moved: no reference example carries an uncited literature row, verified by
recompiling all sixteen. Which also means the corpus cannot exercise this — the standing
corpus-uniformity trap — so the behaviour is pinned by fixtures rather than by an example.

## RM73 (phase boundary) — authoring is a process, and it now has an end

✅ **Shipped in 0.6.0** (2026-08-16), completing the item; the provenance half below shipped the same
day. What remains of RM73 is not a half but a **promotion**: making a closure a *precondition* of
compiling is major-only under P8, it is filed in
[ROADMAP_1_0 § RM73 (gate half)](ROADMAP_1_0.md#rm73-gate-half--the-closure-gate-refuses-on-step-3-of-the-round-trip),
and it is **blocked** there for a reason found while building this — see the last section.

**What was missing was one sentence's worth of state.** RM45 had already built almost all of it for a
different purpose: `verification.json` binds `module_hash` over the authored files, the compiler
recomputes that binding on every compile, and a mismatch drops the whole block with a warning. So
change-evidence over the authored set had been shipping since 0.6 — what nobody had is a record saying
*a human declared this finished*, because the document was written as a **side effect of a pass
running** and therefore only ever said "the enricher ran".

**What shipped: `Closure`, `just-dna-compiler close`, and a warning.** `VerificationDoc.closure` is an
optional block (`closed_at`, `closed_by?`, `signature?`), `close_module` writes it, and both
`validate_spec` and `compile_module` report a module that carries none. Five decisions worth keeping:

- **No new file, no new binding, no new proof-of-work.** The closure rides the attestation, so an edit
  after closing un-closes the module for free; a free-standing `closure.json` would need its own
  staleness rule and would be dropped silently by `reverse` (the RM51 class). It sits **outside**
  `pow_digest`'s payload, so closing re-mines nothing and every attestation written before 0.6 still
  verifies. Measured: all sixteen reference examples compile to a byte-identical `artifact.digest` and
  `content_signature` before and after being closed.
- **Deliberate, never a side effect.** `validate` stays read-only however cleanly it passes, because a
  mark left by whatever happened to run reproduces the exact defect this item levels at
  `verification.json`. `--private-key` signs the closure over `module_hash` with the same
  `signing.sign_digest` the artifact signature uses, which turns *someone closed this* into *this
  party closed this*. Unsigned stays legal and still change-evident — tamper-*evidence* was always the
  guarantee on offer.
- **Refuses an invalid spec; does not refuse on a warning.** Declaring finished a set the compiler will
  not accept is a contradiction. Declaring finished one that carries an unresolvable rsID or an
  ungrounded threshold is ordinary, and refusing there would make closure unreachable for exactly the
  modules whose findings no authored edit can clear (P5, the `not_covered` class).
- **The enricher's merge had to learn it, and this is the never-clobber trap a third time.**
  `record_verification` rebuilds the document rather than editing it, so it dropped the new field by
  default — silently, and in the wrong direction, since enrichment writes only derived sidecars and the
  ordinary case is a closed module staying closed. It now carries the closure across **only while the
  binding holds**, and drops rather than re-binds it otherwise: re-stamping would have the machine
  assert on the author's behalf. Same shape as `SourceRow.dataset` and `draft_digest`, one column over.
- **Absence warns; a false claim drops the block.** No closure is the state every module was in before
  0.6, so it is a warning in both modes, never `strict`-gated (an unclosed module is perfectly
  reproducible). A closure that is *signed* and whose signature does not verify drops the whole
  document — absence is a limit, a claim is a claim.
- **Closing adds a block to the document; it does not rebuild one.** The first version re-attested,
  which rewrote `producer` from `just-dna-enricher 0.6.0` to `just-dna-compiler 0.6.0` on the three
  reference examples that carry real check records — a field naming who put the *checks*, so the
  compiler was claiming an enricher's cross-checks as a side effect of an unrelated act. Found by
  reading the corpus diff rather than by a test, and now pinned by one. Keeping the document verbatim
  is also what makes *closing re-mines nothing* literally true rather than nearly so.

**Whether compile should warn on absence was decided twice, and the second answer was right.** The
first analysis argued for silence, on the grounds that `reverse` cannot re-emit the document, so a
closed module's `compile → reverse → compile` warns on step 3 where step 1 was silent — and RM44 made
`manifest.compilation.warnings` a surface consumers parse. That was overturned by two facts. The
divergence **costs nothing enforceable**: `artifact_digest` is a Merkle root over `_OUTPUT_FILES`,
which is parquet only, `manifest.json` is not in it, warnings feed no signature, and no round-trip test
compares them. And with no warning, the closure has **no consumer in 0.x at all** — the manifest field
would be read by a catalog that does not exist yet and by nothing else until 1.0, which is the
designed-and-never-delivered shape that let the `knows_drug` raise escape. So the corpus was closed
instead: all sixteen reference examples ship a closure, with a test asserting each one is still current
so an authored edit fails loudly rather than degrading into a *stale* warning nobody reads.

**And that probe is what blocks 1.0.** Warnings being free is a fact about warnings; a **refusal** is
not free. Under the planned gate, a reversed spec is unclosed by construction — reverse rebuilds from
parquet and the document is not there — so `compile → reverse → compile` would refuse on step 3 for
every module, and P7's round trip is enforced by tests. The obvious repair is closed too:
`manifest.verification` carries the records but not `difficulty`/`nonce`, so reverse cannot rebuild a
valid document from the artifact it holds. Three candidate answers are recorded, undecided, in
ROADMAP_1_0 — and the reason this was worth writing down rather than discovering later is that
`verification.json` has carried the identical asymmetry since RM45 without consequence, so the
precedent is silent about the danger.

---

## RM73 (provenance half) — a drafted value that has not moved is a copy that can be *established*

✅ **Shipped in 0.6.0** (2026-08-16), alongside the phase boundary above; this is the half the sprouts
were actually asking for, and it landed first because it needed no phase boundary to answer.

**The problem, restated at the size that shipped.** RM4's tautology skip exists because a panel
drafted from ClinVar carries ClinVar's own `clin_sig`, so the cross-check compares a value against
itself and reports a zero that *looks like evidence*. The skip was keyed on a module-level marker (the
release stamped into the licence row) because that was the finest grain available, and RM4 named the
hole in its own warning text: a cell edited after the draft is no longer a copy, and no module-level
fact can see it. The expensive repair — `strict` looking every row up — is the validation-by-
duplication route this item had already argued against.

**What shipped: one digest per drafting source, over the projection the check actually reads.**
`enricher/provenance.py` holds three entries — `clinvar`/`variants.csv`/`clin_sig`,
`cpic`/`allele_function.csv`/`function_status`, `clinpgx`/`pharm_variants.csv`/`evidence_level` —
each naming the table, the identity cells and the checked cell together. The provider hashes it and
stamps `SourceRow.draft_digest`; the check recomputes it and compares. Six things worth keeping:

- **The projection is a COLUMN, not a row, and that is what makes it work at all.** A
  `clinvar_draft` module always has edited rows by construction — `genotype` is a placeholder the
  human is *required* to fill — so a whole-row hash is invalidated on every drafted module and the
  skip would never fire once. Scoping to the checked column makes the digest exactly as sensitive as
  the question: filling a stub does not disturb it, editing a `clin_sig` does. Pinned by a test.
- **Raw CSV cells, never loaded models — forced, not stylistic.** One function serves both sides,
  because a writer and a reader that computed this differently would not fail, they would silently
  never match (`clinvar_dataset_label`'s lesson). That function must therefore run at *draft* time,
  when the table is full of `<<REPLACE>>` and `reject_template_placeholders` refuses to load it by
  design. So `variant_key` and `effective_clin_sig` are unavailable and the identity is spelled as
  the raw cells the provider already matches on.
- **The skip is a CONJUNCTION, and shipping only the digest half would have been wrong.** The digest
  hashes the module's table, not the snapshot, so it is silent about currency: a matching digest
  against a *newer* release is a real comparison. Skip requires the recorded release to match **and**
  the digest to match. A consequence worth stating: a check run against a **live** source never
  skips, because there is no release to name.
- **`merge_sources_file` would have eaten it.** Never-clobber is right for terms a curator may have
  hand-written and wrong for a machine-stamped cell that must track the table — the same rule that
  bit `dataset` and produced `withdraw_stale_dataset`, arriving on the neighbouring column one
  release later. `stamp_draft_digest` restamps explicitly. Unlike `dataset` it **re-labels rather
  than withdraws**: a release label cannot name two releases, so a mixed module has no honest value,
  while a digest describes the table as it now stands whatever produced it.
- **Two unmarked tautologies closed, neither previously filed.** `pgx_draft` writes `function_status`
  out of CPIC and `pgx._function_conflicts` compares that column against CPIC; `clinpgx_draft` writes
  `evidence_level` out of ClinPGx and `clinpgx` compares that column against ClinPGx. Both were
  publishing a structurally guaranteed `findings=0` into `verification.json` — RM4's misinformation,
  now inside RM45's proof-of-worked attestation, which is a stronger claim than a warning line. CPIC
  was additionally the one provider recording **no `dataset` at all**, so it now stamps one.
- **In `enrich_pgx` the tautology is a PER-LEG outcome.** That check has two authorities: on a
  CPIC-drafted module the CPIC leg cannot fail while PharmVar's is genuinely independent. The
  existing `legs` dict already carried one outcome per authority, so the CPIC leg records `tautology`
  and PharmVar still runs. A whole-record skip would have discarded a real comparison to suppress a
  hollow one — precisely the expressiveness the module-level marker shape lacked. `tautology` sits
  **last** in `_SKIP_PRECEDENCE`: the other members say the source could not be consulted, and an
  absence a reader can act on outranks a comparison that could not have failed.

**The removal, which is the point as much as the addition.** `ClinSigAudit` and the
copied/authored/no_record bucketing are gone, with `EnrichmentResult.clin_sig_audit`, its CLI line
and the `mode != "strict"` branch in `enrich()`. The bucketing existed for exactly one reason — the
module-level marker could not see a per-row edit, so `strict` paid for a lookup to recover the split
— and the digest answers that offline. **The mode ladder collapsed with it**: this check now behaves
identically in both modes, which is what RM4 wanted and could not have, and `strict` stops meaning
"pay for a per-row lookup", which was never a reproducibility axis (P5). Removing it changed no
verdict: the `copied` bucket was an early exit taken *before* the camp logic, and an exact match
agrees with itself, so every row it caught already reached "no conflict" by the path below it.

**The honest limit, stated rather than discovered.** The digest covers the whole table, so it means
*no checked value has changed since the drafter last wrote*. A row hand-authored **before** a
subsequent re-draft is covered by the new stamp and escapes the check. Strictly narrower than what it
replaces — today's module-level marker lets *every* hand-edit escape — and unlike today any later
edit re-enables the check in full.

**Behaviour change worth reading twice.** A licence row naming the right release but carrying no
digest **no longer skips**. Nothing that was being checked stopped being checked; a module that was
being waved through on a claim is now examined. Its test says so by name.

**Identity effect, measured.** `draft_digest` is deliberately **outside** `SOURCE_FACT_FIELDS` —
`dataset` is inside it because which release these annotations came from is part of the claim the row
makes about the source, while this is a fact about how the module was *built* and moves on every
re-draft. So `sources.signature` moves nowhere, and `content_signature` is untouched
(`pgx_slco1b1_simvastatin` still `sha256:8173dab7…`). A recompile's `artifact.digest` moves for any
module carrying a licence table, since `sources.parquet` gains a column — the additive case P4 scopes
to a fixed `compiler_version`.

## RM80 — `annotations.parquet` had no column for the thing that distinguishes its rows

✅ **Shipped in 0.6.0** (2026-08-16), retro-filed. **Reported by a downstream consumer**, whose note
is the cleanest statement of it: `variant_key` is not unique in that table, so every consumer must
dedup before joining — *either the table should be unique per `variant_key`, or it should carry the
genotype that distinguishes its rows.*

The first option is impossible and the reason is already recorded here: a genuine poly-effect variant
is one locus carrying two annotations, which is why the table was re-keyed on the variant-effect pair
`(variant_key, conclusion, negatives)` in the first place. So the answer is the second — except that
the authored column which decides *which call an annotation applies to* was in no column at all. A
het "carrier" row and a hom "affected" row at one locus could be told apart only by reading the prose
in `conclusion`.

**Carrying it without keying on it would have been worse than the gap**, which is why this is one
change and not two. Two genotypes sharing a conclusion (`C/T` and `T/T` both "carrier") collapse under
the old key, so the surviving row would name one genotype while silently standing for both, and a
consumer filtering on it gets a *wrong* answer instead of a missing one. With `genotype` in the key
the dedup is provably a no-op — `(variant_key, genotype)` is `VariantRow`'s own natural key and
`_cross_validate_variants` rejects duplicates on it — so the table is now exactly one row per authored
variant row. The dedup is kept anyway rather than deleted, because the function must not silently
depend on a guarantee another function enforces.

Two mechanics. Reverse now reads **which** generation of the table an artifact carries
(`ann_key_columns`, derived from the columns present) instead of one bool — three keyings are in the
wild and the old two-branch detection could not express a third; both legacy branches are preserved
exactly. And the genotype reconstruction had to move **above** the annotation probe, because
`weights.parquet` stores the allele list plus a `phased` bit rather than the authored cell, so the
string has to be rebuilt before it can be joined on.

A parquet column is ~free under the 2026-08-13 charter amendment (materialized, derived, no human
types one), which is what makes this a minor rather than a deferral. `content_signature` does not
move; a recompile's `artifact.digest` does, for any module carrying `variants.csv`.

# 0.6 — what answering S35 closed

One item, and it is the shape the triage loop exists to produce: an entry filed with a genuinely open
question, the consumer answering it the next day, and building the answer finding a defect underneath
that neither side had stated. Filed 2026-08-17, closed 2026-08-17.

## RM89 — the publisher cannot upload a table-only module at all

✅ **Shipped in `just-dna-compiler` + `just-dna-enricher` 0.6.0** (2026-08-17), the day after it was
filed, unblocked by [S35](CONSUMER_SUGGESTIONS_HISTORY.md) from just-dna-lite. **Owner** enricher
(`upload._REQUIRED` / `_ALLOW_PATTERNS`) + compiler (a public name) · **Motivating case** seven of the
sixteen reference examples

`upload._REQUIRED` was `("weights.parquet", "annotations.parquet", "studies.parquet")` and `plan_upload`
raised `FileNotFoundError` when any was absent. The comment above it said *"weights/annotations/studies
are what discovery needs"*, and that premise expired when RM2 made the SNP core optional in 0.4: a
module carries only the table kinds it uses, so a module with no `variants.csv` produces none of the
three and could not be published by this tier at all. `fmr1_cgg_repeat` was the instructive one — it has
`studies.parquet` and lacks the other two, so the rule was *"not all three"*, not *"no SNP core"*, and
the obvious repair (**exempt a module with no `variants.csv`**) would still have refused it. Same class
as RM55's `_INTEGER_KINDS`: a rule whose premise the format withdrew, left standing.

**The open question was genuinely open, and it was not ours to answer.** Whether the required set should
become *"`manifest.json` plus at least one parquet"* or drop the parquet requirement entirely depends on
what the consuming discovery path actually opens. It was asked of just-dna-lite alongside RM84's two
questions rather than guessed. Their answer: `_find_lead_table` probes `{base}/{family}.parquet` across
ten lead families and returns the first hit — that single existence probe **is** their "is this a
module" test — and `manifest.json` is not opened by discovery at any point. So of the two candidates,
manifest-plus-at-least-one-parquet is the one a consumer can use.

### What answering it found, and it is larger than the item

**`_REQUIRED` was not the only gate.** The allowlist handed to `upload_folder` was `*_REQUIRED` plus
`manifest.json`, the two logo spellings and `README_CANDIDATES` — so **not one 0.4 family and not one
derived-fact table was in it**. Relaxing `_REQUIRED` alone would have converted *"a table-only module
cannot be published"* into *"a table-only module publishes as `manifest.json` + README with no data"*,
which is a worse failure because it is silent and leaves a directory behind. just-dna-lite found this
half from the other end: `sources.parquet` is not in the allowlist and they read it, so a module
published through this tier arrived with its licence terms missing and their report footer rendered
*"Not stated"* — correct for what they received, and the derivative-work obligation gone with the bytes.

**The consequence neither side had stated, found by probing rather than by reading.**
`manifest.artifact.files` lists a name, a sha256 and a size per parquet, and `artifact.digest` is a
Merkle root over exactly those — so a file attested and not uploaded makes the published manifest a
false claim about bytes that are not there, and the digest cannot be reproduced from what arrives.
Measured over the sixteen reference examples, compiled and run through `plan_upload`: **seven refused
outright, and eight of the remaining nine published an artifact whose own digest did not verify**
(`hboc_palb2` dropped six parquets). Only `grch37_build` — a bare SNP core with no sidecar and no
0.4-family table — was correct. Fifteen of sixteen, on a surface where the failure is silent. Stated
honestly: nothing is known to have been published through it, so this is *would publish*, never *has
published*.

### What was built

**The allowlist is derived, never hand-kept.** `_OUTPUT_FILES` became public as
`compiler.ARTIFACT_PARQUETS` and the publisher imports it, so a new table family reaches the publisher
in the commit that adds it. This is `@fieldnames-from-model` one tier further out, and it is the
property the consumer explicitly asked to have preserved from their own shipped version of this fix.
`LEAD_PARQUETS` is the companion — `weights` plus the nine 0.4 families, matching what their
`_find_lead_table` probes.

**Three positive rules replace the required triple**, ordered most specific first so a refusal names the
actual fault (`@specific-rejection`): the plan must carry every file `manifest.artifact.files` attests;
`weights.parquet` never travels alone (the consumer's `_EXPECTED_WITH_WEIGHTS`, kept and scoped exactly
as they scoped it, since a `pharm_variants`-led module legitimately has neither companion); and at least
one **lead** parquet must be present. A positive rule rather than a deleted constant was the shape both
sides wanted independently — the risk here runs toward letting a half-compiled directory upload, not
toward refusing too much.

**The first rule is a self-check as much as a module check**, which is why it earns its place on top of
a derived allowlist: it compares what would be sent against what the artifact says it contains, so the
two cannot drift apart silently a second time. And an absent or unreadable `manifest.json` **withholds**
rather than refusing — the same tri-state as RM84's `version_unknown_reason`, and what keeps that item's
four reasons four reasons rather than one refusal.

Re-measured after: **16 of 16 publish, and all 16 digests verify** against exactly what would be sent.
Nothing that published before stops publishing; the only new refusals are the two shapes that were never
a publishable module.

# 0.6 — what S36 closed: weights declare a scale, and a study names its allele

Three items from one consumer report about authored `weight` values. Anton Kulaga's note is field
feedback rather than a bug: the column declares no scale, every module means something different by
it, and published GWAS effects often beat hand-set curator weights. Triaging it found a fourth thing
nobody had measured — `weight` is authored **zero times** in this repo — and one thing the report
asked for that is barred outright. Filed and closed 2026-08-17.

## RM91 — a study states an effect magnitude relative to no allele

✅ **Shipped in `just-dna-format` + `just-dna-compiler` 0.6.0** (2026-08-17). **Owner** format (schema +
compiler) · **Motivating case** [S36](CONSUMER_SUGGESTIONS_HISTORY.md), found while checking whether a
GWAS effect could be carried on `studies.csv` at all.

`VariantRow` has carried `effect_allele` since 0.3 for a stated reason — `ref`/`alts` plus the sign of
the magnitude cannot recover which allele the claim is about — and `_check_allele_membership`'s own
message says naming the wrong one *inverts* the conclusion rather than breaking it. `StudyRow` has
carried `effect_size` + `effect_measure` since the same release and had **no such column**, so every
study row in the format stated a magnitude relative to nothing. The existing check iterates `variants`
only, and there was no field on a study row for it to examine even if it had.

**What landed.** One optional column, plus the check that makes it load-bearing:

- `StudyRow.effect_allele`, worded from `VariantRow`'s, and `StudyRow.ALLELE_COLUMNS =
  ("effect_allele",)`. **The omission of `ref` from that tuple is the design, not an oversight**:
  `AuthoredModel.ALLELE_COLUMNS` says *sequence columns that are the claim, never a column that merely
  points at a variant*, and names `StudyRow.ref` as its own example of the second kind.
- `_check_study_effect_alleles`, on the same mode ladder as the variant-side check — warning in
  `best_effort`, error in `strict` — and registered in **both** `validate_spec` and `compile_module`,
  since a mode ladder left compile-only is exactly the defect the 2026-08-07 audit fixed for
  `_verify_vrs_ids` and `_check_p_value_num` (`@parity-by-check`).
- **It reads resolved evidence only and withholds on everything else.** A `StudyRow` has `ref` without
  `alts` — `ref` is there so a position-only row keeps an identifier — so the authored branch has
  nothing to compare, and `{ref}` alone would flag every study of a non-reference allele, which is most
  of them. A row whose key reaches no `resolution.csv` entry is skipped rather than reported:
  unresolvable is unknown, and the house algebra withholds on unknown instead of negating it. A row
  naming no variant at all (legal since RM47) derives no key and is skipped by the same path.
- `_allele_verdict`'s resolved half was **factored out** as `_resolved_allele_verdict(call,
  variant_key, table)` rather than copied. A `StudyRow` has no `alts` and no `variant_key` column, so
  it cannot be passed to the row-shaped predicate; two implementations of "can this locus host that
  call" is precisely the drift `_allele_verdict`'s docstring already records, where membership and
  resolution disagreed the moment one indel was spelled two ways.

**Measured, and the prediction held exactly.** `artifact.digest` moved on **10 of 16** reference
examples — precisely the ten carrying a `studies.parquet`, since the column changes that schema — and
`content_signature` moved on **none of the sixteen**, because `exclude_none=True` omits an unset
optional column. That is what makes it minor-legal under P3 rather than merely additive-looking.

The reverse writer's hand-kept `fieldnames` list is the third of `@three-touch-points` and the one that
gets missed; the round-trip test was **watched failing** with only that entry removed, which raises
`dict contains fields not in fieldnames` at the reverse step rather than at the recompile.

## RM92 — the one magnitude in the format with no unit beside it

✅ **Shipped in `just-dna-format` + `just-dna-compiler` 0.6.0** (2026-08-17). **Owner** format (schema +
compiler) · **Motivating case** [S36](CONSUMER_SUGGESTIONS_HISTORY.md), which is a report about exactly
this and nothing else.

`effect_size` has `effect_measure` beside it. `VariantRow.weight` is a bare `float | None` described
only as "Score (positive=protective)", with no unit column anywhere, no statement of range, and nothing
saying whether two modules' weights are on one scale. The reporter's summary of living with that across
a corpus: the weights "construct nonsense", and *de facto* every module has a different methodology.
The 1.0 tracker had already called `weight` "module-local" — but nothing in the **artifact** said so,
so consumers combined across modules anyway.

**Measured while triaging, and it reframed the item.** `weight` is authored **zero times** in this
repo. Nine of the sixteen reference examples carry a `variants.csv`; four carry a `weight` column
(`hboc_palb2` 16 rows, `hfe_hemochromatosis` 13, `par_boundary` 3, `shox_par1` 10) and **every cell is
blank**; the other five have no such column. The column has never been dogfooded here, which is worth
recording beside the 1.0 review of whether `weight` survives at all.

**What landed.** `Weighting` on `ModuleSpecConfig` and copied to `ModuleManifest` — `scale`, `method`,
`note`, three optional strings, `extra="forbid"`. Advisory exactly like `license`: out of
`artifact.digest`, out of `content_signature`, dropped by `reverse_module`.

**All three fields are free text, and the field the block does *not* have is the design.** A closed
vocabulary would enumerate scales nobody has surveyed, against P5's one-way-door rule. More to the
point, the block deliberately carries **no precedence rule** — nothing saying "use the GWAS effect
where `weight` is null". That was the reporter's own first suggestion and it is refused: a per-row
precedence rule puts two methodologies in one summable column, which is the defect being reported, and
it leaves the module with no single scale left to declare. The module states what its weights *are*;
a consumer picks a table wholesale rather than blending row by row.

**`measure_tiling` is the nearest precedent and it is a column, not a yaml key** — worth stating,
because "flag it like the binning kinds do" is the obvious move and it is the wrong one here.
`measure_tiling` is per-row on `MeasureBinRow` and constant within a bin group; a weighting
methodology is module-wide, and repeating it on every row is exactly the authoring burden the
human-authorable gate exists to price. What *did* transfer is the shape of its resolution: declared →
inferred → default, with the evidence returned beside the value.

**Corpus movement: none.** No digest and no signature moved anywhere, because no example adopted the
block in this commit. The cost lands on the module that *does* adopt it: `module_spec.yaml` is
byte-hashed into `manifest.inputs[0]` and the RM45 attestation binds the same set, so adopting the
block stales an existing `verification.json` and the module must be re-closed. Pinned by a test.

One gap closed in passing: `license`, `panel` and `authorship` are all documented as dropped by
`reverse_module` and **none of them was asserted anywhere**, so the round trip could have started
re-emitting one with no test noticing. `weighting`'s reverse-drop is pinned.

## RM90 — GWAS effect sizes as a derived fact table, because they may not go in `weight`

✅ **Shipped in all three packages, 0.6.0** (2026-08-17). **Owner** format (schema) + compiler (the
seventh fact table) + enricher (the Catalog pass) · **Motivating case**
[S36](CONSUMER_SUGGESTIONS_HISTORY.md), whose reporter asked for the one thing this does not do.

The ask was: have the enricher procure GWAS effects and fill `weight` where the authored cell is null.
Barred, twice over — `MODULE_LIFECYCLE` § Stage 3 names `weight`/`direction`/`effect_size` in the cells
no tool fills, and Stage 5 says every check reports rather than repairs. A null `weight` means *the
author has not modelled this*, which is the house algebra rather than a hole to backfill. There is
also a sign trap in the middle of it: `weight` is documented positive=protective while a GWAS beta is
positive on the effect allele, so a silent fill inverts the claim on exactly the rows nobody re-reads.

So the effect goes in its own table — the third category the compiler already names, *"machine-produced
reference-fact table … injected, fact-hashed, human-overridable"* — and `weights.parquet.weight` stays
100% authored. A module carrying both holds an authored opinion **and** a machine-transcribed reference
fact, which is exactly what it already does with `frequencies` and `gene_metrics`.

### The model was shaped by the real payload, and the download TSV would have got it wrong

Probed on 2026-08-17 against `rest/api/singleNucleotidePolymorphisms/{rsid}/associations`:

- **`orPerCopyNum` and `betaNum` are separate, mutually exclusive keys** — not the download file's
  single ambiguous "OR or BETA" column — so `effect_size` + `effect_measure` maps exactly.
- **`betaUnit` is free text and frequently uninterpretable.** This is the column the table exists for:
  a magnitude without its unit reproduces S36's defect one layer down. It is inside the fact hash.
- **`betaDirection` is increase/decrease, about the measured trait**, and is deliberately not folded
  into `direction` (protective|risk|neutral|unknown). Increasing HDL and increasing LDL are both
  `increase`; one field carrying both axes is the P5 overloading `state` is being unwound for.
- **`riskAlleleName` is `rs4149056-?` when the study never established the allele.** Parsed to `None`,
  never a guess, and the row is **kept and counted** rather than dropped — it is real evidence that
  cannot be used as a weight, and a consumer that silently dropped such rows and one that silently
  kept them would both be wrong invisibly.
- The row carries **no coordinates**: the association payload has none, and one copied from the
  module's own `resolution.csv` would be the module's fact rather than the source's.

`rsid` is **inside** `GWAS_FACT_FIELDS`, which inverts `CLINICAL_ASSERTION_FACT_FIELDS` on purpose:
there the rsID is filled from the module's resolution because the archive returns none, here the
Catalog is queried by it and echoes it back. Copying the newer precedent because it is newer would
have been the wrong reading of it.

### Running it against a real module broke it twice, and both would have shipped green

Neither failure was reachable from a recorded fixture, which is the argument for the probe:

1. **A 404 is the empty answer, not an outage.** The Catalog holds only variants with a published
   association, so it 404s on a rare clinical one. The pass read that as a transport failure and died
   on `rs111033563` — the **first** variant in `hfe_hemochromatosis` — so it could never have completed
   on any clinically-authored module. `GwasNotFound` is a subclass rather than a flag, keeping the
   distinction typed: `associations_for` reports the empty answer, `follow` withholds one association's
   study facts and keeps the effect. The reverse must never happen.
2. **A p-value below float64's range dropped the whole association.** The Catalog publishes
   `pvalue: 0.0` past the subnormal boundary and `p_value_num` is `gt=0` for the reason SCHEMAS gives —
   that is an underflow, not a probability. The model was right and the pass was wrong: it let the
   `ValidationError` discard a real published effect over one derived column. The number is now
   withheld, the verbatim string keeps what the source said, and the row survives. **Six on rs1800562;
   189 rows became 195.** This is the catalogue-scale case the 0.5 mantissa/exponent rejection
   anticipated, met without reopening it.

**And a prediction the measurement refuted.** `_LinkCache` exists because `pmid`, `study_accession`,
`ancestry`, `trait` and `trait_efo_id` all sit behind `_links`, making the pass `1 + 2N` requests per
variant; the expectation was that associations share studies heavily and caching would collapse most of
it. It saved **nothing** — rs1800562's 189 associations each name their own study, so the real figure
was **382 requests and zero cache hits**. The cache stays (it costs a dict and pays on a module whose
variants share literature), the docstring now states the measured budget instead of the guess, and
`--no-study-facts` exists because of the measurement rather than in anticipation of it.

### Licensing: the first source here with no named licence

`GWAS_CATALOG_TERMS` records EBI's prose terms, read 2026-08-17. `license` is null, which is the honest
answer. **`commercial_use` stays `None` deliberately**: the page permits "use" generally but conditions
it on the original data owners' terms, and for an aggregator of thousands of published studies those
are not established here. Unknown is neither permission nor refusal — `taints_commercial_use` requires
an explicit `False`, so a null warns rather than gating, which is the right outcome for terms stated in
prose. Pinned by a test so it is not "tidied" to `True`. Rate limits are **not established** for EBI,
unlike gnomAD's real and load-bearing 10/60s, and the interval says so.

### Measured

Adding the table moved **nothing**: no digest and no signature on any of the sixteen examples, since a
module without the table has no such file. `hfe_hemochromatosis` then adopted it — 195 real rows, 186
associations for rs1800562 across **62 EFO traits in 12 distinct effect units**, three of which are
spellings of one unit (`SD units`, `SD`, `s.d.`) and two more of which differ only in case (`g/dL`,
`g/dl`); 138 rows carry the uninformative `unit` and **42 of 195 name no effect allele at all**. Its
`artifact.digest` moved, correctly, and its **`content_signature` did not** — which corrects the
prediction written into the plan: neither a derived sidecar nor a manifest-only block is authored row
content.
