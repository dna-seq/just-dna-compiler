"""A batch size below 1 is refused when the settings are built and again where it is read (RM455).

`net.batched` with a size of 0 yields no batch, so a client whose `batch_size` was 0 asked nothing and
answered `{}`, which every caller reads as "no record for any id". The gnomAD and E-utilities settings and
both literature clients never checked it. 0.9 gave its own instance (`EnsemblSettings`, review round 1
item 8) one check run at construction and again by the batched read, since a dataclass field may be set
after it is built; these take the same form.

No test here reaches a network: the refusal comes before any request, and the root conftest would fail a
test that tried one.
"""

from collections.abc import Callable
from typing import Any

import pytest
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.gnomad import GnomadClient, GnomadSettings
from just_dna_enricher.literature import EuropePmcClient, PmcIdConverterClient

#: (the owner the message names, a builder taking `batch_size`).
BUILDERS: list[tuple[str, Callable[[int], Any]]] = [
    ("GnomadSettings", lambda size: GnomadSettings(batch_size=size)),
    ("EutilsSettings", lambda size: EutilsSettings(batch_size=size, api_key="", email="")),
    ("EuropePmcClient", lambda size: EuropePmcClient(batch_size=size)),
    ("PmcIdConverterClient", lambda size: PmcIdConverterClient(batch_size=size, contact_email="")),
]


def _gnomad() -> tuple[Any, Any]:
    client = GnomadClient(settings=GnomadSettings())
    return client, client.settings


def _eutils() -> tuple[Any, Any]:
    client = EutilsClient(settings=EutilsSettings(api_key="", email=""))
    return client, client.settings


def _europepmc() -> tuple[Any, Any]:
    client = EuropePmcClient()
    return client, client


def _idconv() -> tuple[Any, Any]:
    client = PmcIdConverterClient(contact_email="")
    return client, client


#: (the owner the message names, a client and the object holding its `batch_size`, one batched read).
READS: list[tuple[str, Callable[[], tuple[Any, Any]], Callable[[Any], object]]] = [
    ("GnomadSettings", _gnomad, lambda c: c.resolve_rsids(["rs429358"])),
    ("GnomadSettings", _gnomad, lambda c: c.fetch_frequencies(["19-44908684-T-C"])),
    ("GnomadSettings", _gnomad, lambda c: c.fetch_gene_constraint(["APOE"])),
    ("EutilsSettings", _eutils, lambda c: c.esummary("pubmed", ["31452104"])),
    ("EuropePmcClient", _europepmc, lambda c: c.lookup(["31452104"])),
    ("PmcIdConverterClient", _idconv, lambda c: c.resolve(["PMC6707385"])),
]


@pytest.mark.parametrize(("owner", "build"), BUILDERS, ids=[owner for owner, _ in BUILDERS])
@pytest.mark.parametrize("size", [0, -1])
def test_a_batch_size_below_1_is_refused_when_built(
    owner: str, build: Callable[[int], Any], size: int
) -> None:
    with pytest.raises(ValueError, match=rf"^{owner}\.batch_size={size} is below 1"):
        build(size)


@pytest.mark.parametrize(("owner", "build"), BUILDERS, ids=[owner for owner, _ in BUILDERS])
def test_a_batch_size_of_1_is_kept(owner: str, build: Callable[[int], Any]) -> None:
    # The boundary: one id per request is a legal, if slow, setting, and is never refused.
    assert build(1).batch_size == 1


@pytest.mark.parametrize(
    ("owner", "make", "read"),
    READS,
    ids=["gnomad-rsids", "gnomad-frequencies", "gnomad-constraint", "eutils-esummary", "europepmc", "idconv"],
)
def test_a_batch_size_set_to_0_after_construction_is_refused_by_the_read(
    owner: str, make: Callable[[], tuple[Any, Any]], read: Callable[[Any], object]
) -> None:
    client, holder = make()
    holder.batch_size = 0
    with pytest.raises(ValueError, match=rf"^{owner}\.batch_size=0 is below 1"):
        read(client)
