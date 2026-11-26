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
1. ✅ 0.9.0 released (2026-11-26, PyPI, tag v0.9.0): rescoped and rebuilt the same day, with the ClinVar-GKM fix and a
   `compat` extra for a CPU without AVX2. Merging 0.9 into main waits on longevity-loci's trial.
2. ✅ 0.8.10 released: the registry's four online rsIDs are accepted; its production upgrade can go ahead.
3. ✅ Rules from you: at most two review rounds per minor; builds go to Codex GPT-6.2 Astra, the lead merges and
   checks; even minors carry features and your decisions, odd minors fixes, a fix minor starting at 10-20 items.
4. ❓ 0.10, the next (even) minor, opened at the 0.9.0 publish: proposed scope and four forks on desk epic #466
   (#467-#470), each with a default; about 52-98 h of builds, 76-144 h with #467's three items.
5. ❓ One question on the maintainer's desk: linking the project's memory to its new folder name.
