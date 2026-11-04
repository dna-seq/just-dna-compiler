"""The ClinVar-GKM lane's builder (RM305): two Parquet files in, the indel witness out.

What the lane is, and why its pin is `(source_release, sha256)`, is in `clinvar_gkm`. This module is
the conversion: download both inputs whole, refuse any byte that is not the file `manifest.json`
states, keep the net insertions and net deletions on GRCh38, join each to the ClinVar variation and
rsID that name it, and write `data/`, `LICENSE.txt` and `release.json`.

**Indels only** (decided 2026-11-04). Kept: every allele whose SPDI deletes and inserts a *different*
number of bases. Dropped, and counted per class in `release.json`: no SPDI expression (GRCh37- or
transcript-only names), an accession off the GRCh38 primary assembly (one T2T allele), the same length
deleted as inserted (substitutions, MNVs, and the reference-agreeing `ReferenceLengthExpression`
alleles such as `NC_000021.9:g.45504512_45504520=`, whichever state type carries them), and a `gnomad`
expression that does not spell a VCF allele.

**Downloaded whole, never range-read**, because the source asks for it ("Download the Parquet files you
need, then query them locally. The R2 hosting has rate limits and is designed for file downloads, not as
a remote query endpoint") and because an R2 range request once came back `200` with the whole file
(LANES_0_8 §4). A whole download is checked by size and digest, which a partial body fails either way.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_format.layout import atomic_write_text
from just_dna_format.normalize import now_utc_iso
from just_dna_format.snapshot import (
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
    SnapshotRelease,
    write_release,
)

from just_dna_enricher.civic_build import _G38_ACCESSIONS
from just_dna_enricher.clinvar_gkm import (
    ALLELE_FILE,
    CLINVAR_GKM_VRS_VERSION,
    CLINVAR_GKM_VRS_VERSION_BASIS,
    INPUT_FILES,
    VARIATION_FILE,
    WITNESS_PARQUET,
    ClinVarGkmClient,
    ClinVarGkmMismatch,
    ClinVarGkmUnavailable,
    GkmManifest,
    ManifestFile,
    clinvar_gkm_release_label,
    parquet_url,
    release_older,
)
from just_dna_enricher.net import StreamedFile, stream_to_file

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only without the [dev] extra
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: The dbSNP coding system in `variation.parquet`'s `mappings`; its `code` carries no `rs` prefix.
DBSNP_SYSTEM = "https://www.ncbi.nlm.nih.gov/snp/"
#: The constraint linking a ClinVar variation to the one allele that defines it.
DEFINING_ALLELE_CONSTRAINT = "DefiningAlleleConstraint"

#: GRCh38 primary-assembly accessions, per chromosome, with the mitochondrion. The same map `civic_build`
#: scores accessions with (the version alone names no build, `@accession-version-names-no-build`).
GRCH38_ACCESSIONS: dict[str, str] = {**_G38_ACCESSIONS, "NC_012920.1": "MT"}


# ── the download, verified against the manifest ─────────────────────────────────────────────────


def verify_against_manifest(path: Path, entry: ManifestFile, sha256: str) -> None:
    """Refuse bytes that are not the file the manifest states: wrong size first, then wrong digest.

    The size is what a partial body fails (a range answered with a slice, a cut connection the
    transport did not report); the digest is what an in-place overwrite fails. Both are
    `ClinVarGkmMismatch`, because both mean the same thing to a caller: these bytes are not the release
    the label would name.
    """
    size = Path(path).stat().st_size
    if size != entry.size:
        raise ClinVarGkmMismatch(
            f"{entry.name} is {size} bytes and manifest.json states {entry.size}: a partial or "
            f"replaced body, refused"
        )
    if sha256.strip().lower().removeprefix("sha256:") != entry.sha256:
        raise ClinVarGkmMismatch(
            f"{entry.name} hashes to {sha256} and manifest.json states {entry.sha256}: the set was "
            f"overwritten after the manifest was read, refused. Build again once the source settles"
        )


def download_input(name: str, manifest: GkmManifest, dest: Path, *, url: str | None = None) -> StreamedFile:
    """Download one input whole and verify it against `manifest`. Retries the transport (`net`)."""
    entry = manifest.file(name)
    fetched = stream_to_file(
        dest,
        url or parquet_url(name),
        error_cls=ClinVarGkmUnavailable,
        what=f"ClinVar-GKM's {name}",
        timeout=120.0,
        remedy="Pass the files you already hold with --allele/--variation/--manifest",
    )
    verify_against_manifest(fetched.path, entry, fetched.sha256)
    return fetched


# ── the slice ───────────────────────────────────────────────────────────────────────────────────


def _require_polars() -> None:
    if pl is None:  # pragma: no cover - exercised only without the [dev] extra
        raise ImportError("polars is required to build or read the ClinVar-GKM snapshot")


def _witness_schema() -> dict:
    """Column order and dtypes of the slice — fixed, so a rebuild of the same bytes is byte-identical."""
    return {
        "vrs_id": pl.Utf8,
        "chrom": pl.Utf8,
        "pos": pl.Int64,
        "ref": pl.Utf8,
        "alt": pl.Utf8,
        "gnomad": pl.Utf8,
        "spdi": pl.Utf8,
        "state_type": pl.Utf8,
        "clinvar_variation_id": pl.Utf8,
        "rsid": pl.Utf8,
    }


#: What each allele's `data` JSON is decoded as. Only these fields are read; the rest is ignored.
def _data_dtype():
    return pl.Struct(
        {
            "expressions": pl.List(pl.Struct({"syntax": pl.Utf8, "value": pl.Utf8})),
            "state": pl.Struct({"type": pl.Utf8}),
        }
    )


@dataclass
class SliceCounts:
    """How every allele read was classified. Each dropped class is counted, never silently lost."""

    alleles: int = 0
    no_spdi: int = 0
    off_grch38: int = 0
    same_length: int = 0
    no_vcf_spelling: int = 0
    indels: int = 0


def _expression(syntax: str):
    return (
        pl.col("_data")
        .struct.field("expressions")
        .list.eval(pl.element().filter(pl.element().struct.field("syntax") == syntax).struct.field("value"))
        .list.first()
    )


def indel_slice(allele_path: Path) -> tuple["pl.DataFrame", SliceCounts]:
    """The net insertions and net deletions of `allele.parquet`, keyed by VRS id and VCF spelling."""
    _require_polars()
    frame = (
        pl.scan_parquet(allele_path)
        .select("id", "data")
        .with_columns(_data=pl.col("data").str.json_decode(_data_dtype()))
        .select(
            vrs_id=pl.col("id"),
            state_type=pl.col("_data").struct.field("state").struct.field("type"),
            spdi=_expression("spdi"),
            gnomad=_expression("gnomad"),
        )
        .collect(engine="streaming")
    )
    counts = SliceCounts(alleles=frame.height)
    parts = frame["spdi"].str.split(":")
    frame = frame.with_columns(
        _acc=parts.list.get(0, null_on_oob=True),
        _del=parts.list.get(2, null_on_oob=True),
        _ins=parts.list.get(3, null_on_oob=True),
    )
    no_spdi = pl.col("spdi").is_null() | pl.col("_ins").is_null()
    counts.no_spdi = frame.filter(no_spdi).height
    frame = frame.filter(~no_spdi)
    on_grch38 = pl.col("_acc").is_in(list(GRCH38_ACCESSIONS))
    counts.off_grch38 = frame.filter(~on_grch38).height
    frame = frame.filter(on_grch38)
    # SPDI may state a deletion as a length (`NC_…:100:3:`) rather than a sequence; a digit-only
    # deleted field is read as its number, never as a three-letter sequence.
    deleted = (
        pl.when(pl.col("_del").str.contains(r"^\d+$"))
        .then(pl.col("_del").cast(pl.Int64, strict=False))
        .otherwise(pl.col("_del").str.len_chars().cast(pl.Int64))
    )
    same_length = deleted == pl.col("_ins").str.len_chars().cast(pl.Int64)
    counts.same_length = frame.filter(same_length).height
    frame = frame.filter(~same_length)
    vcf = pl.col("gnomad").str.split("-")
    frame = frame.with_columns(
        chrom=vcf.list.get(0, null_on_oob=True),
        pos=vcf.list.get(1, null_on_oob=True).cast(pl.Int64, strict=False),
        ref=vcf.list.get(2, null_on_oob=True),
        alt=vcf.list.get(3, null_on_oob=True),
        _parts=vcf.list.len(),
    )
    spelled = (
        pl.col("_parts").eq(4)
        & pl.col("pos").is_not_null()
        & pl.col("ref").str.contains(r"^[ACGTN]+$")
        & pl.col("alt").str.contains(r"^[ACGTN]+$")
    )
    counts.no_vcf_spelling = frame.filter(~spelled.fill_null(False)).height
    frame = frame.filter(spelled.fill_null(False))
    counts.indels = frame.height
    return frame.select("vrs_id", "chrom", "pos", "ref", "alt", "gnomad", "spdi", "state_type"), counts


def variation_links(variation_path: Path) -> "pl.DataFrame":
    """`(vrs_id, clinvar_variation_id, rsid)` from `variation.parquet`, by projected read.

    The allele → variation link is the variation's `DefiningAlleleConstraint` (one to one, LANES §3.4);
    the rsID is a dbSNP `mappings` code, prefixed here with `rs`. A variation with no rsID keeps its
    row with `rsid` null, so the left join below loses no allele.
    """
    _require_polars()
    scan = pl.scan_parquet(variation_path).select("id", "mappings", "constraints")
    link = (
        scan.select("id", "constraints")
        .explode("constraints", empty_as_null=True)
        .select(
            clinvar_variation_id=pl.col("id"),
            vrs_id=pl.col("constraints").struct.field("allele"),
            _type=pl.col("constraints").struct.field("type"),
        )
        .filter((pl.col("_type") == DEFINING_ALLELE_CONSTRAINT) & pl.col("vrs_id").is_not_null())
        .drop("_type")
    )
    rsids = (
        scan.select("id", "mappings")
        .explode("mappings", empty_as_null=True)
        .select(
            clinvar_variation_id=pl.col("id"),
            _system=pl.col("mappings").struct.field("coding").struct.field("system"),
            _code=pl.col("mappings").struct.field("coding").struct.field("code"),
        )
        .filter((pl.col("_system") == DBSNP_SYSTEM) & pl.col("_code").str.contains(r"^\d+$"))
        .select("clinvar_variation_id", rsid=pl.lit("rs") + pl.col("_code"))
        .unique(maintain_order=True)
    )
    return link.join(rsids, on="clinvar_variation_id", how="left").collect(engine="streaming")


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "0+unknown"


def clinvar_gkm_license_text(manifest: GkmManifest) -> str:
    """`LICENSE.txt`: the source's own licence, scope, attribution and disclaimer, verbatim."""
    lines = [
        "ClinVar-GKM indel slice (just-dna-enricher, RM305)",
        "",
        f"Licence: {manifest.license_id or 'not stated in manifest.json'}",
        f"Scope: {manifest.license_scope or 'not stated'}",
        "",
        f"Attribution: {manifest.attribution or 'not stated'}",
        "",
        f"Disclaimer: {manifest.disclaimer or 'not stated'}",
        f"ClinVar data-use policy: {manifest.data_use_policy or 'not stated'}",
        "",
        "WHAT THIS SNAPSHOT IS. A derivation of one ClinVar-GKM Parquet set (release "
        f"{manifest.source_release}): the GRCh38 alleles that are a net insertion or a net deletion, "
        "each with its VRS id, SPDI and gnomAD-style VCF spelling, joined to the ClinVar variation and "
        "dbSNP rsID that name it. A placement witness only; it carries no clinical significance.",
    ]
    return "\n".join(lines) + "\n"


@dataclass
class GkmBuildResult:
    """What a build wrote and what it read."""

    out_dir: Path
    witness_file: Path
    dataset: str
    source_release: str
    row_count: int
    counts: SliceCounts
    with_rsid: int
    distinct_rsids: int
    latest_release: str | None = None
    source_sha256: dict[str, str | None] = field(default_factory=dict)

    @property
    def source_lags(self) -> bool | None:
        """Whether the Parquet set the build read is older than the line's newest weekly release."""
        return release_older(self.source_release, self.latest_release)


def build_snapshot(
    allele_path: Path,
    variation_path: Path,
    out_dir: Path,
    *,
    manifest: GkmManifest,
    source_sha256: dict[str, str | None] | None = None,
    source_url: dict[str, str | None] | None = None,
    latest_release: str | None = None,
) -> GkmBuildResult:
    """Cut the indel slice out of the two inputs and write `data/`, `LICENSE.txt` and `release.json`.

    `source_sha256` is each input's digest as the caller established it. When the inputs came off
    local disk and the caller passes none, they are hashed here and checked against `manifest` the
    same way a download is, so a stale local copy is refused rather than labelled with today's release.
    """
    _require_polars()
    out_dir = Path(out_dir)
    digests = dict(source_sha256 or {})
    for name, path in ((ALLELE_FILE, allele_path), (VARIATION_FILE, variation_path)):
        if digests.get(name) is None:
            digests[name] = _sha256_of(Path(path))
        verify_against_manifest(Path(path), manifest.file(name), str(digests[name]))
    slice_frame, counts = indel_slice(Path(allele_path))
    links = variation_links(Path(variation_path))
    witness = (
        slice_frame.join(links, on="vrs_id", how="left")
        .select(list(_witness_schema()))
        .cast(_witness_schema())
        .sort(["chrom", "pos", "ref", "alt", "vrs_id", "rsid"], nulls_last=True)
    )
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    witness_file = data_dir / WITNESS_PARQUET
    staged = witness_file.with_name(witness_file.name + ".part")
    witness.write_parquet(staged, compression="zstd")
    staged.replace(witness_file)
    license_text = clinvar_gkm_license_text(manifest)
    atomic_write_text(out_dir / SNAPSHOT_LICENSE_FILENAME, license_text)
    dataset = clinvar_gkm_release_label(manifest.source_release)
    assert dataset is not None  # parse_manifest refuses a manifest without a release
    with_rsid = witness.filter(pl.col("rsid").is_not_null())
    result = GkmBuildResult(
        out_dir=out_dir,
        witness_file=witness_file,
        dataset=dataset,
        source_release=manifest.source_release,
        row_count=witness.height,
        counts=counts,
        with_rsid=with_rsid.height,
        distinct_rsids=with_rsid["rsid"].n_unique(),
        latest_release=latest_release,
        source_sha256={name: f"sha256:{digests[name]}" for name in INPUT_FILES},
    )
    write_release(
        out_dir,
        SnapshotRelease(
            dataset=dataset,
            source_url=source_url or {name: parquet_url(name) for name in INPUT_FILES},
            source_sha256=result.source_sha256,
            built_at=now_utc_iso(),
            builder_version=_builder_version(),
            license=manifest.license_id,
            license_sha256="sha256:" + _sha256_text(license_text),
            row_count=witness.height,
            record_count=counts.alleles,
            genome_build="GRCh38",
            source_release=manifest.source_release,
            source_dataset=manifest.dataset,
            source_build_date=manifest.build_date,
            source_schema_version=manifest.schema_version,
            latest_release=latest_release,
            vrs_version=CLINVAR_GKM_VRS_VERSION,
            vrs_version_basis=CLINVAR_GKM_VRS_VERSION_BASIS,
            slice_counts={
                "alleles": counts.alleles,
                "no_spdi": counts.no_spdi,
                "off_grch38": counts.off_grch38,
                "same_length": counts.same_length,
                "no_vcf_spelling": counts.no_vcf_spelling,
                "indels": counts.indels,
                "rows_with_rsid": result.with_rsid,
                "distinct_rsids": result.distinct_rsids,
            },
        ),
    )
    logger.info(
        "ClinVar-GKM %s: %d indel rows from %d alleles (%d with an rsID)",
        manifest.source_release,
        witness.height,
        counts.alleles,
        result.with_rsid,
    )
    return result


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def download_and_build(
    out_dir: Path,
    *,
    client: ClinVarGkmClient | None = None,
    keep_downloads: bool = False,
) -> GkmBuildResult:
    """Read the manifest, download both inputs whole, verify them, cut the slice, drop the downloads.

    The manifest is read **twice**: before the downloads, to know what to verify against, and after,
    so a release that landed mid-build is named as such rather than reported as a corrupt file.
    """
    asker = client or ClinVarGkmClient()
    out_dir = Path(out_dir)
    manifest = asker.parquet_manifest()
    latest = asker.latest_release()
    downloads = out_dir / "_downloads"
    fetched: dict[str, StreamedFile] = {}
    try:
        for name in INPUT_FILES:
            try:
                fetched[name] = download_input(name, manifest, downloads / name, url=asker.file_url(name))
            except ClinVarGkmMismatch as exc:
                now = asker.parquet_manifest()
                if now.source_release != manifest.source_release or now.files != manifest.files:
                    raise ClinVarGkmMismatch(
                        f"ClinVar-GKM published {now.source_release} while this build was downloading "
                        f"{manifest.source_release}; build again"
                    ) from exc
                raise
        return build_snapshot(
            fetched[ALLELE_FILE].path,
            fetched[VARIATION_FILE].path,
            out_dir,
            manifest=manifest,
            source_sha256={name: got.sha256 for name, got in fetched.items()},
            source_url={name: asker.file_url(name) for name in INPUT_FILES},
            latest_release=latest,
        )
    finally:
        if not keep_downloads:
            for name in INPUT_FILES:
                (downloads / name).unlink(missing_ok=True)
            if downloads.is_dir() and not any(downloads.iterdir()):
                downloads.rmdir()
