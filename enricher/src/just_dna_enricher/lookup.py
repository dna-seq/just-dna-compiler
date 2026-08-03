"""Authoring lookups — answer an author's question about a variant or a citation (0.5).

The network half of the authoring surface. `just_dna_compiler.hints` inspects rows using nothing but
the module's own bytes; this module adds the facts that need a reference, in the same report shape.

**It writes nothing — not a file, not a cell.** Every pass in this package that *does* write does so
into a sidecar (`resolution.csv`, `frequencies.csv`, …) after a deliberate command. A lookup is a
question, and its answers come back as `hints.Alteration`s with `applied=False` and a `refusal`
naming why the value is the author's to type.

That refusal is not fastidiousness. Almost every fact here is cross-examined later by a check that
only works because the author wrote the value *independently*: `resolution._verify` compares an
authored coordinate against the table, `sequences.verify_reference_alleles` compares an authored
`ref` against the genome, `literature._doi_conflicts` compares an authored DOI against the registry.
Supplying the cell from the same oracle the checker consults turns each into a tautology — and for an
rsid-only row `_verify` does not run at all, so the row would go from honestly unverified to
apparently verified. `literature` already reasons this way about one field: it asks Crossref about
the **authored** DOI because the derived one "exists by construction".

**Clients are injected and reused.** Each carries its own `PacingGate` — gnomAD is one request per
six seconds, ten per minute — so constructing a client per question throws away both the pacing state
and the connection pool. Hold one `LookupClients` for a session.

Offline is a first-class answer, not a failure: a check that could not run reports `unchecked`, never
`absent`. `None` is not `False` anywhere in this file.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import duckdb
from just_dna_compiler.hints import Alteration, Finding

from just_dna_enricher.clinvar import lookup_clin_sig
from just_dna_enricher.clinvar import lookup_loci as clinvar_lookup_loci
from just_dna_enricher.eutils import EutilsClient, is_missing
from just_dna_enricher.gnomad import GnomadClient
from just_dna_enricher.identifiers import (
    GeneStatus,
    OntologyClient,
    RsidStatus,
    TraitStatus,
    check_rsids,
)
from just_dna_enricher.literature import CrossrefClient, EuropePmcClient, _identifiers
from just_dna_enricher.locations import resolve_clinvar_reference, resolve_ensembl_reference
from just_dna_enricher.resolver import lookup_loci

logger = logging.getLogger(__name__)


def _brief(exc: Exception) -> str:
    """A duckdb binder error carries the whole failing query; a hint wants only the reason."""
    return str(exc).strip().splitlines()[0]

#: Why each looked-up column is reported rather than written. Mirrors `hints.REDUNDANCY_BEARING`,
#: which names the check that would be spent; this names the reason in the report's own vocabulary.
_REFUSAL_BY_COLUMN: dict[str, str] = {
    "rsid": "identity_bearing",
    "chrom": "redundancy_bearing",
    "start": "redundancy_bearing",
    "ref": "redundancy_bearing",
    "alts": "redundancy_bearing",
    "clin_sig": "redundancy_bearing",
    "doi": "redundancy_bearing",
    "trait_efo_id": "intent_bearing",
    "gene": "intent_bearing",
}


@dataclass
class LookupClients:
    """The network clients a lookup session reuses. Every one is optional and lazily built.

    Held by the caller rather than made per call, because each owns a `PacingGate` and an
    `httpx.Client`: a fresh one per question discards the rate-limit state that keeps gnomAD from
    refusing us, and reopens a connection for a single request."""

    gnomad: Optional[GnomadClient] = None
    eutils: Optional[EutilsClient] = None
    europepmc: Optional[EuropePmcClient] = None
    crossref: Optional[CrossrefClient] = None
    ontology: Optional[OntologyClient] = None

    def close(self) -> None:
        for client in (self.gnomad, self.eutils, self.europepmc, self.crossref, self.ontology):
            closer = getattr(client, "close", None)
            if closer is not None:
                closer()


@dataclass
class VariantHint:
    """What is known about one variant, and what of it is the author's to write.

    `loci` is the uniform locus shape every link in this package returns —
    `{chrom, start, ref, alts}` with `start` 1-based and `alts` comma-joined."""

    rsid: Optional[str] = None
    rsid_status: Optional[RsidStatus] = None
    loci: list[dict] = field(default_factory=list)
    rsid_candidates: list[str] = field(default_factory=list)
    populations: list[dict] = field(default_factory=list)
    clin_sig: list[dict] = field(default_factory=list)
    vrs_id: Optional[str] = None
    findings: list[Finding] = field(default_factory=list)
    alterations: list[Alteration] = field(default_factory=list)
    checked: set[str] = field(default_factory=set)

    @property
    def ambiguous(self) -> bool:
        """More than one locus, or more than one rsID at a position — the author must choose."""
        return len(self.loci) > 1 or len(self.rsid_candidates) > 1

    def __str__(self) -> str:
        where = f"{len(self.loci)} locus/loci" if self.loci else "no locus found"
        return f"{self.rsid or '(position)'}: {where}, {len(self.findings)} finding(s)"


@dataclass
class CitationHint:
    """What is known about one citation. Every existence answer is tri-state."""

    pmid: Optional[str] = None
    doi: Optional[str] = None
    pmid_exists: Optional[bool] = None
    doi_exists: Optional[bool] = None
    registry_doi: Optional[str] = None
    pmcid: Optional[str] = None
    open_access: Optional[bool] = None
    abstract_available: Optional[bool] = None
    findings: list[Finding] = field(default_factory=list)
    alterations: list[Alteration] = field(default_factory=list)

    def __str__(self) -> str:
        return f"pmid={self.pmid} exists={self.pmid_exists} doi={self.doi} exists={self.doi_exists}"


def _advisory(column: str, value: str, source: str, note: str) -> Alteration:
    """An answer the author must type themselves. `applied=False`, always."""
    return Alteration(
        row=0,
        column=column,
        before="",
        after=value,
        kind="advisory",
        applied=False,
        source=source,
        refusal=_REFUSAL_BY_COLUMN.get(column, "redundancy_bearing"),
        note=note,
    )


def lookup_variant(
    *,
    rsid: Optional[str] = None,
    chrom: Optional[str] = None,
    start: Optional[int] = None,
    ref: Optional[str] = None,
    alts: Optional[str] = None,
    ambiguity: bool = False,
    frequencies: bool = False,
    offline: bool = False,
    ensembl_cache: Optional[Path] = None,
    clinvar_cache: Optional[Path] = None,
    clients: Optional[LookupClients] = None,
) -> VariantHint:
    """Answer "what is this variant?" — validity, coordinates, alleles, frequencies, clinical calls.

    Give an `rsid`, a coordinate, or both. Nothing is written and nothing is decided: a one-to-many
    rsID returns every locus rather than picking one, and a position matching several rsIDs returns
    every candidate. `ambiguity=True` adds the explicit warning; the candidates are always returned,
    because hiding them would be a decision too.

    `frequencies=True` is opt-in because it costs a paced gnomAD round trip (one per six seconds).
    """
    hint = VariantHint(rsid=rsid)
    clients = clients or LookupClients()

    _lookup_from_cache(hint, rsid, chrom, start, ref, alts, ensembl_cache, clinvar_cache)
    if not offline:
        _check_rsid_currency(hint, rsid, clients)
        if frequencies:
            _lookup_frequencies(hint, clients)
    else:
        hint.findings.append(
            Finding(None, None, "info", "offline: rsID currency and frequencies were not checked")
        )

    _lookup_clin_sig(hint, clinvar_cache)
    if hint.ambiguous and ambiguity:
        hint.findings.append(
            Finding(
                None,
                None,
                "warning",
                f"ambiguous: {len(hint.loci)} locus/loci and {len(hint.rsid_candidates)} rsID "
                f"candidate(s). Reported, never picked — a pick among equals is not a finding",
            )
        )
    _offer_coordinates(hint)
    return hint


def _lookup_from_cache(
    hint: VariantHint,
    rsid: Optional[str],
    chrom: Optional[str],
    start: Optional[int],
    ref: Optional[str],
    alts: Optional[str],
    ensembl_cache: Optional[Path],
    clinvar_cache: Optional[Path],
) -> None:
    """The offline links: the Ensembl snapshot, then ClinVar, in `enrich()`'s own order.

    Each reference gets **its own** lookup — the two are signature-identical but read different
    tables, and pointing the Ensembl one at a ClinVar snapshot asks for columns that are not there."""
    positions = [(chrom, start, ref, alts)] if chrom is not None and start is not None else []
    links = (
        (resolve_ensembl_reference(ensembl_cache), lookup_loci, "ensembl"),
        (resolve_clinvar_reference(clinvar_cache), clinvar_lookup_loci, "clinvar"),
    )
    for reference, lookup, label in links:
        if reference is None:
            continue
        # A snapshot that is present but not the shape this link expects is a normal condition for an
        # advisory lookup (a half-built or older cache), so it becomes a finding rather than an
        # exception at the author. Nothing here is load-bearing enough to fail a question.
        try:
            by_rsid, by_position, warnings = lookup(reference, [rsid] if rsid else [], positions)
        except duckdb.Error as exc:
            hint.findings.append(
                Finding(None, None, "info", f"{label} snapshot at {reference} unreadable: {_brief(exc)}")
            )
            continue
        hint.checked.add(str(reference))
        for locus in by_rsid.get(rsid or "", []):
            if locus not in hint.loci:
                hint.loci.append(locus)
        for candidates in by_position.values():
            for candidate in candidates:
                if candidate not in hint.rsid_candidates:
                    hint.rsid_candidates.append(candidate)
        hint.findings.extend(Finding(None, None, "info", w) for w in warnings)
        if hint.loci:
            break  # first hit wins, the same order `enrich()` uses
    if not hint.loci and not hint.rsid_candidates and not hint.checked:
        hint.findings.append(
            Finding(
                None,
                None,
                "info",
                "no local snapshot found: nothing was looked up offline (see `just-dna-enricher "
                "clinvar build` / the Ensembl cache)",
            )
        )


def _check_rsid_currency(hint: VariantHint, rsid: Optional[str], clients: LookupClients) -> None:
    """dbSNP is the oracle for merge status — Ensembl 400s on some merged ids and would misreport."""
    if not rsid:
        return
    statuses = check_rsids([rsid], client=clients.eutils)
    if not statuses:
        return
    hint.rsid_status = statuses[0]
    if hint.rsid_status.state == "live":
        return
    hint.findings.append(Finding(None, "rsid", "warning", str(hint.rsid_status)))
    if hint.rsid_status.current:
        hint.alterations.append(
            _advisory(
                "rsid",
                hint.rsid_status.current,
                "dbsnp",
                "reported, never written: rewriting an rsID is an identity migration performed by a "
                "network lookup — variant_key would change with no authored edit anywhere",
            )
        )


def _lookup_frequencies(hint: VariantHint, clients: LookupClients) -> None:
    """Population allele counts for the resolved locus. gnomAD serves no `af`; it is ac/an here."""
    single = [
        locus
        for locus in hint.loci
        if locus.get("alts") and "," not in str(locus["alts"])
    ]
    if not single:
        return
    locus = single[0]
    variant_id = f"{locus['chrom']}-{locus['start']}-{locus['ref']}-{locus['alts']}"
    client = clients.gnomad or GnomadClient()
    owned = clients.gnomad is None
    try:
        found = client.fetch_frequencies([variant_id])
    except Exception as exc:  # a lookup is advisory; a gnomAD outage must not raise at the author
        hint.findings.append(Finding(None, None, "info", f"frequencies unchecked: {exc}"))
        return
    finally:
        if owned:
            client.close()
    record = found.get(variant_id)
    if record is None:
        hint.findings.append(
            Finding(None, None, "info", f"gnomAD has no record for {variant_id}")
        )
        return
    hint.vrs_id = record.get("vrs_id")
    for population in record.get("populations", []):
        allele_count, allele_number = population.get("allele_count"), population.get("allele_number")
        hint.populations.append(
            {
                **population,
                # gnomAD deliberately exposes no per-group frequency, so it is computed here rather
                # than read. `None` when the denominator is absent or zero — never a silent 0.0.
                "allele_frequency": (
                    allele_count / allele_number
                    if allele_count is not None and allele_number
                    else None
                ),
            }
        )


def _lookup_clin_sig(hint: VariantHint, clinvar_cache: Optional[Path]) -> None:
    """ClinVar's own call at each resolved allele — advisory in the strongest sense.

    Writing it would have the format adopt ClinVar's clinical opinion, and the charter forbids the
    format arbitrating a clinical dispute (which is why `verify_clin_sig` warns in *both* modes)."""
    reference = resolve_clinvar_reference(clinvar_cache)
    if reference is None:
        return
    alleles = [
        (str(locus["chrom"]), int(locus["start"]), str(locus["ref"]), alt)
        for locus in hint.loci
        if locus.get("ref") and locus.get("alts")
        for alt in str(locus["alts"]).split(",")
        if alt
    ]
    if not alleles:
        return
    try:
        found = lookup_clin_sig(reference, alleles)
    except duckdb.Error as exc:
        hint.findings.append(
            Finding(None, "clin_sig", "info", f"ClinVar snapshot unreadable, clin_sig unchecked: {_brief(exc)}")
        )
        return
    for records in found.values():
        hint.clin_sig.extend(records)
    for record in hint.clin_sig:
        call = record.get("clin_sig")
        if call:
            hint.alterations.append(
                _advisory(
                    "clin_sig",
                    str(call),
                    "clinvar",
                    "ClinVar's own call. Yours is cross-checked against it and the two are allowed "
                    "to differ — the format never arbitrates a clinical dispute",
                )
            )


def _offer_coordinates(hint: VariantHint) -> None:
    """Offer the resolved coordinate as advisory, and say plainly why it is not filled in."""
    if len(hint.loci) != 1:
        return  # more than one locus is a choice, not an answer; zero is nothing to offer
    locus = hint.loci[0]
    for column in ("chrom", "start", "ref", "alts"):
        value = locus.get(column)
        if value in (None, ""):
            continue
        hint.alterations.append(
            _advisory(
                column,
                str(value),
                "snapshot",
                "resolution fills this into resolution.csv, which is where it belongs: authoring it "
                "instead would make the compiler's rsid-vs-coordinate check compare a source with "
                "itself, and for an rsid-only row that check would not run at all",
            )
        )


def lookup_citation(
    *,
    pmid: Optional[str] = None,
    doi: Optional[str] = None,
    offline: bool = False,
    clients: Optional[LookupClients] = None,
) -> CitationHint:
    """Answer "does this citation exist, and what is its other identifier?".

    A paywall hides the *fulltext*, never the PubMed record, so existence is answerable for
    paywalled work. Crossref covers what PubMed does not index at all (preprints, books, datasets).
    """
    hint = CitationHint(pmid=pmid, doi=doi)
    if offline:
        hint.findings.append(
            Finding(None, None, "info", "offline: citation existence was not checked")
        )
        return hint
    clients = clients or LookupClients()
    if pmid:
        _check_pmid(hint, pmid, clients)
    if doi:
        # The **authored** DOI, never a derived one: a DOI the registry just handed over exists by
        # construction, so checking it would answer a question nobody asked.
        crossref = clients.crossref or CrossrefClient()
        hint.doi_exists = crossref.exists(doi)
        if hint.doi_exists is False:
            hint.findings.append(Finding(None, "doi", "warning", f"Crossref has no record of {doi}"))
        elif hint.doi_exists is None:
            hint.findings.append(Finding(None, "doi", "info", "Crossref could not be asked"))
        if clients.crossref is None:
            crossref.close()
    return hint


def _check_pmid(hint: CitationHint, pmid: str, clients: LookupClients) -> None:
    """PubMed existence, plus the DOI and PMC id that arrive free in the same response."""
    eutils = clients.eutils or EutilsClient()
    try:
        records = eutils.esummary("pubmed", [pmid])
    except Exception as exc:
        hint.findings.append(Finding(None, "pmid", "info", f"PubMed could not be asked: {exc}"))
        return
    finally:
        if clients.eutils is None:
            eutils.close()
    record = records.get(pmid)
    if record is None:
        hint.pmid_exists = None  # not asked-and-absent; simply not answered
        return
    hint.pmid_exists = not is_missing(record)
    if not hint.pmid_exists:
        hint.findings.append(
            Finding(None, "pmid", "warning", f"PubMed has no record for PMID {pmid}")
        )
        return
    identifiers = _identifiers(record)
    hint.registry_doi = identifiers.get("doi")
    hint.pmcid = identifiers.get("pmcid")
    _check_availability(hint, pmid, clients)
    if hint.registry_doi and not hint.doi:
        hint.alterations.append(
            _advisory(
                "doi",
                hint.registry_doi,
                "pubmed",
                "PubMed's DOI for this PMID. Not written, because the citation check compares the "
                "DOI you wrote against the registry's — filling it from the registry would compare "
                "the registry with itself",
            )
        )


def _check_availability(hint: CitationHint, pmid: str, clients: LookupClients) -> None:
    """How far a quote check could reach for this paper: fulltext, abstract, or neither.

    Worth answering before an author writes a `provenance_quote`, because a hit and a miss are not
    symmetric — an abstract miss is not a verdict, it is a shorter search. Europe PMC is **not** an
    existence oracle (unknown ids are silently absent), so a miss here leaves the tri-states `None`
    rather than `False`; existence was already settled by PubMed above."""
    europepmc = clients.europepmc or EuropePmcClient()
    try:
        found = europepmc.lookup([pmid])
    except Exception as exc:
        hint.findings.append(Finding(None, None, "info", f"Europe PMC could not be asked: {exc}"))
        return
    finally:
        if clients.europepmc is None:
            europepmc.close()
    record = found.get(pmid)
    if record is None:
        return
    hint.open_access = record.get("is_open_access")
    hint.abstract_available = bool(record.get("abstract"))
    if hint.open_access is False and hint.abstract_available:
        hint.findings.append(
            Finding(
                None,
                None,
                "info",
                "not open access: a quote can only be checked against the abstract, where a miss is "
                "not a verdict",
            )
        )


def lookup_trait(curie: str, *, clients: Optional[LookupClients] = None) -> TraitStatus:
    """Is this trait CURIE current, obsolete, or unknown? (OLS4; `unchecked` when it cannot be asked.)"""
    clients = clients or LookupClients()
    client = clients.ontology or OntologyClient()
    try:
        return client.trait(curie)
    finally:
        if clients.ontology is None:
            client.close()


def lookup_gene(symbol: str, *, clients: Optional[LookupClients] = None) -> GeneStatus:
    """Is this gene symbol approved or retired? (HGNC exact endpoints, never the fuzzy search.)"""
    clients = clients or LookupClients()
    client = clients.ontology or OntologyClient()
    try:
        return client.gene(symbol)
    finally:
        if clients.ontology is None:
            client.close()


def as_report_rows(hint: Any) -> list[dict[str, Any]]:
    """A hint's advisory alterations as plain dicts, for a JSON surface or a table.

    Deliberately not a `HintReport`: that type carries `csv_out`, and a lookup has no CSV to emit —
    it answers a question about a value, not about a row a caller handed over."""
    return [
        {
            "column": alteration.column,
            "value": alteration.after,
            "source": alteration.source,
            "applied": alteration.applied,
            "refusal": alteration.refusal,
            "note": alteration.note,
        }
        for alteration in getattr(hint, "alterations", [])
    ]
