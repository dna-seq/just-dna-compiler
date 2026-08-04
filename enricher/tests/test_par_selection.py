"""Pseudoautosomal locus selection: one place on two contigs, recorded as the X spelling (RM32).

A PAR variant maps to both X and Y, so the one-to-many expansion used to emit two rows for one
finding. Probed 2026-08-04, every annotation source places PAR annotation on **X** and only the
coordinate resolver disagrees — ClinVar has zero records in either PAR on Y, gnomAD v4 excludes the
Y PAR from its callset (X PAR1 640000-641500 serves 880 variants, the same interval on Y serves none),
and the ClinGen Allele Registry mints a Y allele id whose record is a bare dbSNP cross-reference.

Every coordinate below is real and live-verified against Ensembl on 2026-08-04:

* `rs137852556` → X:640851 **and** Y:640851 — SHOX, PAR1, where the two contigs share coordinates.
* `rs184115031` → X:155773979 **and** Y:56960499 — SPRY3, PAR2, where they do **not**. This is the
  case a "same base on X and Y" shortcut gets wrong, and the reason the mapping is an offset rather
  than an equality.
* `rs779201129` → X:155773926 and Y:56960446 — a second PAR2 point on the same offset.
* `rs376745839` → X:2782081, **X only** — XG, 602 bp past the end of PAR1. XG straddles the boundary,
  which is why the verdict has to be per locus and can never be per gene or per module.
"""

import logging
from pathlib import Path

import polars as pl
import pytest

from just_dna_enricher.enrich import enrich, select_par_representative

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: par\n  title: PAR\n  description: d\n  report_title: PAR\n"
)


def _locus(chrom: str, start: int, ref: str, alts: str) -> dict:
    return {"chrom": chrom, "start": start, "ref": ref, "alts": alts}


# ── the predicate ───────────────────────────────────────────────────────────────────────────────


def test_a_par1_pair_keeps_the_x_spelling() -> None:
    x, y = _locus("X", 640851, "C", "T"), _locus("Y", 640851, "C", "T")
    kept, twins = select_par_representative([x, y])
    assert kept == [x]
    assert twins == [y]


def test_a_par2_pair_pairs_on_the_offset_not_on_equality() -> None:
    """The coordinates differ by 98,813,480 here. Nothing about "the same base" would find this."""
    x, y = _locus("X", 155773979, "A", "G"), _locus("Y", 56960499, "A", "G")
    kept, twins = select_par_representative([x, y])
    assert kept == [x] and twins == [y]


def test_the_input_order_does_not_decide_the_survivor() -> None:
    """Y first must still keep X — otherwise the emitted row (and so `artifact.digest`) would depend
    on whichever order the resolver happened to return its mappings in."""
    x, y = _locus("X", 155773979, "A", "G"), _locus("Y", 56960499, "A", "G")
    kept, twins = select_par_representative([y, x])
    assert kept == [x] and twins == [y]


def test_a_non_par_locus_is_untouched() -> None:
    """rs376745839, in XG but past the PAR1 boundary. The gene straddles it; the locus does not."""
    only = _locus("X", 2782081, "C", "T")
    assert select_par_representative([only]) == ([only], [])


def test_a_paralog_pair_is_not_a_par_pair() -> None:
    """The expansion exists for genuine paralogs and must keep serving them. Two autosomal loci have
    no partner relationship, so both survive."""
    loci = [_locus("5", 500, "A", "T"), _locus("6", 600, "A", "T")]
    assert select_par_representative(loci) == (loci, [])


def test_a_y_par_locus_whose_x_partner_is_absent_survives() -> None:
    """This selects between two spellings of one place; it does not delete a place. With no X row to
    prefer there is nothing to choose, so the Y row is the module's only record of the locus."""
    only = _locus("Y", 640851, "C", "T")
    assert select_par_representative([only]) == ([only], [])


def test_partner_coordinates_alone_do_not_fuse_two_variants() -> None:
    """A negative control on the fusion predicate, not an observed variant.

    Partner coordinates say "same place"; they do not say "same variant". If the geometry alone were
    enough, a different allele at the partner position would be silently discarded as a duplicate —
    losing a real finding. So allele agreement is required, and a same-place different-allele pair is
    kept whole.
    """
    x, y = _locus("X", 640851, "C", "T"), _locus("Y", 640851, "C", "G")
    kept, twins = select_par_representative([x, y])
    assert kept == [x, y] and twins == []


def test_a_differing_ref_is_also_not_a_fusion() -> None:
    x, y = _locus("X", 640851, "C", "T"), _locus("Y", 640851, "CA", "T")
    assert select_par_representative([x, y]) == ([x, y], [])


def test_alts_compare_as_a_set_not_as_a_string() -> None:
    """The snapshot link sorts and re-joins `alts` while the REST link preserves the source order, so a
    string compare would fail to pair a multi-allelic PAR site depending on which link answered."""
    x, y = _locus("X", 640851, "C", "T,A"), _locus("Y", 640851, "C", "A,T")
    kept, twins = select_par_representative([x, y])
    assert kept == [x] and twins == [y]


def test_another_build_keeps_both_rather_than_guessing() -> None:
    """PAR intervals are per-assembly (RM15). With no table for the build the partner is unknown, and
    an unknown must not be spent dropping a row."""
    x, y = _locus("X", 640851, "C", "T"), _locus("Y", 640851, "C", "T")
    assert select_par_representative([x, y], build="GRCh37") == ([x, y], [])


# ── through enrich() ────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def par_cache(tmp_path: Path) -> Path:
    """A snapshot carrying the two contigs of two real PAR2 loci, plus a real non-PAR XG locus."""
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": [
                "rs184115031", "rs184115031",     # SPRY3, PAR2 — X and Y
                "rs779201129", "rs779201129",     # SPRY3, PAR2 — X and Y
                "rs376745839",                    # XG, past the PAR1 boundary — X only
            ],
            "chrom": ["X", "Y", "X", "Y", "X"],
            "start": [155773979, 56960499, 155773926, 56960446, 2782081],
            "ref": ["A", "A", "C", "C", "C"],
            "alt": ["G", "G", "T", "T", "T"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


_VARIANTS = (
    "rsid,genotype,state,conclusion,gene\n"
    "rs184115031,A/G,protective,ClinVar: benign,SPRY3\n"
    "rs779201129,C/T,risk,ClinVar: uncertain significance,SPRY3\n"
    "rs376745839,C/T,risk,ClinVar: uncertain significance,XG\n"
)
_STUDIES = "rsid,pmid\nrs184115031,25741868\nrs779201129,25741868\nrs376745839,25741868\n"


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (spec / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return spec


def _loci(result) -> dict[str, set[tuple[str, int]]]:
    out: dict[str, set[tuple[str, int]]] = {}
    for row in result.rows:
        out.setdefault(row.rsid or "", set()).add((row.chrom, row.start))
    return out


def test_enrich_records_one_row_per_par_finding(par_cache: Path, tmp_path: Path) -> None:
    result = enrich(_spec(tmp_path), offline=True, ensembl_cache=par_cache)
    assert _loci(result) == {
        "rs184115031": {("X", 155773979)},
        "rs779201129": {("X", 155773926)},
        "rs376745839": {("X", 2782081)},
    }
    # Three findings, three rows — the point of the change.
    assert len(result.rows) == 3


def test_keep_par_twin_records_both_contigs(par_cache: Path, tmp_path: Path) -> None:
    result = enrich(_spec(tmp_path), offline=True, ensembl_cache=par_cache, keep_par_twin=True)
    assert _loci(result) == {
        "rs184115031": {("X", 155773979), ("Y", 56960499)},
        "rs779201129": {("X", 155773926), ("Y", 56960446)},
        "rs376745839": {("X", 2782081)},          # still one — it is not a PAR locus
    }
    assert len(result.rows) == 5


def test_the_report_is_one_aggregated_line_not_one_per_locus(
    par_cache: Path, tmp_path: Path, caplog
) -> None:
    """Two PAR loci here and ten in the SHOX panel. A line each would bury every other finding —
    the aggregation rule this repo has needed four separate times."""
    with caplog.at_level(logging.INFO, logger="just_dna_enricher.enrich"):
        enrich(_spec(tmp_path), offline=True, ensembl_cache=par_cache)
    lines = [r.getMessage() for r in caplog.records if "Pseudoautosomal" in r.getMessage()]
    assert len(lines) == 1
    message = lines[0]
    assert "2 locus/loci" in message
    # It must name what was left out, why X won, and how to keep both.
    assert "rs184115031 Y:56960499" in message and "rs779201129 Y:56960446" in message
    assert "gnomAD excludes the Y PAR" in message and "--keep-par-twin" in message


def test_nothing_is_reported_when_no_locus_is_pseudoautosomal(tmp_path: Path, caplog) -> None:
    """The XG locus alone. A quiet run must stay quiet — a report on every module would train an
    author to ignore it."""
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame({"id": ["rs376745839"], "chrom": ["X"], "start": [2782081],
                  "ref": ["C"], "alt": ["T"]}).write_parquet(data / "chr.parquet")
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs376745839,C/T,risk,c,XG\n", encoding="utf-8"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs376745839,25741868\n", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="just_dna_enricher.enrich"):
        enrich(spec, offline=True, ensembl_cache=tmp_path / "cache")
    assert not [r for r in caplog.records if "Pseudoautosomal" in r.getMessage()]


def test_an_existing_resolution_row_is_still_authoritative(par_cache: Path, tmp_path: Path) -> None:
    """Selection runs on rows the chain resolves, never on rows a human wrote. Someone who has
    deliberately recorded both contigs keeps them without needing the flag."""
    spec = _spec(tmp_path)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs184115031,rs184115031,X,155773979,A,G,GRCh38,0,manual,resolved\n"
        "rs184115031,rs184115031,Y,56960499,A,G,GRCh38,1,manual,resolved\n",
        encoding="utf-8",
    )
    result = enrich(spec, offline=True, ensembl_cache=par_cache)
    assert _loci(result)["rs184115031"] == {("X", 155773979), ("Y", 56960499)}
