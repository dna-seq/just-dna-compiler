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
from collections.abc import Iterable, Sequence
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

#: How many per-row sentences a record's `detail` carries before it becomes a count. The field is
#: prose a human reads, and a module whose whole panel disagrees would otherwise put one sentence per
#: row into `manifest.verification` — the un-aggregated wall this tree collapses everywhere else. The
#: log and the command's own report still name every one.
DETAIL_LIMIT = 5


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

    Existing records for checks this run did not put are kept (`verification.merge_records`) — a run
    that did not ask a question has said nothing about it, and dropping the earlier answer would turn
    "not asked this time" into "never asked", which is the collapse this whole item exists to undo.
    Since RM72 a *skip* this run writes does not displace an earlier real answer either, for the same
    reason one step further out — but only while the earlier answer still describes the module's
    current authored bytes, which is what `existing_still_binds` carries. Where they have moved, the
    older record is about rows that no longer exist and this run's honest "could not ask" wins.

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
                path.name, exc,
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
                    "re-bound. Re-close the module once you are finished editing it.", path.name,
                )

    doc = attest(
        merge_records(existing, fresh, existing_still_binds=existing_still_binds),
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
        producer=producer_label(),
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
        producer=producer_label(),
    )
