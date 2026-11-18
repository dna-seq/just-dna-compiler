"""Remote snapshot reads: the registry's proxy, then Hugging Face, for a box with no local snapshot (0.9, RM430).

The read order is the maintainer's (desk #261): **the snapshot on local disk, then the registry's proxy,
then Hugging Face**. Local disk stays where it was, in each reader and each `resolve_*_reference`; this
module is the two remote steps, held by one object a caller opts into. Nothing here runs unless a caller
holds a `RemoteSnapshots` and hands it over (`LookupClients.snapshots`): with no holder there is no remote
read and no egress, so every call that existed before 0.9 answers exactly as it did.

**One query method, the proxy's contract on both routes.** `RemoteSnapshots.lookup(lane, table, keys)`
answers the rows of one table of one lane that match identifier keys: values ORed within a column,
columns ANDed, `chrom` and `start` together (equal-length lists pair, `chrom[i]` with `start[i]`, as the
registry's 0.32.1 does). The rows are the lane's own parquet columns, unchanged, so the proxy (which
answers exactly that, `docs/API-REFERENCE.md` §§ 46–47 of the registry) and Hugging Face (read here
through duckdb's `httpfs` over the pinned revision) give the same rows for the same keys. A reader's own
SQL then runs over those rows as it runs over the local glob, so there is one copy of each query.

**Every answer says where it came from** (`RemoteAnswer`): the route, the release label that route
states, the proxy's `served_from`, and the Hub revision read. A proxy answer's release is what its reply
states, else `None`: withheld, never guessed. This traces an answer to its route; it does not detect two
copies that carry one label over different bytes (the trial's findings 8 and 9), and claims nothing of
the sort.

**One release per route per holder.** The first Hugging Face read of a lane pins the repository's
revision (a commit) and reads `release.json`, or for Ensembl `manifest.json`, at that commit; every
later read of that lane through the holder reads the same commit. A 429 can send some keys of one
session to Hugging Face while others came from the proxy, so nothing claims a session is one release:
each answer carries its own. A holder ends with `close()`; a server that wants a newer release opens a
new holder.

**Could-not-ask is one type, `SnapshotRouteUnavailable`**, never an empty answer
(`@unreachable-not-absent`). The holder translates duckdb's HTTP and I/O errors and `httpx`'s errors
into it. A request the routes would refuse as wrong (an unknown lane, table or key column, an Ensembl
key with no position, the proxy's 422, a closed holder) raises `ValueError`, because asking another
route would get the same refusal; it is a caller's or our own defect, so nothing above the holder
turns it into could-not-ask either. A licence the caller's declaration cannot meet raises
`licensing.LicenseRefusal`.

**Every remote URL is built by `remote_url`**, the one function the test suite's network fence wraps:
duckdb opens its sockets in C++, where the fence's Python socket patch cannot see them. That is also why
duckdb is never handed an `hf://` URL: its `hf://` scheme resolves to `huggingface.co` inside duckdb,
past `hf_base_url` and past the fence; the holder lists the revision's files itself and hands duckdb
explicit `https://…/resolve/<commit>/<path>` URLs (a glob over plain HTTP is not supported either).
"""

import json
import logging
import re
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import duckdb
import httpx
from huggingface_hub import get_token
from just_dna_format.snapshot import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    SNAPSHOT_MANIFEST_FILENAME,
    parse_release,
)
from just_dna_format.vrs import normalize_chrom
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.key_compare import KEY_COMPARES, KeyCompare, lane_compare
from just_dna_enricher.licensing import check_declared_use
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS, SnapshotManifest, env_value
from just_dna_enricher.net import GONE, EndpointRetired

logger = logging.getLogger(__name__)

#: The Hub a holder reads unless it is pointed elsewhere (`hf_base_url`, a test's loopback server).
HF_BASE_URL = "https://huggingface.co"
#: The branch a holder pins: the commit `main` names at the lane's first read.
HF_PINNED_BRANCH = "main"
#: The proxy's base URL and its optional bearer token, read with `env_value` when the holder is built
#: and the argument is not given. Unset by default, as the registry asked: its server must never pick
#: up its own proxy by accident and call itself.
PROXY_URL_VAR = "JUST_DNA_SNAPSHOT_PROXY_URL"
PROXY_TOKEN_VAR = "JUST_DNA_SNAPSHOT_PROXY_TOKEN"
#: The proxy's timeouts (decision 3): connect 3 s, read 10 s. It answers in 0.2 to 0.4 s (the trial).
PROXY_TIMEOUT = httpx.Timeout(10.0, connect=3.0)
#: The Hub API's timeouts, for the revision and the release record (two small reads per lane).
HF_API_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
#: The most key values the proxy answers in one request (`lane_max_keys`); a lookup is split to fit.
PROXY_MAX_KEY_VALUES = 100
#: The proxy's HTTP statuses after which a holder asks Hugging Face instead (the registry's list):
#: pacing, an outage, a gateway timeout. A 404 joins them only as `lane_not_available`.
PROXY_FALL_THROUGH_STATUSES = frozenset({429, 503, 504})
PROXY_LANE_NOT_AVAILABLE = "lane_not_available"
#: The proxy's 404 codes that name a wrong request rather than an absent lane: raised like a 422.
PROXY_WRONG_REQUEST_404 = frozenset({"unknown_lane", "unknown_table"})

#: What a lookup on a closing or closed holder raises, as `ValueError`: a wrong request, never could-not-ask.
HOLDER_CLOSED = "this RemoteSnapshots is closed; open a new one"

#: The routes a remote answer can come from: the registry's proxy, or the lane's Hugging Face repo.
ROUTE_PROXY = "proxy"
ROUTE_HF = "hf"
REMOTE_ROUTES = frozenset({ROUTE_PROXY, ROUTE_HF})

#: The columns a lookup may key on: identifiers only, the registry's list, and `chrom` only with `start`.
KEY_COLUMNS: tuple[str, ...] = (
    "rsid",
    "id",
    "gene",
    "genes",
    "symbol",
    "variant_id",
    "variation_id",
    "pmid",
    "allele",
    "study_locus_id",
    "chrom",
    "start",
)
#: Where a table keeps its position: a `start` key reads whichever of these it has, in this order.
POSITION_COLUMNS: tuple[str, ...] = ("start", "pos", "position")
#: A shard or chromosome suffix on a payload file's name, collapsed so one table is one name (the
#: registry's rule, so a table is called the same on both routes).
_SHARD = re.compile(r"-(chr[0-9XYMT]+|[0-9]+)$")
#: What a Hugging Face 429 costs: its anonymous quota is a fixed window (the trial's finding 2).
HF_QUOTA_WINDOW = (
    "Hugging Face's anonymous quota is 3,000 requests per 5 minutes per IP (a fixed window); ask again "
    "after it, or set HF_TOKEN"
)


class SnapshotRouteUnavailable(Exception):
    """A remote route could not be asked, or could not be read: could-not-ask, never an absence.

    `lane` is the lane asked, `route` the route that failed (`proxy`, `hf`), or `None` when no route was
    asked at all (the licence gate skipped the lane, or no route is configured), and `cause` says why.
    Raised by `RemoteSnapshots.lookup` for every failure of a route; duckdb's and `httpx`'s own errors
    are its `__cause__`, so `net.could_not_ask_reason` still reads a 410 as `retired`.
    """

    def __init__(self, lane: str, route: str | None, cause: str) -> None:
        where = {ROUTE_PROXY: "the registry's proxy", ROUTE_HF: "Hugging Face", None: "no remote route"}[
            route
        ]
        verb = "was asked" if route is None else "could not be asked"
        super().__init__(f"{lane}: {where} {verb}: {cause}")
        self.lane = lane
        self.route = route
        self.cause = cause
        #: Set on a proxy failure the registry lists for falling through to Hugging Face (internal).
        self._falls_through = False


class SnapshotRouteRetired(SnapshotRouteUnavailable, EndpointRetired):
    """A remote route answered HTTP 410: it retired the endpoint (RM361's marker, under the one type).

    Caught by every `except SnapshotRouteUnavailable`, so a caller still writes one handler; a handler
    that records why reads `retired` here rather than `unreachable` (`net.could_not_ask_reason`).
    """


def _unavailable(
    lane: str, route: str | None, cause: str, status: int | None = None
) -> SnapshotRouteUnavailable:
    """The could-not-ask error for `status`: `SnapshotRouteRetired` for a 410, else the one type."""
    return (SnapshotRouteRetired if status == GONE else SnapshotRouteUnavailable)(lane, route, cause)


def _falling_through(lane: str, cause: str) -> SnapshotRouteUnavailable:
    """A proxy failure after which Hugging Face is asked instead (the registry's list)."""
    error = SnapshotRouteUnavailable(lane, ROUTE_PROXY, cause)
    error._falls_through = True
    return error


@dataclass(frozen=True)
class RemoteRoute:
    """Where one remote answer came from: the route, its release label, `served_from`, the Hub revision.

    `release` is the label that route states: `release.json`'s `dataset` (Ensembl: `manifest.json`'s
    `release_id`) at the pinned commit for `hf`, and what the proxy's reply states for `proxy`, `None`
    when it states none (withheld, never guessed). `served_from` is the proxy's (`local`, or
    `remote:<repo>`), `None` on `hf`. `revision` is the Hub commit read, `None` where none was stated.
    A proxy answer cut into several requests states each of the three only when every reply states the
    same one; a reply stating none, or two stating different ones, withholds it (`None`).
    """

    route: str
    release: str | None = None
    served_from: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class RemoteAnswer:
    """The rows one remote lookup matched, and where they came from.

    `rows` are the table's own columns, in a stable order. `route` is the one record of where they came
    from (a `RemoteRoute`: the route, its release label, `served_from`, the Hub revision), never a copy
    of its fields, so the two shapes cannot drift apart within the major."""

    rows: list[dict[str, Any]]
    route: RemoteRoute


@dataclass(frozen=True)
class RemoteLane:
    """A lane a holder may read remotely. Its repo is `locations.SNAPSHOT_REPO_IDS`'s; its terms are
    `caches.CACHE_LANES`'s.

    `needs_position`: a key with no `chrom` + `start` is refused before any route is asked. Ensembl's
    alone: its rsID column is about 6.1 GB over 25 files and no row group prunes by it, so the proxy
    refuses it (`remote_needs_position`) and Hugging Face would scan about 10.7 GB (the trial).

    `compares`: table -> key column -> `key_compare.KeyCompare`, the lane's entry in
    `key_compare.KEY_COMPARES`, the registry its keyed functions' local SQL is built from, so a remote read
    compares a key as the local one does: by `gene_key`, member by member of a `;`-joined cell. Derived
    from the lane's name, never restated here. A column it does not name compares the whole cell exactly. The registry's proxy compares every key exactly, so a key with any
    other compare is not sent to it (`proxy_compares`) and Hugging Face answers it.
    """

    name: str
    needs_position: bool = False

    @property
    def compares(self) -> Mapping[str, Mapping[str, KeyCompare]]:
        """The lane's entry in `key_compare.KEY_COMPARES`: table -> column -> compare; empty when exact."""
        return KEY_COMPARES.get(self.name, {})

    def compare(self, table: str, column: str) -> KeyCompare:
        """How `column` of `table` is compared with a key: the lane's declaration, else exactly."""
        return lane_compare(self.name, table, column)

    def proxy_compares(self, table: str, columns: Iterable[str]) -> bool:
        """Whether the registry's proxy compares each of `columns` as the local reader does.

        It compares a whole cell exactly, so it does only where the lane compares the cell whole
        (`KeyCompare.cell_exact`), the holder sending each key as the compare reads it (an rsID as the
        snapshot spells one). Asked for a folded or a joined column it would return fewer rows than the
        local route and say nothing, an absence where the row exists (`@unreachable-not-absent`)."""
        return all(self.compare(table, column).cell_exact for column in columns)


#: The lanes a holder reads remotely. Each needs a published repo; a lane without one (PharmVar and
#: PubMind are operator-built) stays local. Not here on purpose: `mitomap` and `strchive` (no keyed
#: reader; STRchive's catalogue is one small file), `alphagenome_avi` (its one reader is a writing pass,
#: which stays local). Joined with their keyed functions (RM431): `opentargets` (`variants` by chrom +
#: start, `consequences` and `credible_set_members` by `variant_id`), `civic` (`civic` by `gene` or
#: `rsid`) and `clinvar_gkm` (`clinvar_gkm-indels` by chrom + start or `rsid`; its VRS id is no key).
REMOTE_LANES: dict[str, RemoteLane] = {
    lane.name: lane
    for lane in (
        RemoteLane("ensembl", needs_position=True),
        RemoteLane("clinvar"),
        RemoteLane("constraint"),
        RemoteLane("clinpgx"),
        RemoteLane("cpic"),
        RemoteLane("drug_labels"),
        RemoteLane("opentargets"),
        RemoteLane("civic"),
        RemoteLane("clinvar_gkm"),
    )
}


def remote_url(base: str, *parts: str) -> str:
    """Every URL a holder asks, the proxy's and the Hub's alike: `base` joined with `parts`.

    The one place a remote URL is built, so the test suite's network fence can refuse a host that is not
    this machine here (it wraps this function), before duckdb opens a socket the fence cannot see.
    """
    return "/".join([base.rstrip("/"), *(part.strip("/") for part in parts if part.strip("/"))])


def table_name(path: str) -> str:
    """The table a payload file belongs to: its name without extension, shard or chromosome suffix."""
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return _SHARD.sub("", stem)


def _bare_chrom(value: object) -> str:
    """A chromosome as `normalize_chrom` spells it (`chrM` → `MT`), so keys and attestations group alike."""
    return normalize_chrom(str(value))


def _chrom_forms(value: object) -> tuple[str, ...]:
    """Every spelling a stored `chrom` cell may use for `value`: bare and `chr`-prefixed, `MT` and `M`."""
    bare = _bare_chrom(value)
    names = (bare, "M") if bare == "MT" else (bare,)
    return tuple(form for name in names for form in (name, f"chr{name}"))


def _stable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows in an order every route reproduces: the proxy's and duckdb's row orders differ."""
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))


@dataclass(frozen=True)
class _Keys:
    """A lookup's keys, validated: the plain columns, and the positions grouped by chromosome."""

    plain: dict[str, list[Any]]
    #: bare chromosome -> starts asked there, or `None` when the lookup has no position key.
    positions: dict[str, list[int]] | None


def _read_keys(lane: RemoteLane, keys: Mapping[str, Sequence[Any]]) -> _Keys:
    """`keys` checked against the contract both routes answer, or `ValueError` naming the fault."""
    given = {column: list(dict.fromkeys(values)) for column, values in keys.items()}
    if not given or not all(given.values()):
        raise ValueError(
            f"{lane.name}: a remote lookup needs a value for every key it names; nothing enumerates"
        )
    unknown = sorted(set(given) - set(KEY_COLUMNS))
    if unknown:
        raise ValueError(
            f"{lane.name}: not a key column: {', '.join(unknown)} (keys: {', '.join(KEY_COLUMNS)})"
        )
    if ("chrom" in given) != ("start" in given):
        raise ValueError(f"{lane.name}: a position key is chrom and start together")
    if lane.needs_position and "chrom" not in given:
        raise ValueError(
            f"{lane.name} answers remotely by chrom + start only: its rsID column cannot be bounded "
            f"remotely (about 10.7 GB on Hugging Face), so an rsID alone is never sent"
        )
    if "chrom" not in given:
        return _Keys(given, None)
    chroms, starts = keys["chrom"], [int(s) for s in keys["start"]]
    # Equal lengths pair `chrom[i]` with `start[i]`; unequal lengths keep the any-of-each meaning.
    pairs = (
        zip(chroms, starts, strict=True)
        if len(chroms) == len(starts)
        else ((c, s) for c in chroms for s in starts)
    )
    positions: dict[str, list[int]] = {}
    for chrom, start in pairs:
        at = positions.setdefault(_bare_chrom(chrom), [])
        if start not in at:
            at.append(start)
    plain = {column: values for column, values in given.items() if column not in ("chrom", "start")}
    return _Keys(plain, positions)


def _read_as_compared(lane: RemoteLane, table: str, keys: _Keys) -> _Keys:
    """`keys` with each value of a column whose compare reads the key (an rsID: `RS334` is `rs334`) read so.

    The local reader reads an asked key so before its SQL compares the cell, so both routes are asked the
    key as read: the proxy, which compares a cell exactly, then answers as the local route does (review
    round 1, item 5). A column compared as given keeps its values, unconverted. A column left with no value
    (only blanks) is a wrong request, as an empty one is.
    """
    plain: dict[str, list[Any]] = {}
    for column, values in keys.plain.items():
        compare = lane.compare(table, column)
        plain[column] = values if compare.exact else compare.parameter(values)
        if not plain[column]:
            raise ValueError(
                f"{lane.name}: a remote lookup needs a value for every key it names; {column} holds only blanks"
            )
    return _Keys(plain, keys.positions)


def _requests(keys: _Keys) -> list[dict[str, list[Any]]]:
    """The key sets one route is asked, each naming one chromosome at most (decision 3)."""
    if keys.positions is None:
        return [dict(keys.plain)]
    return [{**keys.plain, "chrom": [chrom], "start": starts} for chrom, starts in keys.positions.items()]


def _batch_column(request: Mapping[str, list[Any]]) -> str:
    """The column a request is split along: `start` for a position, else the one with most values."""
    if "start" in request:
        return "start"
    return max(request, key=lambda column: (len(request[column]), column))


def _passed_over(lane: RemoteLane, table: str, wanted: _Keys) -> str | None:
    """Why the registry's proxy is not asked for `wanted`, or `None` when it is: a key it would compare
    otherwise than the local reader (`RemoteLane.proxy_compares`), or a request over its own limit
    (`_proxy_overflow`). Either way Hugging Face is asked instead, and with it off the reason is said."""
    if not lane.proxy_compares(table, wanted.plain):
        compared = "; ".join(
            f"{column} {lane.compare(table, column).described}"
            for column in sorted(wanted.plain)
            if not lane.compare(table, column).cell_exact
        )
        return (
            f"the registry's proxy compares a whole cell exactly, and {lane.name}/{table} compares "
            f"{compared}, as its local reader does, so the proxy is not asked"
        )
    return _proxy_overflow(wanted)


def _proxy_overflow(wanted: _Keys) -> str | None:
    """Why no request of `wanted` fits the proxy's limit of key values, or `None` when every one does.

    The batch column is split to fit, so a request overflows only when its other columns alone fill the
    limit. The limit is the proxy's, never Hugging Face's, so such a request is not wrong on every route:
    the proxy is passed over and Hugging Face asked, as for a folded key (review round 1, item 6).
    """
    for request in _requests(wanted):
        column = _batch_column(request)
        fixed = sum(len(values) for name, values in request.items() if name != column)
        if fixed >= PROXY_MAX_KEY_VALUES:
            return (
                f"the registry's proxy answers at most {PROXY_MAX_KEY_VALUES} key values a request, and {fixed} "
                f"besides {column!r} leave no room, so the proxy is not asked"
            )
    return None


def _proxy_chunks(request: dict[str, list[Any]]) -> list[dict[str, list[Any]]]:
    """`request` cut to the proxy's limit of key values per request, along its batch column.

    Called only for a request `_proxy_overflow` passed, so there is room for at least one value."""
    column = _batch_column(request)
    room = PROXY_MAX_KEY_VALUES - sum(len(values) for name, values in request.items() if name != column)
    values = request[column]
    return [{**request, column: values[i : i + room]} for i in range(0, len(values), room)]


@dataclass
class _Pin:
    """One lane's Hub read: the commit, its files, its release label, and the connection that reads it."""

    repo: str
    revision: str
    files: tuple[str, ...]
    release: str | None
    #: bare chromosome -> the payload files the manifest attests for it; empty when it attests none.
    chromosomes: dict[str, tuple[str, ...]]
    connection: duckdb.DuckDBPyConnection
    schemas: dict[str, dict[str, str]] = field(default_factory=dict)

    def table_files(self, lane: str, table: str) -> tuple[str, ...]:
        found = tuple(
            f
            for f in self.files
            if f.startswith(f"{SNAPSHOT_DATA_DIRNAME}/") and f.endswith(".parquet") and table_name(f) == table
        )
        if not found:
            tables = sorted({table_name(f) for f in self.files if f.startswith(f"{SNAPSHOT_DATA_DIRNAME}/")})
            raise ValueError(
                f"{lane} has no table {table!r} at {self.repo}@{self.revision} (it has {', '.join(tables)})"
            )
        return found


class _ProxyReply(BaseModel):
    """The registry's lane reply (§§ 46–47), read strictly: the one model a proxy 200 is read through.

    Review round 1, item 1: a 200 was read after an outer shape check only, so a missing `truncated` read as
    a whole answer, a row that was not an object reached the readers as an `AttributeError`, and a reply for
    another lane or table was taken for the one asked. Each is a malformed reply now, could-not-ask on the
    proxy with no fall-through. Strict on what the client reads (types are not coerced: `"false"` is no
    bool), and blind to what it does not (`extra="ignore"`), so a field the registry adds later costs
    nothing. `lane`, `table`, `rows` and `truncated` are in every reply since the proxy's first version
    (registry 0.30); `served_from`, `release` and `revision` came later and may be absent or `null`, and one
    of another kind is withheld rather than refused.
    """

    model_config = ConfigDict(extra="ignore", strict=True)

    lane: str
    table: str
    rows: list[dict[str, Any]]
    truncated: bool
    served_from: str | None = None
    release: str | None = None
    revision: str | None = None

    @field_validator("served_from", "release", "revision", mode="before")
    @classmethod
    def _withheld_unless_text(cls, value: object) -> object:
        """Provenance of another kind is withheld (`None`), never a malformed reply: these fields only say
        where the rows came from, so a registry that changes one's kind costs that field, not the route."""
        return value if value is None or isinstance(value, str) else None


def _proxy_reply(lane: str, table: str, body: object) -> _ProxyReply:
    """`body` read as the reply to a request for `lane`'s `table`, or could-not-ask saying what is wrong."""
    try:
        reply = _ProxyReply.model_validate(body)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'the body'}: {error['msg']}"
            for error in exc.errors()[:3]
        )
        raise SnapshotRouteUnavailable(
            lane, ROUTE_PROXY, f"a 200 that is not a lane reply ({problems})"
        ) from exc
    if (reply.lane, reply.table) != (lane, table):
        raise SnapshotRouteUnavailable(
            lane,
            ROUTE_PROXY,
            f"a 200 that is not the reply asked for: it answers {reply.lane}/{reply.table}, not {lane}/{table}",
        )
    return reply


def _hub_cause(exc: Exception) -> str:
    """Why a Hub read failed, with the quota named on a 429 (duckdb's error carries no `Retry-After`)."""
    status = getattr(exc, "status_code", None)
    if status is None and isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return f"{text}. {HF_QUOTA_WINDOW}" if status == 429 else text


class RemoteSnapshots:
    """The remote half of a lane's read order: the registry's proxy, then Hugging Face (0.9, RM430).

    A context manager, and a `LookupClients` field (`snapshots`) the `lookup_*` functions read. It owns
    the proxy's `httpx` client, a client for the Hub's API, one duckdb connection per lane it has read
    from Hugging Face, each lane's pin, and the lock both are made under. Its one query is `lookup`.

    `proxy_url`/`proxy_token`: the registry's proxy, else `$JUST_DNA_SNAPSHOT_PROXY_URL` and
    `$JUST_DNA_SNAPSHOT_PROXY_TOKEN` read with `env_value` now; with neither, the proxy is not asked.
    `huggingface`: whether Hugging Face is asked (on unless `False`). `declared_use`: the declaration the
    licence gate judges before a lane's first remote read, on any route. `hf_base_url`: the Hub's base
    URL (`HF_BASE_URL` unless given); a Hub token (`HF_TOKEN`, else `huggingface_hub.get_token()`) is
    sent only to `HF_BASE_URL`, never to another host.

    Thread-safe: a lane's pin and connection are made once, under that lane's own lock (so a slow first
    read of one lane holds up no other), and every query runs on its own cursor of the lane's
    connection. Each connection lives as long as the holder. `close()` takes the holder's lock, refuses
    every lookup from then on (`ValueError`, `HOLDER_CLOSED`) and waits for the lookups already running
    to finish before it closes a client or a connection under them.
    """

    def __init__(
        self,
        *,
        proxy_url: str | None = None,
        proxy_token: str | None = None,
        huggingface: bool = True,
        declared_use: str = "unstated",
        hf_base_url: str | None = None,
    ) -> None:
        self.proxy_url = (proxy_url if proxy_url is not None else env_value(PROXY_URL_VAR)) or None
        token = (proxy_token if proxy_token is not None else env_value(PROXY_TOKEN_VAR)) or None
        self.huggingface = huggingface
        self.declared_use = declared_use
        self.hf_base_url = (hf_base_url or HF_BASE_URL).rstrip("/")
        self._lock = threading.Lock()
        #: Signalled, under `_lock`, when the last lookup in flight finishes: what `close()` waits on.
        self._idle = threading.Condition(self._lock)
        self._in_flight = 0
        self._pins: dict[str, _Pin] = {}
        self._pin_locks: dict[str, threading.Lock] = {}
        self._closed = False
        self._proxy: httpx.Client | None = None
        if self.proxy_url is not None:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            self._proxy = httpx.Client(timeout=PROXY_TIMEOUT, headers=headers)
        self._hf_token = (
            (env_value("HF_TOKEN") or get_token() or None) if self.hf_base_url == HF_BASE_URL else None
        )
        hub_headers = {"Authorization": f"Bearer {self._hf_token}"} if self._hf_token else {}
        self._hub = httpx.Client(timeout=HF_API_TIMEOUT, headers=hub_headers, follow_redirects=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close every connection and client the holder opened; its pins end with it.

        Takes the holder's lock: from here on a lookup raises `ValueError` (`HOLDER_CLOSED`), and the
        lookups already running finish before anything they read through is closed, so none of them
        meets a closed client and a transport error that is not its route's. It waits as long as they
        run, a whole-table Hub scan included; a wait that is interrupted (`KeyboardInterrupt`) still
        closes everything before the interruption propagates, which is the old race, taken knowingly."""
        with self._lock:
            self._closed = True
            try:
                while self._in_flight:
                    self._idle.wait()
            finally:
                for pin in self._pins.values():
                    pin.connection.close()
                self._pins.clear()
                self._hub.close()
                if self._proxy is not None:
                    self._proxy.close()

    # ── the one query ───────────────────────────────────────────────────────────────────────────

    def lookup(self, lane: str, table: str, keys: Mapping[str, Sequence[Any]]) -> RemoteAnswer:
        """The rows of `lane`'s `table` matching `keys`, from the proxy, else from Hugging Face.

        `keys` maps a key column (`KEY_COLUMNS`) to its values: ORed within a column, ANDed across, and
        `chrom` with `start` paired when their lists are as long as each other. Raises `ValueError` for a
        request either route refuses, `licensing.LicenseRefusal` when the declared use contradicts the
        lane's terms, and `SnapshotRouteUnavailable` when no route could answer.
        """
        spec = REMOTE_LANES.get(lane)
        if spec is None:
            raise ValueError(f"{lane!r} is not read remotely; lanes that are: {', '.join(REMOTE_LANES)}")
        wanted = _read_keys(spec, keys)
        with self._lock:
            if self._closed:
                raise ValueError(HOLDER_CLOSED)
            self._in_flight += 1
        try:
            return self._lookup(lane, table, wanted)
        finally:
            with self._lock:
                self._in_flight -= 1
                if not self._in_flight:
                    self._idle.notify_all()

    def _lookup(self, lane: str, table: str, wanted: _Keys) -> RemoteAnswer:
        """`lookup` past its checks, counted in flight so `close()` waits for it."""
        self._admit(lane)
        spec = REMOTE_LANES[lane]
        wanted = _read_as_compared(spec, table, wanted)
        fell_through: str | None = None
        passed_over = _passed_over(spec, table, wanted) if self._proxy is not None else None
        if passed_over is not None:
            if self.huggingface:  # with it off, the could-not-ask below says so
                logger.info("%s: %s; asking Hugging Face", lane, passed_over)
        elif self._proxy is not None:
            try:
                answer = self._ask_proxy(lane, table, wanted)
            except SnapshotRouteUnavailable as exc:
                if not exc._falls_through:
                    raise
                fell_through = exc.cause
                if self.huggingface:
                    logger.info(
                        "%s: the proxy could not answer (%s); asking Hugging Face next", lane, exc.cause
                    )
            else:
                self._log(lane, table, answer)
                return answer
        if not self.huggingface:
            if fell_through is not None:
                raise SnapshotRouteUnavailable(lane, ROUTE_PROXY, f"{fell_through}, and Hugging Face is off")
            if passed_over is not None:
                raise SnapshotRouteUnavailable(lane, None, f"{passed_over}, and Hugging Face is off")
            raise SnapshotRouteUnavailable(lane, None, "no proxy is configured and Hugging Face is off")
        try:
            answer = self._ask_hf(lane, table, wanted)
        except SnapshotRouteUnavailable as exc:
            if fell_through is None:
                raise
            raise SnapshotRouteUnavailable(
                lane, ROUTE_HF, f"{exc.cause} (the proxy before it: {fell_through})"
            ) from exc
        self._log(lane, table, answer)
        return answer

    @staticmethod
    def _log(lane: str, table: str, answer: RemoteAnswer) -> None:
        logger.info(
            "%s/%s: %d row(s) over %s, release %s, served_from %s, revision %s",
            lane,
            table,
            len(answer.rows),
            answer.route.route,
            answer.route.release,
            answer.route.served_from,
            answer.route.revision,
        )

    def _admit(self, lane: str) -> None:
        """The licence gate, before a lane's remote read on any route: a remote read is an acquisition.

        A lane whose registry entry states no terms is not gated (the rebuild gate's reading of `None`).
        A refusal raises `LicenseRefusal`; a skip reason makes the lane could-not-ask, saying it.
        """
        terms = LANES_BY_NAME[lane].terms
        if terms is None:
            return
        reason = check_declared_use(terms, self.declared_use)
        if reason is not None:
            raise SnapshotRouteUnavailable(lane, None, reason)

    # ── the proxy ───────────────────────────────────────────────────────────────────────────────

    def _ask_proxy(self, lane: str, table: str, wanted: _Keys) -> RemoteAnswer:
        replies: list[_ProxyReply] = []
        for request in _requests(wanted):
            for chunk in _proxy_chunks(request):
                replies.extend(self._proxy_untruncated(lane, table, chunk))
        rows = [row for reply in replies for row in reply.rows]
        return RemoteAnswer(
            rows=_stable(rows),
            route=RemoteRoute(
                route=ROUTE_PROXY,
                release=_agreed(lane, "releases", [reply.release for reply in replies]),
                served_from=_agreed(lane, "served_from values", [reply.served_from for reply in replies]),
                revision=_agreed(lane, "revisions", [reply.revision for reply in replies]),
            ),
        )

    def _proxy_untruncated(self, lane: str, table: str, request: dict[str, list[Any]]) -> list[_ProxyReply]:
        """The replies that answer `request` whole: a truncated one is halved and asked again, to one key."""
        reply = self._proxy_post(lane, table, request)
        if not reply.truncated:
            return [reply]
        column = _batch_column(request)
        values = request[column]
        if len(values) == 1:
            raise SnapshotRouteUnavailable(
                lane,
                ROUTE_PROXY,
                f"the proxy truncated its answer for one key ({column}={values[0]!r}), so the rest of that "
                f"key's rows were not seen; it is unchecked, not absent",
            )
        half = len(values) // 2
        return [
            *self._proxy_untruncated(lane, table, {**request, column: values[:half]}),
            *self._proxy_untruncated(lane, table, {**request, column: values[half:]}),
        ]

    def _proxy_post(self, lane: str, table: str, request: dict[str, list[Any]]) -> _ProxyReply:
        assert self._proxy is not None and self.proxy_url is not None
        url = remote_url(self.proxy_url, "api/v1/lanes", quote(lane, safe=""), quote(table, safe=""))
        try:
            response = self._proxy.post(url, json={"keys": request})
        except httpx.TimeoutException as exc:
            raise _falling_through(lane, f"timed out ({type(exc).__name__})") from exc
        except httpx.TransportError as exc:
            raise _falling_through(lane, f"could not connect ({type(exc).__name__}: {exc})") from exc
        code = _error_code(response)
        if response.status_code == 422 or (response.status_code == 404 and code in PROXY_WRONG_REQUEST_404):
            raise ValueError(
                f"{lane}/{table}: the proxy refused the request as wrong ({response.status_code} {code}): {_said(response)}"
            )
        if response.status_code in PROXY_FALL_THROUGH_STATUSES or (
            response.status_code == 404 and code == PROXY_LANE_NOT_AVAILABLE
        ):
            raise _falling_through(lane, f"HTTP {response.status_code}" + (f" {code}" if code else ""))
        if response.status_code != 200:
            error = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
            raise _unavailable(
                lane, ROUTE_PROXY, f"HTTP {response.status_code}: {_said(response)}", response.status_code
            ) from error
        try:
            body = response.json()
        except ValueError as exc:
            raise SnapshotRouteUnavailable(lane, ROUTE_PROXY, "a 200 whose body is not JSON") from exc
        return _proxy_reply(lane, table, body)

    # ── Hugging Face ────────────────────────────────────────────────────────────────────────────

    def _ask_hf(self, lane: str, table: str, wanted: _Keys) -> RemoteAnswer:
        pin = self._pinned(lane)
        files = pin.table_files(lane, table)
        #: (request, the files it reads, whether the manifest attests them as that chromosome's alone)
        groups: list[tuple[dict[str, list[Any]], tuple[str, ...], bool]] = []
        for request in _requests(wanted):
            attested = pin.chromosomes.get(request["chrom"][0], ()) if "chrom" in request else ()
            own = tuple(f for f in files if f in set(attested))
            # Only a manifest attests which file holds a chromosome, so only such a lane opens one file.
            # A chromosome it attests no file for is read over the whole table: never an empty answer
            # the table was not asked for (`@unreachable-not-absent`).
            groups.append((request, own, True) if own else (request, files, False))
        # The schema is read off a file the lookup opens anyway, so a chromosome's lookup reads no other.
        schema = self._schema(lane, pin, table, groups[0][1][0])
        position = next((c for c in POSITION_COLUMNS if c in schema), None)
        named = set(wanted.plain) | ({"chrom"} if wanted.positions is not None else set())
        missing = sorted(c for c in named if c not in schema)
        if wanted.positions is not None and position is None:
            missing.append("start")
        if missing:
            raise ValueError(
                f"{lane}/{table} has no column {', '.join(missing)} at {pin.repo}@{pin.revision}"
            )
        rows: list[dict[str, Any]] = []
        for request, group, attested_alone in groups:
            if attested_alone:
                # The manifest attests these files hold this chromosome alone, so the scan filters by
                # position only (reading no `chrom` column, half the requests) and the chromosome is
                # checked on the rows that came back, so a file holding more cannot answer for it.
                forms = set(_chrom_forms(request["chrom"][0]))
                by_position = {k: v for k, v in request.items() if k != "chrom"}
                found = self._hf_rows(lane, table, pin, group, by_position, schema, position)
                rows.extend(row for row in found if str(row.get("chrom")) in forms)
            else:
                rows.extend(self._hf_rows(lane, table, pin, group, request, schema, position))
        return RemoteAnswer(
            rows=_stable(rows), route=RemoteRoute(ROUTE_HF, release=pin.release, revision=pin.revision)
        )

    def _hf_rows(
        self,
        lane: str,
        table: str,
        pin: _Pin,
        files: Sequence[str],
        request: Mapping[str, list[Any]],
        schema: Mapping[str, str],
        position: str | None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = [[self._file_url(pin, f) for f in files]]
        for column, values in request.items():
            if column == "start":
                # Integer literals, never bound parameters: a bound integer against the file's own
                # integer type (Ensembl's is UINTEGER) prunes no row group, and one Ensembl position then
                # read the whole chromosome file (66 requests and 65 MB measured on chr19, against 3 and
                # 5.4 MB with literals). `int()` is what makes a literal safe to render.
                clauses.append(f'"{position}" IN ({", ".join(str(int(v)) for v in values)})')
                continue
            compare = REMOTE_LANES[lane].compare(table, column)
            if not compare.cell_exact:
                # The lane's local compare, the same object its keyed function's SQL is built from. A compare
                # that reads only the key (an rsID) takes the plain `IN` below: `_read_as_compared` has read
                # each value already, and `IN` over the column prunes row groups where a function does not.
                clauses.append(compare.predicate(column))
                params.append(compare.parameter(values))
                continue
            asked = (
                [form for v in values for form in _chrom_forms(v)]
                if column == "chrom"
                else [str(v) for v in values]
            )
            if schema[column].endswith("[]"):
                clauses.append(f'list_has_any(CAST("{column}" AS VARCHAR[]), ?)')
                params.append(asked)
            else:
                cell = f'"{column}"' if schema[column] == "VARCHAR" else f'CAST("{column}" AS VARCHAR)'
                clauses.append(f"{cell} IN ({', '.join('?' for _ in asked)})")
                params.extend(asked)
        cursor = pin.connection.cursor()
        try:
            result = cursor.execute(f"SELECT * FROM read_parquet(?) WHERE {' AND '.join(clauses)}", params)
            columns = [d[0] for d in result.description]
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        except (duckdb.IOException, duckdb.InvalidInputException) as exc:
            raise _unavailable(lane, ROUTE_HF, _hub_cause(exc), getattr(exc, "status_code", None)) from exc
        finally:
            cursor.close()

    def _schema(self, lane: str, pin: _Pin, table: str, path: str) -> dict[str, str]:
        """`table`'s columns and their duckdb types, read once per pin from its first file's footer."""
        with self._lock:
            known = pin.schemas.get(table)
        if known is not None:
            return known
        cursor = pin.connection.cursor()
        try:
            described = cursor.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [self._file_url(pin, path)]
            ).fetchall()
        except (duckdb.IOException, duckdb.InvalidInputException) as exc:
            raise _unavailable(lane, ROUTE_HF, _hub_cause(exc), getattr(exc, "status_code", None)) from exc
        finally:
            cursor.close()
        schema = {str(name): str(kind) for name, kind, *_ in described}
        with self._lock:
            pin.schemas[table] = schema
        return schema

    def _file_url(self, pin: _Pin, path: str) -> str:
        return remote_url(self.hf_base_url, "datasets", pin.repo, "resolve", pin.revision, path)

    def _pinned(self, lane: str) -> _Pin:
        """The lane's pin, read once per holder under the lock: its commit, files, label and connection."""
        with self._lock:
            pin = self._pins.get(lane)
            if pin is not None:
                return pin
            pinning = self._pin_locks.setdefault(lane, threading.Lock())
        # The lane's own lock, so one lane's slow first read does not hold up another lane's queries.
        with pinning:
            with self._lock:
                pin = self._pins.get(lane)
            if pin is not None:
                return pin
            pin = self._pin(lane)
            # Made in flight, so `close()` is still waiting for this lookup and closes the pin after it.
            with self._lock:
                self._pins[lane] = pin
            return pin

    def _hub_get(self, lane: str, url: str) -> httpx.Response:
        try:
            response = self._hub.get(url)
        except httpx.HTTPError as exc:
            raise SnapshotRouteUnavailable(lane, ROUTE_HF, f"{type(exc).__name__}: {exc}") from exc
        return response

    def _pin(self, lane: str) -> _Pin:
        repo = SNAPSHOT_REPO_IDS[lane]
        # The extension first: a box without it spends no Hub quota finding that out.
        connection = self._connect(lane)
        try:
            return self._read_pin(lane, repo, connection)
        except BaseException:
            connection.close()
            raise

    def _read_pin(self, lane: str, repo: str, connection: duckdb.DuckDBPyConnection) -> _Pin:
        response = self._hub_get(
            lane, remote_url(self.hf_base_url, "api/datasets", repo, "revision", HF_PINNED_BRANCH)
        )
        if response.status_code != 200:
            error = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
            raise _unavailable(
                lane, ROUTE_HF, _hub_cause(error) + f" (the revision of {repo})", response.status_code
            ) from error
        try:
            listing = response.json()
            revision = str(listing["sha"])
            files = tuple(str(sibling["rfilename"]) for sibling in listing["siblings"])
        except (ValueError, KeyError, TypeError) as exc:
            raise SnapshotRouteUnavailable(
                lane, ROUTE_HF, f"the revision of {repo} could not be read"
            ) from exc
        release: str | None = None
        if RELEASE_FILENAME in files:
            record = parse_release(
                self._hub_file(lane, repo, revision, RELEASE_FILENAME),
                source=f"{repo}@{revision}/{RELEASE_FILENAME}",
            )
            release = ((record.dataset or "").strip() or None) if record is not None else None
        chromosomes: dict[str, tuple[str, ...]] = {}
        if SNAPSHOT_MANIFEST_FILENAME in files:
            manifest = self._manifest(lane, repo, revision)
            if manifest is not None:
                release = release or ((manifest.release_id or "").strip() or None)
                by_chrom: dict[str, list[str]] = {}
                for entry in manifest.files or ():
                    if (
                        entry.chrom
                        and entry.path.startswith(f"{SNAPSHOT_DATA_DIRNAME}/")
                        and entry.path in files
                    ):
                        by_chrom.setdefault(_bare_chrom(entry.chrom), []).append(entry.path)
                chromosomes = {chrom: tuple(paths) for chrom, paths in by_chrom.items()}
        logger.info("%s: pinned %s at revision %s, release %s", lane, repo, revision, release)
        return _Pin(repo, revision, files, release, chromosomes, connection)

    def _hub_file(self, lane: str, repo: str, revision: str, path: str) -> bytes:
        response = self._hub_get(
            lane, remote_url(self.hf_base_url, "datasets", repo, "resolve", revision, path)
        )
        if response.status_code != 200:
            error = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
            raise _unavailable(
                lane, ROUTE_HF, _hub_cause(error) + f" ({path} of {repo})", response.status_code
            ) from error
        return response.content

    def _manifest(self, lane: str, repo: str, revision: str) -> SnapshotManifest | None:
        content = self._hub_file(lane, repo, revision, SNAPSHOT_MANIFEST_FILENAME)
        try:
            return SnapshotManifest.model_validate_json(content)
        except ValidationError:
            logger.warning(
                "%s: %s@%s/%s could not be read; it attests no file",
                lane,
                repo,
                revision,
                SNAPSHOT_MANIFEST_FILENAME,
            )
            return None

    def _connect(self, lane: str) -> duckdb.DuckDBPyConnection:
        """A connection that reads over HTTP with `httpfs` loaded from the local install, never fetched.

        Auto-install is off: duckdb would otherwise download the extension from its own repository, in
        C++, past every fence. No retry inside a call (decision 4), and the HTTP and parquet metadata
        caches on, which is safe because every URL names a commit.
        """
        connection = duckdb.connect(":memory:")
        try:
            connection.execute("SET autoinstall_known_extensions = false")
            connection.execute("SET autoload_known_extensions = false")
            connection.execute("LOAD httpfs")
        except duckdb.Error as exc:
            connection.close()
            raise SnapshotRouteUnavailable(
                lane,
                ROUTE_HF,
                "duckdb's httpfs extension is not installed here; install it ahead of time "
                "(`python -c \"import duckdb; duckdb.connect().install_extension('httpfs')\"`)",
            ) from exc
        try:
            connection.execute("SET http_retries = 0")
            connection.execute("SET enable_http_metadata_cache = true")
            connection.execute("SET parquet_metadata_cache = true")
            if self._hf_token:
                secret = self._hf_token.replace("'", "''")
                scope = self.hf_base_url.replace("'", "''")
                connection.execute(f"CREATE SECRET hub (TYPE http, BEARER_TOKEN '{secret}', SCOPE '{scope}')")
        except duckdb.Error as exc:
            connection.close()
            raise SnapshotRouteUnavailable(
                lane, ROUTE_HF, f"the duckdb connection could not be configured ({type(exc).__name__})"
            ) from exc
        return connection


def _error_code(response: httpx.Response) -> str | None:
    """The proxy's error code, from `{"detail": {"error": …}}` or `{"error": …}`; `None` when absent."""
    try:
        body = response.json()
    except ValueError:
        return None
    detail = body.get("detail", body) if isinstance(body, dict) else None
    code = detail.get("error") if isinstance(detail, dict) else None
    return str(code) if code else None


def _said(response: httpx.Response) -> str:
    return response.text.strip()[:400] or "(empty body)"


def _agreed(lane: str, what: str, values: Sequence[Any]) -> str | None:
    """The one value every reply states, else `None`: two replies disagreeing withhold it, said in the log, and
    a reply stating none withholds it too (the unknown arm). `what` names the values, plural, for the log."""
    stated = {str(v) for v in values if v}
    if len(stated) > 1:
        logger.warning(
            "%s: the proxy's replies to one lookup state %d %s (%s); withheld",
            lane,
            len(stated),
            what,
            ", ".join(sorted(stated)),
        )
        return None
    if stated and any(not v for v in values):
        return None
    return next(iter(stated), None)
