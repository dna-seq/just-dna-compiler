"""The concordance record through the real compile/reverse paths (RM130).

The classifier and the enricher writer are exercised one tier down. What this file asks is the pair
of questions only the compiler can answer: does the record survive `compile → reverse → compile`
byte for byte once an author has *answered* one of its rows through the overlay, and does the
warning that points at it say the right thing to the right author.

The overlay lap is the load-bearing one. The record is the overlay's input side — a conflict is a
question and an `overrides.csv` row is the answer — so a `suppress` against it is the normal way an
answered subject leaves the built table, and `reverse_module` emits the post-overlay table *plus*
the overlay, which means the suppress applies twice. A mechanism whose intended use broke its own
round trip would not be a mechanism.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_format.manifest import read_manifest

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_CONCORDANCE_HEADER = (
    "variant_key,genotype,authored_clin_sig,authority_concordance,authored_position,opposed,"
    "checked_at\n"
)
_CALLS_HEADER = (
    "variant_key,genotype,authority,status,clin_sig,clin_sig_raw,confidence,confidence_unit,"
    "dataset,checked_at\n"
)
_OVERLAY_HEADER = [
    "table", "subject", "member", "field", "operation", "value", "reason", "decided_by",
    "decided_at",
]


def _example(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    """A writable copy of a published reference example, minus its attestation.

    The attestation binds the authored bytes and this file is about to add to them, so it is dropped
    rather than left to go stale and report on itself.
    """
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / name, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    return spec


def _subjects(spec: Path, limit: int = 2) -> list[tuple[str, str]]:
    """`(variant_key, genotype)` pairs taken from the module's own authored rows.

    Read off `variants.csv` rather than invented, so the record is about subjects the module really
    carries and the orphan cross-check has nothing to say about the fixture.
    """
    with (spec / "variants.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen: list[tuple[str, str]] = []
    for row in rows:
        key = (row.get("variant_key") or row.get("rsid") or "").strip()
        genotype = (row.get("genotype") or "").strip()
        if key and genotype and (key, genotype) not in seen:
            seen.append((key, genotype))
        if len(seen) == limit:
            break
    assert len(seen) == limit, "the fixture example must carry enough authored subjects"
    return seen


def _write_record(spec: Path, subjects: list[tuple[str, str]]) -> None:
    """One contested subject per pair, with ClinVar as the single authority behind each."""
    concordance = [_CONCORDANCE_HEADER]
    calls = [_CALLS_HEADER]
    for key, genotype in subjects:
        concordance.append(
            f"{key},{genotype},pathogenic,single,matches_none,true,2026-08-28T00:00:00Z\n"
        )
        calls.append(
            f"{key},{genotype},clinvar,recorded,benign,Benign,3,review_stars,"
            f"clinvar_2026-08-01,2026-08-28T00:00:00Z\n"
        )
    (spec / "clin_sig_concordance.csv").write_text("".join(concordance), encoding="utf-8")
    (spec / "clin_sig_authority_calls.csv").write_text("".join(calls), encoding="utf-8")


def _write_overlay(spec: Path, rows: list[list[str]]) -> None:
    with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_OVERLAY_HEADER)
        writer.writerows(rows)


# ── the round trip, with the record answered the way the mechanism intends ──────────────────────


def test_answering_a_contested_subject_survives_the_round_trip(tmp_path: Path) -> None:
    """compile → reverse → compile, with a `suppress` answering one of two contested subjects.

    The suppress applies twice on the second lap — `reverse_module` emits the post-overlay table
    beside the overlay — and both identities must hold from the first lap, which is the strict form
    of Principle 7 rather than the "settles by lap three" form.
    """
    spec = _example(tmp_path)
    subjects = _subjects(spec)
    _write_record(spec, subjects)
    answered, genotype = subjects[0]
    _write_overlay(spec, [[
        "clin_sig_concordance.csv", answered, genotype, "", "suppress", "",
        "the 2019 submission this rests on was superseded by our own review of the primary data",
        "curator", "2026-08-28",
    ]])

    first = compile_module(spec, tmp_path / "out1", resolve_with_ensembl=False)
    assert first.success, first.errors
    manifest_one = read_manifest(tmp_path / "out1" / "manifest.json")

    reversed_spec = reverse_module(tmp_path / "out1", tmp_path / "back")
    second = compile_module(reversed_spec, tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors
    manifest_two = read_manifest(tmp_path / "out2" / "manifest.json")

    assert manifest_two.artifact.digest == manifest_one.artifact.digest
    assert content_signature(reversed_spec) == content_signature(spec)
    block_one = manifest_one.clin_sig_concordance
    block_two = manifest_two.clin_sig_concordance
    assert block_one is not None and block_two is not None
    assert block_two.signature == block_one.signature
    assert block_two.calls_signature == block_one.calls_signature


def test_the_answered_subject_leaves_the_table_and_the_evidence_stays(tmp_path: Path) -> None:
    """A suppress removes the question; the authority's own words are not the author's to remove.

    That asymmetry is why only the parent is in the overlay's covered set. An author decides which
    call the module stands behind; they do not get to edit what an archive published, and the detail
    rows outliving the question they belonged to is the correct outcome rather than an orphan.
    """
    spec = _example(tmp_path)
    subjects = _subjects(spec)
    _write_record(spec, subjects)
    answered, genotype = subjects[0]
    _write_overlay(spec, [[
        "clin_sig_concordance.csv", answered, genotype, "", "suppress", "",
        "we hold the original functional data and the archive has not read it", "curator",
        "2026-08-28",
    ]])

    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    parents = pl.read_parquet(tmp_path / "out" / "clin_sig_concordance.parquet")
    calls = pl.read_parquet(tmp_path / "out" / "clin_sig_authority_calls.parquet")
    remaining = set(zip(parents["variant_key"], parents["genotype"], strict=True))
    assert (answered, genotype) not in remaining
    assert remaining == {subjects[1]}
    assert (answered, genotype) in set(zip(calls["variant_key"], calls["genotype"], strict=True))


def test_the_manifest_publishes_the_two_hashes_and_the_two_counts(tmp_path: Path) -> None:
    """Two tables, two fact hashes — a corrected normalization moves every detail row and no verdict.

    And the counts a row count cannot give: how many disagreements cross the pathogenic/benign line,
    and how many subjects the comparison could not finish. Both change what the row count means.
    """
    spec = _example(tmp_path)
    subjects = _subjects(spec)
    _write_record(spec, subjects)

    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    block = read_manifest(tmp_path / "out" / "manifest.json").clin_sig_concordance
    assert block is not None
    assert block.signature and block.calls_signature
    assert block.signature != block.calls_signature
    assert block.row_count == len(subjects)
    assert block.call_count == len(subjects)
    assert block.opposed_count == len(subjects)
    assert block.unchecked_count == 0
    assert block.authorities == ["clinvar"]
    assert block.datasets == ["clinvar_2026-08-01"]
    assert block.concordance_states == ["single"]
    assert block.authored_positions == ["matches_none"]
    # No consensus facet, on any spelling: resolving a split needs a weighting model this format
    # does not have, and a summary field would publish a judgement as a fact.
    assert not {"majority", "consensus", "winner", "resolved"} & set(type(block).model_fields)


def test_a_module_with_no_record_publishes_no_block(tmp_path: Path) -> None:
    """`None`, never a block of zeros. A module the comparison never ran on is not a module where
    nothing is contested, and an all-zero summary reads as the second."""
    spec = _example(tmp_path)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert read_manifest(tmp_path / "out" / "manifest.json").clin_sig_concordance is None


# ── the warning ─────────────────────────────────────────────────────────────────────────────────


def test_the_warning_names_the_overlay_and_never_the_superseded_knob(tmp_path: Path) -> None:
    """`overrides.csv` is where an answer goes; `outranks` is the mechanism 0.7 superseded.

    Both record an authored value beating a source with prose, and the succession was decided in the
    overlay's favour. An author meeting this warning for the first time is exactly who should be
    steered onto the side that survives 1.0, so the text is asserted in both directions.
    """
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    contested = [w for w in result.warnings if "clin_sig_concordance.csv records" in w]
    assert len(contested) == 1, result.warnings
    assert "overrides.csv" in contested[0]
    assert "outranks" not in contested[0]
    assert "opposed calls (pathogenic-class against benign-class)" in contested[0]
    assert "not a defect" in contested[0]


def test_the_finding_carries_its_code_and_an_author_can_clear_it(tmp_path: Path) -> None:
    """Every emission site names a member of the vocabulary, and this one is **not** carried.

    The neighbouring `verification_findings_recorded` is carried because nothing an author writes
    moves the number sitting in `verification.json`. This one is the opposite: the answer is an
    overlay row, the count is taken over the post-overlay table, so writing one clears it — and
    claiming otherwise would tell an author to stop looking at the finding they could have answered.
    """
    from just_dna_format.findings import classify
    from just_dna_format.vocab import CARRIED_WARNING_CODES

    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    manifest = read_manifest(tmp_path / "out" / "manifest.json")
    assert manifest.compilation.warnings_summary.get("clin_sig_concordance_contested") == 1
    carried, _summary = classify(result.warnings)
    assert not [w for w in carried if "clin_sig_concordance.csv records" in w]
    assert "clin_sig_concordance_contested" not in CARRIED_WARNING_CODES


def test_answering_the_last_contested_subject_clears_the_warning(tmp_path: Path) -> None:
    """The finding is counted over the **post-overlay** rows, which is what makes it actionable.

    Demonstrated rather than asserted from the source: the same module warns before the overlay
    exists and does not warn after, and what replaces the finding is the suppression's own record —
    so an answered conflict is visible, not silent.
    """
    spec = _example(tmp_path)
    subjects = _subjects(spec, limit=1)
    _write_record(spec, subjects)
    before = compile_module(spec, tmp_path / "out1", resolve_with_ensembl=False)
    assert any("clin_sig_concordance.csv records" in w for w in before.warnings)

    _write_overlay(spec, [[
        "clin_sig_concordance.csv", subjects[0][0], subjects[0][1], "", "suppress", "",
        "the archive's single submission predates the family study this module is built on",
        "curator", "2026-08-28",
    ]])
    after = compile_module(spec, tmp_path / "out2", resolve_with_ensembl=False)
    assert after.success, after.errors
    assert not [w for w in after.warnings if "clin_sig_concordance.csv records" in w]
    assert any("suppress override(s) remove" in w for w in after.warnings)


def test_validate_reports_the_same_sentence_as_compile(tmp_path: Path) -> None:
    """Parity by check: the pre-flight reads injected bytes and the authored variant list, which is
    the standing test for what belongs in it — and this is the finding an author most wants before a
    compile, since answering it is cheap while the module is open."""
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    validated = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert validated.valid and compiled.success

    sentence = [w for w in validated.warnings if "clin_sig_concordance.csv records" in w]
    assert len(sentence) == 1
    assert sentence[0] in compiled.warnings


def test_the_sentence_is_published_once_although_both_passes_build_it(tmp_path: Path) -> None:
    """The count is embedded and both passes emit it, which is normally the trap.

    It is not one here because no compile step between the two passes touches this table or the
    overlay above it, so both reach a byte-identical sentence and the existing de-duplication
    collapses them. Pinned rather than argued, because the manifest publishing two different numbers
    for one finding is what the rule exists to prevent.
    """
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    published = read_manifest(tmp_path / "out" / "manifest.json").compilation.warnings
    assert len([w for w in published if "clin_sig_concordance.csv records" in w]) == 1


def test_a_record_about_a_variant_the_module_dropped_is_reported(tmp_path: Path) -> None:
    """An orphan means something narrower here than on the sibling tables, and the message says so.

    The record is rebuilt whole on every run rather than merged, so a row cannot outlive the check
    that produced it — an orphan can only mean `variants.csv` was narrowed since, and re-running is
    the remedy rather than editing the table.
    """
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    with (spec / "clin_sig_concordance.csv").open("a", encoding="utf-8") as handle:
        handle.write("rs9999999999,A/G,pathogenic,single,matches_none,true,2026-08-28T00:00:00Z\n")

    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    orphan = [w for w in result.warnings if "no variant in this module carries" in w]
    assert any("rs9999999999" in w and "re-run it" in w for w in orphan), result.warnings


def test_two_records_for_one_subject_are_refused(tmp_path: Path) -> None:
    """The key is `(variant_key, genotype)` and a duplicate under it is two verdicts about one
    contested subject — which is what an overlay row is written against, so the author would be
    answering a question the module states twice."""
    spec = _example(tmp_path)
    subjects = _subjects(spec, limit=1)
    _write_record(spec, subjects)
    with (spec / "clin_sig_concordance.csv").open("a", encoding="utf-8") as handle:
        key, genotype = subjects[0]
        handle.write(f"{key},{genotype},benign,single,matches_none,true,2026-08-28T00:00:00Z\n")

    validated = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not validated.valid and not compiled.success
    assert set(validated.errors) <= set(compiled.errors)


@pytest.mark.parametrize("table", ["clin_sig_concordance.csv", "clin_sig_authority_calls.csv"])
def test_both_tables_are_hashed_into_the_transport_block(tmp_path: Path, table: str) -> None:
    """`manifest.derived` records the bytes so a registry re-splitting a download carries them back.
    A sidecar the publisher moves and the manifest does not attest is the silent-layout failure the
    layout module exists to prevent."""
    spec = _example(tmp_path)
    _write_record(spec, _subjects(spec))
    compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    manifest = read_manifest(tmp_path / "out" / "manifest.json")
    assert table in {entry.name for entry in manifest.derived}
