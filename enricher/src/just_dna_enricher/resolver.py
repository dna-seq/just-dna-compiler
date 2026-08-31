"""
Bidirectional rsid <-> position resolver using an Ensembl DuckDB (GRCh38).

Unlike the original pipelines resolver, this standalone version **injects** the Ensembl
reference: the caller passes either a prebuilt `.duckdb` file or a directory of Ensembl parquet
files, and the resolver builds an ephemeral `ensembl_variations` view over it. It never reaches
into `just-dna-pipelines` and never downloads anything — provisioning the reference is the
caller's responsibility (the marketplace pins one reference for the whole ecosystem).
"""

import logging
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.resolution import genotype_fits
from just_dna_format.base import derive_variant_key
from just_dna_format.findings import CodedWarning
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import normalize_chrom

from just_dna_enricher.locations import DUCKDB_NAME, resolve_ensembl_reference

logger = logging.getLogger(__name__)


class EnsemblReferenceError(FileNotFoundError):
    """Raised when a provided Ensembl reference is neither a usable .duckdb nor a parquet dir."""


def _has_ensembl_table(con: duckdb.DuckDBPyConnection) -> bool:
    return any(r[0] == "ensembl_variations" for r in con.execute("SHOW TABLES").fetchall())


def _view_over_parquet(reference: Path) -> duckdb.DuckDBPyConnection | None:
    """Build an in-memory `ensembl_variations` view over the cache's parquet files, or None."""
    parquet_glob: Path | None = None
    if (reference / "data").is_dir() and any((reference / "data").glob("*.parquet")):
        parquet_glob = reference / "data"
    elif reference.is_dir() and any(reference.glob("*.parquet")):
        parquet_glob = reference
    if parquet_glob is None:
        return None
    # DuckDB can't bind a parameter inside CREATE VIEW ... read_parquet(). The pattern is a local
    # path from our own cache resolution, not user input; single-quote-escape it defensively.
    pattern = f"{parquet_glob}/*.parquet".replace("'", "''")
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW ensembl_variations AS SELECT * FROM read_parquet('{pattern}')")
    return con


def _connect(reference: Path) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection exposing an `ensembl_variations` relation.

    `reference` (from `resolve_ensembl_reference`) is a `.duckdb` file or a cache directory. A
    prebuilt DuckDB is used only if it actually contains the `ensembl_variations` table (a stale/
    empty db, as just-dna-lite may leave behind, is ignored in favor of the parquet `data/`).
    """
    reference = Path(reference)

    if reference.is_file() and reference.suffix == ".duckdb":
        con = duckdb.connect(str(reference), read_only=True)
        if _has_ensembl_table(con):
            return con
        con.close()
        raise EnsemblReferenceError(f"{reference} has no ensembl_variations table")

    db = reference / DUCKDB_NAME
    if db.is_file():
        con = duckdb.connect(str(db), read_only=True)
        if _has_ensembl_table(con):
            return con
        con.close()  # empty/stale prebuilt db — fall back to parquet

    con = _view_over_parquet(reference)
    if con is None:
        raise EnsemblReferenceError(f"no usable Ensembl .duckdb or parquet files at {reference}")
    return con


def resolve_variants(
    variants: list[VariantRow],
    ensembl_cache: Path | None = None,
    genome_build: str = "GRCh38",
) -> tuple[list[VariantRow], list[str]]:
    """Fill in missing rsid or position from the injected Ensembl reference (GRCh38).

    Variants that already carry both identifiers are returned unchanged. If no reference is
    available, resolution is skipped with a warning rather than raising.

    **One-to-many rsid → expansion.** A no-coord rsid that maps to several loci is expanded into one
    row per locus, each re-keyed to its coordinate (`variant_key`), so the N loci get N distinct
    identities — a paralog/SV signal a consumer can count (data-agnostic). A 1:1 rsid just fills the
    coordinate and keeps its rsid key. `variant_key` is frozen (`base.derive_variant_key`), so filling
    a coord/rsid never re-keys a row (Principle 7); only expansion reassigns it.

    **GRCh38-bound.** The reference is GRCh38, so resolution runs only for a GRCh38 module; a
    GRCh37/T2T build is skipped with a warning (positions are not re-resolved cross-build — RM15),
    rather than corrupting coordinates against the wrong assembly.

    **Bidirectional consistency (inject-only, no network).** For rows that authored *both* an rsid and
    a coordinate, the same injected reference is used to check that the coordinate is among the rsid's
    loci and the rsid among the coordinate's ids; a disagreement is a **warning** (it may be a dbSNP
    merge/build difference — never fatal, matching the resolver's best-effort stance).
    """
    if genome_build != "GRCh38":
        msg = (
            f"Ensembl resolution skipped: compiler is GRCh38-bound, module genome_build is "
            f"{genome_build!r} — positions are not re-resolved cross-build (RM15)."
        )
        logger.warning(msg)
        return variants, [msg]

    need_pos = [v for v in variants if v.rsid is not None and v.chrom is None]
    need_rsid = [v for v in variants if v.rsid is None and v.chrom is not None]
    verify = [
        v for v in variants
        if v.rsid is not None and v.chrom is not None and v.start is not None
    ]
    if not need_pos and not need_rsid and not verify:
        return variants, []

    reference = resolve_ensembl_reference(ensembl_cache)
    if reference is None:
        msg = (
            "Ensembl resolution skipped: no reference cache found "
            "(set JUST_DNA_PIPELINES_CACHE_DIR or JUST_DNA_ENSEMBL_CACHE, or pass ensembl_cache)"
        )
        logger.warning(msg)
        return variants, [msg]

    try:
        con = _connect(reference)
    except EnsemblReferenceError as exc:
        msg = f"Ensembl resolution skipped: {exc}"
        logger.warning(msg)
        return variants, [msg]

    warnings: list[str] = []
    rsid_to_pos: dict[str, list[dict]] = {}
    if need_pos:
        # sorted, not set-order: the "not found in Ensembl" warnings are appended in this order, so
        # an unsorted set iteration would leave manifest.compilation.warnings non-reproducible.
        unique_rsids = sorted({v.rsid for v in need_pos if v.rsid is not None})
        rsid_to_pos = _lookup_positions_by_rsid(con, unique_rsids, warnings)
    pos_to_rsid: dict[str, str] = {}
    if need_rsid:
        unique_positions = sorted(
            {(v.chrom, v.start, v.ref) for v in need_rsid if v.chrom is not None and v.start is not None}
        )
        pos_to_rsid = _lookup_rsids_by_position(con, unique_positions, warnings)
    if verify:
        _check_rsid_coord_consistency(con, verify, warnings)
    con.close()

    patched: list[VariantRow] = []
    for v in variants:
        if v.rsid is not None and v.chrom is None and v.rsid in rsid_to_pos:
            loci = rsid_to_pos[v.rsid]
            if len(loci) == 1:
                # 1:1 — fill the coordinate; the frozen variant_key stays the rsid.
                patched.append(v.model_copy(update=loci[0]))
            else:
                # One-to-many — expand to one coord-keyed row per locus (deterministic order from the
                # ORDER BY). Each row re-keys variant_key to its coordinate so the loci are distinct.
                #
                # A locus whose alleles cannot host the authored genotype is dropped, exactly as the
                # injected-table path does. The shared predicate is imported rather than reimplemented
                # because digest parity between the two paths is a documented guarantee, and a filter
                # applied on one side only would silently break it.
                usable = [
                    lo for lo in loci
                    if genotype_fits(v.genotype, lo.get("ref"), lo.get("alts"))
                ]
                for lo in loci:
                    if lo not in usable:
                        # Coded with the same members its injected-table twin in
                        # `just_dna_compiler.resolution` uses: the finding is the same and so is the
                        # remedy, and `compile_module` puts both paths' warnings in one channel.
                        warnings.append(CodedWarning(
                            "locus_cannot_host_genotype",
                            f"{v.rsid} maps to {lo['chrom']}:{lo['start']} "
                            f"{lo.get('ref')}>{lo.get('alts')}, which cannot host the authored "
                            f"genotype {v.genotype} — that locus is dropped from the expansion.",
                        ))
                if not usable:
                    warnings.append(CodedWarning(
                        "rsid_no_hosting_locus",
                        f"{v.rsid}: none of its {len(loci)} loci can host the authored genotype "
                        f"{v.genotype}; position remains unset",
                    ))
                    patched.append(v)
                elif len(usable) == 1:
                    patched.append(v.model_copy(update=usable[0]))
                else:
                    # Still per authored row, and deliberately not converged with the compiler's twin,
                    # which S33 moved to one accumulated sentence per rsID with the real row total.
                    # This whole path is the deprecated `ensembl_cache` route, removed at 1.0; porting
                    # the accumulator here would duplicate it into a function that is going away, and
                    # the modules that reach it report `expanded_keys`/`expanded_rows` as `None`
                    # (not established) for the same reason.
                    warnings.append(CodedWarning(
                        "rsid_expanded_to_multiple_loci",
                        f"{v.rsid} maps to {len(usable)} loci in Ensembl; expanded to {len(usable)} "
                        f"rows (one per locus, each keyed by its coordinate — a consumer can count them).",
                    ))
                    for index, locus in enumerate(usable):
                        # Redundant today (the function returns early above for any non-GRCh38 build),
                        # passed anyway — see the twin in `just_dna_compiler.resolution`.
                        key = derive_variant_key(
                            None, locus["chrom"], locus["start"], locus["ref"], locus["alts"],
                            build=genome_build,
                        )
                        # The expansion marker (RM87). Unlike the warning above, this half *is*
                        # converged with the compiler's twin, and it has to be: **digest parity
                        # between this path and the `resolution.csv` path is a documented guarantee**,
                        # and these two columns reach `weights.parquet`. Leaving them at their
                        # defaults here would make the deprecated path's artifact differ from the
                        # supported path's on the same module — which is how two round-trip tests
                        # caught it, since reverse writes a `resolution.csv` and the recompile then
                        # takes the other branch.
                        patched.append(v.model_copy(update={
                            **locus,
                            "variant_key": key,
                            "locus_index": index,
                            "locus_count": len(usable),
                        }))
        elif v.rsid is None and v.chrom is not None:
            key = derive_variant_key(None, v.chrom, v.start, v.ref)
            if key in pos_to_rsid:
                # Fill the rsid; the frozen variant_key stays the coordinate (no flip).
                patched.append(v.model_copy(update={"rsid": pos_to_rsid[key]}))
            else:
                warnings.append(
                    CodedWarning("rsid_without_resolution_label", f"Position {key}: no rsid found in Ensembl")
                )
                patched.append(v)
        else:
            patched.append(v)
    return patched, warnings


def lookup_loci(
    reference: Path,
    rsids: list[str],
    positions: list[tuple[str | None, int | None, str | None, str | None]],
) -> tuple[dict[str, list[dict]], dict[tuple, list[str]], list[str]]:
    """Public cache lookup the enricher uses to *build* a resolution table (0.5).

    Returns `(rsid -> [loci], (chrom,start,ref,alt) -> [candidate rsids], warnings)` from an injected
    Ensembl reference. The reverse map is **allele-aware** (matches the authored `alt` when given) and
    returns *all* candidate rsIDs at that exact allele — never a silent first-pick — so the caller can
    take a deterministic pick and flag a genuine multi-rsid allele as ambiguous. Inject-only.
    """
    warnings: list[str] = []
    con = _connect(reference)
    try:
        rsid_to_loci = (
            _lookup_positions_by_rsid(con, sorted(set(rsids)), warnings) if rsids else {}
        )
        pos_candidates = (
            _lookup_rsid_candidates(con, "ensembl_variations", "id", positions) if positions else {}
        )
    finally:
        con.close()
    return rsid_to_loci, pos_candidates, warnings


def probe_table(
    con: duckdb.DuckDBPyConnection,
    name: str,
    columns: Sequence[tuple[str, str]],
    rows: Sequence[tuple],
) -> None:
    """Materialize `rows` into a TEMP table so a batch lookup can **hash-join** instead of OR-chaining.

    DuckDB cannot fold a disjunction of equality *conjunctions* into a hash probe, so
    `WHERE (chrom=? AND start=? AND ref=? AND alt=?) OR …` is evaluated against every row of the
    reference: the cost grows with `wanted × rows`, i.e. quadratically in the module. Measured on the
    4,431,781-record ClinVar snapshot with 5,000 alleles, same connection, identical output: **127 s**
    OR-chained against **0.13 s** joined. A gene panel of any real size simply does not finish — this
    is what made `enrich()` run two hours at 12% CPU with no I/O and look like a deadlock.

    A single-column list does **not** need this: `x IN (?, …)` is hashed and is already fast
    (`_lookup_positions_by_rsid`, `clinvar.citations_for`). What the planner does not do is fold
    `x = ? OR x = ? OR …` into that `IN` — same 4,793 genes cost 15.22 s OR-chained and 1.02 s as
    `IN` — so a single-column predicate is spelled `IN`, and only multi-column ones come here.

    **The rows are rendered as SQL literals, and that is deliberate — it is the whole speed-up.**
    The join itself is nearly free; what costs is handing 5,000 rows to DuckDB, and its Python
    parameter binding is where the time goes. Measured on the same snapshot and sample, from
    `WHERE`-clause to result: literal `VALUES` **0.21 s**, a composite-key `IN (?, …)` with scalar
    parameters **1.04 s**, a parameterized `UNNEST(?::VARCHAR[])` **3.51 s**, `executemany` **8.6 s**
    — against **88 s** for the OR-chain this replaces. So the obvious "fix" of parameterizing it back
    gives up most of the win; do not make that change without re-measuring. Values are escaped the
    same way `clinvar._connect` escapes the parquet path, and a numeric column is coerced through
    `int()` rather than quoted, so nothing reaches SQL unexamined.

    `columns` is `(name, sql_type)` pairs; an `INTEGER`/`BIGINT` column takes its value through
    `int()`, everything else is quoted. The table is replaced on each call so one connection can serve
    several probes. Callers keep their own `ORDER BY`: a join reorders nothing by itself, and emitted
    row order is digest-visible (Principle 7).
    """
    con.execute(f"DROP TABLE IF EXISTS {name}")
    declaration = ", ".join(f"{column} {sql_type}" for column, sql_type in columns)
    con.execute(f"CREATE TEMP TABLE {name} ({declaration})")
    if not rows:
        return
    numeric = [sql_type.upper() in _NUMERIC_SQL_TYPES for _, sql_type in columns]
    values = ", ".join(
        "(" + ", ".join(_sql_literal(cell, is_numeric) for cell, is_numeric
                        in zip(row, numeric, strict=True)) + ")"
        for row in rows
    )
    con.execute(f"INSERT INTO {name} VALUES {values}")


#: SQL types `probe_table` renders unquoted, through `int()`.
_NUMERIC_SQL_TYPES = frozenset({"BIGINT", "INTEGER", "INT"})


def _sql_literal(cell: object, numeric: bool) -> str:
    """One cell as a SQL literal: NULL, an integer, or a single-quote-escaped string."""
    if cell is None:
        return "NULL"
    if numeric:
        return str(int(cell))  # type: ignore[arg-type]
    return "'" + str(cell).replace("'", "''") + "'"


def _lookup_rsid_candidates(
    con: duckdb.DuckDBPyConnection,
    table: str,
    id_col: str,
    positions: list[tuple[str | None, int | None, str | None, str | None]],
) -> dict[tuple, list[str]]:
    """Allele-aware reverse lookup: `(chrom,start,ref,alt) -> sorted [candidate rsids]`.

    Matches the exact allele when `alt` is given (the fix for allele-blind back-fill: an insertion no
    longer inherits a co-located SNV's rsid), falls back to `(chrom,start,ref)` then `(chrom,start)`
    when the authored variant is less specific. Returns every distinct rsid found, so the caller flags
    a >1 result as ambiguous rather than guessing. Shared shape for the Ensembl (`id`) and ClinVar
    (`rsid`) tables — `id_col` selects which. `ORDER BY` keeps the candidate order deterministic (P7).
    """
    uniq = list(dict.fromkeys(positions))
    concrete = [(c, s) for c, s, r, a in uniq if c is not None and s is not None]
    if not concrete:
        return {pt: [] for pt in uniq}
    probe_table(
        con, "_wanted_positions", [("chrom", "VARCHAR"), ("start", "BIGINT")], sorted(set(concrete))
    )
    rows = con.execute(
        f"SELECT DISTINCT t.chrom, t.start, t.ref, t.alt, t.{id_col} FROM {table} t "
        f"JOIN _wanted_positions w ON t.chrom = w.chrom AND t.start = w.start "
        f"WHERE t.{id_col} LIKE 'rs%' "
        f"ORDER BY t.chrom, t.start, t.ref, t.alt, t.{id_col}"
    ).fetchall()
    by_pos: dict[tuple, list[tuple]] = defaultdict(list)
    for chrom, start, ref, alt, rid in rows:
        by_pos[(str(chrom), int(start))].append((str(ref), str(alt), str(rid)))
    result: dict[tuple, list[str]] = {}
    for chrom, start, ref, alt in uniq:
        cands: list[str] = []
        for rref, ralt, rid in by_pos.get((str(chrom), int(start)) if chrom is not None else (), []):
            if ref is not None and rref != ref:
                continue
            # Membership, not equality: a multi-allelic snapshot row names several alleles in one
            # pipe-joined cell, and `!=` against the whole cell never matched any of them.
            if alt is not None and alt not in _snapshot_alleles(ralt):
                continue
            if rid not in cands:  # rows already ordered by ... id
                cands.append(rid)
        result[(chrom, start, ref, alt)] = cands
    return result


def _snapshot_alleles(cell: object) -> list[str]:
    """The alleles named by one snapshot `alt` cell.

    The Ensembl snapshot records a multi-allelic site as a **single row whose `alt` is pipe-joined**
    (`A|C|T`), whereas every other link in the chain — live Ensembl (`_loci_from_rest`), ClinVar,
    gnomAD — emits a comma-separated list, and that is the shape `ResolutionRow.alts` is written in.
    Normalizing here, at the one boundary where the snapshot is read, keeps a locus dict's `alts` in
    exactly one canonical form no matter which link produced it.

    This is load-bearing rather than cosmetic: `genotype_fits` (the shared allele-membership
    predicate) splits on commas only, so an un-normalized `A|C|T` collapsed to a single opaque
    "allele" and **every** genotype was judged unhostable — a cache-resolved `rs4244285` with the
    perfectly ordinary genotype `A/G` resolved to `not_found`. The reverse back-fill had the mirror
    bug: it compared the authored alt against the whole joined cell with `!=`, so an exact allele
    never matched a multi-allelic site.
    """
    return [a for a in re.split(r"[,|]", str(cell)) if a]


def _lookup_positions_by_rsid(
    con: duckdb.DuckDBPyConnection, rsids: list[str], warnings: list[str]
) -> dict[str, list[dict]]:
    """Batch lookup: rsid -> [{chrom, start, ref, alts}, ...] (ALL loci, deterministically ordered).

    An rsid can map to several loci (paralogs, patch/haplotype scaffolds, PAR). Every locus is
    returned — the caller expands a one-to-many rsid into one row per locus rather than picking one
    (a silent "first-met" pick was non-deterministic and dropped real loci). `ORDER BY id, chrom,
    start, ref` makes the emitted order stable across runs (idempotency, Principle 7)."""
    if not rsids:
        return {}
    placeholders = ", ".join("?" for _ in rsids)
    rows = con.execute(
        f"""
        SELECT id, chrom, start, ref, string_agg(DISTINCT alt, ',' ORDER BY alt) AS alts
        FROM ensembl_variations
        WHERE id IN ({placeholders})
        GROUP BY id, chrom, start, ref
        ORDER BY id, chrom, start, ref
        """,
        rsids,
    ).fetchall()
    result: dict[str, list[dict]] = defaultdict(list)
    for row_id, chrom, start, ref, alts in rows:
        # `string_agg` already joined the group with commas; `_snapshot_alleles` additionally splits
        # any pipe-joined multi-allelic cell, then re-joins sorted+deduped so the order is stable (P7).
        alleles = sorted(set(_snapshot_alleles(alts)))
        result[row_id].append(
            {"chrom": str(chrom), "start": int(start), "ref": str(ref), "alts": ",".join(alleles)}
        )
    for rsid in rsids:
        if rsid not in result:
            # Two things this line must not do, and it did each of them in turn. It must not speak
            # for Ensembl — "in the injected snapshot", not "in Ensembl", because a partial snapshot
            # missing rs1799945 says nothing about the HFE H63D locus Ensembl serves at 6:26090951.
            # And it must not say what happens *next*: whether the position stays unset depends on a
            # live leg this function neither runs nor knows about, so at this point that answer is
            # genuinely unknown and the house rule is to withhold it rather than guess. The one
            # caller that reads these warnings states the consequence once, after both legs (S61).
            warnings.append(
                CodedWarning("rsid_unresolved", f"{rsid}: not in the injected Ensembl snapshot")
            )
    return dict(result)


@dataclass(frozen=True)
class PairCheck:
    """What the rsid↔coordinate comparison did, not just what it found (RM45).

    Same shape and same argument as `sequences.RefCheck`: the disagreements alone answer one of the
    two questions a reader has, and an empty list says three different things — every pair agreed, the
    reference had no record of any of them, or there was no reference at all. `subjects` is the
    denominator the check really ran over, `unknown` names the pairs it could not put the question for
    (an answered absence is not an agreement — S20), and `not_checked` carries a
    `VALID_VERIFICATION_SKIPS` key when the whole pass could not run.
    """

    disagreements: list[str] = field(default_factory=list)
    subjects: int = 0
    unknown: list[str] = field(default_factory=list)
    undecided: list[str] = field(default_factory=list)
    not_checked: str | None = None
    #: Pairs that disagree and whose disagreement the author has already answered in `overrides.csv`
    #: (RM136). **Inside `subjects` and outside `disagreements`**: the comparison ran and found a
    #: difference, so dropping it from the denominator would report a cleaner module than there is.
    #: What changes is only that the finding is not put to the author a second time.
    answered: int = 0


#: The `resolution.csv` columns this comparison actually reads. An overlay `update` on one of them is
#: an answer to a coordinate disagreement; an update on `source` or `status` is not, which is the
#: per-field rule RM136 chose over the per-row one.
_COORDINATE_FIELDS: tuple[str, ...] = ("chrom", "start", "ref", "alts")


def _place(chrom: str | None, start: int | None) -> str:
    """One coordinate as `chrom:start`, contig spelling normalized (`chr10` and `10` are one place)."""
    return f"{normalize_chrom(chrom)}:{start}"


def _is_substitution(ref: str | None) -> bool:
    """Whether a `ref` names a single base, i.e. a locus with no flank an indel could be re-anchored on."""
    return ref is not None and len(ref) == 1


def coordinate_verdict(
    chrom: str | None,
    start: int | None,
    ref: str | None,
    loci: Sequence[dict],
) -> bool | None:
    """Does the reference place this rsID where the row says? **Three-valued**, `hosting_verdict`'s shape.

    The per-row verdict behind both of this tier's rsid↔coordinate checks — the one `enrich()` puts
    against the injected snapshot and the deprecated DuckDB path's `_check_rsid_coord_consistency`
    below — so the two cannot drift into two readings of one question.

    * `True` — one of the rsID's loci sits at the authored coordinate.
    * `False` — none does, **and** every locus the reference gives is a substitution (and the row's own
      `ref`, where it states one, is too). A substitution has no shared flank, so its position is
      unambiguous and a mismatch can only be a different place. Same reasoning that keeps
      `hosting_verdict`'s confident negative sharp.
    * `None` — none does, but an indel is involved. One deletion has several valid spellings and
      re-anchoring moves the coordinate — ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG`
      are the same 2 bp deletion (RM31) — so a differing position is not by itself a contradiction, and
      reporting one would be the false accusation that item exists to end.

    Compared at **`chrom:start`**, not `chrom:start:ref`. Two reasons, and the first is what a
    CPIC-drafted module runs into: `ref` is optional on `HaplotypeRow`/`PharmVariantRow`, and
    `pgx_draft` writes exactly that shape, so keying on it renders `10:94781859:None` and a legal row
    can never match anything. The second is that a `ref` disagreeing with the reference is the
    *reference-allele* check's finding (`sequences.verify_reference_alleles`) — reporting it here too
    would give one defect two names, in the register the manifest publishes. The contig is normalized
    on both sides for the same class of reason: `chr10` and `10` are one place, and no PGx model runs
    the chrom validator that would have folded them together.

    Callers pass the loci the chain actually gathered and handle an **empty** list themselves: no
    record is a question never put, not an agreement, and collapsing the two is the S20 defect.
    """
    if not loci:
        return None
    if _place(chrom, start) in {_place(lo.get("chrom"), lo.get("start")) for lo in loci}:
        return True
    if all(_is_substitution(lo.get("ref")) for lo in loci) and (ref is None or _is_substitution(ref)):
        return False
    return None


def coordinate_disagreement(
    rsid: str,
    chrom: str | None,
    start: int | None,
    ref: str | None,
    loci: Sequence[dict],
) -> str | None:
    """The sentence for a `False` verdict above, or `None` for every other answer.

    A convenience for the caller that only reports contradictions; anything needing to tell an
    agreement from an undecided pair asks `coordinate_verdict` directly.
    """
    if coordinate_verdict(chrom, start, ref, loci) is not False:
        return None
    return disagreement_message(rsid, chrom, start, loci)


def disagreement_message(
    rsid: str, chrom: str | None, start: int | None, loci: Sequence[dict]
) -> str:
    """The sentence a `False` verdict is reported as, in one place so the two callers cannot drift."""
    places = sorted({_place(lo.get("chrom"), lo.get("start")) for lo in loci})
    return (
        f"{rsid} authored at {_place(chrom, start)}, but Ensembl maps {rsid} to {places} "
        f"(reference disagreement — may be a dbSNP merge, or a coordinate from another build)."
    )


def check_rsid_coordinates(
    pairs: Sequence[tuple[str, str | None, int | None, str | None]],
    rsid_loci: Mapping[str, Sequence[dict]],
    answered: AbstractSet[tuple[str, str]] = frozenset(),
) -> PairCheck:
    """Compare each authored `(rsid, chrom, start, ref)` pair against the loci that rsid resolves to.

    Takes the loci the caller's chain already gathered rather than opening anything, so the pass costs
    no lookup of its own and no egress: `enrich()` widens the batch it was already sending.

    **A pair is compared, unplaceable, or undecided, and only the first is a subject.** `unknown` is a
    pair whose rsID the reference has no record of — a question never put — and `undecided` is one
    where it has a record and the verdict is `None` (an indel, whose coordinate re-anchoring can move
    legitimately). Both stay outside `subjects`, so `findings/subjects` describes exactly the pairs a
    verdict was reached on, and both are named to the caller so what was *not* compared can be stated.

    **One direction only** — is the authored coordinate among the rsid's loci — where the deprecated
    path below also asks the converse (is the authored rsid among the ids at that position). The
    converse needs a position→id lookup at `chrom:start:ref` granularity, and the reverse map
    `enrich()` holds is **allele-exact**; asking it would report a disagreement whenever the authored
    ALT is spelled differently from the reference's, which is a false accusation about a row rather
    than a finding. The compiler's `resolution._verify` asks this same single direction over the
    injected table, which is what makes the two halves one question.

    **`answered` is the author's overlay, and a pair it names is counted rather than reported
    (RM136).** Until 0.7 an author who corrected a `resolution.csv` coordinate through `overrides.csv`
    — the mechanism RM124 built for exactly this — kept being told the same thing on every run, with no
    way to clear it and nothing saying the correction had been honoured one tier over. A pair is
    answered when the overlay `update`s **that row's own coordinate cell**, per field: correcting a
    coordinate silences this check and leaves an unrelated finding standing. Per *row* was the cheaper
    rule and was refused — it would silence findings the author never looked at, which is the
    silent-suppress hole the overlay's own design calls its worst case.

    **Answered is not agreed, and the count is what keeps that honest.** The pair leaves
    `disagreements` and stays in `subjects`, with `PairCheck.answered` recording how many. A reader
    still sees that the module and the source differ here; what changes is that the difference reads as
    *settled by the author* rather than as work owed. Dropping it from the denominator would report a
    cleaner module than there is — the silent-success shape this codebase keeps closing.
    """
    disagreements: list[str] = []
    unknown: list[str] = []
    undecided: list[str] = []
    subjects = 0
    answered_count = 0
    for rsid, chrom, start, ref in pairs:
        loci = rsid_loci.get(rsid) or []
        if not loci:
            unknown.append(rsid)
            continue
        verdict = coordinate_verdict(chrom, start, ref, loci)
        if verdict is None:
            # An indel spelling this tier cannot re-anchor. Outside `subjects` rather than inside it
            # with a clean bill — the rule `RefCheck` applies to a read that came back empty.
            undecided.append(rsid)
            continue
        subjects += 1
        if verdict is False:
            # The author's own answer to this exact difference, recorded rather than re-reported.
            # Keyed on the row's `variant_key` — the subject an overlay row names — and on the
            # coordinate cells this check actually compares, so an overlay correcting some other
            # column of the same row does not silence it.
            key = derive_variant_key(rsid, chrom, start, ref)
            if any((key, column) in answered for column in _COORDINATE_FIELDS):
                answered_count += 1
                continue
            disagreements.append(disagreement_message(rsid, chrom, start, loci))
    return PairCheck(
        disagreements=disagreements, subjects=subjects, unknown=unknown, undecided=undecided,
        answered=answered_count,
    )


def _check_rsid_coord_consistency(
    con: duckdb.DuckDBPyConnection, rows: list[VariantRow], warnings: list[str]
) -> None:
    """Warn (never fail) when an authored rsid↔coordinate pair disagrees with the injected reference.

    For each row carrying both an rsid and a coordinate: verify the coordinate is among the rsid's
    loci AND the rsid is among the coordinate's dbSNP ids. A contradiction is a warning (it may be a
    dbSNP merge or a reference-build difference); when the reference knows neither side, the pair is
    left unverified (skipped). Inject-only — the same reference the resolver already opened, no
    network (Constitution Principle 2).

    The first direction is `coordinate_disagreement` above, shared with the pass `enrich()` runs, so
    the two do not drift. The second stays here: it is the half `enrich()` declines to ask, for the
    reason `check_rsid_coordinates` records."""
    rsid_loci = _lookup_positions_by_rsid(con, list({r.rsid for r in rows}), [])
    positions = list({(r.chrom, r.start, r.ref) for r in rows})
    coord_ids = _lookup_rsid_sets_by_position(con, positions)

    for r in rows:
        disagreement = coordinate_disagreement(
            r.rsid, r.chrom, r.start, r.ref, rsid_loci.get(r.rsid or "", [])
        )
        if disagreement is not None:
            warnings.append(CodedWarning("rsid_coordinate_disagrees", disagreement))
            continue
        coordkey = derive_variant_key(None, r.chrom, r.start, r.ref)
        ids = coord_ids.get(coordkey)
        if ids and r.rsid not in ids:
            warnings.append(CodedWarning(
                "rsid_coordinate_disagrees",
                f"{coordkey} authored as {r.rsid}, but Ensembl reports {sorted(ids)} there "
                f"(reference disagreement — may be a dbSNP merge/build difference).",
            ))


def _lookup_rsid_sets_by_position(
    con: duckdb.DuckDBPyConnection,
    positions: list[tuple[str | None, int | None, str | None]],
) -> dict[str, set[str]]:
    """Batch lookup: `chrom:start:ref` -> set of dbSNP ids at that exact position."""
    concrete = [(c, s, ref) for c, s, ref in positions if c is not None and s is not None]
    if not concrete:
        return {}
    conditions = " OR ".join("(chrom = ? AND start = ? AND ref = ?)" for _ in concrete)
    params: list[object] = []
    for chrom, start, ref in concrete:
        params.extend([chrom, start, ref])
    rows = con.execute(
        f"SELECT DISTINCT chrom, start, ref, id FROM ensembl_variations "
        f"WHERE ({conditions}) AND id LIKE 'rs%'",
        params,
    ).fetchall()
    result: dict[str, set[str]] = defaultdict(set)
    for chrom, start, ref, row_id in rows:
        result[derive_variant_key(None, chrom, start, ref)].add(str(row_id))
    return dict(result)


def _lookup_rsids_by_position(
    con: duckdb.DuckDBPyConnection,
    positions: list[tuple[str | None, int | None, str | None]],
    warnings: list[str],
) -> dict[str, str]:
    """Batch lookup: (chrom, start, ref) -> rsid."""
    if not positions:
        return {}
    conditions = []
    params: list[object] = []
    for chrom, start, ref in positions:
        if ref is not None:
            conditions.append("(chrom = ? AND start = ? AND ref = ?)")
            params.extend([chrom, start, ref])
        else:
            conditions.append("(chrom = ? AND start = ?)")
            params.extend([chrom, start])
    where = " OR ".join(conditions)
    rows = con.execute(
        f"SELECT DISTINCT chrom, start, ref, id FROM ensembl_variations "
        f"WHERE ({where}) AND id LIKE 'rs%' "
        # ORDER BY makes the pick deterministic when a position is multi-allelic: two runs against the
        # same DB resolve a ref-less position to the same id, so `resolve_with_ensembl` stays idempotent.
        f"ORDER BY chrom, start, ref, id",
        params,
    ).fetchall()
    # A ref-less input position (ref=None) matched on (chrom, start) only, so the caller's lookup key
    # is `chrom:start:None` — it can never equal a DB key carrying the concrete ref. Register such
    # positions under the ref-less key too, so a position-only-without-ref variant resolves.
    refless = {(str(c), s) for c, s, r in positions if r is None}
    result: dict[str, str] = {}
    refless_warned: set[tuple[str, int]] = set()
    for chrom, start, ref, row_id in rows:
        full = derive_variant_key(None, chrom, start, ref)
        result.setdefault(full, str(row_id))
        pos = (str(chrom), start)
        if pos in refless:
            refless_key = derive_variant_key(None, chrom, start, None)
            if refless_key not in result:
                result[refless_key] = str(row_id)
            elif result[refless_key] != str(row_id) and pos not in refless_warned:
                # A multi-allelic site: the ref-less key already resolved to a different id. The
                # ORDER BY fixes which one wins, but the choice is genuinely ambiguous — surface it.
                refless_warned.add(pos)
                warnings.append(CodedWarning(
                    "rsid_ambiguous",
                    f"{chrom}:{start} (ref unspecified) matches multiple dbSNP ids; resolved to "
                    f"{result[refless_key]} deterministically — specify ref to disambiguate.",
                ))
    return result
