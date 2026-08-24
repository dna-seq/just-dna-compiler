"""The verification attestation (0.6, RM45) — binding, proof-of-work, and the table's fact hash.

`verification.json` is the seam that lets a compiled module say **whether anything it asserts was
ever checked**. The enricher writes it, the compiler reads it and either stamps `manifest.verification`
or drops the block with a warning. The models live in `manifest` beside `ProvenanceDoc`, which is the
same shape one release earlier; the behaviour lives here.

**What the attestation is for, stated at its real size.** It binds a set of check records to the
authored bytes they were computed over, and adds a proof-of-work so re-stamping is not free. That
defeats the **accidental** forgery: an attestation left behind after an edit, or copied from another
module, which is the failure that actually happens. It defeats nothing deliberate, and this module is
not built as though it should — a determined writer regenerates a nonce in under a second, exactly as
the enricher does. The real guarantee available in this format is `manifest.signature`, a detached
Ed25519 signature over `artifact.digest` made by a party a client pins.

**The binding covers the AUTHORED bytes and no others,** and the boundary is a decision rather than a
convenience. Every check in the vocabulary compares something a human wrote — a `clin_sig`, a `ref`,
an rsID, a PMID, a gene beside a locus — so the authored files are precisely what the claim is about.
The derived sidecars are deliberately outside it: `resolution.csv` carries a `fetched_at` per row, so
binding to its bytes would invalidate the attestation on every re-enrichment that changed nothing
anyone claimed. What the boundary costs is real and is stated rather than hidden: re-running the
enricher against a fresher ClinVar leaves the attestation matching, so a consumer reads *which*
release each check was put against from the record's own `release` field rather than inferring
currency from the binding.

**Line endings are outside it too (RM82, 0.6).** The binding reads `\r\n` as `\n`, so an editor that
normalizes newlines, or a Git checkout with `core.autocrlf`, no longer un-closes a module in which no
value moved. It stops there: a BOM, trailing whitespace and a missing final newline are all still
edits, because those are things a human typed rather than things a tool did on their behalf. The
transform lives in `integrity.newline_normalized_file_entry`, and it is used by this binding and by
nothing else — `manifest.inputs[]` and `artifact.digest` still follow every byte, because they answer
*are these the exact bytes* rather than *is this the same module*.

**The closure (RM73, 0.6) rides this document, and that is the whole design.** RM73 asked for a phase
boundary: an attestation that authoring is finished, which a later edit invalidates rather than
silently outliving. Everything that needs is already here — `module_hash` binds the authored bytes,
and the compiler recomputes it and drops the block on any mismatch — so the closure is one optional
block on `VerificationDoc` rather than a second sidecar with its own binding, its own staleness rule
and its own transport. It sits **outside** `pow_digest`'s payload, so no document written before it
existed has been invalidated and closing one re-mines nothing.

The two answer different questions and must not be read as one: the records say *these checks were
put against these bytes*, the closure says *a human declared these bytes final*. A module may
legitimately carry either alone.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from just_dna_format.integrity import IntegrityError, artifact_digest, fact_signature, verify_signature
from just_dna_format.layout import atomic_write_text
from just_dna_format.manifest import (
    Closure,
    FileEntry,
    Verification,
    VerificationDoc,
    VerificationRecord,
)
from just_dna_format.signing import sign_digest

#: Fact columns feeding `verification_signature`, on the discipline `integrity.fact_signature`
#: documents for the four CSV sidecars: what the record *claims*, with the producer's noise left out.
#:
#: `detail` is out because it is prose — rewording a sentence must not move a signature, the same call
#: `LiteratureRow` made about which of its columns are facts. `checked_at` is out for the reason
#: `fetched_at` is out everywhere: when a pass ran is a fact about the run, not about the module.
VERIFICATION_FACT_FIELDS: tuple[str, ...] = (
    "check",
    "subjects",
    "findings",
    "skipped",
    "source",
    "release",
)

#: Leading zero bits the proof-of-work must meet.
#:
#: Twenty, chosen by measurement rather than by taste: this interpreter hashes a short payload at
#: ~1.5M/s, and 2^20 expected trials is ~0.7s, inside the ~1 second budget the item sets. The budget
#: is not decoration — a ClinVar-pathogenic-scale module must build in a couple of hours, which is
#: what forces the work to be **one per document per run** rather than per row or per check.
#:
#: Verifying costs exactly one hash, so a reader pays nothing.
VERIFICATION_DIFFICULTY_BITS: int = 20


def module_binding(entries: Sequence[FileEntry]) -> str:
    """The hash an attestation is bound to: the authored input files, by name and content.

    Deliberately `integrity.artifact_digest` rather than a second canonicalization of the same idea.
    That function is a Merkle root over a `(name, sha256, size)` listing sorted by name, which is
    exactly what is wanted here, and two hand-written canonical forms over one shape is how two
    parties end up disagreeing about a digest. The caller decides *which* entries — see this module's
    docstring for why that is the authored set, and `just_dna_compiler.compiler.authored_input_entries`
    for the one function both tiers ask.

    The caller also decides *how* the entries were read, and for the binding that is
    `integrity.newline_normalized_file_entry` rather than `file_entry` (RM82): the digest **and** the
    size are taken over bytes in which `\\r\\n` reads as `\\n`, so an editor or a `core.autocrlf`
    checkout cannot un-close a module it did not change. Passing raw entries here still works and
    still hashes fine — it just answers the byte question instead, which is `manifest.inputs[]`'s job.
    """
    return artifact_digest(list(entries))


def verification_signature(records: Sequence[VerificationRecord]) -> str:
    """Fact-hash of the check records (`VERIFICATION_FACT_FIELDS`). See `integrity.fact_signature`.

    Order-independent and normalized, like its four siblings, so two producers recording the same
    checks in a different order hash equal.
    """
    return fact_signature(records, VERIFICATION_FACT_FIELDS)


def pow_digest(module_hash: str, signature: str, nonce: int) -> bytes:
    """The raw digest a nonce is judged on: both hashes plus the nonce, in one fixed spelling.

    Both halves are in it on purpose. Binding to `module_hash` alone would let the records be edited
    freely under a nonce that still verifies; binding to `signature` alone would let a whole
    attestation be lifted onto another module.
    """
    payload = f"{module_hash}|{signature}|{nonce}".encode()
    return hashlib.sha256(payload).digest()


def leading_zero_bits(digest: bytes) -> int:
    """How many leading zero bits `digest` has."""
    value = int.from_bytes(digest, "big")
    if value == 0:
        return len(digest) * 8
    return len(digest) * 8 - value.bit_length()


def meets_difficulty(module_hash: str, signature: str, nonce: int, difficulty: int) -> bool:
    """Whether this nonce's digest carries at least `difficulty` leading zero bits."""
    return leading_zero_bits(pow_digest(module_hash, signature, nonce)) >= difficulty


def find_nonce(module_hash: str, signature: str, difficulty: int) -> int:
    """The SMALLEST nonce, counting up from zero, that meets `difficulty`.

    Smallest and not a random search, and the reason is determinism rather than elegance: a random
    nonce gives the file different bytes on every run for identical content, which would make
    `verification.json` the one derived sidecar that cannot be reproduced — and this tree pins
    reproducibility with tests everywhere else. Counting up also makes the work honest: the expected
    cost is 2^difficulty hashes whichever nonce happens to win.
    """
    nonce = 0
    while not meets_difficulty(module_hash, signature, nonce, difficulty):
        nonce += 1
    return nonce


def close(
    module_hash: str,
    *,
    closed_at: str,
    closed_by: str | None = None,
    private_key_pem: bytes | None = None,
) -> Closure:
    """Build the closure that says authoring is finished over `module_hash` (RM73).

    Signing is optional and the message signed is `module_hash` itself, so `signing.sign_digest`
    serves unchanged — it takes whichever digest string it is handed, which is why `Signature` moved
    up beside the models that use it rather than growing a second spelling here.

    Nothing about this function decides *when* it is legitimate to call. That is the caller's job and
    it is a real one: closing a document whose records were attested over other bytes would re-bind
    them to these, which is why `compile_module`'s side of this drops such records rather than
    carrying them across.
    """
    return Closure(
        closed_at=closed_at,
        closed_by=closed_by,
        signature=(
            None if private_key_pem is None
            else sign_digest(module_hash, private_key_pem, signed_at=closed_at)
        ),
    )


def attest(
    records: Sequence[VerificationRecord],
    module_hash: str,
    *,
    producer: str | None = None,
    produced_at: str | None = None,
    difficulty: int | None = None,
    closure: Closure | None = None,
) -> VerificationDoc:
    """Build the document: hash the records, bind them to `module_hash`, and mine the nonce.

    `difficulty` is a parameter rather than a hardcoded read of the constant so a test can exercise
    the whole path in milliseconds; production callers take the default. A document written at a lower
    difficulty than a reader's minimum is rejected by `attestation_failure`, so nothing is lost by
    letting it move.

    **`None` rather than the constant as the default**, and that is not a style preference: a default
    argument is evaluated at import, so writing `difficulty=VERIFICATION_DIFFICULTY_BITS` in the
    signature freezes the value and a test that lowers the constant still pays the full second — on
    every call, through every caller that does not thread the parameter. Reading it in the body is
    what makes the knob reachable at all.
    """
    difficulty = VERIFICATION_DIFFICULTY_BITS if difficulty is None else difficulty
    ordered = _ordered(records)
    signature = verification_signature(ordered)
    return VerificationDoc(
        module_hash=module_hash,
        signature=signature,
        difficulty=difficulty,
        nonce=find_nonce(module_hash, signature, difficulty),
        producer=producer,
        produced_at=produced_at,
        records=ordered,
        # Deliberately outside `pow_digest`'s payload, which stays `module_hash|signature|nonce`.
        # Two consequences worth having: closing an already-attested document re-mines nothing it
        # would not have re-mined anyway, and every attestation written before 0.6 still verifies
        # against a reader that knows about closures. What protects the closure is the binding it
        # rides plus its own optional signature, not the work.
        closure=closure,
    )


def attestation_failure(
    doc: VerificationDoc,
    module_hash: str,
    *,
    difficulty: int | None = None,
) -> str | None:
    """Why this attestation may not be published, or `None` when it holds.

    A **reason** rather than a bool, because the three ways it fails want different sentences and a
    caller that can only say "invalid" sends an author looking in the wrong place: an edited module, a
    hand-edited record set, and a document written before the difficulty moved are three situations
    with three remedies.

    Never raises and never repairs. The caller's answer to every one of these is the same — warn, and
    drop the block — so a compile still succeeds and the manifest simply says nothing, which is the
    correct reading of a record that no longer describes these bytes.

    `difficulty` reads the constant in the body for the reason `attest` does: a default frozen at
    import is a knob no test can turn.
    """
    difficulty = VERIFICATION_DIFFICULTY_BITS if difficulty is None else difficulty
    if doc.module_hash != module_hash:
        return (
            f"the attestation was computed over different module bytes ({doc.module_hash} vs "
            f"{module_hash}) — the spec has been edited since this was written, so nothing here "
            f"describes the rows being compiled"
        )
    recomputed = verification_signature(doc.records)
    if recomputed != doc.signature:
        return (
            f"the recorded check signature {doc.signature} is not the hash of the records beside it "
            f"({recomputed}) — the records were changed after they were attested"
        )
    if doc.difficulty < difficulty:
        return (
            f"the proof-of-work claims {doc.difficulty} bits and this reader requires {difficulty} — "
            f"re-run the checks to attest at the current difficulty"
        )
    if not meets_difficulty(doc.module_hash, doc.signature, doc.nonce, doc.difficulty):
        return (
            f"nonce {doc.nonce} does not meet the {doc.difficulty}-bit proof-of-work it claims — the "
            f"attestation was assembled by hand rather than by a run of the checks"
        )
    # A closure with no signature is checked by the binding above and nothing else — that is the whole
    # of what an unsigned one claims. A signature that is *present* is a stronger claim, so a failure
    # here drops the document: an unverifiable attribution is worse than an anonymous closure, and the
    # asymmetry is the house rule that absence is a limit while a claim is a claim.
    if doc.closure is not None and doc.closure.signature is not None:
        try:
            verify_signature(doc.module_hash, doc.closure.signature)
        except IntegrityError as exc:
            return (
                f"the closure is signed and the signature does not verify against the bytes it "
                f"names ({exc}) — re-close the module with the key that should have signed it"
            )
    return None


def verification_block(doc: VerificationDoc) -> Verification:
    """The manifest summary of a document whose attestation has already been confirmed.

    Deliberately takes no `module_hash` and performs no check: a function that could either summarize
    or refuse would let a caller skip `attestation_failure` and never notice. The order is fixed at
    the one call site — confirm, then summarize.
    """
    return Verification(
        signature=doc.signature,
        module_hash=doc.module_hash,
        producer=doc.producer,
        produced_at=doc.produced_at,
        closure=doc.closure,
        checks=list(doc.records),
    )


def merge_records(
    existing: Sequence[VerificationRecord],
    fresh: Sequence[VerificationRecord],
    *,
    existing_still_binds: bool = True,
) -> list[VerificationRecord]:
    """Fold a run's records into what the document already carried — newest wins, per check.

    Replace rather than accumulate, because a record answers "what happened the last time this check
    was put" and two answers to that are not two facts. A check absent from `fresh` keeps its earlier
    record: a run that did not put a question has said nothing about it, and deleting the older answer
    would turn "not asked this time" into "never asked", which is the exact collapse RM45 exists to
    undo.

    **A `skipped` record does not replace a `ran` one (RM72), and that is the paragraph above applied
    one step further out.** A skip *is* a run that did not put the question — the same fact as an
    absent check, spelled as a record instead of as a silence — so the argument that protects the
    absent check protects this one, and unconditional newest-wins performed exactly the deletion the
    paragraph refuses: `check-acmg --offline` after a real run, or `check-identifiers --no-traits`
    after a full one, rewrote a true `subjects=13 findings=0` verdict to `subjects=0 findings=0
    skipped=offline`. Newest-wins still holds between two records of the same disposition — a fresh
    `ran` replaces an older `ran` (that is the point of re-running), and a fresh skip replaces an
    older skip (the newer reason is the current one).

    **`existing_still_binds` is the condition on that protection, and it is not a knob.** An answer is
    worth protecting because it is still an answer *about this module*; once the authored bytes have
    moved it describes rows that no longer exist, and preserving it over a fresh honest "could not
    ask" would publish a stale finding rather than a real one. That case is not hypothetical: it is
    how `literature` behaves when the module's citations change, and a previous round fixed exactly
    that defect by writing the skip. So the caller passes whether the document it read was computed
    over the bytes it is now being rewritten over (`VerificationDoc.module_hash` vs the binding), and
    with `False` this is plain newest-wins. The default is `True` because a caller holding no earlier
    document has nothing that could fail the test.

    The counter-argument to the protection is real and is answered rather than dismissed: a reader may
    legitimately want to know that *today's* run could not reach the source. That is a fact about the
    **run**, not about the **check**, and this is a per-check document — a run-level fact needs a
    run-level place, which is a separate question and is deliberately not opened here.
    """
    by_check = {record.check: record for record in existing}
    for record in fresh:
        previous = by_check.get(record.check)
        if (
            existing_still_binds
            and record.skipped is not None
            and previous is not None
            and previous.skipped is None
        ):
            continue
        by_check[record.check] = record
    return _ordered(by_check.values())


def read_verification(path: Path) -> VerificationDoc:
    """Load and validate a `verification.json`. Raises on malformed content, like `read_manifest`."""
    return VerificationDoc.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_verification(doc: VerificationDoc, path: Path) -> Path:
    """Write the document as indented JSON, with a trailing newline. Returns the path written."""
    # Atomic since S66: this is written in `enrich()`'s tail beside `resolution.csv` and
    # `sources.csv`, so one kill used to be able to truncate all three at once — and a half-written
    # attestation is the worst of the three, because a document that fails to parse is how a module
    # loses every check record it ever had.
    return atomic_write_text(Path(path), doc.model_dump_json(indent=2) + "\n")


def _ordered(records) -> list[VerificationRecord]:
    """Records sorted by check name — one stable emission order, so the bytes are reproducible.

    Sorted rather than insertion-ordered because the merge above draws from two runs and insertion
    order would then depend on which pass happened to go first. The signature is order-independent
    regardless; this is about the file.
    """
    return sorted(records, key=lambda record: record.check)
