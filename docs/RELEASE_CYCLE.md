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
