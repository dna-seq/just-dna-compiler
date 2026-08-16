# Brief for `just-dna-lite` — what the format publishes that the app does not read

**Who this is for.** An agent or maintainer working in `just-dna-lite`. It is written to be handed over
on its own, so it names no file outside your tree except by full symbol name, and it quotes the checks
rather than asking you to trust a summary.

**What it is.** Five things the format tier publishes, or guarantees, that the reference consumer
currently does not use. It came out of writing a module-lifecycle document on the producer side, where
the seam between "what we publish" and "what is read" turned out to be wider than either side had
written down.

**What it is not: a list of bugs, or a work order.** Three of the five may be deliberate, and one of
them is arguably a defect on *our* side rather than yours (§4). Each entry ends with the question that
is actually yours to answer. Where an answer is "yes, deliberate", the useful outcome is a line in your
docs saying so — the cost of these is not that they are wrong, it is that nobody can tell from the code
whether they were decided.

Every claim below was verified by grep in your tree on 2026-08-16, and the command is given so you can
re-run it rather than take our word.

---

## 1. `verify_manifest` is never called on install

```
grep -rn "verify_manifest" --include=*.py .     # → no matches
```

The install path extracts the tarball and registers the directory. It does not re-hash
`artifact.files[]`, does not recompute `artifact.digest`, and does not compare either against the
shipped `manifest.json`.

Your own `docs/MODULE_MARKETPLACE_SPEC.md` specifies a **"Client verify-then-install flow"** whose
step 4 is *"Check `compilation.compile_success == true` and `compiled_by == "marketplace-server"`."*
Neither field is read back from a downloaded manifest anywhere in the repo — the only occurrences are
`compiled_by` as an argument to your own compile CLI (`module_compiler/cli.py:296`, `:400`), i.e. the
value being written, never the value being checked.

**What we supply**, with the trap named rather than left for you to hit:

```
verify_manifest(module_dir, manifest, *, require_marketplace=True, check_inputs=False,
                check_logs=False, check_provenance=False, check_logo=False,
                check_readme=False, check_derived=False, public_key=None) -> None
```

It re-hashes each `artifact.files[]` entry from disk, recomputes the Merkle root, and verifies
`manifest.signature` (Ed25519 over the `artifact.digest` string) when you pass a pinned public key.
You already import `just_dna_format.integrity` for `build_artifact`.

**`require_marketplace` defaults to `True`, which is the marketplace policy, not a neutral one.** A
single naive call site rejects every locally-compiled module, because our compiler leaves
`compiled_by` null by design. Wiring this means two policies — `True` for a registry install, `False`
for a local compile — which is a fine contract and not the one the parameter name advertises at a
glance.

Worth knowing about the trust model before you decide how much to do: `manifest.signature` is the only
real guarantee in the format. `manifest.verification` is explicitly untrusted — every field says so —
because a forged pass is worse than silence.

**Your question:** is skipping verification a deliberate trade for a registry you control, or the spec
having outrun the code? If it is deliberate, the spec section is the thing to correct.

---

## 2. `resolution_mode` and `fully_resolved` are never read

```
grep -rn "fully_resolved\|resolution_mode" --include=*.py .    # → no matches
```

We publish these two fields with a documented trust rule, and you consume the registry's projected
`resolution.trusted` instead — which is that same rule evaluated server-side.

**That may well be correct**, and if it is, the fields' documentation is what needs fixing on our side:
it addresses "a consumer", and the actual reader is the registry. We have that filed as an open
question. Two things to know either way:

- **The rule changed in 0.6 and the old one is unsafe.** `fully_resolved` is `all()` over
  `variants.csv`, so it is **vacuously `true`** for a module carrying no `variants.csv` — every PGx or
  binning module. The registry followed the old rule (`resolution_mode == "strict" or fully_resolved`)
  and had to migrate a stored projection. The safe rule is
  **`resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`**.
- `resolution_subjects` is the new integer that makes it safe, on `manifest.compilation`. If you ever
  evaluate trust locally — for a side-loaded or peer-shared module the registry never saw — that is the
  rule to use.

**Your question:** is local trust evaluation ever needed, or is registry-projected `trusted` the only
path you intend to support? If the latter, a comment saying so would stop the next reader (us included)
reporting it as a gap.

---

## 3. An annotation run records no module version

`AnnotationManifest` carries `user_name`, `sample_name`, `source_vcf`, `output_dir`, `modules`,
`skipped_modules`, `failed_modules`, `total_variants_annotated`, `restored_variants`,
`total_variants_restored`, and the timing fields. `ModuleOutputMapping` carries `module`, `lead_table`,
`weights_path`, `logo_path`, `metadata_path`.

```
sed -n '529,585p' just-dna-pipelines/src/just_dna_pipelines/annotation/hf_modules.py \
  | grep -inE "version|digest|url"      # → no matches
```

So a rendered report cannot be tied to the module bytes that produced it, and nothing can answer *which
of my saved results are stale*.

**Why we are raising it rather than filing it.** This is the missing prerequisite under two things our
roadmap has already ruled **consumer scope by charter** — the evaluation-output / report-card schema
(our `RM7`) and the "modules as a deterministic verification harness" idea. Both are listed on our side
only so they are not mistaken for format scope. Neither can be built while a run does not record which
module version it ran.

**What we supply.** Everything needed is already in the manifest you have on disk:
`identity.canonical_id` (`namespace/name@version`), `identity.version`, and `artifact.digest`. For a
locally-compiled module `identity.version` is null by design — the registry stamps identity at publish —
so the authored version lives in `module_spec.yaml`, which is what your `_spec_version` already reads
and coerces.

**Your question:** three fields on `ModuleOutputMapping` (version, digest, source URL) — worth it now,
or only when the harness is built?

---

## 4. A path-discovered module has no version to pin — and that is our layout, not your code

Two acquisition paths, two notions of "updated":

- **Registry installs** carry a real per-version audit. You read `needs_upgrade` (hard filter),
  `artifact_digest`, `resolution.trusted` and `yanked`. Fine.
- **Path/HuggingFace discovery** has effectively none. The layout is `data/<name>/weights.parquet` —
  no version in the path, no manifest fetch, no digest check. A republished module keeps the same URL,
  so a cached copy shadows it, and the only invalidation is `invalidate_module_cache_on_version_change`
  purging the HF cache when **your own package version** moves (`get_app_version()`, marker file
  `module_cache.version`).

There is a `vN`-subdirectory fallback in the generic fsspec collection scan (`_VERSION_RE =
re.compile(r"^v(\d+)$")`, highest wins), tried only when `{name}/weights.parquet` is absent. So the
capability half-exists; the flat layout is what has no version.

**The part that is ours.** `just_dna_enricher.upload.upload_module` — the format tier's own HF publisher
— writes exactly that flat `data/<name>/` layout. We publish the shape that cannot express a version.
Saying "the consumer can't pin a module" while shipping the publisher that makes pinning impossible is
not a finding about you.

**Your question, and ours.** Should the HF layout gain a version segment? That is a change to our
publisher and to your discovery in the same breath, so it wants agreeing rather than deciding on one
side. The interim fact worth knowing: on that path, the identity used to detect "the module changed" is
a property of the reader, not of the module — a module republished with new science while the app is
pinned is invisible, and an app patch release with no module change purges everything.

---

## 5. Two different predicates for "is this a module", in one repo

- Discovery probes for **any** of `LEAD_TABLES` (`weights`, `pharm_variants`, `diplotypes`,
  `haplotypes`, `pgs`, `copynumbers`, `repeat_alleles`, `heteroplasmy`, `activity_phenotype`,
  `allele_function`) as `<name>.parquet` — `hf_modules.py:103`.
- `list_custom_modules`, `get_custom_module_specs` and `_scan_local_modules` all test
  `(d / "weights.parquet").exists()` — `module_registry.py:308`, `:318`, `state.py:5563`.

So a `pharm_variants`-led registry install is discovered by one and invisible to the other three. This
is the composition rule the format is built on: a module carries **only** the table kinds it uses, and a
drug-response module carries `pharm_variants.csv` and no `variants.csv` at all — correctly.

Your discovery code already says this better than we could: classification is "by schema, never by
family name", because "ten families exist today and the format keeps adding them, so a name-keyed
switch would need editing every release". The three weights-only predicates are the case that got left
behind.

**Your question:** is `weights.parquet`-exists standing in for "has a lead table", or does it genuinely
mean "SNP-core module" in those three places?

---

## Also in the tree, and relevant to code you already have — but NOT installable yet

**Read this heading literally.** Everything in this section is **0.6, and 0.6 is uncut**: the tree
reads `0.6.0`, the newest release on PyPI is `0.5.4`, and `pip` gives you 0.5.4. So
`resolution_subjects`, `positional_rows`/`positional_rows_placed`, the `gene_validity` /
`clinical_assertions` / `derived` / `readme` / `verification` manifest blocks and
`just_dna_format.layout` **do not exist in any version you can install today**. Do not go looking for
them in your venv. Listed here so the shape is known before the release lands, not as something to
wire this week.


Fields on `manifest.compilation`, all additive, all safe to ignore:

| Field | What it answers |
|---|---|
| `resolution_subjects` | the denominator `fully_resolved` quantifies over — see §2 |
| `positional_rows` / `positional_rows_placed` | **how far the coordinate fill got on `pharm_variants` / `haplotypes` / `heteroplasmy`.** Directly relevant to your rsid-only join fallback: "this table joins to a VCF by position" is `positional_rows_placed == positional_rows`. Both are `int \| None`, and `None` means *this compiler did not count* (a pre-0.6 artifact) — not zero |
| `vrs_alleles` / `vrs_alleles_identified` | allele-identity coverage as two counts, never a ratio |
| `warnings` | prose, and a published surface — `compiler.UNJOINABLE_PHRASE` is pinned by a test in both places it must hold, so the substring match will not break under you |

New top-level manifest blocks: `gene_validity`, `clinical_assertions` (ClinVar's call **and** its
0–4 star review tier, per allele), `derived` (byte hashes of the sidecar CSVs where they live beside the
spec — transport, never identity), `readme` (a hashed `FileEntry`, which is what lets a registry or an
installer serve prose it can attest), and `verification` (per-check records plus the authoring closure —
untrusted by design, see §1).

Public helpers in the schema tier, dependency-free, if you are reimplementing any of this:
`just_dna_format.alleles` (`parsimony_reduce`, `split_genotype`, `is_unobservable_allele`,
`UNOBSERVABLE_ALLELE`), `just_dna_format.vrs` (`normalize_chrom`, which you already use,
`in_pseudoautosomal_region`, `par_partner`), `just_dna_format.layout` (the sidecar name/location
resolver — two accepted spellings, and `derived/` is a legal home).

---

## What we are asking for

Nothing, in code. What is useful back to us is a line per section saying **deliberate** or **gap** —
because three of these are plausibly deliberate, and we cannot tell from the outside. Where the answer
is "the format's documentation is what is wrong" (§2 is the likeliest), say that: it is a producer-side
fix and we will make it.

If you want to file anything against the format tier, the intake is
`docs/CONSUMER_SUGGESTIONS.md` in the `just-dna-format` repo; get the next free `Sn` from
`.claude/triage-state.sh --next` rather than reading a number off a document, because both halves of the
ledger are scanned and written-down numbers go stale within hours.
