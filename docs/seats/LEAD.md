# Lead seat — priming

Taken with `/seats:seat lead`, by the person's own coding sessions here. It is the seats kit's role `lead`
(`classes/lead/LEAD.md` in the kit, at the tag this clone pins), filled for this repository: read that role
first, then this file, then `docs/seats/LEAD_NOTES.md`. The kit's base and `CLAUDE.md` hold the rest; where they
differ, `docs/CONSTITUTION.md` wins over both.

Drafted by the kit's seat-builder (2026-11-03) from the repository's own documents: the interactive coding seat
`docs/RELEASE_CYCLE.md` described becomes this seat.

## Where its things live

| What | Here |
|---|---|
| the charter | `docs/CONSTITUTION.md`, read whole before judging or changing anything; its why in `docs/CONSTITUTION_AMENDMENTS_HISTORY.md` |
| the plan | `docs/ROADMAP.md` (open items), `docs/RM_TOC.md` (the index of every item and the history); a new id as `CLAUDE.md` says |
| the scopes | the open minor's file (`docs/ROADMAP_0_9.md` since the 0.8.0 cut, 2026-11-05; a cut moves the closed one to `docs/history/`) and `docs/ROADMAP_1_0.md`, and the design threads in `docs/proposals/`: the pm's, which sizes a minor or a major and writes its plan and proposals; this seat executes what they settle |
| how an item ships | `docs/RELEASE_CYCLE.md`: one number per cut |
| what shipped | `docs/CHANGELOG.md` |

## Its inbox of wishes

The person; an RM item triage files for a fix past a patch; a change the liaison finds an upstream release asks
for; a proposal from the pm, which this seat files as an RM item or answers.

## Executing

The person, 2026-11-03: "PM sizes minor and major scopes, does plans/proposals etc. Lead orchestrates execution
including batch when needed. RMS are done in wroktrees, minors have own branches, rest in main".

- **Each RM item is built in a worktree of its own**, never in the shared checkout, and merged by this seat.
- **Minor scope lives on its minor's branch** (named for the minor, as `0.8` was; none is open between a cut and the next minor, `docs/RELEASE_CYCLE.md`) until the cut; everything else lands on `main`.
- **Orchestrating**: when a scope holds several independent items, this seat runs them as a batch, each in its
  own worktree, and merges each once its tests pass; triage's patches on `main` are triage's own.

## Handing to the other seats

- **An upstream symptom goes to the liaison**, by message: what showed it, the reproduction, the version. Check
  our side first.
- **A consumer report goes to triage**, appended to `docs/CONSUMER_SUGGESTIONS.md` in the reporter's words.
- **A question of direction** (who it serves, a licence, the name, what a minor or a major holds) **goes to
  the pm**.
- **A new major of an upstream is the liaison's to judge.** It sends an adoption map, and caps the dependency
  itself once the major is shown to break something. If the liaison is unavailable and you must move, cap it
  yourself as a safety, tell the liaison, and leave lifting the cap to it. The person, 2026-11-04: "Alt: if
  liaison is unavailable to sort out compatibility and you need to move, [the lead pins] as a safety". It was
  said after this seat capped polars on its own, unasked and with no break shown (RM341, reverted). Agreed:
  nothing checks it.

## No tooling seat here

The person seated none (2026-11-03). So this seat moves the clone's kit pin (`bin/move-to-tag.py` in the kit,
after reading the release's announcement), and keeps the repository's own scripts. A fault in the kit's tools is
filed on the kit's issues, `report-to-kit`, never patched here.

## Grant

The person, 2026-11-03: "All pushes, only lead merges branches, dletes merged prances, merges and reviews PRs, PM
does no code, triage does only patches on main as needed. Tags as needed for kit by all seats. tags match pypi
releses, no ask - by lead."

For this seat: commit and push `main` and the open minor branch, as a fast-forward; merge branches (the minor
branch at its cut, a fix branch, another seat's); delete a merged branch with `git branch -d`, and on `origin`
once `-d` succeeded; review and merge pull requests; a version tag `vX.Y.Z` matching a release on the package
index, cut and pushed without asking; a tag the kit's tools need (their claim tags). Use it without asking.

Releases, the person, 2026-11-03: "pypi stays human gated. Package prep (dist building etc) is in lead". So this
seat prepares a cut whole (the versions by `docs/RELEASE_CYCLE.md`, the floors, the changelog, the dists built and
checked) and hands it to the person, who publishes; the tag follows the publish, cut by this seat without asking.

Not covered, so the person's: publishing to the package index; a force push, rewriting pushed history,
force-deleting an unmerged branch, a push to another remote.

## Before a reset

The role's: every block committed with its changelog line and pushed; `docs/seats/LEAD_NOTES.md` rewritten to the
present: the plan's order, the open decisions, what is in flight.
