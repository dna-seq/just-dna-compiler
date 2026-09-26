"""RM274: an indel undecided from the allele strings is settled with the reference, or stays undecided.

`hosting_verdict` withholds when the event sizes agree and the payloads differ, because inside a
repeat that is either one event anchored twice or two events. The enricher holds the reference, so it
slides the locus's indel across its repeat and asks whether the genotype's payload is one of its
spellings. The bases are GRCh38 `2:166204460..166204490`, read from Ensembl's sequence endpoint on
2026-09-27; `rs77944059` deletes `CAAA` there, anchored by Ensembl at `166204477`.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.resolution import hosting_verdict
from just_dna_enricher import enrich as enrich_module
from just_dna_enricher.enrich import _settle_by_reference, enrich
from just_dna_enricher.sequences import SequenceProxy, _indel_payloads

_FIRST = 166204460
_CHR2 = "CCAAGGTAAAGAAACAAACAAAAAATAAATG"
_LOCUS = {"chrom": "2", "start": 166204477, "ref": "ACAAA", "alts": "A"}


def _read(chrom: str, start: int, end: int) -> str | None:
    """The window, clipped to what the test holds; a read wholly outside it is unreadable."""
    if chrom != "2":
        return None
    lo, hi = max(start, _FIRST), min(end, _FIRST + len(_CHR2) - 1)
    return _CHR2[lo - _FIRST : hi - _FIRST + 1] if lo <= hi else None


def test_the_payload_set_is_every_rotation_the_repeat_allows() -> None:
    assert _indel_payloads("2", 166204477, "ACAAA", "A", _read) == {"AAAC", "AACA", "ACAA", "CAAA"}


@pytest.mark.parametrize(
    ("genotype", "expected"),
    [
        ("G/GAAAC", True),  # the leftmost spelling's payload: one event, anchored elsewhere
        ("G/GTTTT", False),  # the same size, and no spelling of the locus carries it
        ("G/G", None),  # homozygous: nothing to be relative to, which no reference changes
    ],
)
def test_the_settle_is_three_valued(genotype: str, expected: bool | None) -> None:
    assert _settle_by_reference(genotype, _LOCUS, _read) is expected


def test_the_strings_alone_withhold_on_both_cases_the_reference_settles() -> None:
    """The precondition: without the reference these are arm 9, not a verdict."""
    assert hosting_verdict("G/GAAAC", "ACAAA", "A") is None
    assert hosting_verdict("G/GTTTT", "ACAAA", "A") is None


def test_an_unreadable_reference_leaves_it_undecided() -> None:
    assert _settle_by_reference("G/GAAAC", _LOCUS, lambda _c, _s, _e: None) is None


def test_enrich_keeps_the_same_event_and_drops_the_different_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs77944059", "rs1"],
            "chrom": ["2", "2"],
            "start": [166204477, 166204477],
            "ref": ["ACAAA", "ACAAA"],
            "alt": ["A", "A"],
        }
    ).write_parquet(data / "chr2.parquet")
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    )
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs77944059,G/GAAAC,risk,c\nrs1,G/GTTTT,risk,c\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs77944059,9545397\n")

    class _Proxy(SequenceProxy):
        """The run's real proxy, answering from the test's window instead of seqrepo."""

        def proxy(self) -> None:  # the later reference-allele check skips, as it does offline
            return None

        def subsequence(self, accession: str, start: int, end: int) -> str | None:
            return _read("2", start + 1, end)

    monkeypatch.setattr(enrich_module, "SequenceProxy", _Proxy)
    result = enrich(
        spec, offline=True, ensembl_cache=tmp_path / "cache", clinvar_cache=tmp_path, mint_vrs=False
    )
    placed = {r.rsid: (r.chrom, r.start) for r in result.rows if r.chrom}
    assert placed == {"rs77944059": ("2", 166204477)}
    assert "rs1" in result.unresolved
