"""The computed LD pair behind a study measured on a proxy (0.8, RM331).

`ld_pairs.csv` is a derived-fact sidecar filled by `just-dna-enricher ld-pairs`. An author writes only
`StudyRow.proxy_rsid`, the variant a study measured in place of the row's lead: r² has no meaning without
the population it was computed in, so r² and its population are a **pair**, and the pair is computed from a
reference panel rather than typed (the maintainer's cut, 2026-11-04). One row per
`(proxy_rsid, variant_key, ld_population)`.

**The population is the reference's name for its panel, not the study's code.** `1000GENOMES:phase_3:EUR`
is what Ensembl computed r² in; the study's `ancestry` is `EUR`. Keeping the panel's own spelling says
which reference the number is from without a second column, and leaves a different panel (another
release's, another reference's) a different key rather than the same word meaning two things.

**Withheld is a status, never a zero.** Ensembl answers `200 []` both for a pair on two chromosomes and
for a pair whose r² falls under an internal floor, and lowering its `r2` parameter brings no row back
(docs/probes/LANES_0_8.md §2.4). That answer is `not_reported`, with `r2` empty. A study naming several
superpopulations, or none, gets its row too, with the reason and no population: the lookup never picks a
panel for it.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from just_dna_format.base import since, vocabulary
from just_dna_format.normalize import normalize_utc_timestamp
from just_dna_format.vocab import VALID_LD_PAIR_STATUS, check_vocab, validate_finite

#: The member a row carries when the reference gave a number.
LD_RESOLVED = "resolved"

#: The members written without asking the reference: the study row leaves no single panel to ask in.
LD_POPULATION_WITHHELD: frozenset[str] = frozenset({"ancestry_mixed", "ancestry_unstated"})

# Fact columns feeding `integrity.ld_pair_signature`: everything but the provenance columns.
# `answered_rsid` is outside on `consequences.py`'s reasoning for `gene`: it is the reference's current
# label for the proxy, renamed by a dbSNP merge without the number moving. `dataset` is inside: r² is
# recomputed from each release's genotypes, so two releases' values are two facts.
LD_PAIR_FACT_FIELDS: tuple[str, ...] = (
    "proxy_rsid",
    "variant_key",
    "ld_population",
    "status",
    "r2",
    "d_prime",
    "dataset",
)


class LdPairRow(BaseModel):
    """One (proxy, lead, panel): r² and D′ between them, or the reason they are withheld."""

    #: A study row's pair in one panel. `ld_population` is null on a withheld-for-ancestry row, so one
    #: such row stands for the pair; a single-ancestry study of the same pair is a second row.
    _KEY_FIELDS: ClassVar[tuple[str, ...]] = ("proxy_rsid", "variant_key", "ld_population")

    model_config = ConfigDict(extra="forbid")

    # ── identity ──
    proxy_rsid: str = Field(
        json_schema_extra=since("0.8.0"),
        description="The variant the study measured, as `studies.csv.proxy_rsid` spells it.",
    )
    variant_key: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The study row's lead, keyed as `StudyRow.variant_key` keys it: the rsID, or `chrom:start:ref` "
            "for a coordinate-authored lead. For an rsID lead that is also `weights.parquet.variant_key`."
        ),
    )
    ld_population: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The reference panel r² was computed in, as the reference names it: "
            "`1000GENOMES:phase_3:<CODE>`, the CODE being the study's one `ancestry`. Null when the "
            "study states several superpopulations or none, which `status` says."
        ),
    )

    # ── the pair ──
    status: str = Field(
        json_schema_extra={**vocabulary("ld_pair_status", VALID_LD_PAIR_STATUS), **since("0.8.0")},
        description=(
            "resolved: the reference gave r² and D′. not_reported: it answered with no row, which is a "
            "pair below its reporting floor or not in LD (two chromosomes answer the same), never r² = 0. "
            "rsid_unknown: it does not know one of the two rsIDs. ancestry_mixed / ancestry_unstated: the "
            "study states several superpopulations, or none, so no panel was asked. lead_has_no_rsid: "
            "the lead is coordinate-authored and no rsID is known for it, and the reference takes rsIDs."
        ),
    )
    r2: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        json_schema_extra=since("0.8.0"),
        description="r² between proxy and lead in `ld_population`. Set only when `status` is resolved.",
    )
    d_prime: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        json_schema_extra=since("0.8.0"),
        description="|D′| between proxy and lead in `ld_population`, as the reference reports it.",
    )
    answered_rsid: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The proxy as the reference named it in its answer. Differs from `proxy_rsid` when dbSNP "
            "merged the author's id into another (rs1624712 answers as rs646776); the row stays keyed on "
            "what the author wrote. A label, outside the fact hash."
        ),
    )
    dataset: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The reference release that answered, e.g. 'ensembl_116'. Null on a row nobody was asked about.",
    )

    # ── provenance (EXCLUDED from ld_pair_signature) ──
    source: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The licensed source that answered: ensembl (open). Joins `sources.csv.source`.",
    )
    fetched_at: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="ISO-8601 UTC timestamp when a pass wrote this row; the release is `dataset`.",
    )

    @field_validator("proxy_rsid", "variant_key")
    @classmethod
    def _check_required(cls, v: str, info) -> str:
        v = v.strip()
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @field_validator("ld_population")
    @classmethod
    def _blank_population_is_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        return check_vocab(v, VALID_LD_PAIR_STATUS, "status") or v

    @field_validator("r2", "d_prime")
    @classmethod
    def _check_finite(cls, v: float | None, info) -> float | None:
        validate_finite(v, info.field_name or "r2")
        return v

    @field_validator("fetched_at", mode="before")
    @classmethod
    def _canonical_fetched_at(cls, v: object) -> str | None:
        return normalize_utc_timestamp(v)

    @model_validator(mode="after")
    def _the_number_and_its_reason_agree(self) -> "LdPairRow":
        # A number on a withheld row would be a value with no claim behind it, and a resolved row with no
        # number would be the zero this table exists to refuse. One rule each way.
        if (self.status == LD_RESOLVED) != (self.r2 is not None):
            raise ValueError(
                f"status={self.status!r} with r2={self.r2!r} — r2 is set exactly when status is resolved; "
                f"a withheld pair carries its reason and no number"
            )
        if self.status != LD_RESOLVED and self.d_prime is not None:
            raise ValueError(
                f"status={self.status!r} carries d_prime={self.d_prime!r}; only a resolved pair has one"
            )
        if (self.status in LD_POPULATION_WITHHELD) != (self.ld_population is None):
            raise ValueError(
                f"status={self.status!r} with ld_population={self.ld_population!r} — a population is "
                f"named exactly when the study states one superpopulation"
            )
        return self
