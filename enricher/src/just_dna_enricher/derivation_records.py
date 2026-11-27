"""Offline declarations of changes to the tables an enricher release writes (RM399, RM441)."""

from dataclasses import dataclass
from typing import Annotated, Self

from just_dna_format.base import vocabulary
from just_dna_format.identity import parse_version
from just_dna_format.layout import SOURCES_CSV, sidecar_key
from just_dna_format.release_records import release_version
from just_dna_format.vocab import check_vocab
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.producers import DERIVED_PRODUCERS, WRITTEN_BY_EVERY_PASS

VALID_ENRICHER_DERIVATION_CAUSES: frozenset[str] = frozenset({"lane_moved", "derivation_corrected"})


def _table_key(table: str) -> str:
    key = sidecar_key(table)
    if key not in DERIVED_PRODUCERS and key not in WRITTEN_BY_EVERY_PASS:
        raise ValueError(f"unknown derived table: {table!r}")
    return key


ReleaseLabel = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
RoadmapItem = Annotated[str, StringConstraints(pattern=r"^RM[1-9][0-9]*$")]


class DerivationChange(BaseModel):
    """One change reaching a derived table. A lane's predecessor may have had no release label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table: str
    cause: str = Field(
        json_schema_extra=vocabulary("enricher_derivation_cause", VALID_ENRICHER_DERIVATION_CAUSES)
    )
    items: tuple[RoadmapItem, ...] = Field(min_length=1)
    lane: str | None = None
    old_release: ReleaseLabel | None = None
    new_release: ReleaseLabel | None = None

    @field_validator("table")
    @classmethod
    def _check_table(cls, table: str) -> str:
        return _table_key(table)

    @field_validator("cause")
    @classmethod
    def _check_cause(cls, cause: str) -> str:
        return check_vocab(cause, VALID_ENRICHER_DERIVATION_CAUSES, "cause")

    @model_validator(mode="after")
    def _check_lane_move(self) -> Self:
        if self.cause == "lane_moved":
            if self.lane not in LANES_BY_NAME:
                raise ValueError(f"a lane move requires a known cache lane, got {self.lane!r}")
            if self.new_release is None:
                raise ValueError("a lane move requires the new release label")
        elif any(value is not None for value in (self.lane, self.old_release, self.new_release)):
            raise ValueError("only a lane move carries a lane or its release labels")
        return self


def _correction(table: str, *items: str) -> DerivationChange:
    return DerivationChange(table=table, cause="derivation_corrected", items=items)


# RM372's old repo just-dna-seq/ensembl_variations (2205d5ed) carried no label. The split
# repo just-dna-seq/ensembl_variations_split (ee964d71) names its release in manifest.json.
DERIVATION_RECORDS: dict[str, tuple[DerivationChange, ...] | None] = {
    # RM372/RM267: the split Ensembl release changed insertion placements.
    "0.8.0": (
        DerivationChange(
            table="resolution.csv",
            cause="lane_moved",
            items=("RM372", "RM267"),
            lane="ensembl",
            old_release=None,
            new_release="ensembl-variation-2026_07_13-vep116.0",
        ),
    ),
    # RM398 changes the witness and its licence row, RM400 drops off-primary loci. RM397/401/403/407 do neither.
    "0.8.1": (_correction("resolution.csv", "RM398", "RM400"), _correction(SOURCES_CSV, "RM398")),
    # RM410 moves the constraint lane, RM417 relabels API rows. RM408/411/413–416 concern provisioning or warnings.
    "0.8.2": (
        *(
            DerivationChange(
                table=table,
                cause="lane_moved",
                items=("RM410",),
                lane="constraint",
                old_release="gnomad_v4.1_constraint",
                new_release="gnomad_v4.1.2_constraint",
            )
            for table in ("gene_metrics.csv", SOURCES_CSV)
        ),
        _correction("gene_metrics.csv", "RM417"),
        _correction(SOURCES_CSV, "RM417"),
    ),
    # RM420 refreshes whichever pulled lanes are stale. RM409/418/421–423 affect downloads, pacing, warnings and attestation.
    "0.8.3": None,
    # RM428 restores missing GWAS rows and their licence row after the first page was refused. RM425–427 change text.
    "0.8.4": (_correction("gwas_effects.csv", "RM428"), _correction(SOURCES_CSV, "RM428")),
    # RM438 checks back-filled rsIDs against alleles. RM432: offline over an unreadable constraint snapshot, 0.8.4
    # wrote `not_found` gene rows (and their licence row) naming a release it never opened; 0.8.5 writes none and
    # names the genes as never asked (the lead, 2026-11-27). RM434/436 change wording and a dependency floor.
    "0.8.5": (
        _correction("resolution.csv", "RM438"),
        _correction("gene_metrics.csv", "RM432"),
        _correction(SOURCES_CSV, "RM432"),
    ),
    # RM439 describes an authored field and RM440 reports the rsID loss already introduced in 0.8.5.
    "0.8.6": (),
    # RM442 corrects text written into AlphaGenome licence rows. RM444 changes advice to a caller.
    "0.8.7": (_correction(SOURCES_CSV, "RM442"),),
    # RM445 repairs caches serving old data under newer labels; the affected lanes and releases depend on the cache.
    "0.8.8": None,
    # RM448 restores withheld loci. RM446/447/449/451/452 affect diagnostics, drafting, compilation or failed reads.
    "0.8.9": (_correction("resolution.csv", "RM448"),),
    # RM453 changes the compiler's reading of resolution.csv (a compiled-output change, the format's record), RM456 log
    # discovery. RM455 refuses a client built with `batch_size` 0, which answered `{}`; no default setting is 0, so
    # no derivation at the shipped settings moves ("Nothing a module resolves moves", its CHANGELOG entry).
    "0.8.10": (),
    # RM454 restores mixed-case constraint rows. RM404/412/430/431/437/443/458/461–467/470 add routes, gates or parity checks.
    "0.9.0": (_correction("gene_metrics.csv", "RM454"), _correction(SOURCES_CSV, "RM454")),
}

# These closed lines predate the records. Their final patch numbers let a wheel name every
# uncovered enricher release, including enricher-only patches absent from the compiler's history.
_BEFORE_RECORDS = frozenset(
    f"0.{minor}.{patch}" for minor, last_patch in ((5, 4), (6, 6), (7, 3)) for patch in range(last_patch + 1)
)


@dataclass(frozen=True)
class RederiveReasons:
    """Matching (release, change) pairs and unexamined releases, each in oldest-first order."""

    changes: tuple[tuple[str, DerivationChange], ...]
    unknown_releases: tuple[str, ...]


def rederive_reasons(from_release: str, to_release: str, table: str | None = None) -> RederiveReasons:
    """Explain (from_release, to_release], including a requested end beyond the installed history."""
    low = parse_version(release_version(from_release))
    high = parse_version(release_version(to_release))
    if low > high:
        raise ValueError(f"backwards enricher release span: {from_release!r} to {to_release!r}")
    key = None if table is None else _table_key(table)
    changes: list[tuple[str, DerivationChange]] = []
    unknown: list[str] = []
    releases = DERIVATION_RECORDS.keys() | _BEFORE_RECORDS | {str(high)}
    for release in sorted(releases, key=parse_version):
        if low < parse_version(release) <= high:
            entry = DERIVATION_RECORDS.get(release)
            if entry is None:
                unknown.append(release)
            else:
                changes.extend((release, change) for change in entry if key is None or change.table == key)
    return RederiveReasons(tuple(changes), tuple(unknown))


def needs_rederive(from_release: str, to_release: str, table: str | None = None) -> bool | None:
    """Whether any release in the span declares a matching change. Unknowns withhold a negative."""
    reasons = rederive_reasons(from_release, to_release, table)
    if reasons.changes:
        return True
    return None if reasons.unknown_releases else False


def newest_rederive_release(table: str) -> str | None:
    """Newest recorded release that changed the table or could not say, if there is one."""
    key = _table_key(table)
    return max(
        (
            release
            for release, entry in DERIVATION_RECORDS.items()
            if entry is None or any(change.table == key for change in entry)
        ),
        key=parse_version,
        default=None,
    )
