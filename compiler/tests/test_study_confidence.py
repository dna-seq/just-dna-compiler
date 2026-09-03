"""`StudyRow.confidence` / `confidence_unit` — a citing source's own review state (0.7, RM160).

A citation recovered from a curated source arrives with that source's curation state beside it. CIViC
serves `ACCEPTED`, `SUBMITTED` and `REJECTED` evidence items on one variant, and the difference is
what RM160's currency check acts on — so it has to be a *field* compared for equality, never a phrase
in `conclusion` prose that a check would have to re-parse.

Three halves are pinned here. The pair survives the round trip, which is the `@three-touch-points`
touch point that gets missed (the reverse writer's hand-kept `fieldnames` list, and the row dict under
it that `DictWriter` would fill silently). An unset pair leaves `content_signature` where it was, which
is the P3/P8 property that makes the column minor-legal. And a magnitude with no instrument beside it
is refused at the model, which is `@weight-has-no-unit` restated: `submitted` is unreadable without
being told which ladder it sits on.

Coordinates are the real GRCh38 HFE locus already in `reference_examples/hfe_hemochromatosis/`:
`rs1800562` at 6:26092913, `G>A`.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.spec import StudyRow

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm160\n"
    "  title: RM160\n"
    "  description: how far a citing source stands behind an evidence link\n"
    "  report_title: RM160\n"
    "genome_build: GRCh38\n"
)

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs1800562,6,26092913,G,A,A/A,risk,C282Y homozygote,HFE\n"
)

_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs1800562,rs1800562,6,26092913,G,A,GRCh38,0,authored,resolved\n"
)

#: A real PMID, so the mandatory-grounding rule is met by evidence rather than by a stub.
_PMID = "16199547"

#: CIViC's own word for the instrument, which is the one this column exists to carry unconverted.
_UNIT = "civic_evidence_status"

_HEADER = "rsid,pmid,confidence,confidence_unit\n"


def _spec(directory: Path, *, study_rows: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(_VARIANTS)
    (directory / "studies.csv").write_text(_HEADER + study_rows)
    (directory / "resolution.csv").write_text(_RESOLUTION)
    return directory


def test_the_pair_reaches_the_parquet_and_survives_the_round_trip(tmp_path: Path) -> None:
    """compile → reverse → compile, byte-identical, with both cells still readable.

    Asserting the recompile succeeds is not enough: a column missing from the reverse writer's
    `fieldnames` reaches the parquet and vanishes on the way back, and the spec still validates. The
    digest fixed point plus the value itself is what catches that.
    """
    spec = _spec(tmp_path / "spec", study_rows=f"rs1800562,{_PMID},submitted,{_UNIT}\n")
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors

    studies = pl.read_parquet(tmp_path / "a1" / "studies.parquet")
    assert {"confidence", "confidence_unit"} <= set(studies.columns)
    assert studies["confidence"].to_list() == ["submitted"]
    assert studies["confidence_unit"].to_list() == [_UNIT]

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    header = (tmp_path / "rev" / "studies.csv").read_text().splitlines()[0]
    assert {"confidence", "confidence_unit"} <= set(header.split(","))

    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    again = pl.read_parquet(tmp_path / "a2" / "studies.parquet")
    assert again["confidence"].to_list() == studies["confidence"].to_list()
    assert again["confidence_unit"].to_list() == studies["confidence_unit"].to_list()


def test_an_accepted_row_and_a_submitted_row_are_not_the_same_row(tmp_path: Path) -> None:
    """The whole point of the column: two review states must be distinguishable in one file.

    Both rows cite one paper about one variant, differing only in the source's review state. Without
    the pair they are byte-identical, so the assertion is over what reaches the parquet — and over the
    `content_signature`, which must separate the two modules for the same reason.
    """
    both = _spec(
        tmp_path / "both",
        study_rows=(
            f"rs1800562,{_PMID},accepted,{_UNIT}\n"
            f"rs1800562,{_PMID},submitted,{_UNIT}\n"
        ),
    )
    compiled = compile_module(both, tmp_path / "out")
    assert compiled.success, compiled.errors
    studies = pl.read_parquet(tmp_path / "out" / "studies.parquet")
    assert sorted(studies["confidence"].to_list()) == ["accepted", "submitted"]

    only_submitted = _spec(
        tmp_path / "one", study_rows=f"rs1800562,{_PMID},submitted,{_UNIT}\n"
    )
    other = compile_module(only_submitted, tmp_path / "one_out")
    assert other.success, other.errors
    assert other.manifest.content_signature != compiled.manifest.content_signature


def test_an_unset_pair_leaves_the_authored_identity_alone(tmp_path: Path) -> None:
    """P3/P8: an optional column nobody fills is omitted from `content_signature`.

    The module written without the columns at all and the one that declares them empty must hash
    identically — that is what makes a new optional column minor-legal rather than a change every
    published module has to answer for.
    """
    without = tmp_path / "without"
    without.mkdir()
    (without / "module_spec.yaml").write_text(_SPEC_YAML)
    (without / "variants.csv").write_text(_VARIANTS)
    (without / "studies.csv").write_text(f"rsid,pmid\nrs1800562,{_PMID}\n")
    (without / "resolution.csv").write_text(_RESOLUTION)
    bare = compile_module(without, tmp_path / "bare")
    assert bare.success, bare.errors

    declared = _spec(tmp_path / "declared", study_rows=f"rs1800562,{_PMID},,\n")
    empty = compile_module(declared, tmp_path / "empty")
    assert empty.success, empty.errors
    assert empty.manifest.content_signature == bare.manifest.content_signature


def test_a_magnitude_with_no_instrument_is_refused() -> None:
    """`@weight-has-no-unit`, on the pair this model now carries.

    Refused at the model rather than warned about at compile, because a `confidence` of `3` with no
    unit beside it is not a row anything downstream can read — the failure is in the cell, not in the
    module. The reverse asymmetry is deliberate: a unit with no magnitude names an instrument nothing
    was measured on, which is harmless.
    """
    with pytest.raises(ValueError, match="confidence_unit"):
        StudyRow(pmid=_PMID, confidence="submitted")
    assert StudyRow(pmid=_PMID, confidence_unit=_UNIT).confidence is None


def test_a_blank_cell_reloads_as_absent_not_as_an_empty_magnitude() -> None:
    """A round-tripped empty column must not come back as a `""` the coherence rule has to judge."""
    row = StudyRow(pmid=_PMID, confidence="   ", confidence_unit="")
    assert row.confidence is None and row.confidence_unit is None
