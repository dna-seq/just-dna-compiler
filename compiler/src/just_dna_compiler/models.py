"""Result types returned by the compiler. The compiled *manifest* itself is the
`just_dna_format.manifest.ModuleManifest` — these wrap validation/compilation outcomes."""

from pathlib import Path
from typing import Any

from just_dna_format.manifest import ModuleManifest
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of spec validation."""

    valid: bool = Field(description="Whether the spec is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
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
            "Summary stats (populated only when the spec has variants). De-facto contract keys: "
            "`variant_count` (distinct variant keys), `unique_rsids`, `gene_count`, `genes` (sorted, "
            "None filtered), `categories` (sorted, None filtered), `study_count`, `clinvar_count`, "
            "`pathogenic_count`, `benign_count`, and `module_name` (when the yaml loaded)."
        ),
    )


class ClosureResult(BaseModel):
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
            "Check records discarded because they had been attested over different authored bytes. "
            "Re-binding them would claim a check was put against rows it never saw, so they are "
            "dropped and named rather than carried across."
        ),
    )
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CompilationResult(BaseModel):
    """Result of spec compilation, including the emitted manifest."""

    success: bool = Field(description="Whether compilation succeeded")
    output_dir: Path | None = Field(default=None, description="Directory with output parquets")
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    manifest: ModuleManifest | None = Field(
        default=None, description="The manifest written next to the parquets (None on failure)"
    )
