"""LitVar2/PubTator3 — which papers name this allele, and **at which tier** (RM167).

NCBI's LitVar2 indexes the biomedical literature by variant, and it does so at three tiers that sit
beside each other as separate nodes. A node id is `litvar@<clingen_id>#<rsid>#<gene_id>` with an
unfilled slot collapsing to a bare `#`, so `litvar@rs1800562##` is the **position** node — rsID slot
filled, allele slot empty — and `litvar@CA113795#rs1800562##` is the **allele** node beside it, named
by a ClinGen canonical allele id. A gene carries one gene-level node (`litvar@#3077#`) as well, and
a long tail of `litvar@#<gene_id>#<protein_name>` **text mentions**, which are an unnormalized string
a miner saw rather than an identity. Nothing here treats a mention as a variant.

**The tier a locus is answerable at is a property of the locus, not of the source**, and that is the
whole finding this pass exists to make. Measured 2026-09-01: BRAF rs113488022 carries 32,095 papers on
its position node and three allele nodes (31,276 / 99 / 41) whose three ALTs at one codon differ by
three orders of magnitude, leaving 801 papers (2.5 %) position-only. APOE rs429358 carries 3,945 on
the position node and **328** on its single allele node, so **92 % of the literature at that locus is
not allele-resolved**. A pass that reported the allele node's count as *the* answer would understate
APOE twelvefold, and one that quietly substituted the position count would answer an allele-level
question with a position-level fact. So the answer names its tier: **allele-resolved, position-only
and absent are three outcomes**, and for once the source supplies the three states rather than the
schema imposing them (`@refutation-withholds`).

**What this does NOT answer, and the bound is not a footnote.** LitVar tells you which papers discuss
an allele *that is already identified*. It does not tell you which allele a name meant. Those read as
the same question and are not. Asked of the two records this workspace could not resolve — CIViC 1955
`VHL P71fs (c.211insT)` and 2131 `VHL Q73fs (c.214insGCCC)`, worked down by hand to four candidate
alleles with registered CAIDs — LitVar returns **no node for any of the four**, no node for
`c.211insT` / `211insT` / `c.214insGCCC`, and for `VHL P71fs` exactly one node,
`litvar@#7428#p.P71fsX` with **1 PMID: 19996202**, which is none of the four source papers but an
unrelated paper that happens to write "P71fs" (`@existence-not-identity`). The reason is structural
rather than incidental: PubTator3's export for all four source papers returns title and abstract only,
two passages with **zero variant annotations** in every one, none of them in the PMC open-access
subset. The alleles live in Table 3 of a paywalled 1996–2007 paper, and text mining over abstracts
cannot reach a table. On precisely the class this workspace built an identity protocol for — a source
that names a variant without identifying it, in old literature — **LitVar is the wrong instrument.**

**Terms are NCBI's policy, and a policy is not a licence.** NCBI states it *"places no restrictions on
the use or distribution"* of molecular data and, in the same passage, that it *"cannot provide comment
or unrestricted permission concerning the use, copying, or distribution"* because submitters may hold
rights it cannot assess. ClinVar escapes this through its own `maintenance_use` page, which is why
`CLINVAR_TERMS` records `public-domain`; **LitVar has no such page**, so under `@no-named-licence` its
gating axes are unknown rather than permissive, and recording it as public domain by analogy with
ClinVar is exactly the move that rule forbids. This is **NCBI's side only** — nothing was read about
EMBL-EBI's terms for surfaces EBI co-hosts, and nothing here asserts anything about them.

**No `SourceRow` is written, and that is the rule rather than an omission** (`@write-the-sourcerow`,
its converse). `sources.csv` travels to the registry meaning *this module uses this source*, and this
pass contributes no cell to any table: it compares, it reports, and it writes nothing but an
attestation. `identifiers.py` is the precedent — it consults HGNC and OLS4 for the same kind of
read-only verdict and writes no row either — while `civic_draft.py`, which *does* put registry-derived
values into a module, writes its `clingen_allele_registry` row. The source is named on the
`VerificationRecord` instead, which is where a check's provenance belongs.

**One real API defect, pinned before anyone writes a second client.** `variant/search/gene/GENE`
returns **line-delimited Python `repr()`, not JSON** — single-quoted keys, one dict per line. `httpx`'s
`.json()` raises on it. The other endpoints return proper JSON. `parse_repr_lines` below is a literal
parser (`ast.literal_eval`), never `eval` (`@probe-the-real-file`).
"""

import ast
import json
import logging
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from just_dna_compiler.compiler import load_csv_rows
from just_dna_compiler.draft import DRAFTABLE
from just_dna_format.alleles import split_genotype
from just_dna_format.base import AuthoredModel
from just_dna_format.layout import SidecarCollision, resolve_sidecar
from just_dna_format.manifest import VerificationRecord
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import MULTI_SEP
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.clingen_allele import ClingenAlleleClient, anchor_indel
from just_dna_enricher.licensing import overlaid_input_rows
from just_dna_enricher.net import PacingGate, attempt_floor, dedupe
from just_dna_enricher.verification import examples, ran, skipped

logger = logging.getLogger(__name__)

#: The LitVar2 API root. The service is mounted under `/research/`, and the *other* base a reader is
#: likely to try (`/research/bionlp/litvar/api/v1/`) is a different, older URL space whose paths do
#: not match these; recorded here because two hours went into finding that out.
LITVAR_API_BASE = "https://www.ncbi.nlm.nih.gov/research/litvar2-api"

#: The name this pass records on its `VerificationRecord`. Not a `licensing.TERMS_BY_SOURCE` member —
#: see the module docstring: nothing here reaches a module's tables, so nothing here writes a
#: `SourceRow`, and a terms constant no pass hands to `record_source_terms` would be a registry member
#: nothing writes (`@registry-completeness`).
LITVAR_SOURCE = "litvar"

#: The injected table this pass also reads, for the `alts` and `caid` RM153 records there. Spelled the
#: way every other reader in this tier spells it.
RESOLUTION_CSV = "resolution.csv"

#: NCBI asks for no more than three requests a second without an API key. A third of a second is that
#: budget with a little air in it, and it is what a 388-locus corpus sweep ran at without a refusal.
_REQUEST_INTERVAL = 0.34

#: The prefix LitVar puts on the body of a 400 that means *there is no such node*. A 400 is an
#: **answer** here, the way Ensembl's 400 on an unresolvable rsID is (`@unreachable-not-absent`) — but
#: a malformed query is also a 400, so the discriminator is the body and never the status.
_NOT_FOUND_DETAIL = "Variant not found"

#: What tier one LitVar node sits at. Closed (Principle 6). `mention` is the fifth id shape — an
#: unnormalized protein string under a gene id, with no rsID and no CAID — and it is deliberately a
#: member rather than being filtered away at the parser: a caller listing a gene's nodes must be able
#: to see how much of the tail is text rather than identity.
VALID_LITVAR_NODE_TIER: frozenset[str] = frozenset({"clingen", "rsid", "gene", "mention"})

#: What tier a locus was **answered** at. The three the source supplies, plus the one the house
#: algebra always adds: a question that could not be put is not an absence.
VALID_COVERAGE_TIER: frozenset[str] = frozenset({"allele", "position", "absent", "unchecked"})

#: Why a locus landed on its tier. **One arm per way of getting there, pairwise distinct**
#: (`@answered-is-not-absent`): a verdict function with several arms owes a reason function with the
#: same arms, or a reader gets one sentence for two different situations. `coverage_reason` below is
#: the twin, and a test walks this set and asserts the sentences differ.
VALID_COVERAGE_REASON: frozenset[str] = frozenset(
    {
        # tier == "allele"
        "allele_node_matched",
        # tier == "position"
        "row_names_no_allele",
        "no_allele_node_at_locus",
        "allele_nodes_name_other_alleles",
        # tier == "absent"
        "no_node_for_rsid",
        # tier == "unchecked"
        "offline",
        "index_unreachable",
        "registry_unreachable",
        "allele_not_comparable",
    }
)

#: `reason` → the tier it can appear under. Derived from here rather than restated at each call site,
#: and asserted as an equality over `VALID_COVERAGE_REASON` by a test.
COVERAGE_REASON_TIER: dict[str, str] = {
    "allele_node_matched": "allele",
    "row_names_no_allele": "position",
    "no_allele_node_at_locus": "position",
    "allele_nodes_name_other_alleles": "position",
    "no_node_for_rsid": "absent",
    "offline": "unchecked",
    "index_unreachable": "unchecked",
    "registry_unreachable": "unchecked",
    "allele_not_comparable": "unchecked",
}


class LitvarError(RuntimeError):
    """LitVar could not be consulted in a way the caller must handle."""


class LitvarUnavailable(LitvarError):
    """The service was not reachable, so the question was never put (RM101's shape).

    A subclass rather than a second exception: every existing `except LitvarError` still fires, and a
    caller that needs to separate *the index said no* from *the index never answered* can, without
    reading `__cause__`. Only this one means nobody was asked.
    """


def parse_repr_lines(text: str) -> list[dict]:
    """One dict per line of a Python `repr()` payload, which is what `search/gene` really serves.

    `ast.literal_eval` is a **literal parser**, not `eval`: it walks the parsed syntax tree and refuses
    anything that is not a literal container, so it cannot call, import or execute. Calling `.json()`
    on this payload raises, and calling `eval` on it would be a remote-code path.

    A line that will not parse is a defect in the response rather than in one record, so it raises;
    silently dropping it would make a short answer indistinguishable from a complete one.
    """
    rows: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = ast.literal_eval(stripped)
        except (ValueError, SyntaxError) as exc:
            raise LitvarError(
                f"line {number} of the gene search response is not a Python literal ({exc})"
            ) from exc
        if not isinstance(value, dict):
            raise LitvarError(f"line {number} of the gene search response is not a dict")
        rows.append(value)
    return rows


def node_tier(record: dict) -> str:
    """Which tier a node record sits at, from whichever evidence the endpoint supplied.

    The `flag_rsid_variant` / `flag_clingen_variant` / `flag_gene_variant` booleans say it directly and
    are present on `autocomplete` and `get` — but `search/gene` omits all three, carrying only the
    keys a record has. So both routes are read, flags first: an id is parsed only where nothing states
    the answer, because parsing an id is exactly how the first pass at this got it wrong.
    """
    if record.get("flag_clingen_variant"):
        return "clingen"
    if record.get("flag_rsid_variant"):
        return "rsid"
    if record.get("flag_gene_variant"):
        return "gene"
    if record.get("clingen_id"):
        return "clingen"
    if record.get("rsid"):
        return "rsid"
    # Everything left is `litvar@#<gene_id>#…`. The gene node leaves the last slot empty; anything in
    # it is a protein string a miner normalized nothing about.
    return "gene" if str(record.get("_id", "")).endswith("#") else "mention"


@dataclass(frozen=True)
class LitvarNode:
    """One node in the index, at one tier."""

    node_id: str
    tier: str
    rsid: str | None = None
    clingen_id: str | None = None
    name: str | None = None
    genes: tuple[str, ...] = ()
    #: What the *listing* said this node holds. `None` where the endpoint did not say; never a zero,
    #: because "the endpoint does not carry this field" and "no papers" are different facts.
    pmid_count: int | None = None

    @classmethod
    def parse(cls, record: dict) -> "LitvarNode":
        genes = record.get("gene") or []
        count = record.get("pmids_count")
        return cls(
            node_id=str(record["_id"]),
            tier=node_tier(record),
            rsid=record.get("rsid") or None,
            clingen_id=record.get("clingen_id") or None,
            name=record.get("name") or None,
            genes=tuple(str(g) for g in genes) if isinstance(genes, list) else (),
            pmid_count=int(count) if isinstance(count, int) else None,
        )


class LitvarClient:
    """The four LitVar2 calls this lane needs, paced, retried and translated.

    **Node ids are never constructed from the grammar.** Every id this client hands to `get` or
    `publications` came back from `autocomplete` or `search/gene` verbatim. The first attempt at this
    source read the trailing `##` of `litvar@rs1800562##` as a suffix on the rsID, concluded there was
    no allele tier, and was wrong about the whole source on the strength of one misread character; an
    id that is only ever echoed cannot reproduce that.
    """

    def __init__(
        self,
        *,
        base: str = LITVAR_API_BASE,
        client: httpx.Client | None = None,
        gate: PacingGate | None = None,
    ) -> None:
        self._base = base.rstrip("/")
        self._client = client
        self._gate = gate or PacingGate(_REQUEST_INTERVAL)
        # Per-run, per-client: a locus reached from two tables must not be two requests, and a
        # module-level cache would make two callers in one process share state they never agreed on.
        self._nodes: dict[str, list[LitvarNode]] = {}
        self._details: dict[str, dict] = {}
        self._pmids: dict[str, frozenset[int]] = {}

    # ── the four calls ──────────────────────────────────────────────────────────────────────────

    def autocomplete(self, query: str) -> list[LitvarNode]:
        """Every node whose id, rsID or synonyms match `query`, at whatever tier each sits.

        **The match is a prefix search, so the caller must filter.** `?query=rs429358` returns
        `rs42935848` as a second hit — a real node for a different variant whose number begins with
        the one asked about. `position_node` and `allele_node` below are that filter; nothing should
        take `[0]` off this list.
        """
        key = query.strip()
        if key not in self._nodes:
            status, body = self._request(f"/variant/autocomplete/?query={urllib.parse.quote(key)}")
            self._nodes[key] = [] if status is None else [
                LitvarNode.parse(record) for record in _as_list(body)
            ]
        return list(self._nodes[key])

    def node(self, node_id: str) -> dict | None:
        """The node's own record — `clingen_ids` lives here and nowhere else — or `None` if absent."""
        if node_id not in self._details:
            status, body = self._request(f"/variant/get/{urllib.parse.quote(node_id, safe='')}")
            self._details[node_id] = {} if status is None else _as_dict(body)
        detail = self._details[node_id]
        return detail or None

    def pmids(self, node_id: str) -> frozenset[int]:
        """Every PubMed id the index holds for this node. An absent node answers with an empty set."""
        if node_id not in self._pmids:
            status, body = self._request(
                f"/variant/get/{urllib.parse.quote(node_id, safe='')}/publications"
            )
            values = [] if status is None else _as_dict(body).get("pmids") or []
            self._pmids[node_id] = frozenset(int(p) for p in values if isinstance(p, int))
        return self._pmids[node_id]

    def gene_nodes(self, gene: str) -> list[LitvarNode]:
        """Every node LitVar holds under a gene symbol, across all four id shapes.

        This is the endpoint that serves Python `repr()` rather than JSON. Nothing calls `.json()` on
        it; `parse_repr_lines` does the reading.
        """
        status, body = self._request(f"/variant/search/gene/{urllib.parse.quote(gene, safe='')}")
        if status is None:
            return []
        return [LitvarNode.parse(record) for record in parse_repr_lines(body)]

    # ── transport ───────────────────────────────────────────────────────────────────────────────

    def _request(self, path: str) -> tuple[int | None, str]:
        """`(status, body)`, or `(None, "")` when LitVar answered *there is no such node*.

        The absence is a return value and every failure is an exception, which is the split a caller
        needs: a 400 whose body opens `Variant not found` is the index answering, and a 400 that says
        anything else is a request this client got wrong. Collapsing them would turn a client bug into
        a permanent negative about a variant.
        """
        try:
            response = self._fetch(path)
        except httpx.HTTPStatusError as exc:
            detail = _detail(exc.response)
            if exc.response.status_code == 400 and detail.startswith(_NOT_FOUND_DETAIL):
                return None, ""
            raise LitvarUnavailable(
                f"LitVar answered {exc.response.status_code} for {path}"
                + (f" ({detail})" if detail else "")
            ) from exc
        except httpx.HTTPError as exc:
            raise LitvarUnavailable(f"LitVar could not be reached for {path} ({exc})") from exc
        return response.status_code, response.text

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential_jitter(initial=0.5, max=8),
        stop=attempt_floor(3),
        reraise=True,
    )
    def _fetch(self, path: str) -> httpx.Response:
        # The gate is the first statement, so a retried attempt spends a slot of the budget instead of
        # bursting past it (`@shared-pacing-gate`).
        self._gate.wait()
        client = self._client or httpx
        response = client.get(f"{self._base}{path}", timeout=90.0, follow_redirects=True)
        response.raise_for_status()
        return response

    # ── the two filtered lookups the pass uses ──────────────────────────────────────────────────

    def position_node(self, rsid: str) -> LitvarNode | None:
        """The position node for exactly this rsID, or `None` when the index holds none."""
        wanted = rsid.strip().lower()
        for node in self.autocomplete(rsid):
            if node.tier == "rsid" and (node.rsid or "").lower() == wanted:
                return node
        return None

    def allele_node(self, caid: str) -> LitvarNode | None:
        """The allele node for exactly this CAID, or `None` when the index holds none."""
        wanted = caid.strip().upper()
        for node in self.autocomplete(caid):
            if node.tier == "clingen" and (node.clingen_id or "").upper() == wanted:
                return node
        return None


def _detail(response: httpx.Response) -> str:
    """LitVar's `{"detail": …}` sentence, or an empty string when the body is not that shape."""
    try:
        payload = json.loads(response.text)
    except ValueError:
        return ""
    return str(payload.get("detail", "")) if isinstance(payload, dict) else ""


def _as_list(body: str) -> list[dict]:
    value = json.loads(body)
    if not isinstance(value, list):
        raise LitvarError("expected a JSON array from LitVar")
    return [record for record in value if isinstance(record, dict)]


def _as_dict(body: str) -> dict:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise LitvarError("expected a JSON object from LitVar")
    return value


# ── the module's side of the join ───────────────────────────────────────────────────────────────


def rsid_bearing_tables() -> dict[str, type[AuthoredModel]]:
    """`{filename: model}` for every authored table whose model declares `rsid`.

    Derived from `DRAFTABLE` rather than restated (`@registry-completeness`), the same walk
    `identifiers._id_bearing_tables` does for its own columns — a table kind added later joins this
    roster by existing, not by somebody remembering it.
    """
    return {
        name: model
        for name, model in DRAFTABLE.items()
        if isinstance(model, type)
        and issubclass(model, AuthoredModel)
        and "rsid" in model.model_fields
    }


@dataclass
class LocusRoster:
    """The loci a module names, the alleles it names at each, and which tables that came out of."""

    #: rsID → the non-reference alleles the module writes at it, in first-seen order.
    alleles: dict[str, list[str]] = field(default_factory=dict)
    #: rsID → the reference allele the module states, first one seen.
    refs: dict[str, str] = field(default_factory=dict)
    #: rsID → the 1-based `start` the module states (VCF POS, `@start-1based`). Read for one purpose:
    #: anchoring a one-sided indel the registry states in interbase terms, against the module's own
    #: `ref` base rather than against a sequence service.
    starts: dict[str, int] = field(default_factory=dict)
    #: rsID → a CAID the module already carries for it (`resolution.csv`, RM153).
    caids: dict[str, str] = field(default_factory=dict)
    read: list[str] = field(default_factory=list)
    not_read: dict[str, str] = field(default_factory=dict)

    @property
    def rsids(self) -> list[str]:
        return list(self.alleles)


def module_loci(spec_dir: Path) -> LocusRoster:
    """Every rsID a module names, with the alleles it names there and any CAID it already holds.

    **The allele columns come from the model** (`AuthoredModel.ALLELE_COLUMNS`), never from a list
    here: `variants.csv` states an allele in `alts`, `genotype` and `effect_allele`, `haplotypes.csv`
    in `allele`, `diplotypes.csv` in `genotype`, and a hand-kept list would be the roster defect one
    layer down. `ref` is skipped because it is the locus rather than a claim about an allele.

    `resolution.csv` is read too, for its `alts` and `caid` columns — the CAID is the allele identity
    RM153 puts there, and it is the shortest route from a module row to an allele node.
    """
    roster = LocusRoster()
    for name, model in sorted(rsid_bearing_tables().items()):
        rows, why = _read_table(spec_dir, name, model)
        if why is not None:
            roster.not_read[name] = why
            continue
        roster.read.append(name)
        for row in rows:
            for rsid in _split_cell(getattr(row, "rsid", None)):
                bag = roster.alleles.setdefault(rsid, [])
                for column in getattr(type(row), "ALLELE_COLUMNS", ()):
                    if column == "ref":
                        continue
                    for allele in _split_alleles(getattr(row, column, None)):
                        if allele not in bag:
                            bag.append(allele)
                ref = getattr(row, "ref", None)
                if ref:
                    roster.refs.setdefault(rsid, str(ref).strip().upper())
                start = getattr(row, "start", None)
                if isinstance(start, int):
                    roster.starts.setdefault(rsid, start)
    rows, why = _read_table(spec_dir, RESOLUTION_CSV, ResolutionRow)
    if why is not None:
        roster.not_read[RESOLUTION_CSV] = why
    else:
        roster.read.append(RESOLUTION_CSV)
        # An **input** read, so the author's overlay applies (`@overlay-read-at-inputs-never-at-
        # baselines`): a corrected `alts` or `caid` in `overrides.csv` is the cell this pass should
        # be joining on, and reading the uncorrected one would have it ask about the wrong allele.
        rows = overlaid_input_rows(spec_dir, RESOLUTION_CSV, rows, error=ValueError)
        for row in rows:
            rsid = (getattr(row, "rsid", None) or "").strip()
            if not rsid or rsid not in roster.alleles:
                # A resolution row for a subject no authored table names is a coordinate-keyed row;
                # this pass is keyed on rsIDs, so it has nothing to add there.
                continue
            for allele in _split_alleles(getattr(row, "alts", None)):
                if allele not in roster.alleles[rsid]:
                    roster.alleles[rsid].append(allele)
            caid = (getattr(row, "caid", None) or "").strip()
            if caid:
                roster.caids.setdefault(rsid, caid.upper())
    return roster


def _read_table(
    spec_dir: Path, name: str, model: type
) -> tuple[list, str | None]:
    """Rows, or the reason they were not read. A read-only pass never dies on an unparseable table."""
    try:
        path = resolve_sidecar(spec_dir, name) or spec_dir / name
    except SidecarCollision as exc:
        return [], str(exc)
    if not path.exists():
        return [], "not present"
    rows, errors, _ = load_csv_rows(path, model, path.name)
    if errors:
        return [], f"could not be read ({errors[0]})"
    return rows, None


def _split_cell(value: object) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in MULTI_SEP.split(str(value)) if part.strip()]


def _split_alleles(value: object) -> list[str]:
    """A cell that may be `A`, `A,AC`, `C/T` or `A|G` reduced to the alleles it names, upper-cased."""
    out: list[str] = []
    for part in _split_cell(value):
        for allele in split_genotype(part):
            token = allele.strip().upper()
            if token and token not in out:
                out.append(token)
    return out


# ── the coverage pass ───────────────────────────────────────────────────────────────────────────


@dataclass
class LocusCoverage:
    """What the index holds for one module locus, and at which tier it said it."""

    rsid: str
    #: The tier the module's own rows put the question at: `allele` when it names an allele there,
    #: `position` when it names none. A position-level answer to a position-level question is the
    #: answer, not a shortfall — which is why the two tiers are recorded separately.
    asked_tier: str
    tier: str
    reason: str
    #: Papers on the position node. `None` where the node was never reached.
    position_pmids: int | None = None
    #: Papers on the allele node(s) matching the module's allele. `None` unless `tier == "allele"` —
    #: never a zero, because "no allele node" and "an allele node with no papers" differ.
    allele_pmids: int | None = None
    #: Papers on the position node that **no** allele node at this locus claims. Counted rather than
    #: discarded (`@dont-discard-computed`): it is 92 % of the literature at APOE rs429358, and a pass
    #: that folded it into the allele answer would be reporting a number about a different thing.
    position_only_pmids: int | None = None
    caids_at_locus: tuple[str, ...] = ()
    matched_caids: tuple[str, ...] = ()
    node_id: str | None = None

    @property
    def degraded(self) -> bool:
        """An allele-level question answered at position level — the finding this pass exists for."""
        return self.asked_tier == "allele" and self.tier == "position"


def coverage_reason(coverage: LocusCoverage) -> str:
    """Why this locus landed on its tier, one sentence per arm.

    A verdict function with several arms owes a reason function with the same arms, pairwise distinct
    (`@answered-is-not-absent`) — otherwise two situations a reader must tell apart share a sentence,
    which is how a strand-flipped SNV was once reported as an event-size disagreement.
    """
    rsid = coverage.rsid
    others = ", ".join(coverage.caids_at_locus) or "none"
    return {
        "allele_node_matched": (
            f"{rsid}: the index holds an allele node for the allele this module names "
            f"({', '.join(coverage.matched_caids)}), so the answer is allele-resolved."
        ),
        "row_names_no_allele": (
            f"{rsid}: no row names an allele at this locus, so the question is position-level and "
            f"the position node answers it exactly."
        ),
        "no_allele_node_at_locus": (
            f"{rsid}: the index holds a position node and no allele node at all, so the literature "
            f"here is not allele-resolved by the source. The count is position-level."
        ),
        "allele_nodes_name_other_alleles": (
            f"{rsid}: the index holds allele nodes ({others}) and none of them is the allele this "
            f"module names, so the allele-level answer is withheld and the count is position-level."
        ),
        "no_node_for_rsid": (
            f"{rsid}: the index holds no node for this rsID at any tier — an answered absence, not a "
            f"failed lookup."
        ),
        "offline": f"{rsid}: the run was offline, so the index was never asked.",
        "index_unreachable": (
            f"{rsid}: LitVar could not be reached, so nothing is established about this locus."
        ),
        "registry_unreachable": (
            f"{rsid}: the ClinGen Allele Registry could not be reached for the CAIDs at this locus "
            f"({others}), so whether one of them is this module's allele was never asked."
        ),
        "allele_not_comparable": (
            f"{rsid}: the registry answered for the CAIDs at this locus ({others}) and holds no "
            f"GRCh38 allele these columns can compare, so whether one of them is this module's "
            f"allele is undecided rather than settled."
        ),
    }[coverage.reason]


@dataclass
class LiteratureCoverageReport:
    """One module's literature coverage, per locus and per tier."""

    loci: list[LocusCoverage] = field(default_factory=list)
    tables_read: list[str] = field(default_factory=list)
    tables_not_read: dict[str, str] = field(default_factory=dict)
    offline: bool = False

    def at(self, tier: str) -> list[LocusCoverage]:
        return [locus for locus in self.loci if locus.tier == tier]

    @property
    def answered(self) -> list[LocusCoverage]:
        """Loci the index gave an answer about — the denominator a coverage number is out of."""
        return [locus for locus in self.loci if locus.tier != "unchecked"]

    @property
    def degraded(self) -> list[LocusCoverage]:
        return [locus for locus in self.loci if locus.degraded]

    @property
    def position_only_residue(self) -> int:
        """Papers across the module's loci that sit on a position node and on no allele node."""
        return sum(locus.position_only_pmids or 0 for locus in self.loci)


def check_literature_coverage(
    spec_dir: Path,
    *,
    client: LitvarClient | None = None,
    registry: ClingenAlleleClient | None = None,
    offline: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> LiteratureCoverageReport:
    """Ask LitVar what it holds for each of a module's loci, and at which tier.

    Reports and repairs nothing (`@enrichment-is-validation`). Nothing here is written into a module:
    a PMID list per variant is not a table kind, `literature.csv` is keyed by article, and 32,095
    PMIDs for one BRAF locus would be a row-writer arguing against itself. What lands is the
    attestation and this report.

    `progress` is called with `(done, total)` over **loci**, the unit `@progress-unit-is-subjects`
    fixes, because the total has to be known before the first request goes out.
    """
    spec_dir = Path(spec_dir)
    roster = module_loci(spec_dir)
    report = LiteratureCoverageReport(
        tables_read=roster.read, tables_not_read=roster.not_read, offline=offline
    )
    rsids = dedupe(roster.rsids)
    total = len(rsids)
    if offline:
        report.loci = [
            LocusCoverage(
                rsid=rsid, asked_tier=_asked_tier(roster, rsid), tier="unchecked", reason="offline"
            )
            for rsid in rsids
        ]
        return report
    index = client or LitvarClient()
    allele_registry = registry or ClingenAlleleClient()
    for done, rsid in enumerate(rsids, start=1):
        report.loci.append(_one_locus(index, allele_registry, roster, rsid))
        if progress is not None:
            progress(done, total)
    return report


def _asked_tier(roster: LocusRoster, rsid: str) -> str:
    """Allele-level when the module names an allele or a CAID at this locus, position-level otherwise.

    The asked tier is a property of the **module's rows**, not of the source. Without it a positional
    module — one that names an rsID and no allele anywhere — would have every locus counted as a
    shortfall, when in fact the position node answered exactly the question that was put.
    """
    return "allele" if roster.alleles.get(rsid) or roster.caids.get(rsid) else "position"


def _one_locus(
    index: LitvarClient,
    registry: ClingenAlleleClient,
    roster: LocusRoster,
    rsid: str,
) -> LocusCoverage:
    asked = _asked_tier(roster, rsid)
    try:
        node = index.position_node(rsid)
        if node is None:
            return LocusCoverage(
                rsid=rsid, asked_tier=asked, tier="absent", reason="no_node_for_rsid"
            )
        detail = index.node(node.node_id) or {}
        caids = tuple(
            str(caid).upper() for caid in (detail.get("clingen_ids") or []) if str(caid).strip()
        )
        position = index.pmids(node.node_id)
        # Every allele node at the locus, matched or not: the residue is *papers no allele node
        # claims*, so it is the union that comes out of it, not the module's own node alone.
        allele_pmids = {caid: index.pmids(n.node_id) for caid, n in _allele_nodes(index, caids)}
    except LitvarError as exc:
        logger.warning("LitVar could not answer for %s (%s)", rsid, exc)
        return LocusCoverage(
            rsid=rsid, asked_tier=asked, tier="unchecked", reason="index_unreachable"
        )

    residue = len(position - frozenset().union(*allele_pmids.values()))
    common = {
        "rsid": rsid,
        "asked_tier": asked,
        "position_pmids": len(position),
        "position_only_pmids": residue,
        "caids_at_locus": caids,
        "node_id": node.node_id,
    }
    if asked == "position":
        return LocusCoverage(tier="position", reason="row_names_no_allele", **common)
    # **The CAIDs that carry a node**, not every CAID the position node lists. An allele-level answer
    # has to come off an allele node, so a CAID the index names and holds nothing for cannot produce
    # one — and letting it into the match would report `allele_pmids=0`, which reads as *this allele
    # has no literature* about a node that does not exist.
    answerable = tuple(allele_pmids)
    if not answerable:
        return LocusCoverage(tier="position", reason="no_allele_node_at_locus", **common)
    matched, undecided = _matching_caids(registry, roster, rsid, answerable)
    if matched:
        return LocusCoverage(
            tier="allele",
            reason="allele_node_matched",
            allele_pmids=len(frozenset().union(*(allele_pmids[caid] for caid in matched))),
            matched_caids=matched,
            **common,
        )
    if undecided is not None:
        # Nothing matched *and* at least one CAID could not be compared, so *no allele node here is
        # this module's* was never established. Reporting position-level would be the collapse
        # `@answered-is-not-absent` names: an unasked question rendered as an answer.
        return LocusCoverage(
            rsid=rsid,
            asked_tier=asked,
            tier="unchecked",
            reason=undecided,
            caids_at_locus=caids,
            node_id=node.node_id,
        )
    return LocusCoverage(tier="position", reason="allele_nodes_name_other_alleles", **common)


def _allele_nodes(index: LitvarClient, caids: Iterable[str]) -> list[tuple[str, LitvarNode]]:
    """`(caid, node)` for each CAID the index really holds a node for, in the order given."""
    found: list[tuple[str, LitvarNode]] = []
    for caid in caids:
        node = index.allele_node(caid)
        if node is not None:
            found.append((caid, node))
    return found


def _matching_caids(
    registry: ClingenAlleleClient, roster: LocusRoster, rsid: str, caids: tuple[str, ...]
) -> tuple[tuple[str, ...], str | None]:
    """`(the CAIDs that are this module's allele, why an empty match is not yet established)`.

    Two routes, and the cheap one first: a `resolution.csv` that already carries a CAID for this
    subject has stated the module's allele identity outright, so no lookup is needed. Otherwise each
    CAID goes through the ClinGen Allele Registry and its GRCh38 allele is compared against the ones
    the module names — on the ALT, plus the REF where both state one, because a CAID whose reference
    base disagrees is a different allele rather than this one.

    **A one-sided indel is anchored with the module's own reference base, never with a guess.** The
    registry states an insertion as an empty `referenceAllele` and a deletion as an empty `allele`,
    neither of which any `ref`/`alts` pair can hold; `clingen_allele.anchor_indel` turns one into a
    VCF row given the base immediately before the event, and the module's own row already states that
    base at that position. So the reader injected below answers only for the position the module
    states and withholds everywhere else — a wrong anchor would put a right position under a wrong
    `ref`, which is a false match rather than a missing one.

    The second element is the third leg of the algebra, and it has **two arms that must not merge**:
    `registry_unreachable` (the registry never answered, so nobody asked) and `allele_not_comparable`
    (it answered and holds nothing this column can compare, so the question is undecided). Both mean
    an empty match is not an established negative, and they are cleared by different things.
    """
    recorded = roster.caids.get(rsid)
    if recorded and recorded in caids:
        return (recorded,), None
    wanted = {allele.upper() for allele in roster.alleles.get(rsid, [])}
    ref = roster.refs.get(rsid)
    start = roster.starts.get(rsid)
    matched: list[str] = []
    unreachable = False
    incomparable = False
    for caid in caids:
        identity = registry.resolve(caid)
        if identity.outcome in {"unchecked", "skipped_offline"}:
            unreachable = True
            continue
        coordinate = identity.coordinate
        if coordinate is None and identity.unanchored is not None:
            coordinate = anchor_indel(identity.unanchored, _anchor_from_module(ref, start))
        if coordinate is None:
            incomparable = True
            continue
        _chrom, _start, registry_ref, registry_alt = coordinate
        if registry_alt.upper() not in wanted:
            continue
        if ref and registry_ref.upper() != ref:
            continue
        matched.append(caid)
    if matched:
        return tuple(matched), None
    if unreachable:
        return (), "registry_unreachable"
    return (), "allele_not_comparable" if incomparable else None


def _anchor_from_module(ref: str | None, start: int | None) -> Callable[[str, int], str | None]:
    """A `read_base` that answers from the module's own row, and only where the row really says so.

    `anchor_indel` takes its base reader as a parameter so the anchoring rule can be exercised without
    a sequence service; this is the reader for the one base a module already states — the first
    character of the `ref` it wrote at `start`, which is by construction the base immediately before
    the event. Anything else is `None`, and `anchor_indel` then withholds.
    """

    def read_base(_chrom: str, position: int) -> str | None:
        if not ref or start is None or position != start:
            return None
        return ref[0]

    return read_base


def verification_records(report: LiteratureCoverageReport) -> list[VerificationRecord]:
    """The attestation, and it names the tier — a coverage answer that does not is the defect.

    One record. `subjects` is the loci the index **answered** about, `findings` the loci where an
    allele-level question came back position-level, and `detail` carries the whole tier breakdown,
    because "12 checked, 3 flagged" says nothing about which of 328 and 3,945 a reader is holding.
    """
    if not report.loci:
        return [
            skipped(
                "literature_coverage",
                "nothing_to_check",
                detail=(
                    "no authored table names an rsID, so there was no locus to ask LitVar about"
                ),
                source=LITVAR_SOURCE,
            )
        ]
    if report.offline:
        return [
            skipped(
                "literature_coverage",
                "offline",
                detail=f"--offline, so none of the {len(report.loci)} locus/loci was looked up",
                source=LITVAR_SOURCE,
            )
        ]
    answered = report.answered
    if not answered:
        return [
            skipped(
                "literature_coverage",
                "unreachable",
                detail=(
                    f"none of the {len(report.loci)} locus/loci could be looked up: "
                    f"{examples([locus.rsid for locus in report.loci])}"
                ),
                source=LITVAR_SOURCE,
            )
        ]
    allele = report.at("allele")
    position = report.at("position")
    absent = report.at("absent")
    unchecked = report.at("unchecked")
    degraded = report.degraded
    detail = (
        f"{len(allele)} locus/loci answered at allele tier, {len(position)} at position tier only, "
        f"{len(absent)} absent from the index"
        + (f", {len(unchecked)} could not be asked" if unchecked else "")
        + f"; {report.position_only_residue} paper(s) sit on a position node that no allele node "
        f"claims"
        + (
            f"; allele-level questions answered position-level: "
            f"{examples([locus.rsid for locus in degraded])}"
            if degraded
            else ""
        )
    )
    return [
        ran(
            "literature_coverage",
            subjects=len(answered),
            findings=len(degraded),
            source=LITVAR_SOURCE,
            detail=detail,
        )
    ]
