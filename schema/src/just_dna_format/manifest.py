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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import vocabulary
from just_dna_format.identity import (
    is_valid_version,
    validate_name,
    validate_namespace,
)
from just_dna_format.vocab import (
    RECOMMENDED_AUTHOR_KINDS,
    VALID_AUTHOR_ROLES,
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
    row_count: int = Field(default=0, description="Number of citations covered (one row each)")
    resolved_count: int = Field(
        default=0, description="Citations PubMed returned a record for (`exists` is true)"
    )
    missing_count: int = Field(
        default=0,
        description=(
            "Citations PubMed has no record for (`exists` is false) — a nonexistent PMID, which is a "
            "defect in the module rather than a gap in coverage."
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


class Signature(BaseModel):
    """Optional detached signature over `artifact.digest` (SPEC §5 'future'). Defends against a
    compromised storage backend: a client that pins the marketplace's public key can prove the
    digest was signed by the trusted party."""

    algorithm: str = Field(default="ed25519", description="Signature algorithm")
    public_key: str = Field(description="Base64 (raw) Ed25519 public key")
    signature: str = Field(description="Base64 signature over the artifact.digest string bytes")
    signed_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp")


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
