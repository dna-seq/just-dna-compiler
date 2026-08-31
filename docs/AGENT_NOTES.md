# Agent notes — the long-form gotcha book

Every entry here was a real defect, a real probe, or a repair that was considered and refused. The
operative one-line rule for each lives in `CLAUDE.md`; this file carries the reasoning — what broke,
what was measured, and why the obvious fix is wrong.

**Each entry opens with a `@tag`, and that tag is the key `CLAUDE.md` cites**, so the round trip is:

```bash
grep -A25 '^- .@start-1based' docs/AGENT_NOTES.md   # the entry; 4–60 lines, -A60 for big ones
grep -n  '^- .@' docs/AGENT_NOTES.md            # every tag in order, with its headline
```

Tags are stable: rename one only by renaming its `CLAUDE.md` citation in the same commit. No test
enforces it, so the invariant to keep green by hand is that the two tag sets match exactly.

Two conventions, both inherited from `CLAUDE.md`:

- **Why a bug existed, or what a repair rejected, goes here or in
  [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) — never in the `/create-module` skill**, which is
  operative rules only.
- **New long-form material is appended to the section it belongs in, and gets a one-line headline in
  `CLAUDE.md`.** Do not grow `CLAUDE.md` with the narrative again — it is loaded into every session
  and has a size ceiling.

Related references: [SCHEMAS.md](SCHEMAS.md) (the schema tier), [COMPILER.md](COMPILER.md) (the
transform + the validation-ceiling table), [ENRICHER.md](ENRICHER.md) (the network tier),
[FAQ.md](FAQ.md) (settled questions by question), [RM_TOC.md](RM_TOC.md) (every `RMn`).

## Contents — what each section holds, and what to grep for

| Section | Holds | Grep for |
| --- | --- | --- |
| [Identity](#identity-variant_key-vrs-ids-and-what-a-digest-is-a-function-of) | `variant_key` precedence, `vrs_id` per ALT, coverage counting, the three VRS verdicts, refget | `derive_variant_key`, `vrs_id`, `refget` |
| [Coordinates and the genome build](#coordinates-and-the-genome-build) | 1-based `start`, restamping, `genome_build` injection, ref-mismatch and old-assembly diagnosis | `genome_build`, `_restamp_for_build`, `RM48` |
| [Alleles](#alleles-grammar-spelling-hosting) | non-nucleotide spelling, symbolic alleles (RM5), three-valued hosting (RM31), rsID status | `hosting_verdict`, `parsimony_reduce`, `RM5` |
| [Resolution and the round trip](#resolution-and-the-round-trip) | reversibility, `authored_ident`, expansion, sidecar authority, RM43, S20 | `authored_ident`, `resolution.csv`, `RM43` |
| [Checks](#checks-where-they-run-and-what-severity-means) | validate/compile parity, when to re-run behind resolution, severity rules, warning-as-API | `validate_spec`, `UNJOINABLE_PHRASE`, `mode ladder` |
| [PAR and ploidy](#par-loci-and-contig-ploidy) | PAR1/PAR2 geometry, X-spelling selection (RM32), gnomAD's Y-PAR gap | `par_partner`, `PAR_GRCh38`, `not_covered` |
| [Binning and citations](#binning-bounds-citations-and-literature) | bin grounding (S19/RM47), dense-measure boundaries, PMID/PMCID, quote attestation | `MeasureBinRow`, `PMCID`, `quote_source` |
| [Licensing](#licensing-sources-and-the-compile-gate) | sidecar names/places (RM51), `record_source_terms`, RM33, the compile gate, per-article terms | `sources.csv`, `licensing.`, `declared_use` |
| [PGx sources](#pgx-sources-clinpgx-cpic-pharmvar) | the ClinPGx key, CPIC traps, PharmVar assemblies and credentials | `annotation_id`, `PHARMVAR`, `cpic.` |
| [Drafting](#drafting-and-the-authoring-surfaces) | append-not-mutate, placeholders, vocabularies, hints, RM73 closure + draft digests | `draft.`, `TEMPLATE_PLACEHOLDER`, `closure` |
| [Schema evolution](#schema-evolution-columns-signatures-materialization) | optional-column legality, the three touch points, derived-not-stored, RM80, RM37 | `content_signature`, `COMPILER_MANAGED` |
| [Snapshots and clients](#snapshots-caches-and-network-clients) | rate limits, `locations`, `ensure_*`, probe-table performance, retry knobs, merge-pass suppression | `locations.`, `ensure_`, `probe_table` |
| [Dogfooding](#dogfooding-adversarial-probing-and-how-a-finding-gets-filed) | how a probe is chosen, the adversarial role, fix-vs-surface | `dogfood`, `adversarial` |
| [Testing traps](#testing-traps) | credentials, `.env` leakage across the suite | `api_key`, `load_env` |


## Identity: `variant_key`, VRS ids, and what a digest is a function of

- `@vkey-precedence` — **`variant_key` is the rsid FIRST, and the VRS allele id only for a coordinate-authored substitution
  (0.5) — read the precedence, not this headline.** An earlier wording led with the VRS half and a
  consumer read it as the rule, then filed "`variant_key` = rsid" as 0.4-era drift on four modules where
  it is exactly right.
  `derive_variant_key(rsid, chrom, start, ref, alts=None)` returns, in order: the **rsid**; else the
  **`ga4gh:VA.…`** id when the row is a single-base substitution with a coordinate; else
  `chrom:start:ref:alts` (alts sorted/normalized) or bare `chrom:start:ref`. Indels, MNVs,
  multi-allelic cells and off-assembly contigs deliberately fall through to the coordinate key — a VRS
  id is defined over the *justified* allele, and justifying an indel needs the reference sequence.
  Pass `alts` **only when minting a variant identity** (`VariantRow._freeze`, the one-to-many expansion
  re-key sites). Position-level **matching** — studies, `_verify`, the reverse pos→rsid lookup,
  haplotype dedup — deliberately calls it **without** `alts`, so it never mints a VA (a study matches a
  variant at `chrom:start:ref` regardless of allele). Mixing these up would orphan every study *and*
  reintroduce the same-locus allele collision.

- `@vrsid-per-alt` — **`ResolutionRow.vrs_id` is ONE ID PER ALT, positionally aligned with `alts` — and the rule it used to
  follow was borrowed from the wrong function.** The mint pass abstained on any comma-joined cell,
  quoting `derive_variant_key`'s reason ("a VA names exactly one allele; picking one would be a data
  error wearing an identifier"). True *there* — `variant_key` is one column naming one thing, so a plural
  cell falls through to the coordinate key — and false for `vrs_id`, which the schema keeps **outside**
  `RESOLUTION_FACT_FIELDS`, which no identity rests on, and where nothing is picked because every ALT is
  named. `frequencies._alleles_from_resolution` had reasoned it out correctly all along, so the tier was
  answering the same question two opposite ways. It cost 909 of 1,613 rows their id on a real module
  whose 2,110 alleles were all offline-mintable substitutions. Four things not to redo:
  - **A parallel array, never one row per allele.** `resolve_from_table` groups by `variant_key` and
    reads `len(loci)` as a *locus* count, so per-allele rows would enter the one-to-many expansion path,
    and `locus_index` would carry two kinds of "many" (P5). A single-alt row still spells a bare id.
  - **An empty member is a hole, and holes are kept.** A site can carry a substitution and an indel;
    dropping the whole row's ids over the one that will not mint offline is the same abstention again.
  - **Desync is guarded twice, because a parallel array has a failure mode a scalar does not.** The model
    refuses a wrong-*length* pair at load; `_verify_vrs_ids` recomputes member by member, so a
    right-length pair in the wrong *order* is a mismatch (error in both modes).
  - **It moves nothing.** `vrs_id` is outside every signature and `reverse_module` never re-emits it —
    verified byte-identical `artifact.digest`/`content_signature`/`resolution_signature` on five modules.

- `@vrs-coverage` — **A pass that only checks what is PRESENT must also count what is ABSENT — `_vrs_coverage`,
  `MintResult.coverage_warnings`.** `_verify_vrs_ids` verifies stored ids, so "a row with no `vrs_id` is
  skipped entirely" and a table where nothing was minted verified flawlessly. Fine for a decorative
  cross-reference, wrong for an identity a consumer may key on: coverage of an unstated fraction is not
  something anything can key on, and *unstated* is the defect. Both tiers report it, the counts land in
  `manifest.compilation.vrs_alleles`/`vrs_alleles_identified` (two counts, not a ratio or a bool — same
  reason `fully_resolved` sits beside `resolution_mode`; "complete" is derived), the denominator is
  **alleles not rows**, and gaps group by **reason class** — grouping on `_recompute_vrs_id`'s per-row
  prose produced forty lines each naming a different indel. It **warns in both modes**: an indel offline
  or a build with no refget table is fixable by no authored edit, and `strict` means "reproducible
  artifact", an unrelated axis. Generalize it: when you add a check that inspects recorded values, ask
  what it says about the records that carry none.

- `@va-omits-ref` — **A VA does not encode `ref`.** VRS names the place and the alt; the reference base is determined by
  the accession + interval, so it is not a digest component. Two consequences, both guarded, both of
  which must stay: the compiler has an **"inconsistent reference allele"** error (two rows sharing a key
  while disagreeing on `ref` — internal contradiction, catchable offline), and the enricher has
  `sequences.verify_reference_alleles` (authored `ref` vs the real bases — needs the sequence, so
  online only). A *single-base* wrong ref still mints the correct id, so **only** the enricher check can
  find it; a *multi-base* wrong ref mints a different allele entirely.

- `@vrs-three-outcomes` — **The compiler's VRS check has THREE outcomes, and NONE of them is a mode ladder.** *verified*
  (silent), *mismatch* (recomputed and different — **error in both modes**, since a substitution's id
  is deterministic here so a difference can only be corruption), and *unverifiable* (**could not be
  recomputed at all**), whose severity comes from **whose limit it is** rather than from the mode:
  - **the tier's limit → warning in both modes.** Indel/MNV, off-assembly contig, non-GRCh38 build.
    This escalated under `strict` for one cycle and the consequence was that the enricher's own online
    indel minting produced modules its own compiler refused — `pathogenic_clinvar` (185 alleles) and
    `shox_par1` (2) stopped compiling in the mode their READMEs print, and the skill's step 6 tells
    every author to run it. `strict` means *reproducible artifact*, and an injected indel VA
    reproduces perfectly; only the **verification** is out of reach, which is a different claim.
    Same rule as `_vrs_coverage_warnings` and `not_covered`: **a finding no authored edit could clear
    is not a `strict` matter** (P5 — orthogonal axes stay orthogonal). The old error's own remedies
    gave it away: *lower your guarantee*, or *delete a correct identity*.
  - **the row's contradiction → error in both modes.** An id recorded against no coordinate or no ALT:
    the row asserts an identity while withholding what that identity is a digest of, so nothing
    anywhere could check it. Same class as *inconsistent reference allele*, catchable offline. **A
    stored id against a SYMBOLIC allele joined this class in 0.6 (R2-5), and the order it was settled
    in is the reusable part.** It sat in the tier bucket, failing that bucket's own test — deleting the
    cell clears it, so it is not a finding no authored edit could clear — and it was not simply
    escalated, because the escalation only follows if a present id can *only* be a VA for a different
    allele, which nothing had established: `vrs_id` was checked for well-formedness alone
    (`ga4gh:<TYPE>.<digest>`, five types) while its description said *allele id*. So the **grammar went
    first**: `vrs.validate_vrs_allele_id` makes both `vrs_id` columns `ga4gh:VA.`-only (no
    instantiation — 844 corpus ids, all VA; and a `SL` already failed downstream as a *mismatch*, so
    nothing passing began to fail), and only then does the severity change rest on a stated rule
    instead of preceding one. Generalize both halves: **a format check is not a column rule** — "is
    this well-formed" and "may this column hold it" are different questions, and only the first should
    be generous — and when a severity change depends on a premise, state the premise in the schema
    before changing the severity.

    **The asymmetry that must not be flattened:** an **absent** id on the same symbolic row stays a
    coverage *warning* in both modes, because no tier can mint one and refusing would make every
    structural module uncompilable. *Absence is a limit; a claim is a claim.* Pinned by a test.
  - **`*` (RM59) is a THIRD gap class, not the indel one** (R2-6). `_vrs_gap_reason` and
    `_recompute_vrs_id` both test `is_unobservable_allele`, above the substitution fall-through, or the
    marker is reported as *"an indel or MNV … re-run it online"* — a remedy that can never apply. Filed
    as having no instantiation and upgraded when `*` turned out to **pass**
    `LiteralSequenceExpression`'s `^[A-Z*\-]*$`, so before the enricher guard it would have been handed
    a content-addressed id for a state that is not a sequence. Note what could *not* have caught it:
    **severity**, since the indel branch is also tier-blame — only the reason differs, which is why the
    test asserts the reason.

  An indel is **never** a "mismatch": this tier cannot recompute one, so it can only report that it did
  not check, and saying otherwise would claim a verdict never reached. Multi-allelic is not
  unverifiable either — `vrs_id` is one id per ALT and each is checked alone. Full matrix in
  [COMPILER.md](COMPILER.md). Two mechanics that came with it: `_verify_vrs_ids` takes **no mode
  argument** (there is nothing left for it to switch on), and because it runs in both `validate_spec`
  and `compile_module`, its warnings are **de-duplicated on the message** the way ploidy's already
  were — otherwise 185 alleles print 370 lines.

- `@ga4gh-vrs-core-dep` — **`ga4gh.vrs` is a CORE enricher dependency, not `[dev]`.** Substitution minting is stdlib in the
  format tier; indel normalization goes over the **seqrepo REST** proxy (14 pure-Python packages — the
  plan's `[extras]`/`pysam`/multi-GB-seqrepo assumption was wrong). `--offline` is the only thing that
  degrades minting to substitutions-only. Never add `ga4gh.vrs` to format or compiler: the compiler's
  verify pass is stdlib on purpose.

- `@refget-raises` — **`refget_accession` RAISES for a non-GRCh38 build** (it must — a caller asking for GRCh37 should
  hear "not built", not get a GRCh38 answer). Every call site therefore has to catch
  `UnsupportedBuildError`; one that didn't used to abort a whole compile over a single row.
  **`refget_supports_build` is the yes/no form and the two now read ONE predicate** — they disagreed on
  `None`/`""` (the guard said `True`, the lookup raised) while the guard's docstring claimed to answer
  *"the question `refget_accession` raises on"*, so the guard a caller reaches for **to avoid** the
  exception was the one input that handed it over (R2-10). The reasoning that produced it is the part
  to avoid repeating: *"an unset build is the format's default"* imports a **spec-layer** fact into the
  **identity** layer. `ModuleSpecConfig.genome_build` defaults to GRCh38 and so does each signature,
  but an explicitly passed `None` is not an omitted argument — it is a caller who has not threaded the
  row's build through, which is what `test_build_call_sites.py` walks the AST to prevent. Every other
  build gate in `vrs` already read it that way.

## Coordinates and the genome build

- `@start-1based` — **Every `start` in this codebase is the 1-based VCF position — do NOT convert.** The pipeline stores
  Ensembl's position (`rs1135071` → 5226799 everywhere), CPIC `sequence_location.position` and PharmVar
  `NC_……:g.` use the same convention, and `derive_vrs_allele_id` does the interbase conversion itself,
  once. The instinctive `-1` introduces an off-by-one. **This bullet used to open "Despite the `start`
  docstring saying 0-based" — that docstring was the bug, and it was fixed on 2026-08-06 only after it
  had cost someone 3,038 rows.** `describe`/`requirements`/`reference` print those descriptions, so they
  are the authoring contract, not internal commentary; an external author followed them, shifted four
  whole modules by one base, and every offline gate passed (`--strict` included, VRS ids minted *and*
  reported verified — a content-addressed id is a correct digest of the wrong input). Two durable
  lessons. **A known-but-unrated inconsistency in a printed contract is a live defect, not tidiness** —
  it sat in the ROADMAP as a low-severity blocker for the `end` column precisely because nobody had
  watched it produce a wrong module. And **Class-2 validate-by-redundancy assumes independence**: those
  modules shipped their own hand-built `resolution.csv`, so `resolution._verify` compared the author's
  convention against itself and agreed. `schema/tests/test_coordinate_convention.py` now pins the prose
  to what the minting code does with the number. Two more CPIC traps: `variantallele` carries values `HaplotypeRow.allele`
  rejects, in **two different kinds** that must not be conflated — **IUPAC ambiguity codes** (`R`), an
  uncertainty CPIC recorded and never expressible, and **deletion/repeat notations** (`DELTCT`,
  `AAAGGGGCG(2)`, 23 in CYP2D6), a grammar gap (RM5) a release could widen; `cpic.unusable_allele_reason`
  names which, and calling the second an ambiguity code was a false claim that survived until a real
  CYP2D6 draft. And activity scores are **inequality strings** (`"≥3.0"`), not numbers, so they don't drop
  into `MeasureBinRow`'s numeric bounds.

- `@restamp-for-build` — **A row is stamped before the module is known — so anything build-dependent must be re-derived by
  the compiler.** `VariantRow._freeze_identity` runs at construction, where `module_spec.yaml` is not
  in scope, so it always took `derive_variant_key`'s GRCh38 default. A `genome_build: GRCh37` module
  therefore minted GRCh38 VRS ids, silently, for years of the design — the `build` parameter and its
  fall-through-rather-than-lie guard both existed and were simply never reached.
  `compiler._restamp_for_build` fixes it after load, at **both** load sites (`validate_spec` and
  `compile_module` each read their own copy; fixing one leaves the artifact wrong). When adding
  anything else that depends on the spec, check whether the model can possibly know it.

- `@build-in-manifest-only` — **`genome_build` is in `manifest.json` and NO parquet column — so anything rebuilding a spec must
  read it, and three things didn't.** The bug above was fixed on the forward path and then re-entered
  twice more, because a corpus where **every** reference example is GRCh38 cannot tell "reads the
  module's build" from "writes `GRCh38`". `reverse_module` hardcoded the constant into both the rebuilt
  `module_spec.yaml` and `resolution.csv`'s own column, so `compile → reverse → compile` on a GRCh37
  module minted `ga4gh:VA.…` ids for GRCh37 coordinates — P7 broken *and* a false content-addressed
  claim, since a VA names a base on a sequence the module never referenced. (`resolve_from_table`
  **filters** on that column too, so the mislabelled table was also unjoinable.) And `enrich()` took
  `genome_build="GRCh38"` that **no caller ever passed**, making every `== "GRCh38"` gate inside it
  dead code: a GRCh37 module was resolved against GRCh38 and the answer written under its own build.
  The **frequency pass** was the fourth site: it fed every resolved row to gnomAD regardless of build and
  re-keyed it with `derive_variant_key` *without* passing one. gnomAD's id is `chrom-pos-ref-alt` and
  carries no assembly, so a GRCh37 coordinate is a well-formed request returning **a different variant's**
  counts, written under this module's key — with a GRCh38 VA minted on the way. Fixes:
  `compiler._genome_build_from_artifact` (manifest → explicit arg → default), `enrich.spec_genome_build`,
  and `gnomad.FREQUENCY_GENOME_BUILD` (a named constant precisely because it was the third
  build-confusion in one round). Three rules from it: **a parameter nothing passes is not a guard, so
  grep for the caller**; **any code calling `derive_variant_key`/`derive_vrs_allele_id` on a row must
  pass that row's `build`**, since the default silently mints GRCh38; and **`reference_examples/grch37_build/`
  must stay** or the corpus goes uniform again — `test_reference_examples_roundtrip.py` asserts more than
  one build is represented for exactly that reason. `test_build_call_sites.py` walks the AST and fails on
  a call that hands over an allele without a build, so a *sixth* site cannot arrive silently.

- `@build-injected` — **The build is INJECTED into a row, never authored on one — `AuthoredModel._genome_build` (RM36).** A
  model built from a CSV dict has no `module_spec.yaml` in scope, and a *property* (unlike
  `VariantRow.variant_key`) has no stored field for `_restamp_for_build` to correct afterwards — which is
  why `HeteroplasmyRow.variant_key` minted a GRCh38 VA on a GRCh37 module. `load_csv_rows` tells every
  row it builds; the attribute is **private**, so it is not a column, reaches no CSV or parquet, moves no
  digest, and `extra="forbid"` still rejects an author who writes one. Two shapes that were **rejected**,
  so don't re-propose them: per-row declaration (overkill — the build is module-wide) and **per-CSV, as a
  "service row"** — two files could disagree about one fact, a data table would carry a non-data row (P5),
  a copied row would drop it, and it would still not reach the model, since a loader parsing it already
  knows the build from the yaml. The rule generalizes: **anything module-wide that a row needs is told to
  the row at load, not stated on the row.**

- `@sig-not-build-independent` — **`content_signature` is reference-independent, NOT build-independent — the docstring said the wrong
  one.** True of the reference used to *resolve*; false of the *declared assembly*, which for a
  coordinate-authored module is the frame the numbers are in. Two modules with byte-identical CSVs and
  different builds describe loci 228 bp apart, and the content-dedup key hashed them equal — reachable by
  "lifting over" a panel through the yaml alone. `genome_build` now feeds the hash **only when
  non-default**, which is the existing omit-the-default normalization, not an exception: every GRCh38
  module keeps its signature byte for byte, so a 0.4 module still links to its own 0.5 recompile.

- `@ref-mismatch-causes` — **A "ref mismatch" has three causes, and the coordinate one is the common one.** `verify_reference_alleles`
  reads **one window** spanning a base either side of the claimed span (not three reads — the rows needing
  the diagnosis arrive in thousands) and reports a shifted `start` when exactly one neighbour carries the
  authored `ref`. Both neighbours matching is ambiguous, so it withholds — tri-state, as everywhere else.
  Don't "improve" it by inferring the direction from the module's dominant shift: that is a per-row claim
  built from an aggregate. A shifted row sets `distorts_the_allele_id` **whatever the claimed length**,
  because the id is minted at the authored position; the old length-only test plus its reassurance ("the
  minted allele id is still the true allele at this position") was true of the recorded position and
  worthless when the position is the defect. Sensitivity is structurally partial (~3 rows in 4 — a
  neighbour that happens to equal `ref` hides it), and both docs say so rather than implying a clean bill.
  Findings are grouped by **reason** via `summarize_ref_mismatches`; 56 lines became 2 on a 69-variant
  module.

- `@old-assembly-vs-shift` — **The ±1 shift reading is CONFIDENT AND WRONG on an old-assembly coordinate — RM48 is what orders the
  two (0.6).** Real instance, not hypothetical: take `reference_examples/grch37_build/`'s own two HFE
  rows (`6:26093141 G>A`, `6:26091179 C>G`) and declare `genome_build: GRCh38` — the RM48 scenario
  exactly — and `_read_with_neighbours` reports "coordinate shifted 1 base to the right" for **both**,
  because a neighbouring base equal to the authored `ref` is a one-in-four event and the true variants
  are 228 and 411 bases away. The old-assembly pass reads the same coordinate on GRCh37, finds the
  authored ref *and* a dbSNP record starting there, and names `rs1800562`/`rs1799945`. Four things to
  keep straight. **Two explanations printed side by side with nothing to order them is the defect**, so
  `summarize_build_diagnoses` says which supersedes — and only the two strong tiers do
  (`dbsnp_corroborated`, `multi_base_match`); a **single-base** GRCh37 match rests on exactly the same
  one-in-four coincidence as the shift reading, so ordering those two would invent a verdict. VCF 4.4
  §1.6.1.4 gives a second competing explanation for any single-base disagreement — an ambiguous
  reference base must be reduced to the first alphabetically, so an authored `A` may be a lossily
  reduced `R` — and the message carries it. **The roadmap's stated blocker was checked and is false**:
  `grch37.rest.ensembl.org` is permanent, unauthenticated and same-shaped, so there is no chain file, no
  provisioned asset and no new licence; `PRIMARY_CONTIG_LENGTHS`/`CONTIGS_ONLY_IN` are 25 numbers and
  ~200 names per build, committed beside `PAR_GRCh38` and re-derived by a network-gated test. **No
  GRCh37 refget accession was added** — a length answers "could this exist", an accession is what an
  identity is a function of, and the second is RM15. And **recovery reports, never fills**: filling the
  rs-number would make resolution verify a value against the service that produced it, and `rsid` is
  `identity_bearing`, the sharpest refusal in `lookup._REFUSAL_BY_COLUMN`.

## Alleles: grammar, spelling, hosting

- `@non-nucleotide-spelling` — **A non-nucleotide allele in `ref`/`alts` is a SPELLING defect, and the tempting repair is illegal
  three ways.** `hosting_verdict("C/T", "T", "Y")` is `False` and rightly so — a substitution locus has
  no shared flank, which is what keeps the strand-flip check sharp — but the message then blamed the
  *genotype* ("the row contradicts itself" / "the source's allele list is incomplete"), both false when
  the locus is the thing misspelled. Fixed as a **diagnosis**: `alleles.non_nucleotide_reason` /
  `non_nucleotide_alleles` classify it, both "cannot host" sites name which, and
  `cpic.unusable_allele_reason` delegates to the same function rather than keeping its copy. Do **not**
  "fix" it by adding a nucleotide grammar to `alts`: **no `ref`/`alt`/`alts` column has one** (eleven
  columns, six models), so a grammar rejects `N` too; a module with `alts="Y"` compiles today under
  `best_effort`, so refusing it breaks **P3**; and the only non-ACGT allele in real variant records is
  `N`, already filtered by `clinvar_build` at the snapshot boundary. And do not "expand"
  `Y`→`C,T`: probed across **4,439,382** ClinVar rows and all sixteen modules, `R/Y/S/W/K/M/B/D/H/V`
  appear in REF or ALT **zero** times — the compressed-ALT-set reading that argument rests on has no
  instantiation. Full probe in ROADMAP's 0.6 idea-book. Keep the reasons' **consequences** separate
  (an uncertainty is permanent, a grammar gap is a release away, a symbolic allele is held and simply
  not comparable); appending one to every branch is the CPIC conflation, reintroduced once already
  inside its own fix. **`validate_allele` has TWO users, not one** — `HaplotypeRow.allele` and
  `VariantRow.effect_allele`. This bullet and `alleles.py`'s docstring both said "exactly one,
  `HaplotypeRow.allele`" from 0.5 until RM5, and the count is precisely what someone sizing a grammar
  change reads; the shared diploid grammar `AuthoredModel._validate_genotype` is a third site again
  (`VariantRow` required, `PharmVariantRow` optional). `docs/ROADMAP.md` and `docs/CHANGELOG.md` still
  carry the old claim in their historical entries — leave those, they record what was believed then.

- `@symbolic-alleles` — **A symbolic/structural allele is HELD by the grammar since 0.6, and its length rides in the token
  (RM5).** `<DEL:1500>`, `<CNV:TR:30>` — VCF 4.4's closed five (`DEL/INS/DUP/INV/CNV`) at the first
  level, open subtypes below it. Five things not to redo:
  - **The length is in the token because SVLEN is `Number=A` — one value per ALT.** A scalar authored
    column cannot describe `alts=<DEL:5>,<DUP:9>`, a parallel-array column is the desync shape
    `vrs_id` needed two guards for, and `genotype`/`effect_allele`/`HaplotypeRow.allele` have no
    row-level home for it at all. An authored column is also *full cost* under the 0.6 charter
    amendment, on every table that can carry an allele.
  - **The schema accepts a lengthless `<DEL>`; the compiler refuses it.** Forced, not chosen: a
    model-level rejection is a load error, fatal in **both** modes, and the decided behaviour is
    warn-and-drop under `best_effort`. Don't "tighten" it back into the models.
  - **This is the first check that DISCARDS an authored row, so the warning says DROPPED.** It does not
    break P7 (the fixed point is claimed under `strict`, which refuses here), but `reverse` cannot
    re-emit what never reached the parquet. Droppable only where a row *is* a rule (`variants.csv`,
    `pharm_variants.csv`); on `haplotypes.csv`/`heteroplasmy.csv` it is fatal in both modes, because
    dropping a defining variant or a bin makes a quietly **different** module, not a smaller one.
  - **`hosting_verdict` returns `None` for a symbolic allele — never `False`** — and the guard sits
    directly under the raw-string match, because everything below it is arithmetic over characters a
    symbolic token does not have. Two differing *stated* lengths are still undecided: symbolic notation
    exists for imprecision, so a summary length is not an event size.
  - **Rejected and staying rejected:** VCF's `##ALT=<ID=…>` declaration mechanism and arbitrary named
    IDs (unasked extendability in the layer a human reads); a readable alias carrying its own sequence
    (two spellings of one allele for comparison and identity to resolve). Consequently 5-HTTLPR is
    authored as a plain **indel** (its sequence is known, so the standard says spell it) and CPIC's
    IUPAC codes stay unexpressible. `<*>` is *not* one of the five — it is an observability claim.

- `@hosting-tri-state` — **Hosting is a THREE-valued question — `hosting_verdict`, not `genotype_fits` (RM31, shipped).** One
  indel has several valid spellings: ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the
  same 2 bp deletion, and comparing allele *strings* resolved it to `not_found` while asserting a dbSNP
  merge that does not exist. `alleles.parsimony_reduce` (format tier, stdlib) strips the flank a
  *collection* shares, so both reduce to `{'', 'AG'}`. Four things about it that must not be "simplified":
  - **No position is passed in, and none can be.** The row records *no coordinate* — `clinvar_draft`
    prefers the rsID and the model forbids `ref`/`alts` without a coordinate — so the authored genotype is
    spelled in a frame the row never states. A genotype naming *two* alleles carries the frame instead.
  - **The raw comparison runs FIRST.** Normalization may only ever *add* acceptances, which is what keeps
    every compiled digest and expansion stable; a property test over the reference examples pins it.
  - **The confident negative is about event SIZE.** Re-anchoring moves an indel, it never changes how many
    bases it adds or removes, so differing sizes prove different variants (`rs281864532`: 1 bp insertion
    *and* 2 bp deletion under one rsID). Same size, different content → `None`, and the locus is **kept**
    with a message saying nothing was decided. A substitution/MNV locus has no flank, so a mismatch there
    is `False`, not `None` — that is what keeps the strand-flip check sharp.
  - **`_check_allele_membership` must ask the same predicate.** It did its own exact set difference, so
    once resolution reconciled a spelling and expanded onto the locus, membership refused the same module
    under `strict` — the compiler contradicting itself. Kleene-OR over the loci, matching the union reading.
  Residual: the authored `genotype` keeps its source's frame, so a row can carry `genotype=C/CAG` beside
  `ref=AGAG`. A consumer applies the same reduction (`just_dna_format.alleles` is public for that);
  rewriting the authored cell is the parked co-authoring item.

- `@rsid-not-per-allele` — **An rsID is position/multi-allelic-level, not per-allele.** One rsID (`rs33922842`) legitimately spans
  pathogenic + benign + uncertain alleles at one locus, so clinical identity keys on `variant_key`+
  genotype, never rsID. The reverse pos→rsID back-fill is therefore **allele-aware**
  (`resolver._lookup_rsid_candidates`, shared by `clinvar`): 0 allele-exact candidates → leave `rsid`
  null (don't guess); 1 → attach; ≥2 (a dbSNP merge) → deterministic pick + `status="ambiguous"` +
  `ResolutionRow.rsid_alternates`.

- `@rsid-absent-two-readings` — **`absent` for an rsID means typo *or* withdrawn, and the API cannot separate them.** `rs11273140`
  (withdrawn) and `rs2000000000` (never assigned) return byte-identical responses, so
  `identifiers.classify_rsid` answers `absent` and the message names **both** readings rather than
  guessing — a typo is fixed, a retraction may leave the annotation describing nothing. A test asserts
  the equality on the *recordings* so a future dbSNP release that separates them fails loudly.
  **`VALID_RSID_STATUS` is `{live, merged, absent, withdrawn}`** — four members. This bullet used to say
  three, on the reasoning that nothing could ever produce the fourth, and that is the confusion to avoid:
  "nothing emits it today" is a fact about the live API, while the member exists for the two cases the
  API is not the authority on — a curator who has *established* a retraction records it by hand, and a
  future source that can tell the two apart starts emitting it without a vocabulary change P3 would
  otherwise make a one-way door. Its severity is not `absent`'s either: see the `withdrawn` bullet under
  Resolution, which is fatal in **both** modes.

- `@ncbi-merge-oracle` — **For rsID merge status, NCBI is the oracle — not Ensembl.** Ensembl resolves *some* merged rsIDs
  (`rs77121243` → `rs334`) and returns **HTTP 400 on others** (`rs3216883`, which dbSNP correctly
  reports as merged into `rs3051860`), so Ensembl alone would misclassify a merged rsID as
  unresolvable. `esummary db=snp` is batched and authoritative: `snp_id` != requested + `merged_sort=1`
  means merged, an `error: "cannot get document summary"` record means absent. **No live endpoint
  reports a distinct "withdrawn" state** (the *vocabulary* has one — see the `absent` bullet above): an
  rsID retracted for mapping/clustering errors (`rs11273140`) is byte-identical
  to one never assigned (`rs2000000000`) across esummary, esearch and Ensembl, so a message about an
  absent rsID must name *both* readings — typo vs withdrawn-and-the-annotation-may-be-worthless — and
  assert neither. (`misc/rs_unsupported_b157.txt` looks like a withdrawn registry and is not; it is a
  one-off build-157 ClinVar-parsing incident list.) And when picking a negative-test rsID, check it:
  `rs999999999` looks synthetic but is a real variant at chr6:58247859.

## Resolution and the round trip

- `@resolution-reversible` — **Resolution must be REVERSIBLE — read [COMPILER.md § Resolution](COMPILER.md) before touching
  it.** One rule: `compile → reverse → compile` reproduces the module, or `strict` refuses. The finite
  matrix of authored-shape × mishap is enumerated and enforced in
  `compiler/tests/test_resolution_matrix.py`; a new resolution behaviour adds a row there.
  - **`authored_ident` is what makes it work.** It records which of `{rsid, chrom, start, ref, alts}`
    the author supplied, stamped at load beside `variant_key` and materialized to `weights.parquet`.
    Reverse re-emits exactly that shape. `variant_key` **cannot** substitute for it: it answers "which
    variant is this", not "what did the author write" — identical for an rsid-only row and an
    rsid+coordinate pair, and after expansion it is the per-locus allele id with no trace of the rsid.
  - **An expansion collapses back to ONE authored row on reverse.** Until 0.5 it emitted N position-only
    rows, which moved `content_signature` on every rsid-authored module *and* wrote each locus out
    carrying the single authored genotype — fabricating annotations for loci that genotype cannot
    describe (three such rows in `reference_examples/pathogenic_clinvar/`).
  - **A locus that cannot host the authored genotype is dropped from the expansion**
    (`resolution.hosting_verdict`). The predicate is **shared three ways** — the compiler, the enricher's
    deprecated DuckDB path (digest parity is a documented guarantee) and `enrich()`'s forward
    rsid→loci resolution, which since this round leaves such a record out of `resolution.csv`
    entirely. Resolution is allele-aware in BOTH directions now; the reverse back-fill always was.
  - **`withdrawn` refuses in BOTH modes**, unlike `merged`/`absent` (strict-only). Nothing automated
    emits it — the API cannot tell a retraction from a never-assigned id — but it is a real vocabulary
    member for curator-recorded retractions and for a future source. Don't drop it as dead code.
  - **`ambiguous` is stable and still refuses in strict.** The enricher writes ONE row (deterministic
    pick + `rsid_alternates`); a two-row fixture is fabricated and will invent an instability that does
    not exist. Strict refuses because a pick among equals is not a finding, not because anything is lost.

- `@membership-union` — **The allele-membership check compares against the UNION of every locus a key resolves to**, on the
  authored rows before `resolve_from_table` — a per-expanded-row comparison flags the siblings the
  genotype was never about. Severity is the mode ladder, never an unconditional error. Pinned by tests.

- `@snapshot-pipe-alt` — **The Ensembl snapshot's `alt` is PIPE-joined; every other link uses commas.** A multi-allelic site
  is one snapshot row (`A|C|T`), not one row per alt. `resolver._snapshot_alleles` normalizes at that
  boundary — don't remove it, and don't "fix" it by widening the hosting predicate instead (the locus-dict
  contract is comma-separated, and the snapshot is the deviation). This silently broke *all*
  cache-resolved genotyped variants until 0.5: the comma-only split made `A|C|T` one opaque allele, so
  the allele-aware filter dropped every locus and `rs4244285` with genotype `A/G` came back
  `not_found`. Unit fixtures were comma-separated, so only a real cache showed it — when adding a
  resolver fixture, use the pipe shape for multi-allelic sites.

- `@resolution-reads-pgx-tables` — **Resolution reads `pharm_variants.csv` and `haplotypes.csv` too, not just `variants.csv`** (0.5,
  `enrich._collect_subjects`). PGx modules carry no `variants.csv`, so they used to enrich to an empty
  `resolution.csv`. Subjects dedupe by `variant_key` with **`variants.csv` first** — it alone carries
  `alts`, a fact column, so a PGx row winning would move `artifact.digest`. PGx tables key **without**
  `alts`; a `HaplotypeRow` passes its defining `allele` to the shared `hosting_verdict`.

- `@rsid-alternates-closed` — **Reverse dropping `rsid_alternates` is NOT a bug — closed, don't re-flag it.** This was filed as an
  open loose end and is neither open nor fixable in the writer. `_write_resolution_csv` rebuilds the
  table from `weights.parquet`, which by design carries **no provenance at all** (it already resets
  `source="reversed"`, `status="resolved"`, blank `fetched_at`). `rsid_alternates`/`rsid_current`/
  `rsid_status` are outside the fact set *precisely* so they never reach the artifact, so the data does
  not exist for reverse to emit; adding the column names would produce a permanently empty header.
  Recovering them after a round-trip means re-running the enricher.

- `@sidecar-authoritative` — **`enrich()` treats an existing `resolution.csv` beside the spec as authoritative** (merged, never
  clobbered) — and so do the two new passes for `frequencies.csv` / `gene_metrics.csv`, and VRS minting
  for an existing `vrs_id`. To regenerate after a machinery change you MUST **delete the sidecar first**,
  or stale rows silently persist (this bit me while regenerating the reference example).

  **Since 0.7 that delete is free, and the merge behaviour did not change** (RM124). The merge still
  gap-fills — re-asking every subject on every run was explicitly rejected, since it would put the full
  resolution time on every pass. What changed is what a recorded row can *contain*: a correction now
  lives in `overrides.csv`, so a derived row carries no authored content and deleting the file loses
  nothing. Read the two halves separately, because the old sentence conflated them: "a re-run does not
  refresh what is recorded" is still true, and "deleting discards the curator's rows" is not.

- `@overlay-not-inside` — **`overrides.csv` is applied, never merged into the table it corrects, and
  four things about it are counter-intuitive enough to be worth the entry** (RM124, 0.7).

  **It is a third category and is registered in neither table registry.** Not `_TABLE_KINDS` (those are
  the module's own annotation tables: one of them satisfies the "at least one recognized table" check
  and each is a `LEAD_PARQUETS` member the reference consumer probes on — a directory carrying only
  corrections is not a module). Not `_FACT_TABLES` and therefore not `_DERIVED_FILES` (those are
  machine-produced and fact-hashed). It *is* in `_INPUT_FILES`, `spec_tables` and `_KNOWN_SPEC_FILES`,
  because a human writes every row.

  **It carries a parquet anyway, and that is forced.** `reverse_module` rebuilds a spec from the
  artifact and has nothing else to read the corrections back from, so without `overrides.parquet` the
  round trip would silently discard every one of them and move `content_signature` — Principle 7.
  **What keeps an already-published digest still is its absence, not its slot**: `artifact_digest` sorts the file listing by name before hashing, so a tuple position is invisible to it — what protects an already-published module is that it carries no `overrides.csv`, so the file is absent from its listing entirely. The
  first version of this note said the opposite, and it was a false reason for a true conclusion — the
  kind that survives review because the answer it gives is right today.

  **No operation reports its own no-op, and the reason is the round trip rather than tidiness.**
  Reverse emits the post-overlay table plus the overlay, so on a recompile update-already-equal,
  insert-already-present and suppress-already-absent are all three true of a healthy module. A warning
  on any of them would fire on every round-tripped module and make it disagree with itself on
  `manifest.compilation.warnings`, a published field. **The price is real and is stated rather than
  fixed**: a `suppress` with a typo'd subject does nothing, forever, and cannot warn. The one mismatch
  stable on both laps is an `update` reaching no row, because an update never creates one.

  **An override may not write the table's own subject or member column**, and this is the same rule
  read from the model's side. An update that moved a key would apply once and then leave its own
  overlay row matching nothing — a warning that appears on a module's round trip and not on the module.
  Re-keying a derived row is a suppress plus an insert.

  **A key cell is matched as the model STORES it, and getting this wrong broke the fixed point with a
  capital letter.** The overlay carries raw author text; the derived rows carry canonical values. The
  first implementation compared the two directly, so `FrequencyRow.population` — which
  `normalize_population` lowercases — meant an overlay `member=AFR` matched no row of a table full of
  `afr`. All three operations went wrong differently and the worst went wrong **silently**: the
  `insert` believed its row was absent and appended a duplicate, so every `compile → reverse →
  compile` lap appended another copy, and nothing caught it because `frequencies.csv` is in neither
  `_TABLE_DUPE_KEYS` nor the frequency checks. The `suppress` removed nothing and the `update` warned
  that a row plainly present "is not carried". `locus_index` is the same shape one type over (`"01"`
  is `1`).

  The repair canonicalizes through the **model** — write the cell onto a real row of the table and
  read back what it kept (`_canonical_key_cell`) — rather than through a table of per-column rules,
  which would be a second copy of every validator. And an `insert` places its row by the **built**
  row's subject, not the overlay's spelling, or the row lands at the end of the table instead of the
  end of its group. Found by review, not by the suite: the P7 test used `resolution.csv`, whose key
  columns happen to normalize to themselves.

  **A derived row whose member column is NULL cannot be suppressed at all**, because an empty `member`
  already means the whole group — `gene_validity.csv` rows with no `assertion_id`, and
  `clinical_assertions.csv`'s `not_found` rows. A sentinel for null was refused (a second key grammar
  inside the one column that exists to have only one); the refusal names the case and points at the
  group-scoped `update` or a re-derivation.

  The covered set is **seven** — every merge-not-clobber derived sidecar but `licensing.csv`, which has
  its own merge path and is the one derived table a human is told to write. The proposal's "six" was a
  miscount that enumerated nothing; `test_overrides_overlay.py` asserts an equality against
  `_FACT_TABLES` rather than a floor.

- `@rm43-positional-fill` — **Resolution reaches the positional tables too, since 0.6 (RM43), and
  `authored_ident` is the column that makes it legal.** `_apply_positional_resolution` joins the
  injected `resolution.csv` onto every positional 0.4-family table, in `validate_spec` *and*
  `compile_module` — filling in place, before `_build_table` materializes the rows and before
  `_check_positional_joinability` counts what is still unplaced. It returns `(warnings, applied)`, and
  `applied` is load-bearing rather than bookkeeping: it is what lets the joinability warning say *why*
  a row is unplaced instead of asserting a reason the join never reached. Four gates turn it off — no
  table to consult, no positional rows, a non-GRCh38 module (RM15, and it says so), a caller asking for
  no resolution — and they differ in everything except the one consequence downstream, that nothing was
  looked up. **`authored_ident` on `HaplotypeRow`/`PharmVariantRow`/`MeasureBinRow` is the prerequisite
  that had to ship first**, frozen at construction so that a coordinate filled at compile time does not
  return from `reverse_module` as though its author had typed it. That is the whole reason the fill
  moves `artifact.digest` and leaves `content_signature` alone.

  **Pre-0.6, this entry said the opposite, and the reasoning is worth keeping** because it is what the
  repair had to satisfy. Surfaced in 0.5.3: `_build_table` is `model_dump()` → parquet, so one of these
  rows kept the coordinates its author typed — none, for an rsid-authored module — and the table joined
  to no VCF. The naive repair ("just join `resolution.csv` on `variant_key`") breaks P7, because
  `reverse_module` rebuilds the CSV from the parquet and a filled cell returns as *authored*, moving
  `content_signature` and not merely the digest. `VariantRow.authored_ident` already existed to prevent
  exactly that and no 0.4-family model had one; the 2026-08-11 charter amendment is what made adding a
  stamped column per positional table 0.6 work rather than 1.0. What 0.5.3 shipped in the meantime was
  legibility only — `_check_positional_joinability` reporting, per table, how many rows cannot be joined
  and how many of those `resolution.csv` **could** place, the second count being what separates "never
  enriched" from "the answer exists and this tier does not apply it". That warning is still there and
  still fires in both modes, because rsid-only identity remains legal by the models' own rule — what
  changed is that the remedy it was pointing at now exists.

  **The three traps this entry used to end on are all closed, and are recorded because a reader who
  learned them elsewhere will still be carrying them.** `PharmVariantRow` **has** `alts`.
  `variant_key` is a `stamped_identity_field` on `HaplotypeRow` and `PharmVariantRow`, not a property,
  so it *is* in the parquet and a consumer can join these tables to `weights.parquet` on it. And
  `fully_resolved` being `all(...)` over `VariantRow` — hence vacuously `True` for a table-only module —
  no longer makes the manifest's trust rule unsafe, because RM44 put a count in front of it: the rule is
  `resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`, and the conjunct is
  what stops a vacuous truth reading as an achievement.

- `@unreachable-not-absent` — **An UNREACHABLE source is unchecked, never absent — and the artifact must not say otherwise (S20,
  0.5.4).** `EnsemblResolver.resolve_rsid` returned `([], None)` both when Ensembl answered with no
  GRCh38 locus and when the request never completed, so a failed lookup rendered as a definite negative:
  `loci: []` plus "live Ensembl has no GRCh38 locus for it either". That pair is exactly the fingerprint
  of a **fabricated** rsID, and a consumer auditing a machine-written document put two published
  variants (`rs6567160`, a long-standing MC4R BMI locus, and `rs13010010`) in the fabricated pile on a
  flaky run. Three outcomes now: loci, `[]` for an answered absence (carrying its source, so
  `hint.checked` records *which* link said nothing), `None` for could-not-ask. Three things to keep
  straight. **A 4xx is an answer** — Ensembl 400s on rsIDs it cannot resolve — so only a 5xx, a
  transport error or a timeout is unchecked. The **artifact half was worse and invisible from
  `lookup_variant`**: `enrich()` wrote `ResolutionRow(status="not_found", source="ensembl")` for a
  request that *failed*, stating in the injected table that Ensembl was asked and said no. No row is
  written now — the key stays `unresolved`, so `strict` still refuses and `best_effort` still warns, but
  nothing claims a source answered — and `EnrichmentResult.unreachable_rsids` names them, distinct from
  `unresolved`, which is silent about why and so cannot tell a re-runnable failure from a real absence.
  It **warns in both modes**: no authored edit clears a failed request (P5, the `not_covered` class).
  And the argument was already four lines below in the same function, where the non-GRCh38 branch
  declines to write `not_found` for precisely this reason. Generalize it: **when a function has two ways
  of returning nothing, check whether any caller renders them as one sentence.**

## Checks: where they run, and what severity means

- `@parity-by-check` — **Audit `validate`/`compile` parity by CHECK, not by TABLE — that is how the third instance hid.**
  `_check_allele_membership` stayed compile-only through the pass that fixed `_verify_vrs_ids` and
  `_check_p_value_num`, because that pass asked *which tables does validate read* and this check reads
  **authored** rows. It is a mode ladder, so `validate --strict` blessed modules `compile --strict`
  refused. The rule is unchanged and now applies to three checks: pure computation over injected or
  authored bytes with no `output_dir` belongs in `validate_spec` too. Two mechanics to copy when moving
  one: `compile_module` runs `validate_spec` in **best_effort** whatever its own mode, so the compile
  side must still re-run the check to reach the real severity, and its warnings need de-duplicating on
  the message (`_check_contig_ploidy` is the existing model).

- `@which-loop-calls-the-checker` — **"Keyed kind ⇒ dupe-checked" was never the dividing line — which
  LOOP calls the checker was.** `_validate_table_kind` holds the duplicate-row rule and `validate_spec`
  called it from the `_TABLE_KINDS` loop only, so `sources.csv` — a `_FACT_TABLES` member, keyed
  `(source, layer)`, dupe-refused by drafting since S48 and merged on that pair by
  `licensing.merge_sources_csv` — was the one keyed table nothing checked. Appending an exact copy of a
  row compiled green under `--strict`: no warning, a moved `source_signature`, and a pair free to carry
  **opposite `commercial_use`** in the one file the compile gate reads. Two things to carry. Registering
  the model in `_TABLE_DUPE_KEYS` alone would have done **nothing** — write the red test first and let
  it prove the wiring, because a map entry that no loop consults looks exactly like a fix. And when two
  registries hold the same kind of rule for two families of table, ask what the split is *for*: here it
  was accidental, so the call site widened and the second registry (`draft._CORE_DUPE_KEYS`, which was
  carrying `SourceRow` only because the compiler had no key for it) gave the entry back. (RM107.)

- `@field-description-is-a-claim` — **An analogy inside a `Field(description=…)` is a claim a reader
  will act on, and it does not travel with the field.** Three shipped strings said the authored
  `license` was "advisory and registry-overridable, exactly like `module.version`" — checked in the
  registry's own checkout, its publish path never writes that field. `module.version` really is stamped,
  which is exactly how the sentence survived review: the analogy is true of the field it was copied
  *from*. What the compiler actually does with `license` is the opposite of overriding it —
  `_check_declared_license_agrees` compares it against the annotation-layer sources and warns in both
  modes. Two descriptions were involved, so this reached authors through `describe_table` /
  `authoring_reference`, which is the most-read documentation in the repo. When you catch a doc string
  and the code disagreeing, **make one side true and say which** rather than softening the sentence.
  (RM111. The item cited `normalize.py:40` as the third site; that line is the `IDENTITY_AUTHORITY_KEYS`
  note, which is correct about the identity keys — the real third and fourth sites were
  `manifest.py`'s module docstring and its own `license` field.)

  **A vocabulary's members have STANDING, and a flat list publishes them as peers (S80, RM145).**
  `state` was described as `One of: risk, protective, neutral, significant, alt, ref` while `derive.py`
  called two of them *the retired descriptors* and mapped both to `unknown`. A consumer whose authoring
  surface passes our descriptions through verbatim — which is the contract we want them to keep, since
  a restated vocabulary drifts — therefore offered an agent six equal choices, and the reporter had to
  read `derive.py` in their own `.venv` to author one cell. Measured: 377 `risk`, 4 `neutral`, and zero
  uses of the other three across the sixteen examples.

  Three things to copy. **Group by which axis a value was really on**, not by live-versus-dead: the
  report asked for *current | retired* with `significant` among the retired, and that would tell an
  author it means nothing when it means something the column is the wrong place for. **Name each
  group's successor** — a standing with no destination is a warning nobody can clear, which is P3's own
  test for whether a deprecation belongs in a minor. And **assert over the vocabulary, never against
  the prose**: a test keyed on the exact sentence passes for a description that lists all six under one
  heading again.

- `@validation-ceiling` — **Know the validation ceiling before adding a check.** [COMPILER.md](COMPILER.md) opens with
  *What the compiler can and cannot validate*: three strengthening classes it **can** do (formal
  conformance → validate-by-redundancy → content-addressed self-verification, which is the class VRS
  moved `vrs_id` into) and a table of **inescapable blind spots** that follow from what the tier is.
  The compiler is an assembler/linker, not a truth oracle: it proves well-formed and self-consistent,
  never *true*. When you find something it "should" catch, check that table first — several entries are
  permanent by charter, and what cannot be validated is instead made **legible** (`source`, `dataset`,
  `status`, `authorship.kind`, the signatures). Adding a check that needs a reference means adding it
  to the **enricher**, not the compiler.

- `@a-recorded-judgement-is-a-fact` — **A judgement another tier already made and RECORDED is a fact
  the compiler may gate on, and discarding it at the tier boundary is its own defect (S78, RM143).**
  `strict` means *reproducible*, never *right* — the compiler has no reference and cannot check a
  coordinate, and that line does not move. But `enrich --strict` refused a GRCh37 coordinate pasted
  into a GRCh38 module with a diagnosis naming the rs-number to author instead, `enrich` best-effort
  wrote the table, and `compile --strict` then built it **silently**. The answer existed and had no
  reader.

  **The gate keys on a record, never on a re-run.** `build_disagreement_error` reads `findings > 0` on
  `verification.json`'s `genome_build_agreement`; the compiler adds no reference, no network and no
  opinion, so P2 is untouched. Re-running the check there was the reporter's own preferred repair and
  is impossible: `resolution.csv` holds **one** coordinate, the one the author wrote, so there is
  nothing to compare against without fetching.

  **Which check, and the principle that picks it.** Only the one whose findings mean *one authored file
  contradicts another* — the rows are on a different assembly than the declared `genome_build`. Every
  other recorded finding is a disagreement with an **outside archive**, where the archive is the stale
  side often enough that failing a build would have the format arbitrate someone else's dispute. The
  tempting generalisation — escalate every recorded finding under `strict` — would fail a build over a
  ClinVar disagreement the cross-check deliberately refuses to fail on. Pin the non-escalation with a
  parametrized test, `reference_allele` included: it produces this diagnosis's *input* and still must
  not refuse alone, because a ref mismatch has three causes and one is an assembly.

  **Three silences to test, because each would be worse than the defect.** No attestation (an
  unverified module is the ordinary case — refusing on absent evidence reads unknown as wrong);
  `findings=0` (a clean bill — key on findings, never on the record's presence); and `skipped`, which
  is what `--offline` writes, where nobody asked. And place it **ahead of `output_dir.mkdir()`**, like
  the licence gate, or the refusal has already written something.

- `@enrichment-is-validation` — **Enrichment is partly validation, by design.** The enricher is the only tier that can compare
  authored data against reality (format/compiler are inject-only). Every such check **reports, never
  repairs** — rewriting an authored value destroys the evidence of an upstream bug — and severity
  follows the mode (`best_effort` warns, `strict` refuses). Add new checks in that shape; see the table
  at the top of [ENRICHER.md](ENRICHER.md).

- `@validate-refuses-all` — **`validate` must refuse everything `compile` refuses — it exempted four of the twelve tables.** Both
  loops in `validate_spec` iterate `_TABLE_KINDS`; `resolution.csv` and the four fact sidecars are
  `_FACT_TABLES`, which it never read, though `compile_module` refuses on a bad row in any of them.
  The authoring skill's step 6 puts `validate` immediately before `compile`, making it the author's
  pre-flight, so a green pre-flight then a refusal sends an author hunting a change they did not make — and the worst case shipped: the **licence gate** reads
  `sources.csv` alone, so a module drafted entirely from a no-sale source with no `declared_use`
  validated clean and refused to compile. Rule for a new compile-side check: if it is pure computation
  over injected bytes and needs no `output_dir`, it belongs in `validate_spec` too. What stays
  compile-only is anything reading *resolved* rows.

  **The exemption is about resolved ROWS, not about the word "resolution" — that is how the third
  instance hid (S76, RM141).** Whether the injected table *can place* an authored row is arithmetic
  over bytes the pre-flight has already loaded; it needs no resolution to have run, and it was
  compile-only anyway. So `validate --strict` reported valid on every module whose `resolution.csv`
  covered some of its variants, and `compile --strict` refused it a second later. When you move one:
  **share the predicate rather than restating it** (`resolution.unresolved_subjects` is the function
  `resolve_from_table` applies) and **append the compile's error verbatim**, asserted by *equality* —
  a pre-flight refusing in its own words still sends an author hunting. And expect a **double-report**:
  `compile_module` runs the pre-flight whatever its own mode, so both passes emit the finding, measured
  at 24 warnings for 12 subjects before the message-dedup went in.

- `@ploidy-behind-resolution` — **A warning computed post-resolution is discarded — the second `_cross_validate_variants` call takes
  errors only.** That is right for a warning about authored cells and wrong for any whose input
  resolution fills. It made the non-diploid guardrail invisible to every rsID-authored row, i.e. to
  everything a drafting provider emits. `_check_contig_ploidy` now runs where `chrom` is final and
  keeps a pass inside `validate_spec` (which has no resolution step), de-duplicated on the message.

- `@no-rerun-with-counts` — **The converse of that bullet, and the one it was read as denying: a check whose input resolution does
  NOT fill must run on ONE side, and de-duplicating on the message cannot save it (0.6).** The rule that
  covers both is **re-run a check after resolution exactly when resolution changes its input, and never
  when the message embeds a count.** By the second pass `variants` is `outcome.variants` — the
  post-expansion list, one row per resolved locus — so a one-to-many rsID becomes N rows carrying one
  authored genotype, and the *same* finding is reported with a different count and different example
  keys. Message-dedup keys on the sentence, so two sentences differing only in their number never
  collapse and **both** reach `manifest.compilation.warnings`, which RM44 established is a surface
  consumers parse. That is a published field contradicting itself. Three separate 0.6 lanes shipped it
  independently and each was caught by its own code review, which is what makes it a pattern rather than
  a slip: measured at *"1 row(s)"* beside *"2 row(s)"* on an expanded rsID, and at **328 beside 337** on
  `pathogenic_clinvar`. Nothing is lost by staying in front of resolution when the check is warning-only
  in both modes — there is no severity for a re-run to recover, which is the whole reason the *mode
  ladder* checks re-run at all. The bullet above is not a counterexample: `_check_contig_ploidy` had to
  **move** behind resolution because resolution fills `chrom`, which is the same rule reaching the
  opposite answer from a different input. Ask what fills the input before choosing a side, and if the
  message carries a count, that alone settles it.
  **The countless case still owes the filter, and forgetting it is the recurring half (RM94, then RM106).**
  `compile_module` runs `validate_spec`, so every check reaching both sides runs twice by construction;
  the filter (`w for w in … if w not in all_warnings`) is what makes that harmless. `_frequency_checks`
  did not have one, so RM93's parity move published the `faf95` warning **twice** in
  `manifest.compilation.warnings` — measured at 15 warnings, 14 distinct. When a check moves to
  `validate_spec` for parity, look at what still calls it on the compile side in the same commit, and
  assert `len(warnings) == len(set(warnings))` rather than grepping for the one phrase.

- `@clinsig-never-escalates` — **The ClinVar `clin_sig` cross-check is the one check where `strict` does NOT escalate** — it warns in
  both modes, deliberately, because failing would make the format arbitrate a clinical dispute. The
  reason is documented at the call site; don't "fix" the inconsistency.

- `@tautology-zero` — **A check that cannot fail must not report a zero — `clinical.tautology_reason` (0.5.2).** A panel
  drafted by `draft_gene_panel` copied its `clin_sig` out of the snapshot the cross-check reads, so the
  comparison is a value against itself: 0 conflicts, necessarily, at 90% of the resolve time. The zero
  is the defect, not the cost — it looks like evidence. The skip keys on an **established** match, and
  every unknown (nothing recorded, another source, an unreadable release) leaves the check running. The
  reason lands on `EnrichmentResult.clin_sig_not_checked` because an empty conflict list otherwise means
  both "compared everything" and "never compared". Generalize it: **when a check's inputs can share a
  source, ask whether a pass is structurally guaranteed before reporting one.**

- `@jointly-satisfiable` — **Before adding a table-level check, ask whether its rules are jointly satisfiable.** Inclusive
  bounds + overlap-is-an-error + any-hole-is-a-warning cannot all hold on a continuous measure, so
  every `allele_fraction` table warned forever (RM35, now fixed). Integer kinds tile cleanly, which is
  why nobody noticed.

- `@gt-indices` — **A genotype that is all digits is a pasted VCF `GT`, and the diagnosis runs before the arity check
  (RM77).** `0/1` used to hit the nucleotide-grammar wall, which never says those are **indices** into
  the record's REF/ALT list — the single likeliest mistake in that column. `0/1/1` was worse *because
  of* 0.6: the ploidy fix gave it a confident, correct explanation of the two-allele ceiling, which is
  about the wrong thing, and a correct sentence aimed at the wrong defect sends the author to change
  the wrong cell. Changes no verdict; nothing legal can look like a GT cell. Related: **RM63's own
  replacement wording was false** — a pipe does not mean heterozygous, `C|C` loads — which is the third
  turn of one screw and the standing warning that *a correction is where this happens, because the
  reviewer checks the claim being removed, not the one going in.*

- `@gene-locus-relationship` — **Two true halves can make a false row — check the RELATIONSHIP, not the members (S24, 0.5.4).**
  `variants.csv` carries a `gene` column and nothing compared it to anything: `identifiers` asked HGNC
  whether a symbol was *approved*, which is a different question (`FTO` is approved whatever variant
  sits beside it), so a row pairing a real gene with a variant on another chromosome passed every check.
  Four of a reporter's seven rows were exactly that — real symbols beside invented rs numbers, which
  resolve anyway because dbSNP is dense enough that almost any seven-digit number hits something.
  **Machine-written sources are a real authoring input now, and this is the shape they fail in.**
  `check_identifiers` reports `GeneLocusConflict` per row and repairs nothing (which of the two halves
  is wrong is not knowable here). Four design points, none of which should be "improved":
  **chromosome granularity only** — the stronger interval version is refused in the code using the
  reporter's own argument, since `rs1421085` sits in an FTO intron and acts on *IRX3*/*IRX5* megabases
  away, so a row may legitimately name any of the three and an interval check would fire on correct rows
  until someone switched it off (a test pins that the FTO row stays silent). The join is against HGNC's
  **cytoband** (`16q12.2` → `16`, `mitochondria` → `MT`) and anything unparsed yields `None` rather than
  a guess, because a guess here becomes a false accusation about a row. For an rsID-only row the
  chromosome comes from an **injected `resolution.csv`** beside the spec and nothing is fetched — a
  currency check must not depend on a resolver. And a **pseudoautosomal** gene is exempt: `XG` straddles
  the PAR1 boundary, so X/Y there is a spelling, not a contradiction (RM32).
  `gene_loci_not_checked` carries the reason when the comparison could not run — same rule as
  `clin_sig_not_checked`, because an empty conflict list otherwise says both "compared everything" and
  "never compared".

- `@misspelled-tables` — **Unknown files in a spec directory are tolerated — and probing that contract found the case where
  tolerance is wrong (S16, 0.5.4).** A module may carry a README (every reference example does), curation
  notes, or a registry's `published.json` receipt, whose keys cannot go in `module_spec.yaml` because
  `extra="forbid"` rightly rejects them; none is read, hashed, or in `artifact.files`, so none can move
  `artifact.digest` (pinned by a digest comparison, not asserted). The exception is a **mistyped table
  name**: `varaints.csv` silently is not a table, so every row in it is dropped from a green compile.
  `_check_misspelled_tables` warns on an unknown `.csv` within one small edit of a known name, deriving
  the name set from the table registries. Keyed on **near miss** rather than "any unknown csv" on purpose
  — warning about every unrecognised file would undo the tolerance it sits beside.

- `@one-side-only-has-two-causes` — **A module the release sweep could measure on only one side is a
  fact about *whichever release lacks it*, and the two directions are not the same finding (RM139).**
  `gate_findings` refused a release when a module compiled on one side only, reading it as *a compile
  failed*. That is right in one direction and wrong in the other, and the very first real use of the
  gate — the 0.7.0 cut — hit the wrong one: RM70 added the optional `requires_callable` column to
  `pharm_variants.csv`, `reference_examples/cyp2c9_warfarin_grch37/` uses it, and 0.6.6 refuses that
  spec under `extra="forbid"`. Nothing had failed. The previous release cannot produce a **before**
  state for that module at all, so no like-for-like comparison exists, and the sweep saying nothing
  about it is correct rather than a gap. **It recurs in every minor that adds an authored column and
  exercises it in the corpus**, and equally for any reference example newer than the last release, so
  it is a standing shape and not one cut's accident.

  The split: **missing from AFTER** is a regression *in the release being gated* — fatal
  unconditionally, and it now carries the compiler's own errors, which `build_outputs` had been
  logging and discarding, so the operator is not sent to a log. **Missing from BEFORE** is a fact
  about the *previous* release, whatever the cause; even a bug in that release is not something this
  release did. A stale reused BEFORE directory holding a module the spec root no longer has reads as
  the first, which is the fail-safe direction and is why the runbook says fresh trees every time.

  **The repair that was refused, and the one that is not it.** The entry refused *let the record
  declare a module unmeasurable* as a per-module escape hatch weakening the gate exactly where its
  docstring warns, and that refusal was right about the shape it named. `ReleaseRecord.unmeasured` is
  not that shape, because the gate checks an **equality** over the set the sweep could not measure
  rather than a membership test (`@registry-completeness` again, three surfaces along): listing a
  module measured on both sides is reported as a note rather than obeyed, listing a regression does
  not save it, `as_record` refuses to mint a record over one, and a movement on a measured module
  gates however the list reads. The only strength given up is that *the previous release could not
  compile module X* no longer blocks a tag — which is not a fact about the release being cut. And
  `as_record` fills the field from the measurement, so it is the same forcing function `declared`
  already uses rather than a second kind of gate input beside it.

  The underlying shape is the recurring one: the 0.7.0 record stated the exclusion in its `evidence`
  sentence, honestly, and the gate cannot read prose — so the cut became a two-step a human had to
  wave through. A count or an exclusion that lives only in a sentence goes blind; a test now pins the
  field to the sentence rather than leaving them to be maintained side by side.

- `@warning-text-is-api` — **A warning's TEXT became an API, because the manifest carries prose and no field (RM44).**
  `compile_module` copies its warnings into `manifest.compilation.warnings` → `manifest.json`, and a
  catalog reindexing from a published manifest has nothing else: `fully_resolved` is `all()` over
  `variants.csv`, so it is **vacuously `true`** for a table-only module and the documented trust rule
  (`resolution_mode == "strict" or fully_resolved`) grants a badge to a module that annotates nothing.
  A consumer shipped that, then repaired it by substring-matching `"have no chrom+start"`.
  `compiler.UNJOINABLE_PHRASE` names the fragment and a test pins it in **both** places it must hold —
  emitted verbatim, and present in `manifest.compilation.warnings` — so a reword breaks our build
  instead of their catalog. Two durable points: **anything a consumer can only learn from a warning
  string is an unversioned interface**, so give it a structured field rather than asking everyone
  downstream to parse; and when a flag quantifies over a subset, **publish the denominator** —
  `vrs_alleles`/`vrs_alleles_identified` already argue exactly this one line above it in the same
  model, and nobody applied it to the flag.
  **`resolution_subjects` shipped in 0.6.0** — one additive integer, counted *after* the rsID expansion
  because that is the list the flag iterates, so the safe trust rule is
  `resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`. Three things it did
  **not** do, all deliberate: `fully_resolved` stays `bool` (consumers branch on it, so a `None` is a
  breaking read for all of them), `UNJOINABLE_PHRASE` and its test **stay** (the *unjoinable-row* count
  is a different question, still prose-only until RM43), and there is no second counter (RM45 settled
  three things into three homes). And one thing the item missed, worth generalizing: **the number was
  already available as `Stats.weights_rows`** — equal on every reference example, because the
  materializer emits one weights row per in-scope variant row. Publishing it beside the flag is still
  right (that equality is a property of the transform, not a contract, and `Stats` is documented as
  *display* facets), but **before adding a computed field, check whether another block already carries
  the number, and if it does, say in the code why the new home is the right one.**

- `@warning-code-names-the-finding` — **A warning code is a permanent published key, so it names the
  FINDING and never the site that builds it (RM131).** The channel was a flat `list[str]`: 14 kB of
  prose on a 190-row module, no count, and no way to tell a finding an author *can* clear from one they
  cannot — while `_BLAME_TIER`/`_BLAME_ROW` had been computing exactly that distinction all along and
  spending it on severity, as its own comment admitted ("blame decides severity and nothing else").
  `carried` and `warnings_summary` now ship beside `warnings`, which is unchanged down to the byte.
  Four things worth carrying forward:
  - **The vocabulary is the expensive half, not the container.** `warnings_summary` costs nothing;
    `VALID_WARNING_CODES` is permanent within the major under P3/P6, which is why the original entry
    deferred the whole item rather than shipping a plausible set. Three tempting derivations were all
    refused: from the pinned phrase catalogue (partial by construction, and a digest that silently
    omits findings is worse than none, because the reader believes it), from the emission site (a
    refactor renames a published key), and a cap or a verbosity flag (hides findings, and the author
    with the most warnings most needs the hidden ones).
  - **One code, one remediation.** That is the rule that decides whether two sentences share a member.
    The weight-sign pair reaches the finding through `state` and through `direction` — two axes under
    P5, one edit — so one code; the five orphan fact tables likewise. A VCF pointer collision and an
    unselected element are cleared differently, so they do not.
  - **`carried` = no edit to the SPEC DIRECTORY clears it**, which deliberately makes every "re-run the
    enricher" finding *actionable*: a derived sidecar is part of the spec. Nine members, and the one to
    argue about is `verification_findings_recorded` — a disagreement with an archive that is the stale
    side often enough that nothing is owed. `_carried_vrs_warnings` is the shape this generalises; its
    docstring already said of those lines that "none of them is fixable by an authored edit at all".
  - **A registry of emission sites is the most floor-prone guard shape there is.** `test_warning_codes.py`
    asserts an **equality** in both directions — a declared code nobody emits is a key a consumer waits
    for forever, an emitted code nobody declared fails at a source walk rather than at whichever compile
    first reaches that branch — and the walked set is derived twice over: participating modules are the
    ones importing `CodedWarning`, and a return-literal builder is in scope when a two-pass closure
    shows its result reaching a channel-named local. That closure is what exempts `_check_license_gate`
    and `_check_build_coordinates` *by shape* instead of by a hand-kept list; both only ever reach
    `all_errors`, and a refusal is a different channel. Proved by removing one wrapper and watching
    both guards name the exact site.

- `@finding-loses-its-code-at-a-boundary` — **A `str` subclass keeps 80-odd call sites working and
  loses its tag at exactly two places (RM131).** `findings.CodedWarning` is a `str`, deliberately: the
  transport stays `list[str]`, so every `.extend`, every `if w not in all_warnings` de-duplication —
  the mechanism that lets one check run in both `validate_spec` and `compile_module` and publish one
  line — every `"; ".join` and every consumer already grepping a phrase went untouched. The two leaks
  are the whole cost of that choice, and both are load-bearing:
  - **A pydantic field coerces a `str` subclass to plain `str`.** Right for the published surface
    (`manifest.json` holds JSON strings, and a stored manifest must never be re-classified on read —
    which is why the derivation sits on the *write* side and not in a `Compilation` validator) and
    fatal for a caller that keeps building: `compile_module` seeds `all_warnings` from the pre-flight.
    So `validate_spec` is a thin wrapper over an internal `_validate_spec` that returns
    `(result, findings)`, and `compile_module`/`close_module` take the second. A test pins the trap
    from the other side — reading `result.warnings` back and watching `classify` refuse it — so the
    next reader meets it in a test rather than in a traceback.
  - **Any reformat returns plain prose.** Three sites prefix a table name onto a message another tier
    built (`_check_measure_shape`, `_check_binning_deprecations`, `validate_bins`'s wrapper), and an
    f-string there silently drops the code. `findings.restate` is the one route that carries it, and it
    **refuses** a plain string rather than inventing a code — the same reason `classify` refuses one:
    a catch-all bucket reproduces the silently-partial summary the item exists to remove.

  The corpus half of the guard exists because of these two: a static walk proves every *site* names a
  code, and only a run over every reference example proves every *message that arrives* still carries
  one.

- `@suppression-counts-the-overlay-not-the-effect` — **A record of a correction must be counted over
  the correction, never over what it removed (RM124 × RM131).** `suppress` was the one overlay
  operation whose effect left no trace in the build product: the row is simply absent, and a consumer
  holding the compiled bytes has no `overrides.csv` to read. The obvious record — *N rows removed* —
  breaks the rule one paragraph of `apply_overrides` already states: after `reverse_module` the derived
  table is post-overlay, so on the second lap the suppress matches nothing, and the line would say a
  number on lap 1 and vanish on lap 2 — a module disagreeing with its own round trip on
  `manifest.compilation.warnings`, a published field. Counting the *overlay's* rows says the same thing
  on both laps. Aggregated by **reason** rather than per row, which is what `reason` being a required
  column buys, and classified **actionable** rather than carried: the author owns the overlay and
  deleting the row clears it. The existing no-op test was widened from "the second lap reports nothing"
  to "the second lap reports what the first did" — emptiness was standing in for stability, and only
  the latter is the property the published field needs.

- `@uncited-literature-dropped` — **The compiler DISCARDS a literature row no study and no bin cites; `literature.csv` keeps it
  (RM79).** Two honest counters disagreed —`manifest.literature.missing_count` over the whole table,
  the `citation_existence` record over current citations — and merge-not-clobber makes that gap normal.
  The filed question (*which subject should the block describe?*) was the wrong one: both already
  publish their denominator. What nobody had decided was why a row nothing joins to is in the artifact,
  so the fix is upstream of the counting and the two agree by construction. `split_cited_literature` is
  the one rule the check and the materializer share. Three guards to keep: the check sees **every** row
  (reporting needs the full list) while everything after it sees the kept ones; an **empty** citation
  set discards nothing, since a module citing nothing cannot tell a stale sidecar from unauthored
  citations; and both citation sites count (RM47) — blind to bin `pmid`s the compiler would now
  *discard* a threshold's evidence rather than warn about it.


- `@one-normalizer-two-spellings` — **A check that compares two normalizations reports on the normalizer,
  not on the sources — so there is exactly one map (RM134 § A).** `_normalize_clin_sig` lived inside
  `clinvar_build` with one caller, and the assessment proposed a second hand-written map for PubMind
  citing `_CLIN_SIG_MAP` as the *precedent*. Two maps for one vocabulary, feeding a check whose whole
  output is "do these two normalized calls agree": a drift makes it report `discordant` on our own
  tables while both authorities agree. **But reusing the existing function unchanged was also wrong**, and
  the defect was invisible from either source alone: the map's keys are underscored because ClinVar
  underscore-encodes spaces in `CLNSIG`, PubMind writes `Uncertain significance` and `Conflicting`, and
  both fell through to `other` — against `uncertain_significance` and `conflicting` for ClinVar's own
  wording of the same two concepts. A ClinVar-only suite is green on that; a PubMind-only suite would
  have justified the second map. The repair is two things and no more: a whitespace→underscore step in
  the tokenizer, an **identity on every existing key** (asserted as an equality over the walked map, not
  spot-checked), and a bare `conflicting` key. **What was NOT done matters as much**: PubMind's
  `Benign/Likely benign` folds to `likely_benign`, the same answer ClinVar's `Benign/Likely_benign` gets
  from the severity order, even though `PUBMIND_ASSESSMENT.md` wrote it as `benign` — teaching one
  spelling a different answer from the other is the drift the single map exists to remove. The test that
  matters runs **both sources' raw tokens through the one function and names the member both must
  reach**; comparing them only to each other passes when both land on `other`. `clin_sig.py` imports
  `VALID_CLIN_SIG` and nothing else, so a runtime pass reads it without the builders' `[dev]` extra —
  which is the argument for a shared module rather than one builder importing another.

## PAR loci and contig ploidy

- `@y-not-haploid` — **`chrom=Y` is NOT "never diploid" — PAR1 and PAR2 are diploid in every karyotype.**
  `vrs.in_pseudoautosomal_region` is three-valued and `vrs.PAR_GRCh38` holds the intervals; they are
  assembly constants of the same class as `REFGET_GRCh38`, not an un-injected reference.

- `@par-one-place` — **A PAR locus is ONE place on two contigs, and the enricher records the X spelling (RM32, shipped).**
  `vrs.par_partner` maps a PAR locus to its twin by **index-matched offset** — PAR1 at 0, PAR2 at
  98,813,480 — so never compare "the same base on X and Y": that passes PAR1 and silently fails PAR2,
  where `rs184115031` is X:155773979 **and** Y:56960499. `enrich.select_par_representative` keeps X and
  reports the twin; `--keep-par-twin` keeps both. Five things not to redo:
  - **The place-identity direction is closed by probe, not by opinion.** ClinGen's Allele Registry mints
    **two** CA ids per PAR base (`CA254919`/`CA254920` for `rs137852556`), so `ResolutionRow.caid`
    cannot carry a place and no upstream mints one. A `place_key` column was rejected too — the relation
    is derivable, so a column would restate what the data determines (the `requires_phase` argument).
  - **Selecting X follows the SOURCES, which is why it is legal** (P2). ClinVar has 0 PAR records on Y
    (of 677 Y records), gnomAD v4 excludes the Y PAR (X PAR1 640000-641500 → 880 variants, Y → 0), and
    the Registry's Y record is a bare dbSNP xref. Only Ensembl/dbSNP reports both. The old objection
    ("it encodes the consumer's analysis set") was checked against data and failed.
  - **The verdict is PER LOCUS — `XG` and `SPRY3` straddle a boundary** (XG out of PAR1 at 2,781,479,
    SPRY3 into PAR2 at 155,701,383), so anything gene- or module-scoped is wrong for half of either.
    `reference_examples/par_boundary/` is that case, and its round trip is a fixed point on all three
    signatures — which is why an enricher flag is legal where a `--par` compiler flag is P7-illegal.
  - **Position agreement is necessary, never sufficient.** A twin is dropped only when the partner
    position carries the same `ref`/`alts`; partner coordinates say "same place", not "same variant".
  - **Two non-problems, checked:** `studies.csv` is rsID-keyed so both rows always inherited the
    citation, and `_check_contig_ploidy` only branches on `{MT, Y}` so selecting X makes it quiet rather
    than wrong. It stays, for hand-authored and `--keep-par-twin` modules.

- `@gnomad-no-y-par` — **gnomAD does not cover the Y PAR, and an absence there is not a fact.** `frequencies.csv` wrote
  `status="not_found"` for it — an absence nobody established. `gnomad.covers_locus` (the source
  convention, so enricher-only; the PAR *geometry* stays in `vrs`) gates it, such a locus is not queried
  at all, and the outcome is **`not_covered`** — a third `VALID_FREQUENCY_STATUS` member, distinct from
  `unchecked` (this codebase's word for a question never *put*). It is deliberately outside the `strict`
  gate: a locus the source cannot cover is perfectly reproducible, and refusing would make a PAR module
  uncompilable for a reason no authored edit could fix.

## Binning bounds, citations and literature

- `@bin-grounding` — **A bin boundary is the most interpretive claim the format carries and it has nowhere to cite —
  a SCHEMA limit, not a tier limit (S19/RM47, 0.5.4).** `studies.csv` names a variant (`rsid`, or
  `chrom`+`start`) and a `repeat_alleles.csv` row is keyed `(gene, repeat_unit)`, so nothing can point at
  it: `reference_examples/htt_repeat_expansion` compiles green under `--strict` asserting where
  Huntington disease becomes fully penetrant — 26/27, 35/36, 39/40 — with no citation anywhere, and its
  README said *"a module making a novel claim should carry its evidence"*, advice the schema gave the
  author no way to take. Probing narrowed it in **both** directions and both corrections matter:
  `heteroplasmy.csv` is *not* affected (its optional `rsid`/`chrom`/`start` columns, 0.5.1, give a row
  an identity a study row names exactly — `reference_examples/mt_heteroplasmy` does it), and
  `studies.csv` is **not rejected** in a variants-free module (it loads, validates and materializes
  `studies.parquet`), so a binning or PGx module can cite its literature today; the row simply grounds
  the *module* rather than the bound. What ships is `_check_binning_grounding`: warns in **both** modes
  when a binning table states thresholds and the module records no study rows, message split on whether
  the rows *could* be pointed at — derived from the model (`variant_key is None`), never from the table
  name. One comment was load-bearing and false — `validate_spec`'s exemption was justified as "the 0.4
  tables carry their own evidence (e.g. `evidence_level`)", true of two of the nine kinds; the real
  reason is that for a gene-keyed table the requirement would be **unsatisfiable** rather than merely
  unmet.

- `@rm47-bin-cites` — **RM47 SHIPPED in 0.6 — the row cites, the citation table describes.** That sentence is the whole
  design and it is what stops `StudyRow`'s column set (population, `p_value_num`, `effect_size`,
  `provenance_quote`) migrating onto a citing row one column at a time. **RM132 reached the same rule
  for `pharm_variants.csv` in 0.7** under the generalization worth stating once: *a row cites when its
  claim is finer-grained than `studies.csv`'s key.* `provenance_quote` did not follow there either,
  and the entry says so rather than leaving it implied — the consequence being that a citing row with
  no quote column contributes a denominator of **zero** to the quote-counter check rather than being
  skipped, or a literature row reachable only from such a row reads as cited by nothing. Two additive halves:
  `MeasureBinRow.pmid`, one optional column on the base reaching all four kinds; and `StudyRow`'s
  subject requirement **relaxed to nothing** (`REQUIRED_ANY_OF = ()`), so the paper behind a threshold
  is described without inventing a bare `chrom=4` for HTT — widening an either-or rule only makes
  previously-*invalid* rows valid, so no published module breaks. Six things not to redo:
  - **`StudyRow.variant_key` is `str | None` now.** `derive_variant_key(None, None, None, None)`
    returns the string `"None:None:None"`, which looks like an identity and names nothing; the property
    short-circuits instead, and the orphan half of `_cross_validate_studies` skips such a row (it
    references nothing, so it cannot reference something missing). The dedup key `(None, pmid)` still
    catches two subject-less rows citing one paper, deliberately.
  - **The same-release obligation was the reason the item was filed, and it is two call sites.**
    `_cross_check_literature` reads bin pointers alongside `studies.csv` — blind to them, every
    threshold-grounding citation reads as a stale orphan — and so does `enrich_literature`. Shipping
    the column without both would be evidence the format never checks, which is worse than the gap.
  - **The enricher reaches the citing rows through PUBLIC compiler symbols.** Importing
    `_BINNING_TABLE_KINDS` or keeping a second list of the kinds in the enricher is the RM40/RM41
    shape, and the copy goes stale on the next kind. RM47 shipped this as
    `load_binning_rows`/`binning_citations`; **RM132 generalized it in 0.7** to
    `load_citing_rows`/`table_citations` over a **derived** `_CITING_TABLE_KINDS` — every `_TABLE_KINDS`
    model declaring a `pmid` — which is what turns the discipline into a structure. The old pair stays
    and stays narrow: a caller asking for the binning kinds is asking about thresholds. A test walks
    `enricher/literature.py` with `ast` and asserts no citing CSV name appears in a string constant
    there, which is how "no second roster" is enforced rather than remembered.
  - **Grounding is counted per ROW, off the row — and a variant identity is NOT one of the ways
    (D1-3, 0.6).** `_check_binning_grounding` subtracts bins carrying a `pmid`, full stop; the gate
    ("no study rows at all") is unchanged, so a module with a `studies.csv` is not newly nagged. It
    also subtracted bins carrying a variant identity, on the reasoning that a study row can name that
    variant back — inside a branch whose own first line has established the module records **no** study
    rows, so the citation clearing the bin was one that does not exist. The visible cost: a
    `heteroplasmy.csv` module stating four thresholds and citing nothing was green and silent while the
    identical thresholds on `repeat_alleles.csv` were reported, which is S19 reopened for the one
    binning kind a real MELAS/NARP module uses. Identity survives as the reason that kind is offered a
    **second remedy** (a study row really can point at those bins), never as a reason to say nothing.
    Generalize it: when an exemption cites another record as the thing that makes a row acceptable,
    check whether the branch it sits in has already ruled that record out.
  - **The rejected repairs, so they are not re-proposed:** a packed `subject_key` on `StudyRow`
    (multicolumn keying, never a tuple — and it can drift from the columns it restates); key columns on
    `StudyRow` *instead of* a bin pointer (grounds at *table* granularity, so it still cannot say why
    36 — only the subject-relaxation half was adopted); and `bin_evidence.csv` (its join key **is the
    thresholds, and they are floats**, so re-authoring `40` as `40.0` orphans the evidence silently).
  - **`reference_examples/htt_repeat_expansion` stays uncited.** The example exists to show what the
    warning looks like, and grounding it would move its signatures for nothing.

- `@dense-bin-boundary` — **A shared bin endpoint is a BOUNDARY under continuous tiling, and the higher bin owns it** — the
  lookup rule is *the row with the greatest `measure_min ≤ x`*. So the overlap test is `lo < prev_hi`
  there and stays `lo <= prev_hi` under quantised tiling, where two grid bins sharing an endpoint
  really do both claim that value.
  **Since 0.6 the rule keys on the group's effective `measure_tiling`, not on the kind** — see
  `@measure-tiling` — so a `copy_number` table declaring itself continuous tiles like a fraction, and
  `_DENSE_KINDS`/`_CONTINUOUS_GAP_KINDS`/`_INTEGER_KINDS` survive only as the inputs that build the
  per-kind *default*. The old wording said "on a dense measure" and named the kind set, which is where
  a reader would now look for a rule that has moved.
  `measure_max` is inclusive on **every** kind: half-open for continuous kinds only was the other
  candidate and lost on authorship, which is the charter's gate — it makes one column's meaning depend
  on `measure_kind` (P5), the number in the cell is then not in the bin, and a closed top bin can no
  longer reach a bounded domain's top value (AF `1.0` is homoplasmy, and real). Both spellings produce
  identical authored bytes in the interior and need the same predicate. Also: two bins sharing a
  **lower** bound refuse on any kind — the tie-break has nothing to order — which is reachable only as
  a sharp `[0.1, 0.1]` beside a range starting there.

- `@measure-tiling` — **How the axis is divided is a different question from what is measured, and the tiling rules read the
  first (RM55, 0.6).** VCF 4.4 §7.2 made `CN` non-integral and §3 types `RUC` as a Float, so a copy
  number of 2.4 matched **no bin at all**, silently, `--strict` included — and the half nobody had
  written down is that the schema also **refused the tiling that would fix it**, since a shared
  endpoint on those kinds was an overlap error. The roadmap entry's fix ("a parallel float column
  beside the integer one") named a column that mostly does not exist: `measure_min`/`measure_max` have
  been `float | None` since 0.4, so `measure_min=2.5` always loaded and was simply never answered.
  What shipped:
  - **`measure_tiling`, `{quantised, continuous}`, optional, on the binning base.** A sixth
    `measure_kind` was refused under P5 — kind is *what*, tiling is *how divided*, and folding them is
    a product rather than a sum (`copy_number_continuous`, then `activity_score_quantised`).
  - **Absent means the kind's default, never a value** (`DEFAULT_MEASURE_TILING`, derived from the
    three kind sets): `copy_number`/`repeat_count` → quantised, `allele_fraction`/`prs_percentile` →
    continuous, `activity_score` → **neither**. That is what keeps it additive — no reference
    example's `content_signature` moved, and only the five modules carrying a binning table moved
    `artifact.digest`.
  - **The inference fires only against a `quantised` default, and the proposal said "whatever its
    kind's default says".** That is the one place the build departed from the decided design, and the
    corpus is why: `activity_score` is fractional by nature (`cyp2d6_structural` bins at
    0.25/0.5/1.25/2.25) and its `None` asserts *nothing* about the grid — it reports no interior hole
    precisely because the score is summed onto a grid whose step the schema does not know. Reading it
    as continuous produced three "coverage gap" warnings for intervals no activity score can land in.
    The rule is **the data contradicts the reading**, not *the data is fractional*: only `quantised`
    states a grid for a fraction to falsify. The proposal's own requirement that `activity_score`
    keep its third behaviour *exactly* is the half that was kept.
  - **The inference runs one way and announces itself.** Fractional-ness contradicts a stated grid;
    integer-ness contradicts nothing, since `[0,1] [2,3]` is what a continuous measure looks like when
    its author has only seen whole-number data — which is why deriving the tiling with *no* column was
    refused. An explicit `quantised` beside a fractional value **stands** and warns.
  - **It reads BOUNDS ONLY, and "the modifier is a copy number too, so surely it counts" is the
    obvious wrong repair — it was in the first cut and review caught it.** `modifier_gene` + the
    modifier dosage are *group-key* columns: they say which table you are in, not where a point sits
    on the axis being tiled. Letting the dosage vote produced a **legality flip** (one identical pair
    of SMN1 bins refused at `modifier_copy_number=2.0` and accepted at `2.5`, driven by an unrelated
    column) and **invented coverage gaps** on genuinely integral bounds — the same false-positive
    class `activity_score` is protected from, arriving through a different door. Generalize it:
    *before feeding a number to an inference about an axis, ask whether the number is on that axis.*
  - **`quantised`'s step is hardcoded to 1 and nothing can state another.** Right for
    `copy_number`/`repeat_count`, the only kinds it defaults to; a limit elsewhere — declaring it on
    `allele_fraction`'s `[0, 1]` switches interior gap reporting *off* rather than tightening it,
    since no hole can exceed 1. Loud whenever a bound is fractional (the contradiction warning),
    silent when they are integral. A `measure_step` column would close it and is a full-cost authored
    column nobody has asked for, so it waits for the demand that would fix its shape. Documented on
    the field description an author actually reads, not only here.
  - **The group key's *rendering* is normalized (`format_group_key`).** Re-keying onto the coalesced
    float would have turned every published `…for key ('SMN1', 'SMN2', 2, None)` into `2.0` on a
    module nobody edited, and those strings are copied into `manifest.compilation.warnings`
    (`@warning-text-is-api`). An integral float renders as an integer, so the coalesce is invisible to
    a reader who never writes the new column. Grouping was never affected — `2 == 2.0` and they hash
    equal — so this is a rendering rule and nothing else.
  - **Two rows of one group declaring different tilings is an error**; a blank cell beside a declared
    one is absence, not disagreement (`None` is never a value).
  - **`modifier_copy_number` beside `modifier_cn`**, the one genuine `int`. Read through
    `effective_modifier_copy_number`, which uses **`is not None`, not `or`** — SMN2 = 0 copies is a
    real dosage and a truthiness fallback reads it as unset. Both set is an **error**, not a
    precedence rule (the `vrs_id` desync shape). `_KEY_FIELDS` keys on the **effective** value, which
    is what answers the RM81 objection: a coalesced value is one spelling by the time grouping and
    dedup see it, so the key never holds the ambiguity. Both grouping sites read `_KEY_FIELDS` with
    `getattr`, which resolves the property; the third read site is message text and now filters to
    names that are real columns, because telling an author to look at
    `effective_modifier_copy_number` is a finding no edit clears.
  - **`modifier_cn` is deprecated warn-only, once per table**, naming its replacement — the 0.6
    cadence amendment's actionability condition — so 1.0 inherits a **removal**, not a retype.
  - **The 0.6 RM55 warning became conditional**: it fires per kind only where a group still reads as a
    grid, because its central claim ("green and silently unanswerable at every one of its own
    boundaries") stops being true of a continuous table. `FRACTIONAL_MEASURE_PHRASE` stays
    byte-identical — a warning's text is an API — and only the sentence around it changed. It still
    does not escalate under `strict`, but for a *different* reason than before: a genuinely quantised
    catalog count is correct, so refusing would refuse a correct module over a property of its
    source's type.

- `@citation-existence` — **Existence vs retrievability for citations.** A paywall hides the *fulltext*, never the PubMed
  record — `exists` is answered for paywalled work. The real gaps, both now covered: citations PubMed
  does not index at all (preprints/books/datasets → **Crossref**, checking the *authored* DOI, since
  the derived one exists by construction) and quote-checking for paywalled papers (→ the **abstract**,
  which Europe PMC serves for non-OA records in the same response). `quote_source` records how far the
  search reached because a hit and a miss are not symmetric — an abstract miss is not a verdict.
  Google Scholar is rejected, not deferred: no API, and automated querying violates its terms.

- `@existence-not-identity` — **Existence is not identity — a lookup that answers "does this exist" must say *what* it found (S12,
  0.5.4).** PMIDs are densely allocated, so a recalled or invented 8-digit number is usually a real record
  for a different paper, and `pmid_exists=True` could never catch a fabricated citation; the surrounding
  docs treated existence as the guard, and a consumer's skill had to retract a rule its surface could not
  enforce. `CitationHint` carries `title`/`journal`/`year`/`first_author` from the same `esummary`
  response, via public `literature.bibliographic()` (two tiers read it — the RM41 lesson), with `None` for
  a field the record lacks and a `year` taken only from a leading four digits. No title column on
  `LiteratureRow`: that table records what was *checked*, not bibliography. Generalize it: when a check
  answers a yes/no about an identifier, ask whether "yes" could be true of the wrong thing.

- `@quote-attestation` — **A quote is an ATTESTATION, which is a sharper refusal than a spent comparison (S11, 0.5.4).**
  `provenance_quote`/`provenance_regex` were missing from `hints.REDUNDANCY_BEARING` although
  `literature._study_quote_found` compares both against the fulltext — exactly the drift that map's
  docstring predicts. Both are registered now, **plus** a fifth `REFUSAL_REASONS` member,
  `attestation_bearing` (`hints.ATTESTATION_BEARING`): filling `doi` from the registry that checks it makes
  a Class-2 comparison *vacuous*, while extracting a passage from a fulltext a tool just fetched states
  something **false**. The registration is additive, not instead — a provider consulting either map must
  reach a refusal. And the consequence, now in ENRICHER.md: once a machine has retrieved the text,
  `quotes_found` shows the quote **pairs with the PMID**, not that a human read the paper.

- `@pmid-vs-pmcid` — **PubMed and PubMed Central ids are one letter apart, and the outcome turned on a space (RM50,
  0.6).** `PMID_PATTERN` is `\b(\d{1,8})\b`, so `PMC3110566` → `[]` (no word boundary between `C` and a
  digit) but **`PMC 3110566` → `['3110566']`** — a real PMID for an unrelated article, since PMIDs are
  densely allocated (the S12 class). One spelling was refused with a message that never said "PMCID";
  the other was accepted as a confident citation of the wrong paper. Four parts, all diagnosis:
  - **`spec.PMCID_PATTERN` / `extract_pmcids`** name the PMC context in any spacing (`PMC3110566`,
    `PMC 3110566`, `PMC-3110566`, `pmcid: 3110566`), `extract_pmids` declines the digits inside one,
    and `validate_pmid_cell` — shared by `StudyRow.pmid` and `MeasureBinRow.pmid` — **names the id it
    saw**. Narrow by construction: `21551363; PMC3110566` still yields the real PMID and is accepted,
    so only a cell whose sole numeric content is a PMC id refuses.
  - **`literature._pmcid_conflicts`** catches what the schema cannot see (`21551363 (PMC3110567)` has a
    real PubMed id, so nothing refuses it) — the `_doi_conflicts` shape, free from the `articleids`
    block, `strict` refusing.
  - **PMCID → PMID is a REPORTING lookup** (`hint citation --pmcid`, `PmcIdConverterClient`): the id
    comes back as an advisory with `refusal="redundancy_bearing"`, because filling `pmid` from NCBI
    would make `LiteratureRow.exists` compare NCBI with itself. `pmid` is registered in
    `hints.REDUNDANCY_BEARING` and `lookup._REFUSAL_BY_COLUMN` for exactly that. **Four converter
    outcomes, spelled four ways** — resolved / in-PMC-with-no-pmid / not-in-PMC / never-answered — since
    collapsing the last two renders a failed request as a definite negative (S20). And it then asks
    PubMed *which paper that is*: a converter handing back a number and stopping is S12 one registry
    over. Endpoint: `pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/` (the long-published
    `www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/` 301-redirects to it), `pmid` arrives as a JSON number.
  - **No authored `pmcid` column, and no re-key of `LiteratureRow`.** The citation id is *required*
    today and P8 bars demoting a required field within a major, so a citation with no PubMed id cannot
    become legal in 0.6 whatever column is added — the authoring half is 1.0. An optional authored
    `pmcid` is full cost for content the enricher fills free and still does not help that row.

- `@regex-timeout-process` — **A thread-based regex timeout is a trap.** `re` cannot be interrupted, threads cannot be killed, and
  the interpreter joins `ThreadPoolExecutor` threads at exit — so the obvious implementation returns
  `None` on schedule and then hangs the process on the way out. `literature.regex_matches` uses a
  killable child process. Don't "simplify" it back to a thread.

- `@literature-writer-derived` — **The enricher's `literature.csv` writer is derived from the model.** `_FIELDNAMES` was a hand-kept
  literal and `_write_literature_csv` a per-column dict — the `SOURCES_FIELDNAMES` shape, which lost
  `redistribution` from every `sources.csv` ever written. `LiteratureRow` has no compiler-stamped
  fields, so `list(LiteratureRow.model_fields)` is exactly right, and the renderer is generic.
  Corollary the docs now state: **merge-not-clobber means a re-run does not back-fill** the new licence
  columns onto rows written before 0.6 — delete the sidecar to re-derive.

## Licensing, sources and the compile gate

- `@sidecar-name-and-place` — **A machine-written sidecar has two legal names and two legal places — never join one onto a spec
  directory by hand (RM51 + RM49, 0.6).** `just_dna_format.layout` is the single resolver, in the schema
  tier because *four* parties must agree: compiler reads, enricher writes, publisher uploads, registry
  re-splits. The licence table is `licensing.csv` (the old `sources.csv` is deprecated, warn-only,
  removed at 1.0), and any of the five sidecars may sit under `derived/`. Four things to keep straight:
  - **Write to the file you read** (`layout.sidecar_write_path`, `licensing.sidecar_path`). Writing the
    current spelling onto a module carrying the old one — or the root onto a split module — leaves two
    copies, which is the refusal below, arrived at by following the documented workflow rather than by
    misuse. This is the load-bearing half; tolerating a location on *input* alone breaks on first use.
    **The rule was stated and then not carried through to the writers** — `reverse_module` joined
    `_FACT_TABLES`' name on by hand, and that tuple carries the *deprecated* spelling because the
    parquet keeps it, so `compile → reverse → compile` emitted `sources.csv` and the recompile
    deprecation-warned on a module whose own compile was silent. `manifest.compilation.warnings` is a
    published field (RM44), so a module and its own round trip disagreed on it. Reverse is not an
    exception to the rule, it is the fresh-directory case *of* it: there is nothing to follow, so
    `sidecar_write_path` yields the preferred spelling and a round trip migrates the name — measured
    byte-identical on `artifact.digest`, `content_signature`, `resolution_signature` and
    `manifest.sources` across all eleven reference examples, because the licence table is fact-hashed.
    When a rule like this lands, grep every writer: `draft.append_rows` is the same join.
  - **Both present is an ERROR naming both paths.** No merge, no newest-wins: these tables are
    fact-hashed *and* human-overridable, so two copies are two legitimate claims and preferring one
    discards a curator's override.
  - **Only the machine-written tables move.** `variants.csv` and the table kinds have one name in one
    place; two legal homes for an authored table means a module can carry two with the ignored copy
    invisible. And **`_check_misspelled_tables` had to learn `derived/`** — tolerating a location
    without extending the guard puts a typo'd `derived/varaints.csv` exactly where the check written to
    catch it cannot see. That is also why "search any subdirectory" was refused. **It takes TWO tests
    there, and the first attempt had neither**: fuzzy-matching against `derived/`'s own smaller name set
    returns `[]` at the 0.8 cutoff for `variants.csv`, `studies.csv`, `diplotypes.csv` *and*
    `varaints.csv`, so a module with its `variants.csv` under `derived/` compiled **green with zero
    warnings and zero variant rows** while another table kept it legal — the S16 silent-success shape,
    re-opened as the price of the convenience. An authored name there is an **exact match against the
    wrong name set**, which is sharper than any fuzzy test and is reported as *misplaced*; everything
    else is fuzzy-matched against the **full** known set. The *acceptance* set stays the smaller one,
    which is what keeps unknown files tolerated and keeps the mirror case (a sidecar at the spec root,
    legal) silent. The old test passed only because its fixture was variants-only, so the module was
    refused for carrying no table at all and the guard's silence was invisible — when a guard's test
    kills the module by another route, it is testing the other route.
  - **The outputs did not move**: still `sources.parquet`, still `manifest.sources`, both major-only
    renames. The 0.x tail reads `licensing.csv` → `sources.parquet` → `manifest.sources`, knowingly.
    Neither the name nor the location enters any identity — measured on all eleven reference examples.
  RM51 estimated five enricher write sites; there were **nine**, which is why `record_source_terms` and
  `merge_sources_file` take the **spec directory** now. A count of call sites is exactly the thing that
  goes stale; routing them through one function is the durable form.

- `@licensing-as-data` — **Licensing lives as DATA in the licence table, never as a table in the compiler.** A source→licence map
  in `just_dna_compiler` would give it a source convention (Principle 2, tightened in 0.5) and an
  un-injected reference — and it goes stale (both halves of one did inside 0.5). The enricher reads the
  terms from the bytes it downloaded and pins them with `license_sha256`. Three rules the tests pin,
  don't "simplify" any of them: **only the `annotation` layer taints** (a coordinate is a fact Ensembl
  reports identically, so marking it viral is a false positive); **most-restrictive-wins module-wide**
  (a permissive source can't launder a restricted one); and **`None` ≠ `False`** on
  `share_alike`/`commercial_use` (unknown terms are undetermined, never permitted).

- `@write-the-sourcerow` — **A pass that consults a source must WRITE its `SourceRow` — use `licensing.record_source_terms`.**
  Building the row is half the job; the compile gate and `manifest.sources` read `sources.csv` and
  nothing else, so a row that is only returned is a source the module cannot account for. `clingen.py`
  returned one and never wrote it — permissive terms (CC0) made it look harmless, but CC0 still asks
  for attribution and the table exists to carry it — and then `enrich`/`frequencies`/`gene_metrics`
  turned out to write nothing at all, which is why `VALID_SOURCE_LAYERS` had reserved members no file
  ever carried. `record_source_terms(names, layer, path, error=…)` maps source names → terms → rows and
  does the load-merge-write (over `merge_sources_file`) in one place; don't grow a private copy.
  Corollary: **a fact-layer row cannot taint a module**, so what it carries is *attribution*, which is
  as much the table's purpose as the prohibitions are.

  **The converse, and it is not symmetric: a pass that CONTRIBUTES NOTHING must write no row (S77,
  RM142).** `sources.csv` travels to the registry and means *this module uses this source*, so a row
  from a pass that looked and found nothing is a false statement in a published artifact — and it fires
  `declared_license_disagrees` against a module whose licence never met that source's, sending an author
  to adjudicate a conflict that does not exist. Two agents were measured doing that. **The compiler
  cannot catch it**: `_source_checks`'s orphan warning exempts the `annotation` layer by design (RM46),
  because that is where an author is told to declare a hand-read source. So the guard belongs in the
  pass, and the shape is already there in four of the five — `{row.source for row in out}` records
  nothing when `out` is empty. `clingen.py` built a fixed row and wrote it unconditionally. Key it on
  **what this run covered**: the table's contents include what an earlier run already recorded, and
  `not missing` inverts it — that would drop a real obligation from any module carrying one uncurated
  gene beside a curated one.

- `@fieldnames-from-model` — **A column list written by hand will lose a column — derive it from the model.** `SOURCES_FIELDNAMES`
  was a literal and omitted `redistribution`, so every `sources.csv` ever written recorded *unknown* for
  an axis the terms constants state as `True`, and `merge_sources_file` dropped it again on each merge —
  RM27 is a gate designed to read a column that had reached no file. `SourceRow` has no
  compiler-stamped fields, so `list(SourceRow.model_fields)` is exactly right there. Where a model
  *does* have stamped fields, that is what `base.authored_field_names` and the `COMPILER_MANAGED` marker
  are for — the rule is the same one, never hand-keep a list of a model's columns.

- `@source-vs-authority` — **`source` names the licensed source in every fact table; only `resolution.csv` also records the
  link.** `resolution.csv`'s `source` is *which link answered* (`ensembl-rest`, `cache`, `clinvar`) and
  `authority` is what `sources.csv` joins on (`ensembl`, `clinvar`, `gnomad`), empty for
  `authored`/`reversed`/`manual` because the module's own bytes are not a licensed source. The
  link→authority map (`licensing.RESOLUTION_AUTHORITY_BY_LINK`) lives in the **enricher**; the same map
  in the compiler is the un-injected-reference mistake *Licensing lives as DATA* names above. `gene_metrics.csv` had the same
  overloading (`gnomad-constraint`/`gnomad-api` are routes, not sources) and was fixed the other way —
  it records `gnomad`, and the route stays in `dataset`, which is inside the fact set where `source` is
  not. This was RM33.

- `@orphan-check-exempt` — **A layer with no `source` column to join is exempt from the orphan check, structurally — and that is
  now TWO layers, not one (S23, 0.5.4).** "No table used it" is decided by reading fact tables' `source`
  columns, and `annotation` *is* `variants.csv`/`diplotypes.csv`, which carry none — so the check
  reported the one row the licence gate keys on as probably stale, on every drafted module. `literature`
  joins the exemption by the identical argument whenever the module carries `studies.csv` rows
  (`_source_checks(..., literature_evidenced=…)`, `uncorroborable = {"annotation", "literature"}`):
  `studies.csv` is the hand-curated literature table and has no `source` column *by the same design*, so
  a `pubmed`/`europepmc` row can only be corroborated by the enricher-written `literature.csv`, and a
  module with none has nothing to join. Note which way the old behaviour pushed an author:
  `MISPLACED_COLUMN_REASONS['source']` tells them to declare a hand-read source as a `sources.csv` row,
  and doing so earned a warning that the row was unused, while **deleting** it — shipping with the
  provenance unrecorded — was silent. Compliance warned, omission quiet. Narrow by construction:
  `frequency` still warns, because `frequencies.csv` *is* machine-written with a `source` column, so a
  frequency declaration in a module with no frequencies really is stale. Don't "restore" either half.

- `@gate-is-data-driven` — **The compile gate is data-driven; a `--non-commercial` CLI flag would be charter-illegal.** It
  refuses when an annotation-layer source forbids sale and the module records no declaration, reading
  only injected `sources.csv`. A *flag* cannot be recorded in the artifact — `reverse_module` rebuilds
  `module_spec.yaml` from parquet alone — so `compile → reverse → compile` would refuse on the third
  step (P7). The gate sits immediately before `output_dir.mkdir()`, which is why `sources.csv` is
  parsed there rather than with the other fact tables (they load after mkdir). It refuses in **both**
  modes; `strict` means "reproducible artifact", an unrelated axis (P5).

- `@declared-use-third-axis` — **`declared_use` (`--use`) is a THIRD axis, not a mode.** `mode` says how hard to fail on a finding;
  `declared_use` says who is using the data. Three states, so not a bool pair — defaulting either way
  would make the tool assert a purpose for the user. A forbidding source is *skipped* on `unstated`
  and *refused* on `commercial`, at acquisition (nothing is fetched), in both modes.

- `@redistribution-ungated` — **`redistribution` is a third licensing axis, recorded but NOT gated.** CC BY-NC forbids sale and
  allows sharing; academic-use-only (OMIM, dbNSFP) forbids both. The compile gate deliberately keys
  only on `commercial_use` — a distribution right is not a *use*, so `declared_use` is the wrong axis
  to resolve it against (RM27). Don't "finish" the gate without doing that design.

- `@per-article-terms` — **A literature source's terms are PER ARTICLE, and that is why there is no `pubmed` row (RM46,
  0.6).** `enrich_literature` writes `source="pubmed"` into every row, `TERMS_BY_SOURCE` has no entry
  for it, and `_source_checks` therefore named `pubmed` as undeclared on every literature-enriched
  module — the tier introducing a source, declining to record it, and landing the finding on the
  author. The fix is **four columns on the derived literature row** (`license`, `share_alike`,
  `commercial_use`, `redistribution`), half cost, filled from the Europe PMC response the pass already
  makes. Five things to keep straight:
  - **A `PUBMED_TERMS` constant is wrong in the dangerous direction.** PubMed's *metadata* is one
    thing; the *article* belongs to its publisher, and Europe PMC's open subset spans CC-BY, CC-BY-NC
    and bronze. One "pubmed, fine" row would clear a module carrying a `provenance_quote` lifted from a
    CC-BY-NC article — publisher text in the module's own **annotation** layer, exactly where
    `taints_commercial_use` bites.
  - **`license` is stored VERBATIM** (`cc by`, `cc by-nc`, `cc by-nc-nd` — probed over 100 records) and
    `licensing.article_terms` maps it to rights at **read** time, so a mapping fix reaches rows already
    written (the `cpic_build` rule). Unknown → all three `None`, never `False`.
  - **The licence is INDEPENDENT of `is_open_access`.** PMID 28546431 is `isOpenAccess: N` with
    `license: cc by`: the flag describes Europe PMC's OA subset, the licence describes the article.
    Do not derive one from the other.
  - **All four are OUTSIDE `LITERATURE_FACT_FIELDS`**, beside `is_open_access` and for its reason: a
    publisher re-licensing an article changes the world, not the module, and in the fact set it would
    move `literature_signature` with no authored edit anywhere.
  - **Quoting a non-commercial article WARNS in both modes and gates nothing** — the third such
    exception after the ClinVar `clin_sig` cross-check and `_check_declared_license_agrees`, same
    reason: arbitrating copyright is the same class of overreach as arbitrating a clinical dispute.
    Keyed on the *quote*, not the citation (naming an id costs nothing under any licence), and
    aggregated by licence. The compiler reads the recorded fact, so it still owns no source convention
    — the rejected alternative was a compiler-side list of enricher-introduced sources, which is a
    source convention (P2) and the exact mistake RM33 removed. Consequence: nothing can corroborate a
    `literature`-layer `sources.csv` row any more, so that layer is **unconditionally** exempt from the
    orphan check (S23's conditional could no longer distinguish anything). `frequency` still warns.

- `@pgx-research-only` — **PharmGKB is now ClinPGx, and every PGx upstream is research-only.** `api.pharmgkb.org` was
  **retired 2026-07-20** and no longer resolves; the successor is `api.clinpgx.org` with paths and
  formats unchanged. ClinPGx is the umbrella that merged PharmGKB + CPIC + PharmCAT, so **CPIC is not
  an unrestricted alternative** — `cpicpgx.org/license/` 302-redirects to the ClinPGx data usage
  policy. All three sources (ClinPGx, CPIC, PharmVar) are **CC BY-SA 4.0 plus a contractual no-sale
  clause**, so none is sellable: don't read a bare "CC BY-SA" line as permission to sell, read the
  surrounding terms (`docs/vendor/pharmvar_lic.txt` §3 is the PharmVar one). Ensembl/dbSNP already cover
  rsID→coordinate, so never wire ClinPGx/CPIC as a resolution link — that keeps the coordinate layer
  unrestricted. PharmVar needs an **`Api-Key:` header** (not `X-API-KEY`) at **2 rps**, and its ToS §2
  makes the key personal — never bake one into a module, fixture, or snapshot. API schema:
  `docs/vendor/pharmvar_api_docs.json`.

- `@gated-source-caches` — **Every gated source now has a cache, and PharmVar's is deliberately unpublishable (RM38, shipped in
  enricher 0.5.1).** The three PGx sources were the only `commercial_use=False` entries *and* the only
  ones with no cache — the same set, because every ungated link was already snapshot-first. A hosted
  surface therefore had two options, fetch live per request on the operator's own credentials or skip
  the check. Six things to keep straight now that it is built:
  - **The route is snapshot → live → skip-with-a-reason, and `--offline` means the first only.**
    `PgxResult.routes` records which answered and a snapshot stamps its release into `SourceRow.dataset`
    (the gnomAD-constraint precedent: a consumer must be able to tell a pinned file from a live API).
    `skipped_offline` is a third state, never a silent pass.
  - **`clinpgx` provisions automatically; `pgx`/`draft` fall back to live.** Not an inconsistency —
    ClinPGx has no live route at all (the API was retired), so there is nothing to degrade to, while
    downloading a whole database to answer one gene is the wrong default for an author on a laptop.
  - **`offline` outranks an injected client, decided on the TYPE not on `configured`.** A live client
    under `--offline` would egress from a run documented as making none; a snapshot client is exempt
    because reading a local parquet is not egress. A live client with a perfectly good key is exactly
    the one that must not be used there.
  - **No `ensure_pharmvar_snapshot`, no `pharmvar publish`, ever.** Its bulk data comes under a key its
    terms §2 make personal and non-transferable, and `redistribution=True` describes the CC BY-SA grant
    over the *content*, not a clause about the *account* — an unestablished permission is not a
    permission. Also still don't add a `SourceRow` column for research-use-only — not because of the
    version (an optional column is minor-legal since the 2026-08-11 amendment) but because it belongs to
    RM27's design round: a *distribution* right is not a *use*, and the axis has to be designed once.
  - **The builders store values verbatim and map at READ time.** `cpic_build` writes CPIC's own prose
    (`"No function"`, `"Strong"`) and the snapshot client calls the same `map_function_status` /
    `map_classification` the live client does — so a mapping fix reaches an already-built snapshot, and
    the two routes return the same object by construction rather than by inspection. Same rule for
    `unusable_allele_reason`: it is a *judgement this workspace makes* about CPIC's value, so freezing
    it into the parquet would pin one release's opinion into every snapshot built under it.
  - **A flattened JSON map must carry what the flattening lost.** `recommendation.phenotypes` is a
    `{gene: phenotype}` dict and the live client keeps only single-gene rows; the snapshot is one row
    per gene named, so `gene_count` travels with it and the reader applies the identical rule. Without
    it, flattening silently promotes multi-gene recommendations.

## PGx sources: ClinPGx, CPIC, PharmVar

- `@clinpgx-per-genotype` — **PharmGKB clinical annotations are per-genotype — `(variant_key, drug)` is not a key.** 4,618 of
  5,113 carry exactly three genotype rows, sometimes opposed (rs4149056/simvastatin: CC/CT
  "decreased", TT "increased"), so `PharmVariantRow.genotype` is in the dedup key. Its grammar lives
  on `AuthoredModel` — shared with `VariantRow`, so don't re-declare it. Route haplotype-keyed
  annotations (`*1`) to `DiplotypeRow`; skip symbolic alleles (`del/del`, 177 rows) as **RM5** rather
  than widening the nucleotide grammar. PharmGKB writes `CC`; canonical form is `C/C`, since `CC`
  would otherwise parse as a single two-base allele — disambiguate using the *resolved* ref/alt.

- `@clinpgx-full-key` — **`(variant_key, drug, genotype)` is STILL not a PharmGKB key** — one variant+drug carries several
  distinct annotations (rs4149056+simvastatin is Metabolism/PK 1A, Efficacy 3 AND Toxicity 1A). 1,199
  of 17,380 triples collide; 839 separate by `phenotype_category`, 283 only by `annotation_id`. The key
  is `(variant_key, drug, genotype, phenotype_category, annotation_id)`. **Any code that indexes
  ClinPGx by the bare triple has this bug** — the first cross-check did, and reported correctly-authored
  levels as stale. Look it up by `annotation_id`, then category, and report ambiguity rather than
  comparing against an arbitrary candidate.

- `@probe-names-the-table` — **A negative finding about a source is only as wide as the table you looked at — say which.** The
  comment "CPIC publishes no chromosome" was true of `sequence_location` and false of CPIC: `gene.chr`
  has it, and the drafting provider had been skipping 36 real defining variants (18 CYP2C9, 14 TPMT, 4
  NUDT15) for a year on the strength of a probe that named no table. Joining `gene.chr` on the symbol the
  location row already carries is a **lookup in the source's own tables**, not the inference the original
  comment rightly refused — that distinction is the whole difference between the two.

- `@assembly-first-wins` — **A source that publishes both assemblies will list the wrong one first.** PharmVar emits each defining
  variant once per reference sequence — transcript, GRCh37, GRCh38 — with **GRCh37 first**, and
  `_merge_variants` was first-wins, so 451 of 739 rsID-keyed variants carried a GRCh37 coordinate. The
  accession *version* cannot separate them (chr10 is `.10`/`.11`, and so is chr22); `referenceCollections`
  can. Two durable points. **Filter on the field that names the assembly, never on the accession.** And
  it was latent for a release because nothing consumed `PharmVarAllele.variants` — **a snapshot is what
  turns a latent wrong number into a written one**, so re-check every parsed-but-unused field the first
  time something persists it. `pharmvar.PHARMVAR_GENOME_BUILD` is the named constant (fourth build
  confusion here; `gnomad.FREQUENCY_GENOME_BUILD` is the precedent).

- `@credential-where-read` — **A credential must be loaded where it is read.** `PharmVarClient` read `os.environ` and `.env` only
  ever reached it as a side effect of some *other* call resolving a cache path — which worked for
  `enrich_pgx` by accident and not at all for `pharmvar build`, which resolves nothing and reported "no
  PharmVar API key" on a machine that had one. `load_env()` now runs in `__init__`, `override=False`, so
  a real environment variable and a test's neutralizing `""` both still win.

- `@absent-is-not-different` — **A new optional column that splits a dedup key suppresses only when
  BOTH rows state it and the two values differ — and it is the CHECK that learns the column, never the
  key** (RM140, S75). `studies.csv` is keyed `(variant_key, pmid)`, and `duplicate_study_citation`
  reads a repeat of that pair as *the same claim written twice*. Once `StudyRow.statistical_test`
  existed, two rows naming two analyses of one association stopped being that, so the check contradicted
  the column an author was using as intended.

  **The tempting condition is `a != b`, and it is wrong in the house's own terms.** `None != "Fisher"`
  is `True`, so the naive form suppresses the warning on every absent cell — which retires the check
  outright for every module written before the column existed, silently, and looks like a passing test
  suite. An absent value is **unknown**, and unknown against a stated value cannot establish that two
  rows describe separate work. Kleene: only *stated-and-stated-and-different* is a distinction. Four
  arrangements need pinning and three of them still warn — neither stated, both the same, and one
  stated in either order.

  **Do not widen `_KEY_FIELDS` to get the same effect.** It looks like the tidier fix and it is a much
  larger one: the tuple drives `hints.key_fields` and the `key.columns` an authoring surface publishes,
  `@dedup-key-decides-rows` makes it the thing that decides which columns may become several rows in
  every drafting provider, and re-keying a shipped authored table changes what an identity key means —
  major-only under P3. The check restated `(variant_key, pmid)` rather than reading the tuple, which is
  what let the split be contained in one function. Check that property before choosing this route; if
  the check reads `_KEY_FIELDS`, the two options are not the ones they appear to be.

  **The message is the other half.** Every case that still warns must keep the byte-identical string and
  code (`@warning-text-is-api`) — the change is behaviour, not text — and a test asserting exactly that
  over a spec with no such column at all is what proves no published module moved.

- `@dedup-key-decides-rows` — **Which columns may become several rows is decided by the DEDUP KEY, not by the source's dialect
  (R2-1).** ClinPGx `;`-joins both `drugs` and `gene`. `drug` is *in* `PharmVariantRow`'s dedup key, so
  one record legitimately becomes one row per drug; `gene` is **outside** it, so the same move makes
  copies that collide on `(variant_key, drug, genotype, phenotype_category, annotation_id)` and the
  compiler refuses the module. With one-row-per-member illegal and no rule to pick by (the pharmacogene
  is first in `CYP3A5;ZSCAN25` and second in `PRSS53;VKORC1`), the answer is the CPIC `gene.chr` move —
  write the member the **request** selects, and otherwise withhold and name what the cell held. Also
  check filter ordering while you are there: `skipped_unidentified` was counted *before* the `--gene`
  filter, so a "records the source could not identify" count was inflated by the whole database.

- `@draft-allele-filter` — **A large star-allele gene is drafted with `draft --allele`, and the filter covers all three tables.**
  Unfiltered CYP2D6 is 16,290 diplotype rows (73% `Indeterminate`); the author's real bound is the allele
  set their caller emits, and *n* alleles is *n(n+1)/2* pairs. Filtering `diplotypes.csv` alone would
  leave a module naming alleles `haplotypes.csv` never defines — the thing
  `_cross_validate_haplotype_definitions` warns about — so `_selected_alleles` gates the defining
  variants and the function rows too. `*1` is always kept (defined by carrying no variants; without it
  `*1/*2` is undraftable), an unknown name refuses with CPIC's list, and the flag takes a single `--gene`
  because a star name is gene-scoped. This was RM34. When counting what a filter dropped, count over the
  rows the filter actually judged: tallying the copy-number rows it deliberately passes through read
  "567 of 16836" for a six-allele set.

- `@incidental-call-isolated` — **An incidental call must not be able to discard finished work (R2-4).** `cpic.knows_drug` is asked
  only to sharpen the sentence explaining an empty result, and by then every substantive query has
  returned — so its failure is caught and rendered as the tri-state's *could not ask*, with its **own**
  wording: "the snapshot cannot answer" is fixed by going live and "the request failed" by re-running,
  so folding them puts the snapshot's sentence in front of an author who has no snapshot. Its
  `bool | None` had been *designed and never delivered from the live client*, which is exactly why the
  raise escaped: the handling existed and nothing could reach it.

- `@client-exception-contract` — **A client that leaks its transport library's exception type has no contract (R2-13).**
  `CpicClient._get` called `raise_for_status()` and wrapped only *shape* failures, so an exhausted
  retry ladder left a raw `httpx.HTTPStatusError` that walked through both of `enrich_pgx`'s per-leg
  handlers — written under *"One source failing must not sink the pass"* — and took the other source's
  answer down. The retrying half is `_request` and the translating wrapper is `_get`, in that order:
  wrapping **inside** the retry defeats it, since `retry_if_exception_type` tests the httpx type and a
  `CpicError` raised there is a first-and-final attempt. A test asserts the ladder survived the split,
  because a decorator on the wrong half turns three attempts into one and nothing fails. **Fix both
  legs**: PharmVar had the identical hole, and repairing one makes that comment true in one direction
  only — the guarantee would then hold or not depending on which source went down.

  **The contract has two layers, and RM97 only repaired the lower one (RM101, from S37).** A client
  raising its own type is half the promise; the other half is that a **pass** raises *its* type. Five
  call sites held a client with `try: ... finally: close()` and no `except`, so `GnomadError` walked
  out of `enrich_frequencies`, `EutilsError` out of `enrich_literature` and `check_rsids`, and a
  caller's `except FrequencyEnrichmentError` — the type the pass documents — was silent for exactly
  the failure it was written for. Two things make this worth more than five `except` clauses:

  **The leak is often load-bearing, so repairing the client alone breaks something silently.** Two
  handlers in this tree caught the *leaked* type on purpose: `cli.py`'s `check-identifiers` caught
  `httpx.HTTPError` to attest `unreachable` — on the run whose own test is named *"the run where the
  record matters most is the one with no report to print"* — and `enrich()` caught `EutilsError` under
  *"a dbSNP outage does not sink a finished enrichment"*. Both only ever fired because of the leak.
  Fix the client, and the attestation and the degradation switch off with nothing failing. Grep for
  handlers naming the *client's* type before retyping anything.

  **Translate to a SUBCLASS, never a flat type.** `FrequencyUnavailable(FrequencyEnrichmentError)`,
  after `AcmgListUnavailable`. Flat translation is the obvious repair and it is wrong twice: it
  flattens "your input is wrong" and "the source is down" into one type when every pass here used one
  for both, and it breaks the consumer who already compensated by catching the client's type — which
  the reporter of S37 had. `except <Pass>Error` keeps working (P3), and `except <Pass>Unavailable`
  becomes possible. Chain with `from exc` so `__cause__` still carries the client's error.

  **The same split fixes a conflation that has nothing to do with escaping.** `ClinGenError` covered
  "could not fetch the curation list" *and* "your local `gene_metrics.csv` will not parse" — opposite
  histories, separable only by reading `exc.__cause__`. Matching the message is worse: neither string
  is pinned as an API, so a reword flips a consumer's verdict from "unchecked" to "your table is
  broken". `gene_validity.py` had the identical pair and nobody had reported it.

  **Ask this of every pass, not the ones in the report.** S37 named three; walking the passes found
  three more, and walking the *clients* found `OntologyClient` still leaking raw `httpx` a release
  after RM97 said that was over. RM97's own coverage guard is why it survived: it walked a hand-written
  tuple of eight module names and `identifiers` was not one of them. `@registry-completeness` — the
  guard now discovers by `pkgutil` walk and by signature. `@probe-names-the-table`.

  **The subclass makes a consumer's handler ORDER load-bearing, and that is the cost of the repair
  (S38).** It is the one thing the subclass buys that a flat type would not have: once
  `FrequencyUnavailable` is a `FrequencyEnrichmentError`, two separate `except` arms with the parent
  first leave the narrow arm dead, because Python takes the first matching clause. just-dna-registry
  upgraded to 0.6.2 with exactly that shape in three of four handlers, having read our own migration
  row — which said catching both "keeps working, unchanged" and was written as though *both* could only
  mean one tuple. Their outage field came back empty and the endpoint reported a clean check while
  gnomAD was down: the failure RM101 exists to end, reintroduced by the fix for it, in a consumer that
  had followed the advice.

  **So a migration note has to enumerate the SHAPES, not the type sets.** "Catch both" describes two
  handlers that differ only in punctuation and behave oppositely, and the silent one is not the one a
  reader pattern-matches to. The table in INTEGRATION_0_6 § 8 gained a fourth row and the reference in
  ENRICHER gained the same warning, because a migration note stops being read while the reference does
  not.

  **A guard for it is structural and cheap**, which is the general lesson rather than the specific one:
  a defect invisible at every level except the *shape* of the code wants an `ast` walk, not a review
  habit. `enricher/tests/test_shadowed_handlers.py` parses all three packages and fails on any arm an
  earlier arm in the same `try` already catches; our own tree was clean, and the test that proves the
  walk can fail runs it against the reporter's snippet (`@tautology-zero`). Two false positives were
  designed out deliberately: a parent and child in **one tuple** is redundant, not dead, and dotted
  clause types are not resolved rather than guessed at.

## Drafting and the authoring surfaces

- `@draft-appends` — **Drafting appends, it never mutates — that word is the whole line.** `just_dna_compiler.draft`
  appends rows into an authored CSV at **row** granularity (a file-level "refuse if it exists" rule
  self-defuses after the first gene and makes a multi-gene module unbuildable). A row whose key exists
  is reported (`already_present` / `differs`), never rewritten; drift on existing rows is
  `pgx.enrich_pgx`'s job. Dedup keys on the compiler's own `_TABLE_DUPE_KEYS` so an append cannot
  create a row the compiler then rejects, and rows go **at the end** because authored row order is
  load-bearing for the digest. This is *not* the parked enricher-co-authoring item: appending leaves
  `content_signature` a function of the authored bytes; editing a cell a human wrote would not.

- `@partial-row-omission` — **A partial row is validated by OMISSION, and matches on `match_on`, not the natural key.**
  `draft.PartialRow` exists because ClinVar publishes **alleles, not genotypes**, and
  `VariantRow.genotype` is required: zygosity is inheritance-mode interpretation the source does not
  state, so `clinvar_draft` writes what is published and leaves `genotype` as `TEMPLATE_PLACEHOLDER`.
  Two traps. (1) Validating the non-stubbed cells by substituting dummy values needs a per-column
  value oracle — a hand-kept list again; instead the row is built **without** the stubbed columns and
  errors located on them are discarded. (2) The natural key runs *through* the stub, so it cannot
  decide sameness; `match_on` (the identity columns) does, which is what makes a re-draft after the
  human fills the genotype report `already_present` instead of appending the stub a second time.

- `@placeholder-protects-decision` — **A placeholder protects a DECISION; where the contig leaves none, filling it is not pre-empting
  anything (S6, 0.5.2).** `draft_gene_panel` stubs `genotype` because zygosity follows from the
  inheritance mode and the source does not state it — true on a diploid contig, vacuous on MT (haploid)
  and chrY outside PAR1/PAR2 (hemizygous), where exactly one genotype is expressible.
  `sole_expressible_genotype` writes the ALT there and keeps the stub everywhere else; Y is decided
  **per locus** through three-valued `vrs.in_pseudoautosomal_region`, with `True` *and* `None` keeping
  the placeholder. Three points. **Row counts do not change** — the provider always wrote one row per
  record; the doubling a consumer saw was their own placeholder-expansion step, which now has nothing to
  expand. **The notice is aggregated and names the reading** (homoplasmic/hemizygous; a heteroplasmic
  level is `heteroplasmy.csv`), because at panel scale it is hundreds of loci and the *reading* is what
  the author must know. And **the chrY half of the report did not reproduce** — a real SRY row warns
  through the compiler exactly as MT does — so nothing in the ploidy check moved; check a claim about a
  guard before adjusting the guard.

- `@identity-whole-or-none` — **A drafting provider fills identity WHOLE or not at all.** rsID, else the complete
  `chrom`/`start`/`ref`/`alts` — never a subset. A lone `alts` on a position-only row makes
  `derive_variant_key` mint a VRS `ga4gh:VA.…` id instead of `chrom:start:ref`, so a partial
  coordinate silently changes *which variant the row is*.

- `@gene-map-is-another-sources-attribution` — **A source with no gene column is drafted by gene through
  another source's PER-RECORD attribution, never through a span (RM134 § C).** PubMind publishes
  `(chrom, start, ref, alt)` and nothing else locational, so `draft-panel --gene BRCA1 --source pubmind`
  has to turn a symbol into positions — and this repo deliberately holds no gene coordinates at all,
  which is why `_gene_locus_conflicts` checks at **chromosome** granularity (`@gene-locus-relationship`).
  Two candidate maps, and only one of them states a fact somebody published. The min/max span over
  ClinVar's positions for the gene is the tempting one: it is one query, it catches everything in the
  neighbourhood, and it is **wrong wherever two genes overlap or nest**, because every position inside
  the interval then gets a `gene` cell naming whichever gene defined the interval — a false claim, in an
  authored file, produced by a pass the author trusted. The position-exact map carries ClinVar's own
  per-record claim about that exact base and nothing more. Two consequences to keep: the map takes **no**
  clinical or review filter, because it is a locus universe rather than a selection and filtering it
  narrows what the second source is even asked about while looking like a filter on the second source's
  calls; and the class it cannot reach — a verdict at a position the mapping source has no record for —
  is **not countable**, since attributing it to a gene is precisely what there is no map for. Say so in
  prose; a count there would be the span reintroduced as a number.

- `@filter-before-the-group-picks-a-winner` — **Decide contestation over the WHOLE group before any dial
  runs, or the dial has chosen the winner (RM134 § C).** A coordinate PubMind describes with several
  records is withheld when their calls disagree, because choosing one needs an ordering nobody defined
  (`@multiplicity-is-a-finding`). Push `--clin-sig` or `--min-confidence` into the query — the obvious
  shape, since SQL is where a filter belongs — and a key whose dissenting record the filter removed
  arrives looking unanimous: the run then writes a confident row at a coordinate where the source
  disagrees with itself, and nothing anywhere says so. The filter is not innocent for being the author's:
  it is `mode()` with an ordering supplied by a flag. So fetch every record at the candidate positions,
  decide contested-or-agreeing per key over the full group, and apply the dials only to what survives.
  The test that bites constructs a dissenter which **either** dial alone would have hidden.

- `@sourcerow-placeholder-guard` — **`SourceRow` carries the placeholder guard, and the "a generated stub cannot compile" guarantee is
  now tested over every `DRAFTABLE` kind (RM76).** It is a plain `BaseModel` — a machine-produced
  reference fact, like the other four sidecars — *and* the one a human starts from a template (S21),
  and nobody had reconciled the two: `source=<<REPLACE>>` compiled green under `--strict` and reached
  `manifest.sources` inside the block its own signature covers. The guard sits on the model
  (`ModuleSpecConfig` is the precedent) rather than through the base, so the classification stays true.
  Two reusable halves: a **vocabulary** column catches a stub by accident and a free-text one does not,
  which is why the free-text half stayed open — *and* why the first draft of the test came out green on
  the unfixed code, asserting only that some error mentioned the token. And a printed guarantee that
  holds "wherever a model inherits the right base" is not a guarantee; parametrize over the registry.

- `@stub-cannot-compile` — **A generated stub must be unable to compile — `vocab.TEMPLATE_PLACEHOLDER`, guarded before
  coercion.** The guard is `mode="before"` on purpose: an unreplaced stub in `start: int` then reads
  as "unreplaced template placeholder in column start", not "Input should be a valid integer". Do
  **not** reuse `MeasureBinRow.unresolved` for this — that sentinel means "no measurement at read
  time" and is designed to *compile*; two opposite lifecycles on one field is the overloaded-axis
  anti-pattern (P5).

- `@file-vs-row-refusal` — **Scaffolding refuses per FILE; drafting refuses per ROW — and the difference is derivable.** A
  file-level rule self-defuses for `draft` (you re-run it per gene), but you scaffold a module once,
  and a stub row has no natural key to merge on because its key columns *are* the placeholder.
  Refusal is per file, not per run, or a module could never gain a second table kind. Both use the
  same definition of absent — a zero-byte file counts as missing.

- `@requiredness-three-shapes` — **Requiredness has THREE shapes, and the middle one is invisible to pydantic.** `is_required()` is
  false for `MeasureBinRow.measure_kind` and `unresolved` — they have defaults — but they are not
  `Optional`, and `load_csv_rows` turns an empty cell into `None` **and keeps the key**, so the model
  gets `None` instead of its default and fails on type. `blank_template` + `required_fields` therefore
  told an author to fill three columns and produced a file the compiler refused, naming a fourth.
  Use `draft.field_category` (`required` / `defaulted` / `optional`) and `draft.authoring_requirements`
  — which also reports `REQUIRED_ANY_OF`, the "rsid **or** chrom+start" rule that is a model validator
  and which no per-field flag can express.

- `@sources-csv-draftable` — **`sources.csv` is draftable, and the exception is the rule's own point (S21, 0.5.4).**
  `draft.blank_template("sources.csv")` used to answer *"is not an authored table of this format"* — a
  false claim, made by the surface an author reaches for *instead of* reading the models. It is in
  `DRAFTABLE` now with `(source, layer)` as its natural key, borrowed from
  `licensing.merge_sources_csv` for the same reason `_CORE_DUPE_KEYS`' other entries are borrowed: a
  draft must not append a row the other writer would treat as already present, and one source
  legitimately appears at two layers. The other three fact sidecars stay out — they are produced by an
  enricher pass, so an author never starts one by hand.

- `@registry-completeness` — **A guard that iterates a model registry is only as complete as the registry — and one omission hid
  another (S21, 0.5.4).** `SourceRow.layer` and `.declared_use` ran closed-vocabulary validators while
  carrying no `vocabulary=` marker, so `authoring_reference()` did not describe `sources.csv` at all —
  and the guard that exists for exactly that
  (`test_every_enforced_vocabulary_field_declares_its_options`, which discovers enforcement by
  *behaviour* rather than from a list) never saw it, because it iterates `reference._ALL_MODELS` and
  `SourceRow` was not in it. The behaviour-discovering half was the good design and it was defeated by
  the one hand-kept thing left beside it. **When adding a model, add it to `_ALL_MODELS`**, and when
  reviewing a guard, ask what it enumerates before trusting what it proves. The cost was concrete:
  `sources.csv` is the **only fact sidecar a human writes** and the only table the compile licence gate
  reads, and an author reconstructing it from a filename has to guess that
  `share_alike`/`commercial_use`/`redistribution` are three orthogonal axes where `None` means unknown
  rather than false — not a guessable shape. The reporter got it right only by reading
  `SourceRow.model_fields`, i.e. reading our source to learn our schema.

  **It happened again in 0.6.1, five models wide and in three different shapes (RM93/RM96/RM100), which
  is why this entry is now about the SHAPE rather than about `_ALL_MODELS`.** `_ALL_MODELS` was missing
  `ResolutionRow`, `FrequencyRow`, `GeneMetricsRow`, `LiteratureRow` and `GwasEffectRow` — the last
  added one day before the audit that found the hole, so the registry was falling behind faster than it
  was being caught up. Admitting them turned the guard on and it immediately found **seven** more
  fields enforcing a vocabulary without declaring it. The other two shapes are the same failure wearing
  different clothes: `test_validate_agrees_with_compile` walked a literal list of four filenames while
  the registry held seven fact tables, and `net.py` said "the nine policies" in prose while the tree
  carried twelve. **All three are a number or a list somebody has to remember.**

  Two rules fall out, and they are the operative ones now. **Assert an equality over a walked set, never
  a floor** — `assert len(found) >= 9` cannot see three new policies, and the one in `net.py` reported
  the *right* number by accident, because it double-counted a client once per importing module and the
  inflation cancelled the two modules it never opened. A guard whose number is right for the wrong
  reason is worse than one that is merely wrong, because the number reads as confirmation. And **a
  count in prose is a registry nothing iterates**: the fix removed the number from the docstring rather
  than correcting it.

- `@vocabulary-on-field` — **A vocabulary binding lives on the FIELD, and it carries the members — `base.vocabulary`.** The
  authoring reference's vocabulary block used to be a hand-kept dict and drifted twice: it never
  learned about `recommendation_strength`/`phenotype_category` (0.5), and it filed `actionability`
  under `open_recommended` while `VariantRow` *rejects* a non-member — a drift in **closedness**, not
  membership, which is why the marker carries a `closed` flag and not just a list. The marker holds
  the frozenset's members rather than a name to look up, because a registry in `vocab` cannot import
  `pgx` (the cycle `base`'s dependency note exists to avoid) and a registry elsewhere is a second
  hand-kept list. Rule for where a binding goes: **wherever its validator is** — shared validator →
  `base.SHARED_VOCABULARIES`; model-specific validator → that model's `Field(...)`. Never mark a
  field nothing enforces: `StudyRow.chrom` and the PGx `chrom`s run no chrom validator, so they carry
  no marker, and the guard test catches it in both directions.

- `@vocab-separator-slip` — **A closed vocabulary accepts `-` where `_` goes, and canonicalizes — `vocab.match_vocab` (0.6).**
  The enricher CLI normalized `--use non-commercial` on its way in while `SourceRow` refused the
  identical string in a cell, so the surface an author learns the vocabulary from taught a spelling the
  file rejected. A separator slip is *the* slip a hand-written CSV makes, and the human-authorable gate
  says the schema absorbs that cost rather than charging it.

  **The rule has two halves and only the first was being tested (RM95, 0.6.1): accept the slip, and
  STORE the declared member.** Three validators called `check_vocab` for its raising side effect and
  returned the raw input, so `MeasureBinRow(measure_kind="copy-number")` validated and stored a value
  that is not in the vocabulary, *inside `content_signature`* — and then every subclass rejected it,
  because `_EXPECTED_KIND` was compared against that same raw string. The base class accepted what its
  own subclasses refused, with an error naming the canonical form the input already denoted. So: bind
  the return, and compare against the bound value, not the argument. The test that could not see this
  proved `check_vocab` canonicalizes and never asked whether anyone kept the answer; it now walks every
  closed-vocabulary field in the schema through `field_vocabularies` plus pydantic's decorator registry
  and drives each validator with both spellings. `check_vocab` runs the matcher, so every
  vocabulary gets it and nothing keeps a private copy — the CLI's `_use` delegates now. Three
  properties to preserve: the value **as written is tried first** and both swap directions after (a
  future hyphenated member cannot be broken by this); the match **returns the declared member**, so
  what is stored, fact-hashed and compared is never two spellings; and it **widens only** (P3), so a
  value that names nothing still fails with the full list. How sure we are it was worth doing:
  `test_validate_agrees_with_compile` had been using `non-commercial` as its example of an *invalid*
  value.

- `@authored-field-names` — **`model_fields` is NOT the authored surface — generators must use `base.authored_field_names`.**
  `VariantRow.variant_key` and `authored_ident` are declared fields (carried in memory, materialized
  to `weights.parquet`) that the compiler *stamps* and `reverse_module` deliberately never writes
  back. Anything that turns a model into CSV columns for a human — `draft.blank_template`,
  `draft.append_rows`, `reference.authoring_reference` — has to skip them, and it must skip them by
  the field's own `COMPILER_MANAGED` marker, **never by name**: `FrequencyRow.variant_key` is the same
  name and is genuinely authored and required, so a name set hides a column an author must fill. Both
  hand-kept exclusion lists that preceded the marker were wrong — `reference.py`'s named only
  `variant_key` and never learned about `authored_ident`; `draft.py` had none, so it wrote a
  `variants.csv` the compiler then refused to load (`authored_ident` renders as `rsid` and does not
  reload as a `list[str]`). The bug survived a green suite because every drafting test used a PGx or
  binning table, and no model but `VariantRow` has a stamped field. **When adding a drafting provider
  or any new model-driven generator, test it against `variants.csv` specifically.**

- `@specific-rejection` — **A generic rejection is a dead end where a specific one is a fix, and the reason lives beside the
  constant (0.5.4).** `extra="forbid"` refuses every unknown column identically, so three different
  mistakes read the same. There are now three guards layered on it, all the same shape — a
  `mode="before"` validator that raises a *diagnosis* and changes no verdict: `vocab.reject_reserved` (a
  name held against a future release), `normalize.reject_authority_keys` (`namespace`/`owner`/
  `canonical_id`, registry-stamped — the reasons had existed since 0.4.1 with `authoring_reference()` as
  their only reader), and `vocab.reject_misplaced` / `MISPLACED_COLUMN_REASONS` (`source`, which is real
  on the four **generated** tables and on `sources.csv`, and nowhere else). Four rules. **Diagnosing is
  not applying** — the inject-only rule bars the validator from *stripping* one consumer's convention, and
  a message strips nothing, so `strip_authority_keys` stays opt-in. **Key on the model's own fields**, so
  `FrequencyRow.source` cannot be broken by the message describing it. **A misplaced column is not a
  reserved one**: reserved is for names no model has, and conflating them would bar a real column.
  And **prose, not a cross-model registry** — `base` cannot import `spec`/`pgx` (the cycle the vocabulary
  markers avoid) and a hand-kept model list is the drift being unwound; a sentence about a stable table
  role does not rot the way a column list does.

- `@hint-redundancy-bearing` — **A hint may not fill a cell a Class-2 check cross-examines — `hints.REDUNDANCY_BEARING`.** Class 2
  works because two *independently-authored* things must agree. Fill `chrom`/`start` from Ensembl and
  `resolution._verify` compares Ensembl with Ensembl; worse, for an rsid-only row that check never
  runs at all, so the row moves from honestly unverified to apparently verified and the compile
  reports success. Same for `doi` vs `literature._doi_conflicts` and `ref` vs
  `verify_reference_alleles`. `literature` already argued this for one field (Crossref is asked about
  the **authored** DOI, since a derived one "exists by construction"). So a looked-up value comes back
  `applied=False` with a refusal; the only thing `hints` applies is a `normalized` rewrite the model
  already performs silently on load (`DiplotypeRow` swaps its haplotype pair). A `--apply` flag on a
  lookup would ship the parked enricher-co-authoring item without deciding to.

- `@row-move-allowed` — **"It moves the digest" is NOT a reason to refuse a row move — that argument was checked and it
  failed.** Probed: a pure reorder moves `artifact.digest` but leaves `content_signature` untouched
  (order-independent by construction), the compile → reverse → compile fixed point still holds,
  duplicate keys are rejected so order can disambiguate nothing, and **nothing reads the append-only
  prefix property** (one test asserts it; no other code). The decisive point: an author reordering
  rows in their editor is already legal and already moves the digest, so forbidding the tool the same
  move proves too much. Mid-flight digest stability is worth ~nothing — the digest is consumed at
  exactly one moment, *publish*, and every authoring edit changes it anyway. What stays refused is an
  `at=N` index (it buys nothing an editor does not) and a `sort`/`canonicalize` command (every row
  moves, no local reason for any of them). What shipped is `append_rows(..., group_by=…)` /
  `place_rows`: **the tool picks where, the caller never supplies an index.** Shifted rows keep their
  cells byte-for-byte — `_render_existing` re-reads them as text — and `DraftReport.shifted` names them.

- `@ragged-csv-row` — **A ragged CSV row misdiagnoses the column *after* the mistake, and both coordinates were wrong
  (S18, 0.5.4).** `hints.inspect_rows` padded a short row with `""` (indistinguishable from cells left
  empty) and, for a long one, shifted every column from the offender onward and dropped the overflow — so
  an unquoted comma in `conclusion` produced `Input should be a valid boolean` against `unresolved`, whose
  authored value was `false`. The field-count mismatch is reported **before** the type error it explains,
  error for a surplus (data is discarded, and `csv_out` carries the damage forward) and warning for a
  shortfall (padding is recoverable). Padding and truncating stay: a hint describes a broken file rather
  than refusing it. Separately, `Finding` now carries **`line`** — 1-based, header-inclusive, the
  coordinate `validate`/`compile` print — beside `row`, a 0-based data-row index; **added, never
  redefined**, because a consumer already compensating for the old meaning would then break silently. The
  compiler's own loader had the ragged case right all along (`more values than header columns`, with a
  line number), which is what made the hints surface the odd one out.

- `@draft-digest` — **A drafted value that has not moved is a copy that can be ESTABLISHED, and the digest is scoped to
  the CHECKED COLUMN (RM73 provenance half, 0.6).** RM4's skip was a module-level guess keyed on the
  release label, and it named its own hole: a cell edited after the draft is no longer a copy and no
  module-level fact can see it. Each provider now hashes the table it wrote, projected onto the column
  its own cross-check later reads, and stamps `SourceRow.draft_digest`; the check recomputes it
  (`enricher/provenance.py`, `DRAFT_PROJECTIONS` — three entries, guarded by a test). Seven things not
  to redo:
  - **Column, never row.** A ClinVar-drafted module *always* has edited rows — `genotype` is a
    placeholder the human is required to fill — so a whole-row hash never matches and the skip never
    fires once. Scoped to `clin_sig`, filling the stub leaves it alone and editing the call moves it.
  - **Raw CSV cells, never loaded models.** One function serves writer and reader, because two that
    disagreed would not fail, they would silently never match. So it must run at *draft* time, where
    the table is full of `<<REPLACE>>` and `reject_template_placeholders` refuses to load it by design.
    Hence no `variant_key`, no `effective_clin_sig`.
  - **The skip is a CONJUNCTION.** The digest hashes the module's table, not the snapshot, so it is
    silent about currency — a matching digest against a *newer* release is a real comparison. Release
    **and** digest. A **live** source therefore never skips: no release to name.
  - **`merge_sources_file` would have eaten it**, being never-clobber — the same rule that bit
    `dataset` and produced `withdraw_stale_dataset`, one column over. `stamp_draft_digest` restamps
    explicitly, and unlike `dataset` it **re-labels rather than withdraws**: one column cannot name two
    releases, but a digest describes the table as it now stands whatever produced it.
  - **Outside `SOURCE_FACT_FIELDS`**, unlike `dataset`. Which release the annotations came from is part
    of the row's claim about the source; how this module was built is not, and it moves on every
    re-draft. `sources.signature` moves nowhere; `content_signature` untouched.
  - **It closed two tautologies nobody had filed**, which is the reason to audit by *check* rather than
    by provider: `pgx_draft` writes `function_status` out of CPIC and the PGx check compares that
    column against CPIC; `clinpgx_draft` writes `evidence_level` out of ClinPGx and the ClinPGx check
    compares that. Both published a guaranteed `findings=0` into `verification.json` — RM4's
    misinformation inside RM45's proof-of-worked attestation. CPIC was also the only provider recording
    **no `dataset`**; it stamps one now. In `enrich_pgx` the skip is **per leg** so PharmVar still runs,
    and `tautology` sits **last** in `_SKIP_PRECEDENCE` (an absence a reader can act on outranks a
    comparison that could not have failed).
  - **What went away is the point as much as what arrived.** `ClinSigAudit`, the
    copied/authored/no_record bucketing, `clin_sig_audit` and the `mode != "strict"` branch are
    deleted; the check behaves identically in both modes. It changed no verdict — the `copied` bucket
    was an early exit *before* the camp logic, and an exact match agrees with itself. Standing limit:
    a row hand-authored **before** a later re-draft is covered by the new stamp and escapes.
  **The phase boundary shipped too** — see the next bullet.

- `@closure-phase-boundary` — **Authoring now has an END, and it cost one optional block on a document that already existed
  (RM73's phase boundary, 0.6).** RM45 had built almost all of it for another purpose: `verification.json`
  binds `module_hash` over the authored files, the compiler recomputes it every compile, and a mismatch
  drops the whole block. What was missing was a record saying *a human declared this final* rather than
  *a pass ran*. `VerificationDoc.closure` + `just-dna-compiler close` (`compiler.close_module`) is the
  whole of it. Seven things not to redo:
  - **No new file, no new binding, no new proof-of-work.** The closure rides the attestation, so an edit
    after closing un-closes the module for free. A free-standing `closure.json` needs its own staleness
    rule and is dropped silently by `reverse` — the RM51 class. It sits **outside** `pow_digest`'s
    payload (`module_hash|signature|nonce`, unchanged), so closing re-mines nothing and every
    attestation written before 0.6 still verifies.
  - **`validate` stays read-only, and that is the item's own argument turned on itself.** A record
    stamped by whatever happened to execute says only *someone ran a tool*, which is exactly what RM73
    levels at an attestation produced as a by-product. So closing is its own command. `--private-key`
    signs `module_hash` with the existing `signing.sign_digest`; unsigned is legal and still
    change-evident (tamper-*evidence* was always the guarantee).
  - **Refuses an invalid spec, never a warning.** An authored set the compiler will not accept is not
    finished; one carrying an unresolvable rsID or an ungrounded threshold is ordinary, and refusing
    there makes closure unreachable for every module whose findings no authored edit can clear (P5).
  - **`record_verification` had to learn to carry it — the never-clobber trap a THIRD time**, after
    `SourceRow.dataset` and `draft_digest`. That pass rebuilds the document rather than editing it, so
    it dropped the new field by default, silently and in the wrong direction (enrichment writes only
    derived sidecars, which are outside the binding). It carries the closure across **only while the
    binding holds** and **drops rather than re-binds** it otherwise: re-stamping would have the machine
    assert on the author's behalf. Generalize it — when another tier starts writing into a document
    this one rebuilds, ask what the rebuild discards.
  - **Absence warns; a false claim drops the block.** No closure is the state every module was in
    before 0.6, so it warns in both modes and is never `strict`-gated (an unclosed module is perfectly
    reproducible). A *signed* closure whose signature fails drops the whole document. Same asymmetry as
    the symbolic-allele `vrs_id` pair.
  - **Closing KEEPS the document verbatim and adds one block — it does not rebuild it.** The first
    version re-attested, which rewrote `producer` from `just-dna-enricher 0.6.0` to
    `just-dna-compiler 0.6.0` on the three examples carrying real check records: that field names who
    put the **checks**, so the compiler was claiming an enricher's cross-checks, manufactured by an
    unrelated act. Caught by reading the corpus diff, not by a test. Reuse also makes *closing
    re-mines nothing* literally true — the payload is unchanged, so the nonce already found over it is
    still the answer. Generalize it: **when one act writes into a record another act owns, restamp
    nothing that describes the other.**
  - **Whether to warn on absence was decided TWICE, and the reversal is the reusable part.** The first
    answer was silence, because `reverse` cannot re-emit the document, so a closed module's
    `compile → reverse → compile` warns on step 3 where step 1 was silent, and RM44 made
    `manifest.compilation.warnings` a parsed surface. Overturned by two facts: the divergence **costs
    nothing enforceable** (`artifact_digest` is a Merkle root over `_OUTPUT_FILES`, parquet only;
    `manifest.json` is not in it; warnings feed no signature; no round-trip test compares them), and
    without the warning the closure has **no consumer in 0.x at all** — a manifest field read by a
    catalog that does not exist yet is the designed-and-never-delivered shape that let the
    `knows_drug` raise escape. The corpus was closed instead, with a test that fails loudly when an
    authored edit outdates one.
  - **That same probe is what BLOCKS the 1.0 gate**, and the asymmetry must not be flattened: warnings
    being free is a fact about warnings, and a **refusal** is not free. Under the gate a reversed spec
    is unclosed by construction, so step 3 refuses on every module and P7's round trip is enforced by
    tests. `manifest.verification` carries the records but not `difficulty`/`nonce`, so reverse cannot
    rebuild a valid document either. Three candidate answers, undecided, in ROADMAP_1_0 § RM73 (gate
    half) — do not build the gate before picking one.
  Measured, not argued: all sixteen reference examples compile byte-identically on `artifact.digest`
  and `content_signature` before and after being closed.

- `@binding-normalizes-newlines` — **The binding reads `\r\n` as `\n`, and the naive way to build that is a
  no-op that looks like a fix (RM82, 0.6).** Rewriting an authored CSV's line endings changed no value, no
  digest and no signature, and still dropped the attestation and the closure — so an author whose editor
  normalizes newlines, or whose Git does through `core.autocrlf`, un-closed a module without touching a
  cell. Fixed as a byte transform, which is what separates it from the content-aware binding RM45 refused:
  no loader, no parse, no schema knowledge. Five things worth keeping:
  - **`size` is inside the hashed listing, and that is the trap.** `module_binding` *is*
    `artifact_digest`, which hashes `{"name", "sha256", "size"}` per file, and `file_entry` stamps
    `stat().st_size`. A builder that normalized the bytes it hashed while reporting the on-disk size would
    still move the binding — by one byte per line, on **exactly** the files the fix exists for. So
    `integrity.newline_normalized_file_entry` reports the normalized length beside the normalized digest.
    Generalize it: before normalizing a hash's input, list everything else that feeds the same hash.
  - **A distinct function, never a `normalize=True` flag on `file_entries`.** A flag must mean the same
    thing in every function that takes one, and a boolean that silently changes *what a hash is over* ends
    up re-baselining `manifest.inputs[]` for a caller who passed it by habit, with no error and no warning.
  - **The stopping point is chosen, not inherited.** A BOM, trailing whitespace and a missing final newline
    are the obvious next steps and are all refused: newlines are the one difference a *tool* introduces on
    a file the author did not edit, the others are things a human typed. A lone `\r` is left alone for the
    same reason.
  - **`manifest.inputs[]` and `artifact.digest` deliberately do not follow**, so the two now disagree on a
    line-ending rewrite — which is the decision, not an inconsistency to tidy. They answer *are these the
    exact bytes*; the binding answers *is this the same module*. `_read_verification_block`'s docstring
    said the two were "one fact rather than two that can disagree" and had to be corrected with the change.
  - **The cost was predicted as every `module_hash` in existence and measured at 7 of 16.** A binding moves
    only where an authored file really carries `\r\n`, and the corpus half that does is the
    **machine-written** one — `csv.writer` terminates with `\r\n`, so the rewrite an author actually
    performs is the normalization *to* LF. The nine unmoved kept their records, producer and nonce verbatim
    through the re-close; two of the seven dropped four attested check records each, which is the rule
    working rather than a loss to avoid.

- `@rm4-dataset-marker` — **The marker for that skip is MACHINE-written, and `panel:` is deprecated with it (RM4, 0.6).** The
  skip used to key on the author's `panel:` pin. The claim being established is *provenance* — these
  rows came from this snapshot — and the tool that copied them is the authority on it, so
  `clinvar_draft` stamps the release into the `dataset` column of the `clinvar`/**`annotation`** licence
  row it already had to write, and `tautology_reason` recomputes the same label from the snapshot in
  hand. **One function computes it for both sides** (`clinvar.clinvar_dataset_label`) because that drift
  would be silent: a writer and a reader disagreeing about the label do not fail, they just never match.
  Five things to keep straight:
  - **Compile-time gene-panel materialization is dead, not deferred.** The compiler must not create rows
    no curator wrote (the `direction`-from-`state` objection, independent of the digest), and expansion
    at compile leaves `reverse` choosing between the declaration and the rows — neither a fixed point.
    Drafting already serves the want, and **the author's no-op over the drafted subset is still an
    authorial act**.
  - **`panel:` stays until 1.0 with a compiler warning, and auto-removing it on reverse is refused** —
    reverse writes `module_spec.yaml`, so dropping the block moves that file's bytes and breaks the
    round-trip fixed point. Deleting it by hand moves nothing (measured on `apoe_epsilon`: same
    `artifact.digest`, same `content_signature` with and without).
  - **The `annotation` layer, not the source alone.** `enrich()` writes a second `clinvar` row at the
    `resolution` layer for the coordinates it looked up; keying on the source would silence the check on
    every ClinVar-resolved module.
  - **The hole is a mode ladder, because closing it per row costs the whole 90% saving.** A cell edited
    after the draft is no longer a copy and no module-level fact can see it. `best_effort` keeps the
    cheap skip **and names the hole**; `strict` runs `audit_clin_sig` and reports copied / authored /
    conflicting / no_record. Deciding per row in both modes *is* the look-up, which is what the skip
    exists to avoid.
  - **The audit is kept only where drafting was established, and "copied" is allele-exact.** For a
    module that never claimed a draft, a value equal to ClinVar's is merely *consistent* with it;
    calling it "copied" asserts a provenance nobody established (the false-accusation rule that keeps
    the gene/locus check coarse). Same reason nothing is counted copied in the **locus-wide fallback**,
    where the candidates span every ALT and a match may be a sibling allele's call — such a row lands in
    `authored`, which understates rather than misattributing.
  - **A never-clobber merge turns a machine-stamped provenance cell into a stale claim, so it is
    WITHDRAWN.** `merge_sources_csv` keeps an existing row so a curator's hand-written *terms* survive a
    re-run, and `dataset` inherited that the moment RM4 made it load-bearing: widening a panel from a
    newer snapshot left the row naming the older release, in the column `manifest.sources` publishes.
    `licensing.withdraw_stale_dataset` blanks it — **never re-labels**, because a module carrying two
    releases has no single release to name, so the answer is unknown and unknown is withheld — and only
    when rows were actually added, since a re-draft that added none changed no provenance. Generalize
    it: when you make an existing column load-bearing, re-ask whether the rule that writes it was
    designed for the new job.

## Schema evolution: columns, signatures, materialization

- `@optional-column-legal` — **A new OPTIONAL column is minor-legal, and the "digest window" that said otherwise rested on a
  premise that expired in 0.4.1.** The charter now states the rule (P3/P4): a new optional column or
  table is additive; **removal, promotion to required, and retyping** are the major-only moves,
  because those are what break a reader or invalidate published data. Two mechanics behind it, both
  measured rather than argued:
  - **An unset optional column is omitted from `content_signature`** (`model_dump(exclude_none=True)`)
    and the per-input hashes cover authored bytes nothing rewrote — so adding one leaves the **authored**
    identity byte-identical. Only a *recompile's* `artifact.digest` moves, and P4 already scoped that to
    a fixed `compiler_version`. Verified on `pgx_slco1b1_simvastatin`: `content_signature`
    `8173dab7…` unchanged, inputs unchanged, `artifact.digest` `3375adef…` → `cd687baf…`, and
    `compile → reverse → compile` still a fixed point.
  - **`integrity.file_entries` skips missing files**, so a new optional *table* does not even move the
    digest of a module that does not carry it. Still true, and now the weaker of the two facts rather
    than the whole argument.

  **The history, since the charter no longer carries it.** `artifact.digest` (2026-07-06) was the only
  identity when the Constitution was written (2026-07-08), so it carried both jobs — *which bytes are
  these* and *which content is this* — and "a column change is major-only" followed honestly. 0.4.1
  (2026-07-23) split the second job into `content_signature`; the clause was never revisited, and every
  "that column is a 1.0 item" deferral in the living docs descended from it. Amended 2026-08-11. What
  this does **not** license: a required column, a retype, a removal, or filling values into an existing
  column (that one is `reverse`'s problem — see RM43).

- `@three-touch-points` — **Adding an authored column is exactly three touch points, and the third is the one that gets
  missed.** The pydantic model; the compile-side row dict + polars schema in `compiler.py`; and the
  **reverse-side `fieldnames` list + `_scalar_cell` mapping**. A column missing from the reverse list
  round-trips as silent data loss, which is why every new column gets a round-trip test. Table kinds
  under `_TABLE_KINDS` are exempt — `_build_table`/`_write_table_csv` are generic over `model_fields`,
  so `DiplotypeRow.recommendation_strength` needed no compiler change at all.

  **The third is really two, and the halves fail differently** — found adding `StudyRow.curator` (S55,
  RM120). `_write_studies_csv` and `_write_variants_csv` each name their columns in a `fieldnames`
  list **and** fill a row dict, and the phrase "`fieldnames` list + `_scalar_cell` mapping" reads as
  one site. Miss the list and the column is simply absent, which is loud. Miss the **dict** and
  `csv.DictWriter` fills the key with an empty string, so the header is right, every cell is blank,
  the reversed spec re-validates, and the value is gone — the quiet failure of the two. A
  column-presence assertion passes; only the digest fixed-point catches it. The guard that survives
  a future column is behavioural: fill every authored field of the model, round-trip, and assert no
  cell came back empty (`test_every_column_the_studies_writer_declares_is_actually_written`).

- `@derived-not-stored` — **Derived-not-stored is the house pattern for a convenience number**: store the exact parts in the
  CSV, materialize the derived value into parquet as a `@property`, and let it fall away on reverse
  because it is not a model field. `FrequencyRow.allele_frequency` (AC/AN) and
  `StudyRow.neg_log10_p` (mantissa/exponent) both do this. For p-values it is load-bearing rather than
  cosmetic: float64 goes subnormal below ~1e-308 and is flatly `0.0` below ~5e-324, so a single float
  column would render a panel's strongest association as its weakest.

- `@overlay-read-at-inputs-never-at-baselines` — **The enricher may READ the author's overlay and may
  never write through it, and the seam is input-read versus merge-baseline (RM136).** A pass that reads
  a derived table as an *input to something else* must see what the module asserts, or an author's
  correction is honoured by the compiler and re-reported by the enricher forever. A pass that reads its
  **own output file** to merge against it writes that file back, so handing it post-overlay rows bakes
  the correction into the derived table — the author's answer restated as the tier's, which is RM83's
  refusal. Read the file you write, and write what you read. **Never a second `apply_overrides`**:
  `compiler.load_overlay` is public for exactly this, and a copy would drift on the normalization seam
  that already produced one silent P7 break. **Answered is per FIELD** — the overlay must correct the
  cell the finding is about, since per-row lets one correction silence findings the author never looked
  at — and **answered is not agreed**: the pair stays in the denominator with a count beside it, because
  dropping it reports a cleaner module than there is. Wire a check to the answered set one at a time;
  *which cells does this comparison read* is a per-check fact, and guessing it silences a real finding.

- `@baseline-is-the-file-the-commit-overwrites` — **A check that compares against a table its own run
  rewrites has to read it before the commit, and its finding is then observable exactly once
  (RM151).** `clin_sig_authority_calls.csv` is the only place this format keeps what a source said at
  the time, and `write_concordance_tables` replaces it whole — so *what did the archive say when the
  author wrote this answer* is answerable for exactly as long as the run has not committed.
  `enrich()` already stages everything above its commit, for the unrelated reason that a refused
  `strict` run must change nothing, so the read has a place; what it does not have is a test that can
  see it. **Statement order inside one function is invisible to every assertion over a return value**,
  so it is walked: the AST guard asserts the read's line precedes the write's, in the same enclosing
  function, and it was demonstrated failing on a source copy with the two swapped before it was kept.
  Found by the call it must precede rather than by the enclosing function's name — the pipeline has
  been a private helper behind the public `enrich` for a while, and a test naming that helper goes
  green by finding nothing the day it is renamed.

  **Report-once is a limit to state, not to paper over.** The run that notices rewrites the baseline;
  the next one is silent. Persisting it needs the record *bound* to the value it justifies — a column
  recording what the answer was written against — which is an authored-surface change, a minor rather
  than a patch, and exactly the binding RM117's three objections all turned on missing. None of those
  objections is an objection to *noticing* that the value moved, which is why the observation ships
  and the mechanism does not. **And say which table**: this is the only overridable table with a
  recorded prior value, so a general *the value moved* check would be answerable for one and silently
  absent for the rest (`@probe-names-the-table`).

- `@a-set-that-silences-is-narrower-than-one-that-raises` — **The overlay's answered set has two
  readings and they take opposite rules; do not reuse the wrong one (RM151 beside RM136).**
  `overlay_answers` is **per field**: it decides whether a finding may be *silenced*, so it insists
  the overlay corrected the very cell the finding is about, and anything looser silences findings the
  author never looked at — the silent-suppress hole the overlay's own design calls its worst case.
  `overlay_answered_subjects` is **every operation and every field**: it decides whether a finding is
  *raised*, and what it is about is the `reason`, which the model makes mandatory on every row whatever
  the row does — so a per-field rule would have to name a column the reason does not live in. The
  asymmetry is priced: a finding raised too widely costs a reader one line, one silenced too widely
  costs them the finding. Two readers, beside each other, neither derived from the other.

- `@a-generic-refusal-cannot-name-its-own-cause` — **`extra="forbid"` cannot tell a typo from a column
  newer than the reader, and no wording fixes that (RM146).** `[curator]` (ours, 0.6.5) and `[curatr]`
  (a mistake) produce the byte-identical *Extra inputs are not permitted*, and they want opposite
  actions — upgrade the reader, or fix the cell. The information was not in the model, so the repair is
  to put it there: `base.since("0.6.5")` on every field, read by `field_first_seen`. **Per
  `(model, field)`, never per name** — `curator` is `VariantRow` 0.2.0 and `StudyRow` 0.6.5, so a
  name-keyed roster answers one of those wrongly. Three rules for the next one of these. **Measure the
  backfill, never recall it**: parse each release tag's own sources from the **AST** rather than
  importing them, because old code need not import under a current Python. **Guard with an equality
  over the walked registry**, since a floor is satisfied by exactly the state that produced the report
  — and check the *registry's* completeness too, or you get a clean bill about the models it happens to
  know (RM96). **A mechanical edit needs to know what a field is**: the first pass wrapped nine
  `ClassVar` constants in `Field(...)`, which the suite caught, and unwrapping them needed the AST
  again since the multi-line forms are invisible to a regex.

- `@the-signal-may-already-be-firing-with-the-wrong-words` — **Before building an observability
  check, ask whether the state is already observable and merely misdescribed (RM117).** The signal S52
  asked for — *the archive resolved a conflict the author had answered* — was already producing a
  finding, because `clin_sig_concordance.csv` holds contested subjects only and is **rewritten whole**,
  so a subject leaving the record is exactly how an author learns the archive caught up. The overlay
  row answering it then reached nothing and drew the generic *the subject may be mistyped*, put to an
  author whose judgement had just been confirmed. **So the work was stopping a wrong signal, not adding
  a right one** — which is what earns a code of its own rather than a rewording of the generic one, and
  why the test asserts the misleading line is **gone** as well as that the good one appears. Two
  corollaries. **Pin the wording when the wording is the decision**: grep the message for adjudicating
  words on a **word boundary**, not as substrings — the boundary version caught a real slip (*the
  conflict ended rather than that the correction is wrong*, which grades the author's row while
  claiming not to), and the substring version fires on "correction" and proves nothing. And **route by
  a `continue`, not a predicate**, where a table's absence has one reading: handing it to the generic
  classifier means the two ambiguous readings are still what gets printed.

- `@lap-stable-means-a-property-of-the-module` — **"Report it over the overlay rather than over what
  it reached" has exactly one non-tautological reading, and RM137 is the worked example.** An overlay
  `update` on a row the compiler drops matched on lap 1 and warned on lap 2, so a module disagreed with
  its own round trip on a published field. Counting the overlay's `update` rows outright fires on every
  healthy module (`@tautology-zero`); counting the ones that reached nothing *is* the lap-dependent
  original. The stable quantity is a property of the **target** — *could an artifact of this module
  carry that row at all* — computable from data that survives the trip, so it answers the same on both
  laps. **The finding must then fire matched-or-not**: an earlier cut classified only the unmatched set
  and was silently lap-dependent again, because on lap 1 the doomed row is still present and matches.
  **Assert equality BETWEEN the laps, never "lap 2 warns"** — the latter passes on the broken code.
  Two traps in the predicate: share the real function the drop uses (`cited_pmids`, extracted from
  `split_cited_literature`) rather than restating it, and **mirror its guards** — the drop discards
  nothing when a module cites nothing, and a predicate missing that guard turns an unstable true
  positive into a **stable false** one, which is worse. Scope it to where the loss actually is
  (`LOSSY_OVERLAY_TABLES`, asserted as a registry equality); the tables that rebuild whole need none of
  it. And classify **late, in both callers**: the inputs do not exist where the overlay is applied, and
  hoisting a load to reach them reorders a published warnings list for no gain.

- `@lookup-with-a-default-hides-a-new-member` — **A `.get(x, default)` over a vocabulary makes the map
  the FIRST edit when the vocabulary grows, not a follow-up (RM150).**
  `derive.trimmed_state` projects a `direction` into the legacy `state` set through
  `_DIRECTION_TO_STATE.get(direction, "neutral")`. Measured before `contested` was added:
  `trimmed_state("contested")` already returned `"neutral"` — and so does
  `trimmed_state("a string that is not a direction")`. So adding a member to `VALID_DIRECTIONS` and
  stopping there ships a module whose `upgraded()` emits a wrong legacy `state` with nothing failing
  anywhere. **The consequence for the test is the sharp part**: an assertion on the *output*
  (`trimmed_state("contested") == "neutral"`) passes against the unfixed code and measures nothing, so
  the guard has to be an **equality over the walked set** — `set(_DIRECTION_TO_STATE) ==
  VALID_DIRECTIONS` (`@registry-completeness`). Generalize: when a vocabulary gains a member, grep for
  every `.get(` and `dict[...]` keyed on it and ask which ones default rather than raise; those are
  the ones that will be wrong silently. And the mirror map may legitimately gain **nothing** — no
  legacy `state` means *the sources disagree about the sign*, so `_STATE_TO_DIRECTION` is asymmetric
  on purpose and says so at the site, because the asymmetry invites a "fix".

- `@currency-cannot-be-a-column` — **A marker for "this row was superseded" cannot be STORED in a
  merge-not-clobber file, and RM108 is the worked example.** ClinGen's `assertion_id` embeds the
  curation timestamp, so a re-curated assertion arrives under a new id, misses `_merge_key` and is
  appended beside the row it replaces — correctly, since both are true records. The entry filed for it
  said the marking "needs a column, which is additive and minor-legal". Legal it is; workable it is
  not, and the reason only surfaces when you try to write it: **the row that must be marked is the one
  already in the file**, and merge-not-clobber forbids the pass editing it (`@sidecar-authoritative`).
  The marker would therefore be correct on every run *except the one that created the ambiguity*. A
  boolean fails that way; a `superseded_by` pointer fails that way and adds three more — the source
  may publish no id to point at, a twice-superseded row needs an immediate-versus-current rule, and a
  pointer *locates* rather than asserts, which is the line `GENE_VALIDITY_FACT_FIELDS` already draws to
  keep `report_url` outside the fact set. **Generalize it: before adding a column to a derived sidecar,
  ask which run writes it — if the answer is "a later one, into an earlier one's row", it is a
  derivation and not a column** (`@derived-not-stored`). The payoff is not only correctness: nothing
  stored means no signature moves and no existing module recompiles to different bytes.

- `@a-source-recuring-is-not-a-strict-matter` — **The gene-validity currency findings warn in both
  modes and raise in neither, which is the SECOND deliberate departure from the enricher's mode
  ladder** (`@enrichment-is-validation`; `@clinsig-never-escalates` is the first). The governing rule
  is the compiler's, written at the VRS coverage site: *a finding no authored edit could clear is not
  a `strict` matter*. Here the only edit available is deleting a row, which falsifies the record
  rather than repairing it — a curating body re-curating is the source working. Both codes are in
  `CARRIED_WARNING_CODES` for the same reason. **The two findings stay apart**: a superseded row is
  the archive having moved on, an unorderable group is the archive not having said enough to tell, and
  one number meaning two facts is `@unreachable-not-absent`'s shape. And **both edges withhold** — a
  tie on `classification_date`, or any group member stating none, leaves no row current and none
  superseded. Breaking the tie on `assertion_id` was refused: an identifier carries no chronology, so
  sorting on one manufactures a winner out of a spelling.

- `@first-fact-check-on-both-sides` — **RM108's currency check is the first fact-table check the
  pre-flight also runs, so it was the first to arrive twice.** `compile_module` runs `validate_spec`
  whatever its own mode, both reached the identical sentence, and the doubled line doubled
  `warnings_summary`'s count with it — the case `@no-rerun-with-counts` exists about. The fact-handler
  loop now dedupes on the message like every other both-sides check (RM94's idiom), and the rule holds
  rather than being dodged because **both passes read the same post-overlay rows**: `validate_spec`
  applies the overlay in its own loop, so a message embedding a count says the same number on each
  side. When you move a fact check into the pre-flight, check the extend site dedupes.

- `@verbatim-except-order` — **Store a source's value verbatim — EXCEPT when the encoding lies about its own order.** ClinGen's
  dosage codes are `{0,1,2,3,30,40}` where `30` = "autosomal recessive" and `40` = "dosage sensitivity
  unlikely", so sorting the raw numbers ranks `40` above `3` (sufficient evidence). They are decoded to
  `VALID_DOSAGE_SENSITIVITY` terms at the enricher boundary (`vocab.DOSAGE_SENSITIVITY_BY_CODE` holds
  the total mapping). Verbatim is right for an *identity* (a star allele, an accession); it is wrong
  for a code a consumer will sort. Also: that file writes `"Not yet evaluated"` in the
  triplosensitivity column for 210 of 1,520 genes — an absence, and what makes `int(cell)` crash.

- `@axes-passthrough` — **The 0.3 axes are a materialized PASSTHROUGH; the derivation is read-time and Python-only.** The
  compiler copies `direction`/`stat_significance`/`clin_sig` into `weights.parquet` verbatim and never
  fills a blank from `state` — `derive.direction_from_state` invents a direction from the weight sign
  for `state='significant'`, which is sound as a consumer's fallback and a fabricated fact in a
  published table. So every `state`-only module (all four curated Generation-I ports) ships an empty
  `direction`, correctly. **Do not "finish" it at compile**: it asserts what no curator wrote — that is
  the whole objection, and it does not depend on the digest (filling *values* into an existing column is
  not the additive case the charter permits). The live gap is that a
  parquet-side consumer cannot reach `effective_direction`/`upgraded()` at all, and COMPILER.md's
  coverage row ticks both tiers and reads *complete*; filed for 0.5.2 as docs (ROADMAP 0.6 idea-book,
  CONSUMER_SUGGESTIONS S5).

- `@annotations-keys-genotype` — **`annotations.parquet` carries `genotype` AND keys on it (RM80, 0.6).** `variant_key` is not unique
  there and never could be — poly-effect is real — so the consumer's other option (carry what
  distinguishes the rows) was the only one. Carrying it *without* keying on it would be worse than the
  gap: two genotypes sharing a conclusion collapse under the old variant-effect key, so the survivor
  would name one genotype while standing for both, turning a missing answer into a wrong one. With it
  in the key the dedup is provably a no-op (`(variant_key, genotype)` is `VariantRow`'s natural key and
  duplicates are rejected), kept anyway so the function does not silently lean on another's guarantee.
  Reverse reads **which** of three keyings an artifact carries (`ann_key_columns`) instead of one bool,
  and the genotype reconstruction had to move *above* the annotation probe, since `weights.parquet`
  stores the allele list plus `phased` rather than the authored cell.

- `@yaml-version-int` — **`version: 3` in YAML is an INT, and RM17's coercion could not reach it — found by closing 61
  foreign modules (0.6).** `_enforce_semver` coerces the pre-0.4 corpus's `v2`/`3` to SemVer and is
  `mode="after"`, so the field's `str | None` refused an unquoted YAML number first, with *Input should
  be a valid string*. Quoted `'3'` coerced, unquoted `3` did not, and **unquoted is the only way YAML
  spells a number** — the guard written for a corpus was unreachable from the file format that corpus
  is written in. **26 of 61** foreign modules from three other repositories refused on this and nothing
  else, all integers. Now widened at `mode="before"` (P3-legal — it only makes refused values legal).
  A **float** stays refused *with the reason*: YAML reads `1.10` as `1.1`, so the authored text is gone
  before any validator runs and coercing would publish a version nobody wrote — and once `version: 1`
  works, `version: 1.0` failing on a bare type name is the surprise the fix creates. Two general
  lessons: **a `mode="after"` validator cannot rescue a value the field's type rejects first**, so
  check which layer sees the raw input; and **run the corpus you did not write** — this repo's sixteen
  examples all quote their version, so no reference example could ever have caught it.

- `@effective-defaults-hash` — **`content_signature` hashes a variant row's EFFECTIVE `curator`/`method`/`priority`, not its cell
  (RM37, shipped).** `defaults:` in `module_spec.yaml` and a per-row cell are two spellings of one value,
  and `reverse_module` re-emits it in the other place (it infers the module default via `_most_common`
  and blanks the matching cells), so hashing the cell made `compile → reverse → compile` move the
  signature. `compiler._resolve_spec_defaults` folds the defaults in first. **The normalization is the
  load-bearing part and must not be "simplified": a value equal to the `Defaults` model's own field
  default is written back as `None`, so `exclude_none=True` omits it** — the same trick RM36 used for
  `genome_build`, and what keeps existing signatures byte-identical (one of eleven reference examples
  moved). It also fixed an unfiled defect: `defaults:` previously reached the hash by no path at all, so
  two modules differing only in `defaults.curator` hashed **equal**. `priority` needs no special case —
  its model default is `None`, so an unset one stays omitted, and `reverse` still rightly refuses to
  infer a `priority` default (that would fabricate a value for rows that never set one). No reference
  example could catch any of this: all eleven use `defaults:`, so an externally authored module found it
  — the same corpus-uniformity lesson as RM36, on the axis "where the author chose to write it".

## Snapshots, caches and network clients

- `@atomic-sidecar-write` — **A writer that truncates in place leaves a valid short file, and a
  merge-not-clobber table cannot tell that from an honest one (S66, RM128).** Nine sidecar writers
  across the enricher and the format tier all had the shape `open(path, "w")` + `csv.DictWriter`, so a
  kill between the truncate and the last row left a table that parses cleanly and is simply shorter.
  For `resolution.csv` that is the worst possible residue: the next run reads it back and merges on
  `subject`, and three branches in `enrich()` deliberately write **no row** for a subject nothing could
  answer, so a truncated table is byte-indistinguishable from a module whose author resolved less. The
  reported incident had a client-killed run keep going, reach the write, and replace a restored 330-row
  table with 162 rows — after which the module validated, closed and compiled green. Fixed with
  `layout.atomic_writer` / `atomic_write_text` (temp file **in the same directory**, since `os.replace`
  is atomic only within a filesystem; `fsync` before the rename, or a power loss exposes an empty file
  where a complete one was). Three things worth keeping:
  - **The helper lives in `layout.py`, beside *where* a sidecar goes.** How it is put on disk turned
    out to be the same class of fact as where — four parties agreeing on the name buys nothing if a
    killed run leaves half a table under it. That moved the module docstring's own claim (*"it is
    `pathlib` and two tuples of names"*), which was corrected rather than left to drift.
  - **`newline=""` is passed through, never defaulted.** `csv.writer` terminates with `\r\n`, the
    sidecars are hashed inputs on one path, and the attestation's newline normalization (RM82) was
    built around exactly that byte — a helper that quietly changed it would move bindings on the
    machine-written half of the corpus, which is the half that carries CRLF.
  - **Three writers were reported and nine were fixed.** The other six were the same shape reached by
    copying a neighbour, so a fix scoped to the report is `@registry-completeness` waiting to happen;
    the guard walks the set with an AST check and asserts an equality, not a floor.

- `@enrich-is-a-transaction` — **A long pass that persists nothing until its tail is not "risky", it
  is a run whose work does not exist yet (S66, RM128).** `enrich()` had one `if write:` block at the
  bottom and everything above it in memory, so a kill at minute 29 had written zero bytes. The obvious
  repair, checkpointing the table as it goes, trades away a property nobody had written down — that a
  refused `strict` run leaves the module exactly as it was — and the trade turned out to be
  unnecessary. Four things worth keeping:
  - **Stage the answer, commit the table.** What goes to disk as the run proceeds is a journal of what
    each *live link answered* (`rsid → [locus]`), never the assembled `ResolutionRow`. Everything
    downstream of an answer recomputes on the resumed run — the hosting filter, the pseudoautosomal
    selection, `locus_index`, the minted ids — so a flag that changed between the kill and the resume
    changes the table exactly as it would have, and the journal cannot carry a stale derivation. It is
    seeded **between the caches and the live links**, which is what makes *resumed equals uninterrupted*
    a property rather than a hope: a snapshot provisioned in between still wins what it would have won.
    Only *positive* answers are staged; a failed request is unchecked, not absent. And a staged answer
    is honoured **only if the link that produced it would run this time** — the seeding reads the same
    two booleans that gate the live blocks, so a `--no-gnomad` or `--offline` resume drops that link's
    answers instead of stamping a row a first run with those flags could never have written.
  - **Same-directory staging is the correctness condition, not tidiness.** `os.replace` is atomic only
    within a filesystem, and `shutil.move` across a partition degrades to copy-then-delete. Staging
    beside the target makes a cross-device move structurally impossible rather than merely avoided, so
    the test asserts the sibling relationship instead of trusting a comment. `layout.atomic_writer`
    already staged exactly there — this extends a shipped primitive from one file to a whole run.
  - **Write the promise down when you get the chance.** *A refused `strict` run changes nothing* was
    true only because the refusals happened to precede the write block. It is now stated, and asserted
    on the **bytes of a pre-existing table** — "the file is absent" would have passed for a run that
    wrote nothing and for one that wrote and then failed to clean up.
  - **A knob may not mean two things.** `write=True` meaning "at the end" under `strict` and "as we go"
    under `best_effort` was refused in advance (`@flag-means-same`). Under a transaction it means one
    thing everywhere, because committing is the only write — and `write=False` therefore stages nothing
    and takes no lock, since a caller that writes nothing has no window to exclude.

- `@flock-not-a-lockfile` — **A lock left behind by exactly the kill it exists for is worse than no
  lock (RM128).** Two concurrent `enrich` runs over one spec directory were last-writer-wins over a
  merge with neither knowing; a zombie run once replaced a restored 330-row table with 162 rows, after
  which the module validated, closed and compiled green. A **lockfile** is the obvious repair and it is
  wrong: the kill this item is about leaves one behind, blocking every subsequent run, and the
  staleness rule that would fix that is a clock (`@hash-the-probe` — guard the plan, not the clock).
  `fcntl.flock` on the spec directory's own descriptor dies with the process, so nothing goes stale and
  nothing needs cleaning up. **Non-blocking**: a run silently waiting half an hour behind a zombie is
  its own unattended failure, and the refusal is accurate by construction since the lock is only ever
  held by something alive. **The degradation is owed and is documented rather than silent** — no
  `fcntl` on a non-POSIX platform, or a filesystem answering `ENOLCK`/`EOPNOTSUPP`, logs that the run
  is *not* excluded from a concurrent one, and both branches are reached by tests because an unreached
  refusal branch is not an API. `flock` is untested here on the network filesystems a consumer may use,
  and ENRICHER says so where a consumer meets it.

- `@progress-unit-is-subjects` — **The unit a progress callback reports is a contract, so argue it
  rather than guessing (RM128).** `enrich`'s resolver chain is batched inside `resolver.py` rather than
  being a per-subject loop, so `(done, total)` could have counted subjects, links or phases, and P3
  keeps whichever was shipped working forever. Subjects, for three reasons that compose: the incident
  is an **idle timeout** (both reported runs died at 1800 s with essentially every variant resolved),
  so the caller needs a keepalive with monotonic progress — which rules out phases, since a 29-minute
  phase emits nothing and the timeout fires anyway; **`total` must be known up front** for the number to
  render, and the subject count is while the link count is not; and subjects are the only unit an
  author's mental model already has, where publishing a link count would make a refactor of
  `resolver.py` a contract change. No protocol was added because none was asked for. Monotonicity is
  **structural** — `done` is the size of a set that only grows — and the assembly loop touches every
  subject, so the last report is always `(total, total)` rather than wherever the links ran out.

- `@currency-asks-the-source-not-the-cache` — **A "has my source moved" check must ask the source, and
  a label only compares against a label of its own kind (RM85).** `SourceRow.dataset` recorded which
  release a module's rows came from and nothing acted on it, so `enrich --verify-datasets` now compares
  it against the release the source publishes now. Three things about the shape, each one a repair that
  looked obvious and is wrong. **The current release comes over the wire, never from the provisioned
  snapshot's `release.json`** — that snapshot is very often the one the module was drafted from, so the
  cheap version of this check would compare a value against its own origin and report a confident clean
  bill, the same self-agreement `--rederive` had to be stopped from doing one flag over. **A digest
  label and a stated-date label do not compare**: `clinvar_dataset_label` falls back to
  `clinvar_sha256:…` when the VCF header states no date, so the two forms name one release space in two
  spellings and equality across them means nothing — uncomparable is `no_reference`, and reporting it as
  *behind* would send an author to re-draft a module that may already be current. **And the tri-state
  has to survive the aggregation**: an unaskable leg is named in the record's `detail` and counted into
  neither `subjects` nor `findings`, because a coverage figure whose denominator is stated elsewhere is
  the defect `_vrs_coverage` exists for. The `strict` gate is written over the superseded set alone for
  the `unreachable_rsids` reason — nothing an author edits clears a failed request, so escalating one
  would make `--offline --strict` impossible forever. **The reach is the honest limit**: only ClinVar
  publishes a release label this tier can read in the namespace it records, so one probe ships in a
  registry derived from `default_probes`, and every other source reports `unsupported` — which is *this
  tool cannot ask*, never *you are up to date*.

- `@rederive-never-shortens` — **A re-derivation that drops what it could not ask about is the
  corruption it was meant to detect (RM83's residue, in RM128).** `enrich --rederive` re-asks every
  recorded subject and reports what moved — MODULE_LIFECYCLE § 5.1's canary, which merge-not-clobber
  had made unperformable. The hole is that the three branches deliberately writing **no row** for an
  unanswerable subject fire under `--rederive` too, so an offline re-derivation would commit a table
  with nothing in it and nothing downstream could tell that from a module whose author resolved less.
  So: a recorded subject **answered** this run replaces (including answered-and-absent, which writes a
  `not_found` row); one that could **not be asked** keeps exactly the rows it had, and the carry-forward
  warns naming them — scoped to subjects the spec still names, since an ordinary run prunes a recorded
  row whose variant the author deleted and `--rederive` must not resurrect it. **A re-derivation also
  resumes only another re-derivation**: after a gap-filling run commits, its staged answers are exactly
  what produced the recorded table, so seeding them would compare that table against its own provenance
  and report a clean bill for the subjects being re-checked — which `--keep-staging` would otherwise
  make easy to walk into. Two more things worth keeping: the report is `None` when nobody re-derived and
  `[]` when nothing moved — only a real difference prints, since a comparison whose empty result is the
  normal case must not announce a zero; and the honest limit is stated rather than hidden, because
  `rm` plus a re-run re-derives just as correctly and reports **nothing**, having destroyed the old
  values before the fresh ones arrive.

- `@gnomad-rate-limits` — **Rate limits are load-bearing in `gnomad.py`.** 10 requests/IP/60s, so everything is batched (20
  aliases; 29 returns HTTP 400) behind a 6s pacing gate on an **injectable clock** — tests prove the
  interval without really sleeping. Per-alias GraphQL errors must never sink a batch; a *pathless* error
  must raise (it's our broken query, and swallowing it looks like "nothing found") — **except a pathless
  error that says a record is simply absent.** gnomAD answers an unknown `variantId` with
  `{"message": "Variant not found"}` and **no `path` key**, while still returning `data` with a `null` at
  that alias, so the absence is already fully expressed by the node and the error is commentary. Treating
  it as fatal made `frequencies` die with a traceback on any module carrying a variant gnomAD lacks —
  which is ordinary, and is what `VALID_FREQUENCY_STATUS.not_found` exists for. `_ABSENCE_MESSAGES` is the
  narrow exemption, matched on the message because with no path there is nothing else to match on. The
  general lesson: "pathless ⇒ our bug" was a premise about the API, not a law — check what the API
  actually does before deriving severity from a field's absence.

- `@constraint-two-releases` — **The two gene-constraint routes are different releases.** The live `gnomad_constraint` API field
  serves **v2.1.1**; v4.1 ships only in the bulk TSV. They carry different `dataset` labels, and
  `dataset` is inside the fact set. Don't "fix" a test that asserts they differ.

- `@suppression-from-merge-key` — **A pass's fetch-suppression set must be DERIVED from the merge key,
  never restated beside it.** `enrich_gene_metrics` merges on `(gene, dataset)` and decided "already
  done" with `source.startswith("gnomad")` — a proxy for the key, and the two disagree exactly where it
  matters: a hand-written correction honestly recording `source="manual"` did not mark its gene done,
  the fetch ran anyway, and the sidecar came back with **two rows under one merge key** contradicting
  each other. Nothing downstream reports that — the fact tables have no duplicate rule (RM107's
  neighbour), so the manifest publishes both as ordinary. `clingen.py`, the sibling pass in the same
  package, always tested `(gene, dataset) in existing`; the shape was understood and simply not applied.
  The scoping half is the part to get right rather than skip: `done` asks whether a row sits under a key
  **this pass would write**, which is the gene plus one of the two dataset labels it writes — keying on
  the gene alone is the older bug in the other direction, where a second authority's ClinGen dosage row
  looked like this pass's own work and suppressed the fetch. Same family as `@draft-appends` and
  `@fieldnames-from-model`: derive, don't restate. (RM109.)

- `@empty-work-is-a-path` — **The run with nothing to do is a code path, and the merge passes' documented
  one.** `enrich_gene_metrics` bound `reference` inside `if wanted:` and read it unconditionally below,
  so the **idempotent re-run** — every gene already has a row, which is what merge-not-clobber promises
  is safe — and any module with no `variants.csv` raised `UnboundLocalError` out of the pass. Worse than
  a crash: it is outside `GeneMetricsEnrichmentError`, so the single `except` RM101 built for this exact
  caller caught nothing. Every existing merge test re-ran with `wanted` non-empty, which is how a green
  2859-test suite never saw it. When a pass is documented as re-runnable, **run it twice on a table it
  has already filled**, and once on a module that gives it nothing to want. (RM104.)

- `@duckdb-vs-polars` — **Read snapshots with duckdb, not polars — but NOT for the reason this bullet used to give.**
  `polars` is `[dev]` in the enricher (builders only) and `duckdb` is core, so the convention is: builder
  in polars, runtime pass in duckdb. `clinvar.py` had it right; `clinpgx.py` first read its snapshot with
  polars. **The stated justification was checked in the 0.5 audit and is false**: `just-dna-compiler`
  requires `polars` *unconditionally* and the enricher requires the compiler, so polars is present on
  every enricher install and no runtime pass was ever unusable on a plain
  `pip install just-dna-enricher`. Keep the convention anyway — it is what keeps the enricher's declared
  dependency set honest about what its runtime actually needs, so the tier could stop pulling polars
  transitively without every pass breaking — but do not repeat the broken-install claim, and do not
  reason from it when judging a new pass.

- `@hash-the-probe` — **A batch lookup must HASH its probe, and the cost is in the BINDING, not the join (0.5.2).** DuckDB
  cannot fold a disjunction of equality *conjunctions* into a hash probe, so
  `WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` is evaluated against every row: cost grows
  with `alleles × rows` and a 297-gene panel ran two hours at 12% CPU looking like a deadlock. Fixed by
  `resolver.probe_table` (temp table + join) — 88 s → 0.21 s on 5,000 alleles against the real 4.4M-row
  snapshot. Four things not to redo. **A single-column list is already fine as `IN (…)`** (it is pushed
  into the parquet reader; `x = ? OR x = ? OR …` is not, so `select_by_gene` was 20.9 s → 6.6 s) —
  `_lookup_positions_by_rsid` and `citations_for` were always correct and must be left alone. **The
  probe rows are rendered as escaped SQL literals on purpose**: measured, same query and data, literals
  0.21 s / composite-key `IN (?, …)` 1.04 s / parameterized `UNNEST(?::VARCHAR[])` 3.51 s /
  `executemany` 8.6 s, so parameterizing it back gives up most of the win. **Benchmark on a spread
  sample** — a `LIMIT 5000` sample is clustered on one contig where row-group statistics prune the
  OR-chain, and the first measurement therefore read ~1×. **Guard the plan, not the clock**:
  `test_query_shapes.py` asserts `EXPLAIN` contains a hash join, and separately times both shapes in
  one process so a slow runner moves both numbers together.

- `@default-arg-before-setup` — **`_cache_dir` loads the `.env` itself, and that one ordering fixed three reports (0.5.2).**
  `_resolve_parquet_cache` calls `load_env()` inside itself, but each `resolve_*_reference` passed
  `default_*_cache_dir()` as an *argument* — evaluated first — so with the base set only in `.env` the
  **first** resolve in a process returned `None` and every later one was correct. That asymmetry is the
  whole explanation for `cache pull` writing where `cache status` does not look, `draft-panel --offline`
  refusing a present snapshot, and a test module whose first skip-guard silently skipped. The durable
  rule: **a default computed as an argument is computed before the callee's setup runs** — if the callee
  loads configuration, the default belongs inside it.

- `@dogfood-data-ignored` — **Dogfood data is git-ignored** (`/data/` now in `.gitignore`): local ClinVar VCF at
  `/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz` (2026-06-27); the built snapshot the example used
  is `data/interim/clinvar`. (`resolution.csv` was provisional while 0.5 was unpublished, which is what
  made `artifact.digest` changes for alt-bearing coordinate modules acceptable. **0.5.0 shipped on
  2026-08-07 and it is frozen now** — see *A new OPTIONAL column is minor-legal* under **Schema evolution** below.)

- `@snapshot-accumulates` — **A PUBLISHED snapshot accumulates — provisioning must fetch only its own files.** The publisher adds
  and never deletes, so `just-dna-seq/clinvar/data` still carries a 159 MB `clinvar.parquet` from the
  single-file era beside the 25 `clinvar-chr*.parquet`; its columns are the raw VCF INFO fields
  (`clnsig`, `clnrevstat`), the readers glob `data/*.parquet`, and one foreign file therefore puts two
  schemas under one DuckDB relation and kills every query with `Referenced column "clin_sig" not found`.
  `download._{ENSEMBL,CLINVAR,CONSTRAINT}_FILES` is the glob each `ensure_*` filters on; don't widen one
  to `*.parquet`. The same failure arrives locally from an **old builder** — if a cache errors with
  "present but not queryable", check `data/` for a file the current builder would not write, and rebuild.

- `@snapshot-layout-locations` — **The snapshot layout lives in `locations`, because FOUR parties must agree on it.** Builder writes,
  publisher uploads, provisioner fetches, reader queries — `SNAPSHOT_DATA_DIRNAME`,
  `SNAPSHOT_SIDECAR_DIRNAMES`, `CITATIONS_DIRNAME`, `RELEASE_FILENAME`. Every disagreement so far was
  silent: `release.json` was uploaded and never fetched, `citations/` was built and never published (so a
  *downloaded* snapshot had no PMIDs and `draft-panel` could not produce a compilable module for its
  users), and `CITATIONS_DIRNAME` was declared twice. A sidecar is a **sibling** of `data/`, never inside
  it — the readers glob `data/*.parquet`. Absence is normal at both ends: only ClinVar has a sidecar, and
  only after `clinvar citations`.

- `@release-json-provenance` — **Publishing a second artifact makes provenance a question — answer it in `release.json`.** ClinVar
  publishes `var_citations.txt` on its own cadence, so a snapshot can carry records and citations from
  different releases; `build_citations` merges its own block (read-modify-write, so the VCF's keys
  survive) and hashes the input when no caller supplied a digest. Recording `null` with the bytes on disk
  is an unknown you chose not to establish, and `source_sha256` is what RM4's `reference_sha256` pins
  against. An unreadable `release.json` is reported and left alone — a provenance failure is not a data
  failure, so the table is still written.

- `@publisher-allowlist-derived` — **The publisher's allowlist is DERIVED from the artifact's own file
  list, never hand-kept — and what it drops, the manifest still attests.** `upload._ALLOW_PATTERNS` was
  `weights`/`annotations`/`studies.parquet` plus the manifest, logo and readme: written when a module
  *meant* a SNP core, and left standing when RM2 made the SNP core optional four releases earlier. So
  neither of the nine 0.4-family parquets nor any of the six derived-fact tables was ever uploaded.
  Measured over the sixteen reference examples (S35/RM89): **seven refused outright** and **eight
  published an artifact whose digest could not be verified**, because `manifest.artifact.files` states a
  name, a sha256 and a size per parquet and `artifact.digest` is a Merkle root over exactly those — so
  the manifest was a **false claim about bytes that are not there**. Only a bare SNP core with no
  sidecar was correct. `sources.parquet` was dropped every time it existed, taking the licence terms and
  the attribution obligation with it, which is the half the consumer found from their end.
  **Three things to carry.** *(1)* It is `@fieldnames-from-model` one tier out: `_ALLOW_PATTERNS` now
  imports `compiler.ARTIFACT_PARQUETS`, so a new table family reaches the publisher in the commit that
  adds it. *(2)* **Widen a stale gate with a POSITIVE rule, never by deleting the constant** — dropping
  the required set alone would have published `manifest.json` + README with no data, silent and worse
  than the refusal. The three that replaced it: the plan carries everything the manifest attests;
  `weights.parquet` never travels alone; at least one `LEAD_PARQUETS` member is present. *(3)* The first
  of those is a **self-check** — comparing the plan against the artifact's own attestation is what makes
  a second drift impossible rather than merely unlikely. An absent or unreadable `manifest.json` still
  **withholds** (tri-state, like RM84's `version_unknown_reason`), so a directory without one stays
  publishable.
  **The logo half was the last hand-spelled member, and it was wrong (RM105).** `logo.png`/`logo.jpg`
  sat there while `manifest.LOGO_EXTENSIONS` admits `jpeg` and `_collect_logo` picks the first in
  `sorted()` order — so **`jpeg` wins**, and the one spelling discovery prefers was the one the
  publisher dropped. Two lessons past the fix. The skew was **named twice and owned by nobody**: the
  CHANGELOG entry that introduced the derived allowlist mentions it, and a code comment deferred it
  ("widening it is not this item's decision"), which is how a known defect survives two releases — if
  you defer a neighbouring gap, file it as an `RMn` in the same commit. And `verify_manifest(check_logo=True)`
  does **not** catch it, because an absent file is not a failure there: an attestation check that
  tolerates absence cannot substitute for the publisher carrying the file. Test it as **set equality**
  over `LOGO_EXTENSIONS` — a floor passed, two of three already being listed.

- `@off-switch-needs-a-probe` — **A knob's disabling value is its own case, and reading the code is not
  running it.** Two instances a day apart, and neither was visible in review. The watcher's `BRANCH`
  knob was spelled `${BRANCH:-main}`, which treats an explicitly empty value as unset — so `BRANCH=`,
  the one thing anybody would type to turn the branch-pause off, silently restored `main` and enabled
  it instead; `${BRANCH-main}` is the fix, and the two spellings differ for exactly one value, the one
  no test reaches by accident. Then S39: `resolve_*_reference(load_dotenv_file=False)` loaded the
  `.env` anyway, in **all six** resolvers, because each passes `default_*_cache_dir()` as an
  *argument* and that helper's `load_env()` was unconditional — so the load happened before the
  resolver had looked at its own flag (`@default-arg-before-setup` wearing a different hat). The
  parameter had existed for two releases, was named in six signatures, and did nothing.
  The rule is procedural rather than structural: **run the disabling value.** A knob is not tested by
  a test that passes the enabling value and a test that passes nothing, because those are the same
  path; and a flag threaded through a call chain needs the probe at the *outermost* caller, since that
  is where an eagerly-evaluated default can outflank it. Where the knob is a parameter, walk the
  family and assert every member accepts it rather than listing the ones you remember
  (`@registry-completeness`) — a seventh snapshot's resolver is how this reopens.

- `@ensure-must-be-called` — **A snapshot's `ensure_*` must actually be CALLED — check the pass, not just the function.** Three
  instances so far, all the same shape. `ensure_constraint_snapshot` shipped with the ClinVar
  generalization and had no caller for a whole release, so `gene-metrics` on a plain install skipped the
  v4.1 snapshot entirely and recorded the live API's **v2.1.1** numbers while warning about the
  difference. `draft_gene_panel` *required* `snapshot=`, so the published ClinVar snapshot could not reach
  an author at all — they had to build 4.4M records from a 200 MB VCF first, which is why the published
  citations were useless to anyone who had not. And `citations/` itself was built, never published. When
  a resource becomes fetchable, grep for who asks. The shape to copy is `enrich()`'s: provision when the
  local resolve returns `None` and the run is not `offline`, degrade to the next link on failure (or raise
  where there is no next link — an empty draft reads as "the source has nothing for this gene"), and add
  no second CLI flag — `--offline` is the switch. An explicit path stays the inject-only escape hatch and
  is never second-guessed. And `release.json` travels with the parquet
  (`locations.RELEASE_FILENAME`, shared by `upload` and `download`) because `source_sha256` is what RM4's
  `reference_sha256` pins against; a cache that cannot state its release is not a pinnable reference.

- `@network-tests-optin` — **Network tests are opt-in:** `JUST_DNA_NETWORK_TESTS=1` runs the live gnomAD query, the seqrepo
  refget re-derivation, and indel-normalization round-trips. They pass; they just aren't run by default.

- `@flag-means-same` — **A flag must mean the same thing in every function that takes one (RM39).** `enrich_dosage_sensitivity`
  was the only pass without `offline`, so a caller running the family under one switch had to know, out
  of band, that one member ignored it — and the cost of forgetting was silent egress from a path the
  docs call zero-egress. The shape to copy is `enrich_frequencies`: a **no-op with a warning**, reported
  as `skipped_offline`, which is a first-class answer distinct from "ran and found nothing" and from a
  failure. An *injected* payload (`curation_text=`) still wins — handing over bytes you already hold is
  not egress, and refusing it would break the inject-only escape hatch. Corollary from the same round:
  **"a flag with one legal value" is a claim about the current wiring, not about the function.** That
  was the standing reason `enrich_clinpgx` had no `offline`, and RM38 gave it a second value the same
  week — re-ask the question whenever the wiring changes.

- `@dont-discard-computed` — **A number this workspace computes and discards gets recomputed by every consumer (RM40/RM41).** Two
  instances, one argument. `enrich()` computed the `MintResult` the compiler later stamps into the
  manifest and dropped it, so a pre-compile consumer re-implemented per-ALT-slot counting and could
  disagree with the manifest a publish would produce; it is now `EnrichmentResult.vrs` (`None` when the
  pass did not run — never a coverage of zero). And `_load_csv_rows` was the only correct authored-CSV
  loader *and* private, so a consumer chose between a private symbol and a re-implementation with two
  known traps; it is now `compiler.load_csv_rows`, with `compiler.load_spec_variants` for the
  build-injection-and-restamp, and `verify_acmg_sf`/`check_identifiers` take `spec_dir=` beside
  `variants=` (**exactly one, never both** — a caller passing both has two answers in mind). Before
  logging a computed value and returning, ask whether a caller would have to recompute it.

- `@retry-attempt-floor` — **A constant two deployment shapes want different values of is a knob (RM42).** Nine
  `stop_after_attempt(3..4)` were decorator arguments evaluated at import, so a *server* inside an
  unattended publish could not ask for more persistence than an author at a terminal wants — and a
  consumer was walking the package reassigning `policy.stop`. `net.attempt_floor` reads
  `$JUST_DNA_HTTP_RETRY_ATTEMPTS` per call. Two shape rules worth reusing: **a floor, not a flat set**
  (the per-client differences are deliberate — gnomAD and eutils are at 4 because their budgets are
  tightest — and below a client's own default it is a no-op, since nothing wants *less* persistence),
  and **leave a composed policy alone** (`stop_after_attempt(3) | stop_after_delay(60)` means both, and
  raising one term changes something whose author meant the conjunction).

- `@shared-pacing-gate` — **A rate limiter the injection API tells callers to share must be safe to share (S15, 0.5.4).**
  `PacingGate.wait()` read `last`, slept, then wrote it with no lock, so two threads could both find the
  interval elapsed, both skip the sleep, and turn a published 3/s budget into 6/s — a budget someone else
  enforces by blocking the operator's IP. What decides it is not thread-safety in the abstract but that
  `LookupClients`' own docstring tells callers to hold and reuse a client, so a server threading its
  blocking work arrives at a shared gate *by following our documentation*. The lock covers the
  **bookkeeping, not the sleep**: each caller reserves the next slot and waits for it alone, so N callers
  get N slots one interval apart and none blocks another. Holding a lock across the sleep would instead
  give "one in-flight request per service", which is a **concurrency limit, not a pace** — a different
  axis, and a semaphore's job (P5). Proven on a frozen clock: four threads at a barrier must come out
  spaced by the interval, and the old code yields gaps of `[6.0, 0.0, 0.0]`.

- `@probe-the-real-file` — **Probe a source's real file before modelling it; the docs lie by omission.** Every non-obvious
  decision in this round came from a probe, not from a spec: CPIC's recommendation classifications
  (five values, `n/a` among them), ClinGen's non-ordinal codes, the ACMG SF list existing only as an
  HTML table (so the check was deferred rather than built on a scrape), and Orphanet's IRI — `ORPHA:558`
  is a term at `…/ORDO/Orphanet_558`, so composing `stem + PREFIX + "_" + local` queries `ORPHA_558`
  and gets **HTTP 200 with zero terms**, which is indistinguishable from "this id does not exist". That
  last one is the shape to watch for: a lookup bug that surfaces as a false finding about the module.


- `@multiplicity-is-a-finding` — **A source whose record id is keyed on extracted text fans one variant
  into many contradicting rows, and the fan-out is the result (RM134 § A).** PubMind consolidates into a
  PVID on gene symbol plus cDNA or protein change, never on a coordinate, so 72,121 of 358,559 allele
  keys in the 2026-08-24 file carry several PVIDs, worst case 47, and 35,742 of those disagree on the
  normalized call. Collapsing to one winner was the obvious repair and it is rejected: choosing needs an
  ordering nobody defined, which is `mode()` over an unsorted group — banned outright. Every PVID stays
  its own row and `release.json` records `multi_pvid_keys`, `max_pvids_per_key` and **`contested_keys`
  separately**, because "several records here" is tidy-up work while "several records that contradict
  each other" is the finding. The same builder drops two thirds of its input (codon enumerations that
  need two or three simultaneous substitutions), which is why the drop reasons are a walked registry and
  `input_rows == record_count + sum(dropped.values())` is asserted as an equality: silent truncation
  reads as full coverage. One drop reason was found only by probing the real file — 16 rows whose alt is
  `0` or `N`, which no documentation mentions (`@probe-the-real-file`).

## Dogfooding, adversarial probing, and how a finding gets filed

- `@dogfood-lacks-are-results` — **Dogfooding means using the shipped surface to do real work — and a capability the tool LACKS is
  the result, not an obstacle to route around.** The moment you reach for an ad-hoc script, a raw
  `httpx` call, or a hand-written query to get past something the product cannot do, the exercise has
  stopped producing its signal: you have proven the task is possible with *general* tooling, which was
  never in question, and learned nothing about the product. When the tool cannot do the step, that is
  the finding — record it (roadmap / field notes) and, if it blocks the work, **build it into the
  product and carry on with the product**. This happened for real: drafting an HFE panel needed
  citations, the enricher turned out to *check* an authored PMID but have no way to *find* one, and
  the reflex was to script PubMed esearch directly. That script would have produced a
  reference example while hiding the actual result — grounding evidence is mandatory for a module, the
  ClinVar snapshot carries no PMIDs, so `draft-panel` cannot produce a compilable panel on its own.
  (The same round's *good* dogfooding went the other way: drafting a real panel exposed that one rsID
  naming two alts collapsed to a single row and silently lost an allele, and that got fixed in
  `clinvar_draft`.)

- `@dogfood-not-validation` — **Dogfooding is not validation.** Validation is what tests do — real fixtures, computed
  expectations, adversarial cases. Dogfooding asks a different question: *is this usable, and what is
  missing?* So do not "verify the tool's answers" with a second, independent implementation while
  dogfooding; that is a test, and it belongs in the suite. Use the tool, notice the friction, and
  write down what was not there.

- `@adversarial-role` — **The adversarial role, and why it pays.** Dogfooding finds friction; the sharper yield comes from
  switching roles deliberately — *be a beta-tester trying to show the libraries fail at something they
  advertise*, then switch back and fix. Two rules keep it honest, and both matter. **Attack claims,
  not gaps**: a documented deferral (RM5's symbolic alleles, VRS-for-indels) is a decision, and
  "finding" it proves nothing; what counts is where a docstring, a comment or a doc *promises*
  something the code does not do. **Use real data**: no `rs999999999`, no `e-328`. Every finding of
  the 2026-08-03 round came from a real gene, and each is a sentence that quotes the code's own claim
  back at it — `vrs.py` promised "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids" while
  a GRCh37 module minted GRCh38 ids; a comment called `chrom=Y` "the false-positive-free half" while
  PAR1 is diploid in everyone; `draft-panel` asked for a `genotype` and supplied neither `ref` nor
  `alts`.

- `@probe-uniform-corpus` — **Pick the probe by where the schema generalized from one case.** The two blocking defects that
  round were both "the documented example only ever showed one": `REFERENCE_EXAMPLES.md` §4 shows one
  MT variant per gene, so `HeteroplasmyRow` keyed on the gene and a second real MELAS variant made the
  module uncompilable; the binning bounds were generalized from integer kinds, so a continuous measure
  turned out to be untileable (RM35). Choose a real case with **two** of whatever the example has one
  of, and a case at the edge of a stated convention (a PAR locus for "Y is not diploid", a non-GRCh38
  build for "the key names its build").

- `@probe-your-own-work` — **Turn the tool on the work you just did.** A check written in the morning is the best candidate for
  the afternoon's probe, and it will be wrong in a way its tests were not. The phase-ambiguity check
  shipped, then reported 595 ambiguities in a CYP2C19 module that has none (grouped by row instead of
  by haplotype pair), then — once fixed — told CYP2D6 authors that phase would resolve alleles the
  module defines *identically*, which phase cannot. Both were found by running it on a real 16k-row
  module, neither by re-reading it.

- `@probe-becomes-example` — **Finish each probe as a reference example with a README that names what it broke.** The module is
  the regression test and the README is the evidence; a finding recorded only in a commit message is
  not reproducible. Keep the failing observation in the test suite by demonstrating it on the *old*
  behaviour (strip the column, watch the compiler reject the real rows) rather than asserting that it
  used to fail.

- `@fix-vs-surface` — **Separate "fix it" from "surface it" before writing any code, and be strict about the line.** Fix a
  false claim, a misdiagnosis, a wall of un-aggregated warnings, a guard that is never reached. Surface
  anything where the obvious repair is itself a design decision — and say *why each candidate repair is
  wrong*, because that is the part that makes the item actionable later. RM31/32/33/35 each carry that
  paragraph; RM33's is the cleanest, since one of its two obvious fixes is charter-illegal.

- `@dedup-finding-needs-example` — **Dogfood a P7/dedup finding before you report it — construct a *real, sensible* example against
  the actual code paths, or it is not a finding.** A round-trip/dedup "loss" that is mechanically
  possible but has no real instantiation is noise; walk the data model with a biologist's eye before
  flagging it. The standing example: `annotations.parquet` dedups on the **variant-effect pair**
  `(variant_key, conclusion, negatives)`. An audit flagged "two rows sharing that key + identical
  `conclusion`/`negatives` but differing `gene`/`phenotype`/`category` collapse to the first — a P7
  loss." It read airtight mechanically, yet it is **non-real**, and trying to build one example proves
  why: sharing a `variant_key` forces a *single locus* (a one-to-many rsid is **expanded to distinct
  coord-keys** by the resolver, so paralogs never share a key) ⟹ one `gene`; and identical
  `conclusion`+`negatives` means the *same effect* ⟹ the same `phenotype`/`category`. `gene` isn't
  even carried in `weights.parquet`, so two such rows are physically indistinguishable regardless of
  keying. The constraint set is empty — no real, sensible module hits it. The **genuine** poly-effect
  loss (one locus, two genotypes, *distinct* conclusions — het "carrier" vs hom "affected") is what
  the variant-effect-pair keying already fixed. Lesson: empirical probing + a real-example test beat a
  plausible-looking mechanistic claim; the mechanistic claim, unfalsified, was a mechanical re-flag of
  an already-closed item.

## Testing traps

- `@test-no-credential` — **A test that means "no credential" must SAY so — `api_key=None` does not, and `.env` leaks across
  the whole session.** Two mechanisms compound here, and neither is visible on CI:
  - **`api_key=None` is indistinguishable from "not passed."** `PharmVarClient.__init__` does
    `api_key or os.environ.get(API_KEY_ENV)` (`EutilsSettings` the same for `NCBI_API_KEY`), so an
    explicit `None` still picks up a real key. `test_one_source_failing_does_not_sink_the_pass` built
    a "keyless" client that was configured, PharmVar answered its `MockTransport` happily, and the
    assertions about degrading-without-a-key failed — **only for a developer who had legitimately
    configured a key**. Green on CI, broken on the machine that owns the credential, which is exactly
    the wrong way round.
  - **`.env` reaches `os.environ` from an unrelated test and stays there.** `locations.load_env()`
    runs inside each `resolve_*_reference`, so *any* test that resolves a cache path loads the repo's
    `.env` into the process environment and every later test inherits it. Run that file alone and it
    passes; run the suite and it fails. **Suspect ordering whenever a test passes in isolation and
    fails in the suite** — the pollution is a global `os.environ` mutation, not a fixture.

  So neutralize the variable in an autouse fixture, and **`setenv(VAR, "")`, not `delenv`**:
  `load_dotenv(override=False)` skips a key that is merely *present*, so an empty value survives a
  later reload where a deleted one is silently restored. Every reader treats empty as absent
  (`x or environ.get(...)`). `test_eutils.py` was believed to have the idiom right for `NCBI_API_KEY`
  all along — see the correction below, it did not;
  `test_pgx_licensing.py` now carries it for `PHARMVAR_API_KEY`. Three real credentials sit in `.env`
  (`HF_TOKEN`, `PHARMVAR_API_KEY`, `NCBI_API_KEY`), so this applies to any new test that asserts
  unkeyed behaviour — a pacing interval, a skip, a degradation warning.

  **Confirmed in 0.6.1, one file away from where the rule is written.**
  RM100 made `EutilsSettings` call `load_env()` where it reads `NCBI_API_KEY` (`@credential-where-read`),
  and `test_eutils.py` went red on a developer machine with a key in `.env`: it used
  `monkeypatch.delenv("NCBI_API_KEY")` and had only ever passed because nothing had loaded `.env` yet.
  `test_literature_terms.py` states the rule beside its own fixture, in this repo, in prose. So the
  rule was written down, explained, and violated one file over — which is the 0.6.1 finding in
  miniature: **a written rule is not what catches a regression; a test is.** Worth the confirmation
  because it also validates the *reason* for the spelling: `load_dotenv` skips a variable that is
  merely present, so `setenv(VAR, "")` is the only thing that holds once anything loads `.env`.

- `@weight-has-no-unit` — **`VariantRow.weight` is the one magnitude in the format with no unit column, and
  filling it from a source is barred (RM90/RM92, S36).** `effect_size` has `effect_measure`; `weight` has
  `float | None` and "Score (positive=protective)". A consumer living with that across a corpus reported the
  result — the weights "construct nonsense", every module means something different, and *de facto* each has
  its own methodology. Two things came out of triaging it. **Measured: `weight` is authored zero times in this
  repo** — four of the nine `variants.csv`-carrying examples have the column, 42 rows, every cell blank — so
  the 1.0 review of whether `weight` survives has a data point it lacked. And the obvious repair is refused:
  MODULE_LIFECYCLE § Stage 3 names `weight`/`direction`/`effect_size` among the cells no tool fills, every
  check reports rather than repairs, and a null `weight` means *the author has not modelled this*. There is a
  sign trap under it — `weight` is positive=protective, a GWAS beta is positive on the **effect allele**, so a
  silent fill inverts the claim on rows nobody re-reads. What shipped instead: `gwas_effects.csv` beside the
  authored column (never inside it), and a free-text `weighting:` block so a module states its scale.
  **A per-row precedence rule was refused too** — "use the GWAS value where `weight` is null" puts two
  methodologies in one summable column, which is the reported defect, and leaves nothing for `weighting:` to
  declare. So was splitting the module in two: the split criterion would be *source coverage* rather than
  methodology (module B = "variants with no published GWAS"), and membership would churn on every new paper,
  routing an upstream fact into authored identity — the thing the derived-fact category exists to prevent.

- `@unknown-effect-allele` — **The GWAS Catalog writes `rs4149056-?` when a study never established which
  allele carries the effect, and such a row is kept and counted, never dropped (RM90).** 42 of 195 rows on
  `hfe_hemochromatosis`. It parses to `effect_allele=None` — never `'?'` (which would look like an allele a
  consumer could match on) and never the reference (a fabrication). The row still travels because it is real
  evidence that simply cannot be used as a weight, and `manifest.gwas_effects` publishes
  `with_effect_allele`/`without_effect_allele` so neither silent reading is available: a consumer that dropped
  them and one that kept them would both be wrong invisibly. The same probe supplies the other half of the
  lesson — **12 distinct `effect_unit` values for one variant**, of which `SD units`/`SD`/`s.d.` are three
  spellings of one and `g/dL`/`g/dl` differ only in case. Store the unit verbatim, including the Catalog's
  useless `unit` (138 of those rows), because "these betas are on unknown and possibly different scales" is
  the fact a consumer needs, and normalizing the spellings would be inventing agreement.

- `@acquisition-gate-is-not-a-read-gate` — **`check_declared_use` gates a FETCH; reading a snapshot the
  operator built is not one (RM134 § C).** Its unknown branch returns a skip, which is right for a pass
  about to go and get data whose terms nobody can state — and PubMind is the first source in
  `licensing.py` whose `commercial_use` is `None`, so that branch had never had a real caller. Wiring the
  drafting provider through it the way `clinvar_draft` and `pgx_draft` are wired would have made
  `draft-panel --source pubmind` skip unconditionally, whatever `--use` said: a feature that is dead on
  arrival, and dead for a reason that is not about drafting. Nothing is fetched there — there is
  deliberately no `ensure_pubmind_snapshot`, the operator ran `pubmind build` themselves, and refusing to
  read the result would make our own command's output a file nothing may consume. The precedent already
  existed one file over: `gwas.py` writes its `SourceRow` and never calls the gate, and the GWAS
  Catalog's `commercial_use` is unknown too. So the provider **reports** the reason in the source's own
  words and writes the row with nulls; unknown terms warn and never gate (`@no-named-licence`), and what
  the unknown answer really governs is *publishing* a module carrying those bytes.

- `@no-named-licence` — **A source may state its terms in prose and name no licence, and unknown commercial
  terms warn rather than gate (RM90).** `GWAS_CATALOG_TERMS` is the first entry in `licensing.py` with
  `license=None`: EBI's terms-of-use page says *"EMBL-EBI itself places no additional restrictions on the use
  or redistribution of the data … other than those provided by the original data owners"* and names no CC or
  Apache grant. `redistribution=True` follows directly from that sentence. **`commercial_use` stays `None`,
  and the trailing clause is why** — the sentence permits "use" generally, but conditions it on terms that,
  for an aggregator of thousands of publications, are not established. Unknown is neither permission nor
  refusal, and the machinery already agrees: `taints_commercial_use` requires an explicit `False`, so a null
  warns and the compile gate stays quiet. Do not "tidy" it to `True`; a test pins it. Two more findings from
  the same pass, both about reading a *live* source rather than its docs: a **404 is the empty answer** (the
  Catalog holds only variants with a published association, so it 404s on a rare clinical one — the first
  version read that as an outage and died on the first variant of the first real module), and **`pvalue: 0.0`
  is an underflow the source really publishes** (withhold the queryable number, keep the verbatim string,
  keep the row — an early version discarded whole associations over one derived column).
