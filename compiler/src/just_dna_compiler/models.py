"""Result types returned by the compiler. The compiled *manifest* itself is the
`just_dna_format.manifest.ModuleManifest` — these wrap validation/compilation outcomes."""

from pathlib import Path
from typing import Any

from just_dna_format.findings import classify
from just_dna_format.manifest import ModuleManifest
from pydantic import BaseModel, Field, model_validator


class _Findings(BaseModel):
    """The two derived halves of a warnings channel, filled from `warnings` at construction (RM131).

    Every result type here carries `warnings: list[str]` and three of them are built at 30-odd call
    sites between them, so the derivation lives in a `mode="before"` validator rather than at each
    site: a caller cannot forget it, and there is no failure path where a result comes back with a
    populated channel and an empty summary.

    `mode="before"` is load-bearing and not a style choice. Pydantic coerces a `str` subclass to a
    plain `str` on its way into a `list[str]` field, so a validator running any later would be looking
    at messages that no longer know their own code. Before it, the raw `Finding` objects are still
    there.

    A caller passing `carried`/`warnings_summary` explicitly is left alone, which is what lets a
    result be rebuilt from a dump of itself.
    """

    warnings: list[str] = Field(default_factory=list, description="Non-fatal findings, in full")
    carried: list[str] = Field(
        default_factory=list,
        description=(
            "The subset of `warnings` no edit to the spec directory can clear — a limit of this tier "
            "or a fact of a source. Subtract it from `warnings` for the findings still worth acting "
            "on. Empty means every finding here is actionable, which is an answer rather than a gap."
        ),
    )
    warnings_summary: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "`warnings` counted by kind — keys from VALID_WARNING_CODES, values summing to "
            "`len(warnings)` so the digest accounts for the whole channel."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_from_warnings(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not data.get("warnings"):
            return data
        if "carried" in data or "warnings_summary" in data:
            return data
        carried, summary = classify(data["warnings"])
        return {**data, "carried": carried, "warnings_summary": summary}


class ValidationResult(_Findings):
    """Result of spec validation."""

    valid: bool = Field(description="Whether the spec is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    info: list[str] = Field(
        default_factory=list,
        description=(
            "Informational notes — neither errors nor warnings (nothing is wrong). Used to surface "
            "accepted-but-noteworthy input, e.g. non-reserved `flags` tags (the flags vocabulary is "
            "open, so an unknown tag is INFO, not a warning). See ROADMAP 0.3 item 4."
        ),
    )
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Summary stats for the module. Contract keys: `variant_count` (distinct variant keys), "
            "`unique_rsids`, `gene_count`, `genes` (sorted, None filtered), `categories` (sorted, "
            "None filtered), `study_count`, `clinvar_count`, `pathogenic_count`, `benign_count`, "
            "`module_name` (when the yaml loaded), `table_rows` (**every** authored table kind the "
            "module carries → its row count) and `row_count` (their sum: the family-independent "
            "size of the module).\n\n"
            "**Read `table_rows`/`row_count` rather than `variant_count` when you want *how big is "
            "this module*.** The scalar counters above them describe `variants.csv` and nothing "
            "else, so a module led by `pharm_variants.csv`, `diplotypes.csv` or any other kind "
            "reports `variant_count: 0` and `unique_rsids: 0` however many rows it has — 0 there "
            "means *no variants.csv rows*, never *no data* (S72). `gene_count`/`genes` are the "
            "exception and do describe the whole module, since RM121."
        ),
    )


class ClosureResult(_Findings):
    """Result of closing a module's authoring phase (RM73).

    Closing is refused rather than reported-and-done when the spec does not validate: the phase
    boundary means *this authored set is finished*, and a set the compiler will not accept is not
    finished. Warnings do not refuse — an unresolved rsID or an ungrounded bin is a legitimate state
    to declare done, and treating every warning as a blocker would make closure impossible on modules
    whose findings no authored edit can clear.
    """

    closed: bool = Field(description="Whether the closure was written")
    path: Path | None = Field(
        default=None, description="The `verification.json` written (None when nothing was closed)"
    )
    module_hash: str | None = Field(
        default=None, description="The authored bytes the closure was bound to"
    )
    signed: bool = Field(default=False, description="Whether the closure carries an Ed25519 signature")
    dropped_checks: list[str] = Field(
        default_factory=list,
        description=(
            "Check records discarded because they had been attested over different authored bytes, or "
            "because the attestation carrying them no longer holds. Re-binding them would claim a "
            "check was put against rows it never saw, so they are dropped and named rather than "
            "carried across."
        ),
    )
    errors: list[str] = Field(default_factory=list)


class CompilationResult(_Findings):
    """Result of spec compilation, including the emitted manifest."""

    success: bool = Field(description="Whether compilation succeeded")
    output_dir: Path | None = Field(default=None, description="Directory with output parquets")
    errors: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    manifest: ModuleManifest | None = Field(
        default=None, description="The manifest written next to the parquets (None on failure)"
    )
