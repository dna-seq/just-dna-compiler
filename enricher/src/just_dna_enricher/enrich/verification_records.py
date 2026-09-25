"""The attestation a run writes: `_verification_records` and the release-label and detail helpers
it reads (RM260 split this out of the former single-file `enrich.py`).
"""

from collections.abc import Sequence
from pathlib import Path

from just_dna_format.manifest import VerificationRecord

from just_dna_enricher.civic_citations import EvidenceStatusCheck
from just_dna_enricher.civic_refutation import (
    REFUTATION_BESIDE_CLAIM,
    REFUTATION_WITHOUT_CLAIM,
    RefutationFinding,
)
from just_dna_enricher.clinical import ClinSigConflict
from just_dna_enricher.clinvar import clinvar_dataset_label
from just_dna_enricher.currency import CurrencyCheck, summarize_currency
from just_dna_enricher.grch37 import BuildDiagnosisResult
from just_dna_enricher.identifiers import RsidStatus
from just_dna_enricher.locations import read_release
from just_dna_enricher.resolver import PairCheck
from just_dna_enricher.sequences import RefCheck, summarize_ref_mismatches
from just_dna_enricher.verification import DETAIL_LIMIT, examples, ran, skipped


def _clin_sig_detail(conflicts: Sequence[ClinSigConflict]) -> str | None:
    """Which rows disagreed, grouped by whether the two calls are *opposed* or merely different.

    The check counted its findings and kept none of them (S70). Every conflict reached the logger and
    nothing else, so a record reading `findings: 20, detail: null` left an author able neither to
    defend the twenty nor to correct them — and re-running to see the log again costs the full ClinVar
    comparison. Of the five checks `enrich()` records this was the only one whose findings survived
    nowhere: `reference_allele` and `rsid_coordinate_agreement` carry a `detail`, and `rsid_currency`
    stamps its verdict onto the resolution rows themselves.

    Grouped on `opposed` because that is the distinction the conflict already draws and the one that
    decides what to do: an opposed pair (pathogenic-class against benign-class) is the finding worth
    acting on, a difference is worth knowing. `verification.examples` is the shared aggregation rule,
    so this cannot become the per-row list the CPIC lesson is about.
    """
    if not conflicts:
        return None
    parts = []
    for label, group in (
        ("opposed", [c for c in conflicts if c.opposed]),
        ("differing", [c for c in conflicts if not c.opposed]),
    ):
        if group:
            named = examples([f"{c.variant_key} ({c.authored} vs {c.clinvar})" for c in group])
            parts.append(f"{len(group)} {label}: {named}")
    return "; ".join(parts)


def _civic_release(reference: Path | None) -> str | None:
    """The CIViC snapshot's own release label, or `None` when it names none. Same rule as the rest."""
    return _snapshot_release(reference)


def _refutation_detail(findings: Sequence[RefutationFinding], basis: str | None) -> str | None:
    """What the refutation check found, and **on which basis** — the basis on every run.

    The basis is not decoration here the way a release label is elsewhere. On the `accepted` basis
    this class is empty by construction: every refutation in CIViC that stands against a claim is
    submitted content, and both accepted refutations in the database stand against nothing
    (`docs/probes/CONTRADICTION_CORPORA.md`). So `findings: 0` with no basis beside it says "clear
    water" when what happened was "looked in the half where it cannot appear". A run that found
    nothing still writes the sentence.

    Grouped by code, because the two are different sentences: a source contradicting itself, and a
    module asserting what the source only ever denied.
    """
    stated = f"basis {basis}" if basis else "basis unstated by the snapshot"
    if not findings:
        return f"no authored direction sits beside a published refutation ({stated})"
    parts = []
    for code in (REFUTATION_BESIDE_CLAIM, REFUTATION_WITHOUT_CLAIM):
        group = [f for f in findings if f.code == code]
        if group:
            named = examples([subject.variant_key for finding in group for subject in finding.subjects])
            parts.append(f"{len(group)} {code}: {named}")
    return "; ".join(parts) + f" ({stated})"


def _verification_records(
    *,
    offline: bool,
    verify_ref: bool,
    ref_check: RefCheck,
    build: BuildDiagnosisResult,
    verify_clinsig: bool,
    clin_sig_compared: int | None,
    clin_sig_conflicts: list[ClinSigConflict],
    clin_sig_skip: str | None,
    clin_sig_detail: str | None,
    clinvar_ref: Path | None,
    refutation_findings: list[RefutationFinding],
    refutation_subjects: int | None,
    refutation_skip: str | None,
    refutation_detail: str | None,
    refutation_basis: str | None,
    evidence_status: EvidenceStatusCheck,
    civic_ref: Path | None,
    verify_rsids: bool,
    rsid_subjects: int,
    stale_rsids: list[RsidStatus],
    pairs: PairCheck,
    ensembl_ref: Path | None,
    currency: CurrencyCheck | None,
) -> list[VerificationRecord]:
    """The checks this pass puts, as records `verification.json` can carry (RM45).

    **No count, deliberately (RM243).** This sentence used to open with one, and it was wrong: two
    members were added to the function — `published_refutation` (RM170) and `evidence_status_currency`
    (RM160) — each correctly, and neither moved a figure one line up. ENRICHER.md carried the same stale
    number for the same reason. Neither figure is repeated here even as history, because RM218 found
    that a stale number in quotation marks beside the rule reads, to a skimming reader, exactly like the
    rule; naming the shape is the repair. That shape is `@registry-completeness` — a number beside a
    registry nothing iterates — and this is the third place in the workspace it has been found, after
    `SCHEMAS.md`'s sidecar count and `compiler.py`'s own docstrings. The roster is the `records.append`
    calls below, and `test_enricher_doc_registries.py` walks it against the reference.

    Every count comes from the check that produced it — never re-derived here. That is the whole
    reason `verify_reference_alleles` and `verify_clin_sig` now return what they compared: a
    denominator recomputed beside a check is a denominator that can disagree with it, and a manifest
    field whose two halves disagree is worse than no field.

    `not_requested` is recorded rather than omitted, and the difference matters: an omitted check is
    one nobody has said anything about, while a recorded `not_requested` says this run deliberately
    did not put it. Only the first is what a re-run with the flag on would fill in.
    """
    records: list[VerificationRecord] = []

    # Reference allele. The reason comes off the check, which is the only thing that knows whether the
    # sequence service answered — `offline` is the caller's request, not the outcome.
    if not verify_ref:
        records.append(skipped("reference_allele", "not_requested"))
    elif ref_check.not_checked is not None:
        # The detail follows the reason rather than assuming one: `unsupported` is not a sequence
        # failure at all — the service was fine and the *assembly* has no refget table, so saying
        # "no sequence access" would send an author looking for a network problem they do not have.
        records.append(
            skipped(
                "reference_allele",
                ref_check.not_checked,
                detail=(
                    "this tier has a refget table for GRCh38 only, so an authored ref on another "
                    "assembly has nothing to be compared against (RM15)"
                    if ref_check.not_checked == "unsupported"
                    else "no sequence access this run, so no authored ref was compared"
                ),
                source="seqrepo",
            )
        )
    else:
        records.append(
            ran(
                "reference_allele",
                subjects=ref_check.subjects,
                findings=len(ref_check.mismatches),
                source="seqrepo",
                detail="; ".join(summarize_ref_mismatches(ref_check.mismatches)) or None,
            )
        )

    # Wrong build (RM48). Its subject set is the ref-mismatched rows and nothing else — the pass is
    # *bounded* on purpose (`DEFAULT_DIAGNOSIS_LIMIT`), so `examined` is the honest denominator and
    # `total` is not: recording the larger number would claim rows the pass deliberately did not ask
    # about. `sampled` is why that distinction has to be kept rather than smoothed over, and the detail
    # line says so where it applies.
    #
    # It rides on the reference-allele check having run at all: with no mismatches there is nothing to
    # diagnose, which the pass itself reports as `no_ref_mismatches` — recorded as `nothing_to_check`,
    # because "no row was in scope" is exactly what that member means, and it is emphatically not a
    # finding of zero wrong builds.
    if build.not_checked is not None:
        # **`no_ref_mismatches` alone does not mean the refs agreed.** `diagnose_wrong_build([])`
        # answers it for an empty list whatever emptied the list — a ref check that ran and found
        # nothing, *or* one that never ran at all. Reading it as the first would publish "no authored
        # ref disagreed with the reference" beside a `reference_allele` record saying nothing was
        # compared: one document contradicting itself, with the false half being exactly the
        # answered-absence-versus-unasked-question collapse S20 exists to prevent. So whatever stopped
        # the ref check propagates here, and `nothing_to_check` is reachable only when it really ran.
        # **A permanent limit outranks a transient one, so `unsupported` is tested first.** Offline,
        # a `genome_build: GRCh37` module satisfies both branches — the GRCh37 service was not asked
        # *and* the ref check could not run on an assembly with no refget table — and reporting
        # `offline` there says a re-run with a network would answer it. It would not: the ref check
        # produces no mismatched rows on that build whatever the connectivity, so this pass has no
        # subjects either way. Same ordering rule RM48 applies to its own two readings — the one that
        # does not rest on a transient condition supersedes.
        if ref_check.not_checked == "unsupported":
            reason, detail = (
                "unsupported",
                (
                    "the reference-allele check cannot run on this module's assembly, so no row was ever "
                    "a candidate for a build diagnosis — this is not a connectivity problem and a re-run "
                    "online reports the same thing"
                ),
            )
        elif build.not_checked == "skipped_offline":
            reason, detail = (
                "offline",
                (
                    "the GRCh37 service is the only thing that can tell an old-assembly coordinate from "
                    "a wrong ref, and there is no local GRCh37 data"
                ),
            )
        elif ref_check.not_checked is not None:
            reason, detail = (
                ref_check.not_checked,
                (
                    "the reference-allele check did not run, so there was no mismatched row to diagnose "
                    "— this says nothing about whether the coordinates are on the declared assembly"
                ),
            )
        else:
            reason, detail = (
                "nothing_to_check",
                ("no authored ref disagreed with the reference, so no row needed a build diagnosis"),
            )
        records.append(skipped("genome_build_agreement", reason, detail=detail, source="ensembl-grch37"))
    else:
        records.append(
            ran(
                "genome_build_agreement",
                subjects=build.examined,
                findings=len(build.diagnoses),
                source="ensembl-grch37",
                detail=(
                    f"bounded sample: {build.examined} of {build.total} mismatched row(s) asked about"
                    if build.sampled
                    else None
                ),
            )
        )

    # Clinical significance. `release` is the snapshot's own `release.json` answer, which is what a
    # consumer needs to know *which* ClinVar the calls were weighed against — the same reason a
    # frequency row carries its `dataset`. `None` when the snapshot cannot state one, never a guess.
    clinvar_release = _clinvar_release(clinvar_ref)
    if clin_sig_compared is None:
        # The look-up did not run, and `clin_sig_skip` says which of the closed reasons applies. Keyed
        # on the *count being absent* rather than on re-testing the flags, so the record cannot claim a
        # comparison the pass did not make: there is no path where a look-up ran and left it `None`.
        records.append(
            skipped(
                "clinical_significance",
                clin_sig_skip or "not_requested",
                # The prose reason beside the machine key, never instead of it: `tautology_reason`
                # writes a good sentence and this is where it survives the run.
                detail=clin_sig_detail,
                source="clinvar",
            )
        )
    else:
        records.append(
            ran(
                "clinical_significance",
                subjects=clin_sig_compared,
                findings=len(clin_sig_conflicts),
                source="clinvar",
                release=clinvar_release,
                detail=_clin_sig_detail(clin_sig_conflicts),
            )
        )

    # RM170 — the CIViC refutation leg. No `not_requested` arm: there is no flag, because the check
    # fetches nothing and costs a local read. A missing snapshot is `no_reference` and stays visibly
    # different from a run that looked and found nothing.
    if refutation_skip is not None:
        records.append(
            skipped(
                "published_refutation",
                refutation_skip,
                detail=(
                    "no CIViC snapshot was provisioned this run, so no authored direction was "
                    "compared against a published refutation. Build one with `civic build "
                    "--release <date> --submitted`"
                    if refutation_detail == "no_snapshot"
                    else "a CIViC snapshot was located but could not be read"
                ),
                source="civic",
            )
        )
    else:
        # The basis is in `detail` on every run including the empty one, and that is the point: on the
        # `accepted` basis this class is empty **by construction** — every refutation standing against
        # a claim in CIViC is submitted content — so a bare `findings=0` would read as clear water.
        records.append(
            ran(
                "published_refutation",
                subjects=refutation_subjects,
                findings=len(refutation_findings),
                source="civic",
                release=_civic_release(civic_ref),
                detail=_refutation_detail(refutation_findings, refutation_basis),
            )
        )

    # RM160 — the CIViC citation canary. Four skip reasons rather than one, because they are cleared
    # by four different things: nothing recorded, no egress, nothing this run could map back to a
    # variant id, and a source that did not answer. `findings` counts both codes under one record
    # because they share a subject *set* — the citations this module holds from CIViC — the same
    # reason the refutation leg above puts two codes under one record.
    if evidence_status.skip is not None:
        records.append(
            skipped(
                "evidence_status_currency",
                evidence_status.skip,
                detail=evidence_status.detail(),
                source="civic",
            )
        )
    else:
        records.append(
            ran(
                "evidence_status_currency",
                subjects=evidence_status.subjects,
                findings=len(evidence_status.findings),
                source="civic",
                detail=evidence_status.detail(),
            )
        )

    # rsID currency. dbSNP publishes a build number per record rather than a release for the service,
    # so there is nothing true to put in `release` — the same call `LiteratureRow` made about `dataset`.
    if not verify_rsids:
        records.append(skipped("rsid_currency", "not_requested", source="dbsnp"))
    elif offline:
        records.append(
            skipped(
                "rsid_currency",
                "offline",
                detail="dbSNP has no offline merge table, so currency cannot be established locally",
                source="dbsnp",
            )
        )
    else:
        records.append(
            ran(
                "rsid_currency",
                subjects=rsid_subjects,
                findings=len(stale_rsids),
                source="dbsnp",
            )
        )
    # rsID ↔ coordinate. This tier's half of a question the compiler asks too (`resolution._verify`
    # over the injected table), so one name covers both and this record covers **this** half: the
    # authored pair against the Ensembl snapshot the chain opened. `source` is the authority the
    # licence table joins on, not the link that answered — the `gene_metrics.csv` rule from RM33.
    unplaced = examples(sorted(set(pairs.unknown)))
    unsettled = examples(sorted(set(pairs.undecided)))
    # What was not compared, and why, in one sentence per reason — never one per row.
    not_compared = [
        note
        for note in (
            f"the injected Ensembl snapshot carries no record for {len(pairs.unknown)} of them "
            f"({unplaced}), and absent from this snapshot is not absent from Ensembl"
            if pairs.unknown
            else "",
            f"{len(pairs.undecided)} name an indel ({unsettled}), whose spelling can move the "
            f"coordinate legitimately, so no verdict was reached"
            if pairs.undecided
            else "",
        )
        if note
    ]
    if pairs.not_checked is not None:
        if pairs.not_checked == "unsupported":
            detail = (
                "coordinate resolution is GRCh38-bound, so an authored rsID+coordinate pair on "
                "another assembly has nothing to be compared against (RM15)"
            )
        elif pairs.not_checked == "nothing_to_check":
            detail = (
                "no row authors both an rsID and a coordinate, so the module makes no pair claim to "
                "compare — this is not a comparison that found nothing"
            )
        elif not_compared:
            # A snapshot was read and settled nothing. Distinct from having no snapshot at all, and the
            # pairs are named because *which* ones went unchecked is what a re-run against a fuller
            # snapshot — or an online run that can normalize an indel — would change.
            detail = "no authored pair could be compared: " + "; ".join(not_compared)
        else:
            detail = "no Ensembl snapshot was opened this run, so no authored pair was compared" + (
                " — a run with egress provisions one" if pairs.not_checked == "offline" else ""
            )
        records.append(
            skipped("rsid_coordinate_agreement", pairs.not_checked, detail=detail, source="ensembl")
        )
    else:
        # What was NOT compared travels with what was: coverage of an unstated fraction is the defect
        # `_vrs_coverage` exists for, one check over.
        notes = list(pairs.disagreements[:DETAIL_LIMIT])
        if len(pairs.disagreements) > DETAIL_LIMIT:
            notes.append(
                f"({len(pairs.disagreements) - DETAIL_LIMIT} further disagreement(s) not listed "
                f"here; the run's log names every one.)"
            )
        if not_compared:
            notes.append("Further authored pairs were not compared: " + "; ".join(not_compared) + ".")
        records.append(
            ran(
                "rsid_coordinate_agreement",
                subjects=pairs.subjects,
                findings=len(pairs.disagreements),
                source="ensembl",
                release=_snapshot_release(ensembl_ref),
                detail=" ".join(notes) or None,
            )
        )

    # Dataset currency (RM85). `source` is left empty on purpose and is the one place this record
    # departs from its neighbours: it is a single join key into the licence table, and this check is
    # multi-leg by construction — a module recording ClinVar and CPIC has two sources implicated, so
    # naming one would hide the other and a comma-joined value would break the join the column exists
    # for. The same call `allele_function` makes for its two authorities. `release` is left empty for
    # the same reason: there is no one release this check was put *against*.
    # `None` **is** the not-requested case and is not tested beside a flag: `_run_enrichment` sets
    # one from the other, so taking both would let this function disagree with itself — a
    # `verify_datasets=True, currency=None` call would record `not_requested` about a check that was.
    if currency is None:
        records.append(skipped("dataset_currency", "not_requested"))
    elif currency.not_checked is not None:
        records.append(
            skipped(
                "dataset_currency",
                currency.not_checked,
                detail=(
                    "; ".join(summarize_currency(currency))
                    or "the module records no release, so it makes no claim about where its rows came from"
                ),
            )
        )
    else:
        # `subjects` is the legs asked **and answered comparably**, never every recorded release: a
        # source nobody could reach is named in `detail` instead, because counting it would publish
        # coverage of a fraction the record does not state — the defect the reference-allele pass
        # shipped once and `_vrs_coverage` exists for.
        records.append(
            ran(
                "dataset_currency",
                subjects=currency.subjects,
                findings=len(currency.behind),
                detail="; ".join(summarize_currency(currency)) or None,
            )
        )

    # Deliberately takes neither `variants` nor `rows`: nothing here may count anything itself, and a
    # function that cannot see the tables cannot be tempted to. The denominators come in already
    # computed, from the checks that computed them.
    return records


def _snapshot_release(reference: Path | None) -> str | None:
    """The label a snapshot's own `release.json` states, or `None` when it states none.

    The `dataset` key, which is the one every builder writes and `cache status` prints, so a reader of
    the attestation and a reader of the cache see the same string. No fallback and no guess: a
    snapshot that cannot name its release is an unknown, and an unknown is withheld rather than
    written as a label something could match — the same call `clinvar_dataset_label` makes for its own
    (richer) source. ClinVar has its own function because its release is a *file date* with a digest
    fallback; nothing equivalent is published for the Ensembl variation snapshot.
    """
    if reference is None:
        return None
    release = read_release(Path(reference))
    if not release:
        return None
    return str(release.get("dataset") or "").strip() or None


def _clinvar_release(reference: Path | None) -> str | None:
    """The ClinVar release a snapshot states, or `None` when it states none.

    Delegates to `clinvar.clinvar_dataset_label` rather than re-reading `clinvar_file_date`, because a
    second spelling of one label is the drift that function's own docstring exists to prevent — and it
    had already started: this hand-read dropped the `clinvar_` prefix, so `verification.checks[].release`
    and `sources[].dataset` named the same snapshot two ways, and it dropped the digest fallback, so a
    snapshot built from a VCF with no header date recorded "the source publishes none" when it could
    name its release exactly. `None` stays the honest answer for a snapshot that genuinely cannot say.
    """
    return clinvar_dataset_label(reference)
