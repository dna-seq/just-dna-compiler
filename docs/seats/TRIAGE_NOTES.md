# Triage seat — notes

State the seat's last holder left. The inbox is the seat's real state (`triage-state.py` fingerprints it);
this file holds only what the inbox cannot say.

## First seating, 2026-11-03

**Tools, against the kit's** (first-seating handout, step 1):

- **Retire**: `.claude/wake-on-suggestions.sh`, its prompt hook, and `.claude/watch-suggestions.sh`. The
  kit's `[seat.triage.watch.inbox]` does the same job and fired on the real S125–S127 edit at seating.
  Retired by the lead in `8c010c0` (2026-11-03). `CONSUMER_TRIAGE_LOOP.md` §1 and its Sync section are
  this seat's to keep from there.
- **Keep**: `.claude/triage-state.py`, `.claude/triage-archive.py`, `.claude/rm-next.py`. The priming keeps
  the clone's copies until the lead retires them. The kit's ledger and the clone's agreed at seating
  (both `--next` → S128), and this pass ran the kit's ledger and archiver, the clone's `rm-next.py`.
- **Keep, runbook's**: the gist sync in `docs/CONSUMER_TRIAGE_LOOP.md`. Checked at seating: revision
  `96b69533…`, the recorded baseline, so nothing to adopt.

**Consolidated 2026-11-04** (`62542f3`, on the maintainer's ask): the kit's ledger and archiver are the
logic, a strict superset of the clone's and the gist's. `.claude/triage-state.py` and `triage-archive.py`
are byte-identical copies kept for CI, guarded by a parity test; re-copy them when the pin moves. The
gist sync is retired. `.claude/rm-next.py` stays until kit #242 and #243 land. Kit issues filed, by
priority: #241 (high, bare `--next` answers S1), #242 (high, paths only from the environment;
`item-next.py` bare reserves into `docs/ROADMAP.md`), #243 (medium, index rows own no id), #244 (low,
malformed marker sha), #245 (low, link-checker gotcha; notes-file wording).

**Kit v0.1.118 closed all five (2026-11-04, `e8c68b3`).** The scripts read `.blueprints.toml` `[triage]`;
`.claude/` re-took the kit's three files (`triage_conf.py` is new); they are outside ruff, since formatting
them would be the drift. `rm-next.py` still stays: the fix counts entry rows only in the index file, and
`RM_TOC` is paged, so filed as kit #247 (medium). A shell started before `/reload-plugins` still runs the
old kit, and the parity test fails there on purpose.

**Kit v0.1.120 closed #247 (2026-11-04)**: `item-next.py` counts a paged index's page rows. Measured: the
same id set as `.claude/rm-next.py` and the same next number (RM345), so the local allocator and its
tests are removed and every live reference names the kit's. Triage's consolidation is complete: all
three scripts are the kit's, two of them copied into `.claude/` for CI.

**First pass**: S125–S127 answered and archived (`5e2cc18`), after committing the items alone
(`1ee5925`). Filed RM337–RM340.

**Sign every commit `Seat: just-dna-compiler/triage`** (a trailer line above `Co-Authored-By`). The
`inbox-commits` watcher is the kit's `watch-remote.sh --path`, which drops a commit carrying the seat's own
`Seat:` line; without it, triage's own S129 commits woke triage twice (2026-11-04).

## Routes with other repos' triage seats

- **just-dna-registry/triage** (agreed 2026-11-04): a registry consumer item whose fix belongs to format,
  compiler or enricher arrives in `docs/CONSUMER_SUGGESTIONS.md`, restated, with an `Sn` from this ledger
  and a message naming it. An item this seat moves back to the registry gets a message to that seat
  naming it, so neither inbox holds the other's.

- **longevity-loci/liaison** (added to triage's `wake_from` 2026-11-05, `a8262397`, the maintainer's "yes add"):
  a downstream on just-dna-enricher 0.7.3 that files into `docs/CONSUMER_SUGGESTIONS.md` and then messages
  this seat. Same handling as any `Sn`: commit it on arrival, then triage.

- **just-module-creator/liaison** (added to triage's `wake_from` 2026-11-07, `8de1fa80`, on the maintainer's word):
  the MCP authoring plugin's seat, which files the plugin's consumer suggestions into
  `docs/CONSUMER_SUGGESTIONS.md` and messages this seat. Same handling as any `Sn`: commit it on arrival, then triage.

## Items this seat owns

| Item | State |
|---|---|
| RM339 (S126, snapshot cache trusted when partial) | `done`: `74e0e87`, unpushed when built (the pm pushed it in `e2fed68`). A pull writes `pull-record.json` before its first download |
| RM337 (S125, silent drop under `logs/`) | `done`: shipped in the 0.8.0 cut (2026-11-05; `main` e97339a3, `0.8` edf2661c). Before it: handed on: it needs a new warning code, so it is a minor (`172a215`, sized wrong at filing). The pm placed it, now in `ROADMAP_0_8.md` (`f3377a6`) |
| RM340 (S127, VRS warning names `verification.json`) | `done`: `280813b`, on `origin/main` (the pm's fast-forward pushes carried it) |
| RM371 (S128, tenacity `initial=` deprecated at every enricher import) | `done`: `742b1ff`, on `origin/main`. 18 sites renamed `multiplier=`, floor `tenacity>=9.2.1`, AST guard; `0.8` has 21 sites, so the guard goes red at the merge until the lead renames the 3 extra |
| RM377 (S129, strict-only refusals told apart by wording) | `done`: `2a4655e7`, on `origin/main`. Two phrases published in COMPILER.md, read by `test_strict_refusal_phrases.py`; doc + test only, so it passes unchanged on `origin/0.8`. Beside it: on `main`, `validate --strict` with resolution off passes what `compile` refuses; `0.8` closes it as RM367, so no item |
| RM378 (S129, coded errors with an `errors_summary`) | **parked** by the pm after the 0.8.0 cut (`6934fd3e`): unparks when a consumer needs to tell apart refusals RM377's two phrases do not cover, when a scope the maintainer highlights touches it, or when the roadmap is empty; the registry was told. Before it: handed on: a minor, filed `0b99facb`; the pm placed it in **0.9** (`f8b595d6`): 0.8 is near its cut, and the code vocabulary is permanent and has two open questions. The registry's liaison was told its interim (the RM377 phrases) holds through 0.8 |
| RM384 (S130, Ensembl repo id has no public name on 0.8) | `done`: shipped in the 0.8.0 cut (2026-11-05; `main` e97339a3, `0.8` edf2661c). Before it: handed on: a minor, filed `5c8b82e8`; the pm placed it in **0.8** as RM372's tail (`81e7dde2`); the lead builds it. The pm's line: a fix completing a decided 0.8 item goes in, a new capability (RM378) goes to 0.9 |
| RM396 (S131, six paced clients keep interval or gate private) | handed on: a minor, filed `88dea86e`, answered `9a0aa546`; pushed. **Parked** by the pm (`a617b4f3`): no automatic next minor; it unparks when a host needs a second client's pace or `clingen_allele`'s, when a private name the registry reads is renamed, or when the roadmap is empty. The registry's interim reads `pgs._REQUEST_INTERVAL`; the entry keeps the private names as aliases |
| RM398 (S132, no placement witness at dbSNP scale) | `done`: **published**: enricher 0.8.1 on PyPI, tag `v0.8.1` on 6330f908 (2026-11-07). shipped in the v0.8.1 recut (6330f908, pushed, 2026-11-07; full suite 7304 passed). Before it: `19b7519c` + `38602b34` on local `main`, unpushed (2026-11-07), triage-built on the lead's split for the 0.8.1 recut (the lead built RM407). dbSNP's SPDI from the merge check's record replaces the REST witness; `_RecordedEutils` serves the merge check the same records; `_UPSTREAM_OF` keeps dbSNP self-consistent with the snapshot. Measured on the reference examples' 169 snapshot indels: no disagreement from either witness. The registry's replay is RM406's re-measure. A flaky literature regex-timeout test seen under load was reported to the lead |
| RM399 (S132, a release cannot declare a moved snapshot) | handed on: a minor, filed `e56c1f2c`. The pm placed it in **0.9** (`6047e082`), a field beside the five axes first. P3's "never silently" is met in prose only for RM267's correction through RM372 |
| RM400 (S132, REST rung keeps patch/alt-contig loci) | `done`: **published**: enricher 0.8.1 on PyPI, tag `v0.8.1` on 6330f908 (2026-11-07). shipped in the v0.8.1 cut (enricher 0.8.1 only, 2026-11-07; `main` 0ce3ca50, cut commit f38d6771, pushed). Before it: `10213ff0` on local `main`, unpushed (2026-11-07), both halves, triage-built on the lead's hand-over. REST drops off-primary mappings, counted; a re-derivation leaves recorded ones out of the comparison and counts them (the pm's default, no new word). Adds a 0.8 known-issue line in INTEGRATION_0_8 §4 |
| RM401 (S133, live Ensembl and the REST witness ask one rsID per GET) | `done`: **published**: enricher 0.8.1 on PyPI, tag `v0.8.1` on 6330f908 (2026-11-07). shipped in the v0.8.1 cut (enricher 0.8.1 only, 2026-11-07; `main` 0ce3ca50, cut commit f38d6771, pushed). Before it: `6837e66a` on local `main`, unpushed (2026-11-07), triage-built on the lead's hand-over. Probe first: a 200 batch leaves out an rsID with no record (an all-unknown batch is `200 {}`) and keys a merged one by its current id (the asked one in `synonyms`). Matched by name then one synonym; anything else asked by GET; a failed batch is could-not-ask; `batch_size` 20 (1 = off), `batch_timeout` 120 s. Full suite at it: 7273 passed, 1 failed, a pre-existing failure fixed in `b12c77c0` (the cross-tier floor check could not see a package; red since the 0.8.0 cut). Names made private by the pm's ruling (option 2, 2026-11-07) in `b6ea746a`: batch size 20 and timeout 120 s are fixed private constants, `ask_live_witness` keeps 0.8.0's signature; 0.9 publishes them with RM404 |
| RM402 (S133, a snapshot-rejected rsID asked again of live Ensembl) | handed on: a patch; **waits** (the pm, `d61974da`) until RM401 ships and a re-measure; if what is left is small it closes as superseded by RM401. Skip at equal releases; the registry's 38 are strand-flipped genotypes, which `enrich` already names |
| RM403 (S133, retries leave no log line) | `done`: **published**: enricher 0.8.1 on PyPI, tag `v0.8.1` on 6330f908 (2026-11-07). shipped in the v0.8.1 cut (enricher 0.8.1 only, 2026-11-07; `main` 0ce3ca50, cut commit f38d6771, pushed). Before it: `4a07f4ec` on local `main`, unpushed (2026-11-07). Every `@retry` names `net.log_retry`/`net.log_give_up` (WARNING); an AST walk guards it. Enricher suite green at it (3505 passed). Hooks renamed `_log_retry`/`_log_give_up` in `b6ea746a` (the same ruling) |
| RM404 (S133, `enrich()` builds its own eutils client and sequence proxy) | the registry asked (2026-11-07, 638423336) for a 0.8.x patch; triage forwarded it, and the pm ruled it **stays in 0.9** (a new public parameter never lands on `main`) and files the patch half as RM418: one process-wide private NCBI pacing gate, so parallel `enrich()` calls in one process share a budget with no client passed in. The pm answered the registry directly. Before it: handed on: a minor; the pm placed it in **0.9**, built with RM385 (same `SequenceProxy` seam, `d61974da`). The pm read RM396's unpark condition as not met (reading by public name, not handing clients in); ga4gh's missing timeout is upstream |
| RM405 (S133, offline floor in the snapshot's unindexed lookups) | handed on; **parked** by the pm (`d61974da`): about 10 s a module, unreported; the real fix is the snapshot builder's layout. Two of the four queries are positional, not by rsID as reported |
| RM414 (S136, repeat-count warnings name RUC/CIRUC over a declared source_field) | `done`: **published**: format, compiler and enricher 0.8.2 on PyPI, tag `v0.8.2` on b98f7e9c (2026-11-08). Before it: `89610c38` on local `main`, unpushed (2026-11-07), triage-built, a patch. Both findings name the declared field and speak conditionally when it is not VCF's own; schema+compiler suites green (3755) |
| RM415 (S137, bins_ungrounded says no bin pmid beside a cited bin) | `done`: **published**: format, compiler and enricher 0.8.2 on PyPI, tag `v0.8.2` on b98f7e9c (2026-11-08). Before it: `89610c38` on local `main`, unpushed (2026-11-07), triage-built, a patch. The clause is chosen by whether any bin cites |
| RM422 (S138, a `resolution.csv` row for a removed variant compiles silently) | `done`: shipped in the v0.8.3 cut (format, compiler, enricher 0.8.3; cut commit `725eb2bb`, pushed, 2026-11-09; dists built, publish pending). Before it: `61a2056d` on `main`, pushed by the lead (`7811c23b`, 2026-11-09), triage-built on the lead's hand-over: one more `derived_row_orphan` arm in `validate_spec` (pre-flight only, the compile inherits it), subjects = authored locus tables + study proxies, a warning in both modes. Compiler suite green (2472), schema/docs 1364 |
| RM423 (S139, carried check records re-signed over moved bytes) | `done`: shipped in the v0.8.3 cut (`725eb2bb`, pushed, 2026-11-09), built by the lead's builder: `b74d4f01`, closed `5df02d81`. Over moved bytes `merge_records` keeps this run's records only and logs each dropped check. Residual RM424 (candidate 2, a per-record binding) filed, a minor, parked by the pm |
| RM425 (S140, `effect_size`'s description says aggregated over the tracks) | `done`: `290acb51` on `main`, pushed by the lead (`750771af`, 2026-11-09), uncut (the patch after 0.8.3), triage-built on the lead's hand-over (638645150). The description names the single strongest track, sign kept, and the disagreement with `effect_direction`; a test ties it to `_summarise`. Enricher expression tests green (29); schema suite green but for `DREAMS.md` missing from the docs nav (an untracked file not triage's) |
| RM426 (S141, `GeneLocusConflict`'s message guesses the rsID is the invented half) | `done`: `249c18d3` on `main`, pushed by the lead (`406774a1`, 2026-11-09), uncut (the patch after 0.8.3), triage-built on the lead's hand-over (638650546); sized by the pm `6785a1d8` (patch, urgent, fact sentence byte for byte). Closing sentence names both readings and the lookup; test on S141's row; ENRICHER + CHANGELOG declare it. Identifier tests 40 green. Ask 2 declined by the pm, back only through a new `Sn` |
| RM427 (S142, both ClinVar-pass skip lines name `clinvar pull`, which no app registers) | `done`: landed and pushed by the lead as `e7fa81d6` (cherry-picked from `6c0a9c57`), uncut (the patch after 0.8.3). Sized by the pm `cadce134`: asks 1+2 one patch, ask 3 declined (Residuals won't fix). Wording → `cache pull --only clinvar` / `clinvar build`, pinned; `test_quoted_commands.py` walks every quoted group command, proved red first. Worktree `scratchpad/rm427` unlocked; branch `triage/rm427` is cherry-picked, so `-d` refuses and its `-D` is the maintainer's |
| RM428 (S143, the GWAS pass sends `size=1000` and the Catalog v2 now refuses anything above 500 with 400; 0.7.3's v1 answers 410) | sized by the pm `b1f0bc32`: asks 1-3 one patch, `urgent`, ~30 min, for 0.8.4 with RM425-427 (500; the opt-in network test; ask 3 narrow: a 400 on the first request only, retried once with no `size`, one warning per run naming the refused size). Ask 4 on the desk, #252. `done` on main: the lead built asks 1-3 as `f0433de5`, for the 0.8.4 cut. Ask 4 declined by the maintainer on #252 ("no for 0.7.4"), so it closes as won't fix. The consumer liaison was told (639317821). Ask 1 `_PAGE_SIZE = 500`, a patch for after 0.8.3, `unattended` once sized. Asks 2 (opt-in network test) and 3 (a smaller page on a 400, or v2's default of 20) are the pm's to size. Ask 4 (`v0.7.4` off `v0.7.3` with RM354 + ask 1) is a release-line decision for the pm and lead to put to the person. Reproduced live 2026-11-10 22:58 UTC: 500→200, 501/1000→400 |
| RM429 (S144, `GwasResult` carries no `size_refusals`; only a log line) | parked by the pm (`29955a86`): unparks on a counted refusal or a consumer that cannot inject the client. Workaround given: inject `client=` and read `GwasCatalogClient.size_refusals`, a public field RM428 added on main (flagged to the pm) |
| RM430 (S145 asks 1-3, snapshot readers take a remote `hf://` root) | parked on desk #261 (`29955a86`): the maintainer names a 0.9 zone; the pm recommends asks 1-3. The registry's next minor waits on it. Charter: format's `read_release` cannot fetch, so the remote read is the enricher's |
| RM431 (S145 asks 4-7, keyed readers, an rsID index for Ensembl) | parked (`29955a86`): ask 4 goes with RM405; asks 5-7 unpark on a measured slow remote lookup |
| RM432 (S146, `lookup_snapshot` / `civic_snapshot_rows` read an unreadable reference as empty) | `done` on main: the lead built it as `ac3f1bcc` (sized `29955a86`), for the patch after 0.8.4. Both readers raise `FileNotFoundError`; the three callers report could-not-read. Reporter told |
| RM434 (S147, longevity-loci by handoff: no `stat_significance` level states a threshold) | `done` on main: the lead built it as `5e124dfb` (sized `1a976b3f`), for 0.8.5 with RM432. `nominal` declined, not parked. Reporter told |
| RM435 (S148, longevity-loci: no study-level direction without an effect size) | moved to ROADMAP_0_9.md by the pm (`1a976b3f`), a longevitymap v2 leftover, in `GwasEffectRow`'s shape only |
| RM436 (S149, just-dna-lite: `tenacity>=9.2.1` vs google-genai's `<9.2.0`) | sized by the pm (`d01b70cc`): candidate 1, the shim, a patch, `urgent`, in 0.8.5 (keyword by the installed signature, in one place; the floor proved on both sides; RM371's sentence corrected). The lead builds it |
| RM437 (S150, just-dna-lite: no route to the Ensembl `groups/`) | into 0.9 (`9fcc6572`); its doc half is a patch now: INTEGRATION_0_8 § 3 says the lane carries the core only and why a hand-fetched group is unsafe |
| RM438 (S151, just-dna-lite: legacy `resolve_variants` back-fills the first rsID at a position, CYP2D6*4 wrong, reproduced) | sized by the pm (`9fcc6572`): a patch, next on main, into 0.8.5 if it lands before the cut (the lead's call). The back-fill asks the enrich path's hosting rule through one shared function and withholds with `rsid_ambiguous`; pinned on S151's four rows |
| S133 ask 5 (lower the retry floor) | declined: reopens if, after RM401 ships and the re-measure, a host still measures retries as the cost (rekeyed by the pm from "RM401 and RM402"; the registry told) |
| RM338 (S125, which files under `logs/` ship) | `done`: shipped on `main` 2026-11-04 as a patch, released with 0.8.0. Before it: the lead's: taken into its plan and put to the maintainer, 2026-11-03 |
| push of `main` | the maintainer's: auto mode denies a seat's granted push (kit #238), so the maintainer pushes until it lands; the lead asked triage not to push its commits |
