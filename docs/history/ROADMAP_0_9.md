# Roadmap — 0.9 (closed)

**Closed on 2026-11-26, when 0.9.0 was cut.** This was `docs/ROADMAP_0_9.md`: 0.9's scope from 2026-11-16, its two
trial rules, both review rounds' sortings, the pm's placements at the first cut (2026-11-19, never published) and the
rescope of 2026-11-26 that built that cut's leftovers in 0.9, and before that the deferral file of the minors after
0.8. It is kept here for the record of what 0.9 took in and why. Every item 0.9 scoped shipped, the rescoped nine
included, and each record is in [ROADMAP_HISTORY.md § The 0.9 minor](../ROADMAP_HISTORY.md#the-09-minor) with its
`**Residuals**`; the known issue 0.9 ships with is in [INTEGRATION_0_9.md § 4](INTEGRATION_0_9.md#4-known-issues).

**Where its contents went.** 0.10's scope and everything after it (the methylation minor, the VCF 4.4 items, RM149,
RM84 and RM67), with RM459 and RM460 from the first cut, moved to [ROADMAP_0_10.md](ROADMAP_0_10.md) unchanged but
for the file they sit in; RM468 joined them from ROADMAP.md, and RM469 (RM461's residual) was filed there. RM412's
half 1, the per-lane release probe, stays open and parked in [ROADMAP.md](../ROADMAP.md#active-items).
[RM_TOC.md](../RM_TOC.md) indexes every item and is where to look one up. Nothing here is edited as routine work, the
same rule as the rest of this folder.

**The scope, set on 2026-11-16 (the pm).** The maintainer, 2026-11-15: "don't make it too big, these half-a-week
release maraphons bleed me dry, lets make em smaller". So a minor is one theme, every design decision in it made before
its branch, and no new table kind. The cut went to the maintainer's desk as
[#326](https://github.com/winternewt/desk/issues/326) and was applied on its default under the kit's rule of the same
day, that only a real fork goes to the maintainer; it stands until they veto a part of it.

| Minor | Theme | Items |
|---|---|---|
| **0.9** | the enricher reads its reference data wherever it lives: local disk, then the registry's proxy, then Hugging Face (the order set on desk #261); the schema package gains one parsing function | RM430, RM431, RM437, RM443, RM404, RM412's second half |
| **0.10** | a small schema release: four optional additions | RM399 + RM441 (with S156), RM435, RM265, RM385 |
| **methylation** | after 0.10, undated until the PacBio samples are in hand | RM317–RM319, RM433, RM56, RM65, RM66 |
| *parked* | out of 0.9 into [ROADMAP.md](../ROADMAP.md#active-items), each with its gate | RM302, RM350, RM294, RM345 + RM286, RM358, RM360 |

**How 0.9 is built: two rules on trial** ([#327](https://github.com/winternewt/desk/issues/327),
[#328](https://github.com/winternewt/desk/issues/328), applied on their defaults; RELEASE_CYCLE.md is unchanged until
the maintainer decides after 0.9). A **blocker** is a defect this release itself introduced that refuses a valid module,
loses data on a round trip, or stops a downstream project from installing or importing the package.

1. **An item that emerges during the build goes to the next minor**, unless it is a blocker, which is fixed in the
   release.
2. **At most two review rounds.** A finding left after the second ships as a known issue in the upgrade notes and is
   filed for the next release, unless it is a blocker.

The pm reports after 0.9 how both went.

**Review round 1, sorted (the pm, 2026-11-18).** Four models were asked over `main...0.9` at 033b7213 and three
answered. They reported 11 error classes and a design question. **No blocker:** the compiler and schema models are
untouched, so no round trip moves, and a core-only install imports every new module. Every class is a defect in a
0.9 item's own build, so each is part of its item (the trial rule), and all are cheap. **Built before round 2:**

1. **One strict model for the proxy's reply** (RM430). A missing `truncated` is a malformed reply, not a whole one. A
   row that is not an object, or a reply whose lane or table differs from the request, is
   `SnapshotRouteUnavailable`, never an `AttributeError` out of `lookup_variant` (`@client-exception-contract`, the
   fourth leg). Tested by one walk over `REMOTE_LANES` that feeds the proxy malformed bodies.
2. **Every new warning and log text is pinned by its stable prefix** (`@warning-text-is-api`), by one walk over the
   texts the diff adds.
3. **A present but unreadable file is refused, never read as absent** (RM437). An unreadable pull record raises the
   documented typed error, instead of reading as no groups (which silently ended sticky groups). A
   `UnicodeDecodeError` is caught where `JSONDecodeError` is. A group record in the manifest is read leniently, member
   by member, so a field a later release adds cannot cost an older reader the core pin. A remote `release.json` keeps
   the local reader's leniency, by design.
4. **Every hand-kept typed column list gets the equality test** the civic, clinpgx and clinvar_gkm lists already have
   (`@registry-completeness`). `_ensure_declaration` keys on a field, not on `lane.name == "ensembl"`.
5. **`rsid` is declared in `KEY_COMPARES`**, and the equal-answers walk calls the holder with raw keys, not the
   private key builders. This is RM430's own class fix missing a key, not RM454. RM454 is local compares across
   functions; this is one function's two routes disagreeing.
6. **A request over the proxy's per-request limit goes to the next route**, as a folded key does. It never raises
   wrong-request.
7. **An index pin with a file missing its `sha256` is withheld**, never hashed as `""` (RM431, the house algebra).
8. **`batch_size` below 1 is refused where it is used**, not only when the settings are built (RM404).
9. **SCHEMAS.md's two sentences on a mistyped `release.json` key agree** with the code: the key is dropped.
10. **The negated shared predicate treats `NULL` as no match**, as the old `<>` did (cpic `partner_genes`).
11. **`lane_status` and `prepare_lane` call a stale index stale**, as RM431's reading 3 decided, never "present".

Not a defect: two remote asks in one lookup keep the first route, documented as deliberate in ENRICHER.md. At the
cut: the enricher's floor on format moves to 0.9 (it imports `parse_release`), RELEASE_CYCLE step 9. **Round 2 is the
last.** It reads the fixes, and the areas round 1 left unread: RM437's group provisioning past the pull record,
`SequenceProxy`'s lock and per-run memo, `cache rebuild --rehearse-download`, and the CHANGELOG's claim that `enrich`
with neither new argument writes the same bytes as before. That claim gets a test if none exists.

**Review round 2, the last, sorted (the pm, 2026-11-18).** It reviewed `main...0.9` at 4a238152. **No blocker**; 10 of
round 1's 11 fixes held. The eleventh (A, a repaired pull record that read as a finished pull) is fixed at 77c37ff1,
and `mitomap_miss`'s stale reason is in at 31b5bae4. No third round follows (trial rule 2). So a fix built now is
reviewed by nobody: each is a few lines, and its test is shown failing on the code before the fix, as A's was.

**Built before the cut:**

- **D, RM437 decision 4 holds: a group already current is not gated again.** The declared-use gate guards a fetch,
  not a read (`@acquisition-gate-is-not-a-read-gate`), and a current group fetches nothing. A module built from the
  group still meets its terms at the compile gate, through its licence rows. The currency check moves ahead of the
  gate, and `ensure_snapshot`'s docstring says "a named group whose terms refuse the stated use raises when it must
  be fetched".
- **E, in part:** a text passed to `_warn_once` is a warning and joins the pinned-text walk. Exception texts stay out
  of the walk, as confirmed for round 1's (8): a caller catches an exception by its type, not its words.
- **F:** `served_from` withholds when any reply leaves it unstated, so replies that are `local` and unstated give
  `None`, never `local`. **Flipped after the build (the pm, 2026-11-18):** when every reply states its place and
  they differ (`local` and `remote:<repo>`), the places are joined in sorted order, as before. Both served the answer,
  and a set of places is a true answer where a single release is not.
- **H:** a manifest entry with no size gets its own reason, which names the snapshot's publisher as the remedy,
  since a re-pull cannot clear it.
- **I:** the shared sequence proxy's log line says what happens: the build is retried at the next read, nothing is
  skipped.
- **G is as decided, so it gets a test, not a fix.** Ensembl is asked remotely by position only, never by rsID (RM431,
  ask 4), and a read bounded to one position cannot say every locus a multi-place rsID has. So the remote Ensembl
  link withholds the rsID's placement and the next link (ClinVar) is asked. A test pins this, and ENRICHER.md says it.
- **B becomes a measurement before the cut.** The bytes test compares 0.9 with itself offline, so it cannot fail.
  The lead runs 0.8.9 and 0.9 `enrich` online, cache warm, on the same five examples, compares the bytes (clocks
  aside), and the release record states the result. A test with golden outputs recorded from 0.8 is the next minor.

**Known issues in INTEGRATION_0_9, filed for 0.10:**

- **C:** during an Ensembl release transition, the group preflight and the provisioning can read different manifests.
  A group is then refused after the core was refreshed, not before any download. It is loud, never silent: a refusal,
  not wrong data. The fix is a release-transition matrix asserting that the preflight reads the manifest it
  provisions.
- With the proxy set and Hugging Face off, gene lookups on clinpgx, cpic, drug_labels and civic answer could-not-ask
  (the RM430 follow-up), until the registry reads `KEY_COMPARES` (its S36).

The trial rules end here. The pm reports how they went after the cut.

**At the cut, placed (the pm, 2026-11-19).**

1. **`rsid_genotype_reads_as_two_events` goes to 0.10, not 0.9.** RM449 said 0.9 would add it, but it was never in
   0.9's scope. It is a new closed-vocabulary code in format and compiler, an old-reader break, in a minor scoped to
   the enricher whose two review rounds are closed, so a code added now would ship unreviewed. 0.9 keeps the
   borrowed codes. The cut builder claims an RM for 0.10, which is schema work, and adds a dated line to RM449's
   history entry pointing at it. That RM first says which sentences the code would carry after RM453: with no row
   left unpositioned, `rsid_no_hosting_locus` may borrow nothing any more, and what is left is the fill of a mirrored
   site under `rsid_expanded_to_multiple_loci`.
2. **Residuals, on the lead's default, with these homes.** A "next minor" residual gets an RM in ROADMAP_0_10. A
   cleanup with no wrong answer is won't fix, with its reason. RM412 closes its built halves, and half 1's probe stays
   open. Four have homes already decided:
   - RM404's per-run wrap guard with the five `_held_by_one_run` imports, and RM430's three ClinVar asks made one
     query, are **patches on `main` after 0.9 merges**, as placed, not 0.10.
   - RM437's lock residual is **RM450**, the parked pull lock.
   - RM431's prebuilt `.duckdb` against the index pin is **won't fix**: the path is deprecated and retired at 1.0.
3. The two known issues (C, and the gene lanes with the proxy on and Hugging Face off) get RMs in ROADMAP_0_10.

**The rescope (the pm, 2026-11-26), on the maintainer's word:** "0.9, rescope with new RMs of the table and prepare a
plan". 0.9.0 was cut on `cut/v0.9.0` and never published, so the cut is redone, and 0.9 builds the leftovers of its own
build instead of shipping them as known issues and a string of patches.

*How the two trial rules went (the pm's report).* **Rule 2** held: both rounds were sorted with no blocker, and the
maintainer made it the rule for every minor (RELEASE_CYCLE.md step 5, 879f71ea). **Rule 1** kept 0.9 small, but sent
nine items from 0.9's own build to 0.10 or to patches after the merge, the "10 patches after that anyway" the
maintainer named. The rescope takes them back into 0.9; RELEASE_CYCLE.md's step 4 (an item that emerges joins the same
release) stands, and rule 1 is not carried into 0.10.

*Into 0.9.* All enricher, 0.9's theme, except RM465's predicate, which sits in the schema package beside 0.9's
`parse_release`. Every decision is made here, so the builds run without asking; the times are a Codex build plus the
lead's check, per item.

| Item | What 0.9 builds | Decided | About |
|---|---|---|---|
| RM458 | the group preflight reads the manifest the provisioning will provision | the release-transition matrix in the entry is the test | 2 h |
| RM461 | the proxy's `release_unreadable` carried into `RemoteRoute`; `_batch_column` splits on the column holding the most values; the pinned-text walk over every module | `lane_status` given a URL **refuses** it, naming the holder as the route for a remote status: status stays a local-disk question. If the walk needs a new registry of emitted texts, that part goes to 0.10 and the builder says so | 3 h |
| RM462 | one ClinVar request per `lookup_variant`, its reply read three times | | 1 h |
| RM463 | a public name for the per-run wrap, and an AST walk over every reader taking a `SequenceProxy`, shown failing first | | 1 h |
| RM464 | one publish body for the four lane commands, the part-count keys derived from `SnapshotRelease`, one read of `release.json` | the refused-rehearsal exit code is `cache rebuild --publish`'s | 2 h |
| RM465 | a public "is this a whole build" predicate beside `SnapshotRelease`; `parts_read` above `parts_total` refused | the publish gate calls it, no restated check | 1 h |
| RM466 | golden outputs recorded from 0.8.10 on a fixed offline input that reaches the Ensembl snapshot and the ClinVar witness as well as dbSNP and the sequence, clock fields named | | 2 h |
| RM454 | every keyed SQL compare in the enricher declared in `KEY_COMPARES`, one walk over them all | its home is 0.9's registry, so it lands with it rather than as a patch after | 2 h |
| RM467 | both halves as new options, defaults unchanged: the verify passes read only the rows this run wrote when asked; a run re-asks an explicit subject list and carries the rest byte for byte, `SubjectDrift` reporting what moved | a reason-driven selection (a declared correction's reach) waits for RM441's record in 0.10 | 4 h |

*Not into 0.9.* **RM460** goes to 0.10: a new code in format and compiler is an old-reader break, and 0.9 moves no
consumer's format floor. **RM459** goes to 0.10 and waits on the registry (its S36). **RM468** goes to 0.10 beside
RM399 and RM441: a persistent store of live answers is a design of its own (keys per source release, stored negatives,
per-host terms), not a leftover of 0.9's build. **RM457** is parked: its documentation half shipped, and it unparks when
a second consumer maps a parquet's row grain by hand or asks for the read. RM450 stays parked as it was.

*How it runs.*

1. The lead carries the cut's filing commit (`fee94a69`) onto `0.9`, with RM458, RM461 and RM465–RM467's entries in
   this file instead of ROADMAP_0_10, and RM462–RM464 likewise; the rest of `cut/v0.9.0` is redone at step 5. About
   30 minutes.
2. The lead runs the nine as one batch on Codex builders (LEAD.md, 27de1246), each in its worktree, and checks and
   merges each. About half a day of builds in parallel, and half a day of checks and merges.
3. **No third review round.** 0.9 has had its two, and the rule is two per minor; the lead's check at each merge is
   the review of what was added. The maintainer, on this exact point (2026-11-26): "I meant post-build audits...
   despite serious firepower and multi-model runs, these find some obscure bugs, yet the real ones crept into 0.8.x".
   Most of 0.8.8 to 0.8.10's fixes were found by a real run on a real module (the registry's, S158; the lead's on
   `pathogenic_clinvar`, RM451 and RM453), one class by a review round (RM455). So the gate that catches the real ones
   is step 4, and the cut waits on it. Anything a build turns up comes to the pm: a blocker is fixed in 0.9, the rest goes to 0.10.
4. The consumers' trial ([desk #370](https://github.com/winternewt/desk/issues/370)) goes on against the rescoped
   branch. The liaison tells the four consumers what was added; the two that reported are not asked again.
5. The cut is redone: the release record, INTEGRATION_0_9 (its known issues shrink to RM459), the CHANGELOG, the docs
   pass. About 2 hours. Then the maintainer's publish.

**Placed from the builds (the pm, 2026-11-26).** All nine merged; four findings, none a blocker. (1) RM461's
pinned-text walk over every module needs a registry of emitted texts (387 unregistered in 64 modules), so it goes to
0.10 as its own RM, named in RM461's Residuals. (2) RM462 sends two requests, not one: the proxy ANDs its columns, and a
combined Hugging Face read loses the row-group pruning; the third merge is won't fix for that reason. (3) opentargets'
reader still takes `parts_read >= parts_total` as whole: RM465's own class, so part of RM465 in 0.9, the reader calling
the predicate. (4) The gene-metrics pass indexes the snapshot answer by the authored spelling, so a mixed-case gene
reads `not_found` offline: RM454's own class, so part of RM454 in 0.9.

About a day and a half to the cut. 0.10 then holds RM399 + RM441 (S156), RM435, RM265, RM385, RM460 and RM468, and
RM459 once the registry moves; the pm sorts it again when it opens.

**Folded in at the redone cut (2026-11-26).** The redone cut's network gate found ClinVar-GKM's `v1/1.1` line
retired upstream; the pm placed the fix, RM470, in 0.9.1, and the maintainer folded it into 0.9.0 once it was built
("merge gkm into 0.9.0 if built, I'm ready to bublish"). Its record is in ROADMAP_HISTORY beside the rescope's nine.

**Earlier sizings, for the record.** The file opened on 2026-11-03, when the maintainer scoped 0.8 and sent "the rest"
to 0.9; the pm re-sized it on 2026-11-05 after the 0.8.0 cut ("'Auto-next minor' was a policy when we didn't have a
dedicated decision maker for this"), parking 22 items into ROADMAP.md. Everything here is **additive under Principles
3/4/8**; an item waiting on a version belongs in [ROADMAP_1_0.md](../ROADMAP_1_0.md).

**Three of these are not work at all.** RM84's own half shipped in the 0.6 PT2 batch, and only the consumer's
discovery half is open. RM67 is a documented divergence, numbered so it stays findable and does not get re-probed. The
Gherkin corpus (RM149) is **frozen**; its entry says why. All three stay here, so that a reader meets the reasoning
instead of re-deriving it.

Indexed in [RM_TOC.md](../RM_TOC.md), which is the complete list and the place to look an item up.

---

# 0.9's scope — the enricher reads its reference data wherever it lives

The enricher, plus one pure function in the schema package (`parse_release`, RM430 decision 6); the compiler does not move. Six items: RM430, RM431, RM437, RM443, RM404 and RM412's second half. The trial before the design is [REMOTE_READS_0_9](../probes/REMOTE_READS_0_9.md).

The six entries moved to [ROADMAP_HISTORY.md § The 0.9 minor](../ROADMAP_HISTORY.md#the-09-minor) at the cut, each with its `**Residuals**` line, and the rescope's nine after them.

## RM412 — how it was split: half 2 and the flag into 0.9, half 1's per-lane release probe parked

Kept here as RM28's split was kept in [ROADMAP_0_8.md](ROADMAP_0_8.md): the record of the decision that cut one item
in two. **The maintainer, 2026-11-07:** "inverted --rehearse-download flag in 0.9 along with all this
private-to-public debt". **The pm, 2026-11-16** ([desk #326](https://github.com/winternewt/desk/issues/326)): half 2
whole (the 0.8 line's private names made public) and, from half 1, the `--rehearse-download` flag the maintainer
named, into 0.9; half 1's per-lane probe of the source's newest release without its payload (a new `CacheLane`
field) parked. The shipped part's record is
[ROADMAP_HISTORY.md § RM412](../ROADMAP_HISTORY.md#rm412--a-dry-run-cannot-rehearse-the-download-and-the-08-lines-private-names-wait-for-their-public-ones);
the parked probe is open in [ROADMAP.md](../ROADMAP.md#active-items), with its unpark condition.
