# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S88

**Claim ids from here, never from what this file shows.** S1–S87 are all answered and live in the
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

---

## S88 — `needs_recompile` raises `AttributeError` on the one input it is most likely to be handed: a manifest that stamped no compiler version

Reported from `just-module-creator`, 2026-09-03, 0.7 branch at `f4a9b14`, installed editable.

**What we ran.** The call your own § 2.8 recommends, on a manifest read back through `read_manifest`:

```python
mf = read_manifest(out / "manifest.json")     # parses fine
mf.compilation.compiler_version               # None
needs_recompile(mf.compilation.compiler_version, "0.7.0")
# AttributeError: 'NoneType' object has no attribute 'strip'
```

`Compilation.compiler_version` is `str | None` with a `None` default, so a manifest carrying nothing
there is well-formed and round-trips through your own reader. We produced one by editing a real
compiled manifest and re-reading it — no private API, no constructed model.

**Why this is the input that matters rather than a fuzzing result.** The consumer you named for this
API is a registry's `revalidate` / `needs_upgrade`, which walks manifests it did not produce.
`INTEGRATION_0_7 § 3` tells `just-dna-marketplace` to "adopt `needs_recompile` for the
`revalidate` / `needs_upgrade` derivation", and the obvious implementation is a loop over stored
manifests. One manifest with an unstamped `compiler_version` takes that loop down with a
`NoneType.strip`, which is not an error a caller can catch by type or act on by reading.

**And the answer it should give already exists in the design.** The three-valued axis is the whole
point of this API — `None` is *unknown*, `complete` is False over a span you have no record for. An
unstamped version is the purest possible "unknown provenance", and it is the one case that raises
instead of blunting. `needs_recompile("1.0.0", "0.7.0")` already answers all-`None` /
`complete=False` for a version you have no record of; `None` deserves the same answer for a stronger
reason.

**Adjacent inputs, for whoever fixes it.** We tried the spellings a real manifest or a `compiled_by`
tag can carry:

| input | result |
| --- | --- |
| `"just-dna-compiler 0.6.6"` | correct |
| `"just-dna-format 0.6.6"` | accepted — the prefix is not checked, which may be deliberate |
| `"1.0.0"` | all-`None`, `complete=False` — the good shape |
| `None` | **`AttributeError`** |
| `""` | `ValueError: version must be MAJOR.MINOR.PATCH, got: ''` |
| `"0.7"` / `"v0.7.0"` / `"0.6.6+local"` | `ValueError`, same message |
| `"just-dna-compiler 0.6.6 (marketplace-server)"` | `ValueError` on `'(marketplace-server)'` |

`""` and `None` are the same fact — nothing was stamped — and answer differently, which is the pair
we would most like to see agree.

**Candidate fix, and our doubt about it.** Treat `None` (and plausibly `""`) as unknown: return the
all-`None`, `complete=False` answer rather than raising. The doubt is whether that is *too* quiet —
a caller who passes `None` by accident, from a field they meant to read as a string, gets a valid
answer instead of a crash. We think unknown is still right, because this API's contract is that an
unknown answer is safe and a caller has `complete` to test; but if you disagree, a typed
`ValueError` naming the field would still be a large improvement over `NoneType.strip`, and the
`ValueError` messages you already emit are good ones.

**What we did meanwhile.** Nothing — we do not call `needs_recompile` yet. We found it while reading
§ 2.8 to decide whether our `module-revise` and `compare_to_published` surfaces should adopt it, and
we would rather ask before building on it.

---

## S89 — `CACHE_LANES` publishes every attribute of a lane except the environment variable that overrides it

Same session, same branch. Small, additive, and not deadline-bound — filing it now because the
registry it is about is new in this release and consumers will hand-keep the list in the meantime.

**What we were doing.** Our test suite clears every environment variable that could change what a
test asserts, and the list is *derived* wherever it can be — every field of our own settings model
becomes `JMC_<FIELD>` — because a hand-written one drifted the first time somebody added a setting.
Four names are hand-maintained "by necessity", being read by code we do not own. Adopting 0.7, we
went looking for whether the new cache variables should join them, and expected `CACHE_LANES` to
answer, since `INTEGRATION_0_7` says to read it "instead of hard-coding which snapshots exist; a
hand-kept list is what this replaced, and it had drifted by three lanes".

**What we found.** `CacheLane` carries `name`, `subdir`, `serves`, `build_command`, `resolve`,
`default_dir`, `rebuild`, `ensure`, `publish_repo`, `terms`, `unpublished`, `unbuilt`,
`release_label`, `parents` — and no environment variable. The variable is a string literal inside
each resolver:

```python
return _resolve_named_cache(acmg_cache, "JUST_DNA_ACMG_CACHE", ...)
```

The mapping is exactly 1:1 — 14 lanes, and `grep -o 'JUST_DNA_[A-Z_]*' locations.py` gives 14
per-lane variables plus the shared `JUST_DNA_PIPELINES_CACHE_DIR` — so the field would be a pure
restatement of something already true, which is the cheap kind to add.

**Three consumers that want it, all of which currently hand-keep a list of fourteen.** A deployment
auditing which caches were provisioned by variable rather than by path (`prepare_caches` reports the
route but not what steered it); a `.env.template` generated rather than typed, which is what we ship;
and a hermetic test fixture clearing the environment, which is our case.

**Honest scope, so you can weight it.** **Our suite is unaffected today** — we exported all fourteen
to a bogus path and got 658 passed, unchanged. So this is a gap, not a break, and we are not asking
for it before the cut. It is additive, so it can land in 0.7.1 with no cost to anyone.

**Candidate fix.** `env_var: str | None` on `CacheLane`, populated from the same constant each
resolver already passes to `_resolve_named_cache`, and `None` for a lane steered only by the shared
base. Nothing has to read it for the field to pay for itself: the registry's stated purpose is that a
consumer stops keeping its own copy of what the lanes are, and the variable is the one attribute
where that has not happened yet.
