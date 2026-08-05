"""The enricher must resolve against the build the module *declares*, and record nothing else.

`enrich()` took `genome_build: str = "GRCh38"` and **nothing ever passed it** — not the CLI, not
`enrich_and_compile`, not a single caller. Every resolver link inside is gated on
`genome_build == "GRCh38"`, and so is the warning that says a non-GRCh38 module resolves nothing, so
all of that machinery was unreachable: a `genome_build: GRCh37` module was resolved against GRCh38
Ensembl, and the GRCh38 coordinate was written into its `resolution.csv` labelled `GRCh38`, with a
GRCh38 VRS allele id minted for it. The compiler then refused to use any of it
("compiler is GRCh38-bound, module genome_build is 'GRCh37'"), so the visible symptom was an
unresolved module — while the file on disk claimed a coordinate on an assembly the module never named.

Same shape as the `VariantRow` re-stamp bug: the guard and its fall-through both existed, and the value
never arrived.

Network-free — every assertion here is about what does *not* happen.
"""

from pathlib import Path

import pytest
from just_dna_enricher.enrich import EnrichmentError, enrich, spec_genome_build
from just_dna_enricher.frequencies import _alleles_from_resolution
from just_dna_enricher.vrs import VrsMinter, mint_resolution_rows
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import derive_vrs_allele_id

# HFE C282Y: chr6:26,093,141 on GRCh37, chr6:26,092,913 on GRCh38.
_GRCH37_POS = 26_093_141


def _spec(d: Path, build: str | None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    yaml = (
        "schema_version: '1.0'\n"
        "module:\n  name: hfe\n  title: HFE\n  description: d\n  report_title: HFE\n"
    )
    if build is not None:
        yaml += f"genome_build: {build}\n"
    (d / "module_spec.yaml").write_text(yaml, encoding="utf-8")
    (d / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\n"
        "rs1800562,A/A,risk,C282Y homozygote,HFE\n",
        encoding="utf-8",
    )
    (d / "studies.csv").write_text("rsid,pmid\nrs1800562,8696333\n", encoding="utf-8")
    return d


def test_spec_genome_build_reads_the_declaration(tmp_path: Path) -> None:
    assert spec_genome_build(_spec(tmp_path / "a", "GRCh37")) == "GRCh37"
    assert spec_genome_build(_spec(tmp_path / "b", "GRCh38")) == "GRCh38"


def test_an_undeclared_build_is_the_formats_own_default(tmp_path: Path) -> None:
    """A spec that omits `genome_build`, and a bare table directory with no spec at all, both get what
    compiling them would assume — `ModuleSpecConfig.genome_build`'s default. That is a derivation, not
    a guess."""
    assert spec_genome_build(_spec(tmp_path / "a", None)) == "GRCh38"
    bare = tmp_path / "bare"
    bare.mkdir()
    assert spec_genome_build(bare) == "GRCh38"


def test_an_unreadable_spec_refuses_rather_than_picking_a_build(tmp_path: Path) -> None:
    """Enrichment writes facts into the spec directory. For a module whose declaration cannot be read,
    choosing an assembly is the invention this whole fix removes — so it raises instead."""
    spec = _spec(tmp_path / "spec", "GRCh38")
    (spec / "module_spec.yaml").write_text("module: {}\nnonsense: [\n", encoding="utf-8")
    with pytest.raises(EnrichmentError, match="genome_build"):
        spec_genome_build(spec)


def test_a_grch37_module_records_no_lookup_result(tmp_path: Path, caplog) -> None:
    """No link runs, so no row may claim one — and the row that *was* written claimed the worst thing.

    Before the fix this wrote `chrom=6, start=26092913, genome_build=GRCh38` (the **GRCh38** position)
    for a module declaring GRCh37. Now nothing is resolved; the rsID is reported unresolved, and no
    `not_found` row is fabricated either — `not_found` means "the source was asked and does not have
    it", which is a negative about a question never put (`VALID_RESOLUTION_STATUS` has no `unchecked`
    member to write instead).
    """
    spec = _spec(tmp_path / "spec", "GRCh37")
    result = enrich(spec, offline=True)

    assert result.unresolved == ["rs1800562"]
    assert result.rows == []
    assert "GRCh38-bound" in caplog.text
    written = (spec / "resolution.csv").read_text().strip().splitlines()
    assert len(written) == 1, f"header only, no fabricated rows: {written}"


def test_an_authored_coordinate_is_still_transcribed_on_another_build(tmp_path: Path) -> None:
    """What the author wrote is not a lookup result, so it survives — under the module's own build.

    The distinction matters: refusing to record an authored GRCh37 coordinate would lose data, while
    recording a *fetched* GRCh38 one under a GRCh37 label invents it.
    """
    spec = _spec(tmp_path / "spec", "GRCh37")
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
        f"6,{_GRCH37_POS},G,A,A/A,risk,C282Y homozygote,HFE\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        f"chrom,start,ref,pmid\n6,{_GRCH37_POS},G,8696333\n", encoding="utf-8"
    )
    result = enrich(spec, offline=True)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert (row.chrom, row.start, row.genome_build) == ("6", _GRCH37_POS, "GRCh37")
    assert row.source == "authored"
    assert row.vrs_id is None, "GRCh37 has no refget table, so there is no id to mint (RM15)"


def test_minting_skips_an_unsupported_build_instead_of_aborting_the_run() -> None:
    """`refget_accession` raises for a build with no table — deliberately — so every call site must
    catch it. `VrsMinter.mint`'s substitution branch did not, so one `genome_build: GRCh37` row in an
    otherwise fine `resolution.csv` killed the whole enrich run with an unhandled
    `UnsupportedBuildError`. The indel branch beside it had always caught it.
    """
    rows = [
        ResolutionRow(
            variant_key=f"6:{_GRCH37_POS}:G:A", rsid="rs1800562", chrom="6", start=_GRCH37_POS,
            ref="G", alts="A", genome_build="GRCh37", source="authored", status="resolved",
        ),
        ResolutionRow(
            variant_key="6:26092913:G:A", rsid="rs1800562", chrom="6", start=26_092_913,
            ref="G", alts="A", genome_build="GRCh38", source="authored", status="resolved",
        ),
    ]
    result = mint_resolution_rows(rows, minter=VrsMinter(offline=True))

    assert result.skipped_unmintable == 1 and result.minted_stdlib == 1
    assert rows[0].vrs_id is None
    assert rows[1].vrs_id is not None and rows[1].vrs_id.startswith("ga4gh:VA.")


def test_the_frequency_pass_declines_a_row_from_another_build(caplog) -> None:
    """gnomAD v4 is GRCh38-only and its variant id carries no assembly, so an off-build coordinate is a
    *well-formed request for a different variant* — the worst shape a fetch can have.

    The pass took every resolved row regardless of `genome_build` and re-keyed it with
    `derive_variant_key` **without** passing the build, so a GRCh37 row (a) would have had another
    variant's counts written under this module's key and (b) was minted a GRCh38 `ga4gh:VA.…` on the
    way — the same false content-addressed identity as the reverse and enrich bugs, from a third place.
    Third instance of one mistake is what makes it worth a named constant (`FREQUENCY_GENOME_BUILD`).
    """
    rows = [
        ResolutionRow(
            variant_key=f"6:{_GRCH37_POS}:G:A", rsid="rs1800562", chrom="6", start=_GRCH37_POS,
            ref="G", alts="A", genome_build="GRCh37", source="authored", status="resolved",
        ),
        ResolutionRow(
            variant_key="6:26092913:G:A", rsid="rs1800562", chrom="6", start=26_092_913,
            ref="G", alts="A", genome_build="GRCh38", source="authored", status="resolved",
        ),
    ]
    alleles, off_build = _alleles_from_resolution(rows)

    assert [a[2] for a in alleles] == [26_092_913], "only the GRCh38 coordinate may be queried"
    assert off_build == [f"6:{_GRCH37_POS}:G:A"]
    # The GRCh38 row keeps its VA identity; the GRCh37 one never gets one minted for it.
    assert alleles[0][0].startswith("ga4gh:VA.")
    assert derive_vrs_allele_id("6", _GRCH37_POS, "G", "A") not in {a[0] for a in alleles}


def test_an_explicit_build_still_overrides_the_declaration(tmp_path: Path, caplog) -> None:
    """The parameter stays an inject-only escape hatch: a caller that knows better is not second-guessed.
    It just is no longer the *only* way the value could ever be non-default."""
    spec = _spec(tmp_path / "spec", "GRCh38")
    enrich(spec, offline=True, genome_build="T2T-CHM13")
    assert "T2T-CHM13" in caplog.text
