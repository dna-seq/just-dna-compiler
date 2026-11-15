**Where it stands** (2026-11-15). The current release is **0.8.7** (enricher only, on PyPI since 2026-11-15). The scope of
the next minor, 0.9, is being chosen with the maintainer; one zone is decided: reading reference snapshots remotely.

**Headline results**
- ✅ 0.8.7, released: the AlphaGenome licence notices now say what Google's terms say, and the rsID recovery no longer
  claims more than dbSNP records. Full suite 7,416 passed.
- ✅ 0.8.6, released: a re-derivation that drops an rsID now says so; the upgrade guide says the Ensembl snapshot
  carries only its core. Full suite 7,408 passed.
- ✅ Nothing already published moves: the registry measured all 24 production modules for the 0.8.5 rsID fix and
  found 0 rows it changes.
- ✅ AlphaGenome 2's predicted methylation, second trial: at 42 strong blood methylation variants its predicted shift
  was 27 times that at 84 matched non-variants, and 28 of 31 directions agreed. One cohort, no replication.
- ✅ Decided for 0.9: the enricher reads a snapshot from local disk first, then the registry's proxy, then Hugging Face.

**Next**
1. ❓ 0.9's scope — the maintainer answers the pm's small-minor proposal (in chat).
2. ⏳ Measure remote snapshot reads against local disk — pm, a night trial, before 0.9's design.
3. ❓ The registry proxy's lookup interface — pm with the registry, before 0.9's build.
4. ❓ One question on the maintainer's desk: linking the project's memory to its new folder name.
