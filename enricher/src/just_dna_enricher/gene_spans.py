"""Gene symbol → GRCh38 span, from the operator-built MANE snapshot (0.7, RM194).

**There was no such helper in this tier before**, which is why this is a module with a plain name
rather than a private function inside the pass that first needed one. The rule is
`@roster-is-as-wide-as-the-tables-it-reads`'s last line — grep for the *question*, not the bug, since
a private name keeps the second caller from finding the first. "Where does a gene's span come from"
is a question three different passes could ask, and RM194's entry lists the three candidate answers
precisely because nobody had written one down.

**A span from here is a QUERY HINT, never an attribution.** That distinction is what makes the
design decisions below easy, and it is `@gene-map-is-another-sources-attribution` read carefully: a
source with no gene column is drafted by gene through another source's *per-record* attribution and
never from a span, because a min/max span is a false `gene` claim wherever genes overlap or nest.
RM194's case inverts that — AlphaGenome **is** the attributing source, it names the gene on every
record it returns, and the span only decides which interval to ask about. So a span that is too wide
costs query time and nothing else, and a span that is stale means variants were missed rather than
wrongly labelled. Nothing downstream may use a span from here to *assign* a gene to anything.

**Why MANE and not the alternatives.** The Ensembl snapshot is eliminated by its own schema — it is a
variant table with no gene column at all. A module's own authored `gene` is a symbol rather than a
span, so it needs one of the others anyway. MANE is the remaining candidate and is operator-built, so
absence is the ordinary case and has to be an answer rather than an exception.

**Three outcomes, not two** (`@unreachable-not-absent`). No snapshot is *nobody asked*; a snapshot
that does not name the symbol is *asked and absent*; and a symbol placed on a contig RefSeq does not
number in the primary assembly is a third, because returning a coordinate space we cannot name would
be worse than saying so. `SpanLookup` keeps them apart by reason, and a caller that collapses them
back into a bare `None` has thrown away the difference between "build the MANE lane" and "check the
spelling of that symbol".
"""

from dataclasses import dataclass
from pathlib import Path

import duckdb

from just_dna_enricher.locations import resolve_mane_reference
from just_dna_enricher.pharmvar import chrom_from_accession

#: How far AlphaGenome attributes a variant to a gene, in base pairs either side of the gene's span.
#:
#: **Measured, not assumed** (ALPHAGENOME_ATLAS probe, 2026-09-10): gene-filtered scores come back at
#: +500 kb and stop dead at +700 kb, which is the half-window of the model's 1 Mb input. So this is a
#: property of the model rather than a tuning choice, and widening it past 512 kb buys an interval the
#: server will attribute to nobody.
ATTRIBUTION_HORIZON_BP: int = 512_000

#: The file inside a MANE snapshot that carries the spans. Named here rather than spelled at the call
#: site so a snapshot layout change is one edit.
_SUMMARY_PARQUET: str = "summary.parquet"


class GeneSpanError(RuntimeError):
    """The MANE snapshot is present and could not be read — a defect, not an absence."""


@dataclass(frozen=True)
class GeneSpan:
    """One gene's GRCh38 extent, 1-based inclusive, as MANE places it."""

    gene: str
    chrom: str
    start: int
    end: int
    #: Which MANE rows this came from, e.g. `('MANE Select',)`. Recorded so a caller can say what it
    #: asked about rather than only what it got back.
    mane_status: tuple[str, ...]

    def widened(self, flank: int = ATTRIBUTION_HORIZON_BP) -> tuple[str, int, int]:
        """`(chrom, start, end)` with the attribution horizon added either side, clamped at 1.

        Clamped rather than allowed to go negative: `start` is a 1-based VCF position everywhere in
        this workspace (`@start-1based`), and a gene within 512 kb of a contig's start is the ordinary
        case on the short arms rather than an edge worth refusing.
        """
        return self.chrom, max(1, self.start - flank), self.end + flank


@dataclass(frozen=True)
class SpanLookup:
    """What happened when a symbol was looked up. Exactly one of `span`/`reason` is set."""

    span: GeneSpan | None = None
    #: `no_snapshot` | `not_in_mane` | `unplaced_contig` | `contig_disagreement`. Kept as a token
    #: rather than a sentence so a caller can branch on it and still print its own words.
    reason: str | None = None

    def __post_init__(self) -> None:
        if (self.span is None) == (self.reason is None):
            raise GeneSpanError(
                "a SpanLookup states a span or a reason and never both or neither — a lookup that "
                "answered nothing without saying why is the absence this type exists to prevent"
            )


def _connect(snapshot: Path) -> duckdb.DuckDBPyConnection:
    # DuckDB cannot bind a parameter inside CREATE VIEW ... read_parquet(), the same constraint
    # `clinvar._connect` documents. The path comes from our own cache resolution rather than from a
    # caller, and is single-quote-escaped defensively all the same.
    path = str(snapshot / _SUMMARY_PARQUET).replace("'", "''")
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW mane AS SELECT * FROM read_parquet('{path}')")
    return con


def gene_span(symbol: str, *, mane_cache: Path | None = None) -> SpanLookup:
    """The GRCh38 span MANE gives `symbol`, or a reason there is none.

    **Rows are unioned rather than picked between, and that is a consequence of this being a hint.**
    A symbol can carry more than one summary row — MANE Select plus MANE Plus Clinical — and the two
    are different transcripts of one gene, so choosing one would be choosing a transcript on the
    caller's behalf for a value that is not about transcripts at all. The union is the widest window,
    and a window that is too wide costs query time while a window that is too narrow drops the distal
    variants RM194 exists to find. Asymmetric costs, so take the wide side.

    Rows disagreeing on the **contig** is the one case that refuses: that is not a wider gene, it is
    two genes wearing one symbol, and a span spanning both would name a region containing neither.
    """
    snapshot = resolve_mane_reference(mane_cache)
    if snapshot is None:
        return SpanLookup(reason="no_snapshot")

    con = _connect(snapshot)
    try:
        rows = con.execute(
            "SELECT grch38_chr, chr_start, chr_end, mane_status FROM mane "
            "WHERE symbol = ? AND chr_start IS NOT NULL AND chr_end IS NOT NULL",
            [symbol],
        ).fetchall()
    except duckdb.Error as exc:
        raise GeneSpanError(
            f"the MANE snapshot at {snapshot} could not be read for {symbol!r}: {exc}. It is present, "
            f"so this is a malformed or partial snapshot rather than an absent one — rebuild it with "
            f"`just-dna-enricher mane build`."
        ) from exc
    finally:
        con.close()

    if not rows:
        return SpanLookup(reason="not_in_mane")

    # `GRCh38_chr` stays the RefSeq accession in the snapshot, deliberately — the builder keeps what
    # the source wrote. `NC_000022.11` → `22`, and `None` for anything RefSeq does not number in the
    # primary assembly, which is a third answer rather than a contig to guess at.
    contigs = {chrom_from_accession(accession.split(".")[0].removeprefix("NC_")) for accession, *_ in rows}
    if contigs == {None}:
        return SpanLookup(reason="unplaced_contig")
    placed = {c for c in contigs if c is not None}
    if len(placed) > 1:
        return SpanLookup(reason="contig_disagreement")

    chrom = placed.pop()
    usable = [
        row for row in rows
        if chrom_from_accession(row[0].split(".")[0].removeprefix("NC_")) == chrom
    ]
    return SpanLookup(
        span=GeneSpan(
            gene=symbol,
            chrom=chrom,
            start=min(int(row[1]) for row in usable),
            end=max(int(row[2]) for row in usable),
            mane_status=tuple(sorted({str(row[3]) for row in usable if row[3]})),
        )
    )


#: What each `SpanLookup.reason` means to an operator, in the words the pass prints. Separate from
#: the token so a reason map is one edit rather than a sentence copied into every caller — and a
#: verdict with several arms owes a reason function with the same arms, pairwise distinct
#: (`@answered-is-not-absent`).
SPAN_REASONS: dict[str, str] = {
    "no_snapshot": (
        "no gene span is available: the `mane` cache lane is not provisioned, so nothing was asked "
        "rather than asked and not found. Build it with `just-dna-enricher mane build`, or pass "
        "--chrom/--start/--end to supply the interval directly"
    ),
    "not_in_mane": (
        "the MANE snapshot is provisioned and names no such gene symbol. Check the spelling against "
        "the approved HGNC symbol — MANE carries one row per gene under its current name"
    ),
    "unplaced_contig": (
        "MANE places this gene on a contig outside the primary assembly, which has no coordinate "
        "space this workspace can name. Supply --chrom/--start/--end if you know the placement"
    ),
    "contig_disagreement": (
        "the MANE snapshot places this symbol on more than one contig, which is two genes sharing a "
        "name rather than one wider gene. Supply --chrom/--start/--end to say which is meant"
    ),
}
