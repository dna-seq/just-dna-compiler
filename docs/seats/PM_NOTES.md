# Pm notes

The pm's working state, rewritten to the present before each reset. Last rewritten 2026-11-03, at the
first seating.

## First seating (2026-11-03)

- **Tools against the kit's.** None of the repository's own machinery is this seat's. `.claude/rm-next.py`
  is used by whoever files an `RMn` (the lead files them; this seat proposes); `.claude/triage-state.py`,
  `triage-archive.py`, `watch-suggestions.sh`, `wake-on-suggestions.sh` and the `arm_triage_watcher.py`
  hook are triage's. Retired nothing, moved nothing, kept nothing on this seat's behalf.
- **Watchers**: `pm/watch.desk` and `pm/watch.brief` started at punch-in.
- **Avatar**: asked `agents-kit/admin` in `#agent-chat>avatars`; not set yet.

## The scope being sized: 0.8

What 0.8 holds, by where it stands. The list for the person is the proposal below; nothing in a scope
file has moved yet.

- **Built on the `0.8` branch, uncut**: PT1's RM241, RM258, RM263, RM272, RM275, RM278, RM283, RM288,
  RM300, RM308, RM313, and earlier RM256, RM257, RM259, RM260, RM262, RM264 (docs half). `main`'s
  roadmap still lists RM241, RM263 and RM308 as open; that heals at the next `main` → `0.8` sync.
- **Taken in by the maintainer, open**:
  - longevitymap v2: RM322–RM336, a priority (2026-11-03);
  - PacBio methylation: RM317–RM319 (2026-09-30);
  - RM303 (the snapshot layout as a model), RM253 (the repeat-count star allele), RM149 (the Gherkin
    corpus), RM248 (report schema, research);
  - RM188, the parity spine, with RM236–RM240.
- **Named by PT1 as the next round, not yet interviewed**: the indel-placement cluster, RM304 → RM267,
  RM270, RM292, RM305. These are the high-severity items of the release.
- **A minor, release undecided, on `main`'s roadmap**: RM265, RM266, RM281, RM282, RM284, RM286, RM287,
  RM294, RM296, RM298, RM302, RM306.
- **Parked on a corpus, a caller or the maintainer's word**: RM16, RM23, RM28, RM56, RM65, RM66, RM67
  (not work), RM68, RM84, RM122, RM164, RM181, RM261. They wait on a caller, not on 0.8.

**Proposal (for the person, hardest first):**

1. **How much of longevitymap v2 goes in.** In: RM323 (decided first), then RM322, RM324, RM325, RM326,
   RM327, RM328, RM331, RM332 and RM336. Deferred to the next minor: RM333 (a new lane whose licence is
   unprobed), RM334 and RM335 (two new table kinds for evidence v2 can leave out of 2.0.0), RM329 (its
   interim works under RM140) and RM330 (it leans on RM28's two-subject key).
2. **The order of the rounds.** PT2 is the indel cluster, as PT1 planned, and PT3 is longevitymap v2.
   The other way round puts the priority first and leaves five high-severity defects waiting.
3. **PacBio**: RM317 and RM319 in; RM318 (a new region table and a non-VCF pointer) deferred until a
   beneficiary's sample is in hand.
4. **The undecided minors**: in are RM294 and RM302 (v2 uses them), and RM265, RM266, RM284 and RM286
   (small). Deferred are RM281 and RM282 (source surveys), RM287 (a new lane), and RM296, RM298 and
   RM306 (no caller yet).
5. **Already in, unchanged**: RM303, RM253, RM149 and RM248 (research, ships nothing by default), and
   RM188's spine.
6. **Parked stays parked.** RM28 gained a fifth corpus entry (KL-VS); whether its gate has opened is a
   separate question for later.

## Open questions to the person

- The 0.8 sizing above: asked in chat 2026-11-03.
- `docs/STRATEGY.md`: not started; the first question is who the three packages serve.
- `docs/DREAMS.md` (the 2026-10-19 four-model dream) is this seat's file and is untracked. Adding it to
  `mkdocs.yml` (`not_in_nav`) is the lead's edit; until then the docs-nav test fails on it. Its ideas
  have no verdicts yet.

## Licensing, as it stands (noted, not yet raised)

- **The copyright holder.** The person, 2026-11-03: "Copyright is technically still mine (Newton Winter) as
  I still am a sole maintainer". `LICENSE` names "DNA-Seq" instead. Whether the line should name them,
  and what reopens it (a second maintainer, an organisation taking the work), is a point for a lawyer
  and for the person. Not raised yet.
- **The packages**: `LICENSE` is MIT, "Copyright (c) 2026 DNA-Seq", at the repository root only. None of
  the four `pyproject.toml` files declares `license`, and no package directory carries a licence file, so
  whether the wheels ship one is unchecked.
- **A source's terms that `SourceRow` cannot say**: the four axes in `docs/probes/ALPHAGENOME_ATLAS.md`
  §2.6 are holder eligibility, a no-training bar, revocability with a delete obligation, and
  notice-of-modification. None has an `RMn` yet.
- **`redistribution` is recorded and gated nowhere here**; the gate belongs to the registry, at publish
  (RM27).
- **Open items**: RM282 (the PGx lane has one licence class), RM286 (PharmVar's research-use-only
  restriction lives in `notice` prose), and RM333 (Open Targets' licence is unprobed).
- **Republishing encumbered corpora** (SNPedia, CC BY-NC-SA) is a use case the maintainer envisions; the
  NC and SA terms are recorded as data, never treated as a refusal.
