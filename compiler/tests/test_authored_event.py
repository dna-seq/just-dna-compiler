"""The compiler trusts a recorded `authored_event` and never judges two spellings itself (RM375).

An indel can be anchored anywhere inside its repeat, so an authored coordinate and the locus a link
resolved it to can be two spellings of one event: NUDT15's `rs761191455` was `13:48041104 G>GG` in the
old Ensembl snapshot (and in `reference_examples/cpic_gene_pairs/haplotypes.csv`), `13:48041103 T>TG` in
the new one. The compiler holds no reference (P2), so it cannot tell that from a real contradiction; the
enricher can, and records the verdict on the locus's row. What is pinned here, over every table the
two comparers read (`variants.csv` through `resolve_from_table._verify`, the positional kinds through
`resolve_positional_rows`) and over the four states of the cell:

* `same_event` is agreement: no contradiction, the authored coordinate kept, and the fill takes only
  the cells no spelling changes (`rsid`, `chrom`) — never a `ref`/`alts` worn at the author's anchor;
* `different_event` and an empty cell (never judged) keep today's accusation;
* `undecided` keeps the finding but withholds rather than accuses: no "contradicts", no "disagreement";
* the round trip carries the verdict, so lap two reads what lap one read.

Expected values come from the fixtures at runtime.
"""

import csv
import io
import re
from pathlib import Path
from typing import Any

import pytest
from just_dna_compiler.compiler import _POSITIONAL_TABLE_KINDS, compile_module, reverse_module
from just_dna_compiler.resolution import resolve_from_table, resolve_positional_rows
from just_dna_format.binning import HeteroplasmyRow
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import VALID_AUTHORED_EVENT_VERDICTS

RSID = "rs761191455"
#: The new snapshot's spelling (the locus) and the old one's anchor (the authored start).
LOCUS = ("13", 48041103, "T", "TG")
AUTHORED_START = 48041104

#: Every state the cell can hold: the three members and the empty cell (never judged).
STATES: list[str | None] = [*sorted(VALID_AUTHORED_EVENT_VERDICTS), None]

_ACCUSING = re.compile(r"\b(contradicts|disagreement|disagrees)\b")


def _locus(verdict: str | None, *, chrom: str = LOCUS[0], key: str = RSID) -> ResolutionRow:
    return ResolutionRow(
        variant_key=key,
        rsid=RSID,
        chrom=chrom,
        start=LOCUS[1],
        ref=LOCUS[2],
        alts=LOCUS[3],
        genome_build="GRCh38",
        locus_index=0,
        source="cache",
        authority="ensembl",
        status="resolved",
        authored_event=verdict,
    )


def _positional_row(csv_name: str, *, chrom: str | None) -> Any:
    """One row of each positional kind authoring the old anchor and no allele spelling."""
    if csv_name == "haplotypes.csv":
        return HaplotypeRow(haplotype_name="*1", rsid=RSID, chrom=chrom, start=AUTHORED_START, allele="G")
    if csv_name == "pharm_variants.csv":
        return PharmVariantRow(
            rsid=RSID,
            chrom=chrom,
            start=AUTHORED_START,
            gene="NUDT15",
            genotype="G/G",
            drug="d",
            conclusion="c",
        )
    return HeteroplasmyRow(
        gene="MT-ND5",
        rsid=RSID,
        chrom="MT",
        start=AUTHORED_START,
        reference_sequence="NC_012920.1",
        measure_min=0.0,
        measure_max=0.1,
        conclusion="x",
    )


def _positional_cases() -> list[tuple[str, str | None]]:
    """Each positional kind with a whole coordinate, and the two that may author a half one (CPIC)."""
    cases: list[tuple[str, str | None]] = []
    for csv_name, _model in _POSITIONAL_TABLE_KINDS:
        cases.append((csv_name, "MT" if csv_name == "heteroplasmy.csv" else LOCUS[0]))
        if csv_name != "heteroplasmy.csv":
            cases.append((csv_name, None))
    return cases


@pytest.mark.parametrize("verdict", STATES)
@pytest.mark.parametrize(("csv_name", "chrom"), _positional_cases())
def test_a_positional_row_reads_the_recorded_verdict(
    csv_name: str, chrom: str | None, verdict: str | None
) -> None:
    row = _positional_row(csv_name, chrom=chrom)
    table_chrom = "MT" if csv_name == "heteroplasmy.csv" else LOCUS[0]
    report = resolve_positional_rows(
        [row], {row.variant_key: [_locus(verdict, chrom=table_chrom, key=row.variant_key)]}
    )

    assert row.start == AUTHORED_START, "the authored coordinate is never rewritten"
    assert getattr(row, "ref", None) is None and getattr(row, "alts", None) is None, (
        "a ref/alts filled at the author's anchor would be a spelling no source stated"
    )
    if verdict == "same_event":
        assert (report.contradicted, report.undecided) == ([], [])
        assert row.chrom == table_chrom, "the cells no spelling changes are filled"
        assert report.filled == (1 if chrom is None else 0)
    elif verdict == "undecided":
        assert report.contradicted == []
        assert len(report.undecided) == 1
        assert not _ACCUSING.search(report.undecided[0]), report.undecided[0]
        assert row.chrom == chrom, "an undecided row is left as authored"
    else:
        assert report.undecided == []
        assert len(report.contradicted) == 1
        assert "contradicts" in report.contradicted[0]
        assert row.chrom == chrom


def _variant(start: int) -> VariantRow:
    return VariantRow(rsid=RSID, chrom=LOCUS[0], start=start, genotype="G/GG", state="risk", conclusion="c")


@pytest.mark.parametrize("verdict", STATES)
def test_the_snp_core_pair_reads_the_recorded_verdict(verdict: str | None) -> None:
    outcome = resolve_from_table([_variant(AUTHORED_START)], {RSID: [_locus(verdict)]})
    found = [
        ladder.warning
        for ladder in outcome.ladders
        if getattr(ladder.warning, "code", None) == "rsid_coordinate_disagrees"
    ]
    assert [v.start for v in outcome.variants] == [AUTHORED_START]
    if verdict == "same_event":
        assert found == []
        assert outcome.channels(strict=True)[1] == []
    elif verdict == "undecided":
        assert len(found) == 1
        assert not _ACCUSING.search(found[0]), found[0]
    else:
        assert len(found) == 1
        assert "(reference disagreement" in found[0]


_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _cells(row: ResolutionRow) -> str:
    return ",".join("" if v is None else str(v) for v in row.model_dump().values())


def _module(root: Path, verdict: str | None) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "haplotypes.csv").write_text(
        f"haplotype_name,rsid,chrom,start,allele,gene\n*1,{RSID},13,{AUTHORED_START},G,NUDT15\n",
        encoding="utf-8",
    )
    (spec / "resolution.csv").write_text(
        ",".join(ResolutionRow.model_fields) + "\n" + _cells(_locus(verdict)) + "\n", encoding="utf-8"
    )
    return spec


def _contradictions(warnings: list[str]) -> list[str]:
    """`positional_identity_contradicted` by its pinned phrase: a manifest's warnings are plain strings."""
    return [w for w in warnings if "are left exactly as authored" in w]


@pytest.mark.parametrize("verdict", ["same_event", "undecided"])
def test_the_verdict_survives_the_round_trip(tmp_path: Path, verdict: str) -> None:
    """Lap two compiles from what reverse wrote, so the verdict must ride the artifact back, or the
    finding a recorded `same_event` silenced returns on the second lap (`@lap-stable-means-a-property-of-the-module`)."""
    spec = _module(tmp_path, verdict)
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    rows = list(
        csv.DictReader(io.StringIO((tmp_path / "rev" / "resolution.csv").read_text(encoding="utf-8")))
    )
    assert [(r["start"], r["ref"], r["alts"], r["authored_event"]) for r in rows] == [
        (str(LOCUS[1]), LOCUS[2], LOCUS[3], verdict)
    ]
    second = compile_module(tmp_path / "rev", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    one, two = first.manifest.compilation, second.manifest.compilation
    assert one.resolution_signature == two.resolution_signature
    assert _contradictions(one.warnings) == _contradictions(two.warnings)
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    if verdict == "same_event":
        assert _contradictions(one.warnings) == []
