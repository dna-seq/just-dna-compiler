# Release cycle

How an `RMn` becomes a release. Stated by the maintainer on 2026-09-25, because the implicit version
of this had stopped working. The triage runbook ([CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md))
and the roadmap files follow this page; where one of them disagrees, this page is newer.

## Seats

Work runs in Claude Code sessions, each holding one seat for its whole run, on the seats kit since
2026-11-03. [seats/README.md](seats/README.md) lists the four with their primings. For a release:

- the **pm** sizes each minor and major scope: what goes in, its plan and its proposals
  ([ROADMAP_0_9.md](ROADMAP_0_9.md), [ROADMAP_1_0.md](ROADMAP_1_0.md), `proposals/`). It writes no code;
- the **lead** executes what the pm settled, working with the maintainer: each `RMn` in a worktree of its
  own, a minor's scope on that minor's branch, everything else on `main`. It merges, prepares a cut
  whole, and tags it once the maintainer has published (publishing stays theirs);
- **triage** turns inbound `Sn` into replies and `RMn`, and ships the patch fixes on `main`;
- the **liaison** reads each upstream release against what the code uses.

A seat does not take another seat's work or offer to.

## How an item gets its version

1. Triage files the item as **open**.
2. Its release is decided **by omission**. Every patch-class item that is not blocked goes into the
   next patch batch on `main` by default, and nobody asks.
3. An item with an undecided part gets an **interview with the maintainer** before a version is
   assigned to it. Legality under the Constitution still sizes the release; the interview settles the
   design question, not the class.

## Closing an item

An entry that moves to [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) states what it did **not** fix, in one
`**Residuals**` paragraph after its Status/Owner/Motivating block:

```
**Residuals** none
**Residuals** RM272 · won't fix — the beta endpoint 301s and answers no bare rsID
```

Items are separated by ` · `. Each one is an `RMn` or `won't fix — <reason>`, and nothing else:

- **An `RMn` counts only if that item's own entry mentions this one**, by number or by this entry's
  motivating `Sn`. File the residual first, with the seats kit's `item-next.py`, and write the back-reference
  into it. Pointing at an item that is merely open is not enough, and pointing at one that is closed
  never was. RM38 pointed at RM27 and RM50's tracker line pointed at RM50; both targets closed without
  a word about what pointed at them.
- **An idea-book bullet, a parked list, a probe, a code comment or a reference doc is not a home.**
  RM31's residual pointed at the parked "enricher co-authoring" bullet and at a workaround no consumer
  document carried, and a defect nobody chose to leave went unowned for three minors.
- **"Filed" means an `RMn` in the same sentence.** RM192 said *"filed rather than improvised"* and
  filed nothing.
- **`won't fix` needs a reason of at least five words**, and beyond that it is reviewed prose. Decided
  2026-09-27: a longer minimum, or a required citation, would make the escape hatch cost more than
  filing the RM and push authors toward vaguer residuals rather than none.

`schema/tests/test_closure_residuals.py` enforces this. Entries closed before the rule are listed in
`schema/tests/data/residuals_legacy.txt`, which is asserted exact, so it can only shrink: give a legacy
entry its line and delete it from the list in the same commit. The why is
[POSTMORTEM_2026_09_27.md](POSTMORTEM_2026_09_27.md).

**A cut rewrites the lead paragraph of every CHANGELOG heading that names its version**, to say it was
cut and tagged. A reply never cites a heading as *the record* of a state that will change; it cites
the tag. The 0.7.0 heading said *"being built … not yet cut"* for a month after `v0.7.0`, while six
replies (S75–S80) pointed consumers at it. `test_closure_residuals.py` refuses a present-tense uncut
claim under any version that has a release record or is older than the newest versioned heading.

## Patches

Patches are built and cut on `main`. A patch carries however many fixes the latest wave of usage
produced; there is no count to reach. Patches keep coming until the minor roadmap holds enough to be
worth doing.

**A commit on `main` is patch scope only.** Anything that sizes as a minor under Principle 3 (a new
field, table, public function, method or CLI surface) never lands on `main`, not even uncut: it goes on
the open minor branch (`0.8` today), or it is filed and waits for one. Everything on `main` must be
cuttable as a patch at any moment, because the next patch is cut from whatever `main` holds.

This was implicit until 2026-09-25 and broke the day before: the triage seat committed RM256, RM257,
RM259, RM260 and RM262 to `main` as "shipped, uncut, sizes as a minor", which left `main` unable to cut
a patch. 0.7.2 then had to be cut off a revived `0.7` branch, and RM264 had no line to ship on. `main`
was rebuilt from `v0.7.2` with the patch-scope commits only, and the five moved to the `0.8` branch.

**One number per cut (from `v0.7.4`).** A cut's tag names the release, `vX.Y.Z`, and **every package
that changed since the previous tag takes that same number**, skipping whatever its own line never
used; a package that did not change keeps its version and is not built. Every intra-workspace floor
names its dependency's current version, as `test_workspace_versions` already requires: the release
number for a dependency that moved in this cut, its old version for one that did not. Worked example: after `v0.7.3` (format 0.7.1,
compiler 0.7.2, enricher 0.7.3), a cut changing format and enricher is `v0.7.4` with format **0.7.4**,
enricher **0.7.4**, compiler staying 0.7.2, and enricher's floors `format>=0.7.4, compiler>=0.7.2`.
A skipped number is legal SemVer and legal on PyPI. The gain is that the tag and every moved package
say one number, so "which versions are in this release" has one answer. `v0.7.3` was the last cut that
bumped each package by one on its own line (format 0.7.1, compiler 0.7.2, enricher 0.7.3), already
published when the rule was set on 2026-09-27.

**The item counts in the triage runbook's §4 are a "worth doing" lamp, not a start pistol.** They are
reported, never asked about, and they never freeze scope.

## Minors

1. **Interview** on the planned items: some are deferred, some go into scope.
2. **Proposal**: a plan with detailed implementation notes per item and every decision already made,
   so the build can run without asking.
3. **Branch**, then **batch implementation**, mostly unattended.
4. **Second pass**: items that emerge during implementation join the same release automatically,
   unless they need a major.
5. **Review wave and dogfooding wave.** What they find becomes new items, interviewed on their
   decisions and implemented. Repeat until the pm finds no new blocker (below). The triage seat monitors the
   branch meanwhile and processes whatever arrived during the build.
   - **A review reports error classes, never single instances** (the maintainer, 2026-11-04: "so that the
     same error in a second module is not found as a separate item"). Each finding names the rule broken,
     lists every instance across packages, tables, lanes and clients, and names the mechanism that catches
     the whole class (a registry-walking equality test, one shared helper, an AST guard). One item per
     class, fixed as a class.
   - **The pm triages every review's classes before any fix is built** (the maintainer, 2026-11-05): each class
     is placed as *blocks the cut*, or deferred to the next minor. A defect the release itself introduced on a
     surface consumers gate on (a strict refusal of a valid module, a round-trip loss) blocks; a defect that was
     already there is weighed by how often a real run hits it. **A built branch is never deferred**: "if branch is
     built, what's the sense to defer then? Defer unbuilt items."
   - **Deferred items ship as known issues**, listed in the release's INTEGRATION file and its CHANGELOG cut entry,
     each with its `RMn` in the next minor's roadmap. **The review loop ends when the pm finds no new blocker**
     ("If PM finds no new blockers we ship"), not when a review comes back with nothing at all. The next review
     runs on the merged candidate after the blockers' fixes land, and gets the known issues so it does not
     report them again.
   - **A builder's finding outside its unit is filed as a class the same way**, and checked against the
     review's classes before filing, so one defect is never two items.
   - **Changed charter wording is shown to the maintainer, old to new, before the cut.** Deciding that an
     amendment happens is not approving its sentences; the acceptance is recorded in
     CONSTITUTION_AMENDMENTS_HISTORY.md.
6. **Downstream pre-integration**: the consumer repos try the unreleased version (a second level of
   dogfooding). Their suggestions become items and the cycle returns to step 5, now also needing the
   pre-integrations to confirm. Skipping it is the maintainer's call only, and the skip is recorded in the
   release's CHANGELOG cut entry and its INTEGRATION file.
7. **Release-gate sweep**: the release's INTEGRATION file covers every new warning code, manifest field,
   parquet and verify reason; every new code has a `features/` scenario; every closed item states its
   `**Residuals**`; the docs site builds under `--strict`.
8. **Docs pass** (added 2026-11-04): every command in the user guides (GETTING_STARTED, COMPILING,
   CONSUMING, ENRICHING, index) is re-run against the release branch, and the release's new surfaces are
   added to them with commands that were run. The doc map in `CLAUDE.md` and the docs-site navigation are
   checked against the files. Builders update the reference docs for their own change; nobody else
   re-reads the user guides, so this step does.
9. **The cut**, at **zero active items**: versions and floors, the lock, the CHANGELOG cut heading, the
   release record (measured by sweeps; a toolchain move is declared only from a sweep that holds the
   compiler fixed), the INTEGRATION file finished, the branch merged into `main`, the dists built and
   checked. Publishing stays the maintainer's; step 10 follows the publish.
10. **After the publish** (added 2026-11-05: at 0.8.0 the tag, the GitHub release and the docs refresh were
    all missing hours after the publish). Once the maintainer has published, the lead does all three
    without asking:
    - **The tag**: `vX.Y.Z` on the cut commit on `main`, annotated, naming each package's version
      (`just-dna-format 0.8.0, just-dna-compiler 0.8.0, just-dna-enricher 0.8.0`), and pushed.
    - **The GitHub release** on that tag (`gh release create vX.Y.Z --title "X.Y.Z — <one line>"
      --notes-file …`). The lead writes the notes: what the release lets a module or a consumer do, in plain
      words; what a consumer must do at the boundary (pins, caches, re-derivation, which digests move); a
      pointer to the INTEGRATION file and the CHANGELOG; the known issues. Every claim is checked against
      the code, not copied from an entry's title. The 0.7.0 release is the model.
    - **The docs refresh**, by a subagent on a branch off `main`, merged by the lead. It moves the
      previous release's INTEGRATION file into `docs/history/` with its links and the site navigation, and
      refreshes every live sentence about the present (the current release, the current upgrade note, the
      open minor) in README, the user guides, the tier references and `CLAUDE.md`'s doc map. Dated
      records stay as they are. The strict docs build and the doc-link tests run before the merge. The
      docs site publishes from `main` on every push (`.github/workflows/pages.yml`), so the merge is what
      updates the site.

**The failure this sequence guards against** is an urgently needed feature pushed into a release that
has not been cut yet. It resets the cycle, and in earlier lines it produced the `PROPOSAL_*_PT2`/`PT3`
rounds and branches of around 400 commits that were hard to follow and maintain.

## Tic/tac after 1.0 (intended, not yet in force)

From 1.0 on, the intent is to alternate: **even minors are bugfix and stabilization only, odd minors
carry new features**, each with its own deferrals. It does not apply before 1.0, because feature parity
with competitors is needed now. 0.8 is as its roadmap file declares it. Since 2026-11-03 that is the
work already built, the chosen fixes and longevitymap v2. Competitor parity moved to 0.9 with the rest.

## Majors

Roughly as minors. None has been done yet, so the differences are not known.
