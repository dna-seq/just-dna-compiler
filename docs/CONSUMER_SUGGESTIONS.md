# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S41

**Claim ids from here, never from what this file shows.** S1–S37 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

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

## S39 — a library call loads the caller's `.env` into `os.environ`, and it silently un-did a consumer's test isolation

**Status — accepted, and it split in two: a bug we had not seen, fixed in the tree; the default you
asked about, filed as [RM102](ROADMAP.md#rm102--the-enricher-loads-a-env-into-osenviron-from-library-paths-and-only-half-of-that-has-an-off-switch).**

**The bug is the one you did not report.** Probing your report found that `load_dotenv_file=False` —
the parameter you correctly identified as the machinery already being there — **did nothing at all**,
in all six resolvers. Each passes its `default_*_cache_dir()` as an *argument*, and that helper went
through a `_cache_dir` whose `load_env()` was unconditional, so the file was loaded before the resolver
had looked at its own flag. Reproduced with a marker variable in a `.env` and a controlled cwd:
`resolve_cpic_reference(load_dotenv_file=False)` left `PROBE_SECRET_TOKEN=leaked_from_dotenv` in
`os.environ`, and so did the ensembl and clinvar resolvers. The flag is now threaded through
`_cache_dir` and the six `default_*_cache_dir` helpers rather than the load being removed — the
unconditional load is itself a repair (three "the cache is right there" reports in 0.5.2), and the
`True` path is unchanged. `test_locations.py` runs each resolver in a subprocess and pins both
directions plus the pre-fix arrangement, and a twelfth test walks both families asserting each takes
the parameter, so a seventh snapshot cannot quietly reopen it. **In the tree, not cut** — the version
carrying it will be `0.6.3`; check CHANGELOG.md before pinning.

**It does not fix what you actually hit, and that is worth being plain about.** Your reproduction ran
the *default* path — `build_server` → a resolver with `load_dotenv_file` untouched — so nothing above
changes your result. Your `sys.modules` sweep remains the right defence, and your reasoning for walking
the modules rather than patching `dotenv.load_dotenv` is correct: every `from dotenv import load_dotenv`
holds its own binding. Note also that four credential paths — `net`, `eutils`, `literature`, `pharmvar`
— call `load_env()` with **no flag at all**, deliberately, because a credential is loaded where it is
read; so even a caller passing `False` everywhere still has `os.environ` mutated by the first network
client they build.

**Your candidate, and your reason for doubting it, are both in RM102 rather than being answered here.**
You were right to doubt it. A default flip is silent for every caller who never passed the parameter:
nothing warns, and a deployment pointing its cache through `.env` alone simply stops finding it — which
is the exact report the unconditional load was added to end. Under our charter that is S14's shape (the
addition being legal does not make the change legal) and the retirement cadence requires a deprecation
an author can *act* on, so the honest route is warn-then-flip across a minor, not a patch. The
allowlist variant — load the file, set only `JUST_DNA_*` — is rejected in the item for a separate
reason: it makes us a filter over somebody else's file and the allowlist becomes a hand-kept list of
every variable any tier reads.

**Your narrower ask is done.** [ENRICHER.md](ENRICHER.md) § cache locations now states that the load
writes into `os.environ`, that it is a library path rather than a CLI one, that `override=False` skips
a variable that is **present** so *deleting* one is what lets the file win — your finding, and the part
that is genuinely counter-intuitive — and names both the switch and the flagless credential paths. The
cache-internals bullet carries the S39 defect beside the 0.5.2 one it grew out of.
<!-- triaged: 0.6.3 · sha f5fff5532a4e -->

Reported by **just-module-creator** on 2026-08-18, adopting format 0.6.1 / enricher 0.6.2.

**What we ran.** Our suite has an autouse fixture whose job is to make a forgotten `_env_file=None`
harmless: it points `Settings.model_config["env_file"]` at a path that cannot exist, and clears the
ecosystem's variables out of `os.environ` with `monkeypatch.delenv`. It has a test of its own asserting
the clear-list is derived from the model rather than hand-written. On this tree it had stopped working,
and nothing said so.

**What happened.** Measured inside one test, on a machine with a real `.env`:

```
1 after fixture:      None
2 after Settings():   None
3 after build_server: 'mk_live_…'      # a live polygon credential
4 after connect:      'mk_live_…'
```

`build_server` reaches `just_dna_enricher.locations` through our network module, and `locations`
calls `load_dotenv(env_path, override=override)` while resolving a cache path. `override=False` skips
a key that is **present** — so deleting the variable is precisely what lets the file win. The fixture
had made the leak possible rather than prevented it, and the failure shape is the bad one: it passes in
CI where no `.env` exists, and means something different on every developer's machine.

The concrete symptom was a test named `test_a_token_does_not_leak_between_sessions` failing with *"The
server is configured offline"* instead of its assertion — because a session that had authenticated
nothing resolved a real token, got past the auth check, and hit the offline ceiling behind it. It took
a while to believe that the token was arriving from the environment rather than from our own session
store, because the store was empty and the session id was fresh.

**What we did meanwhile.** Neutralized the loader rather than the file: the fixture now walks
`sys.modules` and replaces every `load_dotenv` binding it finds with a no-op returning `False`. Walking
rather than patching `dotenv.load_dotenv` is deliberate — every module that did `from dotenv import
load_dotenv` holds its own binding, so patching the source module reaches none of them. Two tests pin
it, one asserting no ecosystem variable changes across `build_server` and one asserting the sweep
actually reached `just_dna_enricher.locations`; both were run against the unfixed fixture and watched
to fail.

**Why we think it is yours and not just ours.** `load_dotenv` mutates the whole process environment,
and `locations` calls it from a *library* path rather than from a CLI entry point. Any consumer that
imports the enricher and resolves a cache path inherits the contents of whatever `.env` happens to sit
above their working directory — including credentials for services they never asked about. A CLI
loading `.env` is normal and ours does it too; a library function doing it as a side effect of
answering "where is the cache" is the part that surprises.

**A candidate fix, and the reason we are not confident in it.** The obvious move is to have
`locations` read `os.environ` and leave the loading to the entry point — `load_dotenv_file: bool = True`
already exists as a parameter, so the machinery is there and only the default is the question. What we
cannot judge from here is who relies on the current default: if a documented workflow is "call the
enricher's Python API directly and let it find your `.env`", then flipping it breaks that, and a
deprecation cycle is the honest path rather than a patch. The narrower version, if the default has to
stay, is to say so in the ENRICHER docs beside the cache-path helpers — the behaviour is currently
discoverable only by reading `locations.py`, which is how we found it after an hour of assuming the bug
was in our own fixture.

---

## S40 — two 0.6 changes a consumer meets that INTEGRATION_0_6.md does not name, one of them a check that *stopped* refusing

**Status — accepted, all three; [INTEGRATION_0_6.md](INTEGRATION_0_6.md) fixed in this pass, and item
2 also gained the fixture it was missing.** All three reproduced exactly as written, on this tree:
`StudyRow.REQUIRED_ANY_OF` is `()` and `StudyRow(pmid="12345", conclusion="Test")` is accepted with
`variant_key is None`; `reference_examples/shox_par1/resolution.csv` is 10 rows, 10 distinct rsIDs,
every one on chrX, so nothing in it expands; `_OUTPUT_FILES` is gone from
`just_dna_compiler.compiler` and `ARTIFACT_PARQUETS` is there in its place.

**1 — the relaxation now has its own subsection, and your framing is the one that went in.** § 1 gains
a *"one check **stopped** refusing"* heading beside the two tightenings, and the § 1 table gains the
symmetric row (*Requiredness relaxed — one*), because you are right that the old row was literally
true and still left a reader with no way to anticipate the failure. The subsection leads with the
consequence rather than the validator — `StudyRow.variant_key` can be `None`, a null join key in
polars is a silently smaller result rather than an error — and carries your two-line advice verbatim
in spirit: pin the consequence, not the acceptance, and do not repair a null key into a string. Your
argument for *more* emphasis rather than less is quoted in the heading itself: a relaxation is
invisible to a corpus run and visible to every consumer holding a negative test.

We looked for our own half underneath it, as an item like this usually has one, and there is none:
`_cross_validate_studies` handles the subject-less row deliberately (its docstring names RM47 and
explains why the dedup key is `(None, pmid)`), and the compiler's own study paths match on any shared
identifier rather than on `variant_key` equality. So this is documentation-only on our side, which is
worth saying rather than leaving you to infer.

**2 — the sentence was wrong to point at a shipped artifact, and it now says how to build one *and*
where the fixture lives.** Your reading afterwards was generous; ours is that "one is instantiated in
`reference_examples/shox_par1/`" is not defensible when the committed example instantiates nothing,
and it is worse than a plain gap because it was offered as the evidence that your mitigation is
insufficient. § 3 now states outright that the committed example contains no expansion, gives the
regeneration route (`enrich --keep-par-twin`, whose default keeps only the X spelling), and describes
the hand edit — including that the VRS check will refuse the copied `vrs_id` and print the recomputed
ones, which is the ten-minutes-not-an-afternoon detail you found.

**Building it here found the gap under your report.** The claim had no instance anywhere in this
repository, tests included: the corpus's only other expansion is `pathogenic_clinvar`'s
`rs1554917888`, `T>TA` beside `TA>T`, which differs in `ref` — so every existing assertion about
`locus_count` would have survived an expansion that deduped on `(chrom, start, ref)`, and the
same-`ref` case a `ref`-spelling guard cannot see was pinned by nothing.
`test_two_loci_sharing_a_ref_still_count_as_two` now builds the twin from the example's own row
through `par_partner`, and asserts both halves against each other — exactly one distinct `ref` across
the expanded rows, *and* `locus_count == 2` on each. It is the ground-truth artifact you wanted, in a
form that also fails if we ever break it.

**3 — added, as the half-sentence you wrote.** § 1's headline now carries the exception directly:
`_OUTPUT_FILES` was made public as `ARTIFACT_PARQUETS` (§ 2.4), so a consumer who imported the private
name gets an `ImportError` at module scope. We also recorded that you had the better of the two
arguments — re-listing that set by hand is the defect § 2.8 and S35 trace the broken publisher to, so
importing the underscore was the lesser evil and the headline should have said so.

**Nothing is filed.** Three documentation fixes and one test, all in the tree; the fixes are in a
document that describes an already-shipped release, so there is no version to wait for. Thank you for
the last section — the `layout` and § 8 notes are the only evidence we get that a document did its
job, and § 8's *four shapes with the silent one spelled out* is the shape we will keep writing.
<!-- triaged: 0.6.2 · sha 09e9c111af7c -->

Reported by **just-dna-lite** on 2026-08-18, adopting format 0.6.1 / compiler 0.6.1 / enricher 0.6.2
(and registry 0.17.0) from a working 0.5.4 integration. `INTEGRATION_0_6.md` was the whole plan for the
migration and it was accurate about everything it covered — the delta in § 2 held, § 3's per-consumer
list was the real work list, and the two tightenings in § 1 were correctly the only *new* refusals.
Three things still cost time, and all three are documentation rather than code.

### 1. `StudyRow`'s identifier requirement was relaxed (RM47), and nothing in the integration note says so

**What we ran.** `uv run pytest` immediately after the version bump, before touching any of our own
code, exactly as § 1 invites ("nothing you have breaks"). Seven failures, and the first was ours
asserting a *refusal*:

```python
with pytest.raises(Exception, match="At least one identifier"):
    StudyRow(pmid="12345", conclusion="Test")     # 0.5.4: raised.  0.6.1: accepted.
```

**What we expected.** § 1 lists what can newly refuse (RM50, RM48) and states "Fields removed,
retyped, or promoted to required | **none**". We read the whole document looking for the converse and
it is not there. `REQUIRED_ANY_OF` going from `({rsid}, {chrom})` to `()` is not a removed, retyped or
newly-required field, so the table is literally true — and a consumer holding a test suite still gets
a failure the document gave them no way to anticipate. RM47 is in the changelog and the schema
docstring is excellent; it is the *integration* note that is silent.

**Why it is worth a line rather than being obvious.** The load-bearing half is not the validator, it
is the consequence one layer out: **`StudyRow.variant_key` can now be `None`**. Anything joining
`studies.parquet` to a lead table on `variant_key` now meets a null key, and a null join key in polars
is a silently smaller result, not an error. We were lucky — `load_studies_for_variants` filters
`pl.col("rsid").is_in(rsids)`, and a null rsid matches nothing, which is the correct outcome for a
citation that grounds a bin boundary rather than a variant. A consumer who keyed on `variant_key`
instead would have lost rows with no signal at all.

**What we did meanwhile.** Rewrote the test to assert the new contract, and pinned the *consequence*
rather than the acceptance — `row.variant_key is None` and `REQUIRED_ANY_OF == ()` — with a comment
saying not to repair a null key into a string.

**Suggested for 0.6.3, and it is one table.** § 1 has "Two checks can newly refuse an author's spec".
The symmetric entry is missing: *one check stopped refusing, and here is what it does to `variant_key`*.
A relaxation is invisible to a corpus run (it can only turn red green) and visible to every consumer
with a negative test, which is the reverse of the tightenings — so it needs saying more, not less.

### 2. § 3 points us at `reference_examples/shox_par1/` for a same-`ref` expansion, and the shipped example has none

**What we ran.** § 3's first change item for us is to adopt `locus_count > 1`, on the argument that our
own mitigation "**misses same-`ref` expansions**, and one is instantiated in
`reference_examples/shox_par1/` via `enrich --keep-par-twin`". That is exactly the fixture we wanted —
our mitigation is real code with a real measured harm behind it (S33's 3,762 findings) and we wanted a
ground-truth artifact to test the replacement against rather than a frame we invented.

**What happened.** The shipped example has no expansion in it:

```
resolution.csv                     10 rows, 10 distinct rsIDs, no id on >1 locus
compile_module(shox_par1, ...)     success, expanded_keys=0, expanded_rows=0
weights.parquet                    11 rows, locus_count == 1 on every one
```

Read again afterwards, the sentence is defensible — `via enrich --keep-par-twin` can be read as *"this
is the example you would regenerate with that flag"* rather than *"this is what is committed"*. But it
is the only pointer in the document to a concrete instance of the shape, it is offered as evidence
that our mitigation is insufficient, and a consumer follows it expecting to find the thing.

**What we did meanwhile.** Synthesized the twin ourselves: copied the example, duplicated one
`resolution.csv` row onto chrY, and compiled. Two notes from doing it, both in the compiler's favour:

- The VRS check caught it and **refused**, correctly and with the recomputed ids in the message
  (`stored vrs_id … does not match the id recomputed from Y:641036 C>A (ga4gh:VA.0qI84…)` — "this is
  corruption, not a difference of opinion"). Pasting the two reported ids back in was the whole fix.
  That error message is the reason this took ten minutes rather than an afternoon.
- With that done: `expanded_keys=1`, `expanded_rows=2`, and two rows with `ref="C"` on both,
  `start` equal, `locus_count=2`, `locus_index` 0 and 1 — the shape § 3 describes, and one our
  `ref`-spelling guard demonstrably passes through (we ran it both ways: the grouped test finds one
  `ref` spelling per position and withholds nothing).

**Suggested for 0.6.3.** Either commit the twinned `resolution.csv` as its own tiny example, or make
the sentence say the example must be regenerated and name the two-line edit. We would take the
regeneration note happily; what we could not do is tell from the document which of the two it was.

### 3. A smaller one: the only hard break we hit was a *private* name, and § 1's headline reads past it

`from just_dna_compiler.compiler import _OUTPUT_FILES` is an `ImportError` on 0.6.1. This is **fairly
documented** — § 2.4 says `ARTIFACT_PARQUETS` "Was private `_OUTPUT_FILES`" — and it is our own fault
for importing an underscore, which we did knowingly and with a comment saying why (a hand-copied copy
of that list had already gone stale once here, and re-listing it is what INTEGRATION_0_6 § 2.8 and S35
both identify as the defect that broke the publisher; importing the private name was the lesser evil).

Recording it only because "**§ 1. The headline: nothing you have breaks**" is the sentence a reader
carries into the upgrade, and for us the very first thing that happened was an import failing at
module scope. A half-sentence under that headline — *"one private name a consumer may have imported
was made public under a new name; see § 2.4"* — would have set expectations right. No action needed on
the code: making it public is the correct fix and we have adopted it.

### What went right, since a report that only lists friction is a misleading record

`§ 3`'s list for us was accurate and complete. The seven test failures we saw sorted into exactly
three groups, all three anticipated by the document (RM80's annotations key, the `licensing.csv`
rename, and RM47 above). `content_signature` not moving meant there was nothing to re-derive.
`layout` is the module we did not know we needed and it removed a whole class of guesswork — our
drafters' stale-file sweep named `sources.csv` literally, and on a `derived/` tree that leaves the
**deprecated** spelling as the copy the next `sidecar_write_path` merges into, so the module keeps the
old name permanently; `sidecar_candidates` made the fix three lines and correct by construction rather
than by coincidence. And § 8's exception table cost us nothing to check precisely because it was
written as four shapes with the silent one spelled out — we have no handler around an enricher pass at
all, so the answer was "nothing to do", reached in one grep instead of by reasoning about MRO.
