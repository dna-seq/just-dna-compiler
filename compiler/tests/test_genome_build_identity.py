"""`variant_key` must respect the module's declared build (0.5.1).

`derive_variant_key` takes a `build` and documents that any build without a refget table "falls
through to case 3 rather than minting an id that would claim the wrong sequence". `vrs.py` opens by
promising that "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids instead of silently
baking one build into the key".

Neither happened, because `VariantRow._freeze_identity` runs at row construction — where there is no
module and therefore no declared build — and always used the GRCh38 default. Found by compiling a
GRCh37 module, which succeeded in complete silence.

Ground truth: HFE C282Y is 6:26092913 on GRCh38 and 6:26093141 on GRCh37 (Ensembl, 2026-08-03) — the
same variant, 228 bp apart, which is what makes the collision concrete rather than theoretical.
"""

from pathlib import Path

import polars as pl
import pytest

from just_dna_compiler.compiler import _restamp_for_build, compile_module, validate_spec
from just_dna_format.base import derive_variant_key
from just_dna_format.spec import VariantRow

_C282Y_GRCH38 = 26092913
_C282Y_GRCH37 = 26093141


def _yaml(build: str) -> str:
    return (
        "schema_version: '1.0'\n"
        "module:\n  name: build_probe\n  title: B\n  description: d\n  report_title: B\n"
        f"genome_build: {build}\n"
    )


def _spec(tmp_path: Path, build: str, start: int) -> Path:
    spec = tmp_path / build
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_yaml(build), encoding="utf-8")
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
        f"6,{start},G,A,A/A,risk,HFE C282Y homozygote,HFE\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        f"chrom,start,ref,pmid\n6,{start},G,10453733\n", encoding="utf-8"
    )
    return spec


def _key(out: Path) -> str:
    return pl.read_parquet(out / "weights.parquet")["variant_key"].to_list()[0]


def test_two_builds_at_their_own_coordinates_do_not_collide(tmp_path: Path) -> None:
    """The bug, at its sharpest: the *same variant* on two builds must not share one identity, and
    the *same coordinate* on two builds must not either — they are different places."""
    g38 = compile_module(_spec(tmp_path, "GRCh38", _C282Y_GRCH38), tmp_path / "o38")
    g37 = compile_module(_spec(tmp_path, "GRCh37", _C282Y_GRCH37), tmp_path / "o37")
    assert g38.success and g37.success
    assert _key(tmp_path / "o38") != _key(tmp_path / "o37")


def test_the_same_coordinate_on_two_builds_is_two_identities(tmp_path: Path) -> None:
    """Before the fix these were byte-identical `ga4gh:VA.…` ids for loci 228 bp apart."""
    same = _C282Y_GRCH37
    assert compile_module(_spec(tmp_path, "GRCh38", same), tmp_path / "a").success
    assert compile_module(_spec(tmp_path, "GRCh37", same), tmp_path / "b").success
    assert _key(tmp_path / "a") != _key(tmp_path / "b")


def test_a_grch38_module_still_mints_a_vrs_id(tmp_path: Path) -> None:
    """Without this the fix would be indistinguishable from disabling VRS."""
    assert compile_module(_spec(tmp_path, "GRCh38", _C282Y_GRCH38), tmp_path / "o").success
    assert _key(tmp_path / "o").startswith("ga4gh:VA.")


def test_a_non_grch38_module_falls_back_to_the_coordinate_key(tmp_path: Path) -> None:
    assert compile_module(_spec(tmp_path, "GRCh37", _C282Y_GRCH37), tmp_path / "o").success
    assert _key(tmp_path / "o") == f"6:{_C282Y_GRCH37}:G:A"


def test_the_fallback_is_stated_rather_than_silent(tmp_path: Path) -> None:
    """It compiled with no warning at all, which is what let it go unnoticed. The message has to say
    the consequence — a coordinate key does not join against GRCh38-keyed data — not just the fact."""
    spec = _spec(tmp_path, "GRCh37", _C282Y_GRCH37)
    warnings = [w for w in validate_spec(spec).warnings if "GRCh37" in w]
    assert len(warnings) == 1
    assert "build-relative" in warnings[0] and "GRCh38-only" in warnings[0]


def test_grch38_is_untouched_and_emits_nothing(tmp_path: Path) -> None:
    """A no-op on every module that exists today (P3): same keys, no new warning."""
    row = VariantRow(chrom="6", start=_C282Y_GRCH38, ref="G", alts="A",
                     genotype="A/A", state="risk", conclusion="c")
    before = row.variant_key
    assert _restamp_for_build([row], "GRCh38") == []
    assert row.variant_key == before

    spec = _spec(tmp_path, "GRCh38", _C282Y_GRCH38)
    assert not [w for w in validate_spec(spec).warnings if "build-relative" in w]


def test_an_rsid_row_keeps_its_rsid_on_any_build() -> None:
    """Case 1 precedes the build question entirely — an rsID is not build-relative."""
    row = VariantRow(rsid="rs1800562", genotype="A/A", state="risk", conclusion="c")
    assert _restamp_for_build([row], "GRCh37") == []
    assert row.variant_key == "rs1800562"


@pytest.mark.parametrize("build", ["GRCh37", "T2T-CHM13v2.0", "NCBI36"])
def test_every_build_without_a_refget_table_behaves_the_same(build: str) -> None:
    """The guard is about *having a table*, not about GRCh37 specifically."""
    key = derive_variant_key(None, "6", _C282Y_GRCH37, "G", "A", build=build)
    assert key == f"6:{_C282Y_GRCH37}:G:A"
