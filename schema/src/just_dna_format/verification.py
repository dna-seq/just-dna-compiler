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
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from just_dna_format.integrity import artifact_digest, fact_signature
from just_dna_format.manifest import FileEntry, Verification, VerificationDoc, VerificationRecord

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


def attest(
    records: Sequence[VerificationRecord],
    module_hash: str,
    *,
    producer: str | None = None,
    produced_at: str | None = None,
    difficulty: int | None = None,
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
            f"{module_hash}) — the spec has been edited since the checks ran, so nothing here "
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
        checks=list(doc.records),
    )


def merge_records(
    existing: Sequence[VerificationRecord], fresh: Sequence[VerificationRecord]
) -> list[VerificationRecord]:
    """Fold a run's records into what the document already carried — newest wins, per check.

    Replace rather than accumulate, because a record answers "what happened the last time this check
    was put" and two answers to that are not two facts. A check absent from `fresh` keeps its earlier
    record: a run that did not put a question has said nothing about it, and deleting the older answer
    would turn "not asked this time" into "never asked", which is the exact collapse RM45 exists to
    undo.
    """
    by_check = {record.check: record for record in existing}
    by_check.update({record.check: record for record in fresh})
    return _ordered(by_check.values())


def read_verification(path: Path) -> VerificationDoc:
    """Load and validate a `verification.json`. Raises on malformed content, like `read_manifest`."""
    return VerificationDoc.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_verification(doc: VerificationDoc, path: Path) -> Path:
    """Write the document as indented JSON, with a trailing newline. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _ordered(records) -> list[VerificationRecord]:
    """Records sorted by check name — one stable emission order, so the bytes are reproducible.

    Sorted rather than insertion-ordered because the merge above draws from two runs and insertion
    order would then depend on which pass happened to go first. The signature is order-independent
    regardless; this is about the file.
    """
    return sorted(records, key=lambda record: record.check)
