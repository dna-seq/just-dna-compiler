"""Coordinates that cannot exist in the build they are recorded under (RM48, offline half).

An author curating from older literature has hg19/GRCh37 coordinates and the module must be GRCh38.
Nothing in these packages converts, so the conversion happens off-tool and the result lands as an
ordinary authored coordinate carrying no provenance at all. Two shapes of that mistake are
**provably** wrong with no sequence, no network and no provisioned asset, which is what puts them in
the compiler rather than the enricher:

* a position past the end of its contig — GRCh38's chromosome 1 ends at 248,956,422 and GRCh37's runs
  294 kb further, so an un-lifted coordinate in that tail names a base that does not exist;
* a contig only one build has — the 25 primary contigs are spelled identically in both, so this is
  entirely about unplaced scaffolds.

Both are **errors in both modes**, the inconsistent-reference-allele class rather than a mode ladder:
`strict` means *reproducible artifact*, and these rows are not unreproducible, they are false. Nothing
downstream catches them either — a VRS id minted at an impossible position is a correct digest of the
wrong input, which is exactly how a 3,038-row off-by-one once passed every gate including `--strict`.

The tests that matter most here are the ones where nothing fires. A wrong-build diagnosis on a correct
row is worse than no diagnosis, because it is a false accusation about data the author got right.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.vrs import PRIMARY_CONTIG_LENGTHS

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: D\n  description: d\n  report_title: D\n"
    "genome_build: {build}\n"
)
_VAR_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
_RES_HEADER = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"

#: Computed, never typed: the first position of chromosome 1 that GRCh37 has and GRCh38 does not.
_GRCH37_TAIL = PRIMARY_CONTIG_LENGTHS["GRCh38"]["1"] + 1


def _spec(
    tmp_path: Path,
    *,
    build: str = "GRCh38",
    variants: str = "",
    studies: str = "rsid,chrom,start,ref,pmid\nrs1800562,,,,8696333\n",
    resolution: str = "",
) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML.format(build=build))
    if variants:
        (spec / "variants.csv").write_text(_VAR_HEADER + variants)
    (spec / "studies.csv").write_text(studies)
    if resolution:
        (spec / "resolution.csv").write_text(_RES_HEADER + resolution)
    return spec


def _errors(spec: Path, *, strict: bool = False) -> list[str]:
    return validate_spec(spec, strict=strict).errors


def _fires(errors: list[str], fragment: str) -> list[str]:
    return [e for e in errors if fragment in e]


class TestPositionPastTheEndOfItsContig:
    def test_an_unlifted_grch37_coordinate_is_refused_and_names_grch37(self, tmp_path) -> None:
        spec = _spec(
            tmp_path,
            variants=f",1,{_GRCH37_TAIL},G,A,A/A,risk,unlifted\n",
        )
        (found,) = _fires(_errors(spec), "past the end of 1 on GRCh38")
        assert "inside GRCh37's 1" in found
        assert f"{PRIMARY_CONTIG_LENGTHS['GRCh37']['1']:,}" in found
        assert "hint recover" in found, "the message must name the remedy, not only the defect"

    def test_a_position_no_build_has_says_so_instead(self, tmp_path) -> None:
        """MT is the same length in both builds, so GRCh37 explains nothing and must not be offered."""
        beyond_mt = PRIMARY_CONTIG_LENGTHS["GRCh38"]["MT"] + 1
        spec = _spec(tmp_path, variants=f",MT,{beyond_mt},G,A,A,risk,impossible\n")
        (found,) = _fires(_errors(spec), "past the end of MT")
        assert "no build this compiler knows" in found
        assert "GRCh37" not in found

    def test_the_same_mistake_in_the_other_direction_is_caught_too(self, tmp_path) -> None:
        """A GRCh38 coordinate is not automatically legal on GRCh37 — chromosome 17 shrank by 3 Mb."""
        tail = PRIMARY_CONTIG_LENGTHS["GRCh37"]["17"] + 1
        assert tail <= PRIMARY_CONTIG_LENGTHS["GRCh38"]["17"]
        spec = _spec(tmp_path, build="GRCh37", variants=f",17,{tail},G,A,A/A,risk,lifted too far\n")
        (found,) = _fires(_errors(spec), "past the end of 17 on GRCh37")
        assert "inside GRCh38's 17" in found

    def test_many_rows_of_one_cause_are_one_line(self, tmp_path) -> None:
        """Grouped by reason, not by row: a whole panel authored on hg19 is a one-line fix."""
        rows = "".join(
            f",1,{_GRCH37_TAIL + n},G,A,A/A,risk,row {n}\n" for n in range(0, 60, 2)
        )
        spec = _spec(tmp_path, variants=rows)
        found = _fires(_errors(spec), "past the end of 1 on GRCh38")
        assert len(found) == 1
        assert "30 row(s)" in found[0]
        assert "(+27 more)" in found[0], "it must say how many rows it did not name"

    def test_a_legal_coordinate_and_a_telomeric_zero_stay_silent(self, tmp_path) -> None:
        """POS 0 is VCF's telomere convention and is evidence of nothing; only the top is checked."""
        spec = _spec(
            tmp_path,
            variants=(
                ",6,26092913,A,G,G/G,risk,a real GRCh38 HFE locus\n"
                ",6,0,A,G,G/G,risk,a telomeric position\n"
            ),
        )
        assert _fires(_errors(spec), "past the end of") == []

    def test_a_rejected_row_never_reaches_an_artifact_in_either_mode(self, tmp_path) -> None:
        """It is not a mode ladder: `strict` adds nothing here because both modes already refuse."""
        spec = _spec(tmp_path, variants=f",1,{_GRCH37_TAIL},G,A,A/A,risk,unlifted\n")
        for strict in (False, True):
            out = tmp_path / f"out-{strict}"
            result = compile_module(spec, out, strict=strict)
            assert not result.success
            assert _fires(result.errors, "past the end of 1 on GRCh38")
            assert not out.exists(), "a refusal must leave nothing written"


class TestScaffoldOnlyOneBuildHas:
    """`variants.csv` refuses a scaffold name at the model, so this check reaches the other tables.

    `VariantRow.chrom` is a closed vocabulary (1-22, X, Y, MT) and always was; what RM48 added there
    is that the *rejection* names the build (see `schema/tests/test_contig_geometry.py`). Every other
    positional table — `studies.csv`, the PGx tables, `heteroplasmy.csv` — and the injected
    `resolution.csv` accept any contig string, which is where this check does its work.
    """

    def test_a_grch37_scaffold_in_a_grch38_module_is_refused(self, tmp_path) -> None:
        spec = _spec(
            tmp_path,
            variants=",6,26092913,A,G,G/G,risk,fine\n",
            studies="rsid,chrom,start,ref,pmid\n,GL000209.1,1000,G,8696333\n",
        )
        (found,) = _fires(_errors(spec), "GL000209.1")
        assert "top-level sequence of GRCh37" in found
        assert "genome_build: GRCh37" in found

    def test_a_grch38_scaffold_in_a_grch37_module_is_refused(self, tmp_path) -> None:
        spec = _spec(
            tmp_path,
            build="GRCh37",
            variants=",6,26093141,G,A,A/A,risk,fine\n",
            studies="rsid,chrom,start,ref,pmid\n,KI270728.1,1000,G,8696333\n",
        )
        (found,) = _fires(_errors(spec), "KI270728.1")
        assert "top-level sequence of GRCh38" in found

    @pytest.mark.parametrize("contig", ["GL000194.1", "GL000205", "HSCHR6_MHC_APD_CTG1"])
    def test_a_name_that_decides_nothing_claims_nothing(self, tmp_path, contig) -> None:
        """Shared scaffold, unversioned accession, alt locus — each is legal or simply unknown."""
        spec = _spec(
            tmp_path,
            variants=",6,26092913,A,G,G/G,risk,fine\n",
            studies=f"rsid,chrom,start,ref,pmid\n,{contig},1000,G,8696333\n",
        )
        assert _errors(spec) == []


class TestTheInjectedTableIsInScope:
    """The parity case: an rsid-only row has no coordinate until resolution supplies one.

    Leaving `resolution.csv` out of the pre-flight would recreate the defect this repo keeps fixing —
    `validate` green, `compile` refusing, and an author hunting a change they did not make. Each
    resolution row is judged against **its own** `genome_build` column, which is what that column is
    for: the module's yaml speaks for the authored rows, and a row that states its build states the
    frame its numbers are in.
    """

    def _spec_with_injected(self, tmp_path: Path, *, build: str, start: int) -> Path:
        return _spec(
            tmp_path,
            variants="rs1800562,,,,,A/A,risk,an rsid-only row\n",
            resolution=f"rs1800562,rs1800562,1,{start},C,T,{build},0,manual,resolved\n",
        )

    def test_validate_refuses_what_compile_would_refuse(self, tmp_path) -> None:
        spec = self._spec_with_injected(tmp_path, build="GRCh38", start=_GRCH37_TAIL)
        (found,) = _fires(_errors(spec), "resolution.csv")
        assert "past the end of 1 on GRCh38" in found
        assert "rs1800562" in found, "the rsid is what the author will search their CSV for"
        result = compile_module(spec, tmp_path / "out")
        assert not result.success
        assert _fires(result.errors, "resolution.csv")

    def test_a_row_declaring_its_own_build_is_judged_against_that_build(self, tmp_path) -> None:
        """The same numbers are legal under GRCh37 — so the column decides, not the module's yaml.

        The table would not join (`resolve_from_table` filters on the build), which is a separate
        finding; what this pins is that the coordinate check reads the row's own declaration rather
        than assuming the module's.
        """
        spec = self._spec_with_injected(tmp_path, build="GRCh37", start=_GRCH37_TAIL)
        assert _fires(_errors(spec), "past the end of") == []
