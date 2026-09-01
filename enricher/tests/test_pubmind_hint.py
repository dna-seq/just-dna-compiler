"""The `hint variant` leg that asks PubMind, and the spelling it compares on.

Written because the leg had no test at all. `select_by_positions` normalizes the chromosome on both
sides, so the records come back for `chr17` as readily as for `17` — and the filter in `lookup.py`
then compared them against the caller's own spelling, matched nothing, and reported the empty result
as an established absence in PubMind's corpus. A fabricated negative in the exact case the surface
exists for: `hint.loci` is filled by an rsID lookup, and PubMind's channel is coordinate-keyed with
most of its rows carrying no rs-number, so a coordinate-only query has no normalized locus to fall
back on.

The fixture is `assets/hg38_pubmind_db_slice.txt.gz`, cut from the real table, and every coordinate
asserted here is read back out of the built snapshot at runtime rather than pasted.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME
from just_dna_enricher.lookup import VariantHint, _lookup_pubmind
from just_dna_enricher.pubmind_build import build_snapshot

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "hg38_pubmind_db_slice.txt.gz"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory):
    return build_snapshot(_SLICE, tmp_path_factory.mktemp("pubmind")).out_dir


@pytest.fixture(scope="module")
def allele(snapshot):
    """One real record from the fixture, as `(chrom, start, ref, alt)`."""
    frame = pl.read_parquet(snapshot / SNAPSHOT_DATA_DIRNAME / "pubmind.parquet")
    row = frame.row(0, named=True)
    return str(row["chrom"]), int(row["start"]), str(row["ref"]), str(row["alt"])


@pytest.mark.parametrize("spelling", ["bare", "chr_prefixed", "lowercase_bases"])
def test_the_corpus_answers_the_same_whichever_spelling_the_caller_typed(
    snapshot, allele, spelling
):
    """`chr17` and `17` are one chromosome, and the leg must not decide otherwise.

    Parametrized over the three spellings a caller really types rather than asserted for one, because
    the defect was a comparison that happened to agree with the fixture's own spelling — a test using
    only the bare form passes on the broken code and proves nothing.
    """
    chrom, start, ref, alt = allele
    if spelling == "chr_prefixed":
        chrom = f"chr{chrom}"
    elif spelling == "lowercase_bases":
        ref, alt = ref.lower(), alt.lower()

    hint = VariantHint()
    _lookup_pubmind(hint, snapshot, (chrom, start, ref, alt))

    assert hint.pubmind, (
        f"{spelling}: the corpus holds a record at this allele and the leg reported none"
    )
    assert not any("holds no record" in str(finding) for finding in hint.findings), (
        f"{spelling}: an established absence was reported over records the query returned"
    )


def test_an_allele_the_corpus_really_lacks_is_still_reported_as_an_absence(snapshot, allele):
    """The negative must survive the repair: normalizing must not make every query match.

    Same chromosome and position, a different ALT — the record is there and this allele is not, which
    is the state the absence finding is for.
    """
    chrom, start, ref, alt = allele
    other = next(base for base in "ACGT" if base not in {ref.upper(), alt.upper()})

    hint = VariantHint()
    _lookup_pubmind(hint, snapshot, (chrom, start, ref, other))

    assert not hint.pubmind
    assert any("holds no record" in str(finding) for finding in hint.findings), (
        "an allele the corpus does not carry must still be reported as an absence"
    )
