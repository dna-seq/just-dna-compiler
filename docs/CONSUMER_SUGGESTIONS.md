# Consumer suggestions from the registry (just-dna-registry)

*Field notes from adopting `just-dna-format` / `just-dna-compiler` **0.4** in the registry — the
server that catalogs, recompiles, and serves modules. Written after the 0.4 pin bump landed and the
whole test corpus was run through the server-side compile path.*

**Status: consumer feedback / design input — not a shipped contract.** Same spirit as
[`CONSUMER_FIELD_NOTES.md`](CONSUMER_FIELD_NOTES.md): illustrative asks framed to stay inside the
[`CONSTITUTION.md`](CONSTITUTION.md) invariants (additive-within-a-major, orthogonal axes,
declarative-not-code). Everything below is **out-of-digest** (identity/metadata), so none of it
touches `artifact.digest` bytes — it is 4.1-shippable, not major-gated.

---

## S1 — `module:` `extra="forbid"` rejects registry-owned identity keys the whole pre-0.4 corpus carries

**The friction.** 0.4 made the `module:` block `extra="forbid"` (good — it catches `colour:`/`nam:`
typos and the `genome_bild:` safety trap). But it also now *rejects* keys that are **filled by the
registry on publish**, not authored: essentially every pre-0.4 `module_spec.yaml` in the wild carries
`module.version` (an author's informal `v2`/`3`), and some carry `namespace`/`owner`. Under 0.3 these
were silently dropped; under 0.4 they are a hard `Extra inputs are not permitted`. That breaks three
registry paths at once for the entire existing corpus:

- **import** of a legacy spec archive → `422 invalid_spec`
- **upgrade** (re-publishes the carried-forward `module_spec.yaml`) → `422` mid-upgrade
- **revalidate** (contract-drift audit) → flags every pre-0.4 module `needs_upgrade` on a key the
  0.3-column back-population can't fix, so the flag never clears

The registry is the authority on `identity.{version,namespace,canonical_id}` and `owner` (SPEC §4):
it stamps them from the request and *overrides* any authored value. So the authored copies are
vestigial by construction — the `forbid` is firing on fields the format itself says the marketplace
fills.

**What the registry did (and keeps, regardless of 4.1).** We added a small, universal normalization
step — `strip_registry_owned_keys()` — that drops the registry-owned set
(`version`, `namespace`, `owner`, `canonical_id`) from the authored `module:` block *before*
`validate_spec`/`compile_module`, on every server compile path (publish, import, upgrade) and before
the revalidate drift check. It is byte-preserving when nothing is stripped, so a clean 0.4 spec is
untouched. This is robust and version-independent, so **we keep it after 4.1** — it is the right
place for *registry*-owned identity to be normalized. This note is a heads-up, not a "we're blocked"
ask.

**Suggestion for 4.1 (pick whichever fits the charter).** The friction is that the format's own
"the marketplace fills these" fields collide with author-time `forbid`. Options, all additive and
digest-neutral:

1. **Ignore-but-don't-reject the registry-filled set.** Keep `extra="forbid"` for genuinely unknown
   keys, but let `ModuleInfo` accept-and-drop the known registry-owned identity keys
   (`version`/`namespace`/`owner`/`canonical_id`) — they are already documented as marketplace-filled
   on `Identity`. A typo like `versoin:` still fails; `version:` becomes a documented no-op.
2. **Reserve them by name** (the vocabulary idiom already used elsewhere): put the registry-owned
   identity keys in the reserved set with a `RESERVED_NAME_REASONS` entry ("filled by the registry;
   omit from authored specs"), so the failure is *specific* ("reserved, registry-filled") rather than
   the generic extra-inputs message — pointing an author (or authoring agent) straight at the fix.
3. **Document only.** If neither is wanted, a one-line note in `COMPILER.md` / the authoring reference
   that authored specs must omit `module.version`/`namespace`/`owner` (registry-filled) would at
   least make the 0.4 tightening a known migration step rather than a surprise.

Our lean is (1) or (2): a large corpus of authored specs carries `module.version` today, and an
author reading "extra inputs not permitted" for a field the docs elsewhere describe as
marketplace-filled is a confusing dead-end.

## S2 — this is probably not the only pre-0.4 → 0.4 migration edge

The `module.version` case surfaced only because the registry runs the *whole* corpus through
`validate_spec` on every publish/import/upgrade — it's a good fuzzer for "authored shapes that were
tolerated pre-0.4 and are now `forbid`-rejected." Given `extra="forbid"` now covers the SNP core
(`VariantRow`/`StudyRow` via `AuthoredModel`), `Defaults`, and `ModuleInfo`, other silently-dropped-
then-newly-rejected keys are likely lurking in real specs (stray `defaults:` keys, legacy column
aliases). A short **"authored vs. registry-filled field ownership"** table in the authoring reference
— which keys an author sets, which the compiler derives, which the registry stamps — would make the
`forbid` boundary legible and pre-empt the next round of this. The registry's strip handles the
identity keys durably; the rest are author-facing and best addressed in the format's docs/vocab.
