"""Building the SNP-core and frequency parquets: weights, annotations, studies, frequencies."""

from typing import Any

import polars as pl
from just_dna_format.frequency import FrequencyRow
from just_dna_format.spec import ModuleSpecConfig, StudyRow, VariantRow

from just_dna_compiler.compiler.tables import _polars_type, _split_genotype

# ── Parquet builders ───────────────────────────────────────────────────────────


def _build_weights(variants: list[VariantRow], config: ModuleSpecConfig) -> pl.DataFrame:
    """Build the weights.parquet DataFrame from validated variant rows."""
    defaults = config.defaults
    module_name = config.module.name
    records: list[dict[str, Any]] = []
    for v in variants:
        priority = v.priority if v.priority is not None else defaults.priority
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
                "alts": v.alts.split(",") if v.alts else None,
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
    }
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


def _build_studies(studies: list[StudyRow], module_name: str) -> pl.DataFrame:
    """Build the studies.parquet DataFrame from validated study rows."""
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
    }
    return pl.DataFrame(records, schema=schema)
