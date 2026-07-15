# Proposal — 0.4.1: accept the registry-owned identity keys the whole pre-0.4 corpus carries

**Status: proposal / plan — nothing here is shipped.** This is the *"means → draft schema → decision"*
stage for a **0.4.1 patch**, responding to the registry's field report in
[`CONSUMER_SUGGESTIONS.md`](CONSUMER_SUGGESTIONS.md) (S1/S2). It is a **patch**, not 0.5 scope: the
change is a validation *relaxation* on identity/metadata that is **entirely out of `artifact.digest`**,
so it is additive within the major and shippable now (CONSTITUTION P3/P8).

---

## The friction (S1)

0.4 made the authored `module:` block `extra="forbid"` — correct: it catches `colour:` / `nam:` typos
and the `genome_bild:` safety trap. But the same guard now **hard-rejects keys the registry fills on
publish, not the author**: essentially every pre-0.4 `module_spec.yaml` in the wild carries
`module.version` (an author's informal `v2`/`3`), and some carry `namespace` / `owner`. Under 0.3 these
were silently dropped; under 0.4 they are `Extra inputs are not permitted`, breaking three registry
paths for the *entire* legacy corpus:

- **import** of a legacy spec archive → `422 invalid_spec`
- **upgrade** (re-publishes the carried-forward `module_spec.yaml`) → `422` mid-upgrade
- **revalidate** (contract-drift audit) → flags every pre-0.4 module `needs_upgrade` on a key the
  0.3-column back-population can't fix, so the flag never clears

The format itself documents these as marketplace-filled: `Identity.{namespace,version,canonical_id}`
and `manifest.owner` are `Optional`, stamped by the registry on publish and *overriding* any authored
value (`manifest.py` docstrings; SPEC §4). So the authored copies are **vestigial by construction** —
`forbid` is firing on fields the format says the marketplace owns.

The registry already ships a durable, version-independent `strip_registry_owned_keys()` (byte-preserving
when nothing is stripped) and **keeps it regardless of 4.1** — so this is a heads-up + a request to
make the format itself tolerant, not a block.

---

## The registry-owned identity set

Four keys, all identity/metadata, all **out of `artifact.digest`**:

| Key | Home | Owner |
|---|---|---|
| `version` | `Identity.version` (SemVer) | registry stamps on publish |
| `namespace` | `Identity.namespace` | registry stamps on publish |
| `canonical_id` | `Identity.canonical_id` (`namespace/name@version`) | registry derives |
| `owner` | `manifest.owner` | registry stamps on publish |

`name` is **not** in this set — it is genuinely author-set (`ModuleInfo.name`, routed into `Identity`).

---

## Draft decision — accept-and-drop, with a diagnosis (CONSUMER_SUGGESTIONS option 1)

**Recommend option 1 (accept-but-don't-reject), *not* option 2 (reserve by name).** Rationale, on
charter grounds:

- The **reserved namespace is only for names expected to become real *module columns/annotation axes*
  later** (CLAUDE.md; ROADMAP § *Reserved namespace*) — it is not a catalogue of barred names. The
  registry-owned identity keys are the opposite: they will **never** become authored module columns —
  they are stamped *by the registry*. Putting them in `RESERVED_NAMES_0_4` would misuse the mechanism
  (which lives on `AuthoredModel` row models via `reject_reserved`, and does not even apply to the
  `module:` block's `Display`-derived `ModuleInfo`).
- Option 1 keeps `extra="forbid"`'s teeth for **genuine** typos: `versoin:` / `namespac:` still fail
  hard. Only the exact known registry-owned names become a documented no-op.
- It matches the format's own documentation ("filled by the marketplace") — these fields are *known*
  to the format, just not author-set.

**Not silent.** Accept-and-drop, but surface it so the author (or authoring agent) learns the key is
ignored rather than honoured — otherwise an author who thinks `module.version: 2` is load-bearing gets
no signal. Emit an INFO/warning: *"module.version is registry-filled and ignored; omit it from
authored specs."* This also clears the revalidate `needs_upgrade` loop (the drift check sees a clean,
normalized block).

### Shape

1. **`vocab.REGISTRY_OWNED_KEYS`** — a `frozenset[str]` = `{"version", "namespace", "owner",
   "canonical_id"}`, with a `REGISTRY_OWNED_REASONS` mapping (mirroring `RESERVED_NAME_REASONS`) so the
   diagnosis is specific per key. This is a **new, distinct** vocabulary from the reserved namespace —
   different semantics (registry-filled vs. future-module-column), documented as such.
2. **`ModuleInfo`** — add a `@model_validator(mode="before")` that pops any `REGISTRY_OWNED_KEYS`
   present from the input mapping *before* `extra="forbid"` runs, stashing the dropped names so the
   compiler can report them. `extra="forbid"` stays and still rejects everything else.
3. **`validate_spec`** (compiler) — surface the dropped keys as an INFO on `ValidationResult.info`
   (the existing channel used for non-reserved `flags`), e.g. `"dropped registry-filled module keys:
   version"`. Byte-neutral: a clean 0.4 spec drops nothing and is untouched.
4. **Docs (S2) — an "authored vs. compiler-derived vs. registry-stamped" field-ownership table** in
   the authoring reference / `COMPILER.md`, so the `forbid` boundary is legible and the *next* pre-0.4
   migration edge (stray `defaults:` keys, legacy column aliases — S2) is pre-empted. Surface it from
   `authoring_reference()` if cheap.
5. **Tests** — (a) a legacy spec carrying `module.version`/`namespace`/`owner` now validates and
   compiles, with the INFO emitted; (b) a typo (`versoin:`) still fails `extra="forbid"`; (c) a clean
   0.4 spec is byte-identical (drops nothing); (d) the dropped values do **not** leak into the manifest
   (the registry still stamps `Identity`).
6. **Version** — patch bump both packages `0.4.0 → 0.4.1` (`schema_version` stays `"1.0"`). *(Version
   bumps + publishing are the user's domain — not done here.)*

### Charter check

- **P2 (no network):** untouched — pure local validation change.
- **P3/P8 (additive / requiredness):** a **relaxation** — accepts strictly more inputs, demotes no
  required field, changes no output. Clean.
- **`artifact.digest`:** unchanged — the keys are identity/metadata, never materialized into parquet;
  dropped, not stored. Patch-shippable, not major-gated.
- **P5 (reserved namespace):** deliberately **not** used — see rationale above. A separate
  `REGISTRY_OWNED_KEYS` vocabulary keeps the reserved namespace meaning "future module axis" intact.

---

## Open questions (to the registry consumer)

- **Diagnosis channel.** Is an INFO on `ValidationResult.info` visible enough in your import/upgrade
  path, or do you want a distinct typed warning list so a UI can surface "these authored keys were
  ignored" separately from `flags` INFO?
- **`canonical_id`.** You listed `{version, namespace, owner, canonical_id}` in your strip set; confirm
  authored specs actually carry `canonical_id`/`owner` in the wild (not just `version`), so the accepted
  set matches your corpus exactly and we don't accept-drop a key that should still be a typo trap.
- **S2 scope.** Do you want the 0.4.1 patch to also fuzz `Defaults` / row-model legacy aliases now (a
  broader accept-drop or an alias map), or is the field-ownership doc table enough until the registry's
  whole-corpus run surfaces the next concrete offender?
