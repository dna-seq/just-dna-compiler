**Where it stands** (2026-11-26). The current release is **0.8.10** (all three packages, on PyPI since 2026-11-26). 0.9 is
rescoped: it builds its own leftovers before its cut is redone, and 0.10 is six small items right after.

**Headline results**
- ✅ 0.8.8, released: a cache pull no longer keeps old ClinVar files under a new release's label, and the caches
  already wrong are repaired by the next pull. Full suite 7,446 passed.
- ✅ 0.8.7, released: the AlphaGenome licence notices now say what Google's terms say, and the rsID recovery no longer
  claims more than dbSNP records. Full suite 7,416 passed.
- ✅ 0.8.6, released: a re-derivation that drops an rsID now says so; the upgrade guide says the Ensembl snapshot
  carries only its core. Full suite 7,408 passed.
- ✅ Nothing already published moves: the registry measured all 24 production modules for the 0.8.5 rsID fix and
  found 0 rows it changes.
- ✅ AlphaGenome 2's predicted methylation, second trial: at 42 strong blood methylation variants its predicted shift
  was 27 times that at 84 matched non-variants, and 28 of 31 directions agreed. One cohort, no replication.
- ✅ Scoped, 2026-11-16: 0.9 is six items in the enricher (plus one small parsing function in the schema package); 0.10 is five small schema items; methylation follows, undated
  until the PacBio samples are in hand; seven other items wait, each with what brings it back.
- ✅ Decided for 0.9: the enricher reads a snapshot from local disk first, then the registry's proxy, then Hugging Face.
- ✅ 0.9 tries two rules for shorter releases: work found mid-build waits for the next minor, and review stops after two
  rounds, except for a defect the release itself introduced.
- ✅ Measured: a lookup takes 0.02-0.1 s from disk, 0.2-0.4 s through the registry's proxy, 2-29 s from Hugging Face,
  where an anonymous client also runs out of requests after a few large lookups.

**Next**
1. ⏳ 0.9.0 — rescoped and rebuilt the same day: nine of its own leftovers built on Codex builders and merged, full
   suite 8,338 passed, the cut redone with real runs over the reference modules as its gate. Waiting on your publish
   (desk #461). RM470 folded in on your word (ClinVar-GKM retired the data line our snapshot builder reads): the lead
   rebuilds and checks the dists, then hands you the publish command.
2. ✅ 0.8.10 released: the registry's four online rsIDs are accepted; its production upgrade can go ahead.
3. ✅ Two rules from you: at most two review rounds per minor; builds go to Codex GPT-6.2 Astra, the lead merges and checks.
4. ❓ Three items you placed in 0.9 by name were parked by the small cut: parked, a 0.11, or 0.10 (desk #347).
5. ❓ One question on the maintainer's desk: linking the project's memory to its new folder name.
