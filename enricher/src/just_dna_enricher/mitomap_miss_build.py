"""The MITOMAP-minus-ClinVar increment, as a derived cache lane (RM171).

**The question this answers is not "does MITOMAP contribute sixteen new expert-panel calls".** That
number is a fact about one join against one ClinVar vintage, and a hardcoded list of sixteen alleles
is a snapshot of a diff — stale the next time either parent is rebuilt. The question is *what does
MITOMAP publish that the ClinVar cache does not*, answered every time both parents are current, so
what a draft appends is the increment rather than an inventory somebody wrote down once.

**Three buckets, and only one of them drafts.**

* **photocopy** — the exact allele is in ClinVar. Nothing is drafted. On the measured vintage every
  matched bracketed row carried `reviewed_by_expert_panel`, so these are the same ClinGen VCEP call
  arriving by two routes; drafting them would attribute an adopted source's judgement to the wrong
  publisher, and feeding them to a ClinVar concordance check would be a tautology.
* **rated miss** — absent from ClinVar, and the bracket is one of the five documented VCEP classes.
  This is what `draft-panel --source mitomap-miss` writes.
* **unrated miss** — absent, and MITOMAP published no class this tier may map: no bracket at all, or
  `[VUS*]`, or a confirmation token on its own. Counted, never given a class.

A fourth bucket sits beside those three because the question cannot be *asked* of it. **unmintable**
is a row whose published alleles do not spell a VCF `(ref, alt)` — MITOMAP writes a deletion
right-anchored (`refna="TA"`, `regna=":"`), and turning that into a VCF allele needs the rCRS base at
`position - 1`, which Principle 2 forbids these tiers from fetching. Those rows are not misses and
they are not photocopies; they are rows the join has no key for, and folding them into either would be
a claim about a comparison that could not run.

**The exact join, and no position-level fallback.** `(start, ref, alt)` on chrMT, upper-cased on both
sides. A position-level hit is a *different allele at the same locus*, and collapsing onto it would
either hide a real increment or invent one where the two sources left-align an indel differently. The
same left-alignment caveat is why the snapshot marks every indel key: an exact join over
un-normalized indels cannot distinguish "ClinVar does not carry this" from "ClinVar carries it,
spelled at another anchor", so the count is published rather than quietly folded into the miss.

**Its `release.json` pins both parents**, which is what makes a ClinVar rebuild without a child
rebuild a *detectable* stale child rather than a silent one. `stale_parents` re-reads the parents on
disk and names the one that moved (`@currency-asks-the-source-not-the-cache`, applied to a derived
lane: the "source" is the two parents).
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.clinvar_build import chrom_parquet_name
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.mitomap import MitomapError
from just_dna_enricher.mitomap_build import (
    CITATIONS_PARQUET as MITOMAP_CITATIONS_PARQUET,
)
from just_dna_enricher.mitomap_build import (
    VARIANT_COLUMNS,
    VARIANT_PARQUET,
)

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

#: The one parquet this lane writes. A single file rather than one per source table: the table each
#: row came from is a column, so a reader asking "what does MITOMAP add" never has to know how many
#: tables the parent had.
MISS_PARQUET = "mitomap_miss.parquet"

#: The citations for the rows this lane says are *new*, carried into the child so a drafter needs one
#: snapshot rather than two. Only the non-photocopy rows: nothing drafts a photocopy, so shipping its
#: literature here would be paying for evidence about rows this lane exists to refuse.
CITATIONS_PARQUET = "mitomap_miss-citations.parquet"

#: The contig both sides of this join are on. Stated once, here, rather than carried as a constant
#: column in the key — a column that can only ever hold one value is not part of an identity.
CONTIG = "MT"

#: The four outcomes a MITOMAP row can have against the ClinVar parent. A partition: every row lands
#: in exactly one, and `accounts_for_every_row` asserts it rather than trusting the branches.
BUCKETS: tuple[str, ...] = ("photocopy", "rated_miss", "unrated_miss", "unmintable")

#: The keys a parent's `release.json` is pinned on. Read generically rather than per parent, so a
#: parent that starts publishing a new identifying key is pinned on it without this module learning
#: the parent's schema — and a key that *disappears* shows up as a moved pin rather than as silence.
PIN_KEYS: tuple[str, ...] = (
    "dataset", "clinvar_file_date", "source_sha256", "record_count", "rows",
)


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


@dataclass
class MissBuildResult:
    """The increment, its parents, and every number the join computed."""

    out_dir: Path
    parquet_file: Path
    #: `bucket -> rows`, over both source tables.
    buckets: dict[str, int] = field(default_factory=dict)
    #: `table -> {bucket -> rows}`. A finding about MITOMAP is always a finding about a named table.
    buckets_by_table: dict[str, dict[str, int]] = field(default_factory=dict)
    #: `clin_sig -> rows` over the rated misses — the classes this increment would actually draft.
    rated_miss_by_class: dict[str, int] = field(default_factory=dict)
    #: Rated misses whose key is an indel. Published because an exact join over un-normalized indels
    #: cannot tell an absence from a difference of anchor.
    rated_miss_indels: int = 0
    #: `bracket -> rows` for a *missing* row whose only rating is a bracket this tier will not map.
    withheld_in_miss: dict[str, int] = field(default_factory=dict)
    #: `reason -> rows` for the rows the join has no key for.
    unmintable: dict[str, int] = field(default_factory=dict)
    #: How many distinct chrMT alleles the ClinVar parent published — the denominator of "absent".
    clinvar_keys: int = 0
    #: Citation links carried into the child, for the non-photocopy rows only.
    citation_links: int = 0
    parents: dict[str, dict] = field(default_factory=dict)

    @property
    def rated_misses(self) -> int:
        return self.buckets.get("rated_miss", 0)

    def accounts_for_every_row(self, total: int) -> bool:
        """Every MITOMAP row is in exactly one bucket — the partition, asserted rather than assumed."""
        return sum(self.buckets.values()) == total


def parent_pin(directory: Path | None) -> dict:
    """The identifying half of a parent's `release.json`, or `{}` when there is none to read.

    `{}` is a real answer and is stored as one: a parent built by something that wrote no
    `release.json` cannot be pinned, and recording an empty pin says so, where omitting the parent
    entirely would read as "this child has one parent".
    """
    if directory is None:
        return {}
    path = Path(directory) / RELEASE_FILENAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: payload[key] for key in PIN_KEYS if key in payload}


def stale_parents(
    miss_dir: Path, *, parents: dict[str, Path] | None = None
) -> dict[str, tuple[dict, dict]]:
    """Parents whose snapshot on disk no longer matches the pin this child was built against.

    Returns `parent -> (pinned, current)` for each one that moved, empty when the child is current.
    **Absence of a parent is not staleness** and is not reported here: a parent that is gone cannot be
    compared, and reporting it as "moved" would send a reader looking for a rebuild that happened.
    The caller distinguishes the two, because "rebuild the child" and "provision the parent" are
    different instructions.

    `parents` names where each parent lives when the caller knows; otherwise the path recorded in the
    child's own `release.json` is used, which is what a later `draft` run has.
    """
    release = read_miss_release(miss_dir)
    pinned = release.get("parents") or {}
    if not isinstance(pinned, dict):
        return {}
    located = {name: Path(path) for name, path in (parents or {}).items()}
    moved: dict[str, tuple[dict, dict]] = {}
    for name, block in pinned.items():
        if not isinstance(block, dict):
            continue
        recorded = {key: value for key, value in block.items() if key != "path"}
        directory = located.get(name) or (Path(block["path"]) if block.get("path") else None)
        if directory is None or not directory.is_dir():
            continue
        current = parent_pin(directory)
        if current and current != recorded:
            moved[name] = (recorded, current)
    return moved


def read_miss_release(directory: Path) -> dict:
    """A miss snapshot's `release.json` as a dict, or `{}` when it is absent or unreadable."""
    path = Path(directory) / RELEASE_FILENAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def miss_dataset_label(release: dict) -> str | None:
    """The increment's own release label — **both parents, or nothing**.

    `mitomap_2026-08-24+clinvar_2026-06-27`. A derived artifact's identity is the pair it was derived
    from: the same MITOMAP dump against a newer ClinVar is a different increment, and a label naming
    only the source would say two different artifacts were the same one. `None` where either parent
    is unlabelled, because half an identity is not a shorter identity — it is an unknown, and the
    licence row withholds it rather than writing a label that cannot be compared
    (`@currency-asks-the-source-not-the-cache`).
    """
    parents = release.get("parents")
    if not isinstance(parents, dict):
        return None
    mitomap = (parents.get("mitomap") or {}).get("dataset")
    clinvar = (parents.get("clinvar") or {}).get("clinvar_file_date")
    if not mitomap or not clinvar:
        return None
    return f"{mitomap}+clinvar_{clinvar}"


def _clinvar_calls(clinvar_dir: Path) -> dict[tuple[int, str, str], dict]:
    """Every chrMT allele the ClinVar parent publishes, keyed, with the call it carries.

    Keyed on `(start, ref, alt)` upper-cased, which is the join. The call travels with it so a
    photocopy can name the record it is a copy of — that is what makes "the same VCEP call arriving
    by two routes" a checkable statement rather than an assertion in a docstring.

    **Refuses rather than returning an empty mapping when the parquet is not there**, and the
    difference is the whole design: an empty ClinVar makes every MITOMAP row a miss, which is the most
    confident wrong answer this lane could produce.
    """
    parquet = Path(clinvar_dir) / "data" / chrom_parquet_name(CONTIG)
    if not parquet.is_file():
        raise MitomapError(
            f"the ClinVar parent at {clinvar_dir} has no {chrom_parquet_name(CONTIG)}. Refusing: an "
            f"absent parent makes every MITOMAP row look like an increment, which is a claim about a "
            f"comparison that never ran. Build one with `just-dna-enricher clinvar build`."
        )
    frame = pl.read_parquet(
        parquet, columns=["start", "ref", "alt", "variation_id", "clin_sig", "review_status"]
    )
    out: dict[tuple[int, str, str], dict] = {}
    for row in frame.iter_rows(named=True):
        if row["start"] is None or not row["ref"] or not row["alt"]:
            continue
        out.setdefault(
            (int(row["start"]), str(row["ref"]).upper(), str(row["alt"]).upper()), row
        )
    return out


def build_miss_snapshot(
    mitomap_dir: Path, clinvar_dir: Path, out_dir: Path
) -> MissBuildResult:
    """Join the MITOMAP snapshot against the ClinVar chrMT parquet and write the increment.

    Every MITOMAP row is written, bucketed — not only the misses. Keeping the photocopies makes the
    snapshot's central claim checkable from the snapshot itself (a photocopy key is present in the
    parent, a miss key is absent), and it costs a thousand rows.

    Rows are sorted by `(table, start, ref, alt)` so a rebuild from the same two parents is
    byte-identical (Principle 7).
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the MITOMAP-miss snapshot; install the publisher/dev "
            "surface with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    mitomap_dir, clinvar_dir, out_dir = Path(mitomap_dir), Path(clinvar_dir), Path(out_dir)
    frames = []
    for name in VARIANT_PARQUET.values():
        parquet = mitomap_dir / "data" / name
        if not parquet.is_file():
            raise MitomapError(
                f"the MITOMAP parent at {mitomap_dir} has no {name}. Refusing rather than joining "
                f"the table that is there: a miss count short a source table is measured against a "
                f"denominator nobody stated. Build one with `just-dna-enricher mitomap build`."
            )
        frames.append(pl.read_parquet(parquet))
    source = pl.concat(frames)

    calls = _clinvar_calls(clinvar_dir)
    result = MissBuildResult(out_dir=out_dir, parquet_file=out_dir / "data" / MISS_PARQUET)
    result.clinvar_keys = len(calls)

    buckets: Counter[str] = Counter()
    by_table: dict[str, Counter[str]] = {}
    classes: Counter[str] = Counter()
    withheld: Counter[str] = Counter()
    unmintable: Counter[str] = Counter()
    rows: list[dict] = []
    for row in source.iter_rows(named=True):
        defect = row.get("allele_defect")
        start, ref, alt = row.get("start"), row.get("ref"), row.get("alt")
        match: dict | None = None
        if defect is not None or start is None or not ref or not alt:
            bucket = "unmintable"
            unmintable[str(defect or "non_nucleotide")] += 1
        else:
            match = calls.get((int(start), str(ref).upper(), str(alt).upper()))
            if match is not None:
                bucket = "photocopy"
            elif row.get("clin_sig"):
                bucket = "rated_miss"
                classes[str(row["clin_sig"])] += 1
                if len(str(ref)) != len(str(alt)):
                    result.rated_miss_indels += 1
            else:
                bucket = "unrated_miss"
                if row.get("withheld_bracket"):
                    withheld[str(row["withheld_bracket"])] += 1
        buckets[bucket] += 1
        by_table.setdefault(str(row["table"]), Counter())[bucket] += 1
        rows.append({
            **row,
            "chrom": CONTIG,
            "bucket": bucket,
            "key_shape": (
                None if defect is not None or not ref or not alt
                else ("substitution" if len(str(ref)) == len(str(alt)) else "indel")
            ),
            "clinvar_variation_id": (match or {}).get("variation_id"),
            "clinvar_clin_sig": (match or {}).get("clin_sig"),
            "clinvar_review_status": (match or {}).get("review_status"),
        })

    result.buckets = {name: buckets.get(name, 0) for name in BUCKETS}
    result.buckets_by_table = {
        table: {name: counts.get(name, 0) for name in BUCKETS}
        for table, counts in sorted(by_table.items())
    }
    result.rated_miss_by_class = dict(sorted(classes.items()))
    result.withheld_in_miss = dict(sorted(withheld.items()))
    result.unmintable = dict(sorted(unmintable.items()))
    result.parents = {
        "mitomap": {**parent_pin(mitomap_dir), "path": str(mitomap_dir.resolve())},
        "clinvar": {**parent_pin(clinvar_dir), "path": str(clinvar_dir.resolve())},
    }

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(rows, schema=_miss_schema()).sort(
        ["table", "start", "ref", "alt", "record_id"], nulls_last=True
    )
    frame.write_parquet(result.parquet_file)
    result.citation_links = _write_citations(mitomap_dir, data_dir, frame)
    _write_release_json(out_dir, result, source_rows=source.height)
    logger.info(
        "Built the MITOMAP-miss snapshot: %s → %s",
        ", ".join(f"{name} {count}" for name, count in result.buckets.items()), result.parquet_file,
    )
    return result


def _write_citations(mitomap_dir: Path, data_dir: Path, frame) -> int:
    """Carry the parent's citation links for the rows this lane calls new, and only those.

    A photocopy's literature is not written: nothing drafts a photocopy, so shipping evidence for one
    would be paying to carry rows this lane exists to refuse. The result is a child a drafter can read
    on its own — which matters because the alternative is a drafter that has to be handed both
    parents and would then be able to draft from a MITOMAP snapshot that is *not* the one the join
    ran against.
    """
    source = mitomap_dir / "data" / MITOMAP_CITATIONS_PARQUET
    path = data_dir / CITATIONS_PARQUET
    if not source.is_file():
        # Not a refusal: the citation table is a second artifact beside the parent's variant tables,
        # and a parent built before it existed still joins. The child records zero links, which reads
        # as "this increment carries no literature" — true, and visible.
        pl.DataFrame(schema=_citation_schema()).write_parquet(path)
        return 0
    keep = frame.filter(pl.col("bucket") != "photocopy").select(["table", "record_id"]).unique()
    citations = (
        pl.read_parquet(source)
        .join(keep, on=["table", "record_id"], how="inner")
        .select(list(_citation_schema()))
        .unique()
        .sort(["table", "record_id", "pmid"])
    )
    citations.write_parquet(path)
    return citations.height


def _citation_schema() -> dict:
    return {"table": pl.Utf8, "record_id": pl.Utf8, "reference_id": pl.Utf8, "pmid": pl.Utf8}


def _miss_schema() -> dict:
    """The parent's columns plus this lane's six, in that order, so a rebuild is byte-identical.

    Derived from `VARIANT_COLUMNS` rather than restated, so a column added to the MITOMAP snapshot
    reaches the miss snapshot without a second edit — and cannot be silently dropped by one.
    """
    schema = {name: (pl.Int64 if name == "start" else pl.Utf8) for name in VARIANT_COLUMNS}
    schema.update({
        "chrom": pl.Utf8, "bucket": pl.Utf8, "key_shape": pl.Utf8,
        "clinvar_variation_id": pl.Utf8, "clinvar_clin_sig": pl.Utf8,
        "clinvar_review_status": pl.Utf8,
    })
    return schema


def _write_release_json(out_dir: Path, result: MissBuildResult, *, source_rows: int) -> Path:
    """Both parent pins, every bucket count, and the partition check, beside the data.

    The counts are here for the reason every derived number in this tier is: one computed and dropped
    is one every reader recomputes, differently. They are re-derived on every build and are never read
    back as a constant — which is the difference between publishing an increment and hardcoding a
    diff.
    """
    release = {
        "parents": result.parents,
        "contig": CONTIG,
        "clinvar_keys": result.clinvar_keys,
        "source_rows": source_rows,
        "buckets": result.buckets,
        "buckets_by_table": result.buckets_by_table,
        "rated_miss_by_class": result.rated_miss_by_class,
        "rated_miss_indels": result.rated_miss_indels,
        "withheld_in_miss": result.withheld_in_miss,
        "unmintable": result.unmintable,
        "citation_links": result.citation_links,
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
