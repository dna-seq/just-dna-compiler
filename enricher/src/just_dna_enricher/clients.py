"""The network-client bundle a session reuses, `LookupClients`, and its derived field roster.

**A leaf module (0.9).** It imports the client types it names and nothing that reads them: not
`lookup`, not `enrich`, not a drafter. `lookup` reaches `enrich.orchestration` through its drafters,
so while the bundle lived in `lookup`, `enrich` could not name it at module level. `lookup` imports
both names from here, so `just_dna_enricher.lookup.LookupClients` and `lookup.CLIENT_FIELDS` stay
importable and are the same objects.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field, fields

from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.eutils import EutilsClient
from just_dna_enricher.gnomad import GnomadClient
from just_dna_enricher.grch37 import Grch37Client
from just_dna_enricher.identifiers import OntologyClient
from just_dna_enricher.literature import CrossrefClient, EuropePmcClient, PmcIdConverterClient


@dataclass
class LookupClients:
    """The network clients a lookup session reuses. Every one is optional and lazily built.

    Held by the caller rather than made per call, because each owns a `PacingGate` and an
    `httpx.Client`: a fresh one per question discards the rate-limit state that keeps gnomAD from
    refusing us, and reopens a connection for a single request.

    **One lazy path, and it is the same for every field (S92).** A leg that finds its field unset
    calls `ensure`, which builds the client under a lock, stores it on the bundle and returns it — so
    an unfilled field is paced from the first call on, exactly as a filled one is, and the bundle
    closes it in `close()`. Two of the eight legs used to do that and six built a per-request client
    they closed in a `finally`, which discarded the pacing state this docstring says to keep; a host
    filling six fields and leaving `pmc_idconv` unset had unpaced egress on one leg and nothing at
    the call site to say which. The distinction is gone rather than documented.

    **`enrich(clients=…)` reads four fields and fills none (0.9, RM404).** It reads `ensembl`, `gnomad`,
    `grch37` and `eutils`; a field left unset is built for that run and closed by it, as with no bundle,
    and is never stored here, so the lazy path above is `lookup`'s, not `enrich`'s.

    **A bundle a `lookup_*` call builds for itself is that call's to close.** Hold one yourself for a
    session; pass none for a one-shot question and the call closes what it opened.

    A hosted CPIC draft is not in here on purpose: `pgx_draft.draft_gene` takes an injected
    `client=`, so a host shares pacing by holding one `CpicClient` and passing it, and a field here
    that nothing in `lookup` reads would be a promise `lookup` cannot keep.
    """

    gnomad: GnomadClient | None = None
    eutils: EutilsClient | None = None
    europepmc: EuropePmcClient | None = None
    crossref: CrossrefClient | None = None
    pmc_idconv: PmcIdConverterClient | None = None
    ontology: OntologyClient | None = None
    ensembl: EnsemblResolver | None = None
    grch37: Grch37Client | None = None
    # Not part of the value, and every bundle gets its own: `ensure` mutates a caller-shared
    # dataclass, and a server running its blocking work through a thread pool shares one bundle by
    # following our own advice (the same reason `PacingGate` grew a lock, S15).
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def ensure[T](self, name: str, factory: Callable[[], T]) -> T:
        """The client in field `name`, built by `factory` on first use and kept on the bundle.

        `name` is checked against the dataclass's own fields before anything is set: a plain
        dataclass accepts `setattr(self, "gnomd", …)` silently, and a typo here would build a client
        per call forever while looking exactly like the lazy path."""
        if name not in CLIENT_FIELDS:
            raise AttributeError(f"LookupClients has no client field {name!r}; fields: {CLIENT_FIELDS}")
        with self._lock:
            client = getattr(self, name)
            if client is None:
                client = factory()
                setattr(self, name, client)
            return client

    def close(self) -> None:
        """Close every client on the bundle — walked off the fields, never a hand-kept list."""
        for name in CLIENT_FIELDS:
            closer = getattr(getattr(self, name), "close", None)
            if closer is not None:
                closer()


#: The client fields of `LookupClients`, derived rather than listed (`@registry-completeness`).
CLIENT_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(LookupClients) if not f.name.startswith("_"))
