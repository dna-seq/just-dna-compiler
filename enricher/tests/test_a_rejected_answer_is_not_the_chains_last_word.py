"""RM382: a link's answer the hosting filter rejects is a miss for the chain, never the identity's absence.

Measured regenerating `reference_examples/pathogenic_clinvar`: HBB `rs613985`, authored as the 13 bp
deletion `C/CATAACAGCATCAG`. The split Ensembl snapshot (`ensembl-variation-2026_07_13-vep116.0`) places
the rsID at `3:159434329 T>G` and nowhere else; the genotype cannot sit on a substitution, so the
hosting filter rejects the only locus. The chain had already counted the rsID as answered, so ClinVar,
which places it at `11:5226724 CATAACAGCATCAG>C` (VCV 4074263), was never asked, and the row was written
`status=not_found` beside a log line saying the source HAS the variant.

The fixture rows are the real bytes: the Ensembl row read off `homo_sapiens-chr3.parquet` of that
release, and the two ClinVar records naming `RS=613985` in the 2026-06-27 GRCh38 VCF (`4074263` and
`4074264`, the second a 1 bp deletion 254 bp downstream that the genotype cannot host either).
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import _load_csv_rows, compile_module
from just_dna_enricher.enrich import EnrichmentError, enrich, orchestration
from just_dna_enricher.sequences import SequenceProxy
from just_dna_format.resolution import ResolutionRow

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm382\n  title: RM382\n  description: d\n  report_title: RM382\n"
)
_RSID = "rs613985"
_GENOTYPE = "C/CATAACAGCATCAG"
#: The split snapshot's only placement of rs613985 (chr3 parquet, row_idx 76361428).
_ENSEMBL = {"id": [_RSID], "chrom": ["3"], "start": [159434329], "ref": ["T"], "alt": ["G"]}
#: ClinVar 2026-06-27, the two records carrying RS=613985.
_CLINVAR = {
    "rsid": [_RSID, _RSID],
    "chrom": ["11", "11"],
    "start": [5226724, 5226978],
    "ref": ["CATAACAGCATCAG", "AG"],
    "alt": ["C", "A"],
}
#: Where the hostable answer is, as the table records it.
_PLACED = ("11", 5226724, "CATAACAGCATCAG", "C")


def _spec(root: Path) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        f"rsid,genotype,state,conclusion,gene\n{_RSID},{_GENOTYPE},risk,c,HBB\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_RSID},29165669\n", encoding="utf-8")
    return spec


def _parquet(root: Path, name: str, rows: dict) -> Path:
    (root / "data").mkdir(parents=True)
    pl.DataFrame(rows).write_parquet(root / "data" / name)
    return root


def _ensembl(root: Path) -> Path:
    return _parquet(root / "ens", "homo_sapiens-chr3.parquet", _ENSEMBL)


def _clinvar(root: Path) -> Path:
    return _parquet(root / "cv", "clinvar-chr11.parquet", _CLINVAR)


def _enrich(spec: Path, **kwargs):
    options = {
        "offline": True,
        "clinvar_cache": spec.parent / "no-clinvar",
        "download": False,
        "use_gnomad": False,
        "verify_ref": False,
        "verify_rsids": False,
        "verify_clinsig": False,
        "verify_datasets": False,
        "mint_vrs": False,
    }
    options.update(kwargs)
    return enrich(spec, **options)


def _rows(spec: Path) -> list[ResolutionRow]:
    rows, errors, _ = _load_csv_rows(spec / "resolution.csv", ResolutionRow, "resolution.csv")
    assert errors == []
    return rows


def test_a_rejected_snapshot_answer_lets_clinvar_place_the_variant(tmp_path: Path) -> None:
    """The measured case: the next link that can place the identity answers it, and the compile is strict."""
    spec = _spec(tmp_path)
    result = _enrich(spec, ensembl_cache=_ensembl(tmp_path), clinvar_cache=_clinvar(tmp_path))
    rows = _rows(spec)
    assert [(r.chrom, r.start, r.ref, r.alts) for r in rows] == [_PLACED]
    assert {(r.source, r.status) for r in rows} == {("clinvar", "resolved")}
    assert result.unresolved == [] and result.allele_mismatches == []
    # The rejected answer is recorded as what it was: the snapshot's locus, superseded by ClinVar's.
    (superseded,) = result.superseded_answers
    assert superseded.rsid == _RSID and superseded.links == ("cache",) and superseded.placed_by == "clinvar"
    assert superseded.loci == ("3:159434329 T>G",)
    compiled = compile_module(spec, tmp_path / "out", strict=True)
    assert compiled.success, compiled.errors


def test_a_rejected_answer_no_later_link_places_is_not_written_as_an_absence(tmp_path: Path) -> None:
    """The snapshot alone: answered and rejected, so no `not_found` row, and the key is unresolved."""
    spec = _spec(tmp_path)
    result = _enrich(spec, ensembl_cache=_ensembl(tmp_path))
    assert [r for r in _rows(spec) if r.variant_key == _RSID] == []
    assert result.unresolved == [_RSID]
    (mismatch,) = result.allele_mismatches
    assert mismatch.links == ("cache",) and mismatch.placed_by is None
    assert mismatch.loci == ("3:159434329 T>G",)
    assert result.superseded_answers == []


def test_every_links_rejected_answer_is_named_when_none_can_host(tmp_path: Path) -> None:
    """Both caches answer and neither can host: the finding names both links, in chain order."""
    spec = _spec(tmp_path)
    # ClinVar's second record only (VCV 4074264): a 1 bp deletion, which a 13 bp one cannot be.
    second = {column: values[1:] for column, values in _CLINVAR.items()}
    clinvar = _parquet(tmp_path / "cv", "clinvar-chr11.parquet", second)
    result = _enrich(spec, ensembl_cache=_ensembl(tmp_path), clinvar_cache=clinvar)
    (mismatch,) = result.allele_mismatches
    assert mismatch.links == ("cache", "clinvar")
    assert mismatch.loci == ("3:159434329 T>G", "11:5226978 AG>A")
    assert [r for r in _rows(spec) if r.variant_key == _RSID] == []


def test_strict_names_the_rejection_rather_than_asking_for_a_cache(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    with pytest.raises(EnrichmentError, match="cannot host") as raised:
        _enrich(spec, ensembl_cache=_ensembl(tmp_path), mode="strict")
    assert _RSID in str(raised.value) and "Provide a complete cache" not in str(raised.value)


def test_a_rederive_keeps_a_recorded_placement_the_run_could_not_reach(tmp_path: Path) -> None:
    """`@rederive-never-shortens`: rejecting the snapshot's answer refutes nothing about ClinVar's row."""
    spec, ensembl = _spec(tmp_path), _ensembl(tmp_path)
    _enrich(spec, ensembl_cache=ensembl, clinvar_cache=_clinvar(tmp_path))
    recorded = _rows(spec)
    assert [(r.chrom, r.start, r.source) for r in recorded] == [("11", 5226724, "clinvar")]
    result = _enrich(spec, ensembl_cache=ensembl, rederive=True)
    assert _rows(spec) == recorded
    assert result.unresolved == []


def test_a_rederive_drops_a_recorded_false_absence(tmp_path: Path) -> None:
    """A pre-RM382 `not_found` row is the defect itself: answered-and-rejected replaces it with no row."""
    spec = _spec(tmp_path)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,genome_build,locus_index,source,status\n"
        f"{_RSID},{_RSID},GRCh38,0,cache,not_found\n",
        encoding="utf-8",
    )
    result = _enrich(spec, ensembl_cache=_ensembl(tmp_path), rederive=True)
    assert [r for r in _rows(spec) if r.variant_key == _RSID] == []
    assert result.unresolved == [_RSID]


class _Unreachable:
    """Live Ensembl, whose request failed (S20)."""

    def resolve_rsid(self, rsid: str):
        return None, None

    def close(self) -> None:
        return None


def test_an_unreachable_later_link_is_asked_for_not_blamed_on_the_genotype(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chain was incomplete, so the refusal asks for the link (`@unreachable-not-absent`)."""
    monkeypatch.setattr(orchestration, "SequenceProxy", lambda **kw: SequenceProxy(offline=True))
    spec = _spec(tmp_path)
    with pytest.raises(EnrichmentError) as raised:
        _enrich(spec, ensembl_cache=_ensembl(tmp_path), offline=False, resolver=_Unreachable(), mode="strict")
    assert "Provide a complete cache" in str(raised.value)
    assert "RM382" not in str(raised.value)


class _Resolver:
    """Live Ensembl, answering with the hostable placement (the chain's fourth link)."""

    def resolve_rsid(self, rsid: str):
        chrom, start, ref, alt = _PLACED
        return [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}], "ensembl-rest"

    def close(self) -> None:
        return None


class _Silent:
    def resolve_rsid(self, rsid: str):
        return [], "ensembl-rest"

    def close(self) -> None:
        return None


class _Gnomad:
    """gnomAD, the last link."""

    unanswered: dict = {}

    def resolve_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        chrom, start, ref, alt = _PLACED
        return {r: [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}] for r in rsids}

    def close(self) -> None:
        return None


@pytest.mark.parametrize(
    ("link", "options"),
    [
        ("clinvar", {"clinvar": True}),
        ("ensembl-rest", {"offline": False, "resolver": _Resolver()}),
        ("gnomad", {"offline": False, "resolver": _Silent(), "use_gnomad": True, "gnomad_client": _Gnomad()}),
    ],
    ids=["clinvar-cache", "live-ensembl", "gnomad"],
)
def test_every_later_link_is_reached_past_a_rejected_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link: str, options: dict
) -> None:
    """The guard: one predicate gates every link, so each of the three after the snapshot is reached.

    The sequence service is kept offline so the online legs read nothing over the network; the hosting
    verdict here is decided from the allele strings (a substitution cannot host a deletion).
    """
    monkeypatch.setattr(orchestration, "SequenceProxy", lambda **kw: SequenceProxy(offline=True))
    spec = _spec(tmp_path)
    options = dict(options)
    if options.pop("clinvar", False):
        options["clinvar_cache"] = _clinvar(tmp_path)
    result = _enrich(spec, ensembl_cache=_ensembl(tmp_path), **options)
    rows = _rows(spec)
    assert [(r.chrom, r.start, r.ref, r.alts) for r in rows] == [_PLACED]
    assert {r.source for r in rows} == {link}
    assert [m.placed_by for m in result.superseded_answers] == [link]


def test_a_subject_that_can_host_the_answer_keeps_it() -> None:
    """Any subject of the rsID hosting a locus (a pair too) keeps the answer: nothing usable is replaced."""
    (locus,) = [{"chrom": "3", "start": 159434329, "ref": "T", "alts": "G"}]
    assert orchestration._rejected_by_every_subject([_GENOTYPE], [locus], None) is True
    assert orchestration._rejected_by_every_subject([_GENOTYPE, "G/T"], [locus], None) is False
    # A subject that names no genotype hosts every locus; none at all is no reason to ask on.
    assert orchestration._rejected_by_every_subject([_GENOTYPE, None], [locus], None) is False
    assert orchestration._rejected_by_every_subject([], [locus], None) is False
