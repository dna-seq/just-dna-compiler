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

import collections
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

from just_dna_enricher.civic_vcf import (
    CIVIC_EVIDENCE_STATUSES,
    CIVIC_VCF_FILE,
    VCF_DERIVATION,
    CivicVcfEntry,
    assert_vocabulary_covers,
    read_vcf_entries,
    status_by_evidence,
    summarize,
)
from just_dna_enricher.civic_identities import (
    CIVIC_CURATION_STATES,
    CIVIC_NAME_IDENTITY_BY_VARIANT,
    CURATED_DERIVATION,
    CivicNameIdentity,
)
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_LICENSE_FILENAME,
)

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

#: The status every row in the bulk **TSV** carries. Named because the other published surfaces use a
#: different basis and the counts are not comparable across them.
CIVIC_BULK_STATUS = "accepted"

#: The basis a build actually emitted, recorded in `release.json` so a count is never read against the
#: wrong denominator. `accepted` is the TSV pair alone; `accepted+submitted` means the dated
#: `civic_accepted_and_submitted.vcf` was joined in as well (RM169).
CIVIC_STATUS_BASES: tuple[str, ...] = ("accepted", "accepted+submitted")

#: How a kept row's GRCh38 identity was established, so a consumer can exclude a class without
#: re-deriving why.
#:
#: `rsid`        — CIViC published an rs-number. Build-independent, and the route that lets ordinary
#:                 resolution verify the row against a source other than the one that supplied it.
#: `grch38_hgvs` — a GRCh38 RefSeq `NC_` accession in `hgvs_descriptions`, parsed to chrom/pos/ref/alt.
#: `both`        — an rsID *and* a parsed GRCh38 coordinate agreeing that this is one locus.
#: `caid`        — **neither**, but a ClinGen `allele_registry_id` that a later pass can resolve. The
#:                 row is kept with null `chrom`/`start`/`rsid`: it has a *route* to an identity rather
#:                 than an identity, and a drafter must not write it until something has walked that
#:                 route. Kept rather than dropped because dropping it here would make the recovery
#:                 invisible to every later pass — 99 of the 152 otherwise-unplaceable variants carry
#:                 one, and 64 of those resolve.
#: `curated_name` — CIViC published the identity in the variant's **name** and in none of its
#:                 identifier columns, and it was read out by hand. A distinct member rather than
#:                 folding into `rsid`/`grch38_hgvs`, because those two mean "the source stated this
#:                 in the column for it" and a consumer must be able to exclude the difference
#:                 without re-deriving it. See `civic_identities`.
#: `vcf_csq`     — the identity came from the VCF's `CSQ` block rather than from `VariantSummaries`,
#:                 because that file is `accepted`-only and does not describe the variant at all. The
#:                 routes inside are the same published identifiers (rs-number, GRCh38 accession,
#:                 ClinGen CAID) read by the same parsers; what differs is the *file*, and a consumer
#:                 must be able to exclude a provenance without re-deriving it (RM169).
CIVIC_IDENTITY_DERIVATIONS: frozenset[str] = frozenset(
    {"rsid", "grch38_hgvs", "both", "caid", CURATED_DERIVATION, VCF_DERIVATION}
)

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
    # No rsID, no GRCh38 accession **and** no ClinGen CAID. The record is real and nothing in this
    # release offers a route to a GRCh38 identity for it, so there is nothing a later pass could do
    # either. A CAID-bearing row is NOT dropped here — it is kept with `identity_derivation="caid"`.
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
        strict=True,
    )
}
_G38_ACCESSIONS: dict[str, str] = {
    f"NC_{i:06d}.{v}": c
    for i, v, c in zip(
        range(1, 25),
        (11, 12, 12, 12, 10, 12, 14, 11, 12, 11, 10, 12, 11, 9, 10, 10, 11, 10, 10, 11, 9, 11, 11, 10),
        [str(n) for n in range(1, 23)] + ["X", "Y"],
        strict=True,
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
    #: Submitted evidence items the VCF names on a variant the TSV does not describe. Outside the drop
    #: registry deliberately — those rows never entered the evidence list the registry's equality is
    #: over — and reported separately so the number is not lost (`@dont-discard-computed`).
    unjoinable_submitted: int = 0
    #: Emitted rows per `evidence_status`. Empty on the `accepted` basis, where the answer is the
    #: record count and a second number would only be able to disagree with it.
    status_counts: dict[str, int] = field(default_factory=dict)
    #: Which basis this build read: a member of `CIVIC_STATUS_BASES`. The single most important field
    #: in `release.json` for anyone comparing a count here with a count from anywhere else.
    status_basis: str = CIVIC_BULK_STATUS
    #: Evidence items the VCF holds per status, over the whole file rather than the direction slice —
    #: the denominator this build's own counts sit inside. Empty when no VCF was read.
    vcf_evidence: dict[str, int] = field(default_factory=dict)
    #: What became of each curated identity, keyed by `CIVIC_CURATION_STATES` with every member
    #: present. Counted per **variant**, not per row: the table is keyed by variant id, so a variant
    #: carrying three evidence rows is one application. The three sum to the table's length.
    curated_identities: dict[str, int] = field(default_factory=dict)
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
    #: Distinct ClinGen CAIDs on rows kept with `identity_derivation="caid"` — the size of the class a
    #: later identity pass would resolve, published so the recovery is a number rather than a guess.
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


def variant_rsids(variant: dict) -> list[str]:
    """Every rs-number CIViC states for one variant, name first, then aliases.

    **Two fields, because CIViC uses both and neither is the documented one.** The obvious place is
    `variant_aliases`, and a first version read only that — missing five variants in the germline
    direction set whose *name* is the rs-number itself (`RS2736100`, `rs681673`), sometimes with a
    protein alias beside it and sometimes with nothing. Those five needed no registry lookup and no
    conversion; the identity was published in plain sight, in the column a reader looks at first.

    Name before aliases, because the name is the source's own primary label for the variant while an
    alias is a synonym. Order only decides which is stored as `rsid`; both are parsed either way.
    """
    return parse_rsids(
        " , ".join(x for x in ((variant.get("variant") or ""), (variant.get("variant_aliases") or "")) if x)
    )


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
    "civic_grch37_chrom", "civic_grch37_start", "evidence_status",
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
    vcf: Path | None = None,
    vcf_sha256: str | None = None,
) -> CivicBuildResult:
    """Reduce the CIViC release pair to one parquet plus `release.json`.

    Rows are emitted sorted by `(chrom in karyotype order, start, ref, alt, variant_id, evidence_id)`,
    so a rebuild from the same release is byte-identical (Principle 7); `release.json`'s `built_at` is
    the only per-run-varying byte and lives outside the parquet, exactly as in `pubmind_build`. Rows
    with no parsed GRCh38 coordinate sort after the placed ones, by `variant_id` — a deterministic
    position rather than wherever the dict landed them.

    Every provenance argument defaults to `None` because only a caller that actually fetched can say
    where the bytes came from; a build off local disk records unknown rather than inventing a URL.

    **`vcf` widens the status basis and nothing else (RM169).** Given the dated
    `civic_accepted_and_submitted.vcf` from the same release, every emitted row gains the
    `evidence_status` CIViC assigned it, and the submitted evidence items join the corpus. The TSV pair
    stays primary and every row is still built from TSV columns — the VCF contributes *which* items
    exist and their status, never an identity: its POS is GRCh37 and lifting it is refused (RM48).
    Omitted, the build is exactly what it was, on the `accepted` basis.
    """
    if pl is None:  # pragma: no cover - exercised only where the [dev] extra is absent
        raise CivicBuildError(
            "polars is required to build a snapshot; install the [dev] extra "
            "(`uv sync --extra dev`). Reading a built snapshot needs no such dependency."
        )
    evidence = _read_tsv(Path(evidence_tsv), _EVIDENCE_COLUMNS)
    variants = _read_tsv(Path(variant_tsv), _VARIANT_COLUMNS)
    profiles = _read_tsv(Path(profile_tsv), _PROFILE_COLUMNS)

    # The VCF half. Read before the loop so `evidence` is one list by the time anything walks it: a
    # submitted row that took a different code path from an accepted one would be a second parser,
    # and the drop registry could not close over both.
    dropped = dict.fromkeys(CIVIC_DROP_REASONS, 0)
    doid_by_disease = _doid_by_disease(evidence)
    status_basis = CIVIC_BULK_STATUS
    unjoinable_submitted = 0
    evidence_statuses: dict[int, str] = {}
    vcf_statuses: dict[str, int] = {}
    if vcf is not None:
        entries = read_vcf_entries(Path(vcf))
        assert_vocabulary_covers(entries)
        evidence_statuses = status_by_evidence(entries)
        vcf_statuses = summarize(entries)
        status_basis = "accepted+submitted"
        by_variant_id = {
            (row.get("variant_id") or "").strip(): row
            for row in variants
            if (row.get("variant_id") or "").strip()
        }
        known = {int(row["evidence_id"]) for row in evidence if row["evidence_id"].isdigit()}
        for entry in entries:
            if entry.status != "submitted" or entry.evidence_id in known:
                continue
            variant = by_variant_id.get(str(entry.variant_id))
            if variant is None and (
                entry.allele_registry_id or entry.variant_aliases or entry.civic_hgvs
            ):
                # `VariantSummaries.tsv` is accepted-only too, so most submitted evidence names a
                # variant it does not describe. The same CSQ entry carries the four identity cells the
                # TSV would have supplied, so the row is built from those and stamped `vcf_csq`.
                variant = _variant_row_from_csq(entry)
                by_variant_id[str(entry.variant_id)] = variant
                variants.append(variant)
            if variant is None:
                # A submitted item on a variant the TSV does not describe: no gene, no aliases, no
                # identity route, nothing to build from. Counted here rather than in the main loop
                # because the row never enters `evidence`, and a drop the walking loop cannot see is a
                # drop the registry cannot close over.
                # NOT counted in `dropped`: the registry's equality is over the rows that entered
                # `evidence`, and this item never did. Counting it there would make the input total
                # disagree with the list the loop walks — the guard below catches exactly that, and
                # catching it is what says the two halves are one accounting rather than two.
                unjoinable_submitted += 1
                continue
            evidence.append(_submitted_evidence_row(entry, variant, doid_by_disease))

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

    identity_derivations = dict.fromkeys(sorted(CIVIC_IDENTITY_DERIVATIONS), 0)
    curated = _classify_curated(variants)
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

        rsids = variant_rsids(variant)
        coords = parse_grch38_substitution(variant.get("hgvs_descriptions"))
        if coords is None and has_unparsable_grch38(variant.get("hgvs_descriptions")):
            unparsable_hgvs += 1
        caid = (variant.get("allele_registry_id") or "").strip()
        caid = caid if caid and caid != "unregistered" else ""
        # The curated table is consulted only where the source itself says nothing, and only on an
        # exact name match. Both halves matter: `applied` below is the same predicate `_classify_
        # curated` counts with, so the registry closes, and a row CIViC has since filled never
        # reaches here at all.
        curated_row = _curated_for(variant) if not rsids and coords is None and not caid else None
        if not rsids and coords is None and not caid and curated_row is None:
            dropped["unresolvable_identity"] += 1
            continue

        if variant.get(_CSQ_SOURCED):
            # Stamped ahead of the published-identifier routes, and deliberately: those name *which*
            # identifier answered, while this names which **file** it was read from. For a variant the
            # TSV does not describe at all, the file is the fact a consumer cannot otherwise recover,
            # and the routes inside are visible in the row's own rsid/chrom/allele_registry_id cells.
            derivation = VCF_DERIVATION
        elif curated_row is not None:
            derivation = CURATED_DERIVATION
        elif rsids and coords is not None:
            derivation = "both"
        elif rsids:
            derivation = "rsid"
        elif coords is not None:
            derivation = "grch38_hgvs"
        else:
            derivation = "caid"
            unresolvable_caids.add(caid)
        identity_derivations[derivation] += 1

        direction = CIVIC_DIRECTION_MAP[(significance, direction_raw)]
        if direction is None:
            withheld_direction += 1

        if curated_row is not None:
            chrom, start, ref, alt = (
                curated_row.chrom, curated_row.start, curated_row.ref, curated_row.alt
            )
            rsids = [curated_row.rsid] if curated_row.rsid else rsids
        else:
            chrom, start, ref, alt = coords if coords is not None else (None, None, None, None)
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
                # CIViC's own curation status, verbatim. On the `accepted` basis every row carries
                # `accepted` from the TSV's own column; on the wider basis it is what separates a row
                # an editor signed off from one a curator entered. Never translated into a house
                # grade: it is the source's instrument and naming it is the point (RM169).
                "evidence_status": (row.get("evidence_status") or "").strip() or None,
            }
        )

    assert_registry_closes(len(evidence), len(records), dropped)
    assert_curation_closes(curated)

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
    status_counts = dict(collections.Counter(
        str(r["evidence_status"]) for r in records if r["evidence_status"] is not None
    ))
    result = CivicBuildResult(
        out_dir=out_dir,
        parquet_file=parquet_file,
        input_rows=len(evidence),
        record_count=len(records),
        dropped=dropped,
        identity_derivations=identity_derivations,
        status_counts=status_counts,
        unjoinable_submitted=unjoinable_submitted,
        status_basis=status_basis,
        vcf_evidence=vcf_statuses,
        curated_identities=curated,
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
    _write_license(out_dir)
    return result


#: Shipped beside the parquet because this snapshot is meant to be published, and a redistributed file
#: that does not carry its own terms makes the next reader go and establish them again. The text is
#: the dedication itself rather than a link: a URL is a promise about a page, and pages move.
CIVIC_LICENSE_TEXT = """CIViC (Clinical Interpretation of Variants in Cancer) — https://civicdb.org

The content of CIViC is released under the Creative Commons Public Domain Dedication
(CC0 1.0 Universal). https://creativecommons.org/publicdomain/zero/1.0/

To the extent possible under law, the person who associated CC0 with this work has waived all
copyright and related or neighboring rights to this work. The work is published from the United
States. No warranty is given.

CIViC requests, but does not require, attribution. Please cite:
  Griffith M, Spies NC, Krysiak K, et al. CIViC is a community knowledgebase for expert
  crowdsourcing the clinical interpretation of variants in cancer. Nat Genet. 2017;49(2):170-174.

NOTE ON THIS FILE'S SCOPE. CC0 covers CIViC's *content*. The MIT licence that appears beside it in
CIViC's own FAQ covers their application source code, which is not what this snapshot contains.

WHAT THIS SNAPSHOT IS. A derivation of one dated CIViC bulk release, not a copy of it: the germline
rows on the predisposition/protectiveness axis, placed on GRCh38 through identifiers CIViC itself
publishes. release.json records which release, and that every row is status 'accepted' — the CIViC
GraphQL API defaults to a wider basis and serves roughly 2.35x as many evidence items, so a count
taken from here is not comparable with one taken from there.
"""


def _write_license(out_dir: Path) -> Path:
    """Write the source's own terms beside the data, under the name every sibling snapshot uses."""
    path = Path(out_dir) / SNAPSHOT_LICENSE_FILENAME
    path.write_text(CIVIC_LICENSE_TEXT, encoding="utf-8")
    return path


#: Marks a variant row synthesised from the VCF's `CSQ` block. Private to this module and never a
#: parquet column — what reaches a consumer is `identity_derivation="vcf_csq"`, which is the same fact
#: in the vocabulary a consumer already reads.
_CSQ_SOURCED = "_civic_csq_sourced"


def _variant_row_from_csq(entry: CivicVcfEntry) -> dict[str, str]:
    """A `VariantSummaries` row, built from the `CSQ` cells, for a variant that file does not carry.

    Shaped like a TSV row rather than handled specially, for the same reason
    `_submitted_evidence_row` is: the identity routes downstream then run **unchanged**, so a CSQ-
    sourced variant is placed by the same `variant_rsids` / `parse_grch38_substitution` /
    `allele_registry_id` logic as any other, and nothing has to learn that two shapes exist.

    The coordinate columns are deliberately left empty. The VCF's own POS is GRCh37, `_grch37_chrom`
    would happily record it as provenance, and recording it here would put a coordinate on a row whose
    build stamp this file never states — `@identity-whole-or-none`, and RM48's refusal of a lifted
    coordinate as a row's sole identity. Everything these rows are placed by is build-independent or
    GRCh38-explicit.
    """
    return {
        "variant_id": str(entry.variant_id),
        # CIViC's own profile id, not a synthesised one: the evidence row built beside this carries
        # the same value, so the ordinary profile join links them and the parquet publishes the
        # source's identifier rather than this builder's invention.
        "single_variant_molecular_profile_id": entry.molecular_profile_id,
        "gene": entry.gene,
        "variant": entry.variant_name,
        "variant_aliases": entry.variant_aliases,
        "hgvs_descriptions": entry.civic_hgvs,
        "allele_registry_id": entry.allele_registry_id,
        "chromosome": "",
        "start": "",
        "reference_bases": "",
        "variant_bases": "",
        "reference_build": "",
        # The mark that makes the provenance recoverable at the emit site. A private key rather than a
        # published column: `_read_tsv` never produces it, so its presence means exactly "this row was
        # built from the VCF" and nothing else can set it.
        _CSQ_SOURCED: "1",
    }


def _doid_by_disease(evidence: list[dict[str, str]]) -> dict[str, str]:
    """`disease` label → DOID, learned from the accepted TSV.

    **The VCF carries a disease label and no ontology id**, while every row this snapshot emits today
    carries a DOID — so a submitted row would otherwise be the only kind with an empty `doid`, and a
    consumer filtering on the column would silently lose it. The mapping is *learned from the same
    release* rather than fetched: CIViC states the pairing on 4,878 accepted rows, and over
    `01-Aug-2026` all 298 labels map to exactly one DOID each, so there is nothing to adjudicate.

    A label the accepted rows never carry is left unmapped and its row gets a null `doid` — an unknown
    withheld rather than guessed, which is the house rule and is worth 3 rows on 2 labels here.
    """
    pairs: dict[str, set[str]] = {}
    for row in evidence:
        disease = (row.get("disease") or "").strip()
        doid = (row.get("doid") or "").strip()
        if disease and doid:
            pairs.setdefault(disease, set()).add(doid)
    # A label CIViC pairs with two ids is not a mapping and must not be used as one; dropping it
    # withholds rather than picking, and the count is small enough to name if it ever happens.
    ambiguous = sorted(label for label, ids in pairs.items() if len(ids) > 1)
    if ambiguous:
        logger.warning(
            "%d CIViC disease label(s) map to more than one DOID in this release and are left "
            "unmapped for submitted rows: %s",
            len(ambiguous),
            ", ".join(ambiguous[:5]),
        )
    return {label: next(iter(ids)) for label, ids in pairs.items() if len(ids) == 1}


def _submitted_evidence_row(
    entry: CivicVcfEntry, variant: dict[str, str], doid_by_disease: dict[str, str]
) -> dict[str, str]:
    """One VCF submitted evidence item, shaped exactly like a row of the evidence TSV.

    Shaped rather than special-cased on purpose: the row rejoins `evidence` before anything walks it,
    so a submitted row goes through the same origin filter, the same direction map, the same profile
    join and the same identity routes as an accepted one. One code path, one set of columns, and the
    drop registry closes over both bases without knowing there are two.
    """
    return {
        "molecular_profile_id": (variant.get("single_variant_molecular_profile_id") or "").strip(),
        "evidence_id": str(entry.evidence_id),
        "evidence_type": "Predisposing",
        "evidence_direction": entry.direction,
        "evidence_level": entry.evidence_level,
        "significance": entry.significance,
        "citation_id": entry.citation_id,
        "source_type": entry.source_type,
        "rating": entry.rating,
        "evidence_status": entry.status,
        "variant_origin": entry.variant_origin,
        "disease": entry.disease,
        "doid": doid_by_disease.get(entry.disease, ""),
    }


def _curated_for(variant: dict[str, str]) -> CivicNameIdentity | None:
    """The curated identity for this variant, or `None` — matched on the id **and** the exact name.

    The name guard is the whole safety property (`civic_identities`): a curated answer was an answer
    to a name, so it must not outlive it. Matched verbatim rather than normalized, because a curator
    editing `N150fs (c.448delA)` into anything at all is a signal that the record moved.
    """
    row = CIVIC_NAME_IDENTITY_BY_VARIANT.get(int(variant["variant_id"]))
    if row is None or (variant.get("variant") or "") != row.name:
        return None
    return row


def _curated_superseded(variant: dict[str, str]) -> bool:
    """True when CIViC now publishes an identity of its own for this variant.

    The source always outranks the curated table, so this is checked before a curated row is used.
    Derived from the same three parsers the build places rows with, never restated beside them.
    """
    return bool(
        variant_rsids(variant)
        or parse_grch38_substitution(variant.get("hgvs_descriptions"))
        or ((variant.get("allele_registry_id") or "").strip() not in ("", "unregistered"))
    )


def _classify_curated(variants: list[dict[str, str]]) -> dict[str, int]:
    """Every curated row's state in this release, keyed by `CIVIC_CURATION_STATES`.

    Walked over the table rather than counted as placements happen, because the interesting states
    are the two where **nothing** is placed: a curated row CIViC has since filled in for itself, and
    one whose variant or name has gone. Counting only applications would report those two as the same
    zero (`@unreachable-not-absent`).
    """
    by_id = {
        int(v["variant_id"]): v for v in variants if (v.get("variant_id") or "").strip().isdigit()
    }
    states = dict.fromkeys(CIVIC_CURATION_STATES, 0)
    for row in CIVIC_NAME_IDENTITY_BY_VARIANT.values():
        variant = by_id.get(row.variant_id)
        if variant is None:
            states["absent"] += 1
        elif (variant.get("variant") or "") != row.name:
            states["renamed"] += 1
        else:
            states["superseded" if _curated_superseded(variant) else "applied"] += 1
    return states


def assert_curation_closes(states: dict[str, int]) -> None:
    """Each curated row landed in exactly one state, and the states account for the whole table.

    The same equality-over-a-walked-set the drop registry gets (`@registry-completeness`). A build
    that quietly stopped consulting the table would otherwise look identical to one where every row
    happened to be superseded.
    """
    total = sum(states.values())
    if total != len(CIVIC_NAME_IDENTITY_BY_VARIANT):
        raise CivicBuildError(
            f"the curated identity table does not close: {len(CIVIC_NAME_IDENTITY_BY_VARIANT)} rows, "
            f"{total} accounted for across {sorted(states)} (`@registry-completeness`)."
        )


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
        "evidence_status": pl.Utf8,
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
        "status_basis": result.status_basis,
        "status_counts": result.status_counts,
        "unjoinable_submitted": result.unjoinable_submitted,
        "vcf_evidence": result.vcf_evidence,
        "input_rows": result.input_rows,
        "record_count": result.record_count,
        "dropped": result.dropped,
        "identity_derivations": result.identity_derivations,
        "curated_identities": result.curated_identities,
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
            "and are carried only as provenance. Rows marked identity_derivation='curated_name' "
            "are placed from an identity CIViC states in the variant's name and in none of its "
            "identifier columns, read out by hand: the procedure is docs/probes/"
            "CIVIC_IDENTITY_PROTOCOL.md and the per-variant evidence docs/probes/"
            "CIVIC_UNRESOLVED.md. Nothing here may enter resolution.csv."
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
