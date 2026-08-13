"""The verification attestation: binding, proof-of-work, merge, and the record's own refusals (RM45).

Every expectation here is computed at runtime from the code under test — no pasted digests, no pasted
nonces. The one place a constant appears is `VERIFICATION_DIFFICULTY_BITS`, and it is read rather than
restated, so moving it moves the test with it.

The difficulty is lowered for most cases (an argument the functions take precisely so a suite can),
with one case exercising the shipped value so nobody can lower it to nothing and still be green.
"""

import json

import pytest
from just_dna_format.integrity import file_entries
from just_dna_format.manifest import VerificationDoc, VerificationRecord
from just_dna_format.verification import (
    VERIFICATION_DIFFICULTY_BITS,
    VERIFICATION_FACT_FIELDS,
    attest,
    attestation_failure,
    find_nonce,
    leading_zero_bits,
    meets_difficulty,
    merge_records,
    module_binding,
    pow_digest,
    read_verification,
    verification_block,
    verification_signature,
    write_verification,
)
from just_dna_format.vocab import VALID_VERIFICATION_CHECKS, VALID_VERIFICATION_SKIPS

_EASY = 8  # bits; enough to prove the mechanism, cheap enough to run dozens of times
_HASH = "sha256:" + "ab" * 32


def _records() -> list[VerificationRecord]:
    return [
        VerificationRecord(
            check="clinical_significance", subjects=12, findings=1,
            source="clinvar", release="2026-06-27", checked_at="2026-08-13T00:00:00Z",
        ),
        VerificationRecord(
            check="reference_allele", skipped="offline",
            detail="no sequence access this run", checked_at="2026-08-13T00:00:00Z",
        ),
    ]


# ── the record's own contract ────────────────────────────────────────────────────────────────────


def test_a_skipped_check_may_not_also_report_counts() -> None:
    """The self-contradiction class: 'this did not run' beside 'it looked at 12 rows'."""
    with pytest.raises(ValueError, match="skipped"):
        VerificationRecord(check="rsid_currency", skipped="offline", subjects=12)


def test_findings_may_not_exceed_subjects() -> None:
    with pytest.raises(ValueError, match="finding"):
        VerificationRecord(check="rsid_currency", subjects=2, findings=3)


def test_ran_against_nothing_is_not_the_same_value_as_did_not_run() -> None:
    """The whole reason there are two fields rather than one union-typed slot."""
    ran = VerificationRecord(check="rsid_currency", subjects=0, findings=0)
    did_not = VerificationRecord(check="rsid_currency", skipped="not_requested")
    assert ran.skipped is None and did_not.skipped == "not_requested"
    assert ran != did_not


def test_the_two_vocabularies_are_closed_and_canonicalizing() -> None:
    """A separator slip is absorbed (`vocab.match_vocab`); a value naming nothing still fails."""
    assert VerificationRecord(check="reference-allele").check == "reference_allele"
    assert VerificationRecord(check="rsid_currency", skipped="not-requested").skipped == (
        "not_requested"
    )
    with pytest.raises(ValueError):
        VerificationRecord(check="whatever_i_felt_like")
    with pytest.raises(ValueError):
        VerificationRecord(check="rsid_currency", skipped="because")


def test_a_document_carries_at_most_one_record_per_check() -> None:
    """A re-run replaces; it does not accumulate. Two records for one check are two answers."""
    doubled = [
        VerificationRecord(check="rsid_currency", subjects=1),
        VerificationRecord(check="rsid_currency", subjects=2),
    ]
    with pytest.raises(ValueError, match="more than once"):
        VerificationDoc(
            module_hash=_HASH, signature=verification_signature(doubled),
            difficulty=_EASY, nonce=0, records=doubled,
        )


# ── the fact hash ────────────────────────────────────────────────────────────────────────────────


def test_the_signature_is_order_independent() -> None:
    records = _records()
    assert verification_signature(records) == verification_signature(list(reversed(records)))


def test_prose_and_timestamps_are_outside_the_fact_hash() -> None:
    """Rewording a sentence, or running the same check again, must not move the identity."""
    base = _records()
    reworded = [
        r.model_copy(update={"detail": "reworded entirely", "checked_at": "2027-01-01T00:00:00Z"})
        for r in base
    ]
    assert verification_signature(base) == verification_signature(reworded)
    assert "detail" not in VERIFICATION_FACT_FIELDS
    assert "checked_at" not in VERIFICATION_FACT_FIELDS


def test_a_changed_count_does_move_the_fact_hash() -> None:
    base = _records()
    bumped = [base[0].model_copy(update={"findings": 2}), base[1]]
    assert verification_signature(base) != verification_signature(bumped)


# ── the proof of work ────────────────────────────────────────────────────────────────────────────


def test_the_nonce_is_the_smallest_one_that_works() -> None:
    """Deterministic by construction: nothing below it may meet the difficulty."""
    signature = verification_signature(_records())
    nonce = find_nonce(_HASH, signature, _EASY)
    assert meets_difficulty(_HASH, signature, nonce, _EASY)
    assert not any(meets_difficulty(_HASH, signature, n, _EASY) for n in range(nonce))


def test_attesting_twice_produces_the_same_bytes() -> None:
    """The determinism the round-trip rules pin everywhere else — no random search."""
    first = attest(_records(), _HASH, produced_at="2026-08-13T00:00:00Z", difficulty=_EASY)
    second = attest(_records(), _HASH, produced_at="2026-08-13T00:00:00Z", difficulty=_EASY)
    assert first.model_dump_json() == second.model_dump_json()


def test_the_shipped_difficulty_is_actually_met() -> None:
    """One case at the real constant, so it cannot be lowered to nothing and stay green."""
    doc = attest(_records(), _HASH)
    assert doc.difficulty == VERIFICATION_DIFFICULTY_BITS
    assert leading_zero_bits(pow_digest(doc.module_hash, doc.signature, doc.nonce)) >= (
        VERIFICATION_DIFFICULTY_BITS
    )
    assert attestation_failure(doc, _HASH) is None


def test_the_work_binds_both_halves() -> None:
    """Binding one alone would let the other be swapped freely — records edited, or lifted whole."""
    signature = verification_signature(_records())
    other = "sha256:" + "cd" * 32
    nonce = find_nonce(_HASH, signature, _EASY)
    assert not meets_difficulty(other, signature, nonce, _EASY)
    assert not meets_difficulty(_HASH, verification_signature(_records()[:1]), nonce, _EASY)


# ── the three refusals ───────────────────────────────────────────────────────────────────────────


def test_an_edited_module_fails_on_the_binding() -> None:
    doc = attest(_records(), _HASH, difficulty=_EASY)
    reason = attestation_failure(doc, "sha256:" + "cd" * 32, difficulty=_EASY)
    assert reason is not None and "different module bytes" in reason


def test_edited_records_fail_on_the_signature() -> None:
    doc = attest(_records(), _HASH, difficulty=_EASY)
    tampered = doc.model_copy(
        update={"records": [doc.records[0].model_copy(update={"findings": 0}), doc.records[1]]}
    )
    reason = attestation_failure(tampered, _HASH, difficulty=_EASY)
    assert reason is not None and "not the hash of the records" in reason


def test_a_hand_assembled_nonce_fails_on_the_work() -> None:
    doc = attest(_records(), _HASH, difficulty=_EASY)
    reason = attestation_failure(doc.model_copy(update={"nonce": doc.nonce + 1}), _HASH,
                                 difficulty=_EASY)
    assert reason is not None and "proof-of-work" in reason


def test_a_document_below_the_readers_difficulty_is_refused() -> None:
    doc = attest(_records(), _HASH, difficulty=_EASY)
    reason = attestation_failure(doc, _HASH, difficulty=_EASY + 4)
    assert reason is not None and "requires" in reason


# ── merging across runs ──────────────────────────────────────────────────────────────────────────


def test_a_re_run_replaces_its_own_check_and_leaves_the_others() -> None:
    """Newest wins per check; a check this run did not put keeps what the last one said.

    Deleting the older answer would turn 'not asked this time' into 'never asked' — the collapse the
    whole item exists to undo.
    """
    existing = _records()
    fresh = [VerificationRecord(check="clinical_significance", subjects=99, findings=0)]
    merged = merge_records(existing, fresh)
    by_check = {r.check: r for r in merged}
    assert set(by_check) == {"clinical_significance", "reference_allele"}
    assert by_check["clinical_significance"].subjects == 99
    assert by_check["reference_allele"].skipped == "offline"


def test_merged_records_are_emitted_in_one_stable_order() -> None:
    """Two runs in either order must produce the same file."""
    a, b = _records()
    assert [r.check for r in merge_records([a], [b])] == [r.check for r in merge_records([b], [a])]


# ── the binding, and the document on disk ────────────────────────────────────────────────────────


def test_the_binding_follows_the_bytes_it_hashes(tmp_path) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text("rsid\nrs777\n")
    names = ["variants.csv"]
    before = module_binding(file_entries(spec, names))
    (spec / "variants.csv").write_text("rsid\nrs778\n")
    assert module_binding(file_entries(spec, names)) != before


def test_a_document_round_trips_through_the_file(tmp_path) -> None:
    doc = attest(_records(), _HASH, producer="test 0", difficulty=_EASY)
    path = write_verification(doc, tmp_path / "verification.json")
    assert read_verification(path) == doc
    assert json.loads(path.read_text())["nonce"] == doc.nonce


def test_the_manifest_block_carries_the_records_whole(tmp_path) -> None:
    """A consumer reading the manifest must not have to fetch the sidecar to learn what ran."""
    doc = attest(_records(), _HASH, producer="test 0", difficulty=_EASY)
    block = verification_block(doc)
    assert [r.check for r in block.checks] == [r.check for r in doc.records]
    assert block.module_hash == _HASH and block.signature == doc.signature
    ran = next(r for r in block.checks if r.check == "clinical_significance")
    assert ran.release == "2026-06-27"


# ── the vocabularies themselves ──────────────────────────────────────────────────────────────────


def test_every_check_name_is_a_verification_question() -> None:
    """The membership rule, asserted as a set so a drive-by addition has to answer for itself.

    Fixed once here rather than grown ad hoc, because a name is permanent within a major. Two members
    have no emitter in this workspace yet, on the `withdrawn` precedent — the release that needs them
    should not have to invent a spelling — and the ClinVar assertion tier is deliberately absent: it
    records a source's review status and compares nothing the author wrote.
    """
    assert {
        "reference_allele",
        "rsid_currency",
        "clinical_significance",
        "acmg_secondary_findings",
        "gene_symbol_currency",
        "trait_currency",
        "gene_locus_agreement",
        "citation_existence",
        "citation_identifier",
        "provenance_quote",
        "dosage_sensitivity",
        "allele_function",
        "vrs_allele_id",
        "gene_disease_validity",
        "genome_build_agreement",
    } == VALID_VERIFICATION_CHECKS
    assert "clinvar_assertion_tier" not in VALID_VERIFICATION_CHECKS


def test_a_choice_and_a_capability_are_different_skips() -> None:
    """`not_requested` is cleared by a flag; `offline` by egress. Merging them loses the remedy."""
    assert {"not_requested", "offline"} <= VALID_VERIFICATION_SKIPS
