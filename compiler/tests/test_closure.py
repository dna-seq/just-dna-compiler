"""Closing the authoring phase (RM73) — the mechanism, and the properties it was chosen for.

RM73's claim is that a flat CSV row records nothing about how it came to be, so authoring had no end
and every check needing one guessed. The provenance half shipped in 0.6.0 and answered *did this cell
move*. This is the other question — *is the author done* — and the design decision under test here is
that it needed **no new file, no new binding and no new proof-of-work**: a `closure` block inside the
attestation `verification.json` already carries, whose `module_hash` the compiler already recomputes
and already drops on mismatch.

Run against real reference examples through the real `compile_module` / `close_module`, because the
two claims that matter — *closing moves no identity* and *an edit un-closes* — are only established by
compiling the real thing twice and comparing.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    UNCLOSED_PHRASE,
    authored_input_entries,
    close_module,
    compile_module,
    reverse_module,
    validate_spec,
)
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.manifest import VerificationRecord
from just_dna_format.signing import generate_private_key_pem, public_key_b64_from_pem
from just_dna_format.verification import (
    attest,
    attestation_failure,
    close,
    module_binding,
    pow_digest,
    read_verification,
    write_verification,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_EASY = 8  # bits; every case here is about the closure, not about the cost of the work


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


def _module(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    return spec


def _open_module(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    """A copy with the shipped closure removed — the state a module is in while being authored."""
    spec = _module(tmp_path, name)
    (spec / VERIFICATION_JSON).unlink(missing_ok=True)
    return spec


def _compile(spec: Path, out: Path):
    result = compile_module(spec, out, resolve_with_ensembl=False)
    assert result.success, result.errors
    return result


def _closure_warnings(messages) -> list[str]:
    return [m for m in messages if UNCLOSED_PHRASE in m]


# ── The reason the design is this small ──────────────────────────────────────────────────────────


def test_closing_moves_no_identity(tmp_path: Path) -> None:
    """The measurement the whole shape rests on, taken rather than argued.

    A closure is a statement *about* the authored bytes and must not become part of them. If it moved
    `content_signature` then two modules with identical annotations would stop sharing a content
    identity over who signed off, and if it moved `artifact.digest` then closing would invalidate a
    published version's bytes. `verification.json` is a derived sidecar and in neither hash, which is
    what makes this true — asserted here by compiling the same spec before and after.
    """
    spec = _open_module(tmp_path)
    before = _compile(spec, tmp_path / "before").manifest

    assert close_module(spec).closed
    after = _compile(spec, tmp_path / "after").manifest

    assert after.artifact.digest == before.artifact.digest
    assert after.content_signature == before.content_signature
    assert after.verification.closure is not None, "and the closure really did land"


def test_the_work_is_not_re_mined_and_older_attestations_still_verify(tmp_path: Path) -> None:
    """The closure sits outside `pow_digest`'s payload, deliberately.

    Two things follow and both are worth pinning. A document written before closures existed still
    verifies against a reader that knows about them — nothing published was invalidated by adding the
    field — and closing an attested document does not re-mine, because the payload it is judged on
    never mentioned the closure.
    """
    binding = "sha256:" + "ab" * 32
    doc = attest([VerificationRecord(check="rsid_currency", subjects=3, findings=0)], binding)
    assert attestation_failure(doc, binding) is None

    closed = doc.model_copy(update={"closure": close(binding, closed_at="2026-08-16T00:00:00Z")})
    assert attestation_failure(closed, binding) is None
    assert closed.nonce == doc.nonce
    assert pow_digest(closed.module_hash, closed.signature, closed.nonce) == pow_digest(
        doc.module_hash, doc.signature, doc.nonce
    )


# ── The warning: absent, present, and gone again ─────────────────────────────────────────────────


def test_an_open_module_is_told_in_both_the_pre_flight_and_the_compile(tmp_path: Path) -> None:
    """The parity rule this file has now closed four times: a check wired into one side only.

    `validate` is the author's documented pre-flight, so a notice that reaches only `compile` reaches
    them after the point it was useful. Asserted as one message on each side rather than as a count,
    because the sentence carries none — which is what lets the two runs de-duplicate.
    """
    spec = _open_module(tmp_path)
    assert len(_closure_warnings(validate_spec(spec).warnings)) == 1
    assert len(_closure_warnings(_compile(spec, tmp_path / "out").warnings)) == 1


def test_closing_silences_it_and_editing_an_authored_file_brings_it_back(tmp_path: Path) -> None:
    """The phase boundary, demonstrated end to end on a real module.

    The second half is the whole point of binding rather than declaring: nothing re-reads the closure
    to decide it is stale, and no field records *what* was edited. The hash moves, and the claim about
    the old bytes stops applying to the new ones.
    """
    spec = _open_module(tmp_path)
    assert close_module(spec).closed
    assert _closure_warnings(_compile(spec, tmp_path / "closed").warnings) == []

    variants = spec / "variants.csv"
    variants.write_text(variants.read_text().replace("hemochromatosis", "haemochromatosis"))

    reopened = _compile(spec, tmp_path / "edited")
    assert len(_closure_warnings(reopened.warnings)) == 1
    assert reopened.manifest.verification is None, "a stale document publishes nothing at all"


def test_a_derived_sidecar_does_not_un_close_a_module(tmp_path: Path) -> None:
    """The binding covers the authored set, so enrichment leaves a closed module closed.

    This is what makes the boundary usable rather than merely correct: `resolution.csv` carries a
    `fetched_at` per row, so a closure that moved with it would be destroyed by every re-enrichment
    that changed nothing anyone claimed, and an author would learn to stop closing.
    """
    spec = _open_module(tmp_path)
    assert close_module(spec).closed
    resolution = spec / "resolution.csv"
    resolution.write_text(resolution.read_text().replace("2026-", "2027-"))

    assert _closure_warnings(_compile(spec, tmp_path / "out").warnings) == []


def test_rewriting_an_authored_file_s_line_endings_does_not_un_close_it(tmp_path: Path) -> None:
    """RM82, end to end on a real module and in both directions.

    Before this, an author whose editor normalizes newlines — or whose Git does it through
    `core.autocrlf` — un-closed a module without touching a cell, and the compile said the spec had
    been edited since the checks ran. `hfe_hemochromatosis` is the honest fixture for it: its
    `variants.csv` ships CRLF-terminated (that is `csv.writer`'s default), so *normalizing* it is the
    edit an author really makes, and putting the endings back is the same non-edit from the other side.
    """
    spec = _open_module(tmp_path)
    variants = spec / "variants.csv"
    assert b"\r\n" in variants.read_bytes(), "the fixture is only interesting while it ships CRLF"
    assert close_module(spec).closed

    lf = variants.read_bytes().replace(b"\r\n", b"\n")
    variants.write_bytes(lf)
    normalized = _compile(spec, tmp_path / "lf")
    assert _closure_warnings(normalized.warnings) == []
    assert normalized.manifest.verification is not None

    variants.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert _closure_warnings(_compile(spec, tmp_path / "crlf").warnings) == []


def test_the_inputs_listing_still_follows_the_line_endings_the_binding_ignores(
    tmp_path: Path,
) -> None:
    """The asymmetry RM82 chose, measured on one compile rather than argued.

    `manifest.inputs[]` answers *are these the exact bytes* and must keep moving; the binding answers
    *is this the same module* and must not. A reader who tidies the two builders into one breaks the
    first question, so it is pinned beside the second.
    """
    spec = _open_module(tmp_path)
    variants = spec / "variants.csv"
    assert close_module(spec).closed
    before = _compile(spec, tmp_path / "before")

    variants.write_bytes(variants.read_bytes().replace(b"\r\n", b"\n"))
    after = _compile(spec, tmp_path / "after")

    listed = {e.name: (e.sha256, e.size) for e in after.manifest.inputs}
    was = {e.name: (e.sha256, e.size) for e in before.manifest.inputs}
    assert listed["variants.csv"] != was["variants.csv"], "the raw-byte listing must follow the bytes"
    assert listed["studies.csv"] == was["studies.csv"], "and only for the file that was rewritten"
    assert after.manifest.verification is not None
    assert after.manifest.verification.module_hash == before.manifest.verification.module_hash


# ── What closing refuses, and what it does not ───────────────────────────────────────────────────


def test_closing_refuses_a_spec_that_does_not_validate(tmp_path: Path) -> None:
    """Declaring an authored set finished that the compiler will not accept is a contradiction."""
    spec = _open_module(tmp_path)
    (spec / "variants.csv").write_text("rsid,genotype\nrs1799945,not-a-genotype\n")

    result = close_module(spec)
    assert not result.closed and result.errors
    assert not (spec / VERIFICATION_JSON).exists(), "and nothing was written"


def test_a_refusal_does_not_tell_the_author_to_run_the_command_they_are_running(
    tmp_path: Path,
) -> None:
    """Found by dogfooding, on the first foreign module that failed to close.

    `close_module` runs the pre-flight and reports what it found, and the pre-flight rightly warns
    that the module is not closed — so the first line an author saw, while running `close`, was *Run
    `just-dna-compiler close`*. The warning is correct and its reader is wrong here, which is the RM77
    class: a correct sentence aimed at the wrong thing sends someone to do what they already did.
    """
    spec = _open_module(tmp_path)
    (spec / "variants.csv").write_text("rsid,genotype\nrs1799945,not-a-genotype\n")

    result = close_module(spec)
    assert not result.closed
    assert _closure_warnings(result.warnings) == [], result.warnings
    # And the pre-flight it delegates to still says it, so this is a filter, not a silencing.
    assert len(_closure_warnings(validate_spec(spec).warnings)) == 1


def test_a_closure_only_document_dates_the_closure_and_nothing_else(tmp_path: Path) -> None:
    """`producer`/`produced_at` describe the run that put the checks, and there was none.

    Also from the dogfood: a foreign module closed straight from its authored state published
    `producer: null, produced_at: <now>, checks: []` — a timestamp for a run that never happened,
    sitting beside the closure's own `closed_at` recording the act that did. The two fields are a
    pair and they move together.
    """
    spec = _open_module(tmp_path)
    assert close_module(spec).closed

    doc = read_verification(spec / VERIFICATION_JSON)
    assert (doc.producer, doc.produced_at) == (None, None)
    assert doc.closure.closed_at and doc.records == []


def test_closing_does_not_refuse_on_a_warning(tmp_path: Path) -> None:
    """A warning is not an unfinished module, and treating it as one makes closure unreachable.

    `htt_repeat_expansion` states three penetrance thresholds and cites nothing, which warns in both
    modes by design (RM47/S19) and is the state its README exists to show. If that blocked closing,
    every module carrying a finding no authored edit can clear would be permanently open.
    """
    spec = _open_module(tmp_path, "htt_repeat_expansion")
    assert validate_spec(spec).warnings, "the fixture only means something if it does warn"

    result = close_module(spec)
    assert result.closed and result.warnings == []


# ── Attribution, and the asymmetry between absence and a claim ───────────────────────────────────


def test_a_signed_closure_verifies_and_a_tampered_one_drops_the_block(tmp_path: Path) -> None:
    """An unsigned closure is change-evident; a signed one is attributable.

    The asymmetry under test is the house rule: **absence is a limit, a claim is a claim.** No
    signature is a perfectly legal closure, so it publishes. A signature that does not verify is a
    false claim about who closed the module, so the whole document is dropped rather than published
    with the attribution quietly ignored.
    """
    pem = generate_private_key_pem()
    spec = _open_module(tmp_path)
    assert close_module(spec, closed_by="curator", private_key_pem=pem).signed

    block = _compile(spec, tmp_path / "signed").manifest.verification
    assert block.closure.signature.public_key == public_key_b64_from_pem(pem)
    assert block.closure.closed_by == "curator"

    doc = read_verification(spec / VERIFICATION_JSON)
    forged = doc.closure.signature.model_copy(update={"signature": "AA" + doc.closure.signature.signature[2:]})
    write_verification(doc.model_copy(update={"closure": doc.closure.model_copy(update={"signature": forged})}),
                       spec / VERIFICATION_JSON)

    tampered = _compile(spec, tmp_path / "tampered")
    assert tampered.manifest.verification is None
    assert [w for w in tampered.warnings if "closure is signed" in w]


# ── Records and the closure are different claims about the same bytes ────────────────────────────


def test_closing_keeps_records_over_the_same_bytes_and_drops_records_over_others(
    tmp_path: Path,
) -> None:
    """Two claims, one binding — so re-binding a check to bytes it never saw is the failure to avoid.

    Keeping them while the hash holds is what lets an author enrich, then close, without losing the
    checks. Dropping them when it does not is the same rule the compiler applies at the other end,
    committed here by the tool rather than discovered later by a reader.
    """
    spec = _open_module(tmp_path)
    record = VerificationRecord(check="rsid_currency", subjects=7, findings=0)
    write_verification(
        attest([record], module_binding(authored_input_entries(spec))), spec / VERIFICATION_JSON
    )

    kept = close_module(spec)
    assert kept.dropped_checks == []
    assert [r.check for r in read_verification(spec / VERIFICATION_JSON).records] == ["rsid_currency"]

    variants = spec / "variants.csv"
    variants.write_text(variants.read_text().replace("hemochromatosis", "haemochromatosis"))
    dropped = close_module(spec)
    assert dropped.dropped_checks == ["rsid_currency"]
    assert read_verification(spec / VERIFICATION_JSON).records == []


def test_closing_does_not_claim_to_have_put_the_checks_it_kept(tmp_path: Path) -> None:
    """`producer` names who put the checks, so closing must not stamp its own label over it.

    Caught on the real corpus rather than reasoned about: three reference examples carry an enricher
    attestation, and the first version of this rebuilt the document, which rewrote
    `just-dna-enricher 0.6.0` to `just-dna-compiler 0.6.0` — the compiler claiming it had run an
    enricher's cross-checks, manufactured by an unrelated act. Keeping the document verbatim is also
    what makes "closing re-mines nothing" literally true: the payload is unchanged, so the nonce
    already found over it is still the answer.
    """
    spec = _open_module(tmp_path)
    binding = module_binding(authored_input_entries(spec))
    before = attest(
        [VerificationRecord(check="rsid_currency", subjects=7, findings=0)],
        binding,
        producer="just-dna-enricher 0.6.0",
        produced_at="2026-08-13T23:45:01Z",
    )
    write_verification(before, spec / VERIFICATION_JSON)

    assert close_module(spec).closed
    after = read_verification(spec / VERIFICATION_JSON)
    assert after.producer == "just-dna-enricher 0.6.0"
    assert after.produced_at == "2026-08-13T23:45:01Z"
    assert after.nonce == before.nonce
    assert after.model_copy(update={"closure": None}) == before, "only the closure was added"


def test_reverse_names_the_closure_it_drops_and_says_whose_job_it_is(
    tmp_path: Path, caplog
) -> None:
    """The warning has to describe what was actually lost, not what usually is.

    Reverse cannot re-emit the attestation, and its notice said *the checks were put by the enricher …
    re-run the enricher to re-attest*. That was exact while checks were the only content and became a
    correct sentence aimed at the wrong defect the moment a closure could ride alone — which is now
    thirteen of the sixteen reference examples. Re-running the enricher does not re-close a module and
    could not: only the author may say authoring is finished, and reverse holds no standing to say it
    for them. The RM77 class, on the surface RM73 just changed.
    """
    spec = _open_module(tmp_path)
    assert close_module(spec).closed
    _compile(spec, tmp_path / "a1")

    with caplog.at_level("WARNING", logger="just_dna_compiler.compiler"):
        reverse_module(tmp_path / "a1", tmp_path / "rev")
    dropped = [r.getMessage() for r in caplog.records if "verification attestation" in r.getMessage()]
    assert len(dropped) == 1, caplog.records
    assert "closure" in dropped[0] and "Close" in dropped[0]
    assert "Re-run the enricher" not in dropped[0], "there were no checks to re-attest"

    # And the loss is real, so the assertion cannot pass on the sentence alone.
    assert not (tmp_path / "rev" / VERIFICATION_JSON).exists()
    reversed_compile = _compile(tmp_path / "rev", tmp_path / "a2")
    assert reversed_compile.manifest.verification is None
    assert len(_closure_warnings(reversed_compile.warnings)) == 1


def test_reverse_names_both_when_the_document_carried_both(tmp_path: Path, caplog) -> None:
    """Checks and a closure are two losses with two different parties to fix them."""
    spec = _open_module(tmp_path)
    write_verification(
        attest(
            [VerificationRecord(check="rsid_currency", subjects=7, findings=0)],
            module_binding(authored_input_entries(spec)),
        ),
        spec / VERIFICATION_JSON,
    )
    assert close_module(spec).closed
    _compile(spec, tmp_path / "a1")

    with caplog.at_level("WARNING", logger="just_dna_compiler.compiler"):
        reverse_module(tmp_path / "a1", tmp_path / "rev")
    dropped = [r.getMessage() for r in caplog.records if "verification attestation" in r.getMessage()]
    assert len(dropped) == 1
    assert "Re-run the enricher" in dropped[0] and "close it yourself" in dropped[0]


# ── The corpus ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name", sorted(p.name for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").is_file())
)
def test_every_reference_example_is_closed_and_its_closure_still_describes_it(name: str) -> None:
    """The corpus is the worked answer, so a finished module in it is a closed one.

    This also makes the maintenance burden loud instead of silent. Editing an authored file in an
    example moves its binding, and without this the example would simply start emitting a *stale*
    warning — worse than the unclosed one, and invisible in a suite nobody reads the warnings of.
    Here it fails, and the remedy is one command.
    """
    spec = _EXAMPLES / name
    doc = read_verification(spec / VERIFICATION_JSON)
    assert doc.closure is not None, f"{name} is not closed — run `just-dna-compiler close {spec}`"
    assert attestation_failure(doc, module_binding(authored_input_entries(spec))) is None, (
        f"{name} was edited after it was closed — re-run `just-dna-compiler close {spec}`"
    )
