"""Shared base for every authored-DSL row model (`spec`/`binning`/`pgx`/`pgs`).

Consolidates the boilerplate that was copy-pasted across the row models into one place:

- the **reserved-namespace guard** — `extra="forbid"` plus the `reject_reserved` before-validator, so
  a reserved name fails with a specific diagnosis and any other unknown/misspelled column fails with
  the generic message (see `vocab.reject_reserved`); and
- the **field validators for the shared authored vocabulary** — `rsid`, `trait_efo_id`, `direction`,
  `clin_sig`, `stat_significance`, `evidence_level`, finite-`effect_size`, `genotype`, the VCF
  field-pointer grammar (`source_field`/`callable_from`/`quality_from`) and the element rule that
  qualifies each of those (`source_element`/`callable_element`/`quality_element`).

Each field validator uses `check_fields=False`, so a subclass runs it only for the fields it actually
declares (a model without `clin_sig` simply never runs the `clin_sig` check) and a model that *adds*
one of these fields gets the correct validation for free — the per-field rules cannot drift model to
model, which is exactly what the previous copy-paste risked. Field-specific rules (star-allele
strings, measure bounds, PGS ancestry, the mtDNA legacy-reference guard, identifier completeness)
stay on their own models.

`genotype` moved here in 0.5 when `PharmVariantRow` gained one: the grammar is the *same* grammar
(a PharmGKB per-genotype clinical annotation describes the same diploid call a `VariantRow` does), and
the DRY rule applies as soon as a validator is shared by two models. It is deliberately **not**
widened for the symbolic alleles PharmGKB also carries (`C/del`, `del/del`) — those are RM5, and the
enricher skips them rather than coercing them into a nucleotide grammar that cannot express them.

Dependency-light: imports only `pydantic` + the stdlib `vocab` leaf, and nothing in the package
imports it back, so it introduces no cycle.
"""

from typing import Any, ClassVar, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    ValidationInfo,
    field_validator,
    model_validator,
)

from just_dna_format.vocab import (
    ALLELE_PATTERN,
    VALID_CLIN_SIG,
    VALID_DIRECTIONS,
    VALID_ELEMENT_RULES,
    VALID_EVIDENCE_LEVELS,
    VALID_SIGNIFICANCE,
    VCF_POINTER_COMPANIONS,
    check_vocab,
    reject_misplaced,
    reject_reserved,
    reject_template_placeholders,
    validate_field_token,
    validate_finite,
    validate_rsid,
    validate_trait_ids,
)
from just_dna_format.vrs import UnsupportedBuildError, derive_vrs_allele_id

# ── Compiler-managed columns ────────────────────────────────────────────────────────────────────
# Marker for a field the *compiler* stamps at load rather than the author writing it — today
# `VariantRow.variant_key` and `VariantRow.authored_ident`, which `_freeze_identity` derives and
# which `reverse_module` deliberately never writes back. They are declared as model fields because
# they are carried in memory and materialized to `weights.parquet`, but they are not part of the
# authored surface, and a tool that generates CSV columns from `model_fields` must not offer them:
# `authored_ident` is a `list[str]`, so a rendered cell (`rsid`) does not even reload as one.
#
# Attached with `json_schema_extra` so the fact lives on the field itself. A hand-kept list somewhere
# else is how `reverse_module`'s writer and a generator drift apart — see `authored_field_names`.
COMPILER_MANAGED: dict[str, bool] = {"compiler_managed": True}


def authored_field_names(model: type[BaseModel]) -> list[str]:
    """The columns a human actually authors for `model`, in field-declaration order.

    `model_fields` minus anything marked `COMPILER_MANAGED`. Every generator over the authored
    surface — a blank template, a drafted CSV's header — reads its columns through here, so a field
    that stops being authored stops being offered in the same commit that marks it."""
    return [
        name
        for name, field in model.model_fields.items()
        if not (
            isinstance(field.json_schema_extra, dict)
            and field.json_schema_extra.get("compiler_managed")
        )
    ]


# ── Vocabulary-bound columns ────────────────────────────────────────────────────────────────────
# Marker for a field whose value is drawn from a constrained vocabulary, carrying the members with it
# so an authoring tool can offer them ("valid options to select from") without knowing the field.
#
# **The marker carries the options, not a name to look up.** A name would need a central registry, and
# the vocabularies deliberately live in the leaves that own them (`vocab`, `spec`, `binning`, `pgx`,
# `pgs`, `manifest`, `sources`). A registry in `vocab` cannot import `pgx` — that is the cycle this
# module's "imports only pydantic + the stdlib vocab leaf" note exists to avoid — and a registry
# anywhere else is a second hand-kept list, which is the exact failure being fixed: the authoring
# reference's vocabulary block *was* such a list, and it silently missed `recommendation_strength`
# and `phenotype_category` when 0.5 added them. Reading the members off the frozenset at class-
# definition time makes that drift impossible by construction.
#
# `sorted(...)` of `str` keeps the marker JSON-serializable, so `model_json_schema()` still builds.
def accepts_none(annotation: Any) -> bool:
    """Does this annotation admit `None`? (`Optional[str]` yes; a defaulted bare `str`/`bool` no.)"""
    return annotation is type(None) or type(None) in get_args(annotation)


def field_category(model: type[BaseModel], name: str) -> str:
    """`required` | `defaulted` | `optional` — the three-way split an authoring surface must respect.

    The middle category is the one that bites. `MeasureBinRow.measure_kind` (`str`, default
    `"repeat_count"`) and `unresolved` (`bool`, default `False`) are *not* required, so pydantic's
    `is_required()` says `False` — but `_load_csv_rows` turns an empty cell into `None` and **keeps
    the key**, so the model receives `None` instead of its default and fails on type. An author who
    filled exactly the columns a two-way `required` flag named got a rejection about a column nobody
    had mentioned. A `defaulted` cell has to be written out with its default rather than left blank.

    It lives **here** rather than in the compiler because two surfaces answer this question and they
    drifted: `just_dna_compiler.draft` was fixed to the three-way split and `reference.authoring_reference`
    — the drift-proof description consumers render *instead of* a hand-kept spec dump — was still
    emitting the two-way one. Both now read this. The format tier is the only place both can import
    from, and this needs nothing but pydantic.
    """
    field = model.model_fields[name]
    if field.is_required():
        return "required"
    return "optional" if accepts_none(field.annotation) else "defaulted"


def vocabulary(name: str, options: frozenset[str], *, closed: bool = True) -> dict[str, object]:
    """Mark a field as drawn from `options`, for tools that offer an author the valid values.

    `closed=True` means a validator rejects anything outside the set; `closed=False` marks the
    recommended-but-open sets (`RECOMMENDED_EFFECT_MEASURES`, `ACTIONABILITY_SEED`,
    `RECOMMENDED_AUTHOR_KINDS`), where the members are suggestions and a novel value is legal. A
    consumer must be able to tell "pick one of these" from "these are suggestions", so the two are one
    marker with a flag rather than two markers."""
    return {"vocabulary": {"name": name, "options": sorted(options), "closed": closed}}


# The vocabularies enforced by this class's own shared validators below. Declared once, here, so the
# `check_vocab` call and the marker a tool reads are the *same object* — for these four the two
# cannot disagree even in principle. A per-field marker would have to be repeated on every model
# declaring the column (`direction` is declared on `VariantRow`, `MeasureBinRow` and `DiplotypeRow`),
# and a repeated marker is a list again. The rule for where a binding lives is simply *where its
# validator lives*: shared validator → here; model-specific validator → that model's `Field(...)`.
SHARED_VOCABULARIES: dict[str, frozenset[str]] = {
    "direction": VALID_DIRECTIONS,
    "clin_sig": VALID_CLIN_SIG,
    "stat_significance": VALID_SIGNIFICANCE,
    "evidence_level": VALID_EVIDENCE_LEVELS,
    # The element-rule column(s) (RM54) — `source_element` today, and whatever companion a later
    # release adds beside another pointer. Derived from `VCF_POINTER_COMPANIONS` rather than listed,
    # so the vocabulary a tool offers and the set the validator enforces cannot drift apart from the
    # relation the check reads.
    **dict.fromkeys(VCF_POINTER_COMPANIONS, VALID_ELEMENT_RULES),
}


def field_vocabularies(model: type[BaseModel]) -> dict[str, dict]:
    """`{field_name: {name, options, closed}}` for every vocabulary-bound field of `model`.

    The single route to "what may this cell contain" — `authoring_reference()` and any authoring tool
    read it, and neither keeps a list of its own. Covers both binding sites: a field marked at its own
    declaration, and a field whose vocabulary is enforced by `AuthoredModel`'s shared validators."""
    found: dict[str, dict] = {}
    for name, field in model.model_fields.items():
        marker = (
            field.json_schema_extra.get("vocabulary")
            if isinstance(field.json_schema_extra, dict)
            else None
        )
        if isinstance(marker, dict):
            found[name] = marker
        elif name in SHARED_VOCABULARIES:
            found[name] = vocabulary(name, SHARED_VOCABULARIES[name])["vocabulary"]
    return found


def derive_variant_key(
    rsid: str | None,
    chrom: str | None,
    start: int | None,
    ref: str | None,
    alts: str | None = None,
    *,
    build: str = "GRCh38",
) -> str:
    """The natural identity for a variant-ish row: the rsid when present, else the coordinate.

    Three cases, in precedence order:

    1. **rsid** — an rsid row keeps its rsid, unchanged. (A dbSNP id is position/multi-allelic-level,
       not per-allele, which is why clinical identity keys on this *plus* genotype, never on rsid.)
    2. **A resolved single-base substitution** (0.5) — the key is its **GA4GH VRS allele id**,
       `ga4gh:VA.…`, minted by `vrs.derive_vrs_allele_id`. This is a *content-addressed* identity: it
       names the allele by the digest of the exact reference sequence it sits on, so it is
       build-naming rather than build-ambiguous — the property RM15 was waiting for before coordinate
       identity could be reconsidered. Byte-identical to the ids gnomAD and ClinGen serve, so it joins
       against them directly instead of needing a translation table.
    3. **Everything else** — the coordinate key `chrom:start:ref`, or `chrom:start:ref:alts` when an
       alt is given, so two distinct alleles at one locus (an insertion `C>CAAAG` beside a deletion
       `C>CA`, a benign `C>G` beside a pathogenic `C>A`) do not collide. `alts` is normalized (its
       comma-separated alleles sorted) so the key is stable regardless of authored order.

    Case 2 covers substitutions only — an indel, an MNV, a multi-allelic cell and a contig outside the
    primary assembly all fall through to case 3, because a VRS allele id is defined over the *fully
    justified* allele and justifying an indel needs the reference sequence, which this tier will never
    fetch (Principle 2). See `vrs.derive_vrs_allele_id`. That split is deliberate and permanent-shaped:
    an id is minted only where it can be minted *correctly*, and the fallback is the same key these
    rows already had.

    Single source of truth shared by `VariantRow` (which *freezes* the result into a stored column so
    resolution can never re-key a row) and the one-to-many expansion re-keying. `StudyRow` and the
    position-level *matching* helpers deliberately call this **without** `alts` — a study is
    position/rsid evidence and matches a variant at `chrom:start:ref` regardless of which allele it
    carries — and so are never affected by case 2. See docs/COMPILER.md: the frozen `variant_key` keeps
    a position-only row that later resolves to an rsid from flipping its identity, and lets a
    one-to-many rsid expand to distinct coord-keyed rows (Principle 7).

    `build` is the assembly the coordinate is in; only GRCh38 has a refget table today, and any other
    build falls through to case 3 rather than minting an id that would claim the wrong sequence.
    """
    if rsid is not None:
        return rsid
    if alts and "," not in alts:
        vrs_id = _mint_vrs_key(chrom, start, ref, alts.strip(), build)
        if vrs_id is not None:
            return vrs_id
    base = f"{chrom}:{start}:{ref}"
    alts_norm = ",".join(sorted(a.strip() for a in alts.split(",") if a.strip())) if alts else ""
    return f"{base}:{alts_norm}" if alts_norm else base


def _mint_vrs_key(
    chrom: str | None, start: int | None, ref: str | None, alt: str, build: str
) -> str | None:
    """Case 2 of `derive_variant_key`, isolated so the fallback path stays readable.

    Returns `None` for anything unmintable — including a build with no refget table, which
    `refget_accession` reports by raising rather than by guessing, and which is a fall-through here
    (a GRCh37 module keeps its coordinate key) rather than a hard failure at row-load time.
    """
    try:
        return derive_vrs_allele_id(chrom, start, ref, alt, build=build)
    except UnsupportedBuildError:
        return None


#: The assembly a row is assumed to be on when nobody has said otherwise. Matches
#: `ModuleSpecConfig.genome_build`'s default, deliberately — a row loaded outside a module gets the
#: same answer compiling that directory would give, which is a derivation rather than a guess.
DEFAULT_GENOME_BUILD: str = "GRCh38"


class AuthoredModel(BaseModel):
    """Base for authored-DSL rows: reserved-namespace guard + shared-vocabulary field validators."""

    model_config = ConfigDict(extra="forbid")

    #: The module's declared assembly, **injected by the loader, never authored**.
    #:
    #: A coordinate is not absolute, so any row that derives an identity from one needs to know which
    #: assembly it is in — and a pydantic model is constructed from a CSV row dict, with no
    #: `module_spec.yaml` in scope. The 2026-08-06 sweep found seven paths that answered a GRCh38
    #: question in a GRCh37 module's name because of exactly that gap.
    #:
    #: **A private attribute, not a column, and the distinction is the whole design.** The build is a
    #: *module-wide* property, so stating it per row (or per CSV, as a service row) would let two files
    #: disagree about one fact, overload a data table with a non-data row (Principle 5), and burden the
    #: rare human author with bookkeeping — while still not reaching the model, since a loader that
    #: parsed such a row would already know the build from the yaml it just read. So the build stays
    #: declared exactly once, in `module_spec.yaml`, and the loader *tells* each row it builds. Being
    #: private, it is absent from `model_fields` and from `model_dump()`, so it reaches no CSV, no
    #: parquet, and does not move `artifact.digest`; `extra="forbid"` still rejects it as a column.
    _genome_build: str = PrivateAttr(default=DEFAULT_GENOME_BUILD)

    @property
    def genome_build(self) -> str:
        """The assembly this row was loaded as being on. Read-only; see `_genome_build`."""
        return self._genome_build

    def with_genome_build(self, genome_build: str) -> "AuthoredModel":
        """Tell this row which assembly it is on. Returns `self`, so a loader can map over rows.

        Deliberately a method rather than a settable property: injecting the build is something a
        *loader* does once, at a known point, and making it look like an ordinary attribute assignment
        would invite it being done anywhere. `just_dna_compiler.compiler._load_csv_rows` is the caller.
        """
        self._genome_build = genome_build
        return self

    #: Alternative sets of columns, any ONE of which satisfies the row's identity requirement.
    #: Empty when requiredness is fully expressed by the fields themselves.
    #:
    #: Pydantic's `is_required()` answers "must this column be present", which is not the whole
    #: contract: `VariantRow` needs `rsid` **or** `chrom`+`start`, and that rule lives in a
    #: `model_validator`, invisible to any tool listing required columns. `draft.required_fields`
    #: consequently told an author a `variants.csv` needed nothing but `genotype`/`state`/`conclusion`.
    #: Declaring the groups beside the validator makes the rule machine-readable; a test proves the
    #: declaration and the validator agree by construction, so the two cannot drift.
    #:
    #: A `ClassVar` rather than a per-field marker because the rule is a property of the *model*:
    #: `{"chrom", "start"}` is one group meaning "both together", which no annotation on `chrom`
    #: alone can express. `MeasureBinRow._KEY_FIELDS`/`_EXPECTED_KIND` are the same shape for the
    #: same reason — generic code reading model-level structure without a name list.
    REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]] = ()

    @model_validator(mode="before")
    @classmethod
    def _guard_raw_input(cls, data: object) -> object:
        # Both guards run on the RAW dict, before field coercion, so each can give its own diagnosis
        # instead of pydantic's type error. Placeholder first: a stub row is a half-written template,
        # which is more useful to say than "that column is also reserved".
        reject_template_placeholders(data, what=f"{cls.__name__} row")
        # A column that is real on a *generated* table but not here is a plausible confusion rather
        # than a typo, so it gets its own diagnosis too — keyed on this model's own fields, so a model
        # that genuinely declares it is untouched (S17).
        reject_misplaced(data, cls.model_fields, what=f"{cls.__name__} row")
        # A reserved name fails with a specific diagnosis; any other unknown/typo'd column falls
        # through to `extra="forbid"`'s generic message. See vocab.reject_reserved.
        return reject_reserved(data)

    @field_validator("rsid", check_fields=False)
    @classmethod
    def _validate_rsid(cls, v: str | None) -> str | None:
        return validate_rsid(v)

    @field_validator("trait_efo_id", check_fields=False)
    @classmethod
    def _validate_trait_efo_id(cls, v: str | None) -> str | None:
        return validate_trait_ids(v)

    # The five below read their vocabulary out of `SHARED_VOCABULARIES`, which is also what
    # `field_vocabularies` reports — so the set a tool offers an author is the same object the
    # validator rejects against, not a copy of it. A field named here must have an entry there, which
    # is why a future element-rule companion adds itself to `VCF_POINTER_COMPANIONS` *and* to this
    # list. Adding it to the map alone would mark the field with a `closed` vocabulary that nothing
    # rejects against, and `test_reference.test_declared_closed_options_are_exactly_what_is_accepted`
    # catches precisely that — it discovers enforcement by *behaviour*, so it cannot be satisfied by
    # the declaration it is checking.
    @field_validator("direction", "clin_sig", "stat_significance", "evidence_level",
                     "source_element",
                     check_fields=False)
    @classmethod
    def _validate_shared_vocabulary(cls, v: str | None, info: ValidationInfo) -> str | None:
        name = info.field_name or ""
        return check_vocab(v, SHARED_VOCABULARIES[name], name)

    @field_validator("effect_size", check_fields=False)
    @classmethod
    def _validate_effect_size(cls, v: float | None) -> float | None:
        return validate_finite(v, "effect_size")

    @field_validator("source_field", "callable_from", "quality_from", check_fields=False)
    @classmethod
    def _validate_vcf_field_pointer(cls, v: str | None, info: ValidationInfo) -> str | None:
        # Three columns point into a VCF the same way: `source_field` (where the measured quantity is,
        # on the binning tables), `callable_from` (where the callability signal is, on VariantRow) and
        # `quality_from` (which confidence field the row's `min_quality` floor is stated against).
        return validate_field_token(v, info.field_name or "source_field")

    @model_validator(mode="after")
    def _validate_pointer_companions(self) -> "AuthoredModel":
        # An element rule qualifies a pointer (RM54): it says *which* of a multi-valued field's
        # values the pointer means. With no pointer beside it there is nothing to qualify, so the
        # cell names nothing at all — the row would state a selection over an unstated field. The
        # converse is not an error: a pointer with no element rule is the ordinary case (a scalar
        # field needs no selection), and demanding one would break every module carrying a pointer
        # today (P3). Reachable only by a module authored after this release, since neither column
        # existed before it.
        for element_field, pointer_field in VCF_POINTER_COMPANIONS.items():
            if element_field not in type(self).model_fields:
                continue
            if (
                getattr(self, element_field, None) is not None
                and getattr(self, pointer_field, None) is None
            ):
                raise ValueError(
                    f"{element_field} says which element of a multi-valued VCF field to read, and "
                    f"{pointer_field} is empty — there is no field for it to select from. Set "
                    f"{pointer_field} to the field this rule applies to, or clear {element_field}."
                )
        return self

    @field_validator("genotype", check_fields=False)
    @classmethod
    def _validate_genotype(cls, v: str | None) -> str | None:
        # Optional on `PharmVariantRow`, required on `VariantRow` — pydantic enforces requiredness
        # from the annotation, so the shared grammar only has to let a genuine absence through.
        if v is None:
            return v
        # Phased (order-significant): pipe-separated, exactly two alleles, NOT sorted — phase encodes
        # which allele sits on which homolog. ROADMAP 0.3 item 5b.
        if "|" in v:
            parts = v.split("|")
            if len(parts) != 2:
                raise ValueError(
                    f"phased genotype must be two pipe-separated alleles (e.g. A|G), got: {v!r}"
                )
            for allele in parts:
                if not ALLELE_PATTERN.match(allele):
                    raise ValueError(
                        f"genotype alleles must be nucleotides, got: {allele!r} in {v!r}"
                    )
            return v
        parts = v.split("/")
        if len(parts) == 1:
            # Hemizygous single allele (non-PAR X/Y in males; homoplasmic MT). ROADMAP 0.3 item 5b.
            if not ALLELE_PATTERN.match(parts[0]):
                raise ValueError(f"genotype allele must be nucleotides, got: {v!r}")
            return v
        if len(parts) == 2:
            for allele in parts:
                if not ALLELE_PATTERN.match(allele):
                    raise ValueError(
                        f"genotype alleles must be nucleotides, got: {allele!r} in {v!r}"
                    )
            if parts != sorted(parts):
                raise ValueError(
                    f"unphased genotype alleles must be alphabetically sorted: "
                    f"expected {'/'.join(sorted(parts))!r}, got: {v!r}"
                )
            return v
        raise ValueError(
            f"genotype must be a single allele (hemizygous, e.g. A), two sorted slash-separated "
            f"alleles (A/G), or two pipe-separated phased alleles (A|G), got: {v!r}"
        )
