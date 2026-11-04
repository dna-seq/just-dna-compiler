"""Open Targets Platform snapshot builder (0.8, RM333): one pinned release, trimmed to what a module joins.

The source is the Platform's bulk output on EBI's FTP, served over https
(`https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/<release>/output/<dataset>/part-*.parquet`).
Five datasets are read, all Spark output split into parts (`probes/LANES_0_8.md` § 1 has their schemas,
row counts and sizes as measured on 2026-11-04):

| dataset | what the snapshot keeps |
|---|---|
| `variant` | the allele table (`variants.parquet`) and every per-transcript consequence (`consequences-*.parquet`) |
| `credible_set` | GWAS credible sets (`credible_sets.parquet`) and their members' posteriors (`credible_set_members-*.parquet`) |
| `l2g_prediction` | the locus-to-gene score per (study locus, gene) (`l2g.parquet`) |
| `colocalisation` | the GWAS-left × molecular-QTL-right pairs, with the right side's gene and tissue (`colocalisations-*.parquet`) |
| `study` | read only to name a coloc row's right-hand gene and tissue |

**Flattened at build, read by duckdb at run time** (`@duckdb-vs-polars`). Every list column the runtime
pass would otherwise unnest per query (`locus`, `transcriptConsequences`) is exploded here, once.

**Alleles come from columns, never from the id.** `variantId` is `<chr>_<pos>_<ref>_<alt>` with
underscores (the croissant says hyphens) and, for 2,114 long alleles, an `OTVAR_…` hash; the snapshot
keeps the id only as an internal join key and the alleles from `referenceAllele`/`alternateAllele`.

**What is trimmed, and why each cut is not a judgement.** Credible sets and members are kept for GWAS
studies only, because RM239's posterior and RM333's L2G are about a GWAS locus. Coloc rows are kept
when the left side is a GWAS credible set and the right side is not (`rightStudyType != 'gwas'`): a
GWAS-GWAS pair says two traits share a locus and names no gene, which is ~72% of the dataset. No row is
dropped for its value: no score, posterior or h4 threshold is applied anywhere.

**A partial build says so.** `parts` limits how many parts of each dataset are read, for a test-sized
or bandwidth-limited build; `release.json` then records `parts_read` beside `parts_total`, and the
runtime pass warns that an absent coloc or L2G row may mean "not read" rather than "not published".

Builder-only (`polars` is a guarded import), as every builder here.
"""

import hashlib
import json
import logging
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso
from just_dna_format.snapshot import SnapshotRelease, read_release, write_release

from just_dna_enricher.net import stream_to_file

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None

logger = logging.getLogger(__name__)

#: The release this lane is pinned to. A directory name on the FTP, and the croissant's `version`.
OPENTARGETS_RELEASE: str = "26.09"
DEFAULT_OPENTARGETS_BASE_URL: str = "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform"

#: The datasets read, in build order. `study` comes before `colocalisation` because the coloc rows'
#: right-hand gene and tissue are looked up in it.
OPENTARGETS_DATASETS: tuple[str, ...] = (
    "variant",
    "credible_set",
    "l2g_prediction",
    "study",
    "colocalisation",
)

#: The snapshot's tables. A name ending in `-*` is written one file per source part, so the build never
#: holds an exploded 280-million-row table in memory; the runtime reads it by glob.
VARIANTS_FILE = "variants.parquet"
CONSEQUENCES_GLOB = "consequences-*.parquet"
CREDIBLE_SETS_FILE = "credible_sets.parquet"
MEMBERS_GLOB = "credible_set_members-*.parquet"
L2G_FILE = "l2g.parquet"
COLOC_GLOB = "colocalisations-*.parquet"


#: `release.json`'s `dataset`, the label `cache status` prints and every derived row carries.
def release_label(release: str = OPENTARGETS_RELEASE) -> str:
    return f"opentargets_{release}"


_PART_PATTERN = re.compile(r"part-[0-9A-Za-z.\-]+?\.parquet")


class OpenTargetsBuildError(RuntimeError):
    """The Open Targets lane failed; the builder's own type, so the lane adapter can catch it as this lane."""


class OpenTargetsUnavailable(OpenTargetsBuildError):
    """The FTP did not answer: the fetch failed, not the data."""


@dataclass
class OpenTargetsBuildResult:
    """What a build wrote, counted per table."""

    out_dir: Path
    release: str
    row_counts: dict[str, int] = field(default_factory=dict)
    parts_read: dict[str, int] = field(default_factory=dict)
    parts_total: dict[str, int] = field(default_factory=dict)


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


def _require_polars() -> None:
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise ImportError(
            "polars is required to build the Open Targets snapshot; install the dev surface with "
            "`uv sync --group dev`."
        )


def dataset_url(
    dataset: str, *, release: str = OPENTARGETS_RELEASE, base_url: str = DEFAULT_OPENTARGETS_BASE_URL
) -> str:
    return f"{base_url.rstrip('/')}/{release}/output/{dataset}/"


def list_parts(
    dataset: str,
    listing_dir: Path,
    *,
    release: str = OPENTARGETS_RELEASE,
    base_url: str = DEFAULT_OPENTARGETS_BASE_URL,
) -> list[str]:
    """The part filenames of one dataset, read off the FTP's https directory listing.

    The listing is fetched through `net.stream_to_file`, so it is retried and translated like every
    other download here; the parts are sorted so a partial build always reads the same ones.
    """
    listing = stream_to_file(
        listing_dir / f"{dataset}.listing.html",
        dataset_url(dataset, release=release, base_url=base_url),
        error_cls=OpenTargetsUnavailable,
        what=f"the Open Targets {release} `{dataset}` listing",
    ).path
    names = sorted(set(_PART_PATTERN.findall(listing.read_text(encoding="utf-8", errors="replace"))))
    if not names:
        raise OpenTargetsBuildError(
            f"the {dataset} listing at {dataset_url(dataset, release=release, base_url=base_url)} names no parquet part"
        )
    return names


def download_release(
    dest: Path,
    *,
    release: str = OPENTARGETS_RELEASE,
    base_url: str = DEFAULT_OPENTARGETS_BASE_URL,
    parts: int | None = None,
    workers: int = 8,
) -> dict[str, int]:
    """Mirror the five datasets' parts into `dest/<dataset>/`, returning each dataset's total part count.

    A part already on disk with a parquet footer is not fetched again, so an interrupted mirror resumes.
    `parts` keeps the first N parts of each dataset (sorted by name), for a test-sized or
    bandwidth-limited build; `build_snapshot` records how many were read against the total. The
    croissant (the release's only licence and version marker) is fetched beside them.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    stream_to_file(
        dest / "croissant.json",
        f"{base_url.rstrip('/')}/{release}/croissant.json",
        error_cls=OpenTargetsUnavailable,
        what=f"the Open Targets {release} croissant",
    )
    totals: dict[str, int] = {}
    jobs: list[tuple[Path, str, str]] = []
    for dataset in OPENTARGETS_DATASETS:
        names = list_parts(dataset, dest, release=release, base_url=base_url)
        totals[dataset] = len(names)
        # `study` is one part and is read whole; a limit on it would leave coloc rows unnameable.
        chosen = names if (parts is None or dataset == "study") else names[:parts]
        for name in chosen:
            target = dest / dataset / name
            if target.exists() and _footer_ok(target):
                continue
            jobs.append((target, dataset_url(dataset, release=release, base_url=base_url) + name, dataset))
    atomic_write_text(dest / "parts_total.json", json.dumps(totals, sort_keys=True))

    def _fetch(job: tuple[Path, str, str]) -> None:
        target, url, dataset = job
        stream_to_file(
            target, url, error_cls=OpenTargetsUnavailable, what=f"Open Targets `{dataset}` part {target.name}"
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(_fetch, job) for job in jobs]
        try:
            for future in futures:
                future.result()
        except BaseException:
            # The first failure surfaces now, typed as this lane's, rather than after every queued
            # part has been fetched for nothing.
            pool.shutdown(wait=True, cancel_futures=True)
            raise
    return totals


def _footer_ok(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(4)
        handle.seek(-4, 2)
        return head == b"PAR1" and handle.read(4) == b"PAR1"


def _parts(source: Path, dataset: str) -> list[Path]:
    found = sorted((source / dataset).glob("part-*.parquet"))
    if not found:
        raise OpenTargetsBuildError(
            f"no `{dataset}` parts under {source / dataset}; mirror the release first"
        )
    return found


def _source_digest(source: Path) -> str:
    """One sha256 over every part read, as `<dataset>/<part> <sha256>` lines in sorted order.

    Many parts and no single source file, so the digest names the set: a rebuild from the same bytes
    states the same digest, and a re-run that read one more part does not.
    """
    parts = [(dataset, part) for dataset in OPENTARGETS_DATASETS for part in _parts(source, dataset)]

    def _hash(item: tuple[str, Path]) -> str:
        dataset, part = item
        hasher = hashlib.sha256()
        with part.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 22), b""):
                hasher.update(chunk)
        return f"{dataset}/{part.name} {hasher.hexdigest()}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        lines = list(pool.map(_hash, parts))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _croissant_markers(source: Path) -> dict[str, str | None]:
    path = source / "croissant.json"
    if not path.exists():
        return {"version": None, "date_published": None, "license": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "version": data.get("version"),
        "date_published": data.get("datePublished"),
        "license": data.get("license"),
    }


def _build_variants(source: Path, data_dir: Path) -> int:
    frame = (
        pl.scan_parquet([str(p) for p in _parts(source, "variant")])
        .select(
            pl.col("variantId").alias("variant_id"),
            pl.col("chromosome").cast(pl.Utf8).alias("chrom"),
            pl.col("position").cast(pl.Int64).alias("position"),
            pl.col("referenceAllele").alias("ref"),
            pl.col("alternateAllele").alias("alt"),
        )
        .sort("chrom", "position", "ref", "alt", "variant_id")
        .collect()
    )
    frame.write_parquet(data_dir / VARIANTS_FILE)
    return frame.height


def _build_consequences(source: Path, data_dir: Path) -> int:
    """One file per `variant` part: the exploded `transcriptConsequences`, sorted for byte-stable output."""
    total = 0
    for index, part in enumerate(_parts(source, "variant")):
        frame = (
            pl.scan_parquet(str(part))
            .select(pl.col("variantId").alias("variant_id"), pl.col("transcriptConsequences"))
            .explode("transcriptConsequences")
            .drop_nulls("transcriptConsequences")
            .select(
                "variant_id",
                pl.col("transcriptConsequences").struct.field("transcriptId").alias("transcript"),
                pl.col("transcriptConsequences").struct.field("targetId").alias("gene_id"),
                pl.col("transcriptConsequences").struct.field("approvedSymbol").alias("gene"),
                pl.col("transcriptConsequences")
                .struct.field("variantFunctionalConsequenceIds")
                .list.join(",")
                .alias("consequence_so_ids"),
                pl.col("transcriptConsequences").struct.field("impact").alias("impact"),
                pl.col("transcriptConsequences").struct.field("maneSelect").alias("mane_select"),
                pl.col("transcriptConsequences").struct.field("isEnsemblCanonical").alias("canonical"),
            )
            .sort("variant_id", "transcript")
            .collect()
        )
        frame.write_parquet(data_dir / f"consequences-{index:05d}.parquet")
        total += frame.height
    return total


def _build_credible_sets(source: Path, data_dir: Path) -> tuple[int, int, "pl.DataFrame"]:
    """GWAS heads, GWAS members (one file per part), and the all-types `studyLocusId → studyId` map coloc needs."""
    heads: list = []
    locus_study: list = []
    members_total = 0
    for index, part in enumerate(_parts(source, "credible_set")):
        # One read per part: the all-types map needs two columns of every row, and the GWAS half needs
        # the `locus` list, so the part is read once and both are cut from it.
        frame = pl.read_parquet(
            str(part),
            columns=[
                "studyLocusId",
                "studyId",
                "variantId",
                "studyType",
                "finemappingMethod",
                "confidence",
                "locus",
            ],
        )
        locus_study.append(
            frame.select(pl.col("studyLocusId").alias("study_locus_id"), pl.col("studyId").alias("study_id"))
        )
        gwas = frame.filter(pl.col("studyType") == "gwas")
        heads.append(
            gwas.select(
                pl.col("studyLocusId").alias("study_locus_id"),
                pl.col("studyId").alias("study_id"),
                pl.col("variantId").alias("lead_variant_id"),
                pl.col("finemappingMethod").alias("fine_mapping_method"),
                pl.col("confidence").alias("confidence"),
            )
        )
        members = (
            gwas.select(pl.col("studyLocusId").alias("study_locus_id"), pl.col("locus"))
            .explode("locus")
            .drop_nulls("locus")
            .select(
                "study_locus_id",
                pl.col("locus").struct.field("variantId").alias("variant_id"),
                pl.col("locus").struct.field("posteriorProbability").alias("posterior_probability"),
            )
            .sort("variant_id", "study_locus_id")
        )
        members.write_parquet(data_dir / f"credible_set_members-{index:05d}.parquet")
        members_total += members.height
    head_frame = pl.concat(heads).sort("study_locus_id")
    head_frame.write_parquet(data_dir / CREDIBLE_SETS_FILE)
    return head_frame.height, members_total, pl.concat(locus_study)


def _build_l2g(source: Path, data_dir: Path, gwas_loci: "pl.DataFrame") -> int:
    frame = (
        pl.scan_parquet([str(p) for p in _parts(source, "l2g_prediction")])
        .select(
            pl.col("studyLocusId").alias("study_locus_id"),
            pl.col("geneId").alias("gene_id"),
            pl.col("score").alias("l2g_score"),
        )
        .join(gwas_loci.lazy(), on="study_locus_id", how="semi")
        .sort("study_locus_id", "gene_id")
        .collect()
    )
    frame.write_parquet(data_dir / L2G_FILE)
    return frame.height


def _build_coloc(source: Path, data_dir: Path, gwas_loci: "pl.DataFrame", locus_study: "pl.DataFrame") -> int:
    """One file per coloc part: GWAS-left × molecular-QTL-right rows, the right side named by its study."""
    study = (
        pl.scan_parquet([str(p) for p in _parts(source, "study")])
        .select(
            pl.col("studyId").alias("right_study_id"),
            pl.col("geneId").alias("right_gene_id"),
            pl.col("biosampleId").alias("right_biosample_id"),
        )
        .collect()
    )
    right = locus_study.rename({"study_locus_id": "right_study_locus_id", "study_id": "right_study_id"}).join(
        study, on="right_study_id", how="left"
    )
    total = 0
    for index, part in enumerate(_parts(source, "colocalisation")):
        frame = (
            pl.scan_parquet(str(part))
            .filter(pl.col("rightStudyType") != "gwas")
            .select(
                pl.col("leftStudyLocusId").alias("study_locus_id"),
                pl.col("rightStudyLocusId").alias("right_study_locus_id"),
                pl.col("rightStudyType").alias("right_study_type"),
                pl.col("colocalisationMethod").alias("method"),
                pl.col("h4").cast(pl.Float64),
                pl.col("clpp").cast(pl.Float64),
                pl.col("numberColocalisingVariants").cast(pl.Int64).alias("colocalising_variants"),
            )
            .join(gwas_loci.lazy(), on="study_locus_id", how="semi")
            .join(right.lazy(), on="right_study_locus_id", how="left")
            .sort("study_locus_id", "right_study_locus_id")
            .collect()
        )
        frame.write_parquet(data_dir / f"colocalisations-{index:05d}.parquet")
        total += frame.height
    return total


def build_snapshot(
    source: Path,
    out_dir: Path,
    *,
    release: str = OPENTARGETS_RELEASE,
    base_url: str = DEFAULT_OPENTARGETS_BASE_URL,
) -> OpenTargetsBuildResult:
    """Flatten a mirrored release (`source/<dataset>/part-*.parquet`) into the snapshot at `out_dir`.

    Every table is sorted on its key before it is written, so a rebuild from the same parts writes the
    same parquet bytes (Principle 7); `release.json`'s `built_at` is the only per-run byte.
    """
    _require_polars()
    source, out_dir = Path(source), Path(out_dir)
    # Built beside the live payload and swapped in at the end, never in place: a build that fails
    # halfway must leave the previous snapshot whole rather than a short payload under an old
    # `release.json` the resolver would accept.
    data_dir = out_dir / "data.building"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)

    counts: dict[str, int] = {}
    counts["variants"] = _build_variants(source, data_dir)
    counts["consequences"] = _build_consequences(source, data_dir)
    counts["credible_sets"], counts["credible_set_members"], locus_study = _build_credible_sets(
        source, data_dir
    )
    gwas_loci = pl.read_parquet(data_dir / CREDIBLE_SETS_FILE, columns=["study_locus_id"])
    counts["l2g"] = _build_l2g(source, data_dir, gwas_loci)
    counts["colocalisations"] = _build_coloc(source, data_dir, gwas_loci, locus_study)

    totals_path = source / "parts_total.json"
    totals = json.loads(totals_path.read_text(encoding="utf-8")) if totals_path.exists() else {}
    read = {dataset: len(_parts(source, dataset)) for dataset in OPENTARGETS_DATASETS}
    markers = _croissant_markers(source)
    digest = _source_digest(source)
    live = out_dir / "data"
    if live.exists():
        shutil.rmtree(live)
    data_dir.rename(live)
    write_release(
        out_dir,
        SnapshotRelease(
            dataset=release_label(release),
            source_url=f"{base_url.rstrip('/')}/{release}/output/",
            source_sha256=digest,
            license="CC0-1.0",
            genome_build="GRCh38",
            built_at=now_utc_iso(),
            builder_version=_builder_version(),
            row_counts=counts,
            parts_read=read,
            parts_total=totals or None,
            croissant=markers,
        ),
    )
    logger.info("Built Open Targets %s snapshot at %s: %s", release, out_dir, counts)
    return OpenTargetsBuildResult(
        out_dir=out_dir, release=release, row_counts=counts, parts_read=read, parts_total=totals
    )


def subset_snapshot(
    snapshot: Path,
    out_dir: Path,
    alleles: list[tuple[str, int, str, str]],
    studies: list[str] | None = None,
) -> dict[str, int]:
    """Cut a built snapshot down to the loci of `alleles` (`(chrom, position, ref, alt)`), as a snapshot.

    For a test fixture or a regional snapshot: every table keeps exactly the rows the runtime pass would
    read for those alleles (their variants and consequences, their credible-set memberships, the sets
    they lead, those sets' L2G and coloc rows), so a pass over the subset answers as it would over the
    whole release for those variants. `studies` keeps every credible-set head of those studies too,
    so "the study has credible sets, and the variant is in none" answers on the subset as it does on
    the release. The `release.json` is the parent's with `subset_of` added.
    """
    _require_polars()
    snapshot, out_dir = Path(snapshot), Path(out_dir)
    src, data_dir = snapshot / "data", out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    wanted = pl.DataFrame(
        alleles, schema={"chrom": pl.Utf8, "position": pl.Int64, "ref": pl.Utf8, "alt": pl.Utf8}, orient="row"
    )
    variants = (
        pl.read_parquet(src / VARIANTS_FILE)
        .join(wanted, on=["chrom", "position", "ref", "alt"], how="semi")
        .sort("chrom", "position", "ref", "alt", "variant_id")
    )
    ids = variants.select("variant_id")
    members = pl.scan_parquet(str(src / MEMBERS_GLOB)).join(ids.lazy(), on="variant_id", how="semi").collect()
    sets = pl.read_parquet(src / CREDIBLE_SETS_FILE)
    led = sets.join(ids.rename({"variant_id": "lead_variant_id"}), on="lead_variant_id", how="semi")
    of_studies = sets.filter(pl.col("study_id").is_in(studies or [])).select("study_locus_id")
    kept_sets = sets.join(
        pl.concat([members.select("study_locus_id"), led.select("study_locus_id"), of_studies]).unique(),
        on="study_locus_id",
        how="semi",
    ).sort("study_locus_id")
    loci = led.select("study_locus_id")
    tables = {
        VARIANTS_FILE: variants,
        "consequences-00000.parquet": pl.scan_parquet(str(src / CONSEQUENCES_GLOB))
        .join(ids.lazy(), on="variant_id", how="semi")
        .sort("variant_id", "transcript")
        .collect(),
        CREDIBLE_SETS_FILE: kept_sets,
        "credible_set_members-00000.parquet": members.sort("variant_id", "study_locus_id"),
        L2G_FILE: pl.read_parquet(src / L2G_FILE)
        .join(loci, on="study_locus_id", how="semi")
        .sort("study_locus_id", "gene_id"),
        "colocalisations-00000.parquet": pl.scan_parquet(str(src / COLOC_GLOB))
        .join(loci.lazy(), on="study_locus_id", how="semi")
        .sort("study_locus_id", "right_study_locus_id")
        .collect(),
    }
    counts: dict[str, int] = {}
    for name, frame in tables.items():
        frame.write_parquet(data_dir / name)
        counts[name] = frame.height
    parent = read_release(snapshot)
    record = parent.model_dump(exclude_none=True) if parent is not None else {}
    record.update(
        {
            "built_at": now_utc_iso(),
            "row_counts": counts,
            "subset_of": [f"{c}_{p}_{r}_{a}" for c, p, r, a in alleles],
        }
    )
    write_release(out_dir, SnapshotRelease(**record))
    return counts
