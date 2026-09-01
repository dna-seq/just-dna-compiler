# RM170 — Kleene shape: None stays a neighbour, the warning is the product

**Subject:** the authoring shape for [ROADMAP.md § RM170](../ROADMAP_HISTORY.md#rm170--a-source-that-both-asserts-and-refutes-a-claim-is-muddy-water-and-nothing-tells-an-author).
**Measurements:** [CONTRADICTION_CORPORA](CONTRADICTION_CORPORA.md). Every number this note leans on was measured there; this file does not re-derive them.
**Date:** 2026-09-02.

This is a **design record**, not a second measurement and not a contract. The live item stays in ROADMAP. If a sentence here and the entry disagree, the entry wins until someone edits it.

**The decision this note records.** Extend the camp test so a withhold (`None`) is visible. Do not extend `VALID_DIRECTIONS`. Do not sum camps into a point. Two enricher owners — `civic_draft` and a new verification check — emit a warning. The author seeing it and proceeding is the expected close, not a workaround.

---

## 1. What this is answering

RM170's defect is not "we lack a combined `direction`." It is: an author can write `risk` over a variant a source also rebuts, and every gate stays green.

`contested_variants` cannot see that pair. It counts a variant whose camps include both `risk` and `protective`. A `Does Not Support` row is mapped to `None` and then skipped, so it never enters a camp. That is why the counter is 0 on both bases, correctly, and why the three VHL variants are invisible to it.

A vector sum (reversal as true→false, refute as true→none, final point = the sum) classifies the two fights honestly and then answers the wrong question. A sum asks *what should the cell become?* RM170 asked for a **finding**. Writing the point would reopen two refusals: enricher checks report and never repair, and RM152 refused filling `direction` from source disagreement.

House three-valued algebra is Kleene over *answers* (exists, covered, licence known), not a metric on signs. `risk ∧ withhold` does not become `unknown` on the authored cell. It becomes a finding beside an unchanged cell.

---

## 2. The None algebra

A snapshot variant is a **set**, not a score. Three slots, independently filled:

| slot | who fills it | values |
|---|---|---|
| **camps** | every `Supports` row | `∅`, `{risk}`, `{protective}`, `{risk, protective}` |
| **withhold** | any `Does Not Support` row | absent, or present **with** `evidence_status` and the evidence ids |
| **authored** | the module row, if any | `risk` / `protective` / `unknown` / `contested` / absent |

Rules:

- A withhold is **not** a camp. It does not enter `{risk, protective}`. That is why today's `contested_variants` is correctly 0.
- A withhold is **not** `protective`. `None` is withheld, never negated (`@refutation-withholds`).
- Combining never picks a point. You publish the set. `gene_validity` already does this one grain up: an unorderable `[definitive, refuted]` group is a set, not a verdict.
- Kleene stays on answers, not on signs. The authored `direction` is not rewritten.
- Status is part of the withhold, not a weight. `accepted` and `submitted` are not unit vectors. A hint that omits `status_basis` is false: every assert-and-refute pair in CIViC rests on a submitted rebuttal.

Snapshot readings, before any authored row:

| camps | withhold | name | what it is |
|---|---|---|---|
| one pole | no | **settled** | source has a sign |
| both poles | no | **reversal** | `contested` — genuine opposition. Still 0 in CIViC |
| one pole | yes | **refute-beside-claim** | RM170. A sign sitting next to a withhold |
| both poles | yes | **reversal + withhold** | both findings. Unobserved today |
| empty | yes | **refute-only** | CHEK2 788, TP53 4968. A withhold with no claim beside it |
| empty | no | **nobody-asked** | not on this axis |

The authored row is a second set. The finding is the join of the two, not a reduction of either.

---

## 3. Per-case advocacy

Each case is a different sentence. One code per sentence, or the author cannot tell what to do.

### A. Settled source, author agrees

Snapshot `{risk}`, no withhold. Author writes `risk`.

**Solves:** silence is correct. No warning. That is a pass, not a skip.

**How:** camps match; withhold absent.

### B. Settled source, author disagrees

Snapshot `{risk}`, no withhold. Author writes `protective` (or the reverse).

**Solves:** ordinary source-versus-author, the `clin_sig` shape. Not RM170. Do not steal this into the muddy-water code.

**How:** a later, separate check if CIViC concordance is ever wanted. RM152 refused filling `direction` from this. Leave it parked. The author may outrank a settled source; that is what `record_override` is for.

### C. Reversal (`contested`)

Snapshot `{risk, protective}`.

**Solves:** the fight `contested_variants` already counts. The drafter already names those subjects.

**How:** keep that line. Do not merge it with D. `contested` stays on `VALID_DIRECTIONS` as the *authored* member for "I am saying the sources disagree about the sign." The snapshot statistic is not that cell.

### D. Refute-beside-claim — the RM170 case

Snapshot `{risk}` + withhold. Author writes `risk` (the usual draft).

**Solves:** "you are shipping a sign the source also rebutted, and nothing said so."

**How:**

- **Drafter** writes the Supports row. Does not write a protective row. Emits a **named** warning: variant, evidence ids on both sides, each status, `status_basis`.
- **Checker** fires on that authored row later, same facts, attested.
- Cell stays `risk`. Finding stays.

This is VHL G104V: accepted claim 7134 + submitted refute 10949.

### E. Refute-only, author never writes

Snapshot `∅` + withhold. No authored row.

**Solves:** do not invent a subject. CHEK2 788 is not muddy water about a claim; there is no claim.

**How:** drafter writes nothing (already). Checker: not a subject. `subjects` does not count it. A release-record count of refute-only variants may live on the snapshot; it is not a module finding.

### F. Refute-only, author then writes a sign

Snapshot `∅` + withhold. Author writes `risk`.

**Solves:** a different sentence — "you asserted a sign the source has only ever rebutted." Author-versus-refute, not source-versus-itself.

**How:** own warning code. Same severity (warn, never gate). Same owners. Do not call it D or the subject count silently mixes the three VHL variants with the two claimless ones. Name it: *refute-only, no supporting item on this basis.*

### G. Combination profile (EID 8721)

One evidence item, two variants (VHL S183L **and** VHL D126N).

**Solves:** the parquet's lie that this is two single-variant rebuttals. `_submitted_evidence_row` stamps `molecular_profile_id` from the variant's single-variant profile, so the item is written as two rows claiming MP 2037 and 2406.

**How:** the finding keys on **evidence_id**, then fans out to authored rows. One finding, two subjects. Text says "combination genotype, profile 5278." Do not wait for [RM174](../ROADMAP.md#rm174--a-claim-about-two-variants-in-trans-is-written-as-two-single-variant-rows-because-no-brick-holds-the-real-subject) to ship the check — but do not count "3 variants, 3 independent refutes." Honest count: **one single-variant pair (2428) + one combo item touching two loci.**

### H. Accepted-only snapshot

Subject count 0. The class does not exist on this basis.

**Solves:** silence that is a *measured empty set*, not a skip.

**How:** record `ran(subjects=N, findings=0)` and `detail` names `status_basis=accepted`. `--offline` / no snapshot is `skipped`, and that is a different row.

### I. STRchive `Refuted` + a pathogenic band

Not this algebra. One field grades the locus–disease association; the same record still publishes a pathogenic band the drafter writes. Grade versus bands, no `direction` slot.

**Solves nothing in this check.** Park it. If `evidence` is adopted later: `draft-repeats` and `check-repeat-bands` grow a sibling warning. Different code, different subject, different skill line. Deciding "one check" for RM170 is deciding whether that field is adopted at all; the CIViC sign does not need that answer.

### J. Author sees the warning and keeps the row

**Solves:** the expected close. Muddy water is a fact about the source, not an authoring error.

**How:** cell unchanged. Warning remains — an outranked source never goes green, the same rule as `clin_sig`. Optional `record_override` writes *why* they kept the sign. Closure binds the bytes. `verification.json` says the question was put.

---

## 4. Two owners, both enricher

| owner | stage | first sighting for | writes | must not |
|---|---|---|---|---|
| **`civic_draft`** | 2 | anyone drafting from CIViC | the Supports row; a **named** warning on D / G / (F if they later add) | write the opposite sign; swallow the variant into an aggregate `N rows` |
| **new verification check** | 5, and inside `enrich()` when a civic snapshot is present (same as `clin_sig`) | hand-authors and ClinVar-drafted modules that never touched `civic_draft` | `verification.json` record + findings with `detail` | repair `direction`; escalate under `--strict` |

`just-dna-compiler validate` / `compile` is **not** an owner. Format and compiler never fetch and never hold a CIViC snapshot (Principle 2). Nothing this snapshot produces may enter `resolution.csv`. Once the check has attested, compile **restates** the findings as warnings (`verification_findings_recorded`, S70). That is the echo at stage 6, not the first sign on the road.

`close` is not an owner. It already refuses only an invalid spec. Warnings do not block a close. That is the line that makes "see it and proceed" a designed outcome.

Severity is settled in the entry: warn in both modes, never gate. Neighbours: `@clinsig-never-escalates`, `@a-source-recuring-is-not-a-strict-matter`. A source disagreeing with itself is not an authoring error.

The vocabulary for the finding is `VALID_VERIFICATION_CHECKS` / `VALID_WARNING_CODES`, not `VALID_DIRECTIONS`. RM150 added `contested` beside `unknown` so an absence and a finding stopped sharing a member. A refute-beside-claim is another shade; putting it on `direction` is the old `state` overload (Principle 5).

---

## 5. When the author sees the sign

A road sign, not a barrier. Same sign, three posts. Missing a post is a skip, not a pass.

```
 2 draft ──► 3 curate ──► 4 enrich ──► 5 check ──► 6 validate/compile ──► 6b close
    │                        │            │                │                 │
    │ named warning          │            │ attested       │ echo            │ does not refuse
    │ if civic_draft         │            │ finding        │ of stage 5      │
    │                        │            │                │                 │
    └──── first sighting ────┴────────────┴── guaranteed ──┴── reminder ─────┴── proceed
          for CIViC drafts                    if snapshot
                                              was available
```

**Stage 2 — first post, CIViC drafts only.**
Today: *"N CIViC row(s) refute a predisposition claim… none was drafted."* No variant named.
Needed: the `contested_variant` treatment — name the variant, both evidence ids, statuses, basis. The Supports row is still written. The sign says: you are about to curate a risk row that the same snapshot also rebuts.

They continue to stage 3. That is expected. They fill `genotype`, `conclusion`, maybe keep `direction=risk`. The warning does not delete the row.

**Stage 3 — no new post.**
Curation does not fetch CIViC. Do not hide the finding in `hints`. If they never drafted from CIViC, they have not seen the sign yet. Stage 5 exists for them.

**Stage 4/5 — the guaranteed post.**
Fold the check into `enrich()` when a civic snapshot is on disk or configured, exactly like `clin_sig`. Anyone who enriches a germline-direction module against that snapshot sees a paragraph of this shape:

> Variant 2428 (VHL G104V): authored `direction=risk`. CIViC has supporting EID 7134 (accepted) and Does-Not-Support EID 10949 (submitted). Snapshot basis `accepted+submitted`. A refutation does not establish the opposite sign; this row was not changed.

`--strict` still compiles. The record is `ran`, `findings ≥ 1`, never `skipped`.

If there is no snapshot, or `--offline`: `skipped`, reason named. Not a pass. The skill line is: you have not been told the water is clear; you have been told nobody looked.

**Stage 6 — the reminder.**
`validate` / `compile` reprint the attested findings. Green `--strict` is expected. The warning sits in the list an author is supposed to read on a green run, the same place `clin_sig` mismatches already live.

**Stage 6b — proceed.**
`close` does not care. Closure means a person declared these bytes final knowing what the checks said, not that the water was clear. A closed module with this finding is a checked module that chose to keep a sign. A closed module with `skipped` is an unchecked module. Those must stay distinguishable in `verification.json`.

**After close.**
Edit the row and the closure drops; a check record bound to the old bytes drops with it. Re-check, re-close. Pass 2 re-enters at 3 or 5, not at 0.

They do not see a flipped `direction`, a dropped row, a `<<REPLACE>>`, or a close refusal. Those would turn an expected proceed into a fight with the tool.

---

## 6. Path × edge case

| How the row got there | Snapshot | What they see, when | If they proceed |
|---|---|---|---|
| `civic_draft` VHL G104V | `accepted+submitted` | **2:** named D warning, risk row written. **5:** same finding attested. **6:** echo | close ok; record stays |
| `civic_draft` VHL S183L / D126N | wider | **2 and 5:** one G finding, two rows, text says combination / EID 8721 | close ok |
| `civic_draft` on `accepted` only | accepted | **2:** no D (class is empty). **5:** `ran, findings=0`, basis named | close ok; silence is measured |
| Hand-author `risk` on G104V | wider | **2:** nothing. **5:** first sighting. **6:** echo | same as draft path from 5 on |
| ClinVar-drafted VHL panel | wider | same as hand-author — `draft-panel` is not `civic_draft` | same |
| Hand-author `risk` on CHEK2 788 | either | **5:** F, not D | close ok |
| Author writes nothing on 788 | either | nothing. E. Not a subject | — |
| No civic snapshot / offline | — | **5:** `skipped`. Stage 6 does not invent a finding | close ok; unchecked on this axis |
| They `record_override` "I've read both papers" | wider | warning **remains**. Override is the reason, not a mute | close ok; next reader sees both |
| Re-draft after CIViC accepts 10949 | later release | **2:** `differs` / new named warning; **5:** still D, status may now be accepted | same; currency is a different check |
| `draft-repeats --gene DMD` | STRchive | **not this sign.** Today: nothing. Later: sibling warning on bands | out of scope here |
| Close without ever enriching | — | no sign at all | legal today; the missing record is the honest state. Do not make close require this check (RM73's gate half, major, blocked) |

Proceeding after the sign is the `clin_sig` contract, copied on purpose: two opinions in the world, the format does not arbitrate, `--strict` is reproducibility not truth, the finding carries enough to weigh (here: evidence ids + statuses + basis; there: review stars).

---

## 7. What the author is looking at

Not a new screen. Three existing surfaces, one sentence each.

1. **Draft / enrich / check CLI warning** — the named paragraph in §5. This is the muddy-water sign. It is a warning. The command exits 0 in both modes.
2. **`verification.json`** — a new `VALID_VERIFICATION_CHECKS` member, `subjects`, `findings`, `detail` listing variant keys + EIDs + statuses + basis. `skipped` if it could not run.
3. **Compile warning list** — restatement, so a green strict compile still shows it.

`review_queue` stays for overrides. Do not dump check findings there unless picking up the S70 sidecar (RM130). Not required to close RM170.

---

## 8. What next

Do the CIViC half. Do not wait on STRchive or RM174.

1. **Draft line first.** Cheapest, covers the path that created the item. Change `refutation_states_no_direction` to name variants the way `contested_variant` already does. Include evidence ids, statuses, basis. Pin the phrase. No schema change.
2. **Check second.** New `VALID_VERIFICATION_CHECKS` member. Subject = authored row whose snapshot variant is D or F. Warn both modes. Attest. Fold into `enrich()` when a civic snapshot is available so a hand-author cannot miss it by only running `enrich` and not a new command. `detail` is mandatory: a count with no names is not actionable (S70).
3. **Key findings on `evidence_id`, then fan out to rows.** So G is one finding, two subjects, even while RM174 still mis-stamps the profile column.
4. **Compile echo.** Restated warnings from the record. Already the pattern; wire this member into the same list.
5. **Tests from the probe's three variants plus 788.** D fires on 2428; G is one finding not two; E does not fire; F fires only with an authored sign; accepted-only is `findings=0` with basis in `detail`; no snapshot is `skipped`.
6. **Park STRchive** as a sibling, or a line under RM165, not a second axis of this check.
7. **RM174 in parallel.** Repair 2 (keep the fan-out, publish the real profile). Repair 1 would delete two of the three subjects and make the check look barren.

Not next: new `VALID_DIRECTIONS` members, a draft filter, a close gate, compiler-side validation, vector sums, adopting STRchive `evidence`.

The algebra is no longer the block. The remaining block on a *general* check is STRchive — and that answer is not needed to ship the CIViC sign. Ship the sign. Let "see it and proceed" be the documented happy path.
