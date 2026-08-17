"""The 0.6 GWAS-effect sidecar in the compiler (RM90, `gwas_effects.csv`).

The same properties `test_derived_validity_assertions.py` pins for RM24/RM25, because they are what
decide whether a derived table is safe to add at all: a module without it is byte-identical to before,
a module with it holds genuinely more content while the SNP core's own bytes never move, and
`compile → reverse → compile` is a fixed point on the parquet and the signature (Principle 7).

Plus the two findings this table exists to make visible, checked as differences rather than as fields
that happen to exist:

* **the unit set**, because a beta in `umol/l` and a beta in the Catalog's uninformative `unit` are not
  on one scale, and a table storing the magnitude without the unit would reproduce S36's defect one
  layer down; and
* **the associations naming no effect allele**, which the Catalog writes as `rs4149056-?` and which are
  real evidence that cannot be used as a weight.

Every row below is a real GWAS Catalog association, taken from the REST API on 2026-08-17 — including
the two `-?` rows and the `umol/l`/`unit` disagreement, which are not contrived and are the reason the
columns exist.
"""

from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.integrity import gwas_effect_signature

_YAML = """\
schema_version: "1.0"
module:
  name: demo_gwas
  title: GWAS effects
  description: The 0.6 GWAS-effect sidecar
  report_title: GWAS effects
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
"""

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "rs1801133,1,11796321,G,A,A/A,risk,MTHFR C677T homozygote,MTHFR\n"
    "rs4149056,12,21178615,T,C,C/T,risk,SLCO1B1 reduced function,SLCO1B1\n"
)

_STUDIES = (
    "rsid,pmid,conclusion\n"
    "rs1801133,16199547,MTHFR C677T and homocysteine\n"
    "rs4149056,16199547,SLCO1B1 and statin exposure\n"
)

_HEADER = (
    "association_id,variant_key,rsid,effect_allele,effect_size,effect_measure,effect_unit,"
    "effect_direction,standard_error,confidence_interval,risk_allele_frequency,p_value,"
    "p_value_num,trait,trait_efo_id,pmid,study_accession,ancestry,dataset,source,status,fetched_at\n"
)

#: Real associations. Note what they disagree about: association 13069 reports a beta in `umol/l`
#: while 55421052 and 34944434 report one in `unit`, and the latter two name **no effect allele** —
#: the Catalog wrote `rs4149056-?`. One variant, three incompatible scales, two unusable rows.
_GWAS = _HEADER + (
    "13069,rs4149056,rs4149056,C,0.05,beta,umol/l,increase,,[0.03-0.07],0.15,7.0E-13,7.0e-13,"
    "Bilirubin levels,EFO_0004570,16199547,GCST000001,European,gwas_catalog_2026-08-01,"
    "gwas_catalog,resolved,\n"
    "55421052,rs4149056,rs4149056,,0.3017178,beta,unit,increase,0.0467972,[0.21-0.39],,1.0E-10,"
    "1.0e-10,Statin-induced myopathy,EFO_0009999,16199547,GCST000002,European,"
    "gwas_catalog_2026-08-01,gwas_catalog,resolved,\n"
    "34944434,rs4149056,rs4149056,,0.141,beta,unit,increase,,[NR],,5.0E-22,5.0e-22,"
    "Statin exposure,EFO_0009999,16199547,GCST000003,European,gwas_catalog_2026-08-01,"
    "gwas_catalog,resolved,\n"
    "12345,rs1801133,rs1801133,A,0.1583,beta,unit,increase,0.007,[0.14-0.17],0.31,4.0E-104,"
    "4.0e-104,Homocysteine levels,EFO_0004578,16199547,GCST000004,European,"
    "gwas_catalog_2026-08-01,gwas_catalog,resolved,\n"
)


def _spec(tmp_path: Path, *, gwas: bool = False, rows: str | None = None) -> Path:
    spec = tmp_path / f"spec_{int(gwas)}"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if gwas:
        (spec / "gwas_effects.csv").write_text(rows if rows is not None else _GWAS)
    return spec


def _compile(spec: Path, out: Path):
    return compile_module(spec, out, resolve_with_ensembl=False)


# ── additive: a module without it does not move ─────────────────────────────────────────────────


def test_a_module_without_the_sidecar_keeps_its_snp_core_byte_identical(tmp_path: Path) -> None:
    """The additive property, checked on bytes rather than asserted from the charter."""
    without = _compile(_spec(tmp_path, gwas=False), tmp_path / "o0")
    with_it = _compile(_spec(tmp_path, gwas=True), tmp_path / "o1")
    assert without.success and with_it.success, (without.errors, with_it.errors)
    for parquet in ("weights.parquet", "annotations.parquet", "studies.parquet"):
        assert (tmp_path / "o0" / parquet).read_bytes() == (tmp_path / "o1" / parquet).read_bytes()
    assert without.manifest.gwas_effects is None


def test_carrying_the_sidecar_changes_the_artifact_digest(tmp_path: Path) -> None:
    """Different content, different artifact — which is correct, not a regression to avoid."""
    without = _compile(_spec(tmp_path, gwas=False), tmp_path / "o0")
    with_it = _compile(_spec(tmp_path, gwas=True), tmp_path / "o1")
    assert without.manifest.artifact.digest != with_it.manifest.artifact.digest
    # ...while the AUTHORED identity is untouched: a derived sidecar is not authored content.
    assert without.manifest.content_signature == with_it.manifest.content_signature


def test_the_sidecar_is_fact_hashed_not_byte_hashed(tmp_path: Path) -> None:
    """It must not appear in `manifest.inputs`, or a re-run with a new `fetched_at` reads as tampering."""
    result = _compile(_spec(tmp_path, gwas=True), tmp_path / "out")
    assert "gwas_effects.csv" not in {f.name for f in result.manifest.inputs}
    assert result.manifest.gwas_effects.signature is not None
    # ...but it IS transported, byte-hashed, in `manifest.derived` (S26).
    assert any("gwas_effects.csv" in f.name for f in result.manifest.derived)


# ── the grain, and the two things the block exists to publish ───────────────────────────────────


def test_one_row_is_one_association_not_one_variant(tmp_path: Path) -> None:
    """rs4149056 carries three associations here and dozens in the real Catalog. Collapsing them
    would pick a trait on the author's behalf."""
    result = _compile(_spec(tmp_path, gwas=True), tmp_path / "out")
    block = result.manifest.gwas_effects
    assert block.row_count == 4
    assert block.variant_count == 2


def test_the_manifest_publishes_the_unit_set(tmp_path: Path) -> None:
    """The facet that decides whether these effects can be pooled at all.

    Two units here, from one real variant. A consumer reading only `row_count` would have no way to
    know that averaging these betas is meaningless — which is the S36 defect, one layer down.
    """
    result = _compile(_spec(tmp_path, gwas=True), tmp_path / "out")
    assert result.manifest.gwas_effects.units == ["umol/l", "unit"]
    assert result.manifest.gwas_effects.measures == ["beta"]


def test_associations_naming_no_effect_allele_are_counted_not_dropped(tmp_path: Path) -> None:
    """`rs4149056-?` is real evidence that cannot be used as a weight.

    Counted beside its complement rather than filtered, because a consumer that silently dropped
    these and one that silently kept them would both be wrong and neither would be visible.
    """
    result = _compile(_spec(tmp_path, gwas=True), tmp_path / "out")
    block = result.manifest.gwas_effects
    assert block.without_effect_allele == 2
    assert block.with_effect_allele == 2
    assert block.with_effect_allele + block.without_effect_allele == block.row_count
    # The rows survive into the parquet — counted is not dropped.
    frame = pl.read_parquet(tmp_path / "out" / "gwas_effects.parquet")
    assert frame.height == 4


def test_a_null_effect_allele_is_not_an_empty_string(tmp_path: Path) -> None:
    """The house algebra: the source said "unknown", and that must not read as a stated allele."""
    assert _compile(_spec(tmp_path, gwas=True), tmp_path / "out").success
    frame = pl.read_parquet(tmp_path / "out" / "gwas_effects.parquet")
    unknown = frame.filter(pl.col("association_id") == "55421052")
    assert unknown["effect_allele"].to_list() == [None]


# ── Principle 7 ─────────────────────────────────────────────────────────────────────────────────


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec(tmp_path, gwas=True)
    first = _compile(spec, tmp_path / "a1")
    assert first.success, first.errors

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = _compile(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors

    assert (tmp_path / "a1" / "gwas_effects.parquet").read_bytes() == (
        tmp_path / "a2" / "gwas_effects.parquet"
    ).read_bytes()
    assert first.manifest.gwas_effects.signature == second.manifest.gwas_effects.signature


def test_the_reversed_csv_carries_every_column_the_model_declares(tmp_path: Path) -> None:
    """The touch point that gets missed. `_write_table_csv` derives its fieldnames from the model, so
    this should hold by construction — asserted anyway, because "by construction" is what the reverse
    `fieldnames` list for `studies.csv` also looked like until a column went missing from it."""
    spec = _spec(tmp_path, gwas=True)
    _compile(spec, tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    import csv

    with open(tmp_path / "rev" / "gwas_effects.csv", newline="") as fh:
        header = next(csv.reader(fh))
    assert set(header) == set(GwasEffectRow.model_fields)


def test_the_fact_hash_ignores_provenance_but_not_the_unit(tmp_path: Path) -> None:
    """Two properties in one place, because they are the same design decision seen from both sides.

    A re-run that only restamps `fetched_at` must hash equal — that is why the sidecar is fact-hashed
    rather than byte-hashed. A row whose `effect_unit` changed must **not**, because the unit is what
    the magnitude means.
    """
    base = [GwasEffectRow(**r) for r in _rows()]
    restamped = [r.model_copy(update={"fetched_at": "2027-01-01T00:00:00Z"}) for r in base]
    assert gwas_effect_signature(base) == gwas_effect_signature(restamped)

    moved_unit = [r.model_copy(update={"effect_unit": "mg/dl"}) for r in base]
    assert gwas_effect_signature(base) != gwas_effect_signature(moved_unit)


def test_the_descriptive_trait_label_does_not_move_the_hash(tmp_path: Path) -> None:
    """`trait` is outside the fact set on `gene_validity`'s rule — a column that *describes* an
    assertion is not the assertion. The Catalog re-words a trait between releases for an unchanged
    `trait_efo_id`, and that churn must not read as new evidence."""
    base = [GwasEffectRow(**r) for r in _rows()]
    reworded = [r.model_copy(update={"trait": "Type II diabetes mellitus"}) for r in base]
    assert gwas_effect_signature(base) == gwas_effect_signature(reworded)


def test_the_fact_hash_is_order_independent(tmp_path: Path) -> None:
    base = [GwasEffectRow(**r) for r in _rows()]
    assert gwas_effect_signature(base) == gwas_effect_signature(list(reversed(base)))


def _rows() -> list[dict]:
    return [
        {
            "association_id": "13069",
            "variant_key": "rs4149056",
            "rsid": "rs4149056",
            "effect_allele": "C",
            "effect_size": 0.05,
            "effect_measure": "beta",
            "effect_unit": "umol/l",
            "effect_direction": "increase",
            "trait": "Bilirubin levels",
            "trait_efo_id": "EFO_0004570",
            "dataset": "gwas_catalog_2026-08-01",
            "source": "gwas_catalog",
            "status": "resolved",
            "fetched_at": "2026-08-17T00:00:00Z",
        }
    ]


# ── refusals, orphans, and the ordering guard ───────────────────────────────────────────────────


def test_an_invalid_row_is_a_compile_error(tmp_path: Path) -> None:
    """`effect_direction` is closed: 'up' is not a member, and a silently-dropped cell would leave the
    table asserting a direction it does not hold."""
    spec = _spec(tmp_path, gwas=True, rows=_GWAS.replace(",beta,umol/l,increase,", ",beta,umol/l,up,"))
    result = _compile(spec, tmp_path / "out")
    assert not result.success
    assert any("effect_direction" in e for e in result.errors)


def test_validate_refuses_what_compile_refuses(tmp_path: Path) -> None:
    """Both loops iterate `_FACT_TABLES`, so a new table joins both at once — asserted, not assumed."""
    spec = _spec(tmp_path, gwas=True, rows=_GWAS.replace(",beta,umol/l,increase,", ",beta,umol/l,up,"))
    validation = validate_spec(spec)
    compilation = _compile(spec, tmp_path / "out")
    assert not validation.valid and not compilation.success
    assert any("effect_direction" in e for e in validation.errors)


def test_orphan_rows_warn_but_do_not_fail(tmp_path: Path) -> None:
    """An over-broad sidecar is the ordinary result of narrowing a module's variant list after
    enriching it, and must not fail a compile that is otherwise fine."""
    extra = (
        "99999,rs9999999,rs9999999,A,1.2,OR,,increase,,,,1.0E-8,1.0e-8,Something else,"
        "EFO_0000001,16199547,GCST999999,European,gwas_catalog_2026-08-01,gwas_catalog,resolved,\n"
    )
    spec = _spec(tmp_path, gwas=True, rows=_GWAS + extra)
    result = _compile(spec, tmp_path / "out")
    assert result.success, result.errors
    assert any("gwas_effects.csv carries associations" in w and "rs9999999" in w for w in result.warnings)


def test_the_licence_row_for_the_new_layer_is_not_reported_as_an_orphan(tmp_path: Path) -> None:
    """`sources.csv` must stay LAST in `_FACT_TABLES`, and this is what notices if it does not.

    The compile loop stores each model's rows before running the next model's check, and
    `_sources_checks` reads that store to decide which declared sources a table actually used. A fact
    table registered *after* `sources.csv` is invisible to it, and every module carrying one would be
    told its own licence row is stale.
    """
    spec = _spec(tmp_path, gwas=True)
    (spec / "licensing.csv").write_text(
        "source,layer,license,license_url,license_sha256,attribution,notice,share_alike,"
        "commercial_use,redistribution,declared_use,dataset,fetched_at\n"
        "gwas_catalog,gwas_effect,,,,NHGRI-EBI GWAS Catalog,,,,true,unstated,,\n"
    )
    result = _compile(spec, tmp_path / "out")
    assert result.success, result.errors
    assert not [w for w in result.warnings if "no table in this module uses" in w]
    assert result.manifest.sources.layers == ["gwas_effect"]
