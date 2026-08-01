"""Shared base for every authored-DSL row model (`spec`/`binning`/`pgx`/`pgs`).

Consolidates the boilerplate that was copy-pasted across the row models into one place:

- the **reserved-namespace guard** — `extra="forbid"` plus the `reject_reserved` before-validator, so
  a reserved name fails with a specific diagnosis and any other unknown/misspelled column fails with
  the generic message (see `vocab.reject_reserved`); and
- the **field validators for the shared authored vocabulary** — `rsid`, `trait_efo_id`, `direction`,
  `clin_sig`, `stat_significance`, `evidence_level`, and finite-`effect_size`.

Each field validator uses `check_fields=False`, so a subclass runs it only for the fields it actually
declares (a model without `clin_sig` simply never runs the `clin_sig` check) and a model that *adds*
one of these fields gets the correct validation for free — the per-field rules cannot drift model to
model, which is exactly what the previous copy-paste risked. Field-specific rules (genotype/phase,
star-allele strings, measure bounds, PGS ancestry, the mtDNA legacy-reference guard, identifier
completeness) stay on their own models.

Dependency-light: imports only `pydantic` + the stdlib `vocab` leaf, and nothing in the package
imports it back, so it introduces no cycle.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from just_dna_format.vocab import (
    VALID_CLIN_SIG,
    VALID_DIRECTIONS,
    VALID_EVIDENCE_LEVELS,
    VALID_SIGNIFICANCE,
    check_vocab,
    reject_reserved,
    validate_finite,
    validate_rsid,
    validate_trait_ids,
)
from just_dna_format.vrs import UnsupportedBuildError, derive_vrs_allele_id


def derive_variant_key(
    rsid: Optional[str],
    chrom: Optional[str],
    start: Optional[int],
    ref: Optional[str],
    alts: Optional[str] = None,
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
    chrom: Optional[str], start: Optional[int], ref: Optional[str], alt: str, build: str
) -> Optional[str]:
    """Case 2 of `derive_variant_key`, isolated so the fallback path stays readable.

    Returns `None` for anything unmintable — including a build with no refget table, which
    `refget_accession` reports by raising rather than by guessing, and which is a fall-through here
    (a GRCh37 module keeps its coordinate key) rather than a hard failure at row-load time.
    """
    try:
        return derive_vrs_allele_id(chrom, start, ref, alt, build=build)
    except UnsupportedBuildError:
        return None


class AuthoredModel(BaseModel):
    """Base for authored-DSL rows: reserved-namespace guard + shared-vocabulary field validators."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_reserved(cls, data: object) -> object:
        # A reserved name fails with a specific diagnosis; any other unknown/typo'd column falls
        # through to `extra="forbid"`'s generic message. See vocab.reject_reserved.
        return reject_reserved(data)

    @field_validator("rsid", check_fields=False)
    @classmethod
    def _validate_rsid(cls, v: Optional[str]) -> Optional[str]:
        return validate_rsid(v)

    @field_validator("trait_efo_id", check_fields=False)
    @classmethod
    def _validate_trait_efo_id(cls, v: Optional[str]) -> Optional[str]:
        return validate_trait_ids(v)

    @field_validator("direction", check_fields=False)
    @classmethod
    def _validate_direction(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_DIRECTIONS, "direction")

    @field_validator("clin_sig", check_fields=False)
    @classmethod
    def _validate_clin_sig(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_CLIN_SIG, "clin_sig")

    @field_validator("stat_significance", check_fields=False)
    @classmethod
    def _validate_stat_significance(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_SIGNIFICANCE, "stat_significance")

    @field_validator("evidence_level", check_fields=False)
    @classmethod
    def _validate_evidence_level(cls, v: Optional[str]) -> Optional[str]:
        return check_vocab(v, VALID_EVIDENCE_LEVELS, "evidence_level")

    @field_validator("effect_size", check_fields=False)
    @classmethod
    def _validate_effect_size(cls, v: Optional[float]) -> Optional[float]:
        return validate_finite(v, "effect_size")
