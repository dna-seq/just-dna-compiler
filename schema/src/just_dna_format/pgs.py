"""
Polygenic score declaration (0.4 — see docs/CHANGELOG.md).

`pgs.csv` is a **manifest of PGS Catalog IDs, not authored weights** — just-prs resolves a `PGSxxxxxx`
id to a harmonized scoring file itself and scores each id independently, so per-PGS weights would be
dead data. It is therefore a *declared interface* (like `GenePanelSpec`), **not** a `measure→phenotype`
binning table: a PRS yields a Z/percentile *within a matched reference distribution*, which the
format does not bin.

The one-way-door fields (consumer round-2 Q8) are pinned here from day one so a
consumer can refuse or caveat an out-of-ancestry application instead of silently miscalibrating:
- `training_ancestry` — the superpopulation(s) the score was validated in (required floor), plus an
  optional free-form `training_cohort` for the sub-superpop precision superpop codes can't express
  (a Northwest-EUR-trained score applied to a Finnish/Ashkenazi sample).
- `match_rate_floor` — the author-set floor (a > ~20% variant mismatch invalidates the score). Only
  the *floor* lives here: the *observed* per-sample match rate is a **measurement**, so by the
  data-agnostic north star (CLAUDE.md) it is consumer/runtime-side and must NOT live in the module.
- `research_tier` — pins as *data* that a PRS is a within-reference Z/percentile, never an
  ancestry-calibrated absolute risk; `|Z| >= 2.5` in a healthy proband is a population-stratification
  signal, not a disease prediction.

Data-agnostic (design north star — see CLAUDE.md): this declares *which* scores a module curates and
how to caveat them; no sample, genotype, or computed score lives here.
"""

import re

from pydantic import Field, field_validator

from just_dna_format.base import AuthoredModel, vocabulary
from just_dna_format.vocab import MULTI_SEP, check_vocab, validate_finite

PGS_ID_PATTERN: re.Pattern[str] = re.compile(r"^PGS\d+$")
# 1000G superpopulation codes + `multi` for multi-ancestry scores (closed-validated, additive).
VALID_TRAINING_ANCESTRY: frozenset[str] = frozenset({"EUR", "EAS", "AFR", "AMR", "SAS", "multi"})
# Whether the score is usable only as a research-frame Z/percentile or is ancestry-calibrated.
VALID_RESEARCH_TIERS: frozenset[str] = frozenset({"research_only", "calibrated"})


class PgsRow(AuthoredModel):
    """One curated PGS Catalog entry. Inherits `AuthoredModel` (reserved-namespace guard, which keeps
    the namespace closed, + the shared `trait_efo_id` validator)."""

    pgs_id: str = Field(description="PGS Catalog id, e.g. PGS000135")
    trait_efo_id: str | None = Field(
        default=None, description="EFO/MONDO/OBA/HP trait ontology id(s) — joins with variant modules"
    )
    note: str | None = Field(default=None, description="Free-text note")
    group: str | None = Field(default=None, description="Grouping label within the module")
    training_ancestry: list[str] | None = Field(
        default=None,
        # NOT `vocab.RECOMMENDED_ANCESTRY_GROUPS` — these are 1000G superpopulation codes and that is
        # a gnomAD population list. `vocab.py` forbids merging them; keying the marker by vocabulary
        # *name* rather than by field name is what keeps two ancestry lists from collapsing into one.
        json_schema_extra=vocabulary("training_ancestry", VALID_TRAINING_ANCESTRY),
        description="Superpopulation(s) the score was validated in (1000G superpop codes; multi-valued)",
    )
    training_cohort: str | None = Field(
        default=None,
        description="Optional free-form sub-superpop cohort, e.g. 'FIN', 'Ashkenazi', 'UK Biobank NW-EUR'",
    )
    match_rate_floor: float | None = Field(
        default=None,
        description=(
            "Author-set variant-match floor in [0,1]; a score computed below it is invalid. Only the "
            "floor lives in-module — the observed per-sample match rate is a measurement (consumer-side)."
        ),
    )
    research_tier: str | None = Field(
        default=None,
        json_schema_extra=vocabulary("research_tier", VALID_RESEARCH_TIERS),
        description="research_only | calibrated (VALID_RESEARCH_TIERS)",
    )

    @field_validator("pgs_id")
    @classmethod
    def _validate_pgs_id(cls, v: str) -> str:
        if not PGS_ID_PATTERN.match(v):
            raise ValueError(f"pgs_id must match PGS<digits>, e.g. PGS000135, got: {v!r}")
        return v

    @field_validator("training_ancestry", mode="before")
    @classmethod
    def _split_ancestry(cls, v: object) -> object:
        # A CSV cell arrives as a string; split it into a list (programmatic use may pass a list).
        if isinstance(v, str):
            toks = [t.strip() for t in MULTI_SEP.split(v) if t.strip()]
            return toks or None
        return v

    @field_validator("training_ancestry")
    @classmethod
    def _validate_ancestry(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for tok in v:
            check_vocab(tok, VALID_TRAINING_ANCESTRY, "training_ancestry")
        return v

    @field_validator("match_rate_floor")
    @classmethod
    def _validate_match_rate_floor(cls, v: float | None) -> float | None:
        validate_finite(v, "match_rate_floor")
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"match_rate_floor must be within [0, 1], got {v}")
        return v

    @field_validator("research_tier")
    @classmethod
    def _validate_research_tier(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_RESEARCH_TIERS, "research_tier")
