**Where it stands** (2026-11-13). The current release is **0.8.6** (on PyPI since 2026-11-13). The scope of the next minor, 0.9, is not chosen yet.

**Headline results**
- ✅ 0.8.6, released: a re-derivation that drops an rsID now says so; the upgrade guide says the Ensembl
  snapshot carries only its core; a variant row's "significant" is explained. Full suite 7,408 passed.
- ✅ 0.8.5, released: installs beside Google's genai library again (it accepts older `tenacity`); a
  wrong rsID is no longer filled in at a position several variants share; a mistyped snapshot path fails loudly;
  "significant" on a study row says it means the study's own test. Full suite 7,406 passed.
- ✅ Nothing already published moves: the registry measured all 24 production modules for the rsID fix and found 0
  rows it changes. Three ClinVar panels (about 141,000 rows) still on pre-0.8 tables are where it applies next.
- ❔ AlphaGenome 2's predicted methylation, first trial: cheap and strong next to the variant, but at nine known
  blood methylation variants its shifts stayed within its own noise. Inconclusive on 9 pairs from one region.
- ⛔ The 0.7 line stays without GWAS lookups (the maintainer's call); 0.8 has them.

**Next**
1. 🔄 Second, larger AlphaGenome methylation trial (30–40 known blood methylation variants on 10+ chromosomes,
   each against 2 matched non-variants) — pm, running overnight since 2026-11-14 00:45 CET.
2. ❓ Two questions on the maintainer's desk: read snapshots straight from Hugging Face for the registry (0.9), and
   linking the project's memory to its new folder name.
3. ⏳ 0.9 scope interview — pm with the maintainer; after the second trial.
