# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

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

## S149 — enricher 0.8.4's `tenacity>=9.2.1` floor cannot resolve beside google-genai, so just-dna-lite needs an override to install the 0.8 trio

**Reporter:** just-dna-lite (adopting the 0.8.4 cut, 2026-11-12).

**What we ran.** Raised our floors to `just-dna-format/compiler/enricher>=0.8.4` and `just-dna-registry>=0.30.0`,
then `uv lock`.

**What we expected.** RM371's entry (CHANGELOG, 2026-11-04) says "just-dna-lite, just-module-creator and the
marketplace all accept 9.2.1".

**What happened.** No resolution:

```
Because google-genai==1.75.0 depends on tenacity>=8.2.3,<9.2.0 and just-dna-enricher>=0.8.4 depends on
tenacity>=9.2.1, we can conclude that google-genai==1.75.0 and just-dna-enricher>=0.8.4 are incompatible.
```

We depend on `google-genai` (agno's Gemini model, our in-app module creator). Every google-genai release
checked caps `tenacity<9.2.0`: 2.27.0 through 2.34.0, 3.0.0, 3.1.0 and 3.2.0 (the current one); there is no
release to float to. A plain `uv lock --upgrade` did something worse than fail: it kept
`just-dna-enricher==0.7.3` beside `just-dna-format==0.8.4` and `just-dna-registry==0.30.0`, because nothing
we pinned forced the enricher up. So a consumer that relocks without raising the enricher floor gets a mixed
trio silently.

**What we did meanwhile.** A workspace `override-dependencies = ["tenacity>=9.2.1"]` in our root
`pyproject.toml`, marked temporary, with this id. google-genai calls only `stop_after_attempt`,
`retry_if_exception`, `wait_exponential_jitter`, `before_sleep_log` and `(Async)Retrying`
(`google/genai/_api_client.py`), none of which 9.2.1 changed, and a live Gemini call under 9.2.1 reached the
API (it answered 402 for our depleted credits, i.e. the client built and sent the request). We will remove the
override when either side moves.

**Candidates, for you to weigh.** (1) Accept `tenacity>=9.0` and pick `multiplier=` or `initial=` by what the
installed release offers, so the warning RM371 fixed stays fixed without the floor. (2) Keep the floor and
correct RM371's sentence, so the next consumer is not told its install works. We have no view on which is
better for the enricher; (2) costs us a permanent override until Google lifts its cap.

**Status — filed as [RM436](ROADMAP.md#rm436--the-enricher-floors-tenacity921-and-google-genai-caps-it-below-920-so-a-consumer-depending-on-both-cannot-resolve-the-08-trio): a patch either way; the pm picks between your two.** Confirmed. google-genai 3.2.0, its
newest, requires `tenacity<9.2.0,>=8.2.3`, and RM371's sentence that just-dna-lite accepts 9.2.1 was wrong: it read
your direct dependencies and missed the transitive cap. Your second finding is worse than the first, and it is in
the entry. A relock that does not raise the enricher's floor silently kept enricher 0.7.3 beside format 0.8.4. Your
override is sound on the evidence you give, since google-genai's calls are unchanged under 9.2.1.

<!-- triaged: RM436 filed (patch; floor vs shim, pm picks) · sha 8a7e5d94f1bf -->

## S150 — the split Ensembl snapshot's `groups/` sidecars have no provisioning route, so a consumer who wants them must write into the directory 0.8 says only the enricher may write

**Reporter:** just-dna-lite (adopting 0.8.4, 2026-11-12).

**What we ran.** Moved our Ensembl downloader onto the enricher's lane, as INTEGRATION_0_8 § 3 asks
(`download.ensure_snapshot`, `locations.SNAPSHOT_REPO_IDS["ensembl"]`), and deleted ours.

**What we expected.** That the lane would give us the snapshot `just-dna-seq/ensembl_variations_split`
publishes, including the column groups its README lists as default (`consequence`, `clinical`, `predictors`,
`frequency`) and optional (`cadd`, `frequency_populations`, `transcripts`), all attested by the one
`manifest.json` and its `release_id`.

**What happened.** The lane pulls `data/*.parquet` only; `locations.py` says so deliberately ("Files outside
`data/` (prepare-annotations' `groups/*`) are the manifest's and not pulled"). On this machine the cache is a
whole core with a 200-file manifest naming 8 groups, of which none is on disk. Our Ensembl annotation join now
adds `id` and `row_idx` and nothing else: the core holds `chrom, start, ref, alt, id, row_idx`, and every value
our users used to read (ClinVar flags, frequencies, consequence) moved to a group. The old repo's boolean
columns are gone with it.

**Why we did not just download them.** A group is joined on `(chrom, row_idx)`, which the README says is valid
only within one `release_id`. The only safe writer is one that checks the group files against the same
manifest the core was pulled under, records them in the pull record, and re-pulls them with the core when the
release moves (RM420). That is your `_provision_snapshot`. A second downloader of ours writing `groups/` into
`<base>/ensembl_variations` is exactly the shape § 1.29 warns about (another downloader into the lane's
directory mixes releases), and a group left from an older release after `cache pull` follows a newer core would
join rows to the wrong variants silently.

**Meanwhile.** Nothing: our Ensembl step adds rsIDs only, and we tell users not to rely on it. The annotation
is a separate, optional job, so module annotation is unaffected.

**Ask, as a candidate.** An opt-in group selection on the `ensembl` lane (`ensure_snapshot(groups=...)`,
`cache pull --only ensembl --groups consequence,clinical`), attested by the manifest and recorded in the pull
record, plus a public name for the group directory (`snapshot.ensembl_group_dir(cache, group)` or similar) so a
reader never spells the path. A refusal when a present group's files are not the manifest's release would be
the guard `row_idx` needs.

**Status — filed as [RM437](ROADMAP.md#rm437--the-split-ensembl-snapshots-groups-sidecars-have-no-provisioning-route-so-a-consumer-who-needs-a-group-must-write-into-the-lanes-directory-itself): a minor; the pm sizes.** Confirmed: the lane pulls `data/` only, by the comment you
quote. You are right not to write `groups/` yourselves. A group joins to the core on `row_idx`, valid within one
`release_id`, so the only safe writer is the one that pulled the core under the same manifest. Your candidate is the
ask: opt-in groups on the lane, attested and recorded, a public directory name, and a refusal on a release
mismatch. That is a new parameter, a new flag and a new public name, so a minor, and it waits for one.

<!-- triaged: RM437 filed (minor) · sha 718ff0ac926d -->

## S151 — a position-only row resolves to the lexicographically first rsID at its `(chrom, start, ref)`, so dbSNP 157's new insertion at CYP2D6*4 takes rs3892097's place

**Reporter:** just-dna-lite (adopting 0.8.4 against `ensembl-variation-2026_07_13-vep116.0`, 2026-11-12).

**What we ran.** `just_dna_enricher.resolver.resolve_variants` on a coordinate-only `VariantRow` at CYP2D6*4,
`22:42128945`, `ref=C`, `genotype=A/G`, no `rsid` (our test `TestResolver::test_position_to_rsid`).

**What we expected.** `rs3892097`, the test's ground truth (CYP2D6*4). We did not re-run 0.7.3 against the
old snapshot, so we cannot say which release first answered otherwise.

**What happened.** `rs2517910443`. The split snapshot holds four rows at that position:

```
('22', 42128945, 'C', 'A', 'rs3892097')
('22', 42128945, 'C', 'G', 'rs3892097')
('22', 42128945, 'C', 'T', 'rs3892097')
('22', 42128945, 'C', 'CGGGTAAGGGGGCGTCT', 'rs2517910443')
```

`_lookup_rsids_by_position` keys its answer on `derive_variant_key(None, chrom, start, ref)` and fills it with
`setdefault` over rows ordered by `chrom, start, ref, id, alt`. Both rsIDs share the key `22:42128945:C`, and
`'rs2517910443' < 'rs3892097'` as strings, so the insertion wins. The row's genotype (`A/G`, which only the SNV
can host) is never consulted, and nothing warns that the position named two rsIDs. The `ORDER BY` comment says
the pick is deterministic, which it is; it is not right. If the old snapshot held one rsID there, the defect
was latent until dbSNP 157; we have not checked.

**Meanwhile.** Our test is `xfail(strict=True)` naming S151, so it tells us when this changes.

**Candidates.** Narrow the rows at a position to the ones whose ALT set can host the row's genotype (the RM382
hosting rule, applied to the back-fill), and withhold with a warning naming every rsID when more than one is
left. A strict mode would refuse the ambiguous case like any unresolved row.

**Status — filed as [RM438](ROADMAP.md#rm438--resolve_variants-back-fills-a-position-only-row-with-the-first-rsid-at-its-chrom-start-ref-whatever-the-genotype-and-warns-nothing): severity high, a patch; the pm sizes.** Reproduced on `main` with your four rows in an
in-memory table: `_lookup_rsids_by_position` returns `rs2517910443` and no warning. The enrich path that builds
`resolution.csv` is not this code. It uses the allele-aware `_lookup_rsid_candidates`, which never picks
silently. `resolve_variants` is the older public function: the compiler reaches it only through the deprecated
`ensembl_cache` path, and you call it directly. A wrong rsID on a CYP2D6 row is reason enough to fix it now
rather than at its 1.0 removal. Your candidate is the ask: narrow to the ALTs that can host the genotype (RM382's
rule), attach only a single survivor, and withhold with a warning naming every rsID otherwise. Moving to
`enrich` + `resolution.csv` would also take you off this path.

<!-- triaged: RM438 filed (high, patch) · sha c234a6cefc39 -->
