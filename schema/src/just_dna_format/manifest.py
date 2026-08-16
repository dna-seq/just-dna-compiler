"""
The `manifest.json` contract — the single source of truth for a compiled annotation module.

Mirrors SPEC §4. Fields known at compile time (display, stats, compilation, inputs, artifact)
are filled by the compiler; marketplace-level fields (namespace, version, owner, published_at,
canonical_id) are `Optional` and filled by the marketplace on publish. `license` is the one hybrid:
since 0.5 an author may declare it in `module_spec.yaml` and the compiler copies it through, with the
marketplace still overriding on publish — the same advisory-then-stamped pattern as `version`.

This module is intentionally dependency-light (Pydantic + stdlib only) so both
`just-dna-pipelines` (which emits the manifest) and `just-dna-marketplace` (which consumes and
extends it) can share one definition without pulling heavy transitive dependencies.
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from just_dna_format.base import vocabulary
from just_dna_format.identity import (
    is_valid_version,
    validate_name,
    validate_namespace,
)
from just_dna_format.vocab import (
    RECOMMENDED_AUTHOR_KINDS,
    VALID_AUTHOR_ROLES,
    VALID_VERIFICATION_CHECKS,
    VALID_VERIFICATION_SKIPS,
    check_vocab,
)

MANIFEST_VERSION: str = "1.0"
SCHEMA_VERSION: str = "1.0"

# The only `compiled_by` value a downloader trusts (SPEC §5).
MARKETPLACE_COMPILED_BY: str = "marketplace-server"

# Mirrors just-dna-pipelines ModuleInfo.color validation (module_compiler/models.py).
COLOR_PATTERN: re.Pattern[str] = re.compile(r"^#[0-9a-fA-F]{6}$")

# Icon families a module may draw its no-logo fallback glyph from.
VALID_ICON_SETS: frozenset[str] = frozenset({"fomantic", "awesome"})
# Accepted raster logo extensions (lowercase, no dot).
LOGO_EXTENSIONS: frozenset[str] = frozenset({"png", "jpg", "jpeg"})

# Accepted readme extensions (lowercase, no dot). The markup is not parsed anywhere in this
# workspace — the extension travels in `FileEntry.name` so a consumer *rendering* the prose can tell
# markdown from plain text without sniffing the bytes.
README_EXTENSIONS: frozenset[str] = frozenset({"md", "txt", "rst"})
# Stems, in discovery precedence: the conventional uppercase spelling first.
README_STEMS: tuple[str, ...] = ("README", "readme")
# The full candidate set in discovery order, defined **once** because three parties must agree on it:
# the compiler discovers a readme, the enricher's publisher decides whether to upload it, and a
# registry decides what it may serve. A hand-kept second copy is the `locations` failure mode — every
# disagreement there was silent (a sidecar built and never published), and this file is on the same
# path. Stem is the outer loop, so `README.txt` beats `readme.md`; extensions sort `md` first.
README_CANDIDATES: tuple[str, ...] = tuple(
    f"{stem}.{ext}" for stem in README_STEMS for ext in sorted(README_EXTENSIONS)
)

# A curated authoring palette (RM9): recommended `Display.color`/`icon` values by semantic use, so an
# authoring UI / LLM picks from one shared set instead of inventing its own (just-dna-agents' MCP
# `list_colors`/`list_icons` are the drift this replaces). Recommendation only — NOT enforced: `color`
# is validated by `COLOR_PATTERN` and `icon` is free-form within `icon_set`. Icons name Fomantic UI
# glyphs (the default `icon_set`); colours are the Fomantic semantic hexes.
RECOMMENDED_COLORS: dict[str, str] = {
    "risk": "#db2828",
    "protective": "#21ba45",
    "neutral": "#767676",
    "pharmacogenomic": "#6435c9",
    "cardiometabolic": "#00b5ad",
    "cancer": "#f2711c",
    "neuro": "#a333c8",
    "info": "#2185d0",
    "reproductive": "#e03997",
}
RECOMMENDED_ICONS: dict[str, str] = {
    "default": "database",
    "dna": "dna",
    "cardiometabolic": "heartbeat",
    "cancer": "ribbon",
    "pharmacogenomic": "pills",
    "neuro": "brain",
    "lab": "flask",
    "protective": "shield",
    "reproductive": "baby",
}


class Identity(BaseModel):
    """Module identity. `namespace`/`version`/`canonical_id` are filled by the marketplace.

    Identity rules are validated here using the shared `just_dna_format.identity` helpers, so
    the contract enforces exactly what just-dna-pipelines enforces on `module_spec.yaml`.
    """

    namespace: str | None = Field(default=None, description="Owning account/org slug")
    name: str = Field(description="Machine name, matches ^[a-z][a-z0-9_]*$")
    version: str | None = Field(default=None, description="SemVer MAJOR.MINOR.PATCH")
    canonical_id: str | None = Field(
        default=None, description="namespace/name@version"
    )

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return validate_name(v)

    @field_validator("namespace")
    @classmethod
    def _check_namespace(cls, v: str | None) -> str | None:
        return None if v is None else validate_namespace(v)

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_version(v):
            raise ValueError(f"version must be MAJOR.MINOR.PATCH, got: {v!r}")
        return v


class Display(BaseModel):
    """Shared display metadata for a module. The authoring DSL's `spec.ModuleInfo` extends this
    (adding `name`), so the fields and their validation are defined here once."""

    title: str
    description: str
    report_title: str
    icon: str = Field(
        default="database", description="Icon name within `icon_set` — the no-logo fallback glyph"
    )
    icon_set: str = Field(
        default="fomantic",
        json_schema_extra=vocabulary("icon_set", VALID_ICON_SETS),
        description="Icon family for `icon`: 'fomantic' or 'awesome' (FontAwesome)",
    )
    color: str = Field(default="#6435c9", description="Hex color for UI theming")

    @field_validator("color")
    @classmethod
    def _check_color(cls, v: str) -> str:
        if not COLOR_PATTERN.match(v):
            raise ValueError(f"color must be a 6-digit hex code like #21ba45, got: {v!r}")
        return v

    @field_validator("icon_set")
    @classmethod
    def _check_icon_set(cls, v: str) -> str:
        if v not in VALID_ICON_SETS:
            raise ValueError(f"icon_set must be one of {sorted(VALID_ICON_SETS)}, got: {v!r}")
        return v


class Stats(BaseModel):
    """Card/detail stats derived from the spec at compile time.

    `clinvar_count`/`pathogenic_count`/`benign_count` summarize the per-row ClinVar quality flags
    that `weights.parquet` already carries, so consumers can facet on them without reading the
    artifact (SPEC ROADMAP item 5). They are additive and default to 0 for older manifests.
    """

    variant_count: int = 0
    weights_rows: int = 0
    study_count: int = 0
    gene_count: int = 0
    genes: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    clinvar_count: int = Field(default=0, description="Rows flagged in ClinVar")
    pathogenic_count: int = Field(default=0, description="Rows flagged ClinVar-pathogenic")
    benign_count: int = Field(default=0, description="Rows flagged ClinVar-benign")


class Compilation(BaseModel):
    """Provenance of the compile that produced this artifact (SPEC §5 trust fields)."""

    compile_success: bool = False
    compiled_by: str | None = Field(
        default=None, description="e.g. 'marketplace-server'; foreign values are untrusted"
    )
    compiler_version: str | None = None
    ensembl_reference: str | None = Field(
        default=None, description="Pinned Ensembl reference, e.g. org/repo@<rev>"
    )
    compiled_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp")
    warnings: list[str] = Field(default_factory=list)

    # ── 0.5 resolution provenance (all optional, out of artifact.digest) ──
    # Policy vs outcome are orthogonal axes (Principle 5), not one overloaded flag: `resolution_mode`
    # is what was *requested*, `fully_resolved` is what was *achieved*. A consumer trusts a module when
    # `resolution_mode == "strict" or fully_resolved`; the "half-baked" product is
    # `best_effort and not fully_resolved`.
    resolution_mode: str | None = Field(
        default=None, description="Resolution policy used: 'strict' | 'best_effort' (None = legacy/skipped)"
    )
    fully_resolved: bool = Field(
        default=False, description="Every in-scope VariantRow resolved to a genomic position (chrom+start)"
    )
    # The denominator `fully_resolved` quantifies over (RM44). That flag is `all(...)` over the module's
    # `VariantRow`s, so on a module carrying no `variants.csv` it is `all()` over an empty list —
    # **vacuously true**, and the trust rule three lines up then reads as a verdict about a module that
    # resolves nothing. It is not wrong; it simply cannot say which question it answered. Recording the
    # count beside it makes `fully_resolved=true, resolution_subjects=0` self-evidently vacuous, with no
    # new vocabulary and nothing for a consumer to parse out of prose.
    #
    # Same shape as `vrs_alleles`/`vrs_alleles_identified` below, whose comment already argues it: keep
    # the parts, compute the convenience. `0` means nothing was attempted, which is not the same as
    # nothing achieved — and the two are what a `bool` alone cannot separate.
    #
    # Deliberately additive rather than making `fully_resolved` tri-state: it is typed `bool`, consumers
    # branch on it directly, and a `None` would be a breaking read for every one of them.
    #
    # **It restates a number `Stats.weights_rows` also carries today, on purpose.** Measured across the
    # eleven reference examples, the two are equal everywhere, because the materializer emits exactly
    # one weights row per in-scope variant row. That equality is a property of the current transform,
    # not a contract — and `Stats` is documented as *card/detail stats*, i.e. display facets, so a
    # consumer deciding trust would be keying it on a coincidence in a block that does not promise one.
    # A denominator belongs beside the flag it qualifies. `compiler/tests/test_resolution_subjects.py`
    # pins the two together, so if they ever diverge that is a decision someone makes, not a drift.
    #
    # Counted **after** the one-to-many rsID expansion, because that is what `fully_resolved` iterates:
    # `pathogenic_clinvar` authors 328 rows and resolution applies to 337 loci.
    resolution_subjects: int = Field(
        default=0,
        description="Variant rows fully_resolved was evaluated over, after rsID expansion (0 = nothing attempted)",
    )
    resolution_signature: str | None = Field(
        default=None,
        description="Fact-hash of resolution.csv (integrity.resolution_signature); out of artifact.digest",
    )
    resolution_sources: list[str] = Field(
        default_factory=list, description="Sorted union of ResolutionRow.source values that filled the table"
    )

    # VA coverage, recorded as the two counts rather than a ratio or a bool. `fully_resolved` above is
    # the precedent and the analogy is exact: policy vs outcome, and this is the outcome for the
    # *content-addressed* identity where that one is the outcome for the coordinate. Two counts because
    # a consumer deciding whether it can key on the VA needs the shortfall's size, not just its
    # existence, and "complete" is then `vrs_alleles_identified == vrs_alleles` — derived, never stored
    # twice (the house pattern: keep the parts, compute the convenience). Both `0` means no resolution
    # table was present, i.e. nothing was attempted, which is not the same as nothing achieved.
    vrs_alleles: int = Field(
        default=0, description="Allele slots in resolution.csv (a multi-allelic site counts once per ALT)"
    )
    vrs_alleles_identified: int = Field(
        default=0, description="Of those, how many carry a ga4gh:VA. allele id"
    )

    # ── 0.6: how much of the 0.4 families a consumer can join by position (S31) ──
    # The counterpart of `resolution_subjects` for the three positional table kinds
    # (`pharm_variants.csv`, `haplotypes.csv`, `heteroplasmy.csv`), and the same parts-not-a-ratio
    # shape: "complete" is `positional_rows_placed == positional_rows`, derived rather than stored.
    #
    # **This is the structured field `compiler.UNJOINABLE_PHRASE`'s comment has been promising.** RM44
    # published `resolution_subjects` for `variants.csv` and recorded that the *positional* count
    # belonged with RM43; RM43 then shipped the fill without it, so the only surviving record of how
    # much of a PGx table joins to a VCF was still a **sentence** in `compilation.warnings`, which a
    # catalog substring-matches. A count is what a catalog wanted, and it says more than the phrase
    # ever did: the phrase says *some rows do not join*, these two say how many of how many.
    #
    # **`None` rather than `0` for both, and the distinction is the field's second job.** `0` is a real
    # answer — a module carrying no positional table at all — so a legacy manifest defaulting to it
    # would say "this module has no positional rows" about a 1,482-row `pharm_variants` artifact
    # compiled before the fill existed. That is the vacuous-`fully_resolved` failure one block up,
    # re-made in a field written to close it. `None` means *this compiler did not say*, which is what
    # every pre-0.6 manifest honestly is (`resolution_mode`'s "None = legacy/skipped" is the
    # precedent), and it lets a consumer tell the two eras apart from the manifest instead of probing
    # the parquet for nulls — which is exactly how the reporting consumer had to find out.
    #
    # Making these `None`-able costs nothing the way it would have for `fully_resolved`: that flag is
    # typed `bool` and consumers already branch on it, while nothing downstream reads a field that
    # does not exist yet.
    #
    # Counted **after** the positional fill and over the authored rows, so the two are the same
    # denominator the joinability warning uses. Not in `artifact.digest`, like every sibling here.
    positional_rows: int | None = Field(
        default=None,
        description=(
            "Rows across pharm_variants/haplotypes/heteroplasmy (None = compiled before 0.6, which "
            "did not fill or count them; 0 = the module carries no such table)"
        ),
    )
    positional_rows_placed: int | None = Field(
        default=None,
        description="Of those, how many carry chrom+start, hence join to a VCF by position",
    )


class Frequency(BaseModel):
    """Summary of a module's injected allele-frequency sidecar (0.5), out of `artifact.digest`.

    A separate block rather than extra fields on `Compilation`/`Resolution`: `Resolution` is about
    rsID↔coordinate resolution and nothing else, and a frequency table has its own producer, its own
    release, and its own fact-hash. Absent on a module that carries no `frequencies.csv`.
    """

    signature: str | None = Field(
        default=None,
        description="Fact-hash of frequencies.csv (integrity.frequency_signature); out of artifact.digest",
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of FrequencyRow.source values that filled the table"
    )
    datasets: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted union of FrequencyRow.dataset values, e.g. ['gnomad_v4.1_joint'] — which releases "
            "these numbers are from. A consumer reproducing an ACMG BA1/BS1 filter needs this to know "
            "it is filtering against the frequencies the curator saw."
        ),
    )
    populations: list[str] = Field(
        default_factory=list,
        description="Ancestry groups present in the table, in the canonical emission order",
    )
    row_count: int = Field(default=0, description="Number of frequency rows")
    variant_count: int = Field(
        default=0, description="Distinct alleles covered (rows are one per allele × ancestry group)"
    )


class GeneMetrics(BaseModel):
    """Summary of a module's injected gene-constraint sidecar (0.5), out of `artifact.digest`."""

    signature: str | None = Field(
        default=None,
        description="Fact-hash of gene_metrics.csv (integrity.gene_metrics_signature); out of artifact.digest",
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of GeneMetricsRow.source values"
    )
    datasets: list[str] = Field(
        default_factory=list, description="Sorted union of GeneMetricsRow.dataset values"
    )
    row_count: int = Field(default=0, description="Number of gene-metrics rows (one per gene)")
    genes: list[str] = Field(default_factory=list, description="Sorted gene symbols covered")


class GeneValidity(BaseModel):
    """Summary of a module's injected gene–disease validity sidecar (0.6, RM24).

    Out of `artifact.digest`, like every sibling block. `classifications` is emitted **sorted** rather
    than in strength order, for the reason `Frequency.populations` is emitted in canonical order and
    everything else sorted: a set-like facet has no order of its own, and a sorted list is the only one
    that cannot drift. A consumer that wants the ladder reads `vocab.ORDERED_GENE_VALIDITY`, which is
    published precisely so this block does not have to encode it.
    """

    signature: str | None = Field(
        default=None,
        description=(
            "Fact-hash of gene_validity.csv (integrity.gene_validity_signature); out of artifact.digest"
        ),
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of GeneValidityRow.source values"
    )
    datasets: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted union of GeneValidityRow.dataset values, e.g. "
            "['clingen_gene_validity_2026-08-13'] — which curation releases these verdicts are from."
        ),
    )
    row_count: int = Field(default=0, description="Number of assertions recorded")
    genes: list[str] = Field(default_factory=list, description="Sorted gene symbols covered")
    diseases: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted disease CURIEs asserted against, so a catalog can index a module by condition "
            "without opening the parquet."
        ),
    )
    classifications: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted union of the strengths present. Read it as a set, not a verdict: a module whose "
            "list contains 'refuted' carries a gene somebody has argued against, which is information "
            "rather than a defect."
        ),
    )
    submitters: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted union of who made the assertions — an expert panel on ClinGen, a laboratory on "
            "GenCC. Published because on an aggregate the submitter is half the claim."
        ),
    )


class ClinicalAssertions(BaseModel):
    """Summary of a module's injected clinical-assertion sidecar (0.6, RM25).

    The counters exist for the same reason `Literature`'s do: the point of the table is that a
    one-star single submission and a practice guideline are not the same claim, so a summary that
    reported only a row count would throw away exactly what was gained. `max_review_stars` and
    `min_review_stars` are the two ends a catalog can filter on without reading the parquet —
    published as the two counts rather than an average, which would be a number describing no record.
    """

    signature: str | None = Field(
        default=None,
        description=(
            "Fact-hash of clinical_assertions.csv (integrity.clinical_assertion_signature); out of "
            "artifact.digest"
        ),
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of ClinicalAssertionRow.source values"
    )
    datasets: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted union of the archive releases these records are from, e.g. ['clinvar_2026-06-27']."
        ),
    )
    row_count: int = Field(default=0, description="Number of archive records recorded")
    variant_count: int = Field(
        default=0,
        description=(
            "Distinct alleles covered. Lower than `row_count` whenever the archive holds several "
            "records for one allele under different conditions, which is ordinary."
        ),
    )
    clin_sigs: list[str] = Field(
        default_factory=list,
        description="Sorted union of the clinical calls present, in the module vocabulary",
    )
    min_review_stars: int | None = Field(
        default=None,
        description=(
            "Lowest star rating any recorded record carries, or null when none states a review status. "
            "Null is not zero: 0 is the rating 'no assertion criteria provided', and a module with no "
            "rated record at all has made no such claim."
        ),
    )
    max_review_stars: int | None = Field(
        default=None,
        description=(
            "Highest star rating any recorded record carries, or null when none states one. Read the "
            "pair together — a module spanning 0 to 4 is mixing evidence tiers, which is the thing "
            "this table was built to make visible."
        ),
    )
    unrated_count: int = Field(
        default=0,
        description=(
            "Records whose review status the archive did not state (`review_stars` is null). Reported "
            "separately from a 0-star record for the reason above."
        ),
    )
    not_found_count: int = Field(
        default=0,
        description=(
            "Alleles the archive was consulted about and has no record for (`status` is 'not_found'). "
            "A fact about the archive, not a gap in the pass — an allele nobody asked about has no row."
        ),
    )


class Literature(BaseModel):
    """Summary of a module's injected citation sidecar (0.5), out of `artifact.digest`.

    No `datasets` field, unlike its two siblings: PubMed and Europe PMC publish no release identifier,
    so there would be nothing true to put in it. The coverage counters take its place — and they are
    what a reader actually needs, because the fulltext check is *partial by nature* and a summary that
    hid that would read as "all citations verified" when most of them were never retrievable.
    """

    signature: str | None = Field(
        default=None,
        description="Fact-hash of literature.csv (integrity.literature_signature); out of artifact.digest",
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of LiteratureRow.source values"
    )
    row_count: int = Field(
        default=0,
        description=(
            "Number of citations covered (one row each). **The module's current citations**, not "
            "every row in literature.csv: that table is merge-not-clobber, so it keeps a row for a "
            "citation since deleted from studies.csv, and the compiler leaves such a row out of the "
            "artifact (RM79). Every count below shares this denominator."
        ),
    )
    resolved_count: int = Field(
        default=0, description="Citations PubMed returned a record for (`exists` is true)"
    )
    missing_count: int = Field(
        default=0,
        description=(
            "Citations PubMed has no record for (`exists` is false) — a nonexistent PMID, which is a "
            "defect in the module rather than a gap in coverage. Counted over `row_count`, so it "
            "agrees with the `citation_existence` verification record by construction; before RM79 "
            "it counted the whole table and the two could differ with nothing wrong in the module."
        ),
    )
    open_access_count: int = Field(
        default=0, description="Citations with retrievable open-access fulltext"
    )
    abstract_only_count: int = Field(
        default=0,
        description=(
            "Citations whose quotes could only be matched against the abstract. A hit there is "
            "conclusive; a miss is not, because the body was never searched."
        ),
    )
    quotes_authored: int = Field(
        default=0, description="Provenance quotes/regexes authored across all study rows"
    )
    quotes_found: int = Field(
        default=0,
        description=(
            "Of those, how many were located in a fulltext. Read it against `quotes_authored` AND "
            "`open_access_count`: an unfound quote in a paywalled article was never checked, not "
            "checked and missing."
        ),
    )


class Sources(BaseModel):
    """Summary of a module's data-source licensing sidecar (0.5), out of `artifact.digest`.

    **The per-layer facets are lists, and collapsing them to booleans would be a defect.** A module
    that used CPIC only to resolve a coordinate and one that embeds ClinPGx annotation prose would
    render identically under a single `share_alike: bool`, falsely marking the first as viral. The
    lists say *which layer* carries the obligation, so a reader can tell those apart.

    `commercial_use` is the one derived scalar, because it is the one question with a single answer
    for the module as a whole: most-restrictive-wins. One restricted source at the annotation layer
    makes the whole module non-sellable, and mixing in a permissive source cannot launder it.
    """

    signature: str | None = Field(
        default=None,
        description="Fact-hash of sources.csv (integrity.source_signature); out of artifact.digest",
    )
    sources: list[str] = Field(
        default_factory=list, description="Sorted union of SourceRow.source values"
    )
    layers: list[str] = Field(
        default_factory=list, description="Sorted union of the layers any source contributed to"
    )
    licenses: list[str] = Field(
        default_factory=list, description="Sorted union of SourceRow.license values"
    )
    attributions: list[str] = Field(
        default_factory=list,
        description="Sorted union of required credit lines — what a redistributor must reproduce",
    )
    notices: list[str] = Field(
        default_factory=list,
        description="Sorted union of use restrictions stated in the terms (e.g. not for diagnostic use)",
    )
    share_alike_layers: list[str] = Field(
        default_factory=list,
        description="Sorted layers carrying a ShareAlike obligation (empty ≠ 'no obligation known')",
    )
    noncommercial_layers: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted layers whose source forbids sale. Read it WITH `commercial_use`, not instead of "
            "it: only an 'annotation' entry makes the module non-sellable, so a list of "
            "['resolution'] beside `commercial_use: true` is consistent and is the point — a source "
            "used purely to look up a coordinate contributed a fact, not expression."
        ),
    )
    unknown_terms_sources: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted sources whose terms could not be established (commercial_use is null). Reported "
            "separately from the forbidding ones: unknown is not permission, and not a finding either."
        ),
    )
    nonredistributable_layers: list[str] = Field(
        default_factory=list,
        description=(
            "Sorted layers whose source forbids passing the data on at all (academic-use-only terms). "
            "Read WITH `redistribution`, the same way noncommercial_layers pairs with commercial_use."
        ),
    )
    declared_uses: list[str] = Field(
        default_factory=list, description="Sorted union of SourceRow.declared_use values"
    )
    commercial_use: bool | None = Field(
        default=None,
        description=(
            "Derived module-wide verdict, most-restrictive-wins: false when ANY annotation-layer "
            "source forbids sale, else null when any source's terms are unknown, else true. Null "
            "means undetermined, never permitted."
        ),
    )
    redistribution: bool | None = Field(
        default=None,
        description=(
            "Derived module-wide verdict on whether the module may be passed on at all, on the same "
            "most-restrictive-wins ladder as `commercial_use`. Distinct from it: a module can be "
            "freely shareable but unsellable (CC BY-NC), or sellable-in-principle but unshareable "
            "under an academic-use-only source. Null means undetermined, never permitted."
        ),
    )
    row_count: int = Field(default=0, description="Number of (source, layer) rows")


class FileEntry(BaseModel):
    """One hashed file — used for both `inputs[]` and `artifact.files[]` (SPEC §5)."""

    name: str
    sha256: str = Field(description="Lowercase hex digest, prefixed 'sha256:'")
    size: int = Field(description="Byte size of the file")


class Artifact(BaseModel):
    """The compiled output set plus its Merkle-root digest (the content identity)."""

    digest: str = Field(description="sha256: over the canonical file listing (SPEC §5)")
    files: list[FileEntry] = Field(default_factory=list)


class GenePanelSpec(BaseModel):
    """Declares a module derived from a *gene set + significance predicate* over a reference,
    rather than an enumerated variant table (SPEC ROADMAP item 7).

    **Deprecated in 0.6, removed at 1.0 (RM4).** Compile-time materialization was dropped rather than
    built: the compiler must not create rows no curator wrote, and expanding a declaration at compile
    would make a module's content depend on an external file while leaving `reverse` to choose between
    re-emitting the declaration (rows lost) and the rows (declaration lost) — neither a fixed point.
    The want is served by enricher draft-scaffolding, where the rows are authored bytes before the
    compiler sees them and the author's no-op over the drafted subset is still an authorial act. The
    block's one remaining machine reader — the enricher's ClinVar `clin_sig` cross-check, deciding
    whether a drafted module is being compared against its own source — now reads the licence row's
    `dataset` column instead, which the drafting pass writes itself.

    This is the authored *interface* only: the compiler records it verbatim but does not
    materialize it (an app-level adapter enumerates the matching variants into `variants.csv`
    today). Optional and backwards-compatible — absent on ordinary variant modules.

    `extra="forbid"` so a typo in the authored `panel:` block is caught, not silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Reference the panel resolves against, e.g. 'clinvar'")
    reference: str | None = Field(
        default=None, description="Reference release/version id, e.g. a ClinVar release date"
    )
    reference_sha256: str | None = Field(
        default=None, description="Digest pinning the exact reference resource (sha256:...)"
    )
    genes: list[str] = Field(
        default_factory=list, description="Panel gene symbols; empty = genome-wide (no gene filter)"
    )
    significance: list[str] = Field(
        default_factory=list,
        description="Significance predicate, e.g. ['pathogenic', 'likely_pathogenic']",
    )


class ProvenanceItem(BaseModel):
    """One per-variant provenance record (SPEC ROADMAP item 1). Lives in the full `provenance.json`
    document, not in the manifest — the manifest carries only the `Provenance` summary pointer."""

    variant_key: str = Field(description="rsid or chrom:start:ref, matching VariantRow.variant_key")
    rationale: str | None = Field(default=None, description="Why this annotation was made")
    reviewer_verdict: str | None = Field(default=None, description="Reviewer's verdict, if any")
    confidence: float | None = Field(default=None, description="Author/model confidence 0..1")
    human_reviewed: bool = Field(default=False, description="A human reviewed this item")


class ProvenanceDoc(BaseModel):
    """The full `provenance.json` authored beside the spec: a header plus per-variant items. The
    compiler reads and hashes it, then records the lean `Provenance` summary in the manifest so
    catalog cards can flag 'AI-authored · rationale available' without inlining the full text."""

    generator: str | None = Field(default=None, description="Tool/pipeline that produced items")
    model: str | None = Field(default=None, description="Model id, if AI-authored")
    agent_version: str | None = Field(default=None, description="Agent/framework version")
    items: list[ProvenanceItem] = Field(default_factory=list)


class Provenance(BaseModel):
    """Lean summary pointer to a version's `provenance.json` (SPEC ROADMAP item 1). The full items
    live in the hashed file (kept out of `artifact.digest`, like `logs`); this rides in the manifest."""

    generator: str | None = None
    model: str | None = None
    agent_version: str | None = None
    item_count: int = 0
    file: str | None = Field(
        default=None, description="Path to the provenance document relative to the module dir"
    )
    sha256: str | None = Field(default=None, description="sha256: of the provenance document")


#: The untrusted-value warning every verification field repeats. `compiled_by`'s description has said
#: it since the beginning for one field; here it has to be said on every one, because a *forged pass is
#: worse than silence* — a consumer that reads "the clinical calls were cross-checked" off a manifest
#: it did not produce, and believes it, is worse off than one that reads nothing at all. Neither the
#: binding hash nor the proof-of-work below changes that: they defend against a **stale** record on an
#: honestly-produced module, which is the accidental case, and nothing here is built to resist a
#: deliberate one.
UNTRUSTED_NOTE: str = (
    "Foreign values are untrusted: this records what a producer SAYS it checked, and only a "
    "consumer holding the module's own bytes can confirm it."
)


class Signature(BaseModel):
    """Optional detached signature over `artifact.digest` (SPEC §5 'future'). Defends against a
    compromised storage backend: a client that pins the marketplace's public key can prove the
    digest was signed by the trusted party.

    Declared here rather than beside `ModuleManifest`, where it sat until 0.6, because `Closure`
    below signs a different hash with the identical shape. Nothing about it is artifact-specific:
    the signed message is whichever digest string the caller hands `signing.sign_digest`.
    """

    algorithm: str = Field(default="ed25519", description="Signature algorithm")
    public_key: str = Field(description="Base64 (raw) Ed25519 public key")
    signature: str = Field(description="Base64 signature over the artifact.digest string bytes")
    signed_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp")


class Closure(BaseModel):
    """The author's statement that this authored set is **finished** (RM73).

    Authoring is a process and until 0.6 it had no end. Every check that needed to know where a value
    came from had to guess, and each guessed differently, because a flat CSV row records nothing about
    how it came to be. The provenance half of RM73 answered *did this cell move* by hashing what a
    drafting provider wrote; this answers the other question — *is the author done* — and the two are
    genuinely different, which is why one is a column on a licence row and this is a signable act.

    **What it binds is the document's `module_hash`, and nothing here re-derives it.** The closure
    rides inside `VerificationDoc`, whose binding the compiler already recomputes and drops on
    mismatch, so an author who edits a row after closing loses the closure *for free* — the same
    perishability the check records have, arrived at by carrying no second copy of the hash. That is
    the whole mechanism: no new file, no new binding, and no entry in `verification.pow_digest`, whose
    payload is deliberately unchanged so that closing a document re-mines nothing and every
    attestation written before this still verifies.

    **`closed_by` is untrusted and `signature` is not.** A name in a JSON file is a claim anyone can
    type; the Ed25519 signature over `module_hash` is what makes the act attributable, using the same
    `signing.sign_digest` / `integrity.verify_signature` pair the artifact signature uses. Signing is
    optional — an unsigned closure is still change-evident, which is the guarantee this format offers
    (tamper-*evidence*, never tamper-proofing) — and a **present** signature that does not verify
    drops the whole block, because a false claim is worse than silence.
    """

    model_config = ConfigDict(extra="forbid")

    closed_at: str = Field(description="ISO-8601 UTC timestamp of the closing act")
    closed_by: str | None = Field(
        default=None,
        description=(
            "Who closed authoring, as free text. Legibility only — the signature below is what makes "
            f"this attributable. {UNTRUSTED_NOTE}"
        ),
    )
    signature: Signature | None = Field(
        default=None,
        description=(
            "Optional Ed25519 signature over the document's `module_hash` string bytes. Verified by "
            "`verification.attestation_failure`, which drops the block when a present one fails."
        ),
    )


class VerificationRecord(BaseModel):
    """One check, and what putting it produced — the row grain of `verification.json` (RM45).

    A module whose clinical-significance calls were cross-checked against ClinVar and one where that
    check never ran used to ship **identical** manifests: not through an oversight in some path, but
    because no field existed that could differ. This is the record that can.

    **Two counts, never a boolean, and never one union-typed slot.** `subjects` is what the check was
    evaluated over and `findings` is what it turned up, so *ran against nothing* (`subjects=0`,
    `skipped=None`) and *did not run* (`skipped` set) can never occupy the same value.
    `vrs_alleles`/`vrs_alleles_identified` is the precedent and the argument is the same one: an
    unstated denominator is the defect, because coverage of an unknown fraction is not something
    anything can key on.

    **`skipped` is a closed vocabulary with the sentence beside it, not instead of it.** Backfill
    triage branches on *why* a pass did not run, so prose in that slot would relocate the substring
    matching RM44 documents rather than end it. `detail` is where the good sentence goes —
    `clinical.tautology_reason` already writes one, and it stays exactly as it is.
    """

    model_config = ConfigDict(extra="forbid")

    check: str = Field(
        json_schema_extra=vocabulary("verification_check", VALID_VERIFICATION_CHECKS),
        description=f"Which question was put (VALID_VERIFICATION_CHECKS). {UNTRUSTED_NOTE}",
    )
    subjects: int = Field(
        default=0,
        description=(
            "Rows the check was evaluated over — the denominator. 0 with no `skipped` means the "
            f"check ran and had nothing in scope, which is not the same as not running. {UNTRUSTED_NOTE}"
        ),
    )
    findings: int = Field(
        default=0,
        description=f"Of those, how many disagreed with the source. {UNTRUSTED_NOTE}",
    )
    skipped: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("verification_skip", VALID_VERIFICATION_SKIPS),
        description=(
            "Why the check did not run (VALID_VERIFICATION_SKIPS), or null when it did. "
            f"{UNTRUSTED_NOTE}"
        ),
    )
    detail: str | None = Field(
        default=None,
        description=(
            "The human sentence beside the machine key — the reason in full, or a note about what "
            f"was compared. Outside the fact set, so rewording it moves no signature. {UNTRUSTED_NOTE}"
        ),
    )
    source: str | None = Field(
        default=None,
        description=(
            "Which source answered, joining to the `source` column the licensing table keys on "
            f"(e.g. 'clinvar', 'hgnc', 'pubmed'). Null when the check needed none. {UNTRUSTED_NOTE}"
        ),
    )
    release: str | None = Field(
        default=None,
        description=(
            "Which release of that source it was checked against, as the source states it (a "
            "snapshot's `release.json`, a list version). Null when the source publishes none — "
            f"PubMed is continuously updated and has nothing true to put here. {UNTRUSTED_NOTE}"
        ),
    )
    checked_at: str | None = Field(
        default=None,
        description=(
            "ISO-8601 UTC timestamp of the run that put this check. Producer noise, so it is outside "
            f"the fact set. {UNTRUSTED_NOTE}"
        ),
    )

    @field_validator("check")
    @classmethod
    def _check_name(cls, v: str) -> str:
        checked = check_vocab(v, VALID_VERIFICATION_CHECKS, "check")
        if checked is None:
            raise ValueError("check is required")
        return checked

    @field_validator("skipped")
    @classmethod
    def _check_skip(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_VERIFICATION_SKIPS, "skipped")

    @field_validator("subjects", "findings")
    @classmethod
    def _check_counts(cls, v: int) -> int:
        if v < 0:
            raise ValueError("a count must not be negative")
        return v

    @model_validator(mode="after")
    def _check_consistent(self) -> "VerificationRecord":
        # A record that says both "this did not run" and "it looked at 12 rows" contradicts itself,
        # which is the class the compiler treats as fatal wherever else it appears (an id recorded
        # against no coordinate, two rows disagreeing about `ref`). Refusing at load keeps the two
        # fields' meanings from blurring into "how far did it get".
        if self.skipped is not None and (self.subjects or self.findings):
            raise ValueError(
                f"check {self.check!r} is recorded as skipped ({self.skipped!r}) and also as having "
                f"looked at {self.subjects} row(s) with {self.findings} finding(s) — a skipped check "
                f"has no subjects. Record the skip, or record the counts, not both."
            )
        if self.findings > self.subjects:
            raise ValueError(
                f"check {self.check!r} reports {self.findings} finding(s) out of {self.subjects} "
                f"subject(s); a finding is one of the rows the check was evaluated over."
            )
        return self


class VerificationDoc(BaseModel):
    """The full `verification.json` beside the spec: an attestation over a list of check records.

    **Why this is a document and not a fifth fact CSV.** The object has two levels — one attestation
    covering many records — and a CSV can express that only by carrying a non-data service row (the
    shape RM36 rejected on `genome_build`, for exactly the reason it applies here: a data table would
    hold a row that is not data) or by repeating the attestation on every row, where two rows can then
    disagree about a per-run fact. `provenance.json` is the standing precedent for the shape that
    fits: a JSON document beside the spec, read and hashed by the compiler, summarized into a manifest
    block.

    There is a second reason, and the charter names it. The 0.6 amendment observes that a derived
    table which is **both machine-written and human-overridable** can be edited into a state that is
    not merely stale but is a false claim, and that this "wants a mechanism rather than a convention".
    Every CSV sidecar is overridable on purpose — a curator correcting a row the enricher wrote is the
    designed path. An attestation is the one derived thing where that must not silently pass, so it is
    deliberately not in the family whose overridability is a feature.

    **The mechanism, and its exact modesty.** `module_hash` binds the record to the authored bytes it
    was computed over, and `nonce` is a proof-of-work over that binding plus the records' own
    signature. Both exist to stop an **accidental** forgery — an attestation left behind by an edit,
    or copied between modules — and nothing here is built as though the library were hack-resistant,
    because it is not and does not claim to be. A reader who wants a guarantee wants
    `manifest.signature`, which is a real one.
    """

    model_config = ConfigDict(extra="forbid")

    module_hash: str = Field(
        description=(
            "The authored bytes this attestation was computed over "
            "(`verification.module_binding`). The compiler recomputes it and drops the whole block "
            "when it no longer matches."
        )
    )
    signature: str = Field(
        description="Fact-hash of `records` (`verification.verification_signature`)"
    )
    difficulty: int = Field(
        description=(
            "Leading zero bits the proof-of-work meets. Recorded rather than assumed so a document "
            "written under one difficulty is still checkable after the constant moves; a reader "
            "requires at least its own minimum."
        )
    )
    nonce: int = Field(
        description=(
            "The SMALLEST nonce counting up from zero that meets `difficulty`. Smallest, never a "
            "random search: a random one would give the file different bytes on every run for the "
            "same content, which is the determinism the round-trip tests pin everywhere else."
        )
    )
    producer: str | None = Field(
        default=None,
        description=f"Tool and version that put the checks, e.g. 'just-dna-enricher 0.6.0'. {UNTRUSTED_NOTE}",
    )
    produced_at: str | None = Field(
        default=None, description="ISO-8601 UTC timestamp of the run that wrote this document"
    )
    closure: Closure | None = Field(
        default=None,
        description=(
            "The author's statement that this authored set is finished (RM73). Absent on a module "
            "still being authored, which is the ordinary state and the one every module was in "
            "before 0.6. Carried here rather than in a file of its own so it inherits this "
            "document's binding, its staleness check and its transport."
        ),
    )
    records: list[VerificationRecord] = Field(
        default_factory=list, description="One record per check, at most one per check name"
    )

    @model_validator(mode="after")
    def _check_unique(self) -> "VerificationDoc":
        names = [r.check for r in self.records]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(
                f"verification records must be one per check; {duplicated} appear more than once. "
                f"A second record for one check is a re-run, and a re-run replaces rather than "
                f"accumulates — merge before writing."
            )
        return self


class Verification(BaseModel):
    """What a module can say about whether anything it asserts was ever CHECKED (RM45).

    **Absent on a module nothing verified, and absent on one whose attestation no longer matches its
    bytes.** Both read correctly as *says nothing*, which is the only safe default: a block that
    survived an edit would say a check passed over rows it never saw.

    On `Frequency`'s precedent — a separate block rather than fields on `Compilation`, because this
    has its own producer, its own releases and its own fact-hash. It departs from that sibling in one
    way, deliberately: `Frequency` carries derived facets (`sources`, `datasets`, `populations`)
    because its rows stay in the sidecar and never reach the manifest, while these records are few and
    are embedded whole, so a union list here would restate what is already two lines below it. Keep
    the parts, compute the convenience.

    **Nothing in this block is trusted.** Every field repeats it, because the first consumer to read a
    pass off an untrusted manifest will otherwise believe it, and a forged pass is worse than silence.
    """

    signature: str | None = Field(
        default=None,
        description=(
            "Fact-hash of the check records (`verification.verification_signature`); out of "
            f"artifact.digest. {UNTRUSTED_NOTE}"
        ),
    )
    module_hash: str | None = Field(
        default=None,
        description=(
            "The authored bytes the checks were put against. The compiler confirmed this matched the "
            "spec it compiled — that is what presence of this block means, and it is the whole of "
            f"what it means. {UNTRUSTED_NOTE}"
        ),
    )
    producer: str | None = Field(
        default=None,
        description=f"Tool and version that put the checks. {UNTRUSTED_NOTE}",
    )
    produced_at: str | None = Field(
        default=None,
        description=f"ISO-8601 UTC timestamp of the verifying run. {UNTRUSTED_NOTE}",
    )
    closure: Closure | None = Field(
        default=None,
        description=(
            "The author's statement that authoring was finished over these bytes (RM73), when the "
            "module carries one. Its presence here means the compiler confirmed the binding and, if "
            f"the closure was signed, that the signature verifies. {UNTRUSTED_NOTE}"
        ),
    )
    checks: list[VerificationRecord] = Field(
        default_factory=list,
        description=(
            "One record per check put, carrying its counts, its skip reason, and the source release "
            f"it was checked against. {UNTRUSTED_NOTE}"
        ),
    )


class Contribution(BaseModel):
    """One authorship contribution to *this version* of a module (RM14; docs/USE_CASES.md §5a).

    Three orthogonal axes (Principle 5), unbundling the flat `authors`/free-form `curator`:
    `who` (identity), `role` (what they did — closed vocab), and `kind` (a multi-valued tag set
    describing the contributor: a human ladder of assurance `human` → `human_expert` →
    `human_certified`, or `ai` with a scale tag `agent`/`team`/`swarm` — open, so new tags may be
    coined). A joint contribution is two entries (a human and an ai), each with its own `kind`, so
    the mix is always spelled out and there is no lossy `hybrid` tag.

    Module metadata: carried in the manifest, **out of `artifact.digest`** (like `provenance`/`logs`),
    so two versions with identical annotation content but different authorship share a content
    identity. A consumer (the network validator, a review queue, a human auditor) routes its scrutiny
    by `kind` — the format carries the kind, the consumer picks the profile (the data-agnostic north
    star). `extra="forbid"` keeps the record's namespace closed."""

    model_config = ConfigDict(extra="forbid")

    who: str = Field(description="Contributor identity: a name, handle, or model id")
    role: str = Field(
        json_schema_extra=vocabulary("author_role", VALID_AUTHOR_ROLES),
        description="What this contributor did (created|edited|audited|reviewed)",
    )
    kind: list[str] = Field(
        default_factory=list,
        json_schema_extra=vocabulary("author_kind", RECOMMENDED_AUTHOR_KINDS, closed=False),
        description=(
            "Multi-valued tag set describing the contributor — human ladder {human, human_expert, "
            "human_certified} or {ai} + scale {agent, team, swarm}. Open (recommended seed); route "
            "scrutiny by it."
        ),
    )
    at: str | None = Field(default=None, description="ISO-8601 date/timestamp of the contribution")

    @field_validator("who")
    @classmethod
    def _check_who(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("who must not be empty")
        return v

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        # A closed vocabulary (Principle 6); reuse the shared checker's message format.
        check_vocab(v, VALID_AUTHOR_ROLES, "role")  # raises if outside the vocab; role is required
        return v

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: list[str]) -> list[str]:
        # OPEN tag set: normalise to non-empty lowercase tokens, de-duplicated in order. Unknown tags
        # (outside RECOMMENDED_AUTHOR_KINDS) are kept, not rejected — new AI topologies may be coined.
        cleaned: list[str] = []
        for tag in v:
            tok = tag.strip().lower()
            if not tok:
                raise ValueError("kind tags must be non-empty")
            if tok not in cleaned:
                cleaned.append(tok)
        if not cleaned:
            raise ValueError(
                f"kind must list at least one tag (recommended: {sorted(RECOMMENDED_AUTHOR_KINDS)})"
            )
        return cleaned


class ModuleManifest(BaseModel):
    """Full module manifest (SPEC §4). Written next to the parquets as `manifest.json`."""

    manifest_version: str = MANIFEST_VERSION
    schema_version: str = SCHEMA_VERSION

    identity: Identity
    display: Display

    genome_build: str = Field(
        default="GRCh38",
        description=(
            "Reference genome build. The reference compiler is GRCh38-bound — the digest is "
            "GRCh38-relative; other builds are recorded but not honored (RM15)."
        ),
    )
    curator: str | None = None
    method: str | None = None
    license: str | None = Field(
        default=None,
        description=(
            "Module-wide licence. Author-declared via `module_spec.yaml`'s `license:` and copied "
            "through by the compiler; the marketplace overrides on publish. The per-source detail "
            "lives in `sources`, which is where a redistributor should look."
        ),
    )

    owner: str | None = None
    authors: list[str] = Field(default_factory=list)
    authorship: list[Contribution] = Field(
        default_factory=list,
        description=(
            "Structured per-version authorship (RM14): who created/edited/audited this version, and "
            "whether each is AI or a human expert — so a consumer routes scrutiny by author-kind. "
            "Optional, out of `artifact.digest`. Supersedes the flat `authors`/`curator` (kept for "
            "compat; folding them in is a 1.0-cleanup item)."
        ),
    )
    created_at: str | None = None
    published_at: str | None = None

    stats: Stats = Field(default_factory=Stats)
    compilation: Compilation = Field(default_factory=Compilation)
    frequency: Frequency | None = Field(
        default=None,
        description=(
            "Summary of the injected allele-frequency sidecar (0.5), when the module carries one. "
            "The compiled `frequencies.parquet` is in `artifact.digest`; this block is not — it is "
            "the producer-independent fact-hash plus the release/ancestry-group facets a catalog "
            "needs without reading the artifact."
        ),
    )
    gene_metrics: GeneMetrics | None = Field(
        default=None,
        description="Summary of the injected gene-constraint sidecar (0.5), when the module carries one.",
    )
    gene_validity: GeneValidity | None = Field(
        default=None,
        description=(
            "Summary of the injected gene–disease validity sidecar (0.6), when the module carries one. "
            "Beside `gene_metrics` rather than folded into it because the grain differs: constraint is "
            "one value per gene, a validity assertion is one per gene × disease × inheritance mode."
        ),
    )
    clinical_assertions: ClinicalAssertions | None = Field(
        default=None,
        description=(
            "Summary of the injected clinical-assertion sidecar (0.6), when the module carries one. "
            "Carries the star-rating range as well as the fact-hash, because the distinction between a "
            "single-submitter call and a practice guideline is the whole reason the table exists and a "
            "row count alone would discard it."
        ),
    )
    literature: Literature | None = Field(
        default=None,
        description=(
            "Summary of the injected citation sidecar (0.5), when the module carries one. Carries the "
            "coverage counters as well as the fact-hash, because the fulltext check is partial by "
            "nature and a consumer must be able to tell 'checked and found' from 'never retrievable'."
        ),
    )
    sources: Sources | None = Field(
        default=None,
        description=(
            "Summary of the data-source licensing sidecar (0.5), when the module carries one. The "
            "one place a consumer can read what terms a compiled module was built under — which "
            "attributions must be reproduced, whether a ShareAlike obligation attaches, and whether "
            "the module may be sold — without re-deriving any of it from source names."
        ),
    )
    verification: Verification | None = Field(
        default=None,
        description=(
            "What was CHECKED, when the module carries an attestation that still matches its own "
            "authored bytes (RM45). Absent on a module nothing verified AND on one whose attestation "
            "went stale — both mean *says nothing*, which is the reading a consumer must land on. "
            "Out of `artifact.digest` and out of `content_signature`: evidence about a compile is not "
            "the authored data, so re-running a check must not mint a new content identity. Nothing "
            "in it is trusted; see the block's own field descriptions."
        ),
    )
    inputs: list[FileEntry] = Field(default_factory=list)
    content_signature: str | None = Field(
        default=None,
        description=(
            "Stable content identity over the RAW authored data rows (variants/studies + 0.4 table "
            "kinds), name- and Ensembl-independent (see `integrity.content_signature`). Unlike "
            "`artifact.digest` (compiled-parquet bytes, which move on recompile against a different "
            "reference), this survives import/recompile and metadata-strip — so a registry can dedup "
            "content across those paths. Optional and out of `artifact.digest`."
        ),
    )
    artifact: Artifact
    logs: list[FileEntry] = Field(
        default_factory=list,
        description=(
            "Optional per-version run/provenance log files, hashed like inputs. Each `name` is a "
            "path relative to the module dir, so both a top-level aggregate log (e.g. `run.log`) "
            "and per-role files under a `logs/` folder (e.g. `logs/researcher.log`, "
            "`logs/reviewer.log`) are supported. Absent logs do NOT invalidate a module. Kept out "
            "of `artifact.digest` so identical compiled data stays dedup-equal regardless of logs; "
            "full cross-version provenance is the union of every version's logs."
        ),
    )
    derived: list[FileEntry] = Field(
        default_factory=list,
        description=(
            "Optional byte hashes of the derived-fact sidecar CSVs beside the spec — "
            "`resolution.csv` plus the 0.5 fact tables (`frequencies`/`gene_metrics`/`literature`/"
            "`sources`). Kept OUT of `artifact.digest` and `content_signature`: these are evidence "
            "*about* a compile, not the authored data identity is built from, so re-running "
            "enrichment against a fresher source must not mint a new content identity. Absent "
            "entries do NOT invalidate a module. This is a BYTE hash for transport only — the "
            "authoritative identity of these tables stays the FACT hash "
            "(`compilation.resolution_signature`, and each sidecar block's own `signature`), which "
            "is what makes a human override and an enricher rewrite of the same content compare "
            "equal. Two hashes over one file, answering two questions; do not read this one as an "
            "identity."
        ),
    )
    provenance: Provenance | None = Field(
        default=None,
        description=(
            "Optional summary of a version's structured per-variant provenance (SPEC ROADMAP item "
            "1). The full items live in a hashed `provenance.json` (kept out of `artifact.digest`, "
            "like `logs`); this field carries only the generator/model/count/hash pointer."
        ),
    )
    panel: GenePanelSpec | None = Field(
        default=None,
        description=(
            "Set when the module was authored as a gene panel (SPEC ROADMAP item 7). Descriptive "
            "only in this version — the variant set is still enumerated in the artifact."
        ),
    )
    logo: FileEntry | None = Field(
        default=None,
        description=(
            "Optional module logo image (png/jpg/jpeg), hashed like `inputs`. Kept OUT of "
            "`artifact.digest` so a logo swap is a PATCH (metadata only), not a new content "
            "identity. Consumers fall back to `display.icon`/`icon_set` when absent."
        ),
    )
    readme: FileEntry | None = Field(
        default=None,
        description=(
            "Optional module readme (md/txt/rst), hashed like `logo` and kept OUT of both identity "
            "halves — `artifact.digest` and `content_signature` — so correcting a caveat is a PATCH "
            "and never mints a new content identity. Prose ABOUT the module, never part of its "
            "content: the reason it is a `FileEntry` rather than text inlined into `display` is that "
            "a readme is unbounded (a small module's readme can outweigh its data) while `display` "
            "is inlined into every card and listing a catalog serves. Being listed and hashed here "
            "is what lets a registry, an installer or a mirror serve and verify the file at all; "
            "prose that only a catalog database knows is prose no manifest consumer can reach."
        ),
    )
    signature: Signature | None = Field(
        default=None,
        description="Optional detached Ed25519 signature over `artifact.digest` (SPEC §5).",
    )


def read_manifest(path: Path) -> ModuleManifest:
    """Load and validate a `manifest.json` from disk."""
    return ModuleManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_manifest(manifest: ModuleManifest, path: Path) -> Path:
    """Write a manifest to disk as indented JSON. Returns the path written."""
    path = Path(path)
    path.write_text(
        manifest.model_dump_json(indent=2, exclude_none=False) + "\n", encoding="utf-8"
    )
    return path
