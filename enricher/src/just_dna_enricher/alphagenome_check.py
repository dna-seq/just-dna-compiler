"""The Atlas as a resolver — the three things the local artifact provably cannot do (RM193).

RM191's snapshot answers "what did AlphaGenome score this variant?" for 8.8 billion SNVs offline.
This pass exists for the questions it **cannot** answer, and deliberately for nothing else. Reports,
never repairs (`@enrichment-is-validation`).

**(a) A knot the caller's threshold falls inside.** The snapshot stores `raw_score` and reconstructs
`PHRED` through the knot table, which publishes an *interval* per printed score rather than a point.
Where a caller's threshold lands inside that interval the local data genuinely cannot decide, and
the Atlas can: its `raw_score` is a `float32`, ~7 significant digits against the file's 4, and at
the atom that causes every threshold-3 flip six rows the file prints identically as `0.00076` come
back distinct and reproduce the published `PHRED` exactly at five decimals (§ 4.7.1).

That scope is small and **decidable before any request is made** — from 466 KB of knots, without
reading a data row. Genome-wide exactly one knot straddles any integer threshold from 1 to 50, so a
module's candidate set is normally empty and occasionally a handful. **The check refuses to run
unbounded**: rebuilding the column wholesale is 272 days and ~92 M RPCs at the measured rate, and
prohibition 3 makes it the wrong shape of request anyway.

**(b) A `REF` that disagrees with GRCh38.** The Atlas validates it and **names the real base** —
`"reference base does not match the expected reference base: G."` A local file lookup cannot produce
that finding: it simply misses, and a miss is indistinguishable from an unscored position
(`@va-omits-ref` — a VA does not encode `ref`). So the finding carries the observed base, grouped by
reason (`@ref-mismatch-causes`).

**(c) An answer that does not exist.** An indel returns `UNIMPLEMENTED`, which is the third state
rather than a refusal: the request was legal and the Atlas has no score. It is recorded as
could-not-ask and never as a zero (`@unreachable-not-absent`), and `--offline` produces the *same*
third state rather than a silent skip — nobody-asked and asked-and-absent are different, and both
are different from scored-zero, of which the corpus holds 672,931.

**It emits its own check member rather than reusing `reference_allele`.** That check compares an
authored `ref` against the reference *sequence* and belongs to `enrich`; letting an Atlas outage
write a skip against it would make one registry's availability speak for another's question
(`@one-registrys-outage-may-not-speak-for-another`). Two sources, two checks, side by side.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.spec import VariantRow

from just_dna_enricher.alphagenome_avi_build import (
    KNOT_FILENAME,
    RAW_SCORE_SCALE,
    to_long,
)
from just_dna_enricher.licensing import ALPHAGENOME_AVI_TERMS
from just_dna_enricher.locations import (
    SNAPSHOT_DATA_DIRNAME,
    resolve_alphagenome_avi_reference,
)
from just_dna_enricher.verification import ran, record_verification, skipped

# The guarded optional import (CLAUDE.md), and here it guards **most of this module**: everything
# except `_refine` is offline, so a deployment without the [atlas] extra must still be able to read
# the snapshot, reconstruct a PHRED and ask whether a threshold is safe. A module-level `import grpc`
# would make the extra a requirement of the whole CLI, which is the cost RM192 measured its way out
# of.
#
# The fallback binds a class that is never raised rather than `None`, so the `except` arms below stay
# well-formed expressions: `except _NeverRaised` simply never matches, which is exactly right when
# there is no client to have raised anything.
try:
    from just_dna_enricher.atlas_client import (
        AtlasError,
        AtlasNotScored,
        AtlasRefMismatch,
        AtlasRefused,
        AtlasUnavailable,
    )

    ATLAS_CLIENT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised where the [atlas] extra is absent

    class _NeverRaised(Exception):
        """Stands in for an Atlas error type when no client can exist to raise one."""

    AtlasError = AtlasNotScored = AtlasRefMismatch = AtlasRefused = AtlasUnavailable = _NeverRaised
    ATLAS_CLIENT_AVAILABLE = False

logger = logging.getLogger(__name__)

VARIANTS_CSV = "variants.csv"
SOURCE_NAME = ALPHAGENOME_AVI_TERMS.source

#: The check this pass attests, and the reason it is not `reference_allele` is in the module
#: docstring: two registries answering overlapping questions get two checks, never one.
CHECK = "variant_impact_agreement"

#: The Atlas scorer the AVI artifact is the bulk copy of. Named rather than inlined so the pass and
#: a test ask for the same thing.
AVI_SCORER = "AVI_SCORE"

#: How many variants one invocation may refine over the network. **A floor a deployment raises, not
#: a fixed set** (`@retry-attempt-floor`): the number that matters is that it is bounded at all.
#: Rebuilding the whole column is 272 days of requests, and a check that would start down that road
#: because a caller passed a threshold with a large candidate set is a check that has to refuse.
DEFAULT_REFINEMENT_CAP = 200


class VariantImpactError(RuntimeError):
    """The check could not run in a way the caller must see. Never raised for an absent answer."""


# **There is deliberately no `VariantImpactUnavailable`.** Every other pass in this tier owes one,
# because a source it cannot reach is a run it cannot complete. This one can: a transport failure is
# recorded against the variant as `unreachable` and the run returns a *complete* report saying which
# variants were never asked about. A type nobody raises is a promise nobody keeps, so it is not
# declared — the same call `enrich.enrich`, `litvar.check_literature_coverage` and the two
# `civic_citations` passes make, and the reason all five are exempt from the pass-contract guard.


@dataclass(frozen=True)
class ImpactFinding:
    """One thing the Atlas said that the local artifact could not have said.

    `kind` is the remediation key, not the emission site (`@warning-code-names-the-finding`): a
    reader grouping by it gets one bucket per thing they can do about it.
    """

    kind: str
    variant: str
    detail: str
    observed_ref: str | None = None

    def __str__(self) -> str:
        base = f"{self.variant}: {self.detail}"
        return f"{base} (reference base is {self.observed_ref})" if self.observed_ref else base


@dataclass
class VariantImpactResult:
    """What was decided, what was refined, and what could not be asked — the tri-state, reportable."""

    findings: list[ImpactFinding] = field(default_factory=list)
    #: Variants the local snapshot decided on its own. The attestation's denominator, with `refined`.
    decided: list[str] = field(default_factory=list)
    #: Variants whose knot straddled the threshold and which the Atlas resolved. A subset of what
    #: `straddling` names — the rest are `unresolved` when the network could not answer.
    refined: list[str] = field(default_factory=list)
    #: `(variant, reason)` for every variant with **no answer at all**, and the reasons stay apart:
    #: `not_scored` (the Atlas says there is none), `offline` (nobody asked), `unreachable` (asked,
    #: no answer), `absent_from_snapshot` (the local artifact has no row). Four histories, four
    #: remedies, and none of them is a zero.
    unanswered: list[tuple[str, str]] = field(default_factory=list)
    #: Variants whose knot spans the threshold — computed offline, before any request.
    straddling: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    threshold: float | None = None
    dataset: str | None = None

    @property
    def subjects(self) -> int:
        """The denominator the attestation publishes: every variant this pass had an opinion about.

        **Distinct variants, not `len(decided) + len(unanswered)`**, because a variant can be in
        both: the snapshot decides it, and then a threshold falling inside its knot leaves it
        unresolved. A three-variant module reported four subjects until this counted a set — an
        attestation whose denominator exceeds the rows it was computed over is worse than no
        denominator, since it reads as coverage nobody had.
        """
        return len({*self.decided, *(label for label, _ in self.unanswered)})


def _label(variant: VariantRow) -> str:
    """How a variant is named in a finding. One spelling, so two findings about one row match."""
    alt = (variant.alts or "").split(",")[0] if getattr(variant, "alts", None) else ""
    return f"{variant.chrom}:{variant.start} {variant.ref or ''}>{alt}".strip()


def load_module_variants(spec_dir: Path) -> list[VariantRow]:
    """The module's authored variants, or an empty list when it has none.

    An empty list is not an error: a module with no `variants.csv` has posed no question the Atlas
    could answer, and the caller returns without attesting rather than mining a nonce for a check
    that did not apply.
    """
    path = spec_dir / VARIANTS_CSV
    if not path.is_file():
        return []
    rows, errors, _ = load_csv_rows(path, VariantRow, VARIANTS_CSV)
    if errors:
        raise VariantImpactError(f"{VARIANTS_CSV}: {errors[0]}")
    return rows


def _contig_of(path: Path) -> str:
    """The contig a snapshot parquet holds, from its own name.

    `alphagenome_avi-chr6.parquet` → `chr6`. Derived from the filename the builder writes rather
    than by opening the file, because the point is to decide *not* to open it.
    """
    return path.stem.split("-", 1)[-1]


def artifact_contig(chrom: str) -> str:
    """A module's `chrom` in the spelling the AVI artifact uses.

    **Two conventions meet here and neither is wrong.** `VariantRow` normalizes through
    `vrs.normalize_chrom`, which strips the prefix and stores `22`; AlphaGenome ships UCSC-style
    `chr22`, and its tabix index is keyed that way. Joining the module's spelling straight onto the
    snapshot silently matches **nothing** — every row comes back `absent_from_snapshot`, which reads
    exactly like an artifact that does not cover the variant, and is the kind of wrong answer this
    tier's three-valued algebra exists to make impossible.

    One direction only, and at the boundary: the snapshot's spelling is the source's, so the
    conversion belongs to the reader that crosses into it rather than to either model.

    Delegated to `atlas_client.wire_contig` rather than duplicated: the RPC boundary needs the same
    conversion, and two copies of one normalizer is the defect `@one-normalizer-two-spellings` names.
    Kept as a named function here because the snapshot join is a different boundary from the wire,
    and a reader of this module should find the rule where the join is.
    """
    if ATLAS_CLIENT_AVAILABLE:
        from just_dna_enricher.atlas_client import wire_contig

        return wire_contig(chrom)
    value = str(chrom).strip()
    return value if value.lower().startswith("chr") else f"chr{value}"


def _polars():
    try:
        import polars as pl
    except ImportError as exc:  # pragma: no cover - the [dev] extra declares it
        raise VariantImpactError(
            "polars is required to read the AlphaGenome snapshot: `pip install 'just-dna-enricher[dev]'`"
        ) from exc
    return pl


@dataclass(frozen=True)
class LocalScore:
    """One variant's answer from the snapshot, with the ambiguity the knot table records.

    `phred_lo`/`phred_hi` are the **interval**, never a midpoint: where they bracket a caller's
    threshold the local data cannot decide, and saying so is the whole point of publishing them.
    """

    raw_score_e5: int
    phred_lo: float
    phred_hi: float

    def straddles(self, threshold: float) -> bool:
        return self.phred_lo < threshold < self.phred_hi

    def above(self, threshold: float) -> bool:
        """Only meaningful when the knot does not straddle — the caller checks that first."""
        return self.phred_lo >= threshold


def read_local_scores(reference: Path, variants: list[VariantRow]) -> dict[str, LocalScore]:
    """Look the module's variants up in the snapshot, keyed by `_label`.

    A variant with no row is **absent from the result**, never present with a zero: the artifact
    covers ~95% of the assembly and writes 672,931 genuine zeros, so the two must stay
    distinguishable (`@unreachable-not-absent`).
    """
    pl = _polars()
    data = reference / SNAPSHOT_DATA_DIRNAME
    parquets = sorted(data.glob("*.parquet"))
    if not parquets:
        raise VariantImpactError(f"{reference} holds no {SNAPSHOT_DATA_DIRNAME}/*.parquet")
    knot_path = reference / KNOT_FILENAME
    if not knot_path.is_file():
        raise VariantImpactError(
            f"{reference} has data but no {KNOT_FILENAME}. The curve and the scores are two halves "
            "of one artifact: without the knots a PHRED cannot be reconstructed at all, and a "
            "threshold cannot be checked for safety."
        )

    wanted = []
    for row in variants:
        alt = (row.alts or "").split(",")[0] if row.alts else None
        if not (row.chrom and row.start and row.ref and alt):
            continue
        wanted.append((artifact_contig(row.chrom), int(row.start), row.ref, alt, _label(row)))
    if not wanted:
        return {}

    probe = pl.DataFrame(wanted, schema=["chrom", "pos", "ref", "alt", "label"], orient="row").with_columns(
        pl.col("pos").cast(pl.UInt32)
    )

    # **Pre-filter, then join** (CLAUDE.md, polars in the compiler). The obvious spelling — scan
    # every parquet, cast the categorical key columns, join the probe — reads 8,812,917,339 rows to
    # answer a question about a handful, because the cast has to materialise before the join can use
    # it. It does not merely run slowly: the first smoke test against the real 34 GB artifact was
    # killed by the OOM killer, exit 137, on a module with twelve variants.
    #
    # Two filters do the work. The file names carry the contig, so a module on chr6 never opens the
    # other twenty-three; and `pos` is filtered inside the scan, where parquet's row-group statistics
    # skip almost everything before a row is decoded. Only then is there anything small enough to
    # cast and join.
    by_contig: dict[str, set[int]] = {}
    for chrom, pos, *_ in wanted:
        by_contig.setdefault(chrom, set()).add(pos)
    relevant = [p for p in parquets if _contig_of(p) in by_contig]
    if not relevant:
        return {}

    frames = []
    for path in relevant:
        contig = _contig_of(path)
        positions = sorted(by_contig[contig])
        got = (
            pl.scan_parquet(path)
            .filter(pl.col("pos").is_in(positions))
            .with_columns(pl.col("ref").cast(pl.String))
            .collect()
        )
        if got.height:
            frames.append(got.with_columns(pl.lit(contig).alias("chrom")))
    if not frames:
        return {}
    matched = to_long(pl.concat(frames))

    scored = (
        matched.join(probe, on=["chrom", "pos", "ref", "alt"], how="inner")
        .join(pl.read_parquet(knot_path), on="raw_score_e5", how="left")
        .select("label", "raw_score_e5", "phred_lo", "phred_hi")
    )
    return {
        row["label"]: LocalScore(
            raw_score_e5=row["raw_score_e5"],
            phred_lo=row["phred_lo"],
            phred_hi=row["phred_hi"],
        )
        for row in scored.iter_rows(named=True)
        if row["phred_lo"] is not None
    }


def _refine(client, variant: VariantRow, label: str, result: VariantImpactResult) -> None:
    """Ask the Atlas about one variant, and translate each arm into the state it really is.

    Four arms, four outcomes, pairwise distinct (`@answered-is-not-absent`): a refined answer, a
    finding about the caller's `REF`, a third state for a score that does not exist, and a
    could-not-ask for a service that did not answer. None of them writes a number.
    """
    alt = (variant.alts or "").split(",")[0] if variant.alts else ""
    try:
        blocks = client.score_variant(
            variant.chrom, int(variant.start), variant.ref, alt, scorers=(AVI_SCORER,)
        )
    except AtlasRefMismatch as exc:
        # The one finding a local lookup cannot produce, and the server's own words carry the base.
        observed = str(exc).rstrip(".").rsplit(":", 1)[-1].strip() or None
        result.findings.append(
            ImpactFinding(
                kind="ref_mismatch",
                variant=label,
                detail=(
                    "the Atlas validated REF against GRCh38 and disagrees, so this row's identity "
                    "is wrong rather than its score"
                ),
                observed_ref=observed,
            )
        )
        result.unanswered.append((label, "ref_mismatch"))
        return
    except AtlasNotScored as exc:
        result.unanswered.append((label, "not_scored"))
        result.findings.append(
            ImpactFinding(
                kind="not_scored",
                variant=label,
                detail=(
                    f"the Atlas has no score for this variant ({exc}). Not a zero and not a low "
                    "score — the precomputed set covers SNVs, so an indel has no answer here at all"
                ),
            )
        )
        return
    except AtlasUnavailable:
        result.unanswered.append((label, "unreachable"))
        return
    except AtlasRefused as exc:
        result.unanswered.append((label, "refused"))
        result.findings.append(
            ImpactFinding(kind="refused", variant=label, detail=f"the Atlas declined: {exc}")
        )
        return

    block = next((b for b in blocks if b.scorer == AVI_SCORER), None)
    if block is None or block.phred is None:
        # A saturated quantile lands here: the API caps a derived PHRED at 72.247 while the
        # published artifact reaches 89.451, so above the cap the file is the better source and
        # saying "unknown" is the honest answer (§ 6.3, about 1,300 rows genome-wide).
        result.unanswered.append((label, "not_scored"))
        return
    result.refined.append(label)


def check_variant_impact(
    spec_dir: Path,
    *,
    reference: Path | None = None,
    client=None,
    threshold: float | None = None,
    mode: str = "best_effort",
    offline: bool = False,
    write: bool = True,
    refinement_cap: int = DEFAULT_REFINEMENT_CAP,
) -> VariantImpactResult:
    """Compare a module's variants against AlphaGenome's AVI scores. Reports, never repairs.

    `threshold` is what makes the network leg possible at all: without one there is no question the
    local artifact cannot answer, so the pass stays entirely offline. With one, the knot table says
    — before any request — which variants sit inside an interval spanning it, and only those are
    asked about.

    `mode` is carried for the report and is **not** a severity ladder here. A model's score
    disagreeing with an author's expectation is not a `strict` matter; what `strict` still refuses is
    structural, and that refuses in `best_effort` too.
    """
    spec_dir = Path(spec_dir)
    result = VariantImpactResult(mode=mode, threshold=threshold)

    variants = load_module_variants(spec_dir)
    if not variants:
        # The check does not *apply*. Attesting would mine a nonce and publish a verification block
        # about a question the module never posed — `check_repeat_bands`' rule, same reasoning.
        return result

    if reference is None:
        reference = resolve_alphagenome_avi_reference()
    if reference is None:
        note = (
            "AlphaGenome variant-impact check skipped: no AVI snapshot is provisioned. Build one "
            "with `just-dna-enricher alphagenome build --input <the artifact you downloaded>`; it "
            "is never fetched, because the source is behind an eligibility gate."
        )
        result.warnings.append(note)
        logger.warning("%s", note)
        return _attest(
            result,
            spec_dir,
            write=write,
            record=skipped(CHECK, "no_reference", detail=note, source=SOURCE_NAME),
        )

    local = read_local_scores(reference, variants)
    result.dataset = _dataset_of(reference)

    for row in variants:
        label = _label(row)
        if label in local:
            result.decided.append(label)
        else:
            # Absent from the snapshot is its own reason and not "not scored": the artifact may
            # simply not cover this position, and only the Atlas can tell the two apart.
            result.unanswered.append((label, "absent_from_snapshot"))

    if threshold is None:
        return _attest(
            result,
            spec_dir,
            write=write,
            record=ran(
                CHECK,
                subjects=result.subjects,
                findings=len(result.findings),
                source=SOURCE_NAME,
                release=result.dataset,
            ),
        )

    by_label = {_label(row): row for row in variants}
    result.straddling = sorted(label for label, score in local.items() if score.straddles(threshold))
    if not result.straddling:
        return _attest(
            result,
            spec_dir,
            write=write,
            record=ran(
                CHECK,
                subjects=result.subjects,
                findings=len(result.findings),
                source=SOURCE_NAME,
                release=result.dataset,
            ),
        )

    # **The refusal, and it is decided offline.** Both the cap and the reason come from the knot
    # table, so a caller learns the scope of what they asked for without a single request being
    # spent on it.
    if len(result.straddling) > refinement_cap:
        raise VariantImpactError(
            f"{len(result.straddling)} variants sit inside a knot spanning PHRED {threshold}, over "
            f"the cap of {refinement_cap}. Refining them one by one is the wrong shape of request: "
            "rebuilding the column wholesale is 272 days and ~92 M RPCs at the measured rate, and "
            "the Output Terms' prohibition 3 governs bulk redistribution of the result. The knot "
            f"table already says which rows are affected and by how much — read {KNOT_FILENAME} and "
            "pick a threshold no knot straddles, or raise the cap deliberately."
        )

    if offline:
        for label in result.straddling:
            result.unanswered.append((label, "offline"))
        note = (
            f"{len(result.straddling)} variant(s) sit inside a knot spanning PHRED {threshold} and "
            "were not refined: --offline. That is nobody-asked, not a decision — the local artifact "
            "cannot resolve them and nothing was recorded either way."
        )
        result.warnings.append(note)
        return _attest(
            result,
            spec_dir,
            write=write,
            record=skipped(CHECK, "offline", detail=note, source=SOURCE_NAME),
        )

    if client is None:
        note = (
            f"{len(result.straddling)} variant(s) sit inside a knot spanning PHRED {threshold} and "
            "could not be refined: no Atlas client was supplied"
            + ("" if ATLAS_CLIENT_AVAILABLE else " (and the [atlas] extra is not installed)")
            + ". Install the extra and pass an ALPHAGENOME_API_KEY, or accept the interval the knot "
            "table publishes — which is the honest answer for those rows either way."
        )
        for label in result.straddling:
            result.unanswered.append((label, "no_client"))
        result.warnings.append(note)
        return _attest(
            result,
            spec_dir,
            write=write,
            record=skipped(CHECK, "unchecked", detail=note, source=SOURCE_NAME),
        )

    for label in result.straddling:
        try:
            _refine(client, by_label[label], label, result)
        except AtlasError as exc:  # pragma: no cover - `_refine` translates every arm it knows
            result.unanswered.append((label, "unreachable"))
            logger.warning("atlas refinement failed for %s: %s", label, exc)

    return _attest(
        result,
        spec_dir,
        write=write,
        record=ran(
            CHECK,
            subjects=result.subjects,
            findings=len(result.findings),
            source=SOURCE_NAME,
            release=result.dataset,
        ),
    )


def _dataset_of(reference: Path) -> str | None:
    from just_dna_enricher.locations import read_release

    return (read_release(reference) or {}).get("dataset") or None


def _attest(result: VariantImpactResult, spec_dir: Path, *, write: bool, record) -> VariantImpactResult:
    """Record what this pass checked, merging into whatever another command already wrote."""
    if write:
        record_verification([record], spec_dir, error=VariantImpactError)
    return result


def threshold_is_safe(reference: Path, threshold: float) -> tuple[bool, int]:
    """Whether any knot spans `threshold`, and how many rows sit behind the ones that do.

    The offline half of this module, and the one a caller should reach for first: it costs a read of
    466 KB and answers "can I trust a cut here at all" without touching the network. `True` means
    every row in the corpus is decided at this threshold — which, genome-wide, is every integer from
    1 to 50 except 3.
    """
    pl = _polars()
    knots = pl.read_parquet(reference / KNOT_FILENAME)
    spanning = knots.filter((pl.col("phred_lo") < threshold) & (pl.col("phred_hi") > threshold))
    # `cast(Int64)` before summing, and it is not superstition: polars' `sum()` **preserves the
    # input dtype**, so a `UInt32` count column wraps in the reduction itself with no exception.
    # This reader takes the column from a snapshot on disk, and a snapshot built before that was
    # understood carries `n` as `UInt32` — where a threshold matching most of the corpus would come
    # back as a plausible small number. The writer is fixed; the reader does not get to assume it.
    affected = int(spanning["n"].cast(pl.Int64).sum()) if spanning.height else 0
    return spanning.height == 0, affected


def score_to_threshold(score: float) -> int:
    """A `raw_score` as the integer the snapshot stores, for a caller comparing in the right domain.

    Exposed because the alternative is what every consumer does otherwise: divide `raw_score_e5` by
    1e5 and compare floats, which disagrees with the printed value on 53% of rows. Comparing in the
    integer domain has no such failure mode.
    """
    from decimal import Decimal

    return int(Decimal(str(score)) * RAW_SCORE_SCALE)
