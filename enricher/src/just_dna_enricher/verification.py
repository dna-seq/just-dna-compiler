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

**Which commands actually call this, as of 0.6.** `enrich` (four checks), `literature` (three) and
`clinpgx` (one). `check-identifiers` and `check-acmg` still write nothing, and their own docstrings
say so — a tracked gap, not a claim this module gets to make on their behalf. That distinction is
worth keeping sharp here, because the sentence this paragraph replaced named `check-identifiers` as a
second writer and it never was one: the merge was built and tested against a document no two commands
produced, which is exactly the shape of unverified machinery this module exists to end.
"""

import logging
from collections.abc import Iterable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from just_dna_compiler.compiler import authored_input_entries
from just_dna_format.layout import VERIFICATION_JSON, SidecarCollision, sidecar_write_path
from just_dna_format.manifest import Closure, VerificationDoc, VerificationRecord
from just_dna_format.normalize import now_utc_iso
from just_dna_format.verification import (
    attest,
    merge_records,
    module_binding,
    read_verification,
    write_verification,
)

logger = logging.getLogger(__name__)


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

    Existing records for checks this run did not put are kept (`verification.merge_records`) — a run
    that did not ask a question has said nothing about it, and dropping the earlier answer would turn
    "not asked this time" into "never asked", which is the collapse this whole item exists to undo.

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
                path.name, exc,
            )
        else:
            existing = previous.records
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
                    "re-bound. Re-close the module once you are finished editing it.", path.name,
                )

    doc = attest(
        merge_records(existing, fresh),
        binding,
        producer=producer_label(),
        produced_at=now or now_utc_iso(),
        closure=closure,
    )
    # The format tier's writer, so both tiers spell the file one way.
    write_verification(doc, path)
    logger.info(
        "Verification: attested %d check(s) into %s (nonce %d at %d bits).",
        len(doc.records), path.name, doc.nonce, doc.difficulty,
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
    now: str | None = None,
) -> VerificationRecord:
    """A record for a check that RAN, with the denominator it ran over.

    Two constructors rather than one with an optional `skipped`, because the two shapes cannot both
    be filled and the model refuses a record that tries — making the split visible at every call site
    is cheaper than discovering it as a validation error.
    """
    return VerificationRecord(
        check=check,
        subjects=subjects,
        findings=findings,
        source=source,
        release=release,
        detail=detail,
        checked_at=now or now_utc_iso(),
    )


def skipped(
    check: str,
    reason: str,
    *,
    detail: str | None = None,
    source: str | None = None,
    now: str | None = None,
) -> VerificationRecord:
    """A record for a check that did NOT run, carrying the machine key and the sentence.

    The sentence is not optional in practice and is optional in the signature: `clinical.tautology_
    reason` writes a good one and it must survive into the record, while `not_requested` needs none.
    """
    return VerificationRecord(
        check=check,
        skipped=reason,
        detail=detail,
        source=source,
        checked_at=now or now_utc_iso(),
    )
