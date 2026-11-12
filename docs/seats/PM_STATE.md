**Where it stands** (2026-11-12). The current release is **0.8.4** (on PyPI since 2026-11-11). `main` holds one fix
since then, not yet released. The scope of the next minor, 0.9, is not chosen yet.

**Headline results**
- ✅ GWAS lookups fill rows again on 0.8.4. The GWAS Catalog started refusing pages above 500 results; we now ask for
  500 and retry with a smaller page if refused. Checked live on one variant (223 associations).
- ⛔ The 0.7 line stays without GWAS lookups: the Catalog switched off the old API it reads, and no 0.7 fix will be
  released (the maintainer's call). Users get them back by moving to 0.8.
- ❔ AlphaGenome 2's predicted methylation, first trial: cheap and strong next to the variant, but at nine known
  blood methylation variants its shifts stayed within its own noise. Inconclusive on 9 pairs from one region.
- ✅ On `main`, unreleased: a mistyped snapshot path now fails loudly instead of reading as "nothing found".

**Next**
1. ⏸ A second, larger trial of AlphaGenome 2's predicted methylation (30 to 40 known variants across the genome,
   each against matched controls) — pm, paused for the account's weekly quota; restarts after it resets.
2. ⏳ Wording fix: what "significant" means for a study row — lead, built overnight.
3. ⏳ Next patch release (the two fixes above) — lead, after item 2; the PyPI upload is the maintainer's.
4. ❓ Should 0.9 read reference snapshots straight from Hugging Face, for the module registry — the maintainer, on
   the desk.
5. ⏳ 0.9 scope interview — pm with the maintainer; waits on the second trial.
