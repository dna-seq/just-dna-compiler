"""PubMind snapshot reader — the runtime half of the source `pubmind_build` writes (RM134 § B).

The split is the one `clinvar.py` draws against `clinvar_build.py`: the builder is polars and lives
behind the `[dev]` extra, the runtime pass is duckdb and ships in the ordinary install
(`@duckdb-vs-polars`). Nothing here builds, downloads or writes.

**This reader answers one question and deliberately not the other one.** `lookup_pubmind_calls`
serves the concordance check in `clinical.py` — *what does PubMind say about this allele* — and there
is no `lookup_loci` beside it, unlike ClinVar's. That absence is structural rather than unfinished
work: PubMind's coordinates are PyEnsembl back-mappings of text an LLM extracted, so they are
annotation and never resolution, and `resolution.csv`'s `authority` column is a different word for a
different thing (`@source-vs-authority`).

**One allele can carry several records, and they are all returned.** Consolidation upstream is keyed
on the *text* PubMind extracted — a gene symbol plus a cDNA or protein change — so one physical
allele fragments into several PVIDs whose verdicts genuinely disagree; the snapshot measured 72,121
allele keys carrying more than one, 35,742 of them disagreeing. Collapsing them here would be
`mode()` over an unsorted group, which the deterministic-ordering rule bans outright. The
multiplicity is a finding, and what to do with it is `clinical._fold_pubmind_records`' judgement —
this half only reads.
"""

import logging
from collections import defaultdict
from pathlib import Path

import duckdb

from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME, read_release
from just_dna_enricher.resolver import probe_table

logger = logging.getLogger(__name__)


class PubMindReferenceError(FileNotFoundError):
    """Raised when a provided PubMind reference has no usable parquet files.

    A `FileNotFoundError` subclass for the reason `ClinVarReferenceError` is one: a caller bracketing
    a snapshot open with `except OSError` keeps working, and a caller that wants to tell "no snapshot
    here" from "this snapshot will not answer" has the type to do it with.
    """


#: The instrument PubMind measures its own confidence on: an integer 0–3 evidence-depth count over
#: the papers behind a verdict. Recorded beside the number and never converted into ClinVar's
#: gold-star count — two authorities publishing an integer on a small scale is not two authorities
#: publishing the same quantity, and folding them would be three axes in one field.
PUBMIND_CONFIDENCE_UNIT: str = "evidence_depth"

#: Prefix of the `SourceRow.dataset` label a PubMind-drafted module carries, matching the label
#: `pubmind_build` writes into `release.json`. Shared rather than mirrored, for the reason
#: `clinvar_dataset_label` is shared: a writer and a reader disagreeing about a label do not fail,
#: they simply never match, and a guard quietly stops being able to fire.
PUBMIND_DATASET_PREFIX = "pubmind_"


def pubmind_dataset_label(reference: Path | None) -> str | None:
    """Which PubMind snapshot this reference carries, as a `SourceRow.dataset` value.

    PubMind publishes no version string of its own, so `pubmind_build` derives the label from the
    sha256 of the bytes it was built from and records it in `release.json`. Read back rather than
    recomputed: recomputing would need the source table, which a deployment holding only the snapshot
    does not have.

    `None` when the snapshot cannot state its release at all — an absent or unreadable `release.json`,
    or one recording no dataset. An unknown is withheld rather than written as a label something could
    match, because a fabricated label is what would make a tautology guard skip a real comparison.
    """
    if reference is None:
        return None
    release = read_release(Path(reference))
    if not release:
        return None
    label = str(release.get("dataset") or "").strip()
    return label or None


def _connect(reference: Path) -> duckdb.DuckDBPyConnection:
    """Open an in-memory connection exposing a `pubmind` view over the reference's parquet files."""
    reference = Path(reference)
    data_dir = reference / SNAPSHOT_DATA_DIRNAME
    if data_dir.is_dir() and any(data_dir.glob("*.parquet")):
        parquet_glob = data_dir
    elif reference.is_dir() and any(reference.glob("*.parquet")):
        parquet_glob = reference
    else:
        raise PubMindReferenceError(
            f"no usable PubMind parquet files at {reference}. Build one with "
            f"`just-dna-enricher pubmind build` — the snapshot is operator-built and is never "
            f"published, so nothing provisions it for you."
        )
    # DuckDB cannot bind a parameter inside `CREATE VIEW ... read_parquet()`. The pattern comes from
    # our own cache resolution rather than from user input; single-quote-escaped defensively, exactly
    # as the ClinVar reader does it.
    pattern = f"{parquet_glob}/*.parquet".replace("'", "''")
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW pubmind AS SELECT * FROM read_parquet('{pattern}')")
    return con


def lookup_pubmind_calls(
    reference: Path,
    alleles: list[tuple[str, int, str, str]],
) -> dict[tuple[str, int, str, str], list[dict]]:
    """`(chrom, start, ref, alt) -> [{pvid, clin_sig, clin_sig_raw, confidence, ...}]`.

    Allele-exact, never by rsID, and the snapshot carries no rsID column to be tempted by: PubMind
    keys on extracted text and back-maps to coordinates, so a position-level tag would pool verdicts
    about different alleles at one locus into a single answer.

    A list rather than one record, and every element of it is kept — see the module docstring. Ordered
    by `(chrom, start, ref, alt, pvid)`, which is the snapshot's own emitted order, so a caller
    folding the list reads the same records in the same sequence on every run (Principle 7).
    """
    if not alleles:
        return {}
    con = _connect(reference)
    try:
        wanted = list(dict.fromkeys(alleles))
        # `probe_table` is the shared batch-probe helper: a temp table beats an `IN` list that grows
        # with the module, and it is the same plan the ClinVar reader is measured on (`@hash-the-probe`).
        probe_table(
            con,
            "_wanted_alleles",
            [("chrom", "VARCHAR"), ("start", "BIGINT"), ("ref", "VARCHAR"), ("alt", "VARCHAR")],
            wanted,
        )
        rows = con.execute(
            """
            SELECT p.chrom, p.start, p.ref, p.alt, p.pvid, p.clin_sig, p.clin_sig_raw,
                   p.pathogenicity_score, p.confidence, p.derivation
            FROM pubmind p
            JOIN _wanted_alleles w
              ON p.chrom = w.chrom AND p.start = w.start AND p.ref = w.ref AND p.alt = w.alt
            ORDER BY p.chrom, p.start, p.ref, p.alt, p.pvid
            """
        ).fetchall()
    finally:
        con.close()
    result: dict[tuple[str, int, str, str], list[dict]] = defaultdict(list)
    for chrom, start, ref, alt, pvid, clin_sig, raw, score, confidence, derivation in rows:
        result[(str(chrom), int(start), str(ref), str(alt))].append(
            {
                "pvid": pvid,
                "clin_sig": clin_sig,
                "clin_sig_raw": raw,
                "pathogenicity_score": score,
                "confidence": int(confidence) if confidence is not None else None,
                "derivation": derivation,
            }
        )
    return dict(result)
