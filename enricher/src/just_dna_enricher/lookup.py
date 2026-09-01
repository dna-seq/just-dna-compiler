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
from typing import Any

import duckdb
from just_dna_compiler.hints import Alteration, Finding
from just_dna_format.vrs import normalize_chrom

from just_dna_enricher.clinvar import lookup_clin_sig
from just_dna_enricher.clinvar import lookup_loci as clinvar_lookup_loci
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.eutils import EutilsClient, is_missing
from just_dna_enricher.gnomad import GnomadClient
from just_dna_enricher.grch37 import GRCH37_BUILD, Grch37Client, RsidRecovery, recover_rsid
from just_dna_enricher.identifiers import (
    GeneStatus,
    OntologyClient,
    RsidStatus,
    TraitStatus,
    check_rsids,
)
from just_dna_enricher.literature import (
    CrossrefClient,
    EuropePmcClient,
    PmcIdConverterClient,
    _identifiers,
    bibliographic,
)
from just_dna_enricher.locations import (
    resolve_clinvar_reference,
    resolve_ensembl_reference,
    resolve_pubmind_reference,
)
from just_dna_enricher.pubmind_draft import PubMindDraftError, select_by_positions
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
    "pmid": "redundancy_bearing",
    "trait_efo_id": "intent_bearing",
    "gene": "intent_bearing",
}


@dataclass
class LookupClients:
    """The network clients a lookup session reuses. Every one is optional and lazily built.

    Held by the caller rather than made per call, because each owns a `PacingGate` and an
    `httpx.Client`: a fresh one per question discards the rate-limit state that keeps gnomAD from
    refusing us, and reopens a connection for a single request."""

    gnomad: GnomadClient | None = None
    eutils: EutilsClient | None = None
    europepmc: EuropePmcClient | None = None
    crossref: CrossrefClient | None = None
    pmc_idconv: PmcIdConverterClient | None = None
    ontology: OntologyClient | None = None
    ensembl: EnsemblResolver | None = None
    grch37: Grch37Client | None = None

    def close(self) -> None:
        for client in (
            self.gnomad, self.eutils, self.europepmc, self.crossref, self.pmc_idconv,
            self.ontology, self.ensembl, self.grch37,
        ):
            closer = getattr(client, "close", None)
            if closer is not None:
                closer()


@dataclass
class VariantHint:
    """What is known about one variant, and what of it is the author's to write.

    `loci` is the uniform locus shape every link in this package returns —
    `{chrom, start, ref, alts}` with `start` 1-based and `alts` comma-joined."""

    rsid: str | None = None
    rsid_status: RsidStatus | None = None
    loci: list[dict] = field(default_factory=list)
    rsid_candidates: list[str] = field(default_factory=list)
    populations: list[dict] = field(default_factory=list)
    clin_sig: list[dict] = field(default_factory=list)
    #: PubMind's records at each resolved allele — every PVID, never one winner. Empty means
    #: either that the corpus holds nothing there or that no snapshot was consulted, and the two
    #: are told apart by the findings rather than by this list.
    pubmind: list[dict] = field(default_factory=list)
    vrs_id: str | None = None
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
    """What is known about one citation. Every existence answer is tri-state.

    **Existence is not identity, which is why the bibliographic fields are here** (S12). PMIDs are
    densely allocated, so a recalled or invented 8-digit number is very likely to be a real record —
    for a different paper — and `pmid_exists=True` alone therefore cannot catch a fabricated citation.
    Fabrication is a failure of *identity*, so the answer has to name the paper it found and let the
    caller compare it against the one they meant. `title`/`journal`/`year`/`first_author` all arrive in
    the same `esummary` response that answers existence, so this costs no extra request.
    """

    pmid: str | None = None
    doi: str | None = None
    pmid_exists: bool | None = None
    doi_exists: bool | None = None
    registry_doi: str | None = None
    pmcid: str | None = None
    open_access: bool | None = None
    abstract_available: bool | None = None
    # What the record says it is. `None` means the field was absent or the record was never fetched —
    # never "untitled".
    title: str | None = None
    journal: str | None = None
    year: str | None = None
    first_author: str | None = None
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
    rsid: str | None = None,
    chrom: str | None = None,
    start: int | None = None,
    ref: str | None = None,
    alts: str | None = None,
    ambiguity: bool = False,
    frequencies: bool = False,
    offline: bool = False,
    ensembl_cache: Path | None = None,
    clinvar_cache: Path | None = None,
    pubmind_cache: Path | None = None,
    clients: LookupClients | None = None,
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
        # The live coordinate link, in `enrich()`'s own order: caches first, live Ensembl for what
        # they missed. Without it this surface was *silently weaker than the pass it advises on* —
        # `hint variant --rsid rs1799945` answered "not found in Ensembl, position remains unset"
        # for a variant live Ensembl serves at 6:26090951, because the only thing it had ever
        # searched was a local snapshot that did not contain it. An advisory tool that answers "no"
        # where the pass it advises on answers "6:26090951" is worse than one that answers nothing.
        _lookup_live_loci(hint, rsid, clients)
        _check_rsid_currency(hint, rsid, clients)
        if frequencies:
            _lookup_frequencies(hint, clients)
    else:
        hint.findings.append(
            Finding(None, None, "info", "offline: rsID currency and frequencies were not checked")
        )

    _lookup_clin_sig(hint, clinvar_cache)
    _lookup_pubmind(hint, pubmind_cache, (chrom, start, ref, alts))
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
    _state_position_outcome(hint, rsid)
    return hint


def _state_position_outcome(hint: VariantHint, rsid: str | None) -> None:
    """Say once, at the end, whether the rsID ended with a position — the thing no single link knows.

    Each link reports what *it* searched and stops there, because whether the position remains unset
    depends on legs that run after it: a snapshot miss falls through to live Ensembl online and is the
    end of the road offline. The links used to answer that question for themselves, so a payload could
    carry a locus and a finding saying the position was unset in the same breath (S61) — and a reader
    told everywhere to trust findings over bare values reads that run as a failure. At emission time
    the answer is genuinely unknown, which is the third state, so the link withholds it.

    Only `lookup_variant` has both halves, so the consequence is stated here and nowhere else. Guarded
    on `rsid` because a position-only lookup fills `rsid_candidates` and never `loci`: announcing an
    unset position to a caller who supplied one would be the same false sentence with a new subject.
    """
    if not rsid or hint.loci:
        return
    hint.findings.append(Finding(None, None, "info", f"{rsid}: position remains unset"))


def _lookup_from_cache(
    hint: VariantHint,
    rsid: str | None,
    chrom: str | None,
    start: int | None,
    ref: str | None,
    alts: str | None,
    ensembl_cache: Path | None,
    clinvar_cache: Path | None,
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


def _lookup_live_loci(hint: VariantHint, rsid: str | None, clients: LookupClients) -> None:
    """Live Ensembl (V2 GraphQL → V1 REST) for an rsID no local snapshot resolved.

    Runs **only** on a cache miss, so a provisioned snapshot still answers without egress and the
    order matches `enrich()`'s. Reports the source it came from, because a locus from the network and
    a locus from a pinned snapshot are not equally reproducible and the author should know which they
    have. A failure is a finding, never an exception — nothing here is load-bearing enough to fail a
    question.

    **An unreachable Ensembl is reported as unchecked, never as absent (S20).** `resolve_rsid` returns
    `None` for "could not ask" against `[]` for "asked, nothing there", and the two get different
    findings at different severities: `warning` for the failure, because the caller has to decide
    whether to re-run, and `info` for the genuine absence, which is a finished answer. `checked` records
    the source whenever Ensembl actually answered — including when it answered nothing — so the set says
    what was consulted rather than leaving a caller to infer it from a missing element.
    """
    if not rsid or hint.loci:
        return
    if clients.ensembl is None:
        clients.ensembl = EnsemblResolver()
    loci, source = clients.ensembl.resolve_rsid(rsid)
    if loci is None:
        hint.findings.append(
            Finding(
                None, None, "warning",
                f"{rsid}: live Ensembl could not be reached, so its answer is unchecked rather than "
                f"empty — re-run before reading this as an rsID Ensembl does not have",
            )
        )
        return
    hint.checked.add(source or "ensembl-live")
    if not loci:
        hint.findings.append(
            Finding(None, None, "info", f"{rsid}: live Ensembl has no GRCh38 locus for it either")
        )
        return
    hint.loci.extend(loci)
    hint.findings.append(
        Finding(
            None, None, "info",
            f"{rsid}: {len(loci)} locus/loci from live {source} — not from a pinned snapshot, so "
            f"re-running may differ as Ensembl advances",
        )
    )


def _check_rsid_currency(hint: VariantHint, rsid: str | None, clients: LookupClients) -> None:
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


def _lookup_clin_sig(hint: VariantHint, clinvar_cache: Path | None) -> None:
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


def _lookup_pubmind(
    hint: VariantHint,
    pubmind_cache: Path | None,
    authored: tuple[str | None, int | None, str | None, str | None],
) -> None:
    """What PubMind's corpus says at each resolved allele — reported, never written (RM134 § D).

    **It may not fill `clin_sig`, and the reason is sharper here than for ClinVar.** That cell is
    cross-examined by the concordance check, and a hint that filled it from one of the authorities
    being compared would make the check agree with the source it is checking (`@hint-redundancy-bearing`).
    So every call comes back as an `Alteration` with `applied=False` and the redundancy-bearing
    refusal, exactly as ClinVar's does — the same defect `@draft-digest` handles one layer down, and
    here there is no digest to rescue it.

    **Three states, not two.** No snapshot is *nobody asked* — the snapshot is operator-built and
    there is deliberately nothing to download — and it says so rather than answering silently, because
    an empty answer would otherwise read as "PubMind states nothing here". An absence *in* the corpus
    is the third state and is also reported: no paper survived their triage, which is not a benign
    call and not a disagreement.

    A contested coordinate returns every record. Picking one would need an ordering nobody has
    defined, and a hint that picked would be answering a question the snapshot refuses to.
    """
    #: The coordinate the caller typed counts as well as one a lookup resolved, which is a
    #: difference from the ClinVar leg and follows from the source rather than from taste: `hint.loci`
    #: is filled by an **rsID** lookup, and PubMind's channel is coordinate-keyed with most of its
    #: rows carrying no rs-number at all. Asking by coordinate is the case this surface exists for,
    #: so answering nothing there would make the leg unreachable for most of the corpus.
    loci = [*hint.loci]
    chrom, start, ref, alts = authored
    if chrom and start is not None and ref and alts:
        authored_locus = {"chrom": chrom, "start": start, "ref": ref, "alts": alts}
        if authored_locus not in loci:
            loci.append(authored_locus)
    alleles = [
        (str(locus["chrom"]), int(locus["start"]), str(locus["ref"]), alt)
        for locus in loci
        if locus.get("ref") and locus.get("alts")
        for alt in str(locus["alts"]).split(",")
        if alt
    ]
    if not alleles:
        return
    reference = resolve_pubmind_reference(pubmind_cache)
    if reference is None:
        hint.findings.append(
            Finding(
                None, "clin_sig", "info",
                "PubMind was not consulted: no snapshot found ($JUST_DNA_PUBMIND_CACHE, or "
                "--pubmind-cache). It is operator-built and there is none to download, so this is "
                "nobody-asked rather than an absence in their corpus — build one with "
                "`just-dna-enricher pubmind build`",
            )
        )
        return
    # Normalized on BOTH sides, and on every axis the comparison reads. `select_by_positions`
    # normalizes the chromosome at the query and again at its own filter, so the records come back
    # for `chr1` as readily as for `1` — and then this filter compared them against the caller's own
    # spelling, matched nothing, and the branch below reported that as an established absence in
    # PubMind's corpus. A fabricated negative in the exact case this leg exists for: `hint.loci` is
    # filled by an rsID lookup, and PubMind's channel is coordinate-keyed with most of its rows
    # carrying no rs-number, so a coordinate-only query has no normalized locus to fall back on.
    # Bases are upper-cased for the same reason — a lowercase `ref` is the same allele.
    wanted = {
        (normalize_chrom(str(chrom)), start, str(ref).upper(), str(alt).upper())
        for chrom, start, ref, alt in alleles
    }
    try:
        found = select_by_positions(reference, [(chrom, start) for chrom, start, _, _ in alleles])
    except (duckdb.Error, PubMindDraftError) as exc:
        hint.findings.append(
            Finding(
                None, "clin_sig", "info",
                f"PubMind snapshot unreadable, its verdict unchecked: {_brief(exc)}",
            )
        )
        return
    hint.pubmind.extend(
        record
        for record in found
        if (
            normalize_chrom(str(record["chrom"])),
            int(record["start"]),
            str(record["ref"]).upper(),
            str(record["alt"]).upper(),
        ) in wanted
    )
    if not hint.pubmind:
        hint.findings.append(
            Finding(
                None, "clin_sig", "info",
                "PubMind's corpus holds no record at this allele — no paper survived their triage "
                "stage, which is not a benign call and not a disagreement with anybody",
            )
        )
        return
    for record in hint.pubmind:
        call = record.get("clin_sig")
        if not call:
            continue
        hint.alterations.append(
            _advisory(
                "clin_sig",
                str(call),
                "pubmind",
                f"PubMind {record.get('pvid')}: an LLM's reading of the literature "
                f"(confidence {record.get('confidence')}, derivation {record.get('derivation')}). "
                f"Yours is cross-examined against it, so filling it from here would have the check "
                f"agree with the source it is checking",
            )
        )
    calls = {str(r.get("clin_sig") or "") for r in hint.pubmind}
    if len(calls) > 1:
        hint.findings.append(
            Finding(
                None, "clin_sig", "warning",
                f"PubMind's own records disagree here: {', '.join(sorted(calls))} across "
                f"{len(hint.pubmind)} record(s). Their record id keys on the text a model extracted "
                f"rather than on the coordinate, so one position can carry several — every one is "
                f"reported and none is picked",
            )
        )


def _offer_coordinates(hint: VariantHint) -> None:
    """Offer the resolved coordinate as advisory, and say plainly why it is not filled in.

    The `source` is whichever link actually answered. It was hard-coded to `"snapshot"`, which became
    a lie the moment the live link landed: a coordinate from live Ensembl was labelled as coming from
    a pinned snapshot, in the one field an author reads to decide how reproducible the answer is.
    """
    if len(hint.loci) != 1:
        return  # more than one locus is a choice, not an answer; zero is nothing to offer
    locus = hint.loci[0]
    source = next(
        (name for name in sorted(hint.checked) if name.startswith("ensembl-")), "snapshot"
    )
    for column in ("chrom", "start", "ref", "alts"):
        value = locus.get(column)
        if value in (None, ""):
            continue
        hint.alterations.append(
            _advisory(
                column,
                str(value),
                source,
                "resolution fills this into resolution.csv, which is where it belongs: authoring it "
                "instead would make the compiler's rsid-vs-coordinate check compare a source with "
                "itself, and for an rsid-only row that check would not run at all",
            )
        )


@dataclass
class OldAssemblyHint:
    """What GRCh37 dbSNP records at an old coordinate, and why it is not written for you (RM48)."""

    recovery: RsidRecovery
    findings: list[Finding] = field(default_factory=list)
    alterations: list[Alteration] = field(default_factory=list)

    def __str__(self) -> str:
        return str(self.recovery)


def lookup_old_assembly(
    *,
    chrom: str,
    start: int,
    ref: str | None = None,
    alts: str | None = None,
    offline: bool = False,
    clients: LookupClients | None = None,
) -> OldAssemblyHint:
    """Answer "I have an hg19 coordinate — what is its rs-number?".

    The authoring answer to a paper that predates GRCh38. It is **recovery, not liftover**, and the
    difference is the whole design: an rs-number authored into `variants.csv` resolves through the
    ordinary chain into a coordinate `resolution._verify` can cross-examine, while a lifted-over
    position becomes the row's sole identity with nothing to check it against — an
    unverifiable-by-construction identity, which is the hazard class behind this tree's 3,038-row
    off-by-one.

    Nothing is written, and the refusal is the sharpest one in `_REFUSAL_BY_COLUMN`: `rsid` is
    `identity_bearing`, so a machine filling it would be performing an identity migration by network
    lookup, exactly as `_check_rsid_currency` refuses to do for a merged id.

    Several candidates are **reported, never picked** — `--ref`/`--alts` narrow them, and a pick among
    equals is not a finding.
    """
    clients = clients or LookupClients()
    if not offline and clients.grch37 is None:
        clients.grch37 = Grch37Client()
    recovery = recover_rsid(
        chrom, start, ref=ref, alts=alts, client=clients.grch37, offline=offline
    )
    hint = OldAssemblyHint(recovery=recovery)
    level = {
        "recovered": "info",
        "ambiguous": "warning",
        "none": "info",
        "unchecked": "warning",
        "skipped_offline": "info",
    }[recovery.outcome]
    hint.findings.append(Finding(None, None, level, str(recovery)))
    for candidate in recovery.candidates:
        hint.alterations.append(
            _advisory(
                "rsid",
                candidate["rsid"],
                f"dbsnp-{GRCH37_BUILD.lower()}",
                "reported, never written: an rs-number is the row's identity, and filling one from a "
                "lookup migrates variant_key with no authored edit anywhere. Type it into "
                "variants.csv and drop the old coordinate — resolution will place it on the build "
                "the module declares",
            )
        )
    return hint


def lookup_citation(
    *,
    pmid: str | None = None,
    doi: str | None = None,
    pmcid: str | None = None,
    offline: bool = False,
    clients: LookupClients | None = None,
) -> CitationHint:
    """Answer "does this citation exist, and what is its other identifier?".

    A paywall hides the *fulltext*, never the PubMed record, so existence is answerable for
    paywalled work. Crossref covers what PubMed does not index at all (preprints, books, datasets).

    **`pmcid=` is the reverse direction, and it reports rather than fills** (RM50). PubMed and PubMed
    Central number articles independently, `StudyRow.pmid` requires the PubMed one, and a curator
    holding only a PMC id previously had no route to it — the schema refused the cell and named no
    remedy. The resolved PMID comes back as an **advisory** (`applied=False`) the author types
    themselves: writing it into `pmid` would make `literature.exists` compare NCBI against NCBI, the
    same argument that keeps `doi` unfilled. When both are given, the PMC id is additionally checked
    against the PMID's own record, which is where a mismatched pair shows up.
    """
    hint = CitationHint(pmid=pmid, doi=doi)
    if pmcid:
        hint.pmcid = pmcid.strip().upper()
    if offline:
        hint.findings.append(
            Finding(None, None, "info", "offline: citation existence was not checked")
        )
        return hint
    clients = clients or LookupClients()
    resolved_pmid: str | None = None
    if pmcid:
        resolved_pmid = _check_pmcid(hint, hint.pmcid or pmcid, clients, authored_pmid=pmid)
    # The resolved id is then put to PubMed, so the answer names the *paper* rather than only a
    # number: a converter reply a curator cannot check against the article they meant is exactly the
    # existence-is-not-identity failure (S12). The authored `pmid` still wins when there is one.
    if pmid or resolved_pmid:
        _check_pmid(hint, pmid or resolved_pmid or "", clients)
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
    registry_pmcid = identifiers.get("pmcid")
    # An authored PMC id is compared, never overwritten (RM50). A caller who supplied both has two
    # identifiers in mind and the disagreement is the finding; silently replacing one with the other
    # would answer a question nobody asked and hide the one that matters.
    if hint.pmcid and registry_pmcid and hint.pmcid != registry_pmcid.strip().upper():
        hint.findings.append(
            Finding(
                None,
                "pmid",
                "warning",
                f"PMID {pmid} is {registry_pmcid} in PMC, not {hint.pmcid} — the two identifiers "
                f"name different articles",
            )
        )
    elif registry_pmcid:
        hint.pmcid = registry_pmcid
    # Which paper this actually is, from the response that just answered existence (S12). Reported as
    # an `info` finding as well as on the fields, because the caller most likely to have recalled a
    # PMID from memory is the one reading prose rather than JSON.
    citation = bibliographic(record)
    hint.title = citation["title"]
    hint.journal = citation["journal"]
    hint.year = citation["year"]
    hint.first_author = citation["first_author"]
    if hint.title:
        named = ", ".join(
            part for part in (hint.first_author, hint.journal, hint.year) if part
        )
        hint.findings.append(
            Finding(
                None,
                "pmid",
                "info",
                f"PMID {pmid} names: {hint.title!r}" + (f" ({named})" if named else "")
                + " — existence is not identity, so confirm this is the paper you meant.",
            )
        )
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


def _check_pmcid(
    hint: CitationHint, pmcid: str, clients: LookupClients, *, authored_pmid: str | None
) -> str | None:
    """PMCID → PMID through NCBI's id converter (RM50). Reports; never fills.

    Returns the resolved PMID so the caller can go on to ask PubMed *which paper that is* — a
    converter that hands back a number and stops is the same existence-is-not-identity failure S12
    was about, one registry over.

    Three outcomes, as everywhere. A resolved id becomes an **advisory** the author types themselves
    (the `registry_doi` idiom), unless they already supplied a `pmid`, in which case the two are
    compared and a disagreement is the finding. An id PMC answers about with no PubMed id is a real
    negative and is said as one. An id the request never reached leaves everything `None`, because
    "could not ask" and "PMC has no such record" are different claims.
    """
    converter = clients.pmc_idconv or PmcIdConverterClient()
    try:
        resolved = converter.resolve([pmcid])
    except Exception as exc:
        hint.findings.append(
            Finding(None, "pmid", "info", f"the PMC id converter could not be asked: {exc}")
        )
        return None
    finally:
        if clients.pmc_idconv is None:
            converter.close()
    record = resolved.get(pmcid)
    if record is None:
        hint.findings.append(
            Finding(None, "pmid", "info", f"the PMC id converter did not answer about {pmcid}")
        )
        return None
    if not record.in_pmc:
        hint.findings.append(
            Finding(
                None,
                "pmid",
                "warning",
                f"PMC has no record of {pmcid}"
                + (f" ({record.error})" if record.error else ""),
            )
        )
        return None
    pmid = record.pmid
    if pmid is None:
        hint.findings.append(
            Finding(
                None,
                "pmid",
                "warning",
                f"{pmcid} is in PMC but carries no PubMed id, so there is no `pmid` to write for it. "
                f"Cite it by `doi` instead, which studies.csv also accepts",
            )
        )
        return None
    if authored_pmid and authored_pmid.strip() != pmid:
        hint.findings.append(
            Finding(
                None,
                "pmid",
                "warning",
                f"{pmcid} is PMID {pmid}, not the {authored_pmid} written beside it — the two "
                f"identifiers name different articles",
            )
        )
        return None
    hint.alterations.append(
        _advisory(
            "pmid",
            pmid,
            "pmc-idconv",
            f"the PubMed id for {pmcid}. Not written, because the citation check compares the pmid "
            f"you wrote against PubMed's record — filling it from NCBI would compare NCBI with "
            f"itself",
        )
    )
    return pmid


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


def lookup_trait(curie: str, *, clients: LookupClients | None = None) -> TraitStatus:
    """Is this trait CURIE current, obsolete, or unknown? (OLS4; `unchecked` when it cannot be asked.)"""
    clients = clients or LookupClients()
    client = clients.ontology or OntologyClient()
    try:
        return client.trait(curie)
    finally:
        if clients.ontology is None:
            client.close()


def lookup_gene(symbol: str, *, clients: LookupClients | None = None) -> GeneStatus:
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
