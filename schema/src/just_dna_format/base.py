"""Shared base for every authored-DSL row model (`spec`/`binning`/`pgx`/`pgs`).

Consolidates the boilerplate that was copy-pasted across the row models into one place:

- the **reserved-namespace guard** — `extra="forbid"` plus the `reject_reserved` before-validator, so
  a reserved name fails with a specific diagnosis and any other unknown/misspelled column fails with
  the generic message (see `vocab.reject_reserved`); and
- the **field validators for the shared authored vocabulary** — `rsid`, `trait_efo_id`, `direction`,
  `clin_sig`, `stat_significance`, `evidence_level`, finite-`effect_size`, and `genotype`.

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
    Field,
    PrivateAttr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo

from just_dna_format.alleles import (
    SYMBOLIC_ALLELE_TYPES,
    UNOBSERVABLE_ALLELE,
    is_unobservable_allele,
    parse_symbolic_allele,
)
from just_dna_format.vocab import (
    ALLELE_PATTERN,
    VALID_CLIN_SIG,
    VALID_DIRECTIONS,
    VALID_EVIDENCE_LEVELS,
    VALID_SIGNIFICANCE,
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


# ── Stamped positional identity (RM43) ──────────────────────────────────────────────────────────
#: The identity columns a positional row may carry, in the order `authored_ident` records them.
#: `VariantRow._freeze_identity` has used exactly this tuple since 0.5; naming it here is what lets
#: the three 0.4-family positional models reuse the mechanism instead of growing three copies of it.
IDENTITY_FIELDS: tuple[str, ...] = ("rsid", "chrom", "start", "ref", "alts")


def stamped_identity_field(description: str) -> Any:
    """A `Field(...)` for a compiler-stamped identity column on a 0.4-family positional model.

    Three properties, and the middle one is the non-obvious one:

    * `COMPILER_MANAGED`, so `authored_field_names` drops it — no author is offered the column, no
      drafted template writes it, and `reverse_module`'s generic `_write_table_csv` never re-emits it.
    * **`exclude=True`, so it stays out of `model_dump()` and therefore out of `content_signature`.**
      A stamped value is a pure function of the authored cells, so it adds nothing to a *content*
      identity — and including it would move the signature of every already-published module carrying
      one of these tables, which is the one thing a content-dedup key may not do. `_build_table` reads
      the field off the model directly (not through `model_dump()`), so the column still reaches
      parquet. `VariantRow.variant_key`/`authored_ident` are **not** excluded and are inside
      `content_signature` today; that is a grandfathered inconsistency, not a precedent — un-excluding
      them here, or excluding them there, moves published signatures either way, so the asymmetry is
      carried until a major.
    * a fresh `FieldInfo` per call, because pydantic binds one to the model that declares it.
    """
    return Field(
        default=None,
        exclude=True,
        json_schema_extra=COMPILER_MANAGED,
        description=description,
    )


def reject_compiler_filled(data: object, fields: dict[str, Any], *, what: str) -> None:
    """Refuse an **identity** column this model has the compiler fill (RM43), with a diagnosis.

    `alts` is the only such column today: authored and required on `variants.csv`, authored and
    optional on `heteroplasmy.csv`, and **compiler-filled** on `pharm_variants.csv`/`haplotypes.csv`,
    where a pharm annotation matches a variant at `chrom:start:ref` regardless of allele. Writing it
    there by analogy with `variants.csv` is a plausible confusion rather than a typo, and before this
    guard it was silently *accepted*: `extra="forbid"` cannot see it, the value entered
    `authored_ident`, and `_write_table_csv` then dropped it — so `compile → reverse → compile` was
    not a fixed point. It failed loudly before 0.6 added the column, so a bare accept is a regression
    however sensible the input.

    Scoped to `IDENTITY_FIELDS` deliberately, which is what leaves `variant_key`/`authored_ident`
    accepted-and-overwritten: those two are *stamped* rather than filled, and `VariantRow` has
    tolerated them since 0.5 on the "authored values ignored, no foot-gun" rule. Nothing is lost by
    ignoring a stamped value; something is lost by ignoring a filled one.
    """
    if not isinstance(data, dict):
        return
    hits = sorted(
        name
        for name in data
        if name in IDENTITY_FIELDS
        and isinstance((field := fields.get(name)), FieldInfo)
        and isinstance(field.json_schema_extra, dict)
        and field.json_schema_extra.get("compiler_managed")
    )
    if not hits:
        return
    raise ValueError(
        f"{what}: {', '.join(repr(h) for h in hits)} is filled by the compiler on this table, from "
        f"the injected resolution.csv, and is not an authored column here — remove it. It IS authored "
        f"on variants.csv and heteroplasmy.csv, which is the confusion this message exists for; here "
        f"the row's identity is rsid, or chrom + start (+ ref), and the allele list is looked up."
    )


def authored_identity(row: "AuthoredModel") -> list[str]:
    """Which of `IDENTITY_FIELDS` this row's model declares *and* the author actually filled."""
    fields = type(row).model_fields
    return [name for name in IDENTITY_FIELDS if name in fields and getattr(row, name) is not None]


def stamp_identity(row: "AuthoredModel", *, keys_on_alts: bool, freeze_authored: bool) -> None:
    """Stamp `variant_key` (and, at construction, `authored_ident`) onto a positional row.

    The key is derived from the **authored subset only**, never from the row's current cells, which is
    what makes it survive the compile-time coordinate fill: once `authored_ident` is frozen, filling
    `chrom`/`start`/`ref`/`alts` cannot re-key the row however many times this runs. That is the same
    guarantee `VariantRow` gets from `_freeze_identity` never re-running on `model_copy`, arrived at
    from the other direction because these rows are filled **in place** rather than copied.

    `freeze_authored` is `True` exactly once, at construction, and authored values are overwritten
    rather than trusted — a CSV that carries a `variant_key`/`authored_ident` column of its own does
    not get to declare its own identity (`VariantRow` calls that "no foot-gun"). `with_genome_build`
    re-derives the *key* only, because the assembly changes what a coordinate means and cannot change
    what the author wrote.
    """
    if freeze_authored:
        row.authored_ident = authored_identity(row)
    authored = set(row.authored_ident or ())

    def cell(name: str) -> Any:
        return getattr(row, name, None) if name in authored else None

    # A row that names no variant at all keys as `None` — the pre-0.5 `heteroplasmy.csv` shape, where
    # the bins are about a gene. The two PGx models forbid it by validator (rsid, or chrom+start), so
    # for them this branch is unreachable and the key is always a string.
    if cell("rsid") is None and cell("start") is None:
        row.variant_key = None
        return
    row.variant_key = derive_variant_key(
        cell("rsid"),
        cell("chrom"),
        cell("start"),
        cell("ref"),
        cell("alts") if keys_on_alts else None,
        build=row.genome_build,
    )


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


def genotype_allele_ok(allele: str) -> bool:
    """Whether one member of a genotype is spellable: a nucleotide string, a symbolic allele, or `*`.

    The single place `_validate_genotype` decides what an allele *is*, so the three arms of the
    grammar (phased pair, hemizygous single, unphased pair) cannot drift apart — they did not, but
    the check was written out three times and a widening had to be applied three times with it.

    Symbolic alleles joined in 0.6 (RM5): a genotype may name one (`<DEL:1500>/A` — a heterozygous
    deletion), because that is exactly the call a consumer reading a structural VCF has in hand.
    A *lengthless* one passes here and is refused by the compiler; see `vocab.validate_allele` for
    why the split is forced rather than chosen.

    **`*` joined beside them in 0.6 (RM59), and the two arms are deliberately not one arm.** They are
    checked by different predicates against different modules of meaning, and the separation is the
    item rather than an implementation detail: `parse_symbolic_allele` answers *which variant is this,
    unspelled*, and `is_unobservable_allele` answers *whether this sample's allele could be seen at
    all* — the callability axis `requires_callable` already owns (P5). Folding `*` into
    `SYMBOLIC_ALLELE_TYPES` would give one syntax two meanings and hand `*` a length, an event and a
    place it does not have. See `alleles`' RM59 section for the full argument.

    Why the genotype column and not the allele columns: `vocab.validate_allele` (`HaplotypeRow.allele`,
    `VariantRow.effect_allele`) still refuses `*`, and must. Those columns name the allele a *rule* is
    about, and a rule about an allele nobody observed states nothing. A genotype is the one place the
    observation itself is written down, which is why it is the one place `*` belongs.
    """
    return (
        bool(ALLELE_PATTERN.match(allele))
        or parse_symbolic_allele(allele) is not None
        or is_unobservable_allele(allele)
    )


#: What `_validate_genotype` will accept, spelled once for the three messages that have to say it.
#: Names the length convention without claiming this validator enforces it — it does not (a lengthless
#: `<DEL>` loads and the compiler refuses it), and an author rejected on the *type* still needs the
#: full spelling or they earn a second rejection one command later.
#:
#: `*` is named with its meaning rather than as a bare token: an author who has just been rejected is
#: reading this to learn the grammar, and `*` is the one member whose spelling gives away nothing about
#: when to reach for it.
_GENOTYPE_ALLELE_GRAMMAR: str = (
    f"nucleotides, {UNOBSERVABLE_ALLELE!r} (VCF's allele-missing-due-to-overlapping-deletion, for a "
    f"position this sample's call could not observe), or a symbolic/structural allele whose "
    f"first-level type is one of {sorted(SYMBOLIC_ALLELE_TYPES)}, with its length inside the token "
    f"(e.g. <DEL:1500>)"
)


class AuthoredModel(BaseModel):
    """Base for authored-DSL rows: reserved-namespace guard + shared-vocabulary field validators."""

    model_config = ConfigDict(extra="forbid")

    #: Which of this model's columns hold an **allele sequence**, declared on the model itself (RM5).
    #:
    #: The compiler's symbolic-allele check reads it, and it is a `ClassVar` beside `REQUIRED_ANY_OF`
    #: for the same reason that one is: the fact belongs to the model, and a list kept in the compiler
    #: would be a second copy of a model's column names — the drift `SOURCES_FIELDNAMES` already
    #: demonstrated. Empty here, so a model that carries no allele is silent by default rather than by
    #: omission.
    #:
    #: **Sequence columns only.** `AlleleFunctionRow.allele` is a star-allele *name* (`*4`), not a
    #: sequence, and stays out — as does every column that merely *points at* a variant
    #: (`StudyRow.ref`) and every fact sidecar (`FrequencyRow`, `ResolutionRow`): a fact table is
    #: injected rather than authored, and a check that drops rows must never rewrite injected facts.
    ALLELE_COLUMNS: ClassVar[tuple[str, ...]] = ()

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

        A model that stamps an identity (`_KEY_INCLUDES_ALTS` set) re-derives its `variant_key` here,
        which is this loader's answer to the problem `_restamp_for_build` solves for `VariantRow` one
        tier up: a row is constructed from a CSV dict where `module_spec.yaml` is not in scope, so the
        key it froze at construction took `derive_variant_key`'s GRCh38 default. Doing it at the point
        the build arrives means a positional table needs no compiler-side correction pass at all.
        `VariantRow` deliberately does not join in — it leaves `_KEY_INCLUDES_ALTS` unset and keeps its
        existing restamp, which also emits the "keyed by coordinate instead" warning a GRCh37 module
        must hear.
        """
        self._genome_build = genome_build
        if type(self)._KEY_INCLUDES_ALTS is not None:
            stamp_identity(self, keys_on_alts=self._KEY_INCLUDES_ALTS, freeze_authored=False)
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

    #: Does this model stamp a positional identity, and does its key include `alts`? (RM43)
    #:
    #: `None` — the default — means "this model stamps nothing", which is every model but the three
    #: positional 0.4 kinds. `False`/`True` opt a model into `stamp_identity` and say whether `alts`
    #: participates in the key: a pharm annotation or a haplotype junction matches a variant at
    #: `chrom:start:ref` *regardless of allele* (so `False`, and `PharmVariantRow.alts` is filled as
    #: data without touching identity), while `heteroplasmy.csv` keys **with** `alts` because its own
    #: key always did and moving it would re-key every published mtDNA module.
    #:
    #: A tri-state `ClassVar` rather than two flags or a marker per field, for `MeasureBinRow`'s
    #: reason: the fact is a property of the *model*, and "stamps nothing" has to be distinguishable
    #: from "stamps a key without alts" — which a bool cannot do.
    _KEY_INCLUDES_ALTS: ClassVar[bool | None] = None

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
        # An identity column this model has the *compiler* fill (RM43) reads as authorable, because it
        # is genuinely authored on the tables next door. Same guard shape, same reason.
        reject_compiler_filled(data, cls.model_fields, what=f"{cls.__name__} row")
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

    # The four below read their vocabulary out of `SHARED_VOCABULARIES`, which is also what
    # `field_vocabularies` reports — so the set a tool offers an author is the same object the
    # validator rejects against, not a copy of it.
    @field_validator("direction", "clin_sig", "stat_significance", "evidence_level",
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
                if not genotype_allele_ok(allele):
                    raise ValueError(
                        f"genotype alleles must be {_GENOTYPE_ALLELE_GRAMMAR}, got: "
                        f"{allele!r} in {v!r}"
                    )
            return v
        parts = v.split("/")
        if len(parts) == 1:
            # Hemizygous single allele (non-PAR X/Y in males; homoplasmic MT). ROADMAP 0.3 item 5b.
            if not genotype_allele_ok(parts[0]):
                raise ValueError(
                    f"genotype allele must be {_GENOTYPE_ALLELE_GRAMMAR}, got: {v!r}"
                )
            return v
        if len(parts) == 2:
            for allele in parts:
                if not genotype_allele_ok(allele):
                    raise ValueError(
                        f"genotype alleles must be {_GENOTYPE_ALLELE_GRAMMAR}, got: "
                        f"{allele!r} in {v!r}"
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

    @model_validator(mode="after")
    def _freeze_stamped_identity(self) -> "AuthoredModel":
        """Stamp the positional identity at construction, for the models that declare one (RM43).

        A no-op for every model that leaves `_KEY_INCLUDES_ALTS` unset, which is all of them but the
        three positional 0.4 kinds — and for `VariantRow`, which keeps its own `_freeze_identity`.
        Like that one it runs at construction, so `model_copy` does not re-run it and the frozen key
        survives whatever resolution fills in afterwards.
        """
        if type(self)._KEY_INCLUDES_ALTS is not None:
            stamp_identity(self, keys_on_alts=self._KEY_INCLUDES_ALTS, freeze_authored=True)
        return self
