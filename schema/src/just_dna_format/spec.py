"""
The authored module spec DSL (`module_spec.yaml` + `variants.csv` + `studies.csv`).

This is the *input* half of the module format; `manifest.py` is the *output* half. Both live in
this dependency-light package so the compiler is a pure transform between two validated schema
sets, and any consumer can validate a spec or a manifest without pulling the compiler's polars/
duckdb weight.

Identity/display rules reuse the shared helpers in `identity` and `manifest`, so the DSL and the
manifest enforce exactly the same constraints.
"""

import math
import re
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from just_dna_format.derive import (
    benign_from_clin_sig,
    clin_sig_from_booleans,
    direction_from_state,
    pathogenic_from_clin_sig,
    stat_significance_from_state,
    trimmed_state,
)
from just_dna_format.base import AuthoredModel, derive_variant_key
from just_dna_format.identity import validate_name
from just_dna_format.manifest import SCHEMA_VERSION, Contribution, Display, GenePanelSpec
from just_dna_format.normalize import normalize_version
from just_dna_format.vocab import (
    ACTIONABILITY_SEED,
    ALLELE_PATTERN,  # noqa: F401 — re-exported for backward compat (genotype grammar moved to base)
    VALID_CLIN_SIG,  # noqa: F401 — re-exported for backward compat (see note below)
    VALID_DIRECTIONS,  # noqa: F401 — re-exported for backward compat
    VALID_SIGNIFICANCE,  # noqa: F401 — re-exported for backward compat
    check_vocab,
    validate_allele,
    validate_finite,
)
from just_dna_format.vocab import MULTI_SEP as _MULTI_SEP

# The orthogonal-axis vocabularies and identifier grammars now live in `vocab` (shared across the
# authored models). `VALID_DIRECTIONS`/`VALID_SIGNIFICANCE`/`VALID_CLIN_SIG` (and `ALLELE_PATTERN`)
# are re-exported here for backward compatibility. Spec-only vocabularies stay below.
VALID_STATES: frozenset[str] = frozenset(
    {"risk", "protective", "neutral", "significant", "alt", "ref"}
)
VALID_CHROMOSOMES: frozenset[str] = frozenset(
    {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
)
# `flags` is an OPEN list. These are the reserved tags the tooling acts on; any other tag is
# accepted and surfaced as INFO (not a warning) by the compiler. Never put direction / clinical
# / consequence / drug words here — those have (or get) typed columns.
RESERVED_FLAGS: frozenset[str] = frozenset({"conditional", "phased", "pleiotropic"})
# `effect_measure` is intentionally NOT a closed vocabulary (kept permissive so PGS-Catalog
# `weight_type` additions survive). These are the recommended values, for documentation only.
RECOMMENDED_EFFECT_MEASURES: frozenset[str] = frozenset(
    {"OR", "HR", "RR", "beta", "log(OR)", "log(HR)", "NR"}
)
# A PMID is a run of digits. Real sources present them bare (`9545397`), bracketed/prefixed
# (`[PMID: 9545397]`), or as a `;`-joined list (`PMID 17478681; PMID: 30278588`). We accept any
# string that carries at least one PMID token and keep it verbatim (ROADMAP item 6 / Obs #4).
PMID_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{1,8})\b")
# A DOI is `10.<registrant>/<suffix>` (Crockford/Handle grammar). Real sources present it bare
# (`10.1234/abc.def`) or wrapped in a URL (`https://doi.org/10.1234/abc`); we accept any string that
# carries one DOI token and keep it verbatim, mirroring the PMID contract. Wider than a PMID: it also
# covers preprints/books/datasets with no PubMed id (docs/USE_CASES.md §4a, RM11).
DOI_PATTERN: re.Pattern[str] = re.compile(r"10\.\d{4,9}/\S+")


def extract_pmids(raw: str) -> list[str]:
    """Pull digit-only PMIDs out of a free-form reference string, in order, de-duplicated.

    Handles bare digits, the bracketed/prefixed `[PMID: N]` / `PMID N` forms, and `;`-joined
    lists. Returns an empty list when the string carries no PMID token (e.g. a dbSNP URL)."""
    seen: dict[str, None] = {}
    for match in PMID_PATTERN.finditer(raw):
        seen.setdefault(match.group(1), None)
    return list(seen)


class ModuleInfo(Display):
    """The `module:` block of module_spec.yaml: a machine `name` plus the shared `Display`
    metadata (title/description/report_title/icon/color).

    Extends the manifest's `Display` rather than re-declaring those fields, so the display schema
    and its validation (e.g. the hex-colour rule) live in exactly one place. `name` lives here on
    the authoring side; the manifest routes it into `Identity` instead.

    `extra="forbid"` so an authored-block typo (`colour:`, `nam:`) is a hard error, not a silently
    dropped key — the same author-time guard the row models carry, applied to the `module:` block.
    (Set here, not on `Display`, so the manifest side that also uses `Display` is untouched.)
    """

    model_config = ConfigDict(extra="forbid")

    _version_coerced_from: Optional[str] = PrivateAttr(default=None)

    name: str = Field(description="Machine name: lowercase, underscores, no spaces")
    version: Optional[str] = Field(
        default=None,
        description=(
            "Authored **advisory** version — a human marker (informal `v2`/`3` or SemVer). The "
            "publishing registry stamps and overrides the canonical SemVer `Identity.version` on "
            "publish, so this is not load-bearing for identity. **Coerced to SemVer since 0.5** "
            "(RM17): an informal `v2`/`3` is read as `2.0.0`/`3.0.0` and the rewrite is reported "
            "once. Genuinely accepted (not stripped) so the "
            "whole pre-0.4 corpus that carries `module.version` validates — unlike the "
            "registry-stamped identity keys (namespace/owner/canonical_id), which a consumer strips "
            "via just_dna_format.normalize.strip_authority_keys before validation."
        ),
    )

    @model_validator(mode="after")
    def _enforce_semver(self) -> "ModuleInfo":
        """Coerce `version` to SemVer, recording what it was coerced *from* (RM17).

        **Coerce rather than reject**, decided in 0.5: the pre-0.4 corpus is full of `v2` and `3`, and
        rejecting them would break every one of those modules to gain a stricter spelling of a field
        that is advisory anyway — the registry stamps the canonical `Identity.version` on publish. The
        coercion is total, idempotent and lossless in the only direction that matters (`v2` → `2.0.0`
        reads the author's intent; nothing else could).

        The pre-coercion string is kept on `version_coerced_from` so a caller can *report* the rewrite.
        Silently changing an authored value is the thing this codebase does not do — the rule is
        report-never-repair, and this is the narrow exception where the repair is the documented
        behaviour of the field, so it must at least be said out loud."""
        if self.version:
            coerced = normalize_version(self.version)
            if coerced != self.version:
                self._version_coerced_from = self.version
                self.version = coerced
        return self

    @property
    def version_coerced_from(self) -> Optional[str]:
        """The authored `version` before SemVer coercion, or `None` if it was already SemVer.

        Not a field: it describes what happened during validation, not module content, so it stays out
        of `model_dump()` and never reaches the manifest or a CSV."""
        return self._version_coerced_from

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_name(v)


class Defaults(BaseModel):
    """Default values applied to variant rows when not explicitly set.

    `extra="forbid"` so a typo'd default key (`currator:`) is rejected rather than silently ignored
    (which would leave the real default in force with no diagnosis)."""

    model_config = ConfigDict(extra="forbid")

    curator: str = Field(default="ai-module-creator", description="Default curator identifier")
    method: str = Field(default="literature-review", description="Default annotation method")
    priority: Optional[str] = Field(default=None, description="Default priority level")


class ModuleSpecConfig(BaseModel):
    """Top-level model for module_spec.yaml.

    `extra="forbid"` so a misspelled top-level key is a hard error, not a silent no-op. This is
    safety-relevant, not merely tidy: a typo'd `genome_bild:` would otherwise leave `genome_build`
    at its `GRCh38` default, silently resolving a GRCh37-intended module against the wrong assembly
    — exactly the corruption the resolver's build guard exists to prevent, bypassed by one typo."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA_VERSION, description="DSL schema version")
    module: ModuleInfo = Field(description="Module identity and display metadata")
    defaults: Defaults = Field(default_factory=Defaults, description="Default variant-row values")
    genome_build: str = Field(
        default="GRCh38",
        description=(
            "Reference genome build for positions. REALITY: the reference compiler is "
            "**GRCh38-bound** — it resolves and reasons about coordinates as GRCh38 only, so "
            "`artifact.digest` is GRCh38-relative. A GRCh37/T2T build is recorded verbatim but not "
            "honored (positions are not re-resolved per build, and rsid↔coord consistency is not "
            "checked cross-build). Build-aware identity/resolution is RM15 (other-builds-support)."
        ),
    )
    panel: Optional[GenePanelSpec] = Field(
        default=None,
        description=(
            "Optional gene-panel declaration (ROADMAP item 7). Descriptive provenance for modules "
            "derived from a gene set + significance predicate; the compiler records it verbatim "
            "but does not materialize variants from it in this version."
        ),
    )
    authorship: list[Contribution] = Field(
        default_factory=list,
        description=(
            "Optional structured per-version authorship (RM14): one entry per contributor with "
            "who/role/kind (+ optional date). Recorded verbatim into the manifest; out of "
            "`artifact.digest`. A joint contribution is two entries (a human and an ai)."
        ),
    )
    license: Optional[str] = Field(
        default=None,
        description=(
            "Optional licence the author declares for the module as a whole, e.g. 'CC-BY-SA-4.0'. "
            "Advisory and registry-overridable, exactly like `module.version`: the marketplace "
            "stamps the canonical value on publish. The authoritative per-source record is "
            "`sources.csv`, which round-trips; this key is a human convenience and is NOT "
            "reconstructed by the lossy `reverse_module` (same class as `panel`/`authorship`)."
        ),
    )

    @field_validator("schema_version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {v!r}. Expected {SCHEMA_VERSION!r}")
        return v


class VariantRow(AuthoredModel):
    """One row of variants.csv. At least one identifier (rsid or chrom+start) is required.

    Inherits from `AuthoredModel`: `extra="forbid"` + the reserved-namespace guard, and the shared
    field validators for `rsid`/`trait_efo_id`/`direction`/`clin_sig`/`stat_significance`/`effect_size`.
    """

    rsid: Optional[str] = Field(default=None, description="dbSNP identifier, e.g. rs1801133")
    chrom: Optional[str] = Field(default=None, description="Chromosome without 'chr' prefix")
    start: Optional[int] = Field(
        default=None, ge=0, description="0-based genomic position (GRCh38)"
    )
    ref: Optional[str] = Field(default=None, description="Reference allele")
    alts: Optional[str] = Field(default=None, description="Alt allele(s), comma-separated")
    variant_key: Optional[str] = Field(
        default=None,
        description=(
            "Frozen machine identity (rsid, else chrom:start:ref, or chrom:start:ref:alts when an alt "
            "is present so distinct alleles at one locus don't collide), stamped at load and never "
            "re-derived — so the resolver filling a coord/rsid can't re-key the row, and a one-to-many "
            "rsid expands to distinct coord-keyed rows (Principle 7). Compiler-managed: not authored, "
            "materialized to weights.parquet, and never written back by reverse_module."
        ),
    )
    authored_ident: Optional[list[str]] = Field(
        default=None,
        description=(
            "Which identity columns the author actually supplied, from {rsid, chrom, start, ref, "
            "alts}. Stamped at load like `variant_key` and never re-derived, so resolution can fill "
            "or expand without disturbing it. Compiler-managed: not authored, materialized to "
            "weights.parquet, and consumed by reverse_module to re-emit the authored shape — which is "
            "what keeps `content_signature` stable across a round-trip."
        ),
    )
    genotype: str = Field(description="Slash-separated sorted alleles, e.g. A/G")
    weight: Optional[float] = Field(default=None, description="Score (positive=protective)")
    state: str = Field(description="One of: risk, protective, neutral, significant, alt, ref")
    conclusion: str = Field(description="Human-readable interpretation for this genotype")
    negatives: Optional[str] = Field(
        default=None,
        description=(
            "Optional free-text adverse/antagonistic-pleiotropy counterpart to `conclusion` "
            "(e.g. a protective allele's known trade-off). Consumers ignore it when absent."
        ),
    )
    priority: Optional[str] = Field(default=None, description="Priority level override")
    gene: Optional[str] = Field(default=None, description="Gene symbol, e.g. MTHFR")
    phenotype: Optional[str] = Field(default=None, description="Associated trait or phenotype")
    category: Optional[str] = Field(default=None, description="Grouping category within the module")
    clinvar: Optional[bool] = Field(default=None, description="Is this variant in ClinVar?")
    pathogenic: Optional[bool] = Field(default=None, description="ClinVar pathogenic flag")
    benign: Optional[bool] = Field(default=None, description="ClinVar benign flag")
    curator: Optional[str] = Field(default=None, description="Curator override")
    method: Optional[str] = Field(default=None, description="Annotation method override")

    # ── 0.3 additive columns (all optional; shipped in 0.3 — see docs/CHANGELOG.md) ──
    direction: Optional[str] = Field(
        default=None,
        description="Effect direction: one of protective|risk|neutral|unknown. Orthogonal to `state`.",
    )
    stat_significance: Optional[str] = Field(
        default=None,
        description="Statistical significance: significant|suggestive|not_significant|unknown.",
    )
    effect_size: Optional[float] = Field(
        default=None, description="Published effect magnitude (unit given by `effect_measure`)."
    )
    effect_measure: Optional[str] = Field(
        default=None,
        description="Unit of `effect_size`, e.g. OR|HR|beta|RR (recommended; not a closed set).",
    )
    effect_allele: Optional[str] = Field(
        default=None,
        description="The allele that `direction`/`weight`/`effect_size` refer to (nucleotides).",
    )
    flags: Optional[list[str]] = Field(
        default=None,
        description=(
            "Open, multi-valued tag list (CSV: comma/semicolon/pipe-separated). Reserved tags the "
            "tooling acts on: conditional|phased|pleiotropic; other tags are allowed (surfaced as INFO)."
        ),
    )
    trait_efo_id: Optional[str] = Field(
        default=None,
        description="EFO/MONDO/OBA/HP trait ontology id(s), e.g. EFO_0004340 (matches just-prs).",
    )
    clin_sig: Optional[str] = Field(
        default=None,
        description="ClinVar/ACMG clinical significance (VEP CLIN_SIG vocabulary).",
    )

    # ── 0.4 general annotation axes (all optional; retired from the reserved namespace) ──
    # General per-variant refinements — any variant finding may carry them, so they live here rather
    # than in a domain table. A sparse SNP CSV simply omits them.
    requires_callable: Optional[bool] = Field(
        default=None,
        description=(
            "True when the *absence* of this variant is the informative call (recessive carrier, "
            "'pathogenic variant absent' reassurance) — a consumer lacking callability data must "
            "then withhold the reference/absence conclusion, never assert it (no-call ≠ hom-ref)."
        ),
    )
    acmg_sf: Optional[bool] = Field(
        default=None, description="True when the gene is on the ACMG secondary-findings list."
    )
    actionability: Optional[str] = Field(
        default=None,
        description=(
            "Annotation-level actionability of the finding (ACTIONABILITY_SEED: actionable|"
            "preventable|pharmacogenomic|incurable|reproductive|descriptive|modifiable). A property "
            "of the gene–condition–intervention triad a consumer's disclosure policy may read; the "
            "format never decides disclosure."
        ),
    )

    # ── 0.5: the second half of RM6 (retired from the reserved namespace on build) ──
    # `requires_callable` above says a negative *must be proven*; this says where the proof lives.
    # Same declarative-pointer grammar as `source_field` — validated on `AuthoredModel`, shared.
    callable_from: Optional[str] = Field(
        default=None,
        description=(
            "Optional VCF FORMAT/INFO field(s) a consumer establishes callability from (e.g. DP, "
            "GQ, FT, or DP|GQ). A declarative pointer, never an expression: it names where the "
            "evidence for 'this position was actually callable' lives, so a consumer can tell a "
            "confirmed negative from an uncovered one instead of reading both as reference."
        ),
    )

    @model_validator(mode="after")
    def _freeze_identity(self) -> "VariantRow":
        """Stamp the frozen identity *and the authored shape* at load, ignoring authored values for
        both (no foot-gun). Because a `mode="after"` validator does not re-run on `model_copy`, the
        resolver can fill rsid/coord or reassign the key on expansion without either re-deriving.

        `authored_ident` is what makes resolution **reversible**: it records which identity columns the
        author actually supplied, so `reverse_module` can re-emit that exact shape instead of whatever
        resolution happened to fill in. Before it existed, reverse had to guess from `variant_key`,
        which cannot tell an rsid-only row from an rsid+coordinate pair and cannot tell an expanded
        locus from a coordinate the author wrote — so it materialized resolved coordinates into
        `variants.csv` and `content_signature` moved across every round-trip of an rsid-authored
        module. See `base.derive_variant_key` and COMPILER.md § Resolution.
        """
        self.variant_key = derive_variant_key(self.rsid, self.chrom, self.start, self.ref, self.alts)
        self.authored_ident = [
            name for name in ("rsid", "chrom", "start", "ref", "alts")
            if getattr(self, name) is not None
        ]
        return self

    @property
    def authored_key(self) -> str:
        """The identity the author wrote, recomputed from `authored_ident` alone.

        For an expanded one-to-many rsid this is the *authored* rsid while `variant_key` has become
        the per-locus allele id — which is exactly the pairing reverse needs to collapse N artifact
        rows back into the one row that was written.
        """
        authored = set(self.authored_ident or ())
        return derive_variant_key(
            self.rsid if "rsid" in authored else None,
            self.chrom if "chrom" in authored else None,
            self.start if "start" in authored else None,
            self.ref if "ref" in authored else None,
            self.alts if "alts" in authored else None,
        )

    # ── 0.3 read-time aliases + upgrade (ROADMAP item 1/6 + "Upgrade derivation"). ────────────────
    # `state` and the ClinVar booleans stay REQUIRED/authoritative for 0.2 compat (CONSTITUTION
    # Principle 3/8 — a required field is never demoted to optional inside a major). These accessors
    # expose the orthogonal 0.3 axes even for a legacy row that set only `state`, by deriving when the
    # new column is absent; `upgraded()` materializes those derivations for a re-publish. All are
    # total and idempotent (CONSTITUTION Principle 7).
    @property
    def effective_direction(self) -> str:
        """`direction` if set, else derived from the legacy `state` (+ `weight` sign)."""
        return self.direction or direction_from_state(self.state, self.weight)

    @property
    def effective_stat_significance(self) -> str:
        """`stat_significance` if set, else derived from the legacy `state`."""
        return self.stat_significance or stat_significance_from_state(self.state)

    @property
    def effective_clin_sig(self) -> Optional[str]:
        """`clin_sig` if set, else derived from the legacy ClinVar booleans (lossy)."""
        return self.clin_sig or clin_sig_from_booleans(
            self.pathogenic, self.benign, self.clinvar
        )

    @property
    def effective_pathogenic(self) -> Optional[bool]:
        """The authoritative `pathogenic` boolean, or the one implied by `clin_sig` when unset."""
        if self.pathogenic is not None:
            return self.pathogenic
        return pathogenic_from_clin_sig(self.clin_sig)

    @property
    def effective_benign(self) -> Optional[bool]:
        """The authoritative `benign` boolean, or the one implied by `clin_sig` when unset."""
        if self.benign is not None:
            return self.benign
        return benign_from_clin_sig(self.clin_sig)

    def upgraded(self) -> "VariantRow":
        """A copy with the 0.3 axes back-populated from `state`/booleans and `state` trimmed to the
        legacy set {protective, risk, neutral}. `state` stays present (never dropped inside a major)
        but becomes a derived mirror of `direction`. Idempotent: ``r.upgraded().upgraded() ==
        r.upgraded()``."""
        direction = self.effective_direction
        return self.model_copy(
            update={
                "direction": direction,
                "stat_significance": self.effective_stat_significance,
                "clin_sig": self.effective_clin_sig,
                "pathogenic": self.effective_pathogenic,
                "benign": self.effective_benign,
                "state": trimmed_state(direction),
            }
        )

    @property
    def needs_upgrade(self) -> bool:
        """True when a re-publish would materialize a 0.3 column that is currently derived-but-empty
        (or would re-align the legacy `state`). Feeds the marketplace `revalidate`/`needs_upgrade`
        contract-drift flow (which flags drifted-but-fixable modules for a new PATCH)."""
        return self.upgraded() != self

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v: str) -> str:
        if v not in VALID_STATES:
            raise ValueError(f"state must be one of {sorted(VALID_STATES)}, got: {v!r}")
        return v

    @field_validator("chrom")
    @classmethod
    def _validate_chrom(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.removeprefix("chr")
            if normalized not in VALID_CHROMOSOMES:
                raise ValueError(
                    f"chrom must be one of 1-22, X, Y, MT (without 'chr' prefix), got: {v!r}"
                )
            return normalized
        return v

    # `genotype`'s grammar lives on `AuthoredModel` since 0.5 — `PharmVariantRow` declares the same
    # field, and a validator shared by two models belongs on the base (see base.py).

    @field_validator("actionability")
    @classmethod
    def _validate_actionability(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, ACTIONABILITY_SEED, "actionability")

    @field_validator("effect_allele")
    @classmethod
    def _validate_effect_allele(cls, v: Optional[str]) -> Optional[str]:
        return validate_allele(v, "effect_allele")

    @field_validator("weight")
    @classmethod
    def _validate_weight(cls, v: Optional[float]) -> Optional[float]:
        return validate_finite(v, "weight")

    @field_validator("flags", mode="before")
    @classmethod
    def _split_flags(cls, v: object) -> object:
        # A CSV cell arrives as a string; split it into a list. Programmatic construction may pass a
        # list already. The vocabulary is OPEN — unknown tags are accepted (the compiler surfaces
        # them as INFO), so nothing is rejected here beyond emptiness.
        if isinstance(v, str):
            tags = [t.strip() for t in _MULTI_SEP.split(v) if t.strip()]
            return tags or None
        return v

    @field_validator("flags")
    @classmethod
    def _validate_flags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        for tag in v:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(f"flags entries must be non-empty strings, got: {v!r}")
        return v

    @model_validator(mode="after")
    def _validate_identification(self) -> "VariantRow":
        has_rsid = self.rsid is not None
        positional = {"chrom": self.chrom, "start": self.start}
        has_pos = any(v is not None for v in positional.values())
        has_ref = any(v is not None for v in {"ref": self.ref, "alts": self.alts}.values())

        if not has_rsid and not has_pos:
            raise ValueError(
                "At least one identifier is required: provide rsid or position (chrom + start)"
            )
        if has_pos:
            missing = [k for k, v in positional.items() if v is None]
            if missing:
                raise ValueError(
                    f"If any positional columns are provided, chrom and start are required. "
                    f"Missing: {missing}"
                )
        if has_ref and not has_pos:
            raise ValueError("ref/alts require chrom and start to also be provided")
        return self


class StudyRow(AuthoredModel):
    """One row of studies.csv: an (rsid, pmid) evidence link. Grounding evidence is mandatory.

    Inherits `AuthoredModel` (reserved-namespace guard + shared `rsid`/`trait_efo_id`/
    `stat_significance`/`effect_size` validators)."""

    rsid: Optional[str] = Field(default=None, description="dbSNP identifier or variant key")
    chrom: Optional[str] = Field(default=None, description="Chromosome (for position-only variants)")
    start: Optional[int] = Field(
        default=None, ge=0, description="0-based position (position-only variants)"
    )
    ref: Optional[str] = Field(default=None, description="Reference allele (position-only variants)")
    pmid: str = Field(description="PubMed ID or reference — free-form, must be non-empty")
    population: Optional[str] = Field(default=None, description="Study population")
    p_value: Optional[str] = Field(default=None, description="Raw p-value string (free-form)")
    conclusion: Optional[str] = Field(default=None, description="Study-specific conclusion")
    study_design: Optional[str] = Field(default=None, description="e.g. meta-analysis, GWAS")

    # ── 0.3 additive columns (per-study evidence; shipped in 0.3 — see docs/CHANGELOG.md) ──
    stat_significance: Optional[str] = Field(
        default=None,
        description="Per-study statistical significance: significant|suggestive|not_significant|unknown.",
    )
    effect_size: Optional[float] = Field(
        default=None, description="Per-study effect magnitude (unit given by `effect_measure`)."
    )
    effect_measure: Optional[str] = Field(
        default=None, description="Unit of `effect_size`, e.g. OR|HR|beta|RR (recommended, open)."
    )
    trait_efo_id: Optional[str] = Field(
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s) for this study."
    )

    # ── 0.4 provenance columns (RM11/RM12, from the 0.5 scope; docs/USE_CASES.md §4a) ──
    # All optional → P3/P8 clean. They anchor a network-first validator (RM13) without the format
    # ever fetching: the module ships the pointer, the consumer supplies the source and does the check.
    doi: Optional[str] = Field(
        default=None,
        description=(
            "Digital Object Identifier — wider than `pmid` (covers preprints/books/datasets with no "
            "PubMed id). Free-form, kept verbatim; a validator may cross-fill doi↔pmid."
        ),
    )
    provenance_quote: Optional[str] = Field(
        default=None,
        description=(
            "Optional keyword phrase / literal passage locating this study's claim in the cited "
            "article's fulltext. Human-legible; a validator confirms fulltext-contains, yes/no."
        ),
    )
    provenance_regex: Optional[str] = Field(
        default=None,
        description=(
            "Optional regex locating the claim in fulltext — a declarative pattern grammar "
            "(Principle 1: data, not code), matched consumer-side by a linear-time/ReDoS-safe engine."
        ),
    )

    # ── 0.5 additive column: the queryable form of `p_value` above ──
    # `p_value` stays the verbatim record (free-form, and kept by P8 — retyping or removing it is a
    # 1.0 item). This carries the same number in a form that sorts and thresholds.
    p_value_num: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "The p-value as a number, so it can be sorted and thresholded — `p_value` above is a "
            "free-form string and cannot be. In (0, 1]: a p-value of exactly 0 is a source's own "
            "underflow, not a probability, so it is rejected rather than stored as a confident zero."
        ),
    )

    @property
    def variant_key(self) -> str:
        """Stable key matching VariantRow.variant_key. StudyRow is never resolved/expanded, so its
        key stays a derived property (no freezing needed)."""
        return derive_variant_key(self.rsid, self.chrom, self.start, self.ref)

    @property
    def neg_log10_p(self) -> Optional[float]:
        """−log10(p) — derived on write, never stored. `None` when `p_value_num` is unset.

        The scale a consumer actually filters and plots on (`7.3` is genome-wide significance),
        materialized into `studies.parquet` so nobody recomputes it per query. It is deliberately not
        *authored* in this form: that would make the human compute a logarithm to write a row down,
        and the DSL exists for the human — the parquet absorbs the convenience, the CSV keeps the
        number the paper printed."""
        if self.p_value_num is None:
            return None
        # `+ 0.0` normalizes the -0.0 that p == 1 would otherwise produce.
        return -math.log10(self.p_value_num) + 0.0

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("pmid must not be empty")
        if not extract_pmids(v):
            raise ValueError(
                f"pmid must contain at least one PubMed ID (bare digits, or a bracketed/prefixed "
                f"form like '[PMID: 9545397]'), got: {v!r}"
            )
        return v  # kept verbatim; use extract_pmids(pmid) to recover digit-only ids

    @field_validator("doi")
    @classmethod
    def _validate_doi(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not DOI_PATTERN.search(v):
            raise ValueError(
                f"doi must contain a DOI token (10.<registrant>/<suffix>, bare or as a doi.org "
                f"URL), got: {v!r}"
            )
        return v  # kept verbatim

    @field_validator("provenance_regex")
    @classmethod
    def _validate_provenance_regex(cls, v: Optional[str]) -> Optional[str]:
        # Author-time sanity: the pattern must compile. ReDoS-safety is the consumer's concern —
        # it evaluates the pattern with a linear-time engine (Principle 1), never Python `re`.
        if v is None:
            return v
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"provenance_regex is not a valid regular expression: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _validate_study_identification(self) -> "StudyRow":
        if self.rsid is None and self.chrom is None:
            raise ValueError(
                "At least one identifier is required: provide rsid or position (chrom + start)"
            )
        return self
