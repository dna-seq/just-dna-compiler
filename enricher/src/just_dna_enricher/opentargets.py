"""`opentargets enrich`: fill the Open Targets lane's tables from the provisioned snapshot (0.8, RM333).

One pass, four writes, one licence row per write:

| table | grain | from the snapshot |
|---|---|---|
| `locus_to_gene.csv` | (study locus, gene, variant) | the L2G score of every GWAS credible set a module variant is a member of |
| `colocalisations.csv` | (study locus, right study locus, variant) | those credible sets' molecular-QTL colocalisations |
| `consequences.csv` | (variant, transcript) | every module variant's per-transcript VEP consequence (RM236) |
| `gwas_effects.csv` | (association) | RM239's `posterior_probability` and `fine_mapping_method`, filled on rows another pass wrote |

**Coordinates in, from `resolution.csv`**, like `frequencies`: a posterior and a consequence are per
*allele*, and the resolution table is where an rsID has already become `chrom-pos-ref-alt`, which is
exactly how the snapshot keys its variants (its alleles come from columns; its `variantId` is never
parsed). Open Targets is GRCh38-only, so a row on another build is skipped and counted.

**The pass never fetches.** It reads the snapshot `opentargets build` provisioned, and with none it
skips with a warning and writes nothing: nobody asked, which is not "Open Targets holds nothing"
(`@unreachable-not-absent`). There is no `--offline` flag for that reason: the off switch would be a
flag the pass never sees.

**Members, not lead-only** (RM333, decided 2026-11-04). A variant gets the L2G and coloc rows of every
GWAS credible set it sits in, whether or not it leads it: HFE C282Y (rs1800562) is in 82 sets of the
26.09 release and leads none, so a lead-only table would be empty for the module the lane exists for.
`variant_key` is the module variant asked about and is in both tables' keys; `lead_variant_id` still
names the source's lead, and the member's own weight in the set is its posterior on `gwas_effects.csv`.
The snapshot holds GWAS sets only (the builder filters on `studyType`), so a member of a molecular-QTL
set gets no row here; that side arrives as the right half of a colocalisation.

**Three answers per question, kept apart.** For each `gwas_effects.csv` row the posterior is filled
only when exactly one value answers; otherwise it is left empty and the reason is counted: the study
has no credible set in the release, the variant is not in the study's set, or the variant sits in
several of the study's sets with different values (`@multiplicity-is-a-finding`, never a winner).

**A row with no ALT gets the release's allele, only when the release names exactly one** (RM333, decided
2026-11-04). `resolution.csv` may hold an rsID at `(chrom, start, ref)` with `alts` empty (an authored
rsID-only row, `apoe_epsilon`'s two). The pass then reads every allele of the release at that position and
its `rsIds`: an allele carrying the row's rsID (or its `rsid_current`) is a candidate on any REF, an
allele on the row's REF carrying none is a candidate too (unknown, never "not this one": at
`6:26091590 G` the release states rs773443949 on `G>T` and nothing on `G>A`, while dbSNP, through
ClinVar, names both), and an allele carrying only other rsIDs is not. Exactly one candidate, carrying
the rsID on the row's REF, supplies the ALT, and the key is named in `allele_supplied`; any other
non-empty set withholds the key (`allele_unstated_withheld`, never a pick:
`@multiplicity-is-a-finding`), as does a row whose rsID is itself the back-fill's pick
(`status="ambiguous"`); no candidate is the ordinary not-in-release answer. A row with no
rsID either is withheld (`allele_unstated_no_rsid`): a position alone is not an identity
(`@rsid-not-per-allele`). The supplied ALT is never written back to `resolution.csv`
(`@enrichment-is-validation`), and no derived row says which ALT it used: the named key lists and the
counts are the record. A snapshot built before the allele table carried `rs_ids` cannot answer the
question at all: those keys are nobody-asked (`allele_unstated_unasked`), and `strict` refuses.

**Answered replaces, could-not-ask keeps** (`@rederive-never-shortens`): a variant this run looked up
has its rows replaced by the snapshot's answer, and a variant it could not look up (off-build,
unresolved) keeps whatever rows it had.

**An answer is only as complete as the parts it was read from** (RM361). `READS` names the source
datasets each table and the posterior are read from, and `read_is_complete` asks the snapshot's
`release.json` whether every one of them was read whole: `True` only when `parts_read` equals
`parts_total` for each, `False` when one was partial, and `None` when the record cannot say (no
`parts_total`, a dataset missing from it, a count that is not a number). Anything but `True` means an
absent row may be a part nobody opened, so no key is answered for that table: rows the snapshot did
yield are merged in, and every existing row is kept. A key that did not join the allele table is then
`not_read` rather than `not_in_release`, and the posterior on `gwas_effects.csv` is left as it was.
`strict` refuses such a snapshot before anything is read.
"""

import csv
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.consequences import ConsequenceRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.locus_genes import ColocalisationRow, LocusToGeneRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from just_dna_format.snapshot import SnapshotRelease, read_release
from just_dna_format.vrs import normalize_chrom
from pydantic import BaseModel

from just_dna_enricher.licensing import (
    OPENTARGETS_TERMS,
    overlaid_input_rows,
    record_table_sources,
    require_sources_file,
    sidecar_path,
)
from just_dna_enricher.locations import resolve_opentargets_reference
from just_dna_enricher.opentargets_build import (
    COLOC_GLOB,
    CONSEQUENCES_GLOB,
    CREDIBLE_SETS_FILE,
    L2G_FILE,
    MEMBERS_GLOB,
    OPENTARGETS_DATASETS,
    VARIANTS_FILE,
)
from just_dna_enricher.resolver import _typed_rows_connection, probe_table

logger = logging.getLogger(__name__)

SOURCE_NAME: str = OPENTARGETS_TERMS.source
OPENTARGETS_GENOME_BUILD: str = "GRCh38"

#: `(csv, model, licence layer)` for the three tables this pass owns, in write order.
OWNED_TABLES: tuple[tuple[str, type[BaseModel], str], ...] = (
    ("locus_to_gene.csv", LocusToGeneRow, "locus_to_gene"),
    ("colocalisations.csv", ColocalisationRow, "colocalisation"),
    ("consequences.csv", ConsequenceRow, "consequence"),
)
#: The licence layer of the fourth write, the posterior on another pass's table.
GWAS_LAYER: str = "gwas_effect"

#: The source datasets (`OPENTARGETS_DATASETS`) each answer is read from (RM361). An answer counts only
#: when every one of them was read whole; the allele table (`variant`) is in each, because a key that did
#: not join it may sit in a part nobody opened. Asserted against `OWNED_TABLES` and the dataset list.
READS: dict[str, frozenset[str]] = {
    "consequences.csv": frozenset({"variant"}),
    "locus_to_gene.csv": frozenset({"variant", "credible_set", "l2g_prediction"}),
    "colocalisations.csv": frozenset({"variant", "credible_set", "colocalisation", "study"}),
    "gwas_effects.csv": frozenset({"variant", "credible_set"}),
}


class OpenTargetsError(RuntimeError):
    """The Open Targets pass failed; its own type, so the CLI prints a diagnosis rather than a traceback."""


@dataclass
class PosteriorCounts:
    """What happened to each `gwas_effects.csv` row the pass looked at. Every bucket is a different answer."""

    filled: int = 0
    #: The row names no study accession (a Catalog `not_found` row, or a study published without one).
    no_study: int = 0
    #: The variant could not be looked up: unresolved, or on another build. The row keeps its value.
    not_looked_up: int = 0
    #: The variant is not in the release's variant table at all.
    variant_not_in_release: int = 0
    #: The study has no GWAS credible set in the release (asked, and absent).
    study_without_credible_set: int = 0
    #: The study has credible sets, and the variant is in none of them (not in the 95% set).
    not_in_credible_set: int = 0
    #: The variant sits in several of the study's sets with different values: withheld, never picked.
    contested: int = 0
    #: The variant is in one of the study's sets, and the release left that set's method empty: the
    #: posterior means nothing without it (`GwasEffectRow` refuses the half, RM366), so it is withheld.
    #: 26.09 has no such set (0 of 1,519,507 measured); this is the next release's possible shape.
    method_missing: int = 0
    #: The snapshot was not read whole for the datasets the posterior comes from (RM361), so an absent
    #: or a single value may be a part nobody opened. The row keeps its value.
    not_read: int = 0
    #: The module row states no ALT and the release supplied none (several candidate alleles, no rsID,
    #: or a snapshot without rsIDs). The row keeps its value.
    allele_withheld: int = 0


@dataclass
class OpenTargetsResult:
    """Outcome of one pass. `skipped` names why nothing was read, when nothing was."""

    skipped: str | None = None
    dataset: str | None = None
    locus_to_gene: list[LocusToGeneRow] = field(default_factory=list)
    colocalisations: list[ColocalisationRow] = field(default_factory=list)
    consequences: list[ConsequenceRow] = field(default_factory=list)
    gwas_effects: list[GwasEffectRow] = field(default_factory=list)
    posterior: PosteriorCounts = field(default_factory=PosteriorCounts)
    #: Module variants the snapshot was asked about (one per resolved allele).
    asked: list[str] = field(default_factory=list)
    #: Asked, and absent from the release's variant table.
    not_in_release: list[str] = field(default_factory=list)
    #: Asked, and absent from a variant table not read whole (`read_is_complete`): maybe in an unread part.
    not_read: list[str] = field(default_factory=list)
    #: Resolved on another build, so not asked.
    off_build: list[str] = field(default_factory=list)
    #: Resolved to several of the release's alleles, so its per-transcript rows would collide: withheld.
    allele_ambiguous: list[str] = field(default_factory=list)
    #: Module keys sharing one release allele with another key: their L2G and coloc rows are withheld in
    #: every set they are in, and the keys are named. With `variant_key` in the key
    #: the two keys' rows would no longer collide; the arm is kept because one release allele stated
    #: twice under two module keys is a module defect to name, not a fact to write twice.
    shared_allele_keys: list[str] = field(default_factory=list)
    #: Rows with no ALT whose allele the release supplied: one candidate at the locus, carrying the rsID.
    #: Their rows in every table are of that allele, which the module did not author.
    allele_supplied: list[str] = field(default_factory=list)
    #: Rows with no ALT withheld: several candidate alleles at the locus, or the only one states no rsID.
    allele_unstated_withheld: list[str] = field(default_factory=list)
    #: Rows with neither an ALT nor an rsID: a position alone names no allele, so nothing is asked.
    allele_unstated_no_rsid: list[str] = field(default_factory=list)
    #: Rows with no ALT and an rsID, against a snapshot whose allele table carries no rsIDs: nobody asked.
    allele_unstated_unasked: list[str] = field(default_factory=list)
    #: Datasets the snapshot read only some parts of, `{dataset: (read, total)}`.
    partial: dict[str, tuple[int, int]] = field(default_factory=dict)


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


#: Each view the pass and the keyed functions query, and the snapshot file (or glob) it is over.
_VIEWS: dict[str, str] = {
    "variants": VARIANTS_FILE,
    "consequences": CONSEQUENCES_GLOB,
    "credible_sets": CREDIBLE_SETS_FILE,
    "members": MEMBERS_GLOB,
    "l2g": L2G_FILE,
    "coloc": COLOC_GLOB,
}


def _connect(snapshot: Path, views: Sequence[str] = tuple(_VIEWS)) -> duckdb.DuckDBPyConnection:
    """Views over the snapshot's tables (every one unless `views` names some). The paths are our own
    cache's, quoted defensively; a table the snapshot cannot be read for raises `OpenTargetsError`."""
    data = Path(snapshot) / "data"
    con = duckdb.connect(":memory:")
    for view in views:
        name = _VIEWS[view]
        try:
            con.execute(f"CREATE VIEW {view} AS SELECT * FROM read_parquet('{_quoted(data / name)}')")
        except duckdb.Error as exc:
            con.close()
            raise OpenTargetsError(
                f"the Open Targets snapshot at {snapshot} has no readable `{name}`: {exc}"
            ) from exc
    return con


def _part_counts(release: SnapshotRelease, dataset: str) -> tuple[int, int] | None:
    """`(parts read, parts total)` for one dataset, or `None` when the record does not state both.

    Read off the typed fields (RM369), so this is as lenient as `read_release`: a `parts_read` or
    `parts_total` that is not a map at all, or a map holding a value pydantic cannot read as an int
    (`null`, `1.5`, `"x"`), is dropped whole and read as unstated, while pydantic's lax mode reads a
    per-dataset `"1"`, `1.0` or `true` as 1. Nothing is coerced here, and an unstated count is the
    unknown arm (RM361). The strict reading is the publish gate's (`upload._refuse_an_unreadable_record`,
    RM412), which refuses every count that is not a whole number, `null` included.
    """
    read = (release.parts_read or {}).get(dataset)
    total = (release.parts_total or {}).get(dataset)
    if read is None or total is None:
        return None
    return read, total


def dataset_complete(release: SnapshotRelease, dataset: str) -> bool | None:
    """Whether the snapshot read every part of `dataset`: `None` when its record cannot say (RM361)."""
    counts = _part_counts(release, dataset)
    return None if counts is None else counts[0] >= counts[1]


def read_is_complete(release: SnapshotRelease, datasets: frozenset[str]) -> bool | None:
    """Kleene AND of `dataset_complete` over `datasets`: one partial dataset is `False` whatever the rest
    say, and otherwise one the record cannot speak for is `None` (RM361)."""
    answers = [dataset_complete(release, dataset) for dataset in sorted(datasets)]
    if False in answers:
        return False
    return None if None in answers else True


def _partial_datasets(release: SnapshotRelease) -> dict[str, tuple[int, int]]:
    """`{dataset: (read, total)}` for every dataset the snapshot read short of the release's total."""
    return {
        dataset: counts
        for dataset in OPENTARGETS_DATASETS
        if dataset_complete(release, dataset) is False and (counts := _part_counts(release, dataset))
    }


Allele = tuple[str, str | None, str, int, str, str]
#: `(variant_key, rsid, rsid_current, chrom, start, ref)`: a resolved row that states no ALT.
Unstated = tuple[str, str | None, str | None, str, int, str]


def _alleles(rows: list[ResolutionRow]) -> tuple[list[Allele], list[Unstated], list[str], list[str]]:
    """`(variant_key, rsid, chrom, start, ref, alt)` per resolved ALT; one `Unstated` per on-build row that
    states no ALT and carries a settled rsID; the keys of no-ALT rows whose rsID is itself a pick among
    several (`status="ambiguous"`, `rsid_alternates`); and the keys left out as off-build."""
    seen: set[tuple] = set()
    out: list[Allele] = []
    unstated: list[Unstated] = []
    unsettled: set[str] = set()
    off_build: list[str] = []
    for row in rows:
        if row.status == "not_found" or row.chrom is None or row.start is None or row.ref is None:
            continue
        if row.genome_build != OPENTARGETS_GENOME_BUILD:
            off_build.append(row.variant_key)
            continue
        alts = [a.strip() for a in (row.alts or "").split(",") if a.strip()]
        if not alts:
            if row.status == "ambiguous":
                unsettled.add(row.variant_key)
                continue
            entry = (row.variant_key, row.rsid, row.rsid_current, row.chrom, row.start, row.ref)
            if entry not in seen:
                seen.add(entry)
                unstated.append(entry)
            continue
        for alt in alts:
            entry = (row.variant_key, row.rsid, row.chrom, row.start, row.ref, alt)
            if entry not in seen:
                seen.add(entry)
                out.append(entry)
    return out, unstated, sorted(unsettled), sorted(set(off_build))


def _supply_alleles(
    con: duckdb.DuckDBPyConnection, unstated: list[Unstated]
) -> tuple[list[Allele], list[str], list[str]]:
    """The release's ALT for each row that states none, by its rsID at its position.

    Returns the supplied alleles, the keys withheld, and the keys with no candidate at all. The row's
    rsID is `rsid`, or the `rsid_current` dbSNP merged it into. A candidate is an allele at the row's
    `(chrom, start)` carrying that rsID, whatever its REF (one rsID can name a SNV and an indel at one
    position), or an allele at the row's `(chrom, start, ref)` carrying no rsID at all (unknown, so it
    withholds rather than letting its sibling win). An allele carrying only other rsIDs is not one.
    Exactly one candidate, carrying the rsID on the row's own REF, supplies its ALT; any other
    non-empty set withholds. Candidates are distinct `(ref, alt)` pairs, so one allele the release
    lists under two ids is one candidate. Each entry is answered on its own locus.
    """
    probe_table(
        con,
        "unstated",
        [
            ("variant_key", "VARCHAR"),
            ("rsid", "VARCHAR"),
            ("rsid_current", "VARCHAR"),
            ("chrom", "VARCHAR"),
            ("position", "BIGINT"),
            ("ref", "VARCHAR"),
        ],
        unstated,
    )
    carrying: dict[Unstated, set[tuple[str, str]]] = {entry: set() for entry in unstated}
    unknown: dict[Unstated, set[tuple[str, str]]] = {entry: set() for entry in unstated}
    for key, rsid, current, chrom, position, ref, v_ref, v_alt, carries, states_none in con.execute(
        "SELECT u.variant_key, u.rsid, u.rsid_current, u.chrom, u.position, u.ref, v.ref, v.alt, "
        "coalesce(list_contains(v.rs_ids, u.rsid), false) "
        "OR coalesce(list_contains(v.rs_ids, u.rsid_current), false), "
        "coalesce(len(v.rs_ids), 0) = 0 "
        "FROM unstated u JOIN variants v ON v.chrom = u.chrom AND v.position = u.position "
        "ORDER BY u.variant_key, u.chrom, u.position, v.ref, v.alt, v.variant_id"
    ).fetchall():
        entry = (key, rsid, current, chrom, position, ref)
        if carries:
            carrying[entry].add((v_ref, v_alt))
        elif states_none and v_ref == ref:
            unknown[entry].add((v_ref, v_alt))
    supplied: list[Allele] = []
    withheld: set[str] = set()
    absent: set[str] = set()
    for entry in unstated:
        key, rsid, _current, chrom, start, ref = entry
        candidates = carrying[entry] | unknown[entry]
        if len(candidates) == 1 and carrying[entry] and next(iter(carrying[entry]))[0] == ref:
            supplied.append((key, rsid, chrom, start, ref, next(iter(carrying[entry]))[1]))
        elif candidates:
            withheld.add(key)
        else:
            absent.add(key)
    return supplied, sorted(withheld), sorted(absent - withheld)


def _cell(value: object) -> str:
    """One canonical CSV cell, matching the compiler's `_scalar_cell`."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write(
    rows: list[BaseModel], model: type[BaseModel], path: Path, before_commit: Callable[[], None] | None
) -> None:
    fieldnames = list(model.model_fields)
    if nothing_to_write(path, rows):
        return  # RM370: a pass that answered nothing leaves no table
    with atomic_writer(path, newline="", before_commit=before_commit) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in fieldnames})


def _existing(path: Path, model: type[BaseModel]) -> list:
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, model, path.name)
    if errors:
        raise OpenTargetsError(f"existing {path.name} is invalid: {errors[0]}")
    return rows


def _replace_answered(existing: list, fresh: list, answered: set[str], sort_key: Callable) -> list:
    """Keep existing rows for variants this run could not ask about; the answered ones are `fresh`."""
    kept = [row for row in existing if row.variant_key not in answered]
    seen = {merge_key(row) for row in kept}
    out = list(kept)
    for row in fresh:
        key = merge_key(row)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return sorted(out, key=sort_key)


def enrich_opentargets(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    write: bool = True,
    snapshot: Path | None = None,
    declared_use: str = "unstated",
) -> OpenTargetsResult:
    """Fill the three Open Targets tables and RM239's posterior from the provisioned snapshot.

    `mode="strict"` refuses a partial snapshot (one built from some parts of a dataset), because an
    absent coloc or L2G row from it may mean "not read" rather than "not published", and a strict run
    owes an artifact holding everything the release says. `best_effort` writes and warns.
    """
    spec_dir = Path(spec_dir)
    resolved = resolve_opentargets_reference(snapshot)
    if resolved is None:
        logger.warning(
            "Open Targets pass skipped: no snapshot is provisioned (set JUST_DNA_OPENTARGETS_CACHE or "
            "run `just-dna-enricher opentargets build`). Nothing was asked and nothing was written; "
            "this is not a finding that Open Targets holds nothing for these variants."
        )
        return OpenTargetsResult(skipped="no_snapshot")
    release = read_release(resolved) or SnapshotRelease()
    dataset = release.dataset or ""
    if not dataset:
        raise OpenTargetsError(
            f"the Open Targets snapshot at {resolved} has no release label in release.json"
        )
    partial = _partial_datasets(release)
    unstated = [name for name in OPENTARGETS_DATASETS if dataset_complete(release, name) is None]
    if unstated:
        if mode == "strict":
            raise OpenTargetsError(
                f"strict Open Targets enrichment: the snapshot at {resolved} does not record how many "
                f"parts {', '.join(unstated)} has, so whether it holds the whole release is unknown. "
                f"Build it with `opentargets build` (which records the totals), or use mode='best_effort'."
            )
        logger.warning(
            "Open Targets snapshot %s does not record how many parts %s has, so whether it is partial is "
            "unknown: an absent row below may mean a part was not read, and no existing row is replaced.",
            dataset,
            ", ".join(unstated),
        )
    if partial:
        described = ", ".join(f"{name} {got} of {total} parts" for name, (got, total) in partial.items())
        if mode == "strict":
            raise OpenTargetsError(
                f"strict Open Targets enrichment: the snapshot at {resolved} was built from part of the "
                f"release ({described}), so an absent row may mean 'not read' rather than 'not "
                f"published'. Build the whole release, or use mode='best_effort' and read the warning."
            )
        logger.warning(
            "Open Targets snapshot %s is partial (%s): an absent row below may mean the part holding it "
            "was not read, and no existing row is replaced.",
            dataset,
            described,
        )
    complete = {answer: read_is_complete(release, datasets) is True for answer, datasets in READS.items()}

    if write:
        require_sources_file(spec_dir, error=OpenTargetsError)
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=OpenTargetsError)
    if not resolution_path.exists():
        raise OpenTargetsError(
            f"no resolution.csv in {spec_dir}: this pass reads resolved coordinates, so run "
            f"`just-dna-enricher enrich` first."
        )
    resolution_rows = overlaid_input_rows(
        spec_dir, "resolution.csv", _existing(resolution_path, ResolutionRow), error=OpenTargetsError
    )
    alleles, unstated, unsettled, off_build = _alleles(resolution_rows)
    # A row with neither an ALT nor an rsID names a position, not an allele: nothing is asked for it.
    no_rsid = sorted({entry[0] for entry in unstated if not entry[1]})
    unstated = [entry for entry in unstated if entry[1]]
    if off_build:
        logger.warning(
            "Open Targets pass skipped %d variant(s) resolved on a build other than %s: the release is "
            "GRCh38-only, and a coordinate from another build would name a different variant. "
            "Examples: %s",
            len(off_build),
            OPENTARGETS_GENOME_BUILD,
            off_build[:3],
        )

    result = OpenTargetsResult(dataset=dataset, off_build=off_build, partial=partial)
    fetched_at = now_utc_iso()
    con = _connect(resolved)
    try:
        # ── rows that state no ALT: the release's allele, when it names exactly one for the rsID ──
        supplied: list[Allele] = []
        withheld: list[str] = []
        absent: list[str] = []
        unasked: list[str] = []
        if unstated:
            columns = {d[0] for d in con.execute("SELECT * FROM variants LIMIT 0").description}
            if "rs_ids" in columns:
                supplied, withheld, absent = _supply_alleles(con, unstated)
            elif mode == "strict":
                raise OpenTargetsError(
                    f"strict Open Targets enrichment: {len(unstated)} resolution row(s) state an rsID and "
                    f"no ALT, and the snapshot at {resolved} was built before its allele table carried "
                    f"rsIDs, so which allele they name cannot be asked. Rebuild it with `opentargets "
                    f"build`, or use mode='best_effort'."
                )
            else:
                unasked = sorted({key for key, *_ in unstated})
        withheld = sorted(set(withheld) | set(unsettled))
        # A key with a stated ALT on another of its rows is still answered for that allele, as it was
        # before no-ALT rows were read; only a key with nothing else to ask about is held back.
        blocked = set(no_rsid) | set(withheld) | set(unasked)
        supplied = [entry for entry in supplied if entry[0] not in blocked]
        stated = {entry[0] for entry in alleles}
        held = blocked - stated
        alleles = [entry for entry in dict.fromkeys(alleles + supplied) if entry[0] not in held]
        result.allele_supplied = sorted({entry[0] for entry in supplied})
        result.allele_unstated_withheld = withheld
        result.allele_unstated_no_rsid = no_rsid
        result.allele_unstated_unasked = unasked
        probe_table(
            con,
            "wanted",
            [
                ("variant_key", "VARCHAR"),
                ("chrom", "VARCHAR"),
                ("position", "BIGINT"),
                ("ref", "VARCHAR"),
                ("alt", "VARCHAR"),
            ],
            [(key, chrom, start, ref, alt) for key, _rsid, chrom, start, ref, alt in alleles],
        )
        matched = con.execute(
            "SELECT w.variant_key, v.variant_id FROM wanted w JOIN variants v "
            "ON v.chrom = w.chrom AND v.position = w.position AND v.ref = w.ref AND v.alt = w.alt "
            "ORDER BY w.variant_key, v.variant_id"
        ).fetchall()
        ids_by_key: dict[str, list[str]] = {}
        for key, variant_id in matched:
            ids_by_key.setdefault(key, []).append(variant_id)
        asked = sorted({key for key, *_ in alleles} | (set(absent) - held))
        rsid_by_key = {key: rsid for key, rsid, *_ in alleles if rsid}
        result.asked = asked
        unmatched = sorted(set(asked) - set(ids_by_key))
        if dataset_complete(release, "variant") is True:
            result.not_in_release = unmatched
        else:
            result.not_read = unmatched
        keys_by_id: dict[str, list[str]] = {}
        for key, ids in ids_by_key.items():
            for variant_id in ids:
                keys_by_id.setdefault(variant_id, []).append(key)

        # ── consequences: one release allele per module variant, or the variant's rows would collide ──
        single = {key: ids[0] for key, ids in ids_by_key.items() if len(ids) == 1}
        result.allele_ambiguous = sorted(key for key, ids in ids_by_key.items() if len(ids) > 1)
        if single:
            probe_table(
                con, "single", [("variant_key", "VARCHAR"), ("variant_id", "VARCHAR")], sorted(single.items())
            )
            for key, transcript, gene_id, gene, so_ids, impact, mane, canonical in con.execute(
                "SELECT s.variant_key, c.transcript, c.gene_id, c.gene, c.consequence_so_ids, c.impact, "
                "c.mane_select, c.canonical FROM single s JOIN consequences c ON c.variant_id = s.variant_id "
                "ORDER BY s.variant_key, c.transcript"
            ).fetchall():
                result.consequences.append(
                    ConsequenceRow(
                        variant_key=key,
                        transcript=transcript,
                        rsid=rsid_by_key.get(key),
                        gene_id=gene_id,
                        gene=gene,
                        consequence_so_ids=so_ids or None,
                        impact=impact,
                        mane_select=mane,
                        canonical=canonical,
                        dataset=dataset,
                        source=SOURCE_NAME,
                        fetched_at=fetched_at,
                    )
                )

        # ── the credible sets a module variant is a member of: L2G and coloc ──
        all_ids = sorted(keys_by_id)
        probe_table(con, "ids", [("variant_id", "VARCHAR")], [(i,) for i in all_ids])
        memberships_by_locus = con.execute(
            "SELECT DISTINCT m.study_locus_id, m.variant_id, cs.study_id, cs.lead_variant_id "
            "FROM members m JOIN ids ON ids.variant_id = m.variant_id "
            "JOIN credible_sets cs ON cs.study_locus_id = m.study_locus_id "
            "ORDER BY m.study_locus_id, m.variant_id"
        ).fetchall()
        # Two module keys naming one release allele are withheld rather than written twice, and counted,
        # whether or not that allele is in any set: in every set either key is in (a multi-ALT key's
        # other allele included). The other keys of a set keep their rows.
        shared = {key for keys in keys_by_id.values() if len(keys) > 1 for key in keys}
        # `locus_info` is `{study locus: (study, lead)}`, `member_keys` `{study locus: module keys that are
        # members, sorted}`. A key whose two release alleles sit in one set is one member of it, not two.
        locus_info: dict[str, tuple[str | None, str]] = {}
        member_sets: dict[str, set[str]] = {}
        for locus, variant_id, study, lead_id in memberships_by_locus:
            keys = set(keys_by_id.get(variant_id, [])) - shared
            if keys:
                locus_info[locus] = (study, lead_id)
                member_sets.setdefault(locus, set()).update(keys)
        member_keys = {locus: sorted(keys) for locus, keys in member_sets.items()}
        result.shared_allele_keys = sorted(shared)
        if locus_info:
            probe_table(
                con, "loci", [("study_locus_id", "VARCHAR")], [(locus,) for locus in sorted(locus_info)]
            )
            for locus, gene_id, score in con.execute(
                "SELECT l.study_locus_id, l.gene_id, l.l2g_score FROM l2g l "
                "JOIN loci ON loci.study_locus_id = l.study_locus_id ORDER BY l.study_locus_id, l.gene_id"
            ).fetchall():
                study, lead_id = locus_info[locus]
                for key in member_keys[locus]:
                    result.locus_to_gene.append(
                        LocusToGeneRow(
                            study_locus_id=locus,
                            gene_id=gene_id,
                            variant_key=key,
                            lead_variant_id=lead_id,
                            study_accession=study,
                            l2g_score=score,
                            dataset=dataset,
                            source=SOURCE_NAME,
                            fetched_at=fetched_at,
                        )
                    )
            for row in con.execute(
                "SELECT c.study_locus_id, c.right_study_locus_id, c.right_study_id, c.right_study_type, "
                "c.right_gene_id, c.right_biosample_id, c.method, c.h4, c.clpp, c.colocalising_variants "
                "FROM coloc c JOIN loci ON loci.study_locus_id = c.study_locus_id "
                "ORDER BY c.study_locus_id, c.right_study_locus_id"
            ).fetchall():
                (
                    locus,
                    right_locus,
                    right_study,
                    right_type,
                    right_gene,
                    biosample,
                    method,
                    h4,
                    clpp,
                    colocalising,
                ) = row
                study, _lead_id = locus_info[locus]
                if method is None:
                    # A statistic with no method is refused by `ColocalisationRow` (RM366); the pair is
                    # kept and its numbers withheld. The release that was measured has none (0 of
                    # 79,887,470 rows), so this is the shape the next release may take, not this one.
                    h4 = clpp = None
                for key in member_keys[locus]:
                    result.colocalisations.append(
                        ColocalisationRow(
                            study_locus_id=locus,
                            right_study_locus_id=right_locus,
                            variant_key=key,
                            study_accession=study,
                            right_study_id=right_study,
                            right_study_type=right_type,
                            right_gene_id=right_gene,
                            right_biosample_id=biosample,
                            method=method,
                            h4=h4,
                            clpp=clpp,
                            colocalising_variants=colocalising,
                            dataset=dataset,
                            source=SOURCE_NAME,
                            fetched_at=fetched_at,
                        )
                    )

        # ── RM239: the posterior on gwas_effects.csv ──
        gwas_path = sidecar_path(spec_dir, "gwas_effects.csv", error=OpenTargetsError)
        gwas_rows: list[GwasEffectRow] = _existing(gwas_path, GwasEffectRow)
        accessions = sorted({r.study_accession for r in gwas_rows if r.study_accession})
        studies_with_sets: set[str] = set()
        memberships: dict[tuple[str, str], set[tuple[float, str | None]]] = {}
        if accessions:
            probe_table(con, "studies", [("study_id", "VARCHAR")], [(a,) for a in accessions])
            studies_with_sets = {
                s
                for (s,) in con.execute(
                    "SELECT DISTINCT cs.study_id FROM credible_sets cs JOIN studies ON studies.study_id = cs.study_id"
                ).fetchall()
            }
            for variant_id, study, posterior, method in con.execute(
                "SELECT m.variant_id, cs.study_id, m.posterior_probability, cs.fine_mapping_method "
                "FROM members m JOIN ids ON ids.variant_id = m.variant_id "
                "JOIN credible_sets cs ON cs.study_locus_id = m.study_locus_id "
                "JOIN studies ON studies.study_id = cs.study_id "
                # A member with no posterior answers nothing; it is not a value to fill or to contest.
                "WHERE m.posterior_probability IS NOT NULL"
            ).fetchall():
                for key in keys_by_id.get(variant_id, []):
                    memberships.setdefault((key, study), set()).add((posterior, method))
    except duckdb.Error as exc:
        # A snapshot whose tables do not read (a file missing, a part truncated) is this pass's failure,
        # stated as one, never a duckdb traceback.
        raise OpenTargetsError(f"the Open Targets snapshot at {resolved} could not be read: {exc}") from exc
    finally:
        con.close()

    counts = result.posterior
    asked_keys = set(result.asked)
    updated: list[GwasEffectRow] = []
    for row in gwas_rows:
        if not row.study_accession:
            counts.no_study += 1
            updated.append(row)
            continue
        if row.variant_key in held:
            counts.allele_withheld += 1
            updated.append(row)
            continue
        if row.variant_key not in asked_keys:
            counts.not_looked_up += 1
            updated.append(row)
            continue
        if not complete["gwas_effects.csv"]:
            # Neither an absent value nor a single one is an answer from a snapshot not read whole: a
            # set in an unread part may hold the row's value, or contest the one read (RM361).
            counts.not_read += 1
            updated.append(row)
            continue
        values: set[tuple[float, str | None]] = set()
        if row.variant_key in result.not_in_release:
            counts.variant_not_in_release += 1
        elif row.study_accession not in studies_with_sets:
            counts.study_without_credible_set += 1
        else:
            values = memberships.get((row.variant_key, row.study_accession), set())
            if not values:
                counts.not_in_credible_set += 1
            elif len(values) > 1:
                counts.contested += 1
        if len(values) == 1 and next(iter(values))[1] is None:
            counts.method_missing += 1
            values = set()
        if len(values) == 1:
            posterior, method = next(iter(values))
            counts.filled += 1
            # Validated, not `model_copy`'d: the bounds and the finite check run on what is written.
            updated.append(
                GwasEffectRow.model_validate(
                    {**row.model_dump(), "posterior_probability": posterior, "fine_mapping_method": method}
                )
            )
        else:
            updated.append(
                GwasEffectRow.model_validate(
                    {**row.model_dump(), "posterior_probability": None, "fine_mapping_method": None}
                )
            )
    result.gwas_effects = updated
    if gwas_rows:
        logger.info(
            "Open Targets posterior on gwas_effects.csv: %d filled; left empty: %d study without a "
            "credible set, %d variant not in the study's set, %d contested (several sets, different "
            "values), %d with no fine-mapping method in the release, %d variant not in the release; "
            "untouched: %d naming no study, %d not looked up, %d against a snapshot not read whole.",
            counts.filled,
            counts.study_without_credible_set,
            counts.not_in_credible_set,
            counts.contested,
            counts.method_missing,
            counts.variant_not_in_release,
            counts.no_study,
            counts.not_looked_up,
            counts.not_read,
        )
    if result.shared_allele_keys:
        logger.warning(
            "Open Targets pass withheld the L2G and coloc rows of %d module key(s) that share one "
            "release allele with another key: one allele stated under two keys is a module defect to "
            "name, not a fact to write twice. Examples: %s",
            len(result.shared_allele_keys),
            result.shared_allele_keys[:3],
        )
    if result.allele_supplied:
        logger.warning(
            "Open Targets supplied the ALT of %d variant(s) whose resolution row states none: the release "
            "names exactly one allele carrying the row's rsID at its position, and every row written for "
            "them is of that allele, which the module did not author (resolution.csv is not changed). "
            "Examples: %s",
            len(result.allele_supplied),
            result.allele_supplied[:3],
        )
    if result.allele_unstated_withheld:
        logger.warning(
            "Open Targets pass withheld %d variant(s) whose resolution row states no ALT: the release holds "
            "several alleles at the position that may carry the row's rsID (or the only one states no "
            "rsID, or sits on another REF), or the row's rsID is itself a pick among several "
            "(status ambiguous); one is never picked. State the ALT in resolution.csv. Examples: %s",
            len(result.allele_unstated_withheld),
            result.allele_unstated_withheld[:3],
        )
    if result.allele_unstated_no_rsid:
        logger.warning(
            "Open Targets pass skipped %d variant(s) whose resolution row states neither an ALT nor an "
            "rsID: a position alone names no allele. Examples: %s",
            len(result.allele_unstated_no_rsid),
            result.allele_unstated_no_rsid[:3],
        )
    if result.allele_unstated_unasked:
        logger.warning(
            "Open Targets pass could not ask about %d variant(s) whose resolution row states an rsID and no "
            "ALT: the snapshot was built before its allele table carried rsIDs. Nothing was asked, which "
            "is not a finding that the release holds nothing; rebuild it with `opentargets build`. "
            "Examples: %s",
            len(result.allele_unstated_unasked),
            result.allele_unstated_unasked[:3],
        )
    if result.allele_ambiguous:
        logger.warning(
            "Open Targets pass withheld consequences for %d variant(s) that resolve to several of the "
            "release's alleles: their per-transcript rows would share one key. Examples: %s",
            len(result.allele_ambiguous),
            result.allele_ambiguous[:3],
        )

    if write:
        # Answered-and-withheld keeps what it had (`@rederive-never-shortens`): a key whose rows this run
        # withheld is not answered for that table, so its existing rows are not replaced with nothing.
        # Nor is any key answered from datasets the snapshot did not read whole (RM361, `READS`).
        asked = set(result.asked)
        answered = {
            "locus_to_gene.csv": asked - set(result.shared_allele_keys),
            "colocalisations.csv": asked - set(result.shared_allele_keys),
            "consequences.csv": asked - set(result.allele_ambiguous),
        }
        answered = {name: keys if complete[name] else set() for name, keys in answered.items()}
        fresh = {
            "locus_to_gene.csv": (
                result.locus_to_gene,
                lambda r: (r.variant_key, r.study_locus_id, r.gene_id),
            ),
            "colocalisations.csv": (
                result.colocalisations,
                lambda r: (r.variant_key, r.study_locus_id, r.right_study_locus_id),
            ),
            "consequences.csv": (result.consequences, lambda r: (r.variant_key, r.transcript)),
        }
        for csv_name, model, layer in OWNED_TABLES:
            rows, sort_key = fresh[csv_name]
            path = sidecar_path(spec_dir, csv_name, error=OpenTargetsError)
            existing = _existing(path, model)
            if not rows and not existing:
                continue
            merged = _replace_answered(existing, rows, answered[csv_name], sort_key)
            setattr(result, csv_name.removesuffix(".csv"), merged)
            # The licence row lands inside this table's commit, and only when this run contributed a
            # row to it (`@write-the-sourcerow`, `@licence-row-inside-the-commit`).
            this_run = {id(row) for row in rows}
            kept = sum(1 for row in merged if id(row) not in this_run)
            _write(
                merged,
                model,
                path,
                _licence(spec_dir, layer, dataset, declared_use, answered=len(merged) - kept, kept=kept)
                if rows
                else None,
            )
        if gwas_rows and updated != gwas_rows:
            # A posterior an earlier run filled and this one left alone states no release (`_licence`).
            untouched = {id(row) for row in gwas_rows}
            kept = sum(1 for row in updated if id(row) in untouched and row.posterior_probability is not None)
            _write(
                updated,
                GwasEffectRow,
                gwas_path,
                _licence(spec_dir, GWAS_LAYER, dataset, declared_use, answered=counts.filled, kept=kept)
                if counts.filled
                else None,
            )
    return result


def _licence(
    spec_dir: Path, layer: str, dataset: str, declared_use: str, *, answered: int, kept: int
) -> Callable[[], None]:
    """The licence row for `layer`, labelled by the table rather than by this run alone (RM373).

    These tables carry no per-row release, so a row this run answered states this run's `dataset` and a
    row an earlier run wrote and this one kept states none: the label recorded before this run may be a
    pre-0.8 first run's, which `merge_sources_file` kept whatever the table later held, so it is not
    evidence about the kept rows. One kept row withholds the table's label until a run re-answers it.
    """

    def _commit_licence() -> None:
        record_table_sources(
            {OPENTARGETS_TERMS.source: [dataset] * answered + [None] * kept},
            layer,
            spec_dir,
            error=OpenTargetsError,
            # A routine merge declares nothing, so it retires no licence row (RM383).
            answered_every_row=False,
            declared_use=declared_use,
        )

    return _commit_licence


# ── the keyed functions (0.9, RM431 ask 6) ──────────────────────────────────────────────────────
#
# One SQL body per question, over a connection exposing the view it names: the local reader runs it over
# the snapshot's files, and a remote answer's rows (`remote.RemoteSnapshots.lookup`, the tables below) run
# it through `_variants_from_rows` / `_consequences_from_rows`, so a key reads alike on every route.

#: The allele table's columns `lookup_variants` answers, typed for a remote answer's rows.
_VARIANT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("variant_id", "VARCHAR"),
    ("chrom", "VARCHAR"),
    ("position", "BIGINT"),
    ("ref", "VARCHAR"),
    ("alt", "VARCHAR"),
    ("rs_ids", "VARCHAR[]"),
)
#: The per-transcript consequence columns, and the credible-set membership columns.
_CONSEQUENCE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("variant_id", "VARCHAR"),
    ("transcript", "VARCHAR"),
    ("gene_id", "VARCHAR"),
    ("gene", "VARCHAR"),
    ("consequence_so_ids", "VARCHAR"),
    ("impact", "VARCHAR"),
    ("mane_select", "VARCHAR"),
    ("canonical", "BOOLEAN"),
)
_MEMBER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("study_locus_id", "VARCHAR"),
    ("variant_id", "VARCHAR"),
    ("posterior_probability", "DOUBLE"),
)
#: The tables a remote route names (`remote.table_name` of the snapshot's files), and the `table` value
#: each row of `lookup_consequences` carries to say which one it is.
REMOTE_VARIANTS_TABLE = "variants"
REMOTE_CONSEQUENCES_TABLE = "consequences"
REMOTE_MEMBERS_TABLE = "credible_set_members"


def _select_list(con: duckdb.DuckDBPyConnection, view: str, columns: Sequence[tuple[str, str]]) -> str:
    """`columns` as a select list over `view`; one the view lacks reads as a typed `NULL`.

    A snapshot built before the allele table carried `rs_ids` still answers, with that cell `None`, so
    a row has the same keys on every snapshot and on every route.
    """
    present = {d[0] for d in con.execute(f"SELECT * FROM {view} LIMIT 0").description}
    return ", ".join(
        f'"{name}"' if name in present else f'CAST(NULL AS {sql_type}) AS "{name}"'
        for name, sql_type in columns
    )


def _wanted_positions(positions: Sequence[tuple[str, int]]) -> dict[tuple[str, int], list[tuple[str, int]]]:
    """`(chrom, position)` as the release spells it (`normalize_chrom`: no `chr`, `MT`) → the keys asked so."""
    wanted: dict[tuple[str, int], list[tuple[str, int]]] = {}
    for chrom, position in positions:
        bare = normalize_chrom(str(chrom))
        if bare is None:
            raise ValueError(f"{chrom!r} names no chromosome")
        asked = (chrom, int(position))
        keys = wanted.setdefault((bare, int(position)), [])
        if asked not in keys:
            keys.append(asked)
    return wanted


def _variant_keys(positions: Sequence[tuple[str, int]]) -> dict[str, list]:
    """The keys a remote route is asked for `positions`: `chrom` and `start` paired, as the release spells them."""
    wanted = list(_wanted_positions(positions))
    return {"chrom": [chrom for chrom, _ in wanted], "start": [position for _, position in wanted]}


def _variants_over(
    con: duckdb.DuckDBPyConnection, positions: Sequence[tuple[str, int]]
) -> dict[tuple[str, int], list[dict]]:
    """`lookup_variants`' query over a connection exposing `variants`: the one copy."""
    wanted = _wanted_positions(positions)
    if not wanted:
        return {}
    probe_table(con, "_wanted_positions", [("chrom", "VARCHAR"), ("position", "BIGINT")], list(wanted))
    # The positions and chromosomes as literals too: a join alone prunes no row group of the allele
    # table, and a bound integer prunes none either (RM430's measurement). The table is sorted by chrom
    # then position, so the two together leave about one row group per position (0.03 s against 0.08 s
    # for position alone, on 26.09's 128). `int()` and the quote escape make each literal safe.
    starts = ", ".join(str(int(position)) for _, position in wanted)
    chroms = ", ".join("'" + chrom.replace("'", "''") + "'" for chrom in sorted({c for c, _ in wanted}))
    cursor = con.execute(
        f"SELECT v.* FROM (SELECT {_select_list(con, 'variants', _VARIANT_COLUMNS)} FROM variants "
        f"WHERE position IN ({starts}) AND chrom IN ({chroms})) v "
        "JOIN _wanted_positions w ON v.chrom = w.chrom AND v.position = w.position "
        "ORDER BY v.chrom, v.position, v.ref, v.alt, v.variant_id"
    )
    columns = [d[0] for d in cursor.description]
    answer: dict[tuple[str, int], list[dict]] = {}
    for values in cursor.fetchall():
        row = dict(zip(columns, values, strict=True))
        for asked in wanted[(str(row["chrom"]), int(row["position"]))]:
            answer.setdefault(asked, []).append(dict(row))
    return answer


def lookup_variants(
    reference: Path, positions: Sequence[tuple[str, int]]
) -> dict[tuple[str, int], list[dict]]:
    """`(chrom, position)` → every allele the release's allele table states there, as plain dicts (RM431).

    Joins on chrom + position, never on `variant_id`, whose string prunes no row group of the allele
    table (about 55 MB read for one lookup, the registry's measurement). A position is keyed as it was
    asked (`chr6` and `6` are two keys with the same rows) and compared as the release spells it
    (`normalize_chrom`). Each row is the allele table's own columns: `variant_id`, `chrom`, `position`,
    `ref`, `alt`, `rs_ids` (a list; `None` on a snapshot built before the table carried it). A position
    the release states nothing at is not a key; a snapshot that cannot be read raises
    `OpenTargetsError`, never an empty answer. Read-only, and it never fetches.
    """
    if not positions:
        return {}
    con = _connect(reference, ("variants",))
    try:
        return _variants_over(con, positions)
    finally:
        con.close()


def _variants_from_rows(
    rows: Sequence[Mapping[str, object]], positions: Sequence[tuple[str, int]]
) -> dict[tuple[str, int], list[dict]]:
    """`lookup_variants`' answer over a remote answer's rows of `REMOTE_VARIANTS_TABLE`."""
    con = _typed_rows_connection(("variants", _VARIANT_COLUMNS, rows))
    try:
        return _variants_over(con, positions)
    finally:
        con.close()


def _variant_ids(variant_ids: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(v).strip() for v in variant_ids if str(v).strip()))


def _consequences_over(con: duckdb.DuckDBPyConnection, variant_ids: Sequence[str]) -> dict[str, list[dict]]:
    """`lookup_consequences`' queries over a connection exposing `consequences` and `members`: the one copy."""
    ids = _variant_ids(variant_ids)
    if not ids:
        return {}
    marks = ", ".join("?" for _ in ids)
    answer: dict[str, list[dict]] = {}
    for view, table, columns, order in (
        ("consequences", REMOTE_CONSEQUENCES_TABLE, _CONSEQUENCE_COLUMNS, "variant_id, transcript"),
        (
            "members",
            REMOTE_MEMBERS_TABLE,
            _MEMBER_COLUMNS,
            "variant_id, study_locus_id, posterior_probability",
        ),
    ):
        cursor = con.execute(
            f"SELECT {_select_list(con, view, columns)} FROM {view} WHERE variant_id IN ({marks}) ORDER BY {order}",
            ids,
        )
        names = [d[0] for d in cursor.description]
        for values in cursor.fetchall():
            row = dict(zip(names, values, strict=True))
            answer.setdefault(str(row["variant_id"]), []).append({"table": table, **row})
    return {variant_id: answer[variant_id] for variant_id in ids if variant_id in answer}


def lookup_consequences(reference: Path, variant_ids: Sequence[str]) -> dict[str, list[dict]]:
    """`variant_id` → its per-transcript consequences, then its GWAS credible-set memberships (RM431).

    The ids are the release's own (`lookup_variants` answers them). Each row is a plain dict carrying
    `table`, `"consequences"` (the columns of `consequences.csv`'s source: `transcript`, `gene_id`,
    `gene`, `consequence_so_ids`, `impact`, `mane_select`, `canonical`) or `"credible_set_members"`
    (`study_locus_id`, `posterior_probability`), so the two tables' rows stay apart in one list:
    consequences first, by transcript, then memberships, by study locus. An id the release holds neither
    for is not a key; a snapshot that cannot be read raises `OpenTargetsError`. Read-only.
    """
    if not variant_ids:
        return {}
    con = _connect(reference, ("consequences", "members"))
    try:
        return _consequences_over(con, variant_ids)
    finally:
        con.close()


def _consequences_from_rows(
    consequences: Sequence[Mapping[str, object]],
    members: Sequence[Mapping[str, object]],
    variant_ids: Sequence[str],
) -> dict[str, list[dict]]:
    """`lookup_consequences`' answer over a remote answer's rows of the two tables."""
    con = _typed_rows_connection(
        ("consequences", _CONSEQUENCE_COLUMNS, consequences), ("members", _MEMBER_COLUMNS, members)
    )
    try:
        return _consequences_over(con, variant_ids)
    finally:
        con.close()


def summarise(result: OpenTargetsResult) -> dict:
    """The counts a CLI prints, JSON-ready."""
    return {
        "dataset": result.dataset,
        "skipped": result.skipped,
        "asked": len(result.asked),
        "not_in_release": len(result.not_in_release),
        "not_read": len(result.not_read),
        "off_build": len(result.off_build),
        "allele_ambiguous": len(result.allele_ambiguous),
        "shared_allele_keys": len(result.shared_allele_keys),
        "allele_supplied": len(result.allele_supplied),
        "allele_unstated_withheld": len(result.allele_unstated_withheld),
        "allele_unstated_no_rsid": len(result.allele_unstated_no_rsid),
        "allele_unstated_unasked": len(result.allele_unstated_unasked),
        "locus_to_gene": len(result.locus_to_gene),
        "colocalisations": len(result.colocalisations),
        "consequences": len(result.consequences),
        "posterior": result.posterior.__dict__,
        "partial": {name: list(pair) for name, pair in result.partial.items()},
    }


def summary_json(result: OpenTargetsResult) -> str:
    return json.dumps(summarise(result), indent=2, sort_keys=True)
