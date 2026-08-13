"""
Shared constrained vocabularies, identifier patterns, and reusable validator helpers.

A dependency-light leaf (stdlib only) so every authored-DSL model — `spec` (variants/studies),
`binning` (the measure→phenotype primitive), `pgx` (star-alleles), and `pgs` — validates against
one source of truth for the orthogonal axes and identifier grammars. Per CONSTITUTION Principle 6,
constrained vocabularies are `frozenset[str]` + a validator, never `Enum`/`Literal`.

`spec` re-exports the names it historically owned, so existing imports
(`from just_dna_format.spec import VALID_DIRECTIONS`) keep working unchanged.
"""

import math
import re
from collections.abc import Iterable

# ── Orthogonal axis vocabularies (the 0.3 split out of the overloaded `state`) ──────────────────
# Effect direction — the clean phenotypic scalar. Orthogonal to `clin_sig` and `stat_significance`.
VALID_DIRECTIONS: frozenset[str] = frozenset({"protective", "risk", "neutral", "unknown"})
# Graduated statistical significance (named `stat_significance`, NOT `significance` — that is the
# clinical axis).
VALID_SIGNIFICANCE: frozenset[str] = frozenset(
    {"significant", "suggestive", "not_significant", "unknown"}
)
# ClinVar / ACMG clinical significance (VEP `CLIN_SIG` vocabulary). Distinct from `direction`.
VALID_CLIN_SIG: frozenset[str] = frozenset(
    {
        "pathogenic",
        "likely_pathogenic",
        "uncertain_significance",
        "likely_benign",
        "benign",
        "drug_response",
        "association",
        "risk_factor",
        "protective",
        "affects",
        "conflicting",
        "not_provided",
        "other",
    }
)

# ── Identifier grammars ─────────────────────────────────────────────────────────────────────────
RSID_PATTERN: re.Pattern[str] = re.compile(r"^rs\d+$")
ALLELE_PATTERN: re.Pattern[str] = re.compile(r"^[ACGT]+$", re.IGNORECASE)
# EFO/MONDO/OBA/HP-style ontology CURIE, e.g. EFO_0004340 or MONDO:0005265 (matches just-prs's
# `trait_efo_id`). Multiple ids may be given, comma/semicolon/pipe-separated.
TRAIT_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z]*[:_]\w+$")
# Separators accepted inside a multi-valued CSV cell (`flags`, `trait_efo_id`, `training_ancestry`).
MULTI_SEP: re.Pattern[str] = re.compile(r"[,;|]")
# A VCF field-name pointer: one bare token, optionally `|`-alternated (`CN|DS`). Lives here rather
# than on `binning` because two models now point into a VCF this way — `source_field` names where the
# measured quantity is, `callable_from` names where the callability signal is — and a grammar shared
# by two models belongs on the leaf both can import (see `validate_field_token` below).
SOURCE_FIELD_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\|[A-Za-z_][A-Za-z0-9_]*)*$"
)

# ── Reserved namespace (0.4) ──────────────────────────────────────────────────────────────────
# Names reserved because they are **genuine anticipated module-side axes** (CONSTITUTION Principle 5:
# reserve future axes so they survive the one-way door), deliberately NOT built this run. This list is
# ONLY for names that will plausibly become real module columns — it is NOT a catalogue of things that
# "may not appear" (that space is unbounded and meaningless to enumerate: barring `caller` would be as
# arbitrary as barring `pasta_recipe`; `extra="forbid"` already rejects every unknown/misspelled column
# generically). So a name earns a slot here only if a future release is expected to claim it.
#
# Enforcement is two-layered: every authored model sets `extra="forbid"` (rejects any unknown column)
# AND runs the `reject_reserved` before-validator, so a reserved name fails with a *specific* diagnosis
# — what it is reserved for and that a release may claim it — rather than the generic "extra inputs not
# permitted" a random/typo'd column gets. That specific message (not a published dictionary) is the
# list's build-time value; it is honest precisely because these names really are future axes.
#
# `reference_sequence`, `suballele`, `tissue`, `assay_context`, and `source_field` are BUILT this run,
# so they are absent here.
RESERVED_NAMES_0_4: frozenset[str] = frozenset(
    {
        # A module-side hint naming WHICH reference database the app should join this annotation
        # against when several exist (implicit Ensembl for variants / ClinVar for clin_sig today; a
        # module may pin it explicitly, e.g. a specific PharmVar release). Annotation-side addressing,
        # not a measurement — a real future axis.
        "reference_db",
    }
)
# NOTE: `requires_callable`, `acmg_sf`, `actionability` were reserved here and are now BUILT as
# optional `VariantRow` columns — and `callable_from` joined them in 0.5 (RM6's second half: a
# declarative pointer at the VCF field a consumer establishes callability from). A built column must
# not also be reserved, or `reject_reserved` would refuse the very name the author is meant to write. PharmGKB `drug`/`response`/`evidence_level` are built on
# `PharmVariantRow`/`DiplotypeRow`. And `caller`/`caller_version` were dropped from the reserved set
# entirely (round-2 Q2 origin): they name which tool produced a *call* — a consumer-side measurement,
# never module annotation — so there is no future module axis to reserve, and barring them by name
# would be arbitrary (a non-feature among unbounded non-features). A consumer records them on its own
# call data; a module never carries them, and `extra="forbid"` rejects them like any other stray column.

# Why each reserved name is withheld — surfaced verbatim in the author-time error so the author gets a
# *diagnosis* ("here is what the name is reserved for; a release may claim it"), not a bare rejection.
RESERVED_NAME_REASONS: dict[str, str] = {
    "reference_db": (
        "names which reference database the app should join this annotation against — reserved so a "
        "module can pin its join target explicitly instead of relying on the implicit default"
    ),
}

# PharmGKB clinical-annotation evidence levels (item 9). Closed vocabulary (Principle 6).
VALID_EVIDENCE_LEVELS: frozenset[str] = frozenset({"1A", "1B", "2A", "2B", "3", "4"})

# How strongly CPIC recommends the prescribing action for a diplotype (0.5). Closed (Principle 6).
#
# **A different axis from `evidence_level`, and folding them together would be the `state`-overloading
# mistake again.** PharmGKB's 1A…4 grades *how well established the association is*; CPIC's
# classification grades *how firmly it tells a prescriber to act* — two bodies answering two
# questions, and they routinely disagree (a well-evidenced association can carry an optional action).
#
# Members are CPIC's own five, lowercased into the format's token style (its other vocabularies are
# `likely_pathogenic`-shaped, and these terms have clean lowercase forms — unlike ClinPGx's
# `Metabolism/PK`, which is why THAT one keeps source spelling). Live counts over CPIC's
# `recommendation` table on 2026-08-02: Optional 982, Strong 577, Moderate 340, No Recommendation 89,
# n/a 12. `n/a` is deliberately **absent**: it is CPIC recording that it did not classify, which is an
# empty cell here — `None` already means unknown, and inventing a member for it would let "unclassified"
# read as a classification.
VALID_RECOMMENDATION_STRENGTH: frozenset[str] = frozenset(
    {"strong", "moderate", "optional", "no_recommendation"}
)

# ClinGen dosage-sensitivity ratings, for `gene_metrics.csv` (0.5). Closed vocabulary (Principle 6).
#
# **These are stored as terms, not as ClinGen's numeric codes, and that is a deliberate departure
# from this repo's usual "keep the source value verbatim" rule.** Probing the live gene-curation list
# (1,520 genes, 2026-08-01) showed the codes are `{0, 1, 2, 3, 30, 40}` — an *ordinal-looking scale
# that is not ordinal*: 0–3 grade increasing evidence, but 30 means "gene associated with autosomal
# recessive phenotype" and 40 means "dosage sensitivity unlikely". A consumer sorting or thresholding
# on the raw number ranks `40` (unlikely) above `3` (sufficient evidence) — the exact inversion of the
# meaning — and the format would have handed it that trap. Verbatim is right for an *identity* (a star
# allele, an accession); it is wrong for a code whose numeric form lies about its own order.
#
# The mapping is total and lossless in both directions, so nothing is destroyed by carrying the term:
#   0 → no_evidence            1 → little_evidence     2 → some_evidence
#   3 → sufficient_evidence    30 → autosomal_recessive    40 → dosage_sensitivity_unlikely
#
# ClinGen also writes a literal `"Not yet evaluated"` in the triplosensitivity column (210 of 1,520
# genes). That is an absence, not a rating, so it maps to `None` — and it is why a naive `int(cell)`
# reader crashes on this file.
VALID_DOSAGE_SENSITIVITY: frozenset[str] = frozenset(
    {
        "no_evidence",
        "little_evidence",
        "some_evidence",
        "sufficient_evidence",
        "autosomal_recessive",
        "dosage_sensitivity_unlikely",
    }
)
# ClinGen's numeric code → the term above. Lives here beside the vocabulary so the enricher's reader
# and any consumer decoding a legacy column resolve the same mapping.
DOSAGE_SENSITIVITY_BY_CODE: dict[int, str] = {
    0: "no_evidence",
    1: "little_evidence",
    2: "some_evidence",
    3: "sufficient_evidence",
    30: "autosomal_recessive",
    40: "dosage_sensitivity_unlikely",
}

# ── Gene–disease validity (0.6; the `gene_validity.csv` fact table, RM24) ───────────────────────
# How strongly a curating body asserts that variation in a gene causes a disease. Closed vocabulary
# (Principle 6), and **one set for every submitter**: ClinGen writes `Definitive`/`Disputed`, GenCC
# writes `Definitive`/`Disputed Evidence`/`Supportive`, and a consumer filtering on one spelling would
# silently miss the other's rows. The mapping happens at the enricher boundary, the way ClinGen's
# dosage codes already do — builders store verbatim, readers map — so a mapping fix reaches a table
# that was already written.
#
# Ordinal, unlike `VALID_DOSAGE_SENSITIVITY`: definitive > strong > moderate > limited is genuinely a
# strength ladder in ClinGen's own SOP. `disputed`/`refuted`/`no_known_disease_relationship` are NOT
# points on it — they are the opposite claim — which is why this is a set with an intended reading
# rather than an integer column. `ORDERED_GENE_VALIDITY` below states the ladder explicitly for the
# consumer who wants to sort, and deliberately holds only the members that are on it.
#
# `supportive` is GenCC-only (5,274 of 30,410 submissions on 2026-08-13, most of them Orphanet's): a
# submitter asserting the association without grading it on ClinGen's ladder. `animal_model_only` is
# ClinGen-only and appears in no row of the 2026-08-13 release — kept for the `withdrawn` reason, that
# it is a classification the source's own SOP defines and a later release may emit, and Principle 3
# would otherwise make its absence a one-way door.
VALID_GENE_VALIDITY: frozenset[str] = frozenset(
    {
        "definitive",
        "strong",
        "moderate",
        "limited",
        "supportive",
        "disputed",
        "refuted",
        "no_known_disease_relationship",
        "animal_model_only",
    }
)

#: The strength ladder, weakest first — the members of `VALID_GENE_VALIDITY` that are actually ordered.
#:
#: A separate tuple rather than an integer column for the ClinGen-dosage reason inverted: those codes
#: look ordered and are not, so they had to be decoded; these are ordered, so the order is published
#: rather than left for each consumer to hardcode. `supportive` is absent because it is an assertion
#: made off the ladder, and the three negative verdicts are absent because they are a different claim
#: — putting `refuted` at position zero would read as "the weakest evidence for", which inverts it.
ORDERED_GENE_VALIDITY: tuple[str, ...] = (
    "limited",
    "moderate",
    "strong",
    "definitive",
)

#: How a gene–disease relationship is inherited, as the curating body states it. Closed (Principle 6).
#:
#: One set again, and it has to be: ClinGen writes two-letter codes (`AD`, `AR`, `XL`, `SD`, `MT`,
#: `UD`) while GenCC writes HPO term labels (`Autosomal dominant`, `X-linked recessive`, …). The same
#: fact, two spellings, and the column is part of the row's identity — 59 (gene, disease) pairs in the
#: 2026-08-13 ClinGen release carry two rows differing only by mode of inheritance, so dropping it
#: collapses real curations rather than duplicates.
#:
#: `undetermined` is a **stated** finding, not a missing cell: ClinGen's `UD` and GenCC's `Unknown`
#: mean an expert panel looked and could not settle the mode. A source that has no concept of
#: inheritance leaves the column empty instead, which is the ordinary null-is-not-a-value rule.
VALID_INHERITANCE_MODE: frozenset[str] = frozenset(
    {
        "autosomal_dominant",
        "autosomal_recessive",
        "x_linked",
        "x_linked_dominant",
        "x_linked_recessive",
        "y_linked",
        "mitochondrial",
        "semidominant",
        "undetermined",
    }
)

# PharmGKB/ClinPGx clinical-annotation phenotype categories. Closed vocabulary (Principle 6), and
# multi-valued via `MULTI_SEP` — ClinPGx writes `Efficacy;Toxicity` for an annotation that is about
# both, which is a real combination rather than a data error.
#
# This is part of a clinical annotation's *identity*, not decoration: one variant and one drug
# routinely carry several annotations that differ only by category. rs4149056 + simvastatin has three
# — Metabolism/PK at level 1A, Efficacy at 3, Toxicity at 1A — each with its own per-genotype rows.
# Without the category they collapse onto one another.
VALID_PHENOTYPE_CATEGORIES: frozenset[str] = frozenset(
    {"efficacy", "toxicity", "dosage", "metabolism_pk", "pd", "other"}
)


def validate_phenotype_categories(
    value: str | None, field_name: str = "phenotype_category"
) -> str | None:
    """Validate a multi-valued phenotype-category cell against `VALID_PHENOTYPE_CATEGORIES`.

    Accepts ClinPGx's own spellings (`Metabolism/PK`) case-insensitively and normalizes them to the
    vocabulary member (`metabolism_pk`), because the authored DSL should not make a human transcribe
    a slash-and-caps token exactly.
    """
    if value is None:
        return value
    normalized: list[str] = []
    for token in MULTI_SEP.split(value):
        token = token.strip()
        if not token:
            continue
        canonical = token.lower().replace("/", "_").replace(" ", "_").replace("-", "_")
        if canonical not in VALID_PHENOTYPE_CATEGORIES:
            raise ValueError(
                f"{field_name} tokens must be one of "
                f"{sorted(VALID_PHENOTYPE_CATEGORIES)}, got: {token!r}"
            )
        normalized.append(canonical)
    return ";".join(normalized) if normalized else None


# ── Data-source licensing (0.5; the `sources.csv` fact table) ───────────────────────────────────
# Which layer of a module a source contributed to. Closed vocabulary (Principle 6).
#
# The split is the whole point of tracking licences per (source, layer) rather than per source. All
# but the last are machine-produced fact sidecars carrying things a source *reports* — a coordinate,
# an AC/AN, a PMID, a curated verdict — which are not the expressive content a copyright licence
# covers, and which in the coordinate case are identically available from Ensembl. `annotation` is the
# module's own authored tables, where a curated annotation text or evidence level is *expressed* and a
# derivative work genuinely exists.
#
# Only `annotation` taints a module. A module that used CPIC purely to look up a coordinate must not
# be marked as carrying CPIC's restrictions, and a single `share_alike` boolean on the manifest would
# render that case identically to one embedding ClinPGx annotation prose.
#
# `gene_validity` and `clinical_assertion` joined in 0.6 with the two derived tables they name (RM24,
# RM25), and both are fact-class for the reason above rather than by analogy: a ClinGen gene–disease
# verdict and a ClinVar review status are values those sources publish identically to everyone, the
# same standing as a gnomAD frequency. Each is written by a pass, which is the half that matters —
# `VALID_SOURCE_LAYERS` having members no file ever carried is the bug that rule exists to prevent.
VALID_SOURCE_LAYERS: frozenset[str] = frozenset(
    {
        "resolution",
        "frequency",
        "gene_metrics",
        "literature",
        "gene_validity",
        "clinical_assertion",
        "annotation",
    }
)

# What the *acquirer* declared about their intended use when the data was fetched. A third orthogonal
# axis (Principle 5), never folded into the strictness `mode`: `mode` is a claim about how hard to
# fail, this is a claim about who is using the data and why. `unstated` is the honest default — the
# tooling must not assert a purpose on the user's behalf — and is distinct from `non_commercial`,
# which is a declaration actually made.
VALID_DECLARED_USE: frozenset[str] = frozenset({"unstated", "non_commercial", "commercial"})

# ── Resolution status (0.5; the source-independent resolution table) ────────────────────────────
# Closed vocabulary (Principle 6) for a `ResolutionRow`'s outcome. `not_found` is the resolution
# analogue of the binning tables' mandatory `unresolved` sentinel: it records "a source was consulted
# and the locus is genuinely absent", distinct from a variant that was never attempted (row absent).
# `ambiguous` marks a query that resolved to something the resolver could not disambiguate to a single
# locus (rare — a one-to-many rsid is expanded to distinct rows instead, so it is not `ambiguous`).
VALID_RESOLUTION_STATUS: frozenset[str] = frozenset({"resolved", "not_found", "ambiguous"})

# ── Frequency status (0.5.1) ────────────────────────────────────────────────────────────────────
# Closed vocabulary (Principle 6) for a `FrequencyRow`'s outcome. It borrows two members from the
# resolution table above and adds a third, because an allele-frequency source has one more way to
# answer than a coordinate lookup does:
#
# * `resolved`     — the source served counts for this allele.
# * `not_found`    — the source was asked and does not have this allele. A **fact** about a locus the
#                    source does cover: absent from the callset means absent from those samples.
# * `not_covered`  — the source does not cover this locus **at all**, so it has no answer to give and
#                    none can be inferred. gnomAD v4 is the motivating case: it excludes the Y
#                    pseudoautosomal region from its callset outright (probed 2026-08-04 — X PAR1
#                    640000-641500 serves 880 variants, the same interval on Y serves none), so
#                    recording an expanded Y-PAR row as `not_found` asserted an absence that was never
#                    established. That is the `None` ≠ `False` rule: an unknown may not be written down
#                    as a negative.
#
# `not_covered` rather than `unchecked`, which is this codebase's word for a question that was never
# put (`acmg.py`: the row named no gene, the list could not be reached). This is the stronger and more
# specific statement — the source was consulted, and its scope excludes the locus, so the answer is
# unknowable *from this source* rather than merely unobtained.
#
# `ambiguous` is deliberately absent: a frequency row names one allele in one population, so there is
# nothing for a source to be ambiguous between.
VALID_FREQUENCY_STATUS: frozenset[str] = frozenset({"resolved", "not_found", "not_covered"})

# Closed vocabulary (Principle 6) for what dbSNP currently says about an authored rsID. Provenance,
# not a resolution fact — see `ResolutionRow.rsid_status` for why it stays out of the fact set.
#
# **`withdrawn` is real but currently unreachable from the live API, and that is deliberate.** An rsID
# *withdrawn* after a mapping or clustering error (`rs11273140`) and one *never assigned*
# (`rs2000000000`) return byte-identical responses from `esummary`, `esearch` and Ensembl alike, so the
# automated check reports `absent` for both and its message names the two readings without choosing.
# The member is kept anyway for two reasons: a curator who has established the retraction by hand can
# record it in `resolution.csv` and have the tooling honour it, and a future source (a historical dbSNP
# dump, or an endpoint that starts exposing the distinction) can start producing it without a
# vocabulary change — which Principle 3 would otherwise make a one-way door.
#
# The two states are **not interchangeable in severity**: `absent` has benign causes (a very new rsID,
# API lag, a typo) and refuses only under `strict`, while `withdrawn` is a repudiation of the variant
# itself — the annotation resting on it may be worthless — and refuses in **both** modes.
VALID_RSID_STATUS: frozenset[str] = frozenset({"live", "merged", "absent", "withdrawn"})

# What a `provenance_quote`/`provenance_regex` was matched against. The distinction is load-bearing
# rather than descriptive: a **hit** is conclusive from either source, but a **miss** is only
# conclusive against fulltext — an abstract that does not contain the phrase says nothing about the
# body. Collapsing the two would let "not in the 200-word abstract" read as "not in the paper".
VALID_QUOTE_SOURCE: frozenset[str] = frozenset({"fulltext", "abstract"})

# ── Ancestry groups for the frequency table (0.5) ───────────────────────────────────────────────
# An OPEN, seeded vocabulary in the `RECOMMENDED_AUTHOR_KINDS` idiom — deliberately NOT a closed
# `frozenset` + rejecting validator, even though Principle 6 makes closed the default. The reason is
# that `frequencies.csv` must stay **source-independent**: it is shaped for allele frequencies in
# general, and gnomAD is only the first producer. TOPMed, ALFA, and 1000G label their groups
# differently, and a closed set would make each of those an additive vocabulary bump — turning a
# source swap into a schema change. What makes a label interpretable is not membership here but the
# row's `dataset` column, which names the release the label belongs to.
#
# Seeded with gnomAD v4's ten ancestry groups plus `global` (the whole-dataset row, which gnomAD
# reports under a bare empty id). Unknown labels are normalized and kept, not rejected.
RECOMMENDED_ANCESTRY_GROUPS: frozenset[str] = frozenset(
    {
        "global",       # the whole dataset — every source has this row, however it spells it
        "afr",          # African / African-American
        "ami",          # Amish
        "amr",          # Admixed American
        "asj",          # Ashkenazi Jewish
        "eas",          # East Asian
        "fin",          # Finnish
        "mid",          # Middle Eastern
        "nfe",          # Non-Finnish European
        "sas",          # South Asian
        "remaining",    # v4's name for what v2 called `oth` — individuals not assigned above
    }
)
# This is NOT `pgs.VALID_TRAINING_ANCESTRY` and must never be merged with it. Those are 1000G
# superpopulation codes describing *which cohort a PGS was trained on* — a property of a score's
# provenance and portability. These describe *whose alleles were counted* in a reference database.
# Two different axes that happen to share three letters; merging them would be the `state`-overloading
# mistake in new clothing.

# Emission order for the frequency table (Principle 7: deterministic ordering is load-bearing). The
# source returns groups in an order it never promises to keep — and, probed live, returns duplicates —
# so the writer imposes this order instead of preserving the server's. `global` leads because it is
# the row a reader wants first; the rest are alphabetical, which needs no justification and cannot
# drift. A label outside this list sorts after all of them, alphabetically, so an unseeded source's
# groups are still emitted deterministically.
POPULATION_ORDER: tuple[str, ...] = (
    "global", "afr", "ami", "amr", "asj", "eas", "fin", "mid", "nfe", "remaining", "sas",
)


# A well-formed ancestry-group label: a lowercase token that survives a CSV cell and a group-by.
POPULATION_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9_]+$")


# ── Module authorship (RM14; docs/USE_CASES.md §5a) ─────────────────────────────
# A contribution's `role` is a small, stable, CLOSED vocabulary (Principle 6): what a contributor did
# to *this version*.
VALID_AUTHOR_ROLES: frozenset[str] = frozenset({"created", "edited", "audited", "reviewed"})
# A contributor's `kind` is an OPEN, multi-valued tag set — a *recommended seed* keyed for consumer
# faceting (route scrutiny by author-kind), but authors may coin new tags as AI topologies proliferate,
# so unknown tags are kept, not rejected (like `flags`). Facets:
#   • human, a rising ladder of assurance: `human` → `human_expert` → `human_certified`
#     (a medically / board-certified expert, e.g. a clinical geneticist);
#   • ai, plus a scale/topology tag: `ai` with `agent` | `team` | `swarm`.
# There is deliberately **no `hybrid` tag** — it was rejected as non-explicit (hybrid *what* — a human
# + a small model, or a certified expert + a SOTA swarm?). A joint contribution is expressed by two
# entries (a human and an ai), each with its own `kind`, so the mix is always spelled out.
RECOMMENDED_AUTHOR_KINDS: frozenset[str] = frozenset(
    {"human", "human_expert", "human_certified", "ai", "agent", "team", "swarm"}
)
# The reserved `actionability` axis's recommended seed vocabulary (documentation — the field is not
# built yet, so this is not enforced). Round-2 Q9 extended the round-1 seed with `descriptive` (a
# large fraction of findings are self-knowledge / no-action — an explicit "none", not forced into
# `actionable`) and `modifiable` (lifestyle-actionable, distinct from clinical `actionable`).
ACTIONABILITY_SEED: frozenset[str] = frozenset(
    {"actionable", "preventable", "pharmacogenomic", "incurable", "reproductive", "descriptive", "modifiable"}
)


#: The cell a generated template writes where a human must decide the value. A *value* sentinel,
#: not a marker column: replacement happens one row at a time, so a half-filled file keeps failing on
#: exactly the rows still to do, and an author never has to delete a header column. Deliberately not
#: `MeasureBinRow.unresolved` — that sentinel means "the measurement is absent at read time" and is
#: designed to COMPILE, while this one must never compile. Two opposite lifecycles on one field would
#: be the overloaded-axis anti-pattern (CONSTITUTION P5).
TEMPLATE_PLACEHOLDER: str = "<<REPLACE>>"


def reject_template_placeholders(data: object, *, what: str = "row") -> object:
    """A `mode="before"` guard: refuse any cell still carrying `TEMPLATE_PLACEHOLDER`.

    Runs *before* field coercion so an unreplaced stub in a typed column (`start: int`, a closed
    vocabulary, the genotype grammar) is diagnosed as an unfilled template rather than as
    "Input should be a valid integer" — the author is told what to do, not what pydantic wanted.

    This tightens validation: a module carrying the literal string `<<REPLACE>>` in a free-text cell
    would now be invalid. Recorded deliberately rather than slipped in; the token is chosen so no
    curated prose contains it."""
    hits = sorted(_placeholder_paths(data, prefix=""))
    if hits:
        raise ValueError(
            f"unreplaced template placeholder {TEMPLATE_PLACEHOLDER!r} in {what}: "
            f"{', '.join(hits)}. Replace the value, or delete the row if you do not need it."
        )
    return data


def _placeholder_paths(data: object, *, prefix: str) -> list[str]:
    """Dotted paths of every placeholder cell, recursing into nested blocks and lists.

    Recursive because `module_spec.yaml` nests (`module.title`, `authorship[0].who`) and its inner
    blocks are plain `BaseModel`s, not `AuthoredModel`s — so they carry no guard of their own and a
    top-level-only scan would let a scaffolded `module:` block through."""
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            found.extend(_placeholder_paths(value, prefix=f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            found.extend(_placeholder_paths(value, prefix=f"{prefix}[{index}]"))
    elif isinstance(data, str) and data.strip() == TEMPLATE_PLACEHOLDER:
        found.append(prefix or "<value>")
    return found


#: Columns that are real *somewhere* in the authored DSL, and so are a plausible confusion rather than
#: a typo, keyed to what to do instead. A name in here earns a specific diagnosis on a model that does
#: not declare it, exactly as a reserved name does — `extra="forbid"`'s generic "extra inputs are not
#: permitted" is a dead end for a column an author reached for *because* they had seen it elsewhere
#: (S17: a plausible name, rejected, with the reason discoverable only by reading the models).
#:
#: Kept as prose rather than as a cross-model registry, deliberately: `base` cannot import `spec`/`pgx`
#: to ask which models declare a name (the import cycle the vocabulary markers exist to avoid), and a
#: hand-kept list of models would be the drift this module keeps removing. A per-name sentence about a
#: stable table role does not go stale the way a column list does.
MISPLACED_COLUMN_REASONS: dict[str, str] = {
    "source": (
        "is recorded on GENERATED tables only — resolution.csv, frequencies.csv, gene_metrics.csv and "
        "literature.csv, where a pass names the link that answered. A hand-authored fact table has no "
        "such column by design: a curated annotation's provenance is the module's, not a per-row link. "
        "To declare a source you read by hand, add a ROW to sources.csv (whose own `source` column is "
        "the subject of the row, and is what the licence gate and manifest.sources join on)"
    ),
}


def reject_misplaced(data: object, declared: Iterable[str], what: str) -> object:
    """A `mode="before"` guard naming a column that is real elsewhere in the DSL but not on this model.

    Sits between `reject_reserved` (a name no model has, held against a future release) and
    `extra="forbid"` (an unknown or misspelled name). `declared` is the model's own field names, so a
    model that genuinely carries the column — `FrequencyRow.source` — is never touched, and the check
    cannot drift out of step with the models the way a second name list would."""
    if isinstance(data, dict):
        fields = frozenset(declared)
        hits = sorted(k for k in data if k in MISPLACED_COLUMN_REASONS and k not in fields)
        if hits:
            reasons = "; ".join(f"{h!r} {MISPLACED_COLUMN_REASONS[h]}" for h in hits)
            raise ValueError(f"column(s) not authored on a {what}: {reasons}.")
    return data


def reject_reserved(data: object) -> object:
    """A `mode="before"` guard for every authored model, layered *on top of* `extra="forbid"`.

    `extra="forbid"` already rejects any unknown column, but treats a reserved name and a random/typo'd
    one identically (the generic "extra inputs are not permitted"). This guard runs first and, when the
    raw input carries a reserved-namespace column (`RESERVED_NAMES_0_4`), raises a *specific* error
    stating what the name is reserved for and that a future release may claim it — so `reference_db`
    fails differently from `xyzzy`. (It said `caller` until 2026-08-12, which had stopped being true:
    `caller` was *dropped* from the reserved set rather than built, so it takes the generic message like
    any other stray column, and the example claimed a diagnosis the code no longer produces.) That is
    the reserved list's build-time (author/compile-time) value:
    reserved ≠ arbitrary at the point of failure, not merely in a published dictionary. A misspelled or
    genuinely-unknown column still falls through to `extra="forbid"`'s generic message (a hint to check
    the field list). Non-mapping input passes through untouched (pydantic handles it)."""
    if isinstance(data, dict):
        hits = sorted(k for k in data if k in RESERVED_NAMES_0_4)
        if hits:
            reasons = "; ".join(
                f"{h!r} {RESERVED_NAME_REASONS.get(h, 'an anticipated future axis')}" for h in hits
            )
            raise ValueError(
                f"reserved column name(s), not authorable fields: {reasons}. Reserved against the "
                f"one-way door (CONSTITUTION P3/P5) — a future release may claim them; do not author "
                f"them into a module. (Reserved now: {sorted(RESERVED_NAMES_0_4)}.)"
            )
    return data


def validate_field_token(value: str | None, field_name: str) -> str | None:
    """Validate a **VCF field-name pointer**: one bare token, optionally `|`-alternated (`CN|DS`).

    The grammar is what keeps such a column a *pointer* and not an expression — no operators, no
    whitespace, no code — which is what lets Principle 1 (declarative, data-not-code) hold while a
    module still says where in a VCF its quantity or its callability signal lives.

    Shared by `binning.MeasureBinRow.source_field` (the measured quantity) and
    `spec.VariantRow.callable_from` (the callability signal), so it lives on `AuthoredModel` rather
    than being copied per model."""
    if value is not None and not SOURCE_FIELD_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a bare VCF field-name token, optionally |-alternated "
            f"(e.g. REPCN, CN|DS) — a pointer, not an expression, got: {value!r}"
        )
    return value


def match_vocab(value: str, vocab: frozenset[str]) -> str | None:
    """The vocabulary member `value` names, treating `-` and `_` as the same separator.

    **A hyphen where an underscore goes is the most common slip in a hand-written cell**, and this
    format's whole premise is that the DSL is authorable by a human. `--use non-commercial` was
    already accepted by the enricher CLI, which normalized the separator on its way in, while the
    identical string in a `licensing.csv` cell was refused — so the surface an author learns the
    vocabulary from taught a spelling the file rejected.

    Both directions are tried rather than one, and the exact value first: no vocabulary in this
    schema carries a hyphenated member today, but trying the value as written before swapping means a
    future one cannot be broken by this function. A swap can never be ambiguous either — it would take
    two members differing *only* in their separators, which would be two spellings of one thing.

    Returns the canonical member (so the stored cell is always the declared spelling), or `None` when
    the value names nothing. Widening what a field accepts, never narrowing: every value that
    validated before still validates, which is what keeps this Principle 3-legal.
    """
    if value in vocab:
        return value
    for candidate in (value.replace("-", "_"), value.replace("_", "-")):
        if candidate in vocab:
            return candidate
    return None


def check_vocab(value: str | None, vocab: frozenset[str], field_name: str) -> str | None:
    """Validate an optional categorical against a closed `frozenset` vocabulary (Principle 6).

    Passes `None` through (absent = unknown), and canonicalizes a `-`/`_` separator slip to the
    declared member (see `match_vocab`). The message format matches the pre-refactor per-field
    validators exactly (`<field> must be one of [...], got: <value>`)."""
    if value is None:
        return None
    matched = match_vocab(value, vocab)
    if matched is None:
        raise ValueError(f"{field_name} must be one of {sorted(vocab)}, got: {value!r}")
    return matched


def validate_trait_ids(value: str | None, field_name: str = "trait_efo_id") -> str | None:
    """Validate a multi-valued CURIE cell: each `[,;|]`-split token must be an ontology CURIE."""
    if value is None:
        return value
    for tok in MULTI_SEP.split(value):
        tok = tok.strip()
        if tok and not TRAIT_ID_PATTERN.match(tok):
            raise ValueError(
                f"{field_name} tokens must be ontology CURIEs like EFO_0004340 / "
                f"MONDO:0005265, got: {tok!r}"
            )
    return value


def validate_allele(value: str | None, field_name: str = "allele") -> str | None:
    """Validate an optional nucleotide string (`^[ACGT]+$`, case-insensitive)."""
    if value is not None and not ALLELE_PATTERN.match(value):
        raise ValueError(f"{field_name} must be nucleotides (e.g. A, G, AC), got: {value!r}")
    return value


def validate_rsid(value: str | None) -> str | None:
    """Validate an optional dbSNP identifier (`rs<digits>`)."""
    if value is not None and not RSID_PATTERN.match(value):
        raise ValueError(f"rsid must match rs<digits>, got: {value!r}")
    return value


def population_sort_key(population: str) -> tuple[int, str]:
    """Deterministic sort key for an ancestry group: seeded groups in `POPULATION_ORDER`, then the
    rest alphabetically. Total and stable for any label, which is what the open vocabulary needs."""
    try:
        return (POPULATION_ORDER.index(population), "")
    except ValueError:
        return (len(POPULATION_ORDER), population)


def normalize_population(value: str) -> str:
    """Fold an ancestry-group label to its canonical form: stripped, lowercased, and a bare/empty
    label mapped to `global` (which is how gnomAD reports the whole-dataset row)."""
    token = (value or "").strip().lower()
    return token or "global"


def validate_population(value: str) -> str:
    """Validate an ancestry group against the OPEN seeded vocabulary.

    Enforces only that the label is a non-empty, well-formed token — membership in
    `RECOMMENDED_ANCESTRY_GROUPS` is a recommendation, not a gate (see the comment beside it). A
    label that is merely unfamiliar is kept, because the next source will bring its own naming; one
    that is *malformed* (empty, padded, or carrying a separator that would break a CSV cell or a
    group-by) is rejected, because that is a data error rather than a new source's naming.
    """
    if not value or value != value.strip():
        raise ValueError(f"population must be a non-empty label without padding, got: {value!r}")
    if not POPULATION_PATTERN.match(value):
        raise ValueError(
            f"population must be a lowercase token (letters, digits, underscore) — recommended: "
            f"{sorted(RECOMMENDED_ANCESTRY_GROUPS)}, got: {value!r}"
        )
    return value


def validate_finite(value: float | None, field_name: str) -> float | None:
    """Reject a non-finite float (`NaN`/`inf`). A `NaN` breaks round-trip equality (`NaN != NaN`
    makes `needs_upgrade`/idempotency checks oscillate) and serialises to the non-reloadable cell
    `"nan"`; an authored measure is always a finite number. Passes `None` through."""
    if value is not None and not math.isfinite(value):
        raise ValueError(f"{field_name} must be a finite number, got: {value!r}")
    return value
