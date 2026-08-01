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

Both are pinned below, and both are **reported, never repaired**.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id

from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.sequences import (
    RefMismatch,
    SequenceProxy,
    verify_reference_alleles,
)

# chr11:5227002 is the HBB sickle-cell locus; the reference base there is T (checked live, and it is
# what the whole VA ground-truth table in schema/tests/test_vrs.py rests on).
_TRUE_REF = "T"


class _FakeProxy(SequenceProxy):
    """A `SequenceProxy` backed by a literal sequence, so the unit tests need no network.

    Subclassing rather than mocking `get_sequence`: the cache and the offline gate are part of what is
    under test, and this keeps both real.
    """

    def __init__(self, bases: dict[tuple[str, int, int], str]) -> None:
        super().__init__()
        self._bases = bases
        self.reads = 0

    def proxy(self):  # a non-None sentinel: "sequence access is available"
        return object()

    def subsequence(self, accession: str, start: int, end: int):
        key = (accession, start, end)
        if key in self._cache:
            return self._cache[key]
        self.reads += 1
        result = self._bases.get(key)
        self._cache[key] = result
        return result


_CHR11 = "SQ.2NkFm8HK88MqeNkCgj78KidCAXgnsfV1"


def _row(ref: str, **kw) -> ResolutionRow:
    base = dict(variant_key="k", chrom="11", start=5227002, ref=ref, alts="A")
    return ResolutionRow(**{**base, **kw})


# ── the two failure modes ───────────────────────────────────────────────────────────────────────


def test_agreeing_ref_produces_no_finding() -> None:
    proxy = _FakeProxy({(_CHR11, 5227001, 5227002): _TRUE_REF})
    assert verify_reference_alleles([_row(_TRUE_REF)], sequences=proxy) == []


def test_wrong_ref_base_is_reported_even_though_the_id_is_unaffected() -> None:
    """The absorbed case: the minted id is *correct*, and only this check reveals the bad row."""
    proxy = _FakeProxy({(_CHR11, 5227001, 5227002): _TRUE_REF})
    (finding,) = verify_reference_alleles([_row("C")], sequences=proxy)
    assert (finding.claimed, finding.actual) == ("C", _TRUE_REF)
    assert not finding.distorts_the_allele_id
    assert "still the true allele" in str(finding)
    # The reason the check is needed at all: both spellings mint the same id, so nothing downstream
    # could have distinguished them.
    assert derive_vrs_allele_id("11", 5227002, "C", "A") == derive_vrs_allele_id(
        "11", 5227002, _TRUE_REF, "A"
    )


def test_multi_base_ref_claim_is_flagged_as_the_worse_case() -> None:
    """The corrupting case: a longer claim sets the interval, so the id names a different event.

    Reading is always done at the *claimed* length, so the two cases cannot be told apart by comparing
    lengths — what separates them is whether the claim is a single base.
    """
    proxy = _FakeProxy({(_CHR11, 5227001, 5227003): "TG"})
    (finding,) = verify_reference_alleles([_row("TA", alts="T")], sequences=proxy)
    assert finding.distorts_the_allele_id
    assert "DIFFERENT allele" in str(finding)


def test_findings_are_reported_never_repaired() -> None:
    row = _row("C")
    proxy = _FakeProxy({(_CHR11, 5227001, 5227002): _TRUE_REF})
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
    proxy = _FakeProxy({(_CHR11, 5227001, 5227002): _TRUE_REF})
    assert verify_reference_alleles([row], sequences=proxy) == [], why


def test_offline_skips_the_check_without_failing() -> None:
    # A check that cannot run is not a check that passed — but it must not break the enrichment.
    assert verify_reference_alleles([_row("C")], offline=True) == []
    assert SequenceProxy(offline=True).subsequence(_CHR11, 0, 1) is None


def test_repeated_reads_are_cached() -> None:
    proxy = _FakeProxy({(_CHR11, 5227001, 5227002): _TRUE_REF})
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
    bases = {(_CHR11, 5227001, 5227002): _TRUE_REF}
    monkeypatch.setattr(
        "just_dna_enricher.enrich.SequenceProxy", lambda **_kw: _FakeProxy(bases)
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

    assert verify_reference_alleles([_row(_TRUE_REF)]) == []
    (finding,) = verify_reference_alleles([_row("C")])
    assert finding.actual == _TRUE_REF
