"""Resolution reaches the positional 0.4 tables, and the authored shape survives it (RM43).

`compile_module` resolved `variants.csv` and nothing else: every other table went through
`_build_table`, which is the model straight to parquet, so a module whose main table is
`pharm_variants.csv` or `haplotypes.csv` kept exactly the coordinates its author typed — which, for an
rs-number-authored module, is none. A consumer matching a patient VCF by position matched nothing,
silently, as an empty result rather than an error. `reference_examples/pgx_slco1b1_simvastatin` was in
that state on this tree: nine rows, every coordinate null, beside a `resolution.csv` that resolves the
rs-number perfectly well.

What is pinned here is the mechanism rather than the fact of the fill — the fact is in
`test_resolution_matrix.py`, where the positional cases sit in the same authored-shape × mishap grid
the SNP core does, under the same three-signature contract. This file covers the parts that could each
break silently:

* the stamped columns reach parquet and stay out of both the re-emitted CSV and `content_signature`;
* `alts` on a pharm row is **data**, not identity — the key is still derived without it;
* the fill refuses to pick among several loci, and refuses to complete a coordinate the row's own
  cells contradict;
* `reverse` rebuilds `resolution.csv` from the positional parquets, weights winning any shared key;
* a pre-0.6 parquet, which carries no `authored_ident`, reverses exactly as it used to;
* the fill and RM5's symbolic-allele drop meet on the same three tables, in the right order.

Expected values are computed from the fixtures at runtime.
"""

import csv
import io
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    _POSITIONAL_TABLE_KINDS,
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_compiler.resolution import resolve_positional_rows
from just_dna_format.base import authored_field_names, derive_variant_key
from just_dna_format.binning import HeteroplasmyRow
from just_dna_format.pgx import HaplotypeRow, PharmVariantRow
from just_dna_format.resolution import ResolutionRow
from pydantic import ValidationError

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_PGX = _EXAMPLES / "pgx_slco1b1_simvastatin"
_STARS = _EXAMPLES / "cyp2c19_star_alleles"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_RES_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
)
_PHARM_HEADER = "rsid,chrom,start,ref,gene,genotype,drug,conclusion\n"


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(path.read_text())))


def _resolution_row(
    rsid: str, chrom: str, start: int, ref: str, alts: str, locus_index: int
) -> ResolutionRow:
    return ResolutionRow(
        variant_key=rsid, rsid=rsid, chrom=chrom, start=start, ref=ref, alts=alts,
        genome_build="GRCh38", locus_index=locus_index, source="manual", status="resolved",
    )


def _pharm_module(
    directory: Path,
    *,
    pharm: str,
    resolution: str | None,
    genome_build: str = "GRCh38",
    variants: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(
        _YAML + f"genome_build: {genome_build}\n", encoding="utf-8"
    )
    (directory / "pharm_variants.csv").write_text(_PHARM_HEADER + pharm, encoding="utf-8")
    if variants is not None:
        (directory / "variants.csv").write_text(
            "rsid,chrom,start,ref,alts,genotype,state,conclusion\n" + variants, encoding="utf-8"
        )
        (directory / "studies.csv").write_text("rsid,pmid\nrs4149056,29165669\n", encoding="utf-8")
    if resolution is not None:
        (directory / "resolution.csv").write_text(_RES_HEADER + resolution, encoding="utf-8")
    return directory


def _compiled(spec: Path, out: Path, **kwargs) -> pl.DataFrame:
    result = compile_module(spec, out, **kwargs)
    assert result.success, result.errors
    return pl.read_parquet(out / "pharm_variants.parquet")


# ── the reported case ────────────────────────────────────────────────────────────────────────────


def test_the_reported_case_every_coordinate_arrives(tmp_path: Path) -> None:
    """Nine rows, every coordinate null, beside a resolution.csv that answers — the module the item
    was filed against. The expected coordinate is read out of the injected table, not pasted."""
    authored = _rows(_PGX / "pharm_variants.csv")
    assert all(not r.get("chrom") and not r.get("start") for r in authored), (
        "the fixture must be the rsid-only shape this item is about"
    )
    injected = {r["variant_key"]: r for r in _rows(_PGX / "resolution.csv")}

    df = _compiled(_PGX, tmp_path / "out")
    assert df.height == len(authored)
    for row in df.iter_rows(named=True):
        fact = injected[row["rsid"]]
        assert (row["chrom"], str(row["start"]), row["ref"], row["alts"]) == (
            fact["chrom"], fact["start"], fact["ref"], fact["alts"]
        )


def test_a_half_coordinate_is_completed_from_the_table(tmp_path: Path) -> None:
    """CPIC publishes a position on `sequence_location` and the chromosome on `gene`, so a drafted
    `haplotypes.csv` carries `start` with no `chrom` — a coordinate that looks like one and joins to
    nothing. The compiler now completes it, and only where the halves agree."""
    authored = _rows(_STARS / "haplotypes.csv")
    assert all(r.get("start") and not r.get("chrom") for r in authored), "the half-coordinate shape"
    injected = {r["variant_key"]: r for r in _rows(_STARS / "resolution.csv")}

    result = compile_module(_STARS, tmp_path / "out")
    assert result.success, result.errors
    df = pl.read_parquet(tmp_path / "out" / "haplotypes.parquet")
    for row in df.iter_rows(named=True):
        fact = injected[row["rsid"]]
        assert row["chrom"] == fact["chrom"]
        assert row["ref"] == fact["ref"]
        # …and the authored half is the authored half, untouched.
        assert str(row["start"]) == fact["start"]


# ── the stamped columns ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("model", [PharmVariantRow, HaplotypeRow], ids=lambda m: m.__name__)
def test_a_compiler_filled_alts_is_refused_rather_than_silently_dropped(model: type) -> None:
    """`alts` is authored on `variants.csv` and on `heteroplasmy.csv`, and compiler-filled here — so
    writing it by analogy is a plausible confusion, and it used to fail loudly through
    `extra="forbid"`. Adding the column silently *accepted* it: the value entered `authored_ident`,
    `_write_table_csv` then dropped it, and the round trip stopped being a fixed point. A new column
    may not turn a loud failure into a quiet one."""
    fields = {"rsid": "rs4149056", "alts": "C"}
    fields |= (
        {"haplotype_name": "*5", "allele": "C"}
        if model is HaplotypeRow
        else {"gene": "SLCO1B1", "genotype": "C/C", "drug": "simvastatin", "conclusion": "c"}
    )
    with pytest.raises(ValidationError, match="filled by the compiler on this table"):
        model(**fields)


def test_a_row_that_genuinely_authors_alts_is_untouched() -> None:
    """Keyed on the field's own marker, so the guard cannot reach a table where the column is real.
    `heteroplasmy.csv` authors `alts` and it is part of that model's key."""
    row = HeteroplasmyRow(
        gene="MT-TL1", chrom="MT", start=3243, ref="A", alts="G",
        reference_sequence="NC_012920.1", measure_min=0.0, measure_max=0.1, conclusion="x",
    )
    assert row.alts == "G" and "alts" in (row.authored_ident or [])


def test_a_stamped_key_is_overwritten_rather_than_refused() -> None:
    """The other half of the same rule, and the reason the guard is scoped to identity columns:
    `variant_key`/`authored_ident` are *stamped*, so an authored value is ignored and nothing is lost
    — `VariantRow` has tolerated exactly that since 0.5 on the no-foot-gun rule. A *filled* column is
    different, because ignoring it silently discards data the author wrote."""
    row = PharmVariantRow(
        rsid="rs4149056", gene="SLCO1B1", genotype="C/C", drug="simvastatin", conclusion="c",
        variant_key="not-this", authored_ident=["chrom"],
    )
    assert (row.variant_key, row.authored_ident) == ("rs4149056", ["rsid"])


@pytest.mark.parametrize(
    "model", [PharmVariantRow, HaplotypeRow, HeteroplasmyRow],
    ids=lambda m: m.__name__,
)
def test_every_positional_model_stamps_and_hides_its_identity(model: type) -> None:
    """The stamped columns exist on the model, and no surface that generates authored CSV offers one.

    A stamped column that reached a drafted header would produce a CSV the compiler then refuses to
    reload — `authored_ident` is a `list[str]`, and a rendered `rsid` cell does not reload as one.
    """
    stamped = {"variant_key", "authored_ident"}
    assert stamped <= set(model.model_fields), f"{model.__name__} must stamp both"
    assert not stamped & set(authored_field_names(model))


def test_the_stamped_columns_stay_out_of_the_content_signature(tmp_path: Path) -> None:
    """The acceptance criterion, demonstrated rather than asserted: a stamped value is a pure function
    of the authored cells, so it says nothing a *content* identity does not already have — and letting
    it in would move the signature of every published module carrying one of these tables, which is
    the one thing a content-dedup key may not do.

    Pinned two ways, because either alone is weak: the value is absent from `model_dump()` (which is
    what `integrity.content_signature` hashes), and two modules whose pharm rows differ only in the
    identity *spelling* — rsid-authored versus the same locus written out — hash differently, proving
    the signature still tracks the authored bytes rather than the stamped result.
    """
    row = PharmVariantRow(
        rsid="rs4149056", gene="SLCO1B1", genotype="C/C", drug="simvastatin", conclusion="c"
    )
    assert row.variant_key == "rs4149056" and row.authored_ident == ["rsid"]
    assert not {"variant_key", "authored_ident", "alts"} & set(row.model_dump())

    by_rsid = _pharm_module(
        tmp_path / "rsid",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
    )
    before = content_signature(by_rsid)
    assert compile_module(by_rsid, tmp_path / "out").success
    assert content_signature(by_rsid) == before, "compiling must not alter the authored identity"


def test_alts_is_filled_as_data_and_stays_out_of_the_key(tmp_path: Path) -> None:
    """`PharmVariantRow` gains `alts` so a consumer can join a VCF row directly (a VCF carries REF and
    ALT), and the key keeps ignoring it: a pharm annotation matches a variant at `chrom:start:ref`
    regardless of allele, which is what `_collect_subjects` deliberately chose. The roadmap's worry
    that adding the column "would make the key allele-specific" conflated the column with the key."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
    )
    df = _compiled(spec, tmp_path / "out")
    assert df["alts"].to_list() == ["C"]
    assert df["variant_key"].to_list() == ["rs4149056"]

    # …and the same holds for a coordinate-authored row, where the key could have absorbed the alt.
    coord = _pharm_module(
        tmp_path / "coord",
        pharm=",12,21178615,T,SLCO1B1,C/C,simvastatin,c\n",
        resolution=(
            f"{derive_variant_key(None, '12', 21178615, 'T')},rs4149056,12,21178615,T,C,"
            f"GRCh38,0,manual,resolved,\n"
        ),
    )
    coord_df = _compiled(coord, tmp_path / "coord-out")
    assert coord_df["alts"].to_list() == ["C"]
    assert coord_df["variant_key"].to_list() == [derive_variant_key(None, "12", 21178615, "T")]


def test_variant_key_joins_a_pharm_row_to_the_snp_core(tmp_path: Path) -> None:
    """The column exists so a consumer does not re-derive the precedence rule (rsid, else VA, else the
    coordinate key), which is exactly the kind of thing two implementations spell differently. Proven
    by joining, not by comparing strings to a constant."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        variants="rs4149056,,,,,C/C,risk,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
    )
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    weights = pl.read_parquet(out / "weights.parquet")
    pharm = pl.read_parquet(out / "pharm_variants.parquet")
    joined = pharm.join(weights, on="variant_key", how="inner")
    assert joined.height == pharm.height


# ── what the fill refuses to do ──────────────────────────────────────────────────────────────────


def test_several_loci_are_left_unplaced_rather_than_picked(tmp_path: Path) -> None:
    """A one-to-many rsID expands `variants.csv` into N coord-keyed rows. Doing that here would
    multiply a pharm annotation's `(variant_key, drug, genotype, …)` key across loci the author never
    named, so the row is left alone and the joinability line says why."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs999,,,,SLCO1B1,C/G,simvastatin,c\n",
        resolution=(
            "rs999,rs999,5,500,C,G,GRCh38,0,manual,resolved,\n"
            "rs999,rs999,6,600,C,G,GRCh38,1,manual,resolved,\n"
        ),
    )
    df = _compiled(spec, tmp_path / "out")
    assert df.height == 1
    assert df["chrom"].to_list() == [None] and df["start"].to_list() == [None]

    result = compile_module(spec, tmp_path / "out2")
    finding = [w for w in result.warnings if w.startswith("pharm_variants.csv:")]
    assert len(finding) == 1
    assert "at more than one locus" in finding[0]


def test_a_locus_the_genotype_contradicts_is_not_used(tmp_path: Path) -> None:
    """The same allele-aware filter resolution already applies: of two loci under one rsID, only the
    one that can host the row's own genotype is a candidate — so the fill has exactly one and takes
    it, instead of refusing over a locus the row was never about."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs999,,,,SLCO1B1,C/G,simvastatin,c\n",
        resolution=(
            "rs999,rs999,5,500,C,G,GRCh38,0,manual,resolved,\n"
            "rs999,rs999,6,600,A,T,GRCh38,1,manual,resolved,\n"
        ),
    )
    df = _compiled(spec, tmp_path / "out")
    assert (df["chrom"].to_list(), df["start"].to_list()) == (["5"], [500])


def test_an_authored_cell_the_table_contradicts_blocks_the_fill(tmp_path: Path) -> None:
    """Completing a half-coordinate from a locus whose `start` disagrees would build a coordinate no
    source ever stated. Reported, never repaired, and never fatal — the row is left as authored, which
    is the inject-only doctrine (report, never rewrite) rather than a mode ladder."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs4149056,,999,,SLCO1B1,C/C,simvastatin,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    df = pl.read_parquet(tmp_path / "out" / "pharm_variants.parquet")
    assert df["start"].to_list() == [999]
    assert df["chrom"].to_list() == [None], "no half of a contradicted coordinate is completed"
    assert [w for w in result.warnings if "contradicts the resolution table" in w]

    strict = compile_module(spec, tmp_path / "out-strict", strict=True)
    assert strict.success, strict.errors


def test_a_fully_placed_row_is_still_checked_against_the_table(tmp_path: Path) -> None:
    """A row with nothing left to fill can still contradict the table it is keyed into, and the
    promise is that such a disagreement is *reported*. Reachable on `heteroplasmy.csv`, the one
    positional model whose whole identity set is authorable — a mistyped `start` beside a disagreeing
    `resolution.csv` row would otherwise sit in silence, which is exactly what
    `resolve_from_table._verify` exists to catch on the SNP core."""
    rows = [
        PharmVariantRow(
            rsid="rs777", chrom="7", start=701, ref="C", gene="G", genotype="C/G", drug="d",
            conclusion="c",
        )
    ]
    report = resolve_positional_rows(
        rows, {"rs777": [_resolution_row("rs777", "7", 700, "C", "G", 0)]}
    )
    assert report.filled == 0
    assert len(report.contradicted) == 1
    assert "start=701" in report.contradicted[0]
    assert rows[0].start == 701, "reported, never repaired"


def test_a_locus_listing_more_alts_than_the_row_names_is_not_a_contradiction(tmp_path: Path) -> None:
    """A locus lists every ALT recorded there while a row names the one it is about, so `A,G` against
    `G` is agreement. Comparing `alts` by string equality would manufacture a finding about correct
    data; whether the allele can sit there is `hosting_verdict`'s three-valued question, already asked."""
    rows = [
        HeteroplasmyRow(
            gene="MT-TL1", chrom="MT", start=3243, ref="A", alts="G",
            reference_sequence="NC_012920.1", measure_min=0.0, measure_max=0.1, conclusion="x",
        )
    ]
    key = rows[0].variant_key
    assert key is not None
    table = {
        key: [
            ResolutionRow(
                variant_key=key, rsid="rs199474657", chrom="MT", start=3243, ref="A", alts="A,G",
                genome_build="GRCh38", locus_index=0, source="manual", status="resolved",
            )
        ]
    }
    report = resolve_positional_rows(rows, table)
    assert report.contradicted == []
    assert rows[0].rsid == "rs199474657", "the one empty identity cell is filled"
    assert rows[0].alts == "G", "and the authored allele is never overwritten"


def test_a_non_grch38_module_is_skipped_and_says_so(tmp_path: Path) -> None:
    """`resolve_from_table` refuses a non-GRCh38 module outright (RM15) — the identity minting behind
    these keys is GRCh38-only — so joining the positional tables there would place rows against loci
    this tier has no way to re-derive a key for. Same skip, same shape of warning."""
    spec = _pharm_module(
        tmp_path / "spec",
        genome_build="GRCh37",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh37,0,manual,resolved,\n",
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    df = pl.read_parquet(tmp_path / "out" / "pharm_variants.parquet")
    assert df["chrom"].to_list() == [None]
    assert [w for w in result.warnings if "Positional-table fill skipped" in w]


def test_no_resolve_switches_the_positional_fill_off_too(tmp_path: Path) -> None:
    """The flag is the master switch for resolution of every kind, and it must stay one switch: a
    caller who asked to consult nothing must not find one table quietly joined.

    And the pre-flight must answer the same way. `validate_spec` takes the flag for exactly this: it
    decides whether these rows read as unjoinable, so a `validate` that ignored it would be the more
    *optimistic* of the two commands — the disagreement direction the parity rule exists to prevent."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n",
    )
    df = _compiled(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert df["chrom"].to_list() == [None]

    unjoinable = [w for w in validate_spec(spec).warnings if "joins by rsID only" in w]
    assert not unjoinable, "with resolution on, the row is placed and nothing is reported"
    off = [
        w
        for w in validate_spec(spec, resolve_with_ensembl=False).warnings
        if "joins by rsID only" in w
    ]
    assert len(off) == 1
    result = compile_module(spec, tmp_path / "out2", resolve_with_ensembl=False)
    assert off == [w for w in result.warnings if "joins by rsID only" in w]


@pytest.mark.parametrize(
    ("kwargs", "genome_build"),
    [({"resolve_with_ensembl": False}, "GRCh38"), ({}, "GRCh37")],
    ids=["no-resolve", "non-grch38"],
)
def test_an_unconsulted_table_is_never_reported_as_a_refusal_to_pick(
    tmp_path: Path, kwargs: dict, genome_build: str
) -> None:
    """The reason sentence ships inside `manifest.compilation.warnings`, beside `UNJOINABLE_PHRASE`,
    which is a published consumer surface (RM44) — so it may not assert "the compiler looked and would
    not pick" about a lookup that never happened. Both gates that skip the fill must say so instead,
    and this fixture has exactly one clean, non-contradicting locus, so the claim would be false."""
    spec = _pharm_module(
        tmp_path / "spec",
        genome_build=genome_build,
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        resolution=f"rs4149056,rs4149056,12,21178615,T,C,{genome_build},0,manual,resolved,\n",
    )
    result = compile_module(spec, tmp_path / "out", **kwargs)
    assert result.success, result.errors
    finding = [w for w in result.manifest.compilation.warnings if "joins by rsID only" in w]
    assert len(finding) == 1
    assert "was not consulted for this table" in finding[0]
    assert "leaves them unplaced rather than picking" not in finding[0]


# ── reverse ──────────────────────────────────────────────────────────────────────────────────────


def test_reverse_re_emits_the_authored_shape_not_the_filled_one(tmp_path: Path) -> None:
    """A machine-filled coordinate coming back as an *authored* one is the failure `authored_ident`
    exists to prevent — it moves `content_signature`, so the module stops matching itself."""
    out = tmp_path / "out"
    assert compile_module(_PGX, out).success
    reverse_module(out, tmp_path / "rev")

    authored = _rows(_PGX / "pharm_variants.csv")
    reversed_rows = _rows(tmp_path / "rev" / "pharm_variants.csv")
    assert len(reversed_rows) == len(authored)
    for before, after in zip(authored, reversed_rows, strict=True):
        assert after["rsid"] == before["rsid"]
        assert (after["chrom"], after["start"], after["ref"]) == ("", "", "")
    assert "alts" not in reversed_rows[0], "a parquet-only column is never re-emitted"


def test_reverse_rebuilds_the_lookup_table_for_a_table_only_module(tmp_path: Path) -> None:
    """The forced consequence. Without it the reversed spec has no `resolution.csv` at all — a PGx
    module carries no `weights.parquet` for the old writer to read — so the recompile leaves every
    coordinate unfilled and `compile → reverse → compile` stops reproducing the artifact (P7).

    The facts are compared against the injected table's own, restricted to what a reversed table can
    carry: provenance columns are outside the fact set by design and cannot be recovered.
    """
    out = tmp_path / "out"
    assert compile_module(_PGX, out).success
    reverse_module(out, tmp_path / "rev")

    rebuilt = tmp_path / "rev" / "resolution.csv"
    assert rebuilt.is_file()
    facts = {
        (r["variant_key"], r["rsid"], r["chrom"], r["start"], r["ref"], r["alts"])
        for r in _rows(rebuilt)
    }
    injected = {
        (r["variant_key"], r["rsid"], r["chrom"], r["start"], r["ref"], r["alts"])
        for r in _rows(_PGX / "resolution.csv")
    }
    assert facts == injected
    assert {r["source"] for r in _rows(rebuilt)} == {"reversed"}


def test_the_rebuilt_table_is_filed_under_the_key_the_fill_looks_up(tmp_path: Path) -> None:
    """The positional pass writes the parquet's **stored** `variant_key`, not a recomputation.

    A coordinate-authored pharm row keys on `12:21178615:T` — its model omits `alts` from the key —
    while recomputing from `authored_ident` sees an authored `alts` and mints a `ga4gh:VA.…` instead.
    Two spellings of one key: the reverse filed the fact under an id the next fill never looks up, so
    the recompile left the row unfilled. The alts policy lives on the model, and the stored column is
    the only place it survives into the artifact.
    """
    spec = _pharm_module(
        tmp_path / "spec",
        pharm=",12,21178615,T,SLCO1B1,C/C,simvastatin,c\n",
        resolution=(
            f"{derive_variant_key(None, '12', 21178615, 'T')},rs4149056,12,21178615,T,C,"
            f"GRCh38,0,manual,resolved,\n"
        ),
    )
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    before = pl.read_parquet(out / "pharm_variants.parquet")
    reverse_module(out, tmp_path / "rev")

    rebuilt = _rows(tmp_path / "rev" / "resolution.csv")
    assert [r["variant_key"] for r in rebuilt] == before["variant_key"].to_list()

    second = compile_module(tmp_path / "rev", tmp_path / "out2")
    assert second.success, second.errors
    after = pl.read_parquet(tmp_path / "out2" / "pharm_variants.parquet")
    assert after["alts"].to_list() == before["alts"].to_list() == ["C"]
    assert after["rsid"].to_list() == before["rsid"].to_list() == ["rs4149056"]


def test_weights_own_a_key_the_positional_tables_also_name(tmp_path: Path) -> None:
    """`variants.csv` is the only table carrying `alts` as an *authored* fact, so it wins any shared
    key — the same precedence `enrich._collect_subjects` uses, for the same reason. And one row per
    key, or the next compile reads two rows as a one-to-many rsID and enters the expansion path."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n",
        variants="rs4149056,,,,,C/C,risk,c\n",
        resolution="rs4149056,rs4149056,12,21178615,T,\"A,C\",GRCh38,0,manual,resolved,\n",
    )
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    reverse_module(out, tmp_path / "rev")

    rebuilt = _rows(tmp_path / "rev" / "resolution.csv")
    assert len(rebuilt) == 1
    assert rebuilt[0]["alts"] == "A,C", "the SNP core's authored allele list, not the pharm row's"
    assert rebuilt[0]["locus_index"] == "0"


def test_a_module_that_resolved_nothing_gets_no_lookup_table(tmp_path: Path) -> None:
    """Writing a header-only `resolution.csv` into a reversed spec that never had one would invent a
    derived sidecar out of an absence."""
    spec = _pharm_module(
        tmp_path / "spec", pharm="rs4149056,,,,SLCO1B1,C/C,simvastatin,c\n", resolution=None
    )
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    reverse_module(out, tmp_path / "rev")
    assert not (tmp_path / "rev" / "resolution.csv").exists()


def test_a_pre_0_6_parquet_reverses_exactly_as_it_used_to(tmp_path: Path) -> None:
    """An artifact compiled before the stamped columns existed carries no `authored_ident`, so there
    is nothing to say which cells were authored — and the honest answer is to blank none of them,
    which is what the old writer did."""
    spec = _pharm_module(
        tmp_path / "spec",
        pharm=",12,21178615,T,SLCO1B1,C/C,simvastatin,c\n",
        resolution=None,
    )
    out = tmp_path / "out"
    assert compile_module(spec, out).success
    legacy = pl.read_parquet(out / "pharm_variants.parquet").drop(
        "variant_key", "authored_ident", "alts"
    )
    legacy.write_parquet(out / "pharm_variants.parquet")

    reverse_module(out, tmp_path / "rev")
    row = _rows(tmp_path / "rev" / "pharm_variants.csv")[0]
    assert (row["chrom"], row["start"], row["ref"]) == ("12", "21178615", "T")


# ── the report ───────────────────────────────────────────────────────────────────────────────────


def test_the_fill_reports_the_three_outcomes_separately() -> None:
    """`resolve_positional_rows` is public and returns counts rather than a verdict, because "the
    table places this row", "it names several loci and I will not pick" and "nothing names it" are
    three answers, and one number reporting the last two together says neither. The compiler's own
    warning splits on exactly this, and a caller driving the fill directly gets the same split."""
    rows = [
        PharmVariantRow(rsid=rsid, gene="G", genotype="C/G", drug="d", conclusion="c")
        for rsid in ("rs777", "rs999", "rs111")
    ]
    table = {
        "rs777": [_resolution_row("rs777", "7", 700, "C", "G", 0)],
        "rs999": [
            _resolution_row("rs999", "5", 500, "C", "G", 0),
            _resolution_row("rs999", "6", 600, "C", "G", 1),
        ],
    }
    report = resolve_positional_rows(rows, table)
    assert (report.filled, report.unplaced_ambiguous, report.unplaced_absent) == (1, 1, 1)
    assert report.contradicted == []
    placed = [r for r in rows if r.chrom is not None]
    assert [r.rsid for r in placed] == ["rs777"]

    # …and running it again changes nothing: the fill only ever writes into an empty cell.
    again = resolve_positional_rows(rows, table)
    assert (again.filled, again.unplaced_ambiguous, again.unplaced_absent) == (0, 1, 1)


# ── where RM43 meets RM5 ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("model", "fields", "expected_authored"),
    [
        (
            HaplotypeRow,
            {"haplotype_name": "*5", "chrom": "22", "start": 42126499, "ref": "C",
             "allele": "<DEL:1500>", "gene": "CYP2D6"},
            ["chrom", "start", "ref"],
        ),
        (
            PharmVariantRow,
            {"chrom": "22", "start": 42126499, "ref": "C", "gene": "CYP2D6",
             "genotype": "<DEL:1500>/C", "drug": "codeine", "conclusion": "c"},
            ["chrom", "start", "ref"],
        ),
        (
            HeteroplasmyRow,
            {"gene": "MT-TL1", "chrom": "MT", "start": 3243, "ref": "A", "alts": "<DEL:20>",
             "reference_sequence": "NC_012920.1", "measure_min": 0.0, "measure_max": 0.1,
             "conclusion": "x"},
            ["chrom", "start", "ref", "alts"],
        ),
    ],
    ids=lambda v: v.__name__ if isinstance(v, type) else "",
)
def test_a_symbolic_allele_keys_by_coordinate_and_mints_no_va(
    model: type, fields: dict, expected_authored: list[str]
) -> None:
    """A symbolic allele names a variant whose sequence is deliberately unspelled, so it falls through
    to the coordinate key — a content-addressed VA is a digest *of* the sequence and there is none to
    digest. Neither lane had a test for the two meeting, and the stamped columns are where they do.

    `HeteroplasmyRow` is the case that could actually have gone wrong: it is the one positional model
    whose key includes `alts`, so a `<DEL:20>` reaches `derive_variant_key`'s minting branch and has to
    fall through it rather than produce an id for a sequence nobody stated.
    """
    row = model(**fields)
    assert row.authored_ident == expected_authored
    assert not str(row.variant_key).startswith("ga4gh:VA.")
    assert row.variant_key == derive_variant_key(
        None,
        fields["chrom"],
        fields["start"],
        fields["ref"],
        fields["alts"] if type(row)._KEY_INCLUDES_ALTS else None,
    )


def test_a_dropped_row_is_never_filled_and_never_counted(tmp_path: Path) -> None:
    """RM5 drops a `pharm_variants.csv` row carrying a lengthless symbolic allele; RM43 fills
    coordinates into the same table. The drop decides which rows exist, so it must land first — filling
    a row about to be discarded is wasted at best, and counting it in the joinability line reports a
    coordinate gap over a row the artifact does not contain.

    Pinned on the observable consequence rather than on call order: the surviving row is placed, the
    dropped one is absent from the parquet, and neither command claims anything unjoinable.
    """
    spec = _pharm_module(
        tmp_path / "spec",
        pharm=(
            "rs4149056,,,,SLCO1B1,C/C,simvastatin,keeps\n"
            "rs2306283,,,,SLCO1B1,<DEL>/C,simvastatin,dropped\n"
        ),
        resolution=(
            "rs4149056,rs4149056,12,21178615,T,C,GRCh38,0,manual,resolved,\n"
            "rs2306283,rs2306283,12,21176879,A,G,GRCh38,0,manual,resolved,\n"
        ),
    )
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert [w for w in result.warnings if "DROPPED" in w], "RM5 must say it dropped the row"

    df = pl.read_parquet(tmp_path / "out" / "pharm_variants.parquet")
    assert df["conclusion"].to_list() == ["keeps"], "the dropped row reaches no parquet"
    assert (df["chrom"].to_list(), df["start"].to_list()) == (["12"], [21178615])

    # Neither command reports a coordinate gap: the survivor is placed, and the dropped row is not a
    # row the report may speak about at all.
    assert not [w for w in result.warnings if "joins by rsID only" in w]
    assert not [w for w in validate_spec(spec).warnings if "joins by rsID only" in w]


def test_a_haplotype_row_is_refused_before_anything_is_filled(tmp_path: Path) -> None:
    """On `haplotypes.csv` the symbolic finding is fatal in both modes — dropping a defining variant
    makes a quietly *different* haplotype rather than a smaller module. The compile must refuse, and
    refuse before writing, so the fill never runs on a module that has none."""
    spec = tmp_path / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML + "genome_build: GRCh38\n", encoding="utf-8")
    (spec / "haplotypes.csv").write_text(
        "haplotype_name,rsid,allele,gene\n*5,rs3892097,<DEL>,CYP2D6\n", encoding="utf-8"
    )
    (spec / "resolution.csv").write_text(
        _RES_HEADER + "rs3892097,rs3892097,22,42128945,C,T,GRCh38,0,manual,resolved,\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = compile_module(spec, out)
    assert not result.success
    assert any("fatal in both modes" in e for e in result.errors)
    assert not out.exists(), "a refusal must leave no half-written artifact"


# ── the set itself ───────────────────────────────────────────────────────────────────────────────


def test_the_positional_set_is_exactly_the_three_tables_lane_a_covers() -> None:
    """Derived from the models — a table is positional exactly when it declares both `chrom` and
    `start` — and deliberately still three. Adding `repeat_alleles`/`copynumbers` is 0.7 work gated on
    a real caller VCF, not something this fill should acquire by accident."""
    assert {csv_name for csv_name, _model in _POSITIONAL_TABLE_KINDS} == {
        "heteroplasmy.csv", "haplotypes.csv", "pharm_variants.csv"
    }
