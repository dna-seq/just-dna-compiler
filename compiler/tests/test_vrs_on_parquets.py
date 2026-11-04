"""RM270: the `vrs_id` the enricher mints reaches every variant parquet, and `reverse` writes it back.

An indel's `variant_key` is its source's spelling, so a consumer whose caller spelled the same event
another legal way misses the row on an exact join. The VRS allele id is over the fully justified allele,
so it does not depend on the spelling: both spellings of `rs72613567` mint one id, and S117's two
placements of `rs8176719` mint two. It lived in `resolution.csv`, which has no parquet by design, so it
never reached the artifact (`@dont-discard-computed`), and a round trip dropped it (RM241's residual).

The ids below are domain constants: the two RM270's probe and ClinVar-GKM recorded, and `rs8176719`'s
pair minted by `ga4gh.vrs` over real GRCh38 bases (the enricher's `test_placement_witness.py` mints all
six through the run's own proxy). The substitution ids are minted here at runtime by the format tier's
stdlib, which the compiler's verify pass recomputes.

**The carry is from the row's own `resolution.csv` row, by allele, never by position in a cell.** A row's
id list follows that row's own `alts`; an allele its row records no id for is a hole, even when another
subject's row records one for the same spelling, and two rows of one key naming one allele with two ids
withhold it rather than pick one.
"""

import csv
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.vrs import derive_vrs_allele_id

#: Domain constants — see the module docstring.
HSD17B13_ID = "ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7"
RS8176719_ENSEMBL_ID = "ga4gh:VA.Jwesa81jBuk4LSchvngeXwdYHS-lOoDV"
RS8176719_CLINVAR_ID = "ga4gh:VA.gMmj5gwZ40fKx1YdsSFoD7jz790cMQXN"

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_RESOLUTION_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,source,status\n"
)


def _spec(root: Path) -> Path:
    """Both spellings of `rs72613567`, both placements of `rs8176719`, a multi-allelic substitution
    whose second allele carries no id, a pharm row filled from the table, and a study's LD proxy."""
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        "rs72613567,,,,,T/TA,risk,ClinVar's spelling filled from the table\n"
        ",4,87310241,A,AA,A/AA,risk,Ensembl's spelling authored\n"
        ",9,133257520,G,GC,G/GC,risk,the snapshot's placement\n"
        ",9,133257521,T,TC,T/TC,risk,ClinVar's placement\n"
        "rs1801133,,,,,A/G,risk,a multi-allelic substitution\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        "rsid,pmid,proxy_rsid\nrs72613567,9545397,rs1801133\n", encoding="utf-8"
    )
    (spec / "pharm_variants.csv").write_text(
        "rsid,gene,genotype,drug,conclusion\nrs4149056,SLCO1B1,C/T,simvastatin,c\n", encoding="utf-8"
    )
    mthfr_a = derive_vrs_allele_id("1", 11796321, "G", "A")
    slco = derive_vrs_allele_id("12", 21178615, "T", "C")
    (spec / "resolution.csv").write_text(
        _RESOLUTION_HEADER
        + f"rs72613567,rs72613567,4,87310240,T,TA,GRCh38,0,{HSD17B13_ID},2.0,cache,resolved\n"
        + f"4:87310241:A:AA,,4,87310241,A,AA,GRCh38,0,{HSD17B13_ID},2.0,authored,resolved\n"
        + f"9:133257520:G:GC,,9,133257520,G,GC,GRCh38,0,{RS8176719_ENSEMBL_ID},2.0,authored,resolved\n"
        + f"9:133257521:T:TC,,9,133257521,T,TC,GRCh38,0,{RS8176719_CLINVAR_ID},2.0,authored,resolved\n"
        + f'rs1801133,rs1801133,1,11796321,G,"A,T",GRCh38,0,"{mthfr_a},",2.0,cache,resolved\n'
        + f"rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,{slco},2.0,cache,resolved\n",
        encoding="utf-8",
    )
    return spec


def _weights(out: Path) -> dict[tuple, tuple[list | None, str | None]]:
    df = pl.read_parquet(out / "weights.parquet")
    return {
        (r["chrom"], r["start"], r["ref"], tuple(r["alts"] or ())): (r["vrs_id"], r["vrs_spec"])
        for r in df.iter_rows(named=True)
    }


def test_both_spellings_of_one_event_carry_one_id_and_two_events_carry_two(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    weights = _weights(tmp_path / "out")
    # rs72613567: ClinVar's spelling (filled) and Ensembl's (authored) — one event, one id.
    assert weights[("4", 87310240, "T", ("TA",))] == ([HSD17B13_ID], "2.0")
    assert weights[("4", 87310241, "A", ("AA",))] == ([HSD17B13_ID], "2.0")
    # rs8176719: two placements are two events, and the two ids keep them apart.
    assert weights[("9", 133257520, "G", ("GC",))] == ([RS8176719_ENSEMBL_ID], "2.0")
    assert weights[("9", 133257521, "T", ("TC",))] == ([RS8176719_CLINVAR_ID], "2.0")
    assert RS8176719_ENSEMBL_ID != RS8176719_CLINVAR_ID
    # One id per ALT, parallel to `alts`, the hole kept (`@vrsid-per-alt`).
    assert weights[("1", 11796321, "G", ("A", "T"))] == (
        [derive_vrs_allele_id("1", 11796321, "G", "A"), None],
        "2.0",
    )


def test_the_positional_parquet_and_the_proxy_carry_the_id_in_their_own_shape(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    assert compile_module(spec, tmp_path / "out").success
    pharm = pl.read_parquet(tmp_path / "out" / "pharm_variants.parquet").row(0, named=True)
    assert (pharm["alts"], pharm["vrs_id"], pharm["vrs_spec"]) == (
        "C",
        derive_vrs_allele_id("12", 21178615, "T", "C"),
        "2.0",
    )
    (proxy,) = pl.read_parquet(tmp_path / "out" / "studies.parquet")["proxy_loci"][0]
    assert (proxy["alts"], proxy["vrs_id"], proxy["vrs_spec"]) == (
        "A,T",
        f"{derive_vrs_allele_id('1', 11796321, 'G', 'A')},",
        "2.0",
    )


def test_a_row_carries_only_the_ids_its_own_resolution_row_recorded(tmp_path: Path) -> None:
    """Another subject's id for the same spelling is true of the allele, but `reverse` would write it
    under this row's key and the round trip would gain an id the table never held. So a row whose own
    `resolution.csv` row records no id has none on the parquet, and the round trip counts the same."""
    spec = _spec(tmp_path)
    variants = spec / "variants.csv"
    variants.write_text(
        variants.read_text(encoding="utf-8") + ",4,87310240,T,TA,T/TA,risk,the filled spelling authored\n",
        encoding="utf-8",
    )
    resolution = spec / "resolution.csv"
    resolution.write_text(
        resolution.read_text(encoding="utf-8")
        + "4:87310240:T:TA,,4,87310240,T,TA,GRCh38,0,,,authored,resolved\n",
        encoding="utf-8",
    )
    first = compile_module(spec, tmp_path / "out")
    assert first.success, first.errors
    by_key = {
        r["variant_key"]: r["vrs_id"]
        for r in pl.read_parquet(tmp_path / "out" / "weights.parquet").iter_rows(named=True)
    }
    assert by_key["rs72613567"] == [HSD17B13_ID]
    assert by_key["4:87310240:T:TA"] is None
    reverse_module(tmp_path / "out", tmp_path / "reversed")
    second = compile_module(tmp_path / "reversed", tmp_path / "out2")
    assert second.success
    assert (
        second.manifest.compilation.vrs_alleles_identified
        == first.manifest.compilation.vrs_alleles_identified
    )


def test_one_key_recording_one_allele_with_two_ids_is_withheld(tmp_path: Path) -> None:
    """The id is content-addressed, so two ids for one allele under one key means one of them is wrong;
    the parquet carries neither rather than the first one read."""
    spec = _spec(tmp_path)
    resolution = spec / "resolution.csv"
    resolution.write_text(
        resolution.read_text(encoding="utf-8")
        + f"4:87310241:A:AA,,4,87310241,A,AA,GRCh38,1,{RS8176719_CLINVAR_ID},2.0,authored,resolved\n",
        encoding="utf-8",
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert _weights(tmp_path / "out")[("4", 87310241, "A", ("AA",))] == (None, None)


def test_a_round_trip_keeps_every_vrs_id(tmp_path: Path) -> None:
    """RM241's residual: `reverse` writes the parquet's ids back, and the recompile is a fixed point."""
    spec = _spec(tmp_path)
    first = compile_module(spec, tmp_path / "out")
    assert first.success
    reverse_module(tmp_path / "out", tmp_path / "reversed")
    with (tmp_path / "reversed" / "resolution.csv").open(newline="", encoding="utf-8") as handle:
        reversed_ids = {
            (r["chrom"], r["start"], r["ref"], r["alts"]): (r["vrs_id"], r["vrs_spec"])
            for r in csv.DictReader(handle)
        }
    with (spec / "resolution.csv").open(newline="", encoding="utf-8") as handle:
        original = {
            (r["chrom"], r["start"], r["ref"], r["alts"]): (r["vrs_id"], r["vrs_spec"])
            for r in csv.DictReader(handle)
        }
    assert reversed_ids == original
    second = compile_module(tmp_path / "reversed", tmp_path / "out2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert (
        second.manifest.compilation.vrs_alleles_identified
        == first.manifest.compilation.vrs_alleles_identified
    )
    assert _weights(tmp_path / "out2") == _weights(tmp_path / "out")
