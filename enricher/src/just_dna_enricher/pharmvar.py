"""Live PharmVar queries — star-allele definitions and allele function (0.5).

PharmVar is the naming authority for the CYP star alleles, and the only PGx source here that is not
part of the ClinPGx merger. It supplies two things this workspace has no other route to:
`haplotypes.csv` material (which variants define `*2`) and `allele_function.csv` material (what that
allele does), both with GRCh38 genomic coordinates and dbSNP ids already attached.

**Access changed under us and the failure mode is silent.** The API now requires a key, and every
endpoint returns the same `401 {"errorMessage": "API Key is invalid or missing"}` whether the key is
absent, malformed, or passed under the wrong parameter name — so a wrong header looks exactly like a
bad key. The parameter is **`Api-Key`**, a plain header with no `X-` prefix, documented per-endpoint
in the service's own OpenAPI document (`docs/vendor/pharmvar_api_docs.json`) rather than in a
`securityDefinitions` block, which is why it is easy to miss.

**The key is personal.** PharmVar's terms §2 make an account non-transferable, so the key is read
from the environment and never written anywhere: not into a module, a recorded fixture, a log line,
or a snapshot. `PharmVarClient` keeps it in the header only.

**Rate limit: 2 requests/second.** Low enough that per-allele fetching is hopeless and coarse
endpoints are the only sane shape — `/variants/gene/{symbol}` returns a gene's whole variant set in
one call. The unfiltered `/alleles` collection is ~25 MB and ignores a `geneSymbol` query parameter it
does not define, so it is never used here; `reference-sequence` filtering is applied server-side
instead.

Coordinates arrive as HGVS `g.` strings against several reference sequences at once — a transcript
(`NM_…:c.`), a gene region (`NG_…:g.`) and the chromosome (`NC_…:g.`). Only the `NC_` form is a
genomic coordinate, and it is **1-based**, which matches what this pipeline already stores (see the
resolution table): the instinctive conversion to 0-based would introduce an off-by-one.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME, load_env
from just_dna_enricher.net import PacingGate, attempt_floor

logger = logging.getLogger(__name__)

DEFAULT_PHARMVAR_ENDPOINT = "https://www.pharmvar.org/api-service"
# The documented header name. Not `X-API-KEY` — that returns the same 401 as no key at all.
API_KEY_HEADER = "Api-Key"
API_KEY_ENV = "PHARMVAR_API_KEY"
# 2 requests/second, so 0.5s between them. Injectable clock, as everywhere in this package.
PHARMVAR_MIN_INTERVAL = 0.5
# The `dataset` FACT: which release the definitions came from. PharmVar publishes a version per gene
# rather than one global release id, so the pass stamps what the payload reports.
PHARMVAR_SOURCE = "pharmvar"

# `NC_000010.11:g.94781859G>A` → chromosome accession, 1-based position, ref, alt. Only the NC_ form
# is genomic; NM_/NG_ are transcript- and gene-relative and are deliberately not parsed as positions.
_NC_HGVS = re.compile(
    r"^(?P<accession>NC_(?P<num>\d+)\.\d+):g\.(?P<pos>\d+)(?P<ref>[ACGT]+)>(?P<alt>[ACGT]+)$"
)

#: The assembly this pipeline stores, and the only one a coordinate is taken from here.
#:
#: **PharmVar publishes each variant against BOTH assemblies, and lists GRCh37 first.** Every
#: defining variant appears once per reference sequence — `NM_` transcript, `NG_` gene region, and
#: **two** `NC_` chromosome rows, one GRCh37 and one GRCh38 — and `_merge_variants` keeps the first row
#: it sees for an rsID. Probed against the live `/genes` payload (15 genes, 1,173 core alleles, 12,925
#: variant rows): **451 of the 739 rsID-keyed defining variants would come back carrying a GRCh37
#: coordinate**, e.g. DPYD rs868235016 as chr1:97547910 (GRCh37) rather than its GRCh38 position.
#:
#: The accession *version* cannot separate them — chr10 is `NC_000010.10`/`.11` while chr22 is
#: `NC_000022.10`/`.11`, so `.10` appears under both assemblies — but `referenceCollections` says
#: which, exactly (`["GRCh37"]` × 1,995, `["GRCh38"]` × 2,004, and nothing else on an `NC_` row).
#: A row that does not say GRCh38 yields **no position**, rather than a guessed one: it still carries
#: the rsID, so the merge keeps the identity and loses only the coordinate we could not place.
#:
#: This was latent until RM38 — nothing consumed `PharmVarAllele.variants` — and a snapshot stores
#: them, which is what turns a latent wrong number into a written one. Third build confusion in this
#: workspace, hence a named constant rather than a literal (`gnomad.FREQUENCY_GENOME_BUILD` is the
#: precedent).
PHARMVAR_GENOME_BUILD = "GRCh38"


class PharmVarError(RuntimeError):
    """A PharmVar request failed in a way the caller must see (auth, or a broken query)."""


def chrom_from_accession(num: str) -> str | None:
    """`NC_000010` → `10`, `NC_000023` → `X`. None for anything off the primary assembly.

    RefSeq numbers the chromosomes 1–22 then X (23), Y (24), MT (12920 as a special case). Returning
    None rather than guessing keeps an unplaced contig out of the coordinate space entirely.
    """
    index = int(num)
    if 1 <= index <= 22:
        return str(index)
    return {23: "X", 24: "Y"}.get(index)


@dataclass
class PharmVarVariant:
    """One defining variant of a star allele, at a genomic coordinate."""

    rsid: str | None
    chrom: str | None
    start: int | None
    ref: str | None
    alt: str | None

    @property
    def usable(self) -> bool:
        """Whether this carries a genomic coordinate we can key on."""
        return self.chrom is not None and self.start is not None


@dataclass
class PharmVarAllele:
    """One star allele: its identity, its function, and the variants that define it."""

    gene: str
    allele: str
    function: str | None = None
    activity_value: float | None = None
    evidence_level: str | None = None
    is_core: bool = True
    variants: list[PharmVarVariant] = field(default_factory=list)


def parse_genomic_variant(
    payload: dict[str, Any], *, build: str = PHARMVAR_GENOME_BUILD
) -> PharmVarVariant:
    """One `variants[]` entry → a coordinate, when it names one **on `build`**.

    A variant appears several times per allele, once per reference sequence. Only the `NC_` genomic
    row yields a position; the transcript rows still carry the rsID, so the caller merges by rsID
    rather than discarding them.

    And only the `NC_` row whose `referenceCollections` names `build` does — PharmVar publishes both
    assemblies and lists GRCh37 first, so accepting any `NC_` row stores the wrong coordinate for most
    variants. See `PHARMVAR_GENOME_BUILD`.
    """
    rsid = payload.get("rsId") or None
    match = _NC_HGVS.match(str(payload.get("hgvs") or payload.get("position") or ""))
    collections = payload.get("referenceCollections") or []
    if match is None or build not in collections:
        return PharmVarVariant(rsid=rsid, chrom=None, start=None, ref=None, alt=None)
    return PharmVarVariant(
        rsid=rsid,
        chrom=chrom_from_accession(match.group("num")),
        # 1-based, matching Ensembl and what resolution.csv stores. Do NOT subtract one.
        start=int(match.group("pos")),
        ref=match.group("ref"),
        alt=match.group("alt"),
    )


def _merge_variants(
    entries: list[dict[str, Any]], *, build: str = PHARMVAR_GENOME_BUILD
) -> list[PharmVarVariant]:
    """Collapse an allele's per-reference-sequence rows to one entry per variant.

    Keyed by rsID where there is one, else by the coordinate; a row carrying a `build` coordinate
    supersedes a positionless one for the same variant, so the merged entry has both the id and the
    position. That supersede rule is what makes the assembly filter safe: the GRCh37 row now yields no
    position, so the GRCh38 row wins wherever both exist, whichever order they arrive in.
    First-occurrence order is preserved — emitted order feeds `artifact.digest` (Principle 7).

    A row with neither an rsID nor a coordinate is dropped rather than merged. It has nothing to
    identify it, and every such row keyed to the same `None:None:None` string, so they collapsed into
    one blank entry that named no variant at all.
    """
    merged: dict[str, PharmVarVariant] = {}
    for entry in entries:
        parsed = parse_genomic_variant(entry, build=build)
        if parsed.rsid is None and not parsed.usable:
            continue
        key = parsed.rsid or f"{parsed.chrom}:{parsed.start}:{parsed.ref}"
        existing = merged.get(key)
        if existing is None or (not existing.usable and parsed.usable):
            merged[key] = parsed
    return list(merged.values())


def parse_allele(payload: dict[str, Any], *, build: str = PHARMVAR_GENOME_BUILD) -> PharmVarAllele:
    """One `/alleles` entry → a `PharmVarAllele`.

    `activityScore` is absent for most alleles and non-numeric for some ("n/a"), so it is parsed
    defensively rather than trusted — a non-numeric score becomes None instead of failing the allele.
    """
    raw_score = payload.get("activityScore")
    try:
        activity = float(raw_score) if raw_score not in (None, "", "n/a") else None
    except (TypeError, ValueError):
        activity = None
    return PharmVarAllele(
        gene=str(payload.get("geneSymbol") or ""),
        allele=str(payload.get("alleleName") or ""),
        function=payload.get("function") or None,
        activity_value=activity,
        evidence_level=payload.get("evidenceLevel") or None,
        is_core=(payload.get("alleleType") or "").lower() != "sub",
        variants=_merge_variants(list(payload.get("variants") or []), build=build),
    )


class PharmVarClient:
    """Paced PharmVar REST client. The API key comes from the environment and is never persisted."""

    def __init__(
        self,
        endpoint: str = DEFAULT_PHARMVAR_ENDPOINT,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        gate: PacingGate | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        # `.env` is where a developer actually keeps this key, and until now it only reached
        # `os.environ` as a side effect of some *other* call resolving a cache path. That worked for
        # `enrich_pgx` by accident and not at all for the snapshot builder, which resolves nothing —
        # `pharmvar build` reported "no PharmVar API key" on a machine that had one in `.env`. Loading
        # it where the key is read makes the credential path independent of unrelated calls.
        # `override=False`, so a real environment variable and a test's neutralizing `""` both win.
        load_env()
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        self._client = client or httpx.Client(timeout=timeout)
        self._owned = client is None
        self._gate = gate or PacingGate(interval=PHARMVAR_MIN_INTERVAL)

    @property
    def configured(self) -> bool:
        """Whether a key is available. Absent is a *skip*, not an error — the pass degrades."""
        return bool(self._api_key)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def _request(self, path: str, params: dict[str, str] | None = None) -> Any:
        # Pace before retry, as in gnomad.py: retrying spends the same budget that caused the throttle.
        self._gate.wait()
        response = self._client.get(
            f"{self.endpoint}/{path.lstrip('/')}",
            params=params or {},
            headers={API_KEY_HEADER: self._api_key or ""},
        )
        if response.status_code == 401:
            # Do not retry an auth failure, and never echo the key. The message names the two causes
            # the service cannot distinguish, because its 401 is identical for both.
            raise PharmVarError(
                "PharmVar rejected the API key (HTTP 401). The service returns the same response for "
                f"an absent, malformed and unrecognised key; check that {API_KEY_ENV} is set to a "
                f"verified key and that it is sent as the {API_KEY_HEADER!r} header."
            )
        response.raise_for_status()
        return response.json()

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """`PharmVarError` for every way this client can fail — the CPIC repair, symmetrically.

        R2-13 named only `CpicClient`, and the hole is identical here: `raise_for_status()` was
        called and nothing wrapped it, so a persistent PharmVar 5xx escaped as
        `httpx.HTTPStatusError` past `enrich_pgx`'s `(PharmVarError, CpicError)` handler and sank
        CPIC's answer. Fixing one leg and not the other would leave the comment above that handler
        — *"One source failing must not sink the pass"* — true in one direction only, which is worse
        than either state: the guarantee would hold or not depending on which source went down.

        The 401 branch inside `_request` stays where it is. It is a *diagnosis* raised before the
        status check, not a translation of one, and it must not be retried.
        """
        try:
            return self._request(path, params)
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
            raise PharmVarError(f"PharmVar {path} could not be read: {exc}") from exc

    def alleles_for_gene(self, gene: str, *, include_sub_alleles: bool = False) -> list[PharmVarAllele]:
        """Every allele PharmVar defines for one gene, with its defining variants.

        Sub-alleles (`*2.001`) are excluded by default: the core star is the identity this workspace
        keys on (`AlleleFunctionRow.allele`), and including them multiplies the table roughly threefold
        without changing any lookup.
        """
        payload = self._get(
            f"genes/{gene}",
            params={"exclude-sub-alleles": "true"} if not include_sub_alleles else {},
        )
        raw = payload.get("alleles") if isinstance(payload, dict) else payload
        alleles = [parse_allele(entry) for entry in (raw or [])]
        if not include_sub_alleles:
            alleles = [a for a in alleles if a.is_core]
        return alleles

    def all_genes(self, *, include_sub_alleles: bool = False) -> dict[str, list[PharmVarAllele]]:
        """Every gene PharmVar defines, with its alleles — **one request** for the whole database.

        `/genes` returns the same shape as `/genes/{symbol}` for all fifteen genes at once (1,173 core
        alleles, ~5 MB), which at 2 rps is the difference between one call and fifteen. That matters
        only for the snapshot builder, which is its only caller; the runtime passes stay gene-scoped
        because a module's own tables say which genes it is about.
        """
        payload = self._get(
            "genes", params={"exclude-sub-alleles": "true"} if not include_sub_alleles else {},
        )
        entries = payload if isinstance(payload, list) else [payload]
        out: dict[str, list[PharmVarAllele]] = {}
        for entry in entries:
            symbol = str(entry.get("geneSymbol") or "")
            if not symbol:
                continue
            alleles = [parse_allele(a) for a in (entry.get("alleles") or [])]
            if not include_sub_alleles:
                alleles = [a for a in alleles if a.is_core]
            out[symbol] = alleles
        return out


class PharmVarSnapshotClient:
    """`alleles_for_gene` answered from an **operator-built** snapshot (RM38).

    Duck-typed against `PharmVarClient` so `enrich_pgx` needs no branch, and `configured` is True
    because the question it answers — "can this leg run?" — is about reachability, not about a key. A
    snapshot exists or it does not, and `locations.resolve_pharmvar_reference` already decided that
    before this is constructed.

    There is no `all_genes` here: that endpoint exists to *build* a snapshot, and a snapshot does not
    build itself. Read with duckdb (core) rather than polars (`[dev]`, builder-only).
    """

    def __init__(self, reference: Path) -> None:
        self.reference = Path(reference)
        data_dir = self.reference / SNAPSHOT_DATA_DIRNAME
        if not (data_dir / "alleles.parquet").is_file():
            raise PharmVarError(
                f"no PharmVar snapshot at {data_dir} — build one with "
                f"`just-dna-enricher pharmvar build` (it needs your own PHARMVAR_API_KEY; the "
                f"snapshot is never published, see the terms §2 note)"
            )
        self._data_dir = data_dir
        release_path = self.reference / RELEASE_FILENAME
        self.release: dict[str, Any] = (
            json.loads(release_path.read_text()) if release_path.is_file() else {}
        )

    @property
    def configured(self) -> bool:
        """True: a resolved snapshot is the credential's stand-in, and it is already in hand."""
        return True

    @property
    def dataset(self) -> str | None:
        """Which snapshot answered, for `SourceRow.dataset`."""
        return self.release.get("dataset")

    @property
    def genome_build(self) -> str:
        """The assembly the stored coordinates are on. Recorded by the builder, never assumed."""
        return self.release.get("genome_build") or PHARMVAR_GENOME_BUILD

    def close(self) -> None:
        """No-op, so a caller can `close()` this and a live client identically."""

    def _query(self, sql: str, params: list[Any]) -> list[dict]:
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(sql, params)
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            con.close()

    def alleles_for_gene(self, gene: str, *, include_sub_alleles: bool = False) -> list[PharmVarAllele]:
        """Every allele the snapshot holds for one gene, with its defining variants.

        `include_sub_alleles` is accepted for signature parity and cannot be honoured: the builder
        fetches core alleles only, so asking for sub-alleles here would be answered with a subset while
        looking like a full answer. It raises instead — a wrong answer that looks right is the one
        outcome worth refusing.
        """
        if include_sub_alleles:
            raise PharmVarError(
                "the PharmVar snapshot holds core alleles only; sub-alleles need the live API. "
                "Rebuild with --sub-alleles, or run this leg online."
            )
        alleles_path = str(self._data_dir / "alleles.parquet").replace("'", "''")
        variants_path = str(self._data_dir / "variants.parquet").replace("'", "''")
        rows = self._query(
            f"SELECT gene, allele, function, activity_value, evidence_level "
            f"FROM read_parquet('{alleles_path}') WHERE gene = ? ORDER BY allele",
            [gene],
        )
        variants = self._query(
            f"SELECT allele, rsid, chrom, start, ref, alt FROM read_parquet('{variants_path}') "
            f"WHERE gene = ? ORDER BY allele, variant_index",
            [gene],
        )
        by_allele: dict[str, list[PharmVarVariant]] = {}
        for v in variants:
            by_allele.setdefault(v["allele"], []).append(
                PharmVarVariant(
                    rsid=v["rsid"], chrom=v["chrom"], start=v["start"], ref=v["ref"], alt=v["alt"]
                )
            )
        return [
            PharmVarAllele(
                gene=r["gene"],
                allele=r["allele"],
                function=r["function"],
                activity_value=r["activity_value"],
                evidence_level=r["evidence_level"],
                is_core=True,
                variants=by_allele.get(r["allele"], []),
            )
            for r in rows
        ]
