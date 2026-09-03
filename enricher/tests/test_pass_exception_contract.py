"""A pass raises its own error type, and a client's type never escapes one (RM101, S37).

This is `@client-exception-contract` one layer up, and it is the layer RM97 did not reach. That item
made each *client* raise its own type instead of `httpx`'s; a caller of a *pass* is one step further
out and was told, by the pass's own docstring and by the CLI handler beside it, to catch the pass's
type. Five call sites let the client's type straight through a `try/finally` with no `except`, so the
handler was silent for exactly the failure it was written for.

**The reported half and the found half.** just-dna-registry reported `frequencies`, `literature` and
`clingen`. Walking the passes instead of the report found `gene_metrics` and both `identifiers` sites
carrying the same defect, and `gene_validity` carrying the same conflation as `clingen`. That ratio —
three named, three more underneath — is why this file walks a registry rather than pinning the sites
somebody happened to notice. `@registry-completeness`.

**Two contracts, and they are separate claims.** A pass must (1) let no foreign exception type out,
and (2) make "the source could not be reached" distinguishable from "your data is wrong" by *type*,
not by `exc.__cause__` and not by matching a message — neither of which is pinned as an API, so a
reword would silently flip a consumer's verdict from "unchecked" to "your table is broken".
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import just_dna_enricher.gene_metrics as gene_metrics_module
import pytest
from just_dna_enricher.clingen import ClinGenError, ClinGenUnavailable
from just_dna_enricher.eutils import EutilsError
from just_dna_enricher.frequencies import (
    FrequencyEnrichmentError,
    FrequencyUnavailable,
    enrich_frequencies,
)
from just_dna_enricher.gene_metrics import (
    GeneMetricsEnrichmentError,
    GeneMetricsUnavailable,
    enrich_gene_metrics,
)
from just_dna_enricher.gene_validity import GeneValidityError, GeneValidityUnavailable
from just_dna_enricher.gnomad import GnomadError
from just_dna_enricher.identifiers import (
    IdentifierCheckError,
    IdentifierUnavailable,
    check_identifiers,
    check_rsids,
)
from just_dna_enricher.literature import (
    LiteratureEnrichmentError,
    LiteratureUnavailable,
    enrich_literature,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _module(tmp_path: Path, name: str = "hboc_palb2") -> Path:
    """A real reference example, with the sidecars removed that would short-circuit a pass.

    Removed rather than mocked around: a pass whose output file is already complete never reaches its
    client at all, so leaving them would make every case below pass without proving anything.
    """
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    for sidecar in ("frequencies.csv", "literature.csv", "gene_metrics.csv"):
        (spec / sidecar).unlink(missing_ok=True)
    return spec


class _StubGnomad:
    """Raises what the real client raises *after* RM97 — its own type, not `httpx`'s."""

    def fetch_frequencies(self, _ids: list[str]) -> dict:
        raise GnomadError("gnomAD request failed: Server error '503 Service Unavailable'")

    def fetch_gene_constraint(self, _genes: list[str]) -> dict:
        raise GnomadError("gnomAD request failed: Server error '503 Service Unavailable'")

    def close(self) -> None: ...


class _StubEutils:
    def esummary(self, _db: str, _ids: list[str]) -> dict:
        raise EutilsError("eutils request failed: Server error '502 Bad Gateway'")

    def close(self) -> None: ...


class _StubOntology:
    def trait(self, _curie: str) -> object:
        raise IdentifierUnavailable("OLS4 could not be reached: connection refused")

    def gene(self, _symbol: str) -> object:
        raise IdentifierUnavailable("HGNC could not be reached: connection refused")

    def close(self) -> None: ...


@dataclass(frozen=True)
class Case:
    """One pass, and what a caller of it is entitled to.

    `translates` marks the cases where the pass converts a *foreign* type. Where the client already
    raises this module's own type — `check_identifiers` since `OntologyClient` was repaired — the
    pass correctly just propagates, and demanding a `__cause__` there would be demanding a pointless
    re-wrap.

    `prepare` forces the path under test. `enrich_gene_metrics` answers from the constraint snapshot
    when it can and only opens the live link for what the snapshot missed, so without this the case
    passed while never reaching the client at all — a green vacuous test, which is the failure mode
    this file is otherwise about.
    """

    label: str
    call: Callable[[Path], object]
    documented: type
    unavailable: type
    translates: bool = True
    prepare: Callable[[pytest.MonkeyPatch], None] | None = None


def _no_constraint_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """No snapshot provisioned, so the pass must use the live link — a real state, not a contrivance."""
    monkeypatch.setattr(gene_metrics_module, "resolve_constraint_reference", lambda *_a, **_k: None)


PASSES: list[Case] = [
    Case(
        "frequencies.enrich_frequencies",
        lambda spec: enrich_frequencies(spec, write=False, client=_StubGnomad()),
        FrequencyEnrichmentError,
        FrequencyUnavailable,
    ),
    Case(
        "gene_metrics.enrich_gene_metrics",
        lambda spec: enrich_gene_metrics(spec, write=False, client=_StubGnomad()),
        GeneMetricsEnrichmentError,
        GeneMetricsUnavailable,
        prepare=_no_constraint_snapshot,
    ),
    Case(
        "literature.enrich_literature",
        lambda spec: enrich_literature(spec, write=False, eutils=_StubEutils()),
        LiteratureEnrichmentError,
        LiteratureUnavailable,
    ),
    Case(
        "identifiers.check_rsids",
        lambda _spec: check_rsids(["rs334"], client=_StubEutils()),
        IdentifierCheckError,
        IdentifierUnavailable,
    ),
    Case(
        "identifiers.check_identifiers",
        lambda spec: check_identifiers(spec_dir=spec, check_traits=True, check_genes=True,
                                       client=_StubOntology()),
        IdentifierCheckError,
        IdentifierUnavailable,
        translates=False,
    ),
]


@pytest.mark.parametrize("case", PASSES, ids=[c.label for c in PASSES])
def test_a_client_failure_arrives_as_the_passs_own_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: Case
) -> None:
    """The consumer's measurement, as a test.

    Their adapter reads `except FrequencyEnrichmentError: return FrequencyCheck(warnings=[...])` — a
    degradation to report rather than a failed request — and a gnomAD 503 walked past it and ended a
    `POST .../check` with a 500. Our own CLI had the same hole one layer down: `cli.py` prints
    `FREQUENCIES FAILED: {exc}` and exits 1, and on this exact input it printed nothing at all and let
    the exception out.
    """
    if case.prepare is not None:
        case.prepare(monkeypatch)
    spec = _module(tmp_path)
    with pytest.raises(case.documented) as caught:
        case.call(spec)
    assert isinstance(caught.value, case.unavailable), (
        f"{case.label} raised the parent type, so a caller cannot tell a dead source from bad data"
    )
    if case.translates:
        assert caught.value.__cause__ is not None, (
            f"{case.label} dropped the client's exception instead of chaining it"
        )


@pytest.mark.parametrize("case", PASSES, ids=[c.label for c in PASSES])
def test_the_unavailability_type_is_a_subclass_and_not_a_second_exception(case: Case) -> None:
    """P3, additive within a major: an existing `except <Pass>Error` must keep working.

    This is the whole reason the repair is a subclass rather than the obvious translation the report
    proposed and then argued against itself. Translating to a flat type would have flattened "your
    input is wrong" and "the source is down" into one — and worse, the reporter had *already*
    compensated for the leak by catching the client's type, so a flat repair would have broken the
    consumer who filed the item.
    """
    assert issubclass(case.unavailable, case.documented)


def test_every_pass_taking_an_injected_client_is_covered() -> None:
    """Guard the premise, because the guard is what failed last time.

    RM97's coverage guard walked a hand-written tuple of module names and `identifiers` was not in
    it, which is how `OntologyClient` kept the unrepaired shape through a whole release. So this one
    discovers passes by *signature* — a function taking an injected client — rather than by a list
    anybody has to remember to extend.
    """
    import just_dna_enricher

    clientish = {"client", "eutils", "europepmc", "crossref", "resolver", "gnomad_client"}
    discovered: set[str] = set()
    for module_info in pkgutil.iter_modules(list(just_dna_enricher.__path__)):
        module = importlib.import_module(f"just_dna_enricher.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isfunction(obj) and obj.__module__ == module.__name__):
                continue
            if name.startswith("_"):
                continue
            if set(inspect.signature(obj).parameters) & clientish:
                discovered.add(f"{module_info.name}.{name}")

    covered = {case.label for case in PASSES}
    #: Named rather than silently skipped, so each exemption is a decision a reader can dispute.
    exempt = {
        # `GwasError` is both the client's type and the pass's, declared in one module — so there is
        # no foreign type for a caller to fall through, and nothing to translate.
        "gwas.enrich_gwas",
        # Deliberately degrades instead of raising: it catches `GnomadError` under the comment "a
        # last-resort link must not sink the whole enrichment" and logs a warning, and the Ensembl
        # leg answers an unreachable rsID with `None` rather than an exception. Both are the
        # withhold, which is the correct shape and the opposite of the defect here.
        "enrich.enrich",
        # `Grch37Client` raises nothing at all: every httpx path returns `None` or `[]`. There is no
        # exception for these two to translate, and asserting a type would assert the wrong contract.
        "grch37.recover_rsid",
        "grch37.diagnose_wrong_build",
        # Snapshot builders and the drafting surface rather than enrichment passes, and each caller
        # already spells the several types out: `except (CpicError, CpicBuildError)`,
        # `except PharmVarError`, `except (CpicError, *_DRAFT_PRECONDITION_ERRORS)`. Those work
        # today, and they are the *list* shape rather than the type shape — a caller has to know
        # which four to name, which is the drift the report argued against and RM96 is the lesson
        # for. Left alone here on purpose: it is a real question and a wider one than this item,
        # which is about passes whose documented type was silently wrong, not about callers who
        # correctly enumerate a family.
        "cpic_build.build_snapshot",
        "pharmvar_build.build_snapshot",
        "pgx_draft.draft_gene",
        # RM167. Same shape as `enrich.enrich` and the two `grch37` entries above: it catches
        # `LitvarError` per locus and records that locus as `unchecked` with its reason, which is the
        # withhold rather than a leak. There is no pass-level type for a caller to catch because a
        # caller is never asked to — the four tiers ARE the contract, and a run where the index is
        # down still returns a complete report saying so. `LitvarClient` itself is covered in
        # `test_client_exception_contract.py`, where the translation really does happen.
        "litvar.check_literature_coverage",
        # RM160, and the same shape once more: both catch `CivicApiError` per subject and record that
        # subject as `unreachable` with its reason — the withhold rather than a leak, so a run where
        # CIViC is down still returns a complete report saying which variants were never asked about.
        # `CivicCitationsError` exists and is what a caller catches, but it is for this lane's *own*
        # failures (an unreadable licence table, a spec it cannot write into), never for the client's;
        # `CivicApiClient` is covered in `test_client_exception_contract.py`, where the translation
        # really does happen.
        "civic_citations.draft_civic_citations",
        "civic_citations.check_evidence_status_currency",
    }
    uncovered = discovered - covered
    assert uncovered == exempt, sorted(uncovered.symmetric_difference(exempt))


#: `(label, module, parent, subclass, the pass, the sidecar whose invalidity is the local defect)`.
#:
#: These two fetch through a module-level function rather than an injected client, so the signature
#: walk above cannot see them, and their defect was the *conflation* rather than the escape: one type
#: covering "the source could not be fetched" and "the local CSV you handed me will not parse", which
#: are opposite histories. S37 reported ClinGen's; `gene_validity` is its twin and was found by
#: walking, not by report.
CONFLATED = [
    ("clingen", ClinGenError, ClinGenUnavailable, "gene_metrics.csv"),
    ("gene_validity", GeneValidityError, GeneValidityUnavailable, "gene_validity.csv"),
]


@pytest.mark.parametrize("label,parent,unavailable,sidecar", CONFLATED, ids=[c[0] for c in CONFLATED])
def test_an_unfetchable_source_is_a_different_type_from_an_unparsable_local_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str, parent: type,
    unavailable: type, sidecar: str,
) -> None:
    """Both histories driven for real, because the distinction is the whole point of the item.

    A consumer could separate these two only by reading `exc.__cause__` — chained from
    `httpx.HTTPError` for the fetch, raised bare for the table — which is a private detail to depend
    on. Matching the message was the alternative and the reporter rejected it for the right reason:
    neither string is pinned as an API, so a reword would silently flip their verdict from
    "unchecked" to "your table is broken".
    """
    module = importlib.import_module(f"just_dna_enricher.{label}")

    # (1) the source could not be fetched → the subclass.
    def refuse(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(module.httpx, "get", refuse)
    fetch = module.fetch_curation_list if label == "clingen" else module.fetch_validity_export
    with pytest.raises(unavailable) as unreachable:
        fetch("https://example.invalid/list.csv")
    assert unreachable.value.__cause__ is not None

    # (2) a local table that will not parse → the plain parent, and NOT the subclass.
    spec = _module(tmp_path)
    (spec / sidecar).write_text("this,is,not,a,valid,table\n1,2,3\n")
    with pytest.raises(parent) as local:
        if label == "clingen":
            module.enrich_dosage_sensitivity(spec, write=False, curation_text="Gene Symbol\nPALB2\n")
        else:
            module.enrich_gene_validity(spec, write=False, export_text="gene_symbol\nPALB2\n")
    assert not isinstance(local.value, unavailable), (
        f"{label}: an unparsable local table still reads as the source being unreachable"
    )
