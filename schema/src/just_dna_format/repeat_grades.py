"""STRchive's evidence for a repeat locus–disease association (RM294, 0.10).

The enricher writes one fact per authored (gene, repeat_unit), catalogue record and evidence word.
Several records can match the same repeat. A matched record with no grade has an empty cell.
STRchive has published Definitive, Strong, Moderate, Limited, Disputed, Refuted and Provisional.
Provisional means not yet curated. The vocabulary is open and the source's spelling travels verbatim.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.binning import RepeatAlleleRow
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.spelling import gene_key
from just_dna_format.vocab import VALID_RESOLUTION_STATUS, check_vocab


class RepeatGradeRow(BaseModel):
    """One source grade of one repeat–disease association, joined on the module's motif spelling."""

    model_config = ConfigDict(extra="forbid")
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (*RepeatAlleleRow._KEY_FIELDS, "locus_id", "grade")

    gene: str = Field(
        min_length=1, description="Gene as written in repeat_alleles.csv", json_schema_extra=since("0.10.0")
    )
    repeat_unit: str = Field(
        min_length=1,
        description="Repeat motif as written in repeat_alleles.csv",
        json_schema_extra=since("0.10.0"),
    )
    locus_id: str = Field(
        min_length=1,
        description="STRchive's record ID for the association",
        json_schema_extra=since("0.10.0"),
    )
    grade: str | None = Field(
        default=None,
        description="One verbatim evidence word, empty when the record states none",
        json_schema_extra=since("0.10.0"),
    )
    disease: str | None = Field(
        default=None, description="STRchive's descriptive disease label", json_schema_extra=since("0.10.0")
    )
    dataset: str | None = Field(
        default=None,
        description="Snapshot release, empty for an unlabelled catalogue",
        json_schema_extra=since("0.10.0"),
    )
    source: str | None = Field(
        default=None,
        description="Licensed data source, joining sources.csv.source",
        json_schema_extra=since("0.10.0"),
    )
    status: str | None = Field(
        default=None,
        description="Lookup outcome",
        json_schema_extra={**vocabulary("resolution_status", VALID_RESOLUTION_STATUS), **since("0.10.0")},
    )
    fetched_at: str | None = Field(
        default=None, description="UTC time the row was fetched", json_schema_extra=since("0.10.0")
    )

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        return check_vocab(value, VALID_RESOLUTION_STATUS, "status")

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_timestamp(cls, value: object) -> str | None:
        return normalize_utc_timestamp(None if value is None else str(value))


# Outside the fact hash, `disease` labels the record and `source`, `status` and `fetched_at`
# describe how it reached the module. The release is part of the claim.
REPEAT_GRADE_FACT_FIELDS: tuple[str, ...] = (*RepeatGradeRow._KEY_FIELDS, "dataset")


def repeat_key(row: RepeatAlleleRow | RepeatGradeRow) -> tuple[str, str]:
    """The authored repeat identity shared by a grade and every band it describes."""
    return gene_key(row.gene), row.repeat_unit
