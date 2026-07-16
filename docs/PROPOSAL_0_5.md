# Proposal — 0.5 design threads (carried forward from the 0.4 proposal)

**Status: proposal / forward design — nothing here is shipped.** This is the *"means → draft schema
→ decision"* stage of the design cycle (CLAUDE.md → *The design cycle*) for the **0.5** milestone. It
holds the design threads that the 0.4 round **deliberately did not take**, moved here when the 0.4
proposal was retired (its shipped decisions now live in [`CHANGELOG.md`](CHANGELOG.md), 2026-07-10 and
the 0.4.0 branch-review passes).

The concrete deferred-item tracker (`RMn`) stays in [`ROADMAP.md`](ROADMAP.md); this doc is the
design discussion behind the 0.5-scope rows, the same way the 0.4 proposal sat beside the roadmap.
Everything below stays inside the Constitution (declarative-not-code, additive-within-a-major,
orthogonal axes, reserved namespace, the `frozenset[str]` vocabulary idiom).

---

## Carried forward — genuinely deferred (not built in 0.4)

### D1 — Authored PRS weights (a scoring file, not a manifest) → ROADMAP RM16

0.4 shipped `pgs.csv` as a **manifest of PGS Catalog IDs** with the ancestry-validity one-way-door
fields (`training_ancestry`, `training_cohort`, `match_rate_floor`, `research_tier`) — *not* authored
per-variant weights. The reasoning holds: just-prs resolves a `PGSxxxxxx` id to a harmonized scoring
file itself and scores each id independently, so inlined per-PGS weights would be dead data, and a
PRS yields a Z/percentile *within a matched reference distribution* — a shape the format does not bin.

**Deferred means:** an authored `effect_allele` + `effect_weight` scoring file (the separable, heavier
form) for the case a module must ship weights the PGS Catalog does not host. It is a distinct table
kind, digest-bearing (new parquet), and only worth building against a real consumer that combines
authored weights into a score. Parked as **RM16** in the roadmap; do not build speculatively.

### D2 — Complex-VNTR motif-path / declarative allele-string grammar → RM5 / round-3 escape hatch

0.4's `repeat_alleles.csv` bins a plain `repeat_count` keyed on `(gene, repeat_unit)`. The complex-VNTR
**motif-path** form (DAT1 `A-A-B-C-D-…`, where a bare count is too coarse) was **reserved as the home
for the Constitution's sanctioned declarative-grammar escape hatch** (a regex/pattern over an allele
string — Principle 1, data not code), *not* built. It is a near neighbour of:

- **RM5** (symbolic / structural alleles beyond `^[ACGT]+$` — 5-HTTLPR S/L, `<DEL>`/`<INS>`/`<STR n>`),
- the **round-3 STR-microvariant** note (forensic `full.partial` allele names like TH01 `"9.3"`, which
  is *not* the float 9.3 — a distinct allele *string*, never smuggled into a numeric bound).

**Deferred means:** a declarative allele-string pattern column (author-time `re.compile`-checked,
consumer-side ReDoS-safe match), reusing the `source_field`/`provenance_regex` pattern-grammar idiom.
Build it only when a real module's count proves too coarse; until then it stays an escape hatch, not a
required shape.

### V1 — Enforce SemVer on `module.version` (0.4.1's advisory preview → 0.5 rule) → ROADMAP RM17

0.4.1 genuinely adopted `module.version` as a **freeform advisory** field (the whole pre-0.4 corpus
carries an informal `v2`/`3`; see [`PROPOSAL_0_4_1.md`](PROPOSAL_0_4_1.md)). It ships the coercion
algorithm now — `just_dna_format.normalize.normalize_version` — but uses it **read-only**: the compiler
*previews* what a future release will read (warning `v2` → *"will read it as `2.0.0`"*, silent on a
clean `1.2.3`).

**0.5 means:** promote `normalize_version` from preview to **enforcement** on `ModuleInfo.version` — a
`field_validator` that coerces the authored value to canonical `MAJOR.MINOR.PATCH` (or a strict
validator that rejects a non-coercible value, TBD below). The algorithm as built: strip every char
that is not a digit or the `.` separator, split on `.`, take the first three fields (empty/absent → `0`,
leading zeros dropped), right-pad to three — so `v2`→`2.0.0`, `1.5`→`1.5.0`, `1.2.3`→`1.2.3`
(idempotent), a no-digit value → `0.0.0`.

**Charter check:** still **out of `artifact.digest`** (identity metadata) and additive — coercion
*accepts* the same inputs 0.4.1 does, just normalizes them, so it does not tighten requiredness (P8) or
move digest bytes (P3). Once enforced, an authored SemVer flows straight into `Identity.version` (0.4.1
already does this for already-clean values).

**Open questions for 0.5:**
- **Coerce vs. reject.** Coercing (`v2`→`2.0.0`) is maximally compatible and matches the preview an
  author already saw; strict-reject is louder but re-breaks the corpus 0.4.1 just unbroke. Lean:
  **coerce**, keeping the authored string recoverable if a consumer wants the verbatim marker.
- **Separator.** The field report said "comma-separated fields"; a version delimiter is conventionally
  `.`. Confirm the delimiter (the built algorithm uses `.`) before enforcing.
- **Round-trip.** Coercion must stay idempotent (`normalize_version(normalize_version(v)) ==
  normalize_version(v)` — already tested) so compile → reverse → recompile does not oscillate.

---

## Settled in 0.4 — do not reopen

Recorded here as forward-design guardrails so these are not re-proposed for 0.5:

- **One physical binning table** (the field-notes' literal B0). **Rejected** in favour of
  **per-quantity tables sharing one column vocabulary** — the natural keys differ per quantity and
  PRS is ancestry-conditional, so one table would contort the frozen shape. The single "bin-a-measure"
  consumer code path (the actual win) comes from the shared vocabulary, not one table.
- **Tuple binning keys** (`(gene, count)` crammed into one cell). **Rejected** in favour of
  **explicit named columns (multicolumn keying)** — legible to a CSV reader, queryable per-component,
  order-independent. A tuple-as-key is a coder reflex, not a protocol idiom. (Coding-standards call,
  firm; this is why B4's SMN modifier is `modifier_gene`/`modifier_cn`, two columns, not a tuple.)

---

## The rest of 0.5 scope

Everything else that was open at the end of the 0.4 round is tracked as `RMn` in
[`ROADMAP.md`](ROADMAP.md) (§ *0.5 scope*): RM4 (native ClinVar gene-panel materialization), RM5
(symbolic/structural alleles), RM6 (callability as a first-class typed column + `callable_from`), RM10
(inheritance-expectation field), RM15 (build-agnostic identity), RM16 (D1 above). RM7/RM13 are
explicitly **consumer** contracts, not format scope. New ideas enter through the freeform idea-book in
the roadmap and graduate here once they are worth a draft shape.

**Near-term note:** the 0.4.1 patch (inject the authority-key list + genuinely adopt `module.version`
— a consumer field report, not a 0.5 item) has its own plan in
[`PROPOSAL_0_4_1.md`](PROPOSAL_0_4_1.md). Its version follow-up (enforce SemVer) is **V1 / RM17**
above.
