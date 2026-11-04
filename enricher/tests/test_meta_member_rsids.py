"""The rsID-merge check runs over `meta.csv` members too (0.8, RM28's residual; PT2 §5 B1 step 5).

Two rows of one meta key are a refused duplicate, and two nesting keys are a difference precedence
settles. What neither catches is **one variant under two keys**: the archive's one case was IL6R's
rs8192284, merged into rs2228145 and seeded with two tiers. NCBI is the merge oracle, and the enricher's
rsID currency pass is where it is asked — so the pass asks it of every rsID a meta member names, not only
of the rows `resolution.csv` carries. A member naming a merged id is the shape that hides it: it matches
nothing in a module that carries the surviving id, and the merge is the diagnosis.
"""

from pathlib import Path

import pytest
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.enrich.subjects import meta_member_rsids
from just_dna_enricher.identifiers import RsidStatus

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: il6r\n"
    "  title: IL6R\n"
    "  description: one variant under two rsIDs\n"
    "  report_title: IL6R\n"
    "genome_build: GRCh38\n"
    "tier_scale: probe\n"
)
_VARIANTS = "rsid,chrom,start,ref,alts,genotype,state,conclusion\nrs2228145,1,154454494,A,C,A/C,risk,c\n"
_STUDIES = "rsid,pmid\nrs2228145,22421339\n"
_META = (
    "members,tier\n"
    "variants[variant_key=rs8192284],B\n"
    "variants[variant_key=rs2228145],A\n"
    '"pharm_variants[rsid=rs1800562, drug=x]",C\n'
    "variants[gene=IL6R],D\n"
)


def _spec(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    (directory / "meta.csv").write_text(_META, encoding="utf-8")
    return directory


def test_the_rsids_a_member_names_are_read_off_its_conditions(tmp_path: Path) -> None:
    """`variant_key=` and `rsid=` conditions holding an rsID; a gene or a tag names none."""
    assert meta_member_rsids(_spec(tmp_path / "spec")) == ["rs1800562", "rs2228145", "rs8192284"]


def test_a_module_with_no_meta_csv_names_none(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec")
    (spec / "meta.csv").unlink()
    assert meta_member_rsids(spec) == []


def test_the_currency_pass_asks_dbsnp_about_meta_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[list[str]] = []

    def oracle(rsids: list[str], **_kwargs: object) -> list[RsidStatus]:
        asked.append(list(rsids))
        return [
            RsidStatus(rsid, "merged", "rs2228145") if rsid == "rs8192284" else RsidStatus(rsid, "live")
            for rsid in rsids
        ]

    # The name `enrich()` looks up lives in the submodule that runs it (RM260).
    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.check_rsids", oracle)
    result = enrich(
        _spec(tmp_path / "spec"),
        ensembl_cache=tmp_path / "no-cache",
        clinvar_cache=tmp_path / "no-cv",
        verify_rsids=True,
        use_gnomad=False,
        download=False,
    )
    assert asked and "rs8192284" in asked[0]
    assert [(s.rsid, s.current) for s in result.stale_rsids] == [("rs8192284", "rs2228145")]
    # The member's id is asked, never written: resolution.csv carries the module's rows only.
    assert {row.rsid for row in result.rows} == {"rs2228145"}


def test_an_invalid_meta_csv_refuses_before_the_run_does_any_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read at the start of the run, never inside the late rsID pass (`@incidental-call-isolated`)."""
    spec = _spec(tmp_path / "spec")
    (spec / "meta.csv").write_text("members,tier\nvariants[colour=blue],A\n", encoding="utf-8")

    def never(*_args: object, **_kwargs: object) -> list:
        raise AssertionError("the rsID pass ran on a module whose meta.csv is invalid")

    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.check_rsids", never)
    with pytest.raises(EnrichmentError, match="meta.csv is invalid"):
        enrich(
            spec,
            ensembl_cache=tmp_path / "no-cache",
            clinvar_cache=tmp_path / "no-cv",
            verify_rsids=True,
            use_gnomad=False,
            download=False,
        )
    assert not (spec / "resolution.csv").exists()
