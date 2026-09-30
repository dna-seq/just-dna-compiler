# VCF 4.5 against the schema: what changed, and what the 4.4 audit got wrong

**Research doc, 2026-09-30. No code changed; § 2 was filed afterwards as RM313, the rest are candidates.** A read of the full VCFv4.5/BCFv2.2
specification against `just_dna_format` and `just_dna_compiler` at `main` `b2325d5`, redoing
[VCF_4_4_AUDIT.md](VCF_4_4_AUDIT.md) one spec version on. Same scope as that audit: cases the schema gets
wrong or cannot express that are not already tracked as an `RMn` and not already declared as a blind
spot in [COMPILER.md](../COMPILER.md). Candidates are listed for the maintainer to file or not; none is
numbered here.

**Which spec, exactly.** Three `samtools/hts-specs` commits matter, and they are different things:

| Commit | Date | What it is |
|---|---|---|
| `eeff0c6` | 2024-06-28 | *"Finalised VCFv4.5 specifications"*, the commit that added `VCFv4.5.tex` |
| `e821e4f` | 2026-02-24 | the last commit to touch `VCFv4.5.tex` (`LGL`/`LGP` retyped Integer to Float, #851) |
| `510c107` | 2026-08-12 | `master` HEAD on the day of this read; the tree every quotation below comes from |

4.5 is a merged, finalised specification, not a draft or an open pull request. Three pull requests
against it are still open and are cited below where they bear on a finding, always as *upstream
discussion*, never as the spec: #844 (INFO END, opened 2025-09-09), #853 (the gVCF example, 2026-02-24)
and #579 (Phred wording, 2021).

Section numbers are 4.5's. They match 4.4's everywhere except §7, where 4.5 inserted *Changes between
VCFv4.5 and VCFv4.4* as §7.1, so 4.4's §7.2 (*Changes between VCFv4.4 and VCFv4.3*) is §7.3 in 4.5.

---

## The through-line

**4.5 was already the current specification when the 4.4 audit was written.** That audit read
`hts-specs` `c101c79` on 2026-08-13, fourteen months after `eeff0c6`; the file it read,
`VCFv4.4.tex`, carries the title line *"(Superseded by the VCF v4.5 specification)"* in that same tree.
The RM53–RM67 cluster was therefore built against a superseded version. That turns out to cost less
than it sounds, because 4.5 is a small release and nearly all of it lands outside the four pointer
columns. But it is why this audit exists, and it is the first thing to say.

The one 4.5 change that does reach us reaches the **callability** contract, and it reaches it through
the reference block. 4.5 deprecates INFO `END`, moves a gVCF block's extent to a per-sample FORMAT
`LEN`, redefines any `END` still written as the maximum over every sample in the record, and says that
a sample whose position is covered by its own earlier block carries `GT=.` there. Our printed guidance
tells a consumer to find reference evidence by interval containment on `END`. Against a multi-sample
4.5 file that rule credits one sample's block to positions only another sample called, which is the
"not screened" read as "screened negative" collapse the consumer contract exists to forbid (§1).

The largest finding is not a 4.5 change at all. Re-reading §1.6.1.6 to check RM57 against 4.5 showed
that the 4.4 audit's QUAL arithmetic was backwards for monomorphic records: a QUAL floor inverts on no
record at all. That error shipped as RM57 into a pinned warning phrase, a printed field description,
SCHEMAS.md, COMPILER.md and the scenario corpus (§2). The advice beside it, to state the floor against
`GQ`, does not survive either, because the spec defines GQ conditioned on the site being variant.

---

## What 4.5 changed, and what that did to the 4.4 findings

### The 4.5 changes list (§7.1), against the four pointer columns

§7.1 lists nine items. Each is placed here against what it touches in this repo:

| §7.1 item | Touches | Effect here |
|---|---|---|
| Base modification support (FORMAT `M5mC`, `M5hmC`, `M6mA`, …) and `Number=M` | `source_field` | new keys the pointer grammar already accepts; no `measure_kind` holds one (§6) |
| All FORMAT keys `M[0-9]+[ACGTUN]` reserved | key grammar | none; the grammar accepts them and nothing here names one |
| `Number=P` "added" | cardinality | bookkeeping only: `P` was already in 4.4 §1.6.2 and in `vocab.VCF_FIELD_NUMBER` (see §7) |
| Local alleles: `Number=LA/LR/LG`, FORMAT `LAA`, `LAD`, `LADF`, `LADR`, `LEC`, `LGL`, `LGP`, `LPL`, `LPP` | `source_field` + element rules | an element rule stated by ALT index lands on the wrong value of a local-allele field (§5) |
| INFO `END` deprecated, now a computed field | `callable_from`, RM57's guidance, RM65's quotation | the block-containment rule we print is wrong on multi-sample files (§1) |
| BCF `rlen` follows the computed END | none | no BCF surface here |
| FORMAT `LEN` for sample-specific `<*>` blocks | `callable_from`, `requires_callable` | the block's extent is now per sample (§1) |
| Header line mandatory | none | |
| `<NON_REF>` is an alias of `<*>` | allele grammar | already classified identically (§7) |

Two changes are not in the list and matter more than several that are:

- **§5.5, a new `GT` rule.** *"Positions implicitly called by a preceding `<*>` for a sample must have
  GT set to the missing value (`.`) and have no FORMAT fields other than LAA present."* In 4.4 a `.`
  in GT was a no-call. In 4.5 it is also *"see this sample's earlier block"*, and the two are told apart
  only by looking back along the contig (§1).
- **§1.6.1, END's new definition.** When present, END *"must be set to the maximum end reference
  position of"* REF, every SV allele's SVLEN, *"and the end positions calculated from FORMAT LEN for the
  `<*>` symbolic allele"*. That is a per-record maximum across samples, not any one sample's extent.

The rest of what the audit brief asked about was diffed and came back unchanged: the ALT grammar
(other than the alias), the GT grammar, `CN`/`CICN`/`RUC`/`CIRUC`/`RN`/`RUS` and the `<CNV:TR>`
machinery (the examples only lost their `END=`), the reserved INFO table (only END's description
moved), the key grammar, the missing-value and list rules, and the SV/breakend notation. Diffing the
two reserved-key tables mechanically (both versions' Table 1 and Table 2 plus the §3/§4 header lines)
gives **no new INFO/FORMAT collision in 4.5**: the colliding set is `AD ADF ADR CICN CN DP MQ` in both.
The last member is not in our set, which §3 takes up.

### Each 4.4 finding, where it went, and what 4.5 does to it

Line numbers below are re-derived from `b2325d5`; the 4.4 audit's are stale.

| 4.4 § | Item | Status today | Under 4.5 |
|---|---|---|---|
| 1 | Bare key names two fields | **RM53, shipped 0.6.** `INFO/`/`FORMAT/` accepted (`vocab.py:99-100`), bare colliding key warns (`compiler.py:1932`, `vcf_pointer_key_collision`); both reference examples re-authored to `FORMAT/AF`, `FORMAT/DP` | agrees; no new collision. `CICN` was a collision in 4.4 too and was missed (§3) |
| 2 | No element selector | **RM54, shipped 0.6** on `source_field` only (`VALID_ELEMENT_RULES`, `vocab.py:227`); `callable_element`/`quality_element` reserved, not built | the rules are defined by ALT index, which 4.5's local-allele fields do not use (§5); the cardinality table predates 4.5 and misses 4.4 keys too (§3) |
| 3 | `copy_number` modelled as integral | **RM55, shipped 0.6** (`measure_tiling`, `modifier_copy_number` float beside the deprecated `int`); removal half open in [ROADMAP_1_0.md](../ROADMAP_1_0.md) | unchanged; `CN` stays Float |
| 4 | Repeat count is an interval; several motifs | **RM56** 0.6 half shipped (withhold + warning), policy half open in [ROADMAP_0_8.md](../ROADMAP_0_8.md); motifs are **RM66**, open there | unchanged; `RUC`/`CIRUC` identical, `RN`/`RUS` identical |
| 5 | QUAL inverts; a block wants containment and MIN_DP | **RM57, shipped 0.6** as docs + `quality_floor_inverted` | first half **refuted** on re-read, not by 4.5: nothing inverts, and the shipped warning is a false claim (§2); second half (interval containment, `MIN_DP`) stands, and 4.5 changes where the interval's end is read (§1) |
| 6a | `alts="."` splits `variant_key` | **RM58, shipped 0.6** as a diagnosis (`non_nucleotide_reason` answers `"missing"`, `MISSING_ALLELE_PHRASE`). Probed: `1:100:A:.` beside `1:100:A` still, which is the decided shape | unchanged |
| 6b | `*` has no home | **RM59, shipped 0.6.** `*/A` loads, sorted `*` first (`A/*` refused as unsorted); contract states the withhold | unchanged |
| 7 | `chrom` rejects `chrM` | **RM60, shipped 0.6.** Probed: `chrM`, `M`, `MT`, `chrMT` all load as `MT` | unchanged |
| 8a | Pointer grammar rejects `1000G`, dotted keys | **RM61, shipped 0.6.** Probed: both accepted | 4.5's new keys (`M5mC`, `MXaoN`, `LAD`, `LPL`) all parse |
| 8b | float32 at an inclusive bound | **RM62, shipped 0.6** as the compare-in-float32 contract rule | unchanged; the `M` fields are Float too |
| 8c | `A\|G` names no homolog | **RM63, shipped 0.6**; its own overclaim (R2-14) corrected in the 0.6 dogfood round (`base.py:865-880`) | unchanged; 4.5 only reworded PSL's "allele" to "allele value" |
| 8d | Polyploid / partially phased GT | **RM67, not work**, parked in [ROADMAP_0_8.md](../ROADMAP_0_8.md) | unchanged; §1.4.4's new base-modification example `/3\|1/0\|4\|0/0/3/1` is one more live instance, not a change |
| 8e | `ID` is a `;`-list | **RM64, shipped 0.6** (docs) | unchanged |
| 10 | Repeat and CNV tables are positional | **RM65** 0.6 half shipped (the comment), coordinates open in [ROADMAP_0_8.md](../ROADMAP_0_8.md) | the quotation moved: §5.7 now says *"The POS and **SVLEN** of `<CNV:TR>` records should match the STR/VNTR reference catalog sizes"*. ROADMAP_0_8's RM65 entry quotes the old wording unqualified; `compiler.py:1357` quotes it as "VCF 4.4", which stays true. Whoever builds RM65 should key the interval on POS and SVLEN, since END is now derived |

**One correction to the 4.4 audit's framing, beyond §2.** Its §2 called `Number=P` "new in 4.4". It
was: P appears in 4.4 §1.6.2 (upstream issue #705 records the 4.4 commit that introduced it), and 4.5's
changes list lists it again because 4.5 finally defined it in §1.4.2. Nothing in the repo depends on
which release gets the credit; this note exists so nobody re-flags it.

---

## 1. The reference-block rule we print reads a multi-sample 4.5 file wrong, in the dangerous direction

**Severity: high where it applies (multi-sample files with per-sample blocks), nil on a single-sample
gVCF. A change in 4.5 reaching a shipped item (RM57's second half). Patch.**

### What the spec says

Three pieces, all new in 4.5:

- §5.5: reference blocks are now *"represent[ed] … in a single record using the `<*>` allele and the
  FORMAT LEN field"*, and gVCF's use of INFO END *"requires the reference block length to be the same
  for all samples"*, which is the stated reason for the change. Table 2 adds `LEN`, `1 Integer`,
  *"Length of `<*>` reference block"*.
- §1.6.1: END is *"Deprecated"* and, *"when present, must be set to the maximum end reference
  position"* over REF, SV SVLENs *"and the end positions calculated from FORMAT LEN"*. For backwards
  compatibility *"a missing FORMAT LEN field should be inferred from the INFO END tag if present"*.
- §5.5: *"Positions implicitly called by a preceding `<*>` for a sample must have GT set to the missing
  value (`.`) and have no FORMAT fields other than LAA present."*

### What we do

`VariantRow.callable_from`'s printed description (`spec.py:775-778`) and SCHEMAS.md (the *Reference
evidence is a block* paragraph at line 1001) both tell a consumer: *"Reference evidence usually arrives
as a gVCF block (one record with END=), so a consumer finds it by interval containment rather than an
equality join on position, and the block's floor is FORMAT/MIN_DP."* SCHEMAS.md quotes the 4.4 example
record `1 4370 . G <*> . . END=4383 GT:DP:GQ:MIN_DP:PL`.

### Why it breaks

Take a two-sample 4.5 record `1 100 . A <*> . . END=199 GT:MIN_DP:LEN 0/0:30:100 0/0:30:10`. Sample one
called 100..199 as reference; sample two called 100..109. END is 199 because it is the maximum. A
consumer following our sentence finds sample two's `0/0` block, sees `END=199` and a healthy
`MIN_DP=30`, and treats sample two as callable reference at 150. If sample two has no later record
covering 150, it was never called there. For a `requires_callable` row at 150, that consumer reports a
confident absence for a position nobody looked at. SCHEMAS.md names exactly this collapse as the one
that "runs in the dangerous direction", and here our own guidance produces it.

The upstream pull request #844 (open, not merged) states the same failure from the tooling side:
pre-4.5 readers *"will incorrectly interpret the size of the smaller … `<*>` symbolic alleles when END
is present"*, and it proposes that such files carry no END at all. That proposal would move the
failure rather than remove it: with END absent, a consumer reading extent from END sees a one-base
record and under-covers, which withholds safely but withholds nearly everything.

The `GT=.` rule is the second half. Where sample one has a variant at 150 inside sample two's block,
the record at 150 carries `.` for sample two and no other FORMAT field. Our contract says to tell a
covered reference call from a no-call before concluding, and a consumer applying it at that record sees
a no-call. That errs the safe way (a lost answer, not a wrong one), but it is still our text sending the
consumer to the wrong record.

### Why the obvious repairs are wrong

- **Point `callable_from` at `FORMAT/LEN`.** LEN says how far the evidence reaches, not what it is;
  `callable_from` names where the proof lives (`MIN_DP`, `GQ`, `FT`). Folding extent into the proof
  pointer puts two axes in one column (P5), and it would be the same answer on every row of every
  module, which is the mark of a reading rule rather than an annotation.
- **A companion column saying "read extent from LEN".** Full cost on `variants.csv` for a sentence that
  does not vary by row.
- **Keep END and add a footnote.** The rule has to change direction, not gain a caveat: LEN first, END
  only where LEN is absent (the spec's own fallback), and a `.` GT inside the sample's own earlier block
  is that block's call.

The repair is text: the `callable_from` description, the SCHEMAS.md paragraph and its quoted record,
and a sentence in the consumer contract about the 4.5 `GT=.` rule. No column, no validator. **Patch**
(no authored surface moves; P3 and P8 are not reached). P9: nothing priced, no addition.

---

## 2. RM57's QUAL inversion is a shipped false claim, and the GQ advice beside it is not grounded either

**Severity: medium. A false statement in a pinned warning phrase, a printed field description, a
normative doc and the scenario corpus. Not a 4.5 change: §1.6.1.6 is word for word the same in both
versions. The 4.4 audit's §5, first half, is refuted. Patch.**

### What the spec says, and the arithmetic

§1.6.1.6: *"QUAL — quality: Phred-scaled quality score for the assertion made in ALT. i.e. −10log10
prob(call in ALT is wrong). If ALT is `.` (no variant) then this is −10log10 prob(variant), and if ALT
is not `.` this is −10log10 prob(no variant)."*

On a monomorphic record (`ALT=.`), QUAL = 60 means −10·log10 P(variant) = 60, so **P(variant) = 10⁻⁶**.
The record is saying, with high confidence, that the position is reference. The formula changes form
with the record precisely so that QUAL keeps one meaning throughout: how sure the record is of what its
own ALT column asserts. An inclusive `min_quality` floor on QUAL therefore moves in the same direction
on a variant record and on a monomorphic one. **Nothing inverts.**

### What shipped on the misreading

The 4.4 audit's §5 read it the other way: *"a QUAL of 60 on a monomorphic/reference record means this
position is almost certainly variant."* RM57 built that sentence into:

- `compiler.py:1770`, `QUAL_INVERSION_PHRASE = "QUAL means the opposite thing on the record this row is
  read from"`, a phrase COMPILER.md lists as API (line 1648);
- the warning itself, code `quality_floor_inverted` (`compiler.py:1826-1830`): *"on the reference record
  a consumer must read to prove this absence, a HIGH QUAL says the position is probably variant"*;
- the `_check_quality_inversion` docstring (`compiler.py:1791`);
- `VariantRow.quality_from`'s printed description (`spec.py:799-811`): *"a high QUAL says the position
  is probably variant and the floor demands the opposite of what the row is about"*;
- SCHEMAS.md line 989, *"the same 60 on a monomorphic reference record means the position is almost
  certainly variant"*;
- `features/compiler/spec_and_tables.feature:163`, the `@code:quality_floor_inverted` scenario's
  comment, word for word;
- `compiler/tests/test_vcf_conformance_warnings.py`, which pins the phrase and the firing condition.

### What is actually true on each record a `requires_callable` row meets

1. **A monomorphic record, `ALT=.`.** QUAL is confidence in the reference call, and a floor against it
   does what the author meant. The shipped text is false here.
2. **A gVCF `<*>` block.** ALT is `<*>`, not `.`, so by the letter QUAL would be −10·log10 P(no
   variant), confidence that some non-reference allele is present. But the spec's own block records
   write `.` in QUAL (§5.5's example, in both versions), so in practice the floor meets a missing value
   and **cannot run**. Under the contract's existing rule an unevaluable floor withholds, so a
   `requires_callable` row with a QUAL floor withholds on every block. That is a real consequence worth
   telling an author about, and it is not an inversion.
3. **A joint-called site record where this sample is `0/0`.** QUAL is the site's confidence that the
   ALT exists in *someone*, and says nothing about this sample. This is the RM53 shape one column over,
   a site-level quantity read as a per-sample one. The shipped text does not mention it.

### The advice is not grounded either

The warning and the description both steer the author to `GQ`. Table 2 and §1.6.2 define GQ as
*"Conditional genotype quality, encoded as a phred quality −10log10 p(genotype call is wrong,
**conditioned on the site's being variant**)"*. Conditioned on the site being variant is not a
confidence in a reference call, so the spec's definition does not support GQ as the floor for a row
whose informative call is absence. Callers write GQ on reference blocks anyway (§5.5's own example
carries `GQ=60` on a `0/0` `<*>` block), so it is a convention with the spec's example behind it and
the spec's definition against it. `MIN_DP`, the other suggestion, is a depth, not a quality; it belongs
to `callable_from` (§1), not to `min_quality`.

What an honest replacement says is therefore a design question, not a rewording, and this audit does
not settle it. The facts it has to be built from are the three shapes above plus GQ's conditioning.

### Why the obvious repairs are wrong

- **Keep the warning and fix only the prose around the phrase.** The phrase is the part a consumer
  greps, and it is the part that is false. Rewording or retiring `QUAL_INVERSION_PHRASE` is the real
  cost of this item. The tests read the constant, so they follow it, and COMPILER.md records a named
  external consumer only for `UNJOINABLE_PHRASE`, not for this one. A pinned phrase still changes
  deliberately and says so in the CHANGELOG.
- **Rename the code.** `quality_floor_inverted` is a permanent key
  (`@warning-code-names-the-finding`). Whether the finding it names survives in some true form (shape
  2's "this floor cannot run on a block" is the likeliest) or retires is the item's decision; the key is
  not reused for a different finding either way.
- **Swap GQ for another field in the advice.** Nothing in Table 2 is a per-sample reference-call
  confidence by definition. Naming one would repeat this section's mistake with a different field.

**Patch** by class: message text, a printed description, docs and a scenario comment; no schema
reached, P3 and P8 untouched. If the finding retires, a warning code leaving the emitted set is worth
checking against the closed-vocabulary reasoning RM275 used for adding one. P9: nothing added.
`docs/proposals/PROPOSAL_0_6.md` and the 4.4 audit are closed records and keep the old reasoning; this
section is the correction's evidence. Filed on 2026-09-30 as **RM313** ([index](../RM_TOC_300_399.md)) and
taken into 0.8's PT1 round, which retires the code and adds a true replacement finding.

---

## 3. The reserved-key transcription misses keys the spec reserves, one of them the schema's own repeat field

**Severity: medium. The cardinality warning is silent on the flagship repeat field; one collision is
unreported. Present since 4.4, widened by 4.5. RM54/RM53 are shipped, so this would be a new item.
Patch.**

### What the code claims

`vocab.VCF_FIELD_NUMBER` (`vocab.py:145-149`) says it carries `Number` *"from the reserved-key tables
(VCF 4.4 §1.6.1.8 Table 1 for INFO, §1.6.2 Table 2 for FORMAT, plus the structural/copy-number keys of
§5.6)"*, and COMPILER.md and SCHEMAS.md both describe it as a transcription of the spec's reserved-key
tables "and nothing else". The declared blind spot is a *caller's* private key (`REPCN`), which is
correct and not at issue.

### What it actually holds

Extracting both versions' tables and header lines and comparing them with the dict (script under
`data/interim/vcf45/tables.py`, not committed):

- **§3's reserved INFO keys are absent**, and §3 opens *"The following INFO keys are reserved"*. That
  includes `RUC` (`Number=.`), `RN` (`A`), `RUS`, `RUL`, `RB`, `RUB`, `CIRUC`, `CIRB` (all `.`),
  `SVLEN` (`A`), `CIPOS`, `CIEND`, `CILEN`, `CICN` (`.`), `SVCLAIM`, `EVENT` and the ID keys.
- **§4's FORMAT keys are partly present**: `CN`, `CNQ`, `CNL`, `CNP` are there; `CICN` (`2`), `NQ`,
  `HAP`, `AHAP` are not.
- **Table 2's `PP` (`G`) is missing** in both versions.
- **Every 4.5 addition is missing**: `LEN` (`1`), `LAA` and `LA` (`.`), `LAD`/`LADF`/`LADR` (`LR`),
  `LEC` (`LA`), `LGL`/`LGP`/`LPL`/`LPP` (`LG`), and the base-modification family (`M`).

No entry that *is* present disagrees with 4.5.

### Why it matters

`binning._VCF_MEASURE_FIELDS` (`binning.py:214`) names `RUC` as *the* field a consumer reads a
`repeat_count` measurement from. `RUC` is `Number=.`: a flattened list across every ALT allele's repeat
sequences, whose inner lengths are given by `RN`. That is the worst multi-valued case the 4.4 audit
described. Probed end to end, on a copy of `reference_examples/htt_repeat_expansion` with
`source_element` emptied:

```
source_field=INFO/RUC   -> no VCF-pointer warning at all
source_field=FORMAT/AD  -> vcf_pointer_unselected_element (5 rows, Number=R)
```

So the element-rule warning fires on a field nobody puts in a repeat table and stays silent on the one
the schema itself tells authors to use. The shipped examples dodge it by pointing at `FORMAT/REPCN` with
`source_element=largest`, which is why nothing has noticed.

`CICN` is the same gap on the collision side. INFO `CICN` is `Number=.` Float (§3) and FORMAT `CICN` is
`Number=2` Float (§4): reserved in both namespaces, with different cardinality, exactly like `CN`.
`VCF_COLLIDING_KEYS` (`vocab.py:115`) omits it, so a bare `CICN` earns neither the collision warning nor
a cardinality answer. No module points at `CICN` today; RM56's policy half is where one would.

### The shape of the repair, and two traps in it

Transcribe the missing reserved keys, add `CICN` to `VCF_COLLIDING_KEYS` with its reason, and fix the
comment that claims §5.6 is where the structural keys live (they are §3 and §4). Two constraints for
whoever does it:

- `VCF_COLLISION_REASONS` is asserted total over `VCF_COLLIDING_KEYS`, so `CICN` needs its sentence in
  the same change.
- `VCF_NUMBER_MEANINGS` (`vocab.py:199`) is read through `.get(number, "a value list")` in the warning.
  Adding `LA`/`LR`/`LG`/`M` entries to `VCF_FIELD_NUMBER` without meanings for those codes would print
  the default silently (`@lookup-with-a-default-hides-a-new-member`). Add the meanings, and assert
  equality between the codes the table uses and the codes the meanings cover.

The `M[0-9]+[ACGTUN]` family is a pattern, not a key set. A dict can carry its ten named aliases; the
ChEBI-numbered form stays unknown and withholds, which is the house rule working as intended rather than
a gap.

### Why the obvious repair is wrong

**Declare it a blind spot and move on.** The declared blind spot is caller-private keys, and it is
honest because the tier has no right to assert their cardinality. `RUC` is not caller-private; it is in
the spec's reserved list, and this repo names it as the canonical source of a measure kind. Declaring it
unknown would be the tier refusing to read a table it claims to transcribe.

**Patch.** No authored surface; an existing warning code fires on more pointers and an existing
collision code gains a member. By the RM275 precedent a *new* code would size as a minor, and none is
needed. P9: nothing added to any layer.

---

## 4. The version the transcription is pinned to is not stated anywhere a consumer reads

**Severity: low. A documentation gap that §3's repair should close in passing. Patch.**

`vocab.py:108-110` says the constants are *"transcribed from the VCFv4.4 specification's own
reserved-key tables and are fixed for that spec version"*. That is a sound design (a spec-derived fact,
not a source convention), but a consumer meets 4.5 files now, and nothing in SCHEMAS.md or COMPILER.md
says which version the collision set and the cardinality table describe, or what happens with a 4.5-only
key (it is unknown and withholds). Once §3 is done the answer is "4.5, and a key added after it
withholds", and it belongs next to the existing *What the compiler declines to say* paragraph. Patch,
docs only.

The version-qualified citations elsewhere in the code (`"VCF 4.4 §7.2"`, and the pinned
`FRACTIONAL_MEASURE_PHRASE = "is not a whole number in VCF 4.4"` at `binning.py:234`) stay true under
4.5 and should **not** be rewritten: CN and RUC are still Float, and the phrase is API.

---

## 5. An element rule stated by ALT index lands on the wrong value of a local-allele field

**Severity: low today (no module points at an `A`/`R`/`G` FORMAT field with `annotated_alt`), medium
for the first one that does. New in 4.5. Consumer contract, patch.**

### What the spec says

§1.6.2: `LAA` is *"the 1-based index into ALT, defining the alleles that are actually in-play for that
sample and the order in which they are interpreted"*, and every spec-defined `A`, `R` and `G` FORMAT
field *"ha[s] a local-allele equivalent that should be interpreted in the same manner as it's matching
field except for the ALT alleles considered present and the order in which they are interpreted"*. The
worked example: REF `G`, ALT `A,C,T,<*>`, `LAA=2,4`, so `LAD=20,30,10` is REF, C, `<*>`, and `AD` is
absent. A field and its local equivalent *"must encode identical information or one must [be] ignored
by containing the MISSING value or omitted"*, and the spec *"recommend[s] that VCF libraries provide an
API in which local allele encoding can be abstracted away"*.

### What we do

`ELEMENT_RULE_MEANINGS["annotated_alt"]` (`vocab.py:277`) defines the element as *"at its index in the
record's ALT list, which is element index+1 on a Number=R field"*. On `LAD` that index is wrong: the ALT
`C` is ALT index 2, and it sits at `LAD` element 1. The `_alt`-suffixed ranging rules survive (element
zero is still REF on an `LR` field), and so do `largest`, `smallest` and `sum` in value terms, but the
one rule that names an allele names the wrong one.

The realistic failure is one step removed. A module writes `source_field=FORMAT/AD`, which is correct.
The consumer's merged 4.5 file carries only `LAD`, because shrinking multi-sample files is what local
alleles are for. A consumer that falls back to `LAD` and applies our sentence reads the wrong allele's
depth, well-formed and wrong. One that does not fall back finds `AD` missing and withholds, which is
safe.

### Why the obvious repairs are wrong

- **A `local_annotated_alt` rule.** It makes the module describe how a consumer's file was merged,
  which is the consumer's business (P2), and every existing row would need a twin.
- **Reject `FORMAT/L*` pointers.** Refuses a spec-reserved key for no gain; the pointer is legal, only
  the reading needs a rule.

The repair is one sentence in the consumer contract and in `annotated_alt`'s meaning: resolve a
local-allele field to its global equivalent through `LAA` before applying any element rule, as §1.6.2
itself recommends. **Patch** (printed text and docs). P9: nothing added.

---

## 6. A base-modification fraction has a pointer and no measure kind

**Severity: low. No module needs it. New in 4.5. Idea-book material; a minor if it is ever built.**

§1.6.2 adds `M5mC`, `M5hmC`, `M6mA` and the rest: *"Fraction of DNA or RNA bases modified"*, a Float in
`[0, 1]`, `Number=M`, one value per modifiable base per allele in GT order, strand-specific, with
unstranded CpG values stored at the C and the G left missing. A block's modification value applies to
every base the block covers.

The pointer grammar accepts `FORMAT/M5mC` (probed), and the cardinality lookup answers unknown, so an
author gets no false warning. What is missing is a home. `VALID_MEASURE_KINDS` has five members
(`binning.py:157`), and the only fraction among them is `allele_fraction`. Binning a methylation level
under `allele_fraction` would put two quantities under one kind name, which P5 forbids. And none of the
eight element rules selects "the value at this base on this strand", which is what `Number=M` needs.

The use case is real in the abstract. Methylation of an expanded FMR1 CGG tract is part of what separates
a full mutation from a mosaic one, and `reference_examples/fmr1_cgg_repeat` is in the corpus. But no
module or consumer report asks for it, and `docs/probes/CLAWBIO_SURVEY.md`'s `methylation` is an
epigenetic clock, a different thing. This follows the repo's own rule for RM65 and RM66: design it
against a real file, not against the spec's examples.

**Legality if built: minor.** A new `measure_kind` member is an additive vocabulary member (P3, P6), and
a per-base selection rule would be a new `VALID_ELEMENT_RULES` member, also additive. P9: no new column;
the cost is two vocabulary members an author learns, which is cheap as authored-layer additions go but
is a one-way door under P5, so the names deserve the audit P5 asks for before they land.

---

## 7. Checked, and *not* a finding

Recorded so these are not re-probed.

- **No new INFO/FORMAT collision in 4.5.** Computed from both versions' tables, not read off prose: the
  colliding set is identical. (`CICN` is §3's point, and it predates 4.5.)
- **`<NON_REF>` as an alias of `<*>`.** Both classify identically already: `non_nucleotide_reason`
  answers `"notation"` and `symbolic_allele_defect` answers `"unknown_type"` for each (probed). The
  `unknown_type` message names `<*>` and not `<NON_REF>`; adding the alias to that sentence is a
  one-line courtesy, not a defect. As `alts` cells they mint two different `variant_key` strings
  (`1:100:A:<*>` and `1:100:A:<NON_REF>`), the RM58 shape, but either token in an allele column is an
  `unknown_type` symbolic finding: on `variants.csv` the row is dropped with a warning, or refused under
  `strict`, and on the composite tables it is fatal in both modes. Neither key reaches an artifact as a
  claim.
- **GT grammar.** Unchanged in 4.5. The base-modification example `/3|1/0|4|0/0/3/1` is a
  locally-octoploid call, which is RM67's documented divergence and not a new one.
- **Key grammar.** Unchanged. `M5mC`, `MXaoN`, `LAD`, `LPL` all match `SOURCE_FIELD_PATTERN`. The spec
  itself spells one alias `MXaoN` in Table 2 and `MxaoN` in the prose; keys are case-sensitive, the
  pointer grammar preserves case, and matching the file's spelling is the author's job as it is for any
  key.
- **Missing values and lists.** §1.6.2's list-of-missing rule is unchanged. The one new missing-value
  rule is the implicit-call `GT=.`, which is §1.
- **`CN`, `RUC`, `CIRUC`, `<CNV:TR>`.** Unchanged apart from the examples dropping `END=`. RM55's and
  RM56's evidence stands as written.
- **QUAL's definition.** Unchanged. Upstream PR #579 rewords "Phred-scaled" throughout and does not
  touch QUAL's direction. §2 is a correction to our reading, not to the spec.
- **`LGL`/`LGP` retyped to Float** (`e821e4f`). No touchpoint here.
- **BCF `rlen`, the mandatory header line.** No touchpoint here.
- **`alts="."` still keys as `1:100:A:.`.** RM58 decided a diagnosis, not a grammar, and the diagnosis
  ships. Not a regression.

---

## 8. What could not be verified

- **Whether GT itself may be local.** §1.6.2 says one *"can choose to specify the genotype, allele depth
  and the genotype likelihood against a subset of Local Alleles"*, and Table 2 keeps `LA` as
  *"Reserved"*. The spec's own worked example contradicts itself on this: the first pair of records is
  meant to *"encode the same information"* but gives `GT=2/4` beside `LAA=2,4` in one and `GT=2/2` in
  the other, while `LPL`'s zero sits on C/C. The other three pairs agree and read GT as global indices.
  This audit assumes GT stays global, which is what three of four examples and every mainstream reader
  do. If a later errata makes GT local, the consumer's genotype match (the fourth pointer the 4.4 audit
  named) would need the same `LAA` translation as §5. No upstream issue on this example was found;
  #793 (closed) was a layout bug in the same example, and #871 (open, 2026-09-11) reports index errors
  in the PSO example, a different one.
- **What real 4.5 writers do with END.** The spec says END is optional and, when written, a maximum.
  PR #844 proposes omitting it from any file where it would mislead. No real multi-sample 4.5 file with
  per-sample `LEN` was available to check which behaviour callers ship, so §1's severity is stated for
  the file the spec permits, not for a measured one.
- **The gVCF example's `;14`.** 4.5's §5.5 example writes `…:0,60,900;14`, a semicolon where the FORMAT
  separator is a colon. PR #853 (open) fixes it. It does not change what the example means, and nothing
  here quotes it.

---

## Summary: candidate items, with the legality that sizes them

| # | Finding | Class | Legality |
|---|---|---|---|
| 1 | Reference-block containment on END credits one sample's block to another's positions in a multi-sample 4.5 file; `GT=.` inside a block is not a no-call | confident wrong absence, in the dangerous direction | docs + printed description, **patch**; reopens RM57's second half |
| 2 | `quality_floor_inverted` says QUAL inverts on a monomorphic record; it does not (P(variant) = 10⁻⁶ at QUAL 60), and nothing inverts anywhere. The GQ advice is not grounded (GQ is conditioned on the site being variant) | shipped false claim in a pinned warning phrase, `quality_from`'s description, SCHEMAS, COMPILER, `features/` | message + docs, **patch**; the pinned phrase changes deliberately; the replacement advice is a design question. Filed as **RM313**, taken into 0.8 |
| 3 | `VCF_FIELD_NUMBER` misses §3/§4 reserved keys (incl. `RUC`, the schema's own repeat field), Table 2's `PP`, and all 4.5 keys; `CICN` collides and is not in `VCF_COLLIDING_KEYS` | cardinality warning blind on the flagship repeat field | constants + reasons + meanings, **patch**; no new code |
| 4 | No consumer-facing statement of which VCF version the transcription describes | documentation gap | docs, **patch**, with #3 |
| 5 | `annotated_alt` is defined by ALT index; 4.5 local-allele fields index through `LAA` | silent wrong element for a consumer that falls back to `LAD` | consumer contract + printed meaning, **patch** |
| 6 | Base-modification fractions (`Number=M`) have a pointer and no measure kind or element rule | unexpressible, no demand | idea-book; if built, **minor** (two vocabulary members, no column) |

Nothing here needs a major, and nothing here changes a published module's `content_signature`. The two
that most want deciding together are **#1 and #2**: both come out of RM57, and both correct guidance a
consumer or author is told to follow at the one join where a wrong answer means "screened negative" for
a position nobody screened. #1 is text; #2 is text plus a decision about what, if anything, the warning
should say instead. **#3 and #4** are one change to one file.
