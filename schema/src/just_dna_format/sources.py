"""The data-source licensing table (0.5).

`sources.csv` is the fourth derived-fact sidecar, and the second not keyed on a variant. A row
records **what a source is, and on what terms it was used** — one row per (source, layer). Filled by
`just-dna-enricher` (the only tier that fetches, and therefore the only tier that knows), consumed
and hashed by the compiler, never fetched by it.

**Why this exists.** The pharmacogenomics sources are all copyleft, and they differ in ways that
decide what a module may be used for: ClinPGx, CPIC and PharmVar are each CC BY-SA 4.0 *plus* a
contractual clause barring sale, while Ensembl and dbSNP are unrestricted. That obligation attaches
when the derivative work is *made* — at compile — and nothing in the artifact recorded it. A consumer
holding a compiled module could not tell whether it carried a ShareAlike obligation, and the
marketplace could not filter on one.

**Why it is data and not a table in the compiler.** A hardcoded `{"clinpgx": "CC-BY-SA-4.0", …}` map
in `just-dna-compiler` would give that tier a source convention, which Principle 2 removed from it in
0.5, and would be an un-injected reference — the same category as holding a ClinVar snapshot. It
would also be permanently wrong: `api.pharmgkb.org` was retired mid-0.5 and CPIC's licence URL moved
in the same period. So the licence travels as data, read by the enricher from the bytes it actually
downloaded (ClinPGx ships a `LICENSE.txt` inside each archive) and pinned by `license_sha256`, which
makes the recorded terms provably contemporaneous with the recorded data.

**Why a fact table rather than a column on `ResolutionRow`.** `_write_resolution_csv` rebuilds that
table from `weights.parquet`, which by design carries no provenance at all, with a hardcoded field
list and `source` reset to `"reversed"`. A licence column there would be wiped on every
`compile → reverse → compile` cycle and could never be recovered — the same structural reason
`rsid_alternates` is unrecoverable. As its own fact table it round-trips for free, because
`_write_table_csv` derives its columns from `model_fields`.

**Tri-state booleans are load-bearing.** `share_alike` and `commercial_use` are `Optional[bool]`, and
`None` means *unknown*, never *false*. A source whose terms could not be established has not been
shown to permit anything, and rendering that as "does not forbid" is the single most dangerous
simplification available here. `LiteratureRow.quotes_found` carries the same null-is-not-zero
contract for the same reason.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.vocab import (
    VALID_DECLARED_USE,
    VALID_SOURCE_LAYERS,
    check_vocab,
)

# Fact columns feeding `integrity.source_signature`.
#
# **`source` is IN the fact set here, and that inverts the other tables.** On `ResolutionRow`/
# `FrequencyRow`/`GeneMetricsRow`/`LiteratureRow`, `source` is *provenance* — which link happened to
# answer — and is excluded so a human-filled and a machine-filled table with identical facts hash
# equal. Here the source **is the subject** of the row: "ClinPGx, at the annotation layer, is CC BY-SA
# and forbids sale" is the fact. Drop it and the row loses its key. A reader who has internalized the
# other three tables will read this inclusion as a bug; it is not.
#
# `fetched_at` stays out, exactly as everywhere else — when the terms were read is producer noise, not
# a fact about the module.
SOURCE_FACT_FIELDS: tuple[str, ...] = (
    "source",
    "layer",
    "license",
    "license_url",
    "license_sha256",
    "attribution",
    "notice",
    "share_alike",
    "commercial_use",
    "declared_use",
    "dataset",
)


class SourceRow(BaseModel):
    """One data source, at one layer of the module, with the terms it was used under.

    Standalone (not an `AuthoredModel`) for the same reason `ResolutionRow`/`FrequencyRow`/
    `GeneMetricsRow`/`LiteratureRow` are — a machine-produced reference fact rather than an authored
    annotation — with `extra="forbid"` so a typo'd column is caught rather than silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    # ── identity: which source, contributing to which layer ──
    source: str = Field(
        description=(
            "The source identifier, joining to the open `source` column on the other fact tables "
            "(e.g. 'clinpgx', 'cpic', 'pharmvar', 'ensembl', 'gnomad'). Open, like every source "
            "column — a closed vocabulary here would have to be revised every time a link is added."
        )
    )
    layer: str = Field(
        description=(
            "Which layer this source contributed to (VALID_SOURCE_LAYERS). Only 'annotation' — the "
            "module's own authored tables — carries a derivative-work obligation; the fact sidecars "
            "report facts, not expression."
        )
    )

    # ── the terms ──
    license: Optional[str] = Field(
        default=None,
        description=(
            "Licence identifier or name, e.g. 'CC-BY-SA-4.0'. Deliberately an open string rather "
            "than a closed SPDX vocabulary: SPDX evolves, and several of these sources are an SPDX "
            "licence PLUS a bespoke clause, which no single identifier expresses."
        ),
    )
    license_url: Optional[str] = Field(
        default=None, description="Where the terms were read from"
    )
    license_sha256: Optional[str] = Field(
        default=None,
        description=(
            "sha256: over the licence text as read, pinning the terms to the same moment as the "
            "data. Re-enriching recomputes it, so an upstream policy change becomes a finding "
            "rather than a silent pass."
        ),
    )
    attribution: Optional[str] = Field(
        default=None,
        description="The credit line the licence requires — one lookup, not a reconstruction",
    )
    notice: Optional[str] = Field(
        default=None,
        description=(
            "Any use restriction the licence text states that is not captured by the flags below "
            "(e.g. PharmVar's 'not intended for direct diagnostic use or medical decision-making'). "
            "Carried with the data because that is where it is needed."
        ),
    )

    # ── the two orthogonal permissions, tri-state ──
    share_alike: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the licence imposes a ShareAlike/copyleft obligation on derivatives. "
            "None means UNKNOWN, never false."
        ),
    )
    commercial_use: Optional[bool] = Field(
        default=None,
        description=(
            "Whether commercial use/sale is permitted. Orthogonal to `share_alike` — CC BY-SA, "
            "CC BY-NC and CC BY-NC-SA are three different combinations. None means UNKNOWN and must "
            "never be rendered as false: a source whose terms could not be established has not been "
            "shown to permit anything."
        ),
    )

    # ── what the acquirer declared ──
    declared_use: Optional[str] = Field(
        default=None,
        description=(
            "The use declared when the data was fetched (VALID_DECLARED_USE). A claim about the "
            "user, not about the licence — which is why it is a separate axis from the two flags."
        ),
    )

    # ── provenance ──
    dataset: Optional[str] = Field(
        default=None,
        description="Which release the data came from, e.g. 'clinpgx_2026-07-05'",
    )
    fetched_at: Optional[str] = Field(
        default=None, description="ISO-8601 UTC timestamp; EXCLUDED from the fact set"
    )

    @field_validator("layer")
    @classmethod
    def _validate_layer(cls, v: str) -> str:
        checked = check_vocab(v, VALID_SOURCE_LAYERS, "layer")
        if checked is None:
            raise ValueError("layer is required")
        return checked

    @field_validator("declared_use")
    @classmethod
    def _validate_declared_use(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_DECLARED_USE, "declared_use")


def taints_commercial_use(row: SourceRow) -> bool:
    """Whether this row alone makes the module non-sellable.

    Two conditions, both required. The source must actually forbid sale (`commercial_use is False` —
    an *unknown* does not taint, it warns, because "we could not read the terms" is not a finding
    that they forbid anything). And it must sit at the **`annotation`** layer, where expression is
    embedded; a source consulted only for a coordinate contributed a fact that Ensembl reports
    identically, and marking that as viral is the false-positive this predicate exists to prevent.

    Shared so the compiler's gate and the manifest summary cannot drift apart.
    """
    return row.commercial_use is False and row.layer == "annotation"
