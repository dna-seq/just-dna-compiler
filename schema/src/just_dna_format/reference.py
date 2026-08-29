"""
A machine/LLM-facing authoring reference, **generated from the live models** (RM8).

Consumers (MCP servers, agents, docs) tend to hard-code a prose summary of the DSL — its columns,
vocabularies, genome build — which then **drifts** from the real schema (just-dna-agents' MCP
`get_spec_format` predated the 0.3 columns, for example). `authoring_reference()` derives that summary
by introspecting the Pydantic models and vocabularies, so it is a **single source of truth that cannot
drift**: every consumer renders the current field set. For a full JSON Schema, call
`json_schemas()` (Pydantic's `model_json_schema()` per model).

Dependency-light: this is a top-level aggregator over `spec`/`binning`/`pgx`/`pgs`/`manifest`/`vocab`;
nothing in the package imports it, so it introduces no cycle.
"""

from typing import Any

from pydantic import BaseModel

from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import authored_field_names, field_category, field_vocabularies
from just_dna_format.binning import (
    ActivityPhenotypeRow,
    CopyNumberRow,
    HeteroplasmyRow,
    MeasureBinRow,
    RepeatAlleleRow,
)
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import (
    RECOMMENDED_COLORS,
    RECOMMENDED_ICONS,
    SCHEMA_VERSION,
    Contribution,
    Display,
    GenePanelSpec,
    VerificationRecord,
    Weighting,
)
from just_dna_format.normalize import IDENTITY_AUTHORITY_KEYS, IDENTITY_AUTHORITY_REASONS
from just_dna_format.overrides import OverrideRow
from just_dna_format.pgs import (
    PgsRow,
)
from just_dna_format.pgx import (
    AlleleFunctionRow,
    DiplotypeRow,
    HaplotypeRow,
    PharmVariantRow,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import (
    Defaults,
    ModuleInfo,
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
)
from just_dna_format.vocab import (
    RESERVED_NAMES_0_4,
)

# The authored surface, grouped by role. Order is the reading order for an author/agent.
_MODULE_MODELS: dict[str, type[BaseModel]] = {
    "ModuleSpecConfig": ModuleSpecConfig,
    "ModuleInfo": ModuleInfo,
    "Defaults": Defaults,
    "GenePanelSpec": GenePanelSpec,
    "Display": Display,
    "Contribution": Contribution,
    "Weighting": Weighting,
}
_VARIANT_MODELS: dict[str, type[BaseModel]] = {
    "VariantRow": VariantRow,
    "StudyRow": StudyRow,
}
_BINNING_MODELS: dict[str, type[BaseModel]] = {
    "MeasureBinRow": MeasureBinRow,
    "ActivityPhenotypeRow": ActivityPhenotypeRow,
    "CopyNumberRow": CopyNumberRow,
    "RepeatAlleleRow": RepeatAlleleRow,
    "HeteroplasmyRow": HeteroplasmyRow,
}
_PGX_MODELS: dict[str, type[BaseModel]] = {
    "HaplotypeRow": HaplotypeRow,
    "AlleleFunctionRow": AlleleFunctionRow,
    "DiplotypeRow": DiplotypeRow,
    "PharmVariantRow": PharmVariantRow,
}
_PGS_MODELS: dict[str, type[BaseModel]] = {"PgsRow": PgsRow}
# `sources.csv` is the one fact sidecar a HUMAN writes, so it belongs on the authoring surface even
# though its row model is not an `AuthoredModel` (S21). Every other sidecar is produced by an
# enricher pass, where omission costs an author nothing; this one the schema explicitly tells them to
# hand-write — `MISPLACED_COLUMN_REASONS['source']` ends "to declare a source you read by hand, add a
# ROW to sources.csv" — and it is the only table the compile licence gate reads. Left out, an author
# reconstructing it from a filename has to guess that `share_alike`/`commercial_use`/`redistribution`
# are three orthogonal axes where `None` means unknown rather than false, which is not a guessable
# shape. The consumer who reported it got there by reading `SourceRow.model_fields` — reading our
# source to learn our schema, which is the thing this module exists to make unnecessary.
#
# `GeneValidityRow`/`ClinicalAssertionRow` join it in 0.6 for a **different** reason, and the two
# reasons should not be conflated. Nobody hand-writes either — they stay out of `draft.DRAFTABLE`
# with the other machine-written sidecars — but each introduces a *new closed vocabulary*
# (`gene_validity`, `inheritance_mode`), and the only guard that discovers an undeclared one does so
# by behaviour while iterating this registry. A vocabulary the guard cannot see is precisely the S21
# hole, so a model carrying a new one belongs here whoever writes its rows.
#
# **The remaining five joined them in 0.6.1, and the gap they left is the whole of RM96.** This comment
# used to end by naming `FrequencyRow`, `GeneMetricsRow` and `LiteratureRow` as "still outside … a real
# gap, and a wider change than this one" — correctly, and then nothing happened for a release, which is
# how a note about a gap becomes a record of one. Two things it did not say. `ResolutionRow` was
# outside too, and it is the *canonical* holder of `VALID_RESOLUTION_STATUS` — the vocabulary three of
# the others point at by name. And `GwasEffectRow` (RM90) landed outside a day before the audit that
# found this, so the registry was already falling behind faster than it was being caught up.
#
# What the gap cost, measured rather than argued: `GeneMetricsRow.status` names the `ResolutionRow`
# vocabulary in its own description and enforced nothing at all, so `status="totally-made-up"`
# validated. Every sibling fact table enforces its status. `@registry-completeness` from the other
# side — a registry-iterating guard is only as complete as its registry, and the audit that would have
# caught this could not see the model. The price of admitting them is real and was accepted knowingly:
# `authoring_reference()`, `describe`, `requirements` and `json_schemas()` all render five more models,
# which is additive (Principle 3) and changes what a consumer reads. That is the trade — a wider
# printed reference in exchange for guards that cannot miss a model again.
#
# `VerificationRecord` (RM45) is here on exactly that second argument — it carries `verification_check`
# and `verification_skip`, two closed vocabularies whose whole purpose is to be the machine keys a
# consumer reads instead of prose, so a guard that could not see them would be the S21 hole again. One
# thing it does NOT share with the other two: a human must never write one at all. An attestation a
# human assembled is the forgery the binding hash exists to catch, so `authoring_reference()`
# describing its shape is a description of what a consumer will read, never an invitation to author it.
_FACT_MODELS: dict[str, type[BaseModel]] = {
    "SourceRow": SourceRow,
    "ResolutionRow": ResolutionRow,
    "FrequencyRow": FrequencyRow,
    "GeneMetricsRow": GeneMetricsRow,
    "LiteratureRow": LiteratureRow,
    "GeneValidityRow": GeneValidityRow,
    "ClinicalAssertionRow": ClinicalAssertionRow,
    "GwasEffectRow": GwasEffectRow,
    # The concordance record (0.7, RM130). Two models, one table pair, and they are here on the
    # `GeneValidityRow`/`ClinicalAssertionRow` argument rather than the `SourceRow` one: nobody
    # hand-writes a row of either, but between them they introduce three new closed vocabularies
    # (`authority_concordance`, `authored_position`, `authority_call_status`), and the only guard
    # that discovers an undeclared one walks this registry.
    "ClinSigConcordanceRow": ClinSigConcordanceRow,
    "ClinSigAuthorityCallRow": ClinSigAuthorityCallRow,
    "VerificationRecord": VerificationRecord,
}

# `overrides.csv` is a **third** category and gets its own group rather than joining either
# neighbour, because it belongs to neither and blurring the line is what the 0.5 rework spent a
# release undoing. It is not an annotation table like `_VARIANT_MODELS`/`_PGX_MODELS`: it asserts
# nothing about a genotype, it is not a *lead* table, and a directory carrying only this file is not
# a module. It is not a `_FACT_MODELS` sidecar either: a human writes every row of it, so it carries
# `AuthoredModel`'s reserved-namespace guard, it is inside `content_signature`, and it is byte-hashed
# into `manifest.inputs` rather than fact-hashed.
#
# What it *is* is the overlay that makes the seven fact tables pure build products (RM124), so a
# reader of the authoring reference meets it beside them and not inside them.
_OVERLAY_MODELS: dict[str, type[BaseModel]] = {"OverrideRow": OverrideRow}

_ALL_MODELS: dict[str, type[BaseModel]] = {
    **_MODULE_MODELS,
    **_VARIANT_MODELS,
    **_BINNING_MODELS,
    **_PGX_MODELS,
    **_PGS_MODELS,
    **_FACT_MODELS,
    **_OVERLAY_MODELS,
}


def _type_name(annotation: Any) -> str:
    """A readable type label (`Optional[str]`, `list[str]`, `int`) from a field annotation."""
    return (
        str(annotation)
        .replace("typing.", "")
        .replace("<class '", "")
        .replace("'>", "")
    )


def _collect_vocabularies(*, closed: bool) -> dict[str, list[str]]:
    """`{vocabulary name: sorted members}` over every marked field of every authored model.

    Keyed by **vocabulary name**, not by field name, and that is load-bearing: `PgsRow`'s
    `training_ancestry` (1000G superpopulations) and gnomAD's population list are two different
    vocabularies that `vocab.py` forbids merging, and a `measure_kind` pinned to one value on a
    binning subclass is not the open choice on the base. Names are distinct, so a collision would be
    a real modelling error rather than a silent merge — `test_reference.py` asserts there is none."""
    collected: dict[str, list[str]] = {}
    for model in _ALL_MODELS.values():
        for marker in field_vocabularies(model).values():
            if marker["closed"] is closed:
                collected[marker["name"]] = marker["options"]
    return collected


def _collect_vocabulary_notes() -> dict[str, dict[str, str]]:
    """`{vocabulary name: {member: prose}}` for every marked field that carries per-member prose.

    Read off the markers, exactly like `_collect_vocabularies` above, rather than composed here from
    the one relation that has notes today. The comprehension it replaces named `ELEMENT_RULE_MEANINGS`
    and `VCF_POINTER_COMPANIONS` directly, which meant a vocabulary in `pgx`/`binning`/`spec` could
    never contribute prose (this module can import those, but the marker is the only channel a *tool*
    reads) and that a second surface wanting the same prose had to repeat the composition. It did:
    `just_dna_compiler.hints.describe_table` had no notes at all, so the per-table command an author
    actually runs listed `source_element`'s members without their meanings.

    Outer keys sorted, members left in the declaring constant's own order — the reading order it was
    written in, and deterministic for the same reason `_collect_vocabularies` is."""
    collected: dict[str, dict[str, str]] = {}
    for model in _ALL_MODELS.values():
        for marker in field_vocabularies(model).values():
            notes = marker.get("notes")
            if notes:
                collected[marker["name"]] = dict(notes)
    return {name: collected[name] for name in sorted(collected)}


def _describe_model(model: type[BaseModel]) -> list[dict[str, Any]]:
    """Field list for one model, in declaration order — `{name, type, required, description}`.

    Compiler-managed fields are skipped — materialized into the artifact, but not authored, so
    listing them here would read as columns an author writes. (The full machine `json_schemas()`
    still lists them: it is the honest, complete materialized shape.)

    The set comes from the fields' own `COMPILER_MANAGED` marker via `base.authored_field_names`,
    not from a name list kept here. It *was* a name list, and it drifted exactly as you would expect:
    it named `variant_key` and never learned about `authored_ident` when 0.5 added it, so this
    reference — whose entire job is not to drift — offered an author a `list[str]` column the
    compiler stamps. A bare name set is also model-blind, and `FrequencyRow.variant_key` is a
    genuinely authored, required column that such a set would have hidden."""
    fields = []
    authored = set(authored_field_names(model))
    vocabularies = field_vocabularies(model)
    for name, field in model.model_fields.items():
        if name not in authored:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "type": _type_name(field.annotation),
            "required": field.is_required(),
            # `required` alone is pydantic's two-way answer and it is a trap for an authoring tool.
            # `MeasureBinRow.measure_kind` and `unresolved` have defaults, so `is_required()` is
            # False — but `_load_csv_rows` turns an empty cell into `None` and keeps the key, so the
            # model gets `None` instead of its default and fails on type. A consumer that filled only
            # the `required` columns produced a file the compiler refused, naming a fourth column.
            # `just_dna_compiler.draft` was fixed to the three-way split and this surface was not,
            # which is exactly the drift this whole module exists to prevent — so both now read
            # `base.field_category`. `required` is kept beside it: removing a published key would
            # break consumers, and it is not *wrong*, only insufficient on its own.
            "category": field_category(model, name),
            "description": field.description,
        }
        # The allowed values ride on the field, so a tool building a picker reads them here instead
        # of matching a field name against the top-level vocabulary block and hoping the two agree.
        marker = vocabularies.get(name)
        if marker is not None:
            entry["vocabulary"] = marker["name"]
            entry["options"] = marker["options"]
            entry["closed"] = marker["closed"]
            # Per-member prose where the member name cannot carry the whole rule, beside the members
            # it explains rather than only in the top-level `vocabulary_notes` block: a tool rendering
            # one column's picker has the marker in hand and should not need a second lookup.
            if marker.get("notes"):
                entry["notes"] = dict(marker["notes"])
        fields.append(entry)
    return fields


def authoring_reference() -> dict[str, Any]:
    """A drift-proof, JSON-serialisable description of the authored DSL — models (field lists),
    vocabularies, reserved names, and the recommended display palette — generated from the live
    schema. Consumers render this instead of a hand-maintained prose summary (RM8)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "genome_build_default": ModuleSpecConfig.model_fields["genome_build"].default,
        "models": {name: _describe_model(model) for name, model in _ALL_MODELS.items()},
        # Both blocks are generated from the fields' own `vocabulary` markers (`base.py`), not listed
        # here. The list they replace drifted twice: it never learned about `recommendation_strength`
        # or `phenotype_category` when 0.5 added them, and it filed `actionability` under
        # `open_recommended` although `VariantRow` rejects a non-member — a drift in *closedness*,
        # which is why the marker carries that flag and why `actionability` now appears below.
        "vocabularies": _collect_vocabularies(closed=True),
        "open_recommended": _collect_vocabularies(closed=False),
        # Per-member prose, for the vocabularies where the member *name* cannot carry the whole rule.
        # The element rules (RM54) are the case that forced it: on a `Number=R` VCF field the
        # reference is element zero, so "the larger of the two" has two answers, and a vocabulary that
        # is silent about which one it means repeats the defect it was added to fix one level down.
        # Keyed by the same names as `vocabularies` above, so a consumer that found a member there
        # can look up what it means without a second lookup table of its own.
        #
        # Derived from the fields' own markers, like both blocks above it. It was a comprehension over
        # `VCF_POINTER_COMPANIONS` naming `ELEMENT_RULE_MEANINGS` in place — correct, and the only
        # channel that composition could reach was this block, so the prose never got to the per-table
        # `describe` an author filling one table runs (D1-4).
        "vocabulary_notes": _collect_vocabulary_notes(),
        # Alternative identity-column sets, any ONE of which satisfies a row's requirement. Field-level
        # `required` cannot express "rsid OR chrom+start" — that rule is a model validator — so a tool
        # listing required columns told an author a `variants.csv` row needed no identifier at all.
        "required_any_of": {
            name: [sorted(group) for group in model.REQUIRED_ANY_OF]
            for name, model in _ALL_MODELS.items()
            if getattr(model, "REQUIRED_ANY_OF", ())
        },
        "reserved_names": sorted(RESERVED_NAMES_0_4),
        # Field-ownership boundary for the `module:` block (S2): keys the format knows about but that
        # a *publishing registry* stamps, so an author must omit them. Distinct from `reserved_names`
        # (future module columns) — these will never be authored. A consumer strips them before
        # validation via `normalize.strip_authority_keys`; `module.version` is NOT here (it is a
        # genuine advisory authored field).
        "registry_stamped_keys": {
            key: IDENTITY_AUTHORITY_REASONS[key] for key in sorted(IDENTITY_AUTHORITY_KEYS)
        },
        "recommended_palette": {"colors": RECOMMENDED_COLORS, "icons": RECOMMENDED_ICONS},
    }


def json_schemas() -> dict[str, Any]:
    """Full JSON Schema per model (Pydantic `model_json_schema()`), for consumers that want the
    machine-validatable form rather than the compact `authoring_reference()` summary."""
    return {name: model.model_json_schema() for name, model in _ALL_MODELS.items()}
