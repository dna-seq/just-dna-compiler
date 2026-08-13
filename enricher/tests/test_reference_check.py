"""The reference-allele check — enrichment as validation of authored data.

The check exists because a VRS allele id is built from *which sequence*, *which interval*, and *what
replaces it* — the reference allele is not a component, since the refget accession plus the interval
already determine it. That is correct and deliberate, but it leaves an authored `ref` unchecked by
minting, in two ways with very different severity — separated by the *claimed* length, since the actual
bases are always read at the claimed length and so cannot differ from it:

* a **single-base** claim is absorbed — the id minted is still the real allele's id, so only this check
  can reveal that the row is wrong;
* a **multi-base** claim sets the interval, so a wrong `ref` mints a well-formed id for a *different
  allele* — the silent-corruption case.

There is a third case, and it is the one that arrives from real authors: the `ref` cell was right all
along and the **coordinate** is off by one, because `start` is the 1-based VCF position and someone
converted it. It reaches this check wearing the first case's clothes — the base at the recorded
position is simply not the one claimed — so the check looks one base either side before deciding, and
says which of the two it found. Reporting a shifted row as a bad `ref` sends the author to a column
that was never wrong, and the old reassurance ("the minted allele id is still the true allele at this
position") is worthless when the position is the defect.

All three are pinned below, and all three are **reported, never repaired**.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.sequences import (
    RefMismatch,
    SequenceProxy,
    summarize_ref_mismatches,
    verify_reference_alleles,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id

# chr11:5227002 is the HBB sickle-cell locus; the reference base there is T (checked live, and it is
# what the whole VA ground-truth table in schema/tests/test_vrs.py rests on).
_TRUE_REF = "T"


_CHR11 = "SQ.2NkFm8HK88MqeNkCgj78KidCAXgnsfV1"

#: GRCh38 chr11, 1-based 5226997..5227008 — the real bases around the sickle locus, read from the
#: public seqrepo. The check now looks one base either side of the claimed span to tell a wrong `ref`
#: from a shifted `start`, so a fake that answers only one hard-coded interval can no longer stand in
#: for the genome: it would make the neighbour probe come back empty and quietly disable the
#: diagnosis under test.
_HBB_WINDOW = "TCTCCTCAGGAG"
_HBB_WINDOW_FIRST_POS = 5226997


class _FakeProxy(SequenceProxy):
    """A `SequenceProxy` backed by a real slice of chr11, so the unit tests need no network.

    Subclassing rather than mocking `get_sequence`: the cache and the offline gate are part of what is
    under test, and this keeps both real. Any interval inside the window is served by slicing, exactly
    as the real proxy would; anything outside returns `None`, which is also what a caller must handle.
    """

    def __init__(self, window: str = _HBB_WINDOW, first_pos: int = _HBB_WINDOW_FIRST_POS) -> None:
        super().__init__()
        self._window = window
        self._first = first_pos
        self.reads = 0

    def proxy(self):  # a non-None sentinel: "sequence access is available"
        return object()

    def subsequence(self, accession: str, start: int, end: int):
        key = (accession, start, end)
        if key in self._cache:
            return self._cache[key]
        self.reads += 1
        # `start`/`end` are interbase; the window's first base is 1-based `_first`.
        lo, hi = start - (self._first - 1), end - (self._first - 1)
        result = self._window[lo:hi] if lo >= 0 and hi <= len(self._window) else None
        if result is not None and len(result) != end - start:
            result = None
        self._cache[key] = result
        return result


def _row(ref: str, **kw) -> ResolutionRow:
    base = {"variant_key": "k", "chrom": "11", "start": 5227002, "ref": ref, "alts": "A"}
    return ResolutionRow(**{**base, **kw})


# ── the two failure modes ───────────────────────────────────────────────────────────────────────


def test_agreeing_ref_produces_no_finding() -> None:
    proxy = _FakeProxy()
    assert verify_reference_alleles([_row(_TRUE_REF)], sequences=proxy).mismatches == []


def test_wrong_ref_base_is_reported_even_though_the_id_is_unaffected() -> None:
    """The absorbed case: the minted id is *correct*, and only this check reveals the bad row.

    `G` rather than any base: neither neighbour of 5227002 is a G, so no coordinate shift explains
    this row and the finding is genuinely about the `ref` cell.
    """
    proxy = _FakeProxy()
    (finding,) = verify_reference_alleles([_row("G")], sequences=proxy).mismatches
    assert (finding.claimed, finding.actual) == ("G", _TRUE_REF)
    assert finding.shift is None
    assert not finding.distorts_the_allele_id
    assert "still the true allele" in str(finding)
    # The reason the check is needed at all: both spellings mint the same id, so nothing downstream
    # could have distinguished them.
    assert derive_vrs_allele_id("11", 5227002, "G", "A") == derive_vrs_allele_id(
        "11", 5227002, _TRUE_REF, "A"
    )


# ── the third case: the coordinate is what is wrong ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("start", "ref", "shift"),
    [
        # 5227003 is C and 5227004 is A: a row authored one base too far left.
        (5227003, "A", 1),
        # 5227004 is A and 5227003 is C: a row authored one base too far right.
        (5227004, "C", -1),
    ],
)
def test_a_shifted_coordinate_is_diagnosed_as_a_coordinate_problem(
    start: int, ref: str, shift: int
) -> None:
    """A `pos - 1` conversion is reported as a shifted `start`, not as a bad `ref`.

    This is the failure that reaches the check in the wild, and the old message sent the author to
    the wrong column: it named `ref` as the disagreement and then reassured them that "the minted
    allele id is still the true allele at this position" — true of the position recorded, and
    worthless when the position is the thing that is wrong.
    """
    (finding,) = verify_reference_alleles([_row(ref, start=start)], sequences=_FakeProxy()).mismatches
    assert finding.shift == shift
    # A shifted row mints an id at the wrong place, whatever the claimed length.
    assert finding.distorts_the_allele_id
    minted_here = derive_vrs_allele_id("11", start, ref, "G")
    assert minted_here is not None
    assert minted_here != derive_vrs_allele_id("11", start + shift, ref, "G")
    message = str(finding)
    assert f"off by {shift}" in message
    assert "still the true allele" not in message


def test_an_ambiguous_neighbour_claims_no_shift() -> None:
    """5227001 and 5227003 are both C, so a claimed C at 5227002 could have shifted either way.

    Two candidate directions is an unknown, and the house rule is to withhold rather than pick one:
    the finding falls back to reporting the disagreement without asserting a cause.
    """
    (finding,) = verify_reference_alleles([_row("C")], sequences=_FakeProxy()).mismatches
    assert finding.shift is None
    assert "off by" not in str(finding)


def test_findings_are_grouped_by_cause_not_listed_per_row() -> None:
    """One systematic mistake is one line. See `summarize_ref_mismatches`."""
    shifted = [_row("A", start=5227003, variant_key=f"k{i}") for i in range(40)]
    findings = verify_reference_alleles(shifted + [_row("G")], sequences=_FakeProxy()).mismatches
    assert len(findings) == 41

    lines = summarize_ref_mismatches(findings)
    assert len(lines) == 2, lines
    shift_line = next(line for line in lines if "shifted" in line)
    assert shift_line.startswith("40 row(s)")
    assert "and 37 more" in shift_line


def test_multi_base_ref_claim_is_flagged_as_the_worse_case() -> None:
    """The corrupting case: a longer claim sets the interval, so the id names a different event.

    Reading is always done at the *claimed* length, so the two cases cannot be told apart by comparing
    lengths — what separates them is whether the claim is a single base.
    """
    proxy = _FakeProxy()
    (finding,) = verify_reference_alleles([_row("TA", alts="T")], sequences=proxy).mismatches
    assert finding.distorts_the_allele_id
    assert "DIFFERENT allele" in str(finding)


def test_findings_are_reported_never_repaired() -> None:
    row = _row("C")
    proxy = _FakeProxy()
    verify_reference_alleles([row], sequences=proxy)
    assert row.ref == "C"  # untouched — the evidence of the upstream error survives


# ── what is deliberately not checked ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("row", "why"),
    [
        (ResolutionRow(variant_key="k", rsid="rs334"), "no coordinate — nothing to compare"),
        (_row("<DEL>"), "a symbolic allele is not ACGT (RM5)"),
        (
            ResolutionRow(variant_key="k", chrom="GL000009.2", start=100, ref="T"),
            "a contig with no refget accession",
        ),
    ],
)
def test_unverifiable_rows_abstain_rather_than_guess(row: ResolutionRow, why: str) -> None:
    proxy = _FakeProxy()
    assert verify_reference_alleles([row], sequences=proxy).mismatches == [], why


def test_offline_skips_the_check_without_failing() -> None:
    # A check that cannot run is not a check that passed — but it must not break the enrichment.
    assert verify_reference_alleles([_row("C")], offline=True).mismatches == []
    assert SequenceProxy(offline=True).subsequence(_CHR11, 0, 1) is None


def test_repeated_reads_are_cached() -> None:
    proxy = _FakeProxy()
    verify_reference_alleles([_row("C"), _row("C"), _row("G")], sequences=proxy)
    assert proxy.reads == 1  # one interval, one round trip


# ── severity follows the mode, through enrich() ─────────────────────────────────────────────────

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    # An authored coordinate row claiming the WRONG reference base at a real locus.
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion\n"
        "11,5227002,C,A,A/C,risk,wrong ref on purpose\n"
    )
    (spec / "studies.csv").write_text("chrom,start,ref,pmid\n11,5227002,C,12345678\n")
    return spec


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {"id": ["rs1"], "chrom": ["11"], "start": [5227002], "ref": ["T"], "alt": ["A"]}
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


def _patched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route the enrichment's sequence reads at the fake proxy (no network in the unit suite)."""
    monkeypatch.setattr(
        "just_dna_enricher.enrich.SequenceProxy", lambda **_kw: _FakeProxy()
    )


def test_best_effort_reports_the_mismatch_and_still_writes(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patched(monkeypatch)
    spec = _spec(tmp_path)
    result = enrich(spec, offline=False, download=False, use_gnomad=False,
                    ensembl_cache=cache, clinvar_cache=tmp_path / "none")
    assert len(result.ref_mismatches) == 1
    assert isinstance(result.ref_mismatches[0], RefMismatch)
    assert (spec / "resolution.csv").exists()   # best_effort still produces a table


def test_strict_refuses_a_module_that_contradicts_the_genome(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patched(monkeypatch)
    spec = _spec(tmp_path)
    with pytest.raises(EnrichmentError, match="disagree with the GRCh38 reference"):
        enrich(spec, mode="strict", download=False, use_gnomad=False,
               ensembl_cache=cache, clinvar_cache=tmp_path / "none")


def test_verify_ref_can_be_turned_off(
    tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patched(monkeypatch)
    spec = _spec(tmp_path)
    result = enrich(spec, verify_ref=False, download=False, use_gnomad=False,
                    ensembl_cache=cache, clinvar_cache=tmp_path / "none")
    assert result.ref_mismatches == []


@pytest.mark.integration
def test_against_the_real_reference_sequence() -> None:
    """The unit tests above trust `_TRUE_REF`; this one earns it from the live sequence service."""
    import os

    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("reads the live sequence service — set JUST_DNA_NETWORK_TESTS=1 to run")

    assert verify_reference_alleles([_row(_TRUE_REF)]).mismatches == []
    (finding,) = verify_reference_alleles([_row("C")]).mismatches
    assert finding.actual == _TRUE_REF
