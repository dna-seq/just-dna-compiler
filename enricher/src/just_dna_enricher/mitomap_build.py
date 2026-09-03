"""Build the MITOMAP snapshot the miss lane joins against (RM171).

The acquire stage is a plain `curl` of `https://mitomap.org/downloads/mitomap.dump.sql.gz`. That is
worth stating because the *web* surface of the same host answers `curl` and the fetch tool with a
Cloudflare 403 — which is why this source's terms had to be read from a browser — while the *data*
surface has no interstitial at all. Two surfaces, two answers, and the negative belongs to the one it
was measured on (`@two-surfaces-two-denominators`).

The build keeps six tables out of a 6.76 M-line dump and throws the other hundred away: the two
curated variant tables, their two reference link tables, `reference`, and `edit_date`. Each variant
row carries its source columns verbatim beside the four derived ones — the split status, the mapped
`clin_sig`, the reason its alleles cannot be spelled as VCF where that applies, and the gene where
`locus` names exactly one.

**The dataset label comes from inside the dump, which is what makes a local build comparable.** The
dump carries `edit_date`, a per-table curation date (`mMut`, `rtMut`), and the label is both of them —
the same choice ClinVar makes with `##fileDate` rather than with `Last-Modified`. The header and the
sha256 are recorded in `release.json` beside it, because provenance of the *fetch* is a different
question from identity of the *content*, and a build from `--dump <file>` has the second and not the
first.
"""

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.mitomap import (
    DUMP_TABLES,
    EDIT_DATE_NAMES,
    EDIT_DATE_TABLE,
    LINK_TABLES,
    REFERENCE_TABLE,
    VARIANT_TABLES,
    MitomapError,
    MitomapUnavailable,
    allele_defect,
    nlmid_pmid,
    parse_status,
    read_dump_tables,
    single_gene,
    vcep_clin_sig,
    withheld_bracket,
)
from just_dna_enricher.net import stream_to_file

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

DEFAULT_MITOMAP_URL = "https://mitomap.org/downloads/mitomap.dump.sql.gz"

#: One parquet per variant table, named for the table so a reader never has to ask which one it holds.
VARIANT_PARQUET = {name: f"mitomap-{name}.parquet" for name in VARIANT_TABLES}
#: The citation link, resolved to PMIDs, and the reference records behind it.
CITATIONS_PARQUET = "mitomap-citations.parquet"
REFERENCES_PARQUET = "mitomap-references.parquet"

#: The variant parquet's columns, in order, so a rebuild is byte-identical (Principle 7). `aa` is
#: `mmutation`'s amino-acid change and `rna` is `rtmutation`'s RNA feature — one column each, null on
#: the other table, because folding two differently-named source columns into one would state that
#: they are the same fact.
VARIANT_COLUMNS: tuple[str, ...] = (
    "table", "record_id", "locus", "gene", "disease", "allele", "start", "ref", "alt",
    "aa", "rna", "conservation", "controls", "homoplasmy", "heteroplasmy",
    "status", "status_confirmation", "status_bracket", "status_qualifier",
    "clin_sig", "withheld_bracket", "allele_defect", "cfrm_date",
)


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


@dataclass(frozen=True)
class DownloadedDump:
    """Where the dump landed and what the server said about it."""

    path: Path
    sha256: str
    url: str
    #: The `Last-Modified` header, verbatim. `None` when the server sent none — an unknown date, not
    #: a missing one, and the snapshot then carries no `dataset` for the same reason.
    last_modified: str | None


@dataclass
class MitomapBuildResult:
    """What the snapshot holds and what it came from."""

    out_dir: Path
    parquet_files: list[Path]
    #: `table -> rows written`, so a count is always attached to the table it was measured on.
    rows: dict[str, int] = field(default_factory=dict)
    #: `table -> edit_date`, the dump's own in-band statement of when each table was last curated.
    edit_dates: dict[str, str | None] = field(default_factory=dict)
    reference_rows: int = 0
    #: References whose `nlmid` is a bare PMID, those stating none, and the ones stating something
    #: else. Three numbers because they are three different answers, and the last is what the
    #: strategy note left owed on a sample of four.
    references_with_pmid: int = 0
    references_without_nlmid: int = 0
    references_not_a_pmid: int = 0
    citation_links: int = 0
    #: `reason -> count` over both variant tables, from `mitomap.allele_defect`.
    unmintable: dict[str, int] = field(default_factory=dict)
    #: `bracket -> count` for a bracket that is not one of the five documented classes.
    withheld_brackets: dict[str, int] = field(default_factory=dict)
    dataset: str | None = None
    source_sha256: str | None = None
    source_last_modified: str | None = None

    @property
    def variant_rows(self) -> int:
        return sum(self.rows.get(name, 0) for name in VARIANT_TABLES)


def download_mitomap_dump(dest: Path, url: str = DEFAULT_MITOMAP_URL) -> DownloadedDump:
    """Stream the MITOMAP dump to `dest` (atomic `.part` rename), hashing while streaming.

    **`httpx`'s exceptions do not leave this function** (`@client-exception-contract`): a Cloudflare
    403 on a mistyped path has to reach the CLI as `MITOMAP BUILD FAILED: …` rather than as a raw
    `HTTPStatusError`, and the half-written `.part` goes with it so a failed run leaves the directory
    as it found it.
    """
    streamed = stream_to_file(
        dest, url, error_cls=MitomapUnavailable, what="the MITOMAP dump",
    )
    return DownloadedDump(
        path=streamed.path, sha256=streamed.sha256, url=url, last_modified=streamed.last_modified,
    )


def _sha256_file(path: Path) -> str | None:
    """sha256 of a file, or `None` when it cannot be read — an unknown digest, never a missing one."""
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                hasher.update(chunk)
    except OSError as exc:
        logger.warning("Could not hash %s (%s); recording an unknown source_sha256.", path, exc)
        return None
    return hasher.hexdigest()


def dataset_label(edit_dates: dict[str, str | None]) -> str | None:
    """`mitomap_<mmutation date>+<rtmutation date>` from the dump's own `edit_date` table.

    **In band, and that is the ClinVar precedent rather than a preference.** ClinVar's `dataset` is
    the `##fileDate` its VCF states about itself, not the `Last-Modified` its server states about the
    transfer — so the same label comes out whether the file was downloaded or handed over. The dump
    has the same property in `edit_date`, and taking it there is what lets `mitomap build --dump` from
    a copy on disk produce a snapshot that can be compared against a downloaded one. The header and
    the sha256 are still recorded in `release.json`; they are provenance of the *fetch*, which is a
    different question.

    **Two dates, because this lane adopts two tables and they are curated separately.** A compound
    artifact gets a compound label — the same shape the derived miss lane uses for its two parents.
    Taking the later of the two would state that a `rtmutation` from August applies to an `mmutation`
    from October, and `None` where either is missing, because half a label is not a shorter label: it
    is one that cannot be compared.
    """
    dates = [edit_dates.get(name) for name in VARIANT_TABLES]
    if not all(dates):
        return None
    return "mitomap_" + "+".join(str(date) for date in dates)


def _variant_cells(table: str, row: dict[str, str | None]) -> dict[str, object]:
    """One source row → the snapshot's row: every published cell, plus the four derived ones."""
    status = parse_status(row.get("status"))
    position = (row.get("position") or "").strip()
    return {
        "table": table,
        "record_id": (row.get("id") or "").strip() or None,
        "locus": (row.get("locus") or "").strip() or None,
        "gene": single_gene(row.get("locus")),
        "disease": (row.get("dz") or "").strip() or None,
        "allele": (row.get("allele") or "").strip() or None,
        "start": int(position) if position.isdigit() else None,
        "ref": (row.get("refna") or "").strip().upper() or None,
        "alt": (row.get("regna") or "").strip().upper() or None,
        "aa": (row.get("aa") or "").strip() or None,
        "rna": (row.get("rna") or "").strip() or None,
        "conservation": (row.get("cons") or "").strip() or None,
        "controls": (row.get("contr") or "").strip() or None,
        # MITOMAP's presence flags over a literature corpus (`+`/`-`/`nr`), NOT a called genotype.
        # Kept verbatim and named for what they are, because the first repair anyone proposes is to
        # read `homo=+` as a homoplasmic call and fill `VariantRow.genotype` from it.
        "homoplasmy": (row.get("homo") or "").strip() or None,
        "heteroplasmy": (row.get("hetero") or "").strip() or None,
        "status": status.raw or None,
        "status_confirmation": status.confirmation,
        "status_bracket": status.bracket,
        "status_qualifier": status.qualifier,
        "clin_sig": vcep_clin_sig(status),
        "withheld_bracket": withheld_bracket(status),
        "allele_defect": allele_defect(row.get("refna"), row.get("regna")),
        "cfrm_date": (row.get("cfrm_date") or "").strip() or None,
    }


def build_snapshot(
    dump: Path,
    out_dir: Path,
    *,
    source_url: str = DEFAULT_MITOMAP_URL,
    source_sha256: str | None = None,
    source_last_modified: str | None = None,
) -> MitomapBuildResult:
    """Turn a MITOMAP `pg_dump` into `out_dir/data/*.parquet` + `release.json`.

    Rows are sorted by `(start, ref, alt, record_id)` per table so a rebuild from the same bytes is
    byte-identical (Principle 7); `release.json`'s `built_at` is the only per-run-varying byte and
    lives outside the parquet.

    **A dump missing one of the six tables is refused, not built short.** A snapshot silently lacking
    `rtmutation` would make every later miss count a lie about a table nobody looked at, and the
    single hardest thing to notice about a derived artifact is a denominator that changed.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the MITOMAP snapshot; install the publisher/dev surface "
            "with `pip install 'just-dna-enricher[dev]'` (or `uv sync --group dev`)."
        )
    dump = Path(dump)
    out_dir = Path(out_dir)
    tables = read_dump_tables(dump)
    missing = [name for name in DUMP_TABLES if name not in tables]
    if missing:
        raise MitomapError(
            f"{dump} carries no {', '.join(missing)} table. Refusing to build a snapshot that is "
            f"short a table rather than empty in one — a miss count derived from it would be "
            f"measured against a denominator nobody stated."
        )

    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    result = MitomapBuildResult(out_dir=out_dir, parquet_files=[])

    unmintable: Counter[str] = Counter()
    withheld: Counter[str] = Counter()
    for table in VARIANT_TABLES:
        cells = [_variant_cells(table, row) for row in tables[table]]
        for cell in cells:
            if cell["allele_defect"] is not None:
                unmintable[str(cell["allele_defect"])] += 1
            if cell["withheld_bracket"] is not None:
                withheld[str(cell["withheld_bracket"])] += 1
        frame = pl.DataFrame(cells, schema=_variant_schema()).sort(
            ["start", "ref", "alt", "record_id"], nulls_last=True
        )
        path = data_dir / VARIANT_PARQUET[table]
        frame.write_parquet(path)
        result.parquet_files.append(path)
        result.rows[table] = frame.height
    result.unmintable = dict(sorted(unmintable.items()))
    result.withheld_brackets = dict(sorted(withheld.items()))

    references = tables[REFERENCE_TABLE]
    pmid_by_reference: dict[str, str] = {}
    reference_cells: list[dict[str, object]] = []
    for row in references:
        ref_id = (row.get("id") or "").strip()
        pmid = nlmid_pmid(row.get("nlmid"))
        if pmid is not None and ref_id:
            pmid_by_reference[ref_id] = pmid
        raw = (row.get("nlmid") or "").strip()
        if not raw:
            result.references_without_nlmid += 1
        elif pmid is None:
            result.references_not_a_pmid += 1
        else:
            result.references_with_pmid += 1
        reference_cells.append({
            "reference_id": ref_id or None,
            "authors": (row.get("authors") or "").strip() or None,
            "title": (row.get("title") or "").strip() or None,
            "publication": (row.get("publication") or "").strip() or None,
            "year": (row.get("date") or "").strip() or None,
            "nlmid": raw or None,
            "pmid": pmid,
        })
    result.reference_rows = len(reference_cells)
    references_frame = pl.DataFrame(reference_cells, schema=_reference_schema()).sort(
        ["reference_id"], nulls_last=True
    )
    references_path = data_dir / REFERENCES_PARQUET
    references_frame.write_parquet(references_path)
    result.parquet_files.append(references_path)

    citations: list[dict[str, object]] = []
    for table, link_table in LINK_TABLES.items():
        id_column = f"{table}_id"
        for row in tables[link_table]:
            record_id = (row.get(id_column) or "").strip()
            reference_id = (row.get("reference_id") or "").strip()
            pmid = pmid_by_reference.get(reference_id)
            if not record_id or pmid is None:
                # A link into a reference with no PMID is a real link this tier cannot express as a
                # `StudyRow`. Dropped here and counted by the difference between `citation_links` and
                # the dump's own link total, which the drafter reports rather than implying that
                # every MITOMAP citation reached the module.
                continue
            citations.append({
                "table": table, "record_id": record_id, "reference_id": reference_id, "pmid": pmid,
            })
    citations_frame = pl.DataFrame(citations, schema=_citation_schema()).unique(
        subset=["table", "record_id", "pmid"], keep="first"
    ).sort(["table", "record_id", "pmid"])
    citations_path = data_dir / CITATIONS_PARQUET
    citations_frame.write_parquet(citations_path)
    result.parquet_files.append(citations_path)
    result.citation_links = citations_frame.height

    dates = {
        (row.get("table_name") or "").strip(): (row.get("date") or "").strip() or None
        for row in tables[EDIT_DATE_TABLE]
    }
    result.edit_dates = {name: dates.get(EDIT_DATE_NAMES[name]) for name in VARIANT_TABLES}
    result.source_sha256 = source_sha256 or _sha256_file(dump)
    result.source_last_modified = source_last_modified
    result.dataset = dataset_label(result.edit_dates)
    _write_release_json(out_dir, result, source_url=source_url)
    logger.info(
        "Built MITOMAP snapshot: %s → %s",
        ", ".join(f"{name} {count}" for name, count in result.rows.items()), data_dir,
    )
    return result


def _variant_schema() -> dict:
    return {
        name: (pl.Int64 if name == "start" else pl.Utf8) for name in VARIANT_COLUMNS
    }


def _reference_schema() -> dict:
    return {
        "reference_id": pl.Utf8, "authors": pl.Utf8, "title": pl.Utf8, "publication": pl.Utf8,
        "year": pl.Utf8, "nlmid": pl.Utf8, "pmid": pl.Utf8,
    }


def _citation_schema() -> dict:
    return {"table": pl.Utf8, "record_id": pl.Utf8, "reference_id": pl.Utf8, "pmid": pl.Utf8}


def _write_release_json(out_dir: Path, result: MitomapBuildResult, *, source_url: str) -> Path:
    """The snapshot's provenance, including every count this build computed and would otherwise drop.

    `withheld_brackets` and `unmintable` are in here for the same reason as the row counts: they are
    the two numbers a reader of this adoption most needs, and one computed and discarded is one every
    consumer recomputes (`@dont-discard-computed`). Neither is ever read back as a constant — the
    figures are re-derived on every build, which is what stops a diff snapshot from becoming a
    hardcoded inventory.
    """
    release = {
        "dataset": result.dataset,
        "source_url": source_url,
        "source_sha256": result.source_sha256,
        "source_last_modified": result.source_last_modified,
        "rows": result.rows,
        "table_edit_dates": result.edit_dates,
        "reference_rows": result.reference_rows,
        "references_with_pmid": result.references_with_pmid,
        "references_without_nlmid": result.references_without_nlmid,
        "references_not_a_pmid": result.references_not_a_pmid,
        "citation_links": result.citation_links,
        "unmintable": result.unmintable,
        "withheld_brackets": result.withheld_brackets,
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
