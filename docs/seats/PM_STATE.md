**Where it stands** (2026-11-12, evening). **0.8.5 is cut** and waits only for the maintainer's PyPI upload. The
current release on PyPI is still 0.8.4. The scope of the next minor, 0.9, is not chosen yet.

**Headline results**
- ✅ 0.8.5 (cut, not yet published): installs beside Google's genai library again (it accepts older `tenacity`); a
  wrong rsID is no longer filled in at a position several variants share; a mistyped snapshot path fails loudly;
  "significant" on a study row says it means the study's own test. Full suite 7,406 passed.
- ✅ Nothing already published moves: the registry measured all 24 production modules for the rsID fix and found 0
  rows it changes. Three ClinVar panels (about 141,000 rows) still on pre-0.8 tables are where it applies next.
- ❔ AlphaGenome 2's predicted methylation, first trial: cheap and strong next to the variant, but at nine known
  blood methylation variants its shifts stayed within its own noise. Inconclusive on 9 pairs from one region.
- ⛔ The 0.7 line stays without GWAS lookups (the maintainer's call); 0.8 has them.

**Next**
1. ⏳ Publish 0.8.5 to PyPI — the maintainer.
2. ⏳ Three small patches: the Ensembl snapshot's note in the upgrade guide (lead, next), a variant row's
   "significant" explained, and a log line when a re-derivation drops an rsID — built overnight.
3. ⏸ Second, larger AlphaGenome methylation trial — pm, waiting for the weekly quota to fall under 80% (90% now).
4. ❓ Two questions on the maintainer's desk: read snapshots straight from Hugging Face for the registry (0.9), and
   linking the project's memory to its new folder name.
5. ⏳ 0.9 scope interview — pm with the maintainer; after the second trial.
