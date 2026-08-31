"""S85: an rsID the source HAS, whose loci the allele-aware filter rejected, is not `not_found`.

The reported case is a longevity module authored from a paper whose supplementary is GRCh37/hg19:
five subjects resolved to nothing and were written into `resolution.csv` as `status: not_found`,
which reads as *this source has never heard of your rsID*. Ensembl has all five. What failed was
allele matching — the paper spells the submitted strand, so its `G/A` meets GRCh38's `C/T`.

Two different states of the world were producing byte-identical rows, which is the collapse RM98
fixed one branch over (`unreachable_rsids` vs `unconsulted_rsids`) arriving from a third direction:
there the asking never happened, here it *succeeded* and the answer did not match.

`rs61849494` is one of the five, at its real GRCh38 coordinate.
"""

import logging
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.enrich import enrich

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: s85\n  title: S85\n  description: d\n  report_title: S85\n"
)


def _spec(tmp_path: Path, genotype: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        f"rsid,genotype,state,conclusion,gene\nrs61849494,{genotype},risk,c,GENE\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs61849494,25741868\n", encoding="utf-8")
    return spec


def _cache(tmp_path: Path, rsid: str, ref: str, alt: str) -> Path:
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"id": [rsid], "chrom": ["1"], "start": [11856378],
                  "ref": [ref], "alt": [alt]}).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


def test_a_rejected_locus_is_recorded_as_a_mismatch_not_as_an_absence(tmp_path: Path) -> None:
    """The reported case: the snapshot HAS rs61849494, and the authored alleles are its complement."""
    result = enrich(
        _spec(tmp_path, "A/G"), offline=True,
        ensembl_cache=_cache(tmp_path, "rs61849494", "C", "T"),
    )
    assert [m.rsid for m in result.allele_mismatches] == ["rs61849494"]
    found = result.allele_mismatches[0]
    assert found.strand_flip is True
    # It names what it compared against, so the author can see the other strand rather than guess.
    assert found.loci == ("1:11856378 C>T",)
    assert found.genotype == "A/G"
    # The row itself is untouched: still written, still honestly unresolved.
    assert result.unresolved == ["rs61849494"]


def test_a_source_that_genuinely_lacks_the_rsid_records_no_mismatch(tmp_path: Path) -> None:
    """The other side of the distinction, and the one that must keep reading `not_found`.

    Without this the change would merely relabel every absence, which is the failure it exists to
    stop: `not_found` is a *fact* when the source was asked and has no record, and stays one.
    """
    result = enrich(
        _spec(tmp_path, "A/G"), offline=True,
        ensembl_cache=_cache(tmp_path, "rs99999999", "A", "G"),
    )
    assert result.allele_mismatches == []
    assert [r.status for r in result.rows] == ["not_found"]
    assert result.unresolved == ["rs61849494"]


def test_the_two_states_were_indistinguishable_in_the_row_and_still_are(tmp_path: Path) -> None:
    """Why a structured finding rather than a new status member — and the honest limit of the fix.

    The rows really are byte-identical across the two runs above, deliberately: `status` is provenance
    and sits outside `RESOLUTION_FACT_FIELDS`, while dropping the row entirely would move
    `resolution_signature` (`variant_key` and `rsid` are fact fields). So the artifact is unchanged
    and the distinction lives in the result object, where a caller can surface it. Pinning it here
    means a later change to the row cannot happen silently.
    """
    absent = enrich(_spec(tmp_path / "a", "A/G"), offline=True,
                    ensembl_cache=_cache(tmp_path / "a", "rs99999999", "A", "G"))
    rejected = enrich(_spec(tmp_path / "b", "A/G"), offline=True,
                      ensembl_cache=_cache(tmp_path / "b", "rs61849494", "C", "T"))

    def shape(result):
        return [(r.rsid, r.status, r.chrom, r.start) for r in result.rows]

    assert shape(absent) == shape(rejected)
    # ...and the result object is what tells them apart.
    assert (absent.allele_mismatches == []) and (rejected.allele_mismatches != [])


def test_the_run_reports_the_mismatch_once_and_names_the_strand(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """One aggregated line, not one per subject — and it must contradict the `not_found` reading.

    An author greps the artifact, sees `not_found`, and concludes the source lacks the variant. This
    line is what stops that, so it says the source *has* them in as many words.
    """
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.enrich"):
        enrich(_spec(tmp_path, "A/G"), offline=True,
               ensembl_cache=_cache(tmp_path, "rs61849494", "C", "T"))
    lines = [r.getMessage() for r in caplog.records if "cannot host" in r.getMessage()
             and "rsID(s)" in r.getMessage()]
    assert len(lines) == 1
    assert "The source HAS these variants" in lines[0]
    assert "other strand" in lines[0] and "rs61849494" in lines[0]
