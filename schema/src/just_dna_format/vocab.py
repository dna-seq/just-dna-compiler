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

# The symbolic/structural allele grammar (RM5). `alleles` is a stdlib-only leaf that imports nothing
# from this package, so the dependency runs one way and no cycle is possible.
from just_dna_format.alleles import (
    SYMBOLIC_ALLELE_TYPES,
    parse_symbolic_allele,
)

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
# A VCF field-name pointer: a key, optionally namespace-qualified (`INFO/DP`, `FORMAT/DP`), and the
# whole thing optionally `|`-alternated (`CN|DS`). Lives here rather than on `binning` because three
# models now point into a VCF this way — `source_field` names where the measured quantity is,
# `callable_from` where the callability signal is, `quality_from` where the confidence floor is stated
# — and a grammar shared by three models belongs on the leaf all three can import (see
# `validate_field_token` below).
#
# The key charset is the spec's own (§1.6.1.8 for INFO, §1.6.2 for FORMAT): a dot is legal *inside* a
# key, and `1000G` is a legal key beginning with a digit, reserved by name. The old grammar
# (`[A-Za-z_][A-Za-z0-9_]*`) allowed neither, so it claimed to describe VCF field names while refusing
# two shapes the spec names by hand (RM61). Widening only — every token that matched before still
# matches.
#
# One charset serves both namespaces, on purpose. The spec reserves the legacy `1000G` under INFO
# alone, so `FORMAT/1000G` is strictly speaking not a legal *header* key — but this is a pointer at a
# field, not a header being emitted, and splitting the grammar in two to refuse a spelling nobody
# writes buys a distinction with no consequence.

#: The two key namespaces. A VCF field is identified by namespace *and* name; the two reserved-key
#: tables overlap deliberately, so a bare name names two different fields (RM53).
VCF_NAMESPACES: frozenset[str] = frozenset({"INFO", "FORMAT"})
_VCF_KEY = r"(?:[A-Za-z_][0-9A-Za-z_.]*|1000G)"
_VCF_POINTER_ATOM = rf"(?:(?:INFO|FORMAT)/)?{_VCF_KEY}"
SOURCE_FIELD_PATTERN: re.Pattern[str] = re.compile(
    rf"^{_VCF_POINTER_ATOM}(?:\|{_VCF_POINTER_ATOM})*$"
)

# ── The VCF field model: namespace, and cardinality (RM53 / RM54) ────────────────────────────────
# A VCF field is identified by *namespace* (which of the two reserved-key tables it is drawn from) and
# described by *cardinality* (`Number`, which says how many values come back and what each one is of).
# A bare token names neither, and where both readings are type-compatible nothing detects the
# confusion: a consumer reads a well-formed number of the wrong kind and bins it without error.
#
# Both constants below are transcribed from the VCFv4.4 specification's own reserved-key tables and are
# fixed for that spec version — this is not a source convention (P2): nothing here describes what any
# particular caller emits, and a key the tables do not reserve is simply absent, which reads as
# *unknown* rather than as a claim (the house three-valued rule).

#: Keys reserved in **both** namespaces with different meanings. A bare one of these is ambiguous in a
#: way that costs a wrong answer rather than a parse error, which is why it earns its own warning.
VCF_COLLIDING_KEYS: frozenset[str] = frozenset(
    {"DP", "AD", "ADF", "ADR", "MQ", "AF", "CN"}
)

#: What each collision *costs* — the two readings, so a message can name them rather than saying
#: "ambiguous". Total over `VCF_COLLIDING_KEYS` (a test pins that).
VCF_COLLISION_REASONS: dict[str, str] = {
    "DP": (
        "INFO/DP is the combined read depth across all samples; FORMAT/DP is this sample's depth at "
        "the position"
    ),
    "AD": (
        "INFO/AD is the total read depth per allele across samples; FORMAT/AD is this sample's per "
        "allele depth"
    ),
    "ADF": (
        "INFO/ADF is the total forward-strand read depth per allele; FORMAT/ADF is this sample's"
    ),
    "ADR": (
        "INFO/ADR is the total reverse-strand read depth per allele; FORMAT/ADR is this sample's"
    ),
    "MQ": (
        "INFO/MQ is an RMS mapping quality typed Float; FORMAT/MQ is an RMS mapping quality typed "
        "Integer — the two differ in type, not only in scope"
    ),
    "AF": (
        "INFO/AF is the cohort allele frequency of the ALT; FORMAT/AF is not reserved by the spec but "
        "is universally emitted as this sample's allele fraction (VAF) — a heteroplasmy or tumour "
        "fraction is the second one, and the cohort frequency says nothing about this person"
    ),
    "CN": (
        "INFO/CN is the allele-specific copy number and FORMAT/CN is the sample's total copy number "
        "(redefined that way in VCF 4.4, §7.2) — the two answers differ by a factor of the ploidy"
    ),
}

#: `Number` per **qualified** key, from the reserved-key tables (VCF 4.4 §1.6.1.8 Table 1 for INFO,
#: §1.6.2 Table 2 for FORMAT, plus the structural/copy-number keys of §5.6). Deliberately partial: it
#: carries the reserved keys and nothing else, because a caller-specific key's cardinality is a source
#: convention this tier does not get to assert. An absent key is *unknown*, and unknown withholds.
VCF_FIELD_NUMBER: dict[str, str] = {
    # INFO — Table 1.
    "INFO/AA": "1",
    "INFO/AC": "A",
    "INFO/AD": "R",
    "INFO/ADF": "R",
    "INFO/ADR": "R",
    "INFO/AF": "A",
    "INFO/AN": "1",
    "INFO/BQ": "1",
    "INFO/CIGAR": "A",
    "INFO/CN": "A",
    "INFO/DB": "0",
    "INFO/DP": "1",
    "INFO/END": "1",
    "INFO/H2": "0",
    "INFO/H3": "0",
    "INFO/MQ": "1",
    "INFO/MQ0": "1",
    "INFO/NS": "1",
    "INFO/SB": "4",
    "INFO/SOMATIC": "0",
    "INFO/VALIDATED": "0",
    "INFO/1000G": "0",
    # FORMAT — Table 2.
    "FORMAT/AD": "R",
    "FORMAT/ADF": "R",
    "FORMAT/ADR": "R",
    "FORMAT/CN": "1",
    "FORMAT/CNL": "G",
    "FORMAT/CNP": "G",
    "FORMAT/CNQ": "1",
    "FORMAT/DP": "1",
    "FORMAT/EC": "A",
    "FORMAT/FT": "1",
    "FORMAT/GL": "G",
    "FORMAT/GP": "G",
    "FORMAT/GQ": "1",
    "FORMAT/GT": "1",
    "FORMAT/HQ": "2",
    "FORMAT/MQ": "1",
    "FORMAT/PL": "G",
    "FORMAT/PQ": "1",
    "FORMAT/PS": "1",
    "FORMAT/PSL": "P",
    "FORMAT/PSO": "P",
    "FORMAT/PSQ": "P",
}

#: What each multi-valued `Number` code means, for a message that explains rather than accuses.
VCF_NUMBER_MEANINGS: dict[str, str] = {
    "A": "one value per ALT allele, in ALT order",
    "R": "one value per allele, reference first",
    "G": "one value per genotype",
    "P": "one value per allele of the sample's GT",
    ".": "an unbounded list",
    "2": "a fixed pair",
    "4": "a fixed quadruple",
}

#: Which element of a multi-valued field a pointer means — a **closed set of named rules**, applied by
#: the consumer (RM54). Not an index: `AD[1]` is the first line of an expression grammar, which
#: Principle 1 refuses and which is the reason these pointers were a bare token to begin with. A named
#: rule is data, it terminates, and it needs no evaluator.
#:
#: "Element" means *one of the values the field carries for this record*, and that is deliberately
#: wider than a VCF `Number` slot. The spec's own multi-valued cardinalities (`A`, `R`, `G`, `P`, `.`)
#: are the common case, but a caller may also pack several values into a single cell —
#: ExpansionHunter's `REPCN` reports both repeat alleles as `17/42` — and a rule that only spoke about
#: `Number` would have nothing to say about the flagship case it was built for. How the values are
#: encoded is the caller's business and this tier holds no opinion on it (P2); which of them the
#: annotation means is the module's, and that is what this column states.
#:
#: The reference-inclusion trap is written into the vocabulary rather than left to a footnote: on a
#: `Number=R` field the reference is element zero, so "the larger of the two" has two answers. Every
#: ranging rule therefore comes in a pair — the bare name ranges over every value, the `_alt` name
#: ranges over the ALT elements only — and on a field with no reference element (`Number=A`, `G`, `P`,
#: `.`, or a packed cell of the sample's own alleles) the two coincide.
VALID_ELEMENT_RULES: frozenset[str] = frozenset(
    {
        "largest",
        "largest_alt",
        "smallest",
        "smallest_alt",
        "sum",
        "sum_alt",
        "annotated_alt",
        "reference",
    }
)

#: One sentence per member, total over `VALID_ELEMENT_RULES` (a test pins that). This is where the
#: reference-inclusion answer actually lives, so a member can never be silent about it.
#:
#: Every sentence speaks of *the values the field carries*, and none of them speaks of a sample's
#: alleles. `largest` used to illustrate itself as "the longer of the sample's two alleles", which is
#: a claim about a diploid record: on chrX outside the pseudoautosomal regions a male sample is
#: hemizygous and the repeat field carries one value, and fragile X is the presentation FMR1 is known
#: for (`reference_examples/fmr1_cgg_repeat`). The rule was always right there — the greatest of one
#: value is that value — but an author reading the illustration could reasonably conclude otherwise,
#: and these strings are printed into the authoring reference rather than being internal commentary.
ELEMENT_RULE_MEANINGS: dict[str, str] = {
    "largest": (
        "the greatest of the values the field carries for this record, the reference element included "
        "where the field has one (Number=R). This is the rule a dominant repeat expansion wants: the "
        "longest tract the record reports, whether the record carries one value or several, and "
        "counted even where the longest of them is the reference-length element"
    ),
    "largest_alt": (
        "the greatest element among the ALT elements only; on a Number=R field this skips element "
        "zero, which is the reference"
    ),
    "smallest": (
        "the least of the values the field carries for this record, the reference element included "
        "where the field has one (Number=R)"
    ),
    "smallest_alt": (
        "the least element among the ALT elements only; on a Number=R field this skips element zero, "
        "which is the reference"
    ),
    "sum": (
        "the sum of every value the field carries, the reference element included where the field has "
        "one — the denominator of an allele fraction computed from AD"
    ),
    "sum_alt": (
        "the sum of the ALT elements only; on a Number=R field this skips element zero, which is the "
        "reference"
    ),
    "annotated_alt": (
        "the element aligned with the ALT allele this row is about — the allele the consumer matched "
        "the record on, at its index in the record's ALT list, which is element index+1 on a "
        "Number=R field because element zero there is the reference. Where the row names no single "
        "ALT, or the record carries none of the ones it names, the rule decides nothing and a "
        "consumer withholds rather than picking"
    ),
    "reference": (
        "the reference element — element zero of a Number=R field. A field with no reference element "
        "(Number=A, G, P) has nothing for this rule to name, and a consumer withholds"
    ),
}

#: Every column that carries a VCF field pointer. The namespace question (RM53) is theirs equally —
#: `callable_from=DP` is the same error `source_field=AF` is, one column over — so the collision check
#: reads *this*, never `VCF_POINTER_COMPANIONS` below, which answers a different question.
VCF_POINTER_FIELDS: tuple[str, ...] = ("source_field", "callable_from", "quality_from")

#: Each element-rule column and the pointer column it qualifies. One map, so the pair rule, the
#: warning and the authoring reference read one relation instead of three copies of it.
#:
#: **One entry, deliberately.** The element rule (RM54) shipped on the binning tables' `source_field`
#: alone, because that is where the defect has an instantiation: `repeat_alleles.csv` is a table about
#: dominant repeat disorders, the clinical rule for HTT is *the larger of the two alleles*, and
#: `reference_examples/htt_repeat_expansion` stated four thresholds against a multi-valued field with
#: nowhere to say which value it meant. `callable_from` and `quality_from` can name a multi-valued
#: field too (`FORMAT/AD`), and no module does; under the 0.6 charter amendment an authored column
#: costs full price and `variants.csv` is the table every author writes, so those two wait for a real
#: case. Nothing is closed off — a companion column is additive whenever one is wanted (P3), the names
#: are held in `RESERVED_NAMES_0_4` so they survive the one-way door, and everything that reads this
#: map is generic over it.
VCF_POINTER_COMPANIONS: dict[str, str] = {
    "source_element": "source_field",
}

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
        # The two element-rule columns RM54 did *not* build (0.6). `source_element` shipped on the
        # binning tables; these are its companions on `VariantRow`'s two pointers, withheld because no
        # module points either at a multi-valued field and an authored column costs full price. They
        # are reserved rather than merely absent precisely because the symmetry makes them guessable:
        # an author who reasons "if source_field has one, callable_from must too" should hear what the
        # name is held for, not the generic stray-column message.
        "callable_element",
        "quality_element",
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
    "callable_element": (
        "would say which element of a multi-valued `callable_from` to read, the way `source_element` "
        "does for `source_field` — reserved, not built: no module points `callable_from` at a "
        "multi-valued field, and the columns a human writes are the expensive kind"
    ),
    "quality_element": (
        "would say which element of a multi-valued `quality_from` the `min_quality` floor is stated "
        "against — reserved on the same grounds as `callable_element`"
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
        "gwas_effect",
        "annotation",
    }
)

# `effect_measure` is intentionally NOT a closed vocabulary (kept permissive so PGS-Catalog
# `weight_type` additions survive). These are the recommended values, for documentation only.
#
# **Lives here rather than in `spec.py`, where it was defined until 0.6**, because `gwas.py` binds the
# same vocabulary and a fact-table module importing the authored-DSL module to reach a shared
# constant is the wrong direction of dependency. `spec.py` re-exports it, the same backward-compat
# pattern `VALID_CLIN_SIG` and `VALID_DIRECTIONS` already use, so no importer had to change.
RECOMMENDED_EFFECT_MEASURES: frozenset[str] = frozenset(
    {"OR", "HR", "RR", "beta", "log(OR)", "log(HR)", "NR"}
)

# Which way the effect allele moves the MEASURED TRAIT — the GWAS Catalog's `betaDirection` (RM90).
#
# **Not `VALID_DIRECTIONS`, and the separation is structural rather than stylistic.** That vocabulary
# is protective|risk|neutral|unknown and states a *clinical* judgement; this one states the sign of a
# beta. Increasing a trait may be good, bad or neither — increasing HDL and increasing LDL are both
# `increase` — so a field carrying both axes would be exactly the overloading Principle 5 forbids, and
# the anti-pattern `state` is being unwound for. The source keeps them apart; so do we.
VALID_EFFECT_DIRECTIONS: frozenset[str] = frozenset({"increase", "decrease"})

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

# ── The verification attestation (0.6, RM45) ────────────────────────────────────────────────────
# Which question a recorded check put. **Closed, and audited once here rather than grown ad hoc**: a
# free-string key would recreate the failure RM44 documents one level down — the enricher writing one
# spelling, a registry another, and a consumer substring-matching the difference — and a name is
# permanent within a major (Principle 3), so the set is fixed now against everything that could
# plausibly join it.
#
# The membership rule is one question: **does this compare something the module ASSERTS against what
# a source says?** That is what a consumer means by "was anything verified", and it is what keeps the
# axis single (P5). The set was audited against every pass in the tier — the table at the top of
# ENRICHER.md plus the compiler's own cross-checks — rather than written from memory, and the audit
# moved it twice, which is the argument for doing it once and completely:
#
# * `pgx_evidence_level` and `rsid_coordinate_agreement` were **missing**. Both are real
#   authored-vs-source comparisons that ship today (`clinpgx.enrich_clinpgx` → `EvidenceConflict`,
#   which is also the only enricher cross-check that raises under `strict`; and
#   `resolver._check_rsid_coord_consistency`, which is the enricher's half of the pair the compiler's
#   `resolution._verify` checks — one question, two tiers, so one name).
# * `gene_disease_validity` has **no emitter yet** and is kept on the `withdrawn` precedent: a member
#   exists for a case its emitter has not reached, and adding one later is legal while adding it *late*
#   means the release that needs it has no name to write. Note precisely what this is *not* a member
#   for — 0.6's `enrich_gene_validity` **records** ClinGen/GenCC verdicts into a derived table and
#   compares nothing authored, so it does not emit this. The member is for a future pass that checks an
#   authored gene/phenotype pair against those verdicts.
# * `genome_build_agreement` gained its emitter in the same release: `grch37.diagnose_wrong_build`
#   compares an authored coordinate against the other assembly, and the compiler's offline
#   `_check_build_coordinates` asks the cheap half of the same question.
#
# It deliberately **excludes** the ClinVar assertion tier, whose own docstring says it "records what
# ClinVar says and adjudicates nothing" — a member for it would let a manifest report a check where no
# question was put, the exact confusion this block exists to end. `frequencies.csv`,
# `gene_metrics.csv` and the article-licence columns are the same class and have no member either.
#
# **Every member says on its own line what puts it, or that nothing does (RM72).** Two of the
# seventeen are reserved — a member with no emitter is legitimate on the `withdrawn` precedent above,
# and the defect was that only one of the two said so, which is how a headline count of unreachable
# members read wrong. A comment per member, and it is free: the emitter is the first thing a reader
# asking "was this check run" needs, and it is the first thing to rot when a pass moves.
VALID_VERIFICATION_CHECKS: frozenset[str] = frozenset(
    {
        # ── wired: `enrich` writes these five at the end of its run ──
        "reference_allele",           # authored `ref` vs the actual reference sequence — `enrich`
        "rsid_currency",              # authored rsID vs dbSNP (live / merged / absent) — `enrich`
        "clinical_significance",      # authored `clin_sig` vs ClinVar's own, allele-exactly — `enrich`
        "rsid_coordinate_agreement",  # an authored rsID+coordinate PAIR vs the reference — `enrich`
        "genome_build_agreement",     # authored coordinates vs the declared assembly — `enrich`
        # ── wired: one command each ──
        "citation_existence",         # an authored `pmid`/`doi` vs PubMed and Crossref — `literature`
        "citation_identifier",        # an authored `doi` vs the registry's own for that PMID — `literature`
        "provenance_quote",           # `provenance_quote`/`provenance_regex` vs the text — `literature`
        "allele_function",            # authored `function_status` vs PharmVar and CPIC — `pgx`
        "pgx_evidence_level",         # authored `evidence_level` vs ClinPGx's own — `clinpgx check`
        "vrs_allele_id",              # a recorded `ga4gh:VA.…` vs the re-minted one — `vrs mint`
        "acmg_secondary_findings",    # authored `acmg_sf` vs the published SF gene list — `check-acmg`
        "gene_symbol_currency",       # authored `gene` vs HGNC approved / previous — `check-identifiers`
        "trait_currency",             # authored `trait_efo_id` vs OLS4 (obsolete + replacement) — `check-identifiers`
        "gene_locus_agreement",       # the row's `gene` vs the chromosome its variant sits on — `check-identifiers`
        # ── RESERVED: no emitter, deliberately. Adding one later is legal; adding the *name* late
        #    would leave the release that needs it with nothing to write (the `withdrawn` precedent).
        "gene_disease_validity",      # RESERVED — see the bullet above: `enrich_gene_validity` RECORDS
                                      #   ClinGen/GenCC verdicts into a derived table and compares
                                      #   nothing authored, so it does not emit this. The member is for
                                      #   a future pass that checks an authored gene/phenotype pair.
        "dosage_sensitivity",         # RESERVED — `enrich_dosage_sensitivity` is the same shape: it
                                      #   records ClinGen's haplo/triplo curation into `gene_metrics.csv`
                                      #   and no model carries an authored dosage claim to compare it
                                      #   against. The member is for the pass that gains one.
    }
)

# Why a check did not run. Closed for the same reason the names above are, and for one more: backfill
# triage branches on *why*, so prose here would relocate the substring matching rather than end it.
# The human sentence travels **beside** the key (`VerificationRecord.detail`), never instead of it —
# `clinical.tautology_reason` already writes a good one and stays exactly as it is.
#
# `not_requested` and `offline` are different facts about the same absence and must not be merged: one
# is a caller's choice, the other a capability the run did not have, and only the second is cleared by
# re-running with egress. `tautology` is S4's case — a check whose inputs share a source cannot fail,
# and reporting its zero is the misinformation the skip exists to prevent. `not_permitted` is
# `licensing.check_declared_use`'s outcome and is deliberately its own member: a check skipped because
# a source's terms bar the fetch is cleared by a *declaration*, not by egress or by a flag, so folding
# it into `offline` would send a reader looking for a network problem that does not exist.
#
# The set is the union of how the passes already spell their own skips (`skipped_offline`,
# `no_snapshot`, `unusable_snapshot`, `unchecked`, ClinPGx's licensing `skipped`), mapped onto one axis
# — which is the whole point: those six spellings are what a consumer would otherwise have to learn.
VALID_VERIFICATION_SKIPS: frozenset[str] = frozenset(
    {
        "not_requested",   # the caller switched this check off
        "offline",         # the check needs egress and the run had none
        "no_reference",    # no snapshot / sequence / list was provisioned to compare against
        "unreachable",     # the source was asked and never answered (a failed request, not a no)
        "nothing_to_check",  # the module carries no row this check applies to
        "tautology",       # the module was drafted from the very source the check reads (S4)
        "unsupported",     # this tier cannot put the question for these rows (e.g. an unbuilt assembly)
        "not_permitted",   # a source's terms bar the fetch under the declared use (`check_declared_use`)
    }
)

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


def split_field_pointer(value: str) -> list[tuple[str | None, str]]:
    """A pointer cell → its `(namespace, key)` atoms, in authored order.

    `|` is *alternation between fields* (try the first, fall back to the next) and never indexing, so
    a cell yields one atom per alternative. `namespace` is `None` for a bare key, which means
    **unqualified** — an honest absence, not a default: the whole point of RM53 is that guessing the
    namespace converts *unstated* into a *stated* answer, and it would be wrong for the very first
    module that used the column."""
    atoms: list[tuple[str | None, str]] = []
    for part in value.split("|"):
        head, sep, tail = part.partition("/")
        if sep and head in VCF_NAMESPACES:
            atoms.append((head, tail))
        else:
            atoms.append((None, part))
    return atoms


def vcf_field_number(namespace: str | None, key: str) -> str | None:
    """The `Number` the VCF spec reserves for this field, or `None` when it is not knowable here.

    Three-valued, and the third value is the common one. A qualified pointer is looked up directly.

    A **bare** key splits on whether it is a known collision. For a key only one namespace reserves,
    the bare form is not ambiguous at all — no INFO table defines `GQ` — so the single entry is the
    answer. For a colliding key both namespaces have to be in the table *and* agree: `AD` is `R`
    either way, so its cardinality is settled even though its meaning is not, while `CN` is `A` under
    INFO and `1` under FORMAT and has no answer until the pointer says which. `AF` is the case that
    makes the distinction load-bearing — the spec reserves `INFO/AF` and does **not** reserve
    `FORMAT/AF` (which every caller nevertheless emits), so reading the one known entry as the bare
    key's cardinality would answer a question about a field the spec never described.

    Anything the reserved tables do not carry (a caller's own key, `REPCN`) is unknown, and unknown
    withholds: asserting a cardinality for a field this tier has never seen described would be a
    source convention wearing a fact."""
    if namespace is not None:
        return VCF_FIELD_NUMBER.get(f"{namespace}/{key}")
    known = [
        VCF_FIELD_NUMBER[f"{ns}/{key}"]
        for ns in sorted(VCF_NAMESPACES)
        if f"{ns}/{key}" in VCF_FIELD_NUMBER
    ]
    if key in VCF_COLLIDING_KEYS and len(known) < len(VCF_NAMESPACES):
        return None
    return known[0] if len(set(known)) == 1 else None


def is_multi_valued_number(number: str | None) -> bool:
    """Whether a `Number` code describes a value list rather than a single value.

    `0` is a Flag (present or absent) and `1` is a scalar; everything else — `A`, `R`, `G`, `P`, `.`
    and the fixed counts `2`/`4` — returns more than one value, so a pointer at it names a list and
    not a number. `None` (unknown) is **not** multi-valued: withhold, never negate, and never accuse."""
    return number is not None and number not in {"0", "1"}


def validate_field_token(value: str | None, field_name: str) -> str | None:
    """Validate a **VCF field-name pointer**: a key, optionally namespace-qualified, optionally
    `|`-alternated (`FORMAT/REPCN`, `INFO/DP|FORMAT/DP`, `CN|DS`).

    The grammar is what keeps such a column a *pointer* and not an expression — no operators, no
    whitespace, no code — which is what lets Principle 1 (declarative, data-not-code) hold while a
    module still says where in a VCF its quantity, its callability signal or its confidence floor
    lives.

    Two widenings landed in 0.6, both strictly additive (P3 — every cell that validated before still
    validates and still means the same thing):

    * **The namespace qualifier** (RM53). A VCF field is identified by namespace *and* name, and the
      two reserved-key tables collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and — new in 4.4 — `CN`.
      A bare key stays legal and keeps meaning *unqualified*; the compiler warns when an unqualified
      one is a known collision, which is what stops the bare spelling from looking like a decision.
    * **The spec's own key charset** (RM61). A dot is legal inside a key and `1000G` is a legal key,
      both reserved by name; the previous grammar refused them while claiming to describe VCF field
      names.

    The namespace is matched case-sensitively, unlike the `-`/`_` slip `match_vocab` absorbs: `INFO/`
    and `FORMAT/` are how every VCF header, every spec table and `bcftools` spell it, so there is no
    established lowercase spelling for an author to slip into.

    Shared by `binning.MeasureBinRow.source_field` (the measured quantity),
    `spec.VariantRow.callable_from` (the callability signal) and `spec.VariantRow.quality_from` (the
    field the `min_quality` floor is stated against), so it lives on `AuthoredModel` rather than being
    copied per model."""
    if value is not None and not SOURCE_FIELD_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must be a VCF field-name pointer — a key, optionally qualified by its "
            f"namespace and optionally |-alternated (e.g. REPCN, FORMAT/REPCN, CN|DS, "
            f"INFO/DP|FORMAT/DP) — a pointer, not an expression, got: {value!r}. A namespace prefix "
            f"is one of {sorted(VCF_NAMESPACES)} followed by '/'."
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
    """Validate an optional allele: a nucleotide string (`^[ACGT]+$`, case-insensitive), or a
    symbolic/structural allele carrying its length (`<DEL:1500>`, `<CNV:TR:30>`) since 0.6 (RM5).

    **Two users, not one** — `HaplotypeRow.allele` and `VariantRow.effect_allele`. (`alleles.py` and
    CLAUDE.md both said "exactly one" until RM5; the count is what an author of a grammar change reads
    to size the blast radius.)

    A *lengthless* symbolic allele passes here and is refused later, by the compiler. That split is
    forced, not chosen: rejecting it at load makes the row fail to parse, which is fatal in **both**
    modes, and the decided behaviour is a warning-and-drop under `best_effort`. So the schema says
    what the DSL can spell and the compiler says what makes a usable rulebook.
    """
    if value is None or ALLELE_PATTERN.match(value):
        return value
    if parse_symbolic_allele(value) is not None:
        return value
    # The message names the length convention without claiming *this* validator enforces it — it does
    # not, deliberately (see the docstring), and the compiler is what refuses a lengthless one. An
    # author reading this is being rejected on the *type*, so telling them the full spelling here is
    # what stops the second rejection one command later.
    raise ValueError(
        f"{field_name} must be nucleotides (e.g. A, G, AC) or a symbolic/structural allele whose "
        f"first-level type is one of {sorted(SYMBOLIC_ALLELE_TYPES)} — the length belongs inside the "
        f"token (<DEL:1500>, <CNV:TR:30>), and a compile refuses one that states none. "
        f"Got: {value!r}"
    )


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
