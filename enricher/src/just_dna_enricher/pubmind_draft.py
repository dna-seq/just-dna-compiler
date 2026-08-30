"""Draft `variants.csv` rows from the PubMind snapshot (RM134 § C) — `draft-panel --source pubmind`.

**A flag on the existing command, never a second command.** `draft-pubmind` would write the same
tables from the same gene argument, so it would carry its own copy of the genotype worklist, the
placeholder guard, the dedup-against-the-file pass and the refusal summary — the four parts that are
hard to get right and the four that have each been fixed here at least once. `draft-clinpgx` is a
separate command because it writes *different* tables; this does not. So the machinery below is
**imported from `clinvar_draft` rather than copied**, including the worklist seam whose once-only
scoping was the bug RM71 removed: a second copy of that rule is the copy that goes stale.

**PubMind publishes no gene column, and this module does not invent one.** The snapshot is
`(chrom, start, ref, alt)` and nothing else locational — a verdict about a position, keyed to the text
an LLM extracted rather than to a locus. Turning `--gene BRCA1` into a set of positions therefore
needs a gene→locus map, and this repo deliberately holds none: the compiler's own gene/locus check is
chromosome-granular precisely because gene boundaries are not ours to state. So the map is
**ClinVar's own per-record gene attribution, matched at the exact position** — every position ClinVar
records for the gene, with no clinical or review filter, since the map is a locus universe and not a
selection. A min/max span over those positions would be a boundary nobody defined, and would write a
`gene` cell that is a false claim wherever two genes overlap.

The consequence is a scope, stated rather than counted: **a PubMind verdict at a position ClinVar has
no record for cannot be reached by gene at all**, and that class is not countable — attributing it to
a gene is the very thing there is no map for. It includes the codon-decomposed offsets, which are
PubMind's own back-mapping of a protein change and frequently land where nobody has filed a record.

**Identity is the whole coordinate or nothing** (`@identity-whole-or-none`). Most PubMind rows carry
no rsID — the snapshot has no rsID column at all — so `chrom`/`start`/`ref`/`alts` go in together,
and the row matches on the same five columns a ClinVar-drafted row does, so the two providers dedupe
against each other at one event rather than writing it twice.

**What is withheld is named** (`@unreachable-not-absent`). Four classes never become a row — a
contested key, a length-changing row, a call outside `--clin-sig`, and a confidence below the floor
or not stated at all — and each is counted under exactly one reason and reported with that reason.
`PUBMIND_WITHHELD_REASONS` is walked rather than restated, so `candidates == drafted + Σ withheld` is
an equality over the set (`@registry-completeness`).

**A contested key is withheld, not resolved.** Where the PVIDs at one coordinate disagree about the
call, choosing one means an ordering nobody defined — `mode()` over an unsorted group, which the
deterministic-ordering rule bans outright. The multiplicity is the finding: the coordinate, its PVIDs
and its competing calls are all reported, and no row is written. Contestation is decided over **every**
PVID at the key *before* `--clin-sig` and `--min-confidence` are applied, because a filter that
removes the dissenting record has picked the winner just as surely as `mode()` would.

**Terms are unknown, and unknown warns rather than gates** (`@no-named-licence`). `check_declared_use`
is a gate on *fetching*, and its unknown branch skips — correctly, for a pass that would go and get
data whose terms nobody can state. Nothing is fetched here: there is no `ensure_pubmind_snapshot` by
design, the operator built the snapshot themselves with `pubmind build`, and refusing to read it would
make that command's output a file nothing may consume. So the reason is *reported* in the source's own
words and the draft proceeds, exactly as the GWAS Catalog pass does with the same null terms. What the
unknown answer gates is **publishing** a module carrying those bytes, which is the redistribution axis
nothing in this repo designs yet.

**What it will not fill**, each a rule rather than an omission:

* `clinvar`, `pathogenic`, `benign` — all three are ClinVar flags by their own field descriptions, and
  a position appearing in ClinVar's gene map says nothing about whether *this allele* is in ClinVar
  (`@field-description-is-a-claim`).
* `phenotype` — the ANNOVAR-redistributed channel carries no condition, and PubMind's per-record
  detail is withheld from it.
* a study row — the same channel carries no PMID, so a PubMind draft grounds nothing and says so.
* `weight`, `direction`, `trait_efo_id`, `curator`, `method` — as for ClinVar, and for the same
  reasons.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import normalize_chrom

from just_dna_enricher.clinvar import select_by_gene
from just_dna_enricher.clinvar_draft import (
    _MATCH_ON,
    _STATE_BY_CLIN_SIG,
    DEFAULT_CLIN_SIG,
    _genotype_worklist,
    _open_stubs,
    _refusal_summary,
    _resolve_snapshot,
    _signature,
    _state_stub_warnings,
    sole_expressible_genotype,
)
from just_dna_enricher.enrich import source_build_mismatch
from just_dna_enricher.licensing import (
    PUBMIND_TERMS,
    merge_sources_file,
    withdraw_stale_dataset,
)
from just_dna_enricher.locations import RELEASE_FILENAME, resolve_pubmind_reference
from just_dna_enricher.provenance import stamp_draft_digest
from just_dna_enricher.pubmind_build import PUBMIND_GENOME_BUILD
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)

#: How this provider names itself to an author, and the key it is recorded under. The key is
#: `PUBMIND_TERMS.source`, which reaches `sources.csv` — an authored, published file — so it is read
#: from the terms rather than spelled again here.
PUBMIND_SOURCE = PUBMIND_TERMS.source
PUBMIND_LABEL = "PubMind"


class PubMindDraftError(RuntimeError):
    """A PubMind panel draft could not be completed."""


#: The evidence-depth floor, and it is a floor rather than 0 for the same reason
#: `min_review_stars` is 2: PubMind's `confidence` counts how much of the literature spoke, and a
#: confidence-0 row is one paragraph of one paper. 0–3, so 1 is "more than a single mention".
DEFAULT_MIN_CONFIDENCE = 1

#: Why a candidate key produced no row. **Walked, never restated** — the result's own accounting
#: asserts `candidates == drafted + sum(withheld.values())`, which only holds because every reason
#: is a member here and every key is counted under exactly one.
#:
#: The order is the precedence: a key that is both an indel and below the floor is counted as an
#: indel, because the structural reasons are properties of the source's own row and the two dials are
#: the author's. Reading them the other way round would make a count move when a flag moves.
PUBMIND_WITHHELD_REASONS: tuple[str, ...] = (
    # The PVIDs at one coordinate do not agree on the call. Withheld rather than resolved.
    "contested_key",
    # A length-changing row: PubMind's indels are not established to be left-normalized upstream, so
    # a join against them is unverified.
    "indel_derivation",
    # PubMind's call is outside `--clin-sig`. The author's dial, reported so a verdict this run
    # deliberately did not take is still visible.
    "clin_sig_not_selected",
    # No record at the key states a confidence. Its own class: "the source did not say" is not "the
    # source said something below the floor", and `None` is never `False`.
    "confidence_not_stated",
    # Every stated confidence at the key is below `--min-confidence`.
    "below_min_confidence",
)


@dataclass
class PubMindDraftResult:
    """What a PubMind panel draft did — and, in equal detail, what it did not write."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Distinct `(chrom, start, ref, alt)` keys PubMind states anything about at the mapped positions.
    candidates: int = 0
    #: Keys offered to the file as a row. Not the same as `added`: an already-present key is offered.
    drafted: int = 0
    #: Keyed by `PUBMIND_WITHHELD_REASONS`, every member present so a zero is a measured zero.
    withheld: dict[str, int] = field(default_factory=dict)
    #: Positions ClinVar attributes to the requested genes, and how many of them PubMind speaks about.
    mapped_positions: int = 0
    spoken_positions: int = 0

    @property
    def added(self) -> int:
        return sum(len(r.added) for r in self.reports)

    def added_for(self, csv_name: str) -> int:
        return sum(len(r.added) for r in self.reports if r.csv_name == csv_name)

    @property
    def already_present(self) -> int:
        return sum(len(r.already_present) for r in self.reports)

    @property
    def invalid(self) -> int:
        return sum(len(r.invalid) for r in self.reports)

    def accounts_for_every_candidate(self) -> bool:
        """`candidates == drafted + Σ withheld` — the equality `PUBMIND_WITHHELD_REASONS` exists for.

        Walked rather than listed, so a sixth reason cannot arrive without joining the sum.
        """
        return self.candidates == self.drafted + sum(self.withheld.values())


# ── Reading the snapshot ────────────────────────────────────────────────────────────────────────
#
# The reader lives beside its one caller rather than in a `pubmind.py` twin of `clinvar.py`, because
# this pass and the hint are the only things that read the snapshot today and a module holding one
# query is a module. Move it out when a third reader lands.


def _connect(reference: Path) -> duckdb.DuckDBPyConnection:
    """An in-memory connection exposing a `pubmind` view over the snapshot's parquet files."""
    reference = Path(reference)
    data = reference / "data"
    parquet_dir = data if data.is_dir() and any(data.glob("*.parquet")) else reference
    if not (parquet_dir.is_dir() and any(parquet_dir.glob("*.parquet"))):
        raise PubMindDraftError(
            f"no usable PubMind parquet files at {reference}. Build one with "
            f"`just-dna-enricher pubmind build --download`."
        )
    # DuckDB cannot bind a parameter inside `read_parquet()`; the path comes from our own cache
    # resolution rather than from user input, and is single-quote-escaped defensively — the same
    # shape `clinvar._connect` uses.
    pattern = f"{parquet_dir}/*.parquet".replace("'", "''")
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE VIEW pubmind AS SELECT * FROM read_parquet('{pattern}')")
    return con


#: Every column a reader of this snapshot takes, in the order `_schema()` writes them.
_SELECT = "chrom, start, ref, alt, pvid, clin_sig, clin_sig_raw, pathogenicity_score, confidence, derivation"


def select_by_positions(reference: Path, positions: Sequence[tuple[str, int]]) -> list[dict]:
    """Every PubMind record at one of these exact positions — **every** PVID, never a winner.

    A range query per contig, narrowed to the exact positions afterwards: the alternative is an `IN`
    list of tens of thousands of positions, and the alternative to *that* is a span, which is the one
    thing this module refuses to infer. Ordered deterministically so a re-draft offers the same rows
    in the same order (Principle 7).
    """
    wanted = {(normalize_chrom(str(chrom)), int(start)) for chrom, start in positions}
    if not wanted:
        return []
    by_chrom: dict[str, list[int]] = {}
    for chrom, start in sorted(wanted):
        by_chrom.setdefault(chrom, []).append(start)
    con = _connect(reference)
    rows: list[dict] = []
    try:
        for chrom in sorted(by_chrom):
            starts = by_chrom[chrom]
            cursor = con.execute(
                f"SELECT {_SELECT} FROM pubmind WHERE chrom = ? AND start BETWEEN ? AND ? "
                f"ORDER BY start, ref, alt, pvid",
                [chrom, min(starts), max(starts)],
            )
            columns = [d[0] for d in cursor.description]
            rows.extend(
                record
                for record in (dict(zip(columns, row, strict=True)) for row in cursor.fetchall())
                if (normalize_chrom(str(record["chrom"])), int(record["start"])) in wanted
            )
    finally:
        con.close()
    return rows


def pubmind_dataset_label(reference: Path | None) -> str | None:
    """Which PubMind bytes a snapshot was built from, or `None` when it cannot say.

    The builder derives the label from the source file's sha256 because PubMind publishes no version
    string of its own; this reads that value back rather than re-deriving it, so the licence row and
    `release.json` cannot disagree about which release a module's rows came from.
    """
    if reference is None:
        return None
    path = Path(reference) / RELEASE_FILENAME
    if not path.is_file():
        return None
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    label = str(release.get("dataset") or "").strip()
    return label or None


# ── Turning a gene into positions, and positions into rows ──────────────────────────────────────


def gene_positions(reference: Path, genes: Sequence[str]) -> dict[tuple[str, int], set[str]]:
    """`(chrom, start)` → the requested gene(s) ClinVar attributes a record at that position to.

    **No clinical or review filter**, deliberately: this is a locus universe rather than a selection,
    and the dials an author sets are about which *PubMind* verdicts to take. Filtering the map instead
    would silently narrow which positions PubMind is even asked about, and the narrower map is
    invisible in the output.

    A position ClinVar attributes to two of the requested genes keeps both, so nothing here picks a
    gene either.
    """
    mapping: dict[tuple[str, int], set[str]] = {}
    for record in select_by_gene(reference, list(genes), clin_sig=None, min_review_stars=0):
        chrom, start = record.get("chrom"), record.get("start")
        gene = (record.get("gene") or "").strip()
        if chrom is None or start is None or not gene:
            continue
        # Both sides through the same normalizer: the snapshots agree today (each builder strips a
        # `chr` prefix and folds M to MT), and a map keyed on the raw cell would silently find
        # nothing the day one of them stops agreeing.
        mapping.setdefault((normalize_chrom(str(chrom)), int(start)), set()).add(gene)
    return mapping


@dataclass(frozen=True)
class _Key:
    """One coordinate PubMind speaks about, with every record it speaks with."""

    chrom: str
    start: int
    ref: str
    alt: str
    records: tuple[dict, ...]

    @property
    def label(self) -> str:
        return f"{self.chrom}:{self.start} {self.ref}>{self.alt}"

    @property
    def calls(self) -> list[str]:
        """The distinct normalized calls at this key, sorted — over **every** record, pre-filter."""
        return sorted({str(r.get("clin_sig") or "") for r in self.records})

    @property
    def pvids(self) -> list[str]:
        return sorted({str(r.get("pvid") or "") for r in self.records if r.get("pvid")})

    @property
    def derivations(self) -> list[str]:
        return sorted({str(r.get("derivation") or "") for r in self.records})

    @property
    def confidences(self) -> list[int]:
        """Every stated confidence at the key. Empty means the source stated none — not zero."""
        return sorted(int(r["confidence"]) for r in self.records if r.get("confidence") is not None)


def _group_by_key(records: Sequence[dict]) -> list[_Key]:
    """Records → one `_Key` per `(chrom, start, ref, alt)`, in the order the reader emitted them."""
    grouped: dict[tuple[str, int, str, str], list[dict]] = {}
    for record in records:
        key = (
            str(record["chrom"]), int(record["start"]),
            str(record["ref"]), str(record["alt"]),
        )
        grouped.setdefault(key, []).append(record)
    return [
        _Key(chrom=chrom, start=start, ref=ref, alt=alt, records=tuple(rows))
        for (chrom, start, ref, alt), rows in grouped.items()
    ]


def _withhold_reason(key: _Key, *, clin_sig: frozenset[str], min_confidence: int) -> str | None:
    """Why this key gets no row, or `None` to draft it. One reason per key, in registry order.

    The contested test runs **first and over every record**, before either dial: a key whose
    dissenting PVID a filter removed would read as uncontested, and the filter would have chosen the
    winner that `mode()` was banned for choosing.
    """
    if len(key.calls) > 1:
        return "contested_key"
    if "indel" in key.derivations:
        return "indel_derivation"
    if key.calls[0] not in clin_sig:
        return "clin_sig_not_selected"
    if not key.confidences:
        return "confidence_not_stated"
    # The best evidence the agreeing records carry, not each of them: they all state the same call, so
    # a confidence-0 record beside a confidence-3 one does not weaken the confidence-3 one. This is an
    # aggregation over agreement, never a choice between claims — those are withheld above.
    if max(key.confidences) < min_confidence:
        return "below_min_confidence"
    return None


def _row_cells(key: _Key, genes: set[str]) -> dict:
    """One PubMind key → the authored cells this provider is willing to state.

    `gene` is ClinVar's attribution of the position and is written as such; where ClinVar attributes
    the position to two of the requested genes the cell names both, because picking one would be this
    module inventing the gene model it went to ClinVar to avoid inventing.
    """
    call = key.calls[0]
    confidences = key.confidences
    confidence = f"confidence {max(confidences)}" if confidences else "confidence not stated"
    cells: dict = {
        "chrom": key.chrom,
        "start": key.start,
        "ref": key.ref,
        "alts": key.alt,
        "gene": ", ".join(sorted(genes)) or None,
        "clin_sig": call or None,
        # A transcription of what the snapshot holds, not a reading of it — the shape `pgx_draft` set
        # and `clinvar_draft` follows. The derivation rides here because there is no authored column
        # for it and nobody has priced one.
        "conclusion": (
            f"{PUBMIND_LABEL}: {call or 'no call'} ({confidence}; "
            f"{len(key.records)} record(s): {examples(key.pvids)}; "
            f"derivation {', '.join(key.derivations)}) — an LLM's reading of the published "
            f"literature, not a curated assertion"
        ),
    }
    genotype = sole_expressible_genotype(
        {"chrom": key.chrom, "start": key.start, "alt": key.alt}
    )
    if genotype is not None:
        cells["genotype"] = genotype
    state = _STATE_BY_CLIN_SIG.get(call)
    if state is not None:
        cells["state"] = state
    return cells


def _withheld_warnings(
    withheld: dict[str, int],
    contested: Sequence[_Key],
    min_confidence: int,
    clin_sig: frozenset[str],
) -> list[str]:
    """One line per withheld class that actually withheld something, grouped by **reason**.

    A class that withheld nothing says nothing: a check that cannot fail must not report a zero, and
    "0 contested keys" on a module with no contested keys is exactly that. The counts are still all
    carried on the result, where the accounting equality reads them.
    """
    lines: list[str] = []
    if withheld["contested_key"]:
        detail = examples([f"{k.label} ({'/'.join(k.calls)})" for k in contested])
        lines.append(
            f"{withheld['contested_key']} coordinate(s) carry PubMind records that disagree about "
            f"the call, so no row was written for them: {detail}. The disagreement is the finding — "
            f"picking one would need an ordering nobody has defined, and PubMind's records are keyed "
            f"on the text a model extracted rather than on the coordinate, so several can describe "
            f"one position. Decide each by hand, or take the call from a source that states one."
        )
    if withheld["indel_derivation"]:
        lines.append(
            f"{withheld['indel_derivation']} length-changing coordinate(s) were not drafted: PubMind's "
            f"indel rows are not established to be left-normalized, so a join against them may match "
            f"the wrong representation of the same event. They are in the snapshot marked "
            f"`derivation=indel` if you want to work through them by hand."
        )
    if withheld["clin_sig_not_selected"]:
        lines.append(
            f"{withheld['clin_sig_not_selected']} coordinate(s) carry a PubMind call outside "
            f"--clin-sig ({', '.join(sorted(clin_sig))}), so no row was written for them. Reported "
            f"rather than dropped silently: PubMind has an opinion there and this run did not take it."
        )
    if withheld["confidence_not_stated"]:
        lines.append(
            f"{withheld['confidence_not_stated']} coordinate(s) state no confidence at all and were "
            f"not drafted. That is a different thing from a confidence below --min-confidence: the "
            f"source said nothing, so there is nothing to compare against the floor, and treating an "
            f"unstated confidence as 0 would invent a reading."
        )
    if withheld["below_min_confidence"]:
        lines.append(
            f"{withheld['below_min_confidence']} coordinate(s) were not drafted because their best "
            f"stated confidence is below --min-confidence {min_confidence}. PubMind's confidence "
            f"counts how much of the literature spoke, 0-3; lower the floor to take them."
        )
    return lines


def draft_gene_panel_from_pubmind(
    spec_dir: Path,
    genes: Sequence[str],
    *,
    snapshot: Path | None = None,
    pubmind_snapshot: Path | None = None,
    clin_sig: frozenset[str] = DEFAULT_CLIN_SIG,
    min_confidence: int = DEFAULT_MIN_CONFIDENCE,
    declared_use: str = "unstated",
    offline: bool = False,
    download: bool = True,
    dry_run: bool = False,
) -> PubMindDraftResult:
    """Draft `variants.csv` rows for one or more genes from PubMind, leaving `genotype` to the human.

    Two snapshots, and each is doing a different job: `snapshot` is the **ClinVar** one, read for its
    per-record gene attribution and nothing else, and `pubmind_snapshot` is the operator-built PubMind
    one the verdicts come from. Neither is optional, and the messages say which is missing — an
    author who has one and not the other should not have to guess.

    Re-runnable and additive, exactly as the ClinVar path is: a key already in the file — stub or
    filled — is reported rather than re-added, and the open-stub worklist is read off the file rather
    than off this run, so asking twice answers twice.
    """
    build_warning = source_build_mismatch(spec_dir, "the PubMind snapshot", PUBMIND_GENOME_BUILD)
    warnings: list[str] = []

    if pubmind_snapshot is not None:
        reference = Path(pubmind_snapshot)
    else:
        resolved = resolve_pubmind_reference()
        if resolved is None:
            raise PubMindDraftError(
                "no PubMind snapshot found. It is operator-built and never published — the terms of "
                "the ANNOVAR-redistributed table could not be established, so nothing here passes it "
                "on. Build one with `just-dna-enricher pubmind build --download` and point "
                "$JUST_DNA_PUBMIND_CACHE at it, or pass --pubmind-cache PATH."
            )
        reference = Path(resolved)

    clinvar_reference, provisioning = _resolve_snapshot(snapshot, offline=offline, download=download)
    warnings.extend(provisioning)
    if build_warning:
        warnings.append(build_warning)
    # Unknown terms warn and never gate (`@no-named-licence`) — see the module docstring for why
    # `check_declared_use`, which is a gate on *fetching*, is not the right question for a snapshot
    # the operator built themselves.
    warnings.append(
        f"{PUBMIND_SOURCE}: the terms of the ANNOVAR-redistributed table could not be established, "
        f"so every licence cell on this module's {PUBMIND_SOURCE} row is null. Unknown is neither "
        f"permission nor refusal: the compile does not refuse a null, and what the answer would "
        f"govern is publishing a module carrying these values."
    )

    positions = gene_positions(clinvar_reference, genes)
    if not positions:
        return PubMindDraftResult(
            warnings=warnings
            + [
                f"ClinVar records no position for {', '.join(genes)}, so there is no gene map to ask "
                f"PubMind with. PubMind's table names no gene, so a coordinate can only be attributed "
                f"to one through a source that does — check the symbol, or draft by hand."
            ],
            withheld=dict.fromkeys(PUBMIND_WITHHELD_REASONS, 0),
        )

    keys = _group_by_key(select_by_positions(reference, list(positions)))
    withheld = dict.fromkeys(PUBMIND_WITHHELD_REASONS, 0)
    contested: list[_Key] = []
    partials: list[PartialRow] = []
    record_by_signature: dict[tuple[str, ...], dict] = {}
    stubbed_by_signature: dict[tuple[str, ...], tuple[str, ...]] = {}
    for key in keys:
        reason = _withhold_reason(key, clin_sig=clin_sig, min_confidence=min_confidence)
        if reason is not None:
            withheld[reason] += 1
            if reason == "contested_key":
                contested.append(key)
            continue
        cells = _row_cells(key, positions[(key.chrom, key.start)])
        # `state` is stubbed for the same reason it is on the ClinVar path: PubMind states a call, and
        # `VALID_STATES` has no member meaning "undecided", so a call the fold does not cover is the
        # human's. Derived from the cells rather than listed, so a column this provider filled — the
        # haploid genotype — is not then stubbed over the top of itself.
        stubbed = tuple(column for column in ("genotype", "state") if column not in cells)
        signature = _signature(cells)
        record_by_signature[signature] = {
            "chrom": key.chrom, "start": key.start, "ref": key.ref, "alt": key.alt,
            "clin_sig": key.calls[0],
        }
        stubbed_by_signature[signature] = stubbed
        partials.append(
            PartialRow(
                model=VariantRow,
                cells=cells,
                stubbed=stubbed,
                # The same five columns the ClinVar provider matches on, so a coordinate PubMind and
                # ClinVar both speak about is one row in the file rather than two.
                match_on=_MATCH_ON,
            )
        )

    result = PubMindDraftResult(
        warnings=warnings,
        candidates=len(keys),
        drafted=len(partials),
        withheld=withheld,
        mapped_positions=len(positions),
        spoken_positions=len({(k.chrom, k.start) for k in keys}),
    )
    result.warnings.extend(_withheld_warnings(withheld, contested, min_confidence, clin_sig))
    # Absence is not disagreement and is not silence: a position PubMind says nothing about means no
    # paper in the corpus survived their triage, never that the literature is quiet.
    if result.spoken_positions < result.mapped_positions:
        result.warnings.append(
            f"PubMind states nothing at {result.mapped_positions - result.spoken_positions} of the "
            f"{result.mapped_positions} position(s) ClinVar attributes to {', '.join(genes)}. That is "
            f"an absence in their corpus, not a benign call and not a disagreement — and it is only "
            f"the positions ClinVar records: a PubMind verdict somewhere ClinVar has no record for "
            f"cannot be reached by gene at all, because nothing here maps a bare coordinate to one."
        )
    if not partials:
        result.warnings.append("nothing matched; no rows drafted")
        return result

    report = append_partial_rows(
        spec_dir, "variants.csv", partials, group_by=("gene",), dry_run=dry_run
    )
    result.reports.append(report)
    result.warnings.extend(_refusal_summary(report.invalid))
    # PubMind's own channel carries no citation, so a drafted panel is ungrounded by construction and
    # has to say so: `studies.csv` is mandatory, and a module that cannot compile without telling the
    # author why is the defect the ClinVar path already fixed once.
    result.warnings.append(
        f"no studies.csv rows were drafted: the ANNOVAR-redistributed {PUBMIND_LABEL} table carries "
        f"no PMID, and their API withholds per-record detail. Grounding evidence is mandatory, so add "
        f"it by hand, or draft the same genes from ClinVar, which publishes its literature links."
    )

    # ── What is still open, scoped to the FILE rather than to this run ──────────────────────────
    #
    # `_open_stubs` is imported rather than reimplemented: scoping this to `report.added` is the
    # once-only defect RM71 removed on the ClinVar path, where a second run added nothing and
    # therefore said nothing, and a second copy of the rule is the copy that goes stale.
    genotype_stubs = _open_stubs(report, "genotype", stubbed_by_signature)
    if genotype_stubs:
        result.warnings.append(
            f"{len(genotype_stubs)} row(s) carry an unreplaced genotype placeholder and will not "
            f"compile until you decide the zygosity each finding is about."
        )
        result.warnings.extend(
            _genotype_worklist(
                [
                    record_by_signature[signature]
                    for signature, _ in genotype_stubs
                    if signature in record_by_signature
                ],
                source=PUBMIND_LABEL,
            )
        )
        withheld_alleles = [
            signature for signature, _ in genotype_stubs if signature not in record_by_signature
        ]
        if withheld_alleles:
            result.warnings.append(
                f"{len(withheld_alleles)} row(s) of that list carry alleles this run cannot state, "
                f"because nothing it selected covers them "
                f"({examples([':'.join(p for p in s if p) for s in withheld_alleles])}). The alleles "
                f"are withheld rather than guessed: draft the gene each row records, or "
                f"`hint variant`, will state them."
            )
    result.warnings.extend(
        _state_stub_warnings(
            _open_stubs(report, "state", stubbed_by_signature),
            record_by_signature,
            source=PUBMIND_LABEL,
        )
    )

    dataset = pubmind_dataset_label(reference)
    if dataset is None:
        result.warnings.append(
            f"this snapshot does not say which {PUBMIND_LABEL} bytes it carries (no readable "
            f"{RELEASE_FILENAME}), so the licence row records no dataset: nothing downstream can tell "
            f"these rows were copied out of it. Rebuild it with `just-dna-enricher pubmind build`, "
            f"which writes the release file this reads."
        )
    if not dry_run:
        merge_sources_file(
            [PUBMIND_TERMS.row("annotation", declared_use=declared_use, dataset=dataset)],
            spec_dir,
            error=PubMindDraftError,
        )
        # Unconditional, and never-clobber is why: `merge_sources_file` keeps a curator's terms, which
        # would silently drop a second draft's digest — and the digest is what lets a cross-check
        # establish that a value is still this provider's copy rather than assume it (`@draft-digest`).
        stamp_draft_digest(spec_dir, PUBMIND_SOURCE, "annotation", error=PubMindDraftError)
        if report.added:
            superseded = withdraw_stale_dataset(
                spec_dir, PUBMIND_SOURCE, "annotation", dataset, error=PubMindDraftError
            )
            if superseded is not None:
                result.warnings.append(
                    f"this module already recorded rows drafted from {superseded}, and these came "
                    f"from {dataset or 'a snapshot that does not state its release'} — so the licence "
                    f"row's dataset has been cleared rather than re-labelled: it cannot name two "
                    f"releases, and naming one would be a claim about rows that did not come from it."
                )
    return result
