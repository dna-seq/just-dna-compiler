"""Fill `expression_effects.csv` from AlphaGenome's Atlas API (0.7, RM194 + RM200).

One row per `(variant, gene)`: which way a variant moves that gene's predicted expression, how many
of the scorer's 371 tissue tracks agree, and how far the variant sits from the gene. A **recording
pass**, not a check — it is the source of the rows rather than a judge of them, so it writes no
verification record and adds no member to `VALID_VERIFICATION_CHECKS`, exactly as `gwas.py` does not.

**`RNA_SEQ` is the only scorer here, and RM200 measured all twenty-two to say so.** It is the only
one with a gene axis, the only one whose disagreement across tracks is meaningful rather than flat,
and the only one that attributes its own claim to a gene — which is what
`@gene-map-is-another-sources-attribution` requires. The rest either restate `AVI_SCORE` or rank
noise: `CAGE`'s top-5 of 546 tracks carry 2-7% of the effect, running *backwards* to effect size.

**Two ways to name the interval, and the gene filter is mandatory in both.** `--chrom/--start/--end`
wins when given; otherwise the span comes from the MANE lane widened by the model's measured
±512 kb horizon (`gene_spans`). But `gene` is required either way, because the server-side gene
filter is not an optimisation: unfiltered, a 32 bp interval answers with 43 MB against grpc's 4 MB
receive limit, and `atlas_client.score_interval` refuses such a request before sending it.

**Distance is recorded because a threshold without it is wrong.** Scores 100-500 kb out run about an
order of magnitude lower than scores at the gene, so a flat `--min-score` silently keeps only the
proximal variants — which is the failure RM194 exists to prevent, not a tuning detail. Distance needs
the gene's span, so the MANE lane is consulted even when the interval was supplied by hand; when it
is absent, `distance_to_gene` is null and the pass says so rather than substituting an interval edge.

**Non-commercial, and the gate runs before the RPC.** Atlas Output is `commercial_use=False` — the
Output Terms say so in their opening sentence — so `check_declared_use` gates the *fetch*
(`@acquisition-gate-is-not-a-read-gate`). With no `--use` declared that returns a skip, which means a
no-flag run writes nothing and explains why; every documented invocation carries
`--use non-commercial` for that reason.
"""

import csv
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import derive_variant_key, merge_key
from just_dna_format.expression import ExpressionEffectRow
from just_dna_format.layout import atomic_writer
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.enrich import source_build_mismatch
from just_dna_enricher.gene_spans import (
    ATTRIBUTION_HORIZON_BP,
    SPAN_REASONS,
    GeneSpan,
    GeneSpanError,
    gene_span,
)
from just_dna_enricher.licensing import (
    ALPHAGENOME_ATLAS_TERMS,
    check_declared_use,
    merge_sources_file,
    sidecar_path,
)
from just_dna_enricher.locations import load_env, missing_credential_reason

# Guarded at module scope rather than imported inside the function, which is the documented exception
# to this workspace's no-inline-imports rule and the shape `alphagenome_check` uses. The fallback
# binds a class that is never raised rather than `None`, so `except _NeverRaised` stays a well-formed
# expression that simply never matches — exactly right when no client can exist to have raised
# anything. It is what lets the offline half of this pass, and every test injecting a stub client,
# run on a checkout with no protobuf bindings.
try:
    from just_dna_enricher.atlas_client import AtlasError, AtlasUnavailable, connect

    ATLAS_CLIENT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised where the [atlas] extra is absent

    class _NeverRaised(Exception):
        """Stands in for an Atlas error type when no client can exist to raise one."""

    AtlasError = AtlasUnavailable = _NeverRaised
    connect = None
    ATLAS_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)

# **Notes go in `result.warnings` OR through the logger, never both.** The CLI prints
# `result.warnings`, so a note that was also logged appeared twice and read as two findings. The
# result is the contract a library caller holds; the log line was the redundant half. What stays on
# the logger is the cost estimate alone, which is not a warning about the module — it is a heads-up
# about the wall clock, owed before the query rather than in the report after it.

SIDECAR_NAME: str = "expression_effects.csv"
SOURCE_NAME: str = ALPHAGENOME_ATLAS_TERMS.source
SOURCE_LAYER: str = "expression_effect"

#: The one scorer RM200 adopted, and the value `effect_measure` records.
SCORER: str = "RNA_SEQ"

#: The assembly AlphaGenome serves, and it serves no other.
#:
#: **A fact about the source, which is why it is stated rather than defaulted.** It reaches two places
#: that were two statements of one thing: the build-mismatch warning every coordinate writer owes, and
#: the `build=` every identity mint owes (`@build-in-manifest-only` — the build lives in the manifest
#: and no parquet column, so it is passed to each mint call).
#:
#: **It is the SOURCE's build, never the module's, and on a GRCh37 module those differ.** The
#: coordinate in the row came from AlphaGenome, so the identity minted from it names GRCh38 — minting
#: it as GRCh37 would claim a conversion nobody performed. The disagreement is *reported* by
#: `source_build_mismatch` and never repaired, which is the same call every drafting provider makes.
SOURCE_BUILD: str = "GRCh38"

#: Measured throughput, ALPHAGENOME_ATLAS probe 2026-09-10: ~1,091 SNVs/s end to end. Named rather
#: than inlined because it is the basis of the cost estimate the pass prints before it runs, and a
#: magic number in a warning is a number nobody can re-derive.
MEASURED_SNVS_PER_SECOND: int = 1091

#: Roughly three SNVs per base (the three non-reference substitutions), which is what turns an
#: interval width into a query cost. Proved over the AVI artifact's whole 8.8e9 rows in RM197.
SNVS_PER_BASE: int = 3

#: How many rows this pass will write before refusing. A gene plus its flanks is ~3.3 M SNVs, and a
#: CSV sidecar of that size is not a sidecar — but silently truncating would be worse than refusing,
#: so the refusal names the count and the two ways past it (`--min-score`, `--max-rows`).
DEFAULT_MAX_ROWS: int = 50_000

_FIELDNAMES: list[str] = list(ExpressionEffectRow.model_fields)

#: Every reason a candidate was admitted and then not written, each counted separately. A withhold
#: that cannot say which kind it was is the absence this roster exists to prevent.
WITHHELD_REASONS: tuple[str, ...] = (
    "below_min_score",
    "no_gene_axis",
    "already_recorded",
)


class ExpressionError(RuntimeError):
    """This pass could not do its job. The local half — bad input, an unreadable sidecar, a refusal."""


class ExpressionUnavailable(ExpressionError):
    """The Atlas did not answer. Retryable, and **its own type** rather than a bare `ExpressionError`.

    `@client-exception-contract`: a pass owes its own type too, and translating to an `*Unavailable`
    subclass is what lets a caller tell "the service is down, try later" from "your input is wrong".
    `gwas.py` is exempt from that guard only because its client and its pass share one error type
    declared in one module; `AtlasError` lives in `atlas_client`, a foreign module, so this pass is
    not exempt and does not claim to be.
    """


@dataclass
class ExpressionResult:
    """What one run did, with every admitted candidate accounted for."""

    rows: list[ExpressionEffectRow] = field(default_factory=list)
    gene: str | None = None
    interval: tuple[str, int, int] | None = None
    span: GeneSpan | None = None
    #: Variants the service returned a scored block for.
    candidates: int = 0
    written: int = 0
    withheld: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    dataset: str | None = None
    skipped: bool = False

    def accounts_for_every_candidate(self) -> bool:
        """Every admitted candidate was either written or counted under a named reason."""
        return self.candidates == self.written + sum(self.withheld.values())

    def withhold(self, reason: str) -> None:
        if reason not in WITHHELD_REASONS:
            raise ExpressionError(f"{reason!r} is not one of the named withholding reasons")
        self.withheld[reason] = self.withheld.get(reason, 0) + 1


def _gene_block(score) -> tuple[tuple[float, ...], str | None, str | None]:
    """The `RNA_SEQ` track vector for the one filtered gene, or `(…, a refusal reason)`.

    **The shape assertion is load-bearing.** A gene-filtered query answers `(1, tracks)`, and an
    unfiltered one answers `(genes, tracks)` row-major with genes as the major axis — measured
    against the service, by re-querying one gene and matching the row-major slice bit for bit. This
    pass always filters, so anything but a leading axis of 1 means the filter did not apply, and
    guessing which gene a multi-gene block belongs to would be exactly the invented attribution
    `@gene-map-is-another-sources-attribution` forbids.
    """
    for block in score.scores:
        if block.scorer != SCORER:
            continue
        shape = tuple(block.shape or ())
        if len(shape) == 2 and shape[0] != 1:
            return (), "no_gene_axis", None
        # The accession the service itself attributed the block to, when it sent one. With a
        # single-gene filter there is exactly one, which the shape assertion above has just proved.
        attributed = block.genes[0].gene_id if getattr(block, "genes", ()) else None
        return tuple(block.raw or ()), None, attributed
    return (), "no_gene_axis", None


def _summarise(values: tuple[float, ...]) -> tuple[float | None, str | None, int, int]:
    """`(effect_size, effect_direction, tracks_agreeing, tracks_total)` for one gene's tracks.

    **Two different questions, deliberately answered separately.** `effect_size` is the single
    strongest tissue effect *keeping its sign*, which is the number the AVI artifact discards by
    taking `MAX_ABS`; `effect_direction` is the majority sign across all tracks, which is a claim
    about consensus. They can disagree — one tissue moving hard against a mild general trend — and
    that disagreement is real rather than an inconsistency to smooth over.

    Nothing is withheld on low agreement. RM200 tested consensus-as-confidence and killed it: `CAGE`
    is 97% unanimous at a `PHRED` of 0.007, so agreement does not separate a consequential variant
    from an inconsequential one. The counts are recorded; no threshold reads them.
    """
    finite = tuple(v for v in values if math.isfinite(v))
    if not finite:
        return None, None, 0, len(values)
    extreme = max(finite, key=abs)
    positive = sum(1 for v in finite if v > 0)
    negative = sum(1 for v in finite if v < 0)
    if positive == negative:
        return extreme, None, 0, len(finite)
    direction = "increase" if positive > negative else "decrease"
    return extreme, direction, max(positive, negative), len(finite)


def _distance(span: GeneSpan | None, position: int) -> int | None:
    """Base pairs from `position` to the gene, `0` inside it, `None` when no span is known.

    `None` rather than a fallback: the honest record of "the MANE lane is not provisioned" is the
    absence, and an interval edge would be a number that looks like a distance and is not one.
    """
    if span is None:
        return None
    if span.start <= position <= span.end:
        return 0
    return span.start - position if position < span.start else position - span.end


def _resolve_interval(
    gene: str,
    chrom: str | None,
    start: int | None,
    end: int | None,
    mane_cache: Path | None,
    result: ExpressionResult,
) -> tuple[str, int, int] | None:
    """The interval to query and the span to measure distance against, or `None` to skip.

    The two are separate questions and the MANE lane answers both, which is why it is consulted even
    when the interval was supplied by hand: an explicit interval makes the *query* possible without
    MANE, and it does not make `distance_to_gene` computable.
    """
    explicit = chrom is not None and start is not None and end is not None
    lookup = None
    try:
        lookup = gene_span(gene, mane_cache=mane_cache)
    except GeneSpanError as exc:
        # A present-but-unreadable snapshot is a defect, not an absence — but it must not sink a run
        # whose interval the operator already supplied.
        if not explicit:
            raise ExpressionError(str(exc)) from exc
        result.warnings.append(f"{gene}: {exc}; distance_to_gene will be null")

    if lookup is not None and lookup.span is not None:
        result.span = lookup.span
    elif lookup is not None:
        note = f"{gene}: {SPAN_REASONS[lookup.reason]}"
        if not explicit:
            result.warnings.append(note)
            result.skipped = True
            return None
        result.warnings.append(f"{note} — distance_to_gene will be null for every row")

    if explicit:
        return chrom, int(start), int(end)
    return result.span.widened(ATTRIBUTION_HORIZON_BP)


def _cost_note(interval: tuple[str, int, int]) -> str:
    """What this query will cost, said before it is spent rather than discovered.

    RM194 left the provider unbuilt partly because a gene plus flanks is ~50 minutes, and the entry
    is explicit that the provider must say so rather than let an operator find out.
    """
    _, start, end = interval
    snvs = max(0, end - start) * SNVS_PER_BASE
    minutes = snvs / MEASURED_SNVS_PER_SECOND / 60
    return (
        f"querying {end - start:,} bp ≈ {snvs:,} SNVs; at the measured {MEASURED_SNVS_PER_SECOND:,} "
        f"SNVs/s that is about {minutes:.0f} minute(s). A whole gene plus its ±512 kb flanks is "
        f"around 50 minutes, which is why this pass is not a genome-wide one."
    )


def _connect():
    """A client of our own, for a caller that injected none.

    The credential is read **here, where it is used** rather than as a side effect of some earlier
    call (`@credential-where-read`), and an empty string and an unset variable are one absence —
    `export ALPHAGENOME_API_KEY=` must mean the same thing as never setting it.

    **`load_env()` first, which is the half this had missing** (RM212). Reading `os.environ` at the
    point of use is only half the rule; nothing else on this command's path loads a `.env`, so a key
    that lives only there — which is where this workspace's does — was invisible and the pass refused
    with *is not set* while the file sat in the working directory. Measured. It is the same incident
    `caches._rebuild_pharmvar` carries a comment about, one lane over: a check that answers
    differently from the code it stands in front of is worse than no check.
    """
    load_env()
    key = os.environ.get("ALPHAGENOME_API_KEY") or ""
    if not key:
        raise ExpressionError(
            f"ALPHAGENOME_API_KEY is unusable: {missing_credential_reason('ALPHAGENOME_API_KEY')}. "
            "This pass has no snapshot to fall back on — set it, or pass --offline to make the run "
            "an explicit no-op."
        )
    return connect(key)


def _cell(value: object) -> str:
    """One value to a canonical CSV cell, matching the compiler's `_scalar_cell` exactly, so a
    column added later is spelled the same by this writer and by `reverse`."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_csv(rows: list[ExpressionEffectRow], output_path: Path) -> None:
    """Fixed column order, canonical cells, byte-stable across runs, written atomically.

    A pure build product: a correction to a derived row belongs in `overrides.csv`, which is what
    makes deleting this file and re-running cost nothing (`@sidecar-authoritative`).
    """
    with atomic_writer(output_path, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            dumped = row.model_dump()
            writer.writerow({name: _cell(dumped.get(name)) for name in _FIELDNAMES})


def _sort_key(row: ExpressionEffectRow) -> tuple:
    """Deterministic emission order (Principle 7). Every component a string or an int with a
    default, so a row missing a coordinate sorts beside one that has it rather than raising."""
    return (row.gene, row.chrom or "", row.start or 0, row.ref or "", row.alt or "", row.variant_key)


def enrich_expression(
    spec_dir: Path,
    gene: str,
    *,
    chrom: str | None = None,
    start: int | None = None,
    end: int | None = None,
    client=None,
    mane_cache: Path | None = None,
    min_score: float | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
    declared_use: str = "unstated",
    dataset: str | None = None,
    offline: bool = False,
    write: bool = True,
) -> ExpressionResult:
    """Query one gene's interval and merge the answers into `expression_effects.csv`.

    Merge-not-clobber on `(variant_key, gene)`: an existing row is authoritative and a re-run
    gap-fills. Delete the file to re-derive it, which costs nothing because no authored judgement
    lives in it.
    """
    spec_dir = Path(spec_dir)
    result = ExpressionResult(gene=gene)
    output_path = sidecar_path(spec_dir, SIDECAR_NAME, error=ExpressionError)

    # **`offline` outranks an injected client** (RM220), which is `pgx`'s reading and not `gwas`'s.
    # The two shapes coexist in this tier and the difference is the source's licence, not a
    # preference: the GWAS Catalog is ungated, so handing over a transport you already hold really is
    # not egress. The Atlas is **not** — its Additional Terms bar classes of holder outright — so a
    # live client under a flag documented as making no egress is exactly the loophole RM38 closed for
    # the PGx sources, and `test_pgx_licensing.py` already asserts the strict reading by name. This
    # gated `offline and client is None`, so an injected client fetched from a gated source under
    # `--offline`. `@flag-means-same`.
    if offline:
        note = (
            "expression pass skipped: --offline. This pass reads the Atlas API and has no snapshot "
            "to fall back on, so it is a no-op offline rather than a failure. An injected client "
            "does not override it: the Atlas is licence-gated, so --offline means no egress."
        )
        result.warnings.append(note)
        result.skipped = True
        return result

    # The gate runs before anything is fetched (`@acquisition-gate-is-not-a-read-gate`). With
    # `commercial_use=False` an undeclared run is a SKIP, not permission — the tool must not assert a
    # purpose on the operator's behalf.
    refusal = check_declared_use(ALPHAGENOME_ATLAS_TERMS, declared_use)
    if refusal is not None:
        result.warnings.append(refusal)
        result.skipped = True
        return result

    existing: list[ExpressionEffectRow] = []
    if output_path.exists():
        parsed, errors, _ = load_csv_rows(output_path, ExpressionEffectRow, output_path.name)
        if errors:
            raise ExpressionError(f"existing {output_path.name} is invalid: {errors[0]}")
        existing = parsed

    interval = _resolve_interval(gene, chrom, start, end, mane_cache, result)
    if interval is None:
        return result
    result.interval = interval
    logger.warning("expression pass: %s", _cost_note(interval))

    # Every coordinate writer owes this (`@restamp-for-build` one layer up): AlphaGenome publishes
    # GRCh38 only, and a GRCh37 module would silently receive GRCh38 positions. Reported, never
    # repaired and never refused.
    mismatch = source_build_mismatch(spec_dir, SOURCE_NAME, source_build=SOURCE_BUILD)
    if mismatch:
        result.warnings.append(mismatch)

    release = dataset or f"alphagenome_atlas_{now_utc_iso()[:10]}"
    fetched_at = now_utc_iso()
    result.dataset = release

    if client is None and not ATLAS_CLIENT_AVAILABLE:
        raise ExpressionError(
            "the Atlas client is unavailable: install `just-dna-enricher[atlas]` and run "
            "`just-dna-enricher atlas generate` to build the protobuf bindings"
        )
    try:
        scores = (client or _connect()).score_interval(
            interval[0], interval[1], interval[2], scorers=(SCORER,), gene_names=(gene,)
        )
    except AtlasUnavailable as exc:
        raise ExpressionUnavailable(
            f"the Atlas did not answer for {gene} at {interval[0]}:{interval[1]}-{interval[2]}: {exc}"
        ) from exc
    except AtlasError as exc:
        raise ExpressionError(
            f"the Atlas refused the query for {gene} at {interval[0]}:{interval[1]}-{interval[2]}: {exc}"
        ) from exc

    if not scores:
        # `@unreachable-not-absent`: write no row, name it separately. An interval beyond the model's
        # ±512 kb horizon and a symbol the service does not attribute to anything both look like this
        # from here, so the warning names both rather than picking one.
        note = (
            f"{gene}: the Atlas attributed no scored variant in "
            f"{interval[0]}:{interval[1]}-{interval[2]}. Either the interval lies beyond the model's "
            f"±512 kb attribution horizon for this gene, or the service does not know the symbol — "
            f"this surface cannot tell those apart, and neither is written as a row."
        )
        result.warnings.append(note)
        return result

    seen = {merge_key(row) for row in existing}
    out = list(existing)

    for score in scores:
        result.candidates += 1
        values, refused, gene_id = _gene_block(score)
        if refused is not None:
            result.withhold(refused)
            continue
        effect_size, direction, agreeing, total = _summarise(values)
        if min_score is not None and (effect_size is None or abs(effect_size) < min_score):
            result.withhold("below_min_score")
            continue

        # The artifact ships `chr22`; a `VariantRow` stores `22`. RM193 found this exact join
        # matching nothing while looking like an uncovered region, so the strip happens here.
        contig = str(score.chrom).removeprefix("chr")
        row = ExpressionEffectRow(
            variant_key=derive_variant_key(
                None, contig, score.position, score.ref, score.alt, build=SOURCE_BUILD
            ),
            chrom=contig,
            start=score.position,
            ref=score.ref,
            alt=score.alt,
            gene=gene,
            gene_id=gene_id,
            effect_size=effect_size,
            effect_measure=SCORER,
            effect_direction=direction,
            tracks_agreeing=agreeing,
            tracks_total=total,
            distance_to_gene=_distance(result.span, score.position),
            dataset=release,
            source=SOURCE_NAME,
            status="resolved",
            fetched_at=fetched_at,
        )
        key = merge_key(row)
        if key in seen:
            result.withhold("already_recorded")
            continue
        seen.add(key)
        out.append(row)
        result.written += 1

    if len(out) > max_rows:
        raise ExpressionError(
            f"{len(out):,} rows would be written to {SIDECAR_NAME}, over the {max_rows:,} cap. "
            f"A CSV sidecar of that size is not a sidecar, and truncating silently would be worse "
            f"than refusing. Raise the bar with --min-score (distal scores run ~10x lower than "
            f"scores at the gene, so a distance-aware bar keeps more of what matters), narrow the "
            f"interval, or raise --max-rows deliberately."
        )

    out.sort(key=_sort_key)
    if write and result.written:
        _write_csv(out, output_path)
        merge_sources_file(
            [ALPHAGENOME_ATLAS_TERMS.row(SOURCE_LAYER, declared_use=declared_use, dataset=release)],
            spec_dir,
            error=ExpressionError,
        )
    result.rows = out
    return result
