# Symptom → cause → action

Real message text, matched on the distinctive phrase. Most of these cost someone a day.

An `RMn` in a message is a tracked upstream roadmap item: known and deliberate. Leave the data honest
rather than working around it.

## Authoring and loading

**`unreplaced template placeholder '<<REPLACE>>' in VariantRow row: genotype`**
A scaffolded stub or a drafted partial row still needs a human. This blocks **every** loader, including
`enrich` — deliberately, since forward resolution is allele-aware and a placeholder genotype would skip
that filter. Do not try to enrich first: the draft report already printed the allele pair for each
stubbed row (`genotype for rs…: ClinVar publishes C>T — an allele pair from {C, T}`). Curate from that.

**…`in VariantRow row: genotype, state`** — the same message naming **two** columns
The row is an `uncertain_significance` (or otherwise undecided) ClinVar record, so `state` is stubbed as
well. That is not an omission: no vocabulary member means "undecided", and every candidate asserts
something the submitters did not — `neutral` says the variant is benign, `risk` says a direction. The
draft report explains it once per clinical call and names the affected rows. Decide it per row alongside
the genotype; `risk` for a variant you have reason to treat as actionable, `neutral` for one you have
reason to discount, and if you can justify neither, the honest move is to drop the row rather than pick
a `state` to make the compile pass.

**`genotype '0/1' looks like a VCF GT field: those are VCF GT allele indices …`**
The likeliest single mistake in this column, because pasting a `GT` field is the obvious first guess.
`GT` records *indices* into that record's own REF/ALT list — `0` is REF, `1` the first ALT, `.` a
no-call — and `genotype` spells the alleles out. Translate against the same VCF record: with `REF=C`
and `ALT=T`, a `GT` of `0/1` is `C/T` and `1/1` is `T/T`. The indices cannot be resolved for you,
because a genotype cell carries no REF/ALT to count from.

`0/1/1` gets this message too, not the two-allele-ceiling one — the defect there is the notation, not
how many alleles it names, and the ploidy explanation would send you to change the wrong thing.

**`unreplaced template placeholder '<<REPLACE>>' in sources.csv row: source`**
The licence table is the one fact sidecar you write by hand, so its stub blocks a compile exactly like
an authored table's. This was silent until recently: a `<<REPLACE>>` there compiled clean under
`--strict` and was published as the source the module accounted for. Fill in the real source name, or
delete the row if that source is not one this module used.

**`Input should be a valid string [input_value=None]` on a column you were not told to fill**
A *defaulted* column left empty. An empty cell arrives as `None` and overrides the default. Run
`just-dna-compiler requirements <kind>` — its "never leave empty (defaults)" line names them. A list of
required fields alone is not enough; requiredness has three shapes.

**`ref/alts require chrom and start to also be provided`**
Identity is filled whole or not at all. Either give the complete coordinate or use the rsID alone. A
lone `alts` on a position-only row would make the key a VRS allele id instead of `chrom:start:ref`,
silently changing which variant the row is.

**`direction must be one of ['neutral', 'protective', 'risk', 'unknown'], got: 'increase'`**
`direction` is not a magnitude — it is the same axis as `state`. Every closed vocabulary is printed by
`just-dna-compiler describe <kind>`; do not write one from intuition.

**`state='risk' but weight=1.0 > 0`** — a **warning**, so it still compiles
The sign convention is inverted from the one you probably assumed. `weight` contributes to a
wellness-style score rather than to a hazard, so `risk` wants a **negative** weight and `protective` a
positive one. The same warning exists for `direction`. Nothing refuses on it, so a green compile is not
evidence you got it right.

**`trait_efo_id tokens must be ontology CURIEs`** on a value that is not a trait
Almost always a column shift in a hand-edited CSV. Re-write it with a CSV writer rather than by
splitting on commas — several `conclusion` values contain commas.

**`must be a non-empty haplotype name without whitespace`**
A haplotype name is an identity, not a grammar — `*4`, `e4`, `ε4` are all fine. This fires on an empty
cell or one with a space. Note CPIC's `x≥3` copy-number notation is *not* accepted by the star-allele
pattern the CPIC provider checks, so those rows are skipped and counted (RM5's notation gap).

**`draft --gene CYP2D6` produced thousands of diplotype rows**
Expected without a filter, and the fix is `--allele`: name the star alleles your consumer's caller can
emit and every table is drafted to that set (`*1` is kept automatically). Six alleles turn CYP2D6's
16,290 diplotypes into 21. One `--gene` at a time, because `*2` means a different allele in each gene.

## Resolution and enrichment

**`not in the injected Ensembl snapshot, position remains unset`**
The local snapshot does not contain it — **not** a claim that Ensembl does not. Online, the live link
runs next. Offline, that is the end of the road and the row stays unresolved.

**`cannot host the authored genotype … The event sizes differ`**
A real contradiction, and a decidable one: re-anchoring an indel never changes how many bases it adds or
removes, so this is a different variant sharing the rsID rather than another spelling of yours. One rsID
legitimately covers several records at a locus (`rs281864532` is `G>GT`, `GT>G` *and* `GTT>G`), so check
which record your genotype was written from. Two spellings of *one* indel reconcile automatically —
ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the same 2 bp deletion and both resolve.

**`could not be decided here … the same size but different content`**
Not a contradiction and not your mistake: the two spellings describe an event of the same size in
different bases, which is either one indel re-anchored inside a repeat or two different variants, and
telling those apart needs the reference sequence. **The locus is kept** — nothing is dropped and
`--strict` still compiles. Run the enricher (it has sequence access) if you want the ambiguity
resolved; do not edit an allele to silence it.

**`maps to N loci in the resolution table; expanded to M rows`**
Normal for a **paralogous** rsID — one id, several genuinely distinct places. Expected, not an error; do
not delete rows to suppress it. To count *findings* rather than rows, count distinct `rsid` in
`weights.parquet` — the expanded rows keep it. `M` exceeds `N` when you authored more than one genotype
at that rsID: the expansion pairs each authored genotype with each locus.

Worth knowing before you read the compiled table: **only one member of an expansion can match a given
genotype**, and the others are still well-formed rows. A genotype written for the duplication at a
ClinVar dup/del pair lands beside the deletion's reference allele too, where it reads as an ordinary
row and asserts nothing. That is by design — the alleles a source publishes are often incomplete, so a
genotype that does not fit a locus is at least as often a gap in the source as a defect in your module,
and the compiler will not drop rows on that evidence. Nothing you can author changes it; it matters
only if you go on to read `weights.parquet` row by row.

**`rsN is pseudoautosomal: it maps to 2 loci (X:… and Y:…) that are 1 place(s)`**
A different message for a different situation, and the wording is the point: PAR1/PAR2 are shared
between X and Y, so this is **one place spelled twice**, not two places. You only see it if the table
carries both contigs — `enrich` records the X spelling alone by default, since ClinVar holds no PAR
variant on Y and gnomAD excludes the Y PAR from its callset, so the Y row could match nothing in a
standard (analysis-set-masked) GRCh38 pipeline. Re-run `enrich` without `--keep-par-twin` to record X
only; keep both deliberately if your reference is unmasked. Not an error either way.

**`pseudoautosomal: kept the X spelling of N locus/loci; left out …`** (from `enrich`)
Informational, and printed rather than silent precisely so a table half the size you expected is never a
surprise. The named Y loci are the same places as the X ones kept. `--keep-par-twin` records both.

**`N coordinate-authored row(s) have no rsid in the resolution table, so they stay coordinate-keyed`**
Not an error and usually not worth acting on: a coordinate is a complete identity and an rsID is a label
on top of it, so these rows are fully resolved. Re-run the enricher if you want the labels back-filled.

**`Enrichment is GRCh38-bound; the module declares genome_build='GRCh37'`** (from `enrich`)
Expected, and the only honest answer: resolution and VRS minting have one refget table (**RM15**). No
link runs and **no row is recorded** for anything needing a lookup — not even `not_found`, which would
claim the source was asked. Your authored coordinates are still transcribed, under your own build, and
the module compiles: it keeps build-relative coordinate keys instead of `ga4gh:VA.…` ids. Author
coordinates rather than rsIDs on a non-GRCh38 module, since an rsID is only resolvable against GRCh38.

**`GA4GH VRS allele identity is GRCh38-only (RM15), so N variant(s) are keyed by coordinate instead`**
The companion message at compile time, and it is a statement about the key, not a defect. A coordinate
key is **build-relative** — it will not join against a GRCh38-keyed module — which is true of
coordinates and is said out loud rather than hidden behind an id that looks portable.

**``ref mismatch: N row(s) — coordinate shifted 1 base to the right: `start` is the 1-based VCF position and must not be converted``**
The one to read carefully, because the column it names is not the column you would have guessed. Your
`ref` cells are **right**; your `start` cells are each one too low, which is what subtracting one from a
VCF position produces. `start` is the 1-based VCF POS — the same number Ensembl, dbSNP, ClinVar and
gnomAD show you — and nothing in this pipeline wants an interbase offset. Add one back to every `start`,
delete `resolution.csv`, and re-enrich.

Two things about how this reaches you. It is **not** caught offline: a uniformly shifted module passes
`validate`, passes `compile --strict`, reports `fully_resolved: True`, and mints `ga4gh:VA.…` ids the
compiler then reports as *verified* — a content-addressed id is a correct digest of whatever it is
given, so it certifies the wrong locus perfectly happily. And it is caught here only for the rows where
the neighbouring base differs from your `ref`; roughly one row in four escapes by coincidence, so treat
the count as a floor, not a total. Every id minted for a shifted row names the wrong place and must be
regenerated, not patched.

**`ref mismatch: N row(s) — single-base ref disagrees at a position nothing else contradicts`**
The residue after the shift check: the base at your coordinate is not the one you wrote, and neither
neighbour explains it — either the `ref` cell really is wrong, or it is a shifted row whose neighbours
happen to carry the same base so the direction could not be established. If the run also reported a
shift group, assume these belong to it and fix them the same way. The minted id is the true allele *at
the position recorded*, which is only reassuring if the position is right.

**`ref mismatch: N row(s) — multi-base ref disagrees, so the allele spans the wrong bases`**
The corrupting case, and the reason `ref` is checked at all. A multi-base `ref` *sets the interval*, so
a wrong one mints a well-formed id for an allele you did not mean, and nothing downstream can notice.
Fix the row.

All three are **reported, never repaired** — the authored value survives so the evidence of the upstream
mistake is not destroyed — and all three need sequence access, so `--offline` reports nothing here. A
check that could not run is not a check that passed. They are grouped by cause rather than listed per
row, so `N` is a count and only the first few keys are named.

**A sidecar did not change after you edited the spec**
An existing `resolution.csv` / `frequencies.csv` / `gene_metrics.csv` is authoritative and merged.
**Delete the file** and re-run, or stale rows persist silently. This is also the only way to ask whether
an injected `resolution.csv` still agrees with the sources: move it aside, enrich, and compare. The
compiler cannot ask for you — it never fetches, so it takes the table you give it.

**`no gnomAD frequency: [ga4gh:VA.…, …]`** (from `frequencies`)
gnomAD has no record for those alleles, which is ordinary — a GWAS-tag SNP absent from the exome/genome
callset, or a locus gnomAD does not cover. They are recorded as `not_found`, and the rest of the pass is
unaffected. The keys are variant keys, so a resolved substitution appears as its VA digest rather than
its rsID; look it up in `resolution.csv`. Distinct from **`not_covered`**, which means the source cannot
cover that locus at all (the Y PAR) — an absence nobody established is not a finding, and neither status
fails `--strict`.

**`sources.csv has no row for … ['gnomad']`**
A real finding: a source contributed facts and the module records no terms for it. Fixed by
**re-running the pass that consulted it** — `enrich`, `frequencies` and `gene-metrics` each write their
own row into the licence table, and merging never clobbers a row you wrote by hand. A `resolution.csv`
written before the `authority` column existed simply says nothing here; re-enrich to fill it.

**`sources.csv is the deprecated spelling of this table and will be removed at 1.0`**
Not a defect: the file is read exactly as before. Rename it to `licensing.csv` to clear the notice.
Rename, do not copy — a module carrying both is refused, and so is the same table both beside
`module_spec.yaml` and in `derived/`. The message names both paths when that happens.

**`… are the same table in two places, and both are present`**
Two spellings of one file, or the same file at the spec root and in `derived/`. Nothing picks a winner
for you: the file may be hand-edited, so choosing one would silently discard your edits. Keep the copy
you want and delete the other.

## Validation and compile

**`validate` says `valid` and `compile` then refuses**
**Check the modes first — that is the likely cause.** Several checks are a ladder: a warning under
`--best-effort` (the default for both commands) and an error under `--strict`. A bare `validate` followed
by `compile --strict` is a pre-flight for the *other* compile, so pass the same flag to both:
`validate spec/ --strict`.
With the modes matched it should not happen, and if it does, that is a bug worth reporting upstream
rather than working around. `validate` covers `resolution.csv`, the four fact sidecars (`licensing.csv`,
`literature.csv`, `frequencies.csv`, `gene_metrics.csv`), the licence gate, the stored `vrs_id`, the
p-value pair, and whether every genotype and `effect_allele` names an allele its locus actually has.
What still only appears at compile is anything computed from *resolved* rows — the expansion and hosting
findings above — because resolution has not run when `validate` does.

**`--no-resolve switches off resolution entirely, including the injected resolution.csv`**
You passed `--no-resolve` (or `resolve_with_ensembl=False`) with a `resolution.csv` beside the spec. The
flag reads as "do not use Ensembl" and is actually the master switch for resolution of *every* kind, so
the compile succeeds and writes a module whose every row has no `chrom`/`start` — rows no VCF can match.
Drop the flag: consuming an injected table involves no reference and no network either way.

**`allele(s) C are not among the authored alleles at this locus (T/Y) — the genotype is not the problem:
'Y' is an IUPAC ambiguity code`** — a warning under `--best-effort`, an error under `--strict`
The genotype is fine; one cell of `ref`/`alts` is not a nucleotide. Two cases, and the message says which:

* **an IUPAC ambiguity code** (`Y` is C-or-T, `R` is A-or-G, `N` is any base). It records an
  *uncertainty*, so it is never expanded into the alleles it could stand for — expanding would assert
  alleles your source declined to. Write the alleles the locus actually has: if the site really carries
  both, `alts` is `C,T`, and each gets its own `ga4gh:VA.` id.
* **a symbolic or structural allele** (`<DEL>`, a repeat notation). Not a grammar this release holds; the
  variant cannot be expressed as a nucleotide string yet, so leave the row out rather than approximating
  it.

Without this the message blamed the genotype, which sent authors to re-check a correct cell.

**`stored vrs_id ga4gh:VA.… does not match the id recomputed from 11:5225715 G>T`** — an **error in both
modes**, so `--best-effort` will not get you past it
A `ga4gh:VA.…` is content-addressed: for a substitution it is computed from the coordinate and the
alleles alone, with no reference and no network, so the recomputation is deterministic and a
disagreement can only mean the stored id is wrong. Nothing to decide — delete the `vrs_id` cell and let
`vrs mint` write it, or fix whichever of `chrom`/`start`/`ref`/`alts` is wrong. Usual causes are a
hand-built `resolution.csv`, a row copied between variants, or an id kept after the coordinate was
edited.

**`vrs_id ga4gh:VA.… could not be verified — …`** — a warning in both modes
Not the same claim as the one above: nothing was compared, so no verdict was reached. The compiler
cannot recompute an id for an indel, an MNV, an off-assembly contig, a non-GRCh38 build, or the
unobservable-allele marker `*` — the first four need the reference sequence, which this tier never
fetches, and `*` names no allele at all. **Nothing is wrong with your module**, and `--strict` does not
refuse it: the id was minted upstream by the enricher, which does have sequence access, and it is
carried and marked unverified. A multi-allelic row is *not* in that list: `vrs_id` holds one id per ALT,
comma-joined in the same order as `alts`, and each is checked on its own.

**`vrs_id … could not be verified — the row carries no coordinate` / `… against no ALT`** — an error in
both modes
The other half of the same message, and this one *is* about your data. An id is a digest of a place and
an allele, so a row asserting one while recording neither cannot be checked by anything, ever. Re-run
the enricher so the row resolves, or drop the `vrs_id` if the row is meant to stay unresolved.

**`<DEL:4977> is a symbolic allele … a recorded id here names some other allele`** — an error in both
modes
The third member of that family, and the one that looks like a warning and is not. A symbolic allele
names a structural *event* and no sequence, so nothing anywhere can mint an allele id for it — which
means an id sitting in that cell was minted for a **different** allele. Delete the `vrs_id` cell: the
row keeps its identity through `variant_key`, and nothing is lost.

Note the pair this makes with the coverage warning further down. A symbolic allele with **no** id is
normal and stays a warning — no tool can fill it, so refusing would make every structural module
uncompilable. It is the recorded id that is the defect. Absence is a limit; a claim is a claim.

**`VRS allele identity covers 289/474 allele(s) … Anything keying on the VA sees only the covered
fraction`** — a warning in both modes
Not a defect in the module: it reports how much of your resolution table a `ga4gh:VA.` id actually
names, with the remainder grouped by what each is blocked on. If a line says the ids are *computable
offline*, the mint pass has not run — `just-dna-enricher vrs mint <spec_dir>` fills them. If it says
indel/MNV, re-run that command **without** `--offline`, which is what lets it read the reference
sequence. If it names a build with no refget table, nothing can be done today and the module is fine.
It never refuses, in either mode, because the last two causes are fixable by no edit you could make.

**`p_value '1.2e-14' reads as 1.2e-14, but p_value_num says 1.2e-41`** — a warning under
`--best-effort`, an error under `--strict`
Two encodings of one number disagree, so one is a transcription slip. `p_value` is the free-form record
and `p_value_num` is what a consumer filters on, so the number is usually the one to fix. Compared
relatively at 1%, so a rounding (`5.23e-8` beside `5.2e-8`) is silent — a wrong digit or a wrong power of
ten is not. A string that does not denote one definite value (`<0.001`, `NS`, `5e-8 (adjusted)`) is
skipped in silence and disagrees with nothing.

**`module_spec.yaml is not valid YAML: … line 4, column 10`**
A syntax error in your hand-written spec, with pyyaml's own line and column. The usual causes are an
unclosed `[`/`{`, a tab used for indentation, or an unquoted value containing `:`.
**`module_spec.yaml must be a mapping of top-level keys`** is the neighbour case: the file parses but is
a list or a bare scalar.

**`overlapping bins for key (…)`** — an **error**, so the module cannot compile
Two resolved bins in one group select two phenotypes for one measurement. Check the group key first:
bins are grouped by the kind's key columns **plus** `trait_efo_id`. If two different variants are
colliding in a heteroplasmy table, give each its variant identity (`chrom`/`start`/`ref`/`alts`) — that
is what the key is for.

**`coverage gap … no bin covers (0.099, 0.1)`** on a fraction or percentile
The fix is to **make the bounds touch**: write `0.0–0.1` and `0.1–0.3` rather than `0.0–0.099`. On a
continuous measure two bins may share an endpoint and the higher bin owns it, so a measurement of
exactly `0.1` selects the second row. Author the top bin **closed** (`0.3–1.0`) — the top of the domain
is a real measurement. On `repeat_count` / `copy_number` a shared endpoint is still an overlap and still
an error *by default*, because there the bins are read as a grid and genuinely both claim that integer —
write `measure_tiling: continuous` on the group if that axis is not a grid.

**`bins with the same lower bound for key (…)`** — an **error**
Two bins in one group start at the same number, so the shared-endpoint rule has nothing to order and a
measurement at that number has two answers. Usually a sharp bin (`0.1–0.1`) written beside the range
that begins there; drop the sharp row or move the range's start.

**`chrom=MT is not diploid here`** / **`chrom=Y is not diploid here`**
A two-allele genotype on a non-diploid contig. Use a single allele (`G`) for a homoplasmic or hemizygous
call. If the locus is in **PAR1 or PAR2** it really is diploid and this does not fire — if it does,
check the coordinate.

**`chrom=Y with two alleles on build 'GRCh37', which has no pseudoautosomal table`**
Ploidy could not be decided on that build. The message names both readings and asserts neither.

**`genome_build is 'GRCh37': … keyed by coordinate instead … build-relative`**
Your identities will not join against GRCh38-keyed data (gnomAD, ClinVar, ClinGen), and the same key
means a different locus on another build. VRS identity is GRCh38-only (RM15). Publish GRCh38
coordinates unless the module is deliberately build-local.

**`inconsistent reference allele`**
Two rows share a key while disagreeing about `ref`. Exactly one can be right — a VRS allele id names the
place and the alt, not the reference base, so this is the only place the contradiction surfaces
offline. An authored `ref` contradicting the *genome* is a different check, and needs the enricher.

**`Star allele(s) used but not defined in haplotypes.csv`**
`allele_function.csv` or `diplotypes.csv` names an allele nothing defines, so a caller can never emit it
and those rows are dead. Either define it or drop the rows. `*1` is exempt — the reference allele is
defined by carrying no variants.

**`diplotype rows … name haplotypes this module defines identically`**
Different names, identical defining-variant sets, disagreeing conclusions — so at most one can be right,
and **phase does not help**. Either the definitions are incomplete or the rows describe one allele under
several names. Distinct from the next entry.

**`diplotype rows … are indistinguishable without phase`**
Same unphased genotype, different conclusions, but the haplotype definitions *do* differ — so phase
resolves it. Correct and expected for a cis/trans pair; a consumer with unphased calls must withhold.

**`sources.csv declares N source(s) no table in this module uses`**  *(same for `licensing.csv`)*
Over-declaration; usually a stale row after you removed a table. Harmless.

**The compile refuses over licensing**
An annotation-layer source forbids sale and the module records no declaration. Draft with
`--use non-commercial` so the terms are recorded, or drop the source. There is no compiler flag for this
by design — a flag cannot survive `reverse`, so the third compile would refuse.

**`copy_number bins here are tiled as whole numbers, but the field a consumer reads the measurement
from (CN) is not a whole number in VCF 4.4`** *(same for `repeat_count` and `RUC`)*
**Not a defect, and there is now something you can do about it.** VCF 4.4 made both fields fractional —
a copy number may be a segment mean, and a repeat count is typed as a decimal — while these two kinds
are read as a grid unless you say otherwise. The consequence: a fractional measurement *between* two of
your bins matches neither, and the coverage check will not report that hole, because on a grid it only
reports one wider than a step. So `[0,0] [1,1] [2,2] [3,∞)` is a legal, silent tiling that answers
nothing for a measured 2.4.

Decide which your table is. If the caller you expect rounds to whole numbers — a catalog count, a star
allele's copy number — the grid is correct and this line is a notice, not a finding; leave it. If the
caller reports a segment mean or a decimal repeat count, write **`measure_tiling: continuous` on every
row of the group** and tile the axis properly: `[0,1.5] [1.5,2.5] [2.5,]`, bounds touching, the higher
bin owning the shared value. The bounds have always accepted decimals, so nothing else changes, and the
line stops. Do **not** work around it with `[0, 0.999]` — that is an arbitrary number and it leaves a
hole nothing warns about.

**`tiling inferred for key (…): measure_max is 2.5, which no quantised reading can hold`**
**Informational, and it is telling you the compiler made a decision.** You wrote a bound that is not a
whole number on a table that would otherwise be read as a grid, so the group was read as continuous
instead: adjacent bins may share an endpoint and any hole is reported. Nothing is wrong; the point of
the line is that you can see it happened. Write `measure_tiling: continuous` on those rows to state it
yourself, and the line stops.

**`measure_tiling for key (…) is declared 'quantised' and the data contradicts it`**
You said the axis is a grid and then wrote a value that is not on it. **Your declaration stands** —
nothing overrides it — so the bins are still read as a grid and that value sits between two of them.
Either round the bound to a whole number or change the declaration to `continuous`.

**`conflicting measure_tiling for key (…)`** — an **error**
Two rows of one bin group declare different tilings, and the group is read under one. Leave the column
empty on the rows that do not state it: empty means the kind's default, not a third answer.

**`` `modifier_cn` is deprecated and is removed at 1.0 ``**
Move the dosage to `modifier_copy_number`, which is a number that may be fractional. A whole number is
still a whole number, so the value does not change. Set one column or the other — setting both is an
error, because two spellings of one dosage can disagree.

**`copy_number bins: one measurement can span several bins`** *(same for `repeat_count`)*
**Also nothing to fix, and this one is a statement to a consumer rather than to you.** A real copy-number
or repeat call arrives with a confidence interval, and a missing upper bound on it means *unbounded* —
so the measurement is a range, and yours is a table of thresholds it can straddle. The format has no
state for that yet: a consumer that reads an interval touching two or more of your bins must **withhold**,
not pick one, and not fall back to your `unresolved` row (that row means *no measurement was available*,
which is a different claim about the sample). The warning fires on any such table with two or more bins
in one key group, so it is expected on every real one. It never fails a compile, including `--strict`.

**`N row(s) write '.' in alts, which is VCF's MISSING marker, not an allele`**
**Fix this one — leave the cell empty.** In a VCF, `.` in the ALT column means *there are no alternate
alleles*, i.e. a plain reference record. Written into `alts` it is read as though it were an allele and
folded into the row's identity, so your row becomes `6:26093141:G:.` where the same site with the cell
left empty is `6:26093141:G` — two identities for one site, which dedup against nothing and hash
differently. The message prints both keys so you can see the split. It is not the same thing as
`<DEL>` or another symbolic allele, which names a real variant this format cannot yet spell; there is
nothing here for a future release to hold. An rsID-keyed row is unaffected in identity (the message says
so), but the cell is still claiming an allele that does not exist.

**`N row(s) set requires_callable=true and state their min_quality floor against QUAL`**
**Fix this one — use `GQ`, or the reference block's `MIN_DP`.** `QUAL` means opposite things on the two
kinds of record: on a variant record it is confidence that the variant is real, and on a reference
record it is confidence that the position *is* variant. A `requires_callable` row is exactly the one a
consumer proves by reading the reference record, so a floor against `QUAL` there demands evidence
*against* what the row asserts, and the higher you set it the more confidently wrong the answer. The
combination is not refused, because the same row read against a variant record elsewhere in the same
file is legitimate and the compiler never sees the file. While you are there: callability evidence is
usually a *block* (one record spanning a range), so it is found by interval containment rather than by
matching a position, and `DP` on a block is the average over it — `MIN_DP` is the floor, and the floor
is what a callability threshold is about.

**`pmid names PubMed Central id(s) ['PMC3110566'] and no PubMed ID`**
You wrote a PMC id where a PubMed id goes. They are one letter apart and they number articles
**independently**, so a PMC id's digits are a real PMID for a *different* article — writing them
through would cite the wrong paper with nothing to catch it. The refusal names the id it saw rather
than the one it wanted, and it never converts: run
`just-dna-enricher hint citation --pmcid PMC3110566` and write the PMID it reports. Note that
`PMC3110566` and `PMC 3110566` now behave the same; the spaced form used to be silently *accepted* as
PMID 3110566, so a cell that compiled before may refuse now — that is the fix, not a regression.

**`N row(s) place a variant past the end of <CHROM> on <BUILD>`**
The position cannot exist in the build the module declares — it is not a warning, it is arithmetic,
so it is an error in both modes. Two readings, and the message says which applies: if the position
fits the *other* assembly's contig, the rows are probably GRCh37 coordinates in a GRCh38 module, and
the whole file is suspect rather than that one row. If no known build has a contig that long, the
contig and the position disagree with each other and both need checking. Do **not** convert
coordinates by hand to make it pass — if the paper gives an rs number, author that instead and let
`enrich` supply the coordinate, which is the one route that produces something independently checkable.

**`N row(s) name contig <X>, which is a top-level sequence of <BUILD> and of no other build`**
Same family, arriving through the contig name rather than the number. A scaffold like `GL000209.1`
does not get typed by accident — it gets pasted out of a VCF built on the other assembly, so treat it
as evidence about the *file*, not about the row. The same clause appears when a `chrom` cell is
refused outright.

**`VCF pointer cell(s) name a key that INFO and FORMAT both define`** — a warning, not a refusal
`DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and `CN` exist in **both** VCF tables and mean different things:
`INFO/AF` is the cohort's allele frequency, `FORMAT/AF` is this sample's. Both are floats in the same
range, so nothing downstream can detect the confusion — a consumer reads a well-formed number of the
wrong kind. Qualify the pointer (`FORMAT/AF`). A bare key stays legal and keeps meaning *unqualified*,
which is why this warns rather than refuses.

**`point at a field the spec defines as multi-valued and state no element rule`** — also a warning
The field returns a list, not a number: `Number=A` is one value per ALT, `Number=R` one per allele
with the **reference first**, and a repeat caller's `REPCN` carries both alleles. Set the companion
column to say which element you mean. On a `Number=R` field the reference is element zero, which is
why each ranging rule comes in a pair — `largest` counts the reference, `largest_alt` does not. This
matters most where it looks least urgent: a dominant repeat expansion is judged on *the larger* of
the two alleles, and a consumer that averages them or takes the first gets a well-formed wrong answer.

## Checks

**`acmg_sf=false but <GENE> is on ACMG SF v3.3`**
The column is gene-level list membership. If the row is about a variant in a listed gene that is not
itself a reportable finding, leave the cell **blank** — blank means "not stated". ACMG scopes some
entries more narrowly than the gene (HFE is *"c.845G>A; p.C282Y homozygotes only"*).

**`unverifiable: …` and `the list read is ACMG SF v3.2 but v3.3 is published`**
**Not a finding about your module.** You ran `check-acmg` without `--sf-list`, so it fell back to NCBI's
page, which is a release behind — it does not carry `ABCD1`, `CYP27A1` or `PLN`, all of which v3.3
lists. Every disagreement is withheld rather than reported, and `--strict` will not fail on one. To get
an answer, build the snapshot from ACMG's published workbook
(`just-dna-enricher acmg build <workbook.xlsx> --out acmg/`) and re-run with `--sf-list acmg/`, which
also works `--offline`.

**A note saying a gene is listed and `acmg_sf` is blank**
Informational, never a defect, and `--strict` does not escalate it. Blank is a legitimate answer.

**`clin_sig cross-check not run: this module's licence row records that its ClinVar annotations were
drafted from …`**
Working as intended, and more honest than the alternative. Drafting recorded the release your rows were
copied out of, and it is the release the check would compare them against — so every value would be
matched with its own source and the answer would be zero conflicts whatever the data said. A guaranteed
zero looks like evidence without being any.

It is a statement about the module, so it cannot see a call **you** edited afterwards. Re-run with
`--strict`, which does not skip: it looks every value up and reports how many are still copies, how
many you wrote or edited, and how many conflict. (A conflict is a warning in both modes either way —
this is the one check that never fails a run, because a curator is allowed to disagree with a
low-reviewed submission.) `--no-verify-clinsig` is the manual switch and reports `not_requested`.

**`clin_sig cross-check not run: the ClinVar snapshot is present but not queryable`**
The cache was found and could not be read — usually a file the current builder would not have written
sitting in its `data/` directory, which puts two schemas under one query. Nothing was compared, and the
run says so rather than reporting an empty conflict list that reads as a pass. Rebuild it
(`just-dna-enricher clinvar build --download --out cv/`) or re-provision a clean cache.

**`clin_sig cross-check not run: no ClinVar snapshot this run`**
Different sentence, different meaning: nothing was compared because there was nothing to compare
against. Provision a snapshot (`just-dna-enricher cache pull --only clinvar`) or pass
`--clinvar-cache`. An unasked question is never a passed check.

**`pharm_variants.csv: N of N row(s) have no chrom+start, so this table joins by rsID only`**
Not a defect in your module, and nothing to fix by hand — but know what you are shipping. A consumer
joins a VCF by position, so a table with no coordinates matches only through the VCF's `ID` column,
which many callers leave empty. **Since 0.6 the compile fills these tables from `resolution.csv` the
way it always filled `variants.csv`**, so what this line reports is the *residue* — the rows the fill
could not place — and on most modules it no longer appears at all. The sentence tells you which
situation you are in: *"resolution.csv names N of them, but at more than one locus or at one the row's
own allele contradicts"* means the compiler refused to pick between candidates rather than guess (fix
the genotype or the table); *"no resolution.csv row places them"* means run
`just-dna-enricher enrich` first. Writing the coordinates into the table by hand also works and is
legal — identity is filled whole or not at all, so that means `chrom`, `start` **and** `ref`, not a
subset. It never fails a compile, including `--strict`.

**`… N carry one half of a coordinate (a start with no chrom, or the reverse)`**
The more deceptive shape, and usually a drafted `haplotypes.csv`: CPIC publishes the position on one
table and the chromosome on another, so an older draft carries `start` alone. It reads as a coordinate
and joins to nothing. Re-draft the gene (`just-dna-enricher draft --gene …`) and the chromosome comes
with it.

**`N ClinVar citation(s) skipped: the id ClinVar filed under PubMed is not a PMID`**
A defect in the source, not in your module, and nothing to fix by hand: a few hundred of ClinVar's
citation ids are nine digits where a PMID is eight. They are counted rather than listed, and the
remaining citations for the same variant are drafted normally. Rebuilding the snapshot from a current
`clinvar citations` drops them at the source. Reported apart from the `--max-citations` line, which is
about a cap you chose.

**`N row(s) on non-diploid contigs were written with a single-allele genotype`**
Not a warning about a mistake — it is the provider telling you which cells it filled. MT is haploid and
chrY outside the pseudoautosomal regions is hemizygous, so exactly one genotype is expressible and
nothing was pre-empted. Those rows read as homoplasmic/hemizygous; if you mean a heteroplasmic
*fraction*, that is `heteroplasmy.csv`, not a second allele here. A chrY row *inside* PAR1/PAR2 keeps
its placeholder, because there the locus really is diploid.

**`chrom=MT is not diploid here — use a single-allele genotype`**
You (or a tool of your own) wrote `A/G` where only one copy exists. Write the single allele. The same
message covers chrY outside PAR1/PAR2; inside them a pair is correct and no warning is emitted.

**`N genotype(s) at M site(s) have no row: … the reference homozygote / a homozygous alternate
genotype / a heterozygous genotype has no row`**
A curation gap, reported only where you have shown it is one. A consumer matches a subject on
`(variant, genotype)`, so a genotype your table does not carry is a subject your module cannot answer
for — most often the **homozygote**, which is the reading a reader is least likely to expect to be
missing. It fires only at a site where you already wrote **two or more** genotypes: one genotype at a
site is a rule that fires on the call you care about, which is normal and silent. Never fails a
compile, in either mode — which genotypes to annotate is your judgement, and the check only says which
member of the set is absent.

Two things it deliberately does not say. It never asks for an alternate/alternate pair (`A/T` at a
two-alternate site), so a site is complete with the reference homozygote, one heterozygote per
alternate and one homozygote per alternate. And it says nothing about whether a genotype can be
*observed*: whether a hom-ref row ever matches depends on the file a consumer brings — a variant-only
VCF emits no record where the sample matches the reference, while a gVCF or an array does — and that
is the annotator's call, not this format's. Writing the reference-homozygote row is right when you
mean it; the row is what makes the module usable on array data.

**`clin_sig` differs from ClinVar's** and `--strict` did not fail
Deliberate. Two opinions differing is not a factual error, and ClinVar is not truth — a curator who has
read the primary literature may correctly disagree with a one-star submission. The finding carries
ClinVar's review-star count so you can weigh it. The allele-function check behaves the same way.

**A wall of near-identical warnings**
Should not happen; findings aggregate per gene with a count and examples. If you see one, that is a bug
worth reporting upstream rather than filtering.
