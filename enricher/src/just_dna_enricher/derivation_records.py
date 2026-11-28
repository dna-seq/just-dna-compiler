"""Offline declarations of changes to the tables an enricher release writes (RM399, RM441)."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Annotated, Self

from just_dna_compiler.hints import DERIVED_TABLE_MODELS
from just_dna_format.base import field_first_seen, vocabulary
from just_dna_format.identity import Version, parse_version
from just_dna_format.layout import SOURCES_CSV, sidecar_key
from just_dna_format.release_records import release_version
from just_dna_format.vocab import check_vocab
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from just_dna_enricher.caches import LANES_BY_NAME

VALID_ENRICHER_DERIVATION_CAUSES: frozenset[str] = frozenset({"lane_moved", "derivation_corrected"})

# The tagged writers shipped with their row models. Later optional columns and filename aliases
# do not move a table's first release.
_FIRST_PRODUCED = {
    sidecar_key(name): min(map(parse_version, field_first_seen(model).values()))
    for name, model in DERIVED_TABLE_MODELS.items()
}


def _table_key(table: str) -> str:
    key = sidecar_key(table)
    if key not in _FIRST_PRODUCED:
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
        # RM383 retires an unearned resolution source on --rederive and an unearned authority
        # on a whole concordance rewrite. RM379 records the consulted authorities; RM373 labels them.
        _correction(SOURCES_CSV, "RM373", "RM379", "RM383"),
        # RM370 stopped writing header-only sidecars. RM361 withheld unanswered lookups and
        # unstated releases; RM373 replaced run dates and fixed release labels on fact rows too.
        _correction("frequencies.csv", "RM361", "RM370"),
        _correction("gene_metrics.csv", "RM361", "RM370", "RM373"),
        _correction("gene_validity.csv", "RM361", "RM370"),
        _correction("clinical_assertions.csv", "RM370", "RM373"),
        _correction("expression_effects.csv", "RM373"),
        _correction("gwas_effects.csv", "RM354", "RM373"),
        _correction("literature.csv", "RM258", "RM361", "RM370"),
        _correction("clin_sig_concordance.csv", "RM370"),
        _correction("clin_sig_authority_calls.csv", "RM370"),
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
    "0.8.9": (_correction("resolution.csv", "RM448"), _correction(SOURCES_CSV, "RM448")),
    # RM453 changes the compiler's reading of resolution.csv (a compiled-output change, the format's record), RM456 log
    # discovery. RM455 refuses a client built with `batch_size` 0, which answered `{}`; no default setting is 0, so
    # no derivation at the shipped settings moves ("Nothing a module resolves moves", its CHANGELOG entry).
    "0.8.10": (),
    # RM454 restores mixed-case constraint rows. RM404/412/430/431/437/443/458/461–467/470 add routes, gates or parity checks.
    "0.9.0": (_correction("gene_metrics.csv", "RM454"), _correction(SOURCES_CSV, "RM454")),
}

# Published enricher versions, independent of whether anyone examined their effects. The tag
# test checks this inventory against each tag's enricher/pyproject.toml; wheels need no checkout.
_RELEASES = tuple(
    Version(0, minor, patch)
    for minor, last_patch in ((5, 4), (6, 6), (7, 3), (8, 10), (9, 0))
    for patch in range(last_patch + 1)
)


@dataclass(frozen=True)
class RederiveReasons:
    """Matching (release, change) pairs and unexamined releases, each in oldest-first order."""

    changes: tuple[tuple[str, DerivationChange], ...]
    unknown_releases: tuple[str, ...]


def _walk(
    releases: Iterable[Version], key: str | None
) -> Iterator[tuple[str, tuple[DerivationChange, ...] | None]]:
    """Yield matching changes, an examined empty tuple, or a withheld answer at each release."""
    for version in releases:
        release = str(version)
        entry = DERIVATION_RECORDS.get(release)
        if entry is None or (key is not None and version < _FIRST_PRODUCED[key]):
            yield release, None
        else:
            yield release, tuple(change for change in entry if key is None or change.table == key)


def rederive_reasons(from_release: str, to_release: str, table: str | None = None) -> RederiveReasons:
    """Explain (from_release, to_release], including a requested end beyond the installed history."""
    low = parse_version(release_version(from_release))
    high = parse_version(release_version(to_release))
    if low > high:
        raise ValueError(f"backwards enricher release span: {from_release!r} to {to_release!r}")
    key = None if table is None else _table_key(table)
    changes: list[tuple[str, DerivationChange]] = []
    unknown: list[str] = []
    releases = [version for version in _RELEASES if low < version < high]
    if low < high or (key is not None and high < _FIRST_PRODUCED[key]):
        releases.append(high)
    for release, entry in _walk(releases, key):
        if entry is None:
            unknown.append(release)
        else:
            changes.extend((release, change) for change in entry)
    return RederiveReasons(tuple(changes), tuple(unknown))


def needs_rederive(from_release: str, to_release: str, table: str | None = None) -> bool | None:
    """Whether any release in the span declares a matching change. Unknowns withhold a negative."""
    reasons = rederive_reasons(from_release, to_release, table)
    if reasons.changes:
        return True
    return None if reasons.unknown_releases else False


def newest_rederive_release(table: str) -> str | None:
    """Newest published release that could have changed this table, including a missing record."""
    key = _table_key(table)
    eligible = (version for version in reversed(_RELEASES) if version >= _FIRST_PRODUCED[key])
    return next((release for release, entry in _walk(eligible, key) if entry is None or entry), None)
