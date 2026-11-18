# Upstream ledger — AlphaGenome's terms

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. It covers the **terms** that bind the two AlphaGenome sources in
`enricher/src/just_dna_enricher/licensing.py` (`alphagenome_avi`, `alphagenome_atlas`). It does not cover the
client or the protos: those are pinned in `docs/vendor/alphagenome_protos/`, and the v2.0.0 shim trap for the
next pin bump is in the liaison's notes. The documents are web pages with a PDF beside each. There is no feed,
so a change reaches this seat when someone reads the pages (here, the RM433 trial on 2026-11-14).

**Which version binds:** the Output Terms say "The version of these Terms that were effective on the date the
relevant Output was generated will apply to your use of that Output". So a newer text replaces nothing. The
pinned older texts stay live for Output generated under them, and new texts are vendored **beside** them,
with the date in the name.

## Marks

| Document | Pinned (undated name) | Live, vendored 2026-11-14 |
| --- | --- | --- |
| Additional Terms of Service | "Last Modified: September 8, 2026", `alphagenome_additional_tos.pdf` sha256 `0a1b52c4…` | "Last Modified: November 6, 2026", `alphagenome_additional_tos_2026-11-06.pdf` sha256 `191795b6…`, from `https://storage.googleapis.com/alphagenome/terms/20261106/AlphaGenome%20Services%20Additional%20Terms%20of%20Service%20-%20English.pdf` |
| Output Terms of Use | "Effective: June 25, 2025", `alphagenome_output_terms.pdf` sha256 `a1293588…` | `alphagenome_output_terms_2026-10-09.pdf` sha256 `3df37d06…`, from `https://storage.googleapis.com/alphagenome/terms/20260909/AlphaGenome-Output-Terms-of-Use.pdf` |
| Download page (who is in the Permissive class) | saved signed-in 2026-09-10, `alphagenome_download_page.html.gz` | **not re-read**: it is sign-in gated (see below) |
| Model Parameters Terms of Use | none | not vendored; the new training exception names it, and nothing here uses Model Parameters |

The Output Terms' date is given in three ways, and they are recorded as found: the PDF's URL path says
`20260909`, the PDF says "Effective: [October 9, 2026]" with the brackets, and the web page says "Effective:
October 9, 2026". The `_2026-10-09` name follows the PDF's text. Each `.txt` beside a PDF is `pdftotext -layout`
of it.

**Generation dates of what we hold:** the AVI artifact's members are stamped 2026-08-27
(`docs/probes/ALPHAGENOME_ATLAS.md`), so it stays under the June 2025 Output Terms. Atlas Output generated on or
after 2026-10-09 (live `alphagenome_check` calls, the RM433 trial runs) is under the new Output Terms. An Atlas
snapshot built before that date stays under the old ones.

## What changed (normalised diffs of the PDF texts)

**Additional Terms, 2026-09-08 → 2026-11-06.** Three changes:

1. "the AVI Score" becomes "the Permissive Use Downloadable Artifacts for Commercial and Non-Commercial Use" in three
   places: the summary's two exceptions, and prohibition 1a's "(except for …, which may be used for commercial
   purposes)".
2. "Output" now lists "Permissive Use Downloadable Artifacts" where it listed "AVI Scores", and adds "(e.g.,
   embeddings)".
3. "By using Google's AlphaGenome Atlas" becomes "By using any version of Google's AlphaGenome Atlas".

These parts are unchanged word for word:
- the definition clause that grants commercial use to "AVI Scores and other artifacts that are made available for
  download within the 'Permissive Use Downloadable Artifact' section";
- the AVI Score Feature Breakdown exclusion;
- prohibition 1b's carve-out "aside from indirectly via a scientific publication, open source release or to
  support journalism";
- prohibitions 4 (training "similar to AlphaGenome") and 5 (the notice), both already opening "Except for
  Permissive Use Downloadable Artifacts".

**Output Terms, 2025-06-25 → 2026-10-09.** Five changes:

1. **The training bar is wider.** It was "to train machine learning models … for predicting the effects of genetic
   variants similar to AlphaGenome". It is now "To train machine learning models or related technology, except that
   you may use Output and Output Derivatives to train models that function in a similar manner to AlphaGenome
   provided the model weights and parameters … are … governed by the AlphaGenome Model Parameters Terms of Use".
   Training any model is barred; only an AlphaGenome-like model under the Model Parameters Terms is let through.
2. A "Key Definitions" section now comes before "Use restrictions". "Output" includes embeddings and output
   produced from Model Parameters.
3. The use restrictions now open "Unless otherwise specifically permitted in the AlphaGenome Services Additional
   Terms of Service".
4. Who is bound: no longer "without signing up to AlphaGenome API". A holder who agreed to the Additional Terms or
   the Model Parameters Terms is governed by those; anyone else, by these. The Google party is split (Ireland for
   the EEA and Switzerland).
5. The disclaimer is rewritten: "You and anyone you share information generated by AlphaGenome with are solely
   responsible …".

## Verdicts

### No permission axis moves (2026-11-14)

- `alphagenome_avi` `commercial_use=True`: the grant that carries it is unchanged, and it names AVI Scores
  itself.
- `alphagenome_atlas` `commercial_use=False`: Output is still "for non-commercial use only".
- `redistribution=True` on both rests on the maintainer's 2026-09-10 reading of prohibition 1b's carve-out. That
  text is identical in both new documents.
- Not measured: the download page that decides membership of the Permissive class. It is sign-in gated and this
  seat cannot re-fetch it. `commercial_use=True` and the builder's two refusals by name still rest on the
  2026-09-10 save. A re-save from a signed-in browser is the person's to make.

### Who is bound by which training bar

**The Atlas row's `notice` understates the bar for new Output, for the people who receive it.**

A module's consumer has not agreed to the Additional Terms, so the Output Terms bind them. For Output generated
on or after 2026-10-09, that bars training any model, not only "variant-effect models". The repository itself
agreed to the Additional Terms, whose prohibition 4 still reads "similar to AlphaGenome", so the narrower bar is
right for the repository's own use. It is not right for a downstream holder.

The notice travels into a module's `sources.csv` (`SourceTerms.notice`). The fix is a sentence in that notice,
and it is the lead's. Nothing breaks today: no gate reads `notice`.

### Three checks for the lead (to confirm, not conclusions)

1. **The Atlas row's `license` string** dates the Output Terms "(2026-09-08)". The vendored Output Terms say June
   25, 2025, and 2026-09-08 is the Additional Terms' date. This predates the change.
2. **The AVI row's `notice`** says two bars bind anyway, including "no training of variant-effect models
   (prohibition 4)". Prohibition 4 has opened "Except for Permissive Use Downloadable Artifacts" since the
   2026-09-08 text, and so has prohibition 5 (the notice). For AVI under the Additional Terms, neither binds.
   Carrying the notice is harmless over-compliance; stating that the training bar binds is a claim the terms do
   not make. This predates the change.
   **Decided by the person, 2026-11-18** (relayed by the lead): "We don't do training here, thus, don't care about
   the ban. Keep all as is." The cautious notice stays as RM442 shipped it in enricher 0.8.7; the contradiction between
   the two documents is Google's to resolve.
3. **The `LICENSE.txt` slicer** (`alphagenome_avi_build.use_restrictions_text`) cuts from the "Use restrictions"
   heading to "Disclaimers". On the new text it would drop the new "Key Definitions" section, which the
   restrictions now depend on (what "Output" means). The AVI builder should keep reading the undated June 2025
   file. Its artifact predates 2026-10-09, and AVI is outside the notice requirement anyway.

## Adoption map (for the lead)

| Where | What | Why |
| --- | --- | --- |
| `licensing.py` `ALPHAGENOME_ATLAS_TERMS.notice` | Say the Output Terms' training bar for Output generated on or after 2026-10-09: no training of any model, except an AlphaGenome-like one under the Model Parameters Terms. | Verdict 2 |
| `licensing.py` `ALPHAGENOME_ATLAS_TERMS.license` | Name the Output Terms version by its effective date, and decide whether the string tracks generation date or stays a floor. | Check 1 |
| `licensing.py` `ALPHAGENOME_AVI_TERMS.notice` | Confirm whether prohibition 4 binds AVI. | Check 2 |
| `licensing.py:912` comment | It quotes prohibition 1a's "except for the AVI Score", which the 2026-11-06 text spells "except for the Permissive Use Downloadable Artifacts …". | Wording drift only |
| `alphagenome_avi_build._default_terms_file` | Keep it on the undated June 2025 file. A builder for Output generated later would read the dated file whole, not a slice. | Check 3 |
| tests (`test_alphagenome_atlas_terms.py`, `test_alphagenome_avi_build.py`, `test_alphagenome_check.py`) | They read the undated files, which are untouched; no change is owed by this vendoring. | None |

## Outbound

None.
