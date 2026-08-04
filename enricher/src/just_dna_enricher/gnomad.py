"""Live gnomAD v4.1 queries — the third source in the network tier, and the first *rate-limited* one.

One GraphQL endpoint serves all three roles gnomAD plays here:

* `resolve_rsids`         — the resolver-chain link (rsID → loci), appended after live Ensembl;
* `fetch_frequencies`     — the frequency pass (coordinate → per-ancestry-group AC/AN);
* `fetch_gene_constraint` — the gene pass's live fallback (symbol → pLI/LOEUF/Z scores).

**Rate limiting is the design constraint, not an afterthought.** gnomAD allows 10 requests per IP per
60 seconds, so one request per variant is unusable — a forty-variant module would take four minutes.
Everything here is therefore *batched*: GraphQL field aliasing puts many `variant(...)` lookups in one
POST. Probed live, batches of 20 and 25 both succeeded while 29 returned HTTP 400, so the batch size is
**20** with a **6 second** pacing gate — one request per 6s is exactly the 10/minute budget, and about
200 variants/minute.

Pacing comes *before* retry on purpose. `tenacity` retries transport errors, timeouts and 429s, but a
blind retry spends the same budget that caused the 429; the gate is what keeps us inside the limit, and
the retry is only for the genuinely transient case.

**Partial failures are normal and must not sink a batch.** GraphQL reports per-alias failures in
`errors[]` while still returning `data` for every alias that worked — a probed 20-alias batch came back
`resolved=17, errors=3`. Treating a non-empty `errors[]` as total failure would discard 17 good rows, so
every parser here reads both halves.

The query shapes and field names were checked against the live schema by introspection rather than
recalled: `variant(variantId:|rsid:|vrsId:, dataset:)`, `variant_search(query:, dataset:)`,
`gene(gene_symbol:, reference_genome:)`, and a `VariantPopulation` that carries `ac`/`an` but
deliberately **no `af`** — the frequency is ours to compute.
"""

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from just_dna_format.vocab import normalize_population, population_sort_key
from just_dna_format.vrs import in_pseudoautosomal_region, normalize_chrom

from just_dna_enricher.net import PacingGate, batched, dedupe

logger = logging.getLogger(__name__)

DEFAULT_GNOMAD_ENDPOINT = "https://gnomad.broadinstitute.org/api"
# The v4 dataset id the GraphQL API expects (a `DatasetId` enum literal, so it is interpolated
# unquoted), and the frequency subset we read. `joint` combines the exome and genome callsets — the
# widest denominator, and what the gnomAD browser shows by default, so a curator comparing our number
# against the website sees the same one.
DEFAULT_DATASET = "gnomad_r4"
DEFAULT_FREQUENCY_SET = "joint"
# The `dataset` FACT stamped onto every emitted row: the release the numbers describe, not the API we
# happened to call. A v4.1 count and a v2.1.1 count are different facts, so this is inside the fact set.
FREQUENCY_DATASET_LABEL = "gnomad_v4.1_joint"
# The two constraint routes serve DIFFERENT RELEASES, so they get different labels. This was checked,
# not assumed, and it is the opposite of what the plan expected: the plan wanted a test asserting the
# snapshot and the live API agree for BRCA1 within float tolerance. They do not, and they should not.
#
#   BRCA1   bulk v4.1 TSV: pLI 1.55e-34, LOEUF 0.885, mis_z 2.338
#           live API     : pLI 5.52e-38, LOEUF 0.928, mis_z 1.734
#   MYH7    bulk v4.1 TSV: LOEUF 0.644, mis_z 6.806
#           live API     : LOEUF 0.662, mis_z 7.379
#
# Same gene, same MANE transcript (ENST00000357654 for BRCA1) — so this is not a transcript-pick
# difference. The live `gnomad_constraint` field serves **v2.1.1** constraint (0.93 and 0.66 are the
# widely-cited v2.1.1 LOEUFs for these two genes); v4.1 constraint ships only in the bulk file. Since
# `dataset` is inside `GENE_METRICS_FACT_FIELDS` precisely so a v4.1 number and a v2.1.1 number cannot
# be confused, labelling API rows as v4.1 would record a false fact — and would make the fact-hash
# claim two tables identical when they hold different numbers.
CONSTRAINT_DATASET_LABEL = "gnomad_v4.1_constraint"
API_CONSTRAINT_DATASET_LABEL = "gnomad_v2.1.1_constraint"

# The exact message gnomAD returns for an rsID mapping to more than one variant — matched to trigger
# the `variant_search` fallback. Any other message is a genuine failure for that alias.
_MULTIPLE_VARIANTS_RE = re.compile(r"multiple variants found", re.IGNORECASE)
# Sex-stratified population ids (`XX`, `XY`, `nfe_XX`, ...). Sex is a second axis, orthogonal to
# ancestry group (Principle 5), so this pass drops them rather than folding them into `population`.
_SEX_SUFFIX_RE = re.compile(r"(^|_)(XX|XY)$")
# A gnomAD variantId is `chrom-pos-ref-alt`.
_VARIANT_ID_RE = re.compile(r"^(?P<chrom>[^-]+)-(?P<pos>\d+)-(?P<ref>[A-Za-z]+)-(?P<alt>[A-Za-z]+)$")


def covers_locus(
    chrom: Optional[str], start: Optional[int], *, build: str = "GRCh38"
) -> Optional[bool]:
    """Is this locus inside gnomAD's callset at all? **Three-valued**, and `None` means "cannot say".

    gnomAD excludes the **Y pseudoautosomal region**: like a standard GRCh38 analysis set it hard-masks
    the Y PAR, because those bases are a duplicate of the X PAR and reads there cannot be placed. Probed
    live 2026-08-04 — `region(chrom:"X", 640000-641500)` serves **880** variants and the identical
    interval on Y serves **none**, while a single-variant lookup for `Y-640851-C-T` returns
    `Variant not found` where `X-640851-C-T` resolves.

    That matters because "the source has no such allele" and "the source does not look here" are
    different answers, and only the first is a fact. Without this, the one-to-many expansion of a PAR
    rsID handed the frequency pass a Y locus, gnomAD said nothing, and the pass recorded `not_found` —
    an absence nobody established. Three-valued so an unknown build withholds rather than asserting
    coverage it cannot vouch for (PAR intervals are per-assembly — RM15).

    **This is a source convention and it lives here, in the network tier.** The PAR *geometry* is an
    assembly constant and belongs to the format tier (`vrs.in_pseudoautosomal_region`); "gnomAD masks
    it" is a fact about gnomAD, and Principle 2 makes the enricher the only tier permitted to hold one.
    """
    if build != "GRCh38":
        return None
    in_par = in_pseudoautosomal_region(chrom, start, build=build)
    if normalize_chrom(chrom) == "Y" and in_par is True:
        return False
    return True


class GnomadError(RuntimeError):
    """A gnomAD query failed outright (transport, HTTP status, or a malformed response body)."""


class RateLimitedError(GnomadError):
    """gnomAD answered HTTP 429. Retried with backoff; the pacing gate should normally prevent it."""


@dataclass
class GnomadSettings:
    endpoint: str = DEFAULT_GNOMAD_ENDPOINT
    dataset: str = DEFAULT_DATASET
    frequency_set: str = DEFAULT_FREQUENCY_SET
    reference_genome: str = "GRCh38"
    #: Aliases per POST. 20 is inside the probed ceiling (25 worked; 29 was rejected with HTTP 400).
    batch_size: int = 20
    #: Seconds between requests — 6.0 is exactly gnomAD's stated 10-per-60s budget.
    min_request_interval: float = 6.0
    timeout: float = 30.0


def _alias(index: int) -> str:
    """A GraphQL-legal alias for batch slot `index`. Positional, so mapping a response back is index
    arithmetic rather than string surgery on ids that may contain any character (`11-5227002-T-A` is
    not a legal alias, and neither is a gene symbol with a hyphen)."""
    return f"v{index}"


def _gql_string(value: str) -> str:
    """Escape a Python string into a GraphQL string literal.

    These are rsIDs, variant ids and gene symbols from a spec file — not free-form user input — but a
    stray quote or backslash would silently corrupt the *whole batch* (every alias in it), so escaping
    is cheap insurance against one bad cell taking twenty good lookups down with it.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _errors_by_alias(payload: dict) -> tuple[dict[str, str], list[str]]:
    """Split GraphQL `errors[]` into per-alias failures and whole-request failures.

    An error carries a `path` whose first element is the alias that failed; one with no usable path is
    a whole-request problem (a syntax error, an unknown field) rather than one lookup missing. Telling
    those apart is what lets a batch keep its 17 good rows while reporting its 3 bad ones — and what
    stops a genuinely broken query from being mistaken for "nothing found".
    """
    by_alias: dict[str, str] = {}
    fatal: list[str] = []
    for err in payload.get("errors") or []:
        path = err.get("path") or []
        message = str(err.get("message", "unknown error"))
        if path:
            by_alias[str(path[0])] = message
        else:
            fatal.append(message)
    return by_alias, fatal


def _loci_from_variant_ids(variant_ids: Iterable[str]) -> list[dict]:
    """Fold `chrom-pos-ref-alt` ids into the resolver's locus shape, one entry per (chrom,pos,ref).

    Alts at one locus are aggregated into a sorted comma-joined cell, matching what the Ensembl and
    ClinVar links produce — so `enrich()` treats every link's output identically. Loci are sorted by
    `(chrom, start, ref)`, the same explicit ordering the DuckDB links pin with `ORDER BY` (P7).
    """
    grouped: dict[tuple[str, int, str], set[str]] = {}
    for variant_id in variant_ids:
        match = _VARIANT_ID_RE.match(variant_id.strip())
        if match is None:
            logger.warning("gnomAD returned an unparseable variant id %r; skipping", variant_id)
            continue
        key = (match["chrom"], int(match["pos"]), match["ref"].upper())
        grouped.setdefault(key, set()).add(match["alt"].upper())
    return [
        {"chrom": chrom, "start": start, "ref": ref, "alts": ",".join(sorted(alts))}
        for (chrom, start, ref), alts in sorted(grouped.items())
    ]


def _populations_from_joint(joint: dict) -> list[dict]:
    """Reduce a `joint` block to one deterministic row per ancestry group.

    Three things the raw payload does that this undoes, all probed on `11-5227002-T-A`:

    - it carries **sex splits** (`nfe_XX`, `XY`) beside ancestry groups — a second axis, dropped here;
    - it lists `XX`/`XY` **twice** — so a naive pass would double-count;
    - it names the whole-dataset row with a **bare empty id** — mapped to `global`.

    Server order is not preserved: it is not promised and the emitted table must be byte-stable
    (Principle 7), so `population_sort_key` imposes the canonical order instead.
    """
    rows: dict[str, dict] = {}
    for entry in joint.get("populations") or []:
        raw_id = str(entry.get("id") or "")
        if _SEX_SUFFIX_RE.search(raw_id):
            continue
        population = normalize_population(raw_id)
        if population in rows:  # the duplicated-entry case; first occurrence wins
            continue
        rows[population] = {
            "population": population,
            "allele_count": entry.get("ac"),
            "allele_number": entry.get("an"),
            "homozygote_count": entry.get("homozygote_count"),
            "hemizygote_count": entry.get("hemizygote_count"),
        }
    # The whole-dataset row: gnomAD usually supplies it as the bare-id entry, but fall back to the
    # top-level joint counts so `global` is never missing (a consumer's denominator of first resort).
    if "global" not in rows and joint.get("an") is not None:
        rows["global"] = {
            "population": "global",
            "allele_count": joint.get("ac"),
            "allele_number": joint.get("an"),
            "homozygote_count": joint.get("homozygote_count"),
            "hemizygote_count": joint.get("hemizygote_count"),
        }
    # faf95 is ONE value with a named owning group, so it lands on that group's row and stays null
    # everywhere else — no extra column, no field meaning different things on different rows.
    faf95 = joint.get("faf95") or {}
    owner = normalize_population(str(faf95.get("popmax_population") or "")) if faf95 else None
    if owner and owner in rows and faf95.get("popmax") is not None:
        rows[owner]["faf95"] = faf95.get("popmax")
    return sorted(rows.values(), key=lambda r: population_sort_key(r["population"]))


@dataclass
class GnomadClient:
    """Batched, paced gnomAD GraphQL client. Reused across a pass, so one gate covers every request."""

    settings: GnomadSettings = field(default_factory=GnomadSettings)
    gate: Optional[PacingGate] = None
    _client: Optional[httpx.Client] = None

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = PacingGate(self.settings.min_request_interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "GnomadClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── transport ──────────────────────────────────────────────────────────────────────────────
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=2.0, max=30.0),
        retry=retry_if_exception_type(
            (RateLimitedError, httpx.TransportError, httpx.TimeoutException)
        ),
        reraise=True,
    )
    def _post(self, query: str) -> dict:
        """POST one (possibly many-aliased) query, paced and retried. Returns the parsed body.

        A 429 is retried with backoff *on top of* the pacing gate — the gate is what should normally
        prevent it, so one getting through means the server is stricter than advertised or another
        process shares this IP, and backing off is the only correct response. A 4xx that is not 429 is
        not retried: a malformed query does not get better by being asked again.
        """
        assert self.gate is not None
        self.gate.wait()
        try:
            response = self._http().post(self.settings.endpoint, json={"query": query})
        except httpx.HTTPError as exc:
            if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
                raise
            raise GnomadError(f"gnomAD request failed: {exc}") from exc
        if response.status_code == 429:
            raise RateLimitedError("gnomAD returned HTTP 429 (rate limited)")
        response.raise_for_status()
        return response.json()

    def _post_batch(self, fields: list[str], *, what: str) -> tuple[dict[str, Any], dict[str, str]]:
        """Run one aliased batch, returning `(data, per-alias errors)`.

        The per-alias errors are handed back rather than swallowed because they are *data* to the
        caller: `resolve_rsids` reads them to spot the "Multiple variants found" case and reroute those
        rsIDs through `variant_search`. A whole-request error (no alias path) IS raised — that is a bug
        in our query, not a missing record, and returning "nothing found" would hide it behind an
        innocent-looking empty table.
        """
        payload = self._post("{\n" + "\n".join(fields) + "\n}")
        by_alias, fatal = _errors_by_alias(payload)
        if fatal:
            raise GnomadError(f"gnomAD {what} query failed: {'; '.join(fatal)}")
        if by_alias:
            logger.info(
                "gnomAD %s: %d/%d aliases returned an error (partial results kept)",
                what, len(by_alias), len(fields),
            )
        return payload.get("data") or {}, by_alias

    # ── role 1: the resolver-chain link ────────────────────────────────────────────────────────
    def resolve_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        """`rsid -> [{chrom, start, ref, alts}, ...]`, shaped exactly like the cache links' output.

        A **multi-allelic rsID cannot be looked up by rsID**: gnomAD answers `rs334` with "Multiple
        variants found, query using variant ID to select one." rather than a record. That is not an
        error to swallow — `rs334` is sickle-cell, a variant a module is very likely to carry — so those
        rsIDs are collected and retried through `variant_search`, which does return every matching
        variant id, and the alleles are aggregated into one locus. An rsID that returns nothing at all
        is simply absent from the result (the caller falls through to "not found").
        """
        wanted = dedupe(r for r in rsids if r)
        if not wanted:
            return {}
        out: dict[str, list[dict]] = {}
        ambiguous: list[str] = []
        for batch in batched(wanted, self.settings.batch_size):
            fields = [
                f"{_alias(i)}: variant(rsid: {_gql_string(rsid)}, dataset: {self.settings.dataset}) "
                f"{{ variant_id }}"
                for i, rsid in enumerate(batch)
            ]
            data, errors = self._post_batch(fields, what="rsid resolution")
            for i, rsid in enumerate(batch):
                alias = _alias(i)
                if _MULTIPLE_VARIANTS_RE.search(errors.get(alias, "")):
                    ambiguous.append(rsid)
                    continue
                node = data.get(alias)
                if node and node.get("variant_id"):
                    out[rsid] = _loci_from_variant_ids([node["variant_id"]])
        for batch in batched(ambiguous, self.settings.batch_size):
            fields = [
                f"{_alias(i)}: variant_search(query: {_gql_string(rsid)}, "
                f"dataset: {self.settings.dataset}) {{ variant_id }}"
                for i, rsid in enumerate(batch)
            ]
            data, _ = self._post_batch(fields, what="rsid search")
            for i, rsid in enumerate(batch):
                hits = data.get(_alias(i)) or []
                ids = [h.get("variant_id") for h in hits if h.get("variant_id")]
                if ids:
                    out[rsid] = _loci_from_variant_ids(ids)
        return out

    # ── role 2: the frequency pass ─────────────────────────────────────────────────────────────
    def fetch_frequencies(self, variant_ids: list[str]) -> dict[str, dict]:
        """`variantId -> {populations: [...], caid, vrs_id}` for already-resolved coordinates.

        The multi-allelic-rsID problem does not arise here: this pass keys on `chrom-pos-ref-alt`,
        which names exactly one allele. Each population entry carries AC/AN — never a frequency, which
        the API does not expose per group and which we compute from the counts instead.
        """
        wanted = dedupe(v for v in variant_ids if v)
        if not wanted:
            return {}
        subset = self.settings.frequency_set
        out: dict[str, dict] = {}
        for batch in batched(wanted, self.settings.batch_size):
            fields = [
                f"{_alias(i)}: variant(variantId: {_gql_string(vid)}, dataset: {self.settings.dataset}) "
                f"{{ variant_id caid rsids vrs {{ _id }} "
                f"{subset} {{ ac an homozygote_count hemizygote_count "
                f"faf95 {{ popmax popmax_population }} "
                f"populations {{ id ac an homozygote_count hemizygote_count }} }} }}"
                for i, vid in enumerate(batch)
            ]
            data, _ = self._post_batch(fields, what="frequency")
            for i, vid in enumerate(batch):
                node = data.get(_alias(i))
                if not node:
                    continue
                joint = node.get(subset) or {}
                rsids = node.get("rsids") or []
                out[vid] = {
                    "populations": _populations_from_joint(joint),
                    "caid": node.get("caid"),
                    "vrs_id": (node.get("vrs") or {}).get("_id"),
                    # One rsID only when gnomAD reports exactly one: several means the id is
                    # position-level over multiple alleles, and picking one would mis-attribute it.
                    "rsid": rsids[0] if len(rsids) == 1 else None,
                }
        return out

    # ── role 3: the gene pass's live fallback ──────────────────────────────────────────────────
    def fetch_gene_constraint(self, symbols: list[str]) -> dict[str, dict]:
        """`gene symbol -> constraint metrics dict` (empty entry omitted).

        A module has tens of genes at most, so this is one or two batched requests — which is why the
        gene pass can fall back to the live API without the rate limit mattering, while the frequency
        pass cannot go the other way and ship an offline snapshot.
        """
        wanted = dedupe(s for s in symbols if s)
        if not wanted:
            return {}
        out: dict[str, dict] = {}
        for batch in batched(wanted, self.settings.batch_size):
            fields = [
                f"{_alias(i)}: gene(gene_symbol: {_gql_string(symbol)}, "
                f"reference_genome: {self.settings.reference_genome}) "
                f"{{ gene_id symbol mane_select_transcript {{ ensembl_id }} "
                f"gnomad_constraint {{ pli oe_lof oe_lof_lower oe_lof_upper oe_mis "
                f"lof_z mis_z syn_z obs_lof exp_lof flags }} }}"
                for i, symbol in enumerate(batch)
            ]
            data, _ = self._post_batch(fields, what="gene constraint")
            for i, symbol in enumerate(batch):
                node = data.get(_alias(i))
                if not node:
                    continue
                constraint = node.get("gnomad_constraint")
                if not constraint:
                    continue
                mane = node.get("mane_select_transcript") or {}
                flags = constraint.get("flags") or []
                out[symbol] = {
                    "gene": node.get("symbol") or symbol,
                    "gene_id": node.get("gene_id"),
                    "transcript": mane.get("ensembl_id"),
                    # The live route returns the gene's MANE Select transcript alongside its
                    # constraint, so when both are present the metrics are the MANE ones by
                    # construction — unlike the bulk TSV, where the row has to be picked.
                    "mane_select": bool(mane.get("ensembl_id")) or None,
                    "pli": constraint.get("pli"),
                    "loeuf": constraint.get("oe_lof_upper"),
                    "oe_lof": constraint.get("oe_lof"),
                    "oe_lof_lower": constraint.get("oe_lof_lower"),
                    "lof_z": constraint.get("lof_z"),
                    "mis_z": constraint.get("mis_z"),
                    "syn_z": constraint.get("syn_z"),
                    "oe_mis": constraint.get("oe_mis"),
                    "obs_lof": constraint.get("obs_lof"),
                    "exp_lof": constraint.get("exp_lof"),
                    "constraint_flags": "|".join(sorted(flags)) if flags else None,
                }
        return out
