# Release cycle

How an `RMn` becomes a release. Stated by the maintainer on 2026-09-25, because the implicit version
of this had stopped working. The triage runbook ([CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md))
and the roadmap files follow this page; where one of them disagrees, this page is newer.

## Seats

Work runs in two or more Claude Code sessions, each with one purpose:

- the **triage seat**, unattended, which turns inbound `Sn` into replies and `RMn`;
- the **interactive coding seat**, which works with the maintainer.

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
  motivating `Sn`. File the residual first, with `.claude/rm-next.py`, and write the back-reference
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
used; a package that did not change keeps its version and is not built. Every intra-workspace floor a
changed package declares is raised to the release number, which is also each dependency's current
version, so `test_workspace_versions` holds unchanged. Worked example: after `v0.7.3` (format 0.7.1,
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
   decisions and implemented. Repeat until a review comes back clean. The triage seat monitors the
   branch meanwhile and processes whatever arrived during the build.
6. **Downstream pre-integration**: the consumer repos try the unreleased version (a second level of
   dogfooding). Their suggestions become items and the cycle returns to step 5, now also needing the
   pre-integrations to confirm.
7. At **zero active items**, the release is tagged and cut.

**The failure this sequence guards against** is an urgently needed feature pushed into a release that
has not been cut yet. It resets the cycle, and in earlier lines it produced the `PROPOSAL_*_PT2`/`PT3`
rounds and branches of around 400 commits that were hard to follow and maintain.

## Tic/tac after 1.0 (intended, not yet in force)

From 1.0 on, the intent is to alternate: **even minors are bugfix and stabilization only, odd minors
carry new features**, each with its own deferrals. It does not apply before 1.0, because feature parity
with competitors is needed now and moving it out of 0.8 would stall it. So 0.8 stays as its roadmap
file declares it: stabilization and competitor parity.

## Majors

Roughly as minors. None has been done yet, so the differences are not known.
