"""Building the SNP-core and frequency parquets: weights, annotations, studies, frequencies."""

from typing import Any

import polars as pl
from just_dna_format.base import DEFAULT_GENOME_BUILD
from just_dna_format.frequency import FrequencyRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import ModuleSpecConfig, StudyRow, VariantRow
from just_dna_format.vocab import OUTCOME_STRIP_CELLS

from just_dna_compiler.compiler.subjects import ResolutionTable, row_positions
from just_dna_compiler.compiler.tables import _polars_type, _split_genotype, study_coordinate_key
from just_dna_compiler.compiler.vrs_columns import VrsIds, resolution_key

# ── Parquet builders ───────────────────────────────────────────────────────────


class _StudyIndex:
    """The module's study rows, indexed once by the two identifiers a study can name a variant by.

    "Supporting" is the orphan check's rule — the same rsid, or the same `chrom:start:ref`
    (`tables.study_coordinate_key`, shared with `_cross_validate_studies`). Frozen-key equality would
    contribute nothing for an rsid-authored study of a coordinate-keyed variant, and silently, since a
    locus with no supporting rows reads as unknown. Built once per compile, so a module with thousands
    of genotype rows and study rows costs two dict lookups per weights row, not a scan.
    """

    def __init__(
        self,
        studies: list[StudyRow],
        resolution: ResolutionTable | None = None,
        genome_build: str = DEFAULT_GENOME_BUILD,
    ) -> None:
        self.studies = studies
        self.resolution = resolution
        self.genome_build = genome_build
        self.by_rsid: dict[str, list[int]] = {}
        self.by_coord: dict[str, list[int]] = {}
        for i, s in enumerate(studies):
            if s.rsid is not None:
                self.by_rsid.setdefault(s.rsid, []).append(i)
            coord = study_coordinate_key(s.chrom, s.start, s.ref)
            if coord is not None:
                self.by_coord.setdefault(coord, []).append(i)

    def supporting(self, variant: VariantRow) -> list[StudyRow]:
        """`variant`'s supporting study rows, in authored order (which keeps every derivation stable).

        `variant` is the post-resolution row, so a coordinate the enricher filled matches a coordinate-
        authored study too. And every spelling the variant sits at (`subjects.row_positions`, RM362
        2026-11-04): a study at the injected table's spelling of an rsID authored beside another
        spelling is about the same place, as the orphan check already says.
        """
        hits = set(self.by_rsid.get(variant.rsid or "", ()))
        for coord in row_positions(variant, self.resolution, self.genome_build):
            hits.update(self.by_coord.get(coord, ()))
        return [self.studies[i] for i in sorted(hits)]


def _locus_study_facts(studies: list[StudyRow]) -> dict[str, Any]:
    """The locus-level columns `weights.parquet` derives from a variant's study rows (0.8).

    Repeated on every genotype row of the locus: a parquet column is approximately free (P9), and a
    consumer reading one row then needs no second join.

    * `effect_unit` (RM332): the unit of the variant's effect, when every supporting study row that
      states a unit states the same one. `VariantRow` names no study, so "the matching study row" is
      undefined; unanimity is the rule that never guesses (PT2 §3 item 17). Null when none states one,
      and null when two disagree — never the first, never the most common.
    * `eur_only_evidence` (RM328): Kleene over the supporting rows' `ancestry`. False when any row states
      a code other than `EUR` (a decisive counter-example, whatever else is unstated); otherwise null
      when any row states none, or when the locus has no supporting row at all (no evidence is not
      European-only evidence); otherwise true.
    * the outcome strip (RM326): `outcome_<cell>` is true when a supporting row's `phenotype_class`
      maps to that cell in `vocab.OUTCOME_STRIP_CELLS`, and null otherwise. Never false: a locus with no
      study of an outcome is untested, not "no effect".
    """
    units = {s.effect_unit for s in studies if s.effect_unit is not None}
    eur_only: bool | None
    if any(s.ancestry and set(s.ancestry) != {"EUR"} for s in studies):
        eur_only = False
    elif not studies or any(not s.ancestry for s in studies):
        eur_only = None
    else:
        eur_only = True
    studied = {OUTCOME_STRIP_CELLS.get(s.phenotype_class or "") for s in studies}
    return {
        "effect_unit": units.pop() if len(units) == 1 else None,
        "eur_only_evidence": eur_only,
        **{f"outcome_{cell}": (True if cell in studied else None) for cell in _OUTCOME_CELLS},
    }


#: The strip's cells in column order, read off the format constant once (insertion order, deduped).
_OUTCOME_CELLS: tuple[str, ...] = tuple(dict.fromkeys(OUTCOME_STRIP_CELLS.values()))


def _build_weights(
    variants: list[VariantRow],
    config: ModuleSpecConfig,
    studies: list[StudyRow] | None = None,
    vrs: VrsIds | None = None,
    *,
    resolution: ResolutionTable | None = None,
) -> pl.DataFrame:
    """Build the weights.parquet DataFrame from validated variant rows, the locus-level columns
    derived from the module's study rows (`_locus_study_facts`), each allele's `vrs_id` recorded in
    `resolution.csv` (`vrs`, RM270; `None` when no table was read), and the injected table itself
    (`resolution`; `None` where none may be consulted), which serves two readers: the study join reads a
    variant's other spellings from it (RM362's placement), and `resolution_loci` carries the loci it
    files under each row's authored key (RM364)."""
    defaults = config.defaults
    module_name = config.module.name
    records: list[dict[str, Any]] = []
    index = _StudyIndex(studies or [], resolution, config.genome_build)
    vrs = vrs or VrsIds()
    #: Per record, the key the table files it under and what reverse's cell rebuild would write (RM364).
    authored_keys: list[str] = []
    cell_facts: list[tuple[Any, ...] | None] = []
    for v in variants:
        priority = v.priority if v.priority is not None else defaults.priority
        derived = _locus_study_facts(index.supporting(v))
        alts = v.alts.split(",") if v.alts else None
        # The key `resolution.csv` files this row under: the AUTHORED one, which an expansion's re-keyed
        # row no longer stores. One computation for both columns that read the table by it.
        authored_key = resolution_key(
            {
                "authored_ident": v.authored_ident,
                "rsid": v.rsid,
                "ref": v.ref,
                "variant_key": v.variant_key,
            },
            v.chrom,  # type: ignore[arg-type]
            v.start,  # type: ignore[arg-type]
            v.alts,
            config.genome_build,
        )
        vrs_ids, vrs_spec = vrs.lookup(authored_key, v.chrom, v.start, v.ref, alts)
        authored_keys.append(authored_key)
        cell_facts.append(
            None
            if v.chrom is None or v.start is None
            else _locus_fact(v.rsid, v.chrom, v.start, v.ref, v.alts, v.locus_index)
        )
        records.append(
            {
                "rsid": v.rsid,
                # Frozen machine identity (base.derive_variant_key), stamped at load and reassigned
                # only on resolver expansion. Carried so reverse_module can tell an authored rsid from
                # a resolved one and restore the authored shape without re-keying (Principle 7).
                "variant_key": v.variant_key,
                # Which identity columns the AUTHOR wrote. Reverse re-emits exactly these, so an
                # rsid-only row comes back rsid-only instead of carrying whatever coordinate
                # resolution filled in, and an expanded one-to-many rsid collapses back to the single
                # row it was written as. Without it `content_signature` moved on every round-trip of
                # an rsid-authored module. See COMPILER.md § Resolution.
                "authored_ident": v.authored_ident,
                # The expansion marker (0.6, RM87). A one-to-many rsID is paired with every locus it
                # resolves to, so only the member whose alleles can carry the genotype asserts
                # anything; the others are ordinary rows with a real coordinate and the module's own
                # conclusion. `locus_count > 1` is the predicate that identifies them from a single
                # row — `locus_index` alone is 0 on a non-expanded row *and* on the first member.
                # Read off the row rather than derived here, because this builder is a comprehension
                # over `v.<field>` and has no side channel; both are `exclude=True`, so they reach
                # parquet and no `content_signature`.
                "locus_index": v.locus_index,
                "locus_count": v.locus_count,
                "genotype": _split_genotype(v.genotype),
                # Phase bit: `genotype` is stored as an allele *list*, which cannot itself
                # distinguish a phased A|G from an unphased (sorted) A/G — both split to ["A","G"].
                # This flag preserves the distinction so the round-trip is lossless (ROADMAP 0.3 5b).
                "phased": "|" in v.genotype,
                "module": module_name,
                "weight": v.weight,
                "state": v.state,
                "priority": priority,
                "conclusion": v.conclusion,
                "negatives": v.negatives,
                "curator": v.curator or defaults.curator,
                "method": v.method or defaults.method,
                "chrom": v.chrom,
                "start": v.start,
                "end": v.start,
                "ref": v.ref,
                "alts": alts,
                # Tri-state: keep None distinct from False (nullable pl.Boolean). Collapsing
                # None→False lost the difference between "curator stated not-pathogenic" (False) and
                # "unstated" (None) — an authored False did not survive the round-trip, and
                # `effective_pathogenic` flipped False→None on reload (Principle 7). Matches the
                # tri-state 0.4 axes (`requires_callable`/`acmg_sf`).
                "clinvar": v.clinvar,
                "pathogenic": v.pathogenic,
                "benign": v.benign,
                "likely_pathogenic": False,
                "likely_benign": False,
                # ── 0.3 additive columns (materialized passthrough; derivations are NOT computed
                # here — see docs/COMPILER.md). ──
                "direction": v.direction,
                "stat_significance": v.stat_significance,
                "effect_size": v.effect_size,
                "effect_measure": v.effect_measure,
                "effect_allele": v.effect_allele,
                "flags": v.flags,
                "trait_efo_id": v.trait_efo_id,
                "clin_sig": v.clin_sig,
                # ── 0.4 general annotation axes (materialized passthrough). ──
                "requires_callable": v.requires_callable,
                # 0.5 (RM6): where a consumer proves callability — the pointer half of the flag above.
                "callable_from": v.callable_from,
                "acmg_sf": v.acmg_sf,
                "actionability": v.actionability,
                # 0.5.1 (RM29a): the call-confidence cofactor — where the floor is measured, and the
                # floor. Both-or-neither is a model rule, so the pair is always whole here.
                "quality_from": v.quality_from,
                "min_quality": v.min_quality,
                # ── 0.8: derived from the study rows, never authored on a variant; after every 0.7
                # column so none moves, and `reverse` reads none of them back. Named one by one, not
                # spread, so the two-halves guard in test_compiler_regression still sees each key. ──
                "effect_unit": derived["effect_unit"],
                "eur_only_evidence": derived["eur_only_evidence"],
                "outcome_healthspan": derived["outcome_healthspan"],
                "outcome_lifespan": derived["outcome_lifespan"],
                "outcome_exceptional": derived["outcome_exceptional"],
                # ── 0.8 (RM270): the id `resolution.csv` records for each ALT, parallel to `alts` with
                # a null where none is recorded, and the VRS version it was minted under. Copied, never
                # minted here (`vrs_columns`); `reverse` writes both back to `resolution.csv`. ──
                "vrs_id": vrs_ids,
                "vrs_spec": vrs_spec,
                # ── 0.8 (RM364): the loci the table files under the authored key, so `reverse`
                # rebuilds `resolution.csv` from the table's answer rather than from this row's cells,
                # which hold the author's coordinate wherever the fill left the row alone. Last. ──
                "resolution_loci": resolution_loci(authored_key, resolution or {}, config.genome_build),
            }
        )
    schema = {
        "rsid": pl.Utf8,
        "authored_ident": pl.List(pl.Utf8),
        "variant_key": pl.Utf8,
        # RM87 — see the record dict above. Hand-listed twice because `_build_weights`, unlike
        # `_build_table`, derives neither half from the model.
        "locus_index": pl.UInt32,
        "locus_count": pl.UInt32,
        "genotype": pl.List(pl.Utf8),
        "phased": pl.Boolean,
        "module": pl.Utf8,
        "weight": pl.Float64,
        "state": pl.Utf8,
        "priority": pl.Utf8,
        "conclusion": pl.Utf8,
        "negatives": pl.Utf8,
        "curator": pl.Utf8,
        "method": pl.Utf8,
        "chrom": pl.Utf8,
        "start": pl.UInt32,
        "end": pl.UInt32,
        "ref": pl.Utf8,
        "alts": pl.List(pl.Utf8),
        "clinvar": pl.Boolean,
        "pathogenic": pl.Boolean,
        "benign": pl.Boolean,
        "likely_pathogenic": pl.Boolean,
        "likely_benign": pl.Boolean,
        "direction": pl.Utf8,
        "stat_significance": pl.Utf8,
        "effect_size": pl.Float64,
        "effect_measure": pl.Utf8,
        "effect_allele": pl.Utf8,
        "flags": pl.List(pl.Utf8),
        "trait_efo_id": pl.Utf8,
        "clin_sig": pl.Utf8,
        "requires_callable": pl.Boolean,
        "callable_from": pl.Utf8,
        "acmg_sf": pl.Boolean,
        "actionability": pl.Utf8,
        "quality_from": pl.Utf8,
        "min_quality": pl.Float64,
        "effect_unit": pl.Utf8,
        "eur_only_evidence": pl.Boolean,
        "outcome_healthspan": pl.Boolean,
        "outcome_lifespan": pl.Boolean,
        "outcome_exceptional": pl.Boolean,
        "vrs_id": pl.List(pl.Utf8),
        "vrs_spec": pl.Utf8,
        "resolution_loci": pl.List(RESOLUTION_LOCUS_DTYPE),
    }
    # Kept only where the cells would not rebuild them (RM364), decided per key over every record.
    withheld = withhold_reproduced_loci(
        [record["resolution_loci"] for record in records], list(authored_keys), cell_facts
    )
    for record, cell in zip(records, withheld, strict=True):
        record["resolution_loci"] = cell
    return pl.DataFrame(records, schema=schema)


def _build_frequencies(rows: list[FrequencyRow], module_name: str) -> pl.DataFrame:
    """`frequencies.csv` → `frequencies.parquet`, materializing the derived `allele_frequency`.

    The one place this differs from the generic `_build_table`: the CSV stores AC and AN as integers
    (exact through a text round-trip) and *no* frequency, while the parquet carries a real `Float64`
    `allele_frequency` so a consumer never does the division itself. Deriving on write rather than
    storing on both sides keeps one fact in one place in the human-authorable artifact, and gives the
    machine artifact the column it wants — the same "parquet absorbs the precision, the DSL keeps the
    human shape" split the format applies everywhere else.
    """
    schema: dict[str, Any] = {"module": pl.Utf8}
    for name, f in FrequencyRow.model_fields.items():
        schema[name] = _polars_type(f.annotation)
    schema["allele_frequency"] = pl.Float64
    records = [
        {"module": module_name, **row.model_dump(), "allele_frequency": row.allele_frequency} for row in rows
    ]
    return pl.DataFrame(records, schema=schema)


def _build_annotations(variants: list[VariantRow], module_name: str) -> pl.DataFrame:
    """Build annotations.parquet, keyed on `(variant_key, genotype, conclusion, negatives)`
    (first occurrence wins).

    Keying on `variant_key` alone collapsed a genuine *poly-effect* variant — the same locus
    carrying two distinct annotations (different `conclusion`/`category`, as embryo-level / neural
    findings routinely do when `category` does not subsume the effect) — onto its first row, so the
    second row's `gene`/`phenotype`/`category` were silently overwritten on reverse (a Principle 7
    round-trip loss introduced with the `variant_key` column). The effect (`conclusion` + `negatives`)
    is part of the identity, so a row per (variant, effect) is kept.

    **`genotype` joined that key in 0.6 (RM80), reported by a consumer.** `variant_key` is not unique
    here and never could be, so every consumer had to dedup before joining — and the authored column
    that actually distinguishes the rows, the one that decides *which call this annotation applies
    to*, was in no column. A het "carrier" row and a hom "affected" row at one locus were two rows a
    reader could tell apart only by reading the prose in `conclusion`.

    **Carrying it without keying on it would have been worse than the gap**, which is why this is one
    change and not two: two genotypes sharing a conclusion (`C/T` and `T/T` both "carrier") collapse
    under the old key, so the surviving row would name one genotype while silently standing for both,
    and a consumer filtering on it would get a wrong answer instead of a missing one. With `genotype`
    in the key the dedup is provably a no-op — `(variant_key, genotype)` is `VariantRow`'s own natural
    key and `_cross_validate_variants` rejects duplicates on it — so the table is now exactly one row
    per authored variant row. It is kept rather than dropped because this function must not silently
    depend on a guarantee another function enforces.

    Carries `variant_key`/`genotype`/`conclusion`/`negatives` so the table is **self-joinable** back to
    `weights.parquet` on reverse (each weights row rebuilds the same tuple), and an explicit
    `variant_key` (rsid, else `chrom:start:ref`) so a **position-only** variant's annotation survives
    (rsid is null for such a row)."""
    seen_keys: set[tuple[str, str | None, str | None, str | None]] = set()
    records: list[dict[str, str | None]] = []
    for v in variants:
        key = (v.variant_key, v.genotype, v.conclusion, v.negatives)
        if key not in seen_keys:
            records.append(
                {
                    "rsid": v.rsid,
                    "variant_key": v.variant_key,
                    # The authored cell, not the materialized allele list `weights.parquet` carries:
                    # this table is read on its own, so it states the genotype the way the author
                    # wrote it rather than asking a consumer to re-join and re-assemble one.
                    "genotype": v.genotype,
                    "conclusion": v.conclusion,
                    "negatives": v.negatives,
                    "module": module_name,
                    "gene": v.gene or "",
                    "phenotype": v.phenotype or "",
                    "category": v.category or "",
                }
            )
            seen_keys.add(key)
    schema = {
        "rsid": pl.Utf8,
        "variant_key": pl.Utf8,
        "genotype": pl.Utf8,
        "conclusion": pl.Utf8,
        "negatives": pl.Utf8,
        "module": pl.Utf8,
        "gene": pl.Utf8,
        "phenotype": pl.Utf8,
        "category": pl.Utf8,
    }
    return pl.DataFrame(records, schema=schema)


#: The `ResolutionRow` columns a carried locus leaves out, each with the reason (RM380). Every other
#: column is carried: `reverse_module` rebuilds `resolution.csv` from the loci, so a column missing here
#: is a column the round trip drops (P7), and outside a signature is not the same as dropped.
#: `test_resolution_locus_carries_the_row` asserts the model's fields equal the carried ones plus these.
RESOLUTION_LOCUS_EXCLUDED: dict[str, str] = {
    "variant_key": "the key a parquet files the loci under, the row's authored key or `proxy_rsid`",
    "genome_build": "the module's own build, which the manifest states and reverse writes on every row",
    "source": (
        "the link that wrote the row; a reversed row was written by reverse, so it says `reversed` "
        "(`compilation.resolution_sources` is excluded from the round trip for that reason)"
    ),
    "status": (
        "reverse writes `resolved` for every positioned locus it re-emits; a `not_found` row places "
        "nothing and carries no locus"
    ),
    "fetched_at": "when a pass wrote the row; reverse reads no clock, so its emit stays deterministic",
    "rsid_alternates": (
        "a candidate list from a reverse back-fill against a reference at a moment, recovered by "
        "re-running the enricher (`@rsid-alternates-closed`)"
    ),
    "rsid_current": (
        "what dbSNP serves today for a merged rsID, time-varying external state recovered by re-running "
        "the enricher (`@rsid-alternates-closed`)"
    ),
    "rsid_status": (
        "what dbSNP says about the rsID today, time-varying external state recovered by re-running the "
        "enricher (`@rsid-alternates-closed`)"
    ),
}

#: A carried column whose parquet type is not the one its annotation maps to.
_LOCUS_DTYPE_OVERRIDES: dict[str, pl.DataType] = {"start": pl.UInt32}

#: The carried columns, in `ResolutionRow`'s order: every field `RESOLUTION_LOCUS_EXCLUDED` does not name.
RESOLUTION_LOCUS_FIELDS: tuple[str, ...] = tuple(
    name for name in ResolutionRow.model_fields if name not in RESOLUTION_LOCUS_EXCLUDED
)

#: One resolved locus, as a parquet carries it beside the row whose key it was filed under: every
#: `resolution.csv` column but the ones `RESOLUTION_LOCUS_EXCLUDED` names, derived from the model so a
#: column the enricher begins to write reaches the struct with it (RM380). Two carriers:
#: `studies.parquet.proxy_loci` (a study's LD proxy, RM331) and `resolution_loci` on `weights.parquet`
#: and every positional parquet (RM364).
RESOLUTION_LOCUS_DTYPE = pl.Struct(
    {
        name: _LOCUS_DTYPE_OVERRIDES.get(name, _polars_type(ResolutionRow.model_fields[name].annotation))
        for name in RESOLUTION_LOCUS_FIELDS
    }
)

#: The carried columns a parquet row's own cells rebuild, the locus facts plus the row's `vrs_id`/`vrs_spec`
#: columns (RM270). A locus holding a value in any OTHER carried column is never withheld as reproduced:
#: no cell holds it, so withholding it is dropping it.
_CELL_REBUILT: frozenset[str] = frozenset(
    {"rsid", "chrom", "start", "ref", "alts", "locus_index", "vrs_id", "vrs_spec"}
)
_LOCUS_ONLY: tuple[str, ...] = tuple(name for name in RESOLUTION_LOCUS_FIELDS if name not in _CELL_REBUILT)


def resolution_loci(
    key: str | None, resolution: dict[str, list[ResolutionRow]], genome_build: str
) -> list[dict[str, Any]] | None:
    """The loci `resolution.csv` files under `key` on this build, in `locus_index` order, or `None`.

    **Why a parquet carries them.** `reverse_module` rebuilds `resolution.csv` from parquets, so a fact
    no parquet holds does not come back, `resolution_signature` moves, and whatever the compile said
    about it goes silent on the second lap. Two kinds of row are keyed into the table without holding
    its answer in their own columns: a study's LD proxy, which is usually not a module variant (RM331),
    and a variant row the fill left alone (RM364) — one whose authored coordinate the table contradicts,
    one whose key names several loci none of which was taken, a locus dropped as unable to host the
    genotype, and every row of a module on a build the fill skips. Rebuilding those from the row's own
    cells wrote the author's coordinate back as a resolution fact.

    Positioned loci only: a `not_found` row carries no fact for reverse to restore.
    """
    if key is None:
        return None
    loci = sorted(
        (
            r
            for r in resolution.get(key, [])
            if r.genome_build == genome_build and r.chrom is not None and r.start is not None
        ),
        key=lambda r: r.locus_index,
    )
    if not loci:
        return None
    return [{name: getattr(r, name) for name in RESOLUTION_LOCUS_FIELDS} for r in loci]


def _locus_fact(rsid: Any, chrom: Any, start: Any, ref: Any, alts: Any, locus_index: Any) -> tuple[Any, ...]:
    """One table row's facts as `reverse` rebuilds them, `genome_build` and the key aside."""
    return (rsid or None, chrom, start, ref or None, alts or None, locus_index or 0)


def withhold_reproduced_loci(
    cells: list[list[dict[str, Any]] | None],
    keys: list[str | None],
    facts: list[tuple[Any, ...] | None],
) -> list[list[dict[str, Any]] | None]:
    """`cells` with a key's loci nulled wherever its rows' own cells already rebuild them exactly (RM364).

    `facts[i]` is what `reverse`'s cell rebuild writes for row `i` (`None` where it writes nothing, a row
    with no coordinate). Where the set of those facts over a key equals the facts of the loci the table
    files under it, the cells answer and the column stays null, so a module the fill resolved cleanly
    carries nothing new, and its `artifact.digest` matches the deprecated `ensembl_cache` path's, which
    reads no table. Everywhere else, which is every row the fill left alone, the loci are kept.
    """
    by_key: dict[str, set[tuple[Any, ...]]] = {}
    for key, fact in zip(keys, facts, strict=True):
        if key is not None:
            facts_of_key = by_key.setdefault(key, set())
            if fact is not None:
                facts_of_key.add(fact)
    reproduced = {
        key
        for key, cell in zip(keys, cells, strict=True)
        if key is not None
        and cell
        # A row's cells hold no provenance (RM375's verdict, RM267's witness, RM373's release, ...), so a
        # locus holding any is never rebuilt from the cells (RM380). `False` is a value: `is not None`.
        and not any(locus.get(name) is not None for locus in cell for name in _LOCUS_ONLY)
        and by_key[key]
        == {
            _locus_fact(
                locus["rsid"],
                locus["chrom"],
                locus["start"],
                locus["ref"],
                locus["alts"],
                locus["locus_index"],
            )
            for locus in cell
        }
    }
    return [None if key in reproduced else cell for key, cell in zip(keys, cells, strict=True)]


def with_resolution_loci(
    table: pl.DataFrame, resolution: dict[str, list[ResolutionRow]], genome_build: str
) -> pl.DataFrame:
    """A positional table's parquet with `resolution_loci`: the loci filed under each row's key (RM364).

    Keyed on the row's stored `variant_key`, the key the positional fill looked the row up by and the
    key `reverse` files it under. Kept wherever the row's own cells would not rebuild them
    (`withhold_reproduced_loci`): a row the fill left alone still carries what the table said about it.
    An empty `resolution` (no table, or `--no-resolve`) leaves the column null.
    """
    keys = table["variant_key"].to_list()
    cells = [resolution_loci(key, resolution, genome_build) for key in keys]
    facts = [
        None
        if row["chrom"] is None or row["start"] is None
        else _locus_fact(row.get("rsid"), row["chrom"], row["start"], row.get("ref"), row.get("alts"), 0)
        for row in table.iter_rows(named=True)
    ]
    cells = withhold_reproduced_loci(cells, keys, facts)
    return table.with_columns(pl.Series("resolution_loci", cells, dtype=pl.List(RESOLUTION_LOCUS_DTYPE)))


def _build_studies(
    studies: list[StudyRow],
    module_name: str,
    resolution: dict[str, list[ResolutionRow]] | None = None,
    genome_build: str = "GRCh38",
) -> pl.DataFrame:
    """Build the studies.parquet DataFrame from validated study rows.

    `resolution` (the overlaid injected table, keyed by `variant_key`) fills `proxy_loci`; without it the
    column is null, which is what a compile with no `resolution.csv` honestly has.
    """
    records: list[dict[str, Any]] = []
    for s in studies:
        records.append(
            {
                "rsid": s.rsid,
                # Position columns (RM2): a StudyRow may be position-only (rsid null, chrom+start
                # set) — its variant_key is chrom:start:ref. Carrying them keeps such a row lossless
                # through compile → reverse → recompile (Principle 7); dropping them made the reversed
                # row identifier-less, so recompile failed validation.
                "chrom": s.chrom,
                "start": s.start,
                "ref": s.ref,
                "module": module_name,
                "pmid": s.pmid,
                "population": s.population,
                "p_value": s.p_value,
                "conclusion": s.conclusion,
                "study_design": s.study_design,
                # ── 0.3 additive columns (materialized passthrough). ──
                "stat_significance": s.stat_significance,
                "effect_size": s.effect_size,
                "effect_measure": s.effect_measure,
                # RM91 (0.6): what `effect_size` is relative to. Materialized beside the magnitude
                # rather than derived, because nothing can recover it — `ref` names the locus, not
                # the claim.
                "effect_allele": s.effect_allele,
                "trait_efo_id": s.trait_efo_id,
                # RM140 (0.7): which analysis the two numbers above came from. A passthrough like
                # every column around it — nothing can derive it, and nothing checks it yet.
                "statistical_test": s.statistical_test,
                # RM160 (0.7): how far the citing source stands behind this link, in its own
                # units, and the instrument that names them. A passthrough pair — nothing here
                # converts one source's ladder into another's.
                "confidence": s.confidence,
                "confidence_unit": s.confidence_unit,
                # ── 0.4 provenance columns (RM11/RM12, from the 0.5 scope; docs/USE_CASES.md §4a). ──
                "doi": s.doi,
                "provenance_quote": s.provenance_quote,
                "provenance_regex": s.provenance_regex,
                # ── 0.6: who located that passage (S55). ──
                "curator": s.curator,
                # ── 0.5: the queryable p-value. The authored number passes through; `neg_log10_p` is
                # DERIVED on write and absent from `StudyRow`'s fields, so `_write_studies_csv` cannot
                # emit it and the next compile re-derives the identical column (the `allele_frequency`
                # pattern — see `_build_frequencies`).
                "p_value_num": s.p_value_num,
                "neg_log10_p": s.neg_log10_p,
                # ── 0.8: the StudyRow batch (PROPOSAL_0_8_PT2 §3 items 11–17), after every 0.7 column so
                # none of them moves. Passthroughs; nothing here derives one from another. ──
                # RM325: how many were analysed, in what unit, and how many were cases.
                "sample_size": s.sample_size,
                "sample_unit": s.sample_unit,
                "n_cases": s.n_cases,
                # RM326: which outcome the study measured.
                "phenotype_class": s.phenotype_class,
                # RM328: the superpopulation code(s) the estimate was measured in, in authored order.
                "ancestry": s.ancestry,
                # RM329: the age band the estimate covers, and whose age it is.
                "age_min": s.age_min,
                "age_max": s.age_max,
                "age_of": s.age_of,
                # RM330: the stratum the estimate was measured in, and its level.
                "stratum": s.stratum,
                "stratum_level": s.stratum_level,
                # RM331: the LD proxy the study measured, when it was not the lead itself.
                "proxy_rsid": s.proxy_rsid,
                # RM332: the unit of `effect_size`, verbatim.
                "effect_unit": s.effect_unit,
                # RM331: the proxy's resolved loci, so reverse can re-emit its `resolution.csv` row.
                # Compiler-filled and never authored; last, so no earlier column moves.
                "proxy_loci": resolution_loci(s.proxy_rsid, resolution or {}, genome_build),
            }
        )
    schema = {
        "rsid": pl.Utf8,
        "chrom": pl.Utf8,
        "start": pl.UInt32,
        "ref": pl.Utf8,
        "module": pl.Utf8,
        "pmid": pl.Utf8,
        "population": pl.Utf8,
        "p_value": pl.Utf8,
        "conclusion": pl.Utf8,
        "study_design": pl.Utf8,
        "stat_significance": pl.Utf8,
        "effect_size": pl.Float64,
        "effect_measure": pl.Utf8,
        "effect_allele": pl.Utf8,
        "trait_efo_id": pl.Utf8,
        "statistical_test": pl.Utf8,
        "confidence": pl.Utf8,
        "confidence_unit": pl.Utf8,
        "doi": pl.Utf8,
        "provenance_quote": pl.Utf8,
        "provenance_regex": pl.Utf8,
        "curator": pl.Utf8,
        "p_value_num": pl.Float64,
        "neg_log10_p": pl.Float64,
        # Int64, not UInt32: a consumer sums these across studies (`@a-count-that-fits-every-partition-
        # need-not-fit-their-sum`), and polars' `sum()` keeps the input dtype.
        "sample_size": pl.Int64,
        "sample_unit": pl.Utf8,
        "n_cases": pl.Int64,
        "phenotype_class": pl.Utf8,
        "ancestry": pl.List(pl.Utf8),
        "age_min": pl.Float64,
        "age_max": pl.Float64,
        "age_of": pl.Utf8,
        "stratum": pl.Utf8,
        "stratum_level": pl.Utf8,
        "proxy_rsid": pl.Utf8,
        "effect_unit": pl.Utf8,
        "proxy_loci": pl.List(RESOLUTION_LOCUS_DTYPE),
    }
    return pl.DataFrame(records, schema=schema)
