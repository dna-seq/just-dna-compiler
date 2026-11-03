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

**First pass**: S125–S127 answered and archived (`5e2cc18`), after committing the items alone
(`1ee5925`). Filed RM337–RM340.

## Items this seat owns

| Item | State |
|---|---|
| RM339 (S126, snapshot cache trusted when partial) | `unattended`: a patch, built in a worktree from `origin/main` once the maintainer is away. A built Ensembl cache carries a `.sha256` beside each parquet: check it as the completion record |
| RM337 (S125, silent drop under `logs/`) | `unattended`, same; the lead builds RM338 (decided `bf5dbde`) after it, both touch `_collect_logs` |
| RM340 (S127, VRS warning names `verification.json`) | `unattended`, same |
| RM338 (S125, which files under `logs/` ship) | the lead's: taken into its plan and put to the maintainer, 2026-11-03 |
| push of `main` | the maintainer's: auto mode denies a seat's granted push (kit #238), so the maintainer pushes until it lands; the lead asked triage not to push its commits |
