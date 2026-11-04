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

**Answered replaces, could-not-ask keeps** (`@rederive-never-shortens`): a variant this run looked up
has its rows replaced by the snapshot's answer, and a variant it could not look up (off-build,
unresolved) keeps whatever rows it had.
"""

import csv
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.consequences import ConsequenceRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.layout import atomic_writer
from just_dna_format.locus_genes import ColocalisationRow, LocusToGeneRow
from just_dna_format.normalize import now_utc_iso
from just_dna_format.resolution import ResolutionRow
from just_dna_format.snapshot import read_release
from pydantic import BaseModel

from just_dna_enricher.licensing import (
    OPENTARGETS_TERMS,
    merge_sources_file,
    overlaid_input_rows,
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
    VARIANTS_FILE,
)
from just_dna_enricher.resolver import probe_table

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
    #: Resolved on another build, so not asked.
    off_build: list[str] = field(default_factory=list)
    #: Resolved to several of the release's alleles, so its per-transcript rows would collide: withheld.
    allele_ambiguous: list[str] = field(default_factory=list)
    #: Module keys sharing one release allele with another key: the rows of the study loci that allele
    #: is a member of are withheld for those keys and the keys are named. With `variant_key` in the key
    #: the two keys' rows would no longer collide; the arm is kept because one release allele stated
    #: twice under two module keys is a module defect to name, not a fact to write twice.
    lead_key_ambiguous: list[str] = field(default_factory=list)
    #: Datasets the snapshot read only some parts of, `{dataset: (read, total)}`.
    partial: dict[str, tuple[int, int]] = field(default_factory=dict)


def _quoted(path: Path) -> str:
    return str(path).replace("'", "''")


def _connect(snapshot: Path) -> duckdb.DuckDBPyConnection:
    """Views over the snapshot's tables. The paths are our own cache's, quoted defensively."""
    data = snapshot / "data"
    con = duckdb.connect(":memory:")
    for view, name in (
        ("variants", VARIANTS_FILE),
        ("consequences", CONSEQUENCES_GLOB),
        ("credible_sets", CREDIBLE_SETS_FILE),
        ("members", MEMBERS_GLOB),
        ("l2g", L2G_FILE),
        ("coloc", COLOC_GLOB),
    ):
        try:
            con.execute(f"CREATE VIEW {view} AS SELECT * FROM read_parquet('{_quoted(data / name)}')")
        except duckdb.Error as exc:
            con.close()
            raise OpenTargetsError(
                f"the Open Targets snapshot at {snapshot} has no readable `{name}`: {exc}"
            ) from exc
    return con


def _partial_datasets(release: dict) -> dict[str, tuple[int, int]]:
    read = release.get("parts_read") or {}
    total = release.get("parts_total") or {}
    return {
        dataset: (int(read[dataset]), int(total[dataset]))
        for dataset in sorted(read)
        if dataset in total and int(read[dataset]) < int(total[dataset])
    }


def _alleles(rows: list[ResolutionRow]) -> tuple[list[tuple[str, str | None, str, int, str, str]], list[str]]:
    """`(variant_key, rsid, chrom, start, ref, alt)` per resolved ALT, and the keys left out as off-build."""
    seen: set[tuple] = set()
    out: list[tuple[str, str | None, str, int, str, str]] = []
    off_build: list[str] = []
    for row in rows:
        if (
            row.status == "not_found"
            or row.chrom is None
            or row.start is None
            or row.ref is None
            or not row.alts
        ):
            continue
        if row.genome_build != OPENTARGETS_GENOME_BUILD:
            off_build.append(row.variant_key)
            continue
        for alt in (a.strip() for a in row.alts.split(",")):
            entry = (row.variant_key, row.rsid, row.chrom, row.start, row.ref, alt)
            if alt and entry not in seen:
                seen.add(entry)
                out.append(entry)
    return out, sorted(set(off_build))


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
    record = read_release(resolved)
    release = record.model_dump() if record is not None else {}
    dataset = release.get("dataset") or ""
    if not dataset:
        raise OpenTargetsError(
            f"the Open Targets snapshot at {resolved} has no release label in release.json"
        )
    partial = _partial_datasets(release)
    if not release.get("parts_total"):
        if mode == "strict":
            raise OpenTargetsError(
                f"strict Open Targets enrichment: the snapshot at {resolved} does not record how many "
                f"parts each dataset has, so whether it holds the whole release is unknown. Build it "
                f"with `opentargets build` (which records the totals), or use mode='best_effort'."
            )
        logger.warning(
            "Open Targets snapshot %s does not record how many parts each dataset has, so whether it "
            "is partial is unknown: an absent row below may mean a part was not read.",
            dataset,
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
            "was not read.",
            dataset,
            described,
        )

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
    alleles, off_build = _alleles(resolution_rows)
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
        asked = sorted({key for key, *_ in alleles})
        rsid_by_key = {key: rsid for key, rsid, *_ in alleles if rsid}
        result.asked = asked
        result.not_in_release = sorted(set(asked) - set(ids_by_key))
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
        # `locus_info` is `{study locus: (study, lead)}`, `member_keys` `{study locus: module keys that are
        # members}`. A key whose two release alleles sit in one set is one member of it, not two.
        locus_info: dict[str, tuple[str | None, str]] = {}
        member_keys: dict[str, set[str]] = {}
        shared: set[str] = set()
        for locus, variant_id, study, lead_id in memberships_by_locus:
            keys = keys_by_id.get(variant_id, [])
            if len(keys) > 1:
                shared.update(keys)
            locus_info[locus] = (study, lead_id)
            member_keys.setdefault(locus, set()).update(keys)
        # Two module keys naming one release allele are withheld rather than written twice, and counted,
        # in every set (a multi-ALT key's other allele included); the other keys of a set keep their rows.
        for locus in list(member_keys):
            member_keys[locus] -= shared
            if not member_keys[locus]:
                del member_keys[locus], locus_info[locus]
        result.lead_key_ambiguous = sorted(shared)
        if locus_info:
            probe_table(
                con, "loci", [("study_locus_id", "VARCHAR")], [(locus,) for locus in sorted(locus_info)]
            )
            for locus, gene_id, score in con.execute(
                "SELECT l.study_locus_id, l.gene_id, l.l2g_score FROM l2g l "
                "JOIN loci ON loci.study_locus_id = l.study_locus_id ORDER BY l.study_locus_id, l.gene_id"
            ).fetchall():
                study, lead_id = locus_info[locus]
                for key in sorted(member_keys[locus]):
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
                for key in sorted(member_keys[locus]):
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
        if row.variant_key not in asked_keys:
            counts.not_looked_up += 1
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
            "values), %d variant not in the release; untouched: %d naming no study, %d not looked up.",
            counts.filled,
            counts.study_without_credible_set,
            counts.not_in_credible_set,
            counts.contested,
            counts.variant_not_in_release,
            counts.no_study,
            counts.not_looked_up,
        )
    if result.lead_key_ambiguous:
        logger.warning(
            "Open Targets pass withheld the L2G and coloc rows of %d module key(s) that share one "
            "release allele with another key: one allele stated under two keys is a module defect to "
            "name, not a fact to write twice. Examples: %s",
            len(result.lead_key_ambiguous),
            result.lead_key_ambiguous[:3],
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
        asked = set(result.asked)
        answered = {
            "locus_to_gene.csv": asked - set(result.lead_key_ambiguous),
            "colocalisations.csv": asked - set(result.lead_key_ambiguous),
            "consequences.csv": asked - set(result.allele_ambiguous),
        }
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
            _write(merged, model, path, _licence(spec_dir, layer, dataset, declared_use) if rows else None)
        if gwas_rows and updated != gwas_rows:
            _write(
                updated,
                GwasEffectRow,
                gwas_path,
                _licence(spec_dir, GWAS_LAYER, dataset, declared_use) if counts.filled else None,
            )
    return result


def _licence(spec_dir: Path, layer: str, dataset: str, declared_use: str) -> Callable[[], None]:
    return lambda: merge_sources_file(
        [OPENTARGETS_TERMS.row(layer, declared_use=declared_use, dataset=dataset)],
        spec_dir,
        error=OpenTargetsError,
    )


def summarise(result: OpenTargetsResult) -> dict:
    """The counts a CLI prints, JSON-ready."""
    return {
        "dataset": result.dataset,
        "skipped": result.skipped,
        "asked": len(result.asked),
        "not_in_release": len(result.not_in_release),
        "off_build": len(result.off_build),
        "allele_ambiguous": len(result.allele_ambiguous),
        "lead_key_ambiguous": len(result.lead_key_ambiguous),
        "locus_to_gene": len(result.locus_to_gene),
        "colocalisations": len(result.colocalisations),
        "consequences": len(result.consequences),
        "posterior": result.posterior.__dict__,
        "partial": {name: list(pair) for name, pair in result.partial.items()},
    }


def summary_json(result: OpenTargetsResult) -> str:
    return json.dumps(summarise(result), indent=2, sort_keys=True)
