"""Build the CIViC snapshot (`[dev]`) — derived, dated, and the first one that may be published.

CIViC (Griffith et al., *Nat Genet* 2017; `civicdb.org`) is a curated knowledgebase of variant
interpretations in cancer. It is a **source**, of the same kind as ClinVar and PubMind: an
authoritative *annotation* source. Nothing it produces may enter `resolution.csv` — CIViC states a
clinical opinion about a locus something else resolved, and `resolution.csv`'s `authority` column is a
different word for a different thing (`@source-vs-authority`).

**Two published surfaces disagree, and the dated download is the one a snapshot may use.** The
GraphQL API defaults to `status: NON_REJECTED` and serves 11,518 evidence items; the bulk
`ClinicalEvidenceSummaries` TSV is 4,903 rows and every one is `accepted`. That is a 2.35x difference
between two faces of one database, declared by neither. A snapshot has to be byte-reproducible from a
pinned input, and only the download side has dated releases (`01-Aug-2026/...`), so this builder reads
the TSV pair and records the basis explicitly. A figure from here is not comparable with a figure from
the API, and `release.json` says so.

**The direction axis is what CIViC has to offer here, and it is not `clin_sig`.** Measured over the
whole database, the germline subset carries five ACMG-tier calls and **zero** benign-class ones, so it
can never make a clinical-significance disagreement sayable. What it does carry is
`Predisposition`/`Protectiveness` crossed with `Supports`/`Does Not Support` — this format's
`direction` axis (`risk`/`protective`). See `docs/probes/CIVIC_SURVEY.md` for every number.

**"Does not support predisposition" is not "protective", and the null is the point.** A refutation
removes a claim; it does not establish the opposite one. So a `Does Not Support` row is kept, its raw
words preserved, and its derived `direction` left **null** — the house's three-valued rule, where an
unknown is withheld rather than negated. A drafter withholds those rows; it must not read them as
`protective`.

**Every drop is counted and the counts close.** The origin filter alone removes about three quarters
of the source, and a filter whose scope is narrower than its name is the defect this item was filed
against. So `input_rows == record_count + sum(dropped.values())` is asserted as an equality over a
walked registry (`@registry-completeness`), and every reason lands in `release.json`
(`@dont-discard-computed`).

**Identity comes from what CIViC publishes, never from a liftover.** Its coordinates are GRCh37 or
absent — never GRCh38 — but the variant file also carries rsIDs and, for some records, RefSeq `NC_`
accessions on both builds. An rsID is build-independent and resolves through the ordinary chain,
producing the independent second value `resolution._verify` cross-examines; a lifted coordinate would
be the row's sole identity with nothing to check it against, which is what RM48 refused. So a record
is kept when it carries an rsID or a GRCh38 accession, and dropped — counted — when it carries
neither. `allele_registry_id` rides along so the dropped class stays addressable later.

**Scoring an accession for build needs the per-chromosome map.** `NC_000001.11` is GRCh38 while
`NC_000002.11` is GRCh37: the version meaning "GRCh38" differs per chromosome. A first pass at this
tested for `".11"` or `".12"` and overcounted reachable records five-fold.

Builder-only: `polars` is a guarded `[dev]` import, exactly as in the sibling builders.
"""

import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from just_dna_format.normalize import now_utc_iso

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME

try:  # the one guarded optional import (CLAUDE.md): polars is builder-only ([dev] extra)
    import polars as pl
except ImportError:  # pragma: no cover - exercised only where the [dev] extra is absent
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

#: Where the dated releases live. `nightly` also serves, but a nightly cannot be pinned and a
#: snapshot that cannot name its input is a snapshot nothing can reproduce.
CIVIC_DOWNLOAD_BASE = "https://civicdb.org/downloads"

#: The two files a build needs. The evidence file carries the claims; the variant file carries the
#: identities, and neither is usable alone.
CIVIC_EVIDENCE_FILE = "ClinicalEvidenceSummaries.tsv"
CIVIC_VARIANT_FILE = "VariantSummaries.tsv"
#: The third file, and it earns its place: without it a profile that names two variants and a profile
#: that names none are indistinguishable, so a build could only report one blurred reason for two
#: different facts. Combination genotypes are a real class here — CIViC encodes them both as a
#: multi-variant profile and as a conjunction inside a single variant's own name.
CIVIC_PROFILE_FILE = "MolecularProfileSummaries.tsv"

CIVIC_PARQUET = "civic.parquet"

#: The build this snapshot emits. Recorded rather than implied — CIViC's own coordinates are GRCh37,
#: and every build confusion in this package began as a literal that read as decoration.
CIVIC_GENOME_BUILD = "GRCh38"

#: The status every row in the bulk file carries. Named because the API's default basis is a
#: different one and the two are not comparable.
CIVIC_BULK_STATUS = "accepted"

#: How a kept row's GRCh38 identity was established, so a consumer can exclude a class without
#: re-deriving why.
#:
#: `rsid`        — CIViC published an rs-number. Build-independent, and the route that lets ordinary
#:                 resolution verify the row against a source other than the one that supplied it.
#: `grch38_hgvs` — a GRCh38 RefSeq `NC_` accession in `hgvs_descriptions`, parsed to chrom/pos/ref/alt.
#: `both`        — an rsID *and* a parsed GRCh38 coordinate agreeing that this is one locus.
CIVIC_IDENTITY_DERIVATIONS: frozenset[str] = frozenset({"rsid", "grch38_hgvs", "both"})

#: Why a source evidence row produced no output row. Walked rather than restated, so
#: `input_rows == record_count + sum(dropped.values())` is an equality over it and a new reason
#: cannot be added without joining the sum (`@registry-completeness`).
CIVIC_DROP_REASONS: tuple[str, ...] = (
    # The big one, and the reason it is named first: CIViC is a somatic resource and roughly three
    # quarters of it describes tumour tissue no germline genotype can satisfy. Counted rather than
    # filtered silently, because a filter whose scope is narrower than its name is the defect this
    # snapshot was designed against.
    "non_germline_origin",
    # Germline, but the significance is not on the direction axis — therapy response, prognosis,
    # protein function, or an ACMG tier this snapshot deliberately does not carry.
    "not_direction_axis",
    # The profile names several variants, so it has no single-variant profile id to join on. A
    # conjunction of alterations is not one variant's annotation, and minting one identity for it
    # would assert a locus the source did not. Established from the profile file rather than inferred
    # from a failed join, which is what makes it distinguishable from the next reason.
    "combination_profile",
    # The profile names exactly one variant and that variant has no row in the variant file, or the
    # profile has no row in the profile file at all. A dangling reference inside the release, kept as
    # its own reason so it is never silently reported as a combination.
    "no_variant_record",
    # Neither an rsID nor a GRCh38 accession. The record is real and this snapshot cannot place it on
    # this format's build; `allele_registry_id` is carried in the release notice so the class stays
    # addressable rather than being quietly forgotten.
    "unresolvable_identity",
)

#: `(significance, evidence_direction)` → this format's `direction`, or `None` to withhold.
#:
#: **The withholds are load-bearing, not gaps.** "Does not support predisposition" refutes a risk
#: claim; it does not establish protectiveness, and writing `protective` there would be an unknown
#: recorded as a negative. The row is kept with its raw words and a null `direction`.
CIVIC_DIRECTION_MAP: dict[tuple[str, str], str | None] = {
    ("Predisposition", "Supports"): "risk",
    ("Protectiveness", "Supports"): "protective",
    ("Predisposition", "Does Not Support"): None,
    ("Protectiveness", "Does Not Support"): None,
}

#: The significances that put a row on the direction axis at all.
CIVIC_DIRECTION_SIGNIFICANCES: frozenset[str] = frozenset({"Predisposition", "Protectiveness"})

#: The origins a germline consumer can satisfy. `Unknown`/`N/A`/`Mixed`/`Combined` are excluded
#: deliberately: an origin the curator did not establish is not an origin we may assert.
CIVIC_GERMLINE_ORIGINS: frozenset[str] = frozenset({"Rare Germline", "Common Germline"})

#: RefSeq primary-assembly accessions, per chromosome, for the two builds. Domain constants, and the
#: whole reason they are written out is that the version number alone does not name a build.
_G37_ACCESSIONS: dict[str, str] = {
    f"NC_{i:06d}.{v}": c
    for i, v, c in zip(
        range(1, 25),
        (10, 11, 11, 11, 9, 11, 13, 10, 11, 10, 9, 11, 10, 8, 9, 9, 10, 9, 9, 10, 8, 10, 10, 9),
        [str(n) for n in range(1, 23)] + ["X", "Y"],
    )
}
_G38_ACCESSIONS: dict[str, str] = {
    f"NC_{i:06d}.{v}": c
    for i, v, c in zip(
        range(1, 25),
        (11, 12, 12, 12, 10, 12, 14, 11, 12, 11, 10, 12, 11, 9, 10, 10, 11, 10, 10, 11, 9, 11, 11, 10),
        [str(n) for n in range(1, 23)] + ["X", "Y"],
    )
}
assert not (_G37_ACCESSIONS.keys() & _G38_ACCESSIONS.keys()), (
    "an accession cannot name both builds; the per-chromosome map is wrong"
)

#: A simple substitution on a genomic accession: `NC_000002.12:g.29209798C>T`. Only substitutions are
#: parsed — a `del`/`dup`/`delins` needs the reference base the TSV does not carry, and guessing one
#: is how a wrong-allele row gets minted.
_HGVS_SUB_RE = re.compile(r"^(NC_\d{6}\.\d+):g\.(\d+)([ACGT]+)>([ACGT]+)$")
_RSID_RE = re.compile(r"^[Rr][Ss]\d+$")

#: Karyotype order for the emitted rows (deterministic; a parquet has no inherent order to recover).
_CHROM_ORDER: tuple[str, ...] = tuple([str(i) for i in range(1, 23)] + ["X", "Y", "MT"])
_CHROM_INDEX: dict[str, int] = {c: i for i, c in enumerate(_CHROM_ORDER)}


class CivicBuildError(RuntimeError):
    """The build cannot proceed: a missing input, an unreadable file, a column that is not there."""


class CivicUnavailable(CivicBuildError):
    """The release could not be fetched — a transport failure or a release that does not exist.

    A **subclass**, so `except CivicBuildError` keeps catching everything it did, while a caller that
    wants to distinguish "the source did not answer" from "the source answered something we cannot
    build" can (`@client-exception-contract`). The subclassing makes a caller's `except` order
    load-bearing, which is why it is stated here rather than left to be discovered.
    """


@dataclass(frozen=True)
class CivicDownload:
    """What a download established about one file's bytes — each half `None` when unstated."""

    path: Path
    sha256: str | None
    url: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class CivicBuildResult:
    """Outcome of a build: the paths, the counts kept, and every count dropped."""

    out_dir: Path
    parquet_file: Path
    #: Evidence rows read from the evidence TSV, before any filter.
    input_rows: int
    record_count: int
    #: Keyed by `CIVIC_DROP_REASONS`, every member present so a zero is a measured zero.
    dropped: dict[str, int] = field(default_factory=dict)
    #: `identity_derivation` → rows carrying it. Every member of `CIVIC_IDENTITY_DERIVATIONS` present.
    identity_derivations: dict[str, int] = field(default_factory=dict)
    #: Distinct CIViC variant ids in the output.
    variants: int = 0
    #: Rows whose derived `direction` is null because the source refuted a claim rather than making
    #: one. Counted separately from a drop: the row is kept, the axis value is withheld.
    withheld_direction: int = 0
    #: Variants carrying evidence in more than one direction camp — the multiplicity that matters.
    #: Never collapsed: choosing a winner is `mode()` over an unsorted group.
    contested_variants: int = 0
    #: Variants dropped for `unresolvable_identity` that nonetheless carry a ClinGen CAID, so a later
    #: identity pass knows how much it would recover.
    unresolvable_with_caid: int = 0
    #: `hgvs_descriptions` cells carrying a GRCh38 accession in a form the substitution parser cannot
    #: read (a del/dup/delins). Withheld rather than guessed at, and counted so "no GRCh38 accession"
    #: and "one we could not parse" stay distinguishable.
    unparsable_hgvs: int = 0
    evidence_sha256: str | None = None
    variant_sha256: str | None = None
    profile_sha256: str | None = None
    #: The dated release this was built from, e.g. `civic_01-Aug-2026`. `None` when the inputs came
    #: off local disk with no release named: an unknown release, never a fabricated one.
    dataset: str | None = None


def civic_release_url(release: str, filename: str) -> str:
    """The URL of one file in a dated release.

    CIViC's dated releases repeat the date in the filename (`01-Aug-2026/01-Aug-2026-<file>`), which
    is a shape a caller should not have to know.
    """
    return f"{CIVIC_DOWNLOAD_BASE}/{release}/{release}-{filename}"


def download_civic_file(dest: Path, url: str) -> CivicDownload:
    """Stream one release file to `dest` (atomic `.part` rename).

    Mirrors `pubmind_build.download_pubmind_table`, including keeping `ETag` and `Last-Modified`: a
    dated release should be immutable, and recording the headers is what would turn an upstream
    revision into a finding rather than a silent change of answer.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    hasher = hashlib.sha256()
    logger.info("Downloading %s ...", url)
    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
            response.raise_for_status()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    hasher.update(chunk)
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        # Translated rather than leaked: a caller of this package may not be made to depend on
        # httpx's exception tree to know that a fetch failed (`@client-exception-contract`).
        raise CivicUnavailable(f"could not download {url}: {exc}") from exc
    tmp.replace(dest)
    return CivicDownload(
        path=dest, sha256=hasher.hexdigest(), url=url, etag=etag, last_modified=last_modified
    )


def parse_rsids(aliases: str | None) -> list[str]:
    """The rs-numbers in a `variant_aliases` cell, lowercased, in source order without duplicates.

    CIViC's aliases are a comma-separated free-form list holding rs-numbers beside protein names and
    legacy labels, so the rs-numbers are selected by shape rather than by position.
    """
    seen: list[str] = []
    for token in re.split(r"[,\s]+", (aliases or "").strip()):
        if _RSID_RE.fullmatch(token) and token.lower() not in seen:
            seen.append(token.lower())
    return seen


def parse_grch38_substitution(hgvs: str | None) -> tuple[str, int, str, str] | None:
    """`(chrom, start, ref, alt)` from a GRCh38 genomic HGVS substitution, or `None`.

    `None` covers three different things on purpose — no accession, a GRCh37 accession, and a GRCh38
    accession in a form this parser does not read. The caller separates the third with
    `has_unparsable_grch38`, because "the source said nothing" and "the source said something we
    cannot hold" are different findings.
    """
    for token in re.split(r"[,\s]+", (hgvs or "").strip()):
        match = _HGVS_SUB_RE.match(token)
        if match is None:
            continue
        accession, position, ref, alt = match.groups()
        chrom = _G38_ACCESSIONS.get(accession)
        if chrom is not None:
            return chrom, int(position), ref, alt
    return None


def has_unparsable_grch38(hgvs: str | None) -> bool:
    """True when a GRCh38 accession is present but no substitution on it could be parsed."""
    if parse_grch38_substitution(hgvs) is not None:
        return False
    return any(
        token.split(":")[0] in _G38_ACCESSIONS
        for token in re.split(r"[,\s]+", (hgvs or "").strip())
        if ":" in token
    )


def _read_tsv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    """Every row of a CIViC TSV, with the columns a build depends on checked up front.

    Checked here rather than at first use, because a missing column is a build-shaped failure and
    discovering it halfway through leaves a partial parquet behind.
    """
    path = Path(path)
    if not path.exists():
        raise CivicBuildError(f"CIViC input not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = [c for c in required if c not in (reader.fieldnames or ())]
        if missing:
            raise CivicBuildError(
                f"{path.name} is missing the column(s) {missing}. CIViC changed its release layout, "
                f"and this builder must be re-probed against the new one rather than guessing."
            )
        return list(reader)


_EVIDENCE_COLUMNS: tuple[str, ...] = (
    "molecular_profile_id", "evidence_id", "evidence_type", "evidence_direction",
    "evidence_level", "significance", "citation_id", "source_type", "rating",
    "evidence_status", "variant_origin", "disease", "doid",
)
_PROFILE_COLUMNS: tuple[str, ...] = ("molecular_profile_id", "variant_ids")
_VARIANT_COLUMNS: tuple[str, ...] = (
    "variant_id", "single_variant_molecular_profile_id", "gene", "variant",
    "variant_aliases", "hgvs_descriptions", "allele_registry_id", "chromosome",
    "start", "reference_bases", "variant_bases", "reference_build",
)

#: Emitted column order. Fixed, because a rebuild must be byte-identical (Principle 7) and a parquet
#: written from a dict whose key order drifted is a different file for the same data.
CIVIC_COLUMNS: tuple[str, ...] = (
    "chrom", "start", "ref", "alt", "rsid", "allele_registry_id",
    "identity_derivation", "direction", "significance_raw", "evidence_direction_raw",
    "variant_id", "variant_name", "gene", "evidence_id", "molecular_profile_id",
    "evidence_level", "rating", "variant_origin", "pmid", "disease", "doid",
    "civic_grch37_chrom", "civic_grch37_start",
)


def build_snapshot(
    evidence_tsv: Path,
    variant_tsv: Path,
    profile_tsv: Path,
    out_dir: Path,
    *,
    release: str | None = None,
    evidence_sha256: str | None = None,
    variant_sha256: str | None = None,
    profile_sha256: str | None = None,
) -> CivicBuildResult:
    """Reduce the CIViC release pair to one parquet plus `release.json`.

    Rows are emitted sorted by `(chrom in karyotype order, start, ref, alt, variant_id, evidence_id)`,
    so a rebuild from the same release is byte-identical (Principle 7). Rows with no parsed GRCh38
    coordinate sort after the placed ones, by `variant_id` — a deterministic position rather than
    wherever the dict landed them.

    Every provenance argument defaults to `None` because only a caller that actually fetched can say
    where the bytes came from; a build off local disk records unknown rather than inventing a URL.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise CivicBuildError(
            "polars is required to build a snapshot; install the [dev] extra "
            "(`uv sync --extra dev`). Reading a built snapshot needs no such dependency."
        )
    evidence = _read_tsv(Path(evidence_tsv), _EVIDENCE_COLUMNS)
    variants = _read_tsv(Path(variant_tsv), _VARIANT_COLUMNS)
    profiles = _read_tsv(Path(profile_tsv), _PROFILE_COLUMNS)

    #: profile id → how many variants it names. A profile naming two is a combination genotype and
    #: is dropped as one; a profile this map has never heard of is a dangling reference.
    profile_arity: dict[str, int] = {
        (row.get("molecular_profile_id") or "").strip(): len(
            [v for v in re.split(r"[,\s]+", (row.get("variant_ids") or "").strip()) if v]
        )
        for row in profiles
    }
    by_profile: dict[str, dict[str, str]] = {
        row["single_variant_molecular_profile_id"]: row
        for row in variants
        if (row.get("single_variant_molecular_profile_id") or "").strip()
    }

    dropped = dict.fromkeys(CIVIC_DROP_REASONS, 0)
    identity_derivations = dict.fromkeys(sorted(CIVIC_IDENTITY_DERIVATIONS), 0)
    records: list[dict[str, object]] = []
    unparsable_hgvs = 0
    withheld_direction = 0
    unresolvable_caids: set[str] = set()

    for row in evidence:
        if row.get("variant_origin") not in CIVIC_GERMLINE_ORIGINS:
            dropped["non_germline_origin"] += 1
            continue
        significance = row.get("significance") or ""
        direction_raw = row.get("evidence_direction") or ""
        if (significance, direction_raw) not in CIVIC_DIRECTION_MAP:
            dropped["not_direction_axis"] += 1
            continue
        profile_id = (row.get("molecular_profile_id") or "").strip()
        variant = by_profile.get(profile_id)
        if variant is None:
            # The profile file is what separates these: a profile naming two or more variants is a
            # combination genotype, and anything else that fails to join is a dangling reference.
            # Inferring both from one failed join would report a real class and an integrity failure
            # under the same name.
            arity = profile_arity.get(profile_id, 0)
            dropped["combination_profile" if arity > 1 else "no_variant_record"] += 1
            continue

        rsids = parse_rsids(variant.get("variant_aliases"))
        coords = parse_grch38_substitution(variant.get("hgvs_descriptions"))
        if coords is None and has_unparsable_grch38(variant.get("hgvs_descriptions")):
            unparsable_hgvs += 1
        if not rsids and coords is None:
            dropped["unresolvable_identity"] += 1
            caid = (variant.get("allele_registry_id") or "").strip()
            if caid and caid != "unregistered":
                unresolvable_caids.add(caid)
            continue

        if rsids and coords is not None:
            derivation = "both"
        elif rsids:
            derivation = "rsid"
        else:
            derivation = "grch38_hgvs"
        identity_derivations[derivation] += 1

        direction = CIVIC_DIRECTION_MAP[(significance, direction_raw)]
        if direction is None:
            withheld_direction += 1

        chrom, start, ref, alt = coords if coords is not None else (None, None, None, None)
        caid = (variant.get("allele_registry_id") or "").strip()
        records.append(
            {
                "chrom": chrom,
                "start": start,
                "ref": ref,
                "alt": alt,
                "rsid": rsids[0] if rsids else None,
                "allele_registry_id": caid or None,
                "identity_derivation": derivation,
                "direction": direction,
                "significance_raw": significance,
                "evidence_direction_raw": direction_raw,
                "variant_id": int(variant["variant_id"]),
                "variant_name": variant.get("variant") or None,
                "gene": variant.get("gene") or None,
                "evidence_id": int(row["evidence_id"]),
                "molecular_profile_id": int(profile_id),
                "evidence_level": row.get("evidence_level") or None,
                "rating": int(row["rating"]) if (row.get("rating") or "").isdigit() else None,
                "variant_origin": row.get("variant_origin") or None,
                "pmid": _pmid(row),
                "disease": row.get("disease") or None,
                "doid": row.get("doid") or None,
                "civic_grch37_chrom": _grch37_chrom(variant),
                "civic_grch37_start": _grch37_start(variant),
            }
        )

    assert_registry_closes(len(evidence), len(records), dropped)

    records.sort(key=_sort_key)
    out_dir = Path(out_dir)
    data_dir = out_dir / SNAPSHOT_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    parquet_file = data_dir / CIVIC_PARQUET
    frame = pl.DataFrame(records, schema=_polars_schema()) if records else pl.DataFrame(
        schema=_polars_schema()
    )
    frame.write_parquet(parquet_file)

    camps: dict[int, set[str]] = {}
    for record in records:
        if record["direction"] is not None:
            camps.setdefault(int(record["variant_id"]), set()).add(str(record["direction"]))
    result = CivicBuildResult(
        out_dir=out_dir,
        parquet_file=parquet_file,
        input_rows=len(evidence),
        record_count=len(records),
        dropped=dropped,
        identity_derivations=identity_derivations,
        variants=len({int(r["variant_id"]) for r in records}),
        withheld_direction=withheld_direction,
        contested_variants=sum(1 for v in camps.values() if len(v) > 1),
        unresolvable_with_caid=len(unresolvable_caids),
        unparsable_hgvs=unparsable_hgvs,
        evidence_sha256=evidence_sha256,
        variant_sha256=variant_sha256,
        profile_sha256=profile_sha256,
        dataset=f"civic_{release}" if release else None,
    )
    _write_release_json(out_dir, result, release=release)
    return result


def assert_registry_closes(input_rows: int, kept: int, dropped: dict[str, int]) -> None:
    """Every input row is either kept or counted under a reason, and nothing falls between.

    An equality over the walked registry, never a floor (`@registry-completeness`). A filter added
    without a counter beside it would let the build truncate silently, and silent truncation reads as
    full coverage — which is the defect the whole drop registry exists to prevent.

    Its own function so it can be exercised directly: a test that has to contrive a broken build in
    order to reach a guard usually ends up proving something else instead.
    """
    total = sum(dropped.values())
    if input_rows != kept + total:
        raise CivicBuildError(
            f"the drop registry does not account for every input row: {input_rows} read, "
            f"{kept} kept, {total} dropped across {sorted(dropped)}. A row was filtered out without "
            f"a counter beside it (`@registry-completeness`)."
        )


def _pmid(row: dict[str, str]) -> str | None:
    """The PMID, only when the source really is PubMed.

    CIViC's `citation_id` is namespaced by `source_type` — an ASCO abstract id sits in the same
    column — so reading it unconditionally would file an abstract number as a PubMed id, which is
    the PMID/PMCID confusion in another costume (`@pmid-vs-pmcid`).
    """
    if (row.get("source_type") or "").strip().upper() != "PUBMED":
        return None
    return (row.get("citation_id") or "").strip() or None


def _grch37_chrom(variant: dict[str, str]) -> str | None:
    """CIViC's own chromosome, kept only where the record really is GRCh37 and complete.

    Recorded as provenance, never as identity: this snapshot's `chrom`/`start` are GRCh38. It is here
    so a later identity pass can see what the source actually held, and it is withheld whenever the
    coordinate is partial — a build stamp with no chromosome beside it is the malformed shape a
    provider must not treat as a position (`@identity-whole-or-none`).
    """
    if (variant.get("reference_build") or "").strip() != "GRCh37":
        return None
    chrom = (variant.get("chromosome") or "").strip()
    return chrom or None


def _grch37_start(variant: dict[str, str]) -> int | None:
    """CIViC's own 1-based position, withheld unless the chromosome is there to place it."""
    if _grch37_chrom(variant) is None:
        return None
    start = (variant.get("start") or "").strip()
    return int(start) if start.isdigit() else None


def _sort_key(record: dict[str, object]) -> tuple:
    """Karyotype order, then position, then the source's own ids.

    Unplaced rows (an rsID with no parsed coordinate) sort after every placed one rather than
    interleaving on a null, so the emitted order is total and a rebuild reproduces it exactly.
    """
    chrom = record["chrom"]
    return (
        0 if chrom is not None else 1,
        _CHROM_INDEX.get(str(chrom), len(_CHROM_ORDER)) if chrom is not None else 0,
        int(record["start"]) if record["start"] is not None else 0,
        str(record["ref"] or ""),
        str(record["alt"] or ""),
        int(record["variant_id"]),
        int(record["evidence_id"]),
    )


def _polars_schema() -> dict:
    """The emitted schema, spelled out so an all-null column cannot be inferred to the wrong type."""
    return {
        "chrom": pl.Utf8, "start": pl.Int64, "ref": pl.Utf8, "alt": pl.Utf8,
        "rsid": pl.Utf8, "allele_registry_id": pl.Utf8, "identity_derivation": pl.Utf8,
        "direction": pl.Utf8, "significance_raw": pl.Utf8, "evidence_direction_raw": pl.Utf8,
        "variant_id": pl.Int64, "variant_name": pl.Utf8, "gene": pl.Utf8,
        "evidence_id": pl.Int64, "molecular_profile_id": pl.Int64,
        "evidence_level": pl.Utf8, "rating": pl.Int64, "variant_origin": pl.Utf8,
        "pmid": pl.Utf8, "disease": pl.Utf8, "doid": pl.Utf8,
        "civic_grch37_chrom": pl.Utf8, "civic_grch37_start": pl.Int64,
    }


def _write_release_json(out_dir: Path, result: CivicBuildResult, *, release: str | None) -> Path:
    """Write `release.json` — the provenance, the status basis, and every count the build made."""
    payload = {
        "source": "civic",
        "release": release,
        "dataset": result.dataset,
        "evidence_sha256": result.evidence_sha256,
        "variant_sha256": result.variant_sha256,
        "profile_sha256": result.profile_sha256,
        "genome_build": CIVIC_GENOME_BUILD,
        "status_basis": CIVIC_BULK_STATUS,
        "input_rows": result.input_rows,
        "record_count": result.record_count,
        "dropped": result.dropped,
        "identity_derivations": result.identity_derivations,
        "variants": result.variants,
        "withheld_direction": result.withheld_direction,
        "contested_variants": result.contested_variants,
        "unresolvable_with_caid": result.unresolvable_with_caid,
        "unparsable_hgvs": result.unparsable_hgvs,
        "redistributable": True,
        "licence": "CC0-1.0",
        "notice": (
            "CIViC content is CC0 1.0 Universal, so this snapshot may be redistributed. It is built "
            "from the dated bulk TSV release, every row of which is status 'accepted' — the GraphQL "
            "API defaults to NON_REJECTED and serves roughly 2.35x as many evidence items, so a "
            "count here is not comparable with one taken from the API. Coordinates are GRCh38, "
            "derived from the RefSeq accessions CIViC publishes; CIViC's own coordinates are GRCh37 "
            "and are carried only as provenance. Nothing here may enter resolution.csv."
        ),
        "built_at": now_utc_iso(),
        "builder_version": _builder_version(),
    }
    path = out_dir / RELEASE_FILENAME
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _builder_version() -> str:
    try:
        return version("just-dna-enricher")
    except PackageNotFoundError:  # pragma: no cover - only if run from an uninstalled tree
        return "unknown"
