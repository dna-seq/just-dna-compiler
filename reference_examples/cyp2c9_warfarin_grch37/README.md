# `cyp2c9_warfarin_grch37` — two positional tables, no `variants.csv`, and a build the tier does not resolve

**What this probes:** *the 0.6 positional-resolution round (RM43) on every axis where the corpus was
uniform.* Until this module, RM43's fill had exactly one instantiation —
`pgx_slco1b1_simvastatin`: nine rows, one positional kind, GRCh38, rsID-only. This module differs on
all four at once: **two** positional kinds together (`haplotypes.csv` + `pharm_variants.csv`),
coordinate-authored rows beside rsID-only ones, an injected resolution table nobody enriched, and
`genome_build: GRCh37`, which is the branch where the fill does not run at all.

It is also a real module. CYP2C9 \*2/\*3 with CPIC's function and phenotype calls, plus the
warfarin pharmacogenes ClinPGx grades at 1A/1B — VKORC1 `rs9923231`, CYP4F2 `rs2108622`, and
`rs12777823`, the African-ancestry dosing locus. Drafted with the shipped CLIs; nothing here was
typed from memory.

## Where the coordinates came from

`hint variant` answers on GRCh38 only, and that is a decision rather than a gap — `hint recover`
says so in its own output: *"author that rs-number instead of the coordinate: it names the variant
without naming a build … a converted position is its own only witness."* So every GRCh37 number
below was **verified through the tool**, in the direction the tool offers:

```
just-dna-enricher hint recover --chrom 10 --start 96702047 --ref C --alts T   # → rs1799853  (*2)
just-dna-enricher hint recover --chrom 10 --start 96741053 --ref A --alts C   # → rs1057910  (*3)
just-dna-enricher hint recover --chrom 16 --start 31107689 --ref C --alts T   # → rs9923231
just-dna-enricher hint recover --chrom 19 --start 15990431 --ref C --alts T   # → rs2108622
just-dna-enricher hint recover --chrom 10 --start 96405502 --ref G --alts A   # → rs12777823
```

`resolution.csv`'s three coordinate rows are `source=manual` for that reason: they are the
inject-only escape hatch, hand-recorded and tool-confirmed, which is the only way a GRCh37 module
can carry a resolution table at all.

## What it broke

### 1 — every drafting provider ignores the module's declared build

`just-dna-enricher draft --gene CYP2C9` into this directory, whose `module_spec.yaml` says
`genome_build: GRCh37`, wrote

```
*2,rs1799853,10,94942290,T,CYP2C9      ← GRCh38. The GRCh37 position is 96702047.
```

with no warning of any kind. CPIC serves GRCh38 (`allele_definitions.parquet`, probed), ClinVar's
snapshot is GRCh38, ClinPGx's is GRCh38 — and `draft`, `draft-panel` and `draft-clinpgx` all take a
`spec_dir`, all read `module_spec.yaml`'s sibling tables, and **none of them reads the build the
yaml declares.**

The blast radius is two of the three, and the difference is worth stating precisely: `pgx_draft`
writes `chrom=`/`start=` from CPIC, and `clinvar_draft` writes the full coordinate for any record
with no rsID — so both put GRCh38 positions into a module of any declared build. `clinpgx_draft`
writes no coordinate columns at all, so it reads the build for no reason and can do no harm by
not reading it. All three share the omission; only two can produce a wrong row.

The function that answers the question already exists and is exactly right:
`enrich.spec_genome_build`, written for the bug one release earlier where *"the guard existed; the
value never arrived."* It has **one caller** — `enrich()`. This is the same defect, in the three
commands an author reaches for *before* enrich.

It hid for the same reason its ancestors did. `enricher/tests/test_pgx_draft.py` writes
`genome_build: GRCh38` into its fixture — the only drafting test that mentions a build at all
declares the default, so it cannot tell "reads the module's build" from "writes GRCh38".

### 2 — the attestation records a check it could not run as having run clean

`enrich` on a GRCh37 module says the right thing loudly:

> Enrichment is GRCh38-bound; the module declares genome_build='GRCh37', so no lookup runs …

and then writes a `verification.json` (RM45) saying this:

```
reference_allele        | subjects 0 | findings 0 | skipped null
genome_build_agreement  | subjects 0 | findings 0 | skipped nothing_to_check
                        | "no authored ref disagreed with the reference, so no row needed a build diagnosis"
```

Neither line is true. `verify_reference_alleles` reaches
`refget_accession(row.chrom, row.genome_build)`, catches `UnsupportedBuildError` and `continue`s —
a bare skip indistinguishable from "this row had no coordinate" — so `RefCheck.not_checked` stays
`None` and the check reports as having *run*, over zero subjects. The build-agreement record then
takes the `else` branch and publishes a sentence asserting a comparison that never happened.

The record-assembly code anticipates this exact contradiction and guards two of the three ways the
subject list can be empty:

> `no_ref_mismatches` alone does not mean the refs agreed … Reading it as the first would publish
> "no authored ref disagreed with the reference" beside a `reference_allele` record saying nothing
> was compared: one document contradicting itself.

The third way — *the check ran and had no subjects, because every row is on an assembly this tier
has no table for* — is the one that was missed. And `VALID_VERIFICATION_SKIPS` already has the
member for it, with the case spelled out in its own comment:

```python
"unsupported",  # this tier cannot put the question for these rows (e.g. an unbuilt assembly)
```

**Nothing in the workspace emits `unsupported`, and no test asserts it.** Reproduced on the existing
corpus module, which is the sharper demonstration since that one carries real `ref` values:

```bash
cp -r reference_examples/grch37_build /tmp/g37 && just-dna-enricher enrich /tmp/g37
cat /tmp/g37/verification.json      # reference_allele: subjects 0, skipped null
```

The tier knows how to say this — the VRS coverage warning in the very same run reads *"no refget
table for build 'GRCh37'; VRS minting is GRCh38-only today (RM15)"*. Only the attestation does not.

### 3 — `clinpgx_draft` says the snapshot has no `gene` column, and it has one

```
--gene was given but the ClinPGx annotation snapshot carries no gene column; the filter was not applied.
```

`annotations.parquet` has a `gene` column, populated on **15,331 of 16,087 rows** — and
`clinpgx_build.py` both writes it (line 186) and reads it back (line 212) to build the snapshot's
own gene list. So `--gene` is refused for a stated reason that is false about our own file, and
`PharmVariantRow.gene` is left empty on every drafted row although the source states it. The `gene`
cells in this module's `pharm_variants.csv` were filled by hand from the same parquet the drafter
read.

This is the *"probe the table, not the source"* shape, with the aggravation that the table is one we
built.

### 4 — `annotation_text` is written for every row and read by nothing

The same parquet carries `annotation_text` on **16,087 of 16,087 rows** — a per-genotype prose
statement, which is what `conclusion` is for. `clinpgx_draft` discards it and synthesizes

```
ClinPGx 655385012: C/C and warfarin — dosage
```

a restatement of the row's own key, under a comment calling it *"a transcription of the published
parts"*. The published part is the sentence. Grep confirms `annotation_text` is referenced twice in
the workspace, both in the builder that writes it.

Every `conclusion` in this module was written by hand against that column, because a module whose
conclusions restate their keys says nothing to a consumer, and nothing in the pipeline flags it.

### 5 — the joinability warning recommends a re-run that cannot help

Before the three `manual` rows were injected, compile said:

> `pharm_variants.csv: 12 of 12 row(s) have no chrom+start … no resolution.csv row places them —
> run `just-dna-enricher enrich` first.`

directly **below** the line explaining that the fill is skipped because the module is GRCh37. Enrich
had already been run, and on this build it can never place those rows.

`_check_positional_joinability` has the right branch — `fill_applied=False` yields *"was not
consulted for this table — see the skip reported above"* — but it is tested **after** `if not
placeable`, and on a non-GRCh38 module the table is empty for exactly those keys, because enrich
declines to resolve them. So on the modules where "the fill never ran" is the entire story, the
branch that says so is the one the author cannot reach. It fires here only because this module
injects a hand-built table:

> resolution.csv names 12 of them and was not consulted for this table — see the skip reported above.

### 6 — the corpus round-trip sweep never compared `resolution_signature`

This module was supposed to fail `test_reference_examples_roundtrip.py`. It passed, and the reason is
worth more than the finding it was hiding:

```python
getattr(manifest, "resolution_signature", None)
```

`resolution_signature` lives on `manifest.compilation`, beside `resolution_mode` and
`fully_resolved`. The manifest root has no such attribute, so that expression returned `None` — on
both sides of every comparison, for all eleven examples, for the whole of 0.6. The test's own
docstring devotes a bullet to why this signature is checked separately from the other two ("hashed by
fact rather than by byte, so a reverse-emitted table with different provenance still hashes equal"),
and nothing had ever compared one. A defaulted `getattr` on a name that does not exist is
indistinguishable from a name whose value is legitimately `None` — which is exactly the case this
sweep has to be able to see, since a module carrying no `resolution.csv` has no signature.

Making the comparison then showed the corpus holds three shapes, not one:

| | lap 1 → lap 2 | lap 2 → lap 3 |
|---|---|---|
| nine examples | unchanged | unchanged |
| `grch37_build`, `mt_heteroplasmy` | `None` → a value | stable |
| `cyp2c9_warfarin_grch37` | `c6fd3238…` → `a0558501…` | stable |

The middle row is materialization, not loss: neither module carries a `resolution.csv`, reverse
always writes one from the parquets, and the spec it produces states facts the authored one left
implicit. `grch37_build`'s own README claims the round trip is "a fixed point on `artifact.digest`,
`content_signature` **and** `resolution_signature`" — written under a test that could not check the
third.

The bottom row is this module, and the loss is forced rather than fixable: the fill is skipped on
GRCh37, so the `pharm_variants.csv` coordinates never reach a parquet, so reverse has nothing to
rebuild the injected rows from. Materializing them anyway would mean joining a table across builds,
which is the thing the skip exists to refuse. The sweep now asserts lap-2 stability universally and
a non-null lap-1 signature only on the default build — an exemption **derived from the declared
build**, not a list of module names.

### 7 — a "no snapshot" test that only fails on a machine that has one

Running the suite after `just-dna-enricher cache pull` reddened
`test_no_snapshot_records_the_skip_rather_than_a_clean_pass`, which neutralized its cache with

```python
monkeypatch.setenv("JUST_DNA_CLINPGX_CACHE", "")
```

citing the suite's credential rule. **The idiom is inverted for a cache path.** For a credential,
empty means absent — every reader is `key or os.environ.get(...)`. For a cache the ladder is
`explicit → $env_var → the default dir` and `os.getenv` returning `""` is falsy, so an empty value
does not mean "no snapshot", it means *fall through to `~/.cache/just-dna-pipelines/clinpgx`* —
exactly where `cache pull` puts one. So the test passed on CI and failed on any machine that had
followed the provisioning instructions, which is the same wrong way round as the `PHARMVAR_API_KEY`
case. `offline=True` is not the lever either, and correctly so: reading a local parquet is not egress
(RM38). It points at an empty directory now.

### 8 — `--drug` cannot tell a typo from a real drug CPIC scores differently

```
warning: CYP2C9: CPIC has no recommendations for 'warfarin' — nothing drafted.
warning: CYP2C9: CPIC has no recommendations for 'notarealdrugxyz' — nothing drafted.
```

Byte-identical. CPIC's live `drug` lookup returns empty for an unknown name and the code returns
`[]` for both cases, so the message asserts an absence about CPIC that it did not establish. This is
the `absent`-rsID distinction the workspace already makes carefully one command over — *typo, or a
real thing the source records differently* — and the answer matters here: CPIC's warfarin guideline
is real, it is simply not a phenotype-keyed recommendation, which is why this module carries the
star alleles and ClinPGx's variant annotations rather than a CPIC recommendation row.

## What was probed and held

- **The `licensing.csv` spelling.** Both drafting providers wrote the preferred name into a fresh
  directory (RM51). The compile gate refuses with `declared_use` blanked, naming both sources:
  *"['clinpgx', 'cpic'] contribute annotation-layer content under terms that forbid sale"* (RM27).
- **RM5's two unusable-allele kinds stayed apart** after the grammar widened. CPIC's `*36=S` is
  reported as an IUPAC ambiguity — permanent — and `*6=DELA` as a grammar gap, with the message
  saying in-line that RM5's `<DEL:1500>` *"is a different spelling from CPIC's `DELTCT`"*. Nothing
  moved into the wrong bucket.
- **RM44's denominator does its job.** This module is `fully_resolved: true` over **zero** variant
  rows. `resolution_subjects: 0` is published beside it, so the documented trust rule
  `resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)` correctly withholds
  the badge that the flag alone would grant.
- **The count rule (0.6) holds here.** The joinability warning embeds a count and is emitted once
  per command, in `validate` and in `compile` alike — not once on each side of resolution.
- **The `"keyed by coordinate instead"` warning is `VariantRow`-only, and that is survivable.** A
  table-only module never constructs one, so it never hears that sentence; what it hears instead is
  the fill-skip warning at compile and, once its resolution rows carry `alts`, the VRS-coverage
  reason *"no refget table for build 'GRCh37'"*. The author is told; they are told somewhere else.

## The sibling probe — RM48's real reach, measured on two rows

Same module, `genome_build` flipped to `GRCh38`, coordinates left on GRCh37, plus a two-row
`variants.csv` so the reference-allele check has subjects. That is RM48's scenario verbatim, and it
resolved to **one caught, one not**:

```
Old-assembly coordinate — 1 row(s) — the authored ref is the GRCh37 base AND GRCh37 dbSNP records a
variant starting there — the strongest of the three, and the one that names the rs-number to author
instead (10:96702047 → rs1799853). 1 of these were also read as a ±1 coordinate shift, and this
supersedes that …
```

RM48 works exactly as designed on `rs1799853`: the ±1 shift reading fired, the old-assembly reading
fired, and the ordering rule suppressed the weaker one and named the rs-number. The other row is the
honest limit. `rs1057910`'s GRCh37 position is `10:96741053`, and GRCh38 carries an `A` there too —
so the authored `ref` matched, the row never entered the mismatch set, and nothing was diagnosed.
It went further than "not diagnosed": it was minted a content-addressed identity and recorded as
settled.

```
ga4gh:VA.pgprki8YgzfOSV9Dpe1ccPX4uNdlyAvB,,10,96741053,A,C,GRCh38,0,…,authored,,resolved
```

A VRS allele id is a correct digest of the wrong input — the same sentence the 0-vs-1-based
docstring incident earned. The diagnosis is gated on a ref mismatch and a matching neighbour base is
a one-in-four event, so both docs already say sensitivity is structurally partial; what this module
records is what partial looks like on a real pair of variants 1.76 Mb apart. **"The compiler catches
wrong-build coordinates" is not a reading anyone should take** — offline, nothing fires at all, and
online it fires for the rows whose ref happens to disagree.

## The round trip, measured

```bash
just-dna-compiler compile reference_examples/cyp2c9_warfarin_grch37 out/d2
just-dna-compiler reverse out/d2 out/d2_rev
just-dna-compiler compile out/d2_rev out/d2_again
```

| | `artifact.digest` | `content_signature` | `resolution_signature` | `manifest.verification` |
|---|---|---|---|---|
| compile | `d7a4f37e…` | `989e8298…` | `c6fd3238…` | present |
| recompile | `d7a4f37e…` | `989e8298…` | **`a0558501…`** | **absent** |

The authored identity is a fixed point. Two things are not, and both are consequences of the RM15
skip rather than of reverse:

**The injected resolution rows do not survive.** The fill never ran, so the `pharm_variants.csv`
coordinates never reached a parquet, so `reverse` — which rebuilds the table from the positional
parquets — has nothing to rebuild them from. The three `manual` rows are simply gone, and
`resolution_signature` returns to its pre-injection value. The GRCh38 control is a clean fixed point
on all three signatures (`pgx_slco1b1_simvastatin`, `271a0d3f…` before and after), so this is
build-specific, not general.

**`manifest.verification` is dropped in silence.** `reverse` cannot re-attest — an attestation is a
record of checks that were put, and fabricating one would be far worse than losing it — but nothing
says the block is being dropped, and `manifest.compilation.warnings` is a surface consumers parse
(RM44). The two compiles' warning lists differ for the same reason: the round-tripped module reports
*"no resolution.csv row places them"* where the original reported *"was not consulted for this
table"*.

## Reproducing

```bash
just-dna-compiler validate reference_examples/cyp2c9_warfarin_grch37 --strict
just-dna-compiler compile  reference_examples/cyp2c9_warfarin_grch37 out/d2 --strict
```

Green under `--strict`, with four warnings, none of which an authored edit could clear: VRS coverage
is 0/5 on a build with no refget table, the positional fill is skipped for the same reason, and
`pharm_variants.csv` joins by rsID only because the fill that would place it did not run. That is
the `not_covered` class — `strict` means *reproducible artifact*, and this module reproduces exactly.
