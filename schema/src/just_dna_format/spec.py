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
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from just_dna_format.base import (
    COMPILER_MANAGED,
    AuthoredModel,
    derive_variant_key,
    since,
    stamped_identity_field,
    vocabulary,
)
from just_dna_format.derive import (
    benign_from_clin_sig,
    clin_sig_from_booleans,
    direction_from_state,
    pathogenic_from_clin_sig,
    stat_significance_from_state,
    trimmed_state,
)
from just_dna_format.identity import validate_name
from just_dna_format.manifest import (
    SCHEMA_VERSION,
    Contribution,
    Display,
    GenePanelSpec,
    Weighting,
)
from just_dna_format.normalize import normalize_version, reject_authority_keys
from just_dna_format.vocab import (
    ACTIONABILITY_SEED,
    ALLELE_PATTERN,  # noqa: F401 — re-exported for backward compat (genotype grammar moved to base)
    RECOMMENDED_EFFECT_MEASURES,  # noqa: F401 — re-exported; moved to vocab in 0.6 so gwas.py can bind it
    VALID_CLIN_SIG,  # noqa: F401 — re-exported for backward compat (see note below)
    VALID_DIRECTIONS,  # noqa: F401 — re-exported for backward compat
    VALID_SIGNIFICANCE,  # noqa: F401 — re-exported for backward compat
    check_vocab,
    reject_template_placeholders,
    validate_allele,
    validate_finite,
)
from just_dna_format.vocab import MULTI_SEP as _MULTI_SEP
from just_dna_format.vrs import normalize_chrom, sole_build_naming_contig

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
# A PMID is a run of digits. Real sources present them bare (`9545397`), bracketed/prefixed
# (`[PMID: 9545397]`), or as a `;`-joined list (`PMID 17478681; PMID: 30278588`). We accept any
# string that carries at least one PMID token and keep it verbatim (ROADMAP item 6 / Obs #4).
PMID_PATTERN: re.Pattern[str] = re.compile(r"\b(\d{1,8})\b")
# PubMed and PubMed Central number articles independently, and their identifiers are one letter apart
# (RM50). `PMC3110566` never parsed as a PMID (there is no word boundary between `C` and a digit), but
# **`PMC 3110566` did** — and 3110566 is a real PMID for an unrelated article, because PMIDs are
# densely allocated. So the outcome turned on a space and the accepted spelling silently cited the
# wrong paper. This pattern names the PMC context in **any** spacing (`PMC3110566`, `PMC 3110566`,
# `PMC-3110566`, `pmcid: 3110566`), so `extract_pmids` can decline the digits inside it and the
# refusal can say which id it saw rather than which one it wanted.
PMCID_PATTERN: re.Pattern[str] = re.compile(r"PMC(?:ID)?\s*[:\-]?\s*(\d{1,9})", re.IGNORECASE)
# A DOI is `10.<registrant>/<suffix>` (Crockford/Handle grammar). Real sources present it bare
# (`10.1234/abc.def`) or wrapped in a URL (`https://doi.org/10.1234/abc`); we accept any string that
# carries one DOI token and keep it verbatim, mirroring the PMID contract. Wider than a PMID: it also
# covers preprints/books/datasets with no PubMed id (docs/USE_CASES.md §4a, RM11).
DOI_PATTERN: re.Pattern[str] = re.compile(r"10\.\d{4,9}/\S+")


def extract_pmcids(raw: str) -> list[str]:
    """Pull PubMed **Central** ids out of a free-form reference string, canonicalized to `PMC…`.

    In order, de-duplicated, and tolerant of the spacings a hand-written cell produces (`PMC3110566`,
    `PMC 3110566`, `pmcid: 3110566`). This exists so a refusal can name the identifier the author
    actually wrote — a generic "must contain at least one PubMed ID" is a dead end where a specific
    "that is a PMCID" is a fix — and so the enricher can cross-check an authored PMC id against the
    one PubMed reports for the same record.
    """
    seen: dict[str, None] = {}
    for match in PMCID_PATTERN.finditer(raw):
        seen.setdefault(f"PMC{match.group(1)}", None)
    return list(seen)


def extract_pmids(raw: str) -> list[str]:
    """Pull digit-only PMIDs out of a free-form reference string, in order, de-duplicated.

    Handles bare digits, the bracketed/prefixed `[PMID: N]` / `PMID N` forms, and `;`-joined
    lists. Returns an empty list when the string carries no PMID token (e.g. a dbSNP URL).

    **A digit run whose immediate context spells `PMC` is not a PMID and is skipped** (RM50). It is a
    different registry's number for (usually) a different article, so reading it as a PubMed id is a
    confident citation of the wrong paper. A cell carrying both — `21551363; PMC3110566` — still
    yields the real PMID; only a cell whose sole numeric content is a PMC id comes back empty, which
    is what lets `validate_pmid_cell` name it.
    """
    excluded = [match.span(1) for match in PMCID_PATTERN.finditer(raw)]
    seen: dict[str, None] = {}
    for match in PMID_PATTERN.finditer(raw):
        start = match.start(1)
        if any(lo <= start < hi for lo, hi in excluded):
            continue
        seen.setdefault(match.group(1), None)
    return list(seen)


def validate_pmid_cell(value: str | None, field: str, *, required: bool) -> str | None:
    """The shared grammar for a free-form citation pointer, kept verbatim on success.

    **Every citation pointer in the schema routes through here**, so the rule cannot drift between
    them as citation sites are added — and they are added: `StudyRow.pmid` (required, grounding a
    variant), `MeasureBinRow.pmid` (optional, RM47's bin pointer grounding a *boundary*) and
    `PharmVariantRow.pmid` (optional, RM132, grounding one drug/genotype claim). `required` is the
    only thing that differs between them; the diagnosis is not.

    The PMCID branch is the whole point of separating this out (RM50). Before it, a cell reading
    `PMC 3110566` was accepted as PMID 3110566 and a cell reading `PMC3110566` was refused with a
    message that never used the word PMCID — the same mistake, diagnosed two different unhelpful ways.
    Now both are refused and the message names the id that was seen. **It never repairs**: converting a
    PMC id to a PMID needs the registry, which this tier does not have and would not use if it did
    (`just-dna-enricher hint citation --pmcid` is the reporting route).
    """
    if value is None:
        if required:
            raise ValueError(f"{field} must not be empty")
        return None
    value = str(value).strip()
    if not value:
        if required:
            raise ValueError(f"{field} must not be empty")
        return None
    if extract_pmids(value):
        return value  # kept verbatim; use extract_pmids(value) to recover digit-only ids
    pmcids = extract_pmcids(value)
    if pmcids:
        raise ValueError(
            f"{field} names PubMed Central id(s) {pmcids} and no PubMed ID. PMC and PubMed number "
            f"articles independently, so a PMC id's digits are a different article's PMID — reading "
            f"them as one would cite the wrong paper. Look the PMID up (e.g. "
            f"`just-dna-enricher hint citation --pmcid {pmcids[0]}`) and write that, got: {value!r}"
        )
    raise ValueError(
        f"{field} must contain at least one PubMed ID (bare digits, or a bracketed/prefixed "
        f"form like '[PMID: 9545397]'), got: {value!r}"
    )


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

    _version_coerced_from: str | None = PrivateAttr(default=None)

    name: str = Field(json_schema_extra=since("0.2.0"), description="Machine name: lowercase, underscores, no spaces")
    version: str | None = Field(json_schema_extra=since("0.5.0"), 
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

    @model_validator(mode="before")
    @classmethod
    def _diagnose_authority_keys(cls, data: object) -> object:
        """Name a registry-stamped identity key instead of letting `extra="forbid"` call it a stray.

        Runs on the RAW block, before field coercion, so the diagnosis replaces pydantic's generic
        message rather than arriving after it. Nothing is stripped — see
        `normalize.reject_authority_keys`."""
        return reject_authority_keys(data)

    @field_validator("version", mode="before")
    @classmethod
    def _accept_the_number_yaml_read(cls, value: object) -> object:
        """A bare `version: 3` is an **int** by the time YAML hands it over, and RM17 meant to take it.

        The coercion below was written to accept "the pre-0.4 corpus full of `v2` and `3`" — but it is
        `mode="after"`, so an int never reaches it and the field refused with pydantic's *Input should
        be a valid string*, which names the type rather than the fix. Quoted `'3'` coerced; unquoted
        `3` did not, and unquoted is the only way YAML spells a number. The guard the corpus needed was
        unreachable from the file format the corpus is written in.

        Measured before changing it: of 61 foreign modules swept through `close_module`, **26 refused
        on exactly this** — every one an integer (`1`, `2`, `3`, `5`), across three independent
        toolchains. That was 90% of all refusals.

        Widening only, so P3 holds: a value that was refused is now read the way its quoted twin
        already was, and `version_coerced_from` reports the rewrite exactly as before.

        **A float is refused, deliberately, and the message is the point.** YAML reads `1.10` as
        `1.1`, so the author's text is gone before this code runs and coercing would publish a version
        they did not write. No instantiation in the corpus — all 26 are ints — but the fix above
        creates the neighbour: once `version: 1` works, `version: 1.0` failing with a type name would
        be the surprise. `bool` is an `int` subclass and is left to the string check, since `version:
        true` is not a version anyone meant.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            raise ValueError(
                f"version {value!r} was read by YAML as a number, and the text you wrote cannot be "
                f"recovered from it — YAML reads 1.10 as 1.1, so a version is quoted or it is guessed. "
                f'Write it as a string: version: "{value}". An integer needs no quotes; a version with '
                f"a dot does."
            )
        return value

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
    def version_coerced_from(self) -> str | None:
        """The authored `version` before SemVer coercion, or `None` if it was already SemVer.

        Not a field: it describes what happened during validation, not module content, so it stays out
        of `model_dump()` and out of every CSV.

        **It does reach the manifest, since RM103** — `Identity.version_coerced_from`, copied by the
        compiler rather than serialized from here. That is the distinction this docstring used to
        blur: staying out of the authored surface is a property of the *field*, while publishing the
        fabrication is what makes it auditable in the artifact instead of only in a build log
        somebody had to have kept."""
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

    curator: str = Field(json_schema_extra=since("0.2.0"), default="ai-module-creator", description="Default curator identifier")
    method: str = Field(json_schema_extra=since("0.2.0"), default="literature-review", description="Default annotation method")
    priority: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Default priority level")


class ModuleSpecConfig(BaseModel):
    """Top-level model for module_spec.yaml.

    `extra="forbid"` so a misspelled top-level key is a hard error, not a silent no-op. This is
    safety-relevant, not merely tidy: a typo'd `genome_bild:` would otherwise leave `genome_build`
    at its `GRCh38` default, silently resolving a GRCh37-intended module against the wrong assembly
    — exactly the corruption the resolver's build guard exists to prevent, bypassed by one typo."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_template_placeholders(cls, data: object) -> object:
        # The YAML counterpart of `AuthoredModel`'s guard: a scaffolded `module_spec.yaml` must not
        # compile with its stub values still in place. Only the top level is scanned here; the nested
        # blocks (`module:`, `defaults:`) are models of their own and are checked when they validate.
        return reject_template_placeholders(data, what="module_spec.yaml")

    schema_version: str = Field(json_schema_extra=since("0.2.0"), default=SCHEMA_VERSION, description="DSL schema version")
    module: ModuleInfo = Field(json_schema_extra=since("0.2.0"), description="Module identity and display metadata")
    defaults: Defaults = Field(json_schema_extra=since("0.2.0"), default_factory=Defaults, description="Default variant-row values")
    genome_build: str = Field(json_schema_extra=since("0.2.0"), 
        default="GRCh38",
        description=(
            "Reference genome build for positions. REALITY: the reference compiler is "
            "**GRCh38-bound** — it resolves and reasons about coordinates as GRCh38 only, so "
            "`artifact.digest` is GRCh38-relative. A GRCh37/T2T build is recorded verbatim but not "
            "honored (positions are not re-resolved per build, and rsid↔coord consistency is not "
            "checked cross-build). Build-aware identity/resolution is RM15 (other-builds-support)."
        ),
    )
    panel: GenePanelSpec | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        description=(
            "DEPRECATED in 0.6, removed at 1.0 (RM4) — delete it. Descriptive provenance for modules "
            "derived from a gene set + significance predicate; the compiler records it verbatim and "
            "never materialized variants from it. Its one machine reader, the enricher's ClinVar "
            "clin_sig cross-check, now reads the drafted-from release out of the licence row's "
            "`dataset` column, which the drafting pass writes itself. A module carrying the block "
            "still compiles, with a deprecation warning."
        ),
    )
    authorship: list[Contribution] = Field(json_schema_extra=since("0.4.0"), 
        default_factory=list,
        description=(
            "Optional structured per-version authorship (RM14): one entry per contributor with "
            "who/role/kind (+ optional date). Recorded verbatim into the manifest; out of "
            "`artifact.digest`. A joint contribution is two entries (a human and an ai)."
        ),
    )
    license: str | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "Optional licence the author declares for the module as a whole, e.g. 'CC-BY-SA-4.0'. "
            "The author's own claim, and nothing overwrites it: the compiler copies it through and "
            "**checks** it against the annotation-layer rows of the licensing table, warning in both "
            "modes when they disagree rather than replacing either. Advisory only in the sense that "
            "no gate reads it — unlike `module.version`, which a publishing registry really does "
            "stamp. The authoritative per-source record is `sources.csv`, which round-trips; this "
            "key is a human convenience and is NOT reconstructed by the lossy `reverse_module` "
            "(same class as `panel`/`authorship`)."
        ),
    )
    weighting: Weighting | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "What this module's `weight` column means — `scale`, `method` and `note`, all free text "
            "(RM92). `weight` is the one magnitude in the format with no unit beside it, so without "
            "this a consumer combining two modules' weights cannot know they are on different "
            "scales. Advisory, copied into the manifest, and NOT reconstructed by the lossy "
            "`reverse_module` (same class as `panel`/`authorship`/`license`)."
        ),
    )

    authority_precedence: list[str] = Field(json_schema_extra=since("0.7.0"), 
        default_factory=list,
        description=(
            "Optional ordered list of the annotation authorities this module's curator weighted while deciding its clinical calls, most-trusted first — e.g. `[clinvar, pubmind]` (RM134). A **methodological stance, recorded and computed with by nothing**: no tier reads it to resolve anything, no check consults it, no verdict and no emitted row depends on it, and changing it moves neither identity half. It exists so a consumer can see the stance instead of inferring it by reading every contested row.\n\nIt resolves nothing because nothing can. With five authorities in a two-against-three disagreement, this order says one thing and a majority says another, and choosing between those rules is a judgement about how rank trades against agreement count — a weighting model this format does not have and has declined to invent three times. So the concordance record states the agreement state and each authority's own call, a consumer holding its own model computes what it likes, and a per-variant exception is an `overrides.csv` row rather than a second mechanism. Advisory like `weighting:`/`authorship:`/`license:`, copied into the manifest, and NOT reconstructed by the lossy `reverse_module`."
        ),
    )

    @field_validator("authority_precedence")
    @classmethod
    def _check_authority_precedence(cls, v: list[str]) -> list[str]:
        """Reject an empty entry and a repeated one; the vocabulary itself stays open.

        Open because `authority` is open wherever else it appears — a deployment may weigh an
        authority this release has never heard of, and a closed set would make declaring that
        impossible rather than merely unusual.

        The two refusals are about the list being an *order*: a blank entry ranks nothing, and a name
        appearing twice states two different ranks for one authority, which is not an order at all.
        Neither is a judgement about which authorities exist.
        """
        cleaned = [(entry or "").strip() for entry in v]
        if any(not entry for entry in cleaned):
            raise ValueError(
                "authority_precedence is an ORDER, so every entry must name an authority — an empty "
                "entry ranks nothing. Drop it rather than leaving a hole in the list."
            )
        seen: set[str] = set()
        repeated = sorted({entry for entry in cleaned if entry in seen or seen.add(entry)})
        if repeated:
            raise ValueError(
                f"authority_precedence names {repeated} more than once, which states two ranks for "
                f"one authority. Each authority appears at most once; the order is the whole content "
                f"of the field."
            )
        return cleaned

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

    rsid: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="dbSNP identifier, e.g. rs1801133")
    chrom: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("chromosome", VALID_CHROMOSOMES), **since("0.2.0")},
        description=(
            "Chromosome. A 'chr'/'CHR' prefix is accepted and stripped, and the mitochondrion may be "
            "written MT, chrMT, M or chrM — all fold to MT, which is what gets stored"
        ),
    )
    start: int | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        ge=0,
        description=(
            "1-based genomic position (VCF POS convention), on the module's `genome_build` — the same "
            "convention as `ResolutionRow.start`, Ensembl, ClinVar and gnomAD. Do NOT subtract one: "
            "every check and every minted identity reads this column as VCF POS"
        ),
    )
    ref: str | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        description=(
            "Reference allele. Always spelled in bases — VCF's REF is a sequence, never symbolic; "
            "a structural allele belongs in `alts`"
        ),
    )
    alts: str | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        description=(
            "Alt allele(s), comma-separated. Bases, or a symbolic/structural allele carrying its "
            "length (<DEL:1500>, <CNV:TR:30>); spell the bases out whenever the sequence is known"
        ),
    )
    #: `ref`/`alts` (the locus), `genotype` and `effect_allele` (what the row's claim is about).
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("ref", "alts", "genotype", "effect_allele")
    #: What makes two rows the same row. The SNP core's keys live on the models too, so every
    #: keyed kind answers `hints.key_fields` from one place (S48); the compiler checks these two
    #: inline (`_cross_validate_variants`) rather than through `_TABLE_DUPE_KEYS`.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "genotype")
    variant_key: str | None = Field(
        default=None,
        json_schema_extra={**COMPILER_MANAGED, **since("0.4.0")},
        description=(
            "Frozen machine identity (rsid, else chrom:start:ref, or chrom:start:ref:alts when an alt "
            "is present so distinct alleles at one locus don't collide), stamped at load and never "
            "re-derived — so the resolver filling a coord/rsid can't re-key the row, and a one-to-many "
            "rsid expands to distinct coord-keyed rows (Principle 7). Compiler-managed: not authored, "
            "materialized to weights.parquet, and never written back by reverse_module."
        ),
    )
    authored_ident: list[str] | None = Field(
        default=None,
        json_schema_extra={**COMPILER_MANAGED, **since("0.5.0")},
        description=(
            "Which identity columns the author actually supplied, from {rsid, chrom, start, ref, "
            "alts}. Stamped at load like `variant_key` and never re-derived, so resolution can fill "
            "or expand without disturbing it. Compiler-managed: not authored, materialized to "
            "weights.parquet, and consumed by reverse_module to re-emit the authored shape — which is "
            "what keeps `content_signature` stable across a round-trip."
        ),
    )
    # ── The expansion marker (0.6, RM87) ──────────────────────────────────────────────────────────
    # Two columns rather than one, and the pair is the design. `locus_count` alone carries the
    # predicate but loses the ability to line a weights row up with its `resolution.csv` row;
    # `locus_index` alone is `0` on a non-expanded row *and* on the first member of every expansion,
    # so a reader holding one row cannot tell those apart. A single `expanded: bool` was refused under
    # P5 — it cannot later carry an ordinal without a retype, which is major-only.
    #
    # Declared through `stamped_identity_field`, so both are `exclude=True` and reach no
    # `content_signature`: they record what resolution did, which no human authored. `_build_weights`
    # reads them off the row by attribute, which is how they still reach `weights.parquet`.
    # `int | None`, not bare `int`, and the reason is the loader rather than the value: `load_csv_rows`
    # turns an empty cell into `None` **and keeps the key**, so a bare `int` makes a blank
    # `locus_count` column a type error instead of the accept-and-overwrite `_freeze_identity`
    # promises. The runtime value is never `None` — the validator resets both on every construction —
    # so `_build_weights` still writes two non-null `UInt32` columns.
    locus_index: int | None = stamped_identity_field(
        default=0,
        description=(
            "Which member of a one-to-many expansion this row is: the ordinal of its locus within the "
            "expansion of its authored key, 0-based. 0 on any row that was not expanded — read it "
            "with `locus_count`, never alone. Compiler-managed: not authored, materialized to "
            "weights.parquet, never written back by reverse_module."
        ),
     first_seen="0.6.0")
    locus_count: int | None = stamped_identity_field(
        default=1,
        description=(
            "How many loci the authored key resolved onto: 1 on any row that was not expanded, N on "
            "every member of an N-way expansion. `locus_count > 1` is the row-level predicate for "
            "'this row is one of several the module's author wrote once' — only the member whose "
            "alleles can carry the genotype asserts anything. Compiler-managed: not authored, "
            "materialized to weights.parquet, never written back by reverse_module."
        ),
     first_seen="0.6.0")
    #: rsid, or a full coordinate. Mirrors `_validate_identification` below; pinned to it by test.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = (
        frozenset({"rsid"}),
        frozenset({"chrom", "start"}),
    )

    genotype: str = Field(json_schema_extra=since("0.2.0"), 
        description=(
            "Slash-separated sorted alleles, e.g. A/G, or a single allele where the contig is "
            "hemizygous or haploid (non-PAR X/Y in males, homoplasmic MT). An allele is bases, or a "
            "symbolic/structural allele carrying its length — a heterozygous deletion sorts as "
            "<DEL:1500>/A. A pipe (A|G) is also accepted and records that the call was phased; with "
            "no phase-set column the order names no homolog, so it is phase recorded but "
            "unaddressable — say cis/trans in diplotypes.csv where a module needs it."
        )
    )
    weight: float | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Score (positive=protective)")
    # The description carries the members' STANDING, not just their names (S80). It read
    # `One of: risk, protective, neutral, significant, alt, ref` — six peers, no ordering — and an
    # authoring surface that passes our descriptions through verbatim (which is the contract we want
    # it to keep) therefore offered an agent six equal choices. It picked `alt` for a heterozygote,
    # honestly and wrongly, and the reporter had to read `derive.py` in their `.venv` to find out that
    # `alt`/`ref` are what that module's own docstring calls *the retired descriptors*.
    #
    # **Three groups, not the two the report asked for.** `state` is the Principle 5 anti-pattern the
    # charter names by hand — one field conflating statistical significance, effect direction and a
    # genotype descriptor — so the split has to be by *which axis a value was really on*:
    # `risk`/`protective`/`neutral` are directions and remain the ones to write; `significant` is a
    # significance claim that `direction` cannot express and `stat_significance` now owns; `alt`/`ref`
    # described the genotype and carry no direction at all, which is why `derive.py` maps both to
    # `unknown`. Calling `significant` retired alongside them would tell an author it means nothing,
    # when it means something this column is the wrong place for.
    #
    # **Naming the successor is what makes it actionable.** A standing with no destination is a
    # warning nobody can clear (P3's own test for whether a deprecation belongs in a minor), and all
    # three successors already ship.
    #
    # Not removed, and the reporter did not ask for that: published modules carry these values, the
    # read-time `effective_*` aliases depend on them, and removal is major-only under P3 regardless.
    state: str = Field(
        json_schema_extra={**vocabulary("state", VALID_STATES), **since("0.2.0")},
        description=(
            "Direction of effect for this genotype. Current: risk, protective, neutral. "
            "Superseded, still valid and still read: `significant` — a significance claim rather "
            "than a direction, write `stat_significance` instead; `alt`/`ref` — genotype "
            "descriptors carrying no direction, which derive to `direction=unknown`. Prefer the "
            "orthogonal `direction`/`stat_significance` columns, which this one predates."
        ),
    )
    conclusion: str = Field(json_schema_extra=since("0.2.0"), description="Human-readable interpretation for this genotype")
    negatives: str | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        description=(
            "Optional free-text adverse/antagonistic-pleiotropy counterpart to `conclusion` "
            "(e.g. a protective allele's known trade-off). Consumers ignore it when absent."
        ),
    )
    priority: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Priority level override")
    gene: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Gene symbol, e.g. MTHFR")
    phenotype: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Associated trait or phenotype")
    category: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Grouping category within the module")
    clinvar: bool | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Is this variant in ClinVar?")
    pathogenic: bool | None = Field(json_schema_extra=since("0.2.0"), default=None, description="ClinVar pathogenic flag")
    benign: bool | None = Field(json_schema_extra=since("0.2.0"), default=None, description="ClinVar benign flag")
    curator: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Curator override")
    method: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Annotation method override")

    # ── 0.3 additive columns (all optional; shipped in 0.3 — see docs/CHANGELOG.md) ──
    # **The two axes are orthogonal, and the description now says what that means for a weak trend
    # (S83).** Two runs of one prompt over one paper split `risk`/`unknown` on a concordant
    # non-significant trend (p ≈ 0.073, OR 3.58, CI 0.96–13.4), and both were defensible against the
    # old text, which named the members and said only *orthogonal to `state`* — the reader's question
    # is whether a sign you cannot lean on is still a sign, and orthogonality is precisely the answer:
    # yes, because `stat_significance` is the column that says whether to lean on it.
    #
    # **`unknown` means no sign to record, never a sign you may not act on.** Left unsaid, `unknown`
    # absorbs *the estimate does not exclude either direction*, and then the pair cannot express the
    # ordinary case it exists for — a real trend that is not established. Writing `unknown` there
    # discards the sign the paper reports and leaves `stat_significance` saying it about nothing.
    #
    # No new member: the state the reporter wanted is already the **pair** `direction=<sign>` +
    # `stat_significance=suggestive|not_significant`, and a member meaning "looked, no sign
    # established" would be a second spelling of it — P5's overloading, arriving as a synonym rather
    # than as a conflation.
    #
    # **That reasoning covered one of the reporter's three shades, and RM150 took a second.** The
    # other two — *nobody asked* and *the sources disagree* — are not one thing, and this description
    # used to say `unknown` meant both. One is an absence and the other is a finding, and no pairing
    # of `direction` with `stat_significance` can express "two sources disagree about the sign", which
    # is why this shade earned a member where the third did not. `unknown` keeps its original meaning
    # (re-pointing a shipped member is a retype in all but name), and `contested` is added beside it.
    direction: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description=(
            "Effect direction: one of protective|risk|neutral|unknown|contested. The sign of the "
            "reported estimate, whether or not it is established — a non-significant or borderline "
            "trend still has a direction, and `stat_significance` is what says how far to lean on "
            "it. **`unknown` and `contested` are different answers**: `unknown` is an absence, "
            "nobody assessed the sign; `contested` is a finding, the sources were consulted and they "
            "disagree about which way the effect runs. Neither is a sign you may not act on. "
            "Orthogonal to `state`, which predates both."
        ),
    )
    stat_significance: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description="Statistical significance: significant|suggestive|not_significant|unknown.",
    )
    effect_size: float | None = Field(json_schema_extra=since("0.3.0"), 
        default=None, description="Published effect magnitude (unit given by `effect_measure`)."
    )
    effect_measure: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary(
            "effect_measure", RECOMMENDED_EFFECT_MEASURES, closed=False
        ), **since("0.3.0")},
        description="Unit of `effect_size`, e.g. OR|HR|beta|RR (recommended; not a closed set).",
    )
    effect_allele: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description=(
            "The allele that `direction`/`weight`/`effect_size` refer to — bases, or a "
            "symbolic/structural allele carrying its length (e.g. <DEL:1500>)."
        ),
    )
    flags: list[str] | None = Field(
        default=None,
        json_schema_extra={**vocabulary("reserved_flags", RESERVED_FLAGS, closed=False), **since("0.3.0")},
        description=(
            "Open, multi-valued tag list (CSV: comma/semicolon/pipe-separated). Reserved tags the "
            "tooling acts on: conditional|phased|pleiotropic; other tags are allowed (surfaced as INFO)."
        ),
    )
    trait_efo_id: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description="EFO/MONDO/OBA/HP trait ontology id(s), e.g. EFO_0004340 (matches just-prs).",
    )
    clin_sig: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description="ClinVar/ACMG clinical significance (VEP CLIN_SIG vocabulary).",
    )

    # ── 0.4 general annotation axes (all optional; retired from the reserved namespace) ──
    # General per-variant refinements — any variant finding may carry them, so they live here rather
    # than in a domain table. A sparse SNP CSV simply omits them.
    requires_callable: bool | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        description=(
            "True when the *absence* of this variant is the informative call (recessive carrier, "
            "'pathogenic variant absent' reassurance) — a consumer lacking callability data must "
            "then withhold the reference/absence conclusion, never assert it (no-call ≠ hom-ref)."
        ),
    )
    acmg_sf: bool | None = Field(json_schema_extra=since("0.4.0"), 
        default=None, description="True when the gene is on the ACMG secondary-findings list."
    )
    actionability: str | None = Field(
        default=None,
        # CLOSED, despite `ACTIONABILITY_SEED`'s name and its own docstring: `_validate_actionability`
        # below calls `check_vocab`, which rejects a non-member. The authoring reference advertised it
        # under `open_recommended`, so a tool offering a novel value got a rejection it was told to
        # expect to work — a drift in *closedness* rather than in membership, which is exactly why
        # this marker carries the flag instead of just the members.
        json_schema_extra={**vocabulary("actionability", ACTIONABILITY_SEED), **since("0.4.0")},
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
    callable_from: str | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "Optional VCF field(s) a consumer establishes callability from, best written with the "
            "namespace (e.g. FORMAT/DP, FORMAT/GQ, FORMAT/FT, or FORMAT/DP|FORMAT/GQ). A declarative "
            "pointer, never an expression: it names where the evidence for 'this position was "
            "actually callable' lives, so a consumer can tell a confirmed negative from an uncovered "
            "one instead of reading both as reference. A bare key means unqualified — and INFO/DP is "
            "the cohort's combined depth, which says nothing about whether this sample was callable. "
            "Reference evidence usually arrives as a gVCF *block* (one record with END=), so a "
            "consumer finds it by interval containment rather than an equality join on position, "
            "and the block's floor is FORMAT/MIN_DP — a DP of 25 averaged over 14 bases is "
            "compatible with an uncovered base inside them."
        ),
    )
    # There is no `callable_element` here, and the absence is a decision (RM54, 0.6). The binning
    # tables' `source_field` got the element rule because that is where the defect had a real case;
    # `callable_from` can name a multi-valued field (`FORMAT/AD`) and no module does, and under the
    # 0.6 charter amendment a `variants.csv` column is the most expensive kind of addition this format
    # makes. The name is held in `vocab.RESERVED_NAMES_0_4` so it survives the one-way door.

    # ── 0.5.1: RM29(a), the call-confidence cofactor. Two columns, not a predicate. ──
    #
    # `requires_callable` says a negative must be proven and `callable_from` says where the proof
    # lives; both are about whether the position was *seen*. This pair is the orthogonal question of
    # whether what was seen is good enough to act on — an annotation stating where it stops being
    # reliable. RM29 records why it is columns rather than an expression: **a row's columns already
    # conjoin**, so a pointer plus a bound needs no grammar, no evaluator and no sandbox (P1).
    #
    # Deliberately *not* the dropped `caller`/`caller_version` names. Those recorded which tool made a
    # call — consumer-side measurement provenance with no module-side meaning. This states an
    # applicability bound the annotation itself carries, the same kind of thing `MeasureBinRow`'s
    # `[min, max]` states, and like those bounds it is inclusive.
    quality_from: str | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "Optional VCF field the `min_quality` floor is stated against, best written with the "
            "namespace (e.g. FORMAT/GQ, QUAL, FORMAT/DP). Same pointer grammar as "
            "`source_field`/`callable_from`; a pointer, never an expression. A bare key means "
            "unqualified, and INFO/MQ is a Float where FORMAT/MQ is an Integer. Prefer a per-sample "
            "confidence field: QUAL changes sign with the record (VCF 1.6.1.6 — prob(no variant) on "
            "a variant record, prob(variant) where ALT is '.'), so on a requires_callable row, whose "
            "evidence is the reference record, a high QUAL says the position is probably variant and "
            "the floor demands the opposite of what the row is about."
        ),
    )
    # No `quality_element` either, and for the same reason as `callable_element` above: `min_quality`
    # is a scalar floor, so a multi-valued `quality_from` would need one — and nothing points at one.
    min_quality: float | None = Field(json_schema_extra=since("0.5.0"), 
        default=None,
        description=(
            "Inclusive floor on `quality_from`: withhold this row's conclusion where the consumer's "
            "value is below it. A consumer that cannot read the field withholds rather than "
            "asserting — an unevaluable floor is unknown, never satisfied."
        ),
    )

    @field_validator("min_quality")
    @classmethod
    def _validate_min_quality(cls, v: float | None) -> float | None:
        return validate_finite(v, "min_quality")

    @model_validator(mode="after")
    def _require_quality_pair(self) -> "VariantRow":
        """Both or neither — half a floor states nothing a consumer can act on.

        A bound with no field does not say *what* must clear it, and a field with no bound states no
        threshold at all. Either half alone reads as a configured gate and is not one, which is worse
        than an empty cell: a consumer would have to guess the missing half, and every guess is a
        clinical policy the module did not write.
        """
        if (self.quality_from is None) != (self.min_quality is None):
            missing = "min_quality" if self.min_quality is None else "quality_from"
            raise ValueError(
                f"quality_from and min_quality are both-or-neither; {missing} is empty. A floor "
                f"needs a field to be measured against, and a field needs a floor to be a floor."
            )
        return self

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

        The RM87 pair is reset here for the same "no foot-gun" reason, and it is not decoration: the
        fields exist on the model, so `extra="forbid"` cannot see a `locus_count` column in someone's
        `variants.csv`, and nothing else would ever overwrite it — a non-expanded row is marked by the
        field *defaults*, with no stamp-at-load pass to correct an authored cell. An accepted
        `locus_count=5` would reach `weights.parquet` unhashed and vanish on reverse, so
        `compile → reverse → compile` would stop being a fixed point. Accepted-and-overwritten is the
        same treatment `variant_key` gets one line up.
        """
        self.variant_key = derive_variant_key(self.rsid, self.chrom, self.start, self.ref, self.alts)
        self.authored_ident = [
            name for name in ("rsid", "chrom", "start", "ref", "alts")
            if getattr(self, name) is not None
        ]
        self.locus_index = 0
        self.locus_count = 1
        return self

    # `authored_key` — "the identity the author wrote, recomputed from `authored_ident`" — lived here
    # and is **removed**. It had no caller anywhere in the workspace: `reverse_module` recomputes the
    # same expression inline from a polars row dict, which is not a `VariantRow` and so could never
    # have used the property. What made a dead duplicate worth deleting rather than leaving is that it
    # was *build-blind* — it called `derive_variant_key` with no `build`, so on a `genome_build: GRCh37`
    # module it minted a GRCh38 `ga4gh:VA.…`, the exact identity falsification the 2026-08-06 sweep
    # found in four other places. A second copy of a rule that has already gone wrong four times is a
    # trap, not a convenience. The live copy in `_write_variants_csv` passes the build.
    #
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
    def effective_clin_sig(self) -> str | None:
        """`clin_sig` if set, else derived from the legacy ClinVar booleans (lossy)."""
        return self.clin_sig or clin_sig_from_booleans(
            self.pathogenic, self.benign, self.clinvar
        )

    @property
    def effective_pathogenic(self) -> bool | None:
        """The authoritative `pathogenic` boolean, or the one implied by `clin_sig` when unset."""
        if self.pathogenic is not None:
            return self.pathogenic
        return pathogenic_from_clin_sig(self.clin_sig)

    @property
    def effective_benign(self) -> bool | None:
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
    def _validate_chrom(cls, v: str | None) -> str | None:
        """Fold the author's spelling to this format's member, or refuse and say why (RM60 + RM48).

        **The gate and the normalizer disagreed, and the stricter one was the gate.** This did
        `removeprefix("chr")` and then required membership, while `vrs.normalize_chrom` — in the same
        package, and what every id-minting path already runs — also strips `CHR`/`Chr` and folds
        `M`/`chrM` to `MT`. So `MT` and `chrMT` validated and `chrM`, `M` and `CHR7` did not, with a
        message that lists `MT` and never mentions that `chrM` is the same contig. That matters because
        real GRCh38 files split on exactly this: Ensembl-style writes `MT`, the hs38DH analysis set most
        human pipelines actually align against writes `chrM`.

        Routing the gate through the normalizer **widens only** (P3): every value that validated before
        still validates and still normalizes to the same member, so no published module changes and no
        stored key moves. Alt contigs, scaffolds, patches and decoys stay rejected, correctly and by
        charter — `REFGET_GRCh38` is primary assembly only. Same class as the 0.6 `-`-for-`_` vocabulary
        tolerance: what is stored is always the declared member, never the author's spelling, so nothing
        downstream ever sees two spellings of one contig.

        **And when the rejected name is another build's, say which (RM48).** The verdict does not
        change — an unplaced scaffold is out of this vocabulary either way — but whether the author
        learns *why* does, because `GL000209.1` and `KI270728.1` do not arrive by typo. They arrive by
        pasting rows out of a VCF built on the other assembly, which means the module's *other* rows
        are probably on it too. Told only "chrom must be one of 1-22, X, Y, MT", an author deletes the
        scaffold row and ships the rest; told which build names it, they check the build. Same
        generic-rejection-is-a-dead-end rule as `reject_reserved` and `reject_misplaced`: diagnose,
        decide nothing new. `sole_build_naming_contig` withholds on every name its tables cannot
        settle, so a contig both builds carry adds no clause rather than a guess.

        The two halves compose in one direction only, and it is worth saying which: the widening
        decides what is *accepted*, the diagnosis only enriches what is *refused*. Neither can turn a
        rejection into an acceptance or the reverse.
        """
        if v is None:
            return v
        normalized = normalize_chrom(v)
        if normalized is None or normalized not in VALID_CHROMOSOMES:
            elsewhere = sole_build_naming_contig(v)
            because = (
                f" — that is a top-level sequence of {elsewhere} and of no other build this schema "
                f"knows, so these rows are most likely on {elsewhere} rather than on the build the "
                f"module declares"
                if elsewhere
                else ""
            )
            raise ValueError(
                f"chrom must be one of 1-22, X, Y, MT, got: {v!r}. A 'chr'/'CHR' prefix is accepted "
                f"and stripped, and 'M'/'chrM' is accepted as a spelling of MT; an alt contig, "
                f"scaffold, patch or decoy is not — this format keys on the primary assembly "
                f"only{because}"
            )
        return normalized

    # `genotype`'s grammar lives on `AuthoredModel` since 0.5 — `PharmVariantRow` declares the same
    # field, and a validator shared by two models belongs on the base (see base.py).

    @field_validator("actionability")
    @classmethod
    def _validate_actionability(cls, v: str | None) -> str | None:
        return check_vocab(v, ACTIONABILITY_SEED, "actionability")

    @field_validator("effect_allele")
    @classmethod
    def _validate_effect_allele(cls, v: str | None) -> str | None:
        return validate_allele(v, "effect_allele")

    @field_validator("weight")
    @classmethod
    def _validate_weight(cls, v: float | None) -> float | None:
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
    def _validate_flags(cls, v: list[str] | None) -> list[str] | None:
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

    #: What makes two rows the same row (see `VariantRow._KEY_FIELDS`).
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("variant_key", "pmid")

    rsid: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="dbSNP identifier or variant key")
    # No `chromosome` marker: `StudyRow` runs no chrom validator (only `VariantRow` does), and a
    # marker must describe what actually rejects. Same call as the PGx tables — see `pgx.py`.
    chrom: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Chromosome (for position-only variants)")
    start: int | None = Field(json_schema_extra=since("0.2.0"), 
        default=None,
        ge=0,
        description="1-based position, VCF POS convention (position-only variants) — do not subtract one",
    )
    ref: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Reference allele (position-only variants)")
    #: **Empty since 0.6 (RM47): a study row need not name a variant at all.** It used to be
    #: `({rsid}, {chrom})` — rsid, or a bare `chrom` with no `start`. The rule was unsatisfiable for
    #: exactly the modules that most needed a citation: a `repeat_alleles.csv`/`copynumbers.csv`/
    #: `activity_phenotype.csv` row is keyed `(gene, …)` and names no variant, so an author grounding
    #: a threshold had to invent one — writing a bare `chrom=4` for HTT, which asserts a locus the
    #: paper is not about. Widening an either-or rule only makes previously-*invalid* rows valid, so
    #: no published module breaks (P3/P8: nothing became required and nothing was retyped).
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = ()
    #: `effect_allele` only, and the omission of `ref` is the point (RM91). `AuthoredModel`'s rule is
    #: *sequence columns that are the claim, never a column that merely points at a variant*, and it
    #: names `StudyRow.ref` as its own example of the second kind. `effect_allele` is the first kind:
    #: it is what the row's magnitude is stated relative to, exactly as on `VariantRow`.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ("effect_allele",)

    pmid: str = Field(json_schema_extra=since("0.2.0"), description="PubMed ID or reference — free-form, must be non-empty")
    population: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Study population")
    p_value: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Raw p-value string (free-form)")
    conclusion: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="Study-specific conclusion")
    study_design: str | None = Field(json_schema_extra=since("0.2.0"), default=None, description="e.g. meta-analysis, GWAS")

    # ── 0.3 additive columns (per-study evidence; shipped in 0.3 — see docs/CHANGELOG.md) ──
    stat_significance: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None,
        description="Per-study statistical significance: significant|suggestive|not_significant|unknown.",
    )
    effect_size: float | None = Field(json_schema_extra=since("0.3.0"), 
        default=None, description="Per-study effect magnitude (unit given by `effect_measure`)."
    )
    effect_measure: str | None = Field(
        default=None,
        json_schema_extra={**vocabulary("effect_measure", RECOMMENDED_EFFECT_MEASURES, closed=False), **since("0.3.0")},
        description="Unit of `effect_size`, e.g. OR|HR|beta|RR (recommended, open).",
    )
    # RM91 (0.6). `VariantRow` has carried `effect_allele` since 0.3 for a stated reason — `ref`/`alts`
    # plus the sign of the magnitude cannot recover which allele the claim is about — and a study row
    # states a magnitude too, with no such column. So `effect_size` here was relative to nothing, and
    # the failure mode is the silent one: a wrong effect allele inverts the finding rather than
    # breaking it. Optional, so every published module stays valid (P8) and an unset cell is omitted
    # from `content_signature`.
    effect_allele: str | None = Field(json_schema_extra=since("0.6.0"), 
        default=None,
        description=(
            "The allele this study's `effect_size` is stated relative to — bases, or a "
            "symbolic/structural allele carrying its length (e.g. <DEL:1500>). Absent means the "
            "study did not state one, which is not the same as the reference allele."
        ),
    )
    trait_efo_id: str | None = Field(json_schema_extra=since("0.3.0"), 
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s) for this study."
    )

    # ── 0.7 additive column: which analysis produced the numbers on this row (RM140, S75) ──
    # `study_design` describes the STUDY — case-control, GWAS, meta-analysis. One study routinely runs
    # several analyses of one association, and this column describes THE ANALYSIS. The motivating case
    # is a single paper reporting `OR 1.4, p 0.36` from an allelic Fisher's exact test and
    # `OR 1.42, p 0.75` from a univariate logistic regression of the same variant: two agents building
    # the same module from it produced rows that differed only in `p_value`, and one of the two had
    # taken its `effect_size` from one analysis and its `p_value` from the other. Everything was green,
    # because a `p_value` and an `effect_size` on one row are *asserted* to belong together and nothing
    # recorded what either came from. A provenance quote cannot witness it either: the quote grounding
    # that row's significance verdict contains no statistic at all.
    #
    # **A column, and deliberately not a gate.** Requiring the pair to come from one analysis is
    # unwritable until the fact it compares exists, and adding the column and the gate together would
    # make every published row retroactively incomplete. The reporter argued this against their own
    # first candidate; it is recorded here because the column looks under-specified without it.
    #
    # **Free text like `study_design`, and no `RECOMMENDED_*` vocabulary.** The space is open —
    # "Fisher's exact (allelic)", "univariate logistic regression", "logistic regression adjusted for
    # age, sex, BMI", "fixed-effect meta-analysis" — and a recommended set is additive later if a
    # corpus ever shows a shape. What the column has to do first is make two rows distinguishable.
    statistical_test: str | None = Field(json_schema_extra=since("0.7.0"), 
        default=None,
        description=(
            "Which analysis produced this row's `p_value`/`effect_size` — the test or model, and what "
            "it was adjusted for, e.g. `Fisher's exact (allelic)` or `logistic regression adjusted "
            "for age and sex`. Free text. `study_design` describes the study; this describes the "
            "analysis, and one study may report several. Absent means the paper's analysis was not "
            "recorded, never that it had only one."
        ),
    )

    # ── 0.4 provenance columns (RM11/RM12, from the 0.5 scope; docs/USE_CASES.md §4a) ──
    # All optional → P3/P8 clean. They anchor a network-first validator (RM13) without the format
    # ever fetching: the module ships the pointer, the consumer supplies the source and does the check.
    doi: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        description=(
            "Digital Object Identifier — wider than `pmid` (covers preprints/books/datasets with no "
            "PubMed id). Free-form, kept verbatim; a validator may cross-fill doi↔pmid."
        ),
    )
    provenance_quote: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        description=(
            "Optional keyword phrase / literal passage locating this study's claim in the cited "
            "article's fulltext. Human-legible; a validator confirms fulltext-contains, yes/no."
        ),
    )
    provenance_regex: str | None = Field(json_schema_extra=since("0.4.0"), 
        default=None,
        description=(
            "Optional regex locating the claim in fulltext — a declarative pattern grammar "
            "(Principle 1: data, not code), matched consumer-side by a linear-time/ReDoS-safe engine."
        ),
    )

    # ── 0.6 additive column: who located the passage above (S55) ──
    # `VariantRow.curator` has always let a row name who decided it; the table where the *attestation*
    # lives had no such column, so a quote could not name its locator. That asymmetry is backwards
    # given which of the two is an attestation, and it is what made `attestation_bearing` bite: the
    # refusal protected a fiction about *who* read the article rather than the reading itself, and the
    # column then stayed empty for the only reader actually present. An AI curator is not an edge case
    # here — `Defaults.curator` defaults to the literal `ai-module-creator`.
    #
    # **Free text resolvable against `authorship`, never a `machine_located: bool`.** Two-valued
    # collapses the case that actually occurs — a passage an agent found and a human then confirmed —
    # into one of two lies, and it cannot name *which* agent or *which* human. `Contribution.who`
    # already reads "a name, handle, or model id" for exactly this reason.
    #
    # **It records labour, never responsibility.** An AI is not a subject of right, so the human
    # author holds it entirely whatever this cell says; the point is that a reviewer can route
    # scrutiny, which is what `Contribution.kind`'s own docstring says its axis is for.
    curator: str | None = Field(json_schema_extra=since("0.6.5"), 
        default=None,
        description=(
            "Who located this row's provenance quote/regex — a name, handle, or model id, resolvable "
            "against the manifest's `authorship`. Row-level because real work is mixed at row "
            "granularity: a human may read a review while an agent traverses its citations, in one "
            "module, in one pass. Records the distribution of labour so a reviewer can route "
            "scrutiny; it does not move responsibility, which the human author holds regardless."
        ),
    )

    # ── 0.5 additive column: the queryable form of `p_value` above ──
    # `p_value` stays the verbatim record (free-form, and kept by P8 — retyping or removing it is a
    # 1.0 item). This carries the same number in a form that sorts and thresholds.
    p_value_num: float | None = Field(json_schema_extra=since("0.5.0"), 
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
    def variant_key(self) -> str | None:
        """Stable key matching VariantRow.variant_key, or `None` when the row names no variant.

        StudyRow is never resolved/expanded, so its key stays a derived property (no freezing needed).

        `None` is the 0.6 shape (RM47): a citation row may now describe the module or a gene-keyed
        binning table rather than a variant, and `derive_variant_key(None, None, None, None)` would
        otherwise hand back the string `"None:None:None"` — a key that looks like an identity and
        names nothing. Same reasoning as `HeteroplasmyRow.variant_key`, and the reason the orphan half
        of the compiler's study cross-check skips these rows: a row that names no variant cannot
        reference one that is missing."""
        if self.rsid is None and self.chrom is None:
            return None
        return derive_variant_key(self.rsid, self.chrom, self.start, self.ref)

    @property
    def neg_log10_p(self) -> float | None:
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
        # Shared with `MeasureBinRow.pmid` — see `validate_pmid_cell`. Required here: grounding
        # evidence is mandatory for a variant annotation.
        checked = validate_pmid_cell(v, "pmid", required=True)
        assert checked is not None
        return checked

    @field_validator("doi")
    @classmethod
    def _validate_doi(cls, v: str | None) -> str | None:
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
    def _validate_provenance_regex(cls, v: str | None) -> str | None:
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
        # **A row may name NO variant since 0.6 (RM47), but never half of one.** The old rule demanded
        # an rsid or a bare `chrom`, which a citation grounding a *bin boundary* cannot supply:
        # `repeat_alleles.csv` is keyed `(gene, repeat_unit)`, so the rule pushed authors into writing a
        # bare `chrom=4` for HTT — an assertion about a locus in a row that is about a threshold. What
        # the relaxation legalises is the empty subject, and only that. A row carrying `start`/`ref`
        # with no `rsid` and no `chrom` is the commonest CSV slip (a blank cell in the middle of a
        # coordinate) and it is not a subject-less citation: `variant_key` would answer `None` while
        # `studies.parquet` still carried the orphaned position, so the row would read as grounding the
        # module while holding a coordinate nothing can join. `VariantRow` refuses a partial coordinate
        # for the same reason.
        if self.rsid is None and self.chrom is None:
            dangling = [
                name for name, value in (("start", self.start), ("ref", self.ref))
                if value is not None
            ]
            if dangling:
                raise ValueError(
                    f"a study row may name no variant at all — a citation can ground the module or a "
                    f"binning bound — but {dangling} without rsid or chrom is a half-written "
                    f"coordinate, not an absent one. Add chrom, or clear these columns."
                )
        return self
