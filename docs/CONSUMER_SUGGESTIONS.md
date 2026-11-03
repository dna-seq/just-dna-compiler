# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S125

**Claim ids from here, never from what this file shows.** S1–S124 are all answered and live in the
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

## S125 — `logs/` ships only `*.log`, and a `.jsonl`, `.json`, `.md`, `.txt` or image beside it is dropped without a word

*From just-module-creator, 2026-10-05. Our tracking id is `F116`.*

**What we ran.** `assets/fto_bmi` from our repo (a real, compiling module), copied to a scratch dir,
with six files added under `logs/`: `authoring.log`, `trace/session-a.jsonl` (one JSON object per
line), `run.json`, `notes.md`, `notes.txt` and `fig.png`. Then, with format 0.7.1 / compiler 0.7.2 as
installed:

```python
r = compiler.compile_module(spec, out, resolve_with_ensembl=True, ensembl_cache=None, strict=False)
```

**What happened.** `success=True`, **zero warnings**, and `manifest.logs` holds exactly one entry,
`logs/authoring.log`. The other five are neither copied into `out/` nor mentioned anywhere. The cause
is `_collect_logs`, which globs `*.log` at the top level and `logs/**/*.log` below it.

**The registry inherits it without saying so.** `specfiles.carries_spec_content` passes the whole
`logs/` subtree through upload, and the server-side compile in `services/publish.py` leaves log
discovery to the compiler. So an author uploads `logs/notes.md`, the registry accepts it, and the
published version doesn't contain it. One fix in `_collect_logs` covers both paths.

**Why we hit it.** We are building a per-session ledger for retracing how each authored row came to
be: search receipts (service, query, IDs returned), fetch receipts (the fulltext's hash and length,
never the text), and decision entries (who decided, why, anchored to a hash and offset in a fetched
text). It also feeds a reviewer pass that flags rows with no chain connecting them to any search or
reading. The natural encoding is JSON Lines, and a file named `.jsonl` would not ship.

**We know about S82 / RM147, and we are diverging on purpose.** That answer put "read it, took
nothing" in an uncited `literature.csv` row and advised against a `logs/` writer, since it would be
unstructured and unqueryable. For your layer that's right, and we're not asking you to adopt a ledger
schema. But the row is lossy by design: it records that a paper was read and produced no row, and it
drops the reasoning in between (ambiguous wording, a cohort overlap, a small sample, contradicts the
mainstream view). Recording that reasoning used to cost a curator a lab journal written by hand; for an
agent it costs nothing, so we'd rather keep it. It stays unstructured only until somebody builds the
writer, and the writer is authoring workflow, which is our layer. We'll iterate the format on our side
(every line carries a `"v"`), and if it proves out we'll bring it back as something portable for you to
generalise. All we're asking now is that the transport carries it.

**What we'd ask, in order of preference.**

1. **Decide on content, not on the name.** A filename extension is a weak gate. If the concern is what
   gets published, text-versus-binary is the line that matters. Cheap checks that cost almost nothing
   on a compile:
   - `.log`, `.txt`, `.md`: decodes as UTF-8.
   - `.json`: parses.
   - `.jsonl`: every non-blank line parses as JSON.

   A file that claims `.json` and fails to parse could warn, or refuse under `--strict`. That's your call.
2. **A starting allowlist of `.log .txt .md .json .jsonl`**, if content sniffing is more than you want
   to own.
3. **Images are a question rather than a request.** A figure (a score distribution, a forest plot
   behind a weight) is a reasonable thing to keep with a run. `LOGO_EXTENSIONS` is a precedent for a
   magic-byte-checkable raster set (`png`, `jpg`, `jpeg`). SVG is the one to think twice about, since
   it's XML that can carry script. The registry serves every file as `application/octet-stream` today
   (`api/routers/modules.py`, `get_file`), so nothing renders inline yet, but any future inline
   rendering would make SVG a vector. A size ceiling is also yours to set.
4. **If you decline all of that, warn on what the sweep leaves behind:** *"logs/trace/a.jsonl is under
   logs/ and will not ship; only *.log does"*. The silent drop is the defect whatever the answer to 1–3.
   Right now the author's check passes and the file is gone.

**What it costs, as far as we can see.** `logs` is outside `artifact.digest`
(`docs/audit/COMPILER_FROM_CODE.md`, the exclusions list), so widening the set moves no module's
identity. `manifest.logs[]` is a list of `FileEntry` with a name, so no schema change. One exposure
change is worth a changelog line: a module that already has a stray `notes.md` in `logs/` starts
shipping it on its next recompile, and a published log is permanent.

**What we're doing meanwhile.** Naming ledger files `*.log` with JSON Lines inside. It travels, but the
name hides the type, so no consumer can tell a structured ledger from free text without opening it.

**Addendum, same day: the RM147 home is a derived table, which is part of why we want our own
record.** `literature.csv` is in `hints.DERIVED_TABLE_MODELS` and registry `DERIVED_FILES`, and
`LiteratureRow` is a standalone model rather than an `AuthoredModel`, by its own docstring. So the
documented place for an authored fact (a person or agent read this paper and decided against it) is a
row hand-written into a machine-produced table. It survives, because the literature pass is
merge-not-clobber and says deleting a curator's row is not its call. But it has no column for the
reason, who decided or when, and `TABLES.md`'s `overrides.csv` section describes editing a derived CSV
directly as the repair that file exists to refuse. We're not asking for a new authored table; we'd put
the reasoning in our ledger. We mention it because the two passages read as contradicting each other,
and you may want one of them to say which applies to a hand-written uncited row.

## S126 — an interrupted snapshot pull leaves a cache that reads as complete, so it is never finished

*From just-dna-registry (`registry warm-caches`), 2026-10-08, enricher 0.7.3.*

**What we ran.** `uv run --extra server registry warm-caches --apply` on a fresh host, empty
`/data/just-dna-cache/ensembl_variations`. HuggingFace read timeouts on chr12 (default
`HF_HUB_DOWNLOAD_TIMEOUT` of 10 s, five retries) ended it: `✗ ensembl: FAILED — The read operation timed out`.

**What we expected.** The next run resumes and fetches the 22 missing chromosomes.

**What happened.** The 3 chromosomes that had finished were valid parquets, so `--dry-run` reported
`✓ ensembl` and a second `--apply` would have skipped the lane. Enrich would then have resolved rsIDs
against 3 of 25 chromosomes and said nothing. Cause, in `enricher/src/just_dna_enricher/download.py`,
`_provision_snapshot`: `if existing and not corrupt: return cache_dir` trusts any non-empty set of
footer-valid files. The per-file `.part` + rename-after-verify makes an interrupted pull look exactly like
a finished one: every file present is whole, and the ones missing leave no trace. The lane `resolve()`
inherits the same answer, so `warm-caches`, its dry run and -lite's `prepare-caches` all agree it is present.
It applies to all three snapshots that share the helper.

**What we did meanwhile.** Moved the partial directory aside by hand and re-ran with
`HF_HUB_DOWNLOAD_TIMEOUT=120`; 25/25 landed. Nothing on our side can see the gap.

**Candidate fix.** At the end of a successful pull, write a completion record into the cache (the file
list, or the remote listing it was fetched against), and trust a cache only when that record exists and
every file it names is present and footer-valid. A cache without the record is incomplete: fetch what is
missing, skip what verifies. That keeps "no network on a warm cache". The cost is caches provisioned before
the record existed: they would refetch once, or could be grandfathered by comparing against the remote
listing the first time the network is reachable. A smaller second item: the 10 s default timeout is short
for 0.5–1 GB files; a longer default, or naming `HF_HUB_DOWNLOAD_TIMEOUT` in the error, would have saved the
diagnosis.

---

## S127 — after RM251, `source="authored"` in `resolution.csv` means two different things and nothing in the row tells them apart

*From just-module-creator, 2026-10-25. Our tracking id is `F118`.*

**What we ran.** A new statin module: `draft_from_cpic` for SLCO1B1 and CYP2C9 (enricher 0.7.3 from
PyPI, snapshot `cpic_snapshot_b0ffd4c6f010`), then `enrich --strict` against a provisioned Ensembl
lane, then `compile --strict`. format 0.7.1, compiler 0.7.2.

**RM251 works, and we want to say so first.** This is the shape S104 reported, re-run on the shipped
fix. 117 of 130 `resolution.csv` rows came back `source="cache"` with `ref`, `alts` and a `ga4gh:VA`
id, where before the fix every CPIC-drafted haplotype row was a photocopy of the module. VRS coverage
on this module is 166/183 alleles rather than 0.

**What we did not expect.** The 13 remaining `source="authored"` rows are two populations with
nothing in the row to separate them:

```
variant_key           rsid           source    status    rsid_status  ref  alts
10:94938788:None      (empty)        authored  resolved  (empty)              # 6 rows
rs2492587526          rs2492587526   authored  resolved  live                 # 7 rows
```

- **Six rows have no rsID at all.** CPIC's `allele_definitions` gives a position and no rs-number, so
  there was never anything to ask. `authored` is the right label and no fill was ever possible.
- **Seven rows carry a live rsID the Ensembl lane does not know.** All seven are recent high-numbered
  ids (`rs2492587526`, `rs2492591692`, `rs2492634549`, `rs2492650213`, `rs2492662738`, `rs2492662839`,
  `rs2493006942`). `rsid_status="live"` — so the currency link reached dbSNP and the id is real —
  while the lane that supplies `ref`/`alts` has no record, because our snapshot predates the dbSNP
  build that minted them.

Both land as `source="authored", status="resolved"` with empty `ref`/`alts`, and the compile folds
them into one warning: *"VRS allele identity covers 166/183 allele(s) … 17 allele(s): no ALT
recorded"*.

**Why it matters to a consumer rather than to us.** The two cases have opposite remedies. The first is
permanent — no refresh of anything will ever fill it, and a module carrying those rows is as complete
as it can be. The second is a stale cache, and the remedy is a newer Ensembl snapshot. A consumer
reading the sidecar, or an agent deciding whether a module is finished, cannot currently tell "this
module is done" from "pull a newer lane and re-run". We hit this on a module we were about to close,
and had to read `rsid_status` against `ref` across 130 rows to work out which it was.

`status="resolved"` on a row with no `ref`, no `alts` and no VRS id reads oddly on its own, too — the
row resolved to a position and nothing else.

**What we did meanwhile.** Nothing in the data: the rows are truthful and the module compiles green at
91% VRS coverage. We wrote the split into the module's README so a later reader does not have to
re-derive it, and we are not re-pulling Ensembl for seven CYP2C9 defining variants that no diplotype
in this module needs a VRS id for.

**A candidate, and the argument against it.** The obvious fix is a second `source` value — say
`unresolved_in_lane` beside `authored`. We think that is wrong: `source` answers *where this row's
values came from*, and in both cases the answer really is "the author". The question we could not
answer is a different one — *was a lookup attempted, and what did it say?* — and `status` is the
column already shaped for it. A `status="position_only"`, or leaving `status` as is and adding the
lane's verdict where `rsid_status` already sits, would separate the two without overloading `source`.
We have no view on which, and the reporting gap is the finding rather than the spelling.

**Correction, same day, before anyone answers.** The claim above is narrower than we wrote it. We
then read the published `verification.json` and found `rsid_coordinate_agreement` already states the
split in its `detail`, by name:

> *"Further authored pairs were not compared: the injected Ensembl snapshot carries no record for 7
> of them (rs2492587526, rs2492591692, rs2492634549, rs2492650213, rs2492662738 and 2 more), and
> absent from this snapshot is not absent from Ensembl; 2 name an indel (rs1304490498, rs9332131),
> whose spelling can move the coordinate legitimately, so no verdict was reached."*

That is exactly the distinction we said was missing, including the "absent from this snapshot is not
absent from Ensembl" reading we had to derive by hand. So the information is recorded and the
sentence is a good one. What stands is only that it is recorded **in a different file from the rows
it is about**: `resolution.csv` carries the rows, `verification.json` carries the explanation, and
nothing joins them — a consumer reading the sidecar, or a compile warning counting 17 alleles with
no VRS id, gets no pointer to the check that already explained why. If the answer is "read
`verification.json`", that is a fine answer and we would suggest only that the VRS-coverage warning
name it. We would not have filed this had we read the attestation first; the useful part of the
report may just be that we did not think to.
