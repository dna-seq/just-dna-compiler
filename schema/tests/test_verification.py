"""The verification attestation: binding, proof-of-work, merge, and the record's own refusals (RM45).

Every expectation here is computed at runtime from the code under test — no pasted digests, no pasted
nonces. The one place a constant appears is `VERIFICATION_DIFFICULTY_BITS`, and it is read rather than
restated, so moving it moves the test with it.

The difficulty is lowered for most cases (an argument the functions take precisely so a suite can),
with one case exercising the shipped value so nobody can lower it to nothing and still be green.
"""

import json

import pytest
from just_dna_format import integrity
from just_dna_format.integrity import (
    artifact_digest,
    file_entries,
    newline_normalized_file_entries,
    newline_normalized_file_entry,
    sha256_bytes,
)
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


def test_a_skip_does_not_replace_an_answer_the_document_already_holds() -> None:
    """RM72. `check-acmg --offline` after a real run must not turn a verdict into 'never asked'.

    The argument is the one the function already makes for a check *absent* from `fresh`: a skip is a
    run that did not put the question, spelled as a record instead of as a silence, so the same
    protection applies. Under the old unconditional `dict.update` this assertion read
    `subjects == 0, skipped == 'offline'`.
    """
    answered, _ = _records()
    stale = VerificationRecord(
        check=answered.check, skipped="offline", detail="no snapshot and no egress",
    )
    kept = {r.check: r for r in merge_records([answered], [stale])}[answered.check]
    assert (kept.subjects, kept.findings, kept.skipped) == (12, 1, None)


def test_newest_wins_between_two_records_of_the_same_disposition() -> None:
    """The protection is only across dispositions — re-running is still how a record is updated."""
    answered, skipped_record = _records()
    newer_answer = VerificationRecord(check=answered.check, subjects=30, findings=2)
    newer_skip = VerificationRecord(check=skipped_record.check, skipped="not_requested")

    by_check = {
        r.check: r
        for r in merge_records([answered, skipped_record], [newer_answer, newer_skip])
    }
    assert (by_check[answered.check].subjects, by_check[answered.check].findings) == (30, 2)
    assert by_check[skipped_record.check].skipped == "not_requested"


def test_an_answer_about_bytes_that_have_moved_does_not_outrank_this_run() -> None:
    """The condition on the protection, and the case that makes it necessary rather than tidy.

    An answer earns its protection by still being an answer about *this* module. Once the authored
    rows have changed it describes rows that no longer exist, and keeping it over a fresh "could not
    ask" republishes a stale finding — which is how `literature` behaves when a module's citations
    change, and precisely the defect an earlier round fixed by writing the skip.
    """
    answered, _ = _records()
    fresh = VerificationRecord(check=answered.check, skipped="offline", detail="rows changed")
    kept = {
        r.check: r for r in merge_records([answered], [fresh], existing_still_binds=False)
    }[answered.check]
    assert kept.skipped == "offline" and kept.subjects == 0


# ── the binding, and the document on disk ────────────────────────────────────────────────────────


def test_the_binding_follows_the_bytes_it_hashes(tmp_path) -> None:
    """A changed value moves the binding — over the entry builder the binding actually uses (RM82)."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_bytes(b"rsid\nrs777\n")
    names = ["variants.csv"]
    before = module_binding(newline_normalized_file_entries(spec, names))
    (spec / "variants.csv").write_bytes(b"rsid\nrs778\n")
    assert module_binding(newline_normalized_file_entries(spec, names)) != before


def test_a_crlf_rewrite_does_not_move_the_binding(tmp_path) -> None:
    """The whole of RM82: an editor's line endings are not an edit.

    Both halves of the entry have to follow, which is why this asserts on the binding rather than on
    the digest alone — `artifact_digest` hashes `size` beside `sha256`, so a builder that normalized
    only the bytes it hashed would still move the binding by one byte per line.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    csv = spec / "variants.csv"
    csv.write_bytes(b"rsid,genotype\nrs777,A/G\nrs778,C/T\n")
    names = ["variants.csv"]
    before = module_binding(newline_normalized_file_entries(spec, names))

    csv.write_bytes(csv.read_bytes().replace(b"\n", b"\r\n"))
    assert csv.stat().st_size != len(csv.read_bytes().replace(b"\r\n", b"\n"))  # really rewritten
    assert module_binding(newline_normalized_file_entries(spec, names)) == before


def test_the_raw_entries_still_move_on_a_crlf_rewrite(tmp_path) -> None:
    """The asymmetry is the decision: `manifest.inputs[]`/`artifact.digest` still follow every byte.

    Without this the next reader tidies the two builders into one, and a registry loses its answer to
    *are these the exact bytes I was served*.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    csv = spec / "variants.csv"
    csv.write_bytes(b"rsid,genotype\nrs777,A/G\n")
    names = ["variants.csv"]
    before = file_entries(spec, names)

    csv.write_bytes(csv.read_bytes().replace(b"\n", b"\r\n"))
    after = file_entries(spec, names)
    assert (after[0].sha256, after[0].size) != (before[0].sha256, before[0].size)
    assert artifact_digest(after) != artifact_digest(before)


def test_the_normalized_entry_reports_the_normalized_length(tmp_path) -> None:
    """`size` is the normalized stream's length, not `stat().st_size` — the trap, asserted directly."""
    spec = tmp_path / "spec"
    spec.mkdir()
    body = b"rsid\nrs777\nrs778\n"
    (spec / "variants.csv").write_bytes(body.replace(b"\n", b"\r\n"))
    entry = newline_normalized_file_entry(spec, "variants.csv")
    assert entry.size == len(body) < (spec / "variants.csv").stat().st_size
    assert entry.sha256 == sha256_bytes(body)


def test_a_lone_carriage_return_is_left_alone(tmp_path) -> None:
    """`\\r` on its own is not what a tool writes when it normalizes, so it stays an edit."""
    spec = tmp_path / "spec"
    spec.mkdir()
    csv = spec / "variants.csv"
    csv.write_bytes(b"rsid\nrs777\n")
    names = ["variants.csv"]
    before = module_binding(newline_normalized_file_entries(spec, names))
    csv.write_bytes(b"rsid\rrs777\n")
    assert module_binding(newline_normalized_file_entries(spec, names)) != before


def test_mixed_endings_normalize_to_the_all_lf_spelling(tmp_path) -> None:
    """Half-converted files are the realistic shape of the bug — one appended row, one editor."""
    spec = tmp_path / "spec"
    spec.mkdir()
    csv = spec / "variants.csv"
    lf = b"rsid,genotype\nrs777,A/G\nrs778,C/T\n"
    csv.write_bytes(b"rsid,genotype\r\nrs777,A/G\nrs778,C/T\r\n")
    mixed = newline_normalized_file_entry(spec, "variants.csv")
    csv.write_bytes(lf)
    assert (mixed.sha256, mixed.size) == (sha256_bytes(lf), len(lf))
    assert mixed == newline_normalized_file_entry(spec, "variants.csv")


def test_a_crlf_split_across_a_read_boundary_still_normalizes(tmp_path, monkeypatch) -> None:
    """The one thing a chunked rewrite gets wrong: `\\r` ending a read, `\\n` starting the next.

    The chunk size is monkeypatched rather than parameterized so the *public* function is what runs —
    a boundary the caller cannot choose is exactly the one that must not need choosing.
    """
    monkeypatch.setattr(integrity, "_CHUNK", 8)
    spec = tmp_path / "spec"
    spec.mkdir()
    lf = b"".join(b"rs%03d\n" % n for n in range(40))  # every chunk boundary lands somewhere new
    (spec / "variants.csv").write_bytes(lf.replace(b"\n", b"\r\n"))
    entry = newline_normalized_file_entry(spec, "variants.csv")
    assert (entry.sha256, entry.size) == (sha256_bytes(lf), len(lf))


def test_a_file_ending_in_a_bare_carriage_return_keeps_it(tmp_path, monkeypatch) -> None:
    """The carry has nothing to pair with at EOF, so it must be emitted rather than swallowed."""
    monkeypatch.setattr(integrity, "_CHUNK", 4)
    spec = tmp_path / "spec"
    spec.mkdir()
    body = b"rsid\r\nrs777\r"
    (spec / "variants.csv").write_bytes(body)
    entry = newline_normalized_file_entry(spec, "variants.csv")
    assert (entry.sha256, entry.size) == (sha256_bytes(b"rsid\nrs777\r"), len(b"rsid\nrs777\r"))


def test_the_normalized_builder_skips_a_file_the_module_does_not_carry(tmp_path) -> None:
    """The skip-missing contract `file_entries` has — a module carries only the kinds it uses."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_bytes(b"rsid\nrs777\n")
    entries = newline_normalized_file_entries(spec, ["variants.csv", "diplotypes.csv"])
    assert [e.name for e in entries] == ["variants.csv"]


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

    Fixed once here rather than grown ad hoc, because a name is permanent within a major. The set is
    written out in full so a drive-by addition has to answer for itself against the membership rule.
    """
    assert {
        "reference_allele",
        "rsid_currency",
        "rsid_coordinate_agreement",
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
        "pgx_evidence_level",
        "vrs_allele_id",
        "gene_disease_validity",
        "genome_build_agreement",
        "dataset_currency",
    } == VALID_VERIFICATION_CHECKS


def test_a_pass_that_only_records_a_source_gets_no_member() -> None:
    """The exclusion half of the rule, which is the half that would silently rot.

    0.6 added two derived tables whose passes read a source and write it down — the ClinVar assertion
    tier and gene-disease validity. Neither compares anything the author wrote (`assertions.py`'s own
    docstring: "records what ClinVar says and adjudicates nothing"), so neither may have a check name:
    a member would let a manifest report a check where no question was put, which is exactly the
    confusion RM45 exists to end.

    `gene_disease_validity` IS a member, and that is not a contradiction — it is reserved for a future
    pass that checks an *authored* gene/phenotype pair against those verdicts, which is a different
    question from recording them. The names below are the recording passes, and none of them appears.
    """
    for recorded_not_checked in (
        "clinvar_assertion_tier",
        "clinical_assertions",
        "allele_frequency",
        "gene_constraint",
        "article_license",
    ):
        assert recorded_not_checked not in VALID_VERIFICATION_CHECKS


def test_each_skip_names_a_different_remedy() -> None:
    """Three that must never be merged, because each is cleared by a different action.

    `not_requested` by a flag, `offline` by egress, `not_permitted` by a declaration — and a reader who
    saw a licensing skip spelled `offline` would go looking for a network problem that does not exist.
    """
    assert {"not_requested", "offline", "not_permitted"} <= VALID_VERIFICATION_SKIPS
