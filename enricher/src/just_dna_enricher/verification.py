"""Recording what a pass CHECKED, so the manifest can say it (RM45).

The enricher is the only tier that can compare authored data against reality, and every such check
already reports itself — to a log line, and onto an `EnrichmentResult` field that dies when the
process exits. `manifest.compilation` inherited none of it, so a module whose clinical calls were
cross-checked against ClinVar and one where the check never ran shipped identical manifests.

This module is the load-merge-write that closes that, deliberately in the shape
`licensing.record_source_terms` already has and for the same reason: RM51 estimated five write sites
for the licence table and found nine, and *a count of call sites is exactly the thing that goes
stale*. One function, so a new pass wires itself in by calling it rather than by growing a private
copy of the merge.

**One proof-of-work per call, which means one per command.** The work is ~0.7s of hashing and it
binds the whole document, so a pass that recorded checks one at a time would pay it per check for no
extra guarantee. `enrich()` therefore collects its records and writes once at the end, `literature`
writes its own three, `clinpgx` its one, and the merge below is what keeps several commands' records
in one document instead of overwriting each other.

**Which commands actually call this — seven of them, covering every member of
`vocab.VALID_VERIFICATION_CHECKS` except the ones whose comment there says RESERVED.** `enrich`
(reference allele, wrong build, clinical significance, rsID currency, rsid↔coordinate, dataset
currency, published refutation, evidence-status currency), `literature` (citation existence, citation
identifier, provenance quote), `check-identifiers` (gene symbol currency, trait currency, gene↔locus
agreement, PGS accession currency, PGS metadata agreement), `clinpgx check`, `clinpgx check-labels`,
`pgx`, `vrs mint`, `check-acmg`, `check-repeat-bands` and `litvar coverage` (one each).

**The counts in that sentence are gone on purpose, and they were wrong when they were there.** It read
"`enrich` (six: …)" while `enrich` emitted seven — RM170's `published_refutation` had landed without
the sentence learning about it, which is the same drift its own next paragraph is about. A number in
prose is a registry nothing iterates (`@registry-completeness`), so the members are named instead and
the grep below is what settles the list.

**Count the call sites before you edit that paragraph, and edit it whenever you add one.** The
sentence it replaces said *"`enrich` (four checks), `literature` (three) and `clinpgx` (one)"* and was
wrong three ways at once — `enrich` emitted five, and `pgx` and `vrs mint` had been wired for a release
without the sentence learning about them. Its own predecessor was wrong the other way, naming
`check-identifiers` as a writer years before it was one, so the merge was machinery tested against a
document no two commands produced. Its successor then said *"fifteen of the seventeen"* and went stale
again the moment a sixteenth member landed, which is why the totals are gone rather than corrected: a
number in prose is a registry nothing iterates (`@registry-completeness`), and *"every member except
the ones marked RESERVED"* is a rule a `grep` settles. A count of call sites is exactly the thing that
goes stale, which is this module's own argument for being one function; the honest version of that
argument is to derive the list with a grep rather than from memory:

```bash
grep -rn 'record_verification(' enricher/src/    # the writers
grep -n  '"[a-z_]*",  *#' schema/src/just_dna_format/vocab.py   # the members, each with its emitter
```
"""

import logging
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_compiler.compiler import authored_input_entries
from just_dna_format.layout import VERIFICATION_JSON, SidecarCollision, sidecar_write_path
from just_dna_format.manifest import Closure, VerificationDoc, VerificationRecord
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow
from just_dna_format.verification import (
    attest,
    merge_records,
    module_binding,
    read_verification,
    write_verification,
)
from just_dna_format.vocab import AUTHORED_SOURCE

from just_dna_enricher.drafting import DRAFT_PROJECTIONS, drafted_unchanged
from just_dna_enricher.licensing import load_sources_file

logger = logging.getLogger(__name__)

#: How many per-row sentences a record's `detail` carries before it becomes a count. The field is
#: prose a human reads, and a module whose whole panel disagrees would otherwise put one sentence per
#: row into `manifest.verification` — the un-aggregated wall this tree collapses everywhere else. The
#: log and the command's own report still name every one.
DETAIL_LIMIT = 5


#: The `checked_source` of a check whose subject is the release each recorded source names, read back
#: against that same source now (`dataset_currency`). One spelling for a check with one leg per source,
#: on both sides, so the record reads `self_consistent` without naming a source it cannot single out.
RECORDED_SOURCE = "recorded_source"

#: The `checked_source` of a check whose subject is an identifier a source reported (`vrs_allele_id`:
#: a source's own `ga4gh:VA.…`, re-minted here). Not `authored` — no author typed it — and not one
#: source, because which source reported it is per row.
REPORTING_SOURCE = "reporting_source"


@dataclass(frozen=True)
class CheckWitness:
    """What a check reads and what it reads it against (RM292) — one entry per emitting check.

    * `checked` — where the values the check reads come from: `authored` (`vocab.AUTHORED_SOURCE`) for
      cells the module's author wrote, or a source when the subject is by construction that source's
      own earlier answer (a currency check). `record_verification` may resolve `authored` further
      against the module's licence table; nothing resolves the others.
    * `witness` — the source(s) the values are compared against, sorted. The same names `source`
      carries where one source answers, because they are the same fact there — the constructors
      refuse a `source` outside this set. Several only where the check has several authorities.
    * `columns` — the authored cells whose drafter's digest could establish them as a copy (the
      `DRAFT_PROJECTIONS` `checked` columns). Empty where no digest covers what the check reads, in
      which case a licence row naming the witness withholds rather than resolves.
    * `tolerance` — the class a tolerance leaves without a verdict, when the check has one. A record
      of a check that ran must then carry `undecided`, and a check with none must not
      (`@tautology-zero`: an abstention that is not counted reads as agreement).
    * `reason` — one sentence on why this is the witness, kept beside the data it explains.
    """

    checked: str
    witness: tuple[str, ...]
    reason: str
    columns: tuple[str, ...] = ()
    tolerance: str | None = None

    @property
    def witness_source(self) -> str:
        """The record's `witness_source`: the authorities `+`-joined in sorted order."""
        return "+".join(sorted(self.witness))


#: **The check roster (RM292): every emitting check states its witness, as data.** Keyed on the
#: `VALID_VERIFICATION_CHECKS` member; `ran()`/`skipped()` read it, so a check with no entry cannot be
#: recorded at all, and `test_check_witness.py` asserts the keys equal the vocabulary's members minus
#: the RESERVED ones. When the checked side and the witness are one source the record reads
#: `self_consistent` — the currency checks below are that by construction.
CHECK_WITNESSES: dict[str, CheckWitness] = {
    # ── `enrich` ──
    "reference_allele": CheckWitness(
        AUTHORED_SOURCE,
        ("seqrepo",),
        "the authored `ref` against the GRCh38 sequence itself — independent, and tolerant by "
        "construction of a misplaced indel anchor, which is a real genome base wherever it sits",
        columns=("ref",),
    ),
    "genome_build_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("ensembl-grch37",),
        "a ref-mismatched authored coordinate against the same position on GRCh37",
    ),
    "clinical_significance": CheckWitness(
        AUTHORED_SOURCE,
        ("clinvar",),
        "the authored `clin_sig` against ClinVar's own call for that allele; a ClinVar-drafted, "
        "unedited column is ClinVar's copy, and the `tautology` skip is that case at the same release",
        columns=("clin_sig",),
    ),
    "published_refutation": CheckWitness(
        AUTHORED_SOURCE,
        ("civic",),
        "the authored `direction` against the refutations CIViC publishes; CIViC's drafter is a "
        "judgement drafter with no digest, so a module drafted from it withholds",
        columns=("direction",),
    ),
    "evidence_status_currency": CheckWitness(
        "civic",
        ("civic",),
        "a curation status CIViC published at drafting against what CIViC says now — the source "
        "against itself, which establishes currency and never the claim",
        columns=("confidence",),
    ),
    "rsid_currency": CheckWitness(
        AUTHORED_SOURCE,
        ("dbsnp",),
        "an authored rsID against dbSNP's merge history (NCBI is the oracle, `@ncbi-merge-oracle`)",
        columns=("rsid",),
    ),
    "rsid_coordinate_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("ensembl",),
        "an authored rsID+coordinate pair against the loci the Ensembl snapshot gives that rsID",
        tolerance=(
            "an indel pair whose position matches none of the snapshot's loci — a re-anchoring can "
            "move it legitimately (RM31), so no verdict is reached and the pair is counted"
        ),
    ),
    "placement_agreement": CheckWitness(
        REPORTING_SOURCE,
        ("clinvar", "clinvar_gkm", "dbsnp", "ensembl"),
        "the placement the run's own link gave an rsID (the Ensembl snapshot, live Ensembl or gnomAD — "
        "per row) against where ClinVar and ClinVar-GKM place it, and, online with the merge check on, "
        "where dbSNP's own record places a snapshot indel neither holds (RM398; Ensembl REST before it); "
        "a ClinVar fill has no independent witness here and is counted with the one-witness class, and "
        "dbSNP against the snapshot is the snapshot against its own upstream, so its agreement is "
        "self-consistent rather than independent (RM267)",
        tolerance=(
            "an indel the witness spells differently, with no reference sequence this run to settle "
            "whether the two spellings are one event — counted, never read as agreement"
        ),
    ),
    "dataset_currency": CheckWitness(
        RECORDED_SOURCE,
        (RECORDED_SOURCE,),
        "the release each licence row records against the release that same source publishes now — "
        "one leg per source, each the source against itself",
        columns=("dataset",),
    ),
    # ── one command each ──
    "variant_impact_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("alphagenome_avi",),
        "a module's variants against the scores AlphaGenome published for them (`alphagenome check`)",
    ),
    "citation_existence": CheckWitness(
        AUTHORED_SOURCE,
        ("crossref", "pubmed"),
        "an authored `pmid` against PubMed and a `doi` against Crossref (`literature`); `source` "
        "names PubMed, whose terms govern the read",
        columns=("pmid", "doi"),
    ),
    "citation_identifier": CheckWitness(
        AUTHORED_SOURCE,
        ("pubmed",),
        "an authored `doi` (or `PMC…` id) against PubMed's own record for that PMID (`literature`)",
        columns=("doi",),
    ),
    "provenance_quote": CheckWitness(
        AUTHORED_SOURCE,
        ("europepmc",),
        "an authored quote or regex against the article's text from Europe PMC (`literature`)",
        columns=("provenance_quote", "provenance_regex"),
    ),
    "allele_function": CheckWitness(
        AUTHORED_SOURCE,
        ("cpic", "pharmvar"),
        "an authored `function_status` against PharmVar and CPIC (`pgx`); the record names the "
        "authorities that answered, and a CPIC leg drafted from CPIC is skipped as a tautology",
        columns=("function_status",),
    ),
    "pgx_evidence_level": CheckWitness(
        AUTHORED_SOURCE,
        ("clinpgx",),
        "an authored `evidence_level` against ClinPGx's own for that annotation (`clinpgx check`)",
        columns=("evidence_level",),
    ),
    "vrs_allele_id": CheckWitness(
        REPORTING_SOURCE,
        ("seqrepo",),
        "a source-reported `ga4gh:VA.…` against the id minted here over the reference sequence (`vrs mint`)",
    ),
    "acmg_secondary_findings": CheckWitness(
        AUTHORED_SOURCE,
        ("acmg",),
        "an authored `acmg_sf` against the published SF gene list (`check-acmg`)",
        columns=("acmg_sf",),
    ),
    "gene_symbol_currency": CheckWitness(
        AUTHORED_SOURCE,
        ("hgnc",),
        "an authored `gene` against HGNC's approved and previous symbols (`check-identifiers`)",
        columns=("gene",),
    ),
    "trait_currency": CheckWitness(
        AUTHORED_SOURCE,
        ("ols4",),
        "an authored `trait_efo_id` against OLS4's obsolete flag and replacement (`check-identifiers`)",
        columns=("trait_efo_id",),
    ),
    "gene_locus_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("hgnc",),
        "an authored `gene` against the chromosome HGNC places it on, beside the row's variant "
        "(`check-identifiers`)",
    ),
    "pgs_accession_currency": CheckWitness(
        AUTHORED_SOURCE,
        ("pgs_catalog",),
        "an authored `pgs_id` against the PGS Catalog's own record for it (`check-identifiers`)",
        columns=("pgs_id",),
    ),
    "pgs_metadata_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("pgs_catalog",),
        "authored training ancestry and cohort against the score record's (`check-identifiers`)",
        columns=("training_ancestry", "training_cohort"),
    ),
    "repeat_band_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("strchive",),
        "an authored repeat-count band table against STRchive's bands (`check-repeat-bands`)",
    ),
    "literature_coverage": CheckWitness(
        AUTHORED_SOURCE,
        ("litvar",),
        "a module's alleles against the papers LitVar indexes for them, at the tier it answered "
        "(`litvar coverage`)",
    ),
    "regulator_label_agreement": CheckWitness(
        AUTHORED_SOURCE,
        ("clinpgx",),
        "an authored gene/allele/drug claim against the regulator labels ClinPGx carries "
        "(`clinpgx check-labels`)",
    ),
}


def _witnessed(
    check: str,
    source: str | None,
    witness_source: str | None,
    undecided: int | None,
    *,
    ran_: bool,
    reported_by: Collection[str] | None = None,
) -> dict:
    """The RM292 fields for a record, from the roster — and the three refusals that keep them honest.

    A `KeyError` for a check the roster does not hold is the mechanism, not an accident: a check that
    cannot state its witness cannot be recorded. `source` must be one of the declared witnesses, the
    override (a multi-authority check naming the ones that answered) a part of them, and a check's
    tolerance decides whether a run must carry `undecided` — a skip may carry one and need not.
    """
    if check not in CHECK_WITNESSES:
        raise KeyError(f"{check!r} has no entry in CHECK_WITNESSES, so it cannot state its witness (RM292)")
    entry = CHECK_WITNESSES[check]
    if source is not None and source not in entry.witness:
        raise ValueError(
            f"{check!r} records source {source!r}, outside the witness its roster entry declares "
            f"({entry.witness_source!r})"
        )
    witness = entry.witness_source
    if witness_source is not None:
        named = witness_source.split("+")
        if not set(named) <= set(entry.witness) or named != sorted(set(named)):
            raise ValueError(
                f"{check!r} names witness {witness_source!r}; it must be a sorted part of "
                f"{entry.witness_source!r}"
            )
        witness = witness_source
    if entry.tolerance is None and undecided is not None:
        raise ValueError(f"{check!r} has no tolerance class, so it has no undecided count to publish")
    if entry.tolerance is not None and ran_ and undecided is None:
        raise ValueError(
            f"{check!r} abstains on a class ({entry.tolerance}); a run must publish the undecided count"
        )
    return {
        "checked_source": _reporting_side(entry, witness, reported_by),
        "witness_source": witness,
        "undecided": undecided,
    }


def _reporting_side(entry: CheckWitness, witness: str, reported_by: Collection[str] | None) -> str | None:
    """The checked side of a `reporting_source` check, named once a reporter is also a witness (RM267).

    `reporting_source` says the values came from whichever source reported each row, which reads
    `independent` against any witness. That stops being true the day a reporter is itself among the
    witnesses — Ensembl REST asked about an Ensembl snapshot placement. Then the one reporter is named,
    so the model derives `self_consistent` (it was the only witness) or withholds (one of several);
    several reporters, one of them a witness, withhold outright. A reporter no witness shares keeps
    `reporting_source`, and the record reads as it did.
    """
    if not reported_by:
        return entry.checked
    if entry.checked != REPORTING_SOURCE:
        raise ValueError(
            f"only a {REPORTING_SOURCE!r} check names its reporters; this one reads {entry.checked!r}"
        )
    if not set(reported_by) & set(witness.split("+")):
        return entry.checked
    return next(iter(reported_by)) if len(set(reported_by)) == 1 else None


def examples(names: Sequence[str], limit: int = DETAIL_LIMIT) -> str:
    """A few names and a count, so a per-row list cannot become the message (the CPIC lesson).

    Here rather than beside one caller, for this module's own stated reason: the second pass that
    wanted it (`identifiers`, RM72) would otherwise have kept a private copy of the aggregation rule,
    and a rule with two copies has one that is about to be wrong.
    """
    shown = ", ".join(names[:limit])
    return shown if len(names) <= limit else f"{shown} and {len(names) - limit} more"


def producer_label() -> str:
    """`just-dna-enricher <version>`, or an honest 'unknown' — mirrors `_compiler_version`."""
    try:
        return f"just-dna-enricher {version('just-dna-enricher')}"
    except PackageNotFoundError:
        return "just-dna-enricher unknown"


def record_verification(
    records: Iterable[VerificationRecord],
    spec_dir: Path,
    *,
    error: type[Exception],
    now: str | None = None,
) -> VerificationDoc | None:
    """Fold this run's check records into the module's attestation and rewrite it.

    Returns the document written, or `None` when there was nothing to record — a run that put no
    check has nothing to say, and writing an empty attestation would create a file asserting that a
    module was checked and nothing was found.

    **Writes to the file it reads** (`layout.sidecar_write_path`), so running this on a module whose
    sidecars live under `derived/` does not leave a second copy at the root — the collision that
    RM49/RM51 made an error, arrived at by following the documented workflow.

    **The binding is recomputed here, from the module's authored bytes as they are right now.** That
    is what makes the record perishable in the way it should be: an author who edits `variants.csv`
    after this ran gets the block dropped at compile with a warning, because the checks were put
    against rows that no longer exist.

    Existing records for checks this run did not put are kept (`verification.merge_records`) while
    the authored bytes stand still — a run that did not ask a question has said nothing about it, and
    dropping the earlier answer would turn "not asked this time" into "never asked", which is the
    collapse this whole item exists to undo. Since RM72 a *skip* this run writes does not displace an
    earlier real answer either, for the same reason one step further out. Both hold only while the
    earlier answer still describes the module's current authored bytes, which is what
    `existing_still_binds` carries.

    **Where the bytes have moved, the document is this run's records alone (RM423).** Every earlier
    record is about rows that no longer exist: a skip's honest "could not ask" wins over it, and a
    check this run did not put is dropped rather than signed under a binding it was never computed
    over — which is what keeps the paragraph above true after any later run, not only after a compile.
    The run logs one warning naming each check it dropped, so the author knows which to put again.

    **An existing closure (RM73) is carried across, but only while the binding holds.** Enrichment
    writes derived sidecars, which are outside the authored set, so the ordinary case is that a run
    here leaves a closed module closed — and it must, or every enrichment would silently un-close one.
    Where the authored bytes *have* moved, the closure is dropped rather than re-bound: re-stamping it
    would have this pass assert on the author's behalf, which is the one thing the deliberate-act
    decision forbids.
    """
    fresh = list(records)
    if not fresh:
        return None
    spec_dir = Path(spec_dir)
    try:
        path = sidecar_write_path(spec_dir, VERIFICATION_JSON)
    except SidecarCollision as exc:
        raise error(str(exc)) from exc

    binding = module_binding(authored_input_entries(spec_dir))
    existing: list[VerificationRecord] = []
    # Whether those existing records are about the bytes being written over now. It gates RM72's
    # skip-does-not-displace-an-answer rule, and it is the same test the closure below applies, for a
    # weaker version of the same reason: an answer over bytes the author has since edited is not an
    # answer this document may keep asserting.
    existing_still_binds = False
    closure: Closure | None = None
    if path.is_file():
        # A document that will not parse is replaced rather than merged into: it records nothing this
        # run can preserve, and refusing would leave an author unable to re-attest without deleting a
        # file by hand. The line says so, because a silently discarded record is the shape of a
        # silent success.
        try:
            previous = read_verification(path)
        except (OSError, ValueError) as exc:
            logger.warning(
                "Could not read the existing %s (%s); this run's records replace it wholesale.",
                path.name,
                exc,
            )
        else:
            existing = previous.records
            existing_still_binds = previous.module_hash == binding
            # The closure (RM73) is carried across only while the authored bytes stand still. This is
            # the never-clobber trap one column over from `SourceRow.dataset` and `draft_digest`: a
            # rebuild that quietly *kept* it would have this pass re-bind a human's "I am finished"
            # to bytes that human never saw — the machine closing the phase behind their back, which
            # is precisely what the deliberate-act decision rules out. Dropped, never re-stamped,
            # because only the author can make this claim again.
            if previous.closure is not None and previous.module_hash == binding:
                closure = previous.closure
            elif previous.closure is not None:
                logger.warning(
                    "%s carried a closure over different authored bytes; it is dropped rather than "
                    "re-bound. Re-close the module once you are finished editing it.",
                    path.name,
                )

    if existing and not existing_still_binds:
        # RM423: over moved bytes `merge_records` keeps this run's records only. Name what that drops,
        # once, because a record that vanishes without a line reads as a check nobody ever put.
        put = {record.check for record in fresh}
        dropped = sorted({record.check for record in existing} - put)
        if dropped:
            logger.warning(
                "%s held %d record(s) put over different authored bytes, not re-signed over these: "
                "%s. Re-run the check(s) to record them again.",
                path.name,
                len(dropped),
                ", ".join(dropped),
            )

    doc = attest(
        # RM292: what each check read is settled against the module as it stands, at the one seam
        # every command writes through, over the records carried across as well as this run's — so no
        # document can sign `authored` over cells its licence table now says came from the witness.
        resolve_witnesses(
            merge_records(existing, fresh, existing_still_binds=existing_still_binds), spec_dir
        ),
        binding,
        producer=producer_label(),
        produced_at=now or now_utc_iso(),
        closure=closure,
    )
    # The format tier's writer, so both tiers spell the file one way.
    write_verification(doc, path)
    logger.info(
        "Verification: attested %d check(s) into %s (nonce %d at %d bits).",
        len(doc.records),
        path.name,
        doc.nonce,
        doc.difficulty,
    )
    return doc


def ran(
    check: str,
    *,
    subjects: int,
    findings: int,
    source: str | None = None,
    release: str | None = None,
    detail: str | None = None,
    witness_source: str | None = None,
    undecided: int | None = None,
    reported_by: Collection[str] | None = None,
    now: str | None = None,
) -> VerificationRecord:
    """A record for a check that RAN, with the denominator it ran over.

    Two constructors rather than one with an optional `skipped`, because the two shapes cannot both
    be filled and the model refuses a record that tries — making the split visible at every call site
    is cheaper than discovering it as a validation error.

    Both sides of the witness come from `CHECK_WITNESSES` (RM292); `witness_source` narrows a
    multi-authority check to the ones that answered, and `undecided` is the tolerance count a tolerant
    check must publish. `reported_by` names the sources a `reporting_source` check's values came from,
    which decides its checked side once one of them is also a witness (`_reporting_side`).
    """
    return VerificationRecord(
        check=check,
        subjects=subjects,
        findings=findings,
        source=source,
        release=release,
        detail=detail,
        checked_at=now or now_utc_iso(),
        producer=producer_label(),
        **_witnessed(check, source, witness_source, undecided, ran_=True, reported_by=reported_by),
    )


def skipped(
    check: str,
    reason: str,
    *,
    detail: str | None = None,
    source: str | None = None,
    undecided: int | None = None,
    reported_by: Collection[str] | None = None,
    now: str | None = None,
) -> VerificationRecord:
    """A record for a check that did NOT run, carrying the machine key and the sentence.

    The sentence is not optional in practice and is optional in the signature: `clinical.tautology_
    reason` writes a good one and it must survive into the record, while `not_requested` needs none.

    The witness is stated on a skip too (RM292): it describes the question, which did not change
    because this run could not put it. `undecided` may ride a skip — a check that reached a verdict on
    nothing can still have abstained on something, and that count is the honest part of the record.
    `reported_by` is `ran`'s: on a skip it names the sources whose values the question was about, so a
    question that includes a reporter's own authority among its witnesses does not read `independent`.
    """
    return VerificationRecord(
        check=check,
        skipped=reason,
        detail=detail,
        source=source,
        checked_at=now or now_utc_iso(),
        producer=producer_label(),
        **_witnessed(check, source, None, undecided, ran_=False, reported_by=reported_by),
    )


def _checked_source(
    entry: CheckWitness,
    witness: str,
    licence: list[SourceRow] | None,
    unchanged: Callable[[str], bool | None],
) -> str | None:
    """Resolve an `authored` side against the licence table, Kleene-style (RM292).

    * an unreadable table → `None`: it established nothing either way;
    * exactly one source whose drafter digest over the cells this check reads still matches → that
      source, the cells being its copy — unless the witness is ALSO named at the `annotation` layer and
      is not that source, because a digest covers the whole table as the last drafter left it, rows
      an earlier draft from the witness put there included;
    * the table names the witness at the `annotation` layer and nothing above settled it, or two
      digests both hold → `None`, withheld: the module drew on the witness and no one can say how much;
    * otherwise → `authored`.

    `unchanged` is `drafting.drafted_unchanged` bound to the module and memoized per source by the
    caller, because it re-reads and re-hashes the drafted table.
    """
    if licence is None:
        return None
    drawn = {row.source for row in licence if row.layer == "annotation"}
    witnesses = set(witness.split("+"))
    copies = [
        source
        for source in sorted(drawn)
        if entry.columns
        and (projection := DRAFT_PROJECTIONS.get(source)) is not None
        and set(entry.columns) <= set(projection.checked)
        and unchanged(source) is True
    ]
    witness_drawn = bool(drawn & witnesses)
    if len(copies) == 1 and (copies[0] in witnesses or not witness_drawn):
        return copies[0]
    if copies or witness_drawn:
        return None
    return AUTHORED_SOURCE


def resolve_witnesses(records: Iterable[VerificationRecord], spec_dir: Path) -> list[VerificationRecord]:
    """Each record's `checked_source` as the module's licence table settles it NOW (RM292).

    Every record whose roster entry reads `authored` is re-settled, the ones carried across from an
    earlier run included: the licence table is outside the authored binding, so a draft since that run
    can have made its cells some source's copy, and a document that kept the older answer would sign
    a side that is no longer true. A currency check's side is the roster's and nothing in a module
    moves it; a record with no witness stated (written before 0.8) is left exactly as it is. The model
    re-derives `independence`, so it cannot outlive the side it rests on.
    """
    records = list(records)
    settles = [
        record.witness_source is not None
        and record.check in CHECK_WITNESSES
        and CHECK_WITNESSES[record.check].checked == AUTHORED_SOURCE
        for record in records
    ]
    if not any(settles):
        return records
    spec_dir = Path(spec_dir)
    licence = load_sources_file(spec_dir)
    memo: dict[str, bool | None] = {}

    def unchanged(source: str) -> bool | None:
        if source not in memo:
            memo[source] = drafted_unchanged(spec_dir, source, licence or [])
        return memo[source]

    resolved: list[VerificationRecord] = []
    for record, settle in zip(records, settles, strict=True):
        if not settle:
            resolved.append(record)
            continue
        checked = _checked_source(CHECK_WITNESSES[record.check], record.witness_source, licence, unchanged)
        if checked == record.checked_source:
            resolved.append(record)
            continue
        data = record.model_dump()
        data.update(checked_source=checked, independence=None)
        resolved.append(VerificationRecord.model_validate(data))
    return resolved
