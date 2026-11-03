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

**First pass**: S125–S127 answered and archived (`5e2cc18`), after committing the items alone
(`1ee5925`). Filed RM337–RM340.

## Items this seat owns

| Item | State |
|---|---|
| RM339 (S126, snapshot cache trusted when partial) | `unattended`: a patch, built in a worktree from `origin/main` once the maintainer is away |
| RM337 (S125, silent drop under `logs/`) | `unattended`, same |
| RM340 (S127, VRS warning names `verification.json`) | `unattended`, same |
| RM338 (S125, which files under `logs/` ship) | the lead's: taken into its plan and put to the maintainer, 2026-11-03 |
| push of `main` | the maintainer's: auto mode denies a seat's granted push (kit #238), so the maintainer pushes until it lands; the lead asked triage not to push its commits |
