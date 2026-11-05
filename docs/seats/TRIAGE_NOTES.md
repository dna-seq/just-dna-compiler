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
| RM338 (S125, which files under `logs/` ship) | `done`: shipped on `main` 2026-11-04 as a patch, released with 0.8.0. Before it: the lead's: taken into its plan and put to the maintainer, 2026-11-03 |
| push of `main` | the maintainer's: auto mode denies a seat's granted push (kit #238), so the maintainer pushes until it lands; the lead asked triage not to push its commits |
