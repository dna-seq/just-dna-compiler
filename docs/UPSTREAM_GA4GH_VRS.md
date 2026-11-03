# Upstream ledger — `ga4gh.vrs` (vrs-python)

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. Upstream: <https://github.com/ga4gh/vrs-python>, releases on its
GitHub release page; clone and watcher as the liaison state file's `ga4gh-vrs` line says.

## Marks

- **Read mark: `2.3.3`**, the version `uv.lock` installs and the newest stable release (2026-06-09). Pin:
  `ga4gh.vrs>=2.3.3,<2.4` in `enricher/pyproject.toml`, capped by RM304.
- **Pre-releases read: `2.4.0-a0` … `2.4.0-a6`** (2026-02-24 … 2026-10-01), read 2026-11-03 for the question
  below. They are tagged on the `vrs/2.1` and `v3` branches, not on `main`.
- **Backlog mark: none.** The ledger began at the installed version; nothing before it is owed.

## What we use of it

Only the enricher imports it; the format tier reimplements the digest in stdlib and the compiler never
touches it (`@ga4gh-vrs-core-dep`).

| Ours | Theirs | What it decides |
| --- | --- | --- |
| `enricher/src/just_dna_enricher/vrs.py:51` | `ga4gh.core.identifiers.ga4gh_identify` | the `ga4gh:VA.` id of every indel/MNV we mint |
| `enricher/src/just_dna_enricher/vrs.py:52`, `:335` | `ga4gh.vrs.normalize` (fully justified allele, default RLE subunit mode) | where an indel slides to, and so its id |
| `enricher/src/just_dna_enricher/vrs.py:324`–`:331` | `models.Allele`, `SequenceLocation`, `SequenceReference`, `LiteralSequenceExpression` | the object that is digested |
| `enricher/src/just_dna_enricher/sequences.py:39`, `:80`, `:100` | `ga4gh.vrs.dataproxy.create_dataproxy`, `get_sequence` | reference reads over the seqrepo REST proxy |
| `schema/src/just_dna_format/vrs.py:403`–`:711` | the `sha512t24u` + canonical-JSON algorithm, reimplemented | substitution ids offline; `schema/tests/test_vrs.py` checks them byte for byte against the library |
| `schema/src/just_dna_format/vrs.py:45` | `VRS_SPEC_VERSION = "2.0"` | the spec our stdlib minter claims |

`AlleleTranslator` is deliberately unused (it imports `hgvs` at module scope; `vrs.py` module docstring).

## Verdicts

### 2.4.0-a0 … 2.4.0-a6 — nothing moves a digest we compute (read 2026-11-03)

The question (first work, item 3): does a release past 2.3.3 change a digest the packages compute?

- **By diff:** `git diff 2.3.3 2.4.0-a6 --stat` over `src/ga4gh/vrs/normalize.py`, `src/ga4gh/core/identifiers.py`
  and `src/ga4gh/core/digests.py` is empty. The changed files are the models (`vrs/models.py`, `core/models.py`,
  new `core/metadata.py`, `core/version.py`): the VRS 2.1 / 2.1.1 and gkm-core 1.2.0 schemas, metadata mixins,
  and new classes (`RelativeAllele` `RA`, `RelativeSequenceLocation` `RSL`, `SequenceOffsetLocation`). The
  `ga4gh.inherent` lists of `Allele`, `SequenceLocation`, `SequenceReference` and `LiteralSequenceExpression`
  are unchanged.
- **By measurement:** the same three already-normalized Alleles on GRCh38 chr19 (an SNV, a deletion as a
  `LiteralSequenceExpression`, an insertion as a `ReferenceLengthExpression`) identified under each version
  (`uvx --isolated --from ga4gh.vrs==<v>`), byte-identical:

  | allele | 2.3.3 | 2.4.0a6 |
  | --- | --- | --- |
  | snv | `ga4gh:VA.CwlSoBa_jwEvG4U0LgeNOLw6etIcIjYi` | same |
  | del_lse | `ga4gh:VA.oO86xyhtLUiAlOSSPg5Jso2RFUT3dBT6` | same |
  | ins_rle | `ga4gh:VA.YFUR4oR_84b-rRFf0UzOjfI4eE5FTKAP` | same |

  The probe called `ga4gh_identify` only, not `normalize()` (no sequence proxy), so it tests serialization and
  digest, not justification. Justification is covered by the diff: `normalize.py` is identical.

**Sorted:** *nothing for us* up to 2.4.0-a6. The pin `<2.4` keeps all of it out anyway.

### The pending digest move: VRS 2.1's smallest-factor RLE rule — tracked as RM304

VRS 2.1 picks the **smallest** repeat-subunit factor for an ambiguous insertion, where 2.0 picked the largest;
affected Allele ids change (`docs/probes/GKS_SURVEY.md` headline 2). State upstream on 2026-11-03:

- Issue ga4gh/vrs-python#637 is open. PR ga4gh/vrs-python#665 (opened 2026-10-02, updated 2026-10-27, not
  merged) adds `RleSubunitMode` with `LARGEST` as the default, "so existing digests are unchanged", and says
  **"The vrs/2.1 branch will make SMALLEST the default, in line with vrs spec v2.1."**
- So a 2.4.0 final built from `vrs/2.1` is expected to move the ids `enricher/src/just_dna_enricher/vrs.py:335`
  mints for ambiguous insertions, unless we pass `rle_subunit_mode` explicitly once that keyword exists.

**Sorted:** *breaks us* the day the `<2.4` cap is lifted, and RM304 already owns it (record the VRS version
behind every `vrs_id`; keep the cap meanwhile). New fact for its owner: the keyword #665 adds would let us pin
the 2.0 behaviour across the upgrade, or choose the 2.1 one, as a decision rather than a side effect.

## Our pieces that duplicate an upstream feature

| Ours | Theirs | Since | Replacing ours would cost |
| --- | --- | --- | --- |
| stdlib substitution minter, `schema/src/just_dna_format/vrs.py` | `normalize` + `ga4gh_identify` | always | the format tier's dependency budget (pydantic + cryptography only); kept on purpose, not a bicycle |

## Outbound

None.
