"""The compiler's half of RM45: read the attestation, confirm it, stamp it — or drop it and say so.

Run against real reference examples through the real `compile_module`, never a mocked read: the whole
claim being tested is that the block appears exactly when the module's own bytes still match what was
checked, and only a real compile of a real spec can establish that.

The stale path is exercised by **editing a module after attesting it** rather than by hand-corrupting
the document, because that is the failure that actually happens and the one the item is about.
"""

import json
import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    authored_input_entries,
    compile_module,
    reverse_module,
    validate_spec,
)
from just_dna_format import verification as verification_module
from just_dna_format.layout import DERIVED_SUBDIR, VERIFICATION_JSON
from just_dna_format.manifest import VerificationRecord
from just_dna_format.verification import (
    attest,
    module_binding,
    read_verification,
    write_verification,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_EASY = 8  # bits; the mechanism, not the cost


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    """Lower the difficulty for the cases that are about the compiler rather than about the work.

    Patched on the module global rather than passed at each call, because that is what the compiler's
    own reader consults — `attestation_failure` reads the constant in its body precisely so this is
    possible. At the shipped 20 bits every case here would mine for about a second, which buys nothing
    a single case cannot prove: `test_the_shipped_difficulty_compiles_too` runs unpatched, and the
    schema suite pins the constant itself.
    """
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


def _module(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    spec = tmp_path / name
    shutil.copytree(_EXAMPLES / name, spec)
    return spec


def _records() -> list[VerificationRecord]:
    return [
        VerificationRecord(
            check="clinical_significance", subjects=7, findings=1,
            source="clinvar", release="2026-06-27",
        ),
        VerificationRecord(check="reference_allele", skipped="offline", detail="no egress"),
    ]


def _attest(spec: Path, *, records=None, where: Path | None = None) -> Path:
    """Attest the module as it stands right now, which is what the enricher does at the end of a run."""
    doc = attest(
        records or _records(),
        module_binding(authored_input_entries(spec)),
        producer="test-suite 0",
        produced_at="2026-08-13T00:00:00Z",
        difficulty=_EASY,
    )
    return write_verification(doc, where or spec / VERIFICATION_JSON)


def _compile(spec: Path, out: Path):
    result = compile_module(spec, out)
    assert result.success, result.errors
    return result


# ── the block appears, and carries what it should ────────────────────────────────────────────────


def test_a_module_with_no_attestation_says_nothing_and_says_it_silently(tmp_path: Path) -> None:
    """The ordinary case. An unverified module is not a finding, so nothing is warned about."""
    result = _compile(_module(tmp_path), tmp_path / "out")
    assert result.manifest.verification is None
    assert not [w for w in result.warnings if VERIFICATION_JSON in w]


def test_an_attestation_over_these_bytes_is_stamped_into_the_manifest(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    _attest(spec)
    result = _compile(spec, tmp_path / "out")

    block = result.manifest.verification
    assert block is not None
    assert block.module_hash == module_binding(authored_input_entries(spec))
    assert {r.check for r in block.checks} == {"clinical_significance", "reference_allele"}
    ran = next(r for r in block.checks if r.check == "clinical_significance")
    assert (ran.subjects, ran.findings, ran.release) == (7, 1, "2026-06-27")
    skipped = next(r for r in block.checks if r.check == "reference_allele")
    assert skipped.skipped == "offline" and skipped.subjects == 0


def test_the_block_survives_being_written_and_read_back(tmp_path: Path) -> None:
    """`manifest.json` is what a downloader actually holds, so the block must survive the JSON."""
    spec = _module(tmp_path)
    _attest(spec)
    out = tmp_path / "out"
    _compile(spec, out)
    written = json.loads((out / "manifest.json").read_text())["verification"]
    assert {c["check"] for c in written["checks"]} == {"clinical_significance", "reference_allele"}
    assert written["producer"] == "test-suite 0"


# ── the stale path: edit the module, watch the block go ──────────────────────────────────────────


def test_editing_the_module_after_attesting_drops_the_block_with_a_warning(tmp_path: Path) -> None:
    """The failure this item is about, reproduced the way it happens.

    The compile still SUCCEEDS: dropping the block was chosen over refusing, because the goal is that
    a stale record never becomes a published claim, not that it be impossible to write while editing.
    """
    spec = _module(tmp_path)
    _attest(spec)
    assert _compile(spec, tmp_path / "before").manifest.verification is not None

    variants = spec / "variants.csv"
    variants.write_text(variants.read_text().replace("hemochromatosis", "haemochromatosis"))

    after = _compile(spec, tmp_path / "after")
    assert after.manifest.verification is None
    stale = [w for w in after.warnings if VERIFICATION_JSON in w and "stale" in w]
    assert len(stale) == 1, after.warnings
    assert "edited since the checks ran" in stale[0]


def test_the_pre_flight_reports_the_same_staleness(tmp_path: Path) -> None:
    """`validate` must not bless what `compile` complains about — the standing parity rule."""
    spec = _module(tmp_path)
    _attest(spec)
    (spec / "variants.csv").write_text((spec / "variants.csv").read_text() + "\n")

    report = validate_spec(spec)
    assert report.valid, report.errors
    assert [w for w in report.warnings if VERIFICATION_JSON in w]


def test_the_warning_is_not_printed_twice(tmp_path: Path) -> None:
    """`compile_module` runs the pre-flight and then re-reads; one finding, one sentence."""
    spec = _module(tmp_path)
    _attest(spec)
    (spec / "variants.csv").write_text((spec / "variants.csv").read_text() + "\n")
    warnings = _compile(spec, tmp_path / "out").warnings
    assert len([w for w in warnings if VERIFICATION_JSON in w]) == 1


def test_an_attestation_lifted_from_another_module_is_dropped(tmp_path: Path) -> None:
    """Copying a whole document across is the other accidental forgery, and it fails on the binding."""
    source = _module(tmp_path, "hfe_hemochromatosis")
    target = _module(tmp_path, "shox_par1")
    _attest(source)
    shutil.copy(source / VERIFICATION_JSON, target / VERIFICATION_JSON)

    result = _compile(target, tmp_path / "out")
    assert result.manifest.verification is None
    assert [w for w in result.warnings if "different module bytes" in w]


def test_an_unreadable_document_is_reported_rather_than_fatal(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    (spec / VERIFICATION_JSON).write_text("{ not json")
    result = _compile(spec, tmp_path / "out")
    assert result.manifest.verification is None
    assert [w for w in result.warnings if "could not be read" in w]


# ── layout, and the guard that catches a typo'd name ─────────────────────────────────────────────


def test_the_attestation_may_live_under_derived(tmp_path: Path) -> None:
    """It is a machine-written sidecar, so it takes both legal places (RM49)."""
    spec = _module(tmp_path)
    (spec / DERIVED_SUBDIR).mkdir()
    _attest(spec, where=spec / DERIVED_SUBDIR / VERIFICATION_JSON)
    result = _compile(spec, tmp_path / "out")
    assert result.manifest.verification is not None
    assert any(entry.name.endswith(VERIFICATION_JSON) for entry in result.manifest.derived)


def test_two_copies_are_refused_rather_than_preferred(tmp_path: Path) -> None:
    """Two attestations are two claims; neither may be silently picked. Nothing is published."""
    spec = _module(tmp_path)
    _attest(spec)
    (spec / DERIVED_SUBDIR).mkdir()
    shutil.copy(spec / VERIFICATION_JSON, spec / DERIVED_SUBDIR / VERIFICATION_JSON)
    result = _compile(spec, tmp_path / "out")
    assert result.manifest.verification is None
    assert [w for w in result.warnings if "same table in two places" in w]


def test_a_mistyped_attestation_name_is_a_near_miss_rather_than_an_ignored_file(
    tmp_path: Path,
) -> None:
    """The guard reads `.json` now, so a typo here is as visible as a typo'd table name.

    Demonstrated in both directions: the typo warns, and a legitimate unknown json file (a registry's
    receipt, named in S16 as a tolerated file) still does not — the tolerance the guard sits beside.
    """
    spec = _module(tmp_path)
    _attest(spec, where=spec / "verifcation.json")
    (spec / "published.json").write_text("{}")
    warnings = _compile(spec, tmp_path / "out").warnings
    assert [w for w in warnings if "verifcation.json" in w]
    assert not [w for w in warnings if "published.json" in w]


# ── identity: the attestation moves nothing ──────────────────────────────────────────────────────


def test_attesting_a_module_moves_neither_identity(tmp_path: Path) -> None:
    """Evidence ABOUT a compile is not the authored data, so re-running checks must not re-mint it."""
    plain = _module(tmp_path, "hfe_hemochromatosis")
    attested = _module(tmp_path / "second", "hfe_hemochromatosis")
    _attest(attested)

    a = _compile(plain, tmp_path / "a").manifest
    b = _compile(attested, tmp_path / "b").manifest
    assert a.artifact.digest == b.artifact.digest
    assert a.content_signature == b.content_signature
    assert a.compilation.resolution_signature == b.compilation.resolution_signature


def test_reverse_does_not_re_emit_the_attestation(tmp_path: Path) -> None:
    """And it must not: `reverse` rebuilds a spec from the artifact, where the document is not.

    Same class as `rsid_alternates` — the data does not exist for reverse to emit, and inventing one
    would be minting an attestation nothing put. The recompiled module simply carries no block, which
    is the correct *says nothing*.
    """
    spec = _module(tmp_path)
    _attest(spec)
    out = tmp_path / "out"
    _compile(spec, out)
    rebuilt = tmp_path / "rev"
    reverse_module(out, rebuilt)
    assert not (rebuilt / VERIFICATION_JSON).exists()
    assert _compile(rebuilt, tmp_path / "out2").manifest.verification is None


def test_the_document_the_enricher_would_write_is_the_one_the_compiler_accepts(
    tmp_path: Path,
) -> None:
    """The two tiers agree on the binding by calling one function, not by both being careful."""
    spec = _module(tmp_path)
    path = _attest(spec)
    doc = read_verification(path)
    assert doc.module_hash == module_binding(authored_input_entries(spec))
    assert _compile(spec, tmp_path / "out").manifest.verification is not None


def test_the_shipped_difficulty_compiles_too(tmp_path: Path, monkeypatch) -> None:
    """One unpatched case, so the default path is exercised rather than assumed.

    Everything above lowers the difficulty to keep the suite quick; if the real constant and the real
    reader ever disagreed, only this case would notice.
    """
    monkeypatch.undo()
    spec = _module(tmp_path)
    doc = attest(_records(), module_binding(authored_input_entries(spec)), producer="test-suite 0")
    write_verification(doc, spec / VERIFICATION_JSON)
    assert _compile(spec, tmp_path / "out").manifest.verification is not None


# ── review regression: an empty table is not a resolved one ─────────────────────────────────────


def test_a_header_only_resolution_table_stamps_no_signature(tmp_path: Path) -> None:
    """`resolution_signature is not None` must keep meaning "this module was resolved".

    Stamping wherever the sidecar merely *exists* publishes the empty-set hash for a header-only file,
    which is a signature naming a table that resolved nothing — and in the deprecated `ensembl_cache`
    branch it is worse than cosmetic: an empty table is falsy, so the DuckDB path runs and the manifest
    would name an injected table that shaped none of the bytes. That is the same false claim the
    `--no-resolve` warning below it refuses to make.
    """
    spec = _module(tmp_path)
    header = (spec / "resolution.csv").read_text().splitlines()[0]
    (spec / "resolution.csv").write_text(header + "\n")

    manifest = _compile(spec, tmp_path / "out").manifest
    assert manifest.compilation.resolution_signature is None
    assert manifest.compilation.resolution_sources == []


def test_a_populated_table_still_stamps(tmp_path: Path) -> None:
    """The other half, so the guard cannot be "fixed" by never stamping."""
    spec = _module(tmp_path)
    manifest = _compile(spec, tmp_path / "out").manifest
    assert manifest.compilation.resolution_signature is not None


def test_reverse_says_the_attestation_cannot_be_carried(tmp_path: Path, caplog) -> None:
    """A round trip drops `manifest.verification`, and the silence about it was the defect (D2).

    `verification.json` records checks the *enricher* put against sources the compiler does not
    reach, and it is bound by hash to the authored bytes, so `reverse_module` has nothing to rebuild
    one from and must not invent one. That part is right. What was wrong is that a module and its own
    round trip then disagreed about a **published** field with nothing edited —
    `manifest.compilation.warnings` is a surface consumers parse (RM44), and `manifest.verification`
    is read the same way — and no output anywhere said the record had been dropped. Losing what was
    checked is acceptable; losing it invisibly is the S16 silent-success shape.
    """
    spec = _module(tmp_path)
    _attest(spec)
    first = _compile(spec, tmp_path / "a1")
    assert first.manifest.verification is not None

    with caplog.at_level("WARNING", logger="just_dna_compiler.compiler"):
        reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert any("verification attestation" in record.message for record in caplog.records)

    # And the loss the warning is about is real, so the test cannot pass by the warning alone.
    assert not (tmp_path / "rev" / VERIFICATION_JSON).exists()
    assert _compile(tmp_path / "rev", tmp_path / "a2").manifest.verification is None


def test_reverse_is_quiet_for_a_module_that_was_never_attested(tmp_path: Path, caplog) -> None:
    """Nothing was lost, so there is nothing to say — the other half of the guard."""
    spec = _module(tmp_path)
    _compile(spec, tmp_path / "a1")
    with caplog.at_level("WARNING", logger="just_dna_compiler.compiler"):
        reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert not [r for r in caplog.records if "verification attestation" in r.message]
